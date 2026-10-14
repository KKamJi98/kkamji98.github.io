"""Jev banner nesting must leave real painted-border clearance."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fhd_svg import FONT, Font, Parse, banner_layout, complete_group_boundaries, source_fragment

ROOT = Path(__file__).resolve().parents[3]


def banner():
    path = ROOT / '_includes/diagrams/static/ai/jev-system-one-banner.html'
    raw = source_fragment(path.read_text())
    figure = next(e for e in Parse(raw).root.descendants() if e.tag == 'figure')
    layout = banner_layout(Font(ROOT / FONT), figure)
    complete_group_boundaries(layout)
    return layout


def test_jev_output_group_has_four_sided_inset_from_child_card_strokes():
    layout = banner()
    group = next(g for g in layout.groups if g['source'] == 'root.0.4.4')
    children = [b for b in layout.boxes if b['source'].startswith('root.0.4.4.')]
    assert len(children) == 3
    gaps = [min(b['x'] - group['x'] for b in children),
            min(b['y'] - group['y'] for b in children),
            min(group['x'] + group['width'] - b['x'] - b['width'] for b in children),
            min(group['y'] + group['height'] - b['y'] - b['height'] for b in children)]
    assert min(round(g, 3) for g in gaps) >= 32, f'Grouped card borders touch: {gaps}'


def test_jev_banner_does_not_render_site_watermark():
    layout = banner()
    assert all('kkamji.net' not in t['text'] for t in layout.texts)


def test_jev_flow_uses_vertical_canvas_with_larger_card_text():
    layout = banner()
    nodes = {b['source'] for b in layout.boxes}
    card_labels = [t for t in layout.texts if t['label'] and t['source'] in nodes]
    card_details = [t for t in layout.texts if not t['label'] and t['source'] in nodes]
    assert min(t['size'] for t in card_labels) >= 38
    assert min(t['size'] for t in card_details) >= 30
    group = next(g for g in layout.groups if g['source'] == 'root.0.4.4')
    assert group['height'] >= 600
