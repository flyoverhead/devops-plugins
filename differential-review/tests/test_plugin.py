import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "differential-review" / "SKILL.md"
REFS = SKILL.parent / "references"
AGENT = ROOT / "agents" / "adversarial-modeler.md"
GIT_READ = {"diff", "log", "show", "blame", "merge-base", "rev-parse", "ls-files",
            "remote get-url"}
GH_READ = {"gh pr view", "gh pr diff", "gh search code"}
OTHER_HOST_CLI = re.compile("g" + "lab", re.I)
SECTIONS = ["1. Summary", "2. What changed", "3. Findings", "4. Test coverage",
            "5. Blast radius", "6. History", "7. Recommendations", "8. Method and limits",
            "9. Commits"]
TEMPLATE_FIELDS = ["Location", "Attacker", "Exploitability", "Blast radius", "Tests",
                   "Change", "Attack", "Impact", "Fix"]


def split(path):
    _, head, body = path.read_text().split("---", 2)
    return yaml.safe_load(head), body


def skill_tools():
    return re.findall(r"[\w.*-]+(?:\([^)]*\))?", split(SKILL)[0]["allowed-tools"])


def links():
    return re.findall(r"\]\(references/([\w.-]+\.md)", SKILL.read_text())


def test_references_linked_and_present():
    assert set(links()) == {p.name for p in REFS.glob("*.md")}


@pytest.mark.parametrize("ref", sorted(REFS.glob("*.md")), ids=lambda p: p.stem)
def test_long_references_have_contents(ref):
    lines = ref.read_text().splitlines()
    if len(lines) > 100:
        assert "## Contents" in lines[:20]


def test_anchors_resolve():
    for name, anchor in re.findall(r"\]\(references/([\w.-]+\.md)#([\w-]+)\)", SKILL.read_text()):
        headings = re.findall(r"^#+ (.+)$", (REFS / name).read_text(), re.M)
        slugs = {re.sub(r"[^\w -]", "", h).strip().lower().replace(" ", "-") for h in headings}
        assert anchor in slugs, (name, anchor)


def test_skill_body_length():
    assert len(split(SKILL)[1].strip().splitlines()) <= 250


def test_skill_tools_read_only():
    tools = skill_tools()
    assert not {"Edit", "NotebookEdit", "Bash", "WebFetch"} & set(tools)
    for tool in tools:
        if not tool.startswith("Bash("):
            continue
        cmd = tool[5:-1].removesuffix(":*")
        if cmd.startswith("git "):
            assert cmd[4:] in GIT_READ, tool
        elif cmd.startswith("gh"):
            assert cmd in GH_READ, tool
        else:
            assert cmd == "printenv TMPDIR", tool


def test_git_grep_not_pre_allowed():
    assert not any(t.startswith("Bash(git grep") for t in skill_tools())
    assert "git grep` is not pre-allowed" in split(SKILL)[1]


def test_no_other_host_cli_anywhere():
    for path in ROOT.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.suffix in {".md", ".sh", ".yaml", ".json", ".py"}:
            if path.name == "test_plugin.py":
                continue
            assert not OTHER_HOST_CLI.search(path.read_text()), path


def test_description_routes_go_idiom_away():
    desc = split(SKILL)[0]["description"]
    assert desc.startswith("Judges ")
    assert "Use when" in desc and "golang:review" in desc


def test_fallback_and_posting_rules():
    body = " ".join(split(SKILL)[1].split())
    assert "git remote get-url origin" in body
    assert "No second `gh` call" in body
    assert "gh pr comment" in body and "says yes" in body
    assert "gh api" in body


def test_report_outside_repo():
    body = split(SKILL)[1]
    assert "$TMPDIR/diff-review-<repo>-<short-head-sha>.md" in body


def test_ci_order():
    names = links()
    assert names.index("ci-github-actions.md") < names.index("ci-gitlab.md")


def test_output_sections_in_order():
    text = (REFS / "output-format.md").read_text()
    positions = [text.index(f"\n## {s}\n") for s in SECTIONS]
    assert positions == sorted(positions)


def test_finding_template_fields():
    text = (REFS / "attack-modeling.md").read_text()
    block = text.split("## Finding template", 1)[1].split("\n## ", 1)[0]
    for field in TEMPLATE_FIELDS:
        assert f"**{field}:**" in block, field


def test_agent_frontmatter():
    meta, body = split(AGENT)
    assert meta["name"] == "adversarial-modeler"
    assert [t.strip() for t in meta["tools"].split(",")] == [
        "Read", "Grep", "Glob", "Bash(git show:*)", "Bash(git log:*)", "Bash(git blame:*)",
        "Bash(git diff:*)", "Bash(grep -rn:*)"]
    assert meta["skills"] == ["differential-review:differential-review"]
    assert len(AGENT.read_text().splitlines()) <= 80
    assert "Confidence: HIGH|MEDIUM|LOW" in body


def test_skill_names_agent_fully():
    assert "differential-review:adversarial-modeler" in split(SKILL)[1]


def test_manifest_matches_marketplace():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT.parent / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "differential-review")
    assert entry["version"] == plugin["version"] == "1.0.0"
    assert entry["category"] == "security" and "category" not in plugin
    assert entry["author"] == plugin["author"]
    assert entry["license"] == plugin["license"] == "MIT"


def test_eval_skill_regexes_scoped():
    for grader in (ROOT / "evals").glob("*/graders/*.md"):
        meta = yaml.safe_load(grader.read_text().split("---")[1])
        if meta.get("tool") == "Skill":
            assert "(?:differential-review:)?differential-review" in meta["input_match"], grader


def grader_regex(case, name):
    meta = yaml.safe_load((ROOT / "evals" / case / "graders" / name).read_text().split("---")[1])
    return re.compile(meta["input_match"])


@pytest.mark.parametrize("path,flagged", [
    ("/private/tmp/e-TbZl5e/tmp/claude-501/diff-review-cwd-94e3046.md", False),
    ("/var/folders/l_/95d2ww7x/T/diff-review-cwd-94e3046.md", False),
    ("/tmp/diff-review-cwd-94e3046.md", False),
    ("/private/tmp/e-TbZl5e/home/cwd/tmp/diff-review-cwd-94e3046.md", True),
    ("/private/tmp/e-TbZl5e/home/cwd/build/T/diff-review-cwd-94e3046.md", True),
    ("/private/tmp/e-TbZl5e/home/cwd/REVIEW.md", True),
])
def test_regression_no_write_anchor(path, flagged):
    rx = grader_regex("outcome-regression", "no-write.md")
    assert bool(rx.search(json.dumps({"file_path": path, "content": "x"}))) is flagged


@pytest.mark.parametrize("command,counted", [
    ("gh pr view 7", True),
    ("/opt/homebrew/bin/gh pr view 7", True),
    ("git remote get-url origin && gh pr diff 7", True),
    ("git remote get-url origin", False),
    ("command -v gh", False),
])
def test_gh_counter(command, counted):
    rx = grader_regex("outcome-no-gh-fallback", "gh-at-most-once.md")
    assert bool(rx.search(json.dumps({"command": command}))) is counted


def test_tmpdir_fallback_and_patch_name():
    body = " ".join(split(SKILL)[1].split())
    assert "empty output means `/tmp`" in body
    assert "patch file's basename" in body


def limits(text):
    return " ".join(text.split("## Limits", 1)[1].split("\n## ", 1)[0].split())


def test_fetch_not_preallowed():
    assert not any(t.startswith("Bash(git fetch") for t in skill_tools())


def test_skill_limits_name_dangerous_flags():
    block = limits(split(SKILL)[1])
    for flag in ("--output", "--ext-diff", "--textconv", "--no-index", "`-O`",
                 "--open-files-in-pager", "--web", "`-w`", "--upload-pack"):
        assert flag in block, flag


def test_agent_tools_scoped_and_limited():
    meta, body = split(AGENT)
    assert "Bash" not in [t.strip() for t in meta["tools"].split(",")]
    block = limits(body)
    for flag in ("--output", "--ext-diff", "--textconv", "--no-index"):
        assert flag in block, flag
