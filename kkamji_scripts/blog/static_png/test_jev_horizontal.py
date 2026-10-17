"""Horizontal balance includes boundaries and branches, not only node centres."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fhd_svg import FONT, Font, Parse, jev_layout, source_fragment

ROOT = Path(__file__).resolve().parents[3]


def layout():
    text = source_fragment((ROOT / '_includes/diagrams/static/ai/jev-decision-pipeline.html').read_text())
    figure = next(e for e in Parse(text).root.descendants() if e.tag == 'figure')
    return jev_layout(Font(ROOT / FONT), figure)


def test_linear_jev_boundaries_share_top_bottom_and_branch_to_right():
    drawing = layout()
    groups = {g['source']: g for g in drawing.groups}
    left, right = groups['root.0.0.0'], groups['root.0.0.2']
    assert abs(left['y'] - right['y']) <= 1, 'A one-sided tall group creates an L-shaped composition'
    assert abs(left['height'] - right['height']) <= 1
    boxes = {b['source']: b for b in drawing.boxes}
    main = [boxes[k] for k in ('root.0.0.0.0', 'root.0.0.0.2', 'root.0.0.2.1')]
    centres = [b['y'] + b['height'] / 2 for b in main]
    assert max(centres) - min(centres) <= 1
    policy = main[-1]
    outcomes = [boxes['root.0.0.2.3.' + str(i)] for i in range(2)]
    assert min(b['x'] for b in outcomes) >= policy['x'] + policy['width'] + 64, 'Outcomes belong in the rightmost column, not underneath policy'
    branch_centre = sum(b['y'] + b['height'] / 2 for b in outcomes) / 2
    assert abs(branch_centre - centres[-1]) <= 1


def test_transfer_caption_stays_between_authority_boundaries():
    drawing = layout()
    groups = {g['source']: g for g in drawing.groups}
    left, right = groups['root.0.0.0'], groups['root.0.0.2']
    captions = [t for t in drawing.texts if t['source'] == 'root.0.0.1']
    assert captions
    for caption in captions:
        assert caption['x'] >= left['x'] + left['width'] + 8
        assert caption['x'] + caption['width'] <= right['x'] - 8


def test_primary_card_titles_share_one_baseline_and_inset():
    drawing = layout()
    boxes = {b['source']: b for b in drawing.boxes}
    keys = ('root.0.0.0.0', 'root.0.0.0.2', 'root.0.0.2.1')
    titles = [next(t for t in drawing.texts if t['source'] == k and t['label']) for k in keys]
    assert len({t['y'] for t in titles}) == 1
    assert {t['x'] - boxes[k]['x'] for t, k in zip(titles, keys)} == {28}
    assert len({(boxes[k]['y'], boxes[k]['height']) for k in keys}) == 1


def test_jev_keeps_the_cover_neon_palette_without_recolouring_connectors():
    from fhd_svg import svg_document
    drawing = layout()
    svg = svg_document(drawing, None, 'x' * 64)
    assert '#6e77ff' in svg and '#2ed6b8' in svg, 'Jev neon must match the cover gradient'
    judge = next(b for b in drawing.boxes if b['source'] == 'root.0.0.0.2')
    assert judge['border'] == 'url(#jev-neon)'
    signals = [g for g in drawing.groups if g.get('owner') == 'root.0.0.0.2']
    assert len(signals) == 3 and len({g['border'] for g in signals}) == 3
    assert 'stroke="#475569"' in svg and 'url(#jev-neon)" stroke-width="3"' in svg


def test_measured_outcomes_match_the_post_policy_table():
    import re
    post = (ROOT / '_posts/2026/09/2026-09-22-jev-system-one-decision-model.md').read_text()
    table = dict(re.findall(r'^\| `([^`]+)` \|.*\| `(escalate|shadow)` \|$', post, re.M))
    assert len(table) == 3
    painted = [t['text'] for t in layout().texts if t['source'] == 'root.0.1']
    for command, outcome in table.items():
        index = painted.index(command)
        assert painted[index + 1] == outcome.capitalize()


def test_every_painted_label_stays_readable_after_article_scaling():
    assert min(t['size'] for t in layout().texts) >= 22
