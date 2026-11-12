"""snapshot.py: exports, refusals, atomic publish."""
import json
import os

from conftest import cli, git, make_repo


def test_exports_both_states(tmp_path):
    repo, s0, s1 = make_repo(tmp_path)
    out = tmp_path / "snap"
    done = cli("snapshot.py", repo, s0, s1, out, ok=True)
    assert done.stdout == "" and done.stderr == ""
    assert (out / "S0/gate.sh").read_text() != (out / "S1/gate.sh").read_text()
    assert not (out / "S0/.git").exists()
    src = json.loads((out / "source.json").read_text())
    assert src["s0"] == s0 and src["s1"] == s1 and len(src["tree0"]) == 40
    assert "gate: simplify" in (out / "change-message.txt").read_text()
    assert "diff --git" in (out / "change.patch").read_text()


def test_refusals(tmp_path):
    repo, s0, s1 = make_repo(tmp_path)
    assert "same commit" in cli("snapshot.py", repo, s1, "HEAD", tmp_path / "a", ok=False).stderr
    assert "inside the repository" in cli("snapshot.py", repo, s0, s1, repo / "out", ok=False).stderr
    (tmp_path / "taken").mkdir()
    assert "already exists" in cli("snapshot.py", repo, s0, s1, tmp_path / "taken", ok=False).stderr
    assert "does not name a commit" in cli("snapshot.py", repo, "nope", s1, tmp_path / "b", ok=False).stderr
    assert cli("snapshot.py", repo, s0).returncode == 2


def test_export_attributes_refused(tmp_path):
    repo, s0, _ = make_repo(tmp_path)
    (repo / ".gitattributes").write_text("secret.txt export-ignore\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "attrs")
    done = cli("snapshot.py", repo, s0, "HEAD", tmp_path / "c", ok=False)
    assert "export-ignore" in done.stderr and not (tmp_path / "c").exists()


def test_lfs_pointer_refused(tmp_path):
    repo, s0, _ = make_repo(tmp_path)
    (repo / "big.bin").write_text("version https://git-lfs.github.com/spec/v1\noid sha256:00\nsize 9\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "lfs")
    assert "LFS" in cli("snapshot.py", repo, s0, "HEAD", tmp_path / "d", ok=False).stderr


def test_escaping_symlink_refused(tmp_path):
    repo, s0, _ = make_repo(tmp_path)
    (repo / "up").symlink_to("../../etc")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "link")
    assert "outside the tree" in cli("snapshot.py", repo, s0, "HEAD", tmp_path / "e", ok=False).stderr
    assert not any(p.name.startswith(".e.") for p in tmp_path.iterdir())


def blob(repo, data: str) -> str:
    import subprocess
    done = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"], input=data,
                          capture_output=True, text=True, check=True)
    return done.stdout.strip()


def tree(repo, entries: dict) -> str:
    """entries: {path: (mode, text)}; builds nested trees with git mktree, no working tree involved."""
    import subprocess
    top, subs = [], {}
    for path, (mode, text) in entries.items():
        head, _, rest = path.partition("/")
        if rest:
            subs.setdefault(head, {})[rest] = (mode, text)
        else:
            top.append(f"{mode} blob {blob(repo, text)}\t{head}")
    for name, inner in subs.items():
        top.append(f"040000 tree {tree(repo, inner)}\t{name}")
    done = subprocess.run(["git", "-C", str(repo), "mktree"], input="\n".join(top) + "\n",
                          capture_output=True, text=True, check=True)
    return done.stdout.strip()


def commit_tree(repo, parent, entries) -> str:
    return git(repo, "commit-tree", tree(repo, entries), "-p", parent, "-m", "crafted")


def test_case_folding_escape_refused(tmp_path):
    repo, s0, _ = make_repo(tmp_path)
    evil = commit_tree(repo, s0, {"S": ("120000", "."), "s/A": ("120000", ".."), "s/a/B": ("120000", ".."),
                                  "s/a/b/PWNED": ("100644", "owned\n")})
    (tmp_path / "out").mkdir()
    done = cli("snapshot.py", repo, s0, evil, tmp_path / "out" / "snap", ok=False)
    assert "collide" in done.stderr or "below the symlink" in done.stderr, done.stderr
    assert "Traceback" not in done.stderr
    assert not (tmp_path / "PWNED").exists() and not (tmp_path / "out" / "PWNED").exists()
    assert list((tmp_path / "out").iterdir()) == []


def test_path_below_symlink_refused(tmp_path):
    repo, s0, _ = make_repo(tmp_path)
    evil = commit_tree(repo, s0, {"d": ("120000", "sub"), "d/x": ("100644", "x\n"), "sub/y": ("100644", "y\n")})
    assert "below the symlink" in cli("snapshot.py", repo, s0, evil, tmp_path / "f", ok=False).stderr


def test_unicode_collision_refused(tmp_path):
    repo, s0, _ = make_repo(tmp_path)
    composed, decomposed = "caf\u00e9", "cafe\u0301"
    assert composed != decomposed
    evil = commit_tree(repo, s0, {composed: ("100644", "a\n"), decomposed: ("100644", "b\n")})
    assert len(git(repo, "ls-tree", "--name-only", evil).splitlines()) == 2
    assert "collide" in cli("snapshot.py", repo, s0, evil, tmp_path / "g", ok=False).stderr


def test_info_attributes_export_ignore_caught(tmp_path):
    repo, s0, _ = make_repo(tmp_path)
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "attributes").write_text("gate.sh export-ignore\n")
    done = cli("snapshot.py", repo, s0, "HEAD", tmp_path / "h", ok=False)
    assert "does not match git ls-tree" in done.stderr and not (tmp_path / "h").exists()


def test_internal_symlink_exported_and_sealable(tmp_path):
    repo, s0, _ = make_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "gate-link.sh").symlink_to("../gate.sh")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "link")
    camp = tmp_path / "camp"
    (camp / "attempts" / "a001").mkdir(parents=True)
    cli("snapshot.py", repo, s0, "HEAD", camp / "attempts" / "a001" / "snapshot", ok=True)
    link = camp / "attempts/a001/snapshot/S1/docs/gate-link.sh"
    assert link.is_symlink() and os.readlink(link) == "../gate.sh"
    (camp / "attempts/a001/rec.json").write_text(json.dumps({
        "stage": "prepare", "agent": "x", "inputs": [], "artifacts": ["attempts/a001/snapshot"]}))
    cli("evidence.py", "seal", camp, "attempts/a001/rec.json", ok=True)
    cli("evidence.py", "verify", camp, "attempts/a001/rec.json", ok=True)
    os.unlink(link)
    link.symlink_to("../README")
    assert "changed" in cli("evidence.py", "verify", camp, "attempts/a001/rec.json", ok=False).stderr


def test_without_tar_filter_symlinks_refused(tmp_path, monkeypatch, mods):
    snapshot = mods["snapshot"]
    repo, s0, _ = make_repo(tmp_path)
    (repo / "l").symlink_to("gate.sh")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "link")
    monkeypatch.setattr(snapshot, "HAS_FILTER", False)
    assert snapshot.main([str(repo), s0, "HEAD", str(tmp_path / "i")]) == 1
    assert not (tmp_path / "i").exists()


def test_broken_archive_is_a_refusal(tmp_path, monkeypatch, mods):
    snapshot = mods["snapshot"]
    repo, s0, s1 = make_repo(tmp_path)
    real = snapshot.git
    monkeypatch.setattr(snapshot, "git", lambda r, *a, data=False: b"not a tar" if a[0] == "archive" else real(r, *a, data=data))
    assert snapshot.main([str(repo), s0, s1, str(tmp_path / "j")]) == 1
    assert not (tmp_path / "j").exists()
