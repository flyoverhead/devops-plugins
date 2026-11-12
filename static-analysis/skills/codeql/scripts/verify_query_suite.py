#!/usr/bin/env python3
"""Check that a .qls suite resolves to at least one query with `codeql resolve queries`."""
import argparse
import json
import subprocess
import sys


def main(argv=None):
    cli = argparse.ArgumentParser(prog='verify_query_suite.py', description=__doc__)
    cli.add_argument('suite', help='the .qls file to resolve')
    cli.add_argument('--codeql', default='codeql', metavar='PATH', help='codeql binary (default: from PATH)')
    args = cli.parse_args(argv)
    try:
        res = subprocess.run([args.codeql, 'resolve', 'queries', '--format=json', '--', args.suite],
                             capture_output=True, text=True)
    except OSError as exc:
        print(f'verify_query_suite.py: cannot run {args.codeql}: {exc}', file=sys.stderr)
        return 1
    if res.returncode != 0:
        print(f'verify_query_suite.py: resolve failed (exit {res.returncode}): {res.stderr.strip()[-800:]}',
              file=sys.stderr)
        return 1
    try:
        queries = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        print(f'verify_query_suite.py: resolve printed invalid JSON: {exc}', file=sys.stderr)
        return 1
    if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
        print('verify_query_suite.py: resolve output is not a list of query paths', file=sys.stderr)
        return 1
    if not queries:
        print('verify_query_suite.py: the suite selects zero queries', file=sys.stderr)
        return 1
    print(f'Resolved {len(queries)} queries')
    return 0


if __name__ == '__main__':
    sys.exit(main())
