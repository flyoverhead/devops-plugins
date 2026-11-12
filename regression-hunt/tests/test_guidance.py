"""guidance.py: copies from git objects, absent names, drift detection."""
from conftest import cli, git, make_repo


def test_copies_present_and_lists_absent(tmp_path):
    repo, s0, s1 = make_repo(tmp_path)
    camp = tmp_path / "c"
    camp.mkdir()
    (repo / "THREAT_MODEL.md").write_text("working tree edit, not committed\n")
    out = cli("guidance.py", camp, "--change", "change-1", "--repo", repo, "--commit", "HEAD", ok=True).stdout
    copy = camp / f"guidance/change-1/{s1}"
    assert (copy / "THREAT_MODEL.md").read_text() == "Callers without the key are untrusted.\n"
    assert "CLAUDE.md" in (copy / "absent.txt").read_text()
    assert f"CLAUDE.md @ {s1}: absent" in out and "untrusted" in out
    assert out.strip().splitlines()[-1] == f"inputs: guidance/change-1/{s1}/THREAT_MODEL.md guidance/change-1/{s1}/absent.txt"
    (copy / "THREAT_MODEL.md").write_text("changed\n")
    assert "no longer matches" in cli("guidance.py", camp, "--change", "change-1", "--repo", repo,
                                      "--commit", s1, ok=False).stderr


def test_bad_inputs(tmp_path):
    repo, _, _ = make_repo(tmp_path)
    camp = tmp_path / "c"
    camp.mkdir()
    assert cli("guidance.py", camp, "--change", "../x", "--repo", repo, "--commit", "HEAD").returncode == 1
    assert cli("guidance.py", camp, "--change", "c", "--repo", repo, "--commit", "nope").returncode == 1
