from pathlib import Path
import json
import subprocess

import pytest
import downloads


ROOT = Path(__file__).resolve().parents[3]
PNG = '/assets/img/diagrams/example--0123456789abcdef.png'
WEBP = PNG.removesuffix('.png') + '.webp'


def test_webp_and_png_provenance_share_the_existing_viewer_route():
    assert downloads.viewer_url(WEBP) == downloads.viewer_url(PNG)
    for path in ['/assets/img/diagrams/../escape.webp', '//outside/x.webp', '/assets/img/diagrams/x.webp?x=1']:
        with pytest.raises(ValueError):
            downloads.viewer_url(path)


def test_helper_delivers_webp_without_rewriting_the_legacy_parameter():
    source = (ROOT / '_includes/diagrams/download.html').read_text()
    assert 'include.png' in source
    assert "'.webp'" in source
    assert 'WebP 다운로드' in source
    assert '고정 크기 다이어그램. 좁은 화면에서는 가로로 스크롤' not in source
    assert 'width="1920" height="1080"' in source


def test_real_ruby_viewer_generator_uses_the_same_webp(tmp_path):
    # Real plugin execution, with the small Jekyll host interface isolated.
    path = tmp_path / '_includes/diagrams/example.html'
    path.parent.mkdir(parents=True)
    path.write_text('<figure><figcaption>Test diagram</figcaption></figure>')
    program = r'''
module Jekyll
  class Generator
    def self.safe(*); end
    def self.priority(*); end
  end
  class PageWithoutAFile
    attr_accessor :content, :data
    def initialize(*); @data = {}; end
  end
end
require ARGV[0]
site = Struct.new(:source, :config, :pages).new(ARGV[1], {}, [])
entry = {'png'=>ARGV[2], 'include'=>'diagrams/example.html', 'post'=>'_posts/example.md', 'figure'=>'example'}
Jekyll::DiagramPostMap.new.generate_viewer(site, entry, {'_posts/example.md'=>'/posts/example/'})
puts site.pages.first.content
'''
    result = subprocess.run(['ruby', '-e', program, str(ROOT / '_plugins/diagram-downloads.rb'), str(tmp_path), PNG], check=True, capture_output=True, text=True)
    assert f'src="{WEBP}"' in result.stdout
    assert f'href="{WEBP}" download' in result.stdout
    assert PNG not in result.stdout


def site_fixture(tmp_path, monkeypatch):
    root = tmp_path / 'root'; site = tmp_path / 'site'
    root.mkdir(); site.mkdir()
    entry = {'post': '_posts/example.md', 'include': 'diagrams/example.html', 'figure': 'example', 'png': PNG, 'status': 'pending-export'}
    plan = {'entries': [entry]}
    data = site / 'assets/data/diagram-posts.json'; data.parent.mkdir(parents=True)
    data.write_text(json.dumps({'_posts/example.md': '/posts/example/'}))
    page = site / 'posts/example/index.html'; page.parent.mkdir(parents=True)
    page.write_text(f'<figure class="sd" id="example"></figure><p class="diagram-download"><img class="diagram-inline" src="{WEBP}" alt="" data-static-diagram="true" width="1920" height="1080"><a href="{WEBP}" download>WebP</a><a href="/diagrams/view/example--0123456789abcdef.html">Open</a></p>')
    viewer = site / 'diagrams/view/example--0123456789abcdef.html'; viewer.parent.mkdir(parents=True)
    viewer.write_text(f'<img class="diagram-canvas" src="{WEBP}" width="1920" height="1080"><a href="{WEBP}" download>WebP</a>')
    monkeypatch.setattr(downloads, 'inventory', lambda *args: {'entries': [{'page': 'posts/example/index.html', 'figure': 'example', 'include': 'diagrams/example.html'}]})
    return root, site, plan, page, viewer


def test_built_delivery_requires_same_webp_inline_download_and_viewer(tmp_path, monkeypatch):
    root, site, plan, page, viewer = site_fixture(tmp_path, monkeypatch)
    assert downloads.built_plan(root, site, plan)[0]['png'] == PNG
    original = page.read_text()
    page.write_text(original.replace(WEBP, PNG))
    with pytest.raises(ValueError, match='WebP'):
        downloads.built_plan(root, site, plan)
    page.write_text(original)
    viewer.write_text(viewer.read_text().replace(WEBP, PNG))
    with pytest.raises(ValueError, match='viewer'):
        downloads.built_plan(root, site, plan)


def test_built_inline_requires_native_intrinsic_width_and_height(tmp_path, monkeypatch):
    root, site, plan, page, viewer = site_fixture(tmp_path, monkeypatch)
    page.write_text(page.read_text().replace('height="1080"', 'height="540"'))
    with pytest.raises(ValueError, match='dimensions|intrinsic'):
        downloads.built_plan(root, site, plan)
