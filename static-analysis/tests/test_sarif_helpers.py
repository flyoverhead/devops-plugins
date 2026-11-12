import json

import sarif_helpers as sh
from conftest import SARIF_RESOURCES, run

FIX = SARIF_RESOURCES / 'fixtures'


def test_fixtures_hold_exactly_one_error():
    counts = {name: sum(f.level == 'error' for f in sh.extract_findings(sh.load_sarif(FIX / name)))
              for name in ('codeql-no-level.sarif', 'levels-on-results.sarif')}
    assert counts == {'codeql-no-level.sarif': 1, 'levels-on-results.sarif': 1}


def test_level_from_rule_when_result_has_none():
    findings = sh.extract_findings(sh.load_sarif(FIX / 'codeql-no-level.sarif'))
    err = sh.filter_by_level(findings, 'error')[0]
    assert (err.file_path, err.start_line) == ('app/db.py', 42)


def test_negative_rule_index_falls_back_to_rule_id():
    doc = sh.load_sarif(FIX / 'codeql-no-level.sarif')
    run_ = doc['runs'][0]
    result = run_['results'][2]
    assert result['ruleIndex'] == -1
    assert sh.find_rule(run_, result)['id'] == 'py/clear-text-logging'
    assert sh.resolve_level(run_, result) == 'warning'


def test_kind_not_fail_is_none():
    doc = sh.load_sarif(FIX / 'levels-on-results.sarif')
    run_ = doc['runs'][0]
    assert sh.resolve_level(run_, run_['results'][2]) == 'none'


def test_default_level_is_warning():
    run_ = {'tool': {'driver': {'rules': []}}}
    assert sh.resolve_level(run_, {'ruleId': 'x'}) == 'warning'


def test_rule_from_tool_extension():
    run_ = {'tool': {'driver': {'name': 'CodeQL', 'rules': []},
                     'extensions': [{'name': 'codeql/go-queries',
                                     'rules': [{'id': 'go/x', 'defaultConfiguration': {'level': 'error'}}]}]}}
    result = {'ruleId': 'go/x', 'rule': {'id': 'go/x', 'index': 0, 'toolComponent': {'index': 0}}}
    assert sh.resolve_level(run_, result) == 'error'


def test_fingerprint_keeps_directory():
    a = sh.compute_fingerprint('r', 'svc/a/main.go', 3, 'msg')
    b = sh.compute_fingerprint('r', 'svc/b/main.go', 3, 'msg')
    assert a != b and len(a) == 16
    assert sh.compute_fingerprint('r', './svc\\a/main.go', 3, 'msg') == a


def test_normalize_path():
    assert sh.normalize_path('file:///repo/src/My%20File.go', base='/repo') == 'src/My File.go'
    assert sh.normalize_path('.\\src\\x.py') == 'src/x.py'
    assert sh.normalize_path(None) == ''


def test_validate_version():
    assert sh.validate_version({'version': '2.1.0', 'runs': []}) == []
    assert sh.validate_version({'version': '2.0.0', 'runs': []})


def test_diff_and_dedupe():
    def doc(lines):
        return {'version': '2.1.0', 'runs': [{'tool': {'driver': {'name': 't', 'rules': []}}, 'results': [
            {'ruleId': 'r', 'message': {'text': 'm'}, 'locations': [{'physicalLocation': {
                'artifactLocation': {'uri': 'a.go'}, 'region': {'startLine': n}}}]} for n in lines]}]}
    base = sh.extract_findings(doc([1, 2]))
    cur = sh.extract_findings(doc([2, 3, 3]))
    assert len(sh.deduplicate(cur)) == 2
    new, fixed, same = sh.diff_findings(base, cur)
    assert [f.start_line for f in new] == [3]
    assert [f.start_line for f in fixed] == [1]
    assert [f.start_line for f in same] == [2]


def test_tool_fingerprint_preferred():
    findings = sh.extract_findings(sh.load_sarif(FIX / 'codeql-no-level.sarif'))
    assert all(len(f.fingerprint) == 16 for f in findings)
    doc = {'version': '2.1.0', 'runs': [{'tool': {'driver': {'name': 't'}}, 'results': [
        {'ruleId': 'r', 'message': {'text': 'm'}, 'partialFingerprints': {'primaryLocationLineHash': 'abc:1'}}]}]}
    assert sh.extract_findings(doc)[0].fingerprint == 'primaryLocationLineHash:abc:1'


def test_merge_keeps_each_run_rule_table(tmp_path):
    merged = sh.merge_sarif_files([FIX / 'codeql-no-level.sarif', FIX / 'levels-on-results.sarif'])
    assert len(merged['runs']) == 2
    levels = [f.level for f in sh.extract_findings(merged)]
    assert levels.count('error') == 2


def test_summary_and_csv():
    findings = sh.extract_findings(sh.load_sarif(FIX / 'codeql-no-level.sarif'))
    s = sh.summary(findings)
    assert s['total'] == 3 and s['by_level']['error'] == 1 and s['files_affected'] == 2
    assert sh.to_csv_rows(findings).splitlines()[1].startswith('error,py/sql-injection')
    assert [f.level for f in sh.sort_by_severity(findings)] == ['error', 'warning', 'note']


def test_cli(tmp_path):
    script = str(SARIF_RESOURCES / 'sarif_helpers.py')
    res = run(['python3', script, str(FIX / 'codeql-no-level.sarif')])
    assert res.returncode == 0 and 'error: 1' in res.stdout and 'top rules:' in res.stdout
    assert run(['python3', script]).returncode == 1
    old = tmp_path / 'old.sarif'
    old.write_text(json.dumps({'version': '2.0.0', 'runs': []}))
    assert 'expected "2.1.0"' in run(['python3', script, str(old)]).stderr
