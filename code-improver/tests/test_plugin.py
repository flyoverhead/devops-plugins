import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "code-improver"
SKILL = SKILL_DIR / "SKILL.md"
REFS = SKILL_DIR / "references"
FIXER = ROOT / "agents" / "fixer.md"
AUDITOR = ROOT / "agents" / "finalize-auditor.md"
EVALS = ROOT / "evals"
REQUIRED = {"outcome-reviewer-unavailable", "negative-one-time-review"}
BASH_OK = {"git rev-parse:*", "git status:*", "git diff:*", "git ls-files:*", "printenv TMPDIR",
           "python3 ${CLAUDE_SKILL_DIR}/scripts/scope_guard.py:*"}
OTHER_TOOLS = {"Read", "Grep", "Glob", "Write", "Skill", "Agent", "AskUserQuestion"}
HALTS = ["reviewer-unavailable", "reviewer-failed", "scope-violation", "scope-check-failed",
         "untracked-files-in-scope", "finalize-regression", "finalize-check-failed"]
TRIGGERS = ["counts-non-decreasing", "recurrence", "structural-rejection", "relocation"]
TEMP_ROOTS = ["/private/tmp/e-Ab12/tmp/", "/tmp/", "/var/folders/xy/abc123/T/",
              "/private/var/folders/xy/abc123/T/claude-501/"]


def split(path):
    _, head, body = path.read_text().split("---", 2)
    return yaml.safe_load(head), body


def flat(text):
    return " ".join(text.split())


def section(body, heading):
    return body.split(heading, 1)[1].split("\n## ", 1)[0]


def grader(case, name):
    return yaml.safe_load((EVALS / case / "graders" / name).read_text().split("---")[1])


def write_call(path, content="x"):
    return json.dumps({"file_path": path, "content": content})


def test_user_invoked_only():
    meta, _ = split(SKILL)
    assert meta["name"] == "code-improver"
    assert meta["disable-model-invocation"] is True
    assert '"target"' in meta["argument-hint"] and '"reviewer"' in meta["argument-hint"]


def test_description_shape():
    desc = split(SKILL)[0]["description"]
    assert desc.startswith("Drives ")
    assert "Use when" in desc and "Not for" in desc and "— use golang:review." in desc
    assert "/code-improver:code-improver" in desc
    assert len(desc) <= 600


def test_allowed_tools_read_only_plus_script():
    tools = re.findall(r"[\w.*-]+(?:\([^)]*\))?", split(SKILL)[0]["allowed-tools"])
    for tool in tools:
        if tool.startswith("Bash("):
            assert tool[5:-1] in BASH_OK, tool
        else:
            assert tool in OTHER_TOOLS, tool
    assert "Edit" not in tools and "Bash" not in tools


@pytest.mark.parametrize("word", ["commit", "push", "stash", "reset", "clean", "checkout", "init",
                                  "git add", "gh ", "hash-object"])
def test_no_writing_git_prefix(word):
    assert word not in split(SKILL)[0]["allowed-tools"]


def test_limits_section():
    limits = section(split(SKILL)[1], "## Limits")
    for flag in ["--output", "--ext-diff", "--no-index"]:
        assert flag in limits, flag
    assert "`git diff`" in limits


def test_body_length_and_maxrounds():
    body = split(SKILL)[1]
    assert len(body.strip().splitlines()) <= 250
    text = flat(body)
    assert "1–20, default 5" in text
    assert "`maxRounds + 1`" in text and "review-only" in text


def test_never_commits_or_inits():
    body = flat(split(SKILL)[1])
    assert "You never commit, push, stash, reset, clean, check out, or `git init`" in body
    assert "you never do it" in body


def test_reviewer_probe_and_no_stand_in():
    body = split(SKILL)[1]
    probe = flat(section(body, "## 3. Probe the reviewer"))
    assert 'halted: "reviewer-unavailable"' in probe
    assert "Do not invoke it to test" in probe
    assert "`golang` for `golang:review`" in probe
    assert "suggest no stand-in" in probe
    assert body.index("## 3. Probe the reviewer") < body.index("## 4. Rounds")
    assert "never review inline in its place" in flat(body)


def test_round_steps_in_order():
    rounds = section(split(SKILL)[1], "## 4. Rounds")
    marks = ["**a. Persist.**", "**b. Review.**", "**c. Merge**", "**d. Clean?**",
             "**e. Escalation check**", "**f. Budget.**", "**g. Fix.**", "**h. Merge verdicts**",
             "**i. Scope guard**"]
    pos = [rounds.index(m) for m in marks]
    assert pos == sorted(pos)
    assert "also after a fixer that died" in rounds


def test_clean_review_then_finalize_then_check():
    body = split(SKILL)[1]
    order = ["## 5. Before finalizing", "## 6. Finalize pass", "## 7. Finalize check", "## 8. Report"]
    assert [body.index(h) for h in order] == sorted(body.index(h) for h in order)
    assert "pre-finalize.diff" in section(body, "## 5. Before finalizing")
    assert "post-finalize.diff" in section(body, "## 6. Finalize pass")


def test_halt_names_and_triggers_documented():
    ledger = (REFS / "ledger.md").read_text()
    body = split(SKILL)[1]
    for name in HALTS:
        assert f"`{name}`" in ledger, name
        assert name in body, name
    for trig in TRIGGERS:
        assert f"`{trig}`" in ledger, trig
    for key in ["seen_prior", "fixed_prior", "refiled_after_verdict", "verified_fixed", "unaddressed"]:
        assert key in ledger, key


def test_finding_id_rule():
    ledger = flat((REFS / "ledger.md").read_text())
    assert "`<file>:<line>:<class>`" in ledger and "`<file>::<class>`" in ledger
    assert "`store/disk.go:12:unchecked-error`" in ledger


def test_sentinel_documented():
    brief = (REFS / "review-brief.md").read_text()
    assert "REVIEWER-UNAVAILABLE:" in brief
    assert "at most 8" in brief and "At most 3 waves" in brief


def test_references_linked_and_present():
    links = set(re.findall(r"\]\(references/([\w.-]+\.md)", SKILL.read_text()))
    linked = links | {"finalize.md"}
    assert linked == {p.name for p in REFS.glob("*.md")}
    assert "${CLAUDE_SKILL_DIR}/references/finalize.md" in SKILL.read_text()


def test_anchors_resolve():
    for name, anchor in re.findall(r"references/([\w.-]+\.md)#([\w-]+)\)", SKILL.read_text()):
        heads = re.findall(r"^#+ (.+)$", (REFS / name).read_text(), re.M)
        slugs = {re.sub(r"[^\w -]", "", h).strip().lower().replace(" ", "-") for h in heads}
        assert anchor in slugs, (name, anchor)


def test_agents_dispatched_by_full_name():
    body = split(SKILL)[1]
    assert "`code-improver:fixer`" in body and "`code-improver:finalize-auditor`" in body
    assert "The fixer cannot load this skill" in flat(body)


def test_fixer_shape_and_limits():
    meta, body = split(FIXER)
    assert meta["name"] == "fixer" and "skills" not in meta
    assert [t.strip() for t in meta["tools"].split(",")] == [
        "Read", "Grep", "Glob", "Edit", "Write", "Bash(git add -N:*)", "Bash(git diff:*)",
        "Bash(git status:*)", "Bash(go test:*)", "Bash(go vet:*)",
        "Bash(python3 */skills/code-improver/scripts/scope_guard.py match *)"]
    assert len(FIXER.read_text().splitlines()) <= 80
    limits = section(body, "## Limits")
    for word in ["git commit", "git push", "git stash", "git reset", "git clean", "git checkout",
                 "git add -N", "git update-index", "git update-ref", "git commit-tree",
                 "--output", "--ext-diff", "--no-index", "-toolexec", "-exec",
                 "-overlay", "-vettool", "-modfile", "-mod=mod", "-outputdir"]:
        assert word in limits, word
    text = flat(body)
    assert "`requires out-of-scope change: <path>`" in text
    assert "`git add -N <path>`" in text
    assert "structural: true" in text
    for field in ['"verdicts"', '"verdict"', '"reason"', '"pin"', '"notes"']:
        assert field in body, field
    assert '"diff_file"' not in body
    assert "the skill writes `<out>/fixes-round-<N>.diff` itself" in text


def test_auditor_read_only():
    meta, body = split(AUDITOR)
    assert meta["name"] == "finalize-auditor" and "skills" not in meta
    assert [t.strip() for t in meta["tools"].split(",")] == ["Read", "Grep", "Glob"]
    assert len(AUDITOR.read_text().splitlines()) <= 80
    for field in ['"regressions"', '"file"', '"line"', '"why"', '"version_ok"']:
        assert field in body, field


def test_finalize_reference():
    text = flat((REFS / "finalize.md").read_text())
    assert "exactly one patch step above it" in text
    assert "`+` lines of `pre-finalize.diff`" in text
    assert "Unreleased" in text and "Never write the word" in text
    assert "## Audit checklist (finalize-auditor)" in (REFS / "finalize.md").read_text()


@pytest.mark.parametrize("phrase,hit", [
    ("handled since round 2", True), ("see Iteration 3", True), ("pass #4 fixed it", True),
    ("unlike the previous attempt", True), ("this check was moved here", True),
    ("renamed per the reviewer", True), ("a round-trip through JSON", False),
    ("round the value to 2 places", False), ("the previous line", False),
])
def test_narration_patterns(phrase, hit):
    table = (REFS / "finalize.md").read_text().split("## Duty 1", 1)[1].split("## Duty 2", 1)[0]
    pats = [p.replace("\\|", "|") for p in re.findall(r"^\| `(.+?)` \|", table, re.M)]
    assert len(pats) == 4
    assert any(re.search(p, phrase, re.I) for p in pats) is hit


def test_no_other_host_cli_anywhere():
    rx = re.compile("g" + "lab", re.I)
    for path in ROOT.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.suffix in {".md", ".sh", ".yaml", ".json", ".py"}:
            assert not rx.search(path.read_text()), path


def test_manifest_matches_marketplace():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT.parent / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "code-improver")
    assert entry["version"] == plugin["version"] == "1.0.0"
    assert entry["category"] == "security" and "category" not in plugin
    assert entry["author"] == plugin["author"] == {"name": "Aleksandr Letunov", "email": "flypatriotka@gmail.com"}
    assert entry["license"] == plugin["license"] == "MIT"


def test_changelog_dated():
    text = (ROOT / "CHANGELOG.md").read_text()
    assert "## 2026-11-11" in text and "Unreleased" not in text


def test_required_evals_present():
    cases = {c.name for c in EVALS.iterdir() if (c / "case.yaml").exists()}
    assert REQUIRED <= cases


def test_fixtures_disable_hooks():
    for setup in EVALS.glob("*/setup.sh"):
        assert "core.hooksPath /dev/null" in setup.read_text(), setup


def test_skill_regexes_scoped():
    for path in EVALS.glob("*/graders/*.md"):
        meta = yaml.safe_load(path.read_text().split("---")[1])
        if meta.get("tool") == "Skill" and "input_match" in meta:
            assert "(?:code-improver:)?code-improver" in meta["input_match"], path


def test_negative_case_not_fired():
    rx = re.compile(grader("negative-one-time-review", "not-fired.md")["input_match"])
    assert rx.search(json.dumps({"skill": "code-improver:code-improver"}))
    assert rx.search(json.dumps({"skill": "code-improver"}))
    assert not rx.search(json.dumps({"skill": "golang:review"}))


@pytest.mark.parametrize("root", TEMP_ROOTS)
@pytest.mark.parametrize("name,allowed", [("ledger.json", True), ("ledger.md", True),
                                          ("status.md", True), ("notes.md", False),
                                          ("ledger.json.bak", False)])
def test_no_write_exemption_anchored(root, name, allowed):
    rx = re.compile(grader("outcome-reviewer-unavailable", "no-write.md")["input_match"])
    flagged = bool(rx.search(write_call(f"{root}code-improver-snapcache/{name}")))
    assert flagged is not allowed


@pytest.mark.parametrize("path", ["/work/repo/tmp/code-improver-snapcache/ledger.json",
                                  "/private/tmp/e-Ab12/ws/snapcache/disk.go",
                                  "/private/tmp/e-Ab12/ws/tmp/code-improver-x/ledger.json"])
def test_no_write_flags_repo_paths(path):
    rx = re.compile(grader("outcome-reviewer-unavailable", "no-write.md")["input_match"])
    assert rx.search(write_call(path))


@pytest.mark.parametrize("content,halted,empty", [
    ({"findings": {}, "result": {"halted": "reviewer-unavailable"}}, True, True),
    ({"findings": {"a:1:b": {}}, "result": {"halted": "reviewer-unavailable"}}, True, False),
    ({"findings": {}, "result": {"halted": "reviewer-failed"}}, False, True),
])
def test_ledger_graders(content, halted, empty):
    call = write_call("/tmp/e-1/tmp/code-improver-snapcache/ledger.json", json.dumps(content, indent=2))
    case = "outcome-reviewer-unavailable"
    assert bool(re.search(grader(case, "ledger-halted.md")["input_match"], call)) is halted
    assert bool(re.search(grader(case, "ledger-no-findings.md")["input_match"], call)) is empty
    other = write_call("/tmp/e-1/tmp/code-improver-snapcache/status.md", json.dumps(content))
    assert not re.search(grader(case, "ledger-halted.md")["input_match"], other)


@pytest.mark.parametrize("command,flagged", [
    ("git commit -s -m x", True), ("git -C /r stash", True), ("git init -q", True),
    ("git add -N snapcache/x.go", True), ("git reset --hard", True),
    ("git checkout -- snapcache/disk.go", True), ("git status --porcelain", False),
    ("git rev-parse --show-toplevel", False), ("git diff --name-only HEAD", False),
    ("git ls-files --others --exclude-standard", False),
    ("/opt/homebrew/bin/git commit -qm x", True), ("cd r && git -c a=b -C . stash", True),
    ("python3 /Users/me/git/github/p/scripts/scope_guard.py init --repo /r --out /o", False),
    ("git log --grep init", False),
])
def test_no_git_mutation_regex(command, flagged):
    rx = re.compile(grader("outcome-reviewer-unavailable", "no-git-mutation.md")["input_match"])
    assert bool(rx.search(json.dumps({"command": command}))) is flagged


def test_fixture_intact_regex_matches_scaffold(tmp_path):
    subprocess.run(["bash", str(EVALS / "outcome-reviewer-unavailable" / "setup.sh")], cwd=tmp_path,
                   check=True, capture_output=True, env={"PATH": "/usr/bin:/bin:/opt/homebrew/bin",
                                                         "HOME": str(tmp_path)})
    body = (EVALS / "outcome-reviewer-unavailable" / "graders" / "fixture-intact.md").read_text()
    pattern = body.split("---", 2)[2].strip()
    src = (tmp_path / "snapcache" / "disk.go").read_text()
    assert re.search(pattern, src)
    assert not re.search(pattern, src.replace("0666", "0o600"))
    assert not re.search(pattern, src + "// trailing\n")


def test_scope_final_before_init():
    base = section(split(SKILL)[1], "## 2. Baseline")
    init = base.index("scope_guard.py init")
    for item in ["`.claude-plugin/plugin.json` and `CHANGELOG.md`", "`.claude-plugin/marketplace.json` to the scope"]:
        assert base.index(item) < init, item
    assert "--plugin-version <version>" in base
    assert "Continue only when `decision` is set" in flat(base)


def test_guard_outcomes_named():
    body = flat(split(SKILL)[1])
    for word in ["`head_moved: true`", "`hidden_flags`", "`scope-mismatch`", "with the pinned scope"]:
        assert word in body, word


def test_finalize_rules():
    body = flat(split(SKILL)[1])
    assert "skip to step 8 with `converged: true`" in body
    assert "The finalize fixer died or returned no record" in body
    fin = section(split(SKILL)[1], "## 6. Finalize pass")
    assert "${CLAUDE_SKILL_DIR}/scripts/scope_guard.py" in fin
    check = flat(section(split(SKILL)[1], "## 7. Finalize check"))
    assert "`version_ok: false`: `finalize-regression`" in check
    assert "`version_checked: false`" in check and "`finalize-check-failed`" in check
    assert '"version_checked"' in AUDITOR.read_text()


def test_agent_types_checked_and_rounds_asked():
    body = flat(split(SKILL)[1])
    assert "If either is missing, say which one and stop" in body
    assert "ask for a value in range; do not pick one" in body


def test_fixer_has_no_ignored_hooks_and_readme_says_why():
    assert "hooks" not in split(FIXER)[0]
    readme = flat((ROOT / "README.md").read_text())
    assert "ignores `hooks` in plugin agent frontmatter" in readme
    assert "everything else under `.git/`" in readme


def test_fixed_rereport_counts_round():
    ledger = (REFS / "ledger.md").read_text()
    row = next(l for l in ledger.splitlines() if l.startswith("| re-reported, status `fixed`"))
    assert "`last_round = r`" in row and "`rounds_seen`" in row


def test_outcome_has_no_skill_grader():
    meta = grader("outcome-reviewer-unavailable", "no-skill-call.md")
    assert meta["tool"] == "Skill" and meta["max"] == 0 and meta["arm"] == "with-only"
