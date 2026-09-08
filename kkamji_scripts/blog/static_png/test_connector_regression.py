"""Real built-article connector regression; no source CSS injection.

DIAGRAM_SITE selects the immutable baseline or a fresh production build.
Native mobile viewports retain article gutters; desktop sizes are exact outer
figure widths, not content widths. Geometry is not visual approval.
"""
import json
import os
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright
from pipeline import (AUDIT, await_assets, deterministic_css, font_policy, gate,
                      load_bundle, rendered_fonts)

ROOT = Path(__file__).resolve().parents[3]
SELECTOR = '#litellm-virtual-key-flow'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def pseudo_box(cdp, root, selector, pseudo):
    node = cdp.send('DOM.querySelector', {'nodeId': root, 'selector': selector})['nodeId']
    description = cdp.send('DOM.describeNode', {'nodeId': node, 'depth': 1})['node']
    target = next(p for p in description.get('pseudoElements', []) if p['pseudoType'] == pseudo)
    quad = cdp.send('DOM.getBoxModel', {'backendNodeId': target['backendNodeId']})['model']['border']
    return dict(left=min(quad[::2]), right=max(quad[::2]),
                top=min(quad[1::2]), bottom=max(quad[1::2]), quad=quad)


@unittest.skipUnless(os.environ.get('DIAGRAM_SITE'), 'DIAGRAM_SITE requires a production build')
class ConnectorRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site = Path(os.environ['DIAGRAM_SITE']).resolve()
        bundle = load_bundle(ROOT / 'assets/fonts/static-png/lock.json')
        export = load_bundle(ROOT / 'assets/fonts/deterministic-export/lock.json')
        bundle.update(export)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(site)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        cls.samples = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                for theme in ('light', 'dark'):
                    for width in (360, 390, 625, 720):
                        page = browser.new_page(viewport={'width': width if width < 400 else 1280, 'height': 1000}, device_scale_factor=2)
                        def route(r):
                            url = r.request.url
                            if r.request.resource_type == 'script':
                                r.abort()
                            elif url.startswith(base):
                                r.continue_()
                            elif url in bundle:
                                row = bundle[url]
                                r.fulfill(body=row['body'], content_type=row['content_type'])
                            else:
                                r.abort()
                        page.route('**/*', route)
                        page.goto(base + '/posts/litellm-gateway/index.html', wait_until='load')
                        page.evaluate('(t)=>document.documentElement.setAttribute("data-mode",t)', theme)
                        page.add_style_tag(content=deterministic_css(export))
                        figure = page.locator(SELECTOR)
                        if width >= 400:
                            figure.evaluate('(e,w)=>{e.style.width=w+"px";e.style.maxWidth="none"}', width)
                        await_assets(figure)
                        fonts = rendered_fonts(page, SELECTOR)
                        font_policy('deterministic-export', fonts, [])
                        sample = figure.evaluate('''f => {
                          const box=e=>{const r=e.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width}};
                          const texts=e=>{const out=[],w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);while(w.nextNode()){if(!w.currentNode.textContent.trim())continue;const r=document.createRange();r.selectNodeContents(w.currentNode);out.push(...[...r.getClientRects()].map(r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom})));}return out;};
                          return {figure:box(f), mobile:getComputedStyle(f.querySelector('.sd-v2-issuance-row')).gridTemplateColumns.split(' ').length===1,
                            issuance:[...f.querySelectorAll('.sd-v2-issuance-row .sd-v2-link')].map(e=>({shaft:box(e),previous:box(e.previousElementSibling),next:box(e.nextElementSibling),previousText:texts(e.previousElementSibling),nextText:texts(e.nextElementSibling)})),
                            fork:box(f.querySelector('.sd-v2-fork')),
                            source:box(f.querySelector('.sd-v2-request-row .sd-node--accent')),
                            outcomes:[...f.querySelectorAll('.sd-v2-outcome')].map(box),
                            down:[...f.querySelectorAll('.sd-v2-down')].map(e=>({shaft:box(e),previous:box(e.previousElementSibling),next:box(e.nextElementSibling)}))};
                        }''')
                        sample.update(theme=theme, width=width, audit=figure.evaluate(AUDIT), fonts=fonts)
                        cdp = page.context.new_cdp_session(page)
                        cdp.send('DOM.enable')
                        root = cdp.send('DOM.getDocument')['root']['nodeId']
                        for i, link in enumerate(sample['issuance']):
                            link['head'] = pseudo_box(cdp, root, SELECTOR + f' .sd-v2-issuance-row .sd-v2-link:nth-child({2+i*2})', 'after')
                        for down in sample['down']:
                            down['head'] = pseudo_box(cdp, root, SELECTOR + ' .sd-v2-down', 'after')
                        if not sample['mobile']:
                            sample['bar'] = pseudo_box(cdp, root, SELECTOR + ' .sd-v2-fork', 'before')
                            sample['trunk'] = pseudo_box(cdp, root, SELECTOR + ' .sd-v2-fork', 'after')
                            sample['branches'] = [pseudo_box(cdp, root, SELECTOR + f' .sd-v2-outcome:nth-child({i})', 'before') for i in (1, 2)]
                        cdp.detach()
                        if os.environ.get('DIAGRAM_CONNECTOR_SHOTS'):
                            shots = Path(os.environ['DIAGRAM_CONNECTOR_SHOTS'])
                            shots.mkdir(parents=True, exist_ok=True)
                            figure.screenshot(path=str(shots / f'{theme}-{width}.png'), animations='disabled')
                        cls.samples.append(sample)
                        page.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
        if os.environ.get('DIAGRAM_CONNECTOR_RESULTS'):
            Path(os.environ['DIAGRAM_CONNECTOR_RESULTS']).write_text(json.dumps(cls.samples, indent=2))

    def test_issuance_paint_centered_with_text_clearance(self):
        for sample in self.samples:
            for link in sample['issuance']:
                with self.subTest(theme=sample['theme'], width=sample['width'], link=link):
                    start, end = ('top', 'bottom') if sample['mobile'] else ('left', 'right')
                    low = min(link['shaft'][start], link['head'][start])
                    high = max(link['shaft'][end], link['head'][end])
                    before = low - link['previous'][end]
                    after = link['next'][start] - high
                    self.assertGreaterEqual(before, 6, 'paint crowds preceding issuance label')
                    self.assertGreaterEqual(after, 6, 'paint crowds following issuance label')
                    self.assertAlmostEqual(before, after, delta=0.75, msg='paint not centered in reserved gap')
                    self.assertGreaterEqual(low - max(t[end] for t in link['previousText']), 6)
                    self.assertGreaterEqual(min(t[start] for t in link['nextText']) - high, 6)


    def test_issuance_centered_between_actual_text_extents(self):
        for s in self.samples:
            for link in s['issuance']:
                with self.subTest(theme=s['theme'], width=s['width']):
                    start, end = ('top', 'bottom') if s['mobile'] else ('left', 'right')
                    low = min(link['shaft'][start], link['head'][start])
                    high = max(link['shaft'][end], link['head'][end])
                    before = low - max(t[end] for t in link['previousText'])
                    after = min(t[start] for t in link['nextText']) - high
                    self.assertAlmostEqual(before, after, delta=1.5,
                                           msg='connector biased toward one text actor')

    def test_downward_paint_has_balanced_card_clearance(self):
        for s in self.samples:
            for down in s['down']:
                with self.subTest(theme=s['theme'], width=s['width']):
                    low = min(down['shaft']['top'], down['head']['top'])
                    high = max(down['shaft']['bottom'], down['head']['bottom'])
                    before = low - down['previous']['bottom']
                    after = down['next']['top'] - high
                    self.assertGreaterEqual(before, 8)
                    self.assertGreaterEqual(after, 8)
                    self.assertAlmostEqual(before, after, delta=0.05)
                    self.assertAlmostEqual((down['head']['left'] + down['head']['right']) / 2,
                                           (down['shaft']['left'] + down['shaft']['right']) / 2, delta=0.05)

    def test_native_width_fonts_and_overflow(self):
        self.assertEqual(len(self.samples), 8)
        for s in self.samples:
            with self.subTest(theme=s['theme'], width=s['width']):
                self.assertTrue(gate(s['audit']), s['audit'])
                if s['width'] >= 400:
                    self.assertEqual(s['figure']['width'], s['width'])
                else:
                    self.assertGreaterEqual(s['figure']['left'], 0)
                    self.assertLessEqual(s['figure']['right'], s['width'])

    def test_fork_centerlines_join_source_and_outcomes(self):
        center = lambda b: (b['left'] + b['right']) / 2
        for s in self.samples:
            if s['mobile']:
                continue  # Mobile intentionally uses a side bus, not a central trunk.
            with self.subTest(theme=s['theme'], width=s['width']):
                self.assertAlmostEqual(center(s['trunk']), center(s['source']), delta=0.05)
                self.assertAlmostEqual(s['trunk']['top'], s['source']['bottom'], delta=0.05)
                self.assertGreaterEqual(s['trunk']['bottom'], (s['bar']['top'] + s['bar']['bottom']) / 2)
                for branch, outcome in zip(s['branches'], s['outcomes']):
                    self.assertAlmostEqual(center(branch), center(outcome), delta=0.05)
                    self.assertLessEqual(branch['top'], s['bar']['bottom'])
                    self.assertLessEqual(s['bar']['left'], branch['left'])
                    self.assertGreaterEqual(s['bar']['right'], branch['right'])
                self.assertAlmostEqual(center(s['trunk']), center(s['branches'][1]), delta=0.05)


if __name__ == '__main__':
    unittest.main()
