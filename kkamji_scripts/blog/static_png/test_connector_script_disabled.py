import os
from pathlib import Path
import subprocess
import sys
import unittest


class ScriptDisabledStyleTests(unittest.TestCase):
    def test_inline_export_style_completes_with_page_scripts_disabled(self):
        directory = Path(__file__).resolve().parent
        code = '''from playwright.sync_api import sync_playwright
from connector_corpus import install_export_css
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(java_script_enabled=False)
    page.set_content('<html><head></head><body>probe</body></html>')
    install_export_css(page, 'body{color:rgb(1,2,3)}')
    assert page.locator('body').evaluate('e=>getComputedStyle(e).color')=='rgb(1, 2, 3)'
    browser.close()
'''
        try:
            result = subprocess.run([sys.executable, '-c', code], cwd=directory, capture_output=True, text=True, timeout=12)
        except subprocess.TimeoutExpired:
            self.fail('style installation hung with page scripts disabled')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
