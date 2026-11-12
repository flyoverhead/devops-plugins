#!/usr/bin/env python3
"""Stdlib helpers for reading, filtering, deduplicating and diffing SARIF 2.1.0.

Import it (sys.path.insert(0, <dir>); import sarif_helpers as sh) or run it on a file
for a summary: python3 sarif_helpers.py results.sarif
"""
import csv
import dataclasses
import hashlib
import io
import json
import os
import sys
from pathlib import PurePosixPath
from urllib.parse import unquote

LEVEL_RANK = {'error': 3, 'warning': 2, 'note': 1, 'none': 0}


@dataclasses.dataclass
class Finding:
    rule_id: str
    level: str
    message: str
    file_path: str
    start_line: int | None
    end_line: int | None
    start_column: int | None
    end_column: int | None
    fingerprint: str
    tool_name: str
    rule_name: str | None
    raw: dict = dataclasses.field(repr=False, default_factory=dict)


def load_sarif(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def save_sarif(doc, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, indent=2)
        fh.write('\n')


def validate_version(doc):
    """Return a list of problems; empty means the document looks like SARIF 2.1.0."""
    problems = []
    if not isinstance(doc, dict):
        return ['top level is not an object']
    if doc.get('version') != '2.1.0':
        problems.append(f'version is {doc.get("version")!r}, expected "2.1.0"')
    if not isinstance(doc.get('runs'), list):
        problems.append('runs is missing or not an array')
    return problems


def safe_get(obj, *keys, default=None):
    for key in keys:
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        elif isinstance(obj, list) and isinstance(key, int) and 0 <= key < len(obj):
            obj = obj[key]
        else:
            return default
    return obj


def normalize_path(uri, base=None):
    """Strip file://, percent-decode, use POSIX separators, make relative to base if given."""
    if not uri:
        return ''
    path = unquote(uri)
    if path.startswith('file://'):
        path = path[len('file://'):]
    path = path.replace('\\', '/')
    while path.startswith('./'):
        path = path[2:]
    if base:
        b = normalize_path(base).rstrip('/') + '/'
        if path.startswith(b):
            path = path[len(b):]
    return str(PurePosixPath(path)) if path else ''


def get_rules(run, component=None):
    """Rule table of the driver, or of tool extension number `component`."""
    where = ('driver',) if component is None else ('extensions', component)
    return safe_get(run, 'tool', *where, 'rules') or []


def _is_index(value):
    return type(value) is int and value >= 0


def find_rule(run, result):
    comp = safe_get(result, 'rule', 'toolComponent', 'index')
    rules = get_rules(run, comp if _is_index(comp) else None)
    idx = safe_get(result, 'rule', 'index', default=result.get('ruleIndex'))
    if _is_index(idx) and idx < len(rules):
        return rules[idx]
    rid = result.get('ruleId') or safe_get(result, 'rule', 'id')
    if rid is not None:
        for rule in rules:
            if isinstance(rule, dict) and rule.get('id') == rid:
                return rule
    return None


def resolve_level(run, result):
    """Effective level per SARIF 2.1.0 section 3.27.10."""
    kind = result.get('kind', 'fail')
    if kind != 'fail':
        return 'none'
    if result.get('level'):
        return result['level']
    rule = find_rule(run, result)
    level = safe_get(rule, 'defaultConfiguration', 'level') if rule else None
    return level or 'warning'


def extract_location(result, base=None):
    phys = safe_get(result, 'locations', 0, 'physicalLocation', default={}) or {}
    region = phys.get('region') or {}
    first = region.get('startLine')
    loc = {'file': normalize_path(safe_get(phys, 'artifactLocation', 'uri'), base)}
    loc.update(start_line=first, end_line=region.get('endLine', first))
    loc.update(start_column=region.get('startColumn'), end_column=region.get('endColumn'))
    return loc


def compute_fingerprint(rule_id, file_path, start_line, message):
    """Rule + full normalised path + line + message prefix; the directory is part of the key."""
    digest = hashlib.sha256()
    for part in (rule_id, normalize_path(file_path), start_line, (message or '')[:50]):
        digest.update(f'{part}|'.encode())
    return digest.hexdigest()[:16]


def tool_fingerprint(result):
    for bag in ('fingerprints', 'partialFingerprints'):
        fp = result.get(bag)
        if isinstance(fp, dict) and fp:
            key = sorted(fp)[0]
            return f'{key}:{fp[key]}'
    return None


def iter_results(doc):
    for run in doc.get('runs') or []:
        for result in run.get('results') or []:
            yield run, result


def extract_findings(doc, base=None):
    findings = []
    for run, result in iter_results(doc):
        loc = extract_location(result, base)
        rule = find_rule(run, result)
        message = str(safe_get(result, 'message', 'text') or '')
        rule_id = result.get('ruleId') or (rule or {}).get('id') or ''
        fp = tool_fingerprint(result) or compute_fingerprint(rule_id, loc['file'], loc['start_line'], message)
        findings.append(Finding(
            rule_id=rule_id,
            level=resolve_level(run, result),
            message=message,
            file_path=loc['file'],
            start_line=loc['start_line'],
            end_line=loc['end_line'],
            start_column=loc['start_column'],
            end_column=loc['end_column'],
            fingerprint=fp,
            tool_name=safe_get(run, 'tool', 'driver', 'name', default='') or '',
            rule_name=(rule or {}).get('name'),
            raw=result,
        ))
    return findings


def _keep(findings, predicate):
    return list(filter(predicate, findings))


def filter_by_level(findings, *levels):
    return _keep(findings, lambda item: item.level in set(levels))


def filter_by_file(findings, substring):
    return _keep(findings, lambda item: substring in item.file_path)


def filter_by_rule(findings, *rule_ids):
    return _keep(findings, lambda item: item.rule_id in set(rule_ids))


def sort_by_severity(findings):
    return sorted(findings, key=lambda f: (-LEVEL_RANK.get(f.level, 0), f.file_path, f.start_line or 0))


def _group(findings, attr):
    out = {}
    for f in findings:
        out.setdefault(getattr(f, attr), []).append(f)
    return out


def group_by_file(findings):
    return _group(findings, 'file_path')


def group_by_rule(findings):
    return _group(findings, 'rule_id')


def count_by_level(findings):
    return {k: len(v) for k, v in _group(findings, 'level').items()}


def count_by_rule(findings):
    return {k: len(v) for k, v in _group(findings, 'rule_id').items()}


def deduplicate(findings):
    seen, out = set(), []
    for f in findings:
        if f.fingerprint not in seen:
            seen.add(f.fingerprint)
            out.append(f)
    return out


def merge_sarif_files(paths):
    """Concatenate runs; each run keeps its own rule table so ruleIndex stays valid."""
    merged = {'version': '2.1.0', '$schema': 'https://json.schemastore.org/sarif-2.1.0.json', 'runs': []}
    for p in paths:
        merged['runs'].extend(load_sarif(p).get('runs') or [])
    return merged


def diff_findings(baseline, current):
    """Return (new, fixed, unchanged) by fingerprint."""
    base = {f.fingerprint: f for f in baseline}
    cur = {f.fingerprint: f for f in current}
    new = [f for k, f in cur.items() if k not in base]
    fixed = [f for k, f in base.items() if k not in cur]
    unchanged = [f for k, f in cur.items() if k in base]
    return new, fixed, unchanged


def to_csv_rows(findings):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['level', 'rule_id', 'file', 'start_line', 'message', 'fingerprint'])
    for f in sort_by_severity(findings):
        w.writerow([f.level, f.rule_id, f.file_path, f.start_line, f.message, f.fingerprint])
    return buf.getvalue()


def summary(findings):
    by_rule = count_by_rule(findings)
    files = group_by_file(findings)
    return dict(total=len(findings), by_level=count_by_level(findings), by_rule=by_rule,
                files_affected=len(files), rules_triggered=len(by_rule))


def main(argv):
    if len(argv) != 1:
        print('usage: sarif_helpers.py FILE.sarif', file=sys.stderr)
        return 1
    doc = load_sarif(argv[0])
    for problem in validate_version(doc):
        print(f'warning: {problem}', file=sys.stderr)
    findings = extract_findings(doc)
    s = summary(findings)
    print(f'total: {s["total"]}')
    for level in ('error', 'warning', 'note', 'none'):
        if level in s['by_level']:
            print(f'{level}: {s["by_level"][level]}')
    print(f'files affected: {s["files_affected"]}, rules triggered: {s["rules_triggered"]}')
    top = sorted(s['by_rule'].items(), key=lambda kv: -kv[1])[:5]
    if top:
        print('top rules:')
        for rule, n in top:
            print(f'  {n:5d}  {rule}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
