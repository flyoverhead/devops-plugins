import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "code-improver" / "scripts" / "scope_guard.py"
ENV = {"GIT_AUTHOR_NAME": "Mira Holt", "GIT_AUTHOR_EMAIL": "mira@example.net",
       "GIT_COMMITTER_NAME": "Mira Holt", "GIT_COMMITTER_EMAIL": "mira@example.net",
       "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": "/nonexistent"}


def run(*args):
    res = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    payload = json.loads(res.stdout) if res.stdout.strip() else None
    return res.returncode, payload, res.stderr


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, env=ENV)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "proj"
    (root / "pkg" / "inner").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "pkg" / "a.go").write_text("package pkg\n")
    (root / "pkg" / "inner" / "b.go").write_text("package inner\n")
    (root / "docs" / "guide.md").write_text("# guide\n")
    (root / ".gitignore").write_text("*.log\n")
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "config", "core.hooksPath", "/dev/null")
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-q", "-m", "seed")
    return root


@pytest.fixture
def out(tmp_path):
    return tmp_path / "artifacts"


def init(repo, out, *scope):
    return run("init", "--repo", repo, "--out", out, "--scope", *(scope or ("pkg/**",)))


def check(out, *scope):
    return run("check", "--out", out, "--scope", *(scope or ("pkg/**",)))


@pytest.mark.parametrize("glob,path,hit", [
    ("pkg/**", "pkg/a.go", True),
    ("pkg/**", "pkg/inner/b.go", True),
    ("pkg/**", "pkgx/a.go", False),
    ("pkg/*", "pkg/a.go", True),
    ("pkg/*", "pkg/inner/b.go", False),
    ("**/*.md", "README.md", True),
    ("**/*.md", "docs/deep/x.md", True),
    ("docs/guide.md", "docs/guide.md", True),
    ("docs/guide?md", "docs/guide.md", False),
    ("docs/[g]uide.md", "docs/guide.md", False),
    (".claude-plugin/marketplace.json", ".claude-plugin/marketplace.json", True),
])
def test_glob_semantics(glob, path, hit):
    code, payload, _ = run("match", "--scope", glob, "--", path)
    assert code == 0 and payload == {path: hit}


def test_match_strips_dot_slash():
    _, payload, _ = run("match", "--scope", "pkg/**", "--", "./pkg/a.go")
    assert payload == {"./pkg/a.go": True}


def test_clean_run_has_no_violations(repo, out):
    code, base, _ = init(repo, out)
    assert code == 0 and base["resumed"] is False
    assert len(base["sha"]) == 40 and (out / "baseline.json").exists()
    code, rep, _ = check(out)
    assert code == 0 and rep["ok"] and rep["violations"] == [] and rep["changed"] == []


def test_in_scope_edit_allowed(repo, out):
    init(repo, out)
    (repo / "pkg" / "inner" / "b.go").write_text("package inner\n\nconst X = 1\n")
    code, rep, _ = check(out)
    assert code == 0 and rep["changed"] == ["pkg/inner/b.go"]


def test_out_of_scope_tracked_edit_is_violation(repo, out):
    init(repo, out)
    (repo / "docs" / "guide.md").write_text("# guide\n\nchanged\n")
    code, rep, _ = check(out)
    assert code == 1 and rep["violations"] == ["docs/guide.md"]


def test_staged_change_is_seen(repo, out):
    init(repo, out)
    (repo / "docs" / "guide.md").write_text("staged\n")
    sh(repo, "git", "add", "docs/guide.md")
    code, rep, _ = check(out)
    assert code == 1 and "docs/guide.md" in rep["violations"]


def test_deleted_file_out_of_scope(repo, out):
    init(repo, out)
    (repo / "docs" / "guide.md").unlink()
    assert check(out)[0] == 1


def test_new_untracked_out_of_scope(repo, out):
    init(repo, out)
    (repo / "notes.txt").write_text("x\n")
    code, rep, _ = check(out)
    assert code == 1 and rep["violations"] == ["notes.txt"]


def test_new_untracked_in_scope_reported_not_violation(repo, out):
    init(repo, out)
    (repo / "pkg" / "c.go").write_text("package pkg\n")
    code, rep, _ = check(out)
    assert code == 0 and rep["new_untracked_in_scope"] == ["pkg/c.go"]
    sh(repo, "git", "add", "-N", "pkg/c.go")
    code, rep, _ = check(out)
    assert code == 0 and rep["new_untracked_in_scope"] == [] and "pkg/c.go" in rep["changed"]


def test_preexisting_untracked_guarded_by_content(repo, out):
    (repo / "scratch.txt").write_text("mine\n")
    init(repo, out)
    assert check(out)[0] == 0
    (repo / "scratch.txt").write_text("rewritten\n")
    code, rep, _ = check(out)
    assert code == 1 and rep["violations"] == ["scratch.txt"]


def test_preexisting_untracked_removed_is_violation(repo, out):
    (repo / "scratch.txt").write_text("mine\n")
    init(repo, out)
    (repo / "scratch.txt").unlink()
    assert check(out)[0] == 1


def test_hash_cap_lists_unguarded(repo, out):
    for i in range(53):
        (repo / f"loose{i:02d}.txt").write_text(str(i))
    code, base, _ = init(repo, out)
    assert len(base["digests"]) == 50 and len(base["unhashed"]) == 3
    code, rep, _ = check(out)
    assert code == 0 and len(rep["unguarded"]) == 3


def test_out_of_scope_untracked_hashed_first(repo, out):
    for i in range(50):
        (repo / "pkg" / f"gen{i:02d}.go").write_text("package pkg\n")
    (repo / "zz-outside.txt").write_text("keep\n")
    _, base, _ = init(repo, out)
    assert "zz-outside.txt" in base["digests"]


def test_ignored_files_not_reported(repo, out):
    init(repo, out)
    (repo / "debug.log").write_text("x\n")
    assert check(out)[0] == 0


def test_out_dir_inside_repo_is_skipped(repo):
    inside = repo / ".ci-out"
    init(repo, inside)
    (inside / "ledger.json").write_text("{}\n")
    assert check(inside)[0] == 0


def test_dirty_tree_refused(repo, out):
    (repo / "pkg" / "a.go").write_text("package pkg // edited\n")
    code, payload, _ = init(repo, out)
    assert code == 3 and payload["error"] == "dirty-tree"
    assert not (out / "baseline.json").exists()


def test_no_commit_refused(tmp_path, out):
    bare = tmp_path / "fresh"
    bare.mkdir()
    sh(bare, "git", "init", "-q")
    code, payload, _ = init(bare, out)
    assert code == 3 and payload["error"] == "no-commit"


def test_not_a_repo_refused(tmp_path, out):
    plain = tmp_path / "plain"
    plain.mkdir()
    code, payload, _ = run("init", "--repo", plain, "--out", out, "--scope", "x/**")
    assert code == 3 and payload["error"] == "not-a-repo"


def test_resume_keeps_baseline_despite_loop_edits(repo, out):
    _, first, _ = run("init", "--repo", repo, "--out", out, "--scope", "pkg/**", "--plugin-version", "1.2.3")
    (repo / "pkg" / "a.go").write_text("package pkg // fixed\n")
    check(out)
    code, again, _ = run("init", "--repo", repo, "--out", out, "--scope", "pkg/**", "--plugin-version", "1.2.4")
    assert code == 0 and again["resumed"] is True and again["sha"] == first["sha"]
    assert again["plugin_version"] == "1.2.3"


def test_resume_refused_when_tree_changed_after_last_check(repo, out):
    init(repo, out)
    (repo / "pkg" / "a.go").write_text("package pkg // fixed\n")
    check(out)
    (repo / "pkg" / "a.go").write_text("package pkg // then the user typed here\n")
    code, payload, _ = init(repo, out)
    assert code == 3 and payload["error"] == "dirty-tree"


def test_resume_refused_without_any_check(repo, out):
    init(repo, out)
    (repo / "pkg" / "a.go").write_text("package pkg // unseen\n")
    assert init(repo, out)[1]["error"] == "dirty-tree"


def test_check_records_last_digest(repo, out):
    init(repo, out)
    (repo / "pkg" / "a.go").write_text("package pkg // x\n")
    digest = check(out)[1]["digest"]
    assert json.loads((out / "baseline.json").read_text())["last_digest"] == digest


def test_scope_pinned_at_init(repo, out):
    init(repo, out, "pkg/**", ".claude-plugin/marketplace.json")
    assert json.loads((out / "baseline.json").read_text())["scope"] == [".claude-plugin/marketplace.json", "pkg/**"]
    assert check(out, ".claude-plugin/marketplace.json", "pkg/**")[0] == 0
    code, payload, _ = check(out, "pkg/**", "docs/**")
    assert code == 3 and payload["error"] == "scope-mismatch"


def test_commit_detected(repo, out):
    init(repo, out)
    (repo / "pkg" / "a.go").write_text("package pkg // committed\n")
    sh(repo, "git", "commit", "-qam", "sneaky")
    code, rep, _ = check(out)
    assert code == 1 and rep["head_moved"] is True


def test_stash_detected(repo, out):
    init(repo, out)
    (repo / "pkg" / "a.go").write_text("package pkg // stashed\n")
    sh(repo, "git", "stash", "-q")
    code, rep, _ = check(out)
    assert code == 1 and rep["head_moved"] is True and rep["changed"] == []


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_hidden_index_flags_flagged(repo, out, flag):
    init(repo, out)
    sh(repo, "git", "update-index", flag, "docs/guide.md")
    (repo / "docs" / "guide.md").write_text("hidden edit\n")
    code, rep, _ = check(out)
    assert code == 1 and rep["hidden_flags"] == ["docs/guide.md"]
    assert "docs/guide.md" in rep["violations"]


def test_preexisting_hidden_flag_not_flagged(repo, out):
    sh(repo, "git", "update-index", "--skip-worktree", "docs/guide.md")
    init(repo, out)
    assert check(out)[0] == 0


def test_git_config_change_detected(repo, out):
    init(repo, out)
    sh(repo, "git", "config", "core.pager", "cat")
    code, rep, _ = check(out)
    assert code == 1 and ".git/config" in rep["violations"]


def test_git_hook_added_detected(repo, out):
    init(repo, out)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 0\n")
    code, rep, _ = check(out)
    assert code == 1 and ".git/hooks/pre-commit" in rep["violations"]


def test_internal_error_is_exit_3_json(repo, out):
    init(repo, out)
    state = json.loads((out / "baseline.json").read_text())
    del state["untracked"]
    (out / "baseline.json").write_text(json.dumps(state))
    code, payload, _ = check(out)
    assert code == 3 and payload["error"] == "internal"


def test_diff_calls_disable_textconv_and_color():
    text = SCRIPT.read_text()
    assert '"--no-ext-diff", "--no-textconv", "--no-color"' in text
    assert text.count("*DIFF") == 3


def test_moved_head_needs_clean_tree(repo, out):
    init(repo, out)
    (repo / "pkg" / "a.go").write_text("package pkg // v2\n")
    sh(repo, "git", "commit", "-qam", "next")
    code, again, _ = init(repo, out)
    assert code == 0 and again["resumed"] is False


def test_digest_tracks_tree_state(repo, out):
    init(repo, out)
    first = check(out)[1]["digest"]
    assert check(out)[1]["digest"] == first
    (repo / "pkg" / "a.go").write_text("package pkg // touched\n")
    assert check(out)[1]["digest"] != first


def test_snapshot_writes_cumulative_diff(repo, out):
    init(repo, out)
    (repo / "pkg" / "a.go").write_text("package pkg\n\nvar Y = 2\n")
    code, payload, _ = run("snapshot", "--out", out, "--name", "fixes-round-1.diff")
    assert code == 0
    text = (out / "fixes-round-1.diff").read_text()
    assert "+var Y = 2" in text and payload["bytes"] == len(text.encode())


@pytest.mark.parametrize("name", ["../escape.diff", "sub/x.diff", "notes.txt", ".hidden.diff"])
def test_snapshot_rejects_bad_names(repo, out, name):
    init(repo, out)
    assert run("snapshot", "--out", out, "--name", name)[0] == 2


def test_check_without_baseline(out):
    code, payload, _ = check(out)
    assert code == 3 and payload["error"] == "no-baseline"


@pytest.mark.parametrize("argv", [[], ["--help"], ["bogus"], ["check", "--out", "x"],
                                  ["init", "--repo", "x"], ["init", "--repo", "x", "--out", "o"], ["match", "--scope", "a/**"],
                                  ["init", "--repo", "a", "--repo", "b", "--out", "o"]])
def test_usage_errors(argv):
    code, payload, err = run(*argv)
    assert code == 2 and payload is None and "scope_guard.py init" in err


def test_stdlib_only():
    allowed = {"hashlib", "json", "os", "re", "subprocess", "sys", "pathlib"}
    text = SCRIPT.read_text()
    imported = {line.split()[1].split(".")[0] for line in text.splitlines()
                if line.startswith(("import ", "from "))}
    assert imported <= allowed, imported - allowed


def test_stash_before_baseline_is_not_a_move(repo, out):
    (repo / "pkg" / "a.go").write_text("package pkg // parked\n")
    sh(repo, "git", "stash", "-q")
    _, base, _ = init(repo, out)
    assert base["stash"]
    assert check(out)[0] == 0
    (repo / "pkg" / "a.go").write_text("package pkg // parked again\n")
    sh(repo, "git", "stash", "-q")
    code, rep, _ = check(out)
    assert code == 1 and rep["head_moved"] is True


def test_stash_drop_after_baseline_is_a_move(repo, out):
    (repo / "pkg" / "a.go").write_text("package pkg // parked\n")
    sh(repo, "git", "stash", "-q")
    init(repo, out)
    sh(repo, "git", "stash", "drop", "-q")
    assert check(out)[1]["head_moved"] is True


@pytest.fixture
def linked(repo, tmp_path):
    wt = tmp_path / "wt"
    sh(repo, "git", "worktree", "add", "-q", "-b", "side", str(wt))
    return wt


def test_linked_worktree_hookspath_detected(linked, out):
    init(linked, out)
    assert check(out)[0] == 0
    sh(linked, "git", "config", "core.hooksPath", ".githooks")
    code, rep, _ = check(out)
    assert code == 1 and ".git/config" in rep["violations"]


def test_linked_worktree_common_hook_detected(linked, repo, out):
    init(linked, out)
    common = subprocess.run(["git", "-C", str(linked), "rev-parse", "--path-format=absolute",
                             "--git-common-dir"], capture_output=True, text=True, check=True).stdout.strip()
    hooks = Path(common) / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "post-checkout").write_text("#!/bin/sh\n")
    code, rep, _ = check(out)
    assert code == 1 and ".git/hooks/post-checkout" in rep["violations"]


def test_linked_worktree_config_worktree_detected(linked, out):
    sh(linked, "git", "config", "extensions.worktreeConfig", "true")
    init(linked, out)
    sh(linked, "git", "config", "--worktree", "core.hooksPath", "/tmp/elsewhere")
    code, rep, _ = check(out)
    assert code == 1 and any(v.endswith("config.worktree") for v in rep["violations"])
