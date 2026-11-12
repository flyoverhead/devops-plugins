"""arms.py on a demo repo: three arms, planned cases, refusals and clean-up."""
import json
import shutil
import sys

import pytest

from conftest import BUILD, cli, dump, git

ARM_KEYS = {"name", "commit", "build_exit", "diagnostic_matched", "artifact_sha256",
            "loaded_identity", "reached", "exit_code"}


def three(demo, out, *extra, poc=None, env_skip=False):
    args = ["run", "--repo", demo.repo, "--baseline", demo.base, "--patch", demo.patch,
            "--build", json.dumps(BUILD), "--out", out]
    if poc is not False:
        args += ["--poc", json.dumps(poc or demo.poc()), "--artifact", "bin/tool"]
    return cli("arms.py", *args, *extra)


def test_runtime_three_arms_pass(demo, tmp_path):
    out = tmp_path / "proof"
    head_before = git(demo.repo, "rev-parse", "HEAD")
    done = three(demo, out)
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["failure_type"] == "runtime"
    assert result["reverted"] == "pass" and result["build_identity"] == "pass"
    assert result["hashes"]["baseline"] == result["hashes"]["reverted"] != result["hashes"]["patched"]
    assert result["reverted_hash_note"] is None
    source = json.loads((out / "receipts/source.json").read_text())
    assert set(source) == {"baseline_commit", "patch_commit", "trees"}
    assert source["trees"]["reverted"] == source["trees"]["baseline"] != source["trees"]["patched"]
    for arm in ("baseline", "patched", "reverted"):
        fact = json.loads((out / "receipts" / arm / "arm.json").read_text())
        assert set(fact) == ARM_KEYS and fact["name"] == arm and fact["reached"]
        for part in ("build", "poc"):
            for name in ("stdout.txt", "stderr.txt", "exit.json"):
                assert (out / "receipts" / arm / part / name).is_file()
        assert set(json.loads((out / "receipts" / arm / "poc/exit.json").read_text())) == {"exit_code", "elapsed_s"}
    assert json.loads((out / "receipts/baseline/arm.json").read_text())["exit_code"] == 1
    assert json.loads((out / "receipts/patched/arm.json").read_text())["exit_code"] == 0
    assert cli("records.py", "check", tmp_path / "missing").returncode == 1
    assert (out / "manifest.json").is_file()
    assert demo.worktree_count() == 1
    assert git(demo.repo, "rev-parse", "HEAD") == head_before
    assert git(demo.repo, "status", "--porcelain") == ""
    assert not list(tmp_path.glob(".proof-trees-*")) and not list(tmp_path.glob("patching-bugs-trees-*"))


def test_poc_sees_neutral_tree_names(demo, tmp_path):
    spy = tmp_path / "spy.py"
    spy.write_text("import sys; print(sys.argv[1]); print('PATCH_REACHED')\n")
    done = three(demo, tmp_path / "proof", poc=[sys.executable, str(spy), "{tree}"])
    assert done.returncode == 0
    for arm in ("baseline", "patched", "reverted"):
        line = (tmp_path / "proof/receipts" / arm / "poc/stdout.txt").read_text().splitlines()[0]
        assert arm not in line.rsplit("/", 1)[-1]


def test_missing_reached_is_inconclusive(demo, tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_SKIP_REACHED", "1")
    result = json.loads(three(demo, tmp_path / "proof").stdout)
    assert result["reverted"] == "inconclusive"


def test_wrong_identity_fails_build_identity(demo, tmp_path):
    liar = tmp_path / "liar.py"
    liar.write_text('print(\'PATCH_LOADED {"path": "/nowhere", "sha256": "' + "0" * 64 + '"}\')\n'
                    "print('PATCH_REACHED')\n")
    result = json.loads(three(demo, tmp_path / "proof", poc=[sys.executable, str(liar)]).stdout)
    assert result["build_identity"] == "fail"
    assert result["reverted"] == "fail"


def test_compile_mode(demo, tmp_path):
    (demo.repo / "tool.sh").write_text("BROKEN\n")
    git(demo.repo, "commit", "-qam", "break")
    broken = git(demo.repo, "rev-parse", "HEAD")
    (demo.repo / "tool.sh").write_text("fine\n")
    git(demo.repo, "commit", "-qam", "mend")
    mended = git(demo.repo, "rev-parse", "HEAD")
    build = ["sh", "-c", "if grep -q BROKEN tool.sh; then echo 'tool.sh:1: BROKEN token' >&2; exit 2; fi"]
    done = cli("arms.py", "run", "--repo", demo.repo, "--baseline", broken, "--patch", mended,
               "--build", json.dumps(build), "--out", tmp_path / "c", "--failure-type", "compile",
               "--expected-diagnostic", "BROKEN token")
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result == {"failure_type": "compile", "reverted": "pass", "build_identity": "not_applicable",
                      "hashes": {"baseline": None, "patched": None, "reverted": None},
                      "reverted_hash_note": None}
    assert json.loads((tmp_path / "c/receipts/baseline/arm.json").read_text())["diagnostic_matched"]


@pytest.mark.parametrize("extra,needle", [
    (["--poc", "[]", "--artifact", "bin/tool"], "--poc"),
    (["--poc", '["x"]', "--artifact", "../bin/tool"], "--artifact"),
    (["--poc", '["x"]', "--artifact", "/abs/tool"], "--artifact"),
    (["--poc", "not json", "--artifact", "bin/tool"], "JSON"),
    (["--failure-type", "compile", "--expected-diagnostic", " "], "expected-diagnostic"),
    (["--failure-type", "compile", "--expected-diagnostic", "x", "--poc", '["x"]'], "neither"),
])
def test_run_argument_rules(demo, tmp_path, extra, needle):
    done = three(demo, tmp_path / "o", *extra, poc=False)
    assert done.returncode == 1 and needle in done.stderr
    assert demo.worktree_count() == 1


def test_build_must_be_nonempty(demo, tmp_path):
    done = cli("arms.py", "run", "--repo", demo.repo, "--baseline", demo.base, "--patch", demo.patch,
               "--build", "[]", "--out", tmp_path / "o", "--failure-type", "compile",
               "--expected-diagnostic", "x")
    assert done.returncode == 1 and "--build" in done.stderr


@pytest.mark.parametrize("drop", ["--repo", "--baseline", "--patch", "--build", "--out"])
def test_required_flags_are_usage_errors(demo, tmp_path, drop):
    full = {"--repo": demo.repo, "--baseline": demo.base, "--patch": demo.patch,
            "--build": json.dumps(BUILD), "--out": tmp_path / "o"}
    args = [x for k, v in full.items() if k != drop for x in (k, v)]
    assert cli("arms.py", "run", *args).returncode == 2


def test_unknown_commit_leaves_no_worktree(demo, tmp_path):
    done = cli("arms.py", "run", "--repo", demo.repo, "--baseline", "f" * 40, "--patch", demo.patch,
               "--build", json.dumps(BUILD), "--out", tmp_path / "o", "--poc", '["x"]',
               "--artifact", "bin/tool")
    assert done.returncode == 1 and demo.worktree_count() == 1


def test_attempt_dir_is_never_overwritten(demo, tmp_path):
    out = tmp_path / "proof"
    assert three(demo, out).returncode == 0
    again = three(demo, out)
    assert again.returncode == 1 and "already exists" in again.stderr
    assert demo.worktree_count() == 1


def test_timeout_is_null_exit(demo, tmp_path):
    slow = tmp_path / "slow.py"
    slow.write_text("import time; time.sleep(5)\n")
    done = three(demo, tmp_path / "proof", "--timeout", "1", poc=[sys.executable, str(slow)])
    result = json.loads(done.stdout)
    assert json.loads((tmp_path / "proof/receipts/baseline/poc/exit.json").read_text())["exit_code"] is None
    assert result["reverted"] == "inconclusive"
    assert demo.worktree_count() == 1


def test_cases_baseline_only(demo, tmp_path):
    plan = tmp_path / "plan.json"
    dump(plan, [{"check_id": "two-up", "argv": demo.poc()},
                {"check_id": "ok", "argv": demo.poc('"go/http.txt"')}])
    out = tmp_path / "reproduce"
    done = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base,
               "--build", json.dumps(BUILD), "--plan", plan, "--out", out, "--artifact", "bin/tool")
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert set(result["commits"]) == {"baseline"}
    made = result["build"]["baseline"]["artifact"]
    assert cli("markers.py", "check-stdout", out / "receipts/cases/two-up/baseline.stdout",
               "--runtime-identity", made["path"], made["sha256"]).returncode == 0
    assert cli("markers.py", "check-stdout", out / "receipts/cases/two-up/baseline.stdout",
               "--runtime-identity", made["path"], "0" * 64).returncode == 1
    runs = {r["check_id"]: r["runs"] for r in result["runs"]}
    assert set(runs["two-up"]) == {"baseline"}
    assert runs["two-up"]["baseline"]["exit_code"] == 1 and runs["ok"]["baseline"]["exit_code"] == 0
    assert runs["two-up"]["baseline"]["stdout"] == "receipts/cases/two-up/baseline.stdout"
    exit_rec = json.loads((out / "receipts/cases/two-up/baseline.exit.json").read_text())
    assert set(exit_rec) == {"exit_code", "elapsed_ms"}
    assert check_stdout(out / runs["two-up"]["baseline"]["stdout"], '"../../out.txt"') == 0
    launch = json.loads((out / "receipts/cases/launch.json").read_text())
    assert launch["commits"] == {"baseline": demo.base} and "argv" in launch
    assert demo.worktree_count() == 1 and git(demo.repo, "status", "--porcelain") == ""


def check_stdout(path, planned):
    return cli("markers.py", "check-stdout", path, "--input", planned).returncode


def test_cases_both_sides_and_failed_build(demo, tmp_path):
    plan = tmp_path / "plan.json"
    dump(plan, [{"check_id": "two-up", "argv": demo.poc()}])
    done = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base, "--patch",
               demo.patch, "--build", json.dumps(BUILD), "--plan", plan, "--out", tmp_path / "p")
    runs = json.loads(done.stdout)["runs"][0]["runs"]
    assert runs["baseline"]["exit_code"] == 1 and runs["patched"]["exit_code"] == 0
    bad = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base,
              "--build", '["false"]', "--plan", plan, "--out", tmp_path / "q")
    result = json.loads(bad.stdout)
    assert result["build"]["baseline"]["exit_code"] == 1 and result["runs"][0]["runs"] == {}


def test_cases_artifact_must_stay_inside(demo, tmp_path):
    plan = tmp_path / "plan.json"
    dump(plan, [])
    done = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base, "--build",
               json.dumps(BUILD), "--plan", plan, "--out", tmp_path / "o", "--artifact", "../x")
    assert done.returncode == 1 and "--artifact" in done.stderr


def test_cases_empty_plan_is_a_build_check(demo, tmp_path):
    plan = tmp_path / "plan.json"
    dump(plan, [])
    done = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base, "--build",
               json.dumps(BUILD), "--plan", plan, "--out", tmp_path / "pre")
    assert done.returncode == 0
    assert json.loads(done.stdout)["build"]["baseline"]["exit_code"] == 0
    assert (tmp_path / "pre/receipts/cases/_build/baseline.stderr").is_file()


@pytest.mark.parametrize("plan", [
    {"check_id": "x", "argv": ["a"]},
    [{"check_id": "../x", "argv": ["a"]}],
    [{"check_id": "x", "argv": []}],
    [{"check_id": "x", "argv": ["a"], "extra": 1}],
    [{"check_id": "x", "argv": ["a"]}, {"check_id": "x", "argv": ["b"]}],
])
def test_cases_plan_rules(demo, tmp_path, plan):
    path = tmp_path / "plan.json"
    dump(path, plan)
    done = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base,
               "--build", json.dumps(BUILD), "--plan", path, "--out", tmp_path / "o")
    assert done.returncode == 1


def test_cases_refuses_a_tracked_change(demo, tmp_path):
    plan = tmp_path / "plan.json"
    dump(plan, [{"check_id": "a", "argv": ["sh", "-c", "echo x >> {tree}/tool.sh"]},
                {"check_id": "b", "argv": ["true"]}])
    done = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base,
               "--build", json.dumps(BUILD), "--plan", plan, "--out", tmp_path / "o")
    assert done.returncode == 1 and "tracked files" in done.stderr
    assert demo.worktree_count() == 1


def test_scratch_parent_writes_stay_out_of_the_run(demo, tmp_path):
    run = tmp_path / "run"
    plan = tmp_path / "plan.json"
    dump(plan, [{"check_id": "climb", "argv": ["sh", "-c", "echo x > {scratch}/../../escaped; echo PATCH_REACHED"]}])
    done = cli("arms.py", "cases", "--repo", demo.repo, "--baseline", demo.base, "--build",
               json.dumps(BUILD), "--plan", plan, "--out", run / "prove" / "attempt-1")
    assert done.returncode == 0, done.stderr
    assert not list(tmp_path.rglob("escaped"))
    assert sorted(p.name for p in (run / "prove").iterdir()) == ["attempt-1"]


def test_cleanup_keeps_the_users_stale_worktrees(demo, tmp_path):
    mine = tmp_path / "users-tree"
    git(demo.repo, "worktree", "add", "--detach", str(mine), demo.base)
    shutil.rmtree(mine)
    before = git(demo.repo, "worktree", "list", "--porcelain")
    assert three(demo, tmp_path / "proof").returncode == 0
    assert git(demo.repo, "worktree", "list", "--porcelain") == before


def test_failed_remove_drops_only_our_admin_entries(demo, tmp_path, arms_mod):
    trees = arms_mod.Trees(demo.repo, tmp_path / "out")
    ours = trees.add(demo.base)
    stale = tmp_path / "users-tree"
    git(demo.repo, "worktree", "add", "--detach", str(stale), demo.base)
    shutil.rmtree(stale)
    shutil.rmtree(ours)
    trees.made = []
    trees.close()
    listing = git(demo.repo, "worktree", "list", "--porcelain")
    assert str(stale) in listing or stale.name in listing
    assert ours.name not in listing
