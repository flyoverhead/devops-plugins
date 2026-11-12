#!/usr/bin/env python3
"""Decide whether a CodeQL database is worth analysing.

Exit codes:
  0  usable
  1  nothing to analyse: zero baseline LoC, zero project files in the source archive, or unreadable
  2  bad command line
  3  too many extractor errors per project file
  4  unknown diagnostics format; this checker needs an update
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

TOOLCHAIN_PREFIXES = (
    'usr/', 'opt/homebrew/', 'opt/local/', 'Library/', 'Applications/', 'System/',
    'nix/store/', 'snap/',
)
TOOLCHAIN_PARTS = ('/go/pkg/mod/', '/.cargo/registry/', '/.m2/repository/', '/.gradle/caches/',
                   '/node_modules/', '/site-packages/', '/.rustup/', '/.nuget/packages/')


def read_db_yaml(db):
    """Flat `key: value` lines are all this checker needs; nested keys are ignored."""
    text = (db / 'codeql-database.yml').read_text()
    top_level = (ln for ln in text.splitlines() if ln[:1].isalpha() and ':' in ln)
    pairs = (ln.split(':', 1) for ln in top_level)
    return {k.strip(): v.strip().strip('"\'') for k, v in pairs}


def baseline_loc(db, info):
    path = db / 'baseline-info.json'
    if path.is_file():
        data = json.loads(path.read_text())
        langs = data.get('languages') if isinstance(data, dict) else None
        if isinstance(langs, dict):
            return sum(int(v.get('linesOfCode') or 0) for v in langs.values() if isinstance(v, dict))
    try:
        return int(info.get('baselineLinesOfCode') or 0)
    except ValueError:
        return 0


def count_files(db, prefix):
    src = db / 'src.zip'
    if not src.is_file():
        return 0, 0
    with zipfile.ZipFile(src) as zf:
        names = [n for n in zf.namelist() if not n.endswith('/')]
    prefix = prefix.lstrip('/').rstrip('/')
    if prefix:
        project = [n for n in names if n.lstrip('/') == prefix or n.lstrip('/').startswith(prefix + '/')]
    else:
        project = [n for n in names
                   if not n.lstrip('/').startswith(TOOLCHAIN_PREFIXES)
                   and not any(p in '/' + n.lstrip('/') for p in TOOLCHAIN_PARTS)]
    return len(project), len(names)


def json_objects(text):
    """Objects from JSON Lines, a JSON array, or pretty-printed objects back to back."""
    dec = json.JSONDecoder()
    i, out = 0, []
    while i < len(text):
        while i < len(text) and text[i] in ' \t\r\n,':
            i += 1
        if i >= len(text):
            break
        obj, i = dec.raw_decode(text, i)
        if isinstance(obj, list):
            out.extend(o for o in obj if isinstance(o, dict))
        elif isinstance(obj, dict):
            out.append(obj)
    return out


class FormatError(Exception):
    pass


def extractor_errors(db):
    diag = db / 'diagnostic'
    if not diag.is_dir():
        return 0
    files = sorted(p for p in diag.rglob('*') if p.is_file() and p.suffix in ('.json', '.jsonl'))
    summaries = [p for p in files if p.name == 'summary.jsonl']
    for path in summaries:
        try:
            objs = json_objects(path.read_text())
        except json.JSONDecodeError as exc:
            raise FormatError(f'{path}: {exc}') from exc
        counted = None
        for obj in objs:
            attrs = obj.get('attributes')
            if isinstance(attrs, dict) and 'extractor-failures' in attrs:
                counted = (counted or 0) + int(attrs['extractor-failures'])
        if counted is not None:
            return counted
    errors, recognised, seen_any = 0, False, False
    for path in files:
        if path in summaries:
            continue
        try:
            objs = json_objects(path.read_text())
        except json.JSONDecodeError as exc:
            raise FormatError(f'{path}: {exc}') from exc
        for obj in objs:
            seen_any = True
            if 'severity' in obj and ('source' in obj or 'message' in obj or 'markdownMessage' in obj):
                recognised = True
                if str(obj.get('severity')).lower() == 'error':
                    errors += 1
    if seen_any and not recognised:
        raise FormatError(f'no diagnostic under {diag} has a severity field')
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('db', type=Path)
    ap.add_argument('--max-error-ratio', type=float, default=5.0,
                    help='highest acceptable extractor errors per 100 project files (default 5.0)')
    ap.add_argument('--format', choices=('text', 'json'), default='text')
    args = ap.parse_args(argv)

    db = args.db
    try:
        info = read_db_yaml(db)
        loc = baseline_loc(db, info)
        project, archive = count_files(db, info.get('sourceLocationPrefix', ''))
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        print(f'check_db_quality.py: cannot read database {db}: {exc}', file=sys.stderr)
        return 1
    try:
        errors = extractor_errors(db)
    except FormatError as exc:
        print(f'check_db_quality.py: unrecognised diagnostics format ({exc}); the checker needs an update',
              file=sys.stderr)
        return 4
    ratio = round(100.0 * errors / project, 2) if project else 0.0
    report = {
        'baseline_loc': loc,
        'project_files': project,
        'archive_files': archive,
        'extractor_errors': errors,
        'error_ratio': ratio,
        'finalised': info.get('finalised', '').lower() == 'true',
    }
    if args.format == 'json':
        print(json.dumps(report, indent=2))
    else:
        for key, value in report.items():
            print(f'{key}: {value}')

    if loc <= 0 or project <= 0:
        print('check_db_quality.py: nothing to analyse (no baseline lines of code or no project files '
              'in src.zip); do not run queries on this database', file=sys.stderr)
        return 1
    if ratio > args.max_error_ratio:
        print(f'check_db_quality.py: extractor error ratio {ratio}% exceeds {args.max_error_ratio}%; '
              'inspect which files failed before raising the threshold', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
