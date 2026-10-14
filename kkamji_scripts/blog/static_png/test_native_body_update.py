"""Used-body native deltas: real image/Git roundtrip, synthetic review metadata only."""
import copy
import json
import subprocess

import pytest

import downloads
import webp_release as w
from pipeline import digest
from test_native_update import delta
from test_webp_release import built_fixture, fixture


def test_used_body_update_roundtrip_keeps_immutable_archive_and_checks_index(delta):
    s = delta
    root = s.root
    stamp_path = root.parent / 'native-stamp.json'
    mapping = json.loads((root / downloads.MANIFEST).read_text())
    original_entry = mapping['entries'][0]
    preserved = {path: (root / path).read_bytes() for path in
                 (w.NATIVE, w.REVIEWS, s.row['old_png'][1:])}
    original_stamp = stamp_path.read_bytes()
    old_webp = root / downloads.webp_url(s.row['old_png'])[1:]
    old_webp.write_bytes(w.encode_lossless(preserved[s.row['old_png'][1:]]))
    preserved[old_webp.relative_to(root).as_posix()] = old_webp.read_bytes()
    prose = downloads.HELPER.sub('', (root / '_posts/example.md').read_text())

    assert downloads.main(['wire', '--root', str(root)]) == 0
    plan = downloads.validate_source(root)
    entry = plan['entries'][0]
    assert entry['png'] == s.row['new_png']
    assert entry['old_png'] == s.row['old_png']
    assert entry == dict(original_entry, png=s.row['new_png'], old_png=s.row['old_png'])
    post = (root / '_posts/example.md').read_text()
    assert downloads.HELPER.sub('', post) == prose
    assert post.count(downloads.helper(entry)) == 1
    assert '{% include diagrams/example.html %}\n' + downloads.helper(entry) in post
    assert s.row['old_png'] not in post
    assert downloads.main(['wire', '--root', str(root)]) == 0
    assert (root / '_posts/example.md').read_text() == post

    paths = downloads.delivery_output_paths(root, plan)
    for png in (s.row['old_png'], s.row['new_png']):
        assert png[1:] in paths
        assert downloads.webp_url(png)[1:] in paths
    snapshot = downloads.source_snapshot(root)
    assert 'docs/diagram-native-update.json' in snapshot
    assert s.source in snapshot and s.svg in snapshot
    assert not paths.intersection(snapshot)

    native = w.checked_native(root, s.old, s.manifest['base_revision'])
    assert s.row['new_png'] in native['rows']
    assert s.row['old_png'] not in native['rows']
    assert w.convert(root, stamp_path, s.manifest['base_revision'])['outputs'] == 2
    assert not (root / w.MANIFEST).exists()
    built_native = copy.deepcopy(s.baseline)
    built_native['entries'][0]['png'] = s.row['new_png']
    site = root.parent / 'delivery-site'
    built_fixture(root, built_native, site)
    assert w.seal(root, site, stamp_path, s.manifest['base_revision'])['outputs'] == 2
    saved = json.loads((root / w.MANIFEST).read_text())
    body = saved['body_entries'][0]
    assert body['png'] == s.row['new_png']
    assert body['old_png'] == s.row['old_png']
    assert body['webp'] == downloads.webp_url(s.row['new_png'])
    assert body['page'] == 'posts/example/index.html'
    assert {row['png'] for row in saved['outputs']} == set(native['rows'])
    for row in saved['outputs']:
        assert row['dimensions'] == [1920, 1080]
        assert row['pixel_equality'] == 'full-decoded-RGBA-equal'
    assert saved['native_build_stamp'] == s.old
    assert saved['native_baseline']['build_identity'] == s.baseline['build_identity']
    assert saved['native_baseline']['source_fingerprint'] == s.baseline['source_fingerprint']
    assert saved['native_archive_inputs'][s.row['old_png'][1:]] == digest(preserved[s.row['old_png'][1:]])
    assert w.check(root, site)['passed'] is True
    assert w.check(root)['passed'] is True

    from release_manifest import verify_staged
    with pytest.raises(ValueError, match='index'):
        verify_staged(root)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    assert verify_staged(root)['indexed'] is True
    bad_oid = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'], cwd=root,
                                      input=b'TEST index divergence only').decode().strip()
    for path in (s.row['old_png'][1:], s.row['new_png'][1:], s.row['receipt_file'],
                 downloads.webp_url(s.row['new_png'])[1:], downloads.MANIFEST, w.MANIFEST):
        subprocess.run(['git', 'update-index', '--cacheinfo', '100644,' + bad_oid + ',' + path],
                       cwd=root, check=True)
        with pytest.raises(ValueError, match='index differs'):
            verify_staged(root)
        subprocess.run(['git', 'add', '--', path], cwd=root, check=True)
    assert verify_staged(root)['passed'] is True
    assert stamp_path.read_bytes() == original_stamp
    for path, raw in preserved.items():
        assert (root / path).read_bytes() == raw
    for path in (w.NATIVE, w.REVIEWS):
        assert w._git_blob(root, s.manifest['base_revision'], path) == preserved[path]


def test_legacy_mapping_is_unchanged_without_delta(tmp_path, monkeypatch):
    # Reuse the delta fixture's hermetic Git policy without invoking its update.
    import os
    for name in tuple(os.environ):
        if name.startswith('GIT_'):
            monkeypatch.delenv(name)
    for name, value in {'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
                        'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.hooksPath',
                        'GIT_CONFIG_VALUE_0': '/dev/null'}.items():
        monkeypatch.setenv(name, value)
    root, baseline, _ = fixture(tmp_path)
    before = (root / downloads.MANIFEST).read_bytes()
    post = (root / '_posts/example.md').read_bytes()
    assert downloads.discover(root)[0]['entries'] == [
        {key: value for key, value in baseline['entries'][0].items()
         if key not in ('page', 'png_sha256', 'dimensions', 'include_sha256', 'receipt_sha256')}]
    assert downloads.main(['wire', '--root', str(root)]) == 0
    assert (root / downloads.MANIFEST).read_bytes() == before
    assert (root / '_posts/example.md').read_bytes() == post


@pytest.mark.parametrize('damage', ['missing-old', 'wrong-old', 'old-output', 'other-output',
                                  'post', 'include', 'figure', 'unvalidated', 'inactive'])
def test_body_update_cannot_divert_original_occurrence(delta, damage):
    s = delta
    downloads.main(['wire', '--root', str(s.root)])
    plan = downloads.validate_source(s.root)
    native = w.checked_native(s.root, s.old, s.manifest['base_revision'])
    entry = plan['entries'][0]
    if damage == 'missing-old': entry.pop('old_png')
    elif damage == 'wrong-old': entry['old_png'] = s.baseline['unused_entries'][0]['png']
    elif damage == 'old-output': entry['png'] = s.row['old_png']
    elif damage == 'other-output': entry['png'] = s.baseline['unused_entries'][0]['png']
    elif damage == 'post': entry['post'] = '_posts/other.md'
    elif damage == 'include': entry['include'] = 'diagrams/unused.html'
    elif damage == 'figure': entry['figure'] = 'other'
    elif damage == 'unvalidated': native['update'] = None
    elif damage == 'inactive': native['rows'].pop(s.row['new_png'])
    with pytest.raises(ValueError, match='exact.*native'):
        w.usage_bindings(s.root, plan, native)


@pytest.mark.parametrize('damage', ['unsafe-url', 'non-update-url', 'archive-collision',
                                  'other-include', 'other-old', 'duplicate', 'baseline-hash'])
def test_invalid_update_declaration_blocks_wire_before_post_writes(delta, damage):
    s = delta
    if damage == 'unsafe-url': s.row['new_png'] = 'https://example.invalid/divert.png'
    elif damage == 'non-update-url': s.row['new_png'] = '/assets/img/diagrams/divert.png'
    elif damage == 'archive-collision': s.row['new_png'] = s.row['old_png']
    elif damage == 'other-include': s.row['include'] = 'diagrams/unused.html'
    elif damage == 'other-old': s.row['old_png'] = s.baseline['unused_entries'][0]['png']
    elif damage == 'duplicate': s.manifest['sources'].append(copy.deepcopy(s.row))
    elif damage == 'baseline-hash': s.manifest['base_manifest_sha256'] = '0' * 64
    s.save()
    before = {path: (s.root / path).read_bytes() for path in
              ('_posts/example.md', downloads.MANIFEST)}
    with pytest.raises(ValueError):
        downloads.main(['wire', '--root', str(s.root)])
    assert before == {path: (s.root / path).read_bytes() for path in before}


def test_safe_routing_declaration_does_not_replace_native_receipt_authentication(delta):
    s = delta
    s.receipt['automated_status'] = 'failed'
    s.save()
    downloads.main(['wire', '--root', str(s.root)])
    assert downloads.validate_source(s.root)['entries'][0]['png'] == s.row['new_png']
    with pytest.raises(ValueError, match='receipt'):
        w.convert(s.root, s.root.parent / 'native-stamp.json', s.manifest['base_revision'])
    assert not list((s.root / 'assets/img/diagrams').rglob('*.webp'))
    assert not (s.root / w.MANIFEST).exists()
