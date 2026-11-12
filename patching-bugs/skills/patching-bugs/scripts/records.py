#!/usr/bin/env python3
"""Record formats of a patching-bugs run directory: validation, manifests, guidance copies.

    records.py check <run-dir> [--before-repair]
    records.py manifest <step-dir>
    records.py guidance <run-dir> --repo <checkout> --commit <sha>
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SHA40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
ATTEMPT_DIR = re.compile(r"attempt-([1-3])")
GUIDANCE_NAMES = ("CLAUDE.md", "AGENTS.md", "PATCHING_GUIDELINES.md", "THREAT_MODEL.md")
GUIDANCE_BUDGET = 60_000
STEP_NAMES = ("intake", "reproduce", "validate", "patch", "prove", "regression", "report")


class Invalid(Exception):
    """A record, manifest or plan breaks a rule; the message names where."""


def text(lo=1, hi=None):
    def ok(value, at):
        if not isinstance(value, str):
            raise Invalid(f"{at}: wanted a string, got {type(value).__name__}")
        if len(value) < lo or (hi is not None and len(value) > hi):
            span = f"{lo}..{hi}" if hi is not None else f"at least {lo}"
            raise Invalid(f"{at}: length {len(value)} outside {span}")
    return ok


def integer(lo=None, hi=None):
    def ok(value, at):
        if isinstance(value, bool) or not isinstance(value, int):
            raise Invalid(f"{at}: wanted an integer, got {json.dumps(value)}")
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            raise Invalid(f"{at}: {value} outside {lo}..{hi}")
    return ok


def flag(value, at):
    if not isinstance(value, bool):
        raise Invalid(f"{at}: wanted true or false")


def pattern(rx, label):
    def ok(value, at):
        if not isinstance(value, str) or not rx.fullmatch(value):
            raise Invalid(f"{at}: not {label}: {json.dumps(value)}")
    return ok


sha = pattern(SHA40, "a 40-char lowercase commit id")
digest = pattern(HEX64, "a 64-char lowercase sha256")


def exactly(constant):
    def ok(value, at):
        if value != constant or isinstance(value, bool):
            raise Invalid(f"{at}: must be {json.dumps(constant)}")
    return ok


def choice(*options):
    def ok(value, at):
        if value not in options:
            raise Invalid(f"{at}: {json.dumps(value)} is not one of {', '.join(options)}")
    return ok


def nullable(inner):
    def ok(value, at):
        if value is not None:
            inner(value, at)
    return ok


def anything(value, at):
    return None


def items(inner, most=None):
    def ok(value, at):
        if not isinstance(value, list):
            raise Invalid(f"{at}: wanted a list")
        if most is not None and len(value) > most:
            raise Invalid(f"{at}: {len(value)} entries, at most {most} allowed")
        for n, element in enumerate(value):
            inner(element, f"{at}[{n}]")
    return ok


def shape(required=None, optional=None):
    required, optional = required or {}, optional or {}

    def ok(value, at):
        if not isinstance(value, dict):
            raise Invalid(f"{at}: wanted an object")
        unknown = sorted(set(value) - set(required) - set(optional))
        if unknown:
            raise Invalid(f"{at}: unexpected field(s) {', '.join(unknown)}")
        for key, rule in required.items():
            if key not in value:
                raise Invalid(f"{at}: missing field {key}")
            rule(value[key], f"{at}.{key}")
        for key, rule in optional.items():
            if key in value:
                rule(value[key], f"{at}.{key}")
    return ok


SCOPE_CASE = shape({"check_id": text(), "role": choice("representative", "control"),
                    "input": anything, "expected": anything, "why": text(1, 300)})

FINDING = shape(
    {"schema_version": exactly(1), "title": text(1, 120), "claim": text(1, 400),
     "affected_code": items(shape({"path": text(1, 400), "start_line": integer(0),
                                   "end_line": integer(0)})),
     "invariant": text(1, 300), "poc": nullable(text()), "source": text(1, 200),
     "status": choice("hypothesis", "reproduced", "not_reproduced", "confirmed", "not_confirmed")},
    {"reported": shape(optional={"impact": text(), "expected_behavior": text(),
                                 "observed_behavior": text(), "severity": text(),
                                 "priority": text(), "reproduction_steps": items(text())}),
     "repair_scope": shape({"mode": choice("bounded_class", "exact_example"),
                            "boundary": text(1, 400), "cases": items(SCOPE_CASE),
                            "exclusions": items(text(1, 300))})})

RUN = shape({"schema_version": exactly(1), "finding_id": text(1, 400),
             "status": choice("in_progress", "not_reproduced", "not_ready",
                              "ready_with_concerns", "ready"),
             "attempts": integer(0, 3),
             "steps": shape({name: choice("pending", "done", "failed", "skipped")
                             for name in STEP_NAMES})})

REPRODUCE = shape(
    {"schema_version": exactly(1), "outcome": choice("reproduced", "not_reproduced", "blocked"),
     "baseline_commit": sha, "build_argv": items(text(1, 400)), "poc_argv": items(text(1, 400)),
     "target_artifact": nullable(text(1, 400)), "observed": text(1, 400),
     "blocker": nullable(text()), "agent": text(1, 100)},
    {"failure_type": choice("runtime", "compile"), "expected_diagnostic": text(1, 400)})

VALIDATE = shape({"schema_version": exactly(1),
                  "outcome": choice("confirmed", "not_confirmed", "inconclusive"),
                  "agent": text(1, 100), "reason": text(1, 400)})

SUITE = shape({"command": text(1, 400), "passed": integer(0), "failed": integer(0),
               "skipped": integer(0)})

PATCH = shape({"schema_version": exactly(1), "attempt": integer(1, 3), "baseline_commit": sha,
               "patch_commit": nullable(sha), "files_changed": integer(0),
               "lines_added": integer(0), "lines_removed": integer(0),
               "variants": items(shape({"location": text(1, 400),
                                        "status": choice("fixed", "not_fixed"),
                                        "reason": text(1, 200)})),
               "suite_before": SUITE, "suite_after": SUITE, "agent": text(1, 100)})

RUN_RECEIPT = shape({"exit_code": nullable(integer()), "elapsed_ms": integer(0),
                     "stdout": text(1, 400), "stderr": text(1, 400)})

PROVE = shape(
    {"schema_version": exactly(2), "attempt": integer(1, 3),
     "failure_type": choice("runtime", "compile"), "baseline_commit": sha, "patch_commit": sha,
     "reverted": choice("pass", "fail", "inconclusive"),
     "build_identity": choice("pass", "fail", "not_applicable"),
     "hashes": shape({side: nullable(digest) for side in ("baseline", "patched", "reverted")}),
     "reverted_hash_note": nullable(text()),
     "cases": items(shape({"check_id": text(1, 100), "argv": items(text(1, 400)),
                           "source": text(1, 400),
                           "runs": shape({"baseline": RUN_RECEIPT, "patched": RUN_RECEIPT})})),
     "project_checks": items(shape({"check_id": text(1, 100),
                                    "kind": choice("suite", "behavior", "regression", "security"),
                                    "argv": items(text(1)), "baseline": nullable(RUN_RECEIPT),
                                    "patched": RUN_RECEIPT})),
     "unproven": items(text(1, 400)), "agent": text(1, 100)})

REGRESSION = shape({"schema_version": exactly(1), "campaign_dir": text(1, 400),
                    "coverage": choice("COMPLETE", "INCOMPLETE"),
                    "outcomes": items(shape({"candidate_id": text(1, 400),
                                             "outcome": choice("REPRODUCED_REGRESSION",
                                                               "INCOMPLETE_FIX", "LATENT_BUG",
                                                               "PREEXISTING_BUG", "REJECTED",
                                                               "UNRESOLVED"),
                                             "decision_receipt": text(1, 400)}))})

RECEIPT_PAIR = shape({"stdout": text(1, 400), "exit": text(1, 400)})

REPORT_INPUT = shape(
    {"schema_version": exactly(1), "bug": text(1, 600), "fix_why": text(0, 400),
     "open_risks": items(text(1, 200), most=5), "include_poc": flag},
    {"baseline_checks": items(shape({"check_id": text(1, 100), "reproduce": RECEIPT_PAIR,
                                     "validate": RECEIPT_PAIR}), most=30),
     "run_metadata": shape(optional={"date": pattern(DAY, "a YYYY-MM-DD date"),
                                     "elapsed_seconds": integer(0), "model": text(0, 100),
                                     "reasoning_effort": text(0, 60),
                                     "recorded_tokens": integer(0), "run_type": text(0, 80)})})

MANIFEST = shape({"schema_version": exactly(1), "files": anything})


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Invalid(f"{path}: unreadable JSON ({exc})") from None


def dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def hash_tree(step: Path) -> dict:
    """sha256 of every regular file below step except the manifest; symlinks are refused."""
    if step.is_symlink() or not step.is_dir():
        raise Invalid(f"{step}: not a plain directory")
    found = {}
    for entry in sorted(step.rglob("*")):
        rel = entry.relative_to(step).as_posix()
        if entry.is_symlink():
            raise Invalid(f"{step}: symlink {rel} is not allowed in a step directory")
        if entry.is_file() and rel != "manifest.json":
            found[rel] = sha256_file(entry)
    return dict(sorted(found.items()))


def refuse_misplaced_step(step: Path) -> None:
    """A step directory sits in a run directory (run.json or finding.json one or two levels up),
    never in a checkout."""
    inside = subprocess.run(["git", "-C", str(step), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True)
    if inside.returncode == 0 and inside.stdout.strip() == "true":
        raise Invalid(f"{step}: inside a git work tree; run state belongs outside the checkout")
    parent = step.resolve().parent
    markers = ("run.json", "finding.json")
    if not any((where / name).is_file() for where in (parent, parent.parent) for name in markers):
        raise Invalid(f"{step}: no run.json or finding.json in its run directory")


def write_manifest(step: Path) -> None:
    files = hash_tree(step)
    dump(step / "manifest.json", {"schema_version": 1, "files": files})


def verify_manifest(step: Path) -> dict:
    path = step / "manifest.json"
    if not path.is_file():
        raise Invalid(f"{step}: no manifest.json")
    recorded = load(path)
    MANIFEST(recorded, str(path))
    if not isinstance(recorded["files"], dict):
        raise Invalid(f"{path}: files must be an object")
    for rel, hexed in recorded["files"].items():
        digest(hexed, f"{path}: files[{rel}]")
    actual = hash_tree(step)
    missing = sorted(set(recorded["files"]) - set(actual))
    extra = sorted(set(actual) - set(recorded["files"]))
    changed = sorted(k for k in actual if k in recorded["files"] and recorded["files"][k] != actual[k])
    for label, names in (("missing", missing), ("not in manifest", extra), ("changed", changed)):
        if names:
            raise Invalid(f"{step}: {label}: {', '.join(names)}")
    return recorded["files"]


def receipt_path(rel, at, listed):
    if not isinstance(rel, str) or not rel.startswith("receipts/") or ".." in rel.split("/"):
        raise Invalid(f"{at}: {json.dumps(rel)} must be a receipts/... path without '..'")
    if rel not in listed:
        raise Invalid(f"{at}: {rel} is not retained in the manifest")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def scope_gaps(scope) -> list:
    gaps = []
    cases = scope.get("cases", [])
    roles = [c["role"] for c in cases]
    if "representative" not in roles:
        gaps.append("repair_scope has no representative case")
    if scope.get("mode") == "bounded_class":
        if roles.count("representative") < 2:
            gaps.append("bounded_class needs at least two representative cases")
        if "control" not in roles:
            gaps.append("bounded_class needs at least one control case")
        inputs = [canonical(c["input"]) for c in cases]
        if len(set(inputs)) != len(inputs):
            gaps.append("bounded_class repeats an input")
    ids = [c["check_id"] for c in cases]
    if len(set(ids)) != len(ids):
        gaps.append("repair_scope repeats a check_id")
    return gaps


def reproduce_rules(rec, at):
    kind = rec.get("failure_type", "runtime")
    if kind == "runtime" and rec["target_artifact"] is None:
        raise Invalid(f"{at}: a runtime reproduction names its target_artifact")
    if kind == "compile":
        if not rec.get("expected_diagnostic", "").strip():
            raise Invalid(f"{at}: a compile reproduction needs expected_diagnostic")
        if rec["target_artifact"] is not None or rec["poc_argv"]:
            raise Invalid(f"{at}: a compile reproduction has no artifact and an empty poc_argv")
        if not rec["build_argv"]:
            raise Invalid(f"{at}: a compile reproduction needs build_argv")


def prove_rules(rec, at, listed, scope_ids):
    if rec["failure_type"] == "runtime":
        if rec["build_identity"] == "not_applicable":
            raise Invalid(f"{at}: runtime proof cannot mark build_identity not_applicable")
        if rec["build_identity"] == "pass":
            h = rec["hashes"]
            if None in h.values() or h["baseline"] == h["patched"]:
                raise Invalid(f"{at}: build_identity pass needs three hashes, baseline != patched")
    else:
        if rec["build_identity"] != "not_applicable" or any(rec["hashes"].values()):
            raise Invalid(f"{at}: compile proof needs build_identity not_applicable, null hashes")
    for group in ("cases", "project_checks"):
        ids = [item["check_id"] for item in rec[group]]
        if len(set(ids)) != len(ids):
            raise Invalid(f"{at}.{group}: check_id repeated")
    for n, case in enumerate(rec["cases"]):
        where = f"{at}.cases[{n}]"
        if scope_ids is not None and case["check_id"] not in scope_ids:
            raise Invalid(f"{where}: {case['check_id']} is not a repair_scope case")
        receipt_path(case["source"], f"{where}.source", listed)
        for side, run in case["runs"].items():
            for stream in ("stdout", "stderr"):
                receipt_path(run[stream], f"{where}.runs.{side}.{stream}", listed)
    for n, check in enumerate(rec["project_checks"]):
        for side in ("baseline", "patched"):
            if check[side] is not None:
                for stream in ("stdout", "stderr"):
                    receipt_path(check[side][stream],
                                 f"{at}.project_checks[{n}].{side}.{stream}", listed)


def report_input_rules(rec, at, run_dir, listings):
    for n, item in enumerate(rec.get("baseline_checks", [])):
        for step in ("reproduce", "validate"):
            listed = listings.get(step)
            if listed is None:
                raise Invalid(f"{at}.baseline_checks[{n}]: no verified {step}/ step")
            for key in ("stdout", "exit"):
                rel = item[step][key]
                receipt_path(rel, f"{at}.baseline_checks[{n}].{step}.{key}", listed)
            if not item[step]["exit"].endswith(".exit.json"):
                raise Invalid(f"{at}.baseline_checks[{n}].{step}.exit: wanted a .exit.json file")
            exit_rec = load(run_dir / step / item[step]["exit"])
            if not isinstance(exit_rec, dict) or "exit_code" not in exit_rec:
                raise Invalid(f"{at}.baseline_checks[{n}].{step}.exit: no exit_code inside")


def attempt_dirs(run_dir: Path, stage: str) -> dict:
    root = run_dir / stage
    if not root.exists():
        return {}
    found = {}
    for child in sorted(root.iterdir()):
        m = ATTEMPT_DIR.fullmatch(child.name)
        if not m or not child.is_dir() or child.is_symlink():
            raise Invalid(f"{root}: unexpected entry {child.name} (only attempt-1..3)")
        found[int(m.group(1))] = child
    return found


def check_run(run_dir: Path, before_repair: bool = False) -> dict:
    """Validate everything present under run_dir; returns the loaded records."""
    if not run_dir.is_dir():
        raise Invalid(f"{run_dir}: run directory not found")
    out = {"patch": {}, "prove": {}}
    singles = {"run": ("run.json", RUN), "finding": ("finding.json", FINDING)}
    for key, (name, rule) in singles.items():
        path = run_dir / name
        if path.exists():
            out[key] = load(path)
            rule(out[key], name)
    listings = {}
    for step, name, rule in (("reproduce", "reproduce.json", REPRODUCE),
                             ("validate", "validate.json", VALIDATE),
                             ("regression", "regression.json", REGRESSION)):
        folder = run_dir / step
        if not folder.exists():
            continue
        listings[step] = verify_manifest(folder)
        path = folder / name
        if not path.is_file():
            raise Invalid(f"{folder}: {name} missing")
        out[step] = load(path)
        rule(out[step], f"{step}/{name}")
    if "reproduce" in out:
        reproduce_rules(out["reproduce"], "reproduce/reproduce.json")
    scope = out.get("finding", {}).get("repair_scope")
    scope_ids = {c["check_id"] for c in scope["cases"]} if scope else None
    for stage, name, rule in (("patch", "patch.json", PATCH), ("prove", "prove.json", PROVE)):
        for number, folder in attempt_dirs(run_dir, stage).items():
            where = f"{stage}/{folder.name}/{name}"
            listed = verify_manifest(folder)
            if not (folder / name).is_file():
                raise Invalid(f"{folder}: {name} missing")
            rec = load(folder / name)
            rule(rec, where)
            if rec["attempt"] != number:
                raise Invalid(f"{where}: attempt {rec['attempt']} sits in {folder.name}")
            if stage == "prove":
                prove_rules(rec, where, listed, scope_ids)
            out[stage][number] = rec
    if (run_dir / "report-input.json").exists():
        out["report_input"] = load(run_dir / "report-input.json")
        REPORT_INPUT(out["report_input"], "report-input.json")
        report_input_rules(out["report_input"], "report-input.json", run_dir, listings)
    if before_repair:
        repair_gate(out)
    return out


def repair_gate(out):
    finding, run = out.get("finding"), out.get("run")
    if finding is None or run is None:
        raise Invalid("before-repair: finding.json and run.json are both required")
    scope = finding.get("repair_scope")
    if scope is None:
        raise Invalid("before-repair: finding.json has no repair_scope")
    gaps = scope_gaps(scope)
    if gaps:
        raise Invalid("before-repair: " + "; ".join(gaps))
    retained = sorted(set(out["patch"]) | set(out["prove"]))
    if retained and retained[-1] > run["attempts"]:
        raise Invalid(f"before-repair: attempt-{retained[-1]} exists but run.attempts is "
                      f"{run['attempts']}")
    if 3 in retained:
        raise Invalid("before-repair: attempt-3 exists; all three attempts are used")


def git_bytes(repo: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True)


def guidance(run_dir: Path, repo: Path, commit: str) -> str:
    """Copy root guidance files from the commit's objects (or verify existing copies);
    return the labelled hand-over block."""
    top = git_bytes(repo, "rev-parse", "--show-toplevel")
    if top.returncode:
        raise Invalid(f"{repo}: not a git checkout")
    top_dir = Path(top.stdout.decode().strip()).resolve()
    resolved_run = run_dir.resolve()
    if resolved_run == top_dir or top_dir in resolved_run.parents:
        raise Invalid(f"{run_dir}: run directory must live outside the checkout {top_dir}")
    full = git_bytes(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")
    if full.returncode:
        raise Invalid(f"{commit}: not a commit in {repo}")
    commit = full.stdout.decode().strip()
    folder = run_dir / "guidance" / commit
    blobs = {}
    for name in GUIDANCE_NAMES:
        got = git_bytes(repo, "cat-file", "blob", f"{commit}:{name}")
        if got.returncode == 0:
            blobs[name] = got.stdout
    if folder.exists():
        for name in GUIDANCE_NAMES:
            copy = folder / name
            if (name in blobs) != copy.is_file() or (copy.is_file() and copy.read_bytes() != blobs[name]):
                raise Invalid(f"{folder}: copy of {name} does not match {commit}")
    else:
        folder.mkdir(parents=True)
        for name, blob in blobs.items():
            (folder / name).write_bytes(blob)
        absent = [n for n in GUIDANCE_NAMES if n not in blobs]
        lines = [f"# Guidance source\n", f"\nCommit: `{commit}`\n", "\nPresent:\n"]
        lines += [f"- `{n}` sha256 `{hashlib.sha256(blobs[n]).hexdigest()}`\n" for n in blobs] or ["- none\n"]
        lines += ["\nAbsent:\n"] + ([f"- `{n}`\n" for n in absent] or ["- none\n"])
        (folder / "source.md").write_text("".join(lines), encoding="utf-8")
    parts = []
    for name in GUIDANCE_NAMES:
        body = blobs[name].decode("utf-8", "replace") if name in blobs else "absent"
        parts.append(f"=== {name} @ {commit} ===\n{body.rstrip()}\n")
    block = "\n".join(parts)
    if len(block) > GUIDANCE_BUDGET:
        raise Invalid(f"guidance text is {len(block)} chars, over the {GUIDANCE_BUDGET} hand-over budget")
    return block


def parse(argv):
    cli = argparse.ArgumentParser(prog="records.py", description="patching-bugs run records")
    sub = cli.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="validate every record and manifest in a run directory")
    c.add_argument("run_dir", type=Path)
    c.add_argument("--before-repair", action="store_true",
                   help="also require a gap-free repair_scope and a free attempt slot")
    m = sub.add_parser("manifest", help="hash a finished step directory into manifest.json")
    m.add_argument("step_dir", type=Path)
    g = sub.add_parser("guidance", help="copy or verify root guidance files from a commit")
    g.add_argument("run_dir", type=Path)
    g.add_argument("--repo", type=Path, required=True)
    g.add_argument("--commit", required=True)
    return cli.parse_args(argv)


def main(argv=None) -> int:
    args = parse(argv)
    try:
        if args.command == "check":
            check_run(args.run_dir, args.before_repair)
        elif args.command == "manifest":
            if not args.step_dir.is_dir() or args.step_dir.is_symlink():
                raise Invalid(f"{args.step_dir}: no such plain directory")
            refuse_misplaced_step(args.step_dir)
            write_manifest(args.step_dir)
        else:
            sys.stdout.write(guidance(args.run_dir, args.repo, args.commit))
    except Invalid as problem:
        print(f"records.py: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
