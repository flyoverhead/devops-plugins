#!/usr/bin/env python3
"""Mechanical scope guard for the code-improver loop (stdlib only).

Records a baseline (HEAD sha, pinned scope, untracked files and git metadata
with git blob hashes) and later reports every working-tree change that falls
outside that scope, plus commits, stashes and hidden index flags.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HASH_CAP = 50
STATE = "baseline.json"
DIFF = ("diff", "--no-ext-diff", "--no-textconv", "--no-color")

USAGE = """\
scope_guard.py init     --repo DIR --out DIR --scope GLOB ... [--plugin-version X.Y.Z]
scope_guard.py check    --out DIR --scope GLOB ...
scope_guard.py snapshot --out DIR --name FILE.diff
scope_guard.py match    --scope GLOB ... -- PATH ...

Globs are repo-relative: ** spans directories, * stays inside one path
segment, every other character is literal. check must get the scope that
init pinned.
Exit codes: 0 ok, 1 scope violation, 2 bad usage, 3 precondition or git failure.
"""


class Stop(Exception):
    def __init__(self, code, payload):
        super().__init__(payload)
        self.code = code
        self.payload = payload


def glob_regex(glob):
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def in_scope(path, patterns):
    return any(p.match(path) for p in patterns)


def git(root, *args, ok_codes=(0,)):
    res = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if res.returncode not in ok_codes:
        raise Stop(3, {"error": "git-failed", "command": "git " + " ".join(args),
                       "stderr": res.stderr.decode(errors="replace").strip()})
    return res.stdout


def zlist(raw):
    return [p for p in raw.decode(errors="surrogateescape").split("\0") if p]


def blob_hash(path):
    try:
        data = os.readlink(path).encode() if os.path.islink(path) else Path(path).read_bytes()
    except OSError:
        return None
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def untracked(root):
    return sorted(zlist(git(root, "ls-files", "--others", "--exclude-standard", "-z")))


def hidden_flags(root):
    entries = []
    for line in zlist(git(root, "ls-files", "-v", "-z")):
        tag, _, path = line.partition(" ")
        if tag == "S" or (tag.isalpha() and tag.islower()):
            entries.append(path)
    return sorted(entries)


def git_meta(root):
    common = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip())
    own = Path(git(root, "rev-parse", "--absolute-git-dir").decode().strip())
    found = {".git/config": common / "config"}
    if (common / "hooks").is_dir():
        found.update({f".git/hooks/{p.name}": p for p in sorted((common / "hooks").iterdir()) if p.is_file()})
    found[".git/config.worktree" if own == common else
          f".git/worktrees/{own.name}/config.worktree"] = own / "config.worktree"
    return {label: blob_hash(path) for label, path in found.items()}


def head_sha(root):
    return git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}").decode().strip()


def stash_sha(root):
    return git(root, "rev-parse", "--verify", "--quiet", "refs/stash", ok_codes=(0, 1)).decode().strip()


def skip_prefix(root, out):
    try:
        rel = Path(out).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return None
    return rel.as_posix().rstrip("/") + "/"


def keeper(root, out):
    skip = skip_prefix(root, out)
    return (lambda p: not p.startswith(skip)) if skip else (lambda p: True)


def tree_digest(root, sha, keep):
    digest = hashlib.sha256(git(root, *DIFF, "--binary", sha))
    for path in (p for p in untracked(root) if keep(p)):
        digest.update(("\0%s\0%s" % (path, blob_hash(os.path.join(root, path)))).encode())
    return digest.hexdigest()


def parse(argv):
    if not argv or argv[0] in {"-h", "--help"}:
        raise Stop(2, None)
    cmd, opts, paths, key = argv[0], {"scope": []}, [], None
    rest = argv[1:]
    if "--" in rest:
        cut = rest.index("--")
        rest, paths = rest[:cut], rest[cut + 1:]
    for tok in rest:
        if tok in {"--repo", "--out", "--name", "--scope", "--plugin-version"}:
            key = tok[2:]
        elif key == "scope":
            opts["scope"].append(tok)
        elif key and key not in opts:
            opts[key] = tok
            key = None
        else:
            raise Stop(2, None)
    need = {"init": {"repo", "out"}, "check": {"out"}, "snapshot": {"out", "name"},
            "match": set()}
    if cmd not in need or not need[cmd] <= opts.keys():
        raise Stop(2, None)
    if cmd in {"init", "check", "match"} and not opts["scope"]:
        raise Stop(2, None)
    if cmd == "match" and not paths:
        raise Stop(2, None)
    return cmd, opts, paths


def load_state(out):
    path = Path(out) / STATE
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        raise Stop(3, {"error": "no-baseline", "expected": str(path)})


def save_state(out, state):
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / STATE).write_text(json.dumps(state, indent=2) + "\n")


def do_init(opts):
    repo, out = Path(opts["repo"]), Path(opts["out"])
    if not repo.is_dir():
        raise Stop(3, {"error": "not-a-directory", "path": str(repo)})
    try:
        root = git(repo, "rev-parse", "--show-toplevel").decode().strip()
    except Stop:
        raise Stop(3, {"error": "not-a-repo", "path": str(repo)})
    try:
        sha = head_sha(root)
    except Stop:
        raise Stop(3, {"error": "no-commit", "repo": root})
    keep = keeper(root, out)
    dirty = zlist(git(root, "status", "--porcelain=v1", "-z", "--untracked-files=no"))
    if (out / STATE).exists():
        prior = load_state(out)
        same = prior.get("sha") == sha and prior.get("git_root") == root
        if same and dirty and tree_digest(root, sha, keep) == prior.get("last_digest"):
            return 0, dict(prior, resumed=True)
    if dirty:
        raise Stop(3, {"error": "dirty-tree", "repo": root, "entries": dirty[:20]})
    scope = [glob_regex(g) for g in opts["scope"]]
    files = untracked(root)
    files.sort(key=lambda p: in_scope(p, scope))
    state = {
        "sha": sha, "git_root": root, "scope": sorted(opts["scope"]),
        "plugin_version": opts.get("plugin-version"),
        "untracked": sorted(files),
        "digests": {p: blob_hash(os.path.join(root, p)) for p in files[:HASH_CAP]},
        "unhashed": sorted(files[HASH_CAP:]),
        "git_meta": git_meta(root),
        "hidden_flags": hidden_flags(root),
        "stash": stash_sha(root),
        "last_digest": tree_digest(root, sha, keep),
    }
    save_state(out, state)
    return 0, dict(state, resumed=False)


def do_check(opts):
    state = load_state(opts["out"])
    if sorted(opts["scope"]) != state.get("scope"):
        raise Stop(3, {"error": "scope-mismatch", "pinned": state.get("scope"),
                       "given": sorted(opts["scope"])})
    root, sha = state["git_root"], state["sha"]
    scope = [glob_regex(g) for g in opts["scope"]]
    keep = keeper(root, opts["out"])
    try:
        head = head_sha(root)
    except Stop:
        head = None
    head_moved = head != sha or stash_sha(root) != state.get("stash", "")
    changed = [p for p in zlist(git(root, *DIFF, "--name-only", "--no-renames", "-z", sha)) if keep(p)]
    now = [p for p in untracked(root) if keep(p)]
    before = set(state["untracked"])
    violations = [p for p in changed if not in_scope(p, scope)]
    violations += [p for p in now if p not in before and not in_scope(p, scope)]
    unguarded = []
    for path in sorted(before):
        if in_scope(path, scope) or not keep(path):
            continue
        if path not in state["digests"]:
            unguarded.append(path)
        elif state["digests"][path] is None or blob_hash(os.path.join(root, path)) != state["digests"][path]:
            violations.append(path)
    meta_now = git_meta(root)
    meta_then = state.get("git_meta", {})
    violations += [p for p in set(meta_now) | set(meta_then) if meta_now.get(p) != meta_then.get(p)]
    flagged = [p for p in hidden_flags(root) if p not in set(state.get("hidden_flags", []))]
    violations += flagged
    digest = tree_digest(root, sha, keep)
    save_state(opts["out"], dict(state, last_digest=digest))
    report = {
        "ok": not violations and not head_moved,
        "head_moved": head_moved,
        "violations": sorted(set(violations)),
        "hidden_flags": flagged,
        "new_untracked_in_scope": [p for p in now if p not in before and in_scope(p, scope)],
        "unguarded": unguarded,
        "changed": changed,
        "digest": digest,
    }
    return (0 if report["ok"] else 1), report


def do_snapshot(opts):
    name = opts["name"]
    if "/" in name or os.sep in name or not name.endswith(".diff") or name.startswith("."):
        raise Stop(2, None)
    state = load_state(opts["out"])
    data = git(state["git_root"], *DIFF, "--binary", state["sha"])
    target = Path(opts["out"]) / name
    target.write_bytes(data)
    return 0, {"written": str(target), "bytes": len(data)}


def do_match(opts, paths):
    scope = [glob_regex(g) for g in opts["scope"]]
    return 0, {p: in_scope(p.removeprefix("./"), scope) for p in paths}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        cmd, opts, paths = parse(argv)
        if cmd == "init":
            code, payload = do_init(opts)
        elif cmd == "check":
            code, payload = do_check(opts)
        elif cmd == "snapshot":
            code, payload = do_snapshot(opts)
        else:
            code, payload = do_match(opts, paths)
    except Stop as stop:
        if stop.payload is None:
            sys.stderr.write(USAGE)
            return stop.code
        code, payload = stop.code, stop.payload
    except Exception as exc:  # noqa: BLE001
        code, payload = 3, {"error": "internal", "type": type(exc).__name__, "detail": str(exc)}
    print(json.dumps(payload, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
