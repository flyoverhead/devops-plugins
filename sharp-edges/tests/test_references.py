import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = ROOT / "skills" / "sharp-edges" / "SKILL.md"
REF_DIR = SKILL_FILE.parent / "references"
AGENT_FILE = ROOT / "agents" / "sharp-edges-analyzer.md"
REF_FILES = sorted(REF_DIR.glob("*.md"))
LABELS = ("**Bites:**", "**Spot:**", "**Fix:**")
CODE = re.compile(r"^```(\w+)\n(.*?)^```", re.M | re.S)


def frontmatter(path):
    text = path.read_text()
    _, head, body = text.split("---", 2)
    return yaml.safe_load(head), body


def linked_refs():
    return re.findall(r"\]\(references/([\w.-]+\.md)\)", SKILL_FILE.read_text())


def entries(text):
    chunks = re.split(r"^### ", text, flags=re.M)[1:]
    for chunk in chunks:
        title, _, rest = chunk.partition("\n")
        yield title.strip(), rest.split("\n## ")[0]


def test_every_reference_linked_and_present():
    links = linked_refs()
    assert sorted(set(links)) == sorted(p.name for p in REF_FILES)
    for name in links:
        assert (REF_DIR / name).is_file(), name


@pytest.mark.parametrize("ref", REF_FILES, ids=lambda p: p.stem)
def test_entries_have_bites_spot_fix(ref):
    found = list(entries(ref.read_text()))
    assert found, f"{ref.name} has no entries"
    for title, body in found:
        missing = [lab for lab in LABELS if lab not in body]
        assert not missing, f"{ref.name}: '{title}' lacks {missing}"


@pytest.mark.parametrize("ref", REF_FILES, ids=lambda p: p.stem)
def test_long_references_have_contents(ref):
    lines = ref.read_text().splitlines()
    if len(lines) > 100:
        assert "## Contents" in lines[:30], ref.name


def test_github_actions_before_gitlab():
    links = linked_refs()
    assert links.index("ci-github-actions.md") < links.index("ci-gitlab.md")


def test_github_actions_lead_patterns_in_order():
    titles = [t for t, _ in entries((REF_DIR / "ci-github-actions.md").read_text())][:5]
    expected = ("pull_request_target", "run:", "tag or branch", "permissions", "secrets")
    assert len(titles) == 5
    for title, word in zip(titles, expected):
        assert word.lower() in title.lower(), (title, word)


def test_no_component_wording():
    for path in [SKILL_FILE, AGENT_FILE, ROOT / "README.md", *REF_FILES]:
        assert "ci component" not in path.read_text().lower(), path.name


def test_go_loop_capture_gated_on_version():
    text = (REF_DIR / "lang-go.md").read_text()
    body = dict(entries(text))["Loop variable captured by closures"]
    assert "1.22" in body and "go.mod" in body


def code_blocks(lang):
    for path in [SKILL_FILE, *REF_FILES]:
        for match in CODE.finditer(path.read_text()):
            if match.group(1) == lang:
                yield pytest.param(match.group(2), id=f"{path.stem}-{match.start()}")


@pytest.mark.parametrize("code", list(code_blocks("bash")))
def test_bash_blocks_parse(code):
    res = subprocess.run(["bash", "-n"], input=code, text=True, capture_output=True)
    assert res.returncode == 0, res.stderr


@pytest.mark.parametrize("code", list(code_blocks("yaml")))
def test_yaml_blocks_parse(code):
    assert yaml.safe_load(code) is not None


def test_skill_tools_are_read_only():
    meta, body = frontmatter(SKILL_FILE)
    tools = re.findall(r"[\w.*-]+(?:\([^)]*\))?", meta["allowed-tools"])
    assert not {"Write", "Edit", "Bash", "NotebookEdit"} & set(tools)
    for tool in tools:
        if tool.startswith("Bash("):
            assert tool in {"Bash(grep -rn:*)", "Bash(git ls-files:*)", "Bash(ls:*)"}, tool
    assert "gh " not in meta["allowed-tools"]
    assert len(body.strip().splitlines()) <= 250


def test_skill_description_routes_near_misses():
    desc = frontmatter(SKILL_FILE)[0]["description"]
    for target in ("insecure-defaults:audit", "differential-review:differential-review",
                   "golang:review", "ansible:role-checker"):
        assert target in desc


def test_agent_is_read_only_and_short():
    meta, _ = frontmatter(AGENT_FILE)
    assert [t.strip() for t in meta["tools"].split(",")] == ["Read", "Grep", "Glob"]
    assert meta["skills"] == ["sharp-edges:sharp-edges"]
    assert len(AGENT_FILE.read_text().splitlines()) <= 80
