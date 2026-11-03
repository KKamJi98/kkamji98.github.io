"""Keep a post cover separate from explanatory body diagrams."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[3]
POST = ROOT / '_posts/2026/09/2026-09-22-jev-system-one-decision-model.md'


def test_jev_cover_is_frontmatter_not_duplicate_body_diagram():
    text = POST.read_text(encoding='utf-8')
    metadata = yaml.safe_load(text.split('---', 2)[1])
    assert metadata.get('image', {}).get('path') == (
        '/assets/img/ai/jev/jev-system-one-banner-neon-fhd.webp'
    ), 'Jev must keep the explicitly selected neon cover separate from body diagrams'
    assert '{% include diagrams/static/ai/jev-system-one-banner.html %}' not in text
    assert '{% include diagrams/static/ai/jev-decision-pipeline.html %}' in text
    assert '{% include diagrams/static/ai/jev-primitives.html %}' in text


def test_jev_cover_metadata_declares_native_fhd_ratio():
    metadata = yaml.safe_load(POST.read_text(encoding='utf-8').split('---', 2)[1])
    assert metadata['image'].get('width') == 1920
    assert metadata['image'].get('height') == 1080


def test_only_explicit_fhd_cover_context_gets_native_image_dimensions():
    template = (ROOT / '_includes/refactor-content.html').read_text()
    assert '_cover_context' in template and 'diagram-cover' in template
    assert "_cover_prefix == '/assets/img/diagrams/'" in template
    assert "_cover_suffix == '.webp'" in template
    assert template.index("data-static-diagram=") < template.index('_cover_context')
    css = (ROOT / 'assets/css/jekyll-theme-chirpy.scss').read_text()
    assert '#main-wrapper .preview-img.diagram-cover' in css


def test_normal_hook_runs_display_cover_and_review_boundary_regressions():
    hook = (ROOT / '.githooks/pre-commit').read_text()
    for name in ('test_responsive_display.py', 'test_cover_contract.py', 'test_webp_review_regressions.py'):
        assert name in hook


def test_lora_cover_is_an_exact_opt_in_not_a_body_diagram():
    post = ROOT / '_posts/2026/11/2026-11-03-lora-overview.md'
    text = post.read_text(encoding='utf-8')
    image = yaml.safe_load(text.split('---', 2)[1])['image']
    cover = '/assets/img/ai/lora/lora-overview-cover.webp'
    assert image['path'] == cover
    assert (image['width'], image['height']) == (1920, 1080)
    assert 'include diagrams/static/ai/lora/lora-update-path.html' in text
    assert 'include diagrams/static/ai/lora/lora-overview-cover.html' not in text
    template = (ROOT / '_includes/refactor-content.html').read_text()
    assert "{% elsif _src == '" + cover + "' %}" in template
    assert "_cover_prefix == '/assets/img/ai/'" not in template
