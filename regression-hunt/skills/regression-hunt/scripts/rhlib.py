"""Pieces shared by the regression-hunt scripts: campaign paths, hashing, JSON files, locking."""
import contextlib
import datetime as _dt
import fcntl
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

HEX40 = re.compile(r"^[0-9a-f]{40}$")
OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Refusal(Exception):
    """A check failed; the message says which one."""


def campaign(arg) -> Path:
    path = Path(arg).expanduser()
    if not path.is_dir():
        raise Refusal(f"no campaign directory at {arg}")
    return path.resolve()


def under(root: Path, rel, *, exist=True) -> Path:
    """Map a campaign-relative path to a real one, refusing anything that could leave the campaign."""
    if not isinstance(rel, str) or not rel:
        raise Refusal(f"bad path {rel!r}: want a non-empty campaign-relative string")
    if rel.startswith("/") or rel.startswith("~"):
        raise Refusal(f"{rel}: absolute paths are not allowed, write it relative to the campaign")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise Refusal(f"{rel}: empty, '.' and '..' segments are not allowed")
    here = root
    for part in parts:
        here = here / part
        if here.is_symlink():
            raise Refusal(f"{rel}: {part} is a symlink")
    if exist and not here.exists():
        raise Refusal(f"{rel}: missing")
    return here


def inside(rel: str, directory: str) -> bool:
    return rel.startswith(directory.rstrip("/") + "/")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def link_digest(text: str) -> str:
    return hashlib.sha256(b"symlink\0" + os.fsencode(text)).hexdigest()


def expand(root: Path, rel: str) -> dict:
    """Hash one campaign path; a directory becomes every entry below it.

    A symlink below a listed directory is hashed by its link text, and only when it stays inside
    that directory; symlinks are never followed.
    """
    path = under(root, rel)
    if path.is_file():
        return {rel: digest(path)}
    if not path.is_dir():
        raise Refusal(f"{rel}: neither a file nor a directory")
    found = {}
    for top, dirs, files in os.walk(path):
        for name in dirs + files:
            full = Path(top) / name
            key = full.relative_to(root).as_posix()
            if full.is_symlink():
                text = os.readlink(full)
                inner = os.path.normpath(os.path.join(os.path.dirname(full.relative_to(path).as_posix()), text))
                if os.path.isabs(text) or inner == ".." or inner.startswith("../"):
                    raise Refusal(f"{key}: symlink to {text} leaves {rel}")
                found[key] = link_digest(text)
            elif name in files:
                if not full.is_file():
                    raise Refusal(f"{key}: not a regular file")
                found[key] = digest(full)
    return dict(sorted(found.items()))


def expand_all(root: Path, rels) -> dict:
    out = {}
    for rel in rels:
        out.update(expand(root, rel))
    return out


def read_json(path: Path, what="file"):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Refusal(f"{what} {path} does not exist") from None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(f"{what} {path} is not readable JSON ({exc})") from None


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def locked(root: Path, name=".registry.lock"):
    with open(root / name, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def timestamp(value, what="timestamp") -> _dt.datetime:
    if not isinstance(value, str):
        raise Refusal(f"{what} must be an ISO 8601 string")
    try:
        parsed = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Refusal(f"{what} {value!r} is not ISO 8601") from None
    if parsed.tzinfo is None:
        raise Refusal(f"{what} {value!r} has no timezone")
    return parsed


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def nonempty(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def str_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)
