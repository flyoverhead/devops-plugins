#!/usr/bin/env python3
"""Seal a stage record with SHA-256 hashes of its package, or re-check an existing seal."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rhlib import Refusal, campaign, digest, expand_all, read_json, str_list, under, write_json  # noqa: E402

SEAL_SUFFIX = ".seal.json"


def seal_of(rel: str) -> str:
    return rel + SEAL_SUFFIX


def load_package(root: Path, rel: str):
    record = read_json(under(root, rel), "record")
    if not isinstance(record, dict):
        raise Refusal(f"{rel}: a record is a JSON object")
    for key in ("inputs", "artifacts"):
        if not str_list(record.get(key)):
            raise Refusal(f"{rel}: '{key}' must be a list of campaign-relative paths")
    for key in ("agent", "stage"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise Refusal(f"{rel}: '{key}' must be a non-empty string")
    inputs = expand_all(root, record["inputs"])
    artifacts = expand_all(root, record["artifacts"])
    own = {rel, seal_of(rel)}
    clash = own & (set(inputs) | set(artifacts))
    if clash:
        raise Refusal(f"{rel}: the record and its seal cannot be part of their own package ({sorted(clash)[0]})")
    return record, inputs, artifacts


def sealed_inputs(root: Path, record) -> dict:
    deps = {}
    for rel in record["inputs"]:
        target = under(root, rel)
        seal = root / seal_of(rel)
        if target.is_file() and seal.exists():
            deps[rel] = digest(under(root, seal_of(rel)))
    return deps


def compare(kind: str, want: dict, got: dict, rel: str):
    for path in sorted(set(want) | set(got)):
        if path not in got:
            raise Refusal(f"{rel}: {kind} file {path} is gone")
        if path not in want:
            raise Refusal(f"{rel}: {kind} file {path} appeared after sealing")
        if want[path] != got[path]:
            raise Refusal(f"{rel}: {kind} file {path} changed after sealing")


def verify(root: Path, rel: str, _chain=()):
    if rel in _chain:
        raise Refusal(f"dependency cycle: {' -> '.join(_chain + (rel,))}")
    seal_path = root / seal_of(rel)
    if not seal_path.exists():
        raise Refusal(f"{rel}: not sealed")
    seal = read_json(under(root, seal_of(rel)), "seal")
    if not isinstance(seal, dict) or set(seal) != {"record", "inputs", "artifacts", "dependencies"}:
        raise Refusal(f"{seal_of(rel)}: unexpected seal layout")
    if digest(under(root, rel)) != seal["record"]:
        raise Refusal(f"{rel}: record changed after sealing (stale seal)")
    record, inputs, artifacts = load_package(root, rel)
    compare("input", seal["inputs"], inputs, rel)
    compare("artifact", seal["artifacts"], artifacts, rel)
    deps = sealed_inputs(root, record)
    if deps != seal["dependencies"]:
        raise Refusal(f"{rel}: the seals of its sealed inputs changed")
    for dep in deps:
        verify(root, dep, _chain + (rel,))
    return record


def seal(root: Path, rel: str) -> str:
    if (root / seal_of(rel)).exists():
        verify(root, rel)
        return "verified"
    record, inputs, artifacts = load_package(root, rel)
    for dep in [r for r in record["inputs"] if under(root, r).is_file() and (root / seal_of(r)).exists()]:
        verify(root, dep, (rel,))
    write_json(root / seal_of(rel), {
        "record": digest(under(root, rel)),
        "inputs": inputs,
        "artifacts": artifacts,
        "dependencies": sealed_inputs(root, record),
    })
    return "sealed"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="evidence.py",
        description="seal: hash a record's inputs and artifacts into RECORD.seal.json (an existing "
                    "seal is verified instead). verify: re-hash and compare, following sealed inputs.")
    parser.add_argument("action", choices=["seal", "verify"])
    parser.add_argument("campaign", help="campaign directory")
    parser.add_argument("record", help="record path relative to the campaign")
    args = parser.parse_args(argv)
    try:
        root = campaign(args.campaign)
        word = seal(root, args.record) if args.action == "seal" else (verify(root, args.record) and "verified")
    except (Refusal, OSError) as exc:
        print(f"evidence.py {args.action} refused: {exc}", file=sys.stderr)
        return 1
    print(f"{word} {args.record}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
