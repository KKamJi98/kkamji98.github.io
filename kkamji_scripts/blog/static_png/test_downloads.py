import json
from pathlib import Path
import tempfile
import unittest

from downloads import HELPER, Siblings, built_plan, discover, main, validate_source


class DownloadWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'docs').mkdir()
        (self.root/'_posts').mkdir()
        (self.root/'_includes/diagrams').mkdir(parents=True)
        self.post = self.root/'_posts/example.md'
        self.original = '---\ntitle: untouched\ndate: original\n---\nProse.\n{% include diagrams/example.html %}\n{% include diagrams/example.html instance="-two" %}\nFooter.\n'
        self.post.write_text(self.original)
        (self.root/'_includes/diagrams/example.html').write_text('<figure class="sd" id="demo{{include.instance}}"><figcaption>Title</figcaption></figure>')
        (self.root/'docs/diagram-catalog.json').write_text(json.dumps({'summary': {'post_references': 2, 'posts': 1}, 'diagrams': [{'include': 'diagrams/example.html', 'posts': ['_posts/example.md'], 'reference_count': 2}]}))

    def wire(self):
        self.assertEqual(main(['wire', '--root', str(self.root)]), 0)
        return validate_source(self.root)

    def test_all_occurrences_unique_idempotent_and_prose_unchanged(self):
        plan = self.wire()
        first = self.post.read_bytes()
        self.assertEqual(HELPER.sub('', first.decode()), self.original)
        self.assertEqual(len({e['png'] for e in plan['entries']}), 2)
        self.assertEqual([e['figure'] for e in plan['entries']], ['demo', 'demo-two'])
        self.wire()
        self.assertEqual(first, self.post.read_bytes())

    def test_catalog_missing_occurrence_fails_before_write(self):
        self.post.write_text(self.original.replace('instance="-two"', 'extra="unsafe"'))
        before = self.post.read_bytes()
        with self.assertRaises(ValueError): self.wire()
        self.assertEqual(before, self.post.read_bytes())
        self.assertFalse((self.root/'docs/diagram-downloads.json').exists())

    def test_nonstandalone_fenced_and_nested_are_rejected(self):
        for text in ['prefix {% include diagrams/example.html %}\n', '```html\n{% include diagrams/example.html %}\n```\n', '<figure>\n{% include diagrams/example.html %}\n</figure>\n']:
            with self.subTest(text=text):
                self.post.write_text(text)
                with self.assertRaises(ValueError): discover(self.root)

    def test_sibling_outside_figure_and_native_download(self):
        text = '<main><figure class="sd" id="demo"><div>body</div></figure>\n<p class="diagram-download"><a href="/x.png" download>PNG</a><a href="/x.png">Open</a></p></main>'
        rows = Siblings(text).rows
        self.assertEqual(rows, [{'figure': 'demo', 'links': [('/x.png', True), ('/x.png', False)]}])
        with self.assertRaises(ValueError): Siblings(text.replace('</figure>', ''))
        with self.assertRaises(ValueError): Siblings(text.replace('</figure>', '</figure><div>intervening</div>'))

    def sidecar(self, site, mapping=None):
        path = site/'assets/data/diagram-posts.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(mapping if mapping is not None else {'_posts/example.md': '/'}))
        return path

    def test_swapped_reused_include_urls_reject_wrong_post_ownership(self):
        self.post.write_text('{% include diagrams/example.html %}\n')
        (self.root/'_posts/other.md').write_text(self.post.read_text())
        catalog = json.loads((self.root/'docs/diagram-catalog.json').read_text())
        catalog['summary']['posts'] = 2
        catalog['diagrams'][0]['posts'].append('_posts/other.md')
        (self.root/'docs/diagram-catalog.json').write_text(json.dumps(catalog))
        plan = self.wire()
        site = self.root/'site'; site.mkdir()
        self.sidecar(site, {'_posts/example.md': '/custom/', '_posts/other.md': '/another.html'})
        pages = [site/'custom/index.html', site/'another.html']
        def write_pages(entries):
            for page, entry in zip(pages, entries):
                page.parent.mkdir(parents=True, exist_ok=True)
                page.write_text('<figure class="sd" id="demo"></figure><p class="diagram-download"><a href="' + entry['png'] + '" download>PNG</a><a href="' + entry['png'] + '">Open</a></p>')
        write_pages(plan['entries'])
        self.assertEqual(len(built_plan(self.root, site, plan)), 2)
        write_pages(list(reversed(plan['entries'])))
        with self.assertRaisesRegex(ValueError, 'post/page ownership mismatch'):
            built_plan(self.root, site, plan)

    def test_post_sidecar_missing_duplicate_wrong_and_unsafe_mappings_fail(self):
        plan, site, out, args = self.export_fixture()
        sidecar = self.sidecar(site)
        invalid = ['{}', '[]', '{"_posts/example.md":"/", "_posts/example.md":"/"}',
                   '{"_posts/example.md":"/wrong/"}',
                   '{"_posts/example.md":"https://example.com/"}',
                   '{"_posts/example.md":"/../index.html"}',
                   '{"_posts/example.md":"/%2e%2e/index.html"}',
                   '{"_posts/example.md":"/?query=1"}',
                   '{"_posts/example.md":"/", "_posts/extra.md":"/"}']
        for text in invalid:
            with self.subTest(text=text):
                sidecar.write_text(text)
                with self.assertRaises(ValueError): built_plan(self.root, site, plan)
        sidecar.unlink()
        with self.assertRaises(ValueError): built_plan(self.root, site, plan)

    def test_built_coverage_missing_unknown_and_duplicate_fail(self):
        plan = self.wire()
        site = self.root/'site'; site.mkdir()
        page = site/'index.html'
        content = '<main>' + ''.join('<figure class="sd" id="' + e['figure'] + '"></figure><p class="diagram-download"><a href="' + e['png'] + '" download>PNG</a><a href="' + e['png'] + '">Open</a></p>' for e in plan['entries']) + '</main>'
        page.write_text(content)
        self.sidecar(site)
        self.assertEqual(len(built_plan(self.root, site, plan)), 2)
        page.write_text(content.replace('class="diagram-download"', 'class="other"', 1))
        with self.assertRaises(ValueError): built_plan(self.root, site, plan)
        page.write_text(content.replace(plan['entries'][0]['png'], '/unknown.png'))
        with self.assertRaises(ValueError): built_plan(self.root, site, plan)
        page.write_text(content.replace(plan['entries'][1]['png'], plan['entries'][0]['png']))
        with self.assertRaises(ValueError): built_plan(self.root, site, plan)

    def test_indented_occurrence_is_explicitly_blocked(self):
        self.post.write_text(self.original.replace('\n{% include diagrams/example.html instance=', '\n  {% include diagrams/example.html instance='))
        plan = self.wire()
        self.assertEqual(plan['linked_count'], 1)
        self.assertEqual(plan['blocked_count'], 1)
        self.assertEqual(plan['entries'][1]['status'], 'blocked-insertion')
        self.assertEqual(len(HELPER.findall(self.post.read_text())), 1)

    def test_export_exact_paths_and_changed_build_rejection(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from downloads import built_assets_snapshot, digest, source_snapshot
        plan = self.wire()
        with tempfile.TemporaryDirectory() as external:
            site = Path(external)/'site'; site.mkdir()
            out = Path(external)/'receipts'
            page = site/'index.html'
            page.write_text('<main>' + ''.join('<figure class="sd" id="' + e['figure'] + '"></figure><p class="diagram-download"><a href="' + e['png'] + '" download>PNG</a><a href="' + e['png'] + '">Open</a></p>' for e in plan['entries']) + '</main>')
            self.sidecar(site)
            (site/'.diagram-download-build.json').write_text(json.dumps({'source': source_snapshot(self.root), 'assets': built_assets_snapshot(site, plan), 'html': {'index.html': digest(page.read_bytes())}}))
            calls = []
            def fake_pipeline(command, **kwargs):
                calls.append(command)
                self.assertEqual(command[command.index('--font-profile') + 1], 'deterministic-export')
                target = Path(command[command.index('--out') + 1]); target.mkdir(parents=True, exist_ok=True)
                figure = command[command.index('--figure') + 1]
                raw = b'\x89PNG\r\n\x1a\n' + b'synthetic-adapter-fixture-not-a-real-image'
                if '--check' not in command:
                    (target/(figure + '-625-light.png')).write_bytes(raw)
                    (target/(figure + '-625-light.json')).write_text(json.dumps({'png_sha256': digest(raw), 'quality_status': 'passed'}))
                return SimpleNamespace(returncode=0)
            args = ['--root', str(self.root), '--site', str(site), '--out', str(out)]
            with patch('downloads.subprocess.run', side_effect=fake_pipeline):
                self.assertEqual(main(['export'] + args), 0)
                self.assertEqual(main(['check'] + args), 0)
                self.assertEqual(len(calls), 4)
                for entry in plan['entries']:
                    self.assertEqual((self.root/entry['png'].lstrip('/')).read_bytes(), (site/entry['png'].lstrip('/')).read_bytes())
                (self.root/plan['entries'][0]['png'].lstrip('/')).write_bytes(b'corrupt')
                with self.assertRaises(ValueError): main(['check'] + args)
                page.write_text(page.read_text() + 'changed')
                with self.assertRaisesRegex(ValueError, 'built HTML changed'): main(['export'] + args)

    def export_fixture(self):
        from downloads import built_assets_snapshot, digest, source_snapshot
        plan = self.wire()
        external = tempfile.TemporaryDirectory()
        self.addCleanup(external.cleanup)
        site = Path(external.name)/'site'; site.mkdir()
        out = Path(external.name)/'receipts'
        page = site/'index.html'
        page.write_text('<main>' + ''.join('<figure class="sd" id="' + e['figure'] + '"></figure><p class="diagram-download"><a href="' + e['png'] + '" download>PNG</a><a href="' + e['png'] + '">Open</a></p>' for e in plan['entries']) + '</main>')
        self.sidecar(site)
        (site/'.diagram-download-build.json').write_text(json.dumps({'source': source_snapshot(self.root), 'assets': built_assets_snapshot(site, plan), 'html': {'index.html': digest(page.read_bytes())}}))
        return plan, site, out, ['--root', str(self.root), '--site', str(site), '--out', str(out)]

    def test_parallel_default_preserves_report_order_and_isolates_targets(self):
        from threading import Event, Lock
        from types import SimpleNamespace
        from unittest.mock import patch
        plan, site, out, args = self.export_fixture()
        rows = built_plan(self.root, site, plan)
        second_done = Event(); lock = Lock(); calls = []; completed = []
        def run(command, **kwargs):
            figure = command[command.index('--figure') + 1]
            with lock: calls.append(command)
            if figure == rows[0]['figure']:
                self.assertTrue(second_done.wait(2), 'second worker did not run concurrently')
            with lock: completed.append(figure)
            if figure == rows[1]['figure']: second_done.set()
            return SimpleNamespace(returncode=7)
        with patch('downloads.subprocess.run', side_effect=run):
            self.assertEqual(main(['export'] + args), 1)
            report = json.loads((out/'downloads-export.json').read_text())
            self.assertEqual([e['png'] for e in report['entries']], [e['png'] for e in rows])
            self.assertEqual(completed, [e['figure'] for e in reversed(rows)])
            self.assertEqual(len({c[c.index('--out') + 1] for c in calls}), 2)
            self.assertTrue(all(e['exit_code'] == 7 and e['status'] == 'failed' for e in report['entries']))
            export_calls = {c[c.index('--figure') + 1]: c for c in calls}
            calls.clear()
            self.assertEqual(main(['check'] + args + ['--jobs', '1']), 1)
            for command in calls:
                self.assertEqual(command, export_calls[command[command.index('--figure') + 1]] + ['--check'])
            self.assertEqual(json.loads((out/'downloads-export.json').read_text()), report)

    def test_worker_count_is_bounded_for_every_jobs_value(self):
        from threading import Event, Lock
        from types import SimpleNamespace
        from unittest.mock import patch
        self.post.write_text(''.join('{% include diagrams/example.html instance="-' + str(i) + '" %}\n' for i in range(8)))
        catalog = json.loads((self.root/'docs/diagram-catalog.json').read_text())
        catalog['summary']['post_references'] = 8
        catalog['diagrams'][0]['reference_count'] = 8
        (self.root/'docs/diagram-catalog.json').write_text(json.dumps(catalog))
        plan, site, out, args = self.export_fixture()
        for jobs in range(1, 5):
            with self.subTest(jobs=jobs):
                ready = Event(); lock = Lock(); active = 0; peak = 0
                def run(command, **kwargs):
                    nonlocal active, peak
                    with lock:
                        active += 1; peak = max(peak, active)
                        if active == jobs: ready.set()
                    self.assertTrue(ready.wait(2), 'requested workers did not start')
                    with lock: active -= 1
                    return SimpleNamespace(returncode=7)
                with patch('downloads.subprocess.run', side_effect=run) as launch:
                    self.assertEqual(main(['export'] + args + ['--jobs', str(jobs)]), 1)
                self.assertEqual(peak, jobs)
                self.assertEqual(launch.call_count, 8)
                self.assertEqual(len(json.loads((out/'downloads-export.json').read_text())['entries']), 8)

    def test_launch_failure_is_reported_without_losing_other_results(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        plan, site, out, args = self.export_fixture()
        rows = built_plan(self.root, site, plan)
        def run(command, **kwargs):
            if command[command.index('--figure') + 1] == rows[0]['figure']:
                raise OSError('cannot launch pipeline')
            return SimpleNamespace(returncode=9)
        with patch('downloads.subprocess.run', side_effect=run):
            self.assertEqual(main(['export'] + args), 1)
        results = json.loads((out/'downloads-export.json').read_text())['entries']
        self.assertEqual(len(results), 2)
        self.assertIsNone(results[0]['exit_code'])
        self.assertEqual(results[0]['error'], 'cannot launch pipeline')
        self.assertEqual(results[1]['exit_code'], 9)

    def test_final_snapshot_guard_rejects_midrun_source_or_html_changes(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from downloads import built_assets_snapshot, digest, source_snapshot
        for changed in ['source', 'html', 'source-image', 'built-asset']:
            for operation in ['change', 'delete', 'add']:
                with self.subTest(changed=changed, operation=operation):
                    plan, site, out, args = self.export_fixture()
                    path = {'source': self.post, 'html': site/'index.html',
                            'source-image': self.root/'assets/img/diagrams/input.svg',
                            'built-asset': site/'assets/style.css'}[changed]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if not path.exists(): path.write_text('original')
                    before = path.read_text()
                    stamp = site/'.diagram-download-build.json'
                    stamp.write_text(json.dumps({'source': source_snapshot(self.root),
                        'assets': built_assets_snapshot(site, plan),
                        'html': {'index.html': digest((site/'index.html').read_bytes())}}))
                    added = path.with_name('new-input' + path.suffix)
                    def run(command, **kwargs):
                        if operation == 'change': path.write_text(before + '\nchanged during export\n')
                        elif operation == 'delete': path.unlink(missing_ok=True)
                        else: added.write_text('new input')
                        return SimpleNamespace(returncode=7)
                    with patch('downloads.subprocess.run', side_effect=run):
                        self.assertEqual(main(['export'] + args + ['--jobs', '1']), 1)
                    report = json.loads((out/'downloads-export.json').read_text())
                    self.assertEqual(report['status'], 'failed')
                    self.assertIn('changed during export/check', report['error'])
                    self.assertEqual(len(report['entries']), 2)
                    path.write_text(before); added.unlink(missing_ok=True)
                    with patch('downloads.subprocess.run', side_effect=run):
                        with self.assertRaisesRegex(ValueError, 'changed during export/check'):
                            main(['check'] + args + ['--jobs', '1'])
                    path.write_text(before); added.unlink(missing_ok=True)

    def test_target_hash_collision_fails_before_launch(self):
        from downloads import fingerprint
        from unittest.mock import patch
        plan, site, out, args = self.export_fixture()
        def collide(value):
            return '0' * 64 if 'page' in value else fingerprint(value)
        with patch('downloads.fingerprint', side_effect=collide), patch('downloads.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, 'output directory collision'):
                main(['export'] + args)
            run.assert_not_called()
        self.assertFalse((out/'downloads-export.json').exists())

    def test_source_images_are_inputs_except_exact_mapped_outputs(self):
        from downloads import source_snapshot
        plan = self.wire()
        image = self.root/'assets/img/diagrams/retained.svg'
        image.parent.mkdir(parents=True)
        image.write_text('original')
        before = source_snapshot(self.root)
        for operation in ['change', 'delete', 'add']:
            with self.subTest(operation=operation):
                if operation == 'change': image.write_text('changed')
                elif operation == 'delete': image.unlink()
                else: (image.parent/'new.svg').write_text('new')
                self.assertNotEqual(source_snapshot(self.root), before)
                image.write_text('original')
                (image.parent/'new.svg').unlink(missing_ok=True)
        output = self.root/plan['entries'][0]['png'].lstrip('/')
        output.write_bytes(b'output-is-not-a-source-input')
        self.assertEqual(source_snapshot(self.root), before)

    def test_built_asset_mutations_fail_before_export(self):
        from downloads import digest
        from unittest.mock import patch
        plan, site, out, args = self.export_fixture()
        asset = site/'assets/style.css'; asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_text('original')
        stamp = site/'.diagram-download-build.json'
        saved = json.loads(stamp.read_text())
        saved['assets']['assets/style.css'] = digest(asset.read_bytes())
        stamp.write_text(json.dumps(saved))
        for operation in ['change', 'delete', 'add']:
            with self.subTest(operation=operation), patch('downloads.subprocess.run') as run:
                if operation == 'change': asset.write_text('changed')
                elif operation == 'delete': asset.unlink()
                else: (asset.parent/'new.woff2').write_bytes(b'new')
                with self.assertRaisesRegex(ValueError, 'built assets changed'):
                    main(['export'] + args)
                run.assert_not_called()
                asset.write_text('original')
                (asset.parent/'new.woff2').unlink(missing_ok=True)

    def test_jobs_cli_accepts_only_one_through_four(self):
        self.wire()
        for jobs in ['1', '2', '3', '4']:
            with self.subTest(jobs=jobs):
                self.assertEqual(main(['source-check', '--root', str(self.root), '--jobs', jobs]), 0)
        for jobs in ['0', '5', '-1', '1.5', 'many']:
            with self.subTest(jobs=jobs), self.assertRaises(SystemExit) as exc:
                main(['source-check', '--root', str(self.root), '--jobs', jobs])
            self.assertEqual(exc.exception.code, 2)

    def test_missing_helper_fails_source_check(self):
        self.wire()
        self.post.write_text(self.original)
        with self.assertRaises(ValueError): validate_source(self.root)


if __name__ == '__main__':
    unittest.main()
