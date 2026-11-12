"""End-to-end behaviour of `run` on throwaway repositories."""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

from conftest import INTERP, SCRIPT, entry, g, invoke, seven_checks, swap


def flagged(result):
    return [item["check_id"] for item in result["assessment"]["findings"]]


def gaps_for(result, cid):
    return [item["reason"] for item in result["assessment"]["gaps"] if item["check_id"] == cid]


def by_id(result, cid):
    return next(c for c in result["checks"] if c["id"] == cid)


def test_commit_pair_surfaces_the_two_level_traversal(project):
    p = project()
    pinned = p.scaffold()
    assert (pinned["base_commit"], pinned["patched_commit"]) == (p.base_sha, p.fix_sha)
    assert pinned["changed_files"] == ["uploads/naming.py"]
    done, out, result = p.with_checks(seven_checks()).execute()
    assert done.returncode == 1, done.stderr.decode()
    assert result["schema_version"] == "2.0"
    assert flagged(result) == ["two-levels-up"] and result["assessment"]["gaps"] == []
    assert set(result["coverage"].values()) == {1}
    assert list(by_id(result, "suite-run")["runs"]) == ["patched"]
    assert by_id(result, "echo-plain")["comparison"]["matched"]
    assert json.loads(done.stdout)["result"] == str(out / "result.json")
    assert p.worktree_count() == 1, "runner left a worktree behind"


def test_patch_file_input(project):
    p = project(via_patch=True)
    assert p.scaffold()["patched_commit"] is None
    plan = json.loads(p.plan.read_text())
    assert plan["patch_file"] == "../strip.diff" and "patched_ref" not in plan
    done, out, result = p.with_checks(seven_checks()).execute()
    assert done.returncode == 1
    assert result["inputs"]["patched_commit"] is None
    assert flagged(result) == ["two-levels-up"]
    assert (out / "patch.diff").read_bytes() == p.patch.read_bytes()
    assert p.worktree_count() == 1


def test_two_runs_agree(project):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    first, second = p.execute("a")[2], p.execute("b")[2]
    assert first["assessment"] == second["assessment"] and first["inputs"] == second["inputs"]

    def fingerprints(res):
        return {(c["id"], side): r["stdout_sha256"] for c in res["checks"] for side, r in c["runs"].items()}
    assert fingerprints(first) == fingerprints(second)


def test_non_ascii_summary_survives_c_locale(project):
    plain_c = {"LANG": "C", "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONIOENCODING": ""}
    p = project()
    p.scaffold(summary="Dateiname mit Ümlaut — escapes", more_env=plain_c)
    done, out, result = p.with_checks(seven_checks()).execute(more_env=plain_c)
    assert done.returncode == 1, done.stderr.decode()
    assert result["finding"]["summary"] == "Dateiname mit Ümlaut — escapes"
    assert "Ümlaut" in (out / "report.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("how", ["leading-space", "on-stderr", "trailing-text", "silent"])
def test_reach_line_has_to_be_exact_and_on_stdout(project, how):
    p = project()
    p.scaffold()
    odd = entry("one-level-up", "exploit", [INTERP, "{plan_dir}/checks/probe.py", "../x", how])
    done, _, result = p.with_checks(swap(seven_checks(), "one-level-up", odd)).execute()
    assert done.returncode == 10
    reasons = gaps_for(result, "one-level-up")
    assert reasons and all(r.startswith("marker_missing") for r in reasons)


def test_broken_control_holds_back_findings(project):
    p = project()
    p.scaffold()
    bad = entry("baseline-name", "control", [INTERP, "{plan_dir}/checks/probe.py", "../x"])
    done, _, result = p.with_checks(swap(seven_checks(), "baseline-name", bad)).execute()
    assert done.returncode == 10 and flagged(result) == []
    assert any("held back" in r for r in gaps_for(result, "two-levels-up"))


SNOOP = """\
import json, os, sys
open_fds = []
for fd in range(3, 256):
    try:
        os.fstat(fd)
        open_fds.append(fd)
    except OSError:
        pass
seen = {"cwd": os.getcwd(), "tree": os.environ["PPV_CHECKOUT"], "mirror": os.environ["PPV_PLAN_DIR"],
        "scratch": os.environ["PPV_SCRATCH"], "tmp": os.environ["TMPDIR"], "fds": open_fds,
        "names": sorted(os.environ), "mirror_files": sorted(os.listdir(os.environ["PPV_PLAN_DIR"]))}
with open(os.path.join(os.environ["PPV_SCRATCH"], "seen.json"), "w") as fh:
    json.dump(seen, fh)
print(os.environ["PPV_REACHED_MARKER"], flush=True)
"""


def test_blind_kinds_cannot_tell_sides_apart(project):
    p = project()
    p.scaffold()
    (p.plan_dir / "checks" / "snoop.py").write_text(SNOOP)
    snoop = entry("two-levels-up", "variant", [INTERP, "{plan_dir}/checks/snoop.py", "{checkout}"])
    _, out, result = p.with_checks(swap(seven_checks(), "two-levels-up", snoop)).execute()
    seen = {side: json.loads((out / "scratch" / f"two-levels-up-{side}" / "seen.json").read_text())
            for side in ("base", "patched")}
    for side, view in seen.items():
        assert view["fds"] == [], f"{side}: inherited descriptors {view['fds']}"
        assert "PPV_SIDE" not in view["names"]
        assert view["tmp"] == view["scratch"] and view["cwd"] == os.path.realpath(view["tree"])
        assert not {"plan.json", "strip.diff"} & set(view["mirror_files"])
        for key in ("tree", "mirror", "scratch"):
            assert not any(word in view[key].lower() for word in ("base", "patched")), (side, key)
    left, right = seen["base"], seen["patched"]
    assert os.path.dirname(left["tree"]) == os.path.dirname(right["tree"])
    assert len(os.path.basename(left["tree"])) == len(os.path.basename(right["tree"]))
    assert left["names"] == right["names"]
    assert gaps_for(result, "two-levels-up") == ["no reproduction: the assertion already holds on base"]


def test_which_side_goes_first_varies(project):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    leaders = set()
    for attempt in range(10):
        runs = by_id(p.execute(f"order{attempt}")[2], "one-level-up")["runs"]
        leaders.add(min(runs, key=lambda side: runs[side]["stdout"]))
        if len(leaders) == 2:
            break
    assert leaders == {"base", "patched"}


def test_only_named_variables_reach_checks(project):
    p = project()
    p.scaffold()
    (p.plan_dir / "checks" / "show_env.py").write_text(
        "import os\nprint(os.environ.get('RELEASE_CHANNEL'), os.environ.get('UNLISTED_SETTING'))\n")
    printer = entry("echo-plain", "behavior", [INTERP, "{plan_dir}/checks/show_env.py"],
                    compare_stream="stdout")
    _, out, result = p.with_checks(swap(seven_checks(), "echo-plain", printer)).execute(
        flags=["--allow-env", "RELEASE_CHANNEL"],
        more_env={"RELEASE_CHANNEL": "beta", "UNLISTED_SETTING": "should-not-pass"})
    assert result["inputs"]["forwarded_env"] == {"RELEASE_CHANNEL": "beta"}
    log = by_id(result, "echo-plain")["runs"]["base"]["stdout"]
    assert (out / log).read_text() == "beta None\n"


@pytest.mark.parametrize("name", ["NPM_TOKEN", "AWS_SECRET_ACCESS_KEY", "SMTP_PASSWORD", "SIGNING_KEY",
                                  "GH_PAT", "DB_PWD", "SSH_PASS", "API_JWT", "SENTRY_DSN", "NETRC",
                                  "SIGNING_KEYS", "GPG_PRIVKEY", "KUBECONFIG", "DOCKER_CONFIG", "AWS_PROFILE",
                                  "LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "NODE_OPTIONS", "GIT_SSH_COMMAND",
                                  "BASH_ENV", "PYTHONSTARTUP", "PPV_CASE_ID", "HOME", "ABSENT_VARIABLE_XYZ",
                                  "has-dash"])
def test_refused_variables_stop_before_anything_runs(project, name):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    harmless = not name.startswith(("DYLD_", "LD_")) and name != "ABSENT_VARIABLE_XYZ"
    done, out, _ = p.execute(flags=["--allow-env", name], more_env={name: "v"} if harmless else None)
    assert done.returncode == 64 and not out.exists()
    assert b"Traceback" not in done.stderr


def test_scratch_contents_and_helpers_are_kept(project, tmp_path):
    p = project()
    p.scaffold()
    stray = tmp_path / "stray-input.txt"
    stray.write_text("outside every root\n")
    (p.plan_dir / "checks" / "leave_note.py").write_text(
        "import os\nopen(os.path.join(os.environ['PPV_SCRATCH'], 'left.txt'), 'w').write(os.environ['PPV_SIDE'])\n")
    note = entry("nested-name", "regression",
                 [INTERP, "{plan_dir}/checks/leave_note.py", str(stray), "uploads/naming.py"])
    _, out, result = p.with_checks(swap(seven_checks(), "nested-name", note)).execute()
    for side in ("base", "patched"):
        assert (out / "scratch" / f"nested-name-{side}" / "left.txt").read_text() == side
    base_run = by_id(result, "nested-name")["runs"]["base"]
    files = {item["index"]: item for item in base_run["argv_files"]}
    script = (p.plan_dir / "checks" / "leave_note.py").read_bytes()
    assert files[1]["argument"] == "{plan_dir}/checks/leave_note.py"
    assert files[1]["sha256"] == hashlib.sha256(script).hexdigest()
    assert (out / files[1]["artifact"]).read_bytes() == script
    assert files[2]["artifact"] is None and "outside" in files[2]["archive_reason"]
    assert files[3]["artifact"].startswith("helpers/")
    assert base_run["argv0_sha256"] == hashlib.sha256(open(INTERP, "rb").read()).hexdigest()


def test_branch_that_moves_after_pinning_is_refused(project):
    p = project()
    g(p.repo, p.env, "branch", "candidate")
    p.scaffold(fix_ref="candidate")
    p.with_checks(seven_checks())
    g(p.repo, p.env, "switch", "-q", "candidate")
    (p.repo / "uploads" / "later.py").write_text("LATER = True\n")
    g(p.repo, p.env, "add", "-A")
    g(p.repo, p.env, "commit", "-qm", "later work")
    assert invoke(p.env, "validate-plan", "--plan", p.plan).returncode == 64
    done, out, _ = p.execute()
    assert done.returncode == 64 and b"moved" in done.stderr and not out.exists()


def test_edited_patch_is_refused(project):
    p = project(via_patch=True)
    p.scaffold()
    p.with_checks(seven_checks())
    p.patch.write_bytes(p.patch.read_bytes() + b"\n")
    done, out, _ = p.execute()
    assert done.returncode == 64 and not out.exists()


def test_vanished_repository_is_refused(project):
    p = project()
    p.scaffold()
    plan = json.loads(p.with_checks(seven_checks()).plan.read_text())
    plan["repository"] = "../gone"
    p.plan.write_text(json.dumps(plan))
    done, out, _ = p.execute()
    assert done.returncode == 64 and b"not found" in done.stderr and not out.exists()


def test_symlinked_helper_is_refused(project):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    os.symlink("/etc/hosts", p.plan_dir / "checks" / "linked")
    done, _, _ = p.execute()
    assert done.returncode == 64 and b"symlink" in done.stderr


def test_slow_check_becomes_a_gap_not_a_finding(project):
    p = project()
    p.scaffold()
    (p.plan_dir / "checks" / "nap.py").write_text("import time\ntime.sleep(30)\n")
    slow = entry("nested-name", "regression", [INTERP, "{plan_dir}/checks/nap.py"], timeout_seconds=1)
    started = time.monotonic()
    done, _, result = p.with_checks(swap(seven_checks(), "nested-name", slow)).execute()
    assert time.monotonic() - started < 25
    assert done.returncode == 10
    assert {r["status"] for r in by_id(result, "nested-name")["runs"].values()} == {"timeout"}
    assert flagged(result) == ["two-levels-up"]


def test_parallel_runs_do_not_collide(project):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    workers = [subprocess.Popen([INTERP, str(SCRIPT), "run", "--plan", str(p.plan), "--output",
                                 str(p.root / f"lane{n}")], env=p.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE) for n in (1, 2)]
    assert [w.wait(timeout=180) for w in workers] == [1, 1]
    assert p.worktree_count() == 1


def finished_pid():
    child = subprocess.Popen([INTERP, "-c", "pass"])
    child.wait()
    return child.pid


def test_dead_owner_worktree_is_reaped_live_one_kept(project, tmp_path):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    host = socket.gethostname()
    abandoned_dir = tmp_path / "ppv-run-leftover"
    abandoned_dir.mkdir()
    abandoned, alive = abandoned_dir / "c0ffee", tmp_path / "busy-tree"
    g(p.repo, p.env, "worktree", "add", "--detach", "--lock", "--reason",
      f"ppv-owner pid={finished_pid()} host={host} dir={abandoned_dir}", str(abandoned), p.base_sha)
    g(p.repo, p.env, "worktree", "add", "--detach", "--lock", "--reason",
      f"ppv-owner pid={os.getpid()} host={host} dir={tmp_path}", str(alive), p.base_sha)
    assert p.execute()[0].returncode == 1
    listing = g(p.repo, p.env, "worktree", "list", "--porcelain")
    assert str(abandoned) not in listing and not abandoned_dir.exists()
    assert str(alive) in listing


def test_patch_bumping_a_submodule(tmp_path, gitenv):
    lib = tmp_path / "vendorlib"
    lib.mkdir()
    g(lib, gitenv, "init", "-q")
    (lib / "RELEASE").write_text("old\n")
    g(lib, gitenv, "add", "-A")
    g(lib, gitenv, "commit", "-qm", "old")
    old = g(lib, gitenv, "rev-parse", "HEAD")
    (lib / "RELEASE").write_text("new\n")
    g(lib, gitenv, "commit", "-qam", "new")
    new = g(lib, gitenv, "rev-parse", "HEAD")
    app = tmp_path / "app"
    app.mkdir()
    g(app, gitenv, "init", "-q")
    g(app, gitenv, "submodule", "add", "-q", str(lib), "third_party/vendorlib")
    g(app / "third_party" / "vendorlib", gitenv, "checkout", "-q", old)
    g(app, gitenv, "add", "-A")
    g(app, gitenv, "commit", "-qm", "vendor old lib")
    g(app / "third_party" / "vendorlib", gitenv, "checkout", "-q", new)
    bump = tmp_path / "bump.diff"
    bump.write_bytes(subprocess.run(["git", "diff", "--binary", "--submodule=short"], cwd=app,
                                    env=gitenv, check=True, capture_output=True).stdout)
    g(app / "third_party" / "vendorlib", gitenv, "checkout", "-q", old)
    plan_dir = tmp_path / "v"
    (plan_dir / "checks").mkdir(parents=True)
    plan = plan_dir / "plan.json"
    made = invoke(gitenv, "scaffold", "--repo", app, "--base-ref", "HEAD", "--patch-file", bump,
                  "--finding-id", "VND-2", "--finding-summary", "stale vendored lib",
                  "--evidence-level", "build", "--output", plan)
    assert made.returncode == 0, made.stderr
    assert json.loads(made.stdout)["submodules"] == ["third_party/vendorlib"]
    read = "open(os.path.join(os.environ['PPV_CHECKOUT'], 'third_party/vendorlib/RELEASE')).read()"
    (plan_dir / "checks" / "release.py").write_text(f"import os\nprint({read}.strip())\n")
    (plan_dir / "checks" / "is_new.py").write_text(
        f"import os, sys\nprint(os.environ['PPV_REACHED_MARKER'], flush=True)\nsys.exit(0 if {read} == 'new\\n' else 1)\n")
    noop = [INTERP, "-c", "pass"]
    body = json.loads(plan.read_text())
    body["checks"] = sorted([
        entry("a-release", "behavior", [INTERP, "{plan_dir}/checks/release.py"], compare_stream="stdout"),
        entry("b-control", "control", noop), entry("c-exploit", "exploit", [INTERP, "{plan_dir}/checks/is_new.py"]),
        entry("d-regression", "regression", noop), entry("e-security", "security", noop),
        entry("f-suite", "suite", noop), entry("g-variant", "variant", [INTERP, "{plan_dir}/checks/is_new.py"]),
    ], key=lambda c: c["id"])
    plan.write_text(json.dumps(body))
    out = tmp_path / "evidence"
    done = invoke(gitenv, "run", "--plan", plan, "--output", out)
    result = json.loads((out / "result.json").read_text())
    assert result["inputs"]["submodules"] == {"third_party/vendorlib": {"base_commit": old, "patched_commit": new}}
    assert done.returncode == 1, result["assessment"]
    assert [f["check_id"] for f in result["assessment"]["findings"]] == ["a-release"]
    runs = result["checks"][0]["runs"]
    assert (out / runs["base"]["stdout"]).read_text() == "old\n"
    assert (out / runs["patched"]["stdout"]).read_text() == "new\n"
    assert g(app, gitenv, "worktree", "list", "--porcelain").count("worktree ") == 1


def test_unavailable_submodule_commit_is_reported(tmp_path, gitenv, runner):
    g(tmp_path, gitenv, "init", "-q")
    pinned = runner.Pinned(repo=tmp_path, base="1" * 40, patched=None, patch=b"-", changed=["lib"],
                           submodules={"lib": {"base_commit": "2" * 40, "patched_commit": None}})
    trees = runner.Checkouts(pinned, holder=tmp_path, sides={"base": tmp_path / "x", "patched": tmp_path / "y"})
    trees._fill_submodule("base", "lib", "2" * 40)
    assert len(trees.setup_gaps) == 1 and "base side lacks submodule lib" in trees.setup_gaps[0]["reason"]


def test_unrelated_missing_worktree_is_left_registered(project, tmp_path):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    elsewhere = tmp_path / "colleague-tree"
    g(p.repo, p.env, "worktree", "add", "--detach", str(elsewhere), p.base_sha)

    shutil.rmtree(elsewhere)
    assert p.execute()[0].returncode == 1
    assert str(elsewhere) in g(p.repo, p.env, "worktree", "list", "--porcelain")


def test_reaper_only_trusts_runner_dirs_under_temp(runner, tmp_path):
    holder = tmp_path / "ppv-run-abc"
    assert runner.owned_location(holder, holder / "tree")
    assert not runner.owned_location(holder, tmp_path / "tree")
    assert not runner.owned_location(tmp_path / "plain", tmp_path / "plain" / "tree")
    assert not runner.owned_location(Path("/opt/ppv-run-abc"), Path("/opt/ppv-run-abc/tree"))


def test_flooding_output_is_cut_and_reported(project):
    p = project()
    p.scaffold()
    (p.plan_dir / "checks" / "flood.py").write_text(
        "import sys, time\nchunk = b'x' * (1 << 20)\n"
        "for _ in range(20):\n    sys.stdout.buffer.write(chunk)\nsys.stdout.flush()\ntime.sleep(30)\n")
    flood = entry("nested-name", "regression", [INTERP, "{plan_dir}/checks/flood.py"], timeout_seconds=60)
    started = time.monotonic()
    done, out, result = p.with_checks(swap(seven_checks(), "nested-name", flood)).execute()
    assert time.monotonic() - started < 40
    assert done.returncode == 10
    for run in by_id(result, "nested-name")["runs"].values():
        assert run["truncated"] and run["status"] == "execution_error"
        assert (out / run["stdout"]).stat().st_size == 16 << 20
    assert any("16 MiB cap" in r for r in gaps_for(result, "nested-name"))
    assert flagged(result) == ["two-levels-up"]


def test_scratch_file_count_cap(project):
    p = project()
    p.scaffold()
    (p.plan_dir / "checks" / "litter.py").write_text(
        "import os\nfor n in range(2100):\n    open(os.path.join(os.environ['PPV_SCRATCH'], f'f{n}'), 'w').close()\n")
    litter = entry("nested-name", "regression", [INTERP, "{plan_dir}/checks/litter.py"])
    done, out, result = p.with_checks(swap(seven_checks(), "nested-name", litter)).execute()
    assert done.returncode == 10
    assert any("archive cap" in r for r in gaps_for(result, "nested-name"))
    kept = list((out / "scratch" / "nested-name-base").iterdir())
    assert 0 < len(kept) <= 2000


def test_scratch_byte_cap(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "SCRATCH_BYTES_CAP", 1000)
    src, dst = tmp_path / "s", tmp_path / "d"
    src.mkdir()
    (src / "big").write_bytes(b"z" * 5000)
    assert "archive cap" in runner.keep_scratch(src, dst)


def test_unreadable_scratch_becomes_a_gap(project):
    p = project()
    p.scaffold()
    (p.plan_dir / "checks" / "lockout.py").write_text(
        "import os\nd = os.path.join(os.environ['PPV_SCRATCH'], 'sealed')\nos.mkdir(d)\n"
        "open(os.path.join(d, 'inside'), 'w').write('x')\nos.chmod(d, 0)\n")
    lock = entry("nested-name", "regression", [INTERP, "{plan_dir}/checks/lockout.py"])
    done, out, result = p.with_checks(swap(seven_checks(), "nested-name", lock)).execute()
    assert done.returncode == 10, done.stderr.decode()
    assert any("scratch archive incomplete" in r for r in gaps_for(result, "nested-name"))
    assert result["cleanup_errors"] == []
    assert p.worktree_count() == 1
    assert (out / "artifact-manifest.json").exists()


def test_go_private_settings_may_pass(project):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    done, _, result = p.execute(flags=["--allow-env", "GOPRIVATE", "--allow-env", "GONOSUMDB"],
                                more_env={"GOPRIVATE": "corp.example/*", "GONOSUMDB": "corp.example/*"})
    assert done.returncode == 1
    assert sorted(result["inputs"]["forwarded_env"]) == ["GONOSUMDB", "GOPRIVATE"]


def test_value_with_url_credentials_is_refused(project):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    done, out, _ = p.execute(flags=["--allow-env", "GOPROXY"],
                             more_env={"GOPROXY": "https://bob:hunter2@proxy.example/go"})
    assert done.returncode == 64 and b"credentials in a URL" in done.stderr and not out.exists()
