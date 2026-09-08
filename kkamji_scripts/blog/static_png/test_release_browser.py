"""Fresh production article regression. DIAGRAM_SITE must point to a final build.
Runs offline with the repository's exact-URL font snapshot; system Hangul fallback
is allowed here, so these DOM checks are not production font-parity approval.
"""
import json
import os
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright
from pipeline import AUDIT, gate, load_bundle

ROOT = Path(__file__).resolve().parents[3]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class ReleaseBrowserTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DIAGRAM_SITE'), 'DIAGRAM_SITE must point to a fresh production build')
    def test_built_articles_at_mobile_and_body_widths(self):
        site = Path(os.environ['DIAGRAM_SITE'])
        bundle = load_bundle(ROOT / 'assets/fonts/static-png/lock.json')
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(site)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        names = ['litellm-architecture', 'litellm-virtual-key-flow', 'llm-gateway-position',
                 'gateway-plane-compare', 'envoy-ai-gateway-crd-flow', 'vault-secrets-operator',
                 'sap-c02-deployment-rollback-paths']
        pages = {}
        for path in (site / 'posts').glob('*/index.html'):
            text = path.read_text()
            for name in names:
                if f'id="{name}-title"' in text:
                    pages[name] = str(path.relative_to(site))
        self.assertEqual(set(pages), set(names))
        results = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                for theme in ['light', 'dark']:
                    for width in [360, 390, 625, 720]:
                        page = browser.new_page(viewport={'width': width if width < 400 else 1280, 'height': 1000})
                        def route(request):
                            url = request.request.url
                            if url.startswith(base):
                                request.continue_()
                            elif url in bundle:
                                row = bundle[url]
                                request.fulfill(body=row['body'], content_type=row['content_type'])
                            else:
                                request.abort()
                        page.route('**/*', route)
                        for name in names:
                            with self.subTest(theme=theme, width=width, figure=name):
                                page.goto(base + '/' + pages[name], wait_until='networkidle')
                                page.evaluate('(t)=>document.documentElement.setAttribute("data-mode",t)', theme)
                                page.evaluate('document.fonts.ready')
                                figure = page.locator(f'figure[aria-labelledby="{name}-title"]')
                                if width >= 400:
                                    figure.evaluate('''(e,w)=>{const s=getComputedStyle(e);
                                      e.style.width=(w+parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)
                                        +parseFloat(s.borderLeftWidth)+parseFloat(s.borderRightWidth))+'px';
                                      e.style.maxWidth='none';}''', width)
                                metrics = figure.evaluate(AUDIT)
                                self.assertTrue(gate(metrics), metrics)
                                details = figure.evaluate('''e=>({
                                  overflow:e.scrollWidth-e.clientWidth,
                                  title:parseFloat(getComputedStyle(e.querySelector('.sd-title')).fontSize),
                                  labels:[...e.querySelectorAll('.sd-label')].map(n=>parseFloat(getComputedStyle(n).fontSize)),
                                  details:[...e.querySelectorAll('.sd-detail,.sd-edge-label,.sd-note,.sd-v2-condition')].map(n=>parseFloat(getComputedStyle(n).fontSize)),
                                  interactive:e.querySelectorAll('button,a,input,script,[onclick]').length,
                                  anchors:[...e.querySelectorAll('.sd-v2-rail:has(+ .sd-v2-adjunct)')].map(r=>{
                                    const p=r.querySelector('.sd-node--accent'),b=p.getBoundingClientRect();
                                    const a=r.nextElementSibling.querySelector('.sd-v2-relation').getBoundingClientRect();
                                    const mobile=getComputedStyle(r).gridTemplateColumns.split(' ').length===1;
                                    const ps=getComputedStyle(p,'::before');
                                    return {mobile,gap:mobile?parseFloat(ps.right)-p.clientWidth:a.top-b.bottom};
                                  })})''')
                                self.assertEqual(details['overflow'], 0)
                                self.assertEqual(details['interactive'], 0)
                                self.assertGreaterEqual(details['title'], 22)
                                self.assertTrue(all(n >= 16 for n in details['labels']))
                                self.assertTrue(all(n >= 14 for n in details['details']))
                                for anchor in details['anchors']:
                                    self.assertAlmostEqual(anchor['gap'], 0, delta=1, msg=str(anchor))
                                results.append(dict(name=name, theme=theme, width=width, **details))
                        page.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            if os.environ.get('DIAGRAM_BROWSER_RESULTS'):
                Path(os.environ['DIAGRAM_BROWSER_RESULTS']).write_text(json.dumps(results, indent=2))
        self.assertEqual(len(results), 56)


if __name__ == '__main__':
    unittest.main()
