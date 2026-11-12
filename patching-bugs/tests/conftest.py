"""Shared pieces: the scripts as modules and as CLIs, an isolated git, a tiny demo project."""
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "skills" / "patching-bugs" / "scripts"
PY = sys.executable


def _module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def rec():
    return _module("records")


@pytest.fixture(scope="session")
def mk():
    return _module("markers")


@pytest.fixture(scope="session")
def arms_mod():
    _module("records")
    _module("markers")
    return _module("arms")


@pytest.fixture(scope="session")
def verdict_mod():
    _module("records")
    _module("markers")
    return _module("verdict")


def git_env(home: Path) -> dict:
    cfg = home / "gitconfig"
    cfg.write_text("[user]\n\tname = Test Person\n\temail = test@example.invalid\n"
                   "[commit]\n\tgpgsign = false\n[core]\n\thooksPath = /dev/null\n"
                   "[init]\n\tdefaultBranch = main\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=str(cfg), GIT_CONFIG_NOSYSTEM="1")
    return env


@pytest.fixture(autouse=True)
def isolated_git(tmp_path, monkeypatch):
    home = tmp_path / "_git"
    home.mkdir()
    for key, value in git_env(home).items():
        monkeypatch.setenv(key, value)
    for key in [k for k in os.environ if k.startswith("GIT_") and k not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")]:
        monkeypatch.delenv(key, raising=False)


def git(where, *args) -> str:
    done = subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def cli(script, *args):
    return subprocess.run([PY, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True)


TOOL_BASE = """\
#!/bin/sh
mkdir -p "$(dirname "$1/$2")" && printf 'x' > "$1/$2"
"""
TOOL_FIXED = """\
#!/bin/sh
case "/$2/" in */../*) echo "refused: $2" >&2; exit 3;; esac
mkdir -p "$(dirname "$1/$2")" && printf 'x' > "$1/$2"
"""
BUILD = ["sh", "-c", "mkdir -p bin && cp tool.sh bin/tool && chmod +x bin/tool"]

HARNESS = textwrap.dedent("""\
    import hashlib, json, os, subprocess, sys
    tree, scratch, raw = sys.argv[1:4]
    name = json.loads(raw)
    tool = os.path.realpath(os.path.join(tree, "bin", "tool"))
    print("PATCH_LOADED " + json.dumps({"path": tool, "sha256": hashlib.sha256(open(tool, "rb").read()).hexdigest()}))
    home = os.path.join(scratch, "a", "b", "home")
    os.makedirs(home)
    done = subprocess.run(["sh", tool, home, name], capture_output=True)
    outside = []
    for top, _, files in os.walk(scratch):
        for f in files:
            full = os.path.realpath(os.path.join(top, f))
            if not full.startswith(os.path.realpath(home) + os.sep):
                outside.append(full)
    actual = "outside" if outside else ("stored" if done.returncode == 0 else "refused")
    print("PATCH_CASE " + json.dumps({"input": name, "actual": actual}))
    if os.environ.get("HARNESS_SKIP_REACHED") != "1":
        print("PATCH_REACHED", flush=True)
    sys.exit(1 if outside else 0)
    """)


class Demo:
    """A repo whose baseline tool writes outside its home for ../ names and whose patch refuses them."""

    def __init__(self, root: Path):
        self.root = root
        self.repo = root / "repo"
        self.repo.mkdir(parents=True)
        git(self.repo, "init", "-q")
        (self.repo / "tool.sh").write_text(TOOL_BASE)
        (self.repo / ".gitignore").write_text("bin/\n")
        (self.repo / "tool_test.sh").write_text("#!/bin/sh\nexit 0\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "tool")
        self.base = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "tool.sh").write_text(TOOL_FIXED)
        (self.repo / "tool_test.sh").write_text("#!/bin/sh\necho 'refusal covered'\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qsm", "fix(tool): refuse parent segments")
        self.patch = git(self.repo, "rev-parse", "HEAD")
        self.harness = root / "poc" / "harness.py"
        self.harness.parent.mkdir()
        self.harness.write_text(HARNESS)

    def poc(self, name='"../../out.txt"'):
        return [PY, str(self.harness), "{tree}", "{scratch}", name]

    def worktree_count(self):
        return git(self.repo, "worktree", "list", "--porcelain").count("worktree ")


@pytest.fixture
def demo(tmp_path):
    return Demo(tmp_path)


SCOPE = {
    "mode": "bounded_class",
    "boundary": "names handed to tool stay inside its home directory",
    "cases": [
        {"check_id": "two-up", "role": "representative", "input": "../../out.txt",
         "expected": "refused", "why": "the reported escape"},
        {"check_id": "nested-up", "role": "representative", "input": "a/../../../out.txt",
         "expected": "refused", "why": "climbs out after a real folder"},
        {"check_id": "nested-ok", "role": "control", "input": "go/http.txt",
         "expected": "stored", "why": "nested names inside the home keep working"},
    ],
    "exclusions": ["symlinks planted inside home by another process"],
}


def dump(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def finding(**over):
    data = {"schema_version": 1, "title": "tool writes outside its home for ../ names",
            "claim": "a name with parent segments makes tool write a file outside the home directory",
            "affected_code": [{"path": "tool.sh", "start_line": 2, "end_line": 2}],
            "invariant": "tool writes only inside its home directory", "poc": None,
            "source": "unit-test report", "status": "confirmed",
            "reported": {"expected_behavior": "refused", "observed_behavior": "file outside home"},
            "repair_scope": json.loads(json.dumps(SCOPE))}
    data.update(over)
    return data


def build_run(demo: Demo, tmp: Path, regression=None) -> Path:
    """Drive the real scripts through reproduce, validate, patch and prove; return the run dir."""
    run = tmp / "run"
    plan = tmp / "plan.json"
    dump(plan, [{"check_id": c["check_id"],
                 "argv": demo.poc(json.dumps(c["input"]))} for c in SCOPE["cases"]])
    dump(run / "finding.json", finding())
    dump(run / "run.json", {"schema_version": 1, "finding_id": "DEMO-1", "status": "in_progress",
                            "attempts": 1, "steps": {k: "done" for k in
                                                     ("intake", "reproduce", "validate", "patch",
                                                      "prove", "regression", "report")}})
    for step, agent in (("reproduce", "reproducer-a1"), ("validate", "validator-b2")):
        out = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base,
                  "--build", json.dumps(BUILD), "--plan", plan, "--out", run / step)
        assert out.returncode == 0, out.stderr
    dump(run / "reproduce" / "reproduce.json", {
        "schema_version": 1, "outcome": "reproduced", "baseline_commit": demo.base,
        "build_argv": BUILD, "poc_argv": demo.poc(), "target_artifact": "bin/tool",
        "observed": "out.txt written two levels above home", "blocker": None,
        "agent": "reproducer-a1", "failure_type": "runtime"})
    dump(run / "validate" / "validate.json", {"schema_version": 1, "outcome": "confirmed",
                                              "agent": "validator-b2",
                                              "reason": "rerun shows the same escape"})
    for step in ("reproduce", "validate"):
        assert cli("records.py", "manifest", run / step).returncode == 0
    attempt = run / "patch" / "attempt-1"
    dump(attempt / "patch.json", {
        "schema_version": 1, "attempt": 1, "baseline_commit": demo.base,
        "patch_commit": demo.patch, "files_changed": 2, "lines_added": 3, "lines_removed": 0,
        "variants": [{"location": "tool.sh:2", "status": "fixed", "reason": "single write path"}],
        "suite_before": {"command": "sh tool_test.sh", "passed": 0, "failed": 0, "skipped": 0},
        "suite_after": {"command": "sh tool_test.sh", "passed": 1, "failed": 0, "skipped": 0},
        "agent": "patcher-c3"})
    (attempt / "fix.patch").write_text("diff\n")
    (attempt / "tests.patch").write_text("diff\n")
    assert cli("records.py", "manifest", attempt).returncode == 0

    proof = run / "prove" / "attempt-1"
    (proof / "receipts" / "harness").mkdir(parents=True)
    (proof / "receipts" / "harness" / "harness.py").write_text(HARNESS)
    cases = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base,
                "--patch", demo.patch, "--build", json.dumps(BUILD), "--plan", plan,
                "--out", proof)
    assert cases.returncode == 0, cases.stderr
    checks_plan = tmp / "checks.json"
    dump(checks_plan, [{"check_id": "suite", "argv": ["sh", "{tree}/tool_test.sh"]}])
    checks = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base,
                 "--patch", demo.patch, "--build", json.dumps(BUILD), "--plan", checks_plan,
                 "--out", proof, "--label", "checks")
    assert checks.returncode == 0, checks.stderr
    arms = cli("arms.py", "run", "--repo", demo.repo, "--baseline", demo.base, "--patch",
               demo.patch, "--build", json.dumps(BUILD), "--out", proof,
               "--poc", json.dumps(demo.poc()), "--artifact", "bin/tool")
    assert arms.returncode == 0, arms.stderr
    three = json.loads(arms.stdout)
    suite_runs = json.loads(checks.stdout)["runs"][0]["runs"]
    dump(proof / "prove.json", {
        "schema_version": 2, "attempt": 1, "failure_type": "runtime",
        "baseline_commit": demo.base, "patch_commit": demo.patch,
        "reverted": three["reverted"], "build_identity": three["build_identity"],
        "hashes": three["hashes"], "reverted_hash_note": three["reverted_hash_note"],
        "cases": [{"check_id": r["check_id"], "argv": r["argv"],
                   "source": "receipts/harness/harness.py", "runs": r["runs"]}
                  for r in json.loads(cases.stdout)["runs"]],
        "project_checks": [{"check_id": "suite", "kind": "suite", "argv": ["sh", "tool_test.sh"],
                            "baseline": suite_runs["baseline"], "patched": suite_runs["patched"]}],
        "unproven": ["symlinks inside home were not exercised"], "agent": "prover-d4"})
    assert cli("records.py", "manifest", proof).returncode == 0
    if regression is not None:
        dump(run / "regression" / "regression.json", regression)
        assert cli("records.py", "manifest", run / "regression").returncode == 0
    return run
