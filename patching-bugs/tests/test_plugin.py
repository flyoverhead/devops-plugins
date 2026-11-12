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
STAGES = ["reproduce-bug", "validate-bug", "implement-patch", "prove-patch"]
ALL = ["patching-bugs", *STAGES]
SHARED = "${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/"
OWN = "${CLAUDE_SKILL_DIR}/scripts/"
READ_ONLY_BASH = {"git rev-parse:*", "git status:*", "git log:*", "git show:*", "git diff:*",
                  "git ls-files:*", "printenv TMPDIR", "mkdir -p:*"}
PREAPPROVED_SCRIPTS = {"records.py:*", "markers.py:*", "verdict.py:*"}
OTHER_TOOLS = {"Read", "Grep", "Glob", "Write", "Agent"}


def split(path):
    _, head, body = path.read_text().split("---", 2)
    return yaml.safe_load(head), body


def tokens(meta):
    return re.findall(r"[\w.*-]+(?:\([^)]*\))?", meta["allowed-tools"])


def grader(case, name):
    return yaml.safe_load((EVALS / case / "graders" / name).read_text().split("---")[1])


def matches(case, name, payload):
    return bool(re.search(grader(case, name)["input_match"], json.dumps(payload)))


@pytest.mark.parametrize("name", ALL)
def test_frontmatter(name):
    meta, body = split(SKILLS / name / "SKILL.md")
    assert meta["name"] == name
    desc = meta["description"]
    assert re.match(r"^[A-Z][a-z]+s ", desc), desc[:30]
    assert "Use when" in desc and "Not for" in desc
    assert re.search(r"— use [a-z-]+:[a-z-]+\.$", desc)
    assert len(desc) <= 600
    assert len(body.strip().splitlines()) <= 250
    assert ("disable-model-invocation" in meta) is (name == "patching-bugs")
    if name == "patching-bugs":
        assert meta["disable-model-invocation"] is True


@pytest.mark.parametrize("name", ALL)
def test_allowed_tools_read_only(name):
    meta, _ = split(SKILLS / name / "SKILL.md")
    for tok in tokens(meta):
        if tok.startswith("Bash("):
            inner = tok[5:-1]
            if inner.startswith("python3 "):
                prefix = OWN if name == "patching-bugs" else SHARED
                assert inner.startswith("python3 " + prefix), tok
                assert inner[len("python3 " + prefix):] in PREAPPROVED_SCRIPTS, tok
            else:
                assert inner in READ_ONLY_BASH, tok
        else:
            assert tok in OTHER_TOOLS, tok
    head = meta["allowed-tools"]
    for banned in ("arms.py", "Edit", "git commit", "git add", "git push", "worktree", "gh ",
                   "go ", "pytest", "npm", "make"):
        assert banned not in head, banned
    assert "Bash" not in tokens(meta)


def test_patcher_cannot_write_without_a_prompt():
    meta, _ = split(SKILLS / "implement-patch" / "SKILL.md")
    assert "Write" not in tokens(meta)


@pytest.mark.parametrize("name", ALL)
def test_limits_list_forbidden_flags(name):
    meta, body = split(SKILLS / name / "SKILL.md")
    limits = body.split("## Limits", 1)[1]
    head = meta["allowed-tools"]
    for cmd in ("git log", "git show", "git diff"):
        if f"Bash({cmd}:*)" in head:
            assert f"`{cmd}`" in limits and "`--output`" in limits, (name, cmd)
    if "Bash(git diff:*)" in head:
        assert "`--ext-diff`" in limits and "`--no-index`" in limits
    if "Bash(git show:*)" in head:
        assert "`--textconv`" in limits


@pytest.mark.parametrize("name", ALL)
def test_script_paths_exist(name):
    text = (SKILLS / name / "SKILL.md").read_text()
    for script in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/((?:\.\./patching-bugs/)?scripts/\w+\.py)", text):
        assert (SKILLS / name / script).resolve().is_file(), script
    for ref in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/(\.\./[\w-]+/references/[\w-]+\.md)", text):
        assert (SKILLS / name / ref).resolve().is_file(), ref


@pytest.mark.parametrize("name", ALL)
def test_references_linked_with_contents(name):
    _, body = split(SKILLS / name / "SKILL.md")
    for ref in (SKILLS / name / "references").glob("*.md") if (SKILLS / name / "references").exists() else []:
        assert f"references/{ref.name}" in body, ref
        lines = ref.read_text().splitlines()
        if len(lines) > 100:
            assert "## Contents" in lines[:30], ref


def flat(name):
    return " ".join(split(SKILLS / name / "SKILL.md")[1].split())


def test_approval_gate_wording():
    text = flat("patching-bugs")
    assert "explicitly allows running the project's commands" in text
    assert "With such a yes, still show the plan" in text
    for stage in STAGES:
        assert "explicitly" in flat(stage) and "plan" in flat(stage), stage


def test_stage_order_in_coordinator():
    _, body = split(SKILLS / "patching-bugs" / "SKILL.md")
    order = ["## 1. Look", "## 2. Run directory", "## 3. Approval gate", "## 4. Preflight build",
             "## 5. Intake", "## 6. Reproduce, then validate blind", "## 7. Patch and prove",
             "## 8. Regression pass", "## 9. Verdict and report"]
    pos = [body.index(h) for h in order]
    assert pos == sorted(pos)
    for stage in STAGES:
        assert f"patching-bugs:{stage}" in body


def test_verdict_precedence_listed_in_order():
    body = " ".join(split(SKILLS / "patching-bugs" / "SKILL.md")[1].split("## 9. Verdict and report")[1].split())
    names = ["1. reproduce", "→ NOT_REPRODUCED;", "→ NOT_READY;", "→ READY_WITH_CONCERNS;", "4. otherwise READY."]
    pos = [body.index(n) for n in names]
    assert pos == sorted(pos)


def test_commit_rules():
    text = flat("implement-patch")
    assert "git -C /abs/checkout commit -s" in text
    for forbidden in ("`--no-verify`", "`--no-gpg-sign`", "`-c commit.gpgsign=false`"):
        assert forbidden in text
    assert "Never push" in text and "Exactly one commit per attempt" in text


def test_validator_is_blind():
    text = flat("validate-bug")
    assert "reproducer's conversation, notes or summary" in text
    assert "Do not fix it" in text


def test_no_agent_files_and_no_corporate_terms():
    assert not (ROOT / "agents").exists()
    for path in ROOT.rglob("*"):
        if path.is_file() and "results" not in path.parts and path.suffix in {".md", ".py", ".sh", ".json", ".yaml"}:
            assert "gl" + "ab" not in path.read_text().lower(), path


def test_records_reference_has_every_record():
    ref = (SKILLS / "patching-bugs" / "references" / "records.md").read_text()
    for name in ("finding.json", "run.json", "reproduce.json", "validate.json", "patch.json",
                 "prove.json", "regression.json", "report-input.json", "manifest.json",
                 "source.json", "arm.json", "PATCH_LOADED", "PATCH_CASE", "PATCH_REACHED"):
        assert name in ref, name


def test_manifest_matches_marketplace_and_claude_md():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    entry = next(p for p in json.loads(MARKET.read_text())["plugins"] if p["name"] == "patching-bugs")
    assert manifest["version"] == entry["version"] == "1.0.0"
    assert manifest["license"] == entry["license"] == "MIT"
    assert manifest["author"] == entry["author"] == {"name": "Aleksandr Letunov",
                                                     "email": "flypatriotka@gmail.com"}
    assert entry["category"] == "security" and "category" not in manifest
    assert "## 2026-11-11" in (ROOT / "CHANGELOG.md").read_text()
    assert "Unreleased" not in (ROOT / "CHANGELOG.md").read_text()
    claude = (ROOT.parent / "CLAUDE.md").read_text()
    assert "| `patching-bugs` | `patching-bugs`, `reproduce-bug`, `validate-bug`, `implement-patch`, `prove-patch` |" in claude


def test_required_eval_cases_present():
    cases = {p.name for p in EVALS.iterdir() if (p / "case.yaml").exists()}
    assert {"trigger-reproduce-first", "negative-plain-fix", "outcome-go-path-escape",
            "outcome-approval-gate", "outcome-upfront-yes"} <= cases


def test_fixtures():
    for setup in EVALS.glob("*/setup.sh"):
        text = setup.read_text()
        assert "git config core.hooksPath /dev/null" in text, setup
        assert "module example.org/snipvault" in text, setup


def test_skill_regexes_scoped():
    for path in EVALS.glob("*/graders/*.md"):
        meta = yaml.safe_load(path.read_text().split("---")[1])
        if meta.get("tool") == "Skill":
            assert "(?:patching-bugs:)?" in meta["input_match"], path


def test_outcome_prompts():
    escape = (EVALS / "outcome-go-path-escape" / "prompt.md").read_text()
    assert "/patching-bugs:patching-bugs" in escape and "go-ahead to build and run" in escape
    gate = (EVALS / "outcome-approval-gate" / "prompt.md").read_text()
    assert "go-ahead" not in gate and "you may" not in gate.lower() and "before anything" not in gate


CWD = "/private/tmp/e-Ab12/home/cwd"
TEMP_OK = ["/private/tmp/e-Ab12/tmp/patching-bugs-target-1a2b3c4/reproduce/reproduce.json",
           "/private/tmp/e-Ab12/tmp/claude-501/patching-bugs-target-1a2b3c4/prove/attempt-1/prove.json",
           "/var/folders/xy/abc123/T/patching-bugs-target-1a2b3c4/finding.json",
           "/tmp/patching-bugs-target-1a2b3c4/run.json"]
TEMP_BAD = [f"{CWD}/notes.md", f"{CWD}/run/finding.json", "/tmp/other/x.json",
            "/private/tmp/e-Ab12/tmp/../home/cwd/x", "/Users/x/tmp/patching-bugs-a/run.json",
            "/etc/tmp/e-Ab12/tmp/x"]


@pytest.mark.parametrize("tool", ["write", "edit"])
def test_upfront_yes_has_write_graders(tool):
    assert (EVALS / "outcome-upfront-yes" / "graders" / f"no-{tool}.md").read_text() == \
        (EVALS / "outcome-go-path-escape" / "graders" / f"no-{tool}.md").read_text()


@pytest.mark.parametrize("tool", ["write", "edit"])
def test_outcome_write_exemptions_anchored(tool):
    case = "outcome-go-path-escape"
    for path in TEMP_OK + [f"{CWD}/target/vault/vault.go", f"{CWD}/target/vault/escape_test.go"]:
        assert not matches(case, f"no-{tool}.md", {"file_path": path}), path
    for path in TEMP_BAD + [f"{CWD}/target/run/reproduce.json", f"{CWD}/target/.git/config",
                            f"{CWD}/target/../x.go", f"{CWD}/target/poc/harness.py"]:
        assert matches(case, f"no-{tool}.md", {"file_path": path}), path
    gate = "outcome-approval-gate"
    for path in TEMP_OK:
        assert not matches(gate, f"no-{tool}.md", {"file_path": path}), path
    for path in TEMP_BAD + [f"{CWD}/target/vault/vault.go"]:
        assert matches(gate, f"no-{tool}.md", {"file_path": path}), path


def test_records_land_under_the_temp_root():
    case = "outcome-go-path-escape"
    assert matches(case, "reproduce-record-in-tmp.md", {"file_path": TEMP_OK[0]})
    sealed = "python3 /p/scripts/records.py manifest {}"
    assert matches(case, "prove-sealed-in-tmp.md", {"command": sealed.format(
        "/private/tmp/e-Ab12/tmp/claude-501/patching-bugs-target-1a2b3c4/prove/attempt-1")})
    for bad in (f"{CWD}/target/patching-bugs-x/prove/attempt-1",
                "/private/tmp/e-Ab12/tmp/patching-bugs-x/prove/attempt-12"):
        assert not matches(case, "prove-sealed-in-tmp.md", {"command": sealed.format(bad)}), bad
    for bad in (f"{CWD}/target/patching-bugs-x/reproduce/reproduce.json",
                "/Users/x/tmp/e-1/tmp/patching-bugs-x/reproduce/reproduce.json",
                "/private/tmp/e-Ab12/tmp/patching-bugs-x/../reproduce/reproduce.json"):
        assert not matches(case, "reproduce-record-in-tmp.md", {"file_path": bad}), bad


def test_commit_graders():
    case = "outcome-go-path-escape"
    signed = ["cd /x/target && git commit -s -m \"fix(vault): keep names inside\"",
              "git -C /x/target commit -s -F /tmp/msg",
              "git -C \"/x/my target\" commit --signoff -m 'fix: x'",
              "git --no-pager -C /x/t commit -sm \"fix(vault): x\"",
              "git -c user.name=x commit -q -s -m x",
              "/opt/homebrew/bin/git commit -s -m x",
              "git add vault && git commit -s <<'EOF'"]
    for cmd in signed:
        assert matches(case, "one-commit.md", {"command": cmd}), cmd
        assert matches(case, "commit-signed-off.md", {"command": cmd}), cmd
    unsigned = ["git commit -m \"fix: x\"", "git -C t commit -S -m x",
                "git commit -m \"a -s b\"", "git commit -F msg.txt -s",
                "git commit <<EOF -s"]
    for cmd in unsigned:
        assert matches(case, "one-commit.md", {"command": cmd}), cmd
        assert not matches(case, "commit-signed-off.md", {"command": cmd}), cmd
    for cmd in ("git log -1 --format=%B", "git rev-parse --verify x^{commit}", "git commit-tree t",
                "git show --stat HEAD", "git rev-parse HEAD\nrec = {'patch_commit': x}",
                "export PATH=/x/bin:$PATH git\n python3 - <<EOF\n commit hash\nEOF",
                "grep \"git commit\" notes.txt", "grep -r 'git commit -s' .",
                "git log --grep commit"):
        assert not matches(case, "one-commit.md", {"command": cmd}), cmd


def test_bypass_grader():
    case = "outcome-go-path-escape"
    for cmd in ("git commit -s --no-verify -m x", "git commit -n -s -m x", "git commit -sn -m x",
                "git -c commit.gpgsign=false commit -s -m x", "git commit --no-gpg-sign -s -m x",
                "git -C /t commit -s -an -m x"):
        assert matches(case, "no-bypass.md", {"command": cmd}), cmd
    for cmd in ("git -c core.hooksPath=/dev/null commit -s -m x",
                "git -C /t -c core.hooksPath= commit -s -m x", "git -c commit.gpgSign=false commit -s -m x"):
        assert matches(case, "no-bypass.md", {"command": cmd}), cmd
    for cmd in ("git commit -s -m \"no -n here\"", "git commit -s -m x", "git commit --signoff -F m",
                "go test -run TestNames ./...", "grep -- \"--no-verify\" SKILL.md",
                "git commit -s -m \"never --no-verify\"", "git commit -s -F msg --no-verify-note",
                "echo gpgsign=false", "git config core.hooksPath", "git -c core.hooksPath=/dev/null status",
                "git commit -s <<'EOF'\n--no-verify\nEOF"):
        assert not matches(case, "no-bypass.md", {"command": cmd}), cmd


def test_push_grader_does_not_span_lines():
    case = "outcome-go-path-escape"
    for cmd in ("git push origin main", "cd t && git -C t push", "git push", "/usr/bin/git push",
                "git --no-pager push -u origin fix", "git -C \"/x/my t\" push"):
        assert matches(case, "no-push.md", {"command": cmd}), cmd
    for cmd in ("git status\necho push later", "git log --oneline", "grep \"git push\" README.md",
                "git stash push -- vault/vault.go"):
        assert not matches(case, "no-push.md", {"command": cmd}), cmd


def test_reproduce_manifest_grader():
    case = "outcome-go-path-escape"
    cmd = "python3 /p/scripts/records.py manifest {}"
    assert matches(case, "reproduce-sealed-in-tmp.md", {"command": cmd.format(
        "/private/tmp/e-Ab12/tmp/claude-501/patching-bugs-target-1a2b3c4/reproduce")})
    for bad in (f"{CWD}/target/patching-bugs-x/reproduce",
                "/private/tmp/e-Ab12/tmp/patching-bugs-x/reproduce-old"):
        assert not matches(case, "reproduce-sealed-in-tmp.md", {"command": cmd.format(bad)}), bad


def test_build_and_arms_graders():
    case = "outcome-go-path-escape"
    run = 'python3 /p/scripts/arms.py run --repo /t --build \'["go","build","-o","bin/snipvault","./cmd/snipvault"]\''
    assert matches(case, "three-arm-ran.md", {"command": run})
    assert matches(case, "go-build.md", {"command": run})
    assert matches(case, "go-build.md", {"command": "cd target && go build ./..."})
    assert not matches(case, "three-arm-ran.md", {"command": "python3 /p/scripts/arms.py cases --repo /t"})
    gate = "outcome-approval-gate"
    for cmd in (run, "go test ./...", "python3 /p/arms.py cases --x", "git commit -s -m x",
                "./bin/snipvault save x"):
        assert matches(gate, "nothing-ran.md", {"command": cmd}), cmd
    for cmd in ("git status --porcelain", "git rev-parse HEAD", "go version",
                "python3 /p/scripts/records.py guidance /t/run --repo /x --commit abc"):
        assert not matches(gate, "nothing-ran.md", {"command": cmd}), cmd



def test_upfront_yes_case():
    prompt = (EVALS / "outcome-upfront-yes" / "prompt.md").read_text()
    assert "You may build and run the project's code" in prompt
    text = (EVALS / "outcome-upfront-yes" / "graders" / "plan-before-build.md").read_text()
    rx = re.compile(text.split("---", 2)[2].strip())
    skill = json.dumps({"content": (SKILLS / "patching-bugs" / "SKILL.md").read_text()})
    plan = json.dumps({"type": "tool_use", "name": "Write", "input": {
        "file_path": "/tmp/e-1/tmp/patching-bugs-target-abc1234/plan.md", "content": "Plan before running"}})
    build = json.dumps({"command": "python3 arms.py cases --build '[\"go\",\"build\",\"-o\",\"bin/x\"]'"})
    assert not rx.search(skill)
    assert rx.search(skill + "\n" + plan + "\n" + build)
    assert not rx.search(skill + "\n" + build + "\n" + plan)
    assert not rx.search(skill + "\n" + json.dumps({"command": "go build ./..."}) + "\n" + plan)
    gate = (EVALS / "outcome-approval-gate" / "prompt.md").read_text()
    assert "fix SV-14 and commit it" in gate and "tell me" not in gate
