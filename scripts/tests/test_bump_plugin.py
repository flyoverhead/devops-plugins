import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bump_plugin import bump  # noqa: E402


class BumpTest(unittest.TestCase):
    def test_bump_updates_both_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '.claude-plugin').mkdir()
            (root / 'demo/.claude-plugin').mkdir(parents=True)
            (root / '.claude-plugin/marketplace.json').write_text(json.dumps(
                {'plugins': [{'name': 'demo', 'version': '1.0.0', 'description': 'a — b'}]}, indent=2) + '\n')
            (root / 'demo/.claude-plugin/plugin.json').write_text(json.dumps({'name': 'demo', 'version': '1.0.0'}))
            bump(root, 'demo', '2.0.0')
            self.assertEqual(json.loads((root / 'demo/.claude-plugin/plugin.json').read_text())['version'], '2.0.0')
            market = (root / '.claude-plugin/marketplace.json').read_text()
            self.assertEqual(json.loads(market)['plugins'][0]['version'], '2.0.0')
            self.assertIn('\\u2014', market)

    def test_bump_unknown_plugin(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '.claude-plugin').mkdir()
            (root / '.claude-plugin/marketplace.json').write_text('{"plugins": []}\n')
            with self.assertRaises(SystemExit):
                bump(root, 'nope', '1.0.0')

    def test_bump_preserves_key_order(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '.claude-plugin').mkdir()
            (root / 'demo/.claude-plugin').mkdir(parents=True)
            market = {'name': 'm', 'plugins': [{'name': 'demo', 'source': './demo', 'version': '1.0.0', 'description': 'x'}]}
            manifest = {'name': 'demo', 'version': '1.0.0', 'description': 'x', 'author': {'name': 'a'}}
            (root / '.claude-plugin/marketplace.json').write_text(json.dumps(market))
            (root / 'demo/.claude-plugin/plugin.json').write_text(json.dumps(manifest))
            bump(root, 'demo', '1.1.0')
            written = json.loads((root / 'demo/.claude-plugin/plugin.json').read_text())
            self.assertEqual(list(written), ['name', 'version', 'description', 'author'])
            written = json.loads((root / '.claude-plugin/marketplace.json').read_text())
            self.assertEqual(list(written), ['name', 'plugins'])
            self.assertEqual(list(written['plugins'][0]), ['name', 'source', 'version', 'description'])

    def test_invalid_version_exits_before_writing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '.claude-plugin').mkdir()
            (root / 'demo/.claude-plugin').mkdir(parents=True)
            market = '{"plugins": [{"name": "demo", "version": "1.0.0"}]}'
            (root / '.claude-plugin/marketplace.json').write_text(market)
            (root / 'demo/.claude-plugin/plugin.json').write_text('{"name": "demo", "version": "1.0.0"}')
            for bad in ('1.0', 'v1.0.0', '1.0.0-rc1', '01.0.0', '', 'latest'):
                with self.assertRaises(SystemExit, msg=bad):
                    bump(root, 'demo', bad)
            self.assertEqual((root / '.claude-plugin/marketplace.json').read_text(), market)

    def test_cli_invalid_version_returns_1(self):
        script = Path(__file__).resolve().parent.parent / 'bump_plugin.py'
        result = subprocess.run([sys.executable, str(script), 'ansible', '1.0'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('invalid version', result.stderr)


if __name__ == '__main__':
    unittest.main()
