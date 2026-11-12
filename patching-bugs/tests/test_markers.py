"""markers.py: printing the three marker lines and judging captured stdout."""
import hashlib
import json
import os

import pytest

from conftest import cli


def test_loaded_prints_resolved_path_and_hash(tmp_path):
    (tmp_path / "bin").mkdir()
    art = tmp_path / "bin" / "tool"
    art.write_bytes(b"\x7fELF demo")
    done = cli("markers.py", "loaded", "--artifact", "bin/tool", "--root", tmp_path)
    assert done.returncode == 0
    tag, payload = done.stdout.rstrip("\n").split(" ", 1)
    assert tag == "PATCH_LOADED"
    data = json.loads(payload)
    assert data == {"path": str(art.resolve()), "sha256": hashlib.sha256(b"\x7fELF demo").hexdigest()}


def test_loaded_refuses_missing_and_escaping_symlink(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    outside = tmp_path / "secret"
    outside.write_text("x")
    os.symlink(outside, root / "link")
    assert cli("markers.py", "loaded", "--artifact", "nope", "--root", root).returncode == 1
    assert cli("markers.py", "loaded", "--artifact", "link", "--root", root).returncode == 1


def test_case_and_reached_lines():
    done = cli("markers.py", "case", "--input", '"../x"', "--actual", '{"wrote": "outside"}')
    assert done.returncode == 0
    assert done.stdout == 'PATCH_CASE {"input": "../x", "actual": {"wrote": "outside"}}\n'
    assert cli("markers.py", "reached").stdout == "PATCH_REACHED\n"
    assert cli("markers.py", "case", "--input", "{bad", "--actual", "1").returncode == 2


GOOD = 'PATCH_LOADED {"path": "%s", "sha256": "%s"}\nnoise\nPATCH_CASE {"input": "../x", "actual": "outside"}\nPATCH_REACHED\n'


@pytest.mark.parametrize("body,ok", [
    ('PATCH_CASE {"input": 1, "actual": 2}\nPATCH_REACHED\n', True),
    ('PATCH_CASE {"input": 1, "actual": 2}\nPATCH_REACHED\n\n', True),
    ('PATCH_REACHED\nPATCH_CASE {"input": 1, "actual": 2}\n', False),
    ('PATCH_CASE {"input": 1, "actual": 2}\nPATCH_CASE {"input": 1, "actual": 2}\nPATCH_REACHED\n', False),
    ('PATCH_CASE {"input": 1}\nPATCH_REACHED\n', False),
    ('PATCH_CASE {"input": 1, "actual": 2, "side": "b"}\nPATCH_REACHED\n', False),
    ('PATCH_CASE {"input": 1, "actual": 2}\nPATCH_REACHED\nPATCH_REACHED\n', False),
    ('PATCH_CASE not json\nPATCH_REACHED\n', False),
    ('PATCH_CASE {"input": 1, "actual": 2}\n PATCH_REACHED\n', False),
    ('PATCH_CASE {"input": 1, "actual": 2}\nPATCH_REACHED done\n', False),
])
def test_check_stdout_shapes(tmp_path, body, ok):
    f = tmp_path / "out"
    f.write_text(body)
    done = cli("markers.py", "check-stdout", f)
    assert (done.returncode == 0) is ok
    if not ok:
        assert done.stdout.strip()


def test_check_stdout_input_and_identity(tmp_path):
    art = tmp_path / "tool"
    art.write_bytes(b"bytes")
    digest = hashlib.sha256(b"bytes").hexdigest()
    f = tmp_path / "out"
    f.write_text(GOOD % (art, digest))
    assert cli("markers.py", "check-stdout", f, "--input", '"../x"',
               "--runtime-identity", art, digest).returncode == 0
    assert cli("markers.py", "check-stdout", f, "--input", '"../y"').returncode == 1
    assert cli("markers.py", "check-stdout", f, "--runtime-identity", art, "0" * 64).returncode == 1
    assert cli("markers.py", "check-stdout", f, "--runtime-identity", tmp_path / "other", digest).returncode == 1
    f.write_text('PATCH_CASE {"input": "../x", "actual": 1}\nPATCH_REACHED\n')
    assert cli("markers.py", "check-stdout", f, "--runtime-identity", art, digest).returncode == 1


def test_input_compare_is_json_not_text(tmp_path):
    f = tmp_path / "out"
    f.write_text('PATCH_CASE {"input": {"b": 2, "a": 1}, "actual": 0}\nPATCH_REACHED\n')
    assert cli("markers.py", "check-stdout", f, "--input", '{"a":1,"b":2}').returncode == 0
