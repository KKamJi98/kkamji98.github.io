#!/usr/bin/env python3
"""Real Chromium regression tests against production-built Chirpy overrides.

Usage: python tools/test_pwa.py --site /tmp/blog-cache-fix/site
The local fixture serves the supplied build's worker/client, not mock SW APIs.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
import subprocess

from playwright.sync_api import sync_playwright

ARGS = argparse.ArgumentParser()
ARGS.add_argument('--site', type=Path, required=True)
OPTIONS, REMAINING = ARGS.parse_known_args()
STATE = {'version': 'v1', 'legacy': False, 'requests': []}
# Read the installed upstream implementation verbatim, including its real client
# controllerchange/reload handler. No mocked registration or lifecycle APIs.
THEME = Path(subprocess.check_output(
    ['bundle', 'show', 'jekyll-theme-chirpy'], text=True).strip())
LEGACY = (THEME / 'assets/js/dist/sw.min.js').read_text().split('---', 2)[2]
LEGACY_APP = (THEME / 'assets/js/dist/app.min.js').read_text().split('---', 2)[2]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split('?')[0]
        STATE['requests'].append((self.command, self.path, self.headers.get('Cache-Control')))
        status = 200
        mime = 'text/plain'
        if path == '/sw.min.js':
            body = LEGACY if STATE['legacy'] else (OPTIONS.site / 'sw.min.js').read_text() + '\n// fixture deployment ' + STATE['version']
            mime = 'application/javascript'
        elif path == '/assets/js/data/swconf.js':
            body = 'const swconf = ' + json.dumps({
                'cacheName': 'chirpy-1700000000' if STATE['legacy'] else 'chirpy-1900000000', 'resources': ['/', '/asset.css'],
                'interceptor': {'paths': ['/excluded'], 'urlPrefixes': []}, 'purge': False
            }) + ';'
            mime = 'application/javascript'
        elif path == '/app.min.js':
            body = LEGACY_APP if STATE['legacy'] else (OPTIONS.site / 'app.min.js').read_text()
            mime = 'application/javascript'
        elif path in ['/', '/article', '/excluded']:
            body = f'<html><body><h1>{STATE["version"]}</h1></body></html>'
            mime = 'text/html'
        elif path == '/client':
            body = '<html><body><div id="notification"><button aria-label="Update">Update</button></div><script src="/app.min.js?register=true&baseurl="></script></body></html>'
            mime = 'text/html'
        elif path == '/missing':
            status, body = 404, 'missing'
        else:
            body = STATE['version']
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control', 'no-store' if path == '/private' and STATE['version'] == 'v2' else 'public, max-age=600')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body.encode())


class PwaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.origin = f'http://127.0.0.1:{cls.server.server_port}'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def setUp(self):
        STATE.update(version='v1', legacy=False, requests=[])
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(self.origin + '/')

    def tearDown(self):
        self.context.close()

    def register(self):
        self.page.evaluate("""async () => {
          await navigator.serviceWorker.register('/sw.min.js', {updateViaCache: 'none'});
          await navigator.serviceWorker.ready;
        }""")
        self.page.reload()
        self.page.wait_for_function('navigator.serviceWorker.controller !== null')

    def fetch(self, path):
        return self.page.evaluate('p => fetch(p).then(r => r.text())', path)

    def test_modern_update_activates_without_reload(self):
        self.page.goto(self.origin + '/client')
        self.page.evaluate('navigator.serviceWorker.ready')
        self.assertEqual(self.page.evaluate('(async () => (await navigator.serviceWorker.getRegistration()).updateViaCache)()'), 'none')
        self.page.reload()
        self.page.wait_for_function('navigator.serviceWorker.controller !== null')
        other = self.context.new_page()
        other.goto(self.origin + '/client')
        navigations = []
        self.page.on('framenavigated', lambda frame: navigations.append(frame.url))
        other.on('framenavigated', lambda frame: navigations.append(frame.url))
        self.page.clock.install()
        self.page.evaluate('(async () => { window.oldWorker = (await navigator.serviceWorker.getRegistration()).active; })()')
        STATE['version'] = 'v2'
        self.page.clock.fast_forward(61000)
        self.page.wait_for_function("""async () => {
          const r = await navigator.serviceWorker.getRegistration();
          return r.active !== window.oldWorker && r.active.state === 'activated' && !r.waiting;
        }""", timeout=10000)
        self.page.wait_for_timeout(1000)
        self.assertEqual(navigations, [], 'activation must not reload reading tabs')
        self.assertEqual(self.fetch('/mutable.json'), 'v2')

    def test_legacy_upgrade_preserves_reading_page_then_activates_on_close(self):
        STATE['legacy'] = True
        self.register()
        self.page.goto(self.origin + '/client')
        self.page.evaluate('navigator.serviceWorker.ready')
        self.assertIn('v1', self.fetch('/article'))
        self.page.evaluate("caches.open('unrelated-app').then(c => c.put('/sentinel', new Response('keep')))")
        navigations = []
        self.page.on('framenavigated', lambda frame: navigations.append(frame.url))
        STATE.update(legacy=False, version='v2')
        self.page.evaluate('(async () => (await navigator.serviceWorker.getRegistration()).update())()')
        self.page.wait_for_function('(async () => !!(await navigator.serviceWorker.getRegistration()).waiting)()')
        self.page.evaluate("(async () => (await navigator.serviceWorker.getRegistration()).waiting.postMessage('CHIRPY_ACTIVATE_WHEN_SAFE'))()")
        self.page.wait_for_timeout(2000)
        self.assertEqual(navigations, [], 'legacy reload handler must not be triggered automatically')
        self.assertTrue(self.page.evaluate('(async () => !!(await navigator.serviceWorker.getRegistration()).waiting)()'))
        self.assertIn('v1', self.fetch('/article'), 'legacy cache-first fixture must reproduce the bug')
        self.assertTrue(any(path.startswith('/assets/js/data/swconf.js?v=') for _, path, _ in STATE['requests']))
        # Remove the last legacy client without clearing cookies, CacheStorage,
        # the HTTP cache, or the registration. Native SW activation can now finish.
        worker = next(w for w in self.context.service_workers
                      if w.evaluate("typeof canActivate === 'function'"))
        self.page.close()
        worker.evaluate("""async () => {
          const pending = self.registration.waiting;
          if (!pending || pending.state === 'activated') return;
          await new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error('legacy close did not activate')), 5000);
            pending.addEventListener('statechange', () => {
              if (pending.state === 'activated') { clearTimeout(timer); resolve(); }
            });
          });
        }""")
        self.page = self.context.new_page()
        self.page.goto(self.origin + '/client')
        self.page.wait_for_function('navigator.serviceWorker.controller !== null')
        self.assertIn('v2', self.fetch('/article'))
        self.assertEqual(self.fetch('/asset.css'), 'v2')
        keys = self.page.evaluate('caches.keys()')
        self.assertNotIn('chirpy-1700000000', keys)
        self.assertIn('unrelated-app', keys)
        self.context.set_offline(True)
        self.assertIn('v2', self.fetch('/article'))
        self.assertEqual(self.fetch('/asset.css'), 'v2')

    def test_legacy_explicit_update_reloads_once_without_loop(self):
        STATE['legacy'] = True
        self.register()
        self.page.goto(self.origin + '/client')
        STATE.update(legacy=False, version='v2')
        self.page.evaluate('(async () => (await navigator.serviceWorker.getRegistration()).update())()')
        self.page.wait_for_function('(async () => !!(await navigator.serviceWorker.getRegistration()).waiting)()')
        navigations = []
        self.page.on('framenavigated', lambda frame: navigations.append(frame.url))
        with self.page.expect_navigation():
            self.page.locator('[aria-label="Update"]').click()
        self.page.wait_for_timeout(1500)
        self.assertEqual(len(navigations), 1, 'only an explicit legacy Update click may reload once')
        self.assertIn('v2', self.fetch('/article'))
        self.assertFalse(self.page.evaluate('(async () => !!(await navigator.serviceWorker.getRegistration()).waiting)()'))

    def test_mutable_assets_revalidate_and_work_offline(self):
        self.register()
        for path in ['/asset.css', '/mutable.json', '/image.svg']:
            self.assertEqual(self.fetch(path), 'v1')
        STATE['version'] = 'v2'
        for path in ['/asset.css', '/mutable.json', '/image.svg']:
            self.assertEqual(self.fetch(path), 'v2')
        self.context.set_offline(True)
        for path in ['/asset.css', '/mutable.json', '/image.svg']:
            self.assertEqual(self.fetch(path), 'v2')

    def test_no_store_removes_older_offline_copy(self):
        self.register()
        self.assertEqual(self.fetch('/private'), 'v1')
        STATE['version'] = 'v2'
        self.assertEqual(self.fetch('/private'), 'v2')
        self.context.set_offline(True)
        self.assertEqual(self.page.evaluate("fetch('/private').then(() => 'unexpected', () => 'unavailable')"), 'unavailable')

    def test_exclusions_and_security_boundaries(self):
        self.register()
        self.page.evaluate("caches.open('unrelated-app').then(c => c.put('/poison', new Response('poisoned')))")
        self.assertEqual(self.fetch('/poison'), 'v1', 'never consult another application cache')
        self.fetch('/excluded')
        self.page.evaluate("fetch('/post-only', {method: 'POST', body: 'test'})")
        self.page.evaluate("fetch('/range-only', {headers: {Range: 'bytes=0-1'}})")
        self.page.evaluate("fetch('/missing')")
        cross_origin = self.origin.replace('127.0.0.1', 'localhost')
        self.fetch(cross_origin + '/third-party')
        urls = self.page.evaluate("caches.open('chirpy-1900000000').then(c => c.keys()).then(keys => keys.map(r => r.url))")
        for suffix in ['/excluded', '/post-only', '/range-only', '/missing', '/third-party']:
            self.assertFalse(any(url.endswith(suffix) for url in urls), suffix)
        self.context.set_offline(True)
        self.assertEqual(self.page.evaluate("fetch('/not-visited').then(() => 'unexpected', () => 'unavailable')"), 'unavailable')

    def test_activation_only_removes_owned_caches(self):
        self.page.evaluate("""async () => {
          for (const name of ['chirpy-1700000000', 'unrelated-app', 'chirpy-other-app']) {
            const c = await caches.open(name);
            await c.put('/sentinel', new Response(name));
          }
        }""")
        self.register()
        keys = self.page.evaluate('caches.keys()')
        self.assertNotIn('chirpy-1700000000', keys)
        self.assertIn('unrelated-app', keys)
        self.assertIn('chirpy-other-app', keys)
        self.assertEqual(self.page.evaluate("caches.open('unrelated-app').then(c => c.match('/sentinel')).then(r => r.text())"), 'unrelated-app')

    def test_online_html_revalidates_and_offline_falls_back(self):
        self.register()
        self.page.goto(self.origin + '/article')
        self.assertEqual(self.page.locator('h1').inner_text(), 'v1')
        STATE['version'] = 'v2'
        self.page.reload()
        self.assertEqual(self.page.locator('h1').inner_text(), 'v2', 'cached HTML must not mask an online deployment')
        self.assertTrue(any(path == '/article' and cc and ('no-cache' in cc or 'max-age=0' in cc)
                            for _, path, cc in STATE['requests']))
        self.context.set_offline(True)
        self.page.reload()
        self.assertEqual(self.page.locator('h1').inner_text(), 'v2')


if __name__ == '__main__':
    unittest.main(argv=['test_pwa.py', *REMAINING], verbosity=2)
