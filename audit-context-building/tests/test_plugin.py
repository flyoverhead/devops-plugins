import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "audit-context-building"
SKILL = SKILL_DIR / "SKILL.md"
REFS = SKILL_DIR / "references"
AGENT = ROOT / "agents" / "function-analyzer.md"
EVALS = ROOT / "evals"
RECORD_KEYS = ["function", "file", "analysisFile", "invariants", "assumptions", "calls",
               "callers", "sharedState", "openQuestions"]
DOSSIER_SECTIONS = ["State map", "Flows", "Actor reach", "Complexity hotspots",
                    "Cross-unit invariants", "Disagreements", "Unenforced assumptions",
                    "Open questions", "Not analysed"]
PROSE_SECTIONS = ["## Purpose", "## Inputs and assumptions", "## Outputs and effects", "## Walk",
                  "## Dependencies", "## Open questions"]
SHELL = {"git ls-files:*", "git rev-parse:*", "git log:*", "printenv TMPDIR"}
SKILL_RX = "(?:audit-context-building:)?audit-context-building"


def parts(path):
    _, front, body = path.read_text().split("---", 2)
    return yaml.safe_load(front), body


def flat(text):
    return " ".join(text.split())


def grader(case, name):
    return yaml.safe_load((EVALS / case / "graders" / name).read_text().split("---")[1])


def matches(case, name, payload):
    return bool(re.search(grader(case, name)["input_match"], json.dumps(payload)))


def test_frontmatter_and_size():
    meta, body = parts(SKILL)
    assert meta["name"] == "audit-context-building"
    assert len(body.strip().splitlines()) <= 250
    desc = meta["description"]
    assert desc.startswith("Maps ") and len(desc) <= 600
    assert "Use when" in desc and desc.endswith("Not for hunting bugs or insecure values — use insecure-defaults:audit.")


def test_tools_are_read_only():
    tokens = re.findall(r"[\w.*-]+(?:\([^)]*\))?", parts(SKILL)[0]["allowed-tools"])
    assert {"Read", "Grep", "Glob", "Write", "Agent"} <= set(tokens)
    assert not {"Bash", "Edit", "NotebookEdit", "WebFetch", "WebSearch"} & set(tokens)
    assert {t[5:-1] for t in tokens if t.startswith("Bash(")} == SHELL


def test_limits_name_forbidden_git_log_flag():
    limits = flat(parts(SKILL)[1].split("## Limits", 1)[1])
    assert "`git log` is allowed for history only; never pass `--output`" in limits


def test_no_other_code_host_cli():
    banned = re.compile("gl" + "ab", re.I)
    for path in ROOT.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.suffix in {".md", ".sh", ".json", ".yaml", ".py"}:
            assert not banned.search(path.read_text()), path
    assert "gh " not in parts(SKILL)[0]["allowed-tools"]


def test_references_linked_and_resolvable():
    body = SKILL.read_text()
    assert set(re.findall(r"\(references/([\w.-]+\.md)", body)) == {p.name for p in REFS.iterdir()}
    for name, anchor in re.findall(r"\(references/([\w.-]+\.md)#([\w-]+)\)", body):
        heads = re.findall(r"^#+ (.+)$", (REFS / name).read_text(), re.M)
        assert anchor in {re.sub(r"[^\w -]", "", h).strip().lower().replace(" ", "-") for h in heads}
    for ref in REFS.glob("*.md"):
        lines = ref.read_text().splitlines()
        assert len(lines) <= 100 or "## Contents" in lines[:12], ref.name


def test_stages_in_order():
    body = parts(SKILL)[1]
    heads = ["## Stage 1. Orient", "## Stage 2. Analyze", "## Stage 3. Synthesize",
             "## Stage 4. Hand over", "## Limits"]
    pos = [body.index(h) for h in heads]
    assert pos == sorted(pos)


@pytest.mark.parametrize("phrase", [
    "`printenv TMPDIR` gives the temp root; if it prints nothing, use `/tmp`",
    "`<tmp>/audit-context-<repo>-<sha>/`",
    "`git rev-parse --short HEAD`",
    "`<tmp>/audit-context-<dirname>-nogit/`",
    "`functions/NN-<name>.md`",
    "Keep the 12 top units",
    "that unit alone is analysed",
    "Dispatch `audit-context-building:function-analyzer`",
    "**This is not optional**",
    "At most 5 agents run at once",
    "Do not analyse the remaining units inline as a substitute.",
    "never dispatch further agents",
    "`nothing found`",
    "<redacted>",
    "Write the dossier before replying",
    "never the literal `$TMPDIR`",
    "`Not analysed:` the list, or `nothing`",
    "No verdicts.",
])
def test_skill_states(phrase):
    assert phrase in flat(parts(SKILL)[1])


def test_brief_carries_paths():
    body = parts(SKILL)[1]
    for key in ["repoRoot:", "tmpRoot:", "unit:", "why:", "orientation:", "output:"]:
        assert f"\n{key}" in body, key


def test_routing_and_next_phase():
    body = parts(SKILL)[1]
    for target in ["insecure-defaults:audit", "static-analysis:semgrep",
                   "variant-analysis:variant-analysis", "sharp-edges:sharp-edges",
                   "differential-review:differential-review", "golang:review"]:
        assert target in body, target


def test_record_format_has_every_key():
    text = (REFS / "records.md").read_text()
    record = text.split("## Returned record", 1)[1].split("## Dossier", 1)[0]
    for key in RECORD_KEYS:
        assert f"\n{key}:" in record, key
    for kind in ["internal", "external-source-available", "external-black-box"]:
        assert f"| {kind} |" in record
    assert "unclear; need to inspect" in record and "| nothing found" in record


def test_dossier_sections_in_order():
    dossier = (REFS / "records.md").read_text().split("## Dossier", 1)[1]
    pos = [dossier.index(f"`## {s}`") for s in DOSSIER_SECTIONS]
    assert pos == sorted(pos)


def test_prose_sections_in_order():
    prose = (REFS / "records.md").read_text().split("## Prose file", 1)[1].split("## Returned record", 1)[0]
    pos = [prose.index(f"`{s}`") for s in PROSE_SECTIONS]
    assert pos == sorted(pos)


def test_stacks_cover_every_stack():
    text = (REFS / "stacks.md").read_text()
    for head in ["## Go and Python services", "## TypeScript", "## CLIs and Bash", "## Ansible",
                 "## Terraform", "## GitLab CI"]:
        assert head in text
    assert "`set -e` does nothing" in text and "establishes nothing" in text


def test_agent_shape():
    meta, body = parts(AGENT)
    assert meta["name"] == "function-analyzer"
    assert [t.strip() for t in meta["tools"].split(",")] == ["Read", "Grep", "Glob", "Write"]
    assert meta["skills"] == ["audit-context-building:audit-context-building"]
    assert "Not for" in meta["description"]
    assert len(AGENT.read_text().splitlines()) <= 80
    for key in RECORD_KEYS:
        assert f"\n{key}:" in body, key
    assert "Write exactly one file, `output`" in body
    assert "Never dispatch agents" in body
    assert "<redacted>" in body


def refusal_section():
    return flat(parts(AGENT)[1].split("## Check the output path first", 1)[1].split("## Method", 1)[0])


def test_agent_refuses_bad_paths():
    section = refusal_section()
    assert "`tmpRoot` is missing or empty in the brief" in section
    assert "`output` is not `<tmpRoot>/audit-context-<dir>/functions/NN-<name>.md`" in section
    assert "`output` starts with `repoRoot` + `/`" in section
    assert "contains `..`" in section
    assert "`/tmp/`" not in section and "`/private/tmp/`" not in section
    assert "`refused: <reason, quoting the path>`" in section


def test_agent_normalises_trailing_slash():
    assert "strip trailing `/`" in refusal_section()


def test_agent_normalises_private_prefix():
    section = refusal_section()
    assert "then a leading `/private`" in section and "Compare only the normalised forms" in section


def test_skill_strips_trailing_slash_from_tmp_root():
    body = flat(parts(SKILL)[1])
    assert "Strip trailing slashes from it (macOS `$TMPDIR` ends in `/`)" in body
    assert "tmpRoot: <resolved temp root, no trailing slash; required>" in body


def norm(path):
    path = path.rstrip("/")
    return path[len("/private"):] if path.startswith("/private/") else path


def accepts(output, tmp_root, repo_root):
    if not tmp_root:
        return False
    out, tmp, repo = norm(output), norm(tmp_root), norm(repo_root)
    if not out.startswith("/") or ".." in out or out.startswith(repo + "/"):
        return False
    return re.fullmatch(re.escape(tmp) + r"/audit-context-[^/]+/functions/\d{2}-[a-z0-9.-]+\.md", out) is not None


@pytest.mark.parametrize("output,tmp_root,repo_root,ok", [
    ("/var/folders/q1/zz/T/audit-context-x-1a2b3c4/functions/01-enqueue.md", "/var/folders/q1/zz/T/", "/Users/u/src/x", True),
    ("/private/tmp/e-1/tmp/audit-context-cwd-nogit/functions/02-quota.md", "/tmp/e-1/tmp", "/private/tmp/e-1/home/cwd", True),
    ("/tmp/e-1/tmp/audit-context-cwd-1a2b3c4/functions/03-a.md", "/private/tmp/e-1/tmp/", "/tmp/e-1/home/cwd/", True),
    ("/tmp/audit-context-x-1a2b3c4/functions/01-a.md", "", "/Users/u/src/x", False),
    ("/tmp/notes/functions/01-a.md", "/tmp", "/Users/u/src/x", False),
    ("/tmp/audit-context-x-1a2b3c4/DOSSIER.md", "/tmp", "/Users/u/src/x", False),
    ("/tmp/audit-context-x/functions/1-a.md", "/tmp", "/Users/u/src/x", False),
    ("/private/tmp/e-1/home/cwd/audit-context-x/functions/01-a.md", "/tmp/e-1/home/cwd", "/tmp/e-1/home/cwd/", False),
    ("/tmp/audit-context-x/../functions/01-a.md", "/tmp", "/Users/u/src/x", False),
])
def test_refusal_rule_examples(output, tmp_root, repo_root, ok):
    assert accepts(output, tmp_root, repo_root) is ok


def test_agent_links_resolve():
    for rel in re.findall(r"\]\((\.\./skills/[^)#]+\.md)", AGENT.read_text()):
        assert (AGENT.parent / rel).resolve().is_file(), rel


def test_manifest_matches_marketplace():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT.parent / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "audit-context-building")
    assert entry["version"] == plugin["version"] == "1.0.0"
    assert entry["license"] == plugin["license"] == "MIT"
    assert entry["author"] == plugin["author"] == {"name": "Aleksandr Letunov", "email": "flypatriotka@gmail.com"}
    assert entry["category"] == "security" and "category" not in plugin
    assert not {"homepage", "repository"} & plugin.keys()


def test_changelog():
    text = (ROOT / "CHANGELOG.md").read_text()
    assert text.startswith("# Changelog\n\n## 2026-11-11\n\n### Added") and "Unreleased" not in text


def test_eval_cases():
    assert {p.name for p in EVALS.iterdir() if (p / "case.yaml").exists()} == {
        "trigger-unfamiliar-service", "outcome-callee-branch", "negative-variant-hunt"}
    for g in EVALS.glob("*/graders/*.md"):
        meta = grader(g.parts[-3], g.name)
        if meta.get("tool") == "Skill":
            assert SKILL_RX in meta["input_match"], g


def test_fixtures_neutral_and_hookless():
    for setup in EVALS.glob("*/setup.sh"):
        text = setup.read_text()
        assert "git config core.hooksPath /dev/null" in text
        assert "module example.org/" in text


@pytest.mark.parametrize("payload,hit", [
    ({"file_path": "/tmp/audit-context-cwd-1a2b3c4/functions/01-enqueue.md",
      "content": "recipientQuota returns n unchanged when plan == \"enterprise\"; no maxRecipients check"}, True),
    ({"content": "recipientQuota enterprise maxRecipients",
      "file_path": "/tmp/audit-context-cwd-1a2b3c4/functions/02-quota.md"}, True),
    ({"file_path": "/tmp/audit-context-cwd-1a2b3c4/functions/01-enqueue.md",
      "content": "admitFanout caps at maxRecipients"}, False),
    ({"file_path": "/tmp/audit-context-cwd-1a2b3c4/DOSSIER.md",
      "content": "recipientQuota enterprise maxRecipients"}, False),
])
def test_analyzer_notes_grader(payload, hit):
    meta = grader("outcome-callee-branch", "analyzer-notes.md")
    assert meta["tool"] == "Write" and meta["min"] == 1 and meta["arm"] == "with-only"
    assert matches("outcome-callee-branch", "analyzer-notes.md", payload) is hit


def test_analyzer_grader():
    meta = grader("outcome-callee-branch", "analyzer-dispatched.md")
    assert meta["tool"] == "Agent" and meta["min"] == 1 and meta["arm"] == "with-only"
    assert matches("outcome-callee-branch", "analyzer-dispatched.md",
                   {"subagent_type": "audit-context-building:function-analyzer"})
    assert not matches("outcome-callee-branch", "analyzer-dispatched.md",
                       {"subagent_type": "general-purpose", "prompt": "function-analyzer"})


@pytest.mark.parametrize("path,flagged", [
    ("/private/tmp/e-Ab12/tmp/audit-context-cwd-1a2b3c4/DOSSIER.md", False),
    ("/private/tmp/e-Ab12/tmp/claude-501/audit-context-cwd-1a2b3c4/functions/01-enqueue.md", False),
    ("/var/folders/q1/zz/T/audit-context-cwd-nogit/functions/12-recipientquota.md", False),
    ("/tmp/audit-context-cwd-1a2b3c4-2/DOSSIER.md", False),
    ("/private/tmp/e-Ab12/home/cwd/audit-context-cwd-1a2b3c4/DOSSIER.md", True),
    ("/private/tmp/e-Ab12/home/cwd/DOSSIER.md", True),
    ("/private/tmp/e-Ab12/home/cwd/internal/digest/fanout.go", True),
    ("/tmp/audit-context-cwd-1a2b3c4/DOSSIER.md.sh", True),
    ("/tmp/audit-context-cwd-1a2b3c4/notes.md", True),
    ("/tmp/audit-context-cwd-1a2b3c4/functions/1-enqueue.md", True),
    ("/tmp/audit-context-cwd-1a2b3c4/functions/01-enqueue.md/x", True),
])
def test_no_write_exemption_anchored(path, flagged):
    assert matches("outcome-callee-branch", "no-write.md", {"file_path": path, "content": "x"}) is flagged


@pytest.mark.parametrize("path,hit", [
    ("/private/tmp/e-Ab12/tmp/audit-context-cwd-1a2b3c4/DOSSIER.md", True),
    ("/var/folders/q1/zz/T/audit-context-cwd-nogit/functions/01-enqueue.md", True),
    ("/private/tmp/e-Ab12/home/cwd/audit-context-cwd-1a2b3c4/DOSSIER.md", False),
])
def test_notes_in_tmpdir(path, hit):
    assert matches("outcome-callee-branch", "notes-in-tmpdir.md", {"file_path": path}) is hit
