import json
import tempfile
import unittest
from pathlib import Path

class CorpusTests(unittest.TestCase):
    def test_inventory_all_occurrences_and_missing_used(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('corpus'), 'corpus implementation missing')
        import corpus
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); site = root/'site'; site.mkdir()
            inc = root/'_includes/diagrams'; inc.mkdir(parents=True)
            (inc/'a.html').write_text('<figure class="sd" id="a"></figure>')
            (inc/'b.html').write_text('<figure class="sd" id="b"></figure>')
            catalog = {'diagrams': [{'include':'diagrams/a.html', 'posts':['post.md']},
                                    {'include':'diagrams/b.html', 'posts':[]}]}
            (root/'catalog.json').write_text(json.dumps(catalog))
            for page in ['one.html', 'two.html']:
                (site/page).write_text('<figure id="a" class="sd"></figure>')
            result = corpus.inventory(root, site, root/'catalog.json')
            self.assertEqual(len(result['entries']), 2)
            self.assertEqual(result['unused'], ['diagrams/b.html'])
            (site/'one.html').unlink(); (site/'two.html').unlink()
            with self.assertRaises(ValueError): corpus.inventory(root, site, root/'catalog.json')

class ManifestTests(unittest.TestCase):
    def test_manifest_roundtrip_missing_and_changed_corpus(self):
        import corpus, subprocess, sys
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); site = root/'site'; site.mkdir()
            includes = root/'_includes'; includes.mkdir()
            figure = '<figure class="sd" id="test"><span>Test text</span></figure>'
            (includes/'test.html').write_text(figure)
            (site/'index.html').write_text('<meta charset="utf-8"><style>figure{font-size:16px;margin:0}.content{max-width:100%}</style><article class="content">'+figure+'</article>')
            catalog = root/'catalog.json'
            catalog.write_text(json.dumps({'diagrams':[{'include':'test.html','posts':['post.md']}]}))
            out = root/'out'
            common = ['--root',str(root),'--catalog',str(catalog),'--site',str(site),'--out',str(out),'--font-profile','local-fallback']
            def run(action):
                return subprocess.run([sys.executable, corpus.__file__, action]+common,capture_output=True,text=True)
            result = run('export'); self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result = run('check'); self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            manifest = out/'manifest-light.json'; before = manifest.read_bytes()
            png = next(out.rglob('*-625-light.png')); original = png.read_bytes(); png.unlink()
            self.assertNotEqual(run('check').returncode,0)
            self.assertEqual(manifest.read_bytes(),before, 'check must not rewrite manifest')
            png.write_bytes(original)
            (includes/'test.html').write_text(figure+'<!-- source changed -->')
            self.assertNotEqual(run('check').returncode,0)

class TemplateTests(unittest.TestCase):
    def test_source_instance_template(self):
        import corpus
        self.assertEqual(corpus.Figures('<figure class="sd" id="a{{include.instance}}"></figure>', source=True).ids, ['a{{include.instance}}'])

class SelectorTests(unittest.TestCase):
    def test_labelledby_supports_figures_without_ids(self):
        import corpus
        self.assertEqual(corpus.Figures('<figure class="sd" aria-labelledby="a-title"></figure>').ids, ['a-title'])

if __name__ == '__main__': unittest.main()
