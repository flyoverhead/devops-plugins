"""records.py: field rules of every record, manifests, the before-repair gate, guidance copies."""
import copy
import json
import os

import pytest

from conftest import SCOPE, cli, dump, finding, git

SHA_A, SHA_B = "a" * 40, "b" * 40
HEX = "c" * 64


def run_rec(**over):
    data = {"schema_version": 1, "finding_id": "SV-1", "status": "in_progress", "attempts": 0,
            "steps": {k: "pending" for k in ("intake", "reproduce", "validate", "patch", "prove",
                                             "regression", "report")}}
    data.update(over)
    return data


def reproduce_rec(**over):
    data = {"schema_version": 1, "outcome": "reproduced", "baseline_commit": SHA_A,
            "build_argv": ["go", "build", "-o", "bin/x", "./cmd/x"], "poc_argv": ["poc", "{tree}"],
            "target_artifact": "bin/x", "observed": "file outside", "blocker": None,
            "agent": "reproducer-1", "failure_type": "runtime"}
    data.update(over)
    return data


def patch_rec(**over):
    data = {"schema_version": 1, "attempt": 1, "baseline_commit": SHA_A, "patch_commit": SHA_B,
            "files_changed": 2, "lines_added": 10, "lines_removed": 1,
            "variants": [{"location": "vault.go:30", "status": "fixed", "reason": "same join"}],
            "suite_before": {"command": "go test ./...", "passed": 2, "failed": 0, "skipped": 0},
            "suite_after": {"command": "go test ./...", "passed": 3, "failed": 0, "skipped": 0},
            "agent": "patcher-1"}
    data.update(over)
    return data


def receipt(rel):
    return {"exit_code": 1, "elapsed_ms": 5, "stdout": f"{rel}.stdout", "stderr": f"{rel}.stderr"}


def prove_rec(**over):
    data = {"schema_version": 2, "attempt": 1, "failure_type": "runtime", "baseline_commit": SHA_A,
            "patch_commit": SHA_B, "reverted": "pass", "build_identity": "pass",
            "hashes": {"baseline": "1" * 64, "patched": "2" * 64, "reverted": "1" * 64},
            "reverted_hash_note": None,
            "cases": [{"check_id": "two-up", "argv": ["h"], "source": "receipts/h.py",
                       "runs": {"baseline": receipt("receipts/c/b"), "patched": receipt("receipts/c/p")}}],
            "project_checks": [{"check_id": "suite", "kind": "suite", "argv": ["go", "test"],
                                "baseline": None, "patched": receipt("receipts/s/p")}],
            "unproven": ["windows paths"], "agent": "prover-1"}
    data.update(over)
    return data


def lay_prove(run, data, number=1):
    folder = run / "prove" / f"attempt-{number}"
    for rel in ("receipts/h.py", "receipts/c/b.stdout", "receipts/c/b.stderr", "receipts/c/p.stdout",
                "receipts/c/p.stderr", "receipts/s/p.stdout", "receipts/s/p.stderr"):
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text("x\n")
    dump(folder / "prove.json", data)
    assert cli("records.py", "manifest", folder).returncode == 0
    return folder


def check(run, *flags):
    return cli("records.py", "check", run, *flags)


@pytest.fixture
def run(tmp_path):
    folder = tmp_path / "run"
    dump(folder / "run.json", run_rec())
    dump(folder / "finding.json", finding(status="hypothesis"))
    return folder


def test_minimal_run_passes(run):
    done = check(run)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == ""


@pytest.mark.parametrize("mutate,needle", [
    (lambda f: f.update(title="x" * 121), "title"),
    (lambda f: f.update(claim=""), "claim"),
    (lambda f: f.update(status="fixed"), "status"),
    (lambda f: f.update(schema_version=2), "schema_version"),
    (lambda f: f.update(colour="red"), "unexpected"),
    (lambda f: f.update(poc=""), "poc"),
    (lambda f: f["affected_code"][0].pop("end_line"), "end_line"),
    (lambda f: f["affected_code"][0].update(start_line=-1), "start_line"),
    (lambda f: f["reported"].update(mood="bad"), "unexpected"),
    (lambda f: f["repair_scope"].pop("exclusions"), "exclusions"),
    (lambda f: f["repair_scope"].update(mode="wide"), "mode"),
    (lambda f: f["repair_scope"]["cases"][0].update(role="probe"), "role"),
    (lambda f: f["repair_scope"]["cases"][0].pop("why"), "why"),
    (lambda f: f.update(source=True), "source"),
])
def test_finding_rules(run, mutate, needle):
    data = finding()
    mutate(data)
    dump(run / "finding.json", data)
    done = check(run)
    assert done.returncode == 1 and needle in done.stderr


def test_absent_optional_parts_are_fine(run):
    data = finding()
    del data["reported"], data["repair_scope"]
    dump(run / "finding.json", data)
    assert check(run).returncode == 0


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(attempts=4),
    lambda r: r.update(attempts=True),
    lambda r: r["steps"].pop("report"),
    lambda r: r["steps"].update(extra="done"),
    lambda r: r["steps"].update(prove="running"),
    lambda r: r.update(status="done"),
])
def test_run_rules(run, mutate):
    data = run_rec()
    mutate(data)
    dump(run / "run.json", data)
    assert check(run).returncode == 1


def lay_step(run, step, name, data):
    dump(run / step / name, data)
    assert cli("records.py", "manifest", run / step).returncode == 0


@pytest.mark.parametrize("over,ok", [
    ({}, True),
    ({"failure_type": None}, False),
    ({"baseline_commit": "A" * 40}, False),
    ({"baseline_commit": "a" * 39}, False),
    ({"target_artifact": None}, False),
    ({"build_argv": ["x" * 401]}, False),
    ({"observed": "y" * 401}, False),
    ({"agent": ""}, False),
    ({"outcome": "maybe"}, False),
    ({"failure_type": "compile", "target_artifact": None, "poc_argv": [],
      "expected_diagnostic": "undefined: Foo"}, True),
    ({"failure_type": "compile", "target_artifact": None, "poc_argv": []}, False),
    ({"failure_type": "compile", "target_artifact": None, "poc_argv": ["x"],
      "expected_diagnostic": "e"}, False),
    ({"failure_type": "compile", "target_artifact": None, "poc_argv": [], "build_argv": [],
      "expected_diagnostic": "e"}, False),
    ({"failure_type": "compile", "poc_argv": [], "expected_diagnostic": "e"}, False),
])
def test_reproduce_rules(run, over, ok):
    data = reproduce_rec(**over)
    if over.get("failure_type", "") is None:
        del data["failure_type"]
        data["target_artifact"] = None
    lay_step(run, "reproduce", "reproduce.json", data)
    assert (check(run).returncode == 0) is ok


def test_reproduce_without_failure_type_is_runtime(run):
    data = reproduce_rec()
    del data["failure_type"]
    lay_step(run, "reproduce", "reproduce.json", data)
    assert check(run).returncode == 0


@pytest.mark.parametrize("over,ok", [
    ({}, True),
    ({"outcome": "yes"}, False),
    ({"reason": "r" * 401}, False),
    ({"note": "x"}, False),
])
def test_validate_rules(run, over, ok):
    data = {"schema_version": 1, "outcome": "confirmed", "agent": "v-1", "reason": "same escape"}
    data.update(over)
    lay_step(run, "validate", "validate.json", data)
    assert (check(run).returncode == 0) is ok


@pytest.mark.parametrize("over,ok", [
    ({}, True),
    ({"patch_commit": None}, True),
    ({"attempt": 2}, False),
    ({"lines_added": -1}, False),
    ({"variants": [{"location": "x", "status": "skipped", "reason": "r"}]}, False),
    ({"variants": [{"location": "x", "status": "fixed", "reason": "r" * 201}]}, False),
    ({"suite_after": {"command": "go test", "passed": 1, "failed": 0}}, False),
])
def test_patch_rules(run, over, ok):
    folder = run / "patch" / "attempt-1"
    dump(folder / "patch.json", patch_rec(**over))
    cli("records.py", "manifest", folder)
    assert (check(run).returncode == 0) is ok


def test_attempt_directory_names(run):
    folder = run / "patch" / "attempt-4"
    dump(folder / "patch.json", patch_rec())
    cli("records.py", "manifest", folder)
    done = check(run)
    assert done.returncode == 1 and "attempt-1..3" in done.stderr


@pytest.mark.parametrize("over,ok", [
    ({}, True),
    ({"schema_version": 1}, False),
    ({"build_identity": "not_applicable"}, False),
    ({"hashes": {"baseline": "1" * 64, "patched": "1" * 64, "reverted": "1" * 64}}, False),
    ({"hashes": {"baseline": "1" * 64, "patched": None, "reverted": "1" * 64}}, False),
    ({"hashes": {"baseline": "1" * 64, "patched": "2" * 64}}, False),
    ({"build_identity": "fail", "hashes": {"baseline": None, "patched": None, "reverted": None}}, True),
    ({"failure_type": "compile", "build_identity": "not_applicable",
      "hashes": {"baseline": None, "patched": None, "reverted": None}}, True),
    ({"failure_type": "compile", "build_identity": "pass"}, False),
    ({"failure_type": "compile", "build_identity": "not_applicable"}, False),
    ({"reverted": "maybe"}, False),
    ({"unproven": [""]}, False),
    ({"attempt": 2}, False),
])
def test_prove_rules(run, over, ok):
    lay_prove(run, prove_rec(**over))
    assert (check(run).returncode == 0) is ok


@pytest.mark.parametrize("mutate,needle", [
    (lambda p: p["cases"][0].update(source="h.py"), "receipts/"),
    (lambda p: p["cases"][0].update(source="receipts/../h.py"), "receipts/"),
    (lambda p: p["cases"][0].update(source="receipts/other.py"), "not retained"),
    (lambda p: p["cases"][0]["runs"]["patched"].update(stdout="receipts/gone"), "not retained"),
    (lambda p: p["cases"][0].update(check_id="invented"), "repair_scope"),
    (lambda p: p["cases"].append(copy.deepcopy(p["cases"][0])), "repeated"),
    (lambda p: p["project_checks"][0].update(kind="lint"), "kind"),
    (lambda p: p["project_checks"][0]["patched"].update(exit_code="0"), "exit_code"),
    (lambda p: p["project_checks"][0].update(argv=["go", ""]), "argv"),
    (lambda p: p["cases"][0]["runs"].pop("patched"), "patched"),
])
def test_prove_receipts_and_cases(run, mutate, needle):
    data = prove_rec()
    mutate(data)
    lay_prove(run, data)
    done = check(run)
    assert done.returncode == 1 and needle in done.stderr


def test_regression_rules(run):
    good = {"schema_version": 1, "campaign_dir": "/tmp/c", "coverage": "COMPLETE",
            "outcomes": [{"candidate_id": "c1", "outcome": "LATENT_BUG", "decision_receipt": "d.json"}]}
    lay_step(run, "regression", "regression.json", good)
    assert check(run).returncode == 0
    good["outcomes"][0]["outcome"] = "FIXED"
    lay_step(run, "regression", "regression.json", good)
    assert check(run).returncode == 1


def test_manifest_detects_missing_extra_changed(run):
    lay_step(run, "validate", "validate.json",
             {"schema_version": 1, "outcome": "confirmed", "agent": "v", "reason": "r"})
    (run / "validate/receipts").mkdir()
    extra = run / "validate/receipts/late.txt"
    extra.write_text("late")
    assert "not in manifest" in check(run).stderr
    cli("records.py", "manifest", run / "validate")
    extra.write_text("edited")
    assert "changed" in check(run).stderr
    extra.unlink()
    assert "missing" in check(run).stderr
    (run / "validate/manifest.json").unlink()
    assert "no manifest" in check(run).stderr


def test_manifest_format_and_symlinks(tmp_path):
    step = tmp_path / "step"
    (step / "receipts").mkdir(parents=True)
    dump(tmp_path / "run.json", run_rec())
    (step / "receipts/b.txt").write_text("b")
    (step / "a.json").write_text("{}")
    done = cli("records.py", "manifest", step)
    assert done.returncode == 0 and done.stdout == ""
    text = (step / "manifest.json").read_text()
    assert text.endswith("}\n") and text.startswith("{\n  ")
    data = json.loads(text)
    assert set(data) == {"schema_version", "files"} and list(data["files"]) == ["a.json", "receipts/b.txt"]
    os.symlink(step / "a.json", step / "receipts/link")
    assert cli("records.py", "manifest", step).returncode == 1
    assert cli("records.py", "manifest", tmp_path / "absent").returncode == 1
    os.symlink(step, tmp_path / "linked")
    assert cli("records.py", "manifest", tmp_path / "linked").returncode == 1


def test_manifest_refuses_misplaced_steps(tmp_path):
    orphan = tmp_path / "loose" / "reproduce"
    orphan.mkdir(parents=True)
    done = cli("records.py", "manifest", orphan)
    assert done.returncode == 1 and "run.json or finding.json" in done.stderr
    repo = tmp_path / "repo"
    (repo / "run" / "reproduce").mkdir(parents=True)
    git(repo, "init", "-q")
    dump(repo / "run" / "run.json", run_rec())
    done = cli("records.py", "manifest", repo / "run" / "reproduce")
    assert done.returncode == 1 and "work tree" in done.stderr
    standalone = tmp_path / "solo"
    (standalone / "reproduce").mkdir(parents=True)
    dump(standalone / "finding.json", finding(status="hypothesis"))
    assert cli("records.py", "manifest", standalone / "reproduce").returncode == 0
    attempt = tmp_path / "ok" / "prove" / "attempt-1"
    attempt.mkdir(parents=True)
    dump(tmp_path / "ok" / "run.json", run_rec())
    assert cli("records.py", "manifest", attempt).returncode == 0


def test_usage_errors_exit_2(run):
    assert cli("records.py", "manifest", run, "--before-repair").returncode == 2
    assert cli("records.py").returncode == 2
    assert cli("records.py", "verify", run).returncode == 2


@pytest.mark.parametrize("mutate,needle", [
    (lambda s: None, None),
    (lambda s: s.update(mode="exact_example", cases=[s["cases"][2]]), "no representative"),
    (lambda s: s.update(cases=s["cases"][:1] + s["cases"][2:]), "two representative"),
    (lambda s: s.update(cases=s["cases"][:2]), "control"),
    (lambda s: s["cases"][1].update(check_id="two-up"), "check_id"),
    (lambda s: s["cases"][1].update(input="../../out.txt"), "repeats an input"),
    (lambda s: (s["cases"][0].update(input={"a": 1, "b": 2}),
                s["cases"][1].update(input={"b": 2, "a": 1})), "repeats an input"),
])
def test_before_repair_scope_gate(run, mutate, needle):
    data = finding()
    mutate(data["repair_scope"])
    dump(run / "finding.json", data)
    done = check(run, "--before-repair")
    if needle is None:
        assert done.returncode == 0, done.stderr
    else:
        assert done.returncode == 1 and needle in done.stderr


def test_exact_example_needs_only_one_representative(run):
    data = finding()
    data["repair_scope"].update(mode="exact_example", cases=[SCOPE["cases"][0]])
    dump(run / "finding.json", data)
    assert check(run, "--before-repair").returncode == 0


def test_before_repair_needs_scope_and_free_attempt(run):
    data = finding()
    del data["repair_scope"]
    dump(run / "finding.json", data)
    assert "repair_scope" in check(run, "--before-repair").stderr
    assert check(run).returncode == 0
    dump(run / "finding.json", finding())
    folder = run / "patch" / "attempt-1"
    dump(folder / "patch.json", patch_rec(patch_commit=None))
    cli("records.py", "manifest", folder)
    assert "run.attempts" in check(run, "--before-repair").stderr
    dump(run / "run.json", run_rec(attempts=1))
    assert check(run, "--before-repair").returncode == 0
    for n in (2, 3):
        folder = run / "patch" / f"attempt-{n}"
        dump(folder / "patch.json", patch_rec(attempt=n, patch_commit=None))
        cli("records.py", "manifest", folder)
    dump(run / "run.json", run_rec(attempts=3))
    assert "attempt-3 exists" in check(run, "--before-repair").stderr


def test_third_attempt_is_reachable(run):
    dump(run / "finding.json", finding())
    for n in (1, 2):
        folder = run / "patch" / f"attempt-{n}"
        dump(folder / "patch.json", patch_rec(attempt=n, patch_commit=None))
        cli("records.py", "manifest", folder)
    dump(run / "run.json", run_rec(attempts=2))
    done = check(run, "--before-repair")
    assert done.returncode == 0, done.stderr


def test_report_input_rules(run):
    lay_step(run, "validate", "validate.json",
             {"schema_version": 1, "outcome": "confirmed", "agent": "v", "reason": "r"})
    good = {"schema_version": 1, "bug": "escape", "fix_why": "", "open_risks": [],
            "include_poc": False, "run_metadata": {"date": "2026-11-11", "model": "m"}}
    dump(run / "report-input.json", good)
    assert check(run).returncode == 0
    for bad in ({"open_risks": ["r"] * 6}, {"include_poc": "no"}, {"fix_why": "w" * 401},
                {"run_metadata": {"date": "11/11/2026"}}, {"extra": 1}):
        dump(run / "report-input.json", {**good, **bad})
        assert check(run).returncode == 1, bad
    item = {"check_id": "two-up", "reproduce": {"stdout": "receipts/a.stdout", "exit": "receipts/a.exit.json"},
            "validate": {"stdout": "receipts/a.stdout", "exit": "receipts/a.exit.json"}}
    dump(run / "report-input.json", {**good, "baseline_checks": [item]})
    assert "reproduce" in check(run).stderr
    for step in ("reproduce", "validate"):
        (run / step / "receipts").mkdir(parents=True, exist_ok=True)
        (run / step / "receipts/a.stdout").write_text("PATCH_REACHED\n")
        dump(run / step / "receipts/a.exit.json", {"exit_code": 1})
    lay_step(run, "reproduce", "reproduce.json", reproduce_rec())
    cli("records.py", "manifest", run / "validate")
    assert check(run).returncode == 0, check(run).stderr
    dump(run / "validate/receipts/a.exit.json", {"code": 1})
    cli("records.py", "manifest", run / "validate")
    assert "exit_code" in check(run).stderr


def test_guidance_reads_commit_objects(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "CLAUDE.md").write_text("commit rules: fix(scope)\n")
    (repo / "THREAT_MODEL.md").write_text("names come from users\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "docs")
    sha = git(repo, "rev-parse", "HEAD")
    (repo / "CLAUDE.md").write_text("edited in the working tree\n")
    (repo / "AGENTS.md").write_text("untracked\n")
    run = tmp_path / "run"
    done = cli("records.py", "guidance", run, "--repo", repo, "--commit", sha[:8])
    assert done.returncode == 0, done.stderr
    folder = run / "guidance" / sha
    assert (folder / "CLAUDE.md").read_text() == "commit rules: fix(scope)\n"
    assert not (folder / "AGENTS.md").exists()
    source = (folder / "source.md").read_text()
    assert sha in source and "`AGENTS.md`" in source and "`PATCHING_GUIDELINES.md`" in source
    assert f"=== AGENTS.md @ {sha} ===\nabsent" in done.stdout
    assert "commit rules" in done.stdout
    assert cli("records.py", "guidance", run, "--repo", repo, "--commit", sha).returncode == 0
    (folder / "THREAT_MODEL.md").write_text("tampered\n")
    again = cli("records.py", "guidance", run, "--repo", repo, "--commit", sha)
    assert again.returncode == 1 and "THREAT_MODEL.md" in again.stderr


def test_guidance_refuses_run_dir_inside_checkout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "commit", "-q", "--allow-empty", "-m", "x")
    done = cli("records.py", "guidance", repo / "run", "--repo", repo, "--commit", "HEAD")
    assert done.returncode == 1 and "outside" in done.stderr
    assert cli("records.py", "guidance", tmp_path / "r", "--repo", repo, "--commit", "f" * 40).returncode == 1
