"""Plugin structure, skill frontmatter, safety wording and eval grader regexes."""
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
EVALS = ROOT / "evals"
MARKET = ROOT.parent / ".claude-plugin" / "marketplace.json"
STAGES = ["prepare-regression", "hunt-regressions", "reproduce-regression", "replay-regression",
          "adjudicate-regression", "report-regressions"]
ALL = ["regression-hunt", *STAGES]
SCRIPTS = {"registry.py", "evidence.py", "snapshot.py", "report.py", "runtime.py", "guidance.py"}
READ_ONLY = {"git rev-parse:*", "git remote get-url:*", "git status:*", "git log:*", "git show:*",
             "git diff:*", "git merge-base:*", "git cat-file:*", "git ls-tree:*",
             "gh pr view:*", "gh pr diff:*", "gh pr list:*", "printenv TMPDIR", "shasum -a 256:*"}
TOOLS = {"Read", "Grep", "Glob", "Write", "Agent", "TaskStop"}
SKILL_RX = "(?:regression-hunt:)?(?:" + "|".join(ALL) + ")"


def split(path):
    _, head, body = path.read_text().split("---", 2)
    return yaml.safe_load(head), body


def tokens(meta):
    return re.findall(r"[\w.*-]+(?:\([^)]*\))?", meta["allowed-tools"])


def grader(case, name):
    return yaml.safe_load((EVALS / case / "graders" / name).read_text().split("---")[1])


def hits(case, name, payload):
    return bool(re.search(grader(case, name)["input_match"], json.dumps(payload)))


@pytest.mark.parametrize("name", ALL)
def test_frontmatter(name):
    meta, body = split(SKILLS / name / "SKILL.md")
    assert meta["name"] == name
    desc = meta["description"]
    assert re.match(r"^[A-Z][a-z]+s ", desc)
    assert "Use when" in desc or "Use as" in desc
    assert re.search(r"Not for .+ — use regression-hunt:[a-z-]+\.$|— use [a-z-]+:[a-z-]+\.$", desc)
    assert len(desc) <= 600
    assert len(body.strip().splitlines()) <= 250
    assert "disable-model-invocation" not in meta


@pytest.mark.parametrize("name", ALL)
def test_allowed_tools_read_only(name):
    meta, _ = split(SKILLS / name / "SKILL.md")
    prefix = "python3 ${CLAUDE_SKILL_DIR}/" + ("" if name == "regression-hunt" else "../regression-hunt/") + "scripts/"
    for tok in tokens(meta):
        if tok.startswith("Bash("):
            inner = tok[5:-1]
            if inner.startswith("python3 "):
                assert inner.startswith(prefix), tok
                script = inner[len(prefix):].split(":")[0].split()[0]
                assert script in SCRIPTS, tok
            else:
                assert inner in READ_ONLY, tok
        else:
            assert tok in TOOLS, tok
    head = meta["allowed-tools"]
    for banned in ("gh api", "Edit", "git commit", "git push", "worktree", "go ", "cp ", "make", "npm", "pytest",
                   "mkdir"):
        assert banned not in head, (name, banned)
    assert "Bash" not in tokens(meta)


@pytest.mark.parametrize("name", ALL)
def test_limits_list_forbidden_flags(name):
    meta, body = split(SKILLS / name / "SKILL.md")
    assert "## Limits" in body
    limits = body.split("## Limits", 1)[1]
    head = meta["allowed-tools"]
    flat_limits = " ".join(limits.split())
    for cmd in ("git log", "git show", "git diff"):
        if f"Bash({cmd}:*)" in head:
            assert f"`{cmd}`" in limits and "`--output`" in limits, (name, cmd)
            assert "`--ext-diff`" in limits, (name, cmd)
    for cmd in ("git log", "git show"):
        if f"Bash({cmd}:*)" in head:
            assert "`--textconv`" in limits and "`git log`" in flat_limits, (name, cmd)
    if "Bash(git cat-file:*)" in head:
        assert "`--textconv` and `--filters` on `git cat-file`" in flat_limits
    if "Bash(git diff:*)" in head:
        assert "`--ext-diff`" in limits and "`--no-index`" in limits
    if "Bash(git show:*)" in head:
        assert "`--textconv`" in limits
    assert "Bash(git grep" not in head, name
    if "Bash(gh " in head:
        assert "`--web`" in limits


@pytest.mark.parametrize("name", ALL)
def test_paths_exist(name):
    text = (SKILLS / name / "SKILL.md").read_text()
    for rel in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/((?:\.\./regression-hunt/)?(?:scripts|references)/[\w.-]+)", text):
        assert (SKILLS / name / rel).resolve().exists(), rel
    for rel in re.findall(r"\]\((references/[\w.-]+\.md)\)", text):
        assert (SKILLS / name / rel).exists(), rel


def test_references_have_contents():
    for ref in (SKILLS / "regression-hunt" / "references").glob("*.md"):
        assert "## Contents" in ref.read_text().splitlines()[:12] or "## Contents" in ref.read_text()[:600], ref


def flat(name):
    return " ".join(split(SKILLS / name / "SKILL.md")[1].split())


def test_coordinator_gate_and_fallback():
    text = flat("regression-hunt")
    assert "explicitly allows running the project's commands" in text
    assert "show the plan anyway" in text and "end the turn after the plan" in text
    assert "git remote get-url origin" in text and "do not call `gh` at all" in text
    assert "`gh api`" in text and "never pre-approved" in text
    order = ["## 1. Read the request", "## 2. Plan and approval", "## 3. Open the campaign",
             "## 4. Run the stages", "## 5. Reply"]
    body = split(SKILLS / "regression-hunt" / "SKILL.md")[1]
    assert [body.index(h) for h in order] == sorted(body.index(h) for h in order)
    for stage in STAGES:
        assert f"regression-hunt:{stage}" in text


@pytest.mark.parametrize("name", ["reproduce-regression", "replay-regression"])
def test_experiment_stages_are_gated(name):
    text = flat(name)
    assert "explicitly allow running the project's commands" in text
    assert "never install anything" in text.lower()


def test_dispatch_handshake():
    text = (SKILLS / "regression-hunt" / "references" / "dispatch.md").read_text()
    for needle in ('"general-purpose"', "run_in_background: true", "never `fork`", "runtime.py publish",
                   "registry.py bind", "At most five agents", "never do the stage yourself", "killed"):
        assert needle in text, needle


def test_records_reference_covers_formats():
    ref = (SKILLS / "regression-hunt" / "references" / "records.md").read_text()
    for name in ("scope.json", "registry.json", "campaign.json", ".seal.json", "prepare.json", "source.json",
                 "hunt.json", "reproduce.json", "replay.json", "decision.json", "report-stage.json",
                 "report.json", "supported_behavior", "unsupported_expectation", "security_scope",
                 "REPRODUCED_REGRESSION", "INCOMPLETE_FIX", "LATENT_BUG", "PREEXISTING_BUG", "REJECTED",
                 "UNRESOLVED", "shared-host", "isolated", "build_dirs", "duplicate_of"):
        assert name in ref, name


def test_shapes_match_reference(mods):
    shapes = mods["shapes"]
    assert len(shapes.CHECK_WANT) == 9 and len(shapes.OUTCOMES) == 6
    assert shapes.STAGES == ("prepare", "hunt", "reproduce", "replay", "adjudicate", "report")


def test_no_agents_dir_and_no_banned_terms():
    assert not (ROOT / "agents").exists()
    for path in ROOT.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.suffix in {".md", ".py", ".sh", ".json", ".yaml"}:
            low = path.read_text().lower()
            assert "gl" + "ab" not in low and "trail" + "ofbits" not in low, path


def test_manifest_and_marketplace():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    entry = next(p for p in json.loads(MARKET.read_text())["plugins"] if p["name"] == "regression-hunt")
    assert manifest["version"] == entry["version"] == "1.0.0"
    assert manifest["license"] == entry["license"] == "MIT"
    assert manifest["author"] == entry["author"] == {"name": "Aleksandr Letunov", "email": "flypatriotka@gmail.com"}
    assert entry["category"] == "security" and "category" not in manifest
    log = (ROOT / "CHANGELOG.md").read_text()
    assert "## 2026-11-11" in log and "Unreleased" not in log
    row = "| `regression-hunt` | `" + "`, `".join(ALL) + "` | |"
    assert row in (ROOT.parent / "CLAUDE.md").read_text()


def test_eval_cases_and_fixtures():
    cases = {p.name for p in EVALS.iterdir() if (p / "case.yaml").exists()}
    assert {"trigger-prove-regression", "negative-read-only-review", "outcome-go-auth-regression",
            "outcome-approval-gate"} <= cases
    for setup in EVALS.glob("*/setup.sh"):
        text = setup.read_text()
        assert "git config core.hooksPath /dev/null" in text and "module example.net/shelf" in text
        assert "git remote" not in text and "commit.gpgsign false" in text


def test_skill_graders_scoped():
    for path in EVALS.glob("*/graders/*.md"):
        meta = yaml.safe_load(path.read_text().split("---")[1])
        if meta.get("tool") == "Skill":
            assert "(?:regression-hunt:)?" in meta["input_match"], path
    for skill in ALL:
        payload = {"skill": f"regression-hunt:{skill}"}
        assert hits("negative-read-only-review", "not-fired.md", payload)
        assert hits("trigger-prove-regression", "skill-fired.md", payload)
    assert not hits("negative-read-only-review", "not-fired.md", {"skill": "differential-review:differential-review"})


CWD = "/private/tmp/e-Ab12/home/cwd"
OK = [f"{CWD}/campaign/scope.json", f"{CWD}/campaign/attempts/a003/poc/poc.sh",
      "/private/tmp/e-Ab12/tmp/gocache/x", "/tmp/e-Ab12/tmp/claude-501/bin/git",
      "/var/folders/xy/abc/T/regression-hunt-target-1a2b3c4/scope.json"]
BAD = [f"{CWD}/target/gate/gate.go", f"{CWD}/target/campaign/x.json", f"{CWD}/notes.md",
       f"{CWD}/campaign/../target/gate/gate.go", "/private/tmp/e-Ab12/tmp/../home/cwd/target/x",
       "/Users/x/campaign/scope.json", "/tmp/other/x", f"{CWD}/campaign"]


@pytest.mark.parametrize("case", ["outcome-go-auth-regression", "outcome-approval-gate"])
@pytest.mark.parametrize("tool", ["write", "edit"])
def test_write_graders_anchored(case, tool):
    for path in OK:
        assert not hits(case, f"no-{tool}.md", {"file_path": path}), path
    for path in BAD:
        assert hits(case, f"no-{tool}.md", {"file_path": path}), path


def test_target_untouched_grader():
    case = "outcome-go-auth-regression"
    for cmd in ("git -C /x/target checkout HEAD~1", "cd target && git stash", "git switch -c x",
                "git -C target worktree add /tmp/w HEAD~1", "git reset --hard HEAD~1", "git commit -s -m x"):
        assert hits(case, "target-untouched.md", {"command": cmd}), cmd
    for cmd in ("git -C target log --oneline", "git -C target show HEAD:gate/gate.go", "git diff HEAD~1 HEAD",
                "git -C target worktree list", "git rev-parse HEAD~1"):
        assert not hits(case, "target-untouched.md", {"command": cmd}), cmd


def test_gh_graders():
    case = "outcome-go-auth-regression"
    assert hits(case, "gh-at-most-once.md", {"command": "gh pr view 3 --comments"})
    assert hits(case, "gh-at-most-once.md", {"command": "/opt/homebrew/bin/gh auth status"})
    assert not hits(case, "gh-at-most-once.md", {"command": "git log --grep high"})
    for cmd in ("gh api repos/x/y/pulls/3/comments", "gh pr comment 3 -b hi", "gh pr review 3 --approve",
                "gh pr merge 3"):
        assert hits(case, "no-gh-api-or-write.md", {"command": cmd}), cmd
    assert not hits(case, "no-gh-api-or-write.md", {"command": "gh pr view 3"})


def test_campaign_graders():
    case = "outcome-go-auth-regression"
    assert hits(case, "registry-init.md", {"command": f"python3 /p/scripts/registry.py init {CWD}/campaign"})
    assert not hits(case, "registry-init.md", {"command": "python3 /p/scripts/registry.py show /c"})
    assert hits(case, "handle-files.md", {"command": f"python3 /p/runtime.py wait {CWD}/campaign/runtime/a004-handle"})
    assert hits(case, "registry-accept.md", {"command": f"python3 /p/scripts/registry.py accept {CWD}/campaign a002 attempts/a002/hunt.json"})
    assert not hits(case, "registry-accept.md", {"command": "python3 /p/scripts/registry.py check /c a002 x"})
    for cmd in (f"python3 /p/scripts/report.py {CWD}/campaign --output attempts/a007/report",
                'S=/p/scripts; C=/c; python3 $S/report.py $C --output attempts/a006/report',
                'python3 "/p/my scripts/report.py" "/c" --output x'):
        assert hits(case, "report-rendered.md", {"command": cmd}), cmd
    for cmd in ("cat /p/scripts/report.py", "grep -n def report.py", "ls attempts/a006/report"):
        assert not hits(case, "report-rendered.md", {"command": cmd}), cmd
    gate = "outcome-approval-gate"
    for cmd in ("cd /x/build/S0 && go build -o bin/shelfctl ./cmd/shelfctl", "./bin/shelfctl purge",
                "python3 /p/registry.py reserve /c --stage prepare --change change-1"):
        assert hits(gate, "nothing-ran.md", {"command": cmd}), cmd
    for cmd in ("git -C target log -2", "go version", "python3 /p/registry.py show /c"):
        assert not hits(gate, "nothing-ran.md", {"command": cmd}), cmd


def test_outcome_prompts():
    outcome = (EVALS / "outcome-go-auth-regression" / "prompt.md").read_text()
    assert "You may build and run the project's code" in outcome and "campaign/" in outcome
    gate = (EVALS / "outcome-approval-gate" / "prompt.md").read_text()
    assert "may" not in gate.split("---")[-1] and "run the" not in gate.split("---")[-1]


def test_authorisation_rules_written_down():
    for text in (" ".join((SKILLS / "regression-hunt" / "references" / "dispatch.md").read_text().split()),
                 flat("regression-hunt")):
        assert "Never add, extend or paraphrase an authorisation" in text
        assert "classifier" in text and "denial" in text
        assert "only" in text and "verbatim" in text
    dispatch = " ".join((SKILLS / "regression-hunt" / "references" / "dispatch.md").read_text().split())
    assert "The `Approval:` line carries only the user's own words, quoted verbatim" in dispatch
    assert 'Approval: "<the user\'s words, verbatim>" covers' not in dispatch
    for name in ("reproduce-regression", "replay-regression"):
        assert "never route around it" in flat(name)


@pytest.mark.parametrize("name", STAGES)
def test_stage_paths_literal(name):
    assert "never put the scripts, the campaign or the attempt in shell variables" in flat(name)


def test_retry_table_in_dispatch():
    text = (SKILLS / "regression-hunt" / "references" / "dispatch.md").read_text()
    for row in ("`reserved`, never launched", "`reserved`, launched but bind failed", "`accepted` with status `blocked`",
                "`accepted` complete, or `superseded`", "needs `runtime/aNNN-terminal.json`", "`output_file:`"):
        assert row in text, row


def test_scope_file_grader():
    meta = grader("outcome-go-auth-regression", "scope-holds-range.md")
    assert meta["type"] == "regex" and meta["target"] == {"source": "file", "path": "campaign/scope.json"}
    rx = re.compile(meta["pattern"])
    good = json.dumps({"changes": [{"id": "change-1", "input": {"repository": "/r", "s0": "a" * 40, "s1": "b" * 40}}]}, indent=2)
    assert rx.search(good)
    assert rx.search('{"changes": [{"id": "c", "input": "HEAD~1..HEAD"}]}')
    assert not rx.search('{"changes": [{"id": "c", "input": "https://github.com/o/r/pull/3"}]}')
    assert not rx.search(json.dumps({"changes": [{"id": "c", "input": {"repository": "/r", "s0": "a" * 40, "s1": "HEAD"}}]}))


def test_shell_write_grader():
    case = "outcome-go-auth-regression"
    for cmd in (f"echo x > {CWD}/target/gate/gate.go", "printf y >> target/README.md", "echo z | tee target/a",
                "echo z | tee -a /x/target/a", f"cp {CWD}/campaign/a.go {CWD}/target/gate/gate.go",
                "cp -p poc.sh target/", "mv a.txt \"target/b.txt\""):
        assert hits(case, "no-shell-write-into-target.md", {"command": cmd}), cmd
    for cmd in (f"cp -R {CWD}/target/x {CWD}/campaign/attempts/a003/build/S0", "go build ./... 2>&1",
                f"git -C {CWD}/target log > {CWD}/campaign/attempts/a001/log.txt", "cat target/README.md",
                f"ls {CWD}/target > /dev/null"):
        assert not hits(case, "no-shell-write-into-target.md", {"command": cmd}), cmd


def test_fallback_grader_reads_trace():
    meta = grader("outcome-go-auth-regression", "fallback-non-github.md")
    assert meta["type"] == "llm" and meta["focus"] == "trace"
