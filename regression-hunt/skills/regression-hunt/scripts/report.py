#!/usr/bin/env python3
"""Render a campaign's findings as report.json, report.md and index.html.

Usage: report.py CAMPAIGN [--output REL_DIR]   (default REL_DIR: report)

Integrity problems (an index that disagrees with the frozen scope, a record that is not accepted or
whose seal no longer verifies) stop the run with exit 1 and nothing written. A decision that fails
the confirmation rules is not an integrity problem: that finding is shown as UNRESOLVED with the reason.
"""
import argparse
import html
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402
import registry  # noqa: E402
import shapes  # noqa: E402
from rhlib import Refusal, campaign, nonempty, read_json, under, write_json  # noqa: E402

NOTICE = "Agent conclusions, pending human review. Seals show the evidence is unchanged, not that a conclusion is true."
OPTIONAL = ("category", "severity", "likelihood", "severity_reason", "likelihood_reason", "duplicate_of")


def trusted(root: Path, reg: dict, rel: str, stage: str, change: str) -> dict:
    """Load a record the index points to, or raise: it must be accepted, sealed and belong to change."""
    att = registry.accepted_attempt(reg, rel)
    if att is None or att["stage"] != stage:
        raise Refusal(f"{rel} is not an accepted {stage} record")
    if att["change"] != change:
        raise Refusal(f"{rel} was accepted for change {att['change']}, not {change}")
    rec = evidence.verify(root, rel)
    if rec.get("change") != change:
        raise Refusal(f"{rel} says change {rec.get('change')!r}, the index says {change}")
    if not nonempty(rec.get("security_review")):
        raise Refusal(f"{rel} has an empty security_review")
    return rec


def experiment_ok(root, reg, rel, stage, cand, change, needed) -> tuple:
    att = registry.accepted_attempt(reg, rel)
    if att is None or att["stage"] != stage:
        return None, [f"{rel} is not an accepted {stage} record"]
    rec = evidence.verify(root, rel)
    bad = shapes.experiment(root, rec, att)
    if rec.get("status") != "complete":
        bad.append(f"{stage} {rel} is not complete")
    if rec.get("candidate") != cand or att["change"] != change:
        bad.append(f"{stage} {rel} is for another candidate or change")
    missing = needed - set(rec.get("inputs") or [])
    if missing:
        bad.append(f"{stage} {rel} does not list {', '.join(sorted(missing))} as inputs")
    runs = rec.get("runs") or []
    if [r.get("behavior") for r in runs if isinstance(r, dict)] != ["correct", "failure"]:
        bad.append(f"{stage} {rel}: S0 must behave correctly and S1 must fail")
    return (att, rec), bad


def confirmation_problems(root: Path, reg: dict, dec: dict, dec_att: dict, ctx: dict) -> list:
    bad = []
    if dec.get("status") != "complete":
        bad.append("a confirmation needs status complete")
    if ctx["prepare"] is None or ctx["prepare"].get("status") != "complete":
        bad.append("the prepare record is not complete")
    needed = {ctx["prepare_rel"], ctx["hunt_rel"]} - {None}
    found = {}
    for key, stage in (("reproduction", "reproduce"), ("replay", "replay")):
        rel = dec.get(key)
        if not isinstance(rel, str):
            bad.append(f"'{key}' must name the {stage} record")
            continue
        pair, problems = experiment_ok(root, reg, rel, stage, dec.get("candidate"), dec_att["change"], needed)
        bad += problems
        if pair:
            found[key] = pair
    if len(found) == 2:
        (r_att, r_rec), (p_att, p_rec) = found["reproduction"], found["replay"]
        bad += shapes.replay_vs_reproduction(root, p_rec, r_rec)
        if dec["reproduction"] not in (p_rec.get("inputs") or []):
            bad.append("the replay does not list the reproduction record as an input")
        if r_rec.get("source") != (ctx["prepare"] or {}).get("source"):
            bad.append("the experiments did not use the prepare stage's source.json")
        agents = {r_att["agent"], p_att["agent"], dec_att["agent"]}
        if len(agents) != 3:
            bad.append("reproduction, replay and adjudication were not three different agents")
        for key in ("reproduction", "replay"):
            if dec[key] not in (dec.get("inputs") or []):
                bad.append(f"the decision does not list its {key} record as an input")
    for key, allowed in (("category", shapes.CATEGORIES), ("severity", shapes.SEVERITIES),
                         ("likelihood", shapes.LIKELIHOODS)):
        if dec.get(key) not in allowed:
            bad.append(f"'{key}' must be one of {', '.join(allowed)}")
    for key in ("severity_reason", "likelihood_reason"):
        if not isinstance(dec.get(key), str) or not dec[key].strip():
            bad.append(f"'{key}' is empty")
    bad += check_problems(root, dec)
    want_inputs = needed | {ctx["candidate_rel"]}
    if not want_inputs <= set(dec.get("inputs") or []):
        bad.append("the decision inputs must include the prepare, hunt and candidate records")
    return bad


def check_problems(root: Path, dec: dict) -> list:
    checks = dec.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(shapes.CHECK_WANT):
        return [f"'checks' must hold exactly: {', '.join(shapes.CHECK_WANT)}"]
    files = shapes.package_files(root, dec)
    bad = []
    for key, want in shapes.CHECK_WANT.items():
        item = checks[key] if isinstance(checks[key], dict) else {}
        got = item.get("conclusion")
        if key == "security_scope":
            want = "SUPPORTED" if dec.get("category") == "VULNERABILITY" else "NOT_APPLICABLE"
        if got not in shapes.CONCLUSIONS:
            bad.append(f"check {key}: unknown conclusion {got!r}")
        elif got != want:
            bad.append(f"check {key} is {got}, a confirmation needs {want}")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            bad.append(f"check {key}: empty reason")
        ev = item.get("evidence")
        if got != "NOT_APPLICABLE" and (not isinstance(ev, list) or not ev):
            bad.append(f"check {key}: no evidence")
        for path in ev if isinstance(ev, list) else []:
            if not isinstance(path, str) or not shapes.in_package(path, files):
                bad.append(f"check {key}: evidence {path} is outside the package")
    return bad


def finding_for(root, reg, change, entry, ctx) -> dict:
    cid = entry["id"]
    cand = evidence.verify(root, entry["candidate"])
    title = cand.get("title") or cid
    if isinstance(title, list):
        title = "; ".join(str(t) for t in title)
    row = {"id": cid, "change": change["id"], "input": change["input"], "title": str(title),
           "outcome": "UNRESOLVED", "reason": "", "evidence": [], "verification": None, "unresolved_reason": None}
    if not entry.get("decision"):
        row["reason"] = row["unresolved_reason"] = "No adjudication has been accepted for this candidate yet."
        return row
    dec = trusted(root, reg, entry["decision"], "adjudicate", change["id"])
    dec_att = registry.accepted_attempt(reg, entry["decision"])
    bad = shapes.decision(root, dec, dec_att)
    if dec.get("candidate") != cid:
        bad.append(f"the decision is about {dec.get('candidate')!r}, not {cid}")
    if not bad and dec["outcome"] == "REPRODUCED_REGRESSION":
        bad = confirmation_problems(root, reg, dec, dec_att, ctx)
    if bad:
        row["reason"] = row["unresolved_reason"] = "Decision rejected by validation: " + "; ".join(bad)
        row["evidence"] = [entry["decision"]]
        return row
    row.update(outcome=dec["outcome"], reason=dec["reason"], evidence=list(dec["evidence"]))
    for key in OPTIONAL:
        if dec.get(key) is not None:
            row[key] = dec[key]
    if dec["outcome"] == "UNRESOLVED":
        row["unresolved_reason"] = dec["reason"]
    if dec["outcome"] == "REPRODUCED_REGRESSION":
        ids = [registry.accepted_attempt(reg, dec[k])["id"] for k in ("reproduction", "replay")] + [dec_att["id"]]
        row["verification"] = registry.weakest(reg, ids)
    return row


def settle_duplicates(rows: list):
    by_id = {r["id"]: r for r in rows}
    for row in rows:
        target = row.get("duplicate_of")
        if target is None:
            continue
        canon = by_id.get(target)
        problem = None
        if row["outcome"] == "REPRODUCED_REGRESSION":
            problem = "a confirmation cannot be a duplicate"
        elif canon is None:
            problem = f"duplicate_of {target} is not a finding of this campaign"
        elif canon.get("duplicate_of"):
            problem = f"duplicate_of {target} is itself a duplicate"
        elif canon["outcome"] != row["outcome"]:
            problem = f"duplicate_of {target} has outcome {canon['outcome']}"
        if problem:
            row.update(outcome="UNRESOLVED", unresolved_reason="Decision rejected by validation: " + problem,
                       reason="Decision rejected by validation: " + problem, verification=None)
            row.pop("duplicate_of")


def gather(root: Path) -> dict:
    reg = registry.load(root)
    registry.frozen(reg)
    index = read_json(under(root, "campaign.json"), "campaign index")
    problems = registry.scope_problems(reg, index)
    if problems:
        raise Refusal("; ".join(problems))
    rows, coverage, seen = [], [], set()
    for change in index["changes"]:
        cid = change["id"]
        ctx = {"prepare_rel": change.get("prepare"), "hunt_rel": change.get("hunt"), "prepare": None}
        prep = trusted(root, reg, ctx["prepare_rel"], "prepare", cid) if ctx["prepare_rel"] else None
        hunt = trusted(root, reg, ctx["hunt_rel"], "hunt", cid) if ctx["hunt_rel"] else None
        ctx["prepare"] = prep
        listed = change.get("candidates") or []
        registered = {k for k, c in reg["candidates"].items() if c["change"] == cid and c["file"]}
        if {e.get("id") for e in listed} != registered:
            raise Refusal(f"change {cid}: indexed candidates differ from the accepted ones {sorted(registered)}")
        mine = []
        for entry in listed:
            if entry["id"] in seen:
                raise Refusal(f"candidate {entry['id']} is indexed twice")
            seen.add(entry["id"])
            if reg["candidates"][entry["id"]]["file"] != entry.get("candidate"):
                raise Refusal(f"candidate {entry['id']}: the index points to another file than the registry")
            mine.append(finding_for(root, reg, change, entry, dict(ctx, candidate_rel=entry["candidate"])))
        rows += mine
        done = (prep and prep.get("status") == "complete" and hunt and hunt.get("status") == "complete"
                and all(r["outcome"] != "UNRESOLVED" for r in mine))
        coverage.append({"id": cid, "input": change["input"], "status": "COMPLETE" if done else "INCOMPLETE",
                         "limitations": change.get("limitations") or ""})
    settle_duplicates(rows)
    counts = {o: sum(1 for r in rows if r["outcome"] == o and not r.get("duplicate_of")) for o in shapes.OUTCOMES}
    return {"title": index.get("title") or "Regression hunt", "counts": counts, "changes": coverage,
            "findings": rows}


def shown_input(value) -> str:
    if isinstance(value, dict):
        return f"{value['repository']} @ {value['s0']}..{value['s1']}"
    return str(value)


def link(root: Path, out: Path, rel: str) -> str:
    return os.path.relpath(root / rel, out)


def markdown(data: dict, root: Path, out: Path) -> str:
    lines = [f"# {data['title']}", "", f"> {NOTICE}", "", "## Counts", ""]
    lines += [f"- {k}: {v}" for k, v in data["counts"].items()]
    lines += ["", "## Coverage", ""]
    lines += [f"- {c['id']} ({shown_input(c['input'])}): {c['status']}"
              + (f". Limits: {c['limitations']}" if c["limitations"] else "") for c in data["changes"]]
    for f in data["findings"]:
        label = f["outcome"] + (f" (verification: {f['verification']})" if f["verification"] else "")
        lines += ["", f"## {f['id']}: {f['title']}", "", f"- Outcome: {label}",
                  f"- Change: {f['change']} ({shown_input(f['input'])})", f"- Reason: {f['reason']}"]
        if f.get("duplicate_of"):
            lines.append(f"- Duplicate of: {f['duplicate_of']}")
        for key in ("category", "severity", "likelihood"):
            if f.get(key):
                why = f.get(f"{key}_reason")
                lines.append(f"- {key.capitalize()}: {f[key]}" + (f" ({why})" if why else ""))
        lines += [f"- Evidence: [{e}]({link(root, out, e)})" for e in f["evidence"]]
    return "\n".join(lines) + "\n"


def page(data: dict, root: Path, out: Path) -> str:
    e = html.escape
    parts = [f"<!doctype html><meta charset=\"utf-8\"><title>{e(data['title'])}</title>",
             f"<h1>{e(data['title'])}</h1><p><strong>{e(NOTICE)}</strong></p><h2>Counts</h2><ul>"]
    parts += [f"<li>{e(k)}: {v}</li>" for k, v in data["counts"].items()]
    parts.append("</ul><h2>Coverage</h2><ul>")
    parts += [f"<li>{e(c['id'])} ({e(shown_input(c['input']))}): {e(c['status'])}"
              + (f". Limits: {e(c['limitations'])}" if c["limitations"] else "") + "</li>" for c in data["changes"]]
    parts.append("</ul>")
    for f in data["findings"]:
        label = f["outcome"] + (f" (verification: {f['verification']})" if f["verification"] else "")
        parts.append(f"<section><h2>{e(f['id'])}: {e(f['title'])}</h2><ul>"
                     f"<li>Outcome: {e(label)}</li><li>Change: {e(f['change'])} ({e(shown_input(f['input']))})</li>"
                     f"<li>Reason: {e(f['reason'])}</li>")
        for key in ("category", "severity", "likelihood"):
            if f.get(key):
                parts.append(f"<li>{e(key.capitalize())}: {e(str(f[key]))} {e(str(f.get(key + '_reason') or ''))}</li>")
        parts += [f"<li>Evidence: <a href=\"{e(link(root, out, ev), quote=True)}\">{e(ev)}</a></li>" for ev in f["evidence"]]
        parts.append("</ul></section>")
    return "\n".join(parts) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="report.py", description=__doc__.splitlines()[0])
    parser.add_argument("campaign")
    parser.add_argument("--output", default="report", help="campaign-relative directory to create")
    args = parser.parse_args(argv)
    try:
        root = campaign(args.campaign)
        out = under(root, args.output, exist=False)
        if out.exists():
            raise Refusal(f"{args.output} already exists; reports are written once")
        with registry.locked(root):
            data = gather(root)
        md, doc = markdown(data, root, out), page(data, root, out)
        out.mkdir(parents=True)
        write_json(out / "report.json", data)
        (out / "report.md").write_text(md, encoding="utf-8")
        (out / "index.html").write_text(doc, encoding="utf-8")
    except (Refusal, OSError) as exc:
        print(f"report.py refused: {exc}", file=sys.stderr)
        return 1
    except (KeyError, TypeError, AttributeError) as exc:
        print(f"report.py refused: malformed index or record ({exc!r})", file=sys.stderr)
        return 1
    print(out / "index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
