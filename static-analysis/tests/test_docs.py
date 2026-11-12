import json
import re
import shutil
import subprocess

import pytest

from conftest import PLUGIN, SARIF_RESOURCES, SEMGREP_SCRIPTS, require, run

DOCS = sorted(PLUGIN.glob('skills/*/SKILL.md')) + sorted(PLUGIN.glob('skills/*/references/*.md'))
BLOCK = re.compile(r'^```(\w*)\n(.*?)^```', re.M | re.S)
LINK = re.compile(r'\]\((references/[^)#\s]+)(?:#([\w-]+))?\)')


def blocks(lang):
    for doc in DOCS:
        for m in BLOCK.finditer(doc.read_text()):
            if m.group(1) == lang:
                yield doc, m.group(2)


@pytest.mark.parametrize('doc, code', list(blocks('bash')),
                         ids=lambda v: v.name if hasattr(v, 'name') else '')
def test_bash_blocks_parse(doc, code):
    syntax = run(['bash', '-n', '-c', code])
    assert not syntax.returncode, (doc.name, syntax.stderr)


def anchor(title):
    return re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-')


@pytest.mark.parametrize('skill', sorted(PLUGIN.glob('skills/*/SKILL.md')), ids=lambda p: p.parent.name)
def test_reference_links_resolve(skill):
    for target, frag in LINK.findall(skill.read_text()):
        path = skill.parent / target
        assert path.is_file(), f'{skill}: {target} missing'
        if frag:
            heads = {anchor(h) for h in re.findall(r'^#+ (.+)$', path.read_text(), re.M)}
            assert frag in heads, f'{skill}: #{frag} not a heading in {target}'


def test_pasteable_definitions_match_module():
    doc = (PLUGIN / 'skills/sarif-parsing/references/jq-queries.md').read_text()
    pasted = [m.group(2) for m in BLOCK.finditer(doc) if m.group(1) == 'jq'][0]
    assert pasted.strip() == (SARIF_RESOURCES / 'sarif.jq').read_text().strip()


def test_jq_module_counts_one_error_per_fixture():
    require('jq')
    for name in ('codeql-no-level.sarif', 'levels-on-results.sarif'):
        res = run(['jq', '-L', str(SARIF_RESOURCES), 'include "sarif"; [sarif_results | select(._level == "error")] | length',
                   str(SARIF_RESOURCES / 'fixtures' / name)])
        assert res.stdout.strip() == '1', (name, res.stderr)


def test_naive_level_filter_misses_codeql_errors():
    require('jq')
    naive = 'reduce (.runs[].results[] | select(.level == "error")) as $_ (0; . + 1)'
    res = run(['jq', naive, str(SARIF_RESOURCES / 'fixtures/codeql-no-level.sarif')])
    assert int(res.stdout) == 0


def test_semgrep_important_filter():
    require('jq')
    def item(cid, **meta):
        return {'check_id': cid, 'extra': {'metadata': meta} if meta else {}}
    data = json.dumps({'results': [item('a', category='security', confidence='HIGH', impact='LOW'),
                                   item('b', category='security', confidence='medium', impact='high'),
                                   item('c'), item('d', category='best-practice')],
                       'errors': [], 'paths': {'scanned': ['x']}}, separators=(',', ':'))
    res = subprocess.run(['jq', '-c', '-f', str(SEMGREP_SCRIPTS / 'important-filter.jq')],
                         input=data, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert re.findall(r'"check_id":"(\w)"', res.stdout) == ['b', 'c']
    assert '"paths":{"scanned":["x"]}' in res.stdout


def test_runner_flags_in_docs_exist():
    skill = (PLUGIN / 'skills/semgrep/SKILL.md').read_text()
    help_text = run(['bash', str(SEMGREP_SCRIPTS / 'run-scans.sh'), '--help']).stdout
    for flag in set(re.findall(r'`(--[a-z-]+)', skill)):
        if flag in ('--metrics', '--disable-version-check', '--config', '--severity', '--important', '--scans',
                    '--output', '--autofix'):
            continue
        assert flag in help_text, flag


def test_suite_names_match_generator():
    gen = (PLUGIN / 'skills/codeql/scripts/generate_suite.sh').read_text()
    ref = (PLUGIN / 'skills/codeql/references/query-suites.md').read_text()
    for name in ('security-and-quality', 'security-experimental', 'modeleditor', 'modelgenerator'):
        assert name in gen and name in ref


def test_no_codeql_in_allowed_tools():
    front = (PLUGIN / 'skills/codeql/SKILL.md').read_text().split('---')[1]
    tools = re.search(r'^allowed-tools: (.*)$', front, re.M).group(1)
    assert 'Bash(codeql' not in tools and ' Edit' not in tools and not re.search(r'(^| )Bash( |$)', tools)


def test_semgrep_scan_not_preapproved():
    front = (PLUGIN / 'skills/semgrep/SKILL.md').read_text().split('---')[1]
    tools = re.search(r'^allowed-tools: (.*)$', front, re.M).group(1)
    assert 'Bash(semgrep scan' not in tools and 'Bash(semgrep:' not in tools


def test_sarif_parsing_has_no_write():
    front = (PLUGIN / 'skills/sarif-parsing/SKILL.md').read_text().split('---')[1]
    tools = re.search(r'^allowed-tools: (.*)$', front, re.M).group(1)
    assert 'Write' not in tools and 'Edit' not in tools


def test_shellcheck_scripts():
    if shutil.which('shellcheck') is None:
        pytest.skip('not run: shellcheck missing')
    scripts = [str(p) for p in PLUGIN.glob('skills/*/scripts/*.sh')]
    res = subprocess.run(['shellcheck', *scripts], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout
