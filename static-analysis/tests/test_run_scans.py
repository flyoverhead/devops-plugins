import json
import os

import pytest

from conftest import SEMGREP_SCRIPTS, require, run, write_exe

RUNNER = str(SEMGREP_SCRIPTS / 'run-scans.sh')

STUB_SEMGREP = r'''#!/usr/bin/env bash
case " $* " in *" --version "*) echo "${STUB_VERSION_OUT:-1.0.0}"; exit 0 ;; esac
cfg="" json="" sarif=""
for a in "$@"; do
  case "$a" in
    --config=*) cfg="${a#--config=}" ;;
    --json-output=*) json="${a#--json-output=}" ;;
    --sarif-output=*) sarif="${a#--sarif-output=}" ;;
  esac
done
printf '%s\n' "$*" >> "${STUB_LOG:?}"
case "$cfg" in
  *fail*) echo "boom: rule pack exploded" >&2; exit 7 ;;
  *partial*) rc=2 ;;
  *) rc=0 ;;
esac
case "$cfg" in
  *empty*) scanned='[]' ;;
  *) scanned='["main.go"]' ;;
esac
cat > "$json" <<JSON
{"results": [{"check_id": "demo.rule", "path": "main.go", "start": {"line": 3}, "extra": {}}], "errors": [], "paths": {"scanned": $scanned}}
JSON
cat > "$sarif" <<JSON
{"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "Semgrep OSS", "rules": [{"id": "demo.rule"}]}}, "results": [{"ruleId": "demo.rule", "message": {"text": "x"}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "main.go"}, "region": {"startLine": 3}}}]}]}]}
JSON
exit $rc
'''


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / 'repo'
    r.mkdir()
    (r / 'main.go').write_text('package main\n\nfunc main() {}\n')
    return r


def plan(tmp_path, data, name='rulesets.json'):
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return p


def load_scans(out_dir):
    with open(out_dir / 'scans.json') as fh:
        return json.load(fh)


def runner(*args, env=None, timeout=60):
    return run(["bash", RUNNER, *map(str, args)], env=env, timeout=timeout)


def base_args(repo, out, rules, mode='run-all'):
    return ['--target', repo, '--output-dir', out, '--mode', mode, '--rulesets', rules]


def test_help_lists_flags():
    res = runner('--help')
    assert res.returncode == 0
    for flag in ('--target', '--output-dir', '--mode', '--rulesets', '--pro', '--jobs',
                 '--max-target-bytes', '--dry-run'):
        assert flag in res.stdout


@pytest.mark.parametrize('mutate, message', [
    (lambda a: a.__setitem__(1, 'relative/repo'), 'absolute'),
    (lambda a: a.__setitem__(3, 'relative/out'), 'absolute'),
    (lambda a: a.__setitem__(5, 'everything'), 'run-all or important-only'),
    (lambda a: a.__setitem__(7, '/nonexistent/rulesets.json'), 'cannot read'),
    (lambda a: a.extend(['--jobs', 'four']), 'whole number above zero'),
    (lambda a: a.extend(['--jobs', '0']), 'whole number above zero'),
    (lambda a: a.extend(['--max-target-bytes', '20M']), 'plain digits'),
])
def test_argument_validation(tmp_path, repo, mutate, message):
    args = base_args(repo, tmp_path / 'out', plan(tmp_path, {'baseline': ['p/default']}))
    mutate(args)
    res = runner(*args)
    assert res.returncode == 1
    assert message in res.stderr


def test_output_dir_equal_to_target_refused(tmp_path, repo):
    res = runner(*base_args(repo, repo, plan(tmp_path, {'baseline': ['p/default']})))
    assert res.returncode == 1
    assert 'must not be the target' in res.stderr


def test_output_dir_equal_to_target_via_symlink_refused(tmp_path, repo):
    link = tmp_path / 'link'
    link.symlink_to(repo)
    res = runner(*base_args(repo, link, plan(tmp_path, {'baseline': ['p/default']})))
    assert res.returncode == 1


@pytest.mark.parametrize('data, message', [
    ({'go': ['https://github.com/a/b']}, 'not a registry id'),
    ({'baseline': ['/abs/rules']}, 'not a registry id'),
    ({'third_party': ['p/default']}, 'https git URL'),
    ({'third_party': ['http://github.com/a/b']}, 'https git URL'),
    ({'local': ['relative/rules']}, 'absolute directory'),
    ({}, 'no scans'),
    ({'baseline': 'p/default'}, 'arrays'),
])
def test_plan_validation(tmp_path, repo, data, message):
    res = runner(*base_args(repo, tmp_path / 'out', plan(tmp_path, data)), '--dry-run')
    assert res.returncode == 1
    assert message in res.stderr


def test_local_dir_without_rules_refused(tmp_path, repo):
    empty = tmp_path / 'norules'
    empty.mkdir()
    res = runner(*base_args(repo, tmp_path / 'out', plan(tmp_path, {'local': [str(empty)]})), '--dry-run')
    assert res.returncode == 1
    assert 'no .yml/.yaml rule files' in res.stderr


def test_dry_run_commands(tmp_path, repo):
    data = {
        'baseline': ['p/default', 'p/secrets'],
        'golang': ['p/golang', 'p/default'],
        'go': ['p/golang'],
        'typescript': ['p/typescript'],
        'mystery': ['p/whatever'],
        'third_party': ['https://github.com/example/rules', 'https://github.com/example/rules.git/'],
    }
    out = tmp_path / 'out'
    res = runner(*base_args(repo, out, plan(tmp_path, data), mode='important-only'), '--dry-run')
    assert res.returncode == 0, res.stderr
    lines = [l for l in res.stdout.splitlines() if 'semgrep scan' in l]
    assert len(lines) == 6
    assert all('--metrics=off' in l and '--disable-version-check' in l for l in lines)
    assert all('--severity WARNING --severity ERROR' in l for l in lines)
    go = [l for l in lines if 'p/golang' in l]
    assert len(go) == 1 and r'--include=\*.go' in go[0]
    ts = [l for l in lines if 'p/typescript' in l][0]
    assert r'\*.mts' not in ts and r'\*.cts' not in ts
    assert '--include' not in [l for l in lines if 'p/whatever' in l][0]
    assert sum('git clone --quiet --depth=1' in l for l in res.stdout.splitlines()) == 1
    assert '# alsoShared: go/p/default' in res.stdout
    assert '# unscoped: mystery' in res.stdout
    assert not out.exists()


def test_exclude_pattern_when_output_inside_target(tmp_path, repo):
    res = runner(*base_args(repo, repo / 'scan-out', plan(tmp_path, {'baseline': ['p/default']})), '--dry-run')
    assert res.returncode == 0
    assert '--exclude=scan-out' in res.stdout
    assert '# excludePattern: scan-out' in res.stdout


def test_dockerfile_globs_exclude_variants(tmp_path, repo):
    res = runner(*base_args(repo, tmp_path / 'out', plan(tmp_path, {'dockerfile': ['p/dockerfile']})), '--dry-run')
    line = [l for l in res.stdout.splitlines() if 'semgrep scan' in l][0]
    assert '--include=Dockerfile' in line
    assert 'Containerfile' not in line and 'Dockerfile.prod' not in line


def stub_env(stub_bin, tmp_path):
    write_exe(stub_bin / 'semgrep', STUB_SEMGREP)
    return {'PATH': f'{stub_bin}{os.pathsep}{os.environ["PATH"]}', 'STUB_LOG': str(tmp_path / 'semgrep.log')}


def test_stubbed_run_records_success_partial_failed_and_coverage(tmp_path, repo, stub_bin):
    env = stub_env(stub_bin, tmp_path)
    data = {'baseline': ['p/default', 'p/fail-pack'], 'go': ['p/partial-pack', 'p/empty-pack']}
    out = tmp_path / 'out'
    (out / 'raw').mkdir(parents=True)
    (out / 'raw' / 'stale.sarif').write_text('{}')
    res = runner(*base_args(repo, out, plan(tmp_path, data)), '--jobs', '2', env=env)
    assert res.returncode == 0, res.stderr
    scans = load_scans(out)
    assert res.stdout.strip() == str(out / 'scans.json')
    assert not (out / 'raw' / 'stale.sarif').exists()
    ok = {s['ruleset']: s for s in scans['scans']}
    assert set(ok) == {'p/default', 'p/partial-pack', 'p/empty-pack'}
    assert ok['p/partial-pack']['partial'] is True and ok['p/partial-pack']['exitCode'] == 2
    assert ok['p/default']['findings'] == 1 and ok['p/default']['lang'] == 'all'
    assert [f['ruleset'] for f in scans['failed']] == ['p/fail-pack']
    assert 'boom' in scans['failed'][0]['error']
    assert scans['coveredNothing'] == ['go/p/empty-pack']
    for key in ('outputDir', 'rawDir', 'reposPath', 'mode', 'pro', 'excludePattern', 'maxTargetBytes',
                'skipped', 'alsoShared', 'unscoped', 'oversized'):
        assert key in scans
    log = (tmp_path / 'semgrep.log').read_text()
    assert '--metrics=off' in log and '--config=auto' not in log


def test_stubbed_all_failed_exits_1(tmp_path, repo, stub_bin):
    env = stub_env(stub_bin, tmp_path)
    out = tmp_path / 'out'
    res = runner(*base_args(repo, out, plan(tmp_path, {'baseline': ['p/fail-one']})), env=env)
    assert res.returncode == 1
    assert len(load_scans(out)['failed']) == 1


def test_oversized_files_reported(tmp_path, repo, stub_bin):
    env = stub_env(stub_bin, tmp_path)
    (repo / 'big.go').write_text('package main\n' + '// x\n' * 100)
    out = tmp_path / 'out'
    res = runner(*base_args(repo, out, plan(tmp_path, {'go': ['p/golang']})), '--max-target-bytes', '100', env=env)
    assert res.returncode == 0, res.stderr
    assert load_scans(out)['oversized'] == ['big.go']


def test_trust_anchor_fallback(tmp_path, repo, stub_bin):
    env = stub_env(stub_bin, tmp_path)
    env['STUB_VERSION_OUT'] = 'ca-certs: no trust anchor file found'
    env['SEMGREP_FALLBACK_CA'] = '/etc/ssl/cert.pem'
    res = runner(*base_args(repo, tmp_path / 'out', plan(tmp_path, {'baseline': ['p/default']})), env=env)
    assert res.returncode == 0
    assert 'SSL_CERT_FILE=/etc/ssl/cert.pem' in res.stderr


def test_real_semgrep_local_rules(tmp_path, repo):
    require('semgrep')
    require('jq')
    (repo / 'main.go').write_text(
        'package main\n\nimport "os/exec"\n\nfunc main() {\n\t_ = exec.Command("sh", "-c", "id")\n}\n')
    rules = tmp_path / 'rules'
    rules.mkdir()
    (rules / 'exec.yml').write_text(
        'rules:\n  - id: demo-exec\n    languages: [go]\n    severity: ERROR\n'
        '    message: exec.Command call\n    pattern: exec.Command(...)\n')
    out = tmp_path / 'out'
    res = runner(*base_args(repo, out, plan(tmp_path, {'local': [str(rules)]})), timeout=300)
    assert res.returncode == 0, res.stderr
    scans = load_scans(out)
    assert scans['scans'][0]['findings'] == 1
