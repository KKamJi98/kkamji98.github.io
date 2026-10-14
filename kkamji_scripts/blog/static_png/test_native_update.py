"""Native deltas use explicit test evidence, never production review claims."""
import importlib
import importlib.util


def module():
    assert importlib.util.find_spec('native_update'), 'native update validator is missing'
    return importlib.import_module('native_update')


def test_absent_manifest_leaves_legacy_native_path_untouched(tmp_path):
    assert module().checked_update(tmp_path, 'not-a-commit', {}, {}) is None

import copy
import json
import os
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from pipeline import digest, fingerprint
from fhd_reuse import FONT, PROOF, native_inputs, renderer_literal
import webp_release as w
from test_webp_release import fixture, png_bytes


@pytest.fixture
def delta(tmp_path, monkeypatch):
    for name in tuple(os.environ):
        if name.startswith('GIT_'): monkeypatch.delenv(name)
    for name, value in {'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
                        'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.hooksPath',
                        'GIT_CONFIG_VALUE_0': '/dev/null'}.items(): monkeypatch.setenv(name, value)
    root, baseline, stamp_path = fixture(tmp_path)
    old = json.loads(stamp_path.read_text()); include = baseline['entries'][0]['include']
    source = '_includes/' + include; svg = 'assets/img/diagrams/fhd-svg/example.svg'
    (root / source).write_text((root / source).read_text().replace('Example', 'Replacement'))
    source_hash = digest(w.source_fragment((root / source).read_text()).encode())
    (root / svg).write_text((root / svg).read_text().replace(baseline['entries'][0]['include_sha256'], source_hash)
                           .replace('<image ', '<g><image ').replace('/></svg>', '/></g></svg>'))
    proof = root / PROOF; proof.parent.mkdir(parents=True)
    proof.write_text('<style>' + w.proof_style((root / w.PLUGIN).read_bytes()) + '</style>')
    inputs = native_inputs(root, root, include, 'TEST browser only', renderer_literal(root / w.NATIVE_RENDERER))
    inputs['images'] = {'/assets/img/icon.svg': digest((root / 'assets/img/icon.svg').read_bytes())}
    build = copy.deepcopy(old)
    for path in (source, svg): build['source'][path] = digest((root / path).read_bytes())
    build['html'][PROOF] = digest(proof.read_bytes())
    image = Image.open(BytesIO(png_bytes())).convert('RGBA'); image.putpixel((20, 20), (1, 2, 3, 255))
    output = BytesIO(); image.save(output, format='PNG')
    png = '/assets/img/diagrams/native-updates/20261014/example.png'
    path = root / png[1:]; path.parent.mkdir(parents=True); path.write_bytes(output.getvalue())
    identity = {'include': include, 'source_sha256': source_hash, 'svg_sha256': inputs['svg_sha256'],
                'png_sha256': digest(output.getvalue())}
    receipt = dict(identity, automated_status='passed', metrics={'issues': [], 'canvas': [1920, 1080],
                   'browser': inputs['browser']}, font_sha256=inputs['font_sha256'],
                   build_identity=fingerprint(build), per_source_inputs=inputs, per_source_fingerprint=fingerprint(inputs))
    review = dict(identity, visual_status='passed', semantic_status='passed', actual_original_png_viewed=True,
                  reviewed_at='TEST fixture only', notes='Synthetic TEST metadata, not a production review')
    row = dict(identity, old_png=baseline['entries'][0]['png'], new_png=png)
    manifest = {'schema': 1, 'status': 'fresh-native-update-reviewed', 'base_revision': w.native_revision(root, 'HEAD'),
                'base_manifest_sha256': digest((root / w.NATIVE).read_bytes()),
                'base_review_sha256': digest((root / w.REVIEWS).read_bytes()), 'sources': [row]}
    def save():
        for key, data in [('receipt', receipt), ('review', review), ('render_build', build)]:
            relative = 'docs/native-update-test/' + key + '.json'
            file = root / relative; file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(data)); row[key + '_file'] = relative; row[key + '_sha256'] = digest(file.read_bytes())
        (root / 'docs/diagram-native-update.json').write_text(json.dumps(manifest))
    save()
    return SimpleNamespace(root=root, baseline=baseline, old=old, manifest=manifest, row=row, receipt=receipt,
                           review=review, build=build, source=source, svg=svg, save=save)


def check(s):
    return module().checked_update(s.root, s.manifest['base_revision'], s.baseline, s.old)


def test_reviewed_delta_returns_sealed_artifacts_without_mutating_old_evidence(delta):
    s = delta; before = {p: digest(p.read_bytes()) for p in s.root.rglob('*') if p.is_file()}
    original = copy.deepcopy((s.baseline, s.old)); report = check(s)
    assert report['sources'][s.row['include']]['receipt'] == s.receipt
    assert report['sources'][s.row['include']]['review'] == s.review
    assert report['input_overrides'] == {p: digest((s.root / p).read_bytes()) for p in (s.source, s.svg)}
    assert all(digest((s.root / p).read_bytes()) == sha for p, sha in report['files'].items())
    assert (s.baseline, s.old) == original
    assert before == {p: digest(p.read_bytes()) for p in s.root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('target,key,value', [
    ('manifest','schema',2), ('manifest','status','pending'), ('manifest','base_revision','HEAD'),
    ('manifest','base_manifest_sha256','0'*64), ('manifest','base_review_sha256','0'*64), ('manifest','sources',[]),
    ('row','include','diagrams/unknown.html'), ('row','old_png','/assets/img/diagrams/wrong.png'),
    ('row','new_png','/assets/img/diagrams/not-a-native-update.png'), ('row','receipt_file','../receipt.json'),
    ('row','source_sha256','0'*64), ('row','svg_sha256','0'*64), ('row','png_sha256','0'*64),
    *[('row', key, None) for key in ('svg_sha256', 'png_sha256', 'receipt_sha256', 'review_sha256', 'render_build_sha256')],
    ('receipt','automated_status','failed'), ('receipt','include','diagrams/unused.html'),
    ('receipt','source_sha256','0'*64), ('receipt','svg_sha256','0'*64), ('receipt','png_sha256','0'*64),
    ('receipt','font_sha256','0'*64), ('receipt','build_identity','0'*64), ('receipt','per_source_fingerprint','0'*64),
    ('metrics','issues',['overlap']), ('metrics','issues',None), ('metrics','canvas',[960,540]), ('metrics','browser',''),
    ('inputs','schema',2), ('inputs','extra',True), ('inputs','original_source_sha256','0'*64),
    ('inputs','svg_sha256','0'*64), ('inputs','font_sha256','0'*64), ('inputs','images',{}),
    ('inputs','http_style_sha256','0'*64), ('inputs','renderer_js_sha256','0'*64), ('inputs','browser',''),
    ('review','visual_status','pending'), ('review','semantic_status','pending'), ('review','actual_original_png_viewed',1),
    ('review','notes',''), ('review','reviewed_at',''), ('review','png_sha256','0'*64), ('review','svg_sha256','0'*64),
    ('review','source_sha256','0'*64), ('review','include','diagrams/unused.html'),
])
def test_incomplete_or_stale_delta_fails_closed(delta, target, key, value):
    s = delta; objects = vars(s) | {'metrics': s.receipt['metrics'], 'inputs': s.receipt['per_source_inputs']}
    objects[target][key] = value
    if target == 'inputs': s.receipt['per_source_fingerprint'] = fingerprint(objects[target])
    s.save()
    if target == 'row' and key in ('receipt_file', 'receipt_sha256', 'review_sha256', 'render_build_sha256'):
        s.row[key] = value; (s.root / 'docs/diagram-native-update.json').write_text(json.dumps(s.manifest))
    with pytest.raises((ValueError, OSError)): check(s)


@pytest.mark.parametrize('damage', ['duplicate-source', 'old-collision', 'other-collision', 'old-png', 'stale-build',
                                  'build-font', 'build-image', 'baseline', 'crc', 'iend-crc', 'symlink', 'duplicate-json',
                                  'duplicate-json-review', 'duplicate-json-render_build', 'duplicate-json-manifest'])
def test_archive_path_build_and_json_boundaries(delta, damage):
    s = delta
    if damage == 'duplicate-source': s.manifest['sources'].append(copy.deepcopy(s.row))
    elif damage == 'old-collision': s.row['new_png'] = s.row['old_png']
    elif damage == 'other-collision': s.row['new_png'] = s.baseline['unused_entries'][0]['png']
    elif damage == 'old-png': (s.root / s.row['old_png'][1:]).write_bytes(b'changed archive')
    elif damage == 'stale-build': s.build.clear(); s.build.update(copy.deepcopy(s.old)); s.receipt['build_identity'] = fingerprint(s.old)
    elif damage in ('build-font', 'build-image'):
        s.build['assets'][FONT if damage == 'build-font' else 'assets/img/icon.svg'] = '0'*64
        s.receipt['build_identity'] = fingerprint(s.build)
    elif damage == 'baseline': (s.root / w.NATIVE).write_bytes(b'changed baseline')
    elif damage in ('crc', 'iend-crc'):
        path = s.root / s.row['new_png'][1:]; raw = bytearray(path.read_bytes()); offset = 8
        while raw[offset+4:offset+8] != b'IDAT': offset += int.from_bytes(raw[offset:offset+4], 'big') + 12
        raw[-1 if damage == 'iend-crc' else offset+8+int.from_bytes(raw[offset:offset+4], 'big')] ^= 1; path.write_bytes(raw)
        for obj in (s.row, s.receipt, s.review): obj['png_sha256'] = digest(raw)
    s.save()
    if damage == 'symlink' or damage.startswith('duplicate-json'):
        key = damage.removeprefix('duplicate-json-') if damage.startswith('duplicate-json-') else 'receipt'
        path = s.root / ('docs/diagram-native-update.json' if key == 'manifest' else s.row[key + '_file'])
        if damage == 'symlink':
            backup = path.with_suffix('.backup'); path.rename(backup); path.symlink_to(backup)
        else: path.write_text(json.dumps({next(iter(json.loads(path.read_text()))): None})[:-1] + ',' + path.read_text()[1:])
        if key != 'manifest':
            s.row[key + '_sha256'] = digest(path.read_bytes())
            (s.root / 'docs/diagram-native-update.json').write_text(json.dumps(s.manifest))
    with pytest.raises((ValueError, OSError)): check(s)
