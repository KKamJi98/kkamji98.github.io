import json
import tempfile
import unittest
from pathlib import Path
import pipeline

class FontPolicyTests(unittest.TestCase):
    def test_production_bundle_rejects_modified_binary(self):
        self.assertTrue(hasattr(pipeline, 'load_bundle'), 'pinned production bundle policy missing')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'font.woff2').write_bytes(b'font fixture')
            lock = {'resources': [{'url': 'https://fonts.example/font.woff2', 'path': 'font.woff2',
                'sha256': pipeline.digest(b'font fixture'), 'content_type': 'font/woff2',
                'source': 'https://fonts.example/font.woff2', 'license': 'fixture only'}]}
            (root/'lock.json').write_text(json.dumps(lock))
            self.assertIn('https://fonts.example/font.woff2', pipeline.load_bundle(root/'lock.json'))
            (root/'font.woff2').write_bytes(b'changed')
            with self.assertRaises(ValueError): pipeline.load_bundle(root/'lock.json')

class ProductionGateTests(unittest.TestCase):
    def test_production_rejects_fallback_or_blocked_fonts(self):
        self.assertTrue(hasattr(pipeline, 'font_policy'), 'actual rendered font gate missing')
        web = [{'isCustomFont': True, 'postScriptName': 'Pinned', 'glyphCount': 10}]
        local = [{'isCustomFont': False, 'postScriptName': 'Fallback', 'glyphCount': 10}]
        self.assertEqual(pipeline.font_policy('production', web, [])['status'], 'pinned-web-fonts')
        with self.assertRaises(ValueError): pipeline.font_policy('production', local, [])
        with self.assertRaises(ValueError): pipeline.font_policy('production', web, ['https://x/font'])
        self.assertFalse(pipeline.font_policy('local-fallback', local, [])['production_identical'])

class ProductionBrowserTests(unittest.TestCase):
    def test_offline_pinned_binary_and_fallback_rejection(self):
        import subprocess, sys
        font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
        if not font.is_file(): self.skipTest('fixture requires existing DejaVuSans.ttf; no installation')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); site = root/'site'; site.mkdir()
            (root/'font.ttf').write_bytes(font.read_bytes())
            css = '@font-face{font-family:Pinned;src:url(https://fixture.invalid/font.ttf)}figure{font-family:Pinned;font-size:16px;margin:0}.content{max-width:100%}'
            (root/'style.css').write_text(css)
            resources = []
            for filename, mime in [('font.ttf','font/ttf'), ('style.css','text/css')]:
                resources.append({'url':'https://fixture.invalid/'+filename,'path':filename,
                    'sha256':pipeline.digest((root/filename).read_bytes()),'content_type':mime,
                    'source':'local test fixture, NOT production evidence','license':'existing system test fixture'})
            lock = root/'lock.json'; lock.write_text(json.dumps({'resources':resources}))
            page = '<meta charset="utf-8"><link rel="stylesheet" href="https://fixture.invalid/style.css"><article class="content"><figure class="sd" id="test"><span>Latin text</span></figure></article>'
            (site/'index.html').write_text(page)
            cmd = [sys.executable, str(Path(pipeline.__file__)), '--site', str(site), '--page','index.html','--figure','test','--out',str(root/'out'),'--font-bundle',str(lock)]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
            receipt = json.loads((root/'out/test-625-light.json').read_text())
            self.assertEqual(receipt['font_policy']['status'], 'pinned-web-fonts')
            self.assertFalse(receipt['font_policy']['production_identical'])
            self.assertIn(pipeline.digest(font.read_bytes()), receipt['inputs']['loaded_font_binaries'].values())
            (site/'index.html').write_text(page.replace('Latin text', 'Latin text 한국어'))
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0, 'unbundled Korean fallback must fail')

if __name__ == '__main__': unittest.main()
