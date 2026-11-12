import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "post-patch-validation"
SKILL = SKILL_DIR / "SKILL.md"
AGENTS = {p.stem: p for p in (ROOT / "agents").glob("*.md")}
EVALS = ROOT / "evals"
MARKET = ROOT.parent / ".claude-plugin" / "marketplace.json"
RUNNER_CMD = "python3 ${CLAUDE_SKILL_DIR}/scripts/post_patch_validation.py"
BASH_OK = {"git rev-parse:*", "git diff:*", "git show:*", "git log:*", "git remote get-url:*",
           "mkdir -p:*", "printenv TMPDIR", "gh pr view:*", "gh pr diff:*", "gh repo view:*",
           f"{RUNNER_CMD} scaffold:*", f"{RUNNER_CMD} validate-plan:*", f"{RUNNER_CMD} print-schema"}
OTHER_OK = {"Read", "Write", "Grep", "Glob", "Agent"}
TEMP_WRITES = ["/private/tmp/e-Ab12/home/cwd/ppv/plan.json",
               "/private/tmp/e-Ab12/home/cwd/ppv/checks/probe.py",
               "/private/tmp/e-Ab12/tmp/claude-501/bin/git",
               "/tmp/e-Zz/tmp/x.txt",
               "/var/folders/xy/abc123/T/post-patch-validation-auditlog-1a2b3c4/plan.json"]
BAD_WRITES = ["/private/tmp/e-Ab12/home/cwd/target/logline/field.go",
              "/private/tmp/e-Ab12/home/cwd/ppv/../target/logline/field.go",
              "/private/tmp/e-Ab12/home/cwd/notes.md",
              "/Users/someone/ppv/plan.json",
              "/etc/tmp/e-Ab12/tmp/x"]


def split(path):
    _, head, body = path.read_text().split("---", 2)
    return yaml.safe_load(head), body


def tools(meta):
    return re.findall(r"[\w.*-]+(?:\([^)]*\))?", meta["allowed-tools"])


def grader(case, name):
    return yaml.safe_load((EVALS / case / "graders" / name).read_text().split("---")[1])


def test_skill_frontmatter():
    meta, body = split(SKILL)
    assert meta["name"] == "post-patch-validation"
    assert "disable-model-invocation" not in meta
    desc = meta["description"]
    assert desc.startswith("Executes ") and "Use when" in desc
    assert desc.endswith("Not for a read-only diff look — use differential-review:differential-review.")
    assert len(desc) <= 600
    assert len(body.strip().splitlines()) <= 250


def test_allowed_tools_read_only_and_run_not_preapproved():
    found = tools(split(SKILL)[0])
    for tok in found:
        if tok.startswith("Bash("):
            assert tok[5:-1] in BASH_OK, tok
        else:
            assert tok in OTHER_OK, tok
    head = split(SKILL)[0]["allowed-tools"]
    assert "post_patch_validation.py run" not in head
    for banned in ("gh api", "worktree", "Edit", "git checkout", "git apply", "go "):
        assert banned not in head, banned
    assert "Bash" not in found


def test_limits_section_lists_forbidden_flags():
    body = split(SKILL)[1]
    limits = body.split("## Limits", 1)[1]
    for flag in ("`--output`", "`git diff`", "`git log`", "`git show`", "`--ext-diff`",
                 "`--no-index`", "`--web`/`-w`", "`gh api`"):
        assert flag in limits, flag


def test_workflow_gates_in_order():
    body = split(SKILL)[1]
    order = ["## 1. Inputs", "## 2. Pin", "## 3. Coverage", "## 4. Plan", "## 5. Approval gate",
             "## 6. Run", "## 7. Evidence review", "## 8. Report"]
    pos = [body.index(h) for h in order]
    assert pos == sorted(pos)
    gate = body.split("## 5. Approval gate")[1].split("## 6. Run")[0]
    assert "Run only after a yes" in gate


def test_fallback_said_once_and_no_guessing():
    text = " ".join(split(SKILL)[1].split())
    assert "git remote get-url origin" in text
    assert "say **once** that the PR cannot be read here" in text
    for word in ("commit range", "branch pair", "patch file", "no guessed SHAs", "no `gh api`"):
        assert word in text, word


def test_statuses_and_exit_codes():
    body = split(SKILL)[1]
    for status in ("NEEDS_REPAIR", "BLOCKED", "REVIEW_REQUIRED", "READY_FOR_HUMAN_REVIEW"):
        assert f"`{status}`" in body
    report = body.split("## 8. Report")[1]
    assert report.index("`NEEDS_REPAIR`") < report.index("`BLOCKED`") < report.index("`REVIEW_REQUIRED`")
    for code in ("| 0 |", "| 1 |", "| 10 |", "| 64 |"):
        assert code in body


def test_references_linked_and_long_ones_have_contents():
    body = split(SKILL)[1]
    for ref in (SKILL_DIR / "references").glob("*.md"):
        assert f"references/{ref.name}" in body, ref.name
        lines = ref.read_text().splitlines()
        if len(lines) > 100:
            assert "## Contents" in lines[:30]


def test_marker_and_side_blind_rules_documented():
    plan_ref = (SKILL_DIR / "references" / "plan-format.md").read_text()
    for needle in ("PPV_REACHED", "marker_missing", "{side}", "PPV_SIDE", "--allow-env"):
        assert needle in plan_ref, needle


@pytest.mark.parametrize("name", ["coverage-mapper", "evidence-reviewer"])
def test_agents_read_only(name):
    meta, body = split(AGENTS[name])
    assert meta["name"] == name
    assert len(AGENTS[name].read_text().splitlines()) <= 80
    assert "post-patch-validation:post-patch-validation" in meta["description"]
    toolset = [t.strip() for t in meta["tools"].split(",")]
    for t in toolset:
        assert t in {"Read", "Grep", "Glob"} or re.fullmatch(
            r"Bash\((?:git (?:show|diff|log)|shasum -a 256):\*\)", t), t
    assert "skills" not in meta
    assert "## Limits" in body and "--output" in body.split("## Limits")[1]


def test_mapper_limits_cover_git_grep_flags():
    limits = split(AGENTS["coverage-mapper"])[1].split("## Limits")[1]
    assert "`-O`" in limits and "`--open-files-in-pager`" in limits


def test_skill_names_agents_fully():
    body = split(SKILL)[1]
    assert "post-patch-validation:coverage-mapper" in body
    assert "post-patch-validation:evidence-reviewer" in body


def test_manifest_matches_marketplace():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    entry = next(p for p in json.loads(MARKET.read_text())["plugins"]
                 if p["name"] == "post-patch-validation")
    assert manifest["version"] == entry["version"] == "1.0.0"
    assert manifest["license"] == entry["license"] == "MIT"
    assert manifest["author"] == entry["author"] == {"name": "Aleksandr Letunov",
                                                     "email": "flypatriotka@gmail.com"}
    assert entry["category"] == "security" and "category" not in manifest
    assert "## 2026-11-11" in (ROOT / "CHANGELOG.md").read_text()


def test_required_eval_cases_present():
    cases = {p.name for p in EVALS.iterdir() if (p / "case.yaml").exists()}
    wanted = ["fallback-non-github-remote", "negative-read-only-review", "outcome-approval-gate",
              "outcome-go-missed-variant", "trigger-validate-pr-fix"]
    missing = [name for name in wanted if name not in cases]
    assert not missing, missing


def test_evals_say_pr_never_mr():
    for path in EVALS.rglob("*"):
        if path.is_file() and "results" not in path.parts:
            text = path.read_text()
            assert not re.search(r"\bMRs?\b|merge request", text, re.I), path
    assert "example.net/auditlog" in (EVALS / "outcome-go-missed-variant" / "setup.sh").read_text()


def test_skill_regexes_scoped():
    for path in EVALS.glob("*/graders/*.md"):
        meta = yaml.safe_load(path.read_text().split("---")[1])
        if meta.get("tool") == "Skill":
            assert "(?:post-patch-validation:)?post-patch-validation" in meta["input_match"], path


def test_fallback_grader_rejects_gh_api_and_writes():
    rx = re.compile(grader("fallback-non-github-remote", "no-gh-api-or-write.md")["input_match"])
    for cmd in ("gh api repos/x/y/pulls/41", "cd r && gh pr comment 41 --body x",
                "gh pr review 41 --approve", "gh pr merge 41"):
        assert rx.search(json.dumps({"command": cmd})), cmd
    for cmd in ("gh pr view 41 --json baseRefOid", "gh pr diff 41", "git log --oneline"):
        assert not rx.search(json.dumps({"command": cmd})), cmd
    llm = (EVALS / "fallback-non-github-remote" / "graders" / "asks-for-range.md").read_text()
    assert "commit range" in llm and "branch pair" in llm and "patch file" in llm
    setup = (EVALS / "fallback-non-github-remote" / "setup.sh").read_text()
    assert "git remote add origin https://forge.example.net/" in setup


@pytest.mark.parametrize("case", ["outcome-go-missed-variant", "outcome-approval-gate"])
@pytest.mark.parametrize("tool", ["write", "edit"])
def test_outcome_write_edit_exemption_anchored(case, tool):
    rx = re.compile(grader(case, f"no-{tool}.md")["input_match"])
    for path in TEMP_WRITES:
        assert not rx.search(json.dumps({"file_path": path})), path
    for path in BAD_WRITES:
        assert rx.search(json.dumps({"file_path": path})), path


def test_fixtures_disable_hooks():
    for setup in EVALS.glob("*/setup.sh"):
        assert "git config core.hooksPath /dev/null" in setup.read_text(), setup


def test_fallback_no_write_allows_only_temp_root():
    rx = re.compile(grader("fallback-non-github-remote", "no-write.md")["input_match"])
    assert not rx.search(json.dumps({"file_path": "/private/tmp/e-Ab12/tmp/claude-501/bin/git"}))
    for bad in ("/private/tmp/e-Ab12/home/cwd/logline/field.go",
                "/private/tmp/e-Ab12/tmp/../home/cwd/x", "/Users/x/tmp/y"):
        assert rx.search(json.dumps({"file_path": bad})), bad


def test_approval_gate_rule_and_eval():
    gate = split(SKILL)[1].split("## 5. Approval gate")[1].split("## 6. Run")[0]
    flat = " ".join(gate.split())
    assert "explicitly authorises running the project's commands or checks" in flat
    assert "the table is shown before `run`" in flat
    rx = re.compile(grader("outcome-approval-gate", "no-run.md")["input_match"])
    assert rx.search(json.dumps({"command": "python3 /x/scripts/post_patch_validation.py run --plan p"}))
    assert not rx.search(json.dumps({"command": "python3 /x/scripts/post_patch_validation.py validate-plan --plan p"}))
