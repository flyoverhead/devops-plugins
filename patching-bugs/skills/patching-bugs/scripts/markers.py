#!/usr/bin/env python3
"""Marker lines a PoC or case harness prints, and a reader that judges a captured stdout.

    markers.py loaded --artifact <relative-file> --root <dir>
    markers.py case --input <json> --actual <json>
    markers.py reached
    markers.py check-stdout <file> [--runtime-identity <path> <sha256>] [--input <json>]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

LOADED, CASE, REACHED = "PATCH_LOADED", "PATCH_CASE", "PATCH_REACHED"


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def same_json(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def loaded_line(root: Path, artifact: str) -> str:
    base = root.resolve()
    target = (root / artifact).resolve()
    if base not in target.parents:
        raise LookupError(f"{artifact} resolves outside {base}")
    if not target.is_file():
        raise LookupError(f"{target} is not a file")
    return f"{LOADED} " + compact({"path": str(target),
                                   "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})


def tagged(lines, tag):
    """Payloads of every line that starts with `tag` followed by a space or nothing."""
    found = []
    for line in lines:
        if line == tag or line.startswith(tag + " "):
            found.append(line[len(tag):].strip())
    return found


def observe(stdout: str, planned_input=None, identity=None) -> tuple:
    """Return (problem or None, the PATCH_CASE payload or None) for one captured stdout."""
    lines = stdout.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    cases = tagged(lines, CASE)
    if len(cases) != 1:
        return f"expected one {CASE} line, saw {len(cases)}", None
    try:
        payload = json.loads(cases[0])
    except json.JSONDecodeError:
        return f"{CASE} payload is not JSON", None
    if not isinstance(payload, dict) or set(payload) != {"input", "actual"}:
        return f"{CASE} must carry exactly the keys input and actual", None
    if planned_input is not None and not same_json(payload["input"], planned_input):
        return f"{CASE} input {compact(payload['input'])} is not the planned input", payload
    if lines.count(REACHED) != 1 or len(tagged(lines, REACHED)) != 1:
        return f"{REACHED} must appear exactly once", payload
    if lines[-1] != REACHED:
        return f"{REACHED} is not the last stdout line", payload
    if identity is not None:
        want_path, want_hash = identity
        seen = tagged(lines, LOADED)
        if len(seen) != 1:
            return f"expected one {LOADED} line, saw {len(seen)}", payload
        try:
            got = json.loads(seen[0])
        except json.JSONDecodeError:
            return f"{LOADED} payload is not JSON", payload
        if not isinstance(got, dict) or set(got) != {"path", "sha256"}:
            return f"{LOADED} must carry exactly path and sha256", payload
        if Path(str(got["path"])).resolve() != Path(want_path).resolve():
            return f"{LOADED} path {got['path']} is not {want_path}", payload
        if got["sha256"] != want_hash:
            return f"{LOADED} hash differs from the expected artifact bytes", payload
    return None, payload


def as_json(raw: str, flag: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"markers.py: {flag} is not valid JSON: {raw!r}", file=sys.stderr)
        sys.exit(2)


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(prog="markers.py")
    sub = cli.add_subparsers(dest="command", required=True)
    lo = sub.add_parser("loaded")
    lo.add_argument("--artifact", required=True)
    lo.add_argument("--root", required=True, type=Path)
    ca = sub.add_parser("case")
    ca.add_argument("--input", required=True)
    ca.add_argument("--actual", required=True)
    sub.add_parser("reached")
    ch = sub.add_parser("check-stdout")
    ch.add_argument("file", type=Path)
    ch.add_argument("--runtime-identity", nargs=2, metavar=("PATH", "SHA256"))
    ch.add_argument("--input")
    args = cli.parse_args(argv)

    if args.command == "loaded":
        try:
            print(loaded_line(args.root, args.artifact), flush=True)
        except LookupError as why:
            print(f"markers.py: {why}", file=sys.stderr)
            return 1
    elif args.command == "case":
        payload = {"input": as_json(args.input, "--input"), "actual": as_json(args.actual, "--actual")}
        print(f"{CASE} {compact(payload)}", flush=True)
    elif args.command == "reached":
        print(REACHED, flush=True)
    else:
        planned = as_json(args.input, "--input") if args.input is not None else None
        try:
            captured = args.file.read_text(encoding="utf-8", errors="replace")
        except OSError as why:
            print(f"cannot read {args.file}: {why}")
            return 1
        problem, _ = observe(captured, planned, args.runtime_identity)
        if problem:
            print(problem)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
