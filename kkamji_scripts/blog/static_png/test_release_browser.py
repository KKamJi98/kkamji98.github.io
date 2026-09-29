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
        dimensions = {}
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
                                    page.locator('.content').first.evaluate('''(e,w)=>{
                                      e.style.width=w+'px';e.style.maxWidth=w+'px';}''', width)
                                inline = figure.locator('xpath=following-sibling::*[1]').locator('img.diagram-inline')
                                inline.evaluate('i=>{i.loading="eager"}')
                                inline.scroll_into_view_if_needed()
                                page.wait_for_function('''src => {
                                  const i=document.querySelector(`img.diagram-inline[src="${src}"]`);
                                  return i && i.complete && i.naturalWidth > 0;
                                }''', arg=inline.get_attribute('src'), timeout=30000)
                                inline.evaluate('i=>i.decode()')
                                presentation = figure.evaluate('''e=>{
                                  const p=e.nextElementSibling,i=p.querySelector('img.diagram-inline');
                                  const r=i.getBoundingClientRect(),s=getComputedStyle(e);
                                  return {label:e.getAttribute('aria-labelledby'),
                                    text:e.textContent.trim(),hidden:e.hasAttribute('aria-hidden'),
                                    position:s.position,clip:s.clipPath,
                                    alt:i.getAttribute('alt'),marker:i.getAttribute('data-static-diagram'),
                                    src:i.getAttribute('src'),links:[...p.querySelectorAll('a')].map(a=>a.getAttribute('href')),
                                    complete:i.complete,natural:[i.naturalWidth,i.naturalHeight],
                                    size:[r.width,r.height],overflow:i.scrollWidth-i.clientWidth};}''')
                                self.assertEqual(presentation['label'], name + '-title')
                                self.assertTrue(presentation['text'])
                                self.assertFalse(presentation['hidden'])
                                self.assertEqual(presentation['position'], 'absolute')
                                self.assertNotEqual(presentation['clip'], 'none')
                                self.assertEqual(presentation['alt'], '')
                                self.assertEqual(presentation['marker'], 'true')
                                self.assertEqual(presentation['links'], [presentation['src']] * 2)
                                self.assertTrue(presentation['complete'])
                                self.assertEqual(presentation['natural'][0], 1920)
                                self.assertGreater(presentation['natural'][1], 0)
                                self.assertEqual(presentation['overflow'], 0)
                                if name in dimensions:
                                    self.assertEqual(presentation['natural'], dimensions[name])
                                dimensions[name] = presentation['natural']
                                self.assertAlmostEqual(presentation['size'][1] / presentation['size'][0],
                                  presentation['natural'][1] / presentation['natural'][0], delta=0.01)
                                if width == 360:
                                    self.assertLessEqual(presentation['size'][0], 360)
                                # QA the same source in the disposable browser page, not the clipped view.
                                figure.evaluate('''e=>{
                                  e.style.setProperty('position','static','important');
                                  e.style.setProperty('width','100%','important');
                                  e.style.setProperty('height','auto','important');
                                  e.style.setProperty('overflow','visible','important');
                                  e.style.setProperty('clip-path','none','important');
                                  e.nextElementSibling.style.setProperty('display','none','important');}''')
                                if width >= 400:
                                    figure.evaluate('''(e,w)=>{const s=getComputedStyle(e);
                                      e.style.setProperty('width',(w+parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)
                                        +parseFloat(s.borderLeftWidth)+parseFloat(s.borderRightWidth))+'px','important');
                                      e.style.maxWidth='none';}''', width)
                                metrics = figure.evaluate(AUDIT)
                                self.assertTrue(gate(metrics), metrics)
                                details = figure.evaluate('''e=>({
                                  overflow:e.scrollWidth-e.clientWidth,
                                  titleHidden:(()=>{const t=e.querySelector('.sd-title');return t&&getComputedStyle(t).clipPath==='inset(50%)'&&getComputedStyle(t).position==='absolute'&&t.id===e.getAttribute('aria-labelledby')&&!!t.textContent.trim()})(),
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
                                self.assertTrue(details['titleHidden'])
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
