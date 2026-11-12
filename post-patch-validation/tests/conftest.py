"""Shared pieces: the runner loaded from its file, an isolated git setup, a demo project."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "skills" / "post-patch-validation" / "scripts" / "post_patch_validation.py"
INTERP = sys.executable


@pytest.fixture(scope="session")
def runner():
    loader = importlib.util.spec_from_file_location("ppv_runner_under_test", SCRIPT)
    module = importlib.util.module_from_spec(loader)
    sys.modules[loader.name] = module
    loader.loader.exec_module(module)
    return module


def isolated_git_env(home: Path) -> dict:
    """Environment with a throwaway global git config: plain identity, no signing, no hooks."""
    config = home / ".test-gitconfig"
    config.write_text(
        "[user]\n\tname = Fixture Bot\n\temail = fixture@example.invalid\n"
        "[commit]\n\tgpgsign = false\n[tag]\n\tgpgsign = false\n"
        "[core]\n\thooksPath = /dev/null\n[init]\n\tdefaultBranch = main\n"
        "[protocol \"file\"]\n\tallow = always\n")
    env = {name: val for name, val in os.environ.items() if not name.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = str(config)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


@pytest.fixture
def gitenv(tmp_path):
    return isolated_git_env(tmp_path)


def g(where, env, *args) -> str:
    done = subprocess.run(["git", *args], cwd=where, env=env, capture_output=True)
    assert done.returncode == 0, done.stderr.decode()
    return done.stdout.decode().strip()


def invoke(env, *args, more_env=None):
    """Run the CLI as a separate process, the way the skill does."""
    return subprocess.run([INTERP, str(SCRIPT), *map(str, args)],
                          env={**env, **(more_env or {})}, capture_output=True)


# A tiny "uploads" package: v1 trusts the name, v2 strips one "../".
UPLOADS_V1 = "def tidy(name):\n    return name\n"
UPLOADS_V2 = "def tidy(name):\n    return name.replace('../', '', 1)\n"

HELPERS = {
    "probe.py": """\
import os, sys
sys.path.insert(0, os.environ["PPV_CHECKOUT"])
from uploads.naming import tidy
how = sys.argv[2] if len(sys.argv) > 2 else "plain"
line = os.environ["PPV_REACHED_MARKER"]
emit = {"plain": lambda: print(line, flush=True),
        "leading-space": lambda: print(" " + line, flush=True),
        "on-stderr": lambda: print(line, file=sys.stderr, flush=True),
        "trailing-text": lambda: print(line + " ok", flush=True),
        "silent": lambda: None}
emit[how]()
sys.exit(1 if ".." in tidy(sys.argv[1]) else 0)
""",
    "echo_name.py": """\
import os, sys
sys.path.insert(0, os.environ["PPV_CHECKOUT"])
from uploads.naming import tidy
print(tidy(sys.argv[1]))
""",
    "whole_suite.py": """\
import os, sys
sys.path.insert(0, os.environ["PPV_CHECKOUT"])
from uploads.naming import tidy
sys.exit(0 if tidy("photo.png") == "photo.png" else 1)
""",
}


def entry(cid, kind, argv, **more):
    item = {"id": cid, "kind": kind, "rationale": f"{cid} should hold",
            "covers": ["uploads/naming.py:tidy"], "argv": argv}
    item.update(more)
    return item


def seven_checks():
    """One check per kind; only the two-level traversal survives the patch."""
    probe = [INTERP, "{plan_dir}/checks/probe.py"]
    return sorted([
        entry("baseline-name", "control", probe + ["photo.png"]),
        entry("echo-plain", "behavior", [INTERP, "{plan_dir}/checks/echo_name.py", "photo.png"],
              compare_stream="stdout"),
        entry("neighbour-name", "security", probe + ["notes.txt"]),
        entry("nested-name", "regression", probe + ["album/photo.png"]),
        entry("one-level-up", "exploit", probe + ["../secrets"]),
        entry("suite-run", "suite", [INTERP, "{plan_dir}/checks/whole_suite.py"]),
        entry("two-levels-up", "variant", probe + ["../../secrets"]),
    ], key=lambda c: c["id"])


def swap(checks, cid, replacement):
    return sorted([c for c in checks if c["id"] != cid] + [replacement], key=lambda c: c["id"])


class Project:
    """A demo repository with base and fix, plus a plan directory beside it."""

    def __init__(self, root: Path, env: dict, via_patch: bool):
        self.root, self.env, self.via_patch = root, env, via_patch
        self.repo, self.plan_dir = root / "project", root / "validation"
        self.plan = self.plan_dir / "plan.json"
        (self.repo / "uploads").mkdir(parents=True)
        g(self.repo, env, "init", "-q")
        (self.repo / "uploads" / "__init__.py").write_text("")
        (self.repo / "uploads" / "naming.py").write_text(UPLOADS_V1)
        g(self.repo, env, "add", "-A")
        g(self.repo, env, "commit", "-qm", "uploads: naming helper")
        g(self.repo, env, "tag", "pre-fix")
        self.base_sha = g(self.repo, env, "rev-parse", "HEAD")
        (self.repo / "uploads" / "naming.py").write_text(UPLOADS_V2)
        if via_patch:
            self.patch = root / "strip.diff"
            self.patch.write_bytes(subprocess.run(["git", "diff", "--binary"], cwd=self.repo, env=env,
                                                  capture_output=True, check=True).stdout)
            g(self.repo, env, "checkout", "--", ".")
            self.fix_sha = None
        else:
            g(self.repo, env, "commit", "-qam", "uploads: drop parent segments")
            self.fix_sha = g(self.repo, env, "rev-parse", "HEAD")
        (self.plan_dir / "checks").mkdir(parents=True)
        for name, body in HELPERS.items():
            (self.plan_dir / "checks" / name).write_text(body)

    def scaffold(self, summary="parent segments leave the upload root", fix_ref="HEAD", more_env=None):
        args = ["scaffold", "--repo", self.repo, "--base-ref", "pre-fix", "--finding-id", "UPL-3",
                "--finding-summary", summary, "--evidence-level", "runtime", "--output", self.plan]
        args += ["--patch-file", self.patch] if self.via_patch else ["--patched-ref", fix_ref]
        done = invoke(self.env, *args, more_env=more_env)
        assert done.returncode == 0, done.stderr.decode()
        return json.loads(done.stdout)

    def with_checks(self, checks):
        plan = json.loads(self.plan.read_text())
        plan["checks"] = checks
        self.plan.write_text(json.dumps(plan, indent=1))
        return self

    def execute(self, folder="evidence", flags=(), more_env=None):
        out = self.root / folder
        done = invoke(self.env, "run", "--plan", self.plan, "--output", out, *flags, more_env=more_env)
        record = out / "result.json"
        return done, out, (json.loads(record.read_text()) if record.exists() else None)

    def worktree_count(self):
        return g(self.repo, self.env, "worktree", "list", "--porcelain").count("worktree ")


@pytest.fixture
def project(tmp_path, gitenv):
    counter = iter(range(100))

    def make(via_patch=False):
        root = tmp_path / f"p{next(counter)}"
        root.mkdir()
        return Project(root, gitenv, via_patch)
    return make
