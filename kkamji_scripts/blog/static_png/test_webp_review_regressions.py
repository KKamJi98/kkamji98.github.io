"""Refute-first release boundary regressions using real image/Git fixtures."""
import json
import subprocess

import pytest

from test_webp_release import fixture, built_fixture, module


def test_manifest_cannot_change_between_validation_and_index_check(tmp_path, monkeypatch):
    adapter = module()
    root, native, stamp = fixture(tmp_path)
    adapter.convert(root, stamp)
    site = tmp_path / 'site'
    built_fixture(root, native, site)
    adapter.seal(root, site, stamp)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    real_check = adapter.check

    def mutate_after_valid_check(path, *args, **kwargs):
        result = real_check(path, *args, **kwargs)
        manifest = root / adapter.MANIFEST
        payload = json.loads(manifest.read_text())
        payload['outputs'] = []
        manifest.write_text(json.dumps(payload))
        subprocess.run(['git', 'add', adapter.MANIFEST], cwd=root, check=True)
        relative = native['entries'][0]['png'][1:].replace('.png', '.webp')
        oid = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'], cwd=root, input=b'corrupt indexed derivative').decode().strip()
        subprocess.run(['git', 'update-index', '--cacheinfo', f'100644,{oid},{relative}'], cwd=root, check=True)
        return result

    monkeypatch.setattr(adapter, 'check', mutate_after_valid_check)
    with pytest.raises(ValueError, match='manifest|index'):
        adapter.verify_staged(root)


def test_manifest_bytes_are_pinned_through_real_check(tmp_path, monkeypatch):
    adapter = module()
    root, native, stamp = fixture(tmp_path)
    adapter.convert(root, stamp)
    site = tmp_path / 'site'
    built_fixture(root, native, site)
    adapter.seal(root, site, stamp)
    real_payload = adapter._payload

    def mutate_after_payload(*args, **kwargs):
        result = real_payload(*args, **kwargs)
        path = root / adapter.MANIFEST
        path.write_bytes(path.read_bytes() + b'\n')
        return result

    monkeypatch.setattr(adapter, '_payload', mutate_after_payload)
    with pytest.raises(ValueError, match='manifest'):
        adapter.check(root)


def test_cover_srcset_cannot_substitute_a_different_selected_image(tmp_path):
    import downloads
    from pipeline import digest
    adapter = module()
    root, native, stamp = fixture(tmp_path)
    webp = downloads.webp_url(native['entries'][0]['png'])
    (root / '_posts/example.md').write_text(f'---\ntitle: Example\nimage:\n  path: {webp}\n---\nCover only.\n')
    catalog = root / 'docs/diagram-catalog.json'
    data = json.loads(catalog.read_text())
    data['summary'] = {'post_references': 0, 'posts': 0}
    data['diagrams'][0].update(posts=[], reference_count=0)
    catalog.write_text(json.dumps(data))
    downloads.main(['wire', '--root', str(root)])
    adapter.convert(root, stamp)
    site = tmp_path / 'site'
    page = built_fixture(root, native, site, cover=True)
    page.write_text(page.read_text().replace('<img ', '<img srcset="/assets/img/icon.svg 1x" ', 1))
    build = site / '.diagram-download-build.json'
    data = json.loads(build.read_text())
    data['html'][page.relative_to(site).as_posix()] = digest(page.read_bytes())
    build.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='cover|srcset'):
        adapter.seal(root, site, stamp)
