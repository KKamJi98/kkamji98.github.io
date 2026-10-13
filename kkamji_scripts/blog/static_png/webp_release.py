#!/usr/bin/env python3
"""Lossless derivatives of the immutable reviewed native FHD PNG release.

Raster production and prior visual review remain native evidence. This adapter
only certifies exact decoded pixels, current static delivery and build bytes.
Article/viewer CSS and authoring-report label changes are not native rerenders:
exact include, SVG, font, image, renderer and native proof-style identity is
required, while the current tools and delivery sources receive a separate seal.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

from PIL import Image
from downloads import source_snapshot, validate_source, webp_url
from fhd_reuse import FONT, source_fragment
from pipeline import digest, fingerprint


def _decode(raw, kind):
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format != kind or image.size != (1920, 1080) or getattr(image, 'n_frames', 1) != 1:
                raise ValueError(kind + ' must be a single exact 1920 x 1080 image')
            # Loading pixels alone does not check every PNG chunk CRC.
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            image.load()
            return image.convert('RGBA')
    except (OSError, SyntaxError) as error:
        raise ValueError('invalid or corrupt ' + kind) from error


def _lossless_container(raw):
    if (raw[:4] != b'RIFF' or raw[8:12] != b'WEBP' or len(raw) < 20
            or int.from_bytes(raw[4:8], 'little') + 8 != len(raw)):
        raise ValueError('invalid lossless WebP container bytes')
    chunks = []; offset = 12
    while offset < len(raw):
        if offset + 8 > len(raw): raise ValueError('truncated lossless WebP chunk')
        kind = raw[offset:offset+4]
        length = int.from_bytes(raw[offset+4:offset+8], 'little')
        offset += 8 + length + (length % 2)
        if offset > len(raw): raise ValueError('truncated lossless WebP payload')
        chunks.append(kind)
    if chunks.count(b'VP8L') != 1 or any(kind in chunks for kind in (b'VP8 ', b'ANIM', b'ANMF')):
        raise ValueError('WebP must use a single lossless VP8L payload')


def compare_pixels(png, webp):
    _lossless_container(webp)
    original = _decode(png, 'PNG')
    converted = _decode(webp, 'WEBP')
    pixels = original.tobytes()
    if pixels != converted.tobytes():
        raise ValueError('full decoded RGBA pixels differ')
    return {'dimensions': [1920, 1080], 'pixel_equality': 'full-decoded-RGBA-equal',
            'png_sha256': digest(png), 'webp_sha256': digest(webp), 'rgba_sha256': digest(pixels)}


def encode_lossless(png):
    image = _decode(png, 'PNG')
    output = BytesIO()
    image.save(output, format='WEBP', lossless=True, method=6, exact=True)
    raw = output.getvalue()
    compare_pixels(png, raw)
    return raw


MANIFEST = 'docs/diagram-webp-release.json'
NATIVE = 'docs/diagram-export-release.json'
REVIEWS = 'docs/diagram-fhd-reviews.json'
NATIVE_RENDERER = 'kkamji_scripts/blog/static_png/fhd_export.py'
PLUGIN = '_plugins/diagram-downloads.rb'
CONVERSION = {'format': 'WEBP', 'lossless': True, 'method': 6, 'exact': True,
              'resize': False, 'crop': False, 'comparison': 'full-decoded-RGBA-equal'}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def load_json(raw):
    return json.loads(raw, object_pairs_hook=_object)


def safe_path(root, relative):
    if (not isinstance(relative, str) or relative.startswith('/') or '\\' in relative
            or '\x00' in relative or any(part in ('', '.', '..') for part in relative.split('/'))):
        raise ValueError('unsafe rooted input path')
    root = Path(root).resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root): raise ValueError('input escapes root')
    for part in (path, *path.parents):
        if part == root: break
        if part.is_symlink(): raise ValueError('symlinked rooted input is not accepted')
    return path


def public_path(root, url, extension):
    if not isinstance(url, str) or not re.fullmatch(r'/assets/img/diagrams/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+\.' + extension, url):
        raise ValueError('unsafe public diagram path')
    return safe_path(root, url[1:])


def _git_blob(root, revision, path):
    if revision.startswith('sha256:'):
        # A fresh release uses its exact baseline SHA, not a future Git SHA.
        # checked_native seals reviews, the plugin and every raster input.
        native_revision(root, revision)
        if path not in (NATIVE, REVIEWS, PLUGIN):
            raise ValueError('unsupported content-addressed native evidence')
        return safe_path(root, path).read_bytes()
    try:
        return subprocess.check_output(['git', 'show', revision + ':' + path], cwd=root, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as error:
        raise ValueError('immutable native Git evidence is unavailable: ' + path) from error


def native_revision(root, revision):
    if revision.startswith('sha256:'):
        expected = revision.removeprefix('sha256:')
        if (not re.fullmatch(r'[a-f0-9]{64}', expected)
                or digest(safe_path(root, NATIVE).read_bytes()) != expected):
            raise ValueError('content-addressed native baseline changed')
        return revision
    try:
        resolved = subprocess.check_output(['git', 'rev-parse', '--verify', revision + '^{commit}'], cwd=root, text=True, stderr=subprocess.PIPE).strip()
    except subprocess.CalledProcessError as error:
        raise ValueError('native revision is not a commit') from error
    if not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', resolved): raise ValueError('invalid native commit identity')
    return resolved


def proof_style(plugin):
    # The proof fixture is native raster input, unlike article/viewer delivery CSS.
    text = plugin.decode().split('def generate_proof_fixture(site)', 1)
    if len(text) != 2: raise ValueError('native proof fixture generator is missing')
    styles = re.findall(r'<style>(.*?)</style>', text[1], re.S)
    if len(styles) != 1 or '#{' in styles[0]: raise ValueError('native proof style is ambiguous')
    return styles[0]


def _same_hash(path, expected, label):
    if not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected) or digest(path.read_bytes()) != expected:
        raise ValueError(label + ' changed or lacks sealed native identity')


def checked_native(root, stamp, revision='HEAD'):
    """Use published receipts only with exact native artifact/input identity.

    The original build stamp is retained verbatim and must match BOTH hashes in
    the immutable native release. A current snapshot never replaces old inputs.
    Delivery-only changes need a fresh build, not a fictional native rerender.
    """
    root = Path(root).resolve(); revision = native_revision(root, revision)
    baseline_file = safe_path(root, NATIVE); baseline_raw = baseline_file.read_bytes()
    if baseline_raw != _git_blob(root, revision, NATIVE): raise ValueError('published native baseline changed')
    baseline = load_json(baseline_raw)
    if (baseline.get('schema') != 2 or baseline.get('status') != 'export-and-check-passed'
            or baseline.get('visual_review') != 'all-sources-passed'
            or baseline.get('semantic_review') != 'all-sources-passed'):
        raise ValueError('a fully reviewed schema 2 native release is required')
    if (fingerprint(stamp) != baseline.get('build_identity')
            or fingerprint(stamp.get('source')) != baseline.get('source_fingerprint')):
        raise ValueError('original native build stamp is missing or stale; do not rebase native evidence')
    if not all(isinstance(stamp.get(field), dict) for field in ('source', 'assets', 'html')):
        raise ValueError('native stamp lacks exact source/build input maps')
    review_raw = safe_path(root, REVIEWS).read_bytes()
    if (baseline.get('review_file') != REVIEWS or digest(review_raw) != baseline.get('review_file_sha256')
            or review_raw != _git_blob(root, revision, REVIEWS)):
        raise ValueError('published native review evidence changed')
    reviews = load_json(review_raw).get('sources', [])
    by_include = {row['include']: row for row in reviews}
    catalog = load_json(safe_path(root, 'docs/diagram-catalog.json').read_bytes())['diagrams']
    includes = {row['include'] for row in catalog}
    if (len(includes) != len(catalog) or len(by_include) != len(reviews) or includes != set(by_include)
            or baseline.get('source_count') != len(includes)):
        raise ValueError('native/catalog/review source coverage differs')
    native_rows = baseline['entries'] + baseline.get('unused_entries', [])
    by_png = {row['png']: row for row in native_rows}
    if (len(by_png) != len(native_rows) or {row['include'] for row in native_rows} != includes
            or baseline.get('reference_count') != len(baseline['entries'])
            or baseline.get('post_count') != len({row['post'] for row in baseline['entries']})):
        raise ValueError('native output coverage/collision/count mismatch')
    production_inputs = {}
    def sealed(relative, mapping):
        path = safe_path(root, relative)
        expected = stamp[mapping].get(relative)
        _same_hash(path, expected, 'native raster input: ' + relative)
        production_inputs[relative] = expected
        return path.read_bytes()
    sealed(NATIVE_RENDERER, 'source')
    sealed(FONT, 'assets')
    font_prefix = 'assets/fonts/deterministic-export/'
    original_fonts = {name for name in stamp['source'] if name.startswith(font_prefix)} | {FONT}
    current_fonts = {path.relative_to(root).as_posix() for path in (root / font_prefix).rglob('*') if path.is_file()}
    if current_fonts != original_fonts: raise ValueError('native pinned font input set changed')
    for relative in sorted(original_fonts - {FONT}): sealed(relative, 'source')
    original_svgs = {'assets/img/diagrams/fhd-svg/' + include.removeprefix('diagrams/').removesuffix('.html') + '.svg' for include in includes}
    current_svgs = {path.relative_to(root).as_posix() for path in (root / 'assets/img/diagrams/fhd-svg').rglob('*.svg')}
    if original_svgs != current_svgs: raise ValueError('native authored SVG coverage changed')
    old_plugin = _git_blob(root, revision, PLUGIN)
    if digest(old_plugin) != stamp['source'].get(PLUGIN): raise ValueError('native proof generator differs from original build')
    native_style = proof_style(old_plugin)
    if proof_style(safe_path(root, PLUGIN).read_bytes()) != native_style:
        raise ValueError('native proof raster style changed; rerender rather than converting stale evidence')
    for include, review in sorted(by_include.items()):
        if not re.fullmatch(r'diagrams/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+\.html', include):
            raise ValueError('unsafe canonical include')
        include_raw = sealed('_includes/' + include, 'source')
        if (review.get('visual_status') != 'passed' or review.get('semantic_status') != 'passed'
                or review.get('actual_original_png_viewed') is not True
                or not review.get('notes') or not review.get('reviewed_at')
                or digest(source_fragment(include_raw.decode()).encode()) != review.get('source_sha256')):
            raise ValueError('native semantic/visual review is missing or stale: ' + include)
        svg_rel = 'assets/img/diagrams/fhd-svg/' + include.removeprefix('diagrams/').removesuffix('.html') + '.svg'
        svg_raw = sealed(svg_rel, 'source')
        if digest(svg_raw) != review.get('svg_sha256'): raise ValueError('authored SVG differs from native visual review')
        try: svg = ET.fromstring(svg_raw)
        except ET.ParseError as error: raise ValueError('invalid authored SVG') from error
        if (svg.get('width') != '1920' or svg.get('height') != '1080' or svg.get('viewBox') != '0 0 1920 1080'
                or svg.get('data-source-sha256') != review['source_sha256']):
            raise ValueError('native authored canvas/source identity changed')
        for image in svg.iter('{http://www.w3.org/2000/svg}image'):
            href = image.get('href', image.get('{http://www.w3.org/1999/xlink}href', ''))
            url = urlsplit(href)
            if (url.scheme or url.netloc or url.query or url.fragment or not url.path.startswith('/assets/')):
                raise ValueError('native source image is not an exact same-origin asset')
            sealed(unquote(url.path, errors='strict')[1:], 'assets')
    for png, row in sorted(by_png.items()):
        raw = public_path(root, png, 'png').read_bytes()
        _decode(raw, 'PNG')
        if (row.get('dimensions') != [1920, 1080] or digest(raw) != row.get('png_sha256')
                or by_include[row['include']]['png_sha256'] != digest(raw)):
            raise ValueError('native PNG changed or differs from its visual review: ' + png)
        if 'include_sha256' in row and row['include_sha256'] != production_inputs['_includes/' + row['include']]:
            raise ValueError('native include provenance differs')
        if 'post' in row and not re.fullmatch(r'[a-f0-9]{64}', row.get('receipt_sha256', '')):
            raise ValueError('published native render receipt identity is missing')
    return {'revision': revision, 'baseline': baseline, 'baseline_sha256': digest(baseline_raw),
            'review_sha256': digest(review_raw), 'stamp': stamp, 'production_inputs': production_inputs,
            'proof_style_sha256': digest(native_style.encode()), 'rows': by_png}


def convert(root, native_stamp, revision='HEAD', replace_reviewed=False):
    root = Path(root).resolve()
    stamp = load_json(Path(native_stamp).read_bytes())
    native = checked_native(root, stamp, revision)
    usage_bindings(root, validate_source(root), native)
    before = source_snapshot(root)
    # Validate every source/destination before creating any derivative.
    destinations = []
    previous = {}
    if replace_reviewed:
        saved_raw = safe_path(root, MANIFEST).read_bytes()
        if saved_raw != _git_blob(root, native_revision(root, 'HEAD'), MANIFEST):
            raise ValueError('previous sealed delivery differs from committed evidence')
        saved = load_json(saved_raw)
        if saved.get('status') != 'lossless-conversion-and-built-delivery-checked':
            raise ValueError('reviewed replacement requires the previous sealed delivery')
        previous = {row['webp']: row for row in saved['outputs']}
    for png in sorted(native['rows']):
        destination = public_path(root, webp_url(png), 'webp')
        if destination.exists():
            old = previous.get(webp_url(png))
            replacing = bool(old and old['png_sha256'] != native['rows'][png]['png_sha256'])
            if replacing:
                if digest(destination.read_bytes()) != old['webp_sha256']:
                    raise ValueError('previous reviewed WebP bytes changed; replacement refused')
            else:
                compare_pixels(public_path(root, png, 'png').read_bytes(), destination.read_bytes())
        else:
            replacing = False
        destinations.append((png, destination, replacing))
    for png, destination, replacing in destinations:
        raw = public_path(root, png, 'png').read_bytes()
        converted = encode_lossless(raw)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Do not silently repair a corrupt/altered previously published derivative.
        if destination.exists() and destination.read_bytes() != converted and not replacing:
            raise ValueError('existing WebP differs from the required lossless method 6 exact encoding')
        if not destination.exists() or replacing: destination.write_bytes(converted)
        compare_pixels(raw, destination.read_bytes())
    checked_native(root, stamp, native['revision'])
    if before != source_snapshot(root): raise ValueError('source changed during conversion')
    return {'source_count': native['baseline']['source_count'], 'outputs': len(destinations),
            'status': 'lossless-converted-not-release-sealed'}


def usage_bindings(root, plan, native):
    from downloads import cover_references
    if plan.get('blocked_count', 0) or any(row.get('status') == 'blocked-insertion' for row in plan['entries']):
        raise ValueError('incomplete/blocked body delivery mapping')
    by_png = native['rows']; bodies = []
    for entry in plan['entries']:
        old = by_png.get(entry['png'])
        if not old or any(old.get(key) != entry.get(key) for key in ('post', 'include', 'figure')):
            raise ValueError('body mapping lacks an exact published native occurrence')
        bodies.append({key: entry[key] for key in ('post', 'include', 'figure', 'png')} | {'webp': webp_url(entry['png'])})
    if len({row['webp'] for row in bodies}) != len(bodies): raise ValueError('body output collision')
    by_webp = {webp_url(png): row for png, row in by_png.items()}
    covers = []
    for cover in cover_references(root):
        old = by_webp.get(cover['webp'])
        if not old: raise ValueError('cover has no published native PNG provenance')
        covers.append(dict(cover, include=old['include'], png=old['png']))
    all_includes = {row['include'] for row in by_png.values()}
    body_includes = {row['include'] for row in bodies}
    if set(plan['unused_includes']) != all_includes - body_includes:
        raise ValueError('body-unused source coverage differs from native corpus')
    cover_includes = {row['include'] for row in covers}
    unused = [{'include': include, 'cover_used': include in cover_includes,
               'outputs': sorted(webp_url(png) for png, row in by_png.items() if row['include'] == include)}
              for include in sorted(plan['unused_includes'])]
    return bodies, sorted(covers, key=lambda row: (row['post'], row['field'])), unused


def checked_outputs(root, native, site=None, *, verify_encoding=False):
    outputs = []
    for png, row in sorted(native['rows'].items()):
        webp = webp_url(png)
        source = public_path(root, png, 'png').read_bytes()
        derivative = public_path(root, webp, 'webp').read_bytes()
        evidence = compare_pixels(source, derivative)
        if verify_encoding and encode_lossless(source) != derivative:
            raise ValueError('WebP differs from the required lossless method 6 exact encoding')
        if site is not None:
            if (public_path(site, png, 'png').read_bytes() != source
                    or public_path(site, webp, 'webp').read_bytes() != derivative):
                raise ValueError('built asset differs from native/derived published bytes')
        outputs.append({'include': row['include'], 'png': png, 'webp': webp} | evidence)
    if len({row['webp'] for row in outputs}) != len(outputs): raise ValueError('derivative output collision')
    return outputs


def fresh_build(root, site, plan):
    from downloads import built_assets_snapshot
    root = Path(root).resolve(); site = Path(site).resolve()
    if site == root or site.is_relative_to(root) or root.is_relative_to(site):
        raise ValueError('use a dedicated delivery build outside the repository')
    stamp = load_json(safe_path(site, '.diagram-download-build.json').read_bytes())
    if stamp.get('source') != source_snapshot(root): raise ValueError('source changed; make a fresh delivery build')
    html = {p.relative_to(site).as_posix(): digest(p.read_bytes()) for p in sorted(site.rglob('*.html'))}
    if stamp.get('html') != html or stamp.get('assets') != built_assets_snapshot(site, plan):
        raise ValueError('built HTML/assets changed; make a fresh delivery build')
    for path in set(stamp['assets']) | set(stamp['html']): safe_path(site, path)
    return stamp


def _payload(root, native, stamp, site=None, *, verify_encoding=False):
    from downloads import built_plan, post_pages, Viewer
    plan = validate_source(root)
    bodies, covers, unused = usage_bindings(root, plan, native)
    if stamp.get('source') != source_snapshot(root): raise ValueError('source fingerprint changed; rebuild and seal the derivative release')
    outputs = checked_outputs(root, native, site, verify_encoding=verify_encoding)
    for row in outputs:
        if (stamp.get('assets', {}).get(row['webp'][1:]) != row['webp_sha256']
                or stamp.get('assets', {}).get(row['png'][1:]) != row['png_sha256']):
            raise ValueError('sealed build lacks full native/WebP asset coverage')
    if site is not None:
        rows = built_plan(root, site, plan)
        sidecar_text = safe_path(site, 'assets/data/diagram-posts.json').read_text()
        pages = post_pages(site, plan, (row['post'] for row in covers))
        for body in bodies:
            body['page'] = pages[body['post']]
        for cover in covers:
            cover['page'] = pages[cover['post']]
            images = Viewer(safe_path(site, cover['page']).read_text()).images
            selected = [image for image in images if image.get('src') == cover['webp']]
            if not selected:
                raise ValueError('built cover does not deliver the same WebP')
            if any(image.get('srcset') is not None for image in selected):
                raise ValueError('built cover srcset can select a different asset')
            if any(image.get('src') == cover['png'] for image in images):
                raise ValueError('native PNG slipped into built cover delivery')
        if len(rows) != len(bodies): raise ValueError('built body coverage differs')
    else:
        # Resolve page ownership from the exact sealed URL sidecar, never from
        # the editable release body rows themselves. No new build is claimed.
        saved = load_json(safe_path(root, MANIFEST).read_bytes())
        sidecar_text = saved['post_map_text']
        pages = post_pages(root, plan, (row['post'] for row in covers),
                           url_data=load_json(sidecar_text), require_files=False)
        for body in bodies: body['page'] = pages[body['post']]
        for cover in covers: cover['page'] = pages[cover['post']]
    if digest(sidecar_text.encode()) != stamp.get('assets', {}).get('assets/data/diagram-posts.json'):
        raise ValueError('sealed post/page ownership sidecar differs from build bytes')
    for row in bodies + covers:
        page = row.get('page')
        safe_path(root, page)  # Reject traversal, independently of the build root.
        if page not in stamp.get('html', {}): raise ValueError('sealed build lacks mapped page coverage')
    from PIL import __version__ as pillow_version, features
    return {'schema': 1, 'status': 'lossless-conversion-and-built-delivery-checked',
            'source_count': native['baseline']['source_count'], 'output_count': len(outputs),
            'reference_count': len(bodies), 'post_count': plan['post_count'], 'cover_count': len(covers),
            'body_unused_count': len(unused), 'genuinely_unused_count': sum(not row['cover_used'] for row in unused),
            'conversion': CONVERSION,
            'encoder': {'pillow': pillow_version, 'libwebp': features.version('webp')},
            'native_baseline': {'path': NATIVE, 'revision': native['revision'], 'sha256': native['baseline_sha256'],
                                'source_fingerprint': native['baseline']['source_fingerprint'],
                                'build_identity': native['baseline']['build_identity'],
                                'review_file': REVIEWS, 'review_file_sha256': native['review_sha256'],
                                'review_scope': 'prior native PNG visual/semantic review; exact artifacts and raster inputs unchanged'},
            'native_build_stamp': native['stamp'], 'native_production_inputs': native['production_inputs'],
            'native_proof_style_sha256': native['proof_style_sha256'],
            'source_fingerprint': fingerprint(stamp['source']), 'build_identity': fingerprint(stamp),
            'build': stamp, 'post_map_text': sidecar_text, 'outputs': outputs, 'body_entries': bodies, 'cover_entries': covers,
            'unused_sources': unused,
            'browser_evidence': {'status': 'not-recorded-by-this-adapter',
                                 'scope': 'No native rerender, new visual review or browser responsiveness proof is claimed.'}}


def seal(root, site, native_stamp, revision='HEAD'):
    root = Path(root).resolve(); site = Path(site).resolve()
    stamp_native = load_json(Path(native_stamp).read_bytes())
    native = checked_native(root, stamp_native, revision)
    plan = validate_source(root); stamp = fresh_build(root, site, plan)
    payload = _payload(root, native, stamp, site, verify_encoding=True)
    # A long conversion/check may never bless inputs changed halfway through.
    checked_native(root, stamp_native, native['revision'])
    if fresh_build(root, site, plan) != stamp: raise ValueError('build changed while sealing')
    safe_path(root, MANIFEST).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return {'outputs': payload['output_count'], 'references': payload['reference_count'],
            'covers': payload['cover_count'], 'body_unused': payload['body_unused_count'], 'status': payload['status']}


def check(root, site=None):
    root = Path(root).resolve()
    manifest_path = safe_path(root, MANIFEST)
    manifest_raw = manifest_path.read_bytes()
    saved = load_json(manifest_raw)
    if saved.get('status') != 'lossless-conversion-and-built-delivery-checked': raise ValueError('WebP release is not checked')
    native = checked_native(root, saved['native_build_stamp'], saved['native_baseline']['revision'])
    stamp = saved['build']
    if site is not None:
        site = Path(site).resolve()
        if fresh_build(root, site, validate_source(root)) != stamp: raise ValueError('current build differs from sealed delivery')
    expected = _payload(root, native, stamp, site)
    if expected != saved: raise ValueError('WebP release manifest coverage, bytes or identity differs')
    checked_native(root, native['stamp'], native['revision'])
    if stamp['source'] != source_snapshot(root): raise ValueError('source changed during release validation')
    if site is not None and fresh_build(root, site, validate_source(root)) != stamp:
        raise ValueError('build changed during release validation')
    if manifest_path.read_bytes() != manifest_raw:
        raise ValueError('manifest changed during release validation')
    return {'sources': saved['source_count'], 'outputs': saved['output_count'], 'references': saved['reference_count'],
            'covers': saved['cover_count'], 'passed': True, 'live_build_checked': site is not None}


def verify_staged(root):
    root = Path(root).resolve()
    manifest_path = safe_path(root, MANIFEST)
    manifest_raw = manifest_path.read_bytes()
    stage_raw = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=root)
    report = check(root)
    if manifest_path.read_bytes() != manifest_raw:
        raise ValueError('manifest changed between release and index validation')
    saved = load_json(manifest_raw)
    snapshot = source_snapshot(root)
    required = set(snapshot) | {MANIFEST, NATIVE, REVIEWS} | set(saved['native_production_inputs'])
    for row in saved['outputs']: required.update((row['png'][1:], row['webp'][1:]))
    for relative in required: safe_path(root, relative)
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0'))
    missing = required - tracked
    # Retain the normal gate's deliberately local, ignored Bundler/cache inputs;
    # never waive a real authored image, native artifact, WebP or release record.
    local = {path for path in missing if path in snapshot and (path == 'Gemfile.lock'
             or any(part in ('.jekyll-cache', '_site') for part in Path(path).parts))}
    if local:
        ignored = subprocess.run(['git', 'check-ignore', '-z', '--stdin'], cwd=root,
                                 input='\0'.join(sorted(local)).encode() + b'\0', capture_output=True)
        if ignored.returncode not in (0, 1): raise ValueError('cannot verify local input ignore policy')
        required -= set(ignored.stdout.decode().split('\0')) & local
    if not required.issubset(tracked): raise ValueError('validated source/native/WebP evidence is absent from index')
    indexed = stage_raw.decode().split('\0'); by_path = {}
    for row in indexed:
        if not row: continue
        metadata, relative = row.split('\t', 1)
        mode, oid, stage = metadata.split()
        if relative in required:
            if mode not in ('100644', '100755') or stage != '0':
                raise ValueError('validated input is not a regular, unmerged index file')
            by_path[relative] = oid
    # Diff's stat cache, assume-unchanged and skip-worktree flags are not proof
    # of indexed bytes. Compare real blob identities for every required input.
    object_format = subprocess.check_output(['git', 'rev-parse', '--show-object-format'], cwd=root, text=True).strip()
    if object_format not in ('sha1', 'sha256'): raise ValueError('unsupported Git object hash format')
    sealed = dict(saved['build']['source']) | saved['native_production_inputs']
    sealed.update({NATIVE: saved['native_baseline']['sha256'], REVIEWS: saved['native_baseline']['review_file_sha256']})
    for output in saved['outputs']:
        sealed[output['png'][1:]] = output['png_sha256']; sealed[output['webp'][1:]] = output['webp_sha256']
    for relative in sorted(required):
        raw = safe_path(root, relative).read_bytes()
        if relative in sealed and digest(raw) != sealed[relative]:
            raise ValueError('validated bytes changed during index verification: ' + relative)
        blob = hashlib.new(object_format, b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if blob != by_path.get(relative): raise ValueError('index differs from validated working-tree bytes: ' + relative)
    if source_snapshot(root) != saved['build']['source']:
        raise ValueError('source changed during index verification')
    if manifest_path.read_bytes() != manifest_raw:
        raise ValueError('manifest changed during index validation')
    if subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=root) != stage_raw:
        raise ValueError('index changed during release validation')
    return dict(report, indexed=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['convert', 'seal', 'check'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--site', type=Path, help='fresh dedicated delivery build outside the repository')
    parser.add_argument('--native-stamp', type=Path, help='read-only original native build stamp; never a newly rebased snapshot')
    parser.add_argument('--native-revision', default='HEAD', help='native evidence Git commit, or sha256:<exact native baseline hash> for a freshly reviewed release')
    parser.add_argument('--staged', action='store_true', help='check exact index bytes as well as the release')
    parser.add_argument('--replace-reviewed', action='store_true', help='replace only unchanged sealed old WebP bytes whose newly reviewed native PNG changed')
    args = parser.parse_args(argv)
    if args.action in ('convert', 'seal') and not args.native_stamp: parser.error('--native-stamp is required')
    if args.action == 'seal' and not args.site: parser.error('--site is required')
    if args.staged and args.action != 'check': parser.error('--staged applies only to check')
    try:
        if args.action == 'convert': result = convert(args.root, args.native_stamp, args.native_revision, args.replace_reviewed)
        elif args.action == 'seal': result = seal(args.root, args.site, args.native_stamp, args.native_revision)
        else:
            result = check(args.root, args.site)
            if args.staged: result = dict(verify_staged(args.root), live_build_checked=args.site is not None)
        print(json.dumps(result)); return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'WebP release blocked: ' + str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
