import json

from conftest import SEMGREP_SCRIPTS, run

MERGE = str(SEMGREP_SCRIPTS / 'merge_sarif.py')


def sarif(results, rules=('r1',), tool='Semgrep OSS'):
    return {'version': '2.1.0', 'runs': [{
        'tool': {'driver': {'name': tool, 'rules': [{'id': r} for r in rules]}},
        'results': [{'ruleId': r, 'message': {'text': 'm'},
                     'locations': [{'physicalLocation': {'artifactLocation': {'uri': u},
                                                         'region': {'startLine': l}}}]}
                    for r, u, l in results]}]}


def write(path, data):
    path.write_text(json.dumps(data) if not isinstance(data, str) else data)


def merge(*args):
    return run(['python3', MERGE, *map(str, args)])


def merge_rc(raw, *flags, dest=None):
    """Exit status of a merge into a throwaway output next to raw."""
    return merge(raw, dest or raw.parent / 'merged.sarif', *flags).returncode


def test_dedupes_on_rule_uri_line(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'all-p_default.sarif', sarif([('r1', 'a/main.go', 3), ('r2', 'a/main.go', 9)], rules=('r1', 'r2')))
    write(raw / 'go-p_golang.sarif', sarif([('r1', './a/main.go', 3), ('r1', 'b/main.go', 3)]))
    out = tmp_path.joinpath('merged', 'all.sarif')
    res = merge(raw, out)
    assert res.returncode == 0, res.stderr
    doc = json.loads(out.read_text())
    assert doc['version'] == '2.1.0' and 'schemastore' in doc['$schema']
    assert len(doc['runs']) == 1
    assert len(doc['runs'][0]['results']) == 3
    assert [r['id'] for r in doc['runs'][0]['tool']['driver']['rules']] == ['r1', 'r2']
    assert 'merged: 3' in res.stdout and 'found: 4' in res.stdout


def test_failed_scans_excluded(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'ok.sarif', sarif([('r1', 'x.go', 1)]))
    write(raw / 'bad.sarif', sarif([('r1', 'y.go', 1)]))
    scans = tmp_path / 'scans.json'
    write(scans, {'scans': [{'sarif': str(raw / 'ok.sarif')}], 'failed': [{'sarif': str(raw / 'bad.sarif')}]})
    out = tmp_path / 'm.sarif'
    res = merge(raw, out, '--scans', scans)
    assert res.returncode == 0
    assert 'excluded failed scan: bad.sarif' in res.stdout
    assert len(json.loads(out.read_text())['runs'][0]['results']) == 1


def test_every_scan_failed(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'bad.sarif', sarif([]))
    scans = tmp_path / 'scans.json'
    write(scans, {'scans': [], 'failed': [{'sarif': str(raw / 'bad.sarif')}]})
    assert merge_rc(raw, '--scans', scans) == 1


def test_unparseable_reported(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'ok.sarif', sarif([('r1', 'x.go', 1)]))
    write(raw / 'broken.sarif', '{"runs": [')
    res = merge(raw, tmp_path / 'm.sarif')
    assert res.returncode == 0
    assert 'unparseable: 1 (broken.sarif)' in res.stdout


def test_all_unparseable(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'broken.sarif', 'nope')
    assert merge_rc(raw) == 1


def test_missing_raw_dir_and_no_files(tmp_path):
    assert merge_rc(tmp_path / 'nope') == 1
    empty = tmp_path / 'raw'
    empty.mkdir()
    assert merge_rc(empty) == 1


def test_bad_arguments_exit_1(tmp_path):
    assert merge().returncode == 1


def test_zero_results_writes_no_runs(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'a.sarif', sarif([]))
    out = tmp_path / 'm.sarif'
    assert merge(raw, out).returncode == 0
    assert json.loads(out.read_text())['runs'] == []


def important(path, keys):
    write(path, {'results': [{'check_id': r, 'path': u, 'start': {'line': l}} for r, u, l in keys],
                 'errors': [], 'paths': {}})


def test_important_keeps_only_filtered(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'go-x.sarif', sarif([('r1', 'a.go', 1), ('r2', 'a.go', 2)], rules=('r1', 'r2')))
    important(raw / 'go-x-important.json', [('r2', 'a.go', 2)])
    out = tmp_path / 'm.sarif'
    res = merge(raw, out, '--important')
    assert res.returncode == 0, res.stderr
    assert [r['ruleId'] for r in json.loads(out.read_text())['runs'][0]['results']] == ['r2']
    assert 'dropped: 1' in res.stdout


def test_important_missing_filter_file(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'go-x.sarif', sarif([('r1', 'a.go', 1)]))
    res = merge(raw, tmp_path / 'm.sarif', '--important')
    assert res.returncode == 1 and 'go-x-important.json' in res.stderr


def test_important_invalid_filter_file(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'go-x.sarif', sarif([('r1', 'a.go', 1)]))
    write(raw / 'go-x-important.json', '{"results": 5}')
    assert merge_rc(raw, '--important') == 1


def test_important_format_drift_refused(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    write(raw / 'go-x.sarif', sarif([('r1', 'a.go', 1)]))
    important(raw / 'go-x-important.json', [('r1', 'other.go', 99)])
    out = tmp_path / 'm.sarif'
    res = merge(raw, out, '--important')
    assert res.returncode == 1 and 'none matched' in res.stderr
    assert not out.exists()
