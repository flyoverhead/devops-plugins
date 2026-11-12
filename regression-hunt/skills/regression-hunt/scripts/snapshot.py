#!/usr/bin/env python3
"""Export the before (S0) and after (S1) trees of a change as pristine directories, plus the patch,
the commit messages and source.json. Usage: snapshot.py REPO S0_REF S1_REF OUTPUT

OUTPUT must not exist yet and must lie outside the repository. Silent on success.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from pathlib import Path

USAGE = "usage: snapshot.py REPO S0_REF S1_REF OUTPUT"
LFS_HEAD = b"version https://git-lfs.github.com/spec/"
HAS_FILTER = hasattr(tarfile, "tar_filter")


class Stop(Exception):
    pass


def git(repo, *args, data=False) -> bytes:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if done.returncode != 0:
        raise Stop(f"git {' '.join(args)} failed: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout if data else done.stdout.decode().strip()


def commit_of(repo, ref) -> str:
    try:
        return git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except Stop:
        raise Stop(f"{ref} does not name a commit in {repo}") from None


def link_escapes(name: str, text: str) -> bool:
    if text.startswith("/"):
        return True
    target = os.path.normpath(os.path.join(os.path.dirname(name), text))
    return target == ".." or target.startswith("../") or target.startswith("/")


def screen(repo, sha) -> set:
    """Refuse trees that git archive cannot export faithfully; return the paths the export must hold."""
    listing = git(repo, "ls-tree", "-r", "-z", "--full-tree", sha, data=True).split(b"\0")
    hand = "export it by hand into the attempt directory and record how"
    entries, links = {}, set()
    for row in filter(None, listing):
        meta, path = row.split(b"\t", 1)
        mode, kind, obj = meta.split()
        name = path.decode("utf-8", errors="surrogateescape")
        if kind == b"commit":
            raise Stop(f"{sha[:12]} has a submodule at {name}; check out its pinned commit and {hand}")
        entries[name] = (mode, obj.decode())
        if mode == b"120000":
            links.add(name)
    seen = {}
    for name in entries:
        parts = name.split("/")
        for depth in range(1, len(parts) + 1):
            prefix = "/".join(parts[:depth])
            if depth < len(parts) and prefix in links:
                raise Stop(f"{sha[:12]}:{name} sits below the symlink {prefix}; {hand}")
            key = unicodedata.normalize("NFC", prefix).casefold()
            if seen.setdefault(key, prefix) != prefix:
                raise Stop(f"{sha[:12]}: {seen[key]} and {prefix} collide on a case-insensitive or "
                           f"normalising filesystem; {hand}")
    for name, (mode, obj) in entries.items():
        if name in links:
            text = git(repo, "cat-file", "blob", obj, data=True).decode("utf-8", errors="surrogateescape")
            if not HAS_FILTER:
                raise Stop(f"{sha[:12]}:{name} is a symlink and this Python cannot extract symlinks safely; {hand}")
            if link_escapes(name, text):
                raise Stop(f"{sha[:12]}: symlink {name} points outside the tree ({text}); {hand}")
            continue
        if name == ".gitattributes" or name.endswith("/.gitattributes"):
            attrs = git(repo, "cat-file", "blob", obj, data=True)
            for word in (b"export-ignore", b"export-subst"):
                if word in attrs:
                    raise Stop(f"{sha[:12]}:{name} uses {word.decode()}, so git archive would not "
                               f"match the commit; {hand}")
            if b"filter=lfs" in attrs:
                raise Stop(f"{sha[:12]}:{name} routes files through Git LFS; fetch the real objects and {hand}")
        size = int(git(repo, "cat-file", "-s", obj))
        if size < 512 and git(repo, "cat-file", "blob", obj, data=True).startswith(LFS_HEAD):
            raise Stop(f"{sha[:12]}:{name} is a Git LFS pointer; fetch the real object and {hand}")
    return set(entries)


def exported(dest: Path) -> set:
    found = set()
    for top, dirs, files in os.walk(dest):
        for name in dirs + files:
            full = Path(top) / name
            if full.is_symlink() or full.is_file():
                found.add(full.relative_to(dest).as_posix())
    return found


def unpack(repo, sha, dest: Path, expected: set):
    blob = git(repo, "archive", "--format=tar", sha, data=True)
    dest.mkdir()
    try:
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            members = tar.getmembers()
            for m in members:
                parts = Path(m.name).parts
                if m.name.startswith("/") or ".." in parts:
                    raise Stop(f"{sha[:12]}: archive entry {m.name} would land outside the export")
                if not (m.isfile() or m.isdir() or m.issym()) or m.islnk():
                    raise Stop(f"{sha[:12]}: archive entry {m.name} is not a plain file, directory or symlink")
                if m.issym() and (not HAS_FILTER or link_escapes(m.name, m.linkname)):
                    raise Stop(f"{sha[:12]}: symlink {m.name} cannot be extracted safely ({m.linkname})")
            extra = {"filter": "tar"} if HAS_FILTER else {}
            tar.extractall(dest, members=members, **extra)
    except (tarfile.TarError, OSError) as exc:
        raise Stop(f"{sha[:12]}: extraction failed ({exc})") from None
    got = exported(dest)
    if got != expected:
        diff = sorted(got ^ expected)
        raise Stop(f"{sha[:12]}: the export does not match git ls-tree (first difference: {diff[0]}); "
                   "export attributes or filters may be in play")


def build(repo: Path, s0: str, s1: str, out: Path):
    for name, sha in (("S0", s0), ("S1", s1)):
        unpack(repo, sha, out / name, screen(repo, sha))
    (out / "change.patch").write_bytes(git(repo, "diff", "--no-ext-diff", "--no-textconv", "--binary", "--full-index", s0, s1, data=True))
    log = git(repo, "log", "--format=commit %H%nAuthor: %an <%ae>%nDate: %aI%n%n%B", f"{s0}..{s1}", data=True)
    if not log.strip():
        log = git(repo, "log", "-1", "--format=commit %H%nAuthor: %an <%ae>%nDate: %aI%n%n%B", s1, data=True)
    (out / "change-message.txt").write_bytes(log)
    (out / "source.json").write_text(json.dumps({
        "repository": str(repo), "s0": s0, "s1": s1,
        "tree0": git(repo, "rev-parse", f"{s0}^{{tree}}"),
        "tree1": git(repo, "rev-parse", f"{s1}^{{tree}}"),
    }, indent=2) + "\n")


def run(argv) -> None:
    if len(argv) != 4 or any(a in ("-h", "--help") for a in argv):
        print(USAGE, file=sys.stderr)
        raise SystemExit(2)
    repo_arg, ref0, ref1, out_arg = argv
    try:
        repo = Path(git(repo_arg, "rev-parse", "--show-toplevel")).resolve()
    except Stop:
        raise Stop(f"{repo_arg} is not inside a git work tree") from None
    out = Path(out_arg).expanduser().absolute()
    if out.exists() or out.is_symlink():
        raise Stop(f"{out} already exists; pick a fresh output path")
    parent = out.parent.resolve()
    if not parent.is_dir():
        raise Stop(f"{out.parent} does not exist")
    if parent == repo or repo in parent.parents:
        raise Stop(f"{out} is inside the repository; exports live outside it")
    s0, s1 = commit_of(repo, ref0), commit_of(repo, ref1)
    if s0 == s1:
        raise Stop(f"{ref0} and {ref1} are the same commit {s0}")
    for sha in (s0, s1):
        screen(repo, sha)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=parent))
    try:
        build(repo, s0, s1, staging)
        os.rename(staging, parent / out.name)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv=None) -> int:
    try:
        run(sys.argv[1:] if argv is None else argv)
    except Stop as exc:
        print(f"snapshot.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
