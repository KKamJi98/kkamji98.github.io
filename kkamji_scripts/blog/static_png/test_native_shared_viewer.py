"""Real Ruby viewers retain each exact occurrence and backlink."""
import copy
import json
import subprocess
from pathlib import Path

import pytest
from test_native_shared_updates import shared_fixture

ROOT = Path(__file__).resolve().parents[3]
RUBY = r'''
require 'json'
module Jekyll
  class Generator
    def self.safe(*) = nil
    def self.priority(*) = nil
  end
  class PageWithoutAFile
    attr_accessor :data, :content
    def initialize(*)
      @data = {}
    end
  end
end
require ARGV[0]
input = JSON.parse(STDIN.read)
site = Struct.new(:source, :config, :pages).new(ARGV[1], {'baseurl' => ''}, [])
input.fetch('entries').each { |entry| Jekyll::DiagramPostMap.new.generate_viewer(site, entry, input.fetch('posts')) }
puts JSON.generate(site.pages.map(&:content))
'''


def invoke(root, entries, posts):
    return subprocess.run(['ruby','-e',RUBY,str(ROOT / '_plugins/diagram-downloads.rb'),str(root)],
        input=json.dumps(dict(entries=entries, posts=posts)), text=True, capture_output=True)


def render_viewers(root, entries, posts):
    result = invoke(root, entries, posts)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def mapped(s):
    entries = [dict(include=s.row['include'], post=o['post'], figure=o['figure'], png=o['new_png'], old_png=o['old_png']) for o in s.row['occurrences']]
    posts = {o['post']: '/posts/' + o['post'].split('/')[-1][:-3] + '/' for o in s.row['occurrences']}
    return entries, posts


def test_shared_viewer_accepts_all_exact_occurrences(tmp_path, monkeypatch):
    s = shared_fixture(tmp_path, monkeypatch, 'cross-post'); entries, posts = mapped(s)
    pages = render_viewers(s.root, entries, posts)
    assert len(pages) == len(entries)
    for row, page in zip(entries, pages):
        assert row['png'][:-4] + '.webp' in page
        assert posts[row['post']] + '#' + row['figure'] in page


@pytest.mark.parametrize('field', ['post','figure','include','old_png','png'])
def test_shared_viewer_rejects_swapped_or_undeclared_ownership(tmp_path, monkeypatch, field):
    s = shared_fixture(tmp_path, monkeypatch); entries, posts = mapped(s)
    row = copy.deepcopy(entries[0])
    row[field] = entries[1][field] if field in ('figure','old_png','png') else ('_posts/other.md' if field == 'post' else 'diagrams/unused.html')
    posts['_posts/other.md'] = '/posts/other/'
    result = invoke(s.root, [row], posts)
    assert result.returncode != 0
    assert 'Invalid diagram viewer PNG path' in result.stderr


@pytest.mark.parametrize('damage', ['missing','duplicate-new','swapped-ownership','master-pair','undeclared-hashed'])
def test_shared_viewer_rejects_invalid_fanout_declaration(tmp_path, monkeypatch, damage):
    s = shared_fixture(tmp_path,monkeypatch); entries,posts = mapped(s)
    if damage == 'missing': s.row['occurrences'].pop()
    elif damage == 'duplicate-new': s.row['occurrences'][1]['new_png'] = s.row['occurrences'][0]['new_png']
    elif damage == 'swapped-ownership':
        s.row['occurrences'][0]['figure'] = entries[1]['figure']; entries[0]['figure'] = entries[1]['figure']
    elif damage == 'master-pair': s.row['new_png'] = s.row['occurrences'][1]['new_png']
    else: entries[0]['png'] = '/assets/img/diagrams/native-updates/20261014/undeclared--0000000000000000.png'
    s.save(); result = invoke(s.root,[entries[0]],posts)
    assert result.returncode != 0
    assert 'Invalid diagram viewer PNG path' in result.stderr
