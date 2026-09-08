"""Built CSS connector paint tests, native mobile and exact content desktop.

Set DIAGRAM_SITE to a fresh production build. No connector CSS is injected.
CDP border sides, rather than empty corners of L-shaped boxes, define paint.
"""
import json
import os
import threading
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright
from pipeline import await_assets, deterministic_css, load_bundle
from test_connector_regression import QuietHandler, ROOT


def bounds(q):
    return dict(x=min(q[::2]), y=min(q[1::2]),
                w=max(q[::2])-min(q[::2]), h=max(q[1::2])-min(q[1::2]))


def painted_pseudos(cdp, selector, styles):
    root = cdp.send('DOM.getDocument')['root']['nodeId']
    node = cdp.send('DOM.querySelector', dict(nodeId=root, selector=selector))['nodeId']
    desc = cdp.send('DOM.describeNode', dict(nodeId=node, depth=1))['node']
    painted = []
    for pseudo in desc.get('pseudoElements', []):
        st = styles[pseudo['pseudoType']]
        if st['display'] == 'none':
            continue
        model = cdp.send('DOM.getBoxModel', dict(backendNodeId=pseudo['backendNodeId']))['model']
        q, inner = model['border'], model['padding']
        if st['background'] != 'rgba(0, 0, 0, 0)':
            painted.append(bounds(q))
        for side, width in enumerate(st['borders']):
            if width:
                a, b = side*2, ((side+1) % 4)*2
                painted.append(bounds(q[a:a+2]+q[b:b+2]+inner[b:b+2]+inner[a:a+2]))
    return painted


MEASURE = '''f => {
 const box=e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height}};
 const style=s=>({display:s.display,background:s.backgroundColor,borders:['Top','Right','Bottom','Left'].map(k=>s['border'+k+'Style']==='none'?0:parseFloat(s['border'+k+'Width']))});
 const s=getComputedStyle(f),b=box(f);
 return {figure:f.id,width:b.w-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-2,
 elements:[...f.querySelectorAll('.sd-arrow,.sd-v2-link,.sd-v2-down,.sd-v2-rail > .sd-node,.sd-v2-adjunct,.sd-v2-outcome')].map((e,i)=>{
 e.setAttribute('data-corpus-test',i);
 return {index:i,cls:e.className,parent:e.parentElement.className,box:box(e),
 prev:e.previousElementSibling?box(e.previousElementSibling):null,next:e.nextElementSibling?box(e.nextElementSibling):null,
 margin:getComputedStyle(e).marginTop,labelGap:getComputedStyle(e).gap,
 conditionText:[...e.querySelectorAll('.sd-v2-condition')].flatMap(c=>{const r=document.createRange();r.selectNodeContents(c);return [...r.getClientRects()].map(b=>({x:b.x,y:b.y,w:b.width,h:b.height}));}),
 before:style(getComputedStyle(e,'::before')),after:style(getComputedStyle(e,'::after'))};})};}'''


def corridor_fixture():
    edge = '<div class="sd-node">Source</div><div class="sd-arrow"><span class="sd-edge-label">Request</span></div><div class="sd-node">Target</div>'
    return '<figure class="sd" id="corridors"><figcaption class="sd-title">Corridor controls</figcaption>' + edge + ''.join(
        f'<div class="{cls}">{edge}</div>' for cls in ('sd-lane', 'sd-band', 'sd-flow', 'sd-lane sd-flow', 'sd-band sd-stack')) + '</figure>'


@unittest.skipUnless(os.environ.get('DIAGRAM_SITE'), 'DIAGRAM_SITE requires a production build')
class CorpusConnectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site = Path(os.environ['DIAGRAM_SITE']).resolve()
        bundle = load_bundle(ROOT / 'assets/fonts/static-png/lock.json')
        fonts = load_bundle(ROOT / 'assets/fonts/deterministic-export/lock.json')
        bundle.update(fonts)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(site)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        cls.samples = []
        cases = [('valut-vso-in-k8s-8w', 'vault-secrets-operator'),
                 ('litellm-gateway', 'litellm-architecture'),
                 ('litellm-gateway', 'litellm-virtual-key-flow'),
                 ('envoy-ai-gateway', 'envoy-ai-gateway-crd-flow'),
                 ('envoy-ai-gateway', 'gateway-plane-compare'),
                 ('llm-gateway', 'llm-gateway-position'),
                 (None, 'corridors')]
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                for post, fid in cases:
                    for width in (360, 390, 625, 720):
                        for theme in ('light', 'dark'):
                            page = browser.new_page(viewport={'width': width if width<400 else 1280, 'height': 1000}, device_scale_factor=2)
                            def route(r):
                                u = r.request.url
                                if r.request.resource_type == 'script':
                                    r.abort()
                                elif u.startswith(base):
                                    r.continue_()
                                elif u in bundle:
                                    r.fulfill(body=bundle[u]['body'], content_type=bundle[u]['content_type'])
                                else:
                                    r.abort()
                            page.route('**/*', route)
                            page.goto(base + '/posts/' + (post or 'litellm-gateway') + '/index.html', wait_until='load')
                            if not post:
                                page.locator('article .content').evaluate('(e,h)=>e.innerHTML=h', corridor_fixture())
                            page.add_style_tag(content=deterministic_css(fonts))
                            page.evaluate('t=>document.documentElement.setAttribute("data-mode",t)', theme)
                            f = page.locator('#'+fid)
                            if width>=400:
                                f.evaluate('(f,w)=>{const s=getComputedStyle(f);f.style.width=(w+parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+2)+"px";f.style.maxWidth="none"}', width)
                            await_assets(f)
                            sample = f.evaluate(MEASURE)
                            sample.update(requested_width=width, theme=theme, article=bool(post))
                            cdp = page.context.new_cdp_session(page)
                            for e in sample['elements']:
                                e['paint'] = painted_pseudos(cdp, '#'+fid+f' [data-corpus-test="{e["index"]}"]', e)
                            cls.samples.append(sample)
                            if os.environ.get('DIAGRAM_CORPUS_SHOTS'):
                                shots = Path(os.environ['DIAGRAM_CORPUS_SHOTS']); shots.mkdir(parents=True, exist_ok=True)
                                f.screenshot(path=str(shots/f'{fid}-{width}-{theme}.png'))
                            page.close()
                browser.close()
        finally:
            server.shutdown(); server.server_close()
        if os.environ.get('DIAGRAM_CORPUS_RESULTS'):
            Path(os.environ['DIAGRAM_CORPUS_RESULTS']).write_text(json.dumps(cls.samples, indent=2))

    def test_gapless_nested_labelled_arrows_clear_targets(self):
        tested = 0
        for s in self.samples:
            for e in s['elements']:
                if e['cls'] != 'sd-arrow' or not e['prev'] or not e['next']:
                    continue
                tested += 1
                with self.subTest(figure=s['figure'], width=s['requested_width'], theme=s['theme'], index=e['index']):
                    bottom = max(b['y']+b['h'] for b in e['paint'])
                    self.assertGreaterEqual(e['next']['y']-bottom, 6)
                    self.assertEqual(e['labelGap'], '3.2px', 'own-label gap must remain unchanged')
                    if 'sd-flow' in e['parent'] or 'sd-stack' in e['parent']:
                        self.assertEqual(e['margin'], '0px', 'already spaced flows are negative controls')
                    if e['parent'] == 'sd':
                        self.assertEqual(e['margin'], '12px', 'direct connector spacing is retained')
        self.assertGreater(tested, 0)

    def test_v2_links_centered_with_card_clearance(self):
        tested = 0
        for s in self.samples:
            for e in s['elements']:
                if e['cls'] != 'sd-v2-link' or 'issuance' in e['parent']:
                    continue
                tested += 1
                with self.subTest(figure=s['figure'], width=s['requested_width'], theme=s['theme'], index=e['index']):
                    axis, size = ('y', 'h') if s['width'] < 540 else ('x', 'w')
                    paint = e['paint'] + [e['box']]
                    low = min(b[axis] for b in paint)
                    high = max(b[axis]+b[size] for b in paint)
                    before = low-e['prev'][axis]-e['prev'][size]
                    after = e['next'][axis]-high
                    self.assertGreaterEqual(before, 6)
                    self.assertGreaterEqual(after, 6)
                    self.assertAlmostEqual(before, after, delta=0.05)
        self.assertGreater(tested, 0)

    def test_v2_down_card_clearance(self):
        tested = 0
        for s in self.samples:
            for e in s['elements']:
                if e['cls'] != 'sd-v2-down':
                    continue
                tested += 1
                with self.subTest(figure=s['figure'], width=s['requested_width'], theme=s['theme'], index=e['index']):
                    paint = e['paint'] + [e['box']]
                    before = min(b['y'] for b in paint)-e['prev']['y']-e['prev']['h']
                    after = e['next']['y']-max(b['y']+b['h'] for b in paint)
                    self.assertGreaterEqual(before, 8)
                    self.assertGreaterEqual(after, 8)
                    self.assertAlmostEqual(before, after, delta=0.05)
        self.assertGreater(tested, 0)

    def test_attached_bus_border_strips_join(self):
        tested = 0
        for s in self.samples:
            if s['width'] >= 540 or s['figure'] not in ('litellm-architecture', 'envoy-ai-gateway-crd-flow'):
                continue
            chain = [e for e in s['elements'] if e['paint'] and (e['parent']=='sd-v2-rail' and 'sd-node' in e['cls'] or e['cls']=='sd-v2-adjunct')]
            self.assertEqual(len(chain), 3)
            for a, b in zip(chain, chain[1:]):
                tested += 1
                with self.subTest(figure=s['figure'], width=s['requested_width'], theme=s['theme'], index=a['index']):
                    av = next(p for p in a['paint'] if p['w']<=2.01 and p['h']>p['w'])
                    bv = next(p for p in b['paint'] if p['w']<=2.01 and p['h']>p['w'])
                    self.assertAlmostEqual(av['x']+av['w']/2, bv['x']+bv['w']/2, delta=0.05)
                    self.assertAlmostEqual(av['y']+av['h'], bv['y'], delta=0.05)
        self.assertEqual(tested, 16)

    def test_branch_stroke_clear_of_condition_text(self):
        tested = 0
        for s in self.samples:
            for e in s['elements']:
                if not e['conditionText']:
                    continue
                tested += 1
                with self.subTest(figure=s['figure'], width=s['requested_width'], theme=s['theme'], index=e['index']):
                    distance = min((max(b['x']-t['x']-t['w'], t['x']-b['x']-b['w'], 0)**2 +
                                    max(b['y']-t['y']-t['h'], t['y']-b['y']-b['h'], 0)**2)**0.5
                                   for b in e['paint'] for t in e['conditionText'])
                    self.assertGreaterEqual(distance, 4)
        self.assertEqual(tested, 16)

    def test_case_matrix_and_content_widths(self):
        self.assertEqual(len(self.samples), 56)
        for s in self.samples:
            if s['requested_width']>=400:
                self.assertEqual(s['width'], s['requested_width'])


if __name__ == '__main__':
    unittest.main()
