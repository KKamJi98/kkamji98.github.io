"""Fixed ARC coordinates preserve explicit management and execution relations."""
import sys
from typing import Any
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fhd_svg
ROOT = Path(__file__).resolve().parents[3]


def test_arc_layout_has_horizontal_nodes_and_unlabelled_explicit_edges():
    arc_layout = getattr(fhd_svg, 'arc_layout', None)
    assert callable(arc_layout), 'ARC needs a fixed authored relationship layout'
    raw = (ROOT/'_includes/diagrams/static/ci-cd/arc-overview.html').read_text()
    original = fhd_svg.source_fragment(raw)
    figure = next(e for e in fhd_svg.Parse(original).root.descendants() if e.tag == 'figure')
    layout: Any = arc_layout(fhd_svg.Font(ROOT/fhd_svg.FONT), figure)
    assert len(layout.boxes) == 4
    assert len(layout.connectors) == 5
    assert len({b['y'] + b['height']/2 for b in layout.boxes}) == 1
    assert [b['x'] for b in layout.boxes] == sorted(b['x'] for b in layout.boxes)
    assert layout.groups[0]['height'] == layout.groups[1]['height']
    assert layout.profile['no_connector_labels'] is True
    assert not [t for t in layout.texts if t['source'].endswith('.meaning')]
    assert not fhd_svg.check_layout(layout)
    assert not fhd_svg.semantic_check(layout, figure)
    assert not fhd_svg.visible_text_coverage(layout, original)


def test_arc_author_report_records_the_fixed_display_exception(tmp_path):
    import json
    name = 'diagrams/static/ci-cd/arc-overview.html'
    for relative in [fhd_svg.FONT, '_includes/' + name]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(ROOT / relative)
    catalog = tmp_path / 'docs/diagram-catalog.json'
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({'diagrams': [{'include': name}]}))
    budgets = tmp_path / 'kkamji_scripts/blog/static_png/fhd-font-budgets.json'
    budgets.parent.mkdir(parents=True)
    budgets.write_text(json.dumps({'sources': {}}))
    report = tmp_path / 'arc-report.json'
    assert fhd_svg.author(tmp_path, check=True, report=report) == 0
    payload = json.loads(report.read_text())
    assert payload['display'] == 'fixed-fhd-scroll'
    assert payload['display_overrides'] == {name: 'fixed-fhd-scroll'}
    assert payload['entries'][0]['display'] == 'fixed-fhd-scroll'
    assert payload['entries'][0]['rendered_visual_review'] == 'not-run'
