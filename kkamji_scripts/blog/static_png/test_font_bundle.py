import hashlib
import json
from pathlib import Path
import unittest

from font_bundle import classify, font_urls
from pipeline import load_bundle, font_policy


class PublicBundleTests(unittest.TestCase):
    def test_url_allowlist(self):
        self.assertEqual(classify('https://fonts.gstatic.com/s/lato/v25/x.woff2'), ['lato'])
        for url in ('http://fonts.gstatic.com/s/lato/x.ttf',
                    'https://example.com/font.ttf',
                    'https://fonts.gstatic.com/s/unreviewed/x.ttf'):
            with self.assertRaises(ValueError):
                classify(url)

    def test_relative_font_resolution(self):
        self.assertEqual(font_urls("src:url('../webfonts/a.woff2')", 'https://cdn.example/css/a.css'),
                         ['https://cdn.example/webfonts/a.woff2'])

    def test_pinned_resources_and_licenses(self):
        directory = Path(__file__).resolve().parents[3] / 'assets/fonts/static-png'
        data = json.loads((directory / 'lock.json').read_text())
        bundle = load_bundle(directory / 'lock.json')
        self.assertTrue(bundle)
        for resource in bundle.values():
            classify(resource['url'])
            self.assertTrue(resource['license'])
        for license in data['licenses'].values():
            raw = (directory / license['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), license['sha256'])
        for url, resource in bundle.items():
            if resource['content_type'] == 'text/css':
                for font in font_urls(resource['body'].decode(), url):
                    self.assertIn(font, bundle)

    def test_live_fallback_is_not_production_attestation(self):
        # Public Source Sans Pro has no Hangul face; never silence the gate.
        with self.assertRaises(ValueError):
            font_policy('production', [{'isCustomFont': False}], [])


if __name__ == '__main__':
    unittest.main()
