"""Real decoded-image fixtures, not simulated render receipts."""
import importlib
from io import BytesIO

from PIL import Image
import pytest


def module():
    assert importlib.util.find_spec('webp_release') is not None, 'lossless WebP adapter is missing'
    return importlib.import_module('webp_release')


def png_bytes(size=(1920, 1080)):
    image = Image.new('RGBA', size, (24, 82, 190, 255))
    image.putpixel((0, 0), (210, 35, 81, 0))
    image.putpixel((1, 0), (12, 130, 2, 77))
    out = BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def test_lossless_conversion_preserves_full_rgba_including_transparent_rgb():
    adapter = module()
    original = png_bytes()
    converted = adapter.encode_lossless(original)
    evidence = adapter.compare_pixels(original, converted)
    assert evidence['dimensions'] == [1920, 1080]
    assert evidence['pixel_equality'] == 'full-decoded-RGBA-equal'
    assert evidence['png_sha256'] != evidence['webp_sha256']
    assert evidence['rgba_sha256']


@pytest.mark.parametrize('corruption', ['invalid-png', 'small-png', 'corrupt-webp', 'altered-pixels'])
def test_invalid_or_changed_decoded_images_fail_closed(corruption):
    adapter = module()
    original = png_bytes()
    if corruption == 'invalid-png':
        with pytest.raises(ValueError): adapter.encode_lossless(b'not a PNG')
    elif corruption == 'small-png':
        with pytest.raises(ValueError): adapter.encode_lossless(png_bytes((960, 540)))
    elif corruption == 'corrupt-webp':
        with pytest.raises(ValueError): adapter.compare_pixels(original, b'RIFFbrokenWEBP')
    else:
        different = Image.new('RGBA', (1920, 1080), (1, 2, 3, 255))
        out = BytesIO(); different.save(out, format='WEBP', lossless=True)
        with pytest.raises(ValueError, match='pixels differ'): adapter.compare_pixels(original, out.getvalue())


def fixture(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import downloads
    from pipeline import digest, fingerprint
    root = tmp_path / 'root'; root.mkdir()
    def write(name, content):
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes): path.write_bytes(content)
        else: path.write_text(content)
        return path
    names = ['diagrams/example.html', 'diagrams/unused.html']
    records = []
    reviews = []
    for include in names:
        text = '<figure class="sd" id="' + Path(include).stem + '"><figcaption>Example</figcaption></figure>'
        write('_includes/' + include, text)
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080" data-source-sha256="' + digest(text.encode()) + '"><image href="/assets/img/icon.svg"/></svg>'
        write('assets/img/diagrams/fhd-svg/' + Path(include).stem + '.svg', svg)
        records.append({'include': include, 'posts': ['_posts/example.md'] if include == names[0] else [], 'reference_count': int(include == names[0])})
        reviews.append({'include': include, 'source_sha256': digest(text.encode()), 'svg_sha256': digest(svg.encode()), 'png_sha256': digest(png_bytes()), 'visual_status': 'passed', 'semantic_status': 'passed', 'actual_original_png_viewed': True, 'notes': 'TEST FIXTURE review only', 'reviewed_at': 'fixture'})
    write('_posts/example.md', '---\ntitle: Example\n---\n{% include diagrams/example.html %}\n')
    write('docs/diagram-catalog.json', json.dumps({'summary': {'post_references': 1, 'posts': 1}, 'diagrams': records}))
    downloads.main(['wire', '--root', str(root)])
    plan = downloads.validate_source(root)
    entries = [dict(plan['entries'][0], page='posts/example/index.html', png_sha256=digest(png_bytes()), dimensions=[1920,1080], include_sha256=reviews[0]['source_sha256'], receipt_sha256='a' * 64)]
    unused = [{'include': names[1], 'png': '/assets/img/diagrams/fhd-unused/unused.png', 'dimensions': [1920,1080], 'png_sha256': digest(png_bytes())}]
    for row in entries + unused: write(row['png'].lstrip('/'), png_bytes())
    write('assets/fonts/deterministic-export/NotoSansKR[wght].ttf', b'fixture font only')
    write('assets/fonts/deterministic-export/lock.json', '{"qualification":"TEST FIXTURE only"}')
    write('assets/img/icon.svg', '<svg/>')
    repo = Path(__file__).resolve().parents[3]
    # Copy the actual native renderer and plugin source as immutable test inputs.
    write('kkamji_scripts/blog/static_png/fhd_export.py', (repo / 'kkamji_scripts/blog/static_png/fhd_export.py').read_bytes())
    write('_plugins/diagram-downloads.rb', (repo / '_plugins/diagram-downloads.rb').read_bytes())
    source = downloads.source_snapshot(root)
    stamp = {'source': source, 'assets': {'assets/fonts/deterministic-export/NotoSansKR[wght].ttf': digest(b'fixture font only'), 'assets/img/icon.svg': digest(b'<svg/>')}, 'html': {'diagrams/fhd-proof/index.html': 'b' * 64}}
    review_path = write('docs/diagram-fhd-reviews.json', json.dumps({'sources': reviews}))
    native = {'schema': 2, 'status': 'export-and-check-passed', 'source_count': 2, 'reference_count': 1, 'post_count': 1, 'source_fingerprint': fingerprint(source), 'build_identity': fingerprint(stamp), 'review_file': 'docs/diagram-fhd-reviews.json', 'review_file_sha256': digest(review_path.read_bytes()), 'visual_review': 'all-sources-passed', 'semantic_review': 'all-sources-passed', 'entries': entries, 'unused_entries': unused}
    write('docs/diagram-export-release.json', json.dumps(native))
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'native test fixture'], cwd=root, check=True)
    stamp_path = tmp_path / 'native-stamp.json'; stamp_path.write_text(json.dumps(stamp))
    return root, native, stamp_path


def test_complete_conversion_preserves_native_evidence_and_all_outputs(tmp_path):
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    before = (root / 'docs/diagram-export-release.json').read_bytes()
    report = adapter.convert(root, stamp_path)
    assert report['outputs'] == 2
    assert report['source_count'] == 2
    assert (root / 'docs/diagram-export-release.json').read_bytes() == before
    for row in native['entries'] + native['unused_entries']:
        assert (root / row['png'].lstrip('/')).is_file()
        assert (root / row['png'].lstrip('/').replace('.png', '.webp')).is_file()
    assert not (root / 'docs/diagram-webp-release.json').exists(), 'conversion must not claim a built release'


def built_fixture(root, native, site, *, cover=False):
    import json
    import shutil
    import downloads
    from pipeline import digest
    site.mkdir()
    shutil.copytree(root / 'assets', site / 'assets')
    page = site / 'posts/example/index.html'; page.parent.mkdir(parents=True)
    png = native['entries'][0]['png']; webp = downloads.webp_url(png)
    if cover:
        text = f'<img class="cover" src="{webp}">'
    else:
        text = f'<figure class="sd" id="example"></figure><p class="diagram-download"><img class="diagram-inline" src="{webp}" alt="" data-static-diagram="true" width="1920" height="1080"><a href="{webp}" download>WebP</a><a href="{downloads.viewer_url(webp)}">Open</a></p>'
        viewer = site / downloads.viewer_url(webp).lstrip('/'); viewer.parent.mkdir(parents=True)
        viewer.write_text(f'<img class="diagram-canvas" src="{webp}" width="1920" height="1080"><a href="{webp}" download>WebP</a>')
    page.write_text(text)
    sidecar = site / 'assets/data/diagram-posts.json'; sidecar.parent.mkdir(parents=True)
    sidecar.write_text(json.dumps({'_posts/example.md': '/posts/example/'}))
    plan = downloads.validate_source(root)
    stamp = {'source': downloads.source_snapshot(root), 'assets': downloads.built_assets_snapshot(site, plan), 'html': {p.relative_to(site).as_posix(): digest(p.read_bytes()) for p in site.rglob('*.html')}}
    (site / '.diagram-download-build.json').write_text(json.dumps(stamp))
    return page


def test_seal_binds_current_build_without_changing_prior_native_identity(tmp_path):
    import json
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    delivery_css = root / 'assets/css/delivery.scss'; delivery_css.parent.mkdir(parents=True)
    delivery_css.write_text('.diagram-inline { max-width: 100%; height: auto; }')
    adapter.convert(root, stamp_path)
    site = tmp_path / 'site'; built_fixture(root, native, site)
    report = adapter.seal(root, site, stamp_path)
    assert report['outputs'] == 2
    manifest = json.loads((root / adapter.MANIFEST).read_text())
    assert manifest['native_baseline']['source_fingerprint'] == native['source_fingerprint']
    assert manifest['native_baseline']['build_identity'] == native['build_identity']
    assert manifest['native_baseline']['source_fingerprint'] != manifest['source_fingerprint']
    assert len(manifest['body_entries']) == 1
    assert len(manifest['unused_sources']) == 1
    assert manifest['browser_evidence']['status'] == 'not-recorded-by-this-adapter'
    assert adapter.check(root, site)['passed'] is True


def test_body_to_cover_reclassification_uses_existing_native_output(tmp_path):
    import json
    import downloads
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    png = native['entries'][0]['png']; webp = downloads.webp_url(png)
    (root / '_posts/example.md').write_text(f'---\ntitle: Example\nimage:\n  path: {webp}\n  alt: Example cover\n---\nNo duplicate body figure.\n')
    catalog_file = root / 'docs/diagram-catalog.json'; catalog = json.loads(catalog_file.read_text())
    catalog['summary'] = {'post_references': 0, 'posts': 0}
    catalog['diagrams'][0].update(posts=[], reference_count=0)
    catalog_file.write_text(json.dumps(catalog))
    downloads.main(['wire', '--root', str(root)])
    adapter.convert(root, stamp_path)
    site = tmp_path / 'site'; built_fixture(root, native, site, cover=True)
    adapter.seal(root, site, stamp_path)
    manifest = json.loads((root / adapter.MANIFEST).read_text())
    assert manifest['body_entries'] == []
    assert manifest['cover_entries'][0]['png'] == png
    assert len(manifest['outputs']) == 2
    assert len(manifest['unused_sources']) == 2  # Body-unused, including explicit cover.
    assert sum(row['cover_used'] for row in manifest['unused_sources']) == 1
    assert not (root / 'assets/img/diagrams/fhd-unused/example.webp').exists()


def test_normal_stage_gate_delegates_to_derivative_release_and_checks_index(tmp_path):
    import subprocess
    from release_manifest import verify_staged, staged_requires_verification
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    adapter.convert(root, stamp_path)
    site = tmp_path / 'site'; built_fixture(root, native, site)
    adapter.seal(root, site, stamp_path)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    assert staged_requires_verification(root)
    assert verify_staged(root)['passed'] is True
    derivative = root / native['entries'][0]['png'].lstrip('/').replace('.png', '.webp')
    derivative.write_bytes(derivative.read_bytes() + b'unstaged')
    with pytest.raises(ValueError, match='index|bytes|coverage'):
        verify_staged(root)


def test_new_derivative_manifest_and_cover_url_enter_the_staged_trigger(tmp_path, monkeypatch):
    import release_manifest
    root, native, stamp_path = fixture(tmp_path)
    monkeypatch.setattr(release_manifest.subprocess, 'check_output', lambda *a, **kw: 'docs/diagram-webp-release.json\n')
    assert release_manifest.staged_requires_verification(root)
    replies = iter(['_posts/example.md\n', '+  path: /assets/img/diagrams/example--0123456789abcdef.webp\n'])
    monkeypatch.setattr(release_manifest.subprocess, 'check_output', lambda *a, **kw: next(replies))
    assert release_manifest.staged_requires_verification(root)


def test_pixel_equality_does_not_accept_a_lossy_webp_container():
    adapter = module()
    original = BytesIO(); Image.new('RGB', (1920, 1080), (0, 0, 0)).save(original, format='PNG')
    lossy = BytesIO(); Image.new('RGB', (1920, 1080), (0, 0, 0)).save(lossy, format='WEBP', lossless=False, quality=100)
    with pytest.raises(ValueError, match='lossless'):
        adapter.compare_pixels(original.getvalue(), lossy.getvalue())


def test_nested_tool_and_model_manifest_are_rooted_release_inputs(tmp_path):
    import downloads
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    adapter.convert(root, stamp_path)
    site = tmp_path / 'site'; built_fixture(root, native, site)
    adapter.seal(root, site, stamp_path)
    nested = root / 'kkamji_scripts/blog/static_png/models/new-render-input.json'
    nested.parent.mkdir(parents=True); nested.write_text('{"model_url":"https://example.invalid/new-model"}')
    assert nested.relative_to(root).as_posix() in downloads.source_snapshot(root)
    with pytest.raises(ValueError, match='source'):
        adapter.check(root, site)


@pytest.mark.parametrize('target', ['include', 'svg', 'font', 'image', 'renderer', 'proof-style', 'native-png', 'native-baseline', 'reviews', 'stamp'])
def test_stale_native_evidence_blocks_before_any_derivative_is_written(tmp_path, target):
    import json
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    targets = {'include': '_includes/diagrams/example.html', 'svg': 'assets/img/diagrams/fhd-svg/example.svg',
               'font': 'assets/fonts/deterministic-export/NotoSansKR[wght].ttf', 'image': 'assets/img/icon.svg',
               'renderer': 'kkamji_scripts/blog/static_png/fhd_export.py', 'proof-style': '_plugins/diagram-downloads.rb',
               'native-png': native['entries'][0]['png'].lstrip('/'), 'native-baseline': adapter.NATIVE, 'reviews': adapter.REVIEWS}
    if target == 'stamp':
        stamp = json.loads(stamp_path.read_text()); stamp['source']['newly-rebased-input'] = 'a' * 64
        stamp_path.write_text(json.dumps(stamp))
    elif target == 'proof-style':
        path = root / targets[target]; path.write_text(path.read_text().replace('h2{font-size:16px}', 'h2{font-size:15px}'))
    else:
        path = root / targets[target]; path.write_bytes(path.read_bytes() + b'\nchanged native input\n')
    with pytest.raises(ValueError): adapter.convert(root, stamp_path)
    assert not list((root / 'assets/img/diagrams').rglob('*.webp'))
    assert not (root / adapter.MANIFEST).exists()


@pytest.mark.parametrize('damage', ['missing-webp', 'corrupt-webp', 'altered-webp', 'missing-output-row', 'missing-unused', 'changed-source', 'changed-html', 'changed-built-asset'])
def test_derivative_release_fails_closed_on_missing_changed_or_incomplete_evidence(tmp_path, damage):
    import json
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    adapter.convert(root, stamp_path)
    site = tmp_path / 'site'; page = built_fixture(root, native, site)
    adapter.seal(root, site, stamp_path)
    webp = root / native['entries'][0]['png'].lstrip('/').replace('.png', '.webp')
    if damage == 'missing-webp': webp.unlink()
    elif damage == 'corrupt-webp': webp.write_bytes(b'RIFFbrokenWEBP')
    elif damage == 'altered-webp':
        changed = Image.open(BytesIO(png_bytes())).convert('RGBA'); changed.putpixel((10, 10), (9, 8, 7, 255))
        out = BytesIO(); changed.save(out, format='PNG'); webp.write_bytes(adapter.encode_lossless(out.getvalue()))
    elif damage in ('missing-output-row', 'missing-unused'):
        path = root / adapter.MANIFEST; payload = json.loads(path.read_text())
        payload['outputs' if damage == 'missing-output-row' else 'unused_sources'].pop()
        path.write_text(json.dumps(payload))
    elif damage == 'changed-source': (root / '_posts/example.md').write_text((root / '_posts/example.md').read_text() + 'new prose')
    elif damage == 'changed-html': page.write_text(page.read_text() + 'changed build')
    else:
        built = site / webp.relative_to(root); built.write_bytes(built.read_bytes() + b'changed')
    with pytest.raises((ValueError, OSError)): adapter.check(root, site)


def test_symlinked_output_directory_cannot_escape_the_root(tmp_path):
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    png = root / native['entries'][0]['png'].lstrip('/')
    original = png.read_bytes(); png.unlink()
    outside = tmp_path / 'outside'; outside.mkdir()
    replacement = outside / png.name; replacement.write_bytes(original)
    png.symlink_to(replacement)
    with pytest.raises(ValueError, match='symlink|escapes'): adapter.convert(root, stamp_path)
    assert not list(outside.glob('*.webp'))


def test_index_assume_unchanged_does_not_hide_unstaged_release_bytes(tmp_path):
    import subprocess
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    adapter.convert(root, stamp_path)
    site = tmp_path / 'site'; built_fixture(root, native, site)
    adapter.seal(root, site, stamp_path)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    subprocess.run(['git', 'update-index', '--assume-unchanged', adapter.MANIFEST], cwd=root, check=True)
    # JSON whitespace is semantically neutral but still not the approved index.
    manifest = root / adapter.MANIFEST; manifest.write_text(manifest.read_text() + '\n')
    with pytest.raises(ValueError, match='index'):
        adapter.verify_staged(root)


def test_source_only_gate_rejects_tampered_post_page_ownership(tmp_path):
    import json
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    adapter.convert(root, stamp_path)
    site = tmp_path / 'site'; built_fixture(root, native, site)
    adapter.seal(root, site, stamp_path)
    path = root / adapter.MANIFEST; saved = json.loads(path.read_text())
    saved['body_entries'][0]['page'] = next(page for page in saved['build']['html'] if page.startswith('diagrams/view/'))
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match='ownership|identity|coverage'):
        adapter.check(root)


def test_cli_convert_seal_check_and_index_gate_execute_on_real_fixture_bytes(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    script = Path(adapter.__file__)
    def cli(action, *extra):
        return subprocess.run([sys.executable, '-B', str(script), action, '--root', str(root), *map(str, extra)], capture_output=True, text=True)
    converted = cli('convert', '--native-stamp', stamp_path)
    assert converted.returncode == 0, converted.stderr
    assert json.loads(converted.stdout)['outputs'] == 2
    site = tmp_path / 'site'; built_fixture(root, native, site)
    sealed = cli('seal', '--site', site, '--native-stamp', stamp_path)
    assert sealed.returncode == 0, sealed.stderr
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    checked = cli('check', '--site', site, '--staged')
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)['passed'] is True
    absent_stamp = cli('convert')
    assert absent_stamp.returncode == 2 and '--native-stamp is required' in absent_stamp.stderr
    (root / adapter.MANIFEST).unlink()
    blocked = cli('check', '--site', site)
    assert blocked.returncode == 1 and 'WebP release blocked:' in blocked.stderr


@pytest.mark.parametrize('action', ['convert', 'seal'])
def test_a_different_lossless_encoder_cannot_be_claimed_as_method6(tmp_path, action):
    import downloads
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    for row in native['entries'] + native['unused_entries']:
        image = Image.open(BytesIO(png_bytes())).convert('RGBA')
        alternate = BytesIO(); image.save(alternate, format='WEBP', lossless=True, method=0, exact=True)
        assert alternate.getvalue() != adapter.encode_lossless(png_bytes())
        (root / downloads.webp_url(row['png']).lstrip('/')).write_bytes(alternate.getvalue())
    if action == 'convert':
        with pytest.raises(ValueError, match='encoding|method'): adapter.convert(root, stamp_path)
    else:
        site = tmp_path / 'site'; built_fixture(root, native, site)
        with pytest.raises(ValueError, match='encoding|method'): adapter.seal(root, site, stamp_path)
    assert not (root / adapter.MANIFEST).exists()


@pytest.mark.parametrize('change', ['deleted-font-record', 'extra-unreviewed-svg'])
def test_native_artifact_and_font_input_sets_cannot_be_silently_redefined(tmp_path, change):
    adapter = module()
    root, native, stamp_path = fixture(tmp_path)
    if change == 'deleted-font-record': (root / 'assets/fonts/deterministic-export/lock.json').unlink()
    else: (root / 'assets/img/diagrams/fhd-svg/unreviewed.svg').write_text('<svg/>')
    with pytest.raises((ValueError, OSError)): adapter.convert(root, stamp_path)
    assert not list((root / 'assets/img/diagrams').rglob('*.webp'))


def test_invalid_png_chunk_crc_is_not_treated_as_valid_decoded_pixels():
    adapter = module()
    raw = bytearray(png_bytes()); offset = 8
    while offset < len(raw):
        length = int.from_bytes(raw[offset:offset+4], 'big')
        if raw[offset+4:offset+8] == b'IDAT':
            raw[offset+8+length] ^= 1
            break
        offset += length + 12
    with pytest.raises(ValueError): adapter.encode_lossless(bytes(raw))
