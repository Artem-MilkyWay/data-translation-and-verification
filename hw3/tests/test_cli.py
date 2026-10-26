"""End-to-end checks through the same entry point used for submission."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CLITests(unittest.TestCase):
    def run_cli(self, *args, source=None):
        return subprocess.run([sys.executable, str(ROOT / 'main.py'), *args],
                              input=source, text=True, capture_output=True,
                              cwd=ROOT.parent, timeout=30)

    def test_valid_file_from_other_directory(self):
        result = self.run_cli(str(ROOT / 'examples/typed.funny'), '--ast', '--compact')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data['ok'])
        self.assertEqual(data['errors'], [])
        self.assertEqual(result.stderr, '')
        self.assertEqual(len(result.stdout.splitlines()), 1)

    def test_semantic_errors_return_json_and_nonzero(self):
        result = self.run_cli(str(ROOT / 'examples/errors.funny'))
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertFalse(data['ok'])
        self.assertGreaterEqual(len(data['errors']), 5)
        self.assertIn('E_UNKNOWN_NAME', result.stderr)
        self.assertIn('2:9:', result.stderr)

    def test_stdin(self):
        result = self.run_cli('-', source='function f() returns r: int { r = 0; }')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])

    def test_tokens(self):
        result = self.run_cli('-', '--tokens', source='// bool\nbool')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "2:1\tBOOL_TYPE\t'bool'\n")

    def test_missing_file_is_clean_error(self):
        result = self.run_cli(str(ROOT / 'does_not_exist.funny'))
        self.assertEqual(result.returncode, 2)
        self.assertIn('Cannot read source', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_invalid_syntax_emits_json(self):
        result = self.run_cli('-', source='function f() returns r: int { r = ; }')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['errors'][0]['phase'], 'parser')


if __name__ == '__main__':
    unittest.main()
