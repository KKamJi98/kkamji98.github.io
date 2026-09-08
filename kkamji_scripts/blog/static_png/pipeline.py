#!/usr/bin/env python3
"""Export the rendered canonical figure; no alternate drawing or copied CSS."""
import argparse
import hashlib
import html
import json
import re
import struct
import threading
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from connector_audit import inspect_connectors


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_bundle(lock):
    """Offline, exact-URL production CSS/font snapshots; no network acquisition."""
    if lock is None:
        return {}
    data = json.loads(lock.read_text())
    result = {}
    for entry in data['resources']:
        url = entry['url']
        path = (lock.parent / entry['path']).resolve()
        if (not url.startswith('https://') or url in result or
                not path.is_relative_to(lock.parent.resolve()) or
                not entry.get('source') or not entry.get('license')):
            raise ValueError('invalid bundle URL, path or provenance')
        raw = path.read_bytes()
        if digest(raw) != entry['sha256']:
            raise ValueError('production resource hash mismatch: ' + url)
        result[url] = dict(entry, body=raw)
    if not result:
        raise ValueError('empty production resource bundle')
    return result


def font_policy(profile, rendered, blocked):
    if profile == 'deterministic-export':
        if not rendered or any(not f['isCustomFont'] or f['postScriptName'] not in
                ('NotoSansKR-Thin', 'NotoSansMono-Regular') for f in rendered):
            raise ValueError('deterministic fonts incomplete: unexpected web font or system fallback')
        return {'profile': profile, 'status': 'pinned-export-fonts',
                'production_identical': False, 'parity_scope': 'export-only open fonts; pinned browser required'}
    if profile in ('production', 'strict-production') and (not rendered or blocked or
            any(not f['isCustomFont'] for f in rendered)):
        raise ValueError('production fonts incomplete: system fallback or blocked stylesheet/font')
    return {'profile': profile, 'status': 'pinned-web-fonts' if profile in ('production', 'strict-production') else 'local-fallback',
            'production_identical': False, 'parity_scope': 'offline pinned inputs only; no live production attestation'}


def deterministic_css(bundle):
    faces = []
    for prefix, family in [('NotoSansKR[', 'SD Export Sans'), ('NotoSansMono[', 'SD Export Mono')]:
        matches = [url for url, entry in bundle.items() if entry['path'].startswith(prefix)]
        if len(matches) != 1:
            raise ValueError('deterministic bundle missing required font: ' + prefix)
        faces.append('@font-face{font-family:"' + family + '";src:url("' + matches[0] + '") format("truetype");font-weight:100 900;font-style:normal;font-display:block;}')
    return '\n'.join(faces) + '\nfigure.sd,figure.sd *{font-family:"SD Export Sans" !important;}\nfigure.sd code,figure.sd code *,figure.sd pre,figure.sd kbd,figure.sd samp{font-family:"SD Export Mono" !important;}'


def await_assets(figure):
    # Explicit completion, not quiet-network timing. Timer only bounds failure.
    figure.evaluate('''async f => {
      let timer;
      try { await Promise.race([
        (async () => {
          f.getBoundingClientRect();
          await document.fonts.ready;
          await Promise.all([...f.querySelectorAll('img')].map(i => i.decode()));
        })(),
        new Promise((_,reject) => {timer=setTimeout(()=>reject(Error('export assets timeout')),30000)})
      ]); } finally {clearTimeout(timer)}
    }''')


def rendered_fonts(page, selector):
    """CDP reports actual glyph font usage, not just CSS family declarations."""
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send('DOM.enable'); cdp.send('CSS.enable')
        root = cdp.send('DOM.getDocument')['root']['nodeId']
        nodes = cdp.send('DOM.querySelectorAll', {'nodeId': root, 'selector': ', '.join(part + suffix for part in selector.split(', ') for suffix in ('', ' *'))})['nodeIds']
        fonts = {}
        for node in nodes:
            for font in cdp.send('CSS.getPlatformFontsForNode', {'nodeId': node})['fonts']:
                if font['glyphCount']:
                    key = (font['postScriptName'], font['isCustomFont'])
                    fonts[key] = font
        return sorted(fonts.values(), key=lambda f: (f['postScriptName'], f['isCustomFont']))
    finally:
        cdp.detach()


def fingerprint(inputs):
    return digest(json.dumps(inputs, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())


def freshness(receipt, current, png):
    return png.is_file() and receipt.get('fingerprint') == current and receipt.get('png_sha256') == digest(png.read_bytes())


def gate(metrics):
    return (all(key in metrics and not metrics[key] for key in ['overflow', 'small', 'hidden', 'unselectable', 'broken', 'interaction'])
            and not metrics.get('connector_issues'))


AUDIT = r'''f => {
 const box=f.getBoundingClientRect(), out={overflow:[],small:[],hidden:[],unselectable:[],broken:[],interaction:[]};
 const els=[f,...f.querySelectorAll('*')];
 for(const e of els){
   const r=e.getBoundingClientRect(),s=getComputedStyle(e), name=e.id||e.className||e.tagName;
   if(r.width && (r.left<box.left-1 || r.right>box.right+1 || r.top<box.top-1 || r.bottom>box.bottom+1 || e.scrollWidth>e.clientWidth+2)) out.overflow.push(name);
   if(e.matches('button,a,input,select,textarea,script,[onclick],[tabindex]') || [...e.attributes].some(a=>a.name.startsWith('on')) || s.animationName!=='none') out.interaction.push(name);
   if(e.matches('img') && (!e.complete || !e.naturalWidth)) out.broken.push(e.getAttribute('src'));
   for(const n of e.childNodes){
     if(n.nodeType!==3 || !n.textContent.trim()) continue;
     let minimum=e.closest('.sd-title')?22:e.closest('.sd-label,.sd-lane-title,.sd-band-title')?16:14;
     if(parseFloat(s.fontSize)<minimum) out.small.push({name,size:s.fontSize,minimum,text:n.textContent.trim()});
     if(s.display==='none'||s.visibility!=='visible'||parseFloat(s.opacity)===0||!r.width||!r.height) out.hidden.push(name);
     if(s.userSelect==='none'||s.webkitUserSelect==='none') out.unselectable.push(name);
     const range=document.createRange();range.selectNodeContents(n);
     for(const t of range.getClientRects()) if(t.left<box.left-1||t.right>box.right+1||t.top<box.top-1||t.bottom>box.bottom+1) out.overflow.push('text:'+name);
   }
 }
 let selection=getSelection(); const range=document.createRange();range.selectNodeContents(f);selection.removeAllRanges();selection.addRange(range);
 const selected=selection.toString();selection.removeAllRanges();
 if(!selected.trim()) out.unselectable.push('empty native selection');
 out.width=box.width;out.height=box.height;out.text=f.innerText;out.selection_length=selected.length;
 out.kind=[...f.classList].find(x=>x.startsWith('sd--'))||'unspecified';
 // Review flag only: vertical layering and mobile reflow are not errors.
 const ratios={'sd--flow':4,'sd--comparison':3,'sd--layer':8};
 out.height_review=box.height/box.width>(ratios[out.kind]||6);
 return out;
}'''


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site', type=Path, required=True);p.add_argument('--page', required=True)
    p.add_argument('--figure', required=True);p.add_argument('--out', type=Path, required=True)
    p.add_argument('--check', action='store_true', help='Read-only freshness and quality check')
    p.add_argument('--theme', choices=['light','dark'], default='light')
    p.add_argument('--font-profile', choices=['production', 'strict-production', 'local-fallback', 'diagnostic-local', 'deterministic-export'], default='production')
    p.add_argument('--font-bundle', type=Path)
    p.add_argument('--export-font-bundle', type=Path, default=Path(__file__).resolve().parents[3]/'assets/fonts/deterministic-export/lock.json')
    a=p.parse_args();site=a.site.resolve();pagefile=(site/a.page).resolve()
    if not pagefile.is_relative_to(site) or not pagefile.is_file(): p.error('page must exist inside site')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',a.figure):p.error('invalid figure ID')
    bundle = load_bundle(a.font_bundle)
    export_bundle = load_bundle(a.export_font_bundle) if a.font_profile == 'deterministic-export' else {}
    export_css = deterministic_css(export_bundle) if export_bundle else ''
    if a.font_profile in ('production', 'strict-production') and not bundle:
        p.error('production requires --font-bundle; use explicit --font-profile local-fallback for diagnostics')
    from playwright.sync_api import sync_playwright
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(site)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    dependencies={};blocked=[]; blocked_fonts=[]; loaded_fonts={}
    def response(r):
        if r.request.resource_type == 'font' and r.status == 200:
            loaded_fonts[r.url.replace(origin, '')] = digest(r.body())
        if r.url.startswith(origin) and r.status==200:
            try: dependencies[r.url[len(origin):]]=digest(r.body())
            except Exception: pass
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        ctx=browser.new_context(viewport={'width':1280,'height':1000},device_scale_factor=2,color_scheme=a.theme,java_script_enabled=False,locale='ko-KR',timezone_id='UTC')
        def route(r):
            if r.request.url.startswith(origin+'/'):
                if r.request.resource_type=='script': r.abort()
                else:r.continue_()
            elif r.request.url in export_bundle or r.request.url in bundle:
                resource = export_bundle.get(r.request.url) or bundle[r.request.url]
                r.fulfill(body=resource['body'], content_type=resource['content_type'])
            elif r.request.url.startswith('data:'):r.continue_()
            else:
                blocked.append(r.request.url)
                if r.request.resource_type in ('font', 'stylesheet'): blocked_fonts.append(r.request.url)
                r.abort()
        ctx.route('**/*',route);page=ctx.new_page();page.on('response',response)
        page.goto(origin+'/'+a.page,wait_until='load', timeout=30000)
        page.evaluate('(theme)=>document.documentElement.setAttribute("data-mode",theme)',a.theme)
        selector = 'figure.sd[id="' + a.figure + '"], figure.sd:not([id])[aria-labelledby="' + a.figure + '"]'
        f=page.locator(selector)
        if f.count()!=1:raise RuntimeError('canonical figure must match exactly once')
        if export_css:
            page.evaluate('(css)=>{const s=document.createElement("style");s.textContent=css;document.head.appendChild(s)}', export_css)
        # Change only article frame geometry, never author a second drawing.
        page.evaluate('''()=>{const c=document.querySelector('.content');if(!c)throw Error('article .content missing');c.style.width='625px';c.style.maxWidth='625px';}''')
        f.locator('img').evaluate_all('(imgs)=>imgs.forEach(i=>{i.loading="eager"})')
        f.scroll_into_view_if_needed();await_assets(f)
        desktop=f.evaluate(AUDIT)
        connectors=inspect_connectors(page, selector)
        desktop.update(connector_issues=connectors['issues'], connector_metrics=connectors)
        actual_fonts = rendered_fonts(page, selector)
        policy = font_policy(a.font_profile, actual_fonts, blocked_fonts)
        article_width=page.locator('.content').first.evaluate('e=>e.getBoundingClientRect().width')
        if abs(article_width-625)>1:raise RuntimeError('article frame is not 625px')
        source=f.evaluate('e=>e.outerHTML')
        font_state=page.evaluate('''()=>[...document.fonts].map(f=>({family:f.family,status:f.status,weight:f.weight,style:f.style})).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)))''')
        import platform, importlib.metadata, subprocess
        # Inventory files, not request timing: favicons/lazy loads are nondeterministic.
        from urllib.parse import urlparse, unquote
        resources=set(site.rglob('*.css')) | set(site.rglob('*.woff*')) | set(site.rglob('*.ttf')) | set(site.rglob('*.otf'))
        for src in f.locator('img').evaluate_all('(xs)=>xs.map(x=>x.src)'):
            if src.startswith(origin+'/'):
                resource=(site/unquote(urlparse(src).path.lstrip('/'))).resolve()
                if not resource.is_relative_to(site):raise RuntimeError('image outside site')
                resources.add(resource)
        dependencies={str(x.relative_to(site)):digest(x.read_bytes()) for x in sorted(resources)}
        installed_fonts=sorted(set(subprocess.check_output(['fc-list','--format','%{file}\\n'],text=True).splitlines()))
        system_fonts={x:digest(Path(x).read_bytes()) for x in installed_fonts}
        inputs={'built_html':digest(pagefile.read_bytes()),'figure_html':digest(source.encode()),'dependencies':dependencies, 'fonts':font_state,'system_fonts':system_fonts,'viewport':[1280,1000],'article_width':625,'dpr':2,'theme':a.theme,'browser':browser.version,'playwright':importlib.metadata.version('playwright'),'os':platform.platform(),'tool':digest(Path(__file__).read_bytes()),'network_policy':'offline exact bundle URLs or local; scripts disabled', 'font_policy':policy, 'actual_fonts':actual_fonts, 'loaded_font_binaries':dict(sorted(loaded_fonts.items())), 'production_bundle':{url:{k:v for k,v in entry.items() if k != 'body'} for url,entry in bundle.items()}}
        stem=f'{a.figure}-625-{a.theme}';png=a.out/(stem+'.png');receipt_path=a.out/(stem+'.json')
        mobile_png = a.out/f'{a.figure}-360-{a.theme}.png'
        if not a.check:
            a.out.mkdir(parents=True,exist_ok=True);f.screenshot(path=str(png),animations='disabled')
        page.set_viewport_size({'width':360,'height':1000})
        page.evaluate('''()=>{const c=document.querySelector('.content');c.style.removeProperty('width');c.style.removeProperty('max-width')}''')
        f.scroll_into_view_if_needed();await_assets(f);mobile=f.evaluate(AUDIT)
        connectors=inspect_connectors(page, selector)
        mobile.update(connector_issues=connectors['issues'], connector_metrics=connectors)
        mobile_fonts = rendered_fonts(page, selector)
        font_policy(a.font_profile, mobile_fonts, blocked_fonts)
        if not a.check:f.screenshot(path=str(mobile_png),animations='disabled')
        # Resolve actual CDP PostScript names against fontconfig's binary inventory.
        # Collections/duplicate installations can yield multiple candidates; hash all,
        # explicitly retaining ambiguity rather than pretending one file was selected.
        actual_system = {}
        font_rows = subprocess.check_output(['fc-list', '--format', '%{postscriptname}\t%{file}\n'], text=True).splitlines()
        for font in actual_fonts + mobile_fonts:
            if font['isCustomFont']: continue
            name = font['postScriptName']; candidates = {}
            for row in font_rows:
                names, separator, path = row.partition('\t')
                if separator and name in names.split(',') and path in system_fonts:
                    candidates[path] = system_fonts[path]
            if not candidates:
                raise ValueError('actual system font binary unresolved: ' + name)
            actual_system[name] = dict(sorted(candidates.items()))
        inputs.update(mobile_fonts=mobile_fonts, loaded_font_binaries=dict(sorted(loaded_fonts.items())),
                      mobile_viewport=[360,1000], actual_system_font_binaries=actual_system)
        inputs.update(export_font_bundle={url:{k:v for k,v in entry.items() if k != 'body'} for url,entry in export_bundle.items()}, export_font_css=export_css)
        inputs['connector_tool_sha256'] = {name: digest(Path(__file__).with_name(name).read_bytes())
                                             for name in ('connector_audit.py', 'connector_geometry.py', 'connector_roles.py', 'connector_loop.py')}
        fp = fingerprint(inputs)
        fresh = False
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            fresh = (freshness(receipt, fp, png) and mobile_png.is_file() and
                     receipt.get('mobile_png_sha256') == digest(mobile_png.read_bytes()))
        passed=gate(desktop) and gate(mobile)
        result={'fingerprint':fp,'inputs':inputs,'quality':{'desktop':desktop,'mobile':mobile},'quality_status':'passed' if passed else 'failed','visual_review':'not-run','semantic_review':'not-run','font_policy':policy,'mobile_fonts':mobile_fonts,'freshness':fresh,'png_url':png.name}
        if not a.check:
            raw=png.read_bytes()
            if raw[:8]!=b'\x89PNG\r\n\x1a\n':raise RuntimeError('invalid PNG')
            result.update(png_sha256=digest(raw),png_dimensions=list(struct.unpack('>II',raw[16:24])),
                          mobile_png_sha256=digest(mobile_png.read_bytes()))
            receipt_path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
            link=f'<p class="diagram-download"><a href="{html.escape(png.name)}" download="{html.escape(png.name)}">PNG 다운로드</a> <a href="{html.escape(png.name)}">원본 이미지 열기</a></p>\n'
            (a.out/f'{a.figure}-download.html').write_text(link)
        browser.close()
    server.shutdown(); server.server_close()
    print(json.dumps({'quality':result['quality_status'],'fresh':fresh,'receipt':str(receipt_path),'blocked_external':sorted(set(blocked))},ensure_ascii=False))
    # Quality failures still produce diagnostic screenshots, never a successful release gate.
    return 0 if passed and (fresh or not a.check) else 1

if __name__=='__main__':raise SystemExit(main())
