import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parent

class PipelineTests(unittest.TestCase):
    def test_input_fingerprint_covers_every_dependency(self):
        self.assertTrue((ROOT / 'pipeline.py').exists(), 'pipeline not implemented')
        spec = importlib.util.spec_from_file_location('pipeline', ROOT / 'pipeline.py')
        assert spec is not None and spec.loader is not None
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        base = dict(html='abc', css='def', fonts='ghi', viewport=625, theme='light', browser='123')
        for key in base:
            changed = dict(base); changed[key] = str(base[key]) + 'changed'
            self.assertNotEqual(m.fingerprint(base), m.fingerprint(changed), key)
        self.assertEqual(m.fingerprint(base), m.fingerprint(dict(reversed(list(base.items())))))

class GateTests(unittest.TestCase):
    def test_negative_receipts(self):
        import pipeline as m
        self.assertTrue(hasattr(m, 'freshness'), 'freshness gate missing')
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'x.png'; p.write_bytes(b'png')
            receipt = {'fingerprint': 'old', 'png_sha256': m.digest(p.read_bytes())}
            self.assertFalse(m.freshness(receipt, 'new', p))
            self.assertTrue(m.freshness(receipt, 'old', p))
            p.write_bytes(b'changed')
            self.assertFalse(m.freshness(receipt, 'old', p))
            p.unlink()
            self.assertFalse(m.freshness(receipt, 'old', p))

    def test_geometry_and_legibility_fail_closed(self):
        import pipeline as m
        self.assertTrue(hasattr(m, 'gate'), 'quality gate missing')
        good = dict(overflow=[], small=[], hidden=[], unselectable=[], broken=[], interaction=[])
        self.assertTrue(m.gate(good))
        for key in good:
            bad = dict(good); bad[key] = ['bad fixture']
            self.assertFalse(m.gate(bad), key)

    def test_browser_negative_fixtures(self):
        from playwright.sync_api import sync_playwright
        import pipeline as m
        base = '<figure class="sd sd--layer" style="width:625px;font-size:16px"><span class="sd-label">Visible label</span></figure>'
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(base)
            self.assertTrue(m.gate(page.locator('figure').evaluate(m.AUDIT)))
            fixtures = [('small', 'font-size:10px'), ('unselectable', 'user-select:none'), ('hidden', 'display:none'), ('overflow', 'display:block;width:900px')]
            for key, style in fixtures:
                page.set_content(base)
                page.locator('span').evaluate('(e,s)=>e.style.cssText=s', style)
                self.assertTrue(page.locator('figure').evaluate(m.AUDIT)[key], key)
            page.set_content(base.replace('</figure>', '<button>Click</button></figure>'))
            self.assertTrue(page.locator('figure').evaluate(m.AUDIT)['interaction'])
            page.set_content(base.replace('</figure>', '<img src="data:image/png;base64,broken"></figure>'))
            page.wait_for_load_state('load')
            self.assertTrue(page.locator('figure').evaluate(m.AUDIT)['broken'])
            browser.close()

    def test_real_export(self):
        import subprocess, sys, json, struct
        import tempfile
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        site = pathlib.Path(temp.name)/'site'; site.mkdir()
        # Synthetic test page only, not a production diagram source.
        (site/'index.html').write_text('<html><meta charset="utf-8"><style>body{margin:16px}.content{max-width:100%}figure{margin:0;font-size:16px}</style><article class="content"><figure class="sd" id="litellm-architecture"><span class="sd-label">Selectable test 한국어</span></figure></article></html>')
        out = pathlib.Path(temp.name) / 'artifacts'
        run = subprocess.run([sys.executable, str(ROOT/'pipeline.py'), '--font-profile', 'local-fallback', '--site', str(site), '--page', 'index.html', '--figure', 'litellm-architecture', '--out', str(out)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        p = out/'litellm-architecture-625-light.png'
        self.assertTrue(p.exists(), 'PNG export missing')
        raw = p.read_bytes(); self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
        width, height = struct.unpack('>II', raw[16:24]); self.assertGreater(width, 0); self.assertGreater(height, 0)
        receipt = json.loads((out/'litellm-architecture-625-light.json').read_text())
        self.assertEqual(receipt['visual_review'], 'not-run')
        self.assertTrue(receipt['inputs'].get('actual_system_font_binaries'), 'actual local font-to-binary mapping missing')
        self.assertEqual(receipt['png_dimensions'], [width, height])
        self.assertIn('download', (out/'litellm-architecture-download.html').read_text())
        check = subprocess.run([sys.executable, str(ROOT/'pipeline.py'), '--font-profile', 'local-fallback', '--site', str(site), '--page', 'index.html', '--figure', 'litellm-architecture', '--out', str(out), '--check'], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        mobile = out/'litellm-architecture-360-light.png'
        mobile.write_bytes(b'corrupted')
        bad = subprocess.run([sys.executable, str(ROOT/'pipeline.py'), '--font-profile', 'local-fallback', '--site', str(site), '--page', 'index.html', '--figure', 'litellm-architecture', '--out', str(out), '--check'], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0, 'modified mobile PNG must be stale')
        from functools import partial
        from http.server import ThreadingHTTPServer
        import threading
        import pipeline as m
        from playwright.sync_api import sync_playwright
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(m.QuietHandler,directory=str(out)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        origin=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True)
                page=browser.new_page()
                page.goto(origin+'/litellm-architecture-download.html')
                self.assertEqual(page.locator('figure').count(),0)
                with page.expect_download() as event: page.locator('a[download]').click()
                self.assertEqual(event.value.suggested_filename,p.name)
                page.locator('a:not([download])').click()
                self.assertTrue(page.url.endswith('.png'))
                dims=page.locator('img').evaluate('i=>[i.naturalWidth,i.naturalHeight]')
                self.assertEqual(dims,[width,height])
                browser.close()
        finally: server.shutdown(); server.server_close()

if __name__ == '__main__': unittest.main()
