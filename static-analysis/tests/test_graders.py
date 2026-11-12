import json
import re
from pathlib import Path

import pytest
import yaml

EVALS = Path(__file__).resolve().parents[1] / 'evals'
CODEQL_OUTCOMES = ['outcome-codeql-licence-stop', 'outcome-codeql-local-oss', 'outcome-codeql-plan-gate']


def meta(case, name):
    return yaml.safe_load((EVALS / case / 'graders' / name).read_text().split('---')[1])


def test_skill_regexes_scoped_to_plugin():
    for grader in EVALS.glob('*/graders/*.md'):
        m = yaml.safe_load(grader.read_text().split('---')[1])
        if m.get('tool') == 'Skill':
            assert re.search(r'"\(\?:static-analysis:\)\?(?:codeql|semgrep|sarif-parsing)"',
                             m['input_match']), grader


@pytest.mark.parametrize('case', CODEQL_OUTCOMES + ['outcome-semgrep-plan-gate'])
def test_outcomes_forbid_edits(case):
    m = meta(case, 'no-edit.md')
    assert m['tool'] == 'Edit' and m['max'] == 0 and 'input_match' not in m


def test_semgrep_plan_gate_forbids_all_writes():
    m = meta('outcome-semgrep-plan-gate', 'no-write.md')
    assert m['tool'] == 'Write' and m['max'] == 0 and 'input_match' not in m


@pytest.mark.parametrize('case', CODEQL_OUTCOMES)
@pytest.mark.parametrize('path,flagged', [
    ('/private/tmp/e-Ab12/tmp/claude-501/codeql-svc_1/rulesets.txt', False),
    ('/var/folders/l_/95d2ww7x/T/codeql-svc_2/extensions/models.yml', False),
    ('/tmp/codeql-svc_1/plan.md', False),
    ('/private/tmp/e-Ab12/home/cwd/codeql-svc_1/rulesets.txt', True),
    ('/private/tmp/e-Ab12/home/cwd/tmp/codeql-svc_1/rulesets.txt', True),
    ('/tmp/codeql-svc_1/../../private/tmp/e-Ab12/home/cwd/main.go', True),
    ('/tmp/codeql-svc_1/', True),
    ('/private/tmp/e-Ab12/home/cwd/main.go', True),
])
def test_codeql_no_write_anchor(case, path, flagged):
    rx = re.compile(meta(case, 'no-write.md')['input_match'])
    assert bool(rx.search(json.dumps({'file_path': path, 'content': 'x'}))) is flagged


@pytest.mark.parametrize('skill,hit', [
    ('codeql', True), ('static-analysis:codeql', True), ('other:codeql', False), ('codeql-x', False),
])
def test_codeql_fired_regex(skill, hit):
    rx = re.compile(meta('trigger-codeql', 'skill-fired.md')['input_match'])
    assert bool(rx.search(json.dumps({'skill': skill}))) is hit


def test_semgrep_version_probe_exact():
    front = (EVALS.parent / 'skills/semgrep/SKILL.md').read_text().split('---')[1]
    tools = re.search(r'^allowed-tools: (.*)$', front, re.M).group(1)
    assert 'Bash(semgrep --version --disable-version-check)' in tools
    assert 'Bash(semgrep --version:' not in tools and 'semgrep --version:*' not in tools
