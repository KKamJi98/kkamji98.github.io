"""Role-scoped connector paint contracts on fresh built articles, not injected CSS.

DIAGRAM_SITE is required. Optional DIAGRAM_ROLES_RESULTS and DIAGRAM_ROLES_SHOTS
retain measurements and loop crops. Unused includes use an explicit harness.
"""
import json
import math
import os
import threading
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright
from pipeline import await_assets, deterministic_css, load_bundle, rendered_fonts, font_policy
from test_connector_regression import QuietHandler, ROOT
from test_connector_semantics import CONTRACTS, Source


JS = r'''f=>{
 const box=e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height}};
 const pseudo=(e,p)=>{const s=getComputedStyle(e,p);return {display:s.display,content:s.content,radius:parseFloat(s.borderTopLeftRadius),borders:['Top','Right','Bottom','Left'].map(k=>s['border'+k+'Style']==='none'?0:parseFloat(s['border'+k+'Width']))}};
 const fs=getComputedStyle(f);
 return {width:box(f).w-parseFloat(fs.paddingLeft)-parseFloat(fs.paddingRight)-2,
 overflow:f.scrollWidth>f.clientWidth+1,
 small:[...f.querySelectorAll('.sd-label,.sd-detail,.sd-edge-label')].filter(e=>parseFloat(getComputedStyle(e).fontSize)<(e.matches('.sd-label')?16:14)).length,
 controls:[...f.querySelectorAll('.sd-arrow:not([data-connector-role])')].map(e=>({parent:e.parentElement.className,margin:getComputedStyle(e).marginTop,gap:getComputedStyle(e).gap})),
 edges:[...f.querySelectorAll('[data-connector-role]')].map((e,i)=>{
 e.dataset.rolesTest=i;const role=e.dataset.connectorRole;
 const target=role==='continuation'?e.parentElement.nextElementSibling:e.nextElementSibling;
 return {i,role,box:box(e),parent:box(e.parentElement),next:target?box(target):null,
 from:e.dataset.from,to:e.dataset.to,endpointIds:['from','to'].map(k=>e.dataset[k]?f.querySelectorAll('[id="'+e.dataset[k]+'"]').length:null),
 first:e.querySelector('.sd-node')?box(e.querySelector('.sd-node')):null,
 last:e.querySelector('.sd-node')?box([...e.querySelectorAll('.sd-node')].at(-1)):null,
 margin:getComputedStyle(e.parentElement).marginBottom,arrowMargin:getComputedStyle(e).marginBottom,
 gutter:parseFloat(getComputedStyle(e).paddingLeft),noteBorder:getComputedStyle(e).borderTopStyle,
 sideBorders:['Left','Right','Bottom'].map(k=>parseFloat(getComputedStyle(e)['border'+k+'Width'])),
 before:pseudo(e,'::before'),after:pseudo(e,'::after')};})};}'''


def models(cdp, selector, edge):
    root = cdp.send('DOM.getDocument')['root']['nodeId']
    node = cdp.send('DOM.querySelector', dict(nodeId=root, selector=selector))['nodeId']
    desc = cdp.send('DOM.describeNode', dict(nodeId=node, depth=1))['node']
    out = {}
    for p in desc.get('pseudoElements', []):
        name = p['pseudoType']
        if edge[name]['display'] == 'none':
            continue
        m = cdp.send('DOM.getBoxModel', dict(backendNodeId=p['backendNodeId']))['model']
        q, inner = m['border'], m['padding']
        strips = []
        for side, width in enumerate(edge[name]['borders']):
            if width:
                a, b = side*2, ((side+1)%4)*2
                strips.append(q[a:a+2]+q[b:b+2]+inner[b:b+2]+inner[a:a+2])
        out[name] = dict(quad=q, strips=strips)
    return out


@unittest.skipUnless(os.environ.get('DIAGRAM_SITE'), 'requires fresh production DIAGRAM_SITE')
class ConnectorRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site = Path(os.environ['DIAGRAM_SITE']).resolve()
        bundle = load_bundle(ROOT/'assets/fonts/static-png/lock.json')
        fonts = load_bundle(ROOT/'assets/fonts/deterministic-export/lock.json')
        bundle.update(fonts)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(site)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        pages = [(p, p.read_text()) for p in (site/'posts').glob('*/index.html')]
        cls.samples = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                for include in sorted({c['include'] for c in CONTRACTS}):
                    source = (ROOT/'_includes'/include).read_text()
                    fig = next(n for n in Source(source).nodes if n.tag == 'figure')
                    fid = fig.attrs.get('id') or fig.attrs['aria-labelledby']
                    selector = 'figure.sd#'+fid if fig.attrs.get('id') else 'figure.sd[aria-labelledby="'+fid+'"]'
                    article = next((p for p,t in pages if '"'+fid+'"' in t), None)
                    for width in (360, 390, 625, 720):
                        for theme in ('light','dark'):
                            page = browser.new_page(viewport={'width':width if width<400 else 1280,'height':1000},device_scale_factor=2,locale='ko-KR',timezone_id='UTC')
                            def route(r):
                                u = r.request.url
                                if r.request.resource_type == 'script': r.abort()
                                elif u.startswith(base): r.continue_()
                                elif u in bundle: r.fulfill(body=bundle[u]['body'],content_type=bundle[u]['content_type'])
                                else: r.abort()
                            page.route('**/*',route)
                            page.goto(base+'/'+str(article.relative_to(site) if article else 'posts/litellm-gateway/index.html'),wait_until='load')
                            if not article:
                                page.locator('article .content').evaluate('(e,h)=>e.innerHTML=h',source)
                            page.add_style_tag(content=deterministic_css(fonts))
                            page.evaluate('t=>document.documentElement.setAttribute("data-mode",t)',theme)
                            f=page.locator(selector)
                            if width>=400:
                                f.evaluate('(f,w)=>{const s=getComputedStyle(f);f.style.width=(w+parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+2)+"px";f.style.maxWidth="none"}',width)
                            await_assets(f)
                            font_policy('deterministic-export',rendered_fonts(page,selector),[])
                            s=f.evaluate(JS)
                            s.update(include=include,width_requested=width,theme=theme,article=bool(article))
                            cdp=page.context.new_cdp_session(page)
                            for e in s['edges']:
                                e['paint']=models(cdp,selector+f' [data-roles-test="{e["i"]}"]',e)
                            cls.samples.append(s)
                            if os.environ.get('DIAGRAM_ROLES_SHOTS') and any(e['role']=='loop' for e in s['edges']):
                                out=Path(os.environ['DIAGRAM_ROLES_SHOTS']);out.mkdir(parents=True,exist_ok=True)
                                f.screenshot(path=str(out/f'{fid}-{width}-{theme}.png'))
                                loop=f.locator('.sd-loop');loop.scroll_into_view_if_needed();b=loop.bounding_box()
                                assert b is not None
                                page.screenshot(path=str(out/f'{fid}-{width}-{theme}-detail.png'),clip={'x':b['x'],'y':b['y'],'width':64,'height':min(b['height'],100)})
                                page.screenshot(path=str(out/f'{fid}-{width}-{theme}-source.png'),clip={'x':b['x'],'y':b['y']+b['height']-40,'width':64,'height':40})
                            page.close()
                browser.close()
        finally:
            server.shutdown();server.server_close()
        if os.environ.get('DIAGRAM_ROLES_RESULTS'):
            Path(os.environ['DIAGRAM_ROLES_RESULTS']).write_text(json.dumps(cls.samples,indent=2))

    def edges(self, role):
        for s in self.samples:
            for e in s['edges']:
                if e['role']==role:
                    yield s,e

    def test_continuation_local_corridor(self):
        self.assertEqual(sum(1 for _ in self.edges('continuation')),192)
        for s,e in self.edges('continuation'):
            with self.subTest(include=s['include'],width=s['width_requested'],theme=s['theme']):
                self.assertGreaterEqual(float(e['margin'][:-2]),8)
                bottom=max(max(p[1::2]) for m in e['paint'].values() for p in m['strips'])
                self.assertGreaterEqual(e['next']['y']-bottom,4)

    def test_reference_corridors(self):
        self.assertEqual(sum(1 for _ in self.edges('reference')),72)
        for s,e in self.edges('reference'):
            with self.subTest(include=s['include'],width=s['width_requested'],theme=s['theme'],edge=e['i']):
                bottom=max(max(p[1::2]) for m in e['paint'].values() for p in m['strips'])
                self.assertGreaterEqual(e['next']['y']-bottom,4)
                if 'vault-secrets-operator' in s['include']:
                    self.assertGreaterEqual(float(e['arrowMargin'][:-2]),8)

    def test_loop_painted_tip_source_and_join(self):
        self.assertEqual(sum(1 for _ in self.edges('loop')),24)
        for s,e in self.edges('loop'):
            with self.subTest(include=s['include'],width=s['width_requested'],theme=s['theme']):
                rail=e['paint']['before']['quad'];head=e['paint']['after']['quad']
                tip=max(zip(head[::2],head[1::2]))
                self.assertAlmostEqual(tip[0],e['first']['x'],delta=.5)
                self.assertAlmostEqual(max(rail[::2]),e['last']['x'],delta=.5)
                self.assertAlmostEqual(tip[1],min(rail[1::2])+1,delta=.5)
                self.assertEqual(e['gutter'],16 if s['width']<=680 else 20)
                self.assertGreater(e['before']['radius'],0)
                # Only the straight top painted strip is needed to prove contact.
                # Right corners have zero radius; left radii share vertical space.
                radius=min(e['before']['radius'],max(rail[::2])-min(rail[::2]),
                           (max(rail[1::2])-min(rail[1::2]))/2)
                left=min(rail[::2])+radius;right=max(rail[::2]);top=min(rail[1::2])
                distance=min(math.hypot(max(left-x,x-right,0),max(top-y,y-top-2,0))
                             for p in e['paint']['after']['strips'] for x,y in zip(p[::2],p[1::2]))
                self.assertLessEqual(distance,.5,'head paint must touch straight top rail, not empty L bbox')

    def test_reference_notes_have_no_heads(self):
        self.assertEqual(sum(1 for _ in self.edges('reference-note')),16)
        for _,e in self.edges('reference-note'):
            self.assertFalse(e['paint'])
            self.assertEqual(e['noteBorder'],'dashed')
            self.assertEqual(e['sideBorders'],[0,0,0])

    def test_endpoints_controls_fonts_and_width(self):
        self.assertEqual(len(self.samples),240)
        for s in self.samples:
            with self.subTest(include=s['include'],width=s['width_requested'],theme=s['theme']):
                self.assertFalse(s['overflow']);self.assertEqual(s['small'],0)
                if s['width_requested']>=400:self.assertEqual(s['width'],s['width_requested'])
                for e in s['edges']:
                    if e['role']!='continuation':self.assertEqual(e['endpointIds'],[1,1])
                for c in s['controls']:
                    if c['parent']=='sd-flow':self.assertEqual(c['margin'],'0px')
                    if c['parent']=='sd':self.assertEqual(c['margin'],'12px')


if __name__=='__main__':
    unittest.main()
