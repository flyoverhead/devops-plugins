#!/usr/bin/env python3
"""Run project code on pinned commits in throwaway detached worktrees.

    arms.py run   --repo R --baseline SHA --patch SHA --build ARGV_JSON --out DIR
                  [--poc ARGV_JSON] [--artifact REL] [--failure-type runtime|compile]
                  [--expected-diagnostic TEXT] [--timeout SECONDS]
    arms.py cases --repo R --baseline SHA [--patch SHA] --build ARGV_JSON --plan FILE
                  --out DIR [--artifact REL] [--label NAME] [--timeout SECONDS]

`run` is the three-arm check: baseline, patched, and the patch commit reset to the
baseline tree. `cases` builds each side once and runs every planned argv on it. In
argv, {tree} becomes the worktree path and {scratch} a fresh empty directory per run.
The caller's checkout is never touched; worktrees live in a private directory under the
temp root, outside the run directory, and are removed even on error.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import markers  # noqa: E402
import records  # noqa: E402

GIT_QUIET = ["-c", "core.hooksPath=/dev/null", "-c", "advice.detachedHead=false"]
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
RECORDED_ENV = ("GOCACHE", "GOFLAGS", "GOTOOLCHAIN")


class Refused(Exception):
    pass


def git(repo, *args, check=True):
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
    done = subprocess.run(["git", *GIT_QUIET, "-C", str(repo), *args], capture_output=True,
                          text=True, env=env)
    if check and done.returncode:
        raise Refused(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def argv_list(raw, flag, allow_empty=False):
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise Refused(f"{flag} must be a JSON array of strings") from None
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise Refused(f"{flag} must be a JSON array of strings")
    if not value and not allow_empty:
        raise Refused(f"{flag} is empty")
    return value


def fill(argv, tree, scratch):
    return [part.replace("{tree}", str(tree)).replace("{scratch}", str(scratch)) for part in argv]


def execute(argv, cwd, timeout) -> dict:
    """Run argv with no stdin; a timeout leaves exit_code None."""
    started = time.monotonic()
    try:
        done = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)
        code, out, err = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as late:
        code, out, err = None, late.stdout or b"", (late.stderr or b"") + b"\n[timed out]\n"
    except OSError as why:
        code, out, err = 127, b"", f"cannot start {argv[0]}: {why}\n".encode()
    return {"exit_code": code, "elapsed": time.monotonic() - started, "out": out, "err": err}


def keep_step(folder: Path, facts: dict) -> dict:
    """Arm receipts: folder/stdout.txt, stderr.txt, exit.json with elapsed_s."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "stdout.txt").write_bytes(facts["out"])
    (folder / "stderr.txt").write_bytes(facts["err"])
    records.dump(folder / "exit.json", {"exit_code": facts["exit_code"],
                                        "elapsed_s": round(facts["elapsed"], 3)})
    return facts


def keep_case(base: Path, folder: Path, side: str, facts: dict) -> dict:
    """Case receipts: folder/<side>.stdout, .stderr, .exit.json; returns a prove.json RUN."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{side}.stdout").write_bytes(facts["out"])
    (folder / f"{side}.stderr").write_bytes(facts["err"])
    elapsed_ms = int(facts["elapsed"] * 1000)
    records.dump(folder / f"{side}.exit.json", {"exit_code": facts["exit_code"],
                                                "elapsed_ms": elapsed_ms})
    rel = folder.relative_to(base).as_posix()
    return {"exit_code": facts["exit_code"], "elapsed_ms": elapsed_ms,
            "stdout": f"{rel}/{side}.stdout", "stderr": f"{rel}/{side}.stderr"}


class Trees:
    """Detached worktrees in a private temp directory outside the run directory; always disposed."""

    def __init__(self, repo: Path, out: Path):
        self.repo = repo
        self.home = Path(tempfile.mkdtemp(prefix="patching-bugs-trees-")).resolve()
        if self.home == out.resolve() or self.home in out.resolve().parents:
            raise Refused(f"{out}: the output lies inside the temporary tree home")
        self.made = []

    def add(self, commit: str) -> Path:
        path = self.home / f"t-{secrets.token_hex(4)}"
        git(self.repo, "worktree", "add", "--detach", str(path), commit)
        self.made.append(path)
        return path

    def scratch(self) -> Path:
        deep = Path(tempfile.mkdtemp(prefix="s-", dir=self.home)) / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        return deep

    def drop_admin_entries(self):
        """Remove only our own .git/worktrees/<name> entries, never a global prune."""
        common = git(self.repo, "rev-parse", "--git-common-dir", check=False)
        if not common:
            return
        admin = Path(common) if Path(common).is_absolute() else Path(self.repo) / common
        for entry in sorted((admin / "worktrees").glob("*")) if (admin / "worktrees").is_dir() else []:
            try:
                target = Path((entry / "gitdir").read_text().strip()).resolve()
            except OSError:
                continue
            if self.home in target.parents:
                shutil.rmtree(entry, ignore_errors=True)

    def close(self):
        for path in self.made:
            git(self.repo, "worktree", "remove", "--force", str(path), check=False)
        shutil.rmtree(self.home, ignore_errors=True)
        self.drop_admin_entries()
        leftovers = [str(p) for p in self.made if p.exists()]
        if leftovers:
            print(f"arms.py: could not remove {', '.join(leftovers)}", file=sys.stderr)


def commit_of(repo, ref):
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")


def tree_id(path):
    git(path, "add", "-A", "--", ".")
    return git(path, "write-tree")


def env_snapshot():
    return {name: os.environ[name] for name in RECORDED_ENV if name in os.environ}


def prepare_out(out: Path, reserved):
    out.mkdir(parents=True, exist_ok=True)
    clash = [name for name in reserved if (out / name).exists()]
    if clash:
        raise Refused(f"{out}: {', '.join(clash)} already exists; use a new attempt directory")


def check_run_args(a):
    a.build = argv_list(a.build, "--build")
    a.poc = argv_list(a.poc, "--poc", allow_empty=True) if a.poc is not None else None
    if a.failure_type == "runtime":
        if not a.poc:
            raise Refused("runtime needs a non-empty --poc")
        if not a.artifact or Path(a.artifact).is_absolute() or ".." in Path(a.artifact).parts:
            raise Refused("runtime needs --artifact as a relative path without '..'")
    else:
        if not (a.expected_diagnostic or "").strip():
            raise Refused("compile needs --expected-diagnostic")
        if a.poc is not None or a.artifact is not None:
            raise Refused("compile takes neither --poc nor --artifact")


def one_arm(name, commit, tree, a, receipts: Path, trees: Trees) -> dict:
    where = receipts / name
    built = keep_step(where / "build", execute(a.build, tree, a.timeout))
    said = (built["out"] + built["err"]).decode("utf-8", "replace")
    fact = {"name": name, "commit": commit, "build_exit": built["exit_code"],
            "diagnostic_matched": False, "artifact_sha256": None, "loaded_identity": False,
            "reached": False, "exit_code": None}
    if a.failure_type == "compile":
        fact["diagnostic_matched"] = a.expected_diagnostic in said
        fact["reached"] = built["exit_code"] == 0 or (
            built["exit_code"] not in (None, 0) and fact["diagnostic_matched"])
        fact["exit_code"] = built["exit_code"]
    elif built["exit_code"] == 0:
        artifact = tree / a.artifact
        if artifact.is_file():
            fact["artifact_sha256"] = records.sha256_file(artifact)
        ran = keep_step(where / "poc", execute(fill(a.poc, tree, trees.scratch()), tree, a.timeout))
        lines = ran["out"].decode("utf-8", "replace").splitlines()
        fact["exit_code"] = ran["exit_code"]
        fact["reached"] = markers.REACHED in lines
        seen = markers.tagged(lines, markers.LOADED)
        if len(seen) == 1 and fact["artifact_sha256"]:
            try:
                got = json.loads(seen[0])
                fact["loaded_identity"] = (
                    isinstance(got, dict)
                    and Path(str(got.get("path"))).resolve() == artifact.resolve()
                    and got.get("sha256") == fact["artifact_sha256"])
            except json.JSONDecodeError:
                pass
    records.dump(where / "arm.json", fact)
    return fact


def three_arms(a) -> dict:
    check_run_args(a)
    repo, out = Path(a.repo), Path(a.out)
    base, patch = commit_of(repo, a.baseline), commit_of(repo, a.patch)
    prepare_out(out, ["receipts/source.json", "receipts/baseline", "receipts/patched",
                      "receipts/reverted"])
    receipts = out / "receipts"
    trees = Trees(repo, out)
    try:
        paths = {"baseline": trees.add(base), "patched": trees.add(patch),
                 "reverted": trees.add(patch)}
        git(paths["reverted"], "read-tree", "--reset", "-u", base)
        ids = {side: tree_id(path) for side, path in paths.items()}
        dirty = git(paths["reverted"], "diff", "--name-only", base, check=False)
        if ids["reverted"] != ids["baseline"] or dirty:
            raise Refused("the reverted tree does not equal the baseline tree")
        receipts.mkdir(parents=True, exist_ok=True)
        records.dump(receipts / "source.json",
                     {"baseline_commit": base, "patch_commit": patch, "trees": ids})
        commits = {"baseline": base, "patched": patch, "reverted": patch}
        facts = {side: one_arm(side, commits[side], paths[side], a, receipts, trees)
                 for side in ("baseline", "patched", "reverted")}
    finally:
        trees.close()
    records.dump(receipts / "env.json", env_snapshot())
    records.write_manifest(out)
    return summarise(a.failure_type, facts)


def summarise(kind, facts) -> dict:
    b, p, r = facts["baseline"], facts["patched"], facts["reverted"]
    if not all(f["reached"] for f in facts.values()):
        reverted = "inconclusive"
    elif b["exit_code"] not in (None, 0) and r["exit_code"] == b["exit_code"] and p["exit_code"] == 0:
        reverted = "pass"
    else:
        reverted = "fail"
    hashes = {side: facts[side]["artifact_sha256"] for side in facts}
    if kind == "compile":
        identity = "not_applicable"
    elif all(f["loaded_identity"] for f in facts.values()) and hashes["baseline"] != hashes["patched"]:
        identity = "pass"
    else:
        identity = "fail"
    note = None
    if hashes["reverted"] != hashes["baseline"]:
        note = (f"reverted artifact sha256 {hashes['reverted']} differs from baseline "
                f"{hashes['baseline']}; builds are not byte-reproducible or the trees differ")
    return {"failure_type": kind, "reverted": reverted, "build_identity": identity,
            "hashes": hashes, "reverted_hash_note": note}


def load_plan(path: Path):
    plan = records.load(path)
    if not isinstance(plan, list):
        raise Refused(f"{path}: the plan is a JSON list of {{check_id, argv}} objects")
    ids = []
    for n, item in enumerate(plan):
        if not isinstance(item, dict) or set(item) - {"check_id", "argv"} or "argv" not in item:
            raise Refused(f"{path}[{n}]: wanted exactly check_id and argv")
        cid = item.get("check_id")
        if not isinstance(cid, str) or not SAFE_ID.fullmatch(cid):
            raise Refused(f"{path}[{n}]: check_id must match {SAFE_ID.pattern}")
        argv_list(json.dumps(item["argv"]), f"{path}[{n}].argv")
        ids.append(item["check_id"])
    if len(set(ids)) != len(ids):
        raise Refused(f"{path}: check_id repeated")
    return plan


def planned_cases(a) -> dict:
    repo, out = Path(a.repo), Path(a.out)
    build = argv_list(a.build, "--build")
    if a.artifact and (Path(a.artifact).is_absolute() or ".." in Path(a.artifact).parts):
        raise Refused("--artifact must be a relative path without '..'")
    label = a.label or "cases"
    if not SAFE_ID.fullmatch(label):
        raise Refused(f"--label must match {SAFE_ID.pattern}")
    plan = load_plan(Path(a.plan))
    sides = {"baseline": commit_of(repo, a.baseline)}
    if a.patch:
        sides["patched"] = commit_of(repo, a.patch)
    prepare_out(out, [f"receipts/{label}"])
    group = out / "receipts" / label
    trees = Trees(repo, out)
    result = {"label": label, "commits": sides, "trees": {}, "build": {},
              "runs": [{"check_id": i["check_id"], "argv": i["argv"], "runs": {}} for i in plan]}
    try:
        paths = {side: trees.add(commit) for side, commit in sides.items()}
        for side, path in paths.items():
            result["trees"][side] = tree_id(path)
            git(path, "reset", "-q")
            built = keep_case(out, group / "_build", side, execute(build, path, a.timeout))
            result["build"][side] = built
            if built["exit_code"] != 0:
                continue
            if a.artifact:
                made = (path / a.artifact).resolve()
                built["artifact"] = {"path": str(made), "sha256": records.sha256_file(made)
                                     if made.is_file() else None}
            for item, row in zip(plan, result["runs"]):
                if git(path, "status", "--porcelain", "--untracked-files=no"):
                    raise Refused(f"a run changed tracked files in the {side} tree; stopped")
                facts = execute(fill(item["argv"], path, trees.scratch()), path, a.timeout)
                row["runs"][side] = keep_case(out, group / item["check_id"], side, facts)
    finally:
        trees.close()
        group.mkdir(parents=True, exist_ok=True)
        records.dump(group / "launch.json", {"argv": sys.argv, "commits": sides,
                                             "trees": result["trees"], "build": result["build"],
                                             "env": env_snapshot()})
    return result


def parse(argv):
    cli = argparse.ArgumentParser(prog="arms.py", description=__doc__.splitlines()[0])
    sub = cli.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="baseline / patched / reverted check")
    c = sub.add_parser("cases", help="run planned argv on the baseline (and patched) tree")
    for p in (r, c):
        p.add_argument("--repo", required=True)
        p.add_argument("--baseline", required=True)
        p.add_argument("--build", required=True, help="JSON array, run in the worktree")
        p.add_argument("--out", required=True)
        p.add_argument("--timeout", type=float, default=600.0)
    r.add_argument("--patch", required=True)
    r.add_argument("--poc", help="JSON array; {tree} and {scratch} are filled in")
    r.add_argument("--artifact", help="built file, relative to the worktree")
    r.add_argument("--failure-type", choices=("runtime", "compile"), default="runtime")
    r.add_argument("--expected-diagnostic")
    c.add_argument("--patch")
    c.add_argument("--plan", required=True, help="JSON list of {check_id, argv}")
    c.add_argument("--label", help="receipts/<label>/ folder name (default cases)")
    c.add_argument("--artifact", help="built file to hash after each build, relative to the worktree")
    return cli.parse_args(argv)


def main(argv=None) -> int:
    args = parse(argv)
    try:
        result = three_arms(args) if args.command == "run" else planned_cases(args)
    except (Refused, records.Invalid) as why:
        print(f"arms.py: {why}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
