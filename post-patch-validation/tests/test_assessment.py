"""The judging rules, fed with hand-made run records."""
import copy

import pytest

EVERY_KIND = dict.fromkeys(("control", "exploit", "variant", "behavior", "regression", "security", "suite"), 1)


def rec(code=0, state="completed", reached=None, want="zero"):
    done = state == "completed"
    return {"status": state, "exit_code": code if done else None, "expected": want,
            "matched": done and ((code == 0) == (want == "zero")), "marker": reached}


def pair(base_rc=0, patched_rc=0):
    return {"base": rec(base_rc), "patched": rec(patched_rc)}


def blind_pair(base_rc=1, patched_rc=0, base_seen=True, patched_seen=True):
    return {"base": rec(base_rc, reached=base_seen, want="nonzero"),
            "patched": rec(patched_rc, reached=patched_seen)}


def tidy_plan():
    return [
        {"id": "b", "kind": "behavior", "runs": pair(), "comparison": {"stream": "stdout", "matched": True}},
        {"id": "c", "kind": "control", "runs": pair()},
        {"id": "e", "kind": "exploit", "runs": blind_pair()},
        {"id": "r", "kind": "regression", "runs": pair()},
        {"id": "s", "kind": "security", "runs": pair()},
        {"id": "u", "kind": "suite", "runs": {"patched": rec()}},
        {"id": "v", "kind": "variant", "runs": blind_pair()},
    ]


def altered(**edits):
    checks = tidy_plan()
    for cid, change in edits.items():
        change(next(c for c in checks if c["id"] == cid))
    return checks


def ids(items):
    return [i["check_id"] for i in items]


def test_all_clean(runner):
    verdict = runner.judge(tidy_plan(), EVERY_KIND)
    assert verdict == {"status": "complete", "findings": [], "gaps": [], "human_review_required": True}
    assert runner.exit_status(verdict) == runner.OK_NOTHING == 0


def test_finding_survives_next_to_an_unrelated_gap(runner):
    verdict = runner.judge(altered(v=lambda c: c.update(runs=blind_pair(patched_rc=1)),
                                   r=lambda c: c["runs"].update(patched=rec(state="timeout"))), EVERY_KIND)
    assert ids(verdict["findings"]) == ["v"] and ids(verdict["gaps"]) == ["r"]
    assert verdict["findings"][0]["message"] == runner.WHY_FOUND["variant"]
    assert runner.exit_status(verdict) == 10


def test_exploit_green_on_base_proves_nothing(runner):
    verdict = runner.judge(altered(e=lambda c: c.update(runs=blind_pair(base_rc=0))), EVERY_KIND)
    assert ids(verdict["gaps"]) == ["e"] and verdict["gaps"][0]["reason"].startswith("no reproduction")


@pytest.mark.parametrize("cid", ["r", "s", "b"])
def test_red_base_blocks_blame(runner, cid):
    verdict = runner.judge(altered(**{cid: lambda c: c["runs"].update(pair(1, 1))}), EVERY_KIND)
    assert verdict["findings"] == [] and verdict["gaps"][0]["reason"].startswith("unattributable")


@pytest.mark.parametrize("which", ["base", "patched"])
def test_absent_reach_line_is_a_gap(runner, which):
    runs = blind_pair(patched_rc=1, **{f"{which}_seen": False})
    verdict = runner.judge(altered(v=lambda c: c.update(runs=runs)), EVERY_KIND)
    assert verdict["findings"] == []
    reason = verdict["gaps"][0]["reason"]
    assert reason.startswith("marker_missing") and which in reason


def test_unclean_control_holds_everything_back(runner):
    verdict = runner.judge(altered(c=lambda c: c["runs"].update(patched=rec(1)),
                                   v=lambda c: c.update(runs=blind_pair(patched_rc=1))), EVERY_KIND)
    assert verdict["findings"] == []
    by_check = {g["check_id"]: g["reason"] for g in verdict["gaps"]}
    assert by_check["c"] == "control broke on the patched side"
    assert by_check["v"].startswith("held back")


def test_plan_without_control(runner):
    checks = [c for c in altered(v=lambda c: c.update(runs=blind_pair(patched_rc=1))) if c["kind"] != "control"]
    verdict = runner.judge(checks, {**EVERY_KIND, "control": 0})
    assert {"check_id": None, "reason": "no control check in the plan"} in verdict["gaps"]
    assert verdict["findings"] == []


@pytest.mark.parametrize("patched,base,expect", [
    (rec(1), None, ("gap", "no base run on record")),
    (rec(1), rec(0), ("finding", None)),
    (rec(1), rec(1), ("gap", "unattributable: the suite fails on base as well; both logs kept")),
    (rec(state="timeout"), None, ("gap", "patched run ended as timeout, not completed")),
])
def test_suite_base_follows_patched_failure(runner, patched, base, expect):
    runs = {"patched": patched, **({"base": base} if base else {})}
    verdict = runner.judge(altered(u=lambda c: c.update(runs=runs)), EVERY_KIND)
    if expect[0] == "finding":
        assert ids(verdict["findings"]) == ["u"]
    else:
        assert [g["reason"] for g in verdict["gaps"]] == [expect[1]]


def test_behavior_stream_and_missing_comparison(runner):
    drifted = altered(b=lambda c: c["comparison"].update(matched=False))
    assert [f["kind"] for f in runner.judge(drifted, EVERY_KIND)["findings"]] == ["behavior"]
    blank = altered(b=lambda c: c.pop("comparison"))
    assert runner.judge(blank, EVERY_KIND)["gaps"][0]["reason"] == "behavior check has no stream comparison"


def test_cleanup_trouble_does_not_erase_findings(runner):
    verdict = runner.judge(altered(e=lambda c: c.update(runs=blind_pair(patched_rc=1))), EVERY_KIND,
                           cleanup_errors=["worktree 9f9f stayed behind: locked"])
    assert ids(verdict["findings"]) == ["e"]
    assert verdict["gaps"] == [{"check_id": None, "reason": "cleanup: worktree 9f9f stayed behind: locked"}]
    assert runner.exit_status(verdict) == 10


def test_complete_with_findings_exits_one(runner):
    verdict = runner.judge(altered(s=lambda c: c["runs"].update(patched=rec(1))), EVERY_KIND)
    assert verdict["status"] == "complete" and runner.exit_status(verdict) == 1


def wrap(runner, checks, tier):
    for chk in checks:
        chk.setdefault("rationale", "why")
        chk.setdefault("covers", ["somewhere"])
        for r in chk["runs"].values():
            r.setdefault("stdout", "007-x-patched.stdout")
    return {"case_id": "UPL-3", "finding": {"id": "UPL-3", "summary": "escape"},
            "inputs": {"base_commit": "1" * 40, "patched_commit": None, "patch_sha256": "2" * 64,
                       "changed_files": ["f.py"], "evidence_level": tier, "submodules": {},
                       "plan_sha256": "3" * 64, "forwarded_env": {}},
            "checks": checks, "assessment": runner.judge(checks, EVERY_KIND)}


def test_clean_report_names_level_and_human_review(runner):
    text = runner.report_markdown(wrap(runner, tidy_plan(), "build"))
    positions = [text.index(h) for h in ("## Findings", "## Validation gaps", "## Evidence", "## Next steps")]
    assert positions == sorted(positions)
    assert "All supplied checks passed at evidence level `build`" in text
    assert "human review is still required" in text


def test_report_keeps_findings_and_gaps_apart(runner):
    checks = altered(v=lambda c: c.update(runs=blind_pair(patched_rc=1)),
                     r=lambda c: c["runs"].update(patched=rec(state="timeout")))
    text = runner.report_markdown(wrap(runner, copy.deepcopy(checks), "runtime"))
    found = text.split("## Findings")[1].split("## Validation gaps")[0]
    gaps = text.split("## Validation gaps")[1].split("## Evidence")[0]
    assert "`v`" in found and "`r`" not in found and "`r`" in gaps
    assert "Evidence level here: `runtime`" in text
