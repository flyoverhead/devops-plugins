#!/usr/bin/env python3
"""Decide the verdict of a patching-bugs run directory from its records and receipts.

    verdict.py <run-dir>

Prints the verdict on the first line, then one "- " line per reason, then the claim
breadth. Exit 0 when a verdict was reached, 1 when a required record is missing or a
record fails `records.py check`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arms  # noqa: E402
import markers  # noqa: E402
import records  # noqa: E402


def read_stream(folder: Path, rel: str) -> str:
    try:
        return (folder / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def observed(folder, run, planned):
    """(problem, actual) for one side of a case."""
    if run["exit_code"] is None:
        return "did not complete (timeout or kill)", None
    problem, payload = markers.observe(read_stream(folder, run["stdout"]), planned)
    if problem:
        return problem, None
    return None, payload["actual"]


def judge_case(folder: Path, planned: dict, case: dict):
    """Return ('pass'|'gap'|'finding', why) for one prove.json case."""
    same = markers.same_json
    sides = {}
    for side in ("baseline", "patched"):
        problem, actual = observed(folder, case["runs"][side], planned["input"])
        if problem:
            return "gap", f"{side}: {problem}"
        sides[side] = (case["runs"][side]["exit_code"], actual)
    want = planned["expected"]
    b_exit, b_actual = sides["baseline"]
    p_exit, p_actual = sides["patched"]
    if planned["role"] == "representative":
        if b_exit == 0 or same(b_actual, want):
            return "gap", "baseline did not show the failure"
    elif b_exit != 0 or not same(b_actual, want):
        return "gap", "control misbehaves on the baseline"
    if p_exit != 0 and not same(p_actual, want):
        return "finding", f"patched tree still fails: actual {markers.compact(p_actual)}"
    if p_exit != 0 or not same(p_actual, want):
        return "gap", "patched exit code and actual value disagree"
    return "pass", ""


def judge_check(folder: Path, check: dict):
    base, patched = check["baseline"], check["patched"]
    if patched["exit_code"] is None:
        return "gap", "patched run did not complete"
    if base is None:
        if check["kind"] == "suite" and patched["exit_code"] == 0:
            return "pass", ""
        return "gap", "no baseline run to compare with"
    if base["exit_code"] != 0:
        return "gap", "baseline run does not pass, so the check proves nothing"
    if patched["exit_code"] != 0:
        return "finding", "passes on baseline, fails on the patched tree"
    if check["kind"] == "behavior" and \
            read_stream(folder, base["stdout"]) != read_stream(folder, patched["stdout"]):
        return "finding", "patched output differs from baseline output"
    return "pass", ""


def arm_mismatches(folder: Path, proof: dict) -> list:
    """Recompute the three-arm result from the retained arm.json files."""
    facts = {}
    for arm in ("baseline", "patched", "reverted"):
        path = folder / "receipts" / arm / "arm.json"
        if not path.is_file():
            return [f"gap: receipts/{arm}/arm.json is missing"]
        facts[arm] = records.load(path)
    try:
        again = arms.summarise(proof["failure_type"], facts)
    except (KeyError, TypeError):
        return ["gap: an arm.json lacks the fields the three-arm result needs"]
    return [f"gap: prove.json {key} differs from what the arm receipts give ({again[key]})"
            for key in ("reverted", "build_identity", "hashes") if again[key] != proof[key]]


def proof_problems(folder: Path, proof: dict, patch: dict, scope: dict) -> list:
    if not scope:
        return ["gap: finding.json has no repair_scope to judge the cases against"]
    out = []
    planned = {c["check_id"]: c for c in scope["cases"]}
    for cid in sorted(set(planned) - {c["check_id"] for c in proof["cases"]}):
        out.append(f"gap: planned case {cid} was not run")
    for case in proof["cases"]:
        if not case["argv"]:
            out.append(f"gap: case {case['check_id']} has an empty argv")
            continue
        verdict, why = judge_case(folder, planned[case["check_id"]], case)
        if verdict != "pass":
            out.append(f"{verdict}: case {case['check_id']}: {why}")
    if not proof["project_checks"]:
        out.append("gap: no project checks recorded")
    for check in proof["project_checks"]:
        if not check["argv"]:
            out.append(f"gap: project check {check['check_id']} has an empty argv")
            continue
        verdict, why = judge_check(folder, check)
        if verdict != "pass":
            out.append(f"{verdict}: project check {check['check_id']}: {why}")
    if not proof["unproven"]:
        out.append("gap: the unproven list is empty")
    source_path = folder / "receipts" / "source.json"
    if not source_path.is_file():
        out.append("gap: receipts/source.json is missing")
    else:
        source = records.load(source_path)
        trees = source.get("trees", {}) if isinstance(source, dict) else {}
        if not isinstance(source, dict) or source.get("baseline_commit") != proof["baseline_commit"] \
                or source.get("patch_commit") != proof["patch_commit"]:
            out.append("gap: source.json commits differ from prove.json")
        if trees.get("reverted") != trees.get("baseline"):
            out.append("gap: reverted tree differs from the baseline tree")
        if trees.get("patched") == trees.get("baseline"):
            out.append("gap: patched tree equals the baseline tree")
    out += arm_mismatches(folder, proof)
    if patch and (patch["baseline_commit"], patch["patch_commit"]) != \
            (proof["baseline_commit"], proof["patch_commit"]):
        out.append("gap: prove.json commits differ from patch.json")
    return out


def decide(run_dir: Path):
    data = records.check_run(run_dir)
    for key in ("run", "finding", "reproduce"):
        if key not in data:
            raise records.Invalid(f"{run_dir}: required record {key} is missing")
    finding, rep = data["finding"], data["reproduce"]
    scope = finding.get("repair_scope")
    claim = "exact example"
    if scope and scope["mode"] == "bounded_class" and not records.scope_gaps(scope):
        claim = "bounded class"
    if rep["outcome"] != "reproduced":
        return "NOT_REPRODUCED", [f"reproduction outcome is {rep['outcome']}"], claim
    if "validate" not in data:
        raise records.Invalid(f"{run_dir}: validate/validate.json is missing")
    if data["validate"]["outcome"] != "confirmed":
        return "NOT_REPRODUCED", [f"validation outcome is {data['validate']['outcome']}"], claim

    blockers, concerns = [], []
    latest = data["run"]["attempts"]
    patch, proof = data["patch"].get(latest), data["prove"].get(latest)
    if latest == 0:
        blockers.append("no patch attempt was made")
    if rep["agent"] == data["validate"]["agent"]:
        blockers.append("reproducer and validator share an agent identity")
    above = sorted(n for n in set(data["patch"]) | set(data["prove"]) if n > latest)
    if above:
        blockers.append(f"evidence exists for attempt(s) {above} above run.attempts {latest}")
    if latest and (patch is None or patch["patch_commit"] is None):
        blockers.append(f"attempt {latest} has no patch commit")
    if latest and proof is None:
        blockers.append(f"attempt {latest} has no proof")
    if patch and proof:
        folder = run_dir / "prove" / f"attempt-{latest}"
        if patch["agent"] == proof["agent"]:
            blockers.append("patcher and prover share an agent identity")
        if proof["reverted"] != "pass":
            blockers.append(f"three-arm result is {proof['reverted']}")
        wanted = "not_applicable" if proof["failure_type"] == "compile" else "pass"
        if proof["build_identity"] != wanted:
            blockers.append(f"build_identity is {proof['build_identity']}, wanted {wanted}")
        if proof["failure_type"] != rep.get("failure_type", "runtime"):
            blockers.append("proof failure_type differs from the reproduction")
        if proof["baseline_commit"] != rep["baseline_commit"]:
            blockers.append("proof baseline differs from the reproduced baseline")
        blockers += proof_problems(folder, proof, patch, scope)
        concerns += [f"variant not fixed: {v['location']} ({v['reason']})"
                     for v in patch["variants"] if v["status"] == "not_fixed"]
    regression = data.get("regression")
    if regression is None:
        concerns.append("regression stage has no record (not run)")
    else:
        found = {o["outcome"] for o in regression["outcomes"]}
        blockers += [f"regression outcome {o}" for o in ("REPRODUCED_REGRESSION", "INCOMPLETE_FIX")
                     if o in found]
        if "UNRESOLVED" in found:
            concerns.append("regression candidates left UNRESOLVED")
        if regression["coverage"] == "INCOMPLETE":
            concerns.append("regression coverage INCOMPLETE")
        if "INCOMPLETE_FIX" in found:
            claim = "exact example"
    if blockers:
        claim = "exact example" if claim == "bounded class" and any(
            b.startswith(("gap", "finding")) for b in blockers) else claim
        return "NOT_READY", blockers + concerns, claim
    if concerns:
        return "READY_WITH_CONCERNS", concerns, claim
    return "READY", [], claim


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0].startswith("-"):
        print("usage: verdict.py <run-dir>", file=sys.stderr)
        return 2
    try:
        verdict, reasons, claim = decide(Path(argv[0]))
    except records.Invalid as why:
        print(f"verdict.py: {why}", file=sys.stderr)
        return 1
    print(verdict)
    for reason in reasons:
        print(f"- {reason}")
    print(f"claim: {claim}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
