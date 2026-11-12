#!/usr/bin/env python3
"""Append-only attempt registry of a regression-hunt campaign (registry.json, version 3).

Commands: init, reserve, bind, candidate, retry, check, accept, show. Every command prints JSON.
The report script imports accepted_attempt, scope_problems, change_of and weakest from here.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402
import shapes  # noqa: E402
from rhlib import (Refusal, campaign, digest, expand, inside, locked, read_json, str_list,  # noqa: E402
                   timestamp, under, write_json)

VERSION = 3
RUNTIME = "runtime"
LEVEL = {"isolated": 2, "shared-host": 1}


def registry_path(root: Path) -> Path:
    return root / "registry.json"


def load(root: Path) -> dict:
    path = registry_path(root)
    if not path.exists():
        raise Refusal("registry.json does not exist yet; run init first")
    reg = read_json(path, "registry")
    if not isinstance(reg, dict) or reg.get("version") != VERSION:
        raise Refusal(f"registry.json is not version {VERSION}; older layouts are not migrated")
    return reg


def frozen(reg: dict) -> dict:
    if not reg.get("scope"):
        raise Refusal("scope is not frozen; run init first")
    return reg["scope"]


def valid_input(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return (isinstance(value, dict) and set(value) == {"repository", "s0", "s1"}
            and all(isinstance(v, str) and v.strip() for v in value.values()))


def read_scope(root: Path) -> dict:
    data = read_json(under(root, "scope.json"), "scope")
    changes = data.get("changes") if isinstance(data, dict) else None
    if not isinstance(changes, list) or not changes:
        raise Refusal("scope.json needs a non-empty 'changes' list")
    mapping = {}
    for item in changes:
        cid = item.get("id") if isinstance(item, dict) else None
        if not isinstance(cid, str) or not cid.strip():
            raise Refusal("every change needs a non-empty string 'id'")
        if cid == "campaign":
            raise Refusal("'campaign' is reserved for the report stage")
        if cid in mapping:
            raise Refusal(f"change id {cid} appears twice")
        if not valid_input(item.get("input")):
            raise Refusal(f"change {cid}: 'input' must be a PR URL or commit string, or "
                          "an object with repository, s0 and s1")
        mapping[cid] = item["input"]
    return {"file": "scope.json", "hash": digest(root / "scope.json"), "changes": mapping}


def cmd_init(root: Path, _args) -> dict:
    scope = read_scope(root)
    path = registry_path(root)
    reg = read_json(path, "registry") if path.exists() else None
    if reg is not None:
        if reg.get("version") != VERSION:
            raise Refusal(f"registry.json is not version {VERSION}")
        if reg.get("scope") and reg["scope"]["hash"] != scope["hash"]:
            raise Refusal("scope.json differs from the frozen scope; a changed scope needs a new campaign")
        if reg.get("attempts"):
            raise Refusal("attempts already exist; init only runs on a fresh campaign")
    reg = {"version": VERSION, "scope": scope, "prefixes": {}, "candidates": {}, "attempts": {}}
    write_json(path, reg)
    return {"scope": scope}


def input_hashes(root: Path, reg: dict, stage: str, change: str, inputs: list) -> dict:
    if len(set(inputs)) != len(inputs):
        raise Refusal("an input is listed twice")
    hashes = {}
    for rel in inputs:
        under(root, rel)
        if (root / evidence.seal_of(rel)).exists():
            record = evidence.verify(root, rel)
            if stage != "report" and record.get("change") != change:
                raise Refusal(f"{rel} belongs to change {record.get('change')!r}, not {change}")
            seal = evidence.seal_of(rel)
            hashes[seal] = digest(under(root, seal))
        hashes.update(expand(root, rel))
    return dict(sorted(hashes.items()))


def check_candidate_inputs(reg: dict, stage: str, change: str, candidate, inputs: list):
    if stage in shapes.CANDIDATE_STAGES:
        entry = reg["candidates"].get(candidate) if candidate else None
        if entry is None or entry["change"] != change:
            raise Refusal(f"{stage} needs a known candidate of change {change}")
        if not entry["file"] or entry["file"] not in inputs:
            raise Refusal(f"the accepted candidate file of {candidate} must be one of the inputs")
    elif candidate:
        raise Refusal(f"{stage} does not take a candidate")


def new_attempt(root: Path, reg: dict, **fields) -> dict:
    aid = f"a{len(reg['attempts']) + 1:03d}"
    directory = f"attempts/{aid}"
    (root / directory).mkdir(parents=True, exist_ok=False)
    entry = {"id": aid, "stage": fields["stage"], "change": fields["change"],
             "candidate": fields.get("candidate"), "prefix": fields.get("prefix"),
             "inputs": fields["inputs"], "input_hashes": fields["input_hashes"],
             "directory": directory, "agent": None, "state": "reserved", "record": None,
             "seal": None, "launch": None, "terminal": None, "verification": None}
    reg["attempts"][aid] = entry
    return entry


def cmd_reserve(root: Path, args) -> dict:
    reg = load(root)
    scope = frozen(reg)
    if args.stage == "report":
        if args.change != "campaign":
            raise Refusal("the report stage runs for change 'campaign'")
    elif args.change not in scope["changes"]:
        raise Refusal(f"change {args.change} is not in the frozen scope")
    inputs = list(args.input or [])
    check_candidate_inputs(reg, args.stage, args.change, args.candidate, inputs)
    hashes = input_hashes(root, reg, args.stage, args.change, inputs)
    prefix = None
    if args.stage == "hunt":
        prefix = f"h{len(reg['prefixes']) + 1:03d}-"
        reg["prefixes"][prefix] = args.change
    entry = new_attempt(root, reg, stage=args.stage, change=args.change, candidate=args.candidate,
                        prefix=prefix, inputs=inputs, input_hashes=hashes)
    write_json(registry_path(root), reg)
    return entry


def runtime_receipt(root: Path, rel: str, event: str, attempt: str) -> dict:
    if not inside(rel, RUNTIME):
        raise Refusal(f"agent records live under {RUNTIME}/, not {rel}")
    rec = read_json(under(root, rel), "agent record")
    if not isinstance(rec, dict) or rec.get("event") != event:
        raise Refusal(f"{rel} is not a {event} record")
    if rec.get("attempt") != attempt:
        raise Refusal(f"{rel} belongs to attempt {rec.get('attempt')!r}, not {attempt}")
    timestamp(rec.get("observed_at"), "observed_at")
    raw = rec.get("evidence")
    if not str_list(raw) or not raw:
        raise Refusal(f"{rel}: 'evidence' must list the raw files beside it")
    hashes = expand(root, rel)
    for ev in raw:
        if not inside(ev, RUNTIME):
            raise Refusal(f"{rel}: evidence {ev} is outside {RUNTIME}/")
        if not under(root, ev).is_file() or under(root, ev).stat().st_size == 0:
            raise Refusal(f"{rel}: evidence {ev} is missing or empty")
        hashes.update(expand(root, ev))
    return {"record": rel, "hashes": hashes, "value": rec}


def cmd_bind(root: Path, args) -> dict:
    reg = load(root)
    att = attempt_of(reg, args.attempt)
    if att["state"] != "reserved":
        raise Refusal(f"{att['id']} is {att['state']}; only a reserved attempt can be bound")
    receipt = runtime_receipt(root, args.agent_record, "launch", att["id"])
    rec = receipt["value"]
    if rec.get("tool") != "claude.Agent":
        raise Refusal("only claude.Agent launch records are recognised by this version")
    call, response = rec.get("call"), rec.get("response")
    kind = call.get("subagent_type") if isinstance(call, dict) else None
    if not isinstance(kind, str) or not kind.strip() or kind == "fork":
        raise Refusal("the launch call needs a non-empty subagent_type other than fork")
    if not isinstance(response, dict) or response.get("agent_id") != args.agent:
        raise Refusal(f"the launch response does not carry agent_id {args.agent}")
    for other in reg["attempts"].values():
        if other["agent"] == args.agent:
            raise Refusal(f"handle {args.agent} is already bound to {other['id']}; every attempt needs a fresh agent")
    att.update(agent=args.agent, state="running", launch=receipt, verification="shared-host")
    write_json(registry_path(root), reg)
    return att


def cmd_candidate(root: Path, args) -> dict:
    reg = load(root)
    att = attempt_of(reg, args.attempt)
    if att["stage"] != "hunt" or att["state"] != "running" or att["agent"] != args.agent:
        raise Refusal(f"{att['id']} is not a running hunt bound to {args.agent}")
    if not args.key.strip():
        raise Refusal("the hypothesis key is empty")
    mine = {cid: c for cid, c in reg["candidates"].items() if c["prefix"] == att["prefix"]}
    for cid, entry in mine.items():
        if entry["key"] == args.key:
            return {"candidate": cid}
    cid = f"{att['prefix']}{len(mine) + 1:03d}"
    reg["candidates"][cid] = {"prefix": att["prefix"], "key": args.key, "change": att["change"], "file": None}
    write_json(registry_path(root), reg)
    return {"candidate": cid}


def launched_agent(root: Path, att: dict):
    """The agent a launch record names for this attempt, bound or not."""
    if att["agent"]:
        return att["agent"]
    rel = f"{RUNTIME}/{att['id']}-launch.json"
    if not (root / rel).is_file():
        return None
    rec = read_json(under(root, rel), "launch record")
    response = rec.get("response") if isinstance(rec, dict) else None
    return response.get("agent_id") if isinstance(response, dict) else None


def terminal_receipt(root: Path, att: dict, rel: str) -> dict:
    receipt = runtime_receipt(root, rel, "terminal", att["id"])
    rec = receipt["value"]
    if rec.get("tool") != "claude.task_notification":
        raise Refusal("only claude.task_notification terminal records are recognised by this version")
    response = rec.get("response") if isinstance(rec.get("response"), dict) else {}
    agent = launched_agent(root, att)
    if response.get("task_id") != agent:
        raise Refusal(f"the notification is for {response.get('task_id')!r}, not {agent!r}")
    if response.get("status") == "killed":
        raise Refusal("a killed task has no usable terminal record; record a blocker instead")
    if response.get("status") not in ("completed", "failed"):
        raise Refusal("terminal status must be completed or failed")
    launch = att["launch"] or ({"value": read_json(under(root, f"{RUNTIME}/{att['id']}-launch.json"))}
                               if (root / f"{RUNTIME}/{att['id']}-launch.json").is_file() else None)
    if launch and timestamp(rec["observed_at"]) < timestamp(launch["value"]["observed_at"]):
        raise Refusal("the terminal record is older than the launch")
    return receipt


def cmd_retry(root: Path, args) -> dict:
    reg = load(root)
    old = attempt_of(reg, args.attempt)
    if old["state"] == "running":
        if not args.agent_record:
            raise Refusal(f"{old['id']} is running; pass its terminal record")
        terminal = terminal_receipt(root, old, args.agent_record)
    elif old["state"] == "reserved":
        if launched_agent(root, old):
            if not args.agent_record:
                raise Refusal(f"{old['id']} was launched but never bound; pass the stray agent's terminal record")
            terminal = terminal_receipt(root, old, args.agent_record)
        else:
            terminal = None
    elif old["state"] == "accepted":
        if read_json(under(root, old["record"])).get("status") != "blocked":
            raise Refusal(f"{old['id']} was accepted complete; a new question needs a new reservation")
        terminal = old["terminal"]
    else:
        raise Refusal(f"{old['id']} is superseded; retry its successor instead")
    inputs = old["inputs"] if args.inputs is None else list(args.inputs)
    check_candidate_inputs(reg, old["stage"], old["change"], old["candidate"], inputs)
    hashes = input_hashes(root, reg, old["stage"], old["change"], inputs)
    old.update(state="superseded", terminal=terminal)
    entry = new_attempt(root, reg, stage=old["stage"], change=old["change"], candidate=old["candidate"],
                        prefix=old["prefix"], inputs=inputs, input_hashes=hashes)
    write_json(registry_path(root), reg)
    return entry


def accepted_for(reg: dict, stage: str, change: str) -> set:
    return {a["record"] for a in reg["attempts"].values()
            if a["stage"] == stage and a["change"] == change and a["state"] == "accepted"}


def stage_problems(root: Path, reg: dict, att: dict, rec: dict) -> list:
    stage = att["stage"]
    if stage == "prepare":
        if "source" not in rec:
            return ["'source' is missing (null when blocked)"]
        if rec.get("status") == "complete":
            if not isinstance(rec["source"], str) or not inside(rec["source"], att["directory"]):
                return ["'source' must point to source.json inside the attempt directory"]
            try:
                shapes.source(root, rec["source"])
            except Refusal as exc:
                return [str(exc)]
        return []
    if stage == "hunt":
        return hunt_problems(root, reg, att, rec)
    if stage in ("reproduce", "replay"):
        bad = shapes.experiment(root, rec, att)
        if stage == "replay" and rec.get("status") == "complete" and not bad:
            repro = [r for r in att["inputs"] if accepted_attempt(reg, r)
                     and accepted_attempt(reg, r)["stage"] == "reproduce"
                     and accepted_attempt(reg, r)["candidate"] == att["candidate"]]
            if not repro:
                return ["replay inputs must include the accepted reproduction record of this candidate"]
            bad += shapes.replay_vs_reproduction(root, rec, read_json(under(root, repro[0])))
        return bad
    if stage == "adjudicate":
        bad = shapes.decision(root, rec, att)
        inputs = set(att["inputs"])
        if not inputs & accepted_for(reg, "prepare", att["change"]):
            bad.append("decision inputs must include the accepted prepare record")
        if not inputs & accepted_for(reg, "hunt", att["change"]):
            bad.append("decision inputs must include the accepted hunt record")
        return bad
    return []


def hunt_problems(root: Path, reg: dict, att: dict, rec: dict) -> list:
    ids = rec.get("candidates")
    files = rec.get("candidate_files")
    if not str_list(ids) or len(set(ids)) != len(ids):
        return ["'candidates' must be a list of unique candidate ids"]
    if not isinstance(files, dict):
        return ["'candidate_files' must map candidate ids to files"]
    reserved = {cid for cid, c in reg["candidates"].items() if c["prefix"] == att["prefix"]}
    bad = []
    if set(ids) != reserved:
        bad.append(f"'candidates' {sorted(ids)} differ from the ids reserved under {att['prefix']}: {sorted(reserved)}")
    if set(files) != set(ids):
        bad.append("'candidate_files' keys differ from 'candidates'")
    for cid, rel in files.items():
        if cid not in reserved:
            continue
        if not isinstance(rel, str) or not inside(rel, att["directory"]):
            bad.append(f"candidate file of {cid} must be inside {att['directory']}")
            continue
        try:
            body = evidence.verify(root, rel)
        except Refusal as exc:
            bad.append(f"candidate file of {cid}: {exc}")
            continue
        bad += shapes.candidate_file(body, cid, reg["candidates"][cid]["key"], att["change"])
    return bad


def review(root: Path, reg: dict, att: dict, record_rel: str) -> dict:
    if att["state"] not in ("running", "accepted"):
        raise Refusal(f"{att['id']} is {att['state']}")
    if att["state"] == "accepted" and att["record"] != record_rel:
        raise Refusal(f"{att['id']} was accepted with {att['record']}, not {record_rel}")
    rec = evidence.verify(root, record_rel)
    bad = shapes.common(rec, att, record_rel) + stage_problems(root, reg, att, rec)
    if input_hashes(root, reg, att["stage"], att["change"], att["inputs"]) != att["input_hashes"]:
        bad.append("an assigned input changed since the attempt was reserved")
    launch = att["launch"] or {}
    for rel, want in launch.get("hashes", {}).items():
        try:
            same = digest(under(root, rel)) == want
        except Refusal:
            same = False
        if not same:
            bad.append(f"launch evidence {rel} changed or vanished")
    if att["state"] == "accepted" and digest(root / evidence.seal_of(record_rel)) != att["seal"]:
        bad.append("the seal differs from the accepted one")
    if bad:
        raise Refusal("; ".join(bad))
    return rec


def cmd_check(root: Path, args) -> dict:
    reg = load(root)
    att = attempt_of(reg, args.attempt)
    review(root, reg, att, args.record)
    return {"attempt": att["id"], "record": args.record, "ok": True}


def cmd_accept(root: Path, args) -> dict:
    reg = load(root)
    att = attempt_of(reg, args.attempt)
    if att["state"] != "running":
        raise Refusal(f"{att['id']} is {att['state']}; only a running attempt can be accepted")
    terminal = terminal_receipt(root, att, f"{RUNTIME}/{att['id']}-terminal.json")
    rec = review(root, reg, att, args.record)
    if att["stage"] == "hunt":
        for cid, rel in rec["candidate_files"].items():
            reg["candidates"][cid]["file"] = rel
    att.update(state="accepted", record=args.record, seal=digest(root / evidence.seal_of(args.record)),
               terminal=terminal)
    write_json(registry_path(root), reg)
    return {"attempt": att["id"], "state": "accepted", "record": args.record, "status": rec["status"]}


def cmd_show(root: Path, _args) -> dict:
    return load(root)


def attempt_of(reg: dict, aid: str) -> dict:
    if aid not in reg["attempts"]:
        raise Refusal(f"no attempt {aid}")
    return reg["attempts"][aid]


def accepted_attempt(reg: dict, record_rel: str):
    for att in reg["attempts"].values():
        if att["state"] == "accepted" and att["record"] == record_rel:
            return att
    return None


def change_of(reg: dict, record_rel: str):
    att = accepted_attempt(reg, record_rel)
    return att["change"] if att else None


def scope_problems(reg: dict, index: dict) -> list:
    scope = reg.get("scope") or {}
    listed = index.get("changes") if isinstance(index, dict) else None
    if not isinstance(listed, list):
        return ["campaign.json has no 'changes' list"]
    seen = {c.get("id"): c.get("input") for c in listed if isinstance(c, dict)}
    if len(seen) != len(listed):
        return ["campaign.json lists a change twice or a change without an id"]
    if seen != scope.get("changes"):
        return ["campaign.json changes differ from the frozen scope"]
    return []


def weakest(reg: dict, attempts) -> object:
    levels = [reg["attempts"][a]["verification"] if a in reg["attempts"] else None for a in attempts]
    if not levels or any(level not in LEVEL for level in levels):
        return None
    return min(levels, key=LEVEL.get)


COMMANDS = {"init": cmd_init, "reserve": cmd_reserve, "bind": cmd_bind, "candidate": cmd_candidate,
            "retry": cmd_retry, "check": cmd_check, "accept": cmd_accept, "show": cmd_show}


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="registry.py", description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest="command", required=True)
    for name in ("init", "show"):
        sub.add_parser(name).add_argument("campaign")
    p = sub.add_parser("reserve")
    p.add_argument("campaign")
    p.add_argument("--stage", required=True, choices=shapes.STAGES)
    p.add_argument("--change", required=True)
    p.add_argument("--candidate")
    p.add_argument("--input", action="append", metavar="PATH")
    p = sub.add_parser("bind")
    p.add_argument("campaign")
    p.add_argument("attempt")
    p.add_argument("--agent", required=True)
    p.add_argument("--agent-record", required=True)
    p = sub.add_parser("candidate")
    p.add_argument("campaign")
    p.add_argument("attempt")
    p.add_argument("--agent", required=True)
    p.add_argument("--key", required=True)
    p = sub.add_parser("retry")
    p.add_argument("campaign")
    p.add_argument("attempt")
    p.add_argument("--agent-record")
    p.add_argument("--inputs", nargs="*", metavar="PATH")
    for name in ("check", "accept"):
        p = sub.add_parser(name)
        p.add_argument("campaign")
        p.add_argument("attempt")
        p.add_argument("record")
    return top


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        root = campaign(args.campaign)
        with locked(root):
            out = COMMANDS[args.command](root, args)
    except (Refusal, OSError) as exc:
        print(f"registry.py {args.command} refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
