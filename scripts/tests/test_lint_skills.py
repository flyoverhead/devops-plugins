import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lint_skills import run_lint  # noqa: E402

GOOD_DESC = 'Builds demo things. Use when the user asks for a demo thing.'

def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)

def skill(desc: str = GOOD_DESC, body: str = '# Demo\n\nDo it.\n', extra: str = '') -> str:
    return f'---\nname: good\ndescription: {desc}\n{extra}---\n\n{body}'

class LintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write(self.root / '.claude-plugin/marketplace.json', json.dumps(
            {'metadata': {'version': '1.0.0'}, 'name': 'devops',
             'plugins': [{'name': 'demo', 'source': './demo', 'version': '1.0.0'}]}))
        write(self.root / 'demo/.claude-plugin/plugin.json', json.dumps({'name': 'demo', 'version': '1.0.0'}))
        write(self.root / 'demo/skills/good/SKILL.md', skill())

    def tearDown(self):
        self.tmp.cleanup()

    def rules(self, level='ERROR'):
        return {i[3] for i in run_lint(self.root, validate=False).items if i[0] == level}

    def test_clean_plugin_passes(self):
        self.assertEqual(self.rules(), set())

    def test_s1_banned_pattern(self):
        write(self.root / 'demo/skills/good/SKILL.md',
              skill('This skill should be used when the user asks for demo.'))
        self.assertIn('S1-desc-pattern', self.rules())

    def test_s1_block_scalar(self):
        write(self.root / 'demo/skills/good/SKILL.md', skill('|\n  Builds demo.\n  Use when x.'))
        self.assertIn('S1-desc-block', self.rules())

    def test_s1_length(self):
        write(self.root / 'demo/skills/good/SKILL.md', skill('Builds ' + 'x' * 1600 + '. Use when y.'))
        self.assertIn('S1-desc-length', self.rules())
        write(self.root / 'demo/skills/good/SKILL.md', skill('Builds ' + 'x' * 700 + '. Use when y.'))
        self.assertNotIn('S1-desc-length', self.rules())
        self.assertIn('S1-desc-length', self.rules('WARN'))

    def test_s1_missing(self):
        write(self.root / 'demo/skills/good/SKILL.md', '---\nname: good\n---\n\nBody\n')
        self.assertIn('S1-desc-missing', self.rules())

    def test_s3_body_length(self):
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='line\n' * 501))
        self.assertIn('S3-body-length', self.rules())
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='line\n' * 260))
        self.assertNotIn('S3-body-length', self.rules())
        self.assertIn('S3-body-length', self.rules('WARN'))

    def test_s3_toc(self):
        write(self.root / 'demo/skills/good/references/big.md', '# Big\n' + 'x\n' * 120)
        self.assertIn('S3-toc', self.rules())
        write(self.root / 'demo/skills/good/references/big.md', '# Big\n\n## Contents\n- a\n' + 'x\n' * 120)
        self.assertNotIn('S3-toc', self.rules())

    def test_s3_chain_is_warning(self):
        write(self.root / 'demo/skills/good/references/a.md', 'See [b](b.md).\n')
        write(self.root / 'demo/skills/good/references/b.md', 'B\n')
        self.assertIn('S3-chain', self.rules('WARN'))
        self.assertNotIn('S3-chain', self.rules())

    def test_s6_auto_approve(self):
        write(self.root / 'demo/skills/good/references/v.md', '```bash\nterraform apply -auto-approve\n```\n')
        self.assertIn('S6-auto-approve', self.rules())

    def test_s6_prohibition_text_is_ignored(self):
        write(self.root / 'demo/skills/good/references/v.md', 'Never run `terraform apply -auto-approve`.\n')
        self.assertNotIn('S6-auto-approve', self.rules())

    def test_s6_signoff(self):
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='Run `git commit -m "feat: x"`.\n'))
        self.assertIn('S6-signoff', self.rules())
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='Run `git commit -s -m "feat: x"`.\n'))
        self.assertNotIn('S6-signoff', self.rules())
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='Hooks run on git commit.\n'))
        self.assertNotIn('S6-signoff', self.rules())
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='```bash\ngit commit -sm "x"\n```\n'))
        self.assertNotIn('S6-signoff', self.rules())

    def test_s7_tools(self):
        write(self.root / 'demo/skills/good/SKILL.md', skill(extra='allowed-tools: Bash Read\n'))
        self.assertIn('S7-bare-bash', self.rules())
        write(self.root / 'demo/skills/good/SKILL.md', skill(extra='allowed-tools: Bash(npx:*) Read\n'))
        self.assertIn('S7-npx', self.rules())
        write(self.root / 'demo/skills/good/SKILL.md', skill(extra='allowed-tools: Bash(git diff:*) Read Grep\n',
                                                             body='No `--output`.\n'))
        self.assertEqual(self.rules(), set())

    def _tools(self, tools):
        write(self.root / 'demo/skills/good/SKILL.md', skill(extra=f'allowed-tools: {tools}\n'))
        return self.rules()

    def test_gh_api_allowed_tools_error(self):
        self.assertIn('S7-gh-write', self._tools('Bash(gh api:*) Read'))

    def test_gh_pr_comment_error(self):
        self.assertIn('S7-gh-write', self._tools('Bash(gh pr comment:*) Read'))

    def test_gh_wildcards_error(self):
        for tok in ('Bash(gh:*)', 'Bash(gh *)', 'Bash(gh pr:*)', 'Bash(gh repo:*)',
                    'Bash(gh issue:*)', 'Bash(gh release:*)'):
            self.assertIn('S7-gh-write', self._tools(f'{tok} Read'), tok)

    def test_gh_pr_view_ok(self):
        self.assertNotIn('S7-gh-write', self._tools('Bash(gh pr view:*) Read'))

    def test_gh_search_code_ok(self):
        self.assertNotIn('S7-gh-write', self._tools('Bash(gh search code:*) Read'))

    def test_gh_allowlist_flags_other_commands(self):
        for tok in ('Bash(gh run cancel:*)', 'Bash(gh label create:*)', 'Bash(gh pr checkout:*)',
                    'Bash(gh pr view*)', 'Bash(gh pr viewer:*)', 'Bash(gh auth login)',
                    'Bash(GH_TOKEN=x gh issue create:*)'):
            self.assertIn('S7-gh-write', self._tools(f'{tok} Read'), tok)

    def test_gh_allowlist_accepts_read_forms(self):
        for tok in ('Bash(gh pr view:*)', 'Bash(gh pr diff:*)', 'Bash(gh pr list:*)',
                    'Bash(gh repo view:*)', 'Bash(gh search code:*)', 'Bash(gh auth status)',
                    'Bash(gh pr view 7)'):
            write(self.root / 'demo/skills/good/SKILL.md',
                  skill(extra=f'allowed-tools: {tok} Read\n', body='Never pass `--web`.\n'))
            self.assertEqual(self.rules(), set(), tok)

    def test_ghost_and_ghq_are_not_gh(self):
        self.assertNotIn('S7-gh-write', self._tools('Bash(ghq list:*) Read'))

    def _flag(self, tools, body):
        write(self.root / 'demo/skills/good/SKILL.md',
              skill(extra=f'allowed-tools: {tools}\n', body=body))
        return 'S7-flag-limits' in self.rules()

    def test_flag_limits_required_per_family(self):
        cases = [
            ('Bash(git log:*)', '`--output`'),
            ('Bash(git show:*)', '`--output`'),
            ('Bash(git diff:*)', '`--output`'),
            ('Bash(git grep:*)', '`-O`'),
            ('Bash(git cat-file:*)', '`--textconv`'),
            ('Bash(rg:*)', '`--pre`'),
            ('Bash(semgrep --metrics=off:*)', '`--output`'),
            ('Bash(SSL_CERT_FILE=/x semgrep --metrics=off:*)', '`-o`'),
            ('Bash(gh pr view:*)', '`--web`'),
            ('Bash(go test:*)', '`-toolexec`'),
            ('Bash(go vet:*)', '`-vettool`'),
            ('Bash(go build:*)', '`-toolexec`'),
        ]
        for tools, flag in cases:
            self.assertTrue(self._flag(tools, '# Demo\n'), tools)
            self.assertFalse(self._flag(tools, f'## Limits\n\nNever pass {flag}.\n'), tools)

    def test_flag_limits_ignores_neighbours(self):
        for tools in ('Bash(git diff-tree:*)', 'Bash(git log-ish)', 'Bash(rgx:*)',
                      'Bash(command -v semgrep)', 'Bash(go buildx:*)', 'Bash(git rev-parse:*)'):
            self.assertFalse(self._flag(tools, '# Demo\n'), tools)

    def test_flag_limits_lookalike_flags_do_not_count(self):
        self.assertTrue(self._flag('Bash(rg:*)', 'Use `--pre-glob`.\n'))
        self.assertTrue(self._flag('Bash(git grep:*)', 'Use `-Ofast`.\n'))
        self.assertTrue(self._flag('Bash(semgrep --metrics=off:*)', 'Use `-of`.\n'))
        self.assertTrue(self._flag('Bash(semgrep --metrics=off:*)', 'Use `--output-dir`.\n'))
        self.assertTrue(self._flag('Bash(git diff:*)', 'Use `--output-indicator-new`.\n'))
        self.assertTrue(self._flag('Bash(gh pr view:*)', 'Use `--web-url`.\n'))

    def test_go_build_needs_toolexec_not_other_flags(self):
        self.assertTrue(self._flag('Bash(go build:*)', 'Never pass `-vettool` or `-o`.\n'))
        self.assertFalse(self._flag('Bash(go build:*)', '`go build`: never `-toolexec` or `-o`.\n'))

    def test_cat_file_no_textconv_is_not_a_limit(self):
        self.assertTrue(self._flag('Bash(git cat-file:*)', 'Run `git cat-file --no-textconv`.\n'))

    def test_git_any_subcommand_is_error(self):
        for tok in ('Bash(git:*)', 'Bash(git *)', 'Bash(git*)', 'Bash(git -C:*)', 'Bash(git -C *)',
                    'Bash(git -c:*)', 'Bash(GIT_PAGER=cat git:*)'):
            self.assertIn('S7-git-any', self._tools(f'{tok} Read'), tok)
        for tok in ('Bash(git rev-parse:*)', 'Bash(gitleaks:*)', 'Bash(git status)'):
            self.assertNotIn('S7-git-any', self._tools(f'{tok} Read'), tok)

    def test_agent_git_any_is_error(self):
        self.assertIn('S7-git-any', self._agent('Read, Bash(git -C:*)'))

    def test_agent_without_tools_line(self):
        write(self.root / 'demo/agents/a.md', '---\nname: a\ndescription: A.\n---\nDo it.\n')
        self.assertIn('S7-agent-tools', self.rules())
        self.assertNotIn('S7-agent-tools', self._agent('Read, Grep, Glob'))

    def _history(self, body, where='demo/skills/good/references/r.md'):
        write(self.root / where, body)
        return 'S11-no-ext-diff' in self.rules()

    def test_history_flags_required(self):
        for body in ('Run `git diff <base> <head>`.\n', 'Read `git show <base>:<path>`.\n',
                     '```bash\ngit log -S\'x\' -p -- a/\n```\n', 'Use `git show --stat <sha>`.\n',
                     '```bash\ngit diff --stat \\\n  <range>\n```\n',
                     'Use `git -C ../x diff HEAD`.\n', '`git diff --no-ext-diff HEAD`\n'):
            self.assertTrue(self._history(body), body)
        self.assertTrue(self._history('Run `git diff HEAD`.\n', 'demo/agents/a.md'))

    def test_history_flags_accepted_or_not_applicable(self):
        for body in ('Run `git diff --no-ext-diff --no-textconv <base> <head>`.\n',
                     'Read `git show --no-ext-diff --no-textconv <base>:<path>`.\n',
                     '```bash\ngit log --no-ext-diff --no-textconv -S\'x\' -p\n```\n',
                     'Read `git diff`, then `git show`.\n', '`git log --oneline <range>`\n',
                     '`git diff`: never `--output`.\n', 'Never `git diff --no-index a b`.\n',
                     '`git diff-tree -r HEAD`, `git show-ref`\n', 'Plain git diff HEAD in prose.\n',
                     '`git diff --no-ext-diff --no-textconv HEAD > out.patch`\n'):
            self.assertFalse(self._history(body), body)

    def _agent(self, tools, body='Do it.\n'):
        write(self.root / 'demo/agents/a.md', f'---\nname: a\ndescription: A.\ntools: {tools}\n---\n{body}')
        return self.rules()

    def test_agent_bare_bash(self):
        self.assertIn('S7-bare-bash', self._agent('Read, Grep, Bash'))
        self.assertNotIn('S7-bare-bash', self._agent('Read, Bash(git show:*)', 'No `--output`.\n'))
        self.assertNotIn('S7-bare-bash', self._agent('Read, Grep, Glob'))

    def test_agent_gh_write_and_flags(self):
        self.assertIn('S7-gh-write', self._agent('Read, Bash(gh pr comment:*)', 'No `--web`.\n'))
        self.assertIn('S7-flag-limits', self._agent('Read, Bash(gh search code:*)'))
        self.assertEqual(self._agent('Read, Bash(gh search code:*)', 'No `--web`.\n'), set())

    def test_agent_tools_as_list(self):
        write(self.root / 'demo/agents/a.md',
              '---\nname: a\ndescription: A.\ntools:\n  - Read\n  - Bash\n---\nx\n')
        self.assertIn('S7-bare-bash', self.rules())

    def test_s7_model_pin(self):
        write(self.root / 'demo/skills/good/SKILL.md', skill(extra='model: sonnet\n'))
        self.assertIn('S7-model-pin', self.rules())

    def test_s8_reports_unknown_component(self):
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='Then use `demo:missing`.\n'))
        self.assertIn('S8-xref', self.rules())
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='Then use `demo:good` or /demo:good.\n'))
        self.assertNotIn('S8-xref', self.rules())

    def test_s8_unknown_plugin_namespace_is_ignored(self):
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='Run `other:thing`.\n'))
        self.assertNotIn('S8-xref', self.rules())

    def test_s8_ignores_image_lines(self):
        write(self.root / 'demo/skills/good/SKILL.md',
              skill(body='```dockerfile\nFROM demo:latest\n```\n\nimage: demo:alpine\n'))
        self.assertNotIn('S8-xref', self.rules())

    def test_s8_ignores_changelog(self):
        write(self.root / 'demo/CHANGELOG.md', 'Removed `demo:old-command`.\n')
        self.assertNotIn('S8-xref', self.rules())

    def test_s10_agent(self):
        write(self.root / 'demo/agents/a.md', '---\nname: a\ndescription: A.\n---\n' + 'x\n' * 81)
        self.assertIn('S10-agent-length', self.rules())
        write(self.root / 'demo/agents/a.md', '---\nname: a\ndescription: A.\n---\nQuery the context manager.\n')
        self.assertIn('S10-context-manager', self.rules())

    def test_agent_counts_as_component(self):
        write(self.root / 'demo/agents/helper.md', '---\nname: helper\ndescription: H.\n---\nHelp.\n')
        write(self.root / 'demo/skills/good/SKILL.md', skill(body='Delegate to demo:helper.\n'))
        self.assertNotIn('S8-xref', self.rules())

    def test_repo_commands_dir(self):
        write(self.root / 'demo/commands/x.md', '---\ndescription: x\n---\nx\n')
        self.assertIn('R-commands-dir', self.rules())

    def test_lint_flags_version_mismatch(self):
        write(self.root / '.claude-plugin/marketplace.json', json.dumps(
            {'name': 'devops', 'plugins': [{'name': 'demo', 'source': './demo', 'version': '1.0.0'}]}))
        write(self.root / 'demo/.claude-plugin/plugin.json', json.dumps({'name': 'demo', 'version': '1.0.1'}))
        self.assertIn('R-version-sync', self.rules())

    def test_repo_version_sync(self):
        write(self.root / 'demo/.claude-plugin/plugin.json', json.dumps({'name': 'demo', 'version': '1.1.0'}))
        self.assertIn('R-version-sync', self.rules())

    def test_s6_nested_fence_and_prose_after(self):
        body = ('````markdown\n```bash\ngit commit -m x\n```\n````\n\n'
                'Then run `git commit -s -m "y"`.\n')
        write(self.root / 'demo/skills/good/SKILL.md', skill(body=body))
        res = [i for i in run_lint(self.root, validate=False).items if i[3] == 'S6-signoff']
        self.assertEqual(len(res), 1)

    def test_s6_tilde_fence(self):
        write(self.root / 'demo/skills/good/SKILL.md',
              skill(body='~~~bash\nterraform apply -auto-approve\n~~~\n'))
        self.assertIn('S6-auto-approve', self.rules())

    def test_s6_continued_commit_is_signed(self):
        write(self.root / 'demo/skills/good/SKILL.md',
              skill(body='```bash\ngit commit \\\n  -s -m "x"\n```\n'))
        self.assertNotIn('S6-signoff', self.rules())

    def test_s6_commit_graph(self):
        write(self.root / 'demo/skills/good/SKILL.md',
              skill(body='```bash\ngit commit-graph write\n```\n'))
        self.assertNotIn('S6-signoff', self.rules())

    def test_non_dict_frontmatter(self):
        write(self.root / 'demo/skills/good/SKILL.md', '---\n- a\n- b\n---\n\nBody\n')
        self.assertIn('S1-frontmatter', self.rules())
        write(self.root / 'demo/skills/good/SKILL.md', '---\njust a string\n---\n\nBody\n')
        self.assertIn('S1-frontmatter', self.rules())
        write(self.root / 'demo/agents/a.md', '---\n- a\n---\nx\n')
        self.assertIn('S1-frontmatter', self.rules())

    def test_non_string_description(self):
        write(self.root / 'demo/skills/good/SKILL.md', skill('yes'))
        items = [i for i in run_lint(self.root, validate=False).items if i[3] == 'S1-desc-missing']
        self.assertEqual(len(items), 1)
        self.assertIn('must be a string', items[0][4])
        write(self.root / 'demo/skills/good/SKILL.md', skill('42'))
        self.assertIn('S1-desc-missing', self.rules())

    def test_marketplace_entry_without_name(self):
        write(self.root / '.claude-plugin/marketplace.json', json.dumps(
            {'plugins': [{'source': './x'}, {'name': 'demo', 'version': '1.0.0'}]}))
        self.assertEqual(self.rules(), set())

if __name__ == '__main__':
    unittest.main()
