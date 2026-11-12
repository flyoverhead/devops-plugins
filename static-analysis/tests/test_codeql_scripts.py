import json
import os
import zipfile

import pytest
import yaml

from conftest import CODEQL_SCRIPTS, path_without, require, run, write_exe

STUB_CODEQL = r'''#!/usr/bin/env bash
case "$1 $2" in
  "resolve queries")
    case "${STUB_RESOLVE:-ok}" in
      ok) echo '["/q/a.ql", "/q/b.ql"]' ;;
      empty) echo '[]' ;;
      badjson) echo 'not json' ;;
      notlist) echo '{"a": 1}' ;;
      fail) echo "resolve exploded" >&2; exit 3 ;;
    esac ;;
  "resolve database")
    [ -f "${@: -1}/.stub-valid" ] && exit 0
    exit 1 ;;
  *) echo "codeql stub: $*" >&2; exit 0 ;;
esac
'''


@pytest.fixture
def codeql_env(stub_bin):
    write_exe(stub_bin / 'codeql', STUB_CODEQL)
    return {'PATH': f'{stub_bin}{os.pathsep}{os.environ["PATH"]}'}


def script(name):
    return str(CODEQL_SCRIPTS / name)


class TestVerifyQuerySuite:
    @pytest.mark.parametrize('mode, rc', [('ok', 0), ('empty', 1), ('badjson', 1), ('notlist', 1), ('fail', 1)])
    def test_exit_codes(self, tmp_path, codeql_env, mode, rc):
        suite = tmp_path / 's.qls'
        suite.write_text('- queries: .\n')
        res = run(['python3', script('verify_query_suite.py'), str(suite)], env={**codeql_env, 'STUB_RESOLVE': mode})
        assert res.returncode == rc, res.stderr
        if rc == 0:
            assert res.stdout.strip() == 'Resolved 2 queries'

    def test_missing_binary(self, tmp_path):
        res = run(['python3', script('verify_query_suite.py'), 'x.qls', '--codeql', str(tmp_path / 'nope')])
        assert res.returncode == 1


class TestGenerateSuite:
    def gen(self, mode, env, tmp_path, **extra):
        return run(['bash', script('generate_suite.sh'), mode],
                   env={**env, 'CODEQL_LANG': 'go', 'OUTPUT_DIR': str(tmp_path / 'out'), **extra})

    def test_bad_mode(self, tmp_path, codeql_env):
        assert self.gen('everything', codeql_env, tmp_path).returncode == 2

    def suite(self, tmp_path, mode):
        return yaml.safe_load((tmp_path / f'out/raw/{mode}.qls').read_text())

    def test_run_all(self, tmp_path, codeql_env):
        res = self.gen('run-all', codeql_env, tmp_path,
                       INSTALLED_THIRD_PARTY_PACKS='example/go-queries githubsecuritylab/codeql-go-queries@1.0.0')
        assert res.returncode == 0, res.stderr
        steps = self.suite(tmp_path, 'run-all')
        imports = [s['import'] for s in steps if 'import' in s]
        assert imports == ['codeql-suites/go-security-and-quality.qls', 'codeql-suites/go-security-experimental.qls']
        assert all(s['from'] == 'codeql/go-queries' for s in steps if 'import' in s)
        assert [s['from'] for s in steps if 'queries' in s] == ['example/go-queries',
                                                                 'githubsecuritylab/codeql-go-queries']
        assert {'include': {'kind': ['problem', 'path-problem']}} in steps
        assert {'exclude': {'tags contain': ['modeleditor', 'modelgenerator']}} in steps
        assert any('deprecated' in s.get('exclude', {}) for s in steps)

    def test_important_only(self, tmp_path, codeql_env):
        res = self.gen('important-only', codeql_env, tmp_path)
        assert res.returncode == 0, res.stderr
        steps = self.suite(tmp_path, 'important-only')
        assert not any('import' in s for s in steps)
        assert {'queries': '.', 'from': 'codeql/go-queries'} in steps
        includes = [s['include'] for s in steps if 'include' in s]
        assert [i['precision'] for i in includes] == [['high', 'very-high'], 'medium']
        assert all(i['tags contain'] == 'security' for i in includes)

    def test_failed_verification_removes_suite(self, tmp_path, codeql_env):
        res = self.gen('run-all', {**codeql_env, 'STUB_RESOLVE': 'empty'}, tmp_path)
        assert res.returncode == 1
        assert not (tmp_path / 'out/raw/run-all.qls').exists()

    def test_bad_pack_name(self, tmp_path, codeql_env):
        res = self.gen('run-all', codeql_env, tmp_path, INSTALLED_THIRD_PARTY_PACKS='evil;rm')
        assert res.returncode == 1


def make_db(root, valid=True):
    root.mkdir(parents=True)
    (root / 'codeql-database.yml').write_text('primaryLanguage: go\n')
    if valid:
        (root / '.stub-valid').write_text('')
    return root


class TestFindDatabases:
    def find(self, env, *roots):
        return run(['bash', script('find_databases.sh'), *map(str, roots)], env=env)

    def test_missing_codeql_exits_2(self, tmp_path):
        res = self.find({'PATH': path_without('codeql')}, tmp_path)
        assert res.returncode == 2 and 'codeql is not on PATH' in res.stderr

    def test_filters_and_dedupes(self, tmp_path, codeql_env):
        good = make_db(tmp_path / 'out/codeql.db')
        make_db(tmp_path / 'out/half-built', valid=False)
        make_db(tmp_path / 'out/.hidden/db')
        make_db(tmp_path / 'out/a/b/c/too-deep')
        (tmp_path / 'alias').symlink_to(tmp_path / 'out')
        res = self.find(codeql_env, tmp_path / 'out', tmp_path / 'alias')
        assert res.returncode == 0
        assert res.stdout.splitlines() == [str(good.resolve())]

    def test_dotted_ancestor_root_still_searched(self, tmp_path, codeql_env):
        db = make_db(tmp_path / '.cache/out/codeql.db')
        res = self.find(codeql_env, tmp_path / '.cache/out')
        assert res.stdout.splitlines() == [str(db.resolve())]

    def test_default_roots_use_tmpdir_candidates(self, tmp_path, codeql_env):
        repo = tmp_path / 'myrepo'
        repo.mkdir()
        tmp = tmp_path / 'tmp'
        db = make_db(tmp / 'codeql-myrepo_2/codeql.db')
        make_db(tmp / 'codeql-other_1/codeql.db')
        res = run(['bash', script('find_databases.sh')], env={**codeql_env, 'TMPDIR': str(tmp)}, cwd=repo)
        assert res.stdout.splitlines() == [str(db.resolve())]


class TestBuildLog:
    def sh(self, body, env):
        return run(['bash', '-c', f'. {script("build_log.sh")} || exit 9\n{body}'], env=env)

    def test_requires_output_dir(self):
        res = run(['bash', '-c', f'unset OUTPUT_DIR LOG_FILE; . {script("build_log.sh")} || exit 9'])
        assert res.returncode == 9

    def test_unwritable_log(self, tmp_path):
        ro = tmp_path / 'ro'
        ro.mkdir()
        ro.chmod(0o500)
        try:
            res = self.sh('echo unreachable', {'LOG_FILE': str(ro / 'sub/build.log')})
            assert res.returncode == 9
        finally:
            ro.chmod(0o700)

    def test_run_logged_keeps_exit_status(self, tmp_path):
        env = {'OUTPUT_DIR': str(tmp_path), 'LOG_FILE': ''}
        res = self.sh('log_step autobuild; run_logged bash -c "echo building; exit 7"; echo "rc=$?"', env)
        assert 'rc=7' in res.stdout
        log = (tmp_path / 'build.log').read_text()
        assert 'autobuild' in log and 'building' in log and '-> exit 7' in log
        assert '$ bash -c' in log


def build_db(root, *, loc=120, files=('repo/main.go', 'repo/util.go', 'usr/lib/go/fmt.go'),
             prefix='/repo', diagnostics=None, finalised=True):
    root.mkdir(parents=True)
    yml = f'sourceLocationPrefix: "{prefix}"\nprimaryLanguage: "go"\n'
    if finalised:
        yml += 'finalised: true\n'
    (root / 'codeql-database.yml').write_text(yml)
    (root / 'baseline-info.json').write_text(json.dumps({'languages': {'go': {'linesOfCode': loc}}}))
    with zipfile.ZipFile(root / 'src.zip', 'w') as zf:
        for f in files:
            zf.writestr(f, 'package x\n')
    for rel, text in (diagnostics or {}).items():
        target = root.joinpath('diagnostic', rel)
        os.makedirs(target.parent, exist_ok=True)
        target.write_text(text)
    return root


class TestCheckDbQuality:
    def check(self, db, *args):
        return run(['python3', script('check_db_quality.py'), str(db), *args])

    def test_ok_json(self, tmp_path):
        res = self.check(build_db(tmp_path / 'db'), '--format', 'json')
        assert res.returncode == 0, res.stderr
        data = json.loads(res.stdout)
        assert data == {'baseline_loc': 120, 'project_files': 2, 'archive_files': 3,
                        'extractor_errors': 0, 'error_ratio': 0.0, 'finalised': True}

    def test_no_loc(self, tmp_path):
        assert self.check(build_db(tmp_path / 'db', loc=0)).returncode == 1

    def test_no_project_files(self, tmp_path):
        assert self.check(build_db(tmp_path / 'db', files=('usr/lib/go/fmt.go',))).returncode == 1

    def test_unreadable(self, tmp_path):
        (tmp_path / 'db').mkdir()
        assert self.check(tmp_path / 'db').returncode == 1

    def test_usage_error(self, tmp_path):
        assert self.check(tmp_path, '--format', 'xml').returncode == 2

    def test_toolchain_fallback_without_prefix(self, tmp_path):
        db = build_db(tmp_path / 'db', prefix='', files=('home/u/p/main.go', 'usr/lib/go/fmt.go',
                                                          'home/u/go/pkg/mod/x/y.go'))
        assert json.loads(self.check(db, '--format', 'json').stdout)['project_files'] == 1

    def test_error_ratio_threshold(self, tmp_path):
        diags = {'extractors/go/a.jsonl': json.dumps(
            {'source': {'id': 'go/extractor/x'}, 'severity': 'error', 'markdownMessage': 'bad'}) + '\n'}
        db = build_db(tmp_path / 'db', diagnostics=diags)
        res = self.check(db)
        assert res.returncode == 3
        assert 'extractor_errors: 1' in res.stdout and 'error_ratio: 50.0' in res.stdout
        assert self.check(db, '--max-error-ratio', '60').returncode == 0

    def test_pretty_printed_jsonl_and_summary(self, tmp_path):
        pretty = json.dumps({'source': {'id': 's'}, 'severity': 'warning', 'message': 'w'}, indent=2)
        summary = json.dumps({'attributes': {'extractor-failures': 0}}, indent=2)
        db = build_db(tmp_path / 'db', diagnostics={'extractors/go/x.jsonl': pretty + '\n' + pretty,
                                                   'summary.jsonl': summary})
        res = self.check(db, '--format', 'json')
        assert res.returncode == 0 and json.loads(res.stdout)['extractor_errors'] == 0

    def test_unrecognised_format(self, tmp_path):
        db = build_db(tmp_path / 'db', diagnostics={'extractors/go/x.jsonl': '{"what": "ever"}\n'})
        assert self.check(db).returncode == 4


def test_important_only_jq_filter(tmp_path):
    require('jq')
    rules = [
        {'id': 'hi', 'properties': {'precision': 'high'}},
        {'id': 'med-sev', 'properties': {'precision': 'medium', 'security-severity': '7.5'}},
        {'id': 'med-low', 'properties': {'precision': 'medium', 'security-severity': '4.0'}},
        {'id': 'med-none', 'properties': {'precision': 'medium'}},
        {'id': 'unknown', 'properties': {}},
        {'id': 'low', 'properties': {'precision': 'low'}},
    ]
    results = [{'ruleId': r['id'], 'rule': {'id': r['id'], 'index': i, 'toolComponent': {'index': 0}}}
               for i, r in enumerate(rules)]
    doc = {'version': '2.1.0', 'runs': [{'tool': {'driver': {'name': 'CodeQL', 'rules': []},
                                                  'extensions': [{'name': 'codeql/go-queries', 'rules': rules}]},
                                         'results': results}]}
    src = tmp_path / 'raw.sarif'
    src.write_text(json.dumps(doc))
    res = run(['jq', '-f', script('important-only.jq'), str(src)])
    assert res.returncode == 0, res.stderr
    kept = [r['ruleId'] for r in json.loads(res.stdout)['runs'][0]['results']]
    assert kept == ['hi', 'med-sev', 'unknown']


def test_real_codeql_resolves_languages():
    require('codeql')
    res = run(['codeql', 'resolve', 'languages', '--format=json'])
    assert res.returncode == 0 and 'go' in json.loads(res.stdout)
