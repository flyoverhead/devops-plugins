import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
NAME = "semgrep-rule-variant-creator"
SKILL = ROOT / "skills" / NAME / "SKILL.md"
GRADERS = ROOT / "evals" / "outcome-python-to-go-ts" / "graders"
SEMGREP_CMD = re.compile(r"^(?:\w+=\S+ )*semgrep\b")


def split(path):
    _, head, body = path.read_text().split("---", 2)
    return yaml.safe_load(head), body


def tools():
    return re.findall(r"[\w.*-]+(?:\([^)]*\))?", split(SKILL)[0]["allowed-tools"])


def limits():
    body = split(SKILL)[1]
    return " ".join(body.split("## Limits", 1)[1].split("\n## ", 1)[0].split())


def grader(name):
    return yaml.safe_load((GRADERS / name).read_text().split("---")[1])


def test_frontmatter_basics():
    meta, body = split(SKILL)
    assert meta["name"] == NAME
    desc = meta["description"]
    assert "\n" not in desc and len(desc) <= 1536 and "Use when" in desc
    assert "model" not in meta
    assert len(body.strip().splitlines()) <= 250


def test_no_bare_bash_and_semgrep_runs_local():
    for tok in tools():
        assert tok != "Bash", tok
        if not tok.startswith("Bash("):
            continue
        cmd = tok[5:-1]
        if SEMGREP_CMD.match(cmd):
            assert "--metrics=off" in cmd or "SEMGREP_ENABLE_VERSION_CHECK=0" in cmd, tok


def test_limits_block():
    block = limits()
    for item in ("--metrics=off --disable-version-check", "`-o`", "--output", "--*-output=",
                 "--autofix", "--config http://", "https://"):
        assert item in block, item


def test_manifest_matches_marketplace():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT.parent / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == NAME)
    assert entry["version"] == plugin["version"]
    assert entry["description"] == plugin["description"]
    assert "category" not in plugin


def test_skill_regexes_scoped():
    for path in (ROOT / "evals").glob("*/graders/*.md"):
        meta = yaml.safe_load(path.read_text().split("---")[1])
        if meta.get("tool") == "Skill":
            assert f"(?:{NAME}:)?{NAME}" in meta["input_match"], path


@pytest.mark.parametrize("name", ["no-edit.md", "no-write.md"])
@pytest.mark.parametrize("path,flagged", [
    ("/private/tmp/e-Ab12/home/cwd/rules/cmd-injection/cmd-injection.yaml", False),
    ("/private/tmp/e-Ab12/home/cwd/rules/cmd-injection/cmd-injection.ts", False),
    ("/var/folders/l_/95d2ww7x/T/proj/rules/x/x.yml", False),
    ("/private/tmp/e-Ab12/home/cwd/rules/../internal/probe/handler.go", True),
    ("/private/tmp/e-Ab12/home/cwd/../../../etc/rules/x/x.yaml", True),
    ("/private/tmp/e-Ab12/home/cwd/rules/x/../x.yaml", True),
    ("/private/tmp/e-Ab12/home/cwd/rules/x/..yaml", True),
    ("/private/tmp/e-Ab12/home/cwd/internal/probe/handler.go", True),
    ("/Users/someone/project/rules/x/x.yaml", True),
    ("/private/tmp/e-Ab12/home/cwd/rules/x/x.yaml.bak", True),
])
def test_write_edit_exemption_anchored(name, path, flagged):
    rx = re.compile(grader(name)["input_match"])
    assert bool(rx.search(json.dumps({"file_path": path, "content": "x"}))) is flagged


def test_show_uses_env_version_check():
    text = SKILL.read_text() + (SKILL.parent / "references" / "applicability.md").read_text()
    for line in text.splitlines():
        if "semgrep show" in line and "rejects" not in line:
            assert "SEMGREP_ENABLE_VERSION_CHECK=0 semgrep show" in line, line
