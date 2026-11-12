#!/usr/bin/env python3
"""Exit 0 when two YAML files parse to equal data, 1 when they differ, 2 on error.

Usage: yaml_equal.py <old> <new>; either path may be `-` for stdin.
"""
import sys

import yaml


def load(path):
    if path == '-':
        return yaml.safe_load(sys.stdin)
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def main(argv):
    if len(argv) != 2 or argv == ['-', '-']:
        print('usage: yaml_equal.py <old> <new> (one of them may be -)', file=sys.stderr)
        return 2
    try:
        old, new = (load(p) for p in argv)
    except (OSError, yaml.YAMLError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    if old == new:
        print('equal')
        return 0
    print('different')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
