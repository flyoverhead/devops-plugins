"""registry.py: scope freezing, reservations, binding, candidates, retry, acceptance."""
import json

from conftest import cli, dump


def reg(flow):
    return json.loads((flow.root / "registry.json").read_text())


def test_init_freezes_scope(flow):
    data = reg(flow)
    assert data["version"] == 3 and data["scope"]["file"] == "scope.json"
    assert list(data["scope"]["changes"]) == ["change-1"]
    dump(flow.root / "scope.json", {"changes": [{"id": "change-2", "input": "HEAD"}]})
    assert "differs" in cli("registry.py", "init", flow.root, ok=False).stderr


def test_init_rejects_bad_scopes(tmp_path):
    for scope, word in (({"changes": []}, "non-empty"), ({"changes": [{"id": "campaign", "input": "x"}]}, "reserved"),
                        ({"changes": [{"id": "a", "input": "x"}, {"id": "a", "input": "y"}]}, "twice"),
                        ({"changes": [{"id": "a", "input": {"repository": "r"}}]}, "input")):
        dump(tmp_path / "scope.json", scope)
        done = cli("registry.py", "init", tmp_path, ok=False)
        assert word in done.stderr, done.stderr


def test_init_after_attempts_fails(flow):
    flow.reserve("prepare", flow.guidance)
    assert "attempts already exist" in cli("registry.py", "init", flow.root, ok=False).stderr


def test_wrong_version_rejected(flow):
    data = reg(flow)
    data["version"] = 2
    dump(flow.root / "registry.json", data)
    assert "version 3" in cli("registry.py", "show", flow.root, ok=False).stderr


def test_reserve_rules(flow):
    att = flow.reserve("prepare", flow.guidance)
    assert att["id"] == "a001" and att["directory"] == "attempts/a001" and att["state"] == "reserved"
    assert (flow.root / "attempts/a001").is_dir()
    base = ["reserve", flow.root]
    assert "campaign" in cli("registry.py", *base, "--stage", "report", "--change", "change-1", ok=False).stderr
    assert "frozen scope" in cli("registry.py", *base, "--stage", "hunt", "--change", "nope", ok=False).stderr
    assert "candidate" in cli("registry.py", *base, "--stage", "reproduce", "--change", "change-1", ok=False).stderr
    hunt = flow.reserve("hunt", [])
    assert hunt["prefix"] == "h001-"
    assert flow.reserve("report", [], change="campaign")["change"] == "campaign"


def test_bind_requires_launch_record(flow):
    att = flow.reserve("prepare", flow.guidance)
    agent = flow.launch(att["id"])
    bad = cli("registry.py", "bind", flow.root, att["id"], "--agent", "someone-else",
              "--agent-record", f"runtime/{att['id']}-launch.json", ok=False)
    assert "agent_id" in bad.stderr
    rec = json.loads((flow.root / f"runtime/{att['id']}-launch.json").read_text())
    rec["call"]["subagent_type"] = "fork"
    dump(flow.root / "runtime/fork.json", rec)
    assert "fork" in cli("registry.py", "bind", flow.root, att["id"], "--agent", agent,
                         "--agent-record", "runtime/fork.json", ok=False).stderr
    ok = json.loads(cli("registry.py", "bind", flow.root, att["id"], "--agent", agent,
                        "--agent-record", f"runtime/{att['id']}-launch.json", ok=True).stdout)
    assert ok["state"] == "running" and ok["verification"] == "shared-host"
    assert "reserved" in cli("registry.py", "bind", flow.root, att["id"], "--agent", agent,
                             "--agent-record", f"runtime/{att['id']}-launch.json", ok=False).stderr


def test_candidate_ids_stable(flow):
    flow.prepare()
    att = flow.start("hunt", [flow.prepare_rel])
    ask = lambda key, agent=att["agent"]: cli("registry.py", "candidate", flow.root, att["id"], "--agent", agent, "--key", key)
    first = json.loads(ask("k1").stdout)["candidate"]
    assert first == "h001-001"
    assert json.loads(ask("k2").stdout)["candidate"] == "h001-002"
    assert json.loads(ask("k1").stdout)["candidate"] == first
    assert ask("k3", agent="intruder").returncode == 1


def test_hunt_must_account_for_every_id(flow):
    flow.prepare()
    att = flow.start("hunt", [flow.prepare_rel])
    cli("registry.py", "candidate", flow.root, att["id"], "--agent", att["agent"], "--key", "k1", ok=True)
    rel = flow.finish(att, "hunt.json", {"candidates": [], "candidate_files": {}}, accept=False)
    done = cli("registry.py", "accept", flow.root, att["id"], rel, ok=False)
    assert "differ from the ids reserved" in done.stderr


def test_accept_checks_identity_and_inputs(flow):
    att = flow.start("prepare", flow.guidance)
    rel = flow.finish(att, "prepare.json", {"source": None, "agent": "impostor"}, status="blocked", accept=False)
    assert "'agent'" in cli("registry.py", "accept", flow.root, att["id"], rel, ok=False).stderr
    att2 = flow.start("prepare", flow.guidance)
    rel2 = flow.finish(att2, "prepare.json", {"source": None}, status="blocked", accept=False)
    (flow.root / flow.guidance[-1]).write_text("tampered\n")
    assert cli("registry.py", "accept", flow.root, att2["id"], rel2).returncode == 1


def test_blocked_prepare_accepted(flow):
    att = flow.start("prepare", flow.guidance)
    rel = flow.finish(att, "prepare.json", {"source": None}, status="blocked")
    data = reg(flow)["attempts"][att["id"]]
    assert data["state"] == "accepted" and data["record"] == rel and len(data["seal"]) == 64
    assert cli("registry.py", "check", flow.root, att["id"], rel).returncode == 0


def test_artifact_outside_attempt_rejected(flow):
    att = flow.start("prepare", flow.guidance)
    (flow.root / "loose.txt").write_text("x")
    rel = flow.finish(att, "prepare.json", {"source": None}, artifacts=["loose.txt"], status="blocked", accept=False)
    assert "outside" in cli("registry.py", "accept", flow.root, att["id"], rel, ok=False).stderr


def test_complete_experiment_needs_build_dirs(flow):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    att = flow.start("reproduce", [flow.prepare_rel, flow.hunt_rel, flow.candidates[cid]], candidate=cid)
    rel = flow.finish(att, "reproduce.json", {"candidate": cid, "runs": []}, accept=False)
    assert cli("registry.py", "accept", flow.root, att["id"], rel).returncode == 1


def test_candidate_stage_needs_candidate_file(flow):
    flow.prepare()
    cid = next(iter(flow.hunt()))
    done = cli("registry.py", "reserve", flow.root, "--stage", "reproduce", "--change", "change-1",
               "--candidate", cid, "--input", flow.prepare_rel, ok=False)
    assert "candidate file" in done.stderr


def test_retry_needs_terminal_record(flow):
    att = flow.start("prepare", flow.guidance)
    (flow.root / "runtime/note.txt").write_text(
        f"<task-notification><task-id>{att['agent']}</task-id><status>failed</status></task-notification>")
    cli("runtime.py", "terminal", flow.root, att["id"], "--notification", "runtime/note.txt", ok=True)
    new = json.loads(cli("registry.py", "retry", flow.root, att["id"], "--agent-record",
                         f"runtime/{att['id']}-terminal.json", ok=True).stdout)
    assert new["id"] == "a002" and new["stage"] == "prepare" and new["inputs"] == flow.guidance
    assert reg(flow)["attempts"][att["id"]]["state"] == "superseded"


def test_retry_refuses_killed(flow):
    att = flow.start("prepare", flow.guidance)
    (flow.root / "runtime/k.txt").write_text(f'{{"task_id": "{att["agent"]}", "status": "killed"}}')
    cli("runtime.py", "terminal", flow.root, att["id"], "--notification", "runtime/k.txt", ok=True)
    done = cli("registry.py", "retry", flow.root, att["id"], "--agent-record", f"runtime/{att['id']}-terminal.json")
    assert done.returncode == 1 and "killed" in done.stderr


def test_retry_with_empty_inputs(flow):
    att = flow.start("prepare", flow.guidance)
    (flow.root / "runtime/n.txt").write_text(f"task_id: {att['agent']} status: completed")
    cli("runtime.py", "terminal", flow.root, att["id"], "--notification", "runtime/n.txt", ok=True)
    new = json.loads(cli("registry.py", "retry", flow.root, att["id"], "--agent-record",
                         f"runtime/{att['id']}-terminal.json", "--inputs", ok=True).stdout)
    assert new["inputs"] == []


def test_helpers_for_report(flow, mods):
    registry = mods["registry"]
    _, repro, _, dec = flow.full()
    data = reg(flow)
    assert registry.accepted_attempt(data, dec)["stage"] == "adjudicate"
    assert registry.change_of(data, repro) == "change-1"
    assert registry.weakest(data, ["a001", "a002"]) == "shared-host"
    assert registry.weakest(data, ["a999"]) is None
    index = json.loads((flow.root / "campaign.json").read_text())
    assert registry.scope_problems(data, index) == []
    index["changes"][0]["id"] = "x"
    assert registry.scope_problems(data, index)


def test_accept_needs_terminal_record(flow):
    att = flow.start("prepare", flow.guidance)
    rel = f"{att['directory']}/prepare.json"
    dump(flow.root / rel, {"stage": "prepare", "agent": att["agent"], "attempt": att["id"], "change": "change-1",
                           "status": "blocked", "summary": "s", "security_review": "r", "inputs": att["inputs"],
                           "artifacts": [], "source": None})
    cli("evidence.py", "seal", flow.root, rel, ok=True)
    assert "terminal.json" in cli("registry.py", "accept", flow.root, att["id"], rel, ok=False).stderr
    flow.terminate(att, status="killed")
    assert "killed" in cli("registry.py", "accept", flow.root, att["id"], rel, ok=False).stderr


def test_failed_bind_is_recoverable(flow):
    att = flow.reserve("prepare", flow.guidance)
    agent = flow.launch(att["id"])
    cli("registry.py", "bind", flow.root, att["id"], "--agent", "typo-agent", "--agent-record",
        f"runtime/{att['id']}-launch.json", ok=False)
    assert reg(flow)["attempts"][att["id"]]["state"] == "reserved"
    cli("registry.py", "bind", flow.root, att["id"], "--agent", agent, "--agent-record",
        f"runtime/{att['id']}-launch.json", ok=True)


def test_retry_reserved_without_launch(flow):
    att = flow.reserve("prepare", flow.guidance)
    new = json.loads(cli("registry.py", "retry", flow.root, att["id"], ok=True).stdout)
    assert new["id"] == "a002" and reg(flow)["attempts"]["a001"]["state"] == "superseded"


def test_retry_reserved_after_launch_needs_stray_terminal(flow):
    att = flow.reserve("prepare", flow.guidance)
    agent = flow.launch(att["id"])
    assert "never bound" in cli("registry.py", "retry", flow.root, att["id"], ok=False).stderr
    flow.terminate(dict(att, agent=agent), status="failed")
    cli("registry.py", "retry", flow.root, att["id"], "--agent-record", f"runtime/{att['id']}-terminal.json", ok=True)


def test_retry_blocked_hunt_keeps_prefix_and_ids(flow):
    flow.prepare()
    att = flow.start("hunt", [flow.prepare_rel])
    first = json.loads(cli("registry.py", "candidate", flow.root, att["id"], "--agent", att["agent"],
                           "--key", "empty-key", ok=True).stdout)["candidate"]
    rel = f"{att['directory']}/candidates/{first}.json"
    dump(flow.root / rel, {"id": first, "key": "empty-key", "change": "change-1", "stage": "hunt", "agent": att["agent"],
                           "inputs": [flow.prepare_rel], "artifacts": [], "title": "t", "patch_intent": "p",
                           "prior_behavior": "p", "changed_code": "c", "reachable_trigger": "r",
                           "possible_defect": "d", "false_positive_checks": "f", "proof_needed": "n"})
    cli("evidence.py", "seal", flow.root, rel, ok=True)
    flow.finish(att, "hunt.json", {"candidates": [first], "candidate_files": {first: rel}},
                [f"{att['directory']}/candidates"], status="blocked")
    new = json.loads(cli("registry.py", "retry", flow.root, att["id"], ok=True).stdout)
    assert new["prefix"] == att["prefix"]
    agent = flow.launch(new["id"])
    cli("registry.py", "bind", flow.root, new["id"], "--agent", agent, "--agent-record",
        f"runtime/{new['id']}-launch.json", ok=True)
    again = json.loads(cli("registry.py", "candidate", flow.root, new["id"], "--agent", agent,
                           "--key", "empty-key", ok=True).stdout)["candidate"]
    assert again == first


def test_retry_refuses_complete_accepted(flow):
    flow.prepare()
    assert "accepted complete" in cli("registry.py", "retry", flow.root, "a001", ok=False).stderr
