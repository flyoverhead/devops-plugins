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
        write(self.root / 'demo/skills/good/SKILL.md', skill(extra='allowed-tools: Bash(git diff:*) Read Grep\n'))
        self.assertEqual(self.rules(), set())

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
