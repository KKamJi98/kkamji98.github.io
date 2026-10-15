"""Additive admission uses real bytes/Git and explicitly synthetic TEST reviews."""
import copy
import importlib
import importlib.util
import json
import os
from html import escape
from io import BytesIO
from types import SimpleNamespace

from PIL import Image
import pytest

import downloads
import webp_release as w
from fhd_reuse import FONT, PROOF, renderer_literal
from pipeline import digest, fingerprint
from test_webp_release import fixture


def module():
    assert importlib.util.find_spec('native_additions'), 'additive native admission is missing'
    return importlib.import_module('native_additions')


@pytest.fixture
def addition(tmp_path, monkeypatch):
    # Private fixture repositories only. Never stage or commit the working repo.
    for name in tuple(os.environ):
        if name.startswith('GIT_'): monkeypatch.delenv(name)
    for name, value in {'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
                        'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.hooksPath',
                        'GIT_CONFIG_VALUE_0': '/dev/null'}.items(): monkeypatch.setenv(name, value)
    root, baseline, stamp_path = fixture(tmp_path)
    return add_source(root, baseline, stamp_path)


def add_source(root, baseline, stamp_path):
    """Append test bytes to either the unchanged or replacement fixture corpus."""
    stamp = json.loads(stamp_path.read_text())
    archived = {row['png'][1:]: (root / row['png'][1:]).read_bytes()
                for row in baseline['entries'] + baseline['unused_entries']}
    archived.update({path: (root / path).read_bytes() for path in (w.NATIVE, w.REVIEWS)})
    include = 'diagrams/static/addition.html'
    source = '_includes/' + include
    text = '<figure class="sd" id="addition"><figcaption>New TEST relationship</figcaption></figure>'
    path = root / source; path.parent.mkdir(parents=True); path.write_text(text)
    svg = 'assets/img/diagrams/fhd-svg/static/addition.svg'
    artwork = ('<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" '
               'viewBox="0 0 1920 1080" data-source-sha256="' + digest(text.encode()) + '">'
               '<rect width="1920" height="1080" fill="white"/></svg>')
    path = root / svg; path.parent.mkdir(parents=True); path.write_text(artwork)
    post = root / '_posts/addition.md'
    post.write_text('---\ntitle: Addition TEST only\n---\n{% include ' + include + ' %}\n')
    catalog_path = root / 'docs/diagram-catalog.json'
    catalog = json.loads(catalog_path.read_text())
    catalog['diagrams'].append({'include': include, 'posts': ['_posts/addition.md'], 'reference_count': 1})
    catalog['summary'] = {'post_references': 2, 'posts': 2}
    catalog_path.write_text(json.dumps(catalog))
    downloads.main(['wire', '--root', str(root)])
    entry = next(row for row in downloads.validate_source(root)['entries'] if row['include'] == include)
    out = BytesIO(); Image.new('RGBA', (1920, 1080), (255, 255, 255, 255)).save(out, format='PNG')
    path = root / entry['png'][1:]; path.parent.mkdir(parents=True); path.write_bytes(out.getvalue())
    directory = 'docs/diagram-native-additions/20990101/'
    proof_text = ('<style>' + w.proof_style((root / w.PLUGIN).read_bytes()) + '</style>'
                  '<section class="proof-card" data-index="2" data-include="' + escape(include, quote=True) + '">'
                  '<h2>' + escape(include, quote=True) + '</h2>' + artwork + '</section>')
    path = root / (directory + 'fixture.html'); path.parent.mkdir(parents=True); path.write_text(proof_text)
    build = copy.deepcopy(stamp)
    for relative in (source, svg, 'docs/diagram-catalog.json'):
        build['source'][relative] = digest((root / relative).read_bytes())
    build['html'][PROOF] = digest(path.read_bytes())
    inputs = {'schema': 1, 'include': include, 'original_source_sha256': digest(text.encode()),
              'svg_sha256': digest(artwork.encode()), 'font_sha256': digest((root / FONT).read_bytes()),
              'images': {}, 'http_style_sha256': digest(w.proof_style((root / w.PLUGIN).read_bytes()).encode()),
              'renderer_js_sha256': digest(renderer_literal(root / w.NATIVE_RENDERER).encode()),
              'browser': 'TEST browser only, not a real render claim'}
    identity = {'include': include, 'source_sha256': digest(text.encode()),
                'svg_sha256': digest(artwork.encode()), 'png_sha256': digest(out.getvalue())}
    receipt = dict(identity, index=2, automated_status='passed', metrics={'issues': [], 'canvas': [1920, 1080],
                   'viewBox': '0 0 1920 1080', 'browser': inputs['browser']},
                   png_dimensions=[1920, 1080], font_sha256=inputs['font_sha256'],
                   build_identity=fingerprint(build), per_source_inputs=inputs,
                   per_source_fingerprint=fingerprint(inputs), visual_review='not-run', semantic_review='not-run')
    review = dict(identity, visual_status='passed', semantic_status='passed', actual_original_png_viewed=True,
                  reviewed_at='TEST fixture only', notes='Synthetic TEST review, never production evidence')
    row = dict(identity, **{key: entry[key] for key in ('post', 'figure', 'instance', 'occurrence', 'png')},
               include_sha256=digest(text.encode()), render_fixture_file=directory + 'fixture.html',
               render_fixture_sha256=digest(path.read_bytes()))
    manifest = {'schema': 1, 'status': 'fresh-native-additions-reviewed',
                'base_revision': w.native_revision(root, 'HEAD'),
                'base_manifest_sha256': digest((root / w.NATIVE).read_bytes()),
                'base_review_sha256': digest((root / w.REVIEWS).read_bytes()),
                'base_catalog_sha256': digest(w._git_blob(root, 'HEAD', 'docs/diagram-catalog.json')),
                'sources': [row]}
    def save():
        for key, data in [('receipt', receipt), ('review', review), ('render_build', build)]:
            relative = directory + key + '.json'
            path = root / relative; path.write_text(json.dumps(data))
            row[key + '_file'] = relative; row[key + '_sha256'] = digest(path.read_bytes())
        (root / 'docs/diagram-native-additions.json').write_text(json.dumps(manifest))
    save()
    return SimpleNamespace(root=root, baseline=baseline, stamp=stamp, stamp_path=stamp_path, row=row,
                           manifest=manifest, receipt=receipt, review=review, build=build, source=source,
                           svg=svg, catalog=catalog, archived=archived, save=save)


def check(s):
    return module().checked_additions(s.root, s.manifest['base_revision'], s.baseline, s.stamp)


def test_absent_additions_leave_default_native_path_untouched(tmp_path):
    assert module().checked_additions(tmp_path, 'not-a-commit', {}, {}) is None


def test_checked_addition_authenticates_bytes_without_rewriting_original_evidence(addition):
    s = addition
    before = {p: digest(p.read_bytes()) for p in s.root.rglob('*') if p.is_file()}
    original = copy.deepcopy((s.baseline, s.stamp))
    report = check(s)
    assert set(report['sources']) == {s.row['include']}
    assert set(report['rows']) == {s.row['png']}
    assert report['sources'][s.row['include']]['review'] == s.review
    assert all(digest((s.root / path).read_bytes()) == sha for path, sha in report['files'].items())
    assert (s.baseline, s.stamp) == original
    assert before == {p: digest(p.read_bytes()) for p in s.root.rglob('*') if p.is_file()}
    assert 'old_png' not in report['rows'][s.row['png']]
    assert s.receipt['visual_review'] == s.receipt['semantic_review'] == 'not-run'
    for path, raw in s.archived.items(): assert (s.root / path).read_bytes() == raw


def test_added_identity_cannot_relabel_an_original_semantic_source(addition):
    s = addition
    old = s.root / ('_includes/' + s.baseline['entries'][0]['include'])
    (s.root / s.source).write_bytes(old.read_bytes())
    old_sha = s.row['source_sha256']; new_sha = digest(old.read_bytes())
    svg = s.root / s.svg; svg.write_text(svg.read_text().replace(old_sha, new_sha))
    fixture = s.root / s.row['render_fixture_file']
    fixture.write_text(fixture.read_text().replace(old_sha, new_sha))
    s.row.update(figure='example', include_sha256=new_sha, source_sha256=new_sha,
                 svg_sha256=digest(svg.read_bytes()), render_fixture_sha256=digest(fixture.read_bytes()))
    for item in (s.receipt, s.review):
        item.update(source_sha256=new_sha, svg_sha256=s.row['svg_sha256'])
    inputs = s.receipt['per_source_inputs']
    inputs.update(original_source_sha256=new_sha, svg_sha256=s.row['svg_sha256'])
    s.receipt['per_source_fingerprint'] = fingerprint(inputs)
    for relative in (s.source, s.svg): s.build['source'][relative] = digest((s.root / relative).read_bytes())
    s.build['html'][PROOF] = digest(fixture.read_bytes())
    s.receipt['build_identity'] = fingerprint(s.build)
    s.save(); downloads.main(['wire', '--root', str(s.root)])
    with pytest.raises(ValueError, match='relabel'): check(s)


@pytest.mark.parametrize('target,key,value', [
    ('manifest', 'schema', True), ('manifest', 'status', 'pending'),
    ('manifest', 'base_revision', 'HEAD'), ('manifest', 'base_catalog_sha256', '0'*64),
    ('manifest', 'base_manifest_sha256', '0'*64), ('manifest', 'base_review_sha256', '0'*64),
    ('manifest', 'sources', []), ('row', 'old_png', '/assets/img/diagrams/old.png'),
    ('row', 'post', '_posts/other.md'), ('row', 'figure', 'other'), ('row', 'instance', 'other'),
    ('row', 'occurrence', 2), ('row', 'occurrence', True),
    ('row', 'include', 'diagrams/example.html'), ('row', 'png', '/assets/img/diagrams/arbitrary.png'),
    *[('row', key, '0'*64) for key in ('include_sha256', 'source_sha256', 'svg_sha256', 'png_sha256')],
    ('receipt', 'automated_status', 'failed'), ('receipt', 'png_sha256', '0'*64),
    ('receipt', 'svg_sha256', '0'*64), ('receipt', 'source_sha256', '0'*64),
    ('receipt', 'include', 'diagrams/unused.html'), ('receipt', 'font_sha256', '0'*64),
    ('receipt', 'build_identity', '0'*64), ('receipt', 'per_source_fingerprint', '0'*64),
    ('receipt', 'png_dimensions', [960, 540]), ('receipt', 'index', 1), ('receipt', 'index', True),
    ('metrics', 'issues', ['overlap']), ('metrics', 'issues', None), ('metrics', 'browser', ''),
    ('metrics', 'canvas', [960, 540]), ('metrics', 'viewBox', '0 0 960 540'),
    ('inputs', 'schema', 2), ('inputs', 'extra', True), ('inputs', 'font_sha256', '0'*64),
    ('inputs', 'svg_sha256', '0'*64), ('inputs', 'original_source_sha256', '0'*64),
    ('inputs', 'http_style_sha256', '0'*64), ('inputs', 'renderer_js_sha256', '0'*64),
    ('inputs', 'images', {'/assets/img/missing.svg': '0'*64}), ('inputs', 'browser', 'different'),
    ('review', 'visual_status', 'not-run'), ('review', 'semantic_status', 'not-run'),
    ('review', 'actual_original_png_viewed', False), ('review', 'actual_original_png_viewed', 1),
    ('review', 'notes', ''), ('review', 'reviewed_at', ''), ('review', 'include', 'diagrams/unused.html'),
    ('review', 'source_sha256', '0'*64), ('review', 'svg_sha256', '0'*64), ('review', 'png_sha256', '0'*64),
])
def test_missing_stale_or_unreviewed_additions_fail_closed(addition, target, key, value):
    s = addition
    objects = vars(s) | {'metrics': s.receipt['metrics'], 'inputs': s.receipt['per_source_inputs']}
    objects[target][key] = value
    if target == 'inputs': s.receipt['per_source_fingerprint'] = fingerprint(objects[target])
    s.save()
    with pytest.raises((ValueError, OSError)): check(s)


@pytest.mark.parametrize('damage', [
    'missing-original', 'missing-addition', 'extra-catalog', 'duplicate-catalog', 'duplicate-record',
    'original-png', 'baseline', 'reviews', 'stamp', 'png-bytes', 'png-relabel', 'small-png', 'iend-crc',
    'stale-build', 'build-source', 'build-svg', 'build-font', 'build-renderer', 'build-catalog',
    'proof-style', 'font', 'renderer', 'fixture-bytes', 'fixture-card', 'receipt-hash',
    'receipt-escape', 'post-escape', 'png-escape', 'image-escape', 'symlink', 'duplicate-json',
])
def test_additive_coverage_archive_render_and_path_boundaries(addition, damage):
    s = addition
    if damage in ('missing-original', 'missing-addition', 'extra-catalog', 'duplicate-catalog'):
        if damage == 'missing-original': s.catalog['diagrams'].pop(0)
        elif damage == 'missing-addition': s.catalog['diagrams'].pop()
        elif damage == 'extra-catalog': s.catalog['diagrams'].append({'include': 'diagrams/extra.html'})
        else: s.catalog['diagrams'].append(copy.deepcopy(s.catalog['diagrams'][0]))
        (s.root / 'docs/diagram-catalog.json').write_text(json.dumps(s.catalog))
    elif damage == 'duplicate-record': s.manifest['sources'].append(copy.deepcopy(s.row))
    elif damage == 'original-png': (s.root / s.baseline['entries'][0]['png'][1:]).write_bytes(b'changed archive')
    elif damage in ('baseline', 'reviews'):
        path = s.root / (w.NATIVE if damage == 'baseline' else w.REVIEWS); path.write_bytes(path.read_bytes() + b'\n')
    elif damage == 'stamp': s.stamp['source']['rebased'] = 'a'*64
    elif damage in ('png-bytes', 'png-relabel', 'small-png', 'iend-crc'):
        path = s.root / s.row['png'][1:]
        if damage == 'png-bytes': path.write_bytes(path.read_bytes() + b'changed')
        elif damage == 'png-relabel': path.write_bytes(next(iter(s.archived.values())))
        elif damage == 'small-png':
            out = BytesIO(); Image.new('RGB', (960, 540)).save(out, format='PNG'); path.write_bytes(out.getvalue())
        else:
            raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
        if damage != 'png-bytes':
            for item in (s.row, s.receipt, s.review): item['png_sha256'] = digest(path.read_bytes())
    elif damage == 'stale-build':
        s.build.clear(); s.build.update(copy.deepcopy(s.stamp)); s.receipt['build_identity'] = fingerprint(s.build)
    elif damage.startswith('build-'):
        relative = {'source': s.source, 'svg': s.svg, 'font': FONT, 'renderer': w.NATIVE_RENDERER,
                    'catalog': 'docs/diagram-catalog.json'}[damage.removeprefix('build-')]
        s.build['assets' if damage == 'build-font' else 'source'][relative] = '0'*64
        s.receipt['build_identity'] = fingerprint(s.build)
    elif damage in ('font', 'renderer', 'proof-style'):
        path = s.root / {'font': FONT, 'renderer': w.NATIVE_RENDERER, 'proof-style': w.PLUGIN}[damage]
        if damage == 'proof-style': path.write_text(path.read_text().replace('h2{font-size:16px}', 'h2{font-size:15px}'))
        else: path.write_bytes(path.read_bytes() + b'changed raster input')
    elif damage in ('fixture-bytes', 'fixture-card'):
        path = s.root / s.row['render_fixture_file']; path.write_text(path.read_text().replace('<rect ', '<g/><rect '))
        if damage == 'fixture-card':
            s.row['render_fixture_sha256'] = digest(path.read_bytes()); s.build['html'][PROOF] = digest(path.read_bytes())
            s.receipt['build_identity'] = fingerprint(s.build)
    elif damage == 'post-escape': s.row['post'] = '_posts/../../escape.md'
    elif damage == 'png-escape': s.row['png'] = '/assets/img/diagrams/../../escape.png'
    elif damage == 'image-escape':
        path = s.root / s.svg
        path.write_text(path.read_text().replace('</svg>', '<image href="/assets/../../escape.png"/></svg>'))
        s.row['svg_sha256'] = digest(path.read_bytes())
    s.save()
    if damage in ('receipt-hash', 'receipt-escape', 'symlink', 'duplicate-json'):
        path = s.root / s.row['receipt_file']
        if damage == 'receipt-hash': path.write_bytes(path.read_bytes() + b'\n')
        elif damage == 'receipt-escape': s.row['receipt_file'] = 'docs/diagram-native-additions/../../escape.json'
        elif damage == 'symlink':
            target = s.root.parent / 'outside.json'; path.rename(target); path.symlink_to(target)
        else:
            path.write_text('{"index":null,' + path.read_text()[1:])
            s.row['receipt_sha256'] = digest(path.read_bytes())
        (s.root / 'docs/diagram-native-additions.json').write_text(json.dumps(s.manifest))
    with pytest.raises((ValueError, OSError)): check(s)
