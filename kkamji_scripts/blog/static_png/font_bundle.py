#!/usr/bin/env python3
"""Explicit public font acquisition; exporter itself remains strictly offline.

Snapshots live linked third-party stylesheets and their font URLs without rewriting
CSS. No proprietary system fonts are copied. A snapshot does not guarantee glyph
coverage: strict production policy must still pass for each exported figure.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

PAGE = 'https://kkamji.net/posts/litellm-gateway/'
LICENSES = {
    'lato': ('OFL-1.1', 'https://raw.githubusercontent.com/google/fonts/main/ofl/lato/OFL.txt'),
    'sourcesanspro': ('OFL-1.1', 'https://raw.githubusercontent.com/adobe-fonts/source-sans/release/LICENSE.md'),
    'fontawesome': ('OFL-1.1 fonts; MIT CSS', 'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@7/LICENSE.txt'),
    'tocbot': ('MIT', 'https://cdn.jsdelivr.net/npm/tocbot@4/LICENSE'),
    'glightbox': ('MIT', 'https://cdn.jsdelivr.net/npm/glightbox@3/LICENSE.md'),
    'loading': ('MIT', 'https://cdn.jsdelivr.net/npm/loading-attribute-polyfill@2/LICENSE'),
}


def classify(url):
    p = urlparse(url)
    if p.scheme != 'https':
        raise ValueError('HTTPS required')
    if p.hostname == 'fonts.googleapis.com':
        return ['lato', 'sourcesanspro']
    if p.hostname == 'fonts.gstatic.com':
        for name in ('lato', 'sourcesanspro'):
            if p.path.startswith('/s/' + name + '/'):
                return [name]
    if p.hostname == 'cdn.jsdelivr.net':
        for package, name in (('@fortawesome/fontawesome-free@7/', 'fontawesome'),
                              ('tocbot@4/', 'tocbot'), ('glightbox@3/', 'glightbox'),
                              ('loading-attribute-polyfill@2/', 'loading')):
            if p.path.startswith('/npm/' + package):
                return [name]
    raise ValueError('unreviewed resource: ' + url)


def font_urls(css, base):
    return sorted({urljoin(base, u) for u in re.findall(r'url\([\"\']?([^\)\"\']+)', css)
                   if re.search(r'\.(?:woff2?|ttf|otf)(?:[?#]|$)', u)})


def acquire(out):
    from playwright.sync_api import sync_playwright
    from pipeline import rendered_fonts
    out.mkdir(parents=True, exist_ok=True)
    resources = {}
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(java_script_enabled=False, locale='ko-KR',
                                      timezone_id='UTC', device_scale_factor=2,
                                      viewport={'width': 1280, 'height': 1000})
        page = context.new_page()
        def response(r):
            if r.request.resource_type == 'stylesheet' and urlparse(r.url).hostname != 'kkamji.net':
                classify(r.url)
                resources[r.url] = (r.body(), 'text/css')
        page.on('response', response)
        page.on('requestfailed', lambda r: failures.append({'url': r.url, 'failure': r.failure}))
        page.goto(PAGE, wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        usage = {}
        for width in (1280, 360):
            page.set_viewport_size({'width': width, 'height': 1000})
            page.locator('figure.sd').first.scroll_into_view_if_needed()
            page.evaluate('document.fonts.ready')
            usage[str(width)] = rendered_fonts(page, 'figure.sd')
        evidence = {'page': PAGE, 'browser': browser.version,
                    'user_agent': page.evaluate('navigator.userAgent'),
                    'actual_used_fonts': usage, 'request_failures': failures,
                    'production_identical': False,
                    'profile': 'unmodified public stylesheet snapshot; not a replacement font profile',
                    'captured_at': datetime.now(timezone.utc).isoformat()}
        # Use the browser request client and its UA to retain negotiated CSS bytes.
        for url, (raw, _) in list(resources.items()):
            for font in font_urls(raw.decode(), url):
                classify(font)
                r = context.request.get(font)
                if not r.ok:
                    raise RuntimeError(f'{font}: {r.status}')
                resources[font] = (r.body(), 'font/woff2' if '.woff2' in font else
                                   'font/woff' if '.woff' in font else 'font/ttf')
        licenses = {}
        for name in sorted({n for u in resources for n in classify(u)}):
            spdx, url = LICENSES[name]
            r = context.request.get(url)
            if not r.ok:
                raise RuntimeError(f'license {url}: {r.status}')
            raw = r.body()
            text = raw.decode()
            if not ('SIL OPEN FONT LICENSE' in text or 'Permission is hereby granted' in text):
                raise ValueError('unrecognized license text: ' + url)
            path = 'licenses/' + name + '.txt'
            (out / path).parent.mkdir(exist_ok=True)
            (out / path).write_bytes(raw)
            licenses[name] = {'spdx': spdx, 'url': url, 'path': path,
                              'sha256': hashlib.sha256(raw).hexdigest()}
        browser.close()
    entries = []
    for url, (raw, mime) in sorted(resources.items()):
        sha = hashlib.sha256(raw).hexdigest()
        suffix = '.css' if mime == 'text/css' else Path(urlparse(url).path).suffix
        path = 'resources/' + sha + suffix
        (out / path).parent.mkdir(exist_ok=True)
        (out / path).write_bytes(raw)
        entries.append({'url': url, 'path': path, 'sha256': sha, 'content_type': mime,
                        'source': PAGE, 'license': [licenses[n] for n in classify(url)]})
    lock = {'resources': entries, 'licenses': licenses, 'evidence': evidence}
    (out / 'lock.json').write_text(json.dumps(lock, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'resources': len(entries), 'evidence': evidence}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    acquire(parser.parse_args().out)
