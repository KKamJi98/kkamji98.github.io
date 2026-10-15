"""Read-only additive admission; never rewrite or rebase original native evidence.

Schema 1 has base_revision, base_manifest_sha256, base_review_sha256,
base_catalog_sha256 and sources, with status fresh-native-additions-reviewed.
Each source binds the exact post/include/figure/instance/occurrence/png tuple,
include/source/svg/png SHA-256, three independent JSON evidence files
(receipt, review, render_build), and the preserved actual HTTP render_fixture
HTML. Every evidence path and SHA is explicit. No old_png/new_png is accepted.
The renderer's not-run review fields remain untouched; only separate actual
PNG visual/semantic review can authorize admission.
"""
from html import escape
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zlib
from urllib.parse import unquote, urlsplit

from fhd_reuse import FONT, PROOF, REQUIRED, renderer_literal, source_fragment, style_hash
from pipeline import digest, fingerprint

MANIFEST = 'docs/diagram-native-additions.json'
EVIDENCE = 'docs/diagram-native-additions/'
CATALOG = 'docs/diagram-catalog.json'
TUPLE = ('post', 'include', 'figure', 'instance', 'occurrence', 'png')
HEADER = {'schema', 'status', 'base_revision', 'base_manifest_sha256', 'base_review_sha256',
          'base_catalog_sha256', 'sources'}
FIELDS = set(TUPLE) | {'include_sha256', 'source_sha256', 'svg_sha256', 'png_sha256'} | {
    key + suffix for key in ('receipt', 'review', 'render_build', 'render_fixture')
    for suffix in ('_file', '_sha256')}


def declared_additions(root):
    """Discover explicit output paths, not permission to render, convert or seal."""
    import webp_release as w
    path = w.safe_path(root, MANIFEST)
    if not path.exists(): return None
    raw = path.read_bytes(); data = w.load_json(raw)
    if (not isinstance(data, dict) or set(data) != HEADER or type(data.get('schema')) is not int
            or data['schema'] != 1 or data.get('status') != 'fresh-native-additions-reviewed'
            or not isinstance(data.get('sources'), list) or not data['sources']):
        raise ValueError('a reviewed schema 1 native additions declaration is required')
    includes = set(); outputs = set()
    for row in data['sources']:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError('native addition fields differ; replacement aliases are not accepted')
        include = row['include']
        if (not isinstance(include, str) or not re.fullmatch(r'diagrams/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+\.html', include)
                or include in includes): raise ValueError('unsafe or duplicate native addition include')
        post = row['post']; w.safe_path(root, post)
        if not post.startswith('_posts/') or not post.endswith('.md'):
            raise ValueError('native addition must bind a rooted post')
        if (not isinstance(row['instance'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]*', row['instance'])
                or type(row['occurrence']) is not int or row['occurrence'] < 1
                or not isinstance(row['figure'], str) or not row['figure'].strip()):
            raise ValueError('native addition occurrence identity differs')
        identity = {key: row[key] for key in ('post', 'include', 'instance', 'occurrence')}
        expected = ('/assets/img/diagrams/' + include.removeprefix('diagrams/').removesuffix('.html')
                    + '--' + fingerprint(identity)[:16] + '.png')
        w.public_path(root, row['png'], 'png')
        if row['png'] != expected or row['png'] in outputs:
            raise ValueError('native addition lacks the standard hashed PNG tuple')
        includes.add(include); outputs.add(row['png'])
    return {'data': data, 'raw': raw}


def checked_additions(root, revision, baseline, stamp):
    """Authenticate additive sources independently of immutable or replacement rows."""
    import webp_release as w
    from downloads import discover
    root = Path(root).resolve(); declaration = declared_additions(root)
    if declaration is None: return None
    data = declaration['data']; raw = declaration['raw']
    revision = w.native_revision(root, revision)
    if data['base_revision'] != revision: raise ValueError('native additions base revision differs')
    files = {MANIFEST: digest(raw)}

    def sealed(relative, expected=...):
        content = w.safe_path(root, relative).read_bytes(); sha = digest(content)
        if expected is not ... and (not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected) or sha != expected):
            raise ValueError('native addition artifact hash differs: ' + relative)
        if relative in files and files[relative] != sha: raise ValueError('native addition input changed while checking')
        files[relative] = sha
        return content

    original_raw = sealed(w.NATIVE, data['base_manifest_sha256'])
    review_raw = sealed(w.REVIEWS, data['base_review_sha256'])
    catalog_raw = w._git_blob(root, revision, CATALOG)
    if (w.load_json(original_raw) != baseline or original_raw != w._git_blob(root, revision, w.NATIVE)
            or review_raw != w._git_blob(root, revision, w.REVIEWS)
            or baseline.get('schema') != 2 or baseline.get('status') != 'export-and-check-passed'
            or baseline.get('visual_review') != 'all-sources-passed' or baseline.get('semantic_review') != 'all-sources-passed'
            or baseline.get('review_file') != w.REVIEWS or baseline.get('review_file_sha256') != digest(review_raw)
            or fingerprint(stamp) != baseline.get('build_identity')
            or fingerprint(stamp.get('source')) != baseline.get('source_fingerprint')
            or digest(catalog_raw) != data['base_catalog_sha256']
            or stamp['source'].get(CATALOG) != digest(catalog_raw)):
        raise ValueError('immutable native additions baseline, review, catalog or original stamp differs')
    old_catalog = w.load_json(catalog_raw)['diagrams']
    originals = {row['include'] for row in old_catalog}
    reviews = w.load_json(review_raw)['sources']
    if (len(originals) != len(old_catalog) or len({r['include'] for r in reviews}) != len(reviews)
            or originals != {r['include'] for r in reviews} or baseline['source_count'] != len(originals)):
        raise ValueError('immutable catalog/review source coverage differs')
    records = data['sources']; added = {row['include'] for row in records}
    catalog = w.load_json(sealed(CATALOG))['diagrams']
    current = {row['include'] for row in catalog}
    if added & originals or len(current) != len(catalog) or current != originals | added:
        raise ValueError('native additions catalog must be original plus added sources only')
    plan, _ = discover(root)
    live = [row for row in plan['entries'] if row['include'] in added]
    if (len(live) != len(records) or {row['include'] for row in live} != added
            or any(row['status'] == 'blocked-insertion' for row in live)):
        raise ValueError('native additions require exact single body occurrence coverage')
    live_by_include = {row['include']: row for row in live}
    archive = baseline['entries'] + baseline.get('unused_entries', [])
    archive_paths = {row['png'] for row in archive}
    old_hashes = {row['png_sha256'] for row in archive}
    if len(archive_paths) != len(archive): raise ValueError('immutable native archive output collision')
    for row in archive:
        if digest(w.public_path(root, row['png'], 'png').read_bytes()) != row['png_sha256']:
            raise ValueError('immutable original native PNG changed')
    # These are frozen raster inputs, not the adapter or delivery CSS.
    old_plugin = w._git_blob(root, revision, w.PLUGIN)
    if digest(old_plugin) != stamp['source'].get(w.PLUGIN): raise ValueError('original native proof plugin differs')
    style = w.proof_style(old_plugin)
    plugin_raw = sealed(w.PLUGIN)
    if w.proof_style(plugin_raw) != style: raise ValueError('native proof raster style changed')
    renderer_raw = sealed(w.NATIVE_RENDERER, stamp['source'].get(w.NATIVE_RENDERER, ''))
    renderer_js = renderer_literal(w.safe_path(root, w.NATIVE_RENDERER))
    font_raw = sealed(FONT, stamp['assets'].get(FONT, ''))
    font_prefix = 'assets/fonts/deterministic-export/'
    fonts = {p for p in stamp['source'] if p.startswith(font_prefix)} | {FONT}
    if fonts != {p.relative_to(root).as_posix() for p in (root / font_prefix).rglob('*') if p.is_file()}:
        raise ValueError('native pinned font input set changed')
    for relative in sorted(fonts - {FONT}): sealed(relative, stamp['source'][relative])
    sources = {}; rows = {}; inputs = {}; admitted_hashes = set()
    independent = set()
    for row in records:
        include = row['include']; png = row['png']
        if (any(row[key] != live_by_include[include][key] for key in TUPLE)
                or png in archive_paths or '_includes/' + include in stamp['source']):
            raise ValueError('native addition lacks an exact new post/include/figure/PNG tuple')
        source_rel = '_includes/' + include
        svg_rel = 'assets/img/diagrams/fhd-svg/' + include.removeprefix('diagrams/').removesuffix('.html') + '.svg'
        include_raw = sealed(source_rel, row['include_sha256'])
        svg_raw = sealed(svg_rel, row['svg_sha256'])
        source_sha = digest(source_fragment(include_raw.decode()).encode())
        if source_sha != row['source_sha256']: raise ValueError('added semantic source hash differs')
        if (source_sha in {review['source_sha256'] for review in reviews}
                or digest(svg_raw) in {review['svg_sha256'] for review in reviews}
                or source_sha in {source['source_sha256'] for source in sources.values()}):
            raise ValueError('native addition cannot relabel an original or another added source')
        try: svg = ET.fromstring(svg_raw)
        except ET.ParseError as error: raise ValueError('invalid added SVG') from error
        if (svg.tag != '{http://www.w3.org/2000/svg}svg' or svg.get('width') != '1920' or svg.get('height') != '1080'
                or svg.get('viewBox') != '0 0 1920 1080' or svg.get('data-source-sha256') != source_sha):
            raise ValueError('added SVG canvas/source identity differs')
        png_raw = sealed(png[1:], row['png_sha256']); w._decode(png_raw, 'PNG')
        offset = 8
        while offset < len(png_raw):
            end = offset + 8 + int.from_bytes(png_raw[offset:offset+4], 'big')
            if (offset + 12 > len(png_raw) or end + 4 > len(png_raw)
                    or zlib.crc32(png_raw[offset+4:end]) != int.from_bytes(png_raw[end:end+4], 'big')
                    or (png_raw[offset+4:offset+8] == b'IEND' and end + 4 != len(png_raw))):
                raise ValueError('invalid native addition PNG chunk CRC or boundary')
            offset = end + 4
        if digest(png_raw) in old_hashes | admitted_hashes:
            raise ValueError('native addition cannot relabel an original or another added PNG')
        admitted_hashes.add(digest(png_raw))
        evidence = {}
        for key in ('receipt', 'review', 'render_build', 'render_fixture'):
            relative = row[key + '_file']
            suffix = '.html' if key == 'render_fixture' else '.json'
            if not isinstance(relative, str) or not relative.startswith(EVIDENCE) or not relative.endswith(suffix):
                raise ValueError('native addition evidence must use its dedicated rooted proof directory')
            content = sealed(relative, row[key + '_sha256'])
            evidence[key] = content if key == 'render_fixture' else w.load_json(content)
            if key != 'render_fixture' and not isinstance(evidence[key], dict):
                raise ValueError('native addition JSON evidence is not an object')
        if (row['receipt_file'] == row['review_file'] or row['receipt_file'] in independent
                or row['review_file'] in independent or len({row[k + '_file'] for k in evidence}) != 4):
            raise ValueError('native addition review must be independent of render evidence')
        independent.update((row['receipt_file'], row['review_file']))
        receipt = evidence['receipt']; review = evidence['review']; build = evidence['render_build']
        assets = {FONT: digest(font_raw)}; images = {}
        for image in svg.iter('{http://www.w3.org/2000/svg}image'):
            href = image.get('href', image.get('{http://www.w3.org/1999/xlink}href', ''))
            url = urlsplit(href)
            if url.scheme or url.netloc or url.query or url.fragment or not url.path.startswith('/assets/'):
                raise ValueError('added SVG image is not an exact same-origin asset')
            relative = unquote(url.path, errors='strict')[1:]
            images[href] = digest(sealed(relative)); assets[relative] = images[href]
            inputs[relative] = images[href]
        metrics = receipt.get('metrics', {}); observed = receipt.get('per_source_inputs')
        browser = metrics.get('browser') if isinstance(metrics, dict) else None
        if not isinstance(browser, str) or not browser.strip(): raise ValueError('observed render browser identity is missing')
        expected = {'schema': 1, 'include': include, 'original_source_sha256': source_sha,
                    'svg_sha256': digest(svg_raw), 'font_sha256': digest(font_raw), 'images': images,
                    'http_style_sha256': digest(style.encode()), 'renderer_js_sha256': digest(renderer_js.encode()),
                    'browser': browser}
        if (not isinstance(observed, dict) or set(observed) != REQUIRED or type(observed.get('schema')) is not int
                or observed != expected or receipt.get('per_source_fingerprint') != fingerprint(observed)
                or receipt.get('automated_status') != 'passed' or metrics.get('issues') != []
                or metrics.get('canvas') != [1920, 1080] or metrics.get('viewBox') != '0 0 1920 1080'
                or receipt.get('png_dimensions') != [1920, 1080] or receipt.get('font_sha256') != assets[FONT]):
            raise ValueError('fresh additive render receipt inputs or automated metrics differ')
        fixture = evidence['render_fixture']; index = receipt.get('index')
        if (not all(isinstance(build.get(k), dict) for k in ('source', 'assets', 'html'))
                or receipt.get('build_identity') != fingerprint(build) or fingerprint(build) == fingerprint(stamp)
                or build['html'].get(PROOF) != digest(fixture) or style_hash(fixture.decode()) != digest(style.encode())
                or type(index) is not int or index != [r['include'] for r in catalog].index(include)):
            raise ValueError('fresh render build or actual HTTP fixture identity differs')
        name = escape(include, quote=True)
        card = f'<section class="proof-card" data-index="{index}" data-include="{name}"><h2>{name}</h2>{svg_raw.decode()}</section>'
        if fixture.decode().count(card) != 1: raise ValueError('actual render fixture lacks the exact authored SVG card')
        actual_source = {source_rel: digest(include_raw), svg_rel: digest(svg_raw), CATALOG: files[CATALOG],
                         w.NATIVE_RENDERER: digest(renderer_raw), w.PLUGIN: digest(plugin_raw)}
        actual_source.update({relative: files[relative] for relative in fonts - {FONT}})
        if (any(build['source'].get(p) != sha for p, sha in actual_source.items())
                or any(build['assets'].get(p) != sha for p, sha in assets.items())):
            raise ValueError('saved additive render build lacks actual source/SVG/font/image bytes')
        identity = {'include': include, 'source_sha256': source_sha, 'svg_sha256': digest(svg_raw), 'png_sha256': digest(png_raw)}
        if any(item.get(k) != value for item in (receipt, review) for k, value in identity.items()):
            raise ValueError('additive render receipt or independent review refers to different native artwork')
        if (review.get('visual_status') != 'passed' or review.get('semantic_status') != 'passed'
                or review.get('actual_original_png_viewed') is not True
                or not all(isinstance(review.get(k), str) and review[k].strip() for k in ('reviewed_at', 'notes'))):
            raise ValueError('independent actual original PNG visual/semantic review is missing')
        sources[include] = dict(row, receipt=receipt, review=review)
        rows[png] = {key: row[key] for key in TUPLE} | {
            'dimensions': [1920, 1080], 'png_sha256': digest(png_raw),
            'include_sha256': digest(include_raw), 'receipt_sha256': row['receipt_sha256']}
        inputs.update({source_rel: digest(include_raw), svg_rel: digest(svg_raw)})
    for relative, sha in files.items(): w._same_hash(w.safe_path(root, relative), sha, 'native additions readback')
    return {'path': MANIFEST, 'sha256': digest(raw), 'sources': sources, 'rows': rows, 'files': files,
            'production_inputs': inputs}
