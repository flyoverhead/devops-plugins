#!/usr/bin/env python3
"""Set a plugin's version in plugin.json and marketplace.json together."""
import json
import re
import sys
from pathlib import Path


SEMVER = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n')


def bump(root, plugin, version):
    if not SEMVER.match(version):
        sys.exit(f'invalid version: {version} (want X.Y.Z)')
    root = Path(root)
    market_path = root / '.claude-plugin/marketplace.json'
    market = json.loads(market_path.read_text())
    entry = next((p for p in market.get('plugins', []) if p.get('name') == plugin), None)
    manifest_path = root / plugin / '.claude-plugin/plugin.json'
    if entry is None or not manifest_path.exists():
        sys.exit(f'unknown plugin: {plugin}')
    manifest = json.loads(manifest_path.read_text())
    manifest['version'] = version
    entry['version'] = version
    dump(manifest_path, manifest)
    dump(market_path, market)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: bump_plugin.py <plugin> <version>')
    bump(Path(__file__).resolve().parent.parent, sys.argv[1], sys.argv[2])
    print(f'{sys.argv[1]} -> {sys.argv[2]}')
