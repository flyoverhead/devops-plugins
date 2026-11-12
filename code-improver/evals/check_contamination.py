#!/usr/bin/env python3
"""Flag eval runs whose agent saw the answer key (stdlib only).

Reads the JSON written by `claude plugin eval --json`, opens each run's trace
(file or directory, present on --keep-temp runs) and its judge explanations,
and looks for text that only the suite's own grading files contain.
"""
import argparse
import json
import sys
from pathlib import Path

BODY_MIN = 40
BODY_PHRASES = ("PASS only if",)


def load_args(argv):
    ap = argparse.ArgumentParser(
        prog="check_contamination.py",
        description="Exit 0 when no run leaked grading material, 1 when one did or "
                    "when the input holds nothing to check, 2 on bad usage.")
    ap.add_argument("result", type=Path, help="eval result JSON")
    ap.add_argument("--allow-listing", action="store_true",
                    help="do not count paths into the suite's evals/ directory")
    ap.add_argument("--suite", type=Path,
                    help="plugin root holding evals/ (default: suite.root from the result, "
                         "else the directory above this script)")
    args = ap.parse_args(argv)
    if not args.result.is_file():
        ap.error(f"no such file: {args.result}")
    return args


def suite_root(args, data):
    if args.suite:
        return args.suite.resolve()
    declared = (data.get("suite") or {}).get("root") if isinstance(data, dict) else None
    return Path(declared) if declared else Path(__file__).resolve().parent.parent


def grader_bodies(evals):
    for md in sorted(evals.glob("*/graders/*.md")):
        parts = md.read_text(errors="replace").split("---", 2)
        yield md.stem, (parts[2] if len(parts) == 3 else "")


def build_markers(root):
    evals = root / "evals"
    paths = [f"{root.as_posix()}/evals/"]
    paths += [f"evals/{case.name}/" for case in sorted(evals.iterdir())
              if case.is_dir() and (case / "case.yaml").exists()] if evals.is_dir() else []
    body, slugs = set(BODY_PHRASES), set()
    for stem, text in grader_bodies(evals) if evals.is_dir() else []:
        slugs.add(f"{stem}.md")
        body.update(line.strip() for line in text.splitlines() if len(line.strip()) >= BODY_MIN)
    return {"path": paths, "body": sorted(body), "slug": sorted(slugs)}


def iter_runs(data):
    cases = data.get("cases") if isinstance(data, dict) else None
    for case in cases if isinstance(cases, list) else []:
        name = case.get("name", "?")
        if isinstance(case.get("arms"), dict):
            for arm, runs in case["arms"].items():
                for n, run in enumerate(runs or [], 1):
                    yield f"{name}/{arm}#{n}", run
        for n, run in enumerate(case.get("runs") or [], 1):
            yield f"{name}#{n}", run


def read_trace(spec):
    if not spec:
        return None
    path = Path(spec)
    try:
        if path.is_file():
            return path.read_text(errors="replace")
        if path.is_dir():
            return "\n".join(p.read_text(errors="replace")
                             for p in sorted(path.rglob("*")) if p.is_file())
    except OSError:
        return None
    return None


def hits(text, markers):
    return [m for m in markers if m in text]


def scan(data, markers, allow_listing):
    agent_set = markers["body"] + markers["slug"] + ([] if allow_listing else markers["path"])
    judge_set = markers["slug"] + markers["path"]
    leaks, total, blind, readable = [], 0, 0, 0
    for label, run in iter_runs(data):
        total += 1
        trace = read_trace(run.get("tracePath"))
        judge = "\n".join(str(g.get("explanation") or "") for g in run.get("graders") or [])
        if trace is None:
            blind += 1
        else:
            found = hits(trace, agent_set)
            if found:
                leaks.append(f"LEAK {label} via agent log -> {' | '.join(found)}")
        if trace is not None or judge.strip():
            readable += 1
        if judge.strip():
            found = hits(judge, judge_set)
            if found:
                leaks.append(f"LEAK {label} via judge verdict -> {' | '.join(found)}")
    return leaks, total, blind, readable


def main(argv=None):
    args = load_args(sys.argv[1:] if argv is None else argv)
    try:
        data = json.loads(args.result.read_text())
    except (OSError, ValueError) as exc:
        print(f"unreadable result file: {exc}", file=sys.stderr)
        return 1
    root = suite_root(args, data)
    markers = build_markers(root)
    if not markers["slug"]:
        print(f"no grader files under {root}/evals/*/graders; nothing to compare against",
              file=sys.stderr)
        return 1
    leaks, total, blind, readable = scan(data, markers, args.allow_listing)
    if total == 0 or readable == 0:
        print("nothing to check: the result holds no runs with a trace or judge text",
              file=sys.stderr)
        return 1
    if blind:
        print(f"warning: {blind} of {total} run(s) had no readable trace; "
              "only judge text was checked for them", file=sys.stderr)
    if leaks:
        print("\n".join(leaks))
        return 1
    print(f"ok: {total} run(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
