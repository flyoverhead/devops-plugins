"""evidence.py: sealing, verification, refusals."""
import json
import os

from conftest import cli, dump


def record(root, rel="attempts/a001/rec.json", **over):
    data = {"stage": "prepare", "agent": "agent-x", "inputs": ["in.txt"], "artifacts": ["attempts/a001/out"]}
    data.update(over)
    (root / "attempts/a001/out").mkdir(parents=True, exist_ok=True)
    (root / "attempts/a001/out/a.txt").write_text("a\n")
    (root / "in.txt").write_text("input\n")
    dump(root / rel, data)
    return rel


def test_seal_then_verify(tmp_path):
    rel = record(tmp_path)
    done = cli("evidence.py", "seal", tmp_path, rel, ok=True)
    assert done.stdout.strip() == f"sealed {rel}"
    seal = json.loads((tmp_path / (rel + ".seal.json")).read_text())
    assert set(seal) == {"record", "inputs", "artifacts", "dependencies"}
    assert "attempts/a001/out/a.txt" in seal["artifacts"]
    assert cli("evidence.py", "verify", tmp_path, rel, ok=True).stdout.startswith("verified")
    assert cli("evidence.py", "seal", tmp_path, rel, ok=True).stdout.startswith("verified")


def test_changed_added_and_missing_files_fail(tmp_path):
    rel = record(tmp_path)
    cli("evidence.py", "seal", tmp_path, rel, ok=True)
    (tmp_path / "attempts/a001/out/b.txt").write_text("late\n")
    assert "appeared" in cli("evidence.py", "verify", tmp_path, rel, ok=False).stderr
    os.unlink(tmp_path / "attempts/a001/out/b.txt")
    (tmp_path / "in.txt").write_text("other\n")
    assert "changed" in cli("evidence.py", "verify", tmp_path, rel, ok=False).stderr
    os.unlink(tmp_path / "in.txt")
    assert cli("evidence.py", "verify", tmp_path, rel).returncode == 1


def test_stale_seal(tmp_path):
    rel = record(tmp_path)
    cli("evidence.py", "seal", tmp_path, rel, ok=True)
    dump(tmp_path / rel, {"stage": "prepare", "agent": "other", "inputs": ["in.txt"], "artifacts": []})
    assert "stale" in cli("evidence.py", "verify", tmp_path, rel, ok=False).stderr


def test_refuses_bad_records(tmp_path):
    for over, word in (({"agent": ""}, "agent"), ({"inputs": "in.txt"}, "inputs"),
                       ({"artifacts": ["/etc/passwd"]}, "absolute"), ({"inputs": ["../x"]}, "segments"),
                       ({"artifacts": ["attempts/a001"]}, "own package")):
        rel = record(tmp_path, **over)
        done = cli("evidence.py", "seal", tmp_path, rel, ok=False)
        assert word in done.stderr, (over, done.stderr)
        assert done.stderr.startswith("evidence.py seal refused:")


def test_symlinks_rejected(tmp_path):
    rel = record(tmp_path)
    os.symlink("/etc/hosts", tmp_path / "attempts/a001/out/link")
    assert "symlink" in cli("evidence.py", "seal", tmp_path, rel, ok=False).stderr


def test_dependencies_followed(tmp_path):
    first = record(tmp_path)
    cli("evidence.py", "seal", tmp_path, first, ok=True)
    dump(tmp_path / "attempts/a002/rec.json", {"stage": "hunt", "agent": "b", "inputs": [first], "artifacts": []})
    cli("evidence.py", "seal", tmp_path, "attempts/a002/rec.json", ok=True)
    seal = json.loads((tmp_path / "attempts/a002/rec.json.seal.json").read_text())
    assert list(seal["dependencies"]) == [first]
    (tmp_path / "attempts/a001/out/a.txt").write_text("edited\n")
    assert cli("evidence.py", "verify", tmp_path, "attempts/a002/rec.json").returncode == 1


def test_usage_exit_two(tmp_path):
    assert cli("evidence.py", "stamp", tmp_path, "x").returncode == 2
    assert cli("evidence.py", "seal", tmp_path / "nope", "x").returncode == 1


def test_build_dir_symlinks(tmp_path):
    rel = record(tmp_path)
    build = tmp_path / "attempts/a001/out/node_modules"
    build.mkdir()
    (build / "real.js").write_text("x\n")
    os.symlink("real.js", build / "alias.js")
    os.symlink("..", build / "parent")
    cli("evidence.py", "seal", tmp_path, rel, ok=True)
    seal = json.loads((tmp_path / (rel + ".seal.json")).read_text())
    assert "attempts/a001/out/node_modules/alias.js" in seal["artifacts"]
    assert "attempts/a001/out/node_modules/parent" in seal["artifacts"]


def test_build_dir_escaping_symlink_refused(tmp_path):
    rel = record(tmp_path)
    os.symlink("../../../in.txt", tmp_path / "attempts/a001/out/escape")
    assert "leaves" in cli("evidence.py", "seal", tmp_path, rel, ok=False).stderr
