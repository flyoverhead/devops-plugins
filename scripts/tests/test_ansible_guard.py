import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent.parent / 'ansible/hooks/guard-playbook.sh'
MESSAGE = ('Blocked: run ansible-playbook against real hosts yourself; '
           'Claude may use --check, --syntax-check or --list-*.')

BLOCK = [
    'ansible-playbook site.yml',
    'ansible-playbook -i inventory site.yml',
    'ansible-playbook site.yml -e check=true',
    'ansible-playbook site.yml --diff',
    'ansible-playbook -vvv site.yml',
    'ansible-playbook -D site.yml',
    'ansible-playbook site.yml --tags checks',
    'ansible-playbook -e "x=-C" site.yml',
    'ansible-playbook site.yml # --check',
    'ansible-playbook site.yml  # -C',
    'echo start; ansible-playbook site.yml',
    'true && ansible-playbook site.yml',
    'false || ansible-playbook site.yml',
    'cat hosts | ansible-playbook site.yml',
    'ansible-playbook a.yml --check && ansible-playbook b.yml',
    'ansible-playbook a.yml -C; ansible-playbook b.yml',
    'echo hi\nansible-playbook site.yml',
    '(ansible-playbook site.yml)',
    '(cd roles && ansible-playbook site.yml)',
    'echo $(ansible-playbook site.yml)',
    'x=`ansible-playbook site.yml`',
    'echo "$(ansible-playbook site.yml)"',
    "bash -c 'ansible-playbook site.yml'",
    'sh -c "ansible-playbook site.yml"',
    "bash -lc 'ansible-playbook site.yml'",
    "bash -c 'ansible-playbook a.yml --check; ansible-playbook b.yml'",
    'sudo ansible-playbook site.yml',
    'sudo -u deploy ansible-playbook site.yml',
    'env ansible-playbook site.yml',
    'env ANSIBLE_FORCE_COLOR=1 ansible-playbook site.yml',
    'ANSIBLE_FORCE_COLOR=1 ansible-playbook site.yml',
    'nohup ansible-playbook site.yml',
    'time ansible-playbook site.yml',
    'timeout 60 ansible-playbook site.yml',
    'nice -n 5 ansible-playbook site.yml',
    'exec ansible-playbook site.yml',
    'command ansible-playbook site.yml',
    'echo site.yml | xargs ansible-playbook',
    'echo site.yml | xargs -I{} ansible-playbook {}',
    'uv run ansible-playbook site.yml',
    'poetry run ansible-playbook site.yml',
    'pipx run --spec ansible-core ansible-playbook site.yml',
    'pipenv run ansible-playbook site.yml',
    './venv/bin/ansible-playbook site.yml',
    '/usr/bin/ansible-playbook site.yml',
    'sudo -E env FOO=1 nohup ansible-playbook site.yml',
    'for h in a b; do ansible-playbook -l $h site.yml; done',
    'if true; then ansible-playbook site.yml; fi',
    'ansible-playbook site.yml > out.log 2>&1',
    'ansible-playbook site.yml &',
    'find . -name site.yml -exec ansible-playbook {} \\;',
    'ansible-playbook site.yml --checkmode',
    'ansible-playbook -e @vars.yml site.yml',
    'echo ok && bash -c "sudo ansible-playbook site.yml"',
    'eval "ansible-playbook site.yml"',
    'ansible-playbook site.yml --tags -C',
    'ansible-playbook site.yml --limit --check',
    "su -c 'ansible-playbook site.yml' deploy",
    "su deploy -c 'ansible-playbook site.yml'",
    "su -l -c 'ansible-playbook a.yml --check; ansible-playbook b.yml'",
]

ALLOW = [
    'ansible-playbook site.yml --check',
    'ansible-playbook --check site.yml',
    'ansible-playbook -C site.yml',
    'ansible-playbook -vC site.yml',
    'ansible-playbook -CD site.yml',
    'ansible-playbook -vvvC site.yml',
    'ansible-playbook site.yml --check --diff',
    'ansible-playbook site.yml --syntax-check',
    'ansible-playbook site.yml --list-tasks',
    'ansible-playbook site.yml --list-hosts',
    'ansible-playbook site.yml --list-tags',
    'ansible-playbook a.yml --check && ansible-playbook b.yml --syntax-check',
    "bash -c 'ansible-playbook site.yml --check'",
    'sh -c "ansible-playbook site.yml -C"',
    'sudo ansible-playbook site.yml --check',
    'env ANSIBLE_FORCE_COLOR=1 ansible-playbook -C site.yml',
    'timeout 60 ansible-playbook --list-tasks site.yml',
    'uv run ansible-playbook site.yml --check',
    './venv/bin/ansible-playbook site.yml --syntax-check',
    '(ansible-playbook site.yml --check)',
    'echo $(ansible-playbook site.yml --list-hosts)',
    'ansible-playbook -i inventory -e x=1 site.yml -C',
    'ansible-playbook -e foo=bar -vC site.yml',
    'ansible-playbook site.yml --tags=x -C',
    'ansible-playbook site.yml --tags x --check',
    "su -c 'ansible-playbook site.yml --check' deploy",
    'ls -la',
    'git status',
    'ansible-lint roles/',
    'ansible-playbook-lint site.yml',
    'cat notes/ansible-playbook.md',
    'grep ansible-playbook README.md',
    'grep -rn "ansible-playbook" docs',
    'echo ansible-playbook site.yml',
    'man ansible-playbook',
    'which ansible-playbook',
    'ansible all -m ping',
    'ansible-galaxy install -r requirements.yml',
    'ansible-inventory --list',
    'molecule test',
    'ls roles # ansible-playbook site.yml',
    'echo "ansible-playbook site.yml"',
    "echo 'run ansible-playbook site.yml later'",
    '',
]


def run_guard(command, env=None, raw=None):
    payload = raw if raw is not None else json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command}})
    return subprocess.run([shutil.which('bash'), str(GUARD)], input=payload, capture_output=True, text=True, env=env, timeout=20)


def test_table_sizes():
    assert len(BLOCK) >= 30
    assert len(ALLOW) >= 25


@pytest.mark.parametrize('command', BLOCK)
def test_blocks(command):
    result = run_guard(command)
    assert result.returncode == 2, result.stderr
    assert result.stderr.strip() == MESSAGE


@pytest.mark.parametrize('command', ALLOW)
def test_allows(command):
    result = run_guard(command)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ''


def shim_env(tools):
    shim = tempfile.mkdtemp()
    for tool in tools:
        found = shutil.which(tool)
        assert found, tool
        os.symlink(found, os.path.join(shim, tool))
    return shim, {'PATH': shim, 'HOME': shim}


def test_python_fallback_without_jq():
    shim, env = shim_env(['cat', 'python3'])
    try:
        blocked = run_guard('ansible-playbook site.yml', env=env)
        allowed = run_guard('ansible-playbook site.yml --check', env=env)
    finally:
        shutil.rmtree(shim)
    assert blocked.returncode == 2
    assert allowed.returncode == 0


def test_no_parser_available_warns_and_allows():
    shim, env = shim_env(['cat'])
    try:
        result = run_guard('ansible-playbook site.yml', env=env)
    finally:
        shutil.rmtree(shim)
    assert result.returncode == 0
    assert 'skipped' in result.stderr


def test_non_bash_payload_is_ignored():
    result = run_guard('', raw=json.dumps({'tool_name': 'Read', 'tool_input': {'file_path': 'x'}}))
    assert result.returncode == 0


def test_malformed_json_is_allowed():
    assert run_guard('', raw='not json').returncode == 0


@pytest.mark.parametrize('command', [
    'ansible-playbook --version',
    'ansible-playbook --help',
    'cat <<EOF\nansible-playbook site.yml\nEOF',
])
def test_known_false_positives_are_blocked(command):
    assert run_guard(command).returncode == 2
