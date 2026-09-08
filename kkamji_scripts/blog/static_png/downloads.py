#!/usr/bin/env python3
"""Wire canonical PNG siblings, stamp a fresh build, export and verify exact URLs."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit

from corpus import Figures, inventory
from pipeline import digest, fingerprint

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = 'docs/diagram-downloads.json'
INCLUDE = re.compile(r'{%\s*include\s+(diagrams/[^\s%]+)(.*?)%}', re.S)
HELPER = re.compile(r'^[ \t]*{% include diagrams/download.html png="[^"]+" %}\r?\n', re.M)
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())


def helper(entry, indent=''):
    return indent + '{% include diagrams/download.html png="' + entry['png'] + '" %}\n'


def discover(root):
    catalog = json.loads((root/'docs/diagram-catalog.json').read_text())
    records = {r['include']: r for r in catalog['diagrams']}
    entries = []; edits = {}; seen = defaultdict(list)
    for post in sorted((root/'_posts').rglob('*.md')):
        raw = post.read_text(); clean = HELPER.sub('', raw)
        replacements = []; counts = Counter()
        for match in INCLUDE.finditer(clean):
            name, args = match.groups()
            if name == 'diagrams/download.html':
                raise ValueError('unrecognized existing helper: ' + str(post))
            if name not in records:
                if name.startswith('diagrams/static/'):
                    raise ValueError('uncatalogued include: ' + name)
                continue
            start = clean.rfind('\n', 0, match.start()) + 1
            end = clean.find('\n', match.end())
            indent = clean[start:match.start()]
            if end == -1 or indent.strip() or clean[match.end():end].strip():
                raise ValueError('ambiguous non-standalone insertion: ' + str(post))
            # Refuse code fences, Liquid raw/comment blocks, or an enclosing figure.
            prefix = clean[:start]
            fences = re.findall(r'^\s*(```+|~~~+)', prefix, re.M)
            if len(fences) % 2 or prefix.count('{% raw %}') != prefix.count('{% endraw %}') or prefix.count('{% comment %}') != prefix.count('{% endcomment %}') or prefix.count('<figure') != prefix.count('</figure>'):
                raise ValueError('ambiguous nested insertion: ' + str(post))
            arg = re.fullmatch(r'\s*(?:instance="([a-zA-Z0-9_-]+)")?\s*', args)
            if not arg: raise ValueError('unsupported include arguments: ' + match.group())
            instance = arg.group(1) or ''
            ids = Figures((root/'_includes'/name).read_text(), source=True).ids
            if len(ids) != 1: raise ValueError('expected exactly one figure: ' + name)
            figure = ids[0].replace('{{include.instance}}', instance)
            rel = post.relative_to(root).as_posix(); counts[name] += 1
            identity = {'post': rel, 'include': name, 'instance': instance, 'occurrence': counts[name]}
            suffix = fingerprint(identity)[:16]
            png = '/assets/img/diagrams/' + name.removeprefix('diagrams/').removesuffix('.html') + '--' + suffix + '.png'
            entry = dict(identity, figure=figure, png=png, status='pending-export')
            if indent:
                entry.update(status='blocked-insertion', reason='Indented canonical include requires markup review; sibling adjacency is not proven. No helper inserted.')
            entries.append(entry); seen[name].append(rel)
            if not indent: replacements.append((end + 1, helper(entry)))
        if counts:
            result = clean
            for offset, text in reversed(replacements): result = result[:offset] + text + result[offset:]
            if HELPER.sub('', result) != clean: raise ValueError('prose preservation failed')
            edits[post] = result
    for name, record in records.items():
        if sorted(set(seen[name])) != sorted(record['posts']) or len(seen[name]) != record['reference_count']:
            raise ValueError('catalog/live occurrence mismatch: ' + name)
    summary = catalog['summary']
    if len(entries) != summary['post_references'] or len(edits) != summary['posts']:
        raise ValueError('catalog summary mismatch')
    if len({e['png'] for e in entries}) != len(entries): raise ValueError('output collision')
    plan = {'schema': 1, 'font_profile': 'deterministic-export', 'theme': 'light',
            'status': 'pending-export', 'reference_count': len(entries), 'post_count': len(edits),
            'linked_count': sum(e['status'] == 'pending-export' for e in entries),
            'blocked_count': sum(e['status'] == 'blocked-insertion' for e in entries),
            'unused_includes': sorted(n for n in records if not seen[n]), 'entries': entries}
    return plan, edits


def validate_source(root):
    plan, edits = discover(root)
    if json.loads((root/MANIFEST).read_text()) != plan: raise ValueError('mapping differs from live source')
    for path, expected in edits.items():
        if path.read_text() != expected: raise ValueError('missing or misplaced sibling: ' + str(path))
    return plan


class Siblings(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.stack = []; self.last = None; self.figure = None
        self.active = None; self.rows = []; self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'figure' and 'sd' in (a.get('class') or '').split():
            self.figure = (a.get('id') or a.get('aria-labelledby'), tuple(self.stack))
        if tag == 'p' and 'diagram-download' in (a.get('class') or '').split():
            if 'figure' in self.stack or self.last is None or self.last[1] != tuple(self.stack):
                raise ValueError(f'download is not an immediate figure sibling: stack={self.stack}, preceding={self.last}')
            self.active = {'figure': self.last[0], 'links': []}
        if tag == 'a' and self.active is not None:
            self.active['links'].append((a.get('href'), 'download' in a))
        if tag not in VOID: self.stack.append(tag)
        self.last = None

    def handle_endtag(self, tag):
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack)-1-self.stack[::-1].index(tag)]
        if tag == 'figure' and self.figure:
            self.last = self.figure; self.figure = None
        elif tag == 'p' and self.active is not None:
            self.rows.append(self.active); self.active = None; self.last = None

    def handle_data(self, data):
        if data.strip(): self.last = None


def post_pages(site, plan):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('duplicate post in diagram-posts sidecar: ' + key)
            result[key] = value
        return result

    try:
        urls = json.loads((site/'assets/data/diagram-posts.json').read_text(), object_pairs_hook=unique_object)
    except OSError as exc:
        raise ValueError('missing/unreadable diagram-posts sidecar; run build again') from exc
    if not isinstance(urls, dict) or set(urls) != {e['post'] for e in plan['entries']}:
        raise ValueError('diagram-posts sidecar coverage mismatch')
    pages = {}
    for post, url in urls.items():
        if not isinstance(url, str) or not url.startswith('/') or url.startswith('//'):
            raise ValueError('invalid post URL in diagram-posts sidecar')
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError('invalid post URL in diagram-posts sidecar')
        path = unquote(parsed.path, errors='strict')
        rel = path[1:] + ('index.html' if path.endswith('/') else '')
        if any(part in ('', '.', '..') for part in rel.split('/')) or '\\' in rel or '\x00' in rel:
            raise ValueError('unsafe post URL in diagram-posts sidecar')
        if not (site/rel).resolve().is_relative_to(site.resolve()) or not (site/rel).is_file():
            raise ValueError('post URL has no built page: ' + url)
        if rel in pages.values(): raise ValueError('duplicate page in diagram-posts sidecar: ' + rel)
        pages[post] = rel
    return pages


def built_plan(root, site, plan):
    pages = post_pages(site, plan)
    inv = inventory(root, site, root/'docs/diagram-catalog.json')
    blocked = {e['png']: e for e in plan['entries'] if e['status'] == 'blocked-insertion'}
    by_png = {e['png']: e for e in plan['entries'] if e['status'] != 'blocked-insertion'}; rows = []; seen = set()
    known = {(e['page'], e['figure'], e['include']) for e in inv['entries']}
    for page in sorted(site.rglob('*.html')):
        for row in Siblings(page.read_text()).rows:
            links = row['links']
            if len(links) != 2 or links[0][0] != links[1][0] or not links[0][1]:
                raise ValueError('invalid native download links: ' + str(page))
            png = links[0][0]
            if png not in by_png or png in seen: raise ValueError('unknown/duplicate PNG URL: ' + str(png))
            entry = by_png[png]; rel = page.relative_to(site).as_posix()
            if pages[entry['post']] != rel: raise ValueError('post/page ownership mismatch: ' + png)
            if row['figure'] != entry['figure'] or (rel, row['figure'], entry['include']) not in known:
                raise ValueError('figure/include mismatch: ' + png)
            seen.add(png); rows.append(dict(entry, page=rel))
    if seen != set(by_png):
        raise ValueError('built occurrence/download coverage mismatch')
    for entry in blocked.values():
        matches = [e for e in inv['entries'] if e['figure'] == entry['figure'] and e['include'] == entry['include'] and e['page'] == pages[entry['post']]]
        if len(matches) != 1: raise ValueError('blocked occurrence cannot be uniquely located')
        rows.append(dict(entry, page=matches[0]['page']))
    if len(rows) != len(inv['entries']): raise ValueError('built figure total mismatch')
    return sorted(rows, key=lambda e: e['png'])


def source_snapshot(root):
    outputs = {e['png'].lstrip('/') for e in json.loads((root/MANIFEST).read_text())['entries']}
    paths = set()
    for folder in ['_posts', '_includes', '_layouts', '_sass', '_plugins', '_data', 'assets/css', 'assets/js', 'assets/fonts', 'assets/img']:
        paths.update(p for p in (root/folder).rglob('*') if p.is_file() and p.relative_to(root).as_posix() not in outputs)
    for name in ['_config.yml', 'Gemfile', 'Gemfile.lock', MANIFEST, 'docs/diagram-catalog.json']:
        if (root/name).is_file(): paths.add(root/name)
    return {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in sorted(paths)}


def built_assets_snapshot(site, plan):
    # Conservatively bind every non-HTML build file, including the URL sidecar.
    outputs = {e['png'].lstrip('/') for e in plan['entries']}
    return {p.relative_to(site).as_posix(): digest(p.read_bytes())
            for p in sorted(site.rglob('*')) if p.is_file()
            and p.suffix != '.html' and p.name != '.diagram-download-build.json'
            and p.relative_to(site).as_posix() not in outputs}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['wire', 'source-check', 'build', 'plan', 'export', 'check'])
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--site', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--jobs', type=int, choices=range(1, 5), default=2,
                   help='maximum concurrent export/check subprocesses (default: 2)')
    a = p.parse_args(argv); root = a.root.resolve()
    if a.action == 'wire':
        plan, edits = discover(root)  # Validate all entries before writing any post.
        for path, text in edits.items():
            if path.read_text() != text: path.write_text(text)
        (root/MANIFEST).write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
        validate_source(root)
        print(json.dumps({'references': plan['reference_count'], 'posts': plan['post_count'], 'linked': plan['linked_count'], 'blocked': plan['blocked_count'], 'status': 'pending-export'})); return 0
    plan = validate_source(root)
    if a.action == 'source-check':
        print(json.dumps({'references': plan['reference_count'], 'posts': plan['post_count'], 'unused': len(plan['unused_includes']), 'linked': plan['linked_count'], 'blocked': plan['blocked_count'], 'source_consistent': True})); return 0
    if not a.site: p.error('--site is required')
    site = a.site.resolve(); stamp = site/'.diagram-download-build.json'
    if site == root or root.is_relative_to(site) or site.is_relative_to(root):
        raise ValueError('use a dedicated build directory outside the repository')
    if a.action == 'build':
        import os
        before = source_snapshot(root)
        subprocess.run(['bundle', 'exec', 'jekyll', 'build', '--destination', str(site)], cwd=root,
                       env=dict(os.environ, JEKYLL_ENV='production'), check=True)
        if source_snapshot(root) != before: raise ValueError('source changed during build; rebuild after edits settle')
        rows = built_plan(root, site, plan)
        stamp.write_text(json.dumps({'source': before, 'assets': built_assets_snapshot(site, plan), 'html': {str(p.relative_to(site)): digest(p.read_bytes()) for p in sorted(site.rglob('*.html'))}}, indent=2))
        print(json.dumps({'built_references': len(rows), 'stamp': str(stamp)})); return 0
    saved_stamp = json.loads(stamp.read_text())
    if saved_stamp['source'] != source_snapshot(root): raise ValueError('source changed; run build again')
    if saved_stamp['html'] != {str(p.relative_to(site)): digest(p.read_bytes()) for p in sorted(site.rglob('*.html'))}:
        raise ValueError('built HTML changed; run build again')
    if saved_stamp.get('assets') != built_assets_snapshot(site, plan):
        raise ValueError('built assets changed or stamp lacks assets; run build again')
    rows = built_plan(root, site, plan)
    if a.action == 'plan': print(json.dumps(rows, indent=2)); return 0
    if not a.out: p.error('--out is required')
    out = a.out.resolve(); runtime = out/'downloads-export.json'
    identity = fingerprint({'mapping': plan, 'build': saved_stamp})
    previous = json.loads(runtime.read_text()) if a.action == 'check' else None
    if previous and previous.get('identity') != identity:
        raise ValueError('export manifest stale')
    targets = [fingerprint(e)[:24] for e in rows if e['status'] != 'blocked-insertion']
    if len(set(targets)) != len(targets): raise ValueError('output directory collision')

    def process_entry(entry):
        if entry['status'] == 'blocked-insertion':
            return dict(entry, exit_code=None)
        target = out/fingerprint(entry)[:24]
        cmd = [sys.executable, str(Path(__file__).with_name('pipeline.py')), '--site', str(site),
               '--page', entry['page'], '--figure', entry['figure'], '--out', str(target),
               '--theme', 'light', '--font-profile', 'deterministic-export',
               '--font-bundle', str(root/'assets/fonts/static-png/lock.json'),
               '--export-font-bundle', str(root/'assets/fonts/deterministic-export/lock.json')]
        if a.action == 'check': cmd.append('--check')
        try:
            code = subprocess.run(cmd, check=False).returncode
        except OSError as exc:
            return dict(entry, status='failed', exit_code=None, error=str(exc))
        result = dict(entry, status='failed', exit_code=code)
        if code == 0:
            try:
                stem = entry['figure'] + '-625-light'
                png = target/(stem + '.png'); receipt_path = target/(stem + '.json')
                receipt = json.loads(receipt_path.read_text()); raw = png.read_bytes()
                if not raw.startswith(b'\x89PNG\r\n\x1a\n') or receipt['png_sha256'] != digest(raw) or receipt['quality_status'] != 'passed':
                    raise ValueError('invalid PNG/receipt')
                public = root/entry['png'].lstrip('/'); deployed = site/entry['png'].lstrip('/')
                if a.action == 'export':
                    public.parent.mkdir(parents=True, exist_ok=True); deployed.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(png, public); shutil.copyfile(png, deployed)
                if public.read_bytes() != raw or deployed.read_bytes() != raw: raise ValueError('published bytes differ')
                result.update(status='passed', png_sha256=digest(raw), receipt_sha256=digest(receipt_path.read_bytes()))
            except (OSError, ValueError, KeyError) as exc: result['error'] = str(exc)
        return result

    # map yields input order even when subprocesses finish out of order. Each
    # worker owns its hashed entry directory and its unique public PNG URL.
    with ThreadPoolExecutor(max_workers=a.jobs) as executor:
        results = list(executor.map(process_entry, rows))
    report = {'identity': identity, 'status': 'passed' if results and all(e['status'] == 'passed' for e in results) else 'failed', 'entries': results}
    # A long run must not certify inputs that changed after the initial guard.
    # Preserve partial diagnostics, but never accept them as a fresh export.
    try:
        if saved_stamp['source'] != source_snapshot(root):
            raise ValueError('source changed during export/check; run build again')
        if saved_stamp['html'] != {str(p.relative_to(site)): digest(p.read_bytes()) for p in sorted(site.rglob('*.html'))}:
            raise ValueError('built HTML changed during export/check; run build again')
        if saved_stamp.get('assets') != built_assets_snapshot(site, plan):
            raise ValueError('built assets changed during export/check; run build again')
    except (OSError, ValueError) as exc:
        report.update(status='failed', error=str(exc))
        if a.action == 'check': raise ValueError(str(exc)) from exc
    if a.action == 'export':
        out.mkdir(parents=True, exist_ok=True); runtime.write_text(json.dumps(report, indent=2) + '\n')
    elif report != previous: raise ValueError('receipt/output manifest mismatch')
    print(json.dumps({'references': len(results), 'status': report['status'], 'manifest': str(runtime)}))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
