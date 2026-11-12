import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "fp-check" / "SKILL.md"
REFS = SKILL.parent / "references"
AGENTS = {p.stem: p for p in (ROOT / "agents").glob("*.md")}
SECTIONS = {
    "data-flow-analyzer": ["1.1", "1.2", "1.3", "1.4", "Phase 1 conclusion"],
    "exploitability-verifier": ["2.1", "2.2", "2.3", "2.4", "Phase 2 conclusion"],
    "poc-builder": ["4.1", "4.2", "4.3", "4.4", "4.5", "Phase 4 conclusion"],
}
READ_ONLY_BASH = {
    "Bash(git log:*)", "Bash(git show:*)", "Bash(git blame:*)",
    "Bash(git rev-parse:*)", "Bash(grep -rn:*)", "Bash(printenv TMPDIR)",
}


def split(path):
    _, head, body = path.read_text().split("---", 2)
    return yaml.safe_load(head), body


def skill_tools():
    return re.findall(r"[\w.*-]+(?:\([^)]*\))?", split(SKILL)[0]["allowed-tools"])


def test_references_linked_and_present():
    linked = set(re.findall(r"\]\(references/([\w.-]+\.md)\)", SKILL.read_text()))
    assert linked == {p.name for p in REFS.glob("*.md")}


@pytest.mark.parametrize("ref", sorted(REFS.glob("*.md")), ids=lambda p: p.stem)
def test_long_references_have_contents(ref):
    lines = ref.read_text().splitlines()
    if len(lines) > 100:
        assert "## Contents" in lines[:20]


def test_skill_body_length():
    assert len(split(SKILL)[1].strip().splitlines()) <= 250


def test_skill_tools_read_only():
    tools = skill_tools()
    assert not {"Edit", "NotebookEdit", "Bash", "WebFetch"} & set(tools)
    for tool in tools:
        if tool.startswith("Bash("):
            assert tool in READ_ONLY_BASH, tool
    assert "gh" not in " ".join(tools).split()


def test_description_routes():
    desc = split(SKILL)[0]["description"]
    assert desc.startswith("Decides ")
    for target in ("vulnerability-triage-brocards:vulnerability-triage-brocards",
                   "insecure-defaults:audit", "static-analysis:semgrep"):
        assert target in desc


def test_subagent_stop_hook():
    hooks = split(SKILL)[0]["hooks"]
    assert list(hooks) == ["SubagentStop"]
    (entry,) = hooks["SubagentStop"]
    matcher = re.compile(entry["matcher"])
    for name in SECTIONS:
        assert matcher.search(f"fp-check:{name}"), name
    for other in ("general-purpose", "Explore", "sharp-edges:sharp-edges-analyzer",
                  "data-flow-analyzer", "fp-check:data-flow-analyzer-x"):
        assert not matcher.search(other), other
    (hook,) = entry["hooks"]
    assert hook["type"] == "prompt" and hook["timeout"] == 30
    prompt = hook["prompt"]
    for name, needed in SECTIONS.items():
        assert f"fp-check:{name}" in prompt
        for section in needed:
            assert section in prompt, (name, section)
    assert '{"ok": true}' in prompt
    assert "agent_type is not" not in prompt


def test_hook_handback_and_loop_guard():
    prompt = split(SKILL)[0]["hooks"]["SubagentStop"][0]["hooks"][0]["prompt"]
    handback = prompt.split("no \"Phase 1\"")[1].split(".")[0:2]
    assert '{"ok": true}' in ".".join(handback)
    loop = prompt.split("stop_hook_active is true")[1]
    assert '"impossible": true' in loop and '"ok": false' in loop
    assert '"impossible"' not in prompt.split("stop_hook_active is true")[0]


def test_agents_set():
    assert set(AGENTS) == set(SECTIONS)


@pytest.mark.parametrize("name", sorted(SECTIONS))
def test_agent_frontmatter(name):
    meta, _ = split(AGENTS[name])
    tools = [t.strip() for t in meta["tools"].split(",")]
    expected = ["Read", "Grep", "Glob"] + (["Write"] if name == "poc-builder" else [])
    assert tools == expected
    assert meta["skills"] == ["fp-check:fp-check"]
    assert meta["name"] == name
    assert len(AGENTS[name].read_text().splitlines()) <= 80


@pytest.mark.parametrize("name", sorted(SECTIONS))
def test_procedure_templates_carry_sections(name):
    phase = SECTIONS[name][-1].split()[1]
    block = section_of(REFS / "phase-procedures.md", f"## Phase {phase} ")
    for section in SECTIONS[name][:-1]:
        assert f"### {section} " in block, section
    assert f"### {SECTIONS[name][-1]}" in block


def section_of(path, heading):
    out, inside, fenced = [], False, False
    for line in path.read_text().splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            inside = line.startswith(heading)
        if inside:
            out.append(line)
    return "\n".join(out)


def test_deep_task_titles():
    text = (REFS / "deep-path.md").read_text()
    for title in ("BUG #N - Phase 1.1:", "BUG #N - Phase 2.4:", "BUG #N - Phase 4.5:",
                  "BUG #N - Phase 5:", "BUG #N - GATE REVIEW"):
        assert title in text


def test_skill_names_agents_fully():
    body = split(SKILL)[1]
    for name in SECTIONS:
        assert f"fp-check:{name}" in body


def test_six_gates():
    body = split(SKILL)[1]
    for gate in ("G1 Process", "G2 Reachability", "G3 Real impact", "G4 PoC validation",
                 "G5 Math bounds", "G6 Environment"):
        assert gate in body


def test_manifest_matches_marketplace():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT.parent / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "fp-check")
    assert entry["version"] == plugin["version"] == "1.0.0"
    assert entry["category"] == "security" and "category" not in plugin
    assert entry["author"] == plugin["author"]
    assert entry["license"] == plugin["license"] == "MIT"


def test_eval_skill_regexes_scoped():
    for grader in (ROOT / "evals").glob("*/graders/*.md"):
        meta = yaml.safe_load(grader.read_text().split("---")[1])
        if meta.get("tool") == "Skill":
            assert "(?:fp-check:)?fp-check" in meta["input_match"], grader


def test_hard_limits_name_git_output_flags():
    body = split(SKILL)[1]
    block = " ".join(body.split("## Hard limits", 1)[1].split("\n## ", 1)[0].split())
    for flag in ("--output", "--ext-diff", "--textconv"):
        assert flag in block, flag


@pytest.mark.parametrize("path,flagged", [
    ("/private/tmp/e-Ab12/tmp/claude-501/fp-check-svc/bug-1/poc.py", False),
    ("/var/folders/l_/95d2ww7x/T/fp-check-svc/bug-2/poc_test.go", False),
    ("/tmp/fp-check-svc/bug-1/sub/poc.sh", False),
    ("/private/tmp/e-Ab12/home/cwd/fp-check-svc/bug-1/poc.py", True),
    ("/private/tmp/e-Ab12/home/cwd/tmp/fp-check-svc/bug-1/poc.py", True),
    ("/private/tmp/e-Ab12/home/cwd/internal/handler.go", True),
    ("/tmp/fp-check-svc/bug-1/../../../home/cwd/main.go", True),
    ("/tmp/fp-check-svc/bug-1/..", True),
    ("/tmp/fp-check-svc/bug-1/", True),
])
def test_no_write_anchor(path, flagged):
    meta = yaml.safe_load(
        (ROOT / "evals" / "outcome-two-findings" / "graders" / "no-write.md").read_text().split("---")[1])
    rx = re.compile(meta["input_match"])
    assert bool(rx.search(json.dumps({"file_path": path, "content": "x"}))) is flagged
