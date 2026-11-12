#!/usr/bin/env python3
"""Execute the checks of one security fix against the commit before it and the commit after it.

Standard library only; Python 3.11 or newer, git 2.36 or newer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

OK_NOTHING, OK_FOUND, PARTIAL, BAD_INPUT = 0, 1, 10, 64

CHECK_KINDS = ("control", "exploit", "variant", "behavior", "regression", "security", "suite")
BLIND_KINDS = frozenset({"exploit", "variant"})
EVIDENCE_TIERS = ("source", "build", "runtime")
COMPARE_MODES = ("stdout", "stderr", "combined")
REACH_LINE = b"PPV_REACHED"
DEFAULT_TIMEOUT, LONGEST_TIMEOUT = 300, 3600
ARCHIVE_CAP = 16 << 20
STREAM_CAP = 16 << 20
SCRATCH_BYTES_CAP = 64 << 20
SCRATCH_FILES_CAP = 2000
OWNER_TAG = "ppv-owner"
RUN_DIR_PREFIX = "ppv-run-"

ID_SHAPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
COMMIT_SHAPE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
DIGEST_SHAPE = re.compile(r"[0-9a-f]{64}")
VAR_SHAPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SHELL_NAMES = frozenset("sh bash zsh dash ksh mksh ash fish csh tcsh".split())
SECRET_FRAGMENTS = ("TOKEN", "SECRET", "PASS", "CREDENTIAL", "AUTH", "COOKIE", "PRIVATE",
                    "SESSION", "APIKEY", "ACCESSKEY", "JWT", "DSN", "NETRC", "PRIVKEY", "KUBECONFIG",
                    "DOCKER_CONFIG", "AWS_PROFILE")
SECRET_WORDS = frozenset({"KEY", "KEYS", "PAT", "PWD"})
NOT_SECRET = frozenset({"GOPRIVATE", "GONOSUMDB", "GONOPROXY"})
USERINFO_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s@]+@")
LOADER_VARS = frozenset("""
    LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT NODE_OPTIONS NODE_PATH BASH_ENV ENV PYTHONSTARTUP
    PYTHONPATH PYTHONHOME PYTHONINSPECT PERL5OPT PERL5LIB RUBYOPT RUBYLIB JAVA_TOOL_OPTIONS
    _JAVA_OPTIONS JDK_JAVA_OPTIONS PROMPT_COMMAND SHELLOPTS BASHOPTS PS4 IFS CDPATH ZDOTDIR
    LESSOPEN""".split())
LOADER_PREFIXES = ("DYLD_", "GIT_", "LD_")
RUNNER_OWNED_VARS = frozenset("""PATH HOME USER LOGNAME TMPDIR TEMP TMP LANG LC_ALL TZ
    PYTHONHASHSEED NO_COLOR TERM""".split())

WHY_FOUND = {
    "exploit": "patched revision still trips the original safety assertion",
    "variant": "patched revision still trips an alternate path of the same root cause",
    "behavior": "benign behaviour on the patched revision no longer matches base",
    "regression": "targeted check passes on base and fails on the patched revision",
    "security": "neighbouring security check passes on base and fails on the patched revision",
    "suite": "suite fails on the patched revision while base passes it",
}

USAGE = """\
usage: post_patch_validation.py COMMAND [options]

commands
  scaffold       pin base and patched sides and write a plan without checks
                 --repo DIR --base-ref REF (--patched-ref REF | --patch-file FILE)
                 --finding-id ID --finding-summary TEXT
                 --evidence-level {source,build,runtime} [--case-id ID] --output PLAN
  validate-plan  check a plan's shape and its pins          --plan PLAN
  run            execute a validated plan                    --plan PLAN --output DIR
                                                             [--allow-env NAME ...]
  print-schema   emit the plan JSON Schema

exit status: 0 complete and clean, 1 complete with findings, 10 incomplete,
64 bad input (nothing executed).
"""


PROGRESS = {"executing": False}


class Rejected(Exception):
    """Input the runner will not act on; reported on stderr with exit 64."""


# ----------------------------------------------------------------- byte and file utilities

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_of(path: Path) -> str:
    acc = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(1 << 20):
            acc.update(chunk)
    return acc.hexdigest()


def as_json_bytes(obj) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def say(obj) -> None:
    sys.stdout.buffer.write(as_json_bytes(obj))
    sys.stdout.flush()


def create_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as stream:
        stream.write(data)


def is_within(child: Path, parent: Path) -> bool:
    return child.resolve().is_relative_to(parent.resolve())


def need_utf8(text: str, label: str) -> str:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise Rejected(f"{label}: bytes are not UTF-8")
    return text


def split_nul(raw: bytes) -> list[str]:
    return [item.decode("utf-8", "surrogateescape") for item in raw.split(b"\0") if item]


# ----------------------------------------------------------------- git access

class Git:
    """Every git call of the runner: hooks off, no pager, caller GIT_* variables dropped."""

    FLAGS = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "diff.external=",
             "-c", "core.pager=cat", "-c", "advice.detachedHead=false",
             "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=", "-c", "filter.lfs.required=false")

    @staticmethod
    def call(where, *args, extra_env=None, accept=(0,)) -> bytes:
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env |= {"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
        env |= extra_env or {}
        try:
            done = subprocess.run(["git", *Git.FLAGS, *args], cwd=where, env=env,
                                  stdin=subprocess.DEVNULL, capture_output=True)
        except OSError as exc:
            raise Rejected(f"git is not runnable here: {exc}")
        if done.returncode not in accept:
            tail = done.stderr.decode("utf-8", "replace").strip().splitlines()
            raise Rejected(f"`git {args[0]}` refused: {tail[-1] if tail else done.returncode}")
        return done.stdout

    @classmethod
    def toplevel(cls, where: Path) -> Path:
        if not where.is_dir():
            raise Rejected(f"repository not found: {where}")
        top = cls.call(where, "rev-parse", "--show-toplevel", accept=(0, 128)).decode().strip()
        if not top:
            raise Rejected(f"{where} is not inside a git work tree")
        return Path(top).resolve()

    @classmethod
    def commit(cls, repo: Path, ref: str) -> str:
        out = cls.call(repo, "rev-parse", "--verify", "--quiet", "--end-of-options",
                       ref + "^{commit}", accept=(0, 1, 128)).decode().strip()
        if not COMMIT_SHAPE.fullmatch(out):
            raise Rejected(f"{ref!r} names no commit in {repo}")
        return out

    @classmethod
    def change_between(cls, repo: Path, old: str, new: str) -> bytes:
        stable = ("-c", "diff.renames=false", "-c", "diff.noprefix=false",
                  "-c", "diff.mnemonicPrefix=false", "-c", "core.quotePath=true")
        return cls.call(repo, *stable, "diff", "--binary", "--full-index", "--no-color",
                        "--no-ext-diff", "--no-textconv", "--submodule=short",
                        "--src-prefix=a/", "--dst-prefix=b/", old, new, "--")

    @classmethod
    def paths_between(cls, repo: Path, old: str, new: str) -> list[str]:
        raw = cls.call(repo, "diff", "--no-renames", "--name-only", "-z", old, new, "--")
        return sorted(set(split_nul(raw)))

    @staticmethod
    def _gitlinks(listing: bytes, sha_column: int) -> dict[str, str]:
        found = {}
        for row in listing.split(b"\0"):
            if row[:7] == b"160000 ":
                meta, path = row.split(b"\t", 1)
                found[path.decode("utf-8", "surrogateescape")] = meta.split()[sha_column].decode()
        return found

    @classmethod
    def submodules_at(cls, repo: Path, commit: str) -> dict[str, str]:
        return cls._gitlinks(cls.call(repo, "ls-tree", "-r", "-z", "--full-tree", commit), 2)

    @classmethod
    def trial_apply(cls, repo: Path, base: str, patch: bytes) -> tuple[list[str], dict[str, str]]:
        """Apply a patch to a private index only; report touched paths and resulting gitlinks."""
        with tempfile.TemporaryDirectory(prefix="ppv-index-") as tmp:
            index = {"GIT_INDEX_FILE": os.path.join(tmp, "idx")}
            patch_path = os.path.join(tmp, "change.diff")
            Path(patch_path).write_bytes(patch)
            cls.call(repo, "read-tree", base, extra_env=index)
            try:
                cls.call(repo, "apply", "--cached", "--binary", patch_path, extra_env=index)
            except Rejected as exc:
                raise Rejected(f"the patch does not apply on {base[:12]} ({exc})")
            touched = cls.call(repo, "diff-index", "--cached", "--no-renames", "--name-only", "-z",
                               base, extra_env=index)
            links = cls._gitlinks(cls.call(repo, "ls-files", "-s", "-z", extra_env=index), 1)
        return sorted(set(split_nul(touched))), links


@dataclass
class Pinned:
    repo: Path
    base: str
    patched: str | None
    patch: bytes
    changed: list[str]
    submodules: dict[str, dict]


def pin(repo: Path, base: str, patched: str | None, patch: bytes | None) -> Pinned:
    if patched:
        patch = Git.change_between(repo, base, patched)
        changed = Git.paths_between(repo, base, patched)
        after = Git.submodules_at(repo, patched)
    else:
        changed, after = Git.trial_apply(repo, base, patch)
    if not (patch and changed):
        raise Rejected("base and patched sides are identical; there is nothing to validate")
    before = Git.submodules_at(repo, base)
    links = {path: {"base_commit": before.get(path), "patched_commit": after.get(path)}
             for path in sorted(before.keys() | after.keys())}
    return Pinned(repo, base, patched, patch, changed, links)


# ----------------------------------------------------------------- environment policy

def loader_variable(name: str) -> bool:
    return name in LOADER_VARS or name.startswith(LOADER_PREFIXES)


def secret_looking(name: str) -> bool:
    upper = name.upper()
    if upper in NOT_SECRET:
        return False
    if any(frag in upper for frag in SECRET_FRAGMENTS):
        return True
    return bool(SECRET_WORDS & set(upper.split("_")))


def env_name_trouble(name: str) -> str | None:
    if not VAR_SHAPE.fullmatch(name):
        return "is not a usable variable name"
    if name.startswith("PPV_"):
        return "is in the runner's own PPV_ namespace"
    if name in RUNNER_OWNED_VARS:
        return "is set by the runner itself"
    if loader_variable(name):
        return "can change which code gets loaded"
    if secret_looking(name):
        return "looks like it carries a credential"
    return None


def collect_forwarded(names: list[str]) -> dict[str, str]:
    picked = {}
    for name in names:
        need_utf8(name, "--allow-env")
        trouble = env_name_trouble(name)
        if trouble:
            raise Rejected(f"--allow-env {name} refused: it {trouble}")
        if name not in os.environ:
            raise Rejected(f"--allow-env {name}: the variable is not set for this run")
        if USERINFO_URL.search(os.environ[name]):
            raise Rejected(f"--allow-env {name} refused: its value embeds credentials in a URL")
        picked[name] = os.environ[name]
    return picked


def fixed_environment(forwarded: dict[str, str]) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ.get("HOME", "/")}
    env |= {k: os.environ[k] for k in ("USER", "LOGNAME") if k in os.environ}
    env |= {"LANG": "C", "LC_ALL": "C", "TZ": "UTC", "PYTHONHASHSEED": "0", "NO_COLOR": "1",
            "TERM": "dumb"}
    return env | forwarded


# ----------------------------------------------------------------- plan rules

def shell_hazard(argv: list[str]) -> str | None:
    """Return why argv smuggles a shell command line, or None.

    The whole argv is scanned, so wrappers such as env, timeout, nice, nohup, stdbuf, xargs or
    busybox in front of a shell do not hide it.
    """
    if re.search(r"\s", argv[0]):
        return "first argv element holds whitespace, so it is a command line, not a program"
    for pos, word in enumerate(argv):
        name = Path(word).name
        if name == "env":
            for flag in argv[pos + 1:]:
                if not flag.startswith("-"):
                    break
                if flag.startswith("--split-string") or (not flag.startswith("--") and "S" in flag):
                    return "env string splitting re-creates a shell command line"
        if name not in SHELL_NAMES:
            continue
        for flag in argv[pos + 1:]:
            if flag == "--" or not flag.startswith("-"):
                break
            if flag == "--command" or (not flag.startswith("--") and "c" in flag[1:]):
                return f"`{name} {flag}` evaluates a string; put the logic in a script under checks/"
    return None


def _text(v) -> bool:
    return isinstance(v, str) and bool(v)


def _texts(v, allow_empty=False) -> bool:
    return isinstance(v, list) and (allow_empty or bool(v)) and all(_text(x) for x in v)


def _ident(v) -> bool:
    return isinstance(v, str) and ID_SHAPE.fullmatch(v) is not None


def _commit(v) -> bool:
    return isinstance(v, str) and COMMIT_SHAPE.fullmatch(v) is not None


def _relative_inside(v) -> bool:
    return isinstance(v, str) and not v.startswith("/") and "\0" not in v \
        and ".." not in Path(v).parts


def _str_map(v) -> bool:
    return isinstance(v, dict) and all(isinstance(k, str) and isinstance(x, str)
                                       for k, x in v.items())


# key: (required, test, complaint)
PLAN_FIELDS = {
    "schema_version": (True, lambda v: v == "1.0", 'has to be the string "1.0"'),
    "case_id": (True, _ident, "needs 1-64 of A-Z a-z 0-9 . _ -, starting alphanumeric"),
    "evidence_level": (True, lambda v: v in EVIDENCE_TIERS, "is not source, build or runtime"),
    "finding": (True, lambda v: isinstance(v, dict) and v.keys() == {"id", "summary"}
                and _text(v["id"]) and _text(v["summary"]), "needs exactly a non-empty id and summary"),
    "repository": (True, _text, "is missing or empty"),
    "base_ref": (True, _text, "is missing or empty"),
    "expected_base_commit": (True, _commit, "is not a full commit id"),
    "patched_ref": (False, _text, "is empty"),
    "expected_patched_commit": (False, _commit, "is not a full commit id"),
    "patch_file": (False, _text, "is empty"),
    "expected_patch_sha256": (True, lambda v: isinstance(v, str) and DIGEST_SHAPE.fullmatch(v),
                              "is not 64 lowercase hex digits"),
    "changed_files": (True, _texts, "needs at least one path"),
    "submodules": (True, lambda v: _texts(v, allow_empty=True), "has to be a list of paths"),
    "checks": (True, lambda v: isinstance(v, list), "has to be a list"),
}

CHECK_FIELDS = {
    "id": (True, _ident, "needs 1-64 of A-Z a-z 0-9 . _ -, starting alphanumeric"),
    "kind": (True, lambda v: v in CHECK_KINDS, "is not one of " + "/".join(CHECK_KINDS)),
    "rationale": (True, _text, "is missing or empty"),
    "covers": (True, _texts, "needs at least one non-empty entry"),
    "argv": (True, lambda v: isinstance(v, list) and bool(v) and all(isinstance(a, str) for a in v)
             and bool(v[0]), "needs a non-empty list of strings"),
    "cwd": (False, _relative_inside, "has to stay inside the checkout (relative, no ..)"),
    "env": (False, _str_map, "has to map strings to strings"),
    "timeout_seconds": (False, lambda v: type(v) is int and 1 <= v <= LONGEST_TIMEOUT,
                        f"has to be a whole number of seconds, 1 to {LONGEST_TIMEOUT}"),
    "compare_stream": (False, lambda v: v in COMPARE_MODES, "is not stdout, stderr or combined"),
}


def apply_fields(obj, table: dict, label: str) -> list[str]:
    if not isinstance(obj, dict):
        return [f"{label} is not a JSON object"]
    notes = [f"{label}.{key} is not a known field" for key in sorted(obj.keys() - table.keys())]
    for key, (required, test, complaint) in table.items():
        if key not in obj:
            if required:
                notes.append(f"{label}.{key} is required")
        elif not test(obj[key]):
            notes.append(f"{label}.{key} {complaint}")
    return notes


def check_notes(chk, label: str) -> list[str]:
    notes = apply_fields(chk, CHECK_FIELDS, label)
    if not isinstance(chk, dict):
        return notes
    kind, argv, env = chk.get("kind"), chk.get("argv"), chk.get("env", {})
    if _str_map(env):
        for name in env:
            usable = VAR_SHAPE.fullmatch(name) and not name.startswith("PPV_")
            if not usable or loader_variable(name):
                notes.append(f"{label}.env.{name} is reserved or unsafe")
    if isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv) and argv[0]:
        hazard = shell_hazard(argv)
        if hazard:
            notes.append(f"{label}.argv: {hazard}")
    if (kind == "behavior") != ("compare_stream" in chk):
        notes.append(f"{label}: compare_stream belongs to behavior checks and only to them")
    if kind in BLIND_KINDS:
        texts = [*(argv if isinstance(argv, list) else []), str(chk.get("cwd", "")),
                 *(env.keys() if isinstance(env, dict) else []),
                 *(env.values() if isinstance(env, dict) else [])]
        if any("{side}" in str(t) or "PPV_SIDE" in str(t) for t in texts):
            notes.append(f"{label}: {kind} checks must not learn the side ({{side}}/PPV_SIDE)")
    return notes


def plan_errors(plan) -> list[str]:
    notes = apply_fields(plan, PLAN_FIELDS, "plan")
    if not isinstance(plan, dict):
        return notes
    ref_mode = "patched_ref" in plan or "expected_patched_commit" in plan
    if ref_mode == ("patch_file" in plan):
        notes.append("plan: choose patched_ref with expected_patched_commit, or patch_file, not both or neither")
    elif ref_mode and not {"patched_ref", "expected_patched_commit"} <= plan.keys():
        notes.append("plan: patched_ref and expected_patched_commit come as a pair")
    for key in ("changed_files", "submodules"):
        val = plan.get(key)
        if isinstance(val, list) and val != sorted(set(map(str, val))):
            notes.append(f"plan.{key} has to be sorted without duplicates")
    checks = plan.get("checks")
    if not isinstance(checks, list):
        return notes
    for pos, chk in enumerate(checks):
        notes += check_notes(chk, f"checks[{pos}]")
    ids = [c.get("id") for c in checks if isinstance(c, dict)]
    if all(isinstance(i, str) for i in ids) and ids != sorted(set(ids)):
        notes.append("plan.checks has to be ordered by id, each id once")
    absent = [k for k in CHECK_KINDS if k not in {c.get("kind") for c in checks if isinstance(c, dict)}]
    if absent:
        notes.append("plan.checks lacks kinds: " + ", ".join(absent))
    return notes


def kind_counts(checks) -> dict[str, int]:
    tally = dict.fromkeys(CHECK_KINDS, 0)
    for chk in checks:
        if isinstance(chk, dict) and chk.get("kind") in tally:
            tally[chk["kind"]] += 1
    return tally


def read_plan(path: Path) -> tuple[dict, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Rejected(f"plan {path} unreadable: {exc.strerror}")
    try:
        return json.loads(raw.decode("utf-8")), raw
    except UnicodeDecodeError:
        raise Rejected(f"plan {path} contains bytes that are not UTF-8")
    except json.JSONDecodeError as exc:
        raise Rejected(f"plan {path}: broken JSON near line {exc.lineno} ({exc.msg})")


def confirm_pins(plan: dict, plan_dir: Path) -> Pinned:
    repo = Git.toplevel(plan_dir / plan["repository"])
    base = Git.commit(repo, plan["base_ref"])
    if base != plan["expected_base_commit"]:
        raise Rejected(f"{plan['base_ref']} now points at {base[:12]}, the plan pinned "
                       f"{plan['expected_base_commit'][:12]}: the ref moved; start a new run")
    patched = patch = None
    if "patched_ref" in plan:
        patched = Git.commit(repo, plan["patched_ref"])
        if patched != plan["expected_patched_commit"]:
            raise Rejected(f"{plan['patched_ref']} now points at {patched[:12]}, the plan pinned "
                           f"{plan['expected_patched_commit'][:12]}: the ref moved; start a new run")
    else:
        try:
            patch = (plan_dir / plan["patch_file"]).read_bytes()
        except OSError as exc:
            raise Rejected(f"patch_file unreadable: {exc.strerror}")
    pinned = pin(repo, base, patched, patch)
    for what, now, then in (("patch digest", digest(pinned.patch), plan["expected_patch_sha256"]),
                            ("changed-file list", pinned.changed, plan["changed_files"]),
                            ("submodule list", sorted(pinned.submodules), plan["submodules"])):
        if now != then:
            raise Rejected(f"{what} differs from the pinned plan; scaffold a fresh run")
    return pinned


def plan_schema() -> dict:
    ident = {"type": "string", "pattern": "^" + ID_SHAPE.pattern + "$"}
    commit = {"type": "string", "pattern": "^" + COMMIT_SHAPE.pattern + "$"}
    paths = {"type": "array", "uniqueItems": True, "items": {"type": "string", "minLength": 1}}
    text = {"type": "string", "minLength": 1}
    check = {
        "type": "object", "additionalProperties": False,
        "required": ["id", "kind", "rationale", "covers", "argv"],
        "properties": {
            "id": ident, "kind": {"enum": list(CHECK_KINDS)}, "rationale": text,
            "covers": dict(paths, minItems=1),
            "argv": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "cwd": {"type": "string", "default": "."},
            "env": {"type": "object", "additionalProperties": {"type": "string"}},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": LONGEST_TIMEOUT,
                                "default": DEFAULT_TIMEOUT},
            "compare_stream": {"enum": list(COMPARE_MODES)},
        },
        "if": {"properties": {"kind": {"const": "behavior"}}},
        "then": {"required": ["compare_stream"]},
        "else": {"not": {"required": ["compare_stream"]}},
    }
    props = {
        "schema_version": {"const": "1.0"}, "case_id": ident,
        "evidence_level": {"enum": list(EVIDENCE_TIERS)},
        "finding": {"type": "object", "additionalProperties": False, "required": ["id", "summary"],
                    "properties": {"id": text, "summary": text}},
        "repository": text, "base_ref": text, "expected_base_commit": commit,
        "patched_ref": text, "expected_patched_commit": commit, "patch_file": text,
        "expected_patch_sha256": {"type": "string", "pattern": "^" + DIGEST_SHAPE.pattern + "$"},
        "changed_files": dict(paths, minItems=1), "submodules": paths,
        "checks": {"type": "array", "items": check},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "post-patch-validation plan", "type": "object", "additionalProperties": False,
        "required": [k for k, (req, _t, _c) in PLAN_FIELDS.items() if req], "properties": props,
        "oneOf": [
            {"required": ["patched_ref", "expected_patched_commit"], "not": {"required": ["patch_file"]}},
            {"required": ["patch_file"], "not": {"anyOf": [{"required": ["patched_ref"]},
                                                           {"required": ["expected_patched_commit"]}]}},
        ],
    }


# ----------------------------------------------------------------- checkouts

def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def worktree_entries(repo: Path) -> list[dict]:
    entries, current = [], {}
    for item in Git.call(repo, "worktree", "list", "--porcelain", "-z").split(b"\0") + [b""]:
        if item:
            key, _, val = item.decode("utf-8", "surrogateescape").partition(" ")
            current[key] = val
        elif current:
            entries.append(current)
            current = {}
    return entries


def reap_abandoned(repo: Path) -> list[str]:
    """Drop worktrees whose owner tag names a process on this host that no longer exists."""
    reaped, here = [], socket.gethostname()
    for entry in worktree_entries(repo):
        words = entry.get("locked", "").split()
        if not words or words[0] != OWNER_TAG:
            continue
        tag = dict(w.split("=", 1) for w in words[1:] if "=" in w)
        if tag.get("host") != here or not tag.get("pid", "").isdigit() or process_alive(int(tag["pid"])):
            continue
        holder, tree = Path(tag.get("dir", "")), Path(entry["worktree"])
        if not owned_location(holder, tree):
            continue
        Git.call(repo, "worktree", "unlock", str(tree), accept=(0, 128))
        Git.call(repo, "worktree", "remove", "--force", "--force", str(tree), accept=(0, 128))
        if holder.is_dir():
            shutil.rmtree(holder, ignore_errors=True)
        reaped.append(str(tree))
    return reaped


def owned_location(holder: Path, tree: Path) -> bool:
    """Only touch a leftover that sits in a runner-made directory under the system temp root."""
    if not holder.name.startswith(RUN_DIR_PREFIX) or not holder.is_absolute():
        return False
    temp_root = Path(tempfile.gettempdir()).resolve()
    holder_real = holder.resolve()
    return holder_real.is_relative_to(temp_root) and holder_real != temp_root \
        and tree.resolve().is_relative_to(holder_real)


def local_module_repo(repo: Path, sub: str) -> Path | None:
    gitdir = Path(Git.call(repo, "rev-parse", "--absolute-git-dir").decode().strip())
    for candidate in (gitdir / "modules" / sub, repo / sub):
        if (candidate / "HEAD").exists() or (candidate / ".git").exists():
            return candidate
    return None


def wipe(path: Path, problems: list) -> None:
    for top, dirs, _files in os.walk(path):
        for name in dirs:
            try:
                os.chmod(os.path.join(top, name), 0o700, follow_symlinks=False)
            except (OSError, NotImplementedError):
                pass

    def note(_fn, where, exc):
        problems.append(f"could not delete {where}: {exc[1] if isinstance(exc, tuple) else exc}")
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=note)
    else:
        shutil.rmtree(path, onerror=note)


@dataclass
class Checkouts:
    """Two worktrees under a private run directory, both with random names."""
    pinned: Pinned
    holder: Path | None = None
    sides: dict = field(default_factory=dict)
    cleanup_errors: list = field(default_factory=list)
    setup_gaps: list = field(default_factory=list)
    evidence_gaps: list = field(default_factory=list)
    owned: list = field(default_factory=list)

    def fresh_dir(self) -> Path:
        path = self.holder / secrets.token_hex(6)
        path.mkdir()
        return path

    def build(self) -> None:
        self.holder = Path(tempfile.mkdtemp(prefix=RUN_DIR_PREFIX)).resolve()
        tag = f"{OWNER_TAG} pid={os.getpid()} host={socket.gethostname()} dir={self.holder}"
        for side in random.SystemRandom().sample(["base", "patched"], 2):
            target = self.holder / secrets.token_hex(6)
            rev = self.pinned.patched if side == "patched" and self.pinned.patched else self.pinned.base
            Git.call(self.pinned.repo, "worktree", "add", "--quiet", "--detach", "--lock",
                     "--reason", tag, str(target), rev)
            self.owned.append(target)
            self.sides[side] = target
        if self.pinned.patched is None:
            self._apply_patch()
        for sub, revs in self.pinned.submodules.items():
            for side in ("base", "patched"):
                if revs[side + "_commit"]:
                    self._fill_submodule(side, sub, revs[side + "_commit"])

    def _apply_patch(self) -> None:
        tree = self.sides["patched"]
        carrier = self.holder / (secrets.token_hex(6) + ".diff")
        carrier.write_bytes(self.pinned.patch)
        try:
            Git.call(tree, "apply", "--index", "--binary", str(carrier))
        finally:
            carrier.unlink()
        landed = split_nul(Git.call(tree, "diff", "--cached", "--no-renames", "--name-only", "-z",
                                    self.pinned.base))
        if sorted(set(landed)) != self.pinned.changed:
            raise Rejected("applying the patch touched other files than the pinned list")

    def _fill_submodule(self, side: str, sub: str, rev: str) -> None:
        dest = self.sides[side] / sub
        try:
            source = local_module_repo(self.pinned.repo, sub)
            if source is None:
                raise Rejected("no local clone of it exists")
            Git.call(source, "cat-file", "-e", rev + "^{commit}")
            if dest.exists() and any(dest.iterdir()):
                raise Rejected("its directory is already populated")
            dest.mkdir(parents=True, exist_ok=True)
            Git.call(self.holder, "clone", "--quiet", "--no-checkout", "--no-hardlinks",
                     "--template=", str(source), str(dest))
            Git.call(dest, "checkout", "--quiet", "--detach", rev)
        except Rejected as exc:
            self.setup_gaps.append({"check_id": None,
                                    "reason": f"{side} side lacks submodule {sub} @ {rev[:12]}: {exc}"})

    def dispose(self) -> None:
        for tree in self.owned:
            try:
                Git.call(self.pinned.repo, "worktree", "unlock", str(tree), accept=(0, 128))
                Git.call(self.pinned.repo, "worktree", "remove", "--force", "--force", str(tree))
            except Rejected as exc:
                self.cleanup_errors.append(f"worktree {tree.name} stayed behind: {exc}")
        if self.holder and self.holder.exists():
            wipe(self.holder, self.cleanup_errors)


def mirrorable_files(plan_dir: Path, leave_out: list) -> list[Path]:
    skip = {p.resolve() for p in leave_out if p is not None}
    keep = []
    for top, dirs, files in os.walk(plan_dir):
        here = Path(top)
        for name in list(dirs):
            sub = here / name
            if sub.is_symlink():
                raise Rejected(f"symlinks are not accepted in the plan directory: {sub}")
            earlier_results = (sub / "result.json").exists() or (sub / "artifact-manifest.json").exists()
            if name == ".git" or earlier_results or sub.resolve() in skip:
                dirs.remove(name)
        for name in files:
            item = here / name
            if item.is_symlink():
                raise Rejected(f"symlinks are not accepted in the plan directory: {item}")
            if item.resolve() not in skip:
                keep.append(item.relative_to(plan_dir))
    return sorted(keep)


# ----------------------------------------------------------------- executing one side

@dataclass
class Invocation:
    """One check on one side: prepare private dirs, execute, keep the evidence."""
    check: dict
    side: str
    case_id: str
    checkouts: Checkouts
    plan_dir: Path
    plan_files: list
    env: dict
    results: Path
    number: int

    def _substitutions(self, tree: Path, mirror: Path, scratch: Path) -> dict:
        subs = {"{checkout}": str(tree), "{plan_dir}": str(mirror), "{scratch}": str(scratch)}
        if self.check["kind"] not in BLIND_KINDS:
            subs["{side}"] = self.side
        return subs

    @staticmethod
    def _fill(text: str, subs: dict) -> str:
        for token, value in subs.items():
            text = text.replace(token, value)
        return text

    def _mirror(self) -> Path:
        mirror = self.checkouts.fresh_dir()
        for rel in self.plan_files:
            (mirror / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.plan_dir / rel, mirror / rel, follow_symlinks=False)
        return mirror

    def _record(self) -> dict:
        kind, cid = self.check["kind"], self.check["id"]
        return {"side": self.side, "argv": list(self.check["argv"]), "argv0_sha256": None,
                "argv_files": [], "cwd": self.check.get("cwd", "."),
                "scratch": f"scratch/{cid}-{self.side}", "status": "execution_error",
                "exit_code": None,
                "expected": "nonzero" if kind in BLIND_KINDS and self.side == "base" else "zero",
                "matched": False, "marker": False if kind in BLIND_KINDS else None,
                "stdout": None, "stderr": None, "stdout_sha256": None, "stderr_sha256": None,
                "error": None, "truncated": False}

    def _note(self, reason: str) -> None:
        self.checkouts.evidence_gaps.append(
            {"check_id": self.check["id"], "reason": f"{self.side} evidence: {reason}"})

    def _save_scratch(self, scratch: Path, rec: dict) -> None:
        trouble = keep_scratch(scratch, self.results / rec["scratch"])
        if trouble:
            self._note(trouble)

    def _wait(self, child, out, err, rec) -> None:
        deadline = time.monotonic() + self.check.get("timeout_seconds", DEFAULT_TIMEOUT)
        while True:
            try:
                rec["exit_code"] = child.wait(timeout=0.1)
                rec["status"] = "completed"
                return
            except subprocess.TimeoutExpired:
                pass
            if max(os.fstat(out.fileno()).st_size, os.fstat(err.fileno()).st_size) > STREAM_CAP:
                rec["status"], rec["truncated"] = "execution_error", True
                rec["error"] = "a stream passed the 16 MiB cap; process group killed, output cut"
                return
            if time.monotonic() >= deadline:
                rec["status"], rec["error"] = "timeout", "ran past timeout_seconds; process group killed"
                return

    def execute(self) -> tuple[dict, dict]:
        rec, streams = self._record(), {}
        tree = self.checkouts.sides[self.side]
        scratch, mirror = self.checkouts.fresh_dir(), self._mirror()
        subs = self._substitutions(tree, mirror, scratch)
        argv = [self._fill(a, subs) for a in self.check["argv"]]
        env = dict(self.env)
        env.update({k: self._fill(v, subs) for k, v in self.check.get("env", {}).items()})
        env.update(TMPDIR=str(scratch), TEMP=str(scratch), TMP=str(scratch),
                   PPV_CHECKOUT=str(tree), PPV_PLAN_DIR=str(mirror), PPV_SCRATCH=str(scratch),
                   PPV_CASE_ID=self.case_id, PPV_REACHED_MARKER=REACH_LINE.decode())
        if self.check["kind"] not in BLIND_KINDS:
            env["PPV_SIDE"] = self.side
        workdir = tree / rec["cwd"]
        if not workdir.is_dir() or not is_within(workdir, tree):
            rec["error"] = f"working directory {rec['cwd']!r} is not a directory in the checkout"
            return rec, streams
        program = locate(argv[0], workdir, env["PATH"])
        if program:
            try:
                rec["argv0_sha256"] = digest_of(program)
            except OSError as exc:
                self._note(f"argv[0] could not be hashed ({exc.strerror or exc})")
        rec["argv_files"] = archive_arguments(self.check["argv"], argv, workdir, (mirror, tree),
                                              self.results, self._note)
        stem = f"{self.number:03d}-{self.check['id']}-{self.side}"
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                child = subprocess.Popen(argv, cwd=workdir, env=env, stdin=subprocess.DEVNULL,
                                         stdout=out, stderr=err, close_fds=True,
                                         start_new_session=True)
            except OSError as exc:
                rec["error"] = f"could not be started: {exc.strerror or exc}"
                self._save_scratch(scratch, rec)
                return rec, streams
            try:
                self._wait(child, out, err, rec)
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                child.wait()
            for label, stream in (("stdout", out), ("stderr", err)):
                stream.seek(0)
                streams[label] = stream.read(STREAM_CAP)
                if stream.read(1):
                    rec["truncated"] = True
                create_once(self.results / f"{stem}.{label}", streams[label])
                rec[label], rec[label + "_sha256"] = f"{stem}.{label}", digest(streams[label])
        self._save_scratch(scratch, rec)
        if self.check["kind"] in BLIND_KINDS:
            rec["marker"] = REACH_LINE in (ln.rstrip(b"\r") for ln in streams["stdout"].split(b"\n"))
        if rec["status"] == "completed":
            rec["matched"] = (rec["exit_code"] == 0) is (rec["expected"] == "zero")
        return rec, streams


def locate(program: str, workdir: Path, search_path: str) -> Path | None:
    if "/" not in program:
        hit = shutil.which(program, path=search_path)
        return Path(hit) if hit else None
    candidate = Path(program) if program.startswith("/") else workdir / program
    return candidate if candidate.is_file() else None


def archive_arguments(planned, actual, workdir: Path, roots, results: Path, note=None) -> list[dict]:
    listed = []
    for pos, (shown, used) in enumerate(zip(planned, actual)):
        if not used or (pos == 0 and "/" not in used):
            continue
        target = Path(used) if used.startswith("/") else workdir / used
        if not target.is_file():
            continue
        item = {"index": pos, "argument": shown, "sha256": None, "artifact": None,
                "archive_reason": None}
        listed.append(item)
        try:
            item["sha256"] = digest_of(target)
        except OSError as exc:
            item["archive_reason"] = f"could not be read ({exc.strerror})"
            continue
        if not any(is_within(target, r) for r in roots):
            item["archive_reason"] = "lives outside the plan copy and the checkout; digest only"
        elif target.stat().st_size > ARCHIVE_CAP:
            item["archive_reason"] = "over the 16 MiB archive cap; digest only"
        else:
            kept = results / "helpers" / item["sha256"]
            try:
                if not kept.exists():
                    kept.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(target, kept)
                item["artifact"] = "helpers/" + item["sha256"]
            except (OSError, shutil.Error) as exc:
                item["archive_reason"] = f"copy failed ({exc}); digest only"
                if note:
                    note(f"argv[{pos}] could not be archived")
    return listed


def keep_scratch(src: Path, dst: Path) -> str | None:
    """Copy what a check left in scratch, within the caps; return a problem description or None."""
    problems, files, size = [], 0, 0
    dst.mkdir(parents=True, exist_ok=True)
    for top, dirs, names in os.walk(src, onerror=lambda exc: problems.append(f"unreadable {exc.filename}")):
        rel = Path(top).relative_to(src)
        for name in dirs + names:
            here, there = Path(top) / name, dst / rel / name
            try:
                if here.is_symlink():
                    os.symlink(os.readlink(here), there)
                elif here.is_dir():
                    there.mkdir(exist_ok=True)
                    continue
                else:
                    size += here.lstat().st_size
                    if files + 1 > SCRATCH_FILES_CAP or size > SCRATCH_BYTES_CAP:
                        return (f"scratch over the archive cap ({SCRATCH_FILES_CAP} files / "
                                f"{SCRATCH_BYTES_CAP >> 20} MiB); archive is partial")
                    shutil.copyfile(here, there)
                files += 1
            except (OSError, shutil.Error) as exc:
                problems.append(f"{rel / name}: {getattr(exc, 'strerror', None) or exc}")
    return ("scratch archive incomplete: " + "; ".join(problems[:5])) if problems else None


# ----------------------------------------------------------------- judging

class Judge:
    """Turns recorded runs into findings and gaps."""

    def __init__(self):
        self.findings, self.gaps = [], []

    def gap(self, cid, reason):
        self.gaps.append({"check_id": cid, "reason": reason})

    def found(self, chk):
        self.findings.append({"check_id": chk["id"], "kind": chk["kind"],
                              "message": WHY_FOUND[chk["kind"]]})

    @staticmethod
    def required_sides(chk) -> list[str]:
        if chk["kind"] != "suite":
            return ["base", "patched"]
        pat = chk.get("runs", {}).get("patched")
        failed = bool(pat) and pat.get("status") == "completed" and not pat.get("matched")
        return ["patched", "base"] if failed else ["patched"]

    def one(self, chk) -> bool:
        """Judge a single check; return True when it is clean."""
        cid, runs = chk["id"], chk.get("runs", {})
        before = len(self.findings) + len(self.gaps)
        broken = [s for s in self.required_sides(chk)
                  if s not in runs or runs[s].get("status") != "completed" or runs[s].get("truncated")]
        for side in broken:
            state = runs[side].get("status") if side in runs else None
            if state is None:
                self.gap(cid, f"no {side} run on record")
            elif runs[side].get("truncated"):
                self.gap(cid, f"{side} output hit the 16 MiB cap and was cut")
            else:
                self.gap(cid, f"{side} run ended as {state}, not completed")
        if broken:
            return False
        rule = {"exploit": self._blind, "variant": self._blind, "suite": self._suite,
                "control": self._control, "behavior": self._behavior}.get(chk["kind"], self._plain)
        rule(chk, runs)
        return len(self.findings) + len(self.gaps) == before

    def _blind(self, chk, runs):
        unmarked = [s for s in ("base", "patched") if not runs[s].get("marker")]
        for side in unmarked:
            self.gap(chk["id"], f"marker_missing on {side}: no stdout line equal to PPV_REACHED")
        if unmarked:
            return
        if runs["base"].get("exit_code") == 0:
            self.gap(chk["id"], "no reproduction: the assertion already holds on base")
        elif not runs["patched"].get("matched"):
            self.found(chk)

    def _suite(self, chk, runs):
        if runs["patched"].get("matched"):
            return
        if runs["base"].get("exit_code") == 0:
            self.found(chk)
        else:
            self.gap(chk["id"], "unattributable: the suite fails on base as well; both logs kept")

    def _base_clean(self, chk, runs) -> bool:
        if runs["base"].get("exit_code") != 0:
            self.gap(chk["id"], "unattributable: the check already fails on base")
            return False
        return True

    def _control(self, chk, runs):
        if self._base_clean(chk, runs) and not runs["patched"].get("matched"):
            self.gap(chk["id"], "control broke on the patched side")

    def _behavior(self, chk, runs):
        if not self._base_clean(chk, runs):
            return
        cmp_ = chk.get("comparison")
        if not cmp_:
            self.gap(chk["id"], "behavior check has no stream comparison")
        elif not (runs["patched"].get("matched") and cmp_.get("matched")):
            self.found(chk)

    def _plain(self, chk, runs):
        if self._base_clean(chk, runs) and not runs["patched"].get("matched"):
            self.found(chk)


def judge(checks: list[dict], coverage: dict, cleanup_errors=(), setup_gaps=()) -> dict:
    jd = Judge()
    for kind in CHECK_KINDS:
        if not coverage.get(kind):
            jd.gap(None, f"no {kind} check in the plan")
    controls_clean = bool(coverage.get("control"))
    for chk in checks:
        clean = jd.one(chk)
        if chk["kind"] == "control" and not clean:
            controls_clean = False
    if not controls_clean:
        for item in jd.findings:
            jd.gap(item["check_id"], "held back because the control is not clean: " + item["message"])
        jd.findings = []
    jd.gaps += list(setup_gaps)
    for err in cleanup_errors:
        jd.gap(None, "cleanup: " + err)
    return {"status": "incomplete" if jd.gaps else "complete", "findings": jd.findings,
            "gaps": jd.gaps, "human_review_required": True}


def exit_status(assessment: dict) -> int:
    if assessment["status"] == "incomplete":
        return PARTIAL
    return OK_FOUND if assessment["findings"] else OK_NOTHING


# ----------------------------------------------------------------- report and manifest

def _describe(run) -> str:
    if not run:
        return "—"
    parts = [run["status"]]
    parts.append("rc " + str(run["exit_code"]) if run["exit_code"] is not None else "rc none")
    if run["marker"] is not None:
        parts.append("reached" if run["marker"] else "not reached")
    parts.append("ok" if run["matched"] else "wanted " + run["expected"])
    return " / ".join(parts)


def report_markdown(result: dict) -> str:
    verdict, facts = result["assessment"], result["inputs"]
    logs = {c["id"]: (c["runs"].get("patched") or {}).get("stdout") for c in result["checks"]}
    lines = [f"# {result['case_id']} — post-patch validation", "", "## Findings", ""]
    lines += [f"- {f['kind']} check `{f['check_id']}`: {f['message']} (patched log: `{logs.get(f['check_id'])}`)"
              for f in verdict["findings"]] or ["Nothing found by the supplied checks."]
    lines += ["", "## Validation gaps", ""]
    lines += [f"- {'`%s`' % g['check_id'] if g['check_id'] else 'whole run'}: {g['reason']}"
              for g in verdict["gaps"]] or ["No gaps."]
    subs = facts["submodules"]
    lines += ["", "## Evidence", "",
              f"Finding {result['finding']['id']}: {result['finding']['summary']}", "",
              "| Item | Value |", "|---|---|",
              f"| evidence level | {facts['evidence_level']} |",
              f"| base commit | `{facts['base_commit']}` |",
              f"| patched | `{facts['patched_commit']}` |" if facts["patched_commit"]
              else "| patched | base + `patch.diff` |",
              f"| patch sha256 | `{facts['patch_sha256']}` |",
              f"| plan sha256 | `{facts['plan_sha256']}` |",
              "| submodules | " + ("; ".join(f"`{p}` {v['base_commit'] or 'absent'} to {v['patched_commit'] or 'absent'}"
                                          for p, v in subs.items()) or "none") + " |",
              "| forwarded env | " + ("; ".join(f"`{k}={v}`" for k, v in facts["forwarded_env"].items())
                                     or "none") + " |",
              "", "| Check | Kind | Base | Patched | Streams |", "|---|---|---|---|---|"]
    for c in result["checks"]:
        cmp_ = c.get("comparison")
        same = "—" if not cmp_ else f"{cmp_['stream']}: {'same' if cmp_['matched'] else 'different'}"
        lines.append(f"| `{c['id']}` | {c['kind']} | {_describe(c['runs'].get('base'))} | "
                     f"{_describe(c['runs'].get('patched'))} | {same} |")
    lines += ["", "## Next steps", ""]
    level = facts["evidence_level"]
    if verdict["findings"]:
        lines.append("- Repair the patch; validate the revision as a new pinned run.")
    if verdict["gaps"]:
        lines.append("- Resolve the gaps before reading a clean result as meaningful.")
    if verdict["findings"] or verdict["gaps"]:
        lines.append(f"- Evidence level here: `{level}`. A person reviews the change before merge regardless.")
    else:
        lines.append(f"- All supplied checks passed at evidence level `{level}`; that says nothing about "
                     "checks nobody wrote, and human review is still required before merge.")
    return "\n".join(lines) + "\n"


def manifest(results: Path) -> None:
    """List every file; symlinks (kept from scratch) appear with null digest and size."""
    entries = []
    for p in sorted(results.rglob("*")):
        rel = p.relative_to(results).as_posix()
        if rel == "artifact-manifest.json":
            continue
        if p.is_symlink():
            entries.append({"path": rel, "sha256": None, "bytes": None})
        elif p.is_file():
            entries.append({"path": rel, "sha256": digest_of(p), "bytes": p.stat().st_size})
    if not entries:
        raise Rejected("refusing an artifact manifest with no files in it")
    create_once(results / "artifact-manifest.json", as_json_bytes({"schema_version": "1.0", "files": entries}))


# ----------------------------------------------------------------- commands

def do_scaffold(opts) -> int:
    target = Path(opts.output).absolute()
    if target.exists():
        raise Rejected(f"{target} exists; plans are never overwritten")
    for flag in ("finding_id", "finding_summary", "base_ref", "case_id", "patched_ref"):
        if getattr(opts, flag):
            need_utf8(getattr(opts, flag), "--" + flag.replace("_", "-"))
    if not (opts.finding_id.strip() and opts.finding_summary.strip()):
        raise Rejected("a finding needs both an id and a summary")
    repo = Git.toplevel(Path(opts.repo).absolute())
    if is_within(target.parent, repo):
        raise Rejected("keep the plan outside the repository work tree")
    base = Git.commit(repo, opts.base_ref)
    patched = Git.commit(repo, opts.patched_ref) if opts.patched_ref else None
    patch = None
    if not patched:
        try:
            patch = Path(opts.patch_file).read_bytes()
        except OSError as exc:
            raise Rejected(f"--patch-file unreadable: {exc.strerror}")
        if not patch.strip():
            raise Rejected("--patch-file holds no change")
    pinned = pin(repo, base, patched, patch)
    case_id = opts.case_id or derive_case_id(opts.finding_id)
    if not ID_SHAPE.fullmatch(case_id):
        raise Rejected("--case-id needs 1-64 of A-Z a-z 0-9 . _ -, starting alphanumeric")
    plan = {"schema_version": "1.0", "case_id": case_id, "evidence_level": opts.evidence_level,
            "finding": {"id": opts.finding_id, "summary": opts.finding_summary},
            "repository": os.path.relpath(repo, target.parent), "base_ref": opts.base_ref,
            "expected_base_commit": base}
    if patched:
        plan |= {"patched_ref": opts.patched_ref, "expected_patched_commit": patched}
    else:
        plan["patch_file"] = os.path.relpath(Path(opts.patch_file).absolute(), target.parent)
    plan |= {"expected_patch_sha256": digest(pinned.patch), "changed_files": pinned.changed,
             "submodules": sorted(pinned.submodules), "checks": []}
    create_once(target, as_json_bytes(plan))
    say({"plan": str(target), "base_commit": base, "patched_commit": patched,
         "patch_sha256": plan["expected_patch_sha256"], "changed_files": pinned.changed,
         "evidence_level": opts.evidence_level, "submodules": plan["submodules"],
         "next": "write checks covering all seven kinds (helpers in checks/), then run validate-plan"})
    return OK_NOTHING


def derive_case_id(finding_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", finding_id).strip("-._")[:64] or "case"
    return slug if slug[0].isalnum() else ("c" + slug)[:64]


def do_validate(opts) -> int:
    path = Path(opts.plan).absolute()
    plan, _raw = read_plan(path)
    notes = plan_errors(plan)
    if notes:
        say({"valid": False, "errors": notes})
        raise Rejected(f"{len(notes)} plan problem(s); first: {notes[0]}")
    pinned = confirm_pins(plan, path.parent)
    say({"valid": True, "case_id": plan["case_id"], "evidence_level": plan["evidence_level"],
         "submodules": sorted(pinned.submodules), "checks": [c["id"] for c in plan["checks"]],
         "coverage": kind_counts(plan["checks"])})
    return OK_NOTHING


def output_target(raw: str, repo: Path) -> Path:
    target = Path(raw).absolute()
    if target.is_symlink():
        raise Rejected(f"{target} is a symlink; give a real directory")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise Rejected(f"{target} already has content; evidence is never overwritten")
    if is_within(target, repo):
        raise Rejected("results must live outside the repository work tree")
    return target


def run_check(chk, checkouts, shared, counter, results) -> dict:
    entry = {"id": chk["id"], "kind": chk["kind"], "rationale": chk["rationale"],
             "covers": chk["covers"], "runs": {}}
    if not checkouts.sides:
        return entry
    streams = {}

    def once(side):
        counter[0] += 1
        rec, out = Invocation(chk, side, number=counter[0], checkouts=checkouts,
                              results=results, **shared).execute()
        entry["runs"][side], streams[side] = rec, out

    order = ["patched"] if chk["kind"] == "suite" else random.SystemRandom().sample(["base", "patched"], 2)
    for side in order:
        once(side)
    pat = entry["runs"]["patched"]
    if chk["kind"] == "suite" and pat["status"] == "completed" and not pat["matched"]:
        once("base")
    if chk["kind"] == "behavior" and all(r["status"] == "completed" for r in entry["runs"].values()):
        mode = chk["compare_stream"]
        pick = {s: (o["stdout"] + o["stderr"]) if mode == "combined" else o[mode]
                for s, o in streams.items()}
        entry["comparison"] = {"stream": mode, "matched": pick["base"] == pick["patched"],
                               "base_sha256": digest(pick["base"]),
                               "patched_sha256": digest(pick["patched"])}
    entry["runs"] = {s: entry["runs"][s] for s in ("base", "patched") if s in entry["runs"]}
    return entry


def do_run(opts) -> int:
    plan_path = Path(opts.plan).absolute()
    plan, raw = read_plan(plan_path)
    notes = plan_errors(plan)
    if notes:
        raise Rejected(f"{len(notes)} plan problem(s); first: {notes[0]}")
    forwarded = collect_forwarded(opts.allow_env)
    plan_dir = plan_path.parent
    pinned = confirm_pins(plan, plan_dir)
    results = output_target(opts.output, pinned.repo)
    patch_path = plan_dir / plan["patch_file"] if "patch_file" in plan else None
    files = mirrorable_files(plan_dir, [plan_path, patch_path, results])
    results.mkdir(parents=True, exist_ok=True)
    results = results.resolve()
    PROGRESS["executing"] = True
    reap_abandoned(pinned.repo)
    create_once(results / "patch.diff", pinned.patch)
    create_once(results / "plan.snapshot.json", raw)
    checkouts = Checkouts(pinned)
    shared = {"case_id": plan["case_id"], "plan_dir": plan_dir, "plan_files": files,
              "env": fixed_environment(forwarded)}
    counter, entries = [0], []
    try:
        try:
            checkouts.build()
        except Rejected as exc:
            checkouts.setup_gaps.append({"check_id": None, "reason": f"checkouts could not be prepared: {exc}"})
            checkouts.sides = {}
        for chk in plan["checks"]:
            entries.append(run_check(chk, checkouts, shared, counter, results))
    finally:
        checkouts.dispose()
    coverage = kind_counts(plan["checks"])
    assessment = judge(entries, coverage, checkouts.cleanup_errors,
                       checkouts.setup_gaps + checkouts.evidence_gaps)
    result = {
        "schema_version": "2.0", "case_id": plan["case_id"], "finding": plan["finding"],
        "inputs": {"base_commit": pinned.base, "patched_commit": pinned.patched,
                   "patch_sha256": digest(pinned.patch), "changed_files": pinned.changed,
                   "evidence_level": plan["evidence_level"], "submodules": pinned.submodules,
                   "plan_sha256": digest(raw), "forwarded_env": forwarded},
        "coverage": coverage, "checks": entries, "cleanup_errors": checkouts.cleanup_errors,
        "assessment": assessment,
    }
    create_once(results / "result.json", as_json_bytes(result))
    create_once(results / "report.md", report_markdown(result).encode("utf-8"))
    manifest(results)
    say({"result": str(results / "result.json"), "assessment": assessment})
    return exit_status(assessment)


def do_schema(_opts) -> int:
    say(plan_schema())
    return OK_NOTHING


# ----------------------------------------------------------------- argument parsing

class _Strict(argparse.ArgumentParser):
    def error(self, message):
        raise Rejected(f"bad arguments: {message}; try --help")


COMMANDS = {
    "scaffold": (do_scaffold, [
        ("--repo", {"required": True}), ("--base-ref", {"required": True}),
        ("--finding-id", {"required": True}), ("--finding-summary", {"required": True}),
        ("--evidence-level", {"required": True, "choices": EVIDENCE_TIERS}),
        ("--case-id", {}), ("--output", {"required": True})]),
    "validate-plan": (do_validate, [("--plan", {"required": True})]),
    "run": (do_run, [("--plan", {"required": True}), ("--output", {"required": True}),
                     ("--allow-env", {"action": "append", "default": []})]),
    "print-schema": (do_schema, []),
}


def build_parser() -> argparse.ArgumentParser:
    top = _Strict(prog="post_patch_validation.py", add_help=False)
    branches = top.add_subparsers(dest="command", parser_class=_Strict)
    for name, (_handler, options) in COMMANDS.items():
        sub = branches.add_parser(name, add_help=False)
        for flag, spec in options:
            sub.add_argument(flag, **spec)
        if name == "scaffold":
            either = sub.add_mutually_exclusive_group(required=True)
            either.add_argument("--patched-ref")
            either.add_argument("--patch-file")
    return top


def main(argv=None) -> int:
    words = sys.argv[1:] if argv is None else list(argv)
    if not words:
        sys.stderr.write(USAGE)
        return BAD_INPUT
    if words[0] in ("-h", "--help") or words[1:2] in (["-h"], ["--help"]):
        sys.stdout.write(USAGE)
        return OK_NOTHING
    try:
        opts = build_parser().parse_args(words)
        return COMMANDS[opts.command][0](opts)
    except Rejected as exc:
        if PROGRESS["executing"]:
            sys.stderr.write(f"post-patch-validation: stopped after execution began: {exc}\n")
            return PARTIAL
        sys.stderr.write(f"post-patch-validation: {exc}\n")
        return BAD_INPUT
    except Exception as exc:
        stage = "after execution began" if PROGRESS["executing"] else "before anything ran"
        sys.stderr.write(f"post-patch-validation: unexpected {type(exc).__name__} {stage}: {exc}\n")
        return PARTIAL if PROGRESS["executing"] else BAD_INPUT


if __name__ == "__main__":
    sys.exit(main())
