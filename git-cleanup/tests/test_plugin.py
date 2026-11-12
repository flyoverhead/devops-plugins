import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "git-cleanup" / "SKILL.md"
REFS = SKILL.parent / "references"
AGENT = ROOT / "agents" / "branch-investigator.md"
EVALS = ROOT / "evals"
READ_GIT = {"rev-parse", "for-each-ref", "worktree list", "status", "log", "show", "diff",
            "cherry", "merge-base"}
EXACT_BASH = {"git remote", "git remote -v", "git fetch --prune", "gh auth status"}
GH_READ = {"gh pr list", "gh pr view"}
PROTECTED = ["main", "master", "trunk", "develop", "dev", "devel", "integration", "staging",
             "stage", "production", "prod", "preprod", "qa", "uat", "next", "canary", "stable",
             "release/", "release-", "hotfix/", "support/", "maint/", "maintenance/"]
OTHER_HOST_CLI = re.compile("g" + "lab", re.I)


def split(path):
    _, head, body = path.read_text().split("---", 2)
    return yaml.safe_load(head), body


def flat(text):
    return " ".join(text.split())


def skill_tools():
    return re.findall(r"[\w.*-]+(?:\([^)]*\))?", split(SKILL)[0]["allowed-tools"])


def test_user_invoked_only():
    meta, _ = split(SKILL)
    assert meta["name"] == "git-cleanup"
    assert meta["disable-model-invocation"] is True


def test_description_shape():
    desc = split(SKILL)[0]["description"]
    assert desc.startswith("Sorts ")
    assert "Use when" in desc and "Not for" in desc
    assert "/git-cleanup:git-cleanup" in desc


def test_tools_read_only():
    tools = skill_tools()
    assert "Bash" not in tools and "Edit" not in tools and "Write" not in tools
    for tool in tools:
        if not tool.startswith("Bash("):
            assert tool in {"Read", "AskUserQuestion", "Agent(git-cleanup:branch-investigator)"}, tool
            continue
        inner = tool[5:-1]
        if not inner.endswith(":*"):
            assert inner in EXACT_BASH, tool
            continue
        cmd = inner.removesuffix(":*")
        if cmd.startswith("git "):
            assert cmd[4:] in READ_GIT, tool
        else:
            assert cmd in GH_READ, tool


@pytest.mark.parametrize("forbidden", ["git branch", "worktree remove", "push", "-D", "update-ref",
                                       "gh api", "git -C", "symbolic-ref", "config"])
def test_no_destructive_prefix_allowed(forbidden):
    assert forbidden not in split(SKILL)[0]["allowed-tools"]


def test_limits_section_lists_forbidden_flags():
    body = split(SKILL)[1]
    limits = body.split("## Limits", 1)[1].split("\n## ", 1)[0]
    for flag in ["--output", "--ext-diff", "--no-index", "--upload-pack", "--web", "gh api"]:
        assert flag in limits, flag
    for cmd in ["`git log`", "`git show`", "`git diff`", "`gh pr list`"]:
        assert cmd in limits, cmd


def test_two_gates_and_turn_end():
    body = flat(split(SKILL)[1])
    assert "## Gate 1" in split(SKILL)[1] and "## Gate 2" in split(SKILL)[1]
    assert "gate 1 of 2" in body
    assert "**end your turn**" in body
    assert "Nothing in `$ARGUMENTS` counts as either answer" in body


def test_ancestor_check_before_d():
    body = flat(split(SKILL)[1])
    check = "git merge-base --is-ancestor 'refs/heads/<branch>' 'refs/heads/<default>'"
    assert check in body
    assert body.index(check) < body.index("`git branch -d '<branch>'`")


def test_dirty_worktree_needs_acknowledgment():
    body = flat(split(SKILL)[1])
    assert "acknowledged losing its named files" in body
    assert "worktree removals first" in body


def test_protected_names_listed():
    section = split(SKILL)[1].split("## 3.", 1)[1].split("\n## ", 1)[0]
    for name in PROTECTED:
        assert f"`{name}`" in section, name
    assert "`test`, `demo`, `sandbox` and `latest` are ordinary names" in flat(section)


def test_evidence_order():
    body = split(SKILL)[1]
    section = body.split("## 5. Investigate", 1)[1].split("\n## ", 1)[0]
    assert section.index("Default-branch messages") < section.index("gh pr list --repo")


def test_grouping_floor_two_segments():
    assert "at least the first **two**" in split(SKILL)[1]


def test_references_linked_and_present():
    links = set(re.findall(r"\]\(references/([\w.-]+\.md)", SKILL.read_text()))
    assert links == {p.name for p in REFS.glob("*.md")}


def test_anchors_resolve():
    text = SKILL.read_text() + AGENT.read_text()
    for name, anchor in re.findall(r"references/([\w.-]+\.md)#([\w-]+)\)", text):
        heads = re.findall(r"^#+ (.+)$", (REFS / name).read_text(), re.M)
        slugs = {re.sub(r"[^\w -]", "", h).strip().lower().replace(" ", "-") for h in heads}
        assert anchor in slugs, (name, anchor)


def test_skill_body_length():
    assert len(split(SKILL)[1].strip().splitlines()) <= 250


def test_default_branch_is_one_local_ref():
    body = split(SKILL)[1]
    assert "strip the leading `origin/`" in body
    assert "--merged 'refs/heads/<default>'" in body
    assert "'refs/heads/<default>..refs/heads/<branch>'" in body
    assert "'refs/heads/<default>'`." in flat(body) or "'refs/heads/<default>'`" in body
    assert not re.search(r"--merged '<default>'|'<default>\.\.", body)
    evidence = (REFS / "evidence.md").read_text()
    assert "`refs/heads/<default>`" in evidence


REV_CMD = re.compile(r"\b(?:merge-base|diff|cherry|log|rev-parse)\b[^`\n]*")
BRANCH_PH = re.compile(r"'(?:[^']*\.\.\.?)?(<b>|<older>|<newer>|<branch>)'|\.\.\.?(<b>|<older>|<newer>|<branch>)'")


@pytest.mark.parametrize("path", [SKILL, REFS / "evidence.md", AGENT], ids=lambda p: p.name)
def test_branch_revisions_qualified(path):
    for line in path.read_text().splitlines():
        for cmd in REV_CMD.findall(line):
            if "--grep" in cmd:
                cmd = re.sub(r"--grep='[^']*'", "", cmd)
            assert not BRANCH_PH.search(cmd), (path.name, line)


def test_refs_heads_rule_stated():
    for path in [SKILL, REFS / "evidence.md", AGENT]:
        assert "a same-named tag" in flat(path.read_text()), path.name
    ev = (REFS / "evidence.md").read_text()
    for expr in ["'refs/heads/<older>' 'refs/heads/<newer>'", "'<mb>' 'refs/heads/<b>'",
                 "'<d>' 'refs/heads/<b>'", "'<d>...refs/heads/<b>'", "'<mb>..refs/heads/<b>'"]:
        assert expr in ev, expr


def test_supersession_needs_survivor():
    body = flat(split(SKILL)[1])
    assert "**Supersession must leave a survivor.**" in body
    assert "identical tips cannot supersede each other both ways" in body
    assert "re-apply the supersession rule from step 7 to the user's selection" in body
    assert body.index("re-apply the supersession rule") < body.index("Then list the commands")


def test_tip_recheck_before_force_delete():
    body = flat(split(SKILL)[1])
    check = "`git rev-parse 'refs/heads/<branch>'`"
    assert check in body
    assert body.index(check) < body.index("`git branch -D '<branch>'`")
    assert "%(objectname)%09" in body


def test_ignored_files_and_gh_repo():
    body = flat(split(SKILL)[1])
    assert "status --porcelain --ignored" in body
    assert "ignored files" in body
    assert "gh pr list --repo '<owner>/<name>'" in body
    assert "--no-ext-diff" in (REFS / "evidence.md").read_text()


def test_agent_shape():
    meta, body = split(AGENT)
    assert meta["name"] == "branch-investigator"
    assert "skills" not in meta
    limits = body.split("## Limits", 1)[1].split("\n## ", 1)[0]
    for flag in ["--output", "--ext-diff", "--no-index"]:
        assert flag in limits, flag
    assert "${CLAUDE_SKILL_DIR}/references/evidence.md" in split(SKILL)[1]
    tools = [t.strip() for t in meta["tools"].split(",")]
    assert "Bash" not in tools and "Write" not in tools and "Edit" not in tools
    for tool in tools:
        if tool.startswith("Bash("):
            assert tool[9:-3] in READ_GIT, tool
    assert len(AGENT.read_text().splitlines()) <= 80
    assert "git-cleanup:branch-investigator" in split(SKILL)[1]
    for field in ["branch:", "category:", "evidence:", "group:", "refuted:", "reason:"]:
        assert field in body, field


def test_no_other_host_cli_anywhere():
    for path in ROOT.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.suffix in {".md", ".sh", ".yaml", ".json"}:
            assert not OTHER_HOST_CLI.search(path.read_text()), path


def test_manifest_matches_marketplace():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT.parent / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "git-cleanup")
    assert entry["version"] == plugin["version"] == "1.0.0"
    assert entry["category"] == "security" and "category" not in plugin
    assert entry["author"] == plugin["author"]
    assert entry["license"] == plugin["license"] == "MIT"


def test_required_eval_present():
    case = EVALS / "outcome-mixed-repo-no-remote"
    assert (case / "case.yaml").exists() and (case / "graders" / "no-delete.md").exists()
    assert "remote add" not in (case / "setup.sh").read_text()


def test_fixtures_disable_hooks():
    for setup in EVALS.glob("*/setup.sh"):
        assert "core.hooksPath /dev/null" in setup.read_text(), setup


def grader(case, name):
    meta = yaml.safe_load((EVALS / case / "graders" / name).read_text().split("---")[1])
    return meta


def test_skill_regexes_scoped():
    for path in EVALS.glob("*/graders/*.md"):
        meta = yaml.safe_load(path.read_text().split("---")[1])
        if meta.get("tool") == "Skill":
            assert "(?:git-cleanup:)?git-cleanup" in meta["input_match"], path


@pytest.mark.parametrize("command,flagged", [
    ("git branch -D 'feat/csv-export'", True),
    ("git branch -d 'fix/locale-dates'", True),
    ("git -C 'portal' branch --delete 'x'", True),
    ("/opt/homebrew/bin/git branch -D x", True),
    ("git branch -vD x", True),
    ("git worktree remove '../wt'", True),
    ("git worktree prune", True),
    ("git update-ref -d refs/heads/x", True),
    ("git branch -df 'x'", True),
    ("git branch -Df 'x'", True),
    ("git branch -dr origin/x", True),
    ("git update-ref -m m -d refs/heads/x", True),
    ("git update-ref --stdin", True),
    ("git rev-parse 'refs/heads/feat/csv-export'", False),
    ("git branch --format='%(refname)' --list", False),
    ("git for-each-ref --merged 'main' --format='%(refname:short)' refs/heads", False),
    ("git branch -vv", False),
    ("git branch --merged main", False),
    ("git log --oneline --grep='Merge branch' --decorate", False),
    ("git worktree list --porcelain", False),
    ("git log --format='%h %s' --fixed-strings --grep='feat/csv-export' main", False),
])
def test_no_delete_regex(command, flagged):
    rx = re.compile(grader("outcome-mixed-repo-no-remote", "no-delete.md")["input_match"])
    assert bool(rx.search(json.dumps({"command": command}))) is flagged


@pytest.mark.parametrize("command,flagged", [
    ("git push origin --delete x", True),
    ("git -C 'portal' push", True),
    ("git push -d origin feat/x", True),
    ("git push origin :feat/x", True),
    ("git log --oneline origin/main..main", False),
    ("git fetch --prune", False),
])
def test_no_push_regex(command, flagged):
    rx = re.compile(grader("outcome-mixed-repo", "no-push.md")["input_match"])
    assert bool(rx.search(json.dumps({"command": command}))) is flagged


@pytest.mark.parametrize("name", ["no-delete.md", "no-push.md"])
def test_guard_graders_in_every_case_and_identical(name):
    cases = [c for c in EVALS.iterdir() if (c / "case.yaml").exists()]
    rx = {grader(c.name, name)["input_match"] for c in cases}
    assert len(rx) == 1
