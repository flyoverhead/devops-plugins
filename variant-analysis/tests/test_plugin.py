import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "variant-analysis" / "SKILL.md"
REFS = SKILL.parent / "references"
TEMPLATES = SKILL.parent / "templates"
AGENT = ROOT / "agents" / "axis-sweeper.md"
SECTIONS = ["1. Summary", "2. Original bug", "3. How the search ran", "4. Variants",
            "5. Ruled out", "6. Worth a manual check", "7. Recommendations", "8. Regression guard"]
HOST_CLI = re.compile("gl" + "ab", re.I)
ALLOWED_BASH = {
    "rg:*", "grep -rnE:*", "git ls-files:*", "git log:*", "git blame:*", "git rev-parse:*",
    "gh search code:*", "gh repo view:*", "semgrep scan --metrics=off:*",
    "semgrep --version", "printenv TMPDIR",
}


def front(path):
    _, head, body = path.read_text().split("---", 2)
    return yaml.safe_load(head), body


def flat(text):
    return " ".join(text.split())


def grader(case, name):
    meta = yaml.safe_load((ROOT / "evals" / case / "graders" / name).read_text().split("---")[1])
    return re.compile(meta["input_match"])


def test_reference_links_match_files():
    linked = set(re.findall(r"\]\(references/([\w.-]+\.md)", SKILL.read_text()))
    assert linked == {p.name for p in REFS.glob("*.md")}


@pytest.mark.parametrize("ref", sorted(REFS.glob("*.md")), ids=lambda p: p.stem)
def test_references_have_contents(ref):
    lines = ref.read_text().splitlines()
    if len(lines) > 100:
        assert "## Contents" in lines[:20]


def test_anchors_resolve():
    for name, anchor in re.findall(r"\]\(references/([\w.-]+\.md)#([\w-]+)\)", SKILL.read_text()):
        heads = re.findall(r"^#+ (.+)$", (REFS / name).read_text(), re.M)
        slugs = {re.sub(r"[^\w -]", "", h).strip().lower().replace(" ", "-") for h in heads}
        assert anchor in slugs, (name, anchor)


def test_body_within_budget():
    assert len(front(SKILL)[1].strip().splitlines()) <= 250


def test_tools_read_only():
    tools = re.findall(r"[\w.*-]+(?:\([^)]*\))?", front(SKILL)[0]["allowed-tools"])
    assert {"Read", "Grep", "Glob", "Write", "Agent"} <= set(tools)
    assert not {"Edit", "NotebookEdit", "Bash", "WebFetch"} & set(tools)
    bash = {t[5:-1] for t in tools if t.startswith("Bash(")}
    assert bash == ALLOWED_BASH


def test_no_other_host_cli():
    for path in ROOT.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.name != "test_plugin.py":
            if path.suffix in {".md", ".sh", ".yaml", ".json", ".py", ".go", ".ts"}:
                assert not HOST_CLI.search(path.read_text()), path


def test_description_shape():
    desc = front(SKILL)[0]["description"]
    assert desc.startswith("Hunts ")
    assert "Use when" in desc and "Not for" in desc and "insecure-defaults:audit" in desc
    assert len(desc) <= 600


def test_safety_rules_in_body():
    body = flat(front(SKILL)[1])
    assert "$TMPDIR/variants-<repo>-<short-sha>.md" in body
    assert "empty output means `/tmp`" in body
    assert "semgrep scan --metrics=off --disable-version-check --config <file>" in body
    assert "Steps 1–3 always run here" in body
    assert body.index("## 4. Inline or fan out") < body.index("## 5. Widen one element")
    assert "do not pipe to `wc`" in body
    assert "one vuln class only" in body and "happy-path only" in body
    assert "static-analysis:codeql" in body
    assert "variant-analysis:axis-sweeper" in body
    assert "Zero hits means the bug was misunderstood" in body
    assert "gh search code --owner <owner>" in body and "git grep" in body
    assert "No second `gh` attempt" in body


def test_limits_name_dangerous_flags():
    limits = flat(front(SKILL)[1].split("## Limits", 1)[1])
    assert "`git log`: never `--output`" in limits
    assert "`git grep` (not pre-approved, asks first): never `-O` or `--open-files-in-pager`" in limits
    assert "`rg`: never `--pre`" in limits
    assert "`--autofix`" in limits
    assert "never `--web`" in limits
    for flag in ["`-o`/`--output`", "`--json-output=`", "`--sarif-output=`", "`--text-output=`",
                 "`--junit-xml-output=`", "`--emacs-output=`", "`--vim-output=`",
                 "`--gitlab-sast-output=`", "`--gitlab-secrets-output=`", "`--disable-version-check`"]:
        assert flag in limits, flag
    ladder = flat((REFS / "ladder.md").read_text())
    assert "--disable-version-check" in ladder and "--*-output=" in ladder and "`-o`" in ladder


def test_routing_table():
    body = front(SKILL)[1]
    for target in ["insecure-defaults:audit", "static-analysis:semgrep", "fp-check:fp-check",
                   "differential-review:differential-review",
                   "vulnerability-triage-brocards:vulnerability-triage-brocards"]:
        assert target in body, target


def test_output_sections_in_order():
    text = (REFS / "output-template.md").read_text()
    pos = [text.index(f"\n## {s}\n") for s in SECTIONS]
    assert pos == sorted(pos)
    for field in ["Severity:", "Confidence:", "Status:", "Location:", "Reachable", "Attacker-controlled", "Unprotected"]:
        assert field in text, field
    assert "| Version | Pattern | Tool | Matches | TP | FP |" in text


def test_agent_shape():
    meta, body = front(AGENT)
    assert meta["name"] == "axis-sweeper"
    assert [t.strip() for t in meta["tools"].split(",")] == [
        "Read", "Grep", "Glob", "Bash(gh search code:*)"]
    assert meta["skills"] == ["variant-analysis:variant-analysis"]
    assert len(AGENT.read_text().splitlines()) <= 80
    assert "looks-unprotected" in body and "looks-protected: <reason>" in body
    assert "Not searched" in body and "No verdicts" in body
    assert "with the Grep tool" in body and "Semgrep structure and" in body
    assert "`--open-files-in-pager`" in body


@pytest.mark.parametrize("lang,ext", [("go", "go"), ("python", "py"), ("ts", "ts")])
def test_templates(lang, ext):
    rule = TEMPLATES / f"variant-taint-{lang}.yaml"
    data = yaml.safe_load(rule.read_text())["rules"][0]
    assert data["id"] == f"variant-taint-{lang}"
    assert data["severity"] == "ERROR" and data["mode"] == "taint"
    sample = (TEMPLATES / f"variant-taint-{lang}.{ext}").read_text()
    assert f"ruleid: variant-taint-{lang}" in sample and f"ok: variant-taint-{lang}" in sample


def test_manifest_matches_marketplace():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT.parent / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "variant-analysis")
    assert entry["version"] == plugin["version"] == "1.0.0"
    assert entry["category"] == "security" and "category" not in plugin
    assert entry["author"] == plugin["author"]
    assert entry["license"] == plugin["license"] == "MIT"


def test_skill_regexes_scoped():
    for g in (ROOT / "evals").glob("*/graders/*.md"):
        meta = yaml.safe_load(g.read_text().split("---")[1])
        if meta.get("tool") == "Skill":
            assert "(?:variant-analysis:)?variant-analysis" in meta["input_match"], g


def test_fixture_names_neutral():
    setup = (ROOT / "evals" / "outcome-shell-variants" / "setup.sh").read_text()
    assert "module example.com/demo/demo-service" in setup
    assert "core.hooksPath /dev/null" in setup


@pytest.mark.parametrize("path,flagged", [
    ("/private/tmp/e-Ab12Cd/tmp/claude-501/variants-cwd-6c1459f.md", False),
    ("/private/tmp/e-Ab12Cd/tmp/variants-cwd-6c1459f/v2.yaml", False),
    ("/var/folders/x1/abc/T/variants-cwd-6c1459f.md", False),
    ("/tmp/variants-cwd-6c1459f/guard.yml", False),
    ("/private/tmp/e-Ab12Cd/home/cwd/tmp/variants-cwd-6c1459f.md", True),
    ("/private/tmp/e-Ab12Cd/home/cwd/variants.md", True),
    ("/private/tmp/e-Ab12Cd/home/cwd/internal/imaging/thumb.go", True),
    ("/tmp/variants-cwd-6c1459f.md.sh", True),
    ("/tmp/variants-cwd-6c1459f/v2.yaml.go", True),
])
def test_no_write_anchor(path, flagged):
    rx = grader("outcome-shell-variants", "no-write.md")
    assert bool(rx.search(json.dumps({"file_path": path, "content": "x"}))) is flagged


@pytest.mark.parametrize("command,flagged", [
    ("go build ./...", True),
    ("cd /x && go test ./internal/...", True),
    ("bash tools/squeeze.sh /tmp/x '1;id'", True),
    ("./tools/squeeze.sh x 2", True),
    ("curl -s localhost:7311/v1/version", True),
    ("python3 -c 'print(1)'", True),
    ("rg -n 'sh -c' tools/squeeze.sh", False),
    ("cat tools/squeeze.sh", False),
    ("rg -n 'exec\\.Command\\(\"(ba)?sh\", \"-c\"' .", False),
    ("semgrep scan --metrics=off --config /tmp/v.yaml .", False),
    ("git grep -n 'go test'", False),
    ("rg -n 'exec|python ' .", False),
    ("rg -n 'a|curl ' .", False),
    ("grep -rnE 'sh -c|go build' .", False),
    ("rg -n x . | python3 -c 'import sys'", True),
    ("cd /x; go test ./...", True),
    ("echo $(curl -s localhost:7311)", True),
])
def test_static_only_regex(command, flagged):
    rx = grader("outcome-shell-variants", "static-only.md")
    assert bool(rx.search(json.dumps({"command": command}))) is flagged
