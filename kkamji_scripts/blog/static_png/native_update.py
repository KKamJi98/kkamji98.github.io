"""Read-only validation of reviewed native deltas against an immutable archive."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zlib
from urllib.parse import unquote, urlsplit

from fhd_reuse import FONT, PROOF, REQUIRED, renderer_literal, source_fragment
from pipeline import digest, fingerprint

MANIFEST = 'docs/diagram-native-update.json'


def checked_update(root, revision, baseline, stamp):
    """Return sealed delta evidence, or None when no explicit update exists.

    The saved render stamp binds only actual render inputs. It is never rebased
    onto the current global snapshot, nor substituted for the old native stamp.
    Archive-wide verification and overlay application belong to checked_native.
    """
    import webp_release as w  # The publisher imports this helper in turn.
    root = Path(root).resolve(); path = w.safe_path(root, MANIFEST)
    if not path.exists(): return None
    raw = path.read_bytes(); update = w.load_json(raw)
    if (not isinstance(update, dict) or type(update.get('schema')) is not int or update['schema'] != 1
            or update.get('status') != 'fresh-native-update-reviewed'):
        raise ValueError('a reviewed schema 1 native update is required')
    revision = w.native_revision(root, revision)
    if update.get('base_revision') != revision: raise ValueError('native update base revision differs')
    files = {MANIFEST: digest(raw)}

    def sealed(relative, expected=...):
        content = w.safe_path(root, relative).read_bytes(); sha = digest(content)
        if expected is not ... and (not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected) or sha != expected):
            raise ValueError('native update artifact hash differs: ' + relative)
        if relative in files and files[relative] != sha: raise ValueError('update input changed while checking')
        files[relative] = sha
        return content

    baseline_raw = sealed(w.NATIVE, update.get('base_manifest_sha256', ''))
    review_raw = sealed(w.REVIEWS, update.get('base_review_sha256', ''))
    old_reviews = w.load_json(review_raw)
    if (w.load_json(baseline_raw) != baseline or baseline_raw != w._git_blob(root, revision, w.NATIVE)
            or review_raw != w._git_blob(root, revision, w.REVIEWS)
            or baseline.get('review_file') != w.REVIEWS or digest(review_raw) != baseline.get('review_file_sha256')
            or not isinstance(old_reviews, dict) or baseline.get('schema') != 2
            or baseline.get('status') != 'export-and-check-passed'
            or baseline.get('visual_review') != 'all-sources-passed' or baseline.get('semantic_review') != 'all-sources-passed'
            or fingerprint(stamp) != baseline.get('build_identity')
            or fingerprint(stamp.get('source')) != baseline.get('source_fingerprint')):
        raise ValueError('immutable native baseline, review or original stamp differs')
    rows = baseline['entries'] + baseline.get('unused_entries', [])
    archive = {row['png']: row for row in rows}
    records = update.get('sources')
    if not isinstance(records, list) or not records: raise ValueError('native update source list is empty')
    sources = {}; overrides = {}; destinations = set()
    old_plugin = w._git_blob(root, revision, w.PLUGIN)
    if digest(old_plugin) != stamp['source'].get(w.PLUGIN): raise ValueError('original native proof plugin differs')
    style = w.proof_style(old_plugin)
    if w.proof_style(sealed(w.PLUGIN)) != style: raise ValueError('native proof raster style changed')
    font_raw = sealed(FONT, stamp['assets'].get(FONT, ''))
    renderer = sealed(w.NATIVE_RENDERER, stamp['source'].get(w.NATIVE_RENDERER, ''))
    renderer_js = renderer_literal(w.safe_path(root, w.NATIVE_RENDERER))
    for row in records:
        if not isinstance(row, dict): raise ValueError('native update source record is not an object')
        include = row.get('include')
        if (not isinstance(include, str) or not re.fullmatch(r'diagrams/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+\.html', include)
                or include in sources): raise ValueError('unsafe or duplicate native update include')
        if not isinstance(row.get('old_png'), str): raise ValueError('original native PNG path is missing')
        old = archive.get(row['old_png'])
        if old is None or old['include'] != include: raise ValueError('update does not bind its original native PNG')
        old_raw = w.public_path(root, old['png'], 'png').read_bytes(); w._decode(old_raw, 'PNG')
        if digest(old_raw) != old.get('png_sha256'): raise ValueError('original native PNG changed')
        files[old['png'][1:]] = digest(old_raw)
        new = row.get('new_png')
        if not isinstance(new, str): raise ValueError('new native PNG path is missing')
        w.public_path(root, new, 'png')
        if (not new.startswith('/assets/img/diagrams/native-updates/') or new in archive or new in destinations):
            raise ValueError('native update PNG must be new, noncolliding native-updates evidence')
        png_raw = sealed(new[1:], row.get('png_sha256', '')); w._decode(png_raw, 'PNG')
        # Pillow verification stops before IEND, so verify every chunk CRC too.
        offset = 8
        while offset < len(png_raw):
            end = offset + 8 + int.from_bytes(png_raw[offset:offset+4], 'big')
            if (offset + 12 > len(png_raw) or end + 4 > len(png_raw)
                    or zlib.crc32(png_raw[offset+4:end]) != int.from_bytes(png_raw[end:end+4], 'big')
                    or (png_raw[offset+4:offset+8] == b'IEND' and end + 4 != len(png_raw))):
                raise ValueError('invalid native update PNG chunk CRC or boundary')
            offset = end + 4
        if digest(png_raw) == digest(old_raw): raise ValueError('native update cannot relabel the original PNG')
        destinations.add(new)
        evidence = {}
        for key in ('receipt', 'review', 'render_build'):
            relative = row.get(key + '_file')
            if not isinstance(relative, str) or not relative.startswith('docs/') or not relative.endswith('.json'):
                raise ValueError('native update evidence must be rooted docs JSON')
            evidence[key] = w.load_json(sealed(relative, row.get(key + '_sha256', '')))
            if not isinstance(evidence[key], dict): raise ValueError('native update evidence is not an object')
        if row['receipt_file'] == row['review_file']: raise ValueError('review must be separate from render receipt')
        receipt = evidence['receipt']; review = evidence['review']; build = evidence['render_build']
        include_rel = '_includes/' + include
        svg_rel = 'assets/img/diagrams/fhd-svg/' + include.removeprefix('diagrams/').removesuffix('.html') + '.svg'
        include_raw = sealed(include_rel); svg_raw = sealed(svg_rel, row.get('svg_sha256', ''))
        source_sha = digest(source_fragment(include_raw.decode()).encode())
        if source_sha != row.get('source_sha256'): raise ValueError('current source fragment differs from update')
        try: svg = ET.fromstring(svg_raw)
        except ET.ParseError as error: raise ValueError('invalid updated SVG') from error
        if (svg.get('width') != '1920' or svg.get('height') != '1080' or svg.get('viewBox') != '0 0 1920 1080'
                or svg.get('data-source-sha256') != source_sha): raise ValueError('updated SVG canvas/source identity differs')
        images = {}; assets = {FONT: digest(font_raw)}
        for image in svg.iter('{http://www.w3.org/2000/svg}image'):
            href = image.get('href', image.get('{http://www.w3.org/1999/xlink}href', ''))
            url = urlsplit(href)
            if (url.scheme or url.netloc or url.query or url.fragment or not url.path.startswith('/assets/')):
                raise ValueError('updated SVG image is not an exact same-origin asset')
            relative = unquote(url.path, errors='strict')[1:]
            images[href] = digest(sealed(relative)); assets[relative] = images[href]
        metrics = receipt.get('metrics', {}); inputs = receipt.get('per_source_inputs')
        browser = metrics.get('browser') if isinstance(metrics, dict) else None
        if not isinstance(browser, str) or not browser.strip(): raise ValueError('observed render browser identity is missing')
        expected_inputs = {'schema': 1, 'include': include, 'original_source_sha256': source_sha,
                           'svg_sha256': digest(svg_raw), 'font_sha256': digest(font_raw), 'images': images,
                           'http_style_sha256': digest(style.encode()), 'renderer_js_sha256': digest(renderer_js.encode()),
                           'browser': browser}
        if (not isinstance(inputs, dict) or set(inputs) != REQUIRED or type(inputs.get('schema')) is not int
                or inputs != expected_inputs or receipt.get('per_source_fingerprint') != fingerprint(inputs)
                or receipt.get('automated_status') != 'passed' or metrics.get('issues') != []
                or metrics.get('canvas') != [1920, 1080] or receipt.get('font_sha256') != assets[FONT]):
            raise ValueError('fresh native render receipt inputs or automated metrics differ')
        if (not all(isinstance(build.get(key), dict) for key in ('source', 'assets', 'html'))
                or receipt.get('build_identity') != fingerprint(build) or fingerprint(build) == fingerprint(stamp)
                or not re.fullmatch(r'[a-f0-9]{64}', str(build['html'].get(PROOF, '')))):
            raise ValueError('fresh original render build identity is missing or stale')
        actual_source = {include_rel: digest(include_raw), svg_rel: digest(svg_raw), w.NATIVE_RENDERER: digest(renderer)}
        if (any(build['source'].get(relative) != sha for relative, sha in actual_source.items())
                or any(build['assets'].get(relative) != sha for relative, sha in assets.items())):
            raise ValueError('saved render build does not bind actual source/SVG/font/image bytes')
        identity = {'include': include, 'source_sha256': source_sha, 'svg_sha256': digest(svg_raw), 'png_sha256': digest(png_raw)}
        if any(item.get(key) != value for item in (receipt, review) for key, value in identity.items()):
            raise ValueError('render receipt or independent review refers to different native artwork')
        if (review.get('visual_status') != 'passed' or review.get('semantic_status') != 'passed'
                or review.get('actual_original_png_viewed') is not True
                or not all(isinstance(review.get(key), str) and review[key].strip() for key in ('reviewed_at', 'notes'))):
            raise ValueError('independent original PNG visual/semantic review is missing')
        sources[include] = dict(row, receipt=receipt, review=review)
        overrides.update({include_rel: digest(include_raw), svg_rel: digest(svg_raw)})
    for relative, sha in files.items(): w._same_hash(w.safe_path(root, relative), sha, 'native update readback')
    return {'path': MANIFEST, 'sha256': digest(raw), 'sources': sources, 'files': files, 'input_overrides': overrides}
