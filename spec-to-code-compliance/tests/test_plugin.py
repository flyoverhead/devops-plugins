import json
import re
from pathlib import Path

import pytest
import yaml

PLUGIN = Path(__file__).resolve().parents[1]
SKILL_DIR = PLUGIN / "skills" / "spec-to-code-compliance"
SKILL = SKILL_DIR / "SKILL.md"
REFS = SKILL_DIR / "references"
AGENTS = PLUGIN / "agents"
EVALS = PLUGIN / "evals"
VERDICTS = ["implemented", "partial", "contradicted", "stronger-than-spec", "absent", "undecidable"]
REPORT_SECTIONS = ["Findings", "Held", "Document problems", "Undocumented behaviour", "Refuted",
                   "Unverified", "Not checked", "Unreadable documents", "Open questions"]
ANALYSIS_SECTIONS = ["What an implementation must do", "Where enforcement lives", "Paths walked",
                     "Searched", "How the verdict was reached", "Open questions"]
EXPECTED_BASH = {"git ls-files:*", "git rev-parse:*", "git log:*", "printenv TMPDIR"}
OTHER_HOST = re.compile("gl" + "ab", re.I)


def split(path):
    _, meta, body = path.read_text().split("---", 2)
    return yaml.safe_load(meta), body


def oneline(text):
    return " ".join(text.split())


def grader_meta(case, name):
    return yaml.safe_load((EVALS / case / "graders" / name).read_text().split("---")[1])


def test_every_reference_is_linked_from_skill():
    linked = set(re.findall(r"\(references/([\w.-]+\.md)", SKILL.read_text()))
    assert linked == {p.name for p in REFS.iterdir()}


def test_long_references_have_contents():
    for ref in REFS.glob("*.md"):
        lines = ref.read_text().splitlines()
        assert len(lines) <= 100 or "## Contents" in lines[:15], ref.name


def test_reference_anchors_exist():
    for name, anchor in re.findall(r"\(references/([\w.-]+\.md)#([\w-]+)\)", SKILL.read_text()):
        headings = re.findall(r"^#+ (.+)$", (REFS / name).read_text(), re.M)
        assert anchor in {re.sub(r"[^\w -]", "", h).strip().lower().replace(" ", "-") for h in headings}


def test_skill_size_and_description():
    meta, body = split(SKILL)
    assert meta["name"] == "spec-to-code-compliance"
    assert len(body.strip().splitlines()) <= 250
    desc = meta["description"]
    assert desc.startswith("Measures ") and len(desc) <= 600
    assert "Use when" in desc and "Not for" in desc and "— use insecure-defaults:audit." in desc


def test_allowed_tools_read_only():
    tokens = re.findall(r"[\w.*-]+(?:\([^)]*\))?", split(SKILL)[0]["allowed-tools"])
    assert {"Read", "Grep", "Glob", "Write", "Agent"} <= set(tokens)
    assert not {"Edit", "Bash", "NotebookEdit", "WebFetch", "WebSearch"} & set(tokens)
    assert {t[5:-1] for t in tokens if t.startswith("Bash(")} == EXPECTED_BASH


def test_limits_forbid_git_log_output():
    limits = oneline(split(SKILL)[1].split("## Limits", 1)[1])
    assert "`git log`" in limits and "never pass `--output`" in limits


def test_no_other_host_cli_or_gh_use():
    for path in PLUGIN.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.suffix in {".md", ".sh", ".json", ".yaml"}:
            assert not OTHER_HOST.search(path.read_text()), path
    tools = split(SKILL)[0]["allowed-tools"]
    assert "gh " not in tools


def test_skill_states_safety_and_flow():
    body = oneline(split(SKILL)[1])
    for phrase in [
        "`printenv TMPDIR`; if it prints nothing, use `/tmp`",
        "<TMPDIR>/spec-compliance-<repo>-<short-sha>/",
        "`git rev-parse --short HEAD`",
        "Agents are not optional, whatever the repository size.",
        "at most 5 at a time",
        "At most 5 refuters run at once",
        "`lens: code`", "`lens: document`",
        "you never overrule a refuter",
        "Unverified",
        "Keep the top 10; up to 30 when the user asks",
        "`REQ-01`",
        "<redacted>",
        "before answering",
        "never the literal `$TMPDIR`",
        "`Not checked:` with what was left out, or `nothing`",
    ]:
        assert phrase in body, phrase
    for agent in ["spec-to-code-compliance:spec-compliance-checker",
                  "spec-to-code-compliance:divergence-refuter"]:
        assert agent in body
    order = [body.index(h) for h in ["## 1. Set up", "## 2. Find the documents", "## 3. Extract",
                                     "## 4. Check", "## 5. Refute", "## 6. Reverse direction",
                                     "## 7. Severity", "## 8. Report"]]
    assert order == sorted(order)


def test_routing_targets():
    body = split(SKILL)[1]
    for target in ["insecure-defaults:audit", "static-analysis:semgrep",
                   "audit-context-building:audit-context-building",
                   "differential-review:differential-review"]:
        assert target in body, target


def test_verdicts_and_severity_documented():
    text = (REFS / "verdicts.md").read_text()
    for v in VERDICTS:
        assert f"| `{v}` |" in text, v
    for level in ["critical", "high", "medium", "low"]:
        assert f"| {level} |" in text, level
    assert "## Earning absent" in text and "never overrules" in text


def test_calibration_covers_three_verdicts():
    text = (REFS / "calibration.md").read_text()
    for heading in ["## Implemented", "## Absent", "## Partial"]:
        assert heading in text
    assert text.count("**Mistake:**") == 3


def test_file_formats_section_order():
    text = (REFS / "file-formats.md").read_text()
    report = text.split("## REPORT.md", 1)[1]
    pos = [report.index(f"\n## {s}\n") for s in REPORT_SECTIONS]
    assert pos == sorted(pos)
    analysis = text.split("## Analysis file", 1)[1].split("## REPORT.md", 1)[0]
    pos = [analysis.index(f"## {s}") for s in ANALYSIS_SECTIONS]
    assert pos == sorted(pos)


@pytest.mark.parametrize("name,tools", [
    ("spec-compliance-checker", ["Read", "Grep", "Glob", "Write"]),
    ("divergence-refuter", ["Read", "Grep", "Glob"]),
])
def test_agent_shape(name, tools):
    path = AGENTS / f"{name}.md"
    meta, body = split(path)
    assert meta["name"] == name
    assert [t.strip() for t in meta["tools"].split(",")] == tools
    assert meta["skills"] == ["spec-to-code-compliance:spec-to-code-compliance"]
    assert len(path.read_text().splitlines()) <= 80
    assert "Not for" in meta["description"]
    assert "<redacted>" in body


def test_checker_record_fields():
    body = split(AGENTS / "spec-compliance-checker.md")[1]
    for field in ["id:", "verdict:", "confidence:", "analysisFile:", "evidence:", "searched:",
                  "documentProblem:", "reasoning:"]:
        assert f"\n{field}" in body, field
    assert " | ".join(VERDICTS) in body
    assert "Write exactly one file: the path you were given" in body


def test_refuter_record_fields_and_lenses():
    body = split(AGENTS / "divergence-refuter.md")[1]
    for field in ["id:", "lens:", "refuted:", "revisedVerdict:", "correction:", "evidence:"]:
        assert f"\n{field}" in body, field
    assert "## Lens: code" in body and "## Lens: document" in body
    assert "You write no files and run nothing" in body
    assert "Wording differences alone never refute" in body


def test_agent_reference_links_resolve():
    for agent in AGENTS.glob("*.md"):
        for rel in re.findall(r"\]\((\.\./skills/[^)]+\.md)\)", agent.read_text()):
            assert (AGENTS / rel).resolve().is_file(), (agent.name, rel)


def test_manifest_and_marketplace_agree():
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((PLUGIN.parent / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "spec-to-code-compliance")
    assert entry["version"] == plugin["version"] == "1.0.0"
    assert entry["license"] == plugin["license"] == "MIT"
    assert entry["author"] == plugin["author"] == {"name": "Aleksandr Letunov",
                                                   "email": "flypatriotka@gmail.com"}
    assert entry["category"] == "security" and "category" not in plugin
    assert "homepage" not in plugin and "repository" not in plugin


def test_changelog_dated():
    text = (PLUGIN / "CHANGELOG.md").read_text()
    assert "## 2026-11-11" in text and "Unreleased" not in text


def test_eval_cases_present():
    assert {p.name for p in EVALS.iterdir() if (p / "case.yaml").exists()} == {
        "trigger-docs-vs-code", "outcome-readme-guarantees", "negative-bug-hunt"}


def test_skill_graders_scoped():
    for g in EVALS.glob("*/graders/*.md"):
        meta = yaml.safe_load(g.read_text().split("---")[1])
        if meta.get("tool") == "Skill":
            assert "(?:spec-to-code-compliance:)?spec-to-code-compliance" in meta["input_match"], g


def test_fixtures_neutral_and_hookless():
    for setup in EVALS.glob("*/setup.sh"):
        text = setup.read_text()
        assert "git config core.hooksPath /dev/null" in text
        assert re.search(r"^module example\.org/", text, re.M) or "example.org/" in text


@pytest.mark.parametrize("path,flagged", [
    ("/private/tmp/e-Qx81Lm/tmp/claude-501/spec-compliance-cwd-6713003/REPORT.md", False),
    ("/private/tmp/e-Qx81Lm/tmp/spec-compliance-cwd-6713003/requirements/REQ-02.md", False),
    ("/var/folders/ab/xyz/T/spec-compliance-cwd-6713003/REPORT.md", False),
    ("/tmp/spec-compliance-cwd-6713003/requirements/REQ-11.md", False),
    ("/private/tmp/e-Qx81Lm/home/cwd/spec-compliance-cwd-6713003/REPORT.md", True),
    ("/private/tmp/e-Qx81Lm/home/cwd/REPORT.md", True),
    ("/private/tmp/e-Qx81Lm/home/cwd/internal/relay/signature.go", True),
    ("/tmp/spec-compliance-cwd-6713003/REPORT.md.sh", True),
    ("/tmp/spec-compliance-cwd-6713003/notes.md", True),
    ("/tmp/spec-compliance-cwd-6713003/requirements/REQ-02.md/x", True),
])
def test_no_write_exemption_anchored(path, flagged):
    rx = re.compile(grader_meta("outcome-readme-guarantees", "no-write.md")["input_match"])
    assert bool(rx.search(json.dumps({"file_path": path, "content": "x"}))) is flagged


@pytest.mark.parametrize("path,hit", [
    ("/private/tmp/e-Qx81Lm/tmp/claude-501/spec-compliance-cwd-6713003/REPORT.md", True),
    ("/var/folders/ab/xyz/T/spec-compliance-cwd-6713003/REPORT.md", True),
    ("/private/tmp/e-Qx81Lm/home/cwd/spec-compliance-cwd-6713003/REPORT.md", False),
    ("/tmp/spec-compliance-cwd-6713003/requirements/REQ-01.md", False),
])
def test_report_written_regex(path, hit):
    rx = re.compile(grader_meta("outcome-readme-guarantees", "report-written.md")["input_match"])
    assert bool(rx.search(json.dumps({"file_path": path}))) is hit


@pytest.mark.parametrize("grader,agent", [
    ("checker-dispatched.md", "spec-compliance-checker"),
    ("refuter-dispatched.md", "divergence-refuter"),
])
def test_dispatch_graders(grader, agent):
    meta = grader_meta("outcome-readme-guarantees", grader)
    assert meta["tool"] == "Agent" and meta["min"] == 1
    rx = re.compile(meta["input_match"])
    assert rx.search(json.dumps({"subagent_type": f"spec-to-code-compliance:{agent}"}))
    assert not rx.search(json.dumps({"subagent_type": "general-purpose", "prompt": agent}))
