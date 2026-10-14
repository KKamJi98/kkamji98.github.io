"""The real Ruby viewer accepts only declared body-update occurrences."""
import json
import subprocess
from pathlib import Path

import pytest

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
entry = JSON.parse(STDIN.read)
site = Struct.new(:source, :config, :pages).new(ARGV[1], {'baseurl' => ''}, [])
Jekyll::DiagramPostMap.new.generate_viewer(site, entry, {entry.fetch('post') => '/posts/example/'})
puts site.pages.fetch(0).content
'''


def entry():
    plan = json.loads((ROOT / 'docs/diagram-downloads.json').read_text())
    return next(row for row in plan['entries'] if row.get('old_png'))


def invoke(row):
    return subprocess.run(['ruby', '-e', RUBY, str(ROOT / '_plugins/diagram-downloads.rb'), str(ROOT)], input=json.dumps(row), text=True, capture_output=True)


def test_declared_update_viewer_serves_same_webp():
    row = entry()
    result = invoke(row)
    assert result.returncode == 0, result.stderr
    assert row['png'].removesuffix('.png') + '.webp' in result.stdout
    assert 'width="1920" height="1080"' in result.stdout


@pytest.mark.parametrize('change', ['new-url', 'include', 'old-provenance'])
def test_undeclared_viewer_update_is_rejected(change):
    row = dict(entry())
    if change == 'new-url':
        row['png'] = '/assets/img/diagrams/native-updates/20261014/undeclared.png'
    elif change == 'include':
        row['include'] = 'diagrams/static/ai/jev-primitives.html'
    else:
        row['old_png'] = '/assets/img/diagrams/static/ai/other--0000000000000000.png'
    result = invoke(row)
    assert result.returncode != 0
    assert 'Invalid diagram viewer PNG path' in result.stderr
