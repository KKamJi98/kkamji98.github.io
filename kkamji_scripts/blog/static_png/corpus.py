#!/usr/bin/env python3
"""Plan or explicitly export/check every built canonical figure occurrence."""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from pipeline import digest, fingerprint


class Figures(HTMLParser):
    def __init__(self, text, source=False):
        super().__init__()
        self.source = source
        self.ids = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'figure' and 'sd' in (attrs.get('class') or '').split():
            value = attrs.get('id') or attrs.get('aria-labelledby', '')
            literal = value.replace('{{include.instance}}', '') if self.source else value
            if not literal or not re.fullmatch(r'[a-zA-Z0-9_-]+', literal):
                raise ValueError('missing or unsafe canonical figure ID')
            self.ids.append(value)


def inventory(root, site, catalog):
    records = json.loads(catalog.read_text())['diagrams']
    sources = {}; unused = []; expected = set()
    source_hashes = {}
    for record in records:
        path = (root/'_includes'/record['include']).resolve()
        if not path.is_relative_to((root/'_includes').resolve()):
            raise ValueError('include outside root')
        raw = path.read_bytes(); ids = Figures(raw.decode(), source=True).ids
        if not ids:
            raise ValueError('no figure in ' + record['include'])
        source_hashes[record['include']] = digest(raw)
        if not record['posts']:
            unused.append(record['include'])
        for figure in ids:
            if figure in sources:
                raise ValueError('duplicate source figure ID: ' + figure)
            sources[figure] = record['include']
            if record['posts']: expected.add(figure)
    entries = []; seen = set()
    for path in sorted(site.rglob('*.html')):
        ids = Figures(path.read_text()).ids
        if any(n != 1 for n in Counter(ids).values()):
            raise ValueError('duplicate figure ID in ' + str(path))
        for figure in ids:
            matches = [key for key in sources if re.fullmatch(re.escape(key).replace(re.escape('{{include.instance}}'), '[a-zA-Z0-9_-]*'), figure)]
            if len(matches) != 1:
                raise ValueError('uncatalogued or ambiguous built figure: ' + figure)
            source_key = matches[0]
            page = path.relative_to(site).as_posix()
            entries.append({'figure': figure, 'page': page, 'include': sources[source_key],
                            'output': figure + '/' + digest(page.encode())[:16]})
            seen.add(source_key)
    missing = expected - seen
    if missing:
        raise ValueError('used figures absent from build: ' + ', '.join(sorted(missing)))
    return {'schema': 1, 'entries': entries, 'unused': sorted(unused),
            'catalog_sha256': digest(catalog.read_bytes()), 'source_hashes': source_hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'export', 'check'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--site', required=True, type=Path)
    parser.add_argument('--catalog', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--font-profile', choices=['production', 'strict-production', 'local-fallback', 'diagnostic-local', 'deterministic-export'], default='production')
    parser.add_argument('--font-bundle', type=Path)
    parser.add_argument('--theme', choices=['light', 'dark'], default='light')
    args = parser.parse_args()
    plan = inventory(args.root.resolve(), args.site.resolve(), args.catalog or args.root/'docs/diagram-catalog.json')
    plan.update(theme=args.theme, font_profile=args.font_profile)
    identity = fingerprint(plan)
    manifest = args.out / ('manifest-' + args.theme + '.json')
    if args.action == 'plan':
        print(json.dumps(plan, indent=2)); return 0
    saved = {}
    if args.action == 'check':
        saved = json.loads(manifest.read_text())
        if saved.get('fingerprint') != identity or saved.get('plan') != plan:
            raise ValueError('corpus changed or manifest incomplete; regenerate after a fresh build')
    results = []; receipt_hashes = {}
    for entry in plan['entries']:
        out = args.out / entry['output']
        command = [sys.executable, str(Path(__file__).with_name('pipeline.py')),
                   '--site', str(args.site), '--page', entry['page'], '--figure', entry['figure'],
                   '--out', str(out), '--theme', args.theme, '--font-profile', args.font_profile]
        if args.font_bundle: command += ['--font-bundle', str(args.font_bundle)]
        if args.action == 'check': command += ['--check']
        code = subprocess.run(command, check=False).returncode
        results.append(dict(entry, exit_code=code))
        receipt = out / (entry['figure'] + '-625-' + args.theme + '.json')
        if receipt.is_file(): receipt_hashes[entry['output']] = digest(receipt.read_bytes())
    passed = bool(results) and all(r['exit_code'] == 0 for r in results)
    if args.action == 'check':
        passed = passed and saved.get('receipt_hashes') == receipt_hashes and saved.get('status') == 'passed'
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({'fingerprint': identity, 'plan': plan, 'results': results,
                                       'receipt_hashes': receipt_hashes,
                                       'status': 'passed' if passed else 'failed'}, indent=2))
    print(json.dumps({'count':len(results), 'passed':passed, 'manifest':str(manifest)}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
