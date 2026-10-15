"""Real additive conversion/build/index roundtrips with synthetic TEST receipts."""
import copy
import json
import shutil
import subprocess

import pytest

import downloads
import webp_release as w
from pipeline import digest
from test_native_additions import addition
from test_native_update import delta


def built_site(s, site):
    site.mkdir(); shutil.copytree(s.root / 'assets', site / 'assets')
    plan = downloads.validate_source(s.root); urls = {}
    for entry in plan['entries']:
        name = entry['post'].rsplit('/', 1)[-1].removesuffix('.md')
        page = site / ('posts/' + name + '/index.html'); page.parent.mkdir(parents=True)
        urls[entry['post']] = '/posts/' + name + '/'
        webp = downloads.webp_url(entry['png']); viewer = downloads.viewer_url(webp)
        page.write_text(f'<figure class="sd" id="{entry["figure"]}"></figure>'
                        f'<p class="diagram-download"><img class="diagram-inline" src="{webp}" alt="" '
                        f'data-static-diagram="true" width="1920" height="1080"><a href="{webp}" download>WebP</a>'
                        f'<a href="{viewer}">Open</a></p>')
        path = site / viewer[1:]; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'<img src="{webp}" width="1920" height="1080"><a href="{webp}" download>WebP</a>')
    path = site / 'assets/data/diagram-posts.json'; path.parent.mkdir(parents=True)
    path.write_text(json.dumps(urls))
    stamp = {'source': downloads.source_snapshot(s.root),
             'assets': downloads.built_assets_snapshot(site, plan),
             'html': {p.relative_to(site).as_posix(): digest(p.read_bytes()) for p in site.rglob('*.html')}}
    (site / '.diagram-download-build.json').write_text(json.dumps(stamp))


def test_additive_roundtrip_preserves_original_archive_and_seals_all_active_outputs(addition):
    s = addition
    original_stamp = s.stamp_path.read_bytes()
    native = w.checked_native(s.root, s.stamp, s.manifest['base_revision'])
    assert len(native['rows']) == 3
    assert native['source_count'] == 3
    assert native['baseline'] == s.baseline
    assert set(native['additions']['sources']) == {s.row['include']}
    assert w.convert(s.root, s.stamp_path, s.manifest['base_revision'])['source_count'] == 3
    assert not (s.root / w.MANIFEST).exists()
    snapshot = downloads.source_snapshot(s.root)
    for key in ('receipt', 'review', 'render_build', 'render_fixture'):
        assert s.row[key + '_file'] in snapshot
    assert 'docs/diagram-native-additions.json' in snapshot
    paths = downloads.delivery_output_paths(s.root, downloads.validate_source(s.root))
    assert s.row['png'][1:] in paths
    assert downloads.webp_url(s.row['png'])[1:] in paths
    assert not paths.intersection(snapshot)
    site = s.root.parent / 'delivery-site'; built_site(s, site)
    assert w.seal(s.root, site, s.stamp_path, s.manifest['base_revision'])['outputs'] == 3
    saved = json.loads((s.root / w.MANIFEST).read_text())
    assert saved['source_count'] == saved['output_count'] == 3
    assert saved['native_baseline']['build_identity'] == s.baseline['build_identity']
    assert saved['native_build_stamp'] == s.stamp
    assert saved['native_additions']['added_sources'] == [s.row['include']]
    assert saved['reference_count'] == 2
    assert len(saved['unused_sources']) == 1
    assert all('old_png' not in row for row in saved['body_entries'])
    assert w.check(s.root, site)['passed'] and w.check(s.root)['passed']
    subprocess.run(['git', 'add', '.'], cwd=s.root, check=True)  # private test repo
    assert w.verify_staged(s.root)['indexed'] is True
    assert s.stamp_path.read_bytes() == original_stamp
    for path, raw in s.archived.items():
        assert (s.root / path).read_bytes() == raw
        assert saved['native_archive_inputs'].get(path, digest(raw)) == digest(raw)


@pytest.mark.parametrize('key', ['manifest', 'receipt', 'review', 'render_build', 'render_fixture'])
def test_additions_exact_proof_paths_trigger_required_staged_gate(addition, key):
    from release_manifest import staged_requires_verification
    s = addition
    relative = 'docs/diagram-native-additions.json' if key == 'manifest' else s.row[key + '_file']
    subprocess.run(['git', 'add', '--', relative], cwd=s.root, check=True)  # private test repo
    assert staged_requires_verification(s.root)


def test_unrelated_document_does_not_expand_the_staged_diagram_trigger(addition):
    from release_manifest import staged_requires_verification
    path = addition.root / 'docs/unrelated.json'; path.write_text('{}')
    subprocess.run(['git', 'add', '--', 'docs/unrelated.json'], cwd=addition.root, check=True)
    assert not staged_requires_verification(addition.root)


@pytest.mark.parametrize('damage', ['post', 'include', 'figure', 'instance', 'occurrence',
                                  'png', 'old_png', 'unvalidated', 'inactive', 'omitted'])
def test_addition_usage_requires_exact_authenticated_occurrence(addition, damage):
    s = addition
    native = w.checked_native(s.root, s.stamp, s.manifest['base_revision'])
    plan = downloads.validate_source(s.root)
    entry = next(row for row in plan['entries'] if row['include'] == s.row['include'])
    if damage in ('post', 'include', 'figure', 'instance'):
        entry[damage] = {'post': '_posts/elsewhere.md', 'include': 'diagrams/example.html',
                         'figure': 'elsewhere', 'instance': 'elsewhere'}[damage]
    elif damage == 'occurrence': entry['occurrence'] = 2
    elif damage == 'png': entry['png'] = s.baseline['entries'][0]['png']
    elif damage == 'old_png': entry['old_png'] = entry['png']
    elif damage == 'unvalidated': native['additions'] = None
    elif damage == 'inactive': native['rows'].pop(entry['png'])
    else: plan['entries'].remove(entry)
    with pytest.raises(ValueError, match='native|coverage'):
        w.usage_bindings(s.root, plan, native)


def test_every_proof_archive_source_and_output_uses_actual_index_blobs(addition):
    s = addition
    w.convert(s.root, s.stamp_path, s.manifest['base_revision'])
    site = s.root.parent / 'delivery-site'; built_site(s, site)
    w.seal(s.root, site, s.stamp_path, s.manifest['base_revision'])
    subprocess.run(['git', 'add', '.'], cwd=s.root, check=True)
    bad = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'], cwd=s.root,
                                  input=b'TEST index divergence only').decode().strip()
    paths = {s.source, s.svg, s.row['png'][1:], downloads.webp_url(s.row['png'])[1:],
             w.MANIFEST, w.NATIVE, w.REVIEWS, 'docs/diagram-native-additions.json',
             'docs/diagram-catalog.json', downloads.MANIFEST, s.row['post']}
    paths.update(s.row[key + '_file'] for key in ('receipt', 'review', 'render_build', 'render_fixture'))
    paths.update(row['png'][1:] for row in s.baseline['entries'] + s.baseline['unused_entries'])
    for relative in sorted(paths):
        subprocess.run(['git', 'update-index', '--cacheinfo', '100644,' + bad + ',' + relative], cwd=s.root, check=True)
        with pytest.raises(ValueError, match='index differs'): w.verify_staged(s.root)
        subprocess.run(['git', 'add', '--', relative], cwd=s.root, check=True)
    assert w.verify_staged(s.root)['indexed'] is True


def test_additions_coexist_with_existing_replacements_without_rewriting_either(delta):
    from test_native_additions import add_source
    replacement = delta
    s = add_source(delta.root, delta.baseline, delta.root.parent / 'native-stamp.json')
    update_raw = (s.root / 'docs/diagram-native-update.json').read_bytes()
    native = w.checked_native(s.root, s.stamp, s.manifest['base_revision'])
    assert len(native['rows']) == 3 and native['source_count'] == 3
    assert s.row['png'] in native['rows'] and replacement.row['new_png'] in native['rows']
    assert replacement.row['old_png'] not in native['rows']
    assert w.convert(s.root, s.stamp_path, s.manifest['base_revision'])['outputs'] == 3
    site = s.root.parent / 'delivery-site'; built_site(s, site)
    w.seal(s.root, site, s.stamp_path, s.manifest['base_revision'])
    saved = json.loads((s.root / w.MANIFEST).read_text())
    assert saved['native_update']['changed_sources'] == [replacement.row['include']]
    assert saved['native_additions']['added_sources'] == [s.row['include']]
    assert w.check(s.root, site)['passed'] is True
    subprocess.run(['git', 'add', '.'], cwd=s.root, check=True)
    assert w.verify_staged(s.root)['indexed'] is True
    assert (s.root / 'docs/diagram-native-update.json').read_bytes() == update_raw
    for path, raw in s.archived.items(): assert (s.root / path).read_bytes() == raw
