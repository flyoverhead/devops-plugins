#!/usr/bin/env python3
"""Lint skills, agents and plugin manifests."""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

BANNED_DESC = re.compile(r'this skill should be used', re.I)
BLOCK_DESC = re.compile(r'^description:\s*[|>]', re.M)
XREF = re.compile(r'(?<![\w.@-])/?([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)\b')
DOCKER_FROM = re.compile(r'^\s*FROM\s')
IMAGE_LINE = re.compile(r'image:', re.I)
FENCE = re.compile(r'^\s*(`{3,}|~{3,})')
GIT_COMMIT = re.compile(r'git commit(?![\w-])([^\n]*)')
MD_LINK = re.compile(r'\]\(([^)#\s]+\.md)\)')
PROCEED = re.compile(r'proceed to\s+[`*]*([\w./-]+\.md)', re.I)
PROHIBITION = re.compile(r"\b(never|do not|don't|must not|forbidden|banned|not allowed)\b", re.I)
TOOL_TOKEN = re.compile(r'[\w.*-]+(?:\([^)]*\))?')
NPX = re.compile(r'^Bash\(npx(?::\*| \*|\*)\)$')
MODEL_PIN = {'sonnet', 'haiku', 'opus'}
DESC_HARD, DESC_SOFT = 1536, 600
BODY_HARD, BODY_SOFT = 500, 250
REF_TOC_MIN = 100
AGENT_MAX = 80


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, path, line, rule, msg):
        self.items.append((level, str(path), line, rule, msg))

    def error(self, path, line, rule, msg):
        self.add('ERROR', path, line, rule, msg)

    def warn(self, path, line, rule, msg):
        self.add('WARN', path, line, rule, msg)

    @property
    def errors(self):
        return [i for i in self.items if i[0] == 'ERROR']


def split_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return {}, '', lines, 1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == '---':
            raw = '\n'.join(lines[1:idx])
            try:
                meta = yaml.safe_load(raw) or {}
            except yaml.YAMLError:
                meta = None
            if not isinstance(meta, dict):
                meta = None
            return meta, raw, lines[idx + 1:], idx + 2
    return None, '', lines, 1


def plugins(root):
    return sorted(p.parent.parent for p in root.glob('*/.claude-plugin/plugin.json'))


def components(root):
    known = {}
    for pdir in plugins(root):
        name = json.loads((pdir / '.claude-plugin/plugin.json').read_text()).get('name', pdir.name)
        comps = set()
        for sk in pdir.glob('skills/*/SKILL.md'):
            meta, _, _, _ = split_frontmatter(sk.read_text())
            comps.add((meta or {}).get('name') or sk.parent.name)
            comps.add(sk.parent.name)
        for ag in pdir.glob('agents/**/*.md'):
            meta, _, _, _ = split_frontmatter(ag.read_text())
            comps.add((meta or {}).get('name') or ag.stem)
            comps.add(ag.stem)
        for cmd in pdir.glob('commands/*.md'):
            comps.add(cmd.stem)
        known[name] = comps
    return known


def rel(root, path):
    return path.relative_to(root)


def check_skill(root, path, rep):
    meta, raw, body, body_start = split_frontmatter(path.read_text())
    r = rel(root, path)
    if meta is None:
        rep.error(r, 1, 'S1-frontmatter', 'frontmatter missing or not a YAML mapping')
        return
    if BLOCK_DESC.search(raw):
        rep.error(r, 2, 'S1-desc-block', 'description must be a single-line scalar, not | or >')
    desc = meta.get('description')
    if desc is not None and not isinstance(desc, str):
        rep.error(r, 1, 'S1-desc-missing', 'description must be a string')
    elif not desc or not desc.strip():
        rep.error(r, 1, 'S1-desc-missing', 'description is missing')
    else:
        if BANNED_DESC.search(desc):
            rep.error(r, 2, 'S1-desc-pattern', 'use "<Verb>s <what>. Use when <situations>."')
        total = len(desc) + len(str(meta.get('when_to_use') or ''))
        if total > DESC_HARD:
            rep.error(r, 2, 'S1-desc-length', f'{total} chars > {DESC_HARD}')
        elif total > DESC_SOFT:
            rep.warn(r, 2, 'S1-desc-length', f'{total} chars > {DESC_SOFT} recommended')
    n = len('\n'.join(body).rstrip().splitlines())
    if n > BODY_HARD:
        rep.error(r, body_start, 'S3-body-length', f'body {n} lines > {BODY_HARD}')
    elif n > BODY_SOFT:
        rep.warn(r, body_start, 'S3-body-length', f'body {n} lines > {BODY_SOFT} target')
    tools = meta.get('allowed-tools') or []
    tokens = tools if isinstance(tools, list) else TOOL_TOKEN.findall(str(tools))
    for tok in tokens:
        tok = str(tok).strip()
        if tok == 'Bash':
            rep.error(r, 1, 'S7-bare-bash', 'bare Bash pre-approves every command')
        if NPX.match(tok):
            rep.error(r, 1, 'S7-npx', 'Bash(npx:*) runs any package; name the package')
    if str(meta.get('model', '')).lower() in MODEL_PIN:
        rep.error(r, 1, 'S7-model-pin', f'model: {meta["model"]} overrides the caller')


def check_references(root, skill_dir, rep):
    for md in sorted(skill_dir.rglob('*.md')):
        if md.name == 'SKILL.md':
            continue
        lines = md.read_text().splitlines()
        r = rel(root, md)
        if len(lines) > REF_TOC_MIN:
            head = [l.strip().lower() for l in lines[:30]]
            if '## contents' not in head and '## table of contents' not in head:
                rep.error(r, 1, 'S3-toc', f'{len(lines)} lines without a "## Contents" section')
        for no, line in enumerate(lines, 1):
            for target in MD_LINK.findall(line) + PROCEED.findall(line):
                if (md.parent / target).resolve().is_relative_to(skill_dir.resolve()):
                    rep.warn(r, no, 'S3-chain', f'reference links to {target}; link it from SKILL.md')


def code_spans(line, in_fence):
    if in_fence:
        return [line]
    return re.findall(r'`([^`]*)`', line)


def fenced_lines(text):
    fence = None
    pending, start = '', 0
    for no, line in enumerate(text.splitlines(), 1):
        m = FENCE.match(line)
        if fence is None and m:
            fence = (m.group(1)[0], len(m.group(1)))
            continue
        if fence and m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] \
                and line.strip() == line.strip()[0] * len(line.strip()):
            fence = None
            continue
        if fence and line.rstrip().endswith('\\'):
            start = start or no
            pending += line.rstrip()[:-1] + ' '
            continue
        if pending:
            line, no, pending, start = pending + line, start, '', 0
        yield no, line, fence is not None


def check_safety(root, path, rep):
    for no, line, in_fence in fenced_lines(path.read_text()):
        if PROHIBITION.search(line):
            continue
        for span in code_spans(line, in_fence):
            if '-auto-approve' in span:
                rep.error(rel(root, path), no, 'S6-auto-approve', 'no apply/destroy -auto-approve')
            for m in GIT_COMMIT.finditer(span):
                toks = m.group(1).split()
                signed = '--signoff' in toks or any(
                    t.startswith('-') and not t.startswith('--') and 's' in t[1:] for t in toks)
                if not signed:
                    rep.error(rel(root, path), no, 'S6-signoff', 'git commit needs -s')


def check_agent(root, path, rep):
    text = path.read_text()
    r = rel(root, path)
    if split_frontmatter(text)[0] is None:
        rep.error(r, 1, 'S1-frontmatter', 'frontmatter must be a YAML mapping')
    if len(text.splitlines()) > AGENT_MAX:
        rep.error(r, 1, 'S10-agent-length', f'{len(text.splitlines())} lines > {AGENT_MAX}')
    if re.search(r'context manager', text, re.I):
        rep.error(r, 1, 'S10-context-manager', 'remove the non-existent context manager protocol')


def check_xrefs(root, known, rep):
    files = [root / 'README.md', root / 'CLAUDE.md']
    for pdir in plugins(root):
        files += [p for p in pdir.rglob('*.md') if p.name != 'CHANGELOG.md' and '/evals/' not in str(p)]
    for f in files:
        if not f.exists():
            continue
        for no, line in enumerate(f.read_text().splitlines(), 1):
            if DOCKER_FROM.search(line) or IMAGE_LINE.search(line):
                continue
            for ns, name in XREF.findall(line):
                if ns in known and name not in known[ns]:
                    rep.error(rel(root, f), no, 'S8-xref', f'{ns}:{name} does not exist')


def check_repo(root, rep, validate, require_claude):
    market = json.loads((root / '.claude-plugin/marketplace.json').read_text())
    entries = {p['name']: p for p in market.get('plugins', []) if 'name' in p}
    claude = shutil.which('claude')
    for pdir in plugins(root):
        manifest = json.loads((pdir / '.claude-plugin/plugin.json').read_text())
        r = rel(root, pdir / '.claude-plugin/plugin.json')
        entry = entries.get(manifest.get('name'))
        if entry is None:
            rep.error(r, 1, 'R-version-sync', 'plugin missing from marketplace.json')
        elif entry.get('version') != manifest.get('version'):
            rep.error(r, 1, 'R-version-sync',
                      f'plugin.json {manifest.get("version")} != marketplace.json {entry.get("version")}')
        if (pdir / 'commands').exists():
            rep.error(rel(root, pdir / 'commands'), 1, 'R-commands-dir', 'fold commands into skills')
        if not validate:
            continue
        if claude is None:
            (rep.error if require_claude else rep.warn)(r, 1, 'R-validate', 'claude CLI not found; skipped')
            continue
        res = subprocess.run([claude, 'plugin', 'validate', '--strict', str(pdir)],
                             capture_output=True, text=True)
        if res.returncode != 0:
            last = (res.stdout + res.stderr).strip().splitlines()[-1:] or ['failed']
            rep.error(r, 1, 'R-validate', last[0])


def run_lint(root, validate=True, require_claude=False):
    root = Path(root).resolve()
    rep = Report()
    known = components(root)
    for pdir in plugins(root):
        for sk in sorted(pdir.glob('skills/*/SKILL.md')):
            check_skill(root, sk, rep)
            check_references(root, sk.parent, rep)
            for md in sorted(sk.parent.rglob('*.md')):
                check_safety(root, md, rep)
        for ag in sorted(pdir.glob('agents/**/*.md')):
            check_agent(root, ag, rep)
    check_xrefs(root, known, rep)
    check_repo(root, rep, validate, require_claude)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', default=Path(__file__).resolve().parent.parent, type=Path)
    ap.add_argument('--plugin', action='append', default=[])
    ap.add_argument('--no-validate', action='store_true')
    ap.add_argument('--require-claude', action='store_true')
    args = ap.parse_args(argv)
    rep = run_lint(args.root, validate=not args.no_validate, require_claude=args.require_claude)
    items = [i for i in rep.items
             if not args.plugin or any(i[1].startswith(p + '/') for p in args.plugin)]
    for level, path, line, rule, msg in sorted(items, key=lambda i: (i[1], i[2], i[3])):
        print(f'{path}:{line}: {level} {rule}: {msg}')
    errors = [i for i in items if i[0] == 'ERROR']
    print(f'{len(errors)} error(s), {len(items) - len(errors)} warning(s)')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
