import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parent
LOCK = ROOT.parents[2] / 'assets/fonts/deterministic-export/lock.json'

class ExportTests(unittest.TestCase):
    def test_repeat_bytes_and_font_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            (d/'index.html').write_text('<meta charset="utf-8"><style>.content{max-width:100%}figure{margin:0;font-size:16px}</style><article class="content"><figure class="sd" id="fixture">한국어 Latin <code>code_123</code></figure></article>')
            cmd = [sys.executable, str(ROOT/'pipeline.py'), '--site', str(d), '--page', 'index.html', '--figure', 'fixture', '--font-profile', 'deterministic-export', '--out', str(d/'out')]
            def run(extra=()):
                return subprocess.run(cmd+list(extra), capture_output=True, text=True, timeout=60)
            result = run()
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            png = d/'out/fixture-625-light.png'
            mobile = d/'out/fixture-360-light.png'
            before = (png.read_bytes(), mobile.read_bytes())
            result = run()
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertEqual(before, (png.read_bytes(), mobile.read_bytes()))
            self.assertEqual(run(['--check']).returncode, 0)
            # A changed pinned font input invalidates freshness even with valid new hash.
            import shutil, hashlib
            shutil.copytree(LOCK.parent, d/'fonts')
            lock = json.loads((d/'fonts/lock.json').read_text())
            entry = lock['resources'][0]
            font = d/'fonts'/entry['path']
            font.write_bytes(font.read_bytes()+b'\0')
            entry['sha256'] = hashlib.sha256(font.read_bytes()).hexdigest()
            (d/'fonts/lock.json').write_text(json.dumps(lock))
            changed = run(['--check', '--export-font-bundle', str(d/'fonts/lock.json')])
            self.assertEqual(changed.returncode, 1, changed.stdout+changed.stderr)
            self.assertFalse(json.loads(changed.stdout)['fresh'])

    def test_no_networkidle_wait(self):
        self.assertNotIn('networkidle', (ROOT/'pipeline.py').read_text())
