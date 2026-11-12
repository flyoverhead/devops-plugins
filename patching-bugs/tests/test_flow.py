"""End to end: the real scripts carry the demo bug to a verdict, then single facts are broken."""
import json
import shutil

import pytest

from conftest import build_run, cli, dump


def verdict(run):
    done = cli("verdict.py", run)
    return done.returncode, done.stdout.splitlines(), done.stderr


def remanifest(folder):
    assert cli("records.py", "manifest", folder).returncode == 0


@pytest.fixture
def run(demo, tmp_path):
    return build_run(demo, tmp_path)


def test_full_run_checks_and_is_ready_with_concerns(run):
    assert cli("records.py", "check", run).returncode == 0
    code, lines, _ = verdict(run)
    assert code == 0
    assert lines[0] == "READY_WITH_CONCERNS"
    assert any("regression" in line for line in lines)
    assert lines[-1] == "claim: bounded class"


def test_three_arm_result_inside_the_record(run):
    proof = json.loads((run / "prove/attempt-1/prove.json").read_text())
    assert proof["reverted"] == "pass" and proof["build_identity"] == "pass"
    assert proof["hashes"]["baseline"] != proof["hashes"]["patched"]
    assert proof["reverted_hash_note"] is None


def test_clean_regression_makes_it_ready(demo, tmp_path):
    run = build_run(demo, tmp_path, regression={
        "schema_version": 1, "campaign_dir": "/tmp/campaign", "coverage": "COMPLETE",
        "outcomes": [{"candidate_id": "c1", "outcome": "REJECTED",
                      "decision_receipt": "receipts/c1.json"}]})
    assert verdict(run)[1][0] == "READY"


@pytest.mark.parametrize("outcome,expected", [("INCOMPLETE_FIX", "NOT_READY"),
                                              ("REPRODUCED_REGRESSION", "NOT_READY"),
                                              ("UNRESOLVED", "READY_WITH_CONCERNS")])
def test_regression_outcomes(demo, tmp_path, outcome, expected):
    run = build_run(demo, tmp_path, regression={
        "schema_version": 1, "campaign_dir": "/tmp/campaign", "coverage": "COMPLETE",
        "outcomes": [{"candidate_id": "c1", "outcome": outcome, "decision_receipt": "r.json"}]})
    assert verdict(run)[1][0] == expected


def test_validation_not_confirmed_is_not_reproduced(run):
    path = run / "validate/validate.json"
    data = json.loads(path.read_text())
    data["outcome"] = "inconclusive"
    dump(path, data)
    remanifest(run / "validate")
    assert verdict(run)[1][0] == "NOT_REPRODUCED"


def test_shared_agent_identity_blocks(run):
    path = run / "prove/attempt-1/prove.json"
    data = json.loads(path.read_text())
    data["agent"] = "patcher-c3"
    dump(path, data)
    remanifest(run / "prove/attempt-1")
    code, lines, _ = verdict(run)
    assert lines[0] == "NOT_READY" and any("agent identity" in l for l in lines)


def test_baseline_that_passes_a_representative_is_a_gap(run):
    proof = run / "prove/attempt-1"
    data = json.loads((proof / "prove.json").read_text())
    case = next(c for c in data["cases"] if c["check_id"] == "two-up")
    shutil.copy(proof / case["runs"]["patched"]["stdout"], proof / case["runs"]["baseline"]["stdout"])
    case["runs"]["baseline"]["exit_code"] = 0
    dump(proof / "prove.json", data)
    remanifest(proof)
    code, lines, _ = verdict(run)
    assert lines[0] == "NOT_READY"
    assert any(l.startswith("- gap: case two-up") for l in lines)
    assert lines[-1] == "claim: exact example"


def test_patched_failure_is_a_finding(run):
    proof = run / "prove/attempt-1"
    data = json.loads((proof / "prove.json").read_text())
    case = next(c for c in data["cases"] if c["check_id"] == "nested-up")
    shutil.copy(proof / case["runs"]["baseline"]["stdout"], proof / case["runs"]["patched"]["stdout"])
    case["runs"]["patched"]["exit_code"] = 1
    dump(proof / "prove.json", data)
    remanifest(proof)
    assert any(l.startswith("- finding: case nested-up") for l in verdict(run)[1])


def test_missing_planned_case_and_empty_unproven(run):
    proof = run / "prove/attempt-1"
    data = json.loads((proof / "prove.json").read_text())
    data["cases"] = [c for c in data["cases"] if c["check_id"] != "nested-ok"]
    data["unproven"] = []
    dump(proof / "prove.json", data)
    remanifest(proof)
    lines = verdict(run)[1]
    assert "- gap: planned case nested-ok was not run" in lines
    assert "- gap: the unproven list is empty" in lines


def test_evidence_above_run_attempts_blocks(run):
    shutil.copytree(run / "patch/attempt-1", run / "patch/attempt-2")
    data = json.loads((run / "patch/attempt-2/patch.json").read_text())
    data["attempt"] = 2
    dump(run / "patch/attempt-2/patch.json", data)
    remanifest(run / "patch/attempt-2")
    lines = verdict(run)[1]
    assert lines[0] == "NOT_READY" and any("above run.attempts" in l for l in lines)


def test_not_fixed_variant_is_a_concern(demo, tmp_path):
    run = build_run(demo, tmp_path, regression={
        "schema_version": 1, "campaign_dir": "/tmp/c", "coverage": "COMPLETE", "outcomes": []})
    attempt = run / "patch/attempt-1"
    data = json.loads((attempt / "patch.json").read_text())
    data["variants"].append({"location": "other.sh:9", "status": "not_fixed", "reason": "out of scope"})
    dump(attempt / "patch.json", data)
    remanifest(attempt)
    lines = verdict(run)[1]
    assert lines[0] == "READY_WITH_CONCERNS" and any("other.sh:9" in l for l in lines)


def test_missing_reproduce_record_exits_1(run):
    shutil.rmtree(run / "reproduce")
    code, _, err = verdict(run)
    assert code == 1 and "reproduce" in err


def test_tampered_receipt_fails_check_and_verdict(run):
    receipt = run / "prove/attempt-1/receipts/cases/two-up/baseline.stdout"
    receipt.write_text(receipt.read_text() + "edited\n")
    done = cli("records.py", "check", run)
    assert done.returncode == 1 and "changed" in done.stderr
    assert verdict(run)[0] == 1


def test_verdict_usage(tmp_path):
    assert cli("verdict.py").returncode == 2


def test_arm_receipts_must_agree_with_prove_json(run):
    proof = run / "prove/attempt-1"
    data = json.loads((proof / "prove.json").read_text())
    arm = json.loads((proof / "receipts/reverted/arm.json").read_text())
    arm["exit_code"] = 0
    dump(proof / "receipts/reverted/arm.json", arm)
    remanifest(proof)
    lines = verdict(run)[1]
    assert lines[0] == "NOT_READY"
    assert any("prove.json reverted differs" in l for l in lines)
    assert data["reverted"] == "pass"
