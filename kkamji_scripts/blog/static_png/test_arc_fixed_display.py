"""The ARC article keeps native FHD artwork but uses normal article sizing."""
import re
from pathlib import Path
from test_responsive_display import style_rules

ROOT = Path(__file__).resolve().parents[3]
FIXED = {
    '.diagram-download.diagram-download--fixed-fhd > img.diagram-inline',
    '#main-wrapper main .content .diagram-download.diagram-download--fixed-fhd > img.diagram-inline',
}


def test_fixed_fhd_image_never_implicitly_scales():
    rules = {s: d for selectors, d in style_rules() for s in selectors}
    for selector in FIXED:
        assert selector in rules, 'the explicit opt-in needs a fixed sizing rule'
        for prop in ('width', 'min-width', 'max-width'):
            assert rules[selector].get(prop) == '1920px'
        for prop in ('height', 'min-height', 'max-height'):
            assert rules[selector].get(prop) == '1080px'
        assert rules[selector].get('object-fit') == 'contain'


def test_arc_article_does_not_enable_the_legacy_fixed_display():
    helper = (ROOT / '_includes/diagrams/download.html').read_text()
    assert 'page.arc_diagram_fixed_fhd' in helper
    assert 'diagram-download--fixed-fhd' in helper
    assert '자동 축소하지 않습니다' in helper
    assert 'tabindex="0"' in helper
    opted = [p.relative_to(ROOT).as_posix() for p in (ROOT/'_posts').rglob('*.md')
             if re.search(r'^arc_diagram_fixed_fhd: true$', p.read_text(), re.M)]
    assert opted == []


def test_fixed_fhd_scroll_is_bounded_inside_article():
    rules = {s: d for selectors, d in style_rules() for s in selectors}
    fixed = rules.get('.diagram-download.diagram-download--fixed-fhd', {})
    assert fixed.get('overflow-x') == 'auto'
    assert fixed.get('max-width') == '100%'
    assert fixed.get('overscroll-behavior-inline') == 'contain'
