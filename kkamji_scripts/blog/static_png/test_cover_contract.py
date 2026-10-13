"""Keep a post cover separate from explanatory body diagrams."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[3]
POST = ROOT / '_posts/2026/09/2026-09-22-jev-system-one-decision-model.md'


def test_jev_cover_is_frontmatter_not_duplicate_body_diagram():
    text = POST.read_text(encoding='utf-8')
    metadata = yaml.safe_load(text.split('---', 2)[1])
    assert metadata.get('image', {}).get('path') == (
        '/assets/img/diagrams/static/ai/jev-system-one-banner--e97d9e6d4ae55b70.webp'
    ), 'Jev must have its verified FHD WebP cover metadata'
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
