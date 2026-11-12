"""Field-level checks for the stage records, shared by registry.py and report.py."""
from pathlib import Path

from rhlib import HEX40, OBJECT_ID, Refusal, digest, expand, expand_all, inside, nonempty, read_json, str_list, under

STAGES = ("prepare", "hunt", "reproduce", "replay", "adjudicate", "report")
CANDIDATE_STAGES = ("reproduce", "replay", "adjudicate")
OUTCOMES = ("REPRODUCED_REGRESSION", "INCOMPLETE_FIX", "LATENT_BUG", "PREEXISTING_BUG", "REJECTED", "UNRESOLVED")
CATEGORIES = ("VULNERABILITY", "FUNCTIONAL_BUG", "PERFORMANCE", "BUILD_TEST")
SEVERITIES = ("Low", "Medium", "High", "Critical")
LIKELIHOODS = ("Low", "Medium", "High")
CONCLUSIONS = ("SUPPORTED", "REFUTED", "UNKNOWN", "NOT_APPLICABLE")
CHECK_WANT = {
    "supported_behavior": "SUPPORTED",
    "reachability": "SUPPORTED",
    "introduced_defect": "SUPPORTED",
    "incomplete_fix": "REFUTED",
    "latent_bug": "REFUTED",
    "preexisting_bug": "REFUTED",
    "intentional_change": "REFUTED",
    "unsupported_expectation": "REFUTED",
    "security_scope": None,
}
CANDIDATE_TEXT = ("title", "patch_intent", "prior_behavior", "changed_code", "reachable_trigger",
                  "possible_defect", "false_positive_checks", "proof_needed")
BEHAVIORS = ("correct", "failure", "unknown")


def text_or_list(value) -> bool:
    return (isinstance(value, str) and bool(value.strip())) or (str_list(value) and bool(value))


def common(rec: dict, attempt: dict, record_rel: str) -> list:
    bad = []
    want = {"stage": attempt["stage"], "agent": attempt["agent"], "attempt": attempt["id"],
            "change": attempt["change"]}
    for key, value in want.items():
        if rec.get(key) != value:
            bad.append(f"'{key}' is {rec.get(key)!r}, the assignment says {value!r}")
    if rec.get("status") not in ("complete", "blocked"):
        bad.append("'status' must be complete or blocked")
    if not isinstance(rec.get("summary"), str) or not rec["summary"].strip():
        bad.append("'summary' must be a non-empty string")
    if not nonempty(rec.get("security_review")):
        bad.append("'security_review' is empty")
    if sorted(rec.get("inputs") or []) != sorted(attempt["inputs"]):
        bad.append("'inputs' differ from the inputs reserved for this attempt")
    for rel in rec.get("artifacts") or []:
        if not inside(rel, attempt["directory"]):
            bad.append(f"artifact {rel} lies outside {attempt['directory']}")
    if not inside(record_rel, attempt["directory"]):
        bad.append(f"record {record_rel} lies outside {attempt['directory']}")
    return bad


def source(root: Path, rel) -> dict:
    data = read_json(under(root, rel), "source.json")
    if not isinstance(data, dict) or not isinstance(data.get("repository"), str) or not data["repository"]:
        raise Refusal(f"{rel}: 'repository' missing")
    for key in ("s0", "s1"):
        if not isinstance(data.get(key), str) or not HEX40.match(data[key]):
            raise Refusal(f"{rel}: '{key}' must be a full 40-hex commit")
    for key in ("tree0", "tree1"):
        if not isinstance(data.get(key), str) or not OBJECT_ID.match(data[key]):
            raise Refusal(f"{rel}: '{key}' must be a tree id")
    if data["s0"] == data["s1"]:
        raise Refusal(f"{rel}: s0 and s1 are the same commit")
    return data


def fingerprint(root: Path, rel: str):
    path = under(root, rel)
    if path.is_file():
        return digest(path)
    return {k[len(rel) + 1:]: v for k, v in expand(root, rel).items()}


def experiment(root: Path, rec: dict, attempt: dict) -> list:
    bad = []
    if rec.get("candidate") != attempt["candidate"]:
        bad.append(f"'candidate' is {rec.get('candidate')!r}, the assignment says {attempt['candidate']!r}")
    runs = rec.get("runs", [])
    if not isinstance(runs, list):
        return bad + ["'runs' must be a list"]
    if rec.get("status") != "complete":
        return bad
    try:
        src = source(root, rec.get("source"))
    except Refusal as exc:
        return bad + [str(exc)]
    for key in ("setup", "poc", "workload"):
        try:
            under(root, rec.get(key))
        except Refusal as exc:
            bad.append(f"'{key}': {exc}")
    if [r.get("state") if isinstance(r, dict) else None for r in runs] != ["S0", "S1"]:
        return bad + ["'runs' must hold exactly two runs, S0 first, then S1"]
    for run, rev in zip(runs, (src["s0"], src["s1"])):
        tag = run["state"]
        if run.get("revision") != rev:
            bad.append(f"{tag} revision {run.get('revision')!r} is not source.json's {rev}")
        for key in ("deployment", "command"):
            if not isinstance(run.get(key), str) or not run[key].strip():
                bad.append(f"{tag} '{key}' must be a non-empty string")
        if run.get("behavior") not in BEHAVIORS:
            bad.append(f"{tag} 'behavior' must be one of {', '.join(BEHAVIORS)}")
        try:
            if under(root, run.get("log")).stat().st_size == 0:
                bad.append(f"{tag} log {run['log']} is empty")
        except Refusal as exc:
            bad.append(f"{tag} log: {exc}")
    if not bad and fingerprint(root, runs[0]["log"]) == fingerprint(root, runs[1]["log"]):
        bad.append("the S0 and S1 logs are identical")
    dirs = rec.get("build_dirs")
    if not str_list(dirs) or not dirs:
        bad.append("'build_dirs' must list the build directories of a complete run")
    else:
        for rel in dirs:
            if not inside(rel, attempt["directory"]):
                bad.append(f"build dir {rel} lies outside {attempt['directory']}")
    return bad


def replay_vs_reproduction(root: Path, replay: dict, repro: dict) -> list:
    bad = []
    for key in ("poc", "workload"):
        try:
            if fingerprint(root, replay[key]) != fingerprint(root, repro[key]):
                bad.append(f"replay '{key}' differs from the reproduction's")
        except (Refusal, KeyError) as exc:
            bad.append(f"cannot compare '{key}': {exc}")
    if replay.get("source") != repro.get("source"):
        bad.append("replay and reproduction use different source.json files")
    logs = {r.get("log") for r in replay.get("runs") or [] if isinstance(r, dict)}
    if logs & {r.get("log") for r in repro.get("runs") or [] if isinstance(r, dict)}:
        bad.append("replay reuses the reproduction's log paths")
    return bad


def package_files(root: Path, rec: dict, _seen=None) -> set:
    """Files a record may cite: its own inputs and artifacts, plus the packages of its sealed inputs."""
    seen = set() if _seen is None else _seen
    files = set(expand_all(root, rec.get("inputs") or [])) | set(expand_all(root, rec.get("artifacts") or []))
    for rel in rec.get("inputs") or []:
        seal = root / (rel + ".seal.json")
        if rel in seen or not seal.is_file():
            continue
        seen.add(rel)
        sealed = read_json(seal, "seal")
        files |= set(sealed.get("inputs", {})) | set(sealed.get("artifacts", {}))
        files |= package_files(root, read_json(root / rel, "record"), seen)
    return files


def in_package(rel: str, files: set) -> bool:
    return rel in files or any(f.startswith(rel.rstrip("/") + "/") for f in files)


def decision(root: Path, rec: dict, attempt: dict) -> list:
    bad = []
    if rec.get("candidate") != attempt["candidate"]:
        bad.append(f"'candidate' is {rec.get('candidate')!r}, the assignment says {attempt['candidate']!r}")
    if rec.get("outcome") not in OUTCOMES:
        bad.append(f"'outcome' must be one of {', '.join(OUTCOMES)}")
    if not isinstance(rec.get("reason"), str) or not rec["reason"].strip():
        bad.append("'reason' must be a non-empty string")
    evidence = rec.get("evidence")
    if not str_list(evidence) or not evidence:
        bad.append("'evidence' must be a non-empty list of paths")
    else:
        files = package_files(root, rec)
        bad += [f"evidence {e} is not inside the decision's package" for e in evidence if not in_package(e, files)]
    if "duplicate_of" in rec and rec["duplicate_of"] is not None and not isinstance(rec["duplicate_of"], str):
        bad.append("'duplicate_of' must be a candidate id")
    return bad


def candidate_file(rec: dict, cid: str, key: str, change: str) -> list:
    bad = []
    if rec.get("id") != cid:
        bad.append(f"candidate file id {rec.get('id')!r} is not {cid}")
    if rec.get("key") != key:
        bad.append(f"candidate {cid}: key differs from the registered one")
    if rec.get("change") != change:
        bad.append(f"candidate {cid}: change {rec.get('change')!r} is not {change}")
    bad += [f"candidate {cid}: '{f}' missing or empty" for f in CANDIDATE_TEXT if not text_or_list(rec.get(f))]
    return bad
