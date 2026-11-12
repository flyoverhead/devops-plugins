import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SKILL_DIR = ROOT / "skills" / "mutation-testing"
SKILL = SKILL_DIR / "SKILL.md"
REFS = SKILL_DIR / "references"
EVALS = ROOT / "evals"
CASES = {"trigger-gremlins-survivors", "negative-line-coverage", "outcome-weak-suite-analysis"}
OUTCOME = "outcome-weak-suite-analysis"
SKILL_RX = "(?:mutation-testing:)?mutation-testing"
SHELL = {"command -v:*", "mewt status:*", "mewt results:*", "mewt print:*", "muton status:*",
         "muton results:*", "muton print:*", "mutmut results:*"}
GATED = ("init", "mutate", "run", "test", "purge", "gremlins unleash", "mutmut run", "npx stryker run")


def parts(path):
    _, front, body = path.read_text().split("---", 2)
    return yaml.safe_load(front), body


def flat(text):
    return " ".join(text.split())


def grader(case, name):
    return yaml.safe_load((EVALS / case / "graders" / name).read_text().split("---")[1])


def grader_body(case, name):
    return (EVALS / case / "graders" / name).read_text().split("---", 2)[2].strip()


def matches(case, name, payload):
    return bool(re.search(grader(case, name)["input_match"], json.dumps(payload)))


def test_frontmatter():
    meta, body = parts(SKILL)
    assert meta["name"] == "mutation-testing"
    assert len(body.strip().splitlines()) <= 250
    desc = meta["description"]
    assert desc.startswith("Sorts ") and "Use when" in desc and "Not for" in desc
    assert desc.endswith("use property-based-testing:property-based-testing.")
    assert "line coverage (answer directly)" in desc
    for tool in ("mewt", "muton", "gremlins", "mutmut", "Stryker"):
        assert tool in desc


def test_allowed_tools_read_only():
    tokens = re.findall(r"[\w.*-]+(?:\([^)]*\))?", parts(SKILL)[0]["allowed-tools"])
    assert {t for t in tokens if not t.startswith("Bash(")} == {"Read", "Write", "Grep", "Glob"}
    assert {t[5:-1] for t in tokens if t.startswith("Bash(")} == SHELL | {"printenv TMPDIR"}
    joined = " ".join(tokens)
    for gated in ("unleash", "mutmut run", "stryker", "npx", "mewt run", "mewt test", "mewt init",
                  "mewt mutate", "purge", "gh ", "Edit", "Agent"):
        assert gated not in joined


def test_gates_present():
    body = flat(parts(SKILL)[1])
    for needle in ("explicit yes", "Never run it", "time estimate", "shared database", "One yes, one command",
                   "`mewt purge`", "deliberately not pre-approved"):
        assert needle in body, needle
    for cmd in GATED:
        assert f"`{cmd}`" in body, cmd


def test_limits_section():
    limits = flat(parts(SKILL)[1].split("## Limits", 1)[1])
    assert "read-only" in limits and "`tee`" in limits and "Never install" in limits
    for cmd in GATED:
        assert f"`{cmd}`" in limits


def test_routing():
    body = flat(parts(SKILL)[1])
    assert "| line or branch coverage with no mutants in sight | not this skill; answer directly" in body
    assert "| write new property-based tests | `property-based-testing:property-based-testing` |" in body
    assert "| review Go code with no mutation data | `golang:review` |" in body


def test_tool_table_and_cli_facts():
    body = parts(SKILL)[1]
    for fact in ("gremlins unleash ./...", "--output results.json", '`include = ["**/*.go"]`',
                 "`mutmut run`", "`mutmut results`", "npx stryker run", "reports/mutation/mutation.json",
                 "mewt results --format json", "muton.toml", "muton.sqlite", "--help"):
        assert fact in body, fact
    card = (REFS / "campaign-setup.md").read_text()
    for fact in ("mewt print mutant --id N", "--ids-file", "--severity high,medium", "--mutation-types ER,CR",
                 "--status Uncaught", "--line 42", "mewt print mutations --language", "move/sui",
                 "mewt purge --all", "[[per_target]]", "--config"):
        assert fact in card, fact


def test_analysis_rules():
    text = flat((REFS / "survivor-analysis.md").read_text())
    for needle in ("all five checks", "unresolved", "Never default an unresolved case", "no input reaches it",
                   "| 1 Critical |", "| 2 High |", "| 3 Medium |", "| 4 Low |", "Tie-breakers",
                   "denominator", "24/32 = 75.0 %", "24/30 = 80.0 %", "Excuses to refuse"):
        assert needle in text, needle
    for slug_row in ("| ER (high) |", "| CR (medium) |", "| IF / IT (medium) |"):
        assert slug_row in parts(SKILL)[1]


def test_report_layout_sections():
    text = (REFS / "report-layout.md").read_text()
    for head in ("## Executive Summary", "## Equivalent Mutants", "## Tier 1: Critical", "## Tier 4: Low",
                 "## Recommendations", "## Unresolved Cases", "## Appendix", "Adjusted kill rate"):
        assert head in text
    for ident in ("C-n", "H-n", "M-n", "L-n"):
        assert ident in text


def test_bug_hunt_classes():
    text = flat((REFS / "bug-hunt.md").read_text())
    for cls in ("| confirmed |", "| likely |", "| dead code |", "| not a bug |"):
        assert cls in text
    assert "never in the repository" in text


def test_references_linked_and_toc():
    body = SKILL.read_text()
    assert set(re.findall(r"\(references/([\w.-]+\.md)", body)) == {p.name for p in REFS.iterdir()}
    for name, anchor in re.findall(r"\(references/([\w.-]+\.md)#([\w-]+)\)", body):
        heads = re.findall(r"^#+ (.+)$", (REFS / name).read_text(), re.M)
        assert anchor in {re.sub(r"[^\w -]", "", h).strip().lower().replace(" ", "-") for h in heads}
    for ref in REFS.glob("*.md"):
        lines = ref.read_text().splitlines()
        assert len(lines) <= 100 or "## Contents" in lines[:12], ref.name


def test_manifest_marketplace_claude_md():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["version"] == "1.0.0" and plugin["license"] == "MIT"
    assert plugin["author"] == {"name": "Aleksandr Letunov", "email": "flypatriotka@gmail.com"}
    assert not {"category", "homepage", "repository"} & set(plugin)
    entry = next(p for p in json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())["plugins"]
                 if p["name"] == plugin["name"])
    assert entry["category"] == "security" and entry["source"] == "./mutation-testing"
    for key in ("version", "description", "author", "license", "keywords"):
        assert entry[key] == plugin[key]
    assert "| `mutation-testing` | `mutation-testing` | |" in (REPO / "CLAUDE.md").read_text()


def test_changelog():
    text = (ROOT / "CHANGELOG.md").read_text()
    assert text.startswith("# Changelog\n\n## 2026-11-11\n\n### Added")
    assert "Unreleased" not in text


def test_no_other_code_host_cli_or_origin_words():
    banned = re.compile("gl" + "ab|trail" + r"\s*of\s*bits|" + "|".join(w + "ed " + p for w, p in
                        (("port", "from"), ("bas", "on"), ("inspir", "by"))), re.I)
    for path in ROOT.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.suffix in {".md", ".sh", ".json", ".yaml", ".py"}:
            assert not banned.search(path.read_text()), path


def test_eval_cases():
    assert {p.name for p in EVALS.iterdir() if p.is_dir() and p.name != "results"} == CASES
    for case in CASES:
        setup = (EVALS / case / "setup.sh").read_text()
        assert "core.hooksPath /dev/null" in setup
        assert "vault" not in setup.lower()
    assert "example.org/pantry" in (EVALS / "trigger-gremlins-survivors" / "setup.sh").read_text()
    assert (EVALS / "trigger-gremlins-survivors" / "setup.sh").read_text() == \
        (EVALS / "negative-line-coverage" / "setup.sh").read_text()


def test_skill_regexes_scoped():
    for case, name in [("trigger-gremlins-survivors", "skill-fired.md"), (OUTCOME, "skill-fired.md"),
                       ("negative-line-coverage", "not-fired.md")]:
        assert SKILL_RX in grader(case, name)["input_match"]
        assert matches(case, name, {"skill": "mutation-testing"})
        assert matches(case, name, {"skill": "mutation-testing:mutation-testing"})
        assert not matches(case, name, {"skill": "property-based-testing:property-based-testing"})
        assert not matches(case, name, {"skill": "xmutation-testing"})
    neg = grader("negative-line-coverage", "not-fired.md")
    assert neg["max"] == 0 and neg["arm"] == "both"


REPORT_OK = [
    "/private/tmp/e-Ab12/tmp/claude-501/mutation-testing-cwd-1/mutation-testing-report.md",
    "/tmp/mutation-testing-faregate-3/mutation-testing-report.md",
    "/var/folders/q1/zz/T/mutation-testing-cwd-2/mutation-testing-report.md",
]
OUTSIDE = [
    "/private/tmp/e-Ab12/home/cwd/mutation-testing-report.md",
    "/private/tmp/e-Ab12/home/cwd/src/lib.rs",
    "/private/tmp/e-Ab12/home/cwd/tests/gate.rs",
    "/private/tmp/e-Ab12/home/cwd/mewt-results.json",
    "/private/tmp/e-Ab12/tmp/claude-501/mutation-testing-cwd-1/../../../home/cwd/src/lib.rs",
    "/private/tmp/e-Ab12/tmp/claude-501/mutation-testing-cwd-1/..",
    "/private/tmp/e-Ab12/home/cwd/tmp/mutation-testing-cwd-1/mutation-testing-report.md",
    "/tmp/e-Ab12/home/cwd/mutation-testing-cwd-1/mutation-testing-report.md",
    "/private/tmp/e-Ab12/tmp/claude-501/mutation-testing-cwd/mutation-testing-report.md",
    "/Users/me/repo/mutation-testing-report.md",
]


@pytest.mark.parametrize("name", ["no-write.md", "no-edit.md"])
@pytest.mark.parametrize("path,flagged", [(p, False) for p in REPORT_OK] + [(p, True) for p in OUTSIDE])
def test_write_and_edit_exemptions_anchored(name, path, flagged):
    assert matches(OUTCOME, name, {"file_path": path, "content": "x"}) is flagged


@pytest.mark.parametrize("path,write_flagged,edit_flagged", [
    ("/private/tmp/e-Ab12/tmp/claude-501/mutation-testing-cwd-1/notes/progress.md", False, True),
    ("/private/tmp/e-Ab12/tmp/claude-501/mutation-testing-cwd-1/mutation-testing-report.md.bak", False, True),
    ("/private/tmp/e-Ab12/tmp/claude-501/notes.md", True, True),
    ("/private/tmp/e-Ab12/tmp/claude-501/mutation-testing-cwd-1/.hidden", True, True),
])
def test_scratch_only_inside_report_dir(path, write_flagged, edit_flagged):
    assert matches(OUTCOME, "no-write.md", {"file_path": path}) is write_flagged
    assert matches(OUTCOME, "no-edit.md", {"file_path": path}) is edit_flagged


@pytest.mark.parametrize("path,hit", [(p, True) for p in REPORT_OK] + [(p, False) for p in OUTSIDE])
def test_report_written_grader(path, hit):
    meta = grader(OUTCOME, "report-written.md")
    assert meta["type"] == "tool_used" and meta["tool"] == "Write" and meta["min"] == 1
    assert matches(OUTCOME, "report-written.md", {"file_path": path, "content": "x"}) is hit


def test_outcome_content_graders():
    path = REPORT_OK[0]
    def hit(name, content, file_path=path):
        return matches(OUTCOME, name, {"file_path": file_path, "content": content})
    assert hit("boundary-pair.md", "`!= 0` is equivalent ... `rides_left >= 0` is real")
    assert hit("boundary-pair.md", "x >=0 then y != 0")
    assert not hit("boundary-pair.md", "only `!= 0` here")
    assert not hit("boundary-pair.md", "x >= 0 and y != 0", OUTSIDE[0])
    assert hit("names-blocked-guard.md", "IF on `card.blocked`")
    assert not hit("names-blocked-guard.md", "IF on `card.blocked`", OUTSIDE[0])
    assert grader(OUTCOME, "classification.md")["weight"] == 2
    for name in ("classification.md", "test-advice.md", "statistics.md"):
        assert grader(OUTCOME, name)["type"] == "llm"
        assert "gate.refused.push(card.id);" in grader_body(OUTCOME, name)
    assert "`gate.refused`" in grader_body(OUTCOME, "test-advice.md")
    assert "22/31" in grader_body(OUTCOME, "statistics.md") and "22/30" in grader_body(OUTCOME, "statistics.md")


def test_report_lives_outside_repo():
    body = flat(parts(SKILL)[1])
    assert "`$TMPDIR/mutation-testing-<repo>-N/mutation-testing-report.md`" in body
    assert "Never inside the repository" in body
    assert "in the working directory" not in (REFS / "report-layout.md").read_text()


def test_outcome_fixture_matches_results(tmp_path):
    subprocess.run(["bash", str(EVALS / OUTCOME / "setup.sh")], cwd=tmp_path, check=True, capture_output=True)
    src = (tmp_path / "src" / "lib.rs").read_bytes()
    lines = src.decode().splitlines()
    results = json.loads((tmp_path / "mewt-results.json").read_text())["results"]
    assert len(results) == 9
    assert "eprintln" not in src.decode() and "pub refused: Vec<u32>," in src.decode()
    assert {r["mutant"]["line_offset"] for r in results} == {23, 24, 25, 32, 33, 36, 42, 47}
    for r in results:
        m = r["mutant"]
        assert src[m["byte_offset"]:m["byte_offset"] + len(m["old_text"].encode())].decode() == m["old_text"]
        assert m["old_text"] in lines[m["line_offset"] - 1]
        assert r["outcome"]["status"] == "Uncaught"
    status = (tmp_path / "mewt-status.txt").read_text()
    assert "total=37 tested=31 untested=6" in status and "caught=22 uncaught=9" in status


def test_gremlins_fixture_columns(tmp_path):
    subprocess.run(["bash", str(EVALS / "trigger-gremlins-survivors" / "setup.sh")], cwd=tmp_path,
                   check=True, capture_output=True)
    lines = (tmp_path / "pkg/shelf/life.go").read_text().splitlines()
    for loc, token in (("13:15", "<="), ("13:28", "+"), ("18:20", "+"), ("18:28", "-")):
        ln, col = map(int, loc.split(":"))
        assert lines[ln - 1].expandtabs(1)[col - 1:col - 1 + len(token)] == token, loc
    assert "LIVED" in (tmp_path / "gremlins.txt").read_text()
