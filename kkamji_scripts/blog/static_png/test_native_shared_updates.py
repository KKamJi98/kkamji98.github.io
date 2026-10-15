"""Shared native updates use real PNG/Git bytes; review metadata is TEST only."""
import copy
import json
import os
import shutil
import subprocess
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

import downloads as d
import webp_release as w
from fhd_reuse import FONT, PROOF, native_inputs, renderer_literal
from pipeline import digest, fingerprint
from test_webp_release import fixture, png_bytes


def shared_fixture(tmp_path, monkeypatch, layout='same-post'):
    # Never inherit the parent's repository, config overrides, hooks or index.
    for name in tuple(os.environ):
        if name.startswith('GIT_'): monkeypatch.delenv(name)
    for name, value in {'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
                        'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.hooksPath',
                        'GIT_CONFIG_VALUE_0': '/dev/null'}.items(): monkeypatch.setenv(name, value)
    root, baseline, stamp_path = fixture(tmp_path)
    include = 'diagrams/example.html'
    source = '_includes/' + include; svg = 'assets/img/diagrams/fhd-svg/example.svg'
    old_source = (root / source).read_text()
    if layout == 'same-post':
        (root / source).write_text(old_source.replace('id="example"', 'id="example-{{include.instance}}"'))
        (root / '_posts/example.md').write_text('---\ntitle: Docker TEST\n---\n'
            '{% include diagrams/example.html instance="one" %}\n'
            '{% include diagrams/example.html instance="two" %}\n')
        posts = ['_posts/example.md']; count = 2
    else:
        posts = ['_posts/example.md', '_posts/lab-b.md', '_posts/lab-c.md']; count = 3
        for post in posts:
            (root / post).write_text('---\ntitle: Cilium TEST\n---\n{% include diagrams/example.html %}\n')
    sha = digest(w.source_fragment((root / source).read_text()).encode())
    (root / svg).write_text((root / svg).read_text().replace(digest(old_source.encode()), sha))
    catalog = json.loads((root / 'docs/diagram-catalog.json').read_text())
    catalog['summary'] = {'post_references': count, 'posts': len(posts)}
    catalog['diagrams'][0].update(posts=posts, reference_count=count)
    (root / 'docs/diagram-catalog.json').write_text(json.dumps(catalog))
    d.main(['wire', '--root', str(root)])
    baseline['entries'] = [dict(row, page='posts/' + row['post'].split('/')[-1][:-3] + '/index.html',
        png_sha256=digest(png_bytes()), dimensions=[1920, 1080], include_sha256=sha,
        receipt_sha256='a'*64) for row in d.validate_source(root)['entries']]
    for row in baseline['entries']: (root / row['png'][1:]).write_bytes(png_bytes())
    reviews = json.loads((root / w.REVIEWS).read_text())
    reviews['sources'][0].update(source_sha256=sha, svg_sha256=digest((root / svg).read_bytes()))
    (root / w.REVIEWS).write_text(json.dumps(reviews))
    old = json.loads(stamp_path.read_text()); old['source'] = d.source_snapshot(root)
    baseline.update(reference_count=count, post_count=len(posts), source_fingerprint=fingerprint(old['source']),
                    build_identity=fingerprint(old), review_file_sha256=digest((root / w.REVIEWS).read_bytes()))
    (root / w.NATIVE).write_text(json.dumps(baseline)); stamp_path.write_text(json.dumps(old))
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '-qm', 'shared TEST archive'], cwd=root, check=True)
    (root / source).write_text((root / source).read_text().replace('Example', 'Replacement'))
    source_sha = digest(w.source_fragment((root / source).read_text()).encode())
    (root / svg).write_text((root / svg).read_text().replace(sha, source_sha).replace('<image ', '<g><image ').replace('/></svg>', '/></g></svg>'))
    proof = root / PROOF; proof.parent.mkdir(parents=True)
    proof.write_text('<style>' + w.proof_style((root / w.PLUGIN).read_bytes()) + '</style>')
    inputs = native_inputs(root, root, include, 'TEST browser only', renderer_literal(root / w.NATIVE_RENDERER))
    inputs['images'] = {'/assets/img/icon.svg': digest((root / 'assets/img/icon.svg').read_bytes())}
    build = copy.deepcopy(old)
    for path in (source, svg): build['source'][path] = digest((root / path).read_bytes())
    build['html'][PROOF] = digest(proof.read_bytes())
    image = Image.open(BytesIO(png_bytes())).convert('RGBA'); image.putpixel((20, 20), (1, 2, 3, 255))
    output = BytesIO(); image.save(output, format='PNG'); raw = output.getvalue()
    occurrences = [dict(post=row['post'], figure=row['figure'], old_png=row['png'],
        new_png='/assets/img/diagrams/native-updates/20261014/example-' + str(i) + '.png')
        for i, row in enumerate(baseline['entries'])]
    for occurrence in occurrences:
        path = root / occurrence['new_png'][1:]; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    identity = dict(include=include, source_sha256=source_sha, svg_sha256=inputs['svg_sha256'], png_sha256=digest(raw))
    receipt = dict(identity, automated_status='passed', metrics={'issues': [], 'canvas': [1920,1080], 'browser': inputs['browser']},
        font_sha256=inputs['font_sha256'], build_identity=fingerprint(build), per_source_inputs=inputs, per_source_fingerprint=fingerprint(inputs))
    review = dict(identity, visual_status='passed', semantic_status='passed', actual_original_png_viewed=True,
        reviewed_at='TEST fixture only', notes='Synthetic TEST metadata, not a production review')
    row = dict(identity, old_png=occurrences[0]['old_png'], new_png=occurrences[0]['new_png'], occurrences=occurrences)
    manifest = dict(schema=1, status='fresh-native-update-reviewed', base_revision=w.native_revision(root, 'HEAD'),
        base_manifest_sha256=digest((root / w.NATIVE).read_bytes()), base_review_sha256=digest((root / w.REVIEWS).read_bytes()), sources=[row])
    def save():
        for key, data in [('receipt',receipt), ('review',review), ('render_build',build)]:
            relative = 'docs/native-update-test/' + key + '.json'; file = root / relative
            file.parent.mkdir(parents=True, exist_ok=True); file.write_text(json.dumps(data))
            row[key + '_file'] = relative; row[key + '_sha256'] = digest(file.read_bytes())
        (root / 'docs/diagram-native-update.json').write_text(json.dumps(manifest))
    save()
    return SimpleNamespace(root=root, baseline=baseline, old=old, stamp_path=stamp_path, manifest=manifest, row=row,
        receipt=receipt, review=review, build=build, source=source, svg=svg, save=save)


def delivery_fixture(s, site):
    from test_native_shared_viewer import render_viewers
    site.mkdir(); shutil.copytree(s.root / 'assets', site / 'assets')
    plan = d.validate_source(s.root)
    posts = {row['post']: '/posts/' + row['post'].split('/')[-1][:-3] + '/' for row in plan['entries']}
    for post, url in posts.items():
        text = ''
        for row in plan['entries']:
            if row['post'] != post: continue
            webp = d.webp_url(row['png'])
            text += (f'<figure class="sd" id="{row["figure"]}"></figure><p class="diagram-download">'
                f'<img class="diagram-inline" src="{webp}" alt="" data-static-diagram="true" width="1920" height="1080">'
                f'<a href="{webp}" download>WebP</a><a href="{d.viewer_url(webp)}">Open</a></p>')
        page = site / (url[1:] + 'index.html'); page.parent.mkdir(parents=True); page.write_text(text)
    for row, content in zip(plan['entries'], render_viewers(s.root, plan['entries'], posts)):
        page = site / d.viewer_url(row['png'])[1:]; page.parent.mkdir(parents=True, exist_ok=True); page.write_text(content)
        assert posts[row['post']] + '#' + row['figure'] in content
    sidecar = site / 'assets/data/diagram-posts.json'; sidecar.parent.mkdir(parents=True); sidecar.write_text(json.dumps(posts))
    stamp = dict(source=d.source_snapshot(s.root), assets=d.built_assets_snapshot(site, plan),
        html={p.relative_to(site).as_posix(): digest(p.read_bytes()) for p in site.rglob('*.html')})
    (site / '.diagram-download-build.json').write_text(json.dumps(stamp))
    return plan


@pytest.mark.parametrize('layout', ['same-post', 'cross-post'])
def test_shared_fanout_roundtrip_and_exact_index(tmp_path, monkeypatch, layout):
    s = shared_fixture(tmp_path, monkeypatch, layout)
    preserved = {p: (s.root / p).read_bytes() for p in [w.NATIVE,w.REVIEWS] + [r['png'][1:] for r in s.baseline['entries'] + s.baseline['unused_entries']]}
    declaration = (s.root / 'docs/diagram-native-update.json').read_bytes()
    assert d.main(['wire', '--root', str(s.root)]) == 0
    plan = d.validate_source(s.root)
    assert [r['png'] for r in plan['entries']] == [o['new_png'] for o in s.row['occurrences']]
    assert [r['old_png'] for r in plan['entries']] == [o['old_png'] for o in s.row['occurrences']]
    assert not d.delivery_output_paths(s.root, plan).intersection(d.source_snapshot(s.root))
    native = w.checked_native(s.root, s.old, s.manifest['base_revision'])
    assert len(native['rows']) == len(s.baseline['entries']) + 1
    assert w.convert(s.root, s.stamp_path, s.manifest['base_revision'])['outputs'] == len(native['rows'])
    site = tmp_path / 'site'; delivery_fixture(s, site)
    assert w.seal(s.root, site, s.stamp_path, s.manifest['base_revision'])['outputs'] == len(native['rows'])
    assert w.check(s.root, site)['passed'] and w.check(s.root)['passed']
    subprocess.run(['git', 'add', '.'], cwd=s.root, check=True)
    assert w.verify_staged(s.root)['indexed']
    bad = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'], cwd=s.root, input=b'TEST divergence').decode().strip()
    targets = list(preserved) + [s.row[k + '_file'] for k in ('receipt','review','render_build')]
    targets += [o['new_png'][1:] for o in s.row['occurrences']] + [d.webp_url(o['new_png'])[1:] for o in s.row['occurrences']]
    for path in targets:
        subprocess.run(['git','update-index','--cacheinfo','100644,' + bad + ',' + path], cwd=s.root, check=True)
        with pytest.raises(ValueError, match='index differs'): w.verify_staged(s.root)
        subprocess.run(['git','add','--',path], cwd=s.root, check=True)
    assert (s.root / 'docs/diagram-native-update.json').read_bytes() == declaration
    assert all((s.root / p).read_bytes() == raw for p, raw in preserved.items())


def identical_png(s, reencoded=False):
    raw = (s.root / s.row['old_png'][1:]).read_bytes()
    if reencoded:
        output = BytesIO(); w._decode(raw, 'PNG').save(output, format='PNG', compress_level=0)
        assert output.getvalue() != raw
        raw = output.getvalue()
    for occurrence in s.row['occurrences']: (s.root / occurrence['new_png'][1:]).write_bytes(raw)
    for obj in (s.row,s.receipt,s.review): obj['png_sha256'] = digest(raw)
    s.save()


@pytest.mark.parametrize('reencoded', [False, True])
def test_fresh_identical_render_still_requires_a_real_source_or_svg_delta(tmp_path, monkeypatch, reencoded):
    s = shared_fixture(tmp_path, monkeypatch); identical_png(s, reencoded)
    for relative in (s.source,s.svg):
        raw = w._git_blob(s.root, s.manifest['base_revision'], relative)
        (s.root / relative).write_bytes(raw); s.build['source'][relative] = digest(raw)
    inputs = native_inputs(s.root, s.root, s.row['include'], 'TEST browser only', renderer_literal(s.root / w.NATIVE_RENDERER))
    inputs['images'] = {'/assets/img/icon.svg': digest((s.root / 'assets/img/icon.svg').read_bytes())}
    for obj in (s.row,s.receipt,s.review):
        obj.update(source_sha256=inputs['original_source_sha256'], svg_sha256=inputs['svg_sha256'])
    # Rehashing an old capture with a different global/proof stamp is not a delta.
    s.receipt.update(per_source_inputs=inputs, per_source_fingerprint=fingerprint(inputs), build_identity=fingerprint(s.build))
    s.save()
    with pytest.raises(ValueError, match='identical|relabel|delta'):
        w.checked_native(s.root, s.old, s.manifest['base_revision'])


@pytest.mark.parametrize('layout', ['same-post','cross-post'])
@pytest.mark.parametrize('reencoded', [False, True])
def test_fresh_identical_png_uses_fresh_inputs_without_rebasing_archive(tmp_path, monkeypatch, layout, reencoded):
    s = shared_fixture(tmp_path, monkeypatch, layout); identical_png(s, reencoded)
    original = copy.deepcopy((s.old,s.baseline))
    d.main(['wire','--root',str(s.root)])
    native = w.checked_native(s.root, s.old, s.manifest['base_revision'])
    assert len(native['rows']) == len(s.baseline['entries']) + 1
    assert (s.old,s.baseline) == original
    assert w.convert(s.root,s.stamp_path,s.manifest['base_revision'])['outputs'] == len(native['rows'])
    site = tmp_path / 'site'; delivery_fixture(s,site)
    w.seal(s.root,site,s.stamp_path,s.manifest['base_revision'])
    assert w.check(s.root,site)['passed']


@pytest.mark.parametrize('damage', ['missing-list','missing','duplicate-old','duplicate-new','swapped-post',
    'swapped-figure','swapped-old','master-pair','archive-destination','foreign-url','null','empty'])
def test_bad_occurrence_declaration_fails_before_any_mapping_write(tmp_path, monkeypatch, damage):
    s = shared_fixture(tmp_path, monkeypatch,'cross-post' if damage == 'swapped-post' else 'same-post')
    rows = s.row['occurrences']
    if damage == 'missing-list': s.row.pop('occurrences')
    elif damage == 'missing': rows.pop()
    elif damage == 'duplicate-old': rows[1]['old_png'] = rows[0]['old_png']
    elif damage == 'duplicate-new': rows[1]['new_png'] = rows[0]['new_png']
    elif damage == 'swapped-post': rows[1]['post'] = rows[0]['post']
    elif damage == 'swapped-figure': rows[1]['figure'] = rows[0]['figure']
    elif damage == 'swapped-old': rows[0]['old_png'],rows[1]['old_png'] = rows[1]['old_png'],rows[0]['old_png']
    elif damage == 'master-pair': s.row['new_png'] = rows[1]['new_png']
    elif damage == 'archive-destination': rows[1]['new_png'] = rows[1]['old_png']
    elif damage == 'foreign-url': rows[1]['new_png'] = 'https://example.invalid/divert.png'
    elif damage == 'null': s.row['occurrences'] = None
    else: s.row['occurrences'] = []
    s.save()
    paths = [d.MANIFEST] + [row['post'] for row in s.baseline['entries']]
    before = {p:(s.root / p).read_bytes() for p in paths}
    with pytest.raises(ValueError): d.main(['wire','--root',str(s.root)])
    with pytest.raises(ValueError): d.source_snapshot(s.root)
    with pytest.raises(ValueError): w.checked_native(s.root,s.old,s.manifest['base_revision'])
    assert all((s.root / p).read_bytes() == raw for p,raw in before.items())


@pytest.mark.parametrize('damage', ['different-copy','iend-crc','master-crc','stale-inputs','stale-build',
    'rebased-stamp','stale-review','unviewed-review'])
def test_copy_integrity_and_identical_render_freshness_fail_closed(tmp_path, monkeypatch, damage):
    s = shared_fixture(tmp_path, monkeypatch); identical_png(s)
    if damage == 'different-copy':
        path = s.root / s.row['occurrences'][1]['new_png'][1:]
        image = Image.open(BytesIO(path.read_bytes())).convert('RGBA'); image.putpixel((42,42),(1,2,3,255))
        out = BytesIO(); image.save(out,format='PNG'); path.write_bytes(out.getvalue())
    elif damage == 'iend-crc':
        path = s.root / s.row['occurrences'][1]['new_png'][1:]; raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
    elif damage == 'master-crc':
        raw = bytearray((s.root / s.row['new_png'][1:]).read_bytes()); raw[-1] ^= 1
        for occurrence in s.row['occurrences']: (s.root / occurrence['new_png'][1:]).write_bytes(raw)
        for obj in (s.row,s.receipt,s.review): obj['png_sha256'] = digest(raw)
    elif damage == 'stale-inputs':
        s.receipt['per_source_inputs']['svg_sha256'] = '0'*64
        s.receipt['per_source_fingerprint'] = fingerprint(s.receipt['per_source_inputs'])
    elif damage == 'stale-build':
        s.build.clear(); s.build.update(copy.deepcopy(s.old)); s.receipt['build_identity'] = fingerprint(s.build)
    elif damage == 'rebased-stamp': s.old['source'][s.source] = digest((s.root / s.source).read_bytes())
    elif damage == 'stale-review': s.review['svg_sha256'] = s.baseline['entries'][0]['include_sha256']
    else: s.review['actual_original_png_viewed'] = False
    s.save(); d.main(['wire','--root',str(s.root)])
    with pytest.raises(ValueError): w.checked_native(s.root,s.old,s.manifest['base_revision'])
    assert not list((s.root / 'assets/img/diagrams/native-updates').rglob('*.webp'))
