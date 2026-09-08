"""Focused LOOP contract tests. No stylesheet or corpus writes."""
import math
import unittest
try:
    from .connector_loop import inspect_loop
except ImportError:
    from connector_loop import inspect_loop


def fixture() -> dict:
    border = lambda w: dict(width=w, style='solid' if w else 'none', color='rgb(0, 0, 0)')
    # Outer BR is the right tip. Local square rotated -45 degrees.
    q = [10, 13, 16, 7, 22, 13, 16, 19]
    iq = [10, 13, 14.5857864376, 8.4142135624, 19.1715728752, 13, 14.5857864376, 17.5857864376]
    return dict(role='loop', cls='sd-loop', box=dict(x=0,y=0,w=122,h=100),
        sourceInside=True,targetInside=True,
        sourceRef=dict(id='last',count=1,cls='sd-node',box=dict(x=22,y=65,w=100,h=35),text=[dict(x=38,y=76,w=30,h=12)]),
        targetRef=dict(id='first',count=1,cls='sd-node',box=dict(x=22,y=0,w=100,h=35),text=[dict(x=38,y=16,w=30,h=12)]),
        before=dict(borders=[border(2),border(0),border(2),border(2)],transform='none',radii=['12px','0px','0px','12px']),
        after=dict(borders=[border(0),border(2),border(2),border(0)],transform='matrix(0.707107, -0.707107, 0.707107, 0.707107, 0, 0)',radii=['0px']*4),
        pseudos=[dict(type='before',quad=[4,12,22,12,22,88,4,88],innerQuad=[6,14,22,14,22,86,6,86],paintPolygons=[]),dict(type='after',quad=q,innerQuad=iq,paintPolygons=[q[2:6]+iq[4:6]+iq[2:4],q[4:8]+iq[6:8]+iq[4:6]])])


class LoopTests(unittest.TestCase):
    def test_endpoint_ambiguity_is_unresolved(self):
        e=fixture();e['sourceRef']['count']=2
        self.assertTrue(inspect_loop(e)['unresolved'])

    def test_contact_contract(self):
        good=inspect_loop(fixture())
        self.assertEqual(good['unresolved'], [])
        self.assertEqual(good['findings'], [])
        self.assertIn('head_rail_gap', good['metrics'])
        e=fixture(); e['targetRef']['box']['x']-=2
        self.assertIn('loop-target-contact', inspect_loop(e)['findings'])
        e=fixture(); e['sourceRef']['box']['x']+=4; e['sourceRef']['box']['w']-=4
        self.assertIn('loop-source-contact', inspect_loop(e)['findings'])

    def test_negative_geometry_and_translation(self):
        e=fixture()
        for p in e['pseudos']:
            for k in ('quad','innerQuad'):
                p[k]=[v+(1000 if i%2==0 else -500) for i,v in enumerate(p[k])]
        for b in [e['box'],e['sourceRef']['box'],e['targetRef']['box']]+e['sourceRef']['text']+e['targetRef']['text']:
            b['x']+=1000;b['y']-=500
        self.assertEqual(inspect_loop(e)['findings'],[])
        self.assertEqual(inspect_loop(e)['unresolved'],[])
        for mode,code in [('offseam','loop-head-rail-alignment'),('rotated','loop-head-orientation'),('text','loop-text-clearance')]:
            e=fixture()
            if mode=='text':e['targetRef']['text']=[dict(x=21,y=12,w=10,h=10)]
            else:
                for k in ('quad','innerQuad'):
                    q=e['pseudos'][1][k]
                    if mode=='offseam':e['pseudos'][1][k]=[v+8 if i%2 else v for i,v in enumerate(q)]
                    else:e['pseudos'][1][k]=[v for x,y in zip(q[::2],q[1::2]) for v in (22-(y-13),13+(x-22))]
            if mode=='rotated':e['after']['transform']='matrix(0.707107, 0.707107, -0.707107, 0.707107, 0, 0)'
            self.assertIn(code,inspect_loop(e)['findings'])

    def test_quarter_annulus_not_filled_corner(self):
        from kkamji_scripts.blog.static_png.connector_loop import _rail, _distance, _rect, ARC_ERROR
        e=fixture();cells,_,_,_=_rail(e['before'],e['pseudos'][0])
        # Outer TL empty corner and inner hole must not become painted hulls.
        for b,minimum in [(dict(x=4,y=12,w=.1,h=.1),4),(dict(x=12,y=20,w=.1,h=.1),4)]:
            self.assertGreater(min(_distance(c,_rect(b)) for c in cells),minimum)
        # A point just outside the 45 degree circular arc: analytic radial gap.
        radius=12.75;x=16-radius/math.sqrt(2);y=24-radius/math.sqrt(2)
        tiny=_rect(dict(x=x-1e-6,y=y-1e-6,w=2e-6,h=2e-6))
        self.assertAlmostEqual(min(_distance(c,tiny) for c in cells),.75,delta=ARC_ERROR+3e-6)

    def test_radius_clamping_and_elliptical_support(self):
        e=fixture();e['before']['radii']=['100% 50%','0px','0px','100% 50%']
        r=inspect_loop(e)
        self.assertFalse(r['unresolved'])
        self.assertEqual(r['metrics']['clamped_radii'],[[18,38],[0,0],[0,0],[18,38]])
        e['before']['radii']=['100px','0px','0px','100px']
        self.assertEqual(inspect_loop(e)['metrics']['clamped_radii'],[[18,18],[0,0],[0,0],[18,18]])

    def test_malformed_head_fails_closed(self):
        for mode in ('radii','inner','transform-quad'):
            e=fixture()
            if mode=='radii':e['after']['radii']=[]
            elif mode=='inner':e['pseudos'][1]['innerQuad']=e['pseudos'][1]['quad'][:]
            else:e['after']['transform']='matrix(1, 0, 0, 1, 0, 0)'
            with self.subTest(mode=mode):self.assertTrue(inspect_loop(e)['unresolved'])

    def test_unsupported_styles(self):
        for mode in ('dash','transform','missing-radius','background','scale'):
            e=fixture()
            if mode=='dash':e['before']['borders'][0]['style']='dashed'
            elif mode=='transform':e['before']['transform']='matrix(2, 0, 0, 2, 0, 0)'
            elif mode=='missing-radius':del e['before']['radii']
            elif mode=='background':e['after']['color']='rgb(0, 0, 0)'
            else:e['after']['transform']='matrix(2, 0, 0, 2, 0, 0)'
            with self.subTest(mode=mode):self.assertTrue(inspect_loop(e)['unresolved'])


import os
import json
import threading
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

LOOP_JS = r'''e=>{
const box=r=>({x:r.x,y:r.y,w:r.width,h:r.height});
const texts=e=>{let a=[],w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT),n;while(n=w.nextNode()){if(!n.textContent.trim())continue;let r=document.createRange();r.selectNodeContents(n);for(let b of r.getClientRects())if(b.width&&b.height)a.push(box(b))}return a};
const style=s=>({transform:s.transform,color:s.backgroundColor,background:s.backgroundImage,radii:['TopLeft','TopRight','BottomRight','BottomLeft'].map(k=>s['border'+k+'Radius']),borders:['Top','Right','Bottom','Left'].map(k=>({width:parseFloat(s['border'+k+'Width']),style:s['border'+k+'Style'],color:s['border'+k+'Color']}))});
const nodes=[...e.querySelectorAll('.sd-node')];
const ref=(n,id)=>{if(id&&n.id!==id)throw Error('Declared LOOP endpoint is not first/last node');return {id:n.id||('baseline-node-'+nodes.indexOf(n)),count:id?[...e.closest('figure').querySelectorAll('[id]')].filter(x=>x.id===id).length:1,cls:n.className,box:box(n.getBoundingClientRect()),text:texts(n)}};
return {role:'loop',cls:e.className,box:box(e.getBoundingClientRect()),sourceInside:true,targetInside:true,sourceRef:ref(nodes.at(-1),e.dataset.from),targetRef:ref(nodes[0],e.dataset.to),text:texts(e),before:style(getComputedStyle(e,'::before')),after:style(getComputedStyle(e,'::after'))};}'''

@unittest.skipUnless(os.environ.get('LOOP_SITE'), 'set LOOP_SITE for three-article browser proof')
class LoopBrowserTests(unittest.TestCase):
    def test_three_actual_articles(self):
        from playwright.sync_api import sync_playwright
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        site=Path(os.environ['LOOP_SITE'])
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(site)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        results=[]
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch()
                for article in ('argocd-rbac-5w','gitops-kubernetes-4w','introduce-gitops-1w'):
                    for width in (360,390,625,720):
                        for theme in ('light','dark'):
                            page=browser.new_page(viewport=dict(width=width if width<400 else 1280,height=1000))
                            base=f'http://127.0.0.1:{server.server_port}'
                            page.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base) and r.request.resource_type!='script' else r.abort())
                            page.goto(base+'/posts/'+article+'/',wait_until='load')
                            page.evaluate('t=>document.documentElement.setAttribute("data-mode",t)',theme)
                            loop=page.locator('figure.sd .sd-loop')
                            self.assertEqual(loop.count(),1)
                            if width>=400:
                                loop.evaluate('(e,w)=>{let f=e.closest("figure"),s=getComputedStyle(f);f.style.width=(w+parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+2)+"px";f.style.maxWidth="none"}',width)
                            page.evaluate('document.fonts.ready')
                            loop.scroll_into_view_if_needed()
                            data=loop.evaluate(LOOP_JS)
                            cdp=page.context.new_cdp_session(page)
                            root=cdp.send('DOM.getDocument')['root']['nodeId']
                            node=cdp.send('DOM.querySelector',dict(nodeId=root,selector='figure.sd .sd-loop'))['nodeId']
                            parent=cdp.send('DOM.getBoxModel',dict(nodeId=node))['model']['border']
                            dx=parent[0]-data['box']['x'];dy=parent[1]-data['box']['y']
                            data['pseudos']=[]
                            for p in cdp.send('DOM.describeNode',dict(nodeId=node,depth=1))['node']['pseudoElements']:
                                m=cdp.send('DOM.getBoxModel',dict(backendNodeId=p['backendNodeId']))['model']
                                normalize=lambda q:[v-(dx if i%2==0 else dy) for i,v in enumerate(q)]
                                data['pseudos'].append(dict(type=p['pseudoType'],quad=normalize(m['border']),innerQuad=normalize(m['padding']),paintPolygons=[]))
                            result=inspect_loop(data)
                            results.append(dict(article=article,width=width,theme=theme,result=result,element=data))
                            page.close()
                browser.close()
        finally:
            server.shutdown();server.server_close()
        if os.environ.get('LOOP_RESULTS'):Path(os.environ['LOOP_RESULTS']).write_text(json.dumps(results,indent=2))
        self.assertEqual(len(results),24)
        for r in results:
            with self.subTest(article=r['article'],width=r['width'],theme=r['theme']):
                self.assertEqual(r['result']['unresolved'],[])
                self.assertEqual(r['result']['findings'],[])

if __name__ == '__main__':
    unittest.main()
