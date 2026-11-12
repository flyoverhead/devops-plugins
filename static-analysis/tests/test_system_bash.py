import json
import os
from pathlib import Path

import pytest

from conftest import CODEQL_SCRIPTS, SEMGREP_SCRIPTS, run, write_exe
from test_codeql_scripts import STUB_CODEQL
from test_run_scans import STUB_SEMGREP

SYSTEM_BASH = Path('/bin/bash')
pytestmark = pytest.mark.skipif(not SYSTEM_BASH.exists(), reason='not run: /bin/bash missing')


def stubs(stub_bin, tmp_path):
    write_exe(stub_bin / 'codeql', STUB_CODEQL)
    write_exe(stub_bin / 'semgrep', STUB_SEMGREP)
    return {'PATH': f'{stub_bin}{os.pathsep}{os.environ["PATH"]}', 'STUB_LOG': str(tmp_path / 'semgrep.log')}


def test_generate_suite_without_packs(tmp_path, stub_bin):
    env = stubs(stub_bin, tmp_path)
    for mode in ('run-all', 'important-only'):
        res = run([str(SYSTEM_BASH), str(CODEQL_SCRIPTS / 'generate_suite.sh'), mode],
                  env={**env, 'CODEQL_LANG': 'go', 'OUTPUT_DIR': str(tmp_path / 'out'),
                       'INSTALLED_THIRD_PARTY_PACKS': ''})
        assert res.returncode == 0, res.stderr
        assert 'unbound' not in res.stderr


def test_generate_suite_with_unset_pack_variable(tmp_path, stub_bin):
    env = stubs(stub_bin, tmp_path)
    env.pop('INSTALLED_THIRD_PARTY_PACKS', None)
    res = run(['env', '-u', 'INSTALLED_THIRD_PARTY_PACKS', str(SYSTEM_BASH),
               str(CODEQL_SCRIPTS / 'generate_suite.sh'), 'run-all'],
              env={**env, 'CODEQL_LANG': 'go', 'OUTPUT_DIR': str(tmp_path / 'out')})
    assert res.returncode == 0, res.stderr


def test_find_databases_with_no_roots(tmp_path, stub_bin):
    env = stubs(stub_bin, tmp_path)
    repo = tmp_path / 'repo'
    repo.mkdir()
    res = run([str(SYSTEM_BASH), str(CODEQL_SCRIPTS / 'find_databases.sh')],
              env={**env, 'TMPDIR': str(tmp_path / 'empty-tmp'), 'OUTPUT_DIR': ''}, cwd=repo)
    assert res.returncode == 0, res.stderr
    assert res.stdout == ''


def test_build_log_sources(tmp_path):
    res = run([str(SYSTEM_BASH), '-c', f'. {CODEQL_SCRIPTS / "build_log.sh"} || exit 9; run_logged true; echo rc=$?'],
              env={'OUTPUT_DIR': str(tmp_path), 'LOG_FILE': ''})
    assert 'rc=0' in res.stdout, res.stderr


@pytest.mark.parametrize('dry', [True, False])
def test_run_scans_baseline_only(tmp_path, stub_bin, dry):
    env = stubs(stub_bin, tmp_path)
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'main.go').write_text('package main\n')
    plan = tmp_path / 'rulesets.json'
    plan.write_text(json.dumps({'baseline': ['p/default'], 'third_party': [], 'local': []}))
    out = tmp_path / 'out'
    cmd = [str(SYSTEM_BASH), str(SEMGREP_SCRIPTS / 'run-scans.sh'), '--target', str(repo),
           '--output-dir', str(out), '--mode', 'run-all', '--rulesets', str(plan)]
    res = run(cmd + (['--dry-run'] if dry else []), env=env)
    assert res.returncode == 0, res.stderr
    assert 'unbound' not in res.stderr
    if not dry:
        scans = json.loads((out / 'scans.json').read_text())
        assert scans['alsoShared'] == [] and scans['unscoped'] == [] and scans['oversized'] == []
