"""Fixed authored layouts keep every source atom painted inside the canvas."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fhd_svg
ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('name', sorted(fhd_svg.AUTHORED_LAYOUTS))
def test_authored_layout_passes_geometry_and_semantic_checks(name):
    original = fhd_svg.source_fragment((ROOT / '_includes' / name).read_text())
    figure = next(e for e in fhd_svg.Parse(original).root.descendants() if e.tag == 'figure')
    layout = fhd_svg.AUTHORED_LAYOUTS[name](fhd_svg.Font(ROOT / fhd_svg.FONT), figure)
    edges = [e for e in figure.descendants() if 'sd-arrow' in e.classes]
    assert len(layout.connectors) == len(edges)
    assert len([t for t in layout.texts if t['size'] == 36]) == 1, 'title must stay on one line'
    for box in layout.boxes:
        texts = [t for t in layout.texts if t['source'] == box['source']]
        assert max(t['y'] + t['size'] * 0.25 for t in texts) <= box['y'] + box['height'] - 16
        assert max(t['x'] + t['width'] for t in texts) <= box['x'] + box['width'] - 16
    assert not fhd_svg.check_layout(layout)
    assert not fhd_svg.semantic_check(layout, figure)
    assert not fhd_svg.visible_text_coverage(layout, original)
