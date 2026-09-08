import unittest
import pipeline as m


class DeterministicPolicyTests(unittest.TestCase):
    def test_browser_missing_faces_rejected(self):
        from pathlib import Path
        from playwright.sync_api import sync_playwright
        lock = Path(__file__).resolve().parents[3]/'assets/fonts/deterministic-export/lock.json'
        bundle = m.load_bundle(lock)
        css = m.deterministic_css(bundle)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for missing in ('NotoSansKR', 'NotoSansMono'):
                page = browser.new_page()
                def route(r):
                    entry = bundle.get(r.request.url)
                    if entry and missing not in entry['path']:
                        r.fulfill(body=entry['body'], content_type=entry['content_type'])
                    else:
                        r.abort()
                page.route('**/*', route)
                page.set_content('<meta charset="utf-8"><figure class="sd">한국어 <code>code_123</code></figure>')
                page.evaluate('(css)=>{const s=document.createElement("style");s.textContent=css;document.head.appendChild(s)}', css)
                m.await_assets(page.locator('figure'))
                actual = m.rendered_fonts(page, 'figure.sd')
                with self.assertRaisesRegex(ValueError, 'deterministic', msg=str(actual)):
                    m.font_policy('deterministic-export', actual, [])
                page.close()
            browser.close()

    def test_missing_hangul_rejected(self):
        fonts = [{'isCustomFont': True, 'postScriptName': 'NotoSansKR-Regular'},
                 {'isCustomFont': False, 'postScriptName': 'NanumGothic'}]
        with self.assertRaisesRegex(ValueError, 'deterministic'):
            m.font_policy('deterministic-export', fonts, [])

    def test_missing_code_font_rejected(self):
        with self.assertRaisesRegex(ValueError, 'deterministic'):
            m.font_policy('deterministic-export', [
                {'isCustomFont': False, 'postScriptName': 'Consolas'}], [])

    def test_unexpected_webfont_rejected(self):
        with self.assertRaisesRegex(ValueError, 'deterministic'):
            m.font_policy('deterministic-export', [
                {'isCustomFont': True, 'postScriptName': 'Lato-Regular'}], [])
