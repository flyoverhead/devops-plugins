"""A whole campaign through the real scripts, then the report's decisions under tampering."""
import json

from conftest import cli, dump


def render(flow, out="report"):
    return cli("report.py", flow.root, "--output", out)


def report_json(flow, out="report"):
    return json.loads((flow.root / out / "report.json").read_text())


def test_confirmed_regression_is_reported(flow):
    cid, *_ = flow.full()
    done = render(flow)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith("report/index.html")
    data = report_json(flow)
    assert data["counts"]["REPRODUCED_REGRESSION"] == 1
    row = data["findings"][0]
    assert row["id"] == cid and row["outcome"] == "REPRODUCED_REGRESSION"
    assert row["verification"] == "shared-host" and row["unresolved_reason"] is None
    assert row["severity"] == "High" and row["category"] == "VULNERABILITY"
    assert data["changes"][0]["status"] == "COMPLETE"
    md = (flow.root / "report" / "report.md").read_text()
    assert "pending human review" in md and f"{flow.repo} @ {flow.s0}..{flow.s1}" in md
    page = (flow.root / "report" / "index.html").read_text()
    assert 'href="../attempts/' in page


def test_report_refuses_to_overwrite(flow):
    flow.full()
    assert render(flow).returncode == 0
    again = render(flow)
    assert again.returncode == 1 and "already exists" in again.stderr


def test_same_agent_for_replay_blocks_confirmation(flow, mods):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    repro_att, repro = flow.experiment("reproduce", cid)
    reg = json.loads((flow.root / "registry.json").read_text())
    att = flow.reserve("replay", [flow.prepare_rel, flow.hunt_rel, flow.candidates[cid], repro], candidate=cid)
    flow.launch(att["id"], agent=repro_att["agent"])
    refused = cli("registry.py", "bind", flow.root, att["id"], "--agent", repro_att["agent"],
                  "--agent-record", f"runtime/{att['id']}-launch.json")
    assert refused.returncode == 1 and "already bound" in refused.stderr
    assert reg["attempts"][repro_att["id"]]["agent"] == repro_att["agent"]


def test_s0_failing_is_not_a_confirmation(flow):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    _, repro = flow.experiment("reproduce", cid, s0="failure")
    _, replay = flow.experiment("replay", cid, extra_inputs=[repro], poc_from=repro.rsplit("/", 1)[0] + "/poc")
    _, dec = flow.decide(cid, repro=repro, replay=replay)
    flow.index({cid: dec})
    assert render(flow).returncode == 0
    row = report_json(flow)["findings"][0]
    assert row["outcome"] == "UNRESOLVED"
    assert "S0 must behave correctly" in row["unresolved_reason"]
    assert report_json(flow)["counts"]["REPRODUCED_REGRESSION"] == 0
    assert report_json(flow)["changes"][0]["status"] == "INCOMPLETE"


def test_unknown_check_blocks_confirmation(flow, mods):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    _, repro = flow.experiment("reproduce", cid)
    _, replay = flow.experiment("replay", cid, extra_inputs=[repro], poc_from=repro.rsplit("/", 1)[0] + "/poc")
    checks = {k: {"conclusion": v or "SUPPORTED", "reason": "r", "evidence": [repro]}
              for k, v in mods["shapes"].CHECK_WANT.items()}
    checks["latent_bug"]["conclusion"] = "UNKNOWN"
    _, dec = flow.decide(cid, repro=repro, replay=replay, checks=checks)
    flow.index({cid: dec})
    assert render(flow).returncode == 0
    assert "latent_bug is UNKNOWN" in report_json(flow)["findings"][0]["unresolved_reason"]


def test_changed_poc_in_replay_blocks_confirmation(flow):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    _, repro = flow.experiment("reproduce", cid)
    att, replay = flow.experiment("replay", cid, extra_inputs=[repro], accept=False,
                                  poc_text="#!/bin/sh\nKEY=x sh \"$1/gate.sh\" x\n")
    done = cli("registry.py", "accept", flow.root, att["id"], replay)
    assert done.returncode == 1 and "replay 'poc' differs" in done.stderr


def test_missing_decision_is_pending(flow):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    flow.index({})
    assert render(flow).returncode == 0
    row = report_json(flow)["findings"][0]
    assert row["outcome"] == "UNRESOLVED" and "No adjudication" in row["unresolved_reason"]


def test_exclusion_counts_and_duplicates(flow):
    flow.prepare()
    files = flow.hunt(keys=("first", "second"))
    a, b = list(files)
    _, d1 = flow.decide(a, outcome="LATENT_BUG")
    _, d2 = flow.decide(b, outcome="LATENT_BUG", duplicate_of=a)
    flow.index({a: d1, b: d2})
    assert render(flow).returncode == 0
    data = report_json(flow)
    assert data["counts"]["LATENT_BUG"] == 1
    assert data["findings"][1]["duplicate_of"] == a


def test_bad_duplicate_becomes_unresolved(flow):
    flow.prepare()
    a, b = list(flow.hunt(keys=("first", "second")))
    _, d1 = flow.decide(a, outcome="REJECTED")
    _, d2 = flow.decide(b, outcome="LATENT_BUG", duplicate_of=a)
    flow.index({a: d1, b: d2})
    assert render(flow).returncode == 0
    row = report_json(flow)["findings"][1]
    assert row["outcome"] == "UNRESOLVED" and "has outcome REJECTED" in row["unresolved_reason"]


def test_tampered_evidence_aborts_without_writing(flow):
    _, repro, _, _ = flow.full()
    log = flow.root / repro.rsplit("/", 1)[0] / "logs" / "S1.log"
    log.write_text("edited later\n")
    done = render(flow)
    assert done.returncode == 1 and not (flow.root / "report").exists()


def test_index_out_of_scope_aborts(flow):
    flow.full()
    index = json.loads((flow.root / "campaign.json").read_text())
    index["changes"][0]["input"] = "HEAD~1..HEAD"
    dump(flow.root / "campaign.json", index)
    done = render(flow)
    assert done.returncode == 1 and "frozen scope" in done.stderr


def test_unaccepted_decision_aborts(flow):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    att = flow.start("adjudicate", [flow.prepare_rel, flow.hunt_rel, flow.candidates[cid]], candidate=cid)
    rel = flow.finish(att, "decision.json", {"candidate": cid, "outcome": "REJECTED", "reason": "r",
                                            "evidence": [flow.candidates[cid]]}, accept=False)
    flow.index({cid: rel})
    done = render(flow)
    assert done.returncode == 1 and "not an accepted adjudicate record" in done.stderr


def test_html_escapes_content(flow):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    _, dec = flow.decide(cid, outcome="REJECTED", reason="<script>alert(1)</script>")
    flow.index({cid: dec})
    assert render(flow).returncode == 0
    page = (flow.root / "report" / "index.html").read_text()
    assert "<script>alert" not in page and "&lt;script&gt;" in page


def test_decision_evidence_must_be_in_package(flow):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    (flow.root / "stray.log").write_text("not part of any package\n")
    att = flow.start("adjudicate", [flow.prepare_rel, flow.hunt_rel, flow.candidates[cid]], candidate=cid)
    rel = flow.finish(att, "decision.json", {"candidate": cid, "outcome": "REJECTED", "reason": "r",
                                            "evidence": ["stray.log"]}, accept=False)
    done = cli("registry.py", "accept", flow.root, att["id"], rel)
    assert done.returncode == 1 and "not inside the decision's package" in done.stderr


def test_decision_may_cite_experiment_logs(flow):
    _, repro, _, dec = flow.full()
    body = json.loads((flow.root / dec).read_text())
    assert body["evidence"] == [repro.rsplit("/", 1)[0] + "/logs/S1.log"]


def test_list_title_is_joined(flow):
    flow.prepare()
    att = flow.start("hunt", [flow.prepare_rel])
    cid = json.loads(cli("registry.py", "candidate", flow.root, att["id"], "--agent", att["agent"],
                         "--key", "k", ok=True).stdout)["candidate"]
    rel = f"{att['directory']}/candidates/{cid}.json"
    dump(flow.root / rel, {"id": cid, "key": "k", "change": "change-1", "stage": "hunt", "agent": att["agent"],
                           "inputs": [flow.prepare_rel], "artifacts": [], "title": ["empty key", "purge allowed"],
                           "patch_intent": "p", "prior_behavior": "p", "changed_code": "c", "reachable_trigger": "r",
                           "possible_defect": "d", "false_positive_checks": "f", "proof_needed": "n"})
    cli("evidence.py", "seal", flow.root, rel, ok=True)
    flow.hunt_rel = flow.finish(att, "hunt.json", {"candidates": [cid], "candidate_files": {cid: rel}},
                                [f"{att['directory']}/candidates"])
    flow.candidates = {cid: rel}
    flow.index({})
    assert render(flow).returncode == 0
    assert report_json(flow)["findings"][0]["title"] == "empty key; purge allowed"
    assert "## h001-001: empty key; purge allowed" in (flow.root / "report" / "report.md").read_text()
