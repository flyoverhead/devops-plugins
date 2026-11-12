import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / 'ansible/skills/role-checker'
YAML_EQUAL = CHECKER / 'scripts/yaml_equal.py'
AGENTS = {
    'ansible': (REPO / 'ansible/agents/ansible-engineer.md',
                ['Read', 'Grep', 'Glob', 'Bash(ansible-lint:*)', 'Bash(yamllint:*)',
                 'Bash(ansible-playbook --syntax-check:*)', 'Bash(git log:*)']),
    'terraform': (REPO / 'terraform/agents/terraform-engineer.md',
                  ['Read', 'Grep', 'Glob', 'Bash(terraform fmt -check:*)',
                   'Bash(terraform validate:*)', 'Bash(git log:*)']),
}


def front(path):
    _, head, body = path.read_text().split('---', 2)
    return yaml.safe_load(head), body


def run(*args, stdin=None):
    return subprocess.run([sys.executable, str(YAML_EQUAL), *args], input=stdin,
                          capture_output=True, text=True)


@pytest.fixture
def files(tmp_path):
    old = tmp_path / 'old.yml'
    old.write_text("---\nnginx_port: 80\nnginx_enabled: True\nnginx_name: 'web'\n")
    same = tmp_path / 'same.yml'
    same.write_text('nginx_name: web\nnginx_enabled: true\nnginx_port: 80\n')
    diff = tmp_path / 'diff.yml'
    diff.write_text('nginx_name: web\nnginx_enabled: true\nnginx_port: 8080\n')
    return old, same, diff


def test_yaml_equal_ignores_quoting_order_and_bool_case(files):
    old, same, _ = files
    res = run(str(old), str(same))
    assert res.returncode == 0 and res.stdout.strip() == 'equal'


def test_yaml_equal_reports_value_change(files):
    old, _, diff = files
    res = run(str(old), str(diff))
    assert res.returncode == 1 and res.stdout.strip() == 'different'


def test_yaml_equal_reads_stdin(files):
    old, same, diff = files
    assert run('-', str(same), stdin=old.read_text()).returncode == 0
    assert run('-', str(diff), stdin=old.read_text()).returncode == 1


@pytest.mark.parametrize('args', [[], ['a'], ['-', '-'], ['/nonexistent/a.yml', '/nonexistent/b.yml']])
def test_yaml_equal_errors(args):
    assert run(*args).returncode == 2


def test_yaml_equal_rejects_bad_yaml(tmp_path, files):
    bad = tmp_path / 'bad.yml'
    bad.write_text('a: [1, 2\n')
    assert run(str(bad), str(files[0])).returncode == 2


def test_role_checker_preallows_only_the_script():
    tools = front(CHECKER / 'SKILL.md')[0]['allowed-tools']
    assert 'python3 -c' not in tools
    assert 'Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/yaml_equal.py:*)' in tools
    assert re.findall(r'Bash\(python3[^)]*\)', tools) == [
        'Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/yaml_equal.py:*)']
    restructure = (CHECKER / 'references/RESTRUCTURE.md').read_text()
    assert 'python3 -c' not in restructure
    assert 'python3 ${CLAUDE_SKILL_DIR}/scripts/yaml_equal.py - roles/<role>/defaults/main.yml' in restructure


@pytest.mark.parametrize('name', sorted(AGENTS))
def test_engineer_agent_tools_scoped(name):
    path, expected = AGENTS[name]
    meta, body = front(path)
    tools = [t.strip() for t in meta['tools'].split(',')]
    assert tools == expected
    assert 'Bash' not in tools and 'Edit' not in tools and 'Write' not in tools
    limits = body.split('## Limits', 1)[1].split('\n## ', 1)[0]
    for flag in ('`--output`', '`--ext-diff`', '`--textconv`', '`--no-ext-diff --no-textconv`'):
        assert flag in limits, (name, flag)


def test_ansible_engineer_limits():
    limits = front(AGENTS['ansible'][0])[1].split('## Limits', 1)[1]
    assert '`--fix`' in limits and '`--write`' in limits


def test_terraform_engineer_limits():
    limits = front(AGENTS['terraform'][0])[1].split('## Limits', 1)[1]
    assert '`-check`' in limits and '`-write=true`' in limits
