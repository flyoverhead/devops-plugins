import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SKILL_DIR = ROOT / "skills" / "property-based-testing"
SKILL = SKILL_DIR / "SKILL.md"
REFS = SKILL_DIR / "references"
EVALS = ROOT / "evals"
CASES = ["trigger-whole-input-domain", "outcome-go-money-no-deps", "negative-benchmark"]
OUTCOME = "outcome-go-money-no-deps"
SKILL_RX = "(?:property-based-testing:)?property-based-testing"
SHELL = {"go test:*", "go vet:*", "rg:*",
         "git ls-files:*", "git rev-parse:*"}


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
    assert meta["name"] == "property-based-testing"
    assert meta["effort"] == "low"
    assert len(body.strip().splitlines()) <= 250
    desc = meta["description"]
    assert desc.startswith("Turns ") and len(desc) <= 700
    assert "Use when" in desc and "Not for" in desc
    assert desc.endswith("use golang:test.")
    assert "mutation-testing:mutation-testing" in desc


def test_tools_have_no_bare_bash_or_gh():
    tokens = re.findall(r"[\w.*-]+(?:\([^)]*\))?", parts(SKILL)[0]["allowed-tools"])
    assert not {"Bash", "NotebookEdit", "WebFetch", "WebSearch", "Agent"} & set(tokens)
    assert {t[5:-1] for t in tokens if t.startswith("Bash(")} == SHELL
    assert not any(t.startswith("Bash(gh") or t.startswith("Bash(npx") for t in tokens)
    assert not any("pytest" in t for t in tokens)


def test_limits_list_forbidden_flags():
    limits = flat(parts(SKILL)[1].split("## Limits", 1)[1])
    for flag in ("-exec", "-toolexec", "-overlay", "-o", "-c", "-vettool", "-mod=mod", "-modfile",
                 "-coverprofile", "-cpuprofile", "-memprofile", "-blockprofile", "-mutexprofile",
                 "-trace", "-outputdir", "-fuzzcachedir", "-p", "--basetemp"):
        assert f"`{flag}`" in limits
    assert "`--pre`" in limits
    assert "`-O`" in limits and "`--open-files-in-pager`" in limits


def test_references_linked_and_anchors_resolve():
    body = SKILL.read_text()
    assert set(re.findall(r"\(references/([\w.-]+\.md)", body)) == {p.name for p in REFS.iterdir()}
    for name, anchor in re.findall(r"\(references/([\w.-]+\.md)#([\w-]+)\)", body):
        heads = re.findall(r"^#+ (.+)$", (REFS / name).read_text(), re.M)
        assert anchor in {re.sub(r"[^\w -]", "", h).strip().lower().replace(" ", "-") for h in heads}
    heads = {re.sub(r"[^\w -]", "", h).strip().lower().replace(" ", "-")
             for h in re.findall(r"^#+ (.+)$", body, re.M)}
    for anchor in re.findall(r"\]\(#([\w-]+)\)", body):
        assert anchor in heads
    for ref in REFS.glob("*.md"):
        lines = ref.read_text().splitlines()
        assert len(lines) <= 100 or "## Contents" in lines[:12], ref.name


def test_three_jobs_and_gate_present():
    body = flat(parts(SKILL)[1])
    for needle in ("## Job 1: write", "## Job 2: review", "## Job 3: triage", "## Dependency gate"):
        assert needle in body
    for needle in ("Offer it once", "never edit `go.mod`", "`go get`", "`pip install`",
                   "`npm install`", "A failing property is a finding"):
        assert needle in body


def test_routing_and_libraries():
    body = flat(parts(SKILL)[1])
    assert "`mutation-testing:mutation-testing`" in body and "`golang:test`" in body
    for lib in ("native fuzz", "pgregory.net/rapid", "Hypothesis", "fast-check"):
        assert lib in body
    for banned in ("gopter", "proptest", "jqwik", "Echidna", "Medusa"):
        assert banned not in body


def test_review_severities_complete():
    text = (REFS / "review-and-triage.md").read_text()
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        assert f"| {sev} |" in text
    for cls in ("code bug", "wrong property", "strategy artifact", "ambiguous"):
        assert cls in text


def test_library_idioms_present():
    text = (REFS / "libraries.md").read_text()
    assert "f.Add" in text and "-fuzztime" in text and "rapid.Check" in text
    assert "@given" in text and "fc.assert" in text


def test_no_other_code_host_cli():
    banned = re.compile("gl" + "ab", re.I)
    for path in ROOT.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.suffix in {".md", ".sh", ".json", ".yaml", ".py"}:
            assert not banned.search(path.read_text()), path


def test_manifest_and_marketplace_in_sync():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["version"] == "1.0.0" and plugin["license"] == "MIT"
    assert plugin["author"] == {"name": "Aleksandr Letunov", "email": "flypatriotka@gmail.com"}
    assert not {"category", "homepage", "repository"} & set(plugin)
    entry = next(p for p in json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())["plugins"]
                 if p["name"] == plugin["name"])
    assert entry["category"] == "security"
    for key in ("version", "description", "author", "license", "keywords"):
        assert entry[key] == plugin[key]
    assert "property-based-testing" in (REPO / "CLAUDE.md").read_text()


def test_changelog_shape():
    text = (ROOT / "CHANGELOG.md").read_text()
    assert text.startswith("# Changelog\n\n## 2026-11-11\n\n### Added")
    assert "Unreleased" not in text


def test_eval_case_set_and_fixtures():
    assert sorted(p.name for p in EVALS.iterdir() if p.is_dir() and p.name != "results") == sorted(CASES)
    for case in CASES:
        setup = (EVALS / case / "setup.sh").read_text()
        assert "core.hooksPath /dev/null" in setup
        assert "module example.org/ledgerlib" in setup
        assert "require" not in setup


def test_skill_regexes_scoped():
    for case, name in [(CASES[0], "skill-fired.md"), (OUTCOME, "skill-fired.md"), ("negative-benchmark", "not-fired.md")]:
        rx = grader(case, name)["input_match"]
        assert SKILL_RX in rx
        assert matches(case, name, {"skill": "property-based-testing"})
        assert matches(case, name, {"skill": "property-based-testing:property-based-testing"})
        assert not matches(case, name, {"skill": "mutation-testing:mutation-testing"})
        assert not matches(case, name, {"skill": "xproperty-based-testing"})


@pytest.mark.parametrize("name", ["no-edit-source.md", "no-write.md"])
@pytest.mark.parametrize("path,flagged", [
    ("/private/tmp/e-Ab12/cwd/amount_prop_test.go", False),
    ("/tmp/e-Ab12/cwd/pkg/codec_prop_test.go", False),
    ("/var/folders/q1/zz/T/e-Ab12/cwd/amount_prop_test.go", False),
    ("/private/tmp/e-Ab12/cwd/amount.go", True),
    ("/private/tmp/e-Ab12/cwd/amount_test.go.bak", True),
    ("/private/tmp/e-Ab12/cwd/go.mod", True),
    ("/private/tmp/e-Ab12/cwd/../../x/amount_test.go", True),
    ("/home/u/e-Ab12/cwd/amount_test.go", True),
    ("/Users/me/real/amount_test.go", True),
    ("/private/tmp/elsewhere/amount_test.go", True),
])
def test_write_and_edit_exemptions_anchored(name, path, flagged):
    assert matches(OUTCOME, name, {"file_path": path, "content": "x"}) is flagged


@pytest.mark.parametrize("path,flagged", [
    ("/p/go.mod", True), ("/p/sub/go.sum", True), ("/p/amount.go", False),
])
def test_manifest_edit_grader(path, flagged):
    assert matches(OUTCOME, "no-edit-manifests.md", {"file_path": path}) is flagged


@pytest.mark.parametrize("cmd,hit", [
    ("go get pgregory.net/rapid", True), ("go mod tidy", True), ("go mod edit -require=x@v1", True),
    ("go install x@latest", True), ("pip install hypothesis", True), ("npm install fast-check", True),
    ("rg -n 'pgregory|hypothesis' go.mod", False), ("git grep gopter", False), ("go test ./...", False),
    ("go test -run '^$' -fuzz '^FuzzX$' -fuzztime 20s .", False),
])
def test_dependency_command_grader(cmd, hit):
    assert matches(OUTCOME, "no-dependency-commands.md", {"command": cmd}) is hit


@pytest.mark.parametrize("cmd,hit", [
    ("go test -run '^$' -fuzz '^FuzzX$' -fuzztime 20s .", True), ("go test -run=^$ -fuzz=FuzzX -fuzztime=15s .", True),
    ("go test ./...", False),
])
def test_fuzz_run_grader(cmd, hit):
    assert matches(OUTCOME, "fuzz-run.md", {"command": cmd}) is hit


def test_fixture_builds_and_has_the_latent_bug(tmp_path):
    subprocess.run(["bash", str(EVALS / OUTCOME / "setup.sh")], cwd=tmp_path, check=True,
                   capture_output=True)
    go = shutil.which("go")
    if go is None:
        pytest.skip("not run: go missing")
    probe = tmp_path / "probe_test.go"
    probe.write_text('package ledgerlib\nimport "testing"\n'
                     'func TestProbe(t *testing.T) {\n'
                     '\tfor _, c := range []int64{-100, -101, 0, 1205, -9223372036854775808, 9223372036854775807} {\n'
                     '\t\tif g, err := Parse(Format(c)); err != nil || g != c {\n\t\t\tt.Fatalf("%d", c)\n\t\t}\n\t}\n'
                     '\tif g, _ := Parse(Format(-5)); g == -5 {\n\t\tt.Fatal("expected the latent bug")\n\t}\n}\n')
    out = subprocess.run([go, "test", "./..."], cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_line_coverage_not_routed_to_mutation_testing():
    body = flat(parts(SKILL)[1])
    assert "| line coverage | not a property test; answer directly |" in body
    assert "kill rate | `mutation-testing:mutation-testing` |" in body
    assert "line coverage" not in (ROOT / "README.md").read_text().split("mutation-testing:mutation-testing")[0].split("Not covered")[-1]


def test_use_when_covers_review_and_fallback():
    meta, body = parts(SKILL)
    assert "add or audit property tests" in meta["description"]
    assert "shrinks nothing" in flat(body)
    assert "a input" not in body
