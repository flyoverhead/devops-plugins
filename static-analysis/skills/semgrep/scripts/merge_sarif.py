#!/usr/bin/env python3
"""Merge the per-scan Semgrep SARIF files in RAW_DIR into one SARIF 2.1.0 file."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote

SARIF_SCHEMA_URL = 'https://json.schemastore.org/sarif-2.1.0.json'


class Stop(Exception):
    """A condition under which nothing may be written."""


def read_json(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise Stop(f'{Path(path).name}: {exc}') from exc


def clean_uri(raw):
    text = unquote(raw or '').replace('\\', '/')
    text = text.removeprefix('file://')
    while text.startswith('./'):
        text = text[2:]
    return text


def location_key(rule, uri, line):
    return rule, clean_uri(uri), line


def key_of_sarif_result(res):
    phys = ((res.get('locations') or [{}])[0]).get('physicalLocation') or {}
    return location_key(res.get('ruleId'),
                        (phys.get('artifactLocation') or {}).get('uri'),
                        (phys.get('region') or {}).get('startLine'))


def key_of_json_result(item):
    return location_key(item.get('check_id'), item.get('path'), (item.get('start') or {}).get('line'))


def failed_scan_names(scans_file):
    record = read_json(scans_file)
    ok, bad = record.get('scans') or [], record.get('failed') or []
    if bad and not ok:
        raise Stop('every scan failed; nothing to merge')
    return {os.path.basename(entry.get('sarif', '')) for entry in bad}


def allowed_keys(sarif_file):
    companion = sarif_file.parent / f'{sarif_file.stem}-important.json'
    if not companion.exists():
        raise Stop(f'--important: {companion.name} is missing; run the post-filter on every raw JSON first')
    try:
        filtered = read_json(companion)
    except Stop as exc:
        raise Stop(f'--important: unreadable filter file {exc}') from exc
    items = filtered.get('results') if isinstance(filtered, dict) else None
    if not isinstance(items, list):
        raise Stop(f'--important: {companion.name} has no results array')
    return set(map(key_of_json_result, items))


def runs_of(sarif_file):
    doc = read_json(sarif_file)
    runs = doc.get('runs') if isinstance(doc, dict) else None
    if not isinstance(runs, list):
        raise Stop(f'{sarif_file.name}: no runs array')
    return runs


def merge(files, keep=None):
    """keep maps file name -> allowed keys (important-only); None keeps everything."""
    stats = {'found': 0, 'kept': 0, 'dropped': 0}
    driver, rule_by_id, merged, seen, broken = None, {}, [], set(), []
    for sarif_file in files:
        try:
            runs = runs_of(sarif_file)
        except Stop as exc:
            print(f'warning: skipping unparseable SARIF {exc}', file=sys.stderr)
            broken.append(sarif_file.name)
            continue
        for run in runs:
            this_driver = (run.get('tool') or {}).get('driver') or {}
            if driver is None and this_driver:
                driver = {k: v for k, v in this_driver.items() if k != 'rules'}
            for rule in this_driver.get('rules') or []:
                if isinstance(rule, dict) and rule.get('id'):
                    rule_by_id.setdefault(rule['id'], rule)
            for res in run.get('results') or []:
                stats['found'] += 1
                key = key_of_sarif_result(res)
                if keep is not None and key not in keep[sarif_file.name]:
                    stats['dropped'] += 1
                    continue
                stats['kept'] += 1
                if key not in seen:
                    seen.add(key)
                    merged.append({k: v for k, v in res.items() if k != 'ruleIndex'})
    return driver, list(rule_by_id.values()), merged, stats, broken


def run_merge(args):
    raw = Path(args.raw_dir)
    if not raw.is_dir():
        raise Stop(f'raw dir does not exist: {raw}')
    files = sorted(raw.glob('*.sarif'))
    if not files:
        raise Stop(f'no .sarif files in {raw}')
    if args.scans:
        excluded = failed_scan_names(args.scans)
        for name in sorted(excluded & {f.name for f in files}):
            print(f'excluded failed scan: {name}')
        files = [f for f in files if f.name not in excluded]
        if not files:
            raise Stop('no SARIF left after excluding failed scans')

    keep = {f.name: allowed_keys(f) for f in files} if args.important else None
    driver, rules, results, stats, broken = merge(files, keep)
    if len(broken) == len(files):
        raise Stop('every SARIF file was unparseable')
    if keep is not None:
        wanted = sum(map(len, keep.values()))
        if wanted and not stats['kept']:
            raise Stop(f'filter kept {wanted} keys, merge read {stats["found"]} results, but none matched; '
                       'refusing to write a zero-finding file (format drift?)')

    doc = {'version': '2.1.0', '$schema': SARIF_SCHEMA_URL, 'runs': []}
    if results:
        tool_driver = dict(driver or {'name': 'Semgrep'}, rules=rules)
        doc['runs'] = [{'tool': {'driver': tool_driver}, 'results': results}]
    out = Path(args.output_file)
    os.makedirs(out.parent, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + '\n')

    for label in ('found', 'kept', 'dropped'):
        print(f'{label}: {stats[label]}')
    print(f'merged: {len(results)}')
    if broken:
        print(f'unparseable: {len(broken)} ({", ".join(broken)})')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, exit_on_error=False)
    parser.add_argument('raw_dir')
    parser.add_argument('output_file')
    parser.add_argument('--important', action='store_true',
                        help='keep only results listed in each <stem>-important.json')
    parser.add_argument('--scans', help='scans.json from run-scans.sh; failed scans are left out')
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 1 if exc.code else 0
    try:
        run_merge(args)
    except argparse.ArgumentError as exc:
        print(f'merge_sarif.py: {exc}', file=sys.stderr)
        return 1
    except Stop as exc:
        print(f'merge_sarif.py: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
