"""Offline-only LoRA authoring regressions; no native render or visual approval."""
import copy
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fhd_svg

ROOT = Path(__file__).resolve().parents[3]
INCLUDE = "diagrams/static/ai/lora/lora-update-path.html"


def test_lora_budget_has_a_fixed_opt_in_dispatch():
    include = "diagrams/static/ai/lora/lora-parameter-budget.html"
    assert include in fhd_svg.AUTHORED_LAYOUTS
    assert fhd_svg.AUTHORED_LAYOUTS[include] is fhd_svg.lora_parameter_budget_layout


def test_lora_data_bar_cannot_disappear_from_the_semantic_gate():
    _, _, figure, layout = candidate("diagrams/static/ai/lora/lora-parameter-budget.html")
    layout.groups = layout.groups[:-1]
    assert "missing-source-data-bar" in {i["code"] for i in fhd_svg.semantic_check(layout, figure)}


def test_lora_has_its_own_authored_dispatch():
    assert INCLUDE in fhd_svg.AUTHORED_LAYOUTS, "LoRA needs an opt-in fixed layout"
    assert fhd_svg.AUTHORED_LAYOUTS[INCLUDE] is fhd_svg.lora_update_layout


SVG_PATH = "assets/img/diagrams/fhd-svg/static/ai/lora/lora-update-path.svg"
BUDGET = "diagrams/static/ai/lora/lora-parameter-budget.html"
BUDGET_SVG = "assets/img/diagrams/fhd-svg/static/ai/lora/lora-parameter-budget.svg"
NS = "{http://www.w3.org/2000/svg}"


def candidate(include=INCLUDE):
    path = ROOT / "_includes" / include
    assert path.is_file(), "LoRA needs its own semantic HTML source"
    raw = path.read_text()
    original = fhd_svg.source_fragment(raw)
    figure = next(e for e in fhd_svg.Parse(original).root.descendants() if e.tag == "figure")
    layout = fhd_svg.AUTHORED_LAYOUTS[include](fhd_svg.Font(ROOT / fhd_svg.FONT), figure)
    return raw, original, figure, layout


def test_lora_has_six_nodes_and_the_exact_linear_update_edges():
    _, original, figure, layout = candidate()
    named = {e.attrs["id"]: e for e in [figure, *figure.descendants()] if e.attrs.get("id")}
    assert figure.attrs["id"] == "sd-lora-update-path"
    assert named["sd-lora-update-path-title"].text() == "LoRA in one linear layer"
    assert named["lora-equation"].text() == "h = W0x + sB(Ax), s = alpha/r"
    assert named["lora-base"].text() == "W0 Frozen\n4096 x 4096\nW0x"
    assert named["lora-a"].text() == "A 8 x 4096\nTrainable"
    assert named["lora-b"].text() == "B 4096 x 8\nTrainable\nsB(Ax)"
    assert named["lora-input"].text() == "x 4096"
    assert named["lora-output"].text() == "h 4096"
    assert named["lora-add"].text() == "+ Add"
    assert named["lora-parameters"].text() == "A + B: 65,536 trainable parameters"
    assert named["lora-scope"].text() == "One selected matrix; bias/dropout omitted"
    assert 8 * 4096 + 4096 * 8 == 65536
    assert 4096 * 4096 == 16777216
    assert len(layout.boxes) == 6
    source_edges = [e for e in figure.descendants() if "sd-arrow" in e.classes]
    expected = {
        ("lora-input", "lora-base"), ("lora-input", "lora-a"),
        ("lora-a", "lora-b"), ("lora-base", "lora-add"),
        ("lora-b", "lora-add"), ("lora-add", "lora-output"),
    }
    assert {(e.attrs["data-from"], e.attrs["data-to"]) for e in source_edges} == expected
    assert len(source_edges) == len(layout.connectors) == 6
    assert not fhd_svg.check_layout(layout)
    assert not fhd_svg.semantic_check(layout, figure)
    assert not fhd_svg.visible_text_coverage(layout, original)
    assert layout.profile["no_connector_labels"] is True
    assert original.isascii()


@pytest.mark.parametrize("include, svg_path", [(INCLUDE, SVG_PATH), (BUDGET, BUDGET_SVG)])
def test_lora_fhd_pair_preserves_accessible_source_and_exact_svg(include, svg_path):
    raw, original, figure, layout = candidate(include)
    assert (ROOT / svg_path).is_file()
    svg = (ROOT / svg_path).read_text()
    generated = fhd_svg.svg_document(layout, figure, fhd_svg.sha(original.encode()))
    assert svg == generated + "\n"
    assert raw.count(generated) == 1
    assert raw.count(fhd_svg.SEMANTIC_BEGIN) == 1
    parsed = next(e for e in fhd_svg.Parse(raw).root.descendants() if e.tag == "figure")
    assert parsed.children[0].tag == "figcaption"
    assert parsed.attrs["aria-labelledby"] == parsed.children[0].attrs["id"]
    semantic = next(e for e in parsed.children if "sd-semantic-source" in e.classes)
    for element in [semantic, *semantic.descendants()]:
        assert element.attrs.get("aria-hidden") != "true"
        assert "hidden" not in element.attrs
        assert "style" not in element.attrs
    drawing = ET.fromstring(svg)
    assert drawing.attrib["width"] == "1920"
    assert drawing.attrib["height"] == "1080"
    assert drawing.attrib["viewBox"] == "0 0 1920 1080"
    assert drawing.attrib["aria-hidden"] == "true"
    assert drawing.attrib["data-source-sha256"] == fhd_svg.sha(original.encode())
    assert drawing[0].attrib["fill"] == "#fff"
    assert {e.attrib["data-node"] for e in drawing.iter() if "data-node" in e.attrib} == {
        b["source"] for b in layout.boxes
    }
    painted = {e.attrib["data-edge"]: e for e in drawing.iter() if "data-edge" in e.attrib}
    heads = {e.attrib["data-arrowhead"]: e for e in drawing.iter() if "data-arrowhead" in e.attrib}
    assert set(painted) == set(heads) == {e["source"] for e in layout.connectors}
    semantic_keys = {e.key for e in [figure, *figure.descendants()]}
    assert {e.attrib["data-source"] for e in drawing.iter() if "data-source" in e.attrib} <= semantic_keys
    named_elements = [e for e in figure.descendants() if e.attrs.get("id")]
    assert len({e.attrs["id"] for e in named_elements}) == len(named_elements)
    painted_sources = {value for e in drawing.iter() for key, value in e.attrib.items()
                       if key in {"data-source", "data-node", "data-edge"}}
    assert {e.key for e in named_elements} == painted_sources
    for edge in layout.connectors:
        path, head = painted[edge["source"]], heads[edge["source"]]
        assert path.attrib["data-from"] == " ".join(edge["from"])
        assert path.attrib["data-to"] == " ".join(edge["to"])
        assert path.attrib["stroke"] == head.attrib["fill"] == "#475569"
        assert path.attrib["stroke-width"] == "3"
        points = [[float(v) for v in pair.split(",")] for pair in head.attrib["points"].split()]
        assert points[0] == edge["points"][-1]
        assert len(points) == 3 and points[1] != points[2]
        assert all(32 <= x <= 1888 and 32 <= y <= 1048 for x, y in points)
    for element in drawing.iter():
        assert element.tag.removeprefix(NS) in {"svg", "rect", "path", "title", "polygon", "text"}
        assert all(not key.lower().startswith("on") for key in element.attrib)
        assert not any("href" in key for key in element.attrib)


def test_lora_geometry_keeps_equal_branch_extents_and_shared_centers():
    _, _, figure, layout = candidate()
    named = {e.attrs["id"]: e.key for e in figure.descendants() if e.attrs.get("id")}
    boxes = {key: next(b for b in layout.boxes if b["source"] == source)
             for key, source in named.items() if any(b["source"] == source for b in layout.boxes)}
    expected = {
        "lora-input": (64, 465, 184, 240), "lora-base": (472, 258, 656, 264),
        "lora-a": (400, 648, 328, 264), "lora-b": (872, 648, 328, 264),
        "lora-add": (1368, 465, 184, 240), "lora-output": (1672, 465, 184, 240),
    }
    assert {k: tuple(b[n] for n in ("x", "y", "width", "height")) for k, b in boxes.items()} == expected
    center = lambda b: b["y"] + b["height"] / 2
    assert {center(boxes[k]) for k in ("lora-input", "lora-add", "lora-output")} == {585}
    assert center(boxes["lora-base"]) == 390
    assert center(boxes["lora-a"]) == center(boxes["lora-b"]) == 780
    assert 585 - 390 == 780 - 585
    left_inset = boxes["lora-base"]["x"] - boxes["lora-a"]["x"]
    right_inset = boxes["lora-b"]["x"] + boxes["lora-b"]["width"] - boxes["lora-base"]["x"] - boxes["lora-base"]["width"]
    assert left_inset == right_inset == 72
    assert boxes["lora-a"]["height"] == boxes["lora-b"]["height"]
    baseline = lambda k: next(t["y"] for t in layout.texts if t["source"] == named[k] and t["label"])
    assert baseline("lora-a") == baseline("lora-b")
    assert baseline("lora-input") == baseline("lora-add") == baseline("lora-output")
    edges = {e["source"]: e for e in layout.connectors}
    assert edges[named["lora-input-base"]]["points"][:2] == edges[named["lora-input-a"]]["points"][:2]
    assert edges[named["lora-base-add"]]["points"][-1][1] + edges[named["lora-b-add"]]["points"][-1][1] == 2 * 585
    assert all(a[0] == b[0] or a[1] == b[1] for edge in layout.connectors
               for a, b in zip(edge["points"], edge["points"][1:]))


def font_at(size, bold=False):
    font = ImageFont.truetype(str(ROOT / fhd_svg.FONT), size=int(size))
    font.set_variation_by_axes([700 if bold else 400])
    return font


@pytest.mark.parametrize("include", [INCLUDE, BUDGET])
def test_lora_large_labels_and_pinned_glyph_bounds_fit_without_wrapping(include):
    _, _, figure, layout = candidate(include)
    title = next(t for t in layout.texts if t["source"] == figure.children[0].key)
    assert title["size"] == 72
    assert (layout.label_size, layout.detail_size) == ((88, 40) if include == INCLUDE else (72, 44))
    boxes = {b["source"]: b for b in layout.boxes}
    for text in layout.texts:
        font = font_at(text["size"], text["label"])
        left, top, right, bottom = font.getbbox(text["text"], anchor="ls")
        x, y = text["x"], text["y"]
        assert x + left >= 32 and y + top >= 32
        assert x + right <= 1888 and y + bottom <= 1048
        assert right <= text["width"] + 1, "Pinned glyphs must fit the declared text budget"
        if text["source"] in boxes:
            box = boxes[text["source"]]
            assert text["size"] >= 40
            if text["label"]:
                assert text["size"] == 88
            assert x + left >= box["x"] + 16
            assert x + right <= box["x"] + box["width"] - 16
            assert y + top >= box["y"] + 16
            assert y + bottom <= box["y"] + box["height"] - 16
    if include == INCLUDE:
        assert sum(t["text"] == "s = alpha/r" for t in layout.texts) == 1
        assert sum(t["text"] == "Frozen" for t in layout.texts) == 1
        assert sum(t["text"] == "r = 8" for t in layout.texts) == 1


@pytest.mark.parametrize("include, svg_path", [(INCLUDE, SVG_PATH), (BUDGET, BUDGET_SVG)])
def test_lora_single_source_author_is_byte_preserving_and_deterministic(tmp_path, include, svg_path):
    raw, original, _, _ = candidate(include)
    source = tmp_path / "_includes" / include
    source.parent.mkdir(parents=True)
    source.write_text(original)
    pinned = tmp_path / fhd_svg.FONT
    pinned.parent.mkdir(parents=True)
    pinned.symlink_to(ROOT / fhd_svg.FONT)
    catalog = tmp_path / "docs/diagram-catalog.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({"diagrams": [{"include": include}]}))
    budgets = tmp_path / "kkamji_scripts/blog/static_png/fhd-font-budgets.json"
    budgets.parent.mkdir(parents=True)
    budgets.write_text('{"sources": {}}')
    report = tmp_path / "lora-report.json"
    assert fhd_svg.author(tmp_path, report=report) == 0
    assert source.read_text() == raw
    assert fhd_svg.source_fragment(source.read_text()).encode() == original.encode()
    assert (tmp_path / svg_path).read_bytes() == (ROOT / svg_path).read_bytes()
    before = source.read_bytes()
    assert fhd_svg.author(tmp_path, check=True, report=report) == 0
    assert source.read_bytes() == before
    payload = json.loads(report.read_text())
    assert payload["counts"] == {"static-geometry-passed": 1}
    assert payload["display"] == "responsive-proportional"
    assert len(payload["entries"]) == 1
    entry = payload["entries"][0]
    assert entry["fresh"] is True and entry["include"] == include
    assert entry["issues"] == []
    assert entry["rendered_visual_review"] == entry["semantic_review"] == "not-run"
    assert entry["source_sha256"] == fhd_svg.sha(original.encode())
    assert entry["svg_sha256"] == fhd_svg.sha((ROOT / svg_path).read_bytes().rstrip(b"\n"))
    assert not list(tmp_path.rglob("*.png")) and not list(tmp_path.rglob("*.webp"))
    # A stale inline vector must fail, without changing its preserved source.
    source.write_text(raw.replace('font-size="72"', 'font-size="73"', 1))
    changed = source.read_bytes()
    assert fhd_svg.author(tmp_path, check=True, report=report) != 0
    assert source.read_bytes() == changed
    stale = json.loads(report.read_text())["entries"][0]
    assert stale["status"] == "stale" and stale["fresh"] is False
    assert stale["source_sha256"] == fhd_svg.sha(original.encode())
    # A semantic source edit invalidates the source SHA as well as the SVG.
    source.write_text(raw.replace('4096', '4097', 1))
    assert fhd_svg.author(tmp_path, check=True, report=report) != 0
    changed_source = json.loads(report.read_text())["entries"][0]
    assert changed_source["source_sha256"] != entry["source_sha256"]
    assert changed_source["status"] == "stale"


@pytest.mark.parametrize("port", ["source", "target"])
def test_lora_semantic_gate_rejects_a_disconnected_named_port(port):
    _, _, figure, original = candidate()
    layout = copy.copy(original)
    layout.connectors = copy.deepcopy(original.connectors)
    points = layout.connectors[0]["points"]
    points[0 if port == "source" else -1] = [1000, 1000]
    assert "named-endpoint-disconnected" in {i["code"] for i in fhd_svg.semantic_check(layout, figure)}


def test_lora_semantic_gate_rejects_a_reversed_arrow_direction():
    _, _, figure, original = candidate()
    layout = copy.copy(original)
    layout.connectors = copy.deepcopy(original.connectors)
    layout.connectors[0]["points"][-2] = [layout.connectors[0]["points"][-1][0] + 64, 390]
    assert "named-endpoint-direction-mismatch" in {i["code"] for i in fhd_svg.semantic_check(layout, figure)}


def test_lora_geometry_gate_rejects_node_overlap():
    _, _, _, original = candidate()
    layout = copy.copy(original)
    layout.boxes = copy.deepcopy(original.boxes)
    layout.boxes[1].update(x=64, y=493)
    assert "node-overlap" in {i["code"] for i in fhd_svg.check_layout(layout)}


def separated(a, b):
    return a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3]


def test_lora_cover_is_a_separate_light_fhd_matrix_editorial():
    cover_path = ROOT / "assets/img/ai/lora/lora-overview-cover.svg"
    raw = cover_path.read_text()
    cover = ET.fromstring(raw)
    assert (cover.attrib["width"], cover.attrib["height"], cover.attrib["viewBox"]) == ("1920", "1080", "0 0 1920 1080")
    assert cover.attrib["role"] == "img"
    assert cover.attrib["font-family"] == "LoRA Noto Sans KR"
    assert "text { font-family:" not in raw, "Do not override the embedded native-export font"
    assert cover.find(NS + "title") is not None
    description_element = cover.find(NS + "desc")
    assert description_element is not None and description_element.text is not None
    description = description_element.text
    for fact in ("not measured weights", "not one cell per parameter", "not parameter-area",
                 "s = alpha/r", "32768 + 32768 = 65536", "16777216",
                 "not W0 or W_eff", "Base and adapter are both required"):
        assert fact in description
    background = next(e for e in cover if e.tag == NS + "rect")
    assert background.attrib == {"x": "0", "y": "0", "width": "1920", "height": "1080", "fill": "#fff"}
    texts = list(cover.iter(NS + "text"))
    assert {"LoRA", "Low-Rank Adaptation", "Frozen", "W0", "B", "A", "sBA", "W_eff",
            "W_eff = W0 + sBA", "s = alpha/r", "One 4096 x 4096 matrix, r = 8",
            "16,777,216 frozen", "65,536 trainable"} <= {e.text for e in texts}
    assert raw.isascii() and "kkamji.net" not in raw
    assert "sd-fhd-artwork" not in raw and "data-edge" not in raw
    assert "/assets/fonts/deterministic-export/NotoSansKR%5Bwght%5D.ttf" in raw
    for element in cover.iter():
        assert element.tag.removeprefix(NS) in {"svg", "title", "desc", "defs", "style", "rect", "text"}
        assert all(not key.lower().startswith("on") for key in element.attrib)
        assert not any("href" in key for key in element.attrib)
    matrices = {e.attrib["id"]: e for e in cover.iter(NS + "rect") if "id" in e.attrib}
    assert set(matrices) == {"cover-base", "cover-a", "cover-b", "cover-effective"}
    assert {float(e.attrib["y"]) + float(e.attrib["height"]) / 2 for e in matrices.values()} == {642}
    for k in ("width", "height", "y"):
        assert matrices["cover-base"].attrib[k] == matrices["cover-effective"].attrib[k]
    counts = {"cover-base": 256, "cover-effective": 256, "cover-a": 128, "cover-b": 128}
    for name, rect in matrices.items():
        x, y, w, h = (float(rect.attrib[k]) for k in ("x", "y", "width", "height"))
        cells = [e for e in cover.iter(NS + "rect") if e.attrib.get("data-matrix") == name]
        assert len(cells) == counts[name], "An empty panel is not a matrix schematic"
        assert len({e.attrib["fill"] for e in cells}) >= 4
        cell_bounds = []
        for e in cells:
            cx, cy, cw, ch = (float(e.attrib[k]) for k in ("x", "y", "width", "height"))
            assert x < cx < cx + cw < x + w and y < cy < cy + ch < y + h
            cell_bounds.append((cx, cy, cx + cw, cy + ch))
        for i, a in enumerate(cell_bounds):
            assert all(separated(a, b) for b in cell_bounds[i + 1:])
    bounds = []
    for text in texts:
        font = font_at(text.attrib["font-size"], text.attrib.get("font-weight") == "700")
        assert text.text is not None
        left, top, right, bottom = font.getbbox(text.text, anchor="ls")
        x, y = float(text.attrib["x"]), float(text.attrib["y"])
        assert 32 <= x + left < x + right <= 1888, text.text
        assert 32 <= y + top < y + bottom <= 1048, text.text
        glyph = (x + left, y + top, x + right, y + bottom)
        for rect in matrices.values():
            rx, ry, rw, rh = (float(rect.attrib[k]) for k in ("x", "y", "width", "height"))
            assert separated(glyph, (rx, ry, rx + rw, ry + rh)), text.text
        bounds.append(glyph)
    for i, a in enumerate(bounds):
        assert all(separated(a, b) for b in bounds[i + 1:])


def test_lora_uses_only_the_repository_pinned_font_and_license():
    resources = json.loads((ROOT / "assets/fonts/deterministic-export/lock.json").read_text())["resources"]
    pinned = next(r for r in resources if r["path"] == "NotoSansKR[wght].ttf")
    assert fhd_svg.sha((ROOT / fhd_svg.FONT).read_bytes()) == pinned["sha256"]
    assert fhd_svg.sha((ROOT / "assets/fonts/deterministic-export" / pinned["license_path"]).read_bytes()) == pinned["license_sha256"]


def test_lora_semantic_gate_rejects_a_missing_update_edge():
    _, _, figure, original = candidate()
    layout = copy.copy(original)
    layout.connectors = original.connectors[:-1]
    assert "missing-source-edge" in {i["code"] for i in fhd_svg.semantic_check(layout, figure)}


def test_lora_text_coverage_rejects_a_missing_scale_label():
    _, original, figure, source = candidate()
    layout = copy.copy(source)
    layout.texts = [t for t in source.texts if t["text"] != "s = alpha/r"]
    assert "source-text-mismatch" in {i["code"] for i in fhd_svg.semantic_check(layout, figure)}
    assert "original-visible-text-coverage" in {i["code"] for i in fhd_svg.visible_text_coverage(layout, original)}

def test_lora_budget_encodes_the_exact_counts_and_linear_length_ratio():
    _, source, figure, layout = candidate(BUDGET)
    named = {e.attrs["id"]: e for e in figure.descendants() if e.attrs.get("id")}
    assert figure.attrs["id"] == "sd-lora-parameter-budget"
    assert named["budget-example"].text() == "One 4096 x 4096 matrix, r = 8"
    assert named["budget-a"].text() == "A: 8 x 4096\n32,768"
    assert named["budget-b"].text() == "B: 4096 x 8\n32,768"
    assert named["budget-sum"].text() == "A + B\n65,536"
    assert named["budget-full-count"].text() == "16,777,216"
    assert named["budget-lora-count"].text() == "65,536"
    assert named["budget-axis"].text() == "Same linear scale"
    assert named["budget-zero"].text() == "0"
    assert named["budget-ratio"].text() == "1/256 = 0.390625%"
    assert named["budget-scope"].text() == "One selected matrix only; not a VRAM, time or full-model ratio"
    full, lora = layout.groups
    assert len(layout.groups) == 2 and not layout.boxes and not layout.connectors and not layout.images
    assert int(full["data_value"]) == int(named["budget-full-bar"].attrs["data-value"]) == 4096 * 4096
    assert int(lora["data_value"]) == int(named["budget-lora-bar"].attrs["data-value"]) == 8 * 4096 + 4096 * 8
    assert full["width"] == 1728 and lora["width"] == 6.75
    assert full["width"] / lora["width"] == 256
    assert 100 * int(lora["data_value"]) / int(full["data_value"]) == 0.390625
    assert full["x"] == lora["x"] == 96
    assert full["height"] == lora["height"] == 64
    svg = ET.fromstring((ROOT / BUDGET_SVG).read_text())
    marks = {e.attrib["data-source"]: e for e in svg.iter() if e.attrib.get("data-encoding") == "bar-length"}
    for bar in layout.groups:
        mark = marks[bar["source"]]
        assert mark.attrib["data-value"] == bar["data_value"]
        assert mark.attrib["data-encoding"] == "bar-length"
        assert mark.attrib["fill"] == mark.attrib["stroke"] == bar["fill"]
        assert mark.attrib["stroke-width"] == mark.attrib["rx"] == "0"
        assert float(mark.attrib["width"]) == bar["width"]
    assert not fhd_svg.check_layout(layout)
    assert not fhd_svg.semantic_check(layout, figure)
    assert not fhd_svg.visible_text_coverage(layout, source)


@pytest.mark.parametrize("mutation, code", [
    ({"width": 30}, "data-bar-scale-mismatch"),
    ({"x": 110}, "data-bar-scale-mismatch"),
    ({"height": 80}, "data-bar-scale-mismatch"),
    ({"data_value": "65535"}, "data-bar-value-mismatch"),
    ({"data_encoding": "area"}, "data-bar-value-mismatch"),
    ({"radius": 3}, "data-bar-paint-mismatch"),
    ({"fill": "none"}, "data-bar-paint-mismatch"),
    ({"owner": "unpainted"}, "data-bar-paint-mismatch"),
    ({"border_width": 2}, "data-bar-paint-mismatch"),
    ({"width": 0}, "data-bar-paint-mismatch"),
    ({"y": 480}, "data-bar-text-overlap"),
])
def test_lora_data_bar_gate_rejects_distorted_marks(mutation, code):
    _, _, figure, layout = candidate(BUDGET)
    layout.groups[1].update(mutation)
    assert code in {i["code"] for i in fhd_svg.semantic_check(layout, figure)}


def test_lora_data_bar_gate_rejects_duplicate_marks():
    _, _, figure, layout = candidate(BUDGET)
    layout.groups.append(copy.deepcopy(layout.groups[1]))
    assert "duplicate-source-data-bar" in {i["code"] for i in fhd_svg.semantic_check(layout, figure)}


@pytest.mark.parametrize("value", ["0", "-1", "0.5", "invalid"])
def test_lora_data_bar_gate_rejects_invalid_source_counts(value):
    _, _, figure, layout = candidate(BUDGET)
    mark = next(e for e in figure.descendants() if e.attrs.get("id") == "budget-lora-bar")
    mark.attrs["data-value"] = value
    assert "invalid-source-data-bar" in {i["code"] for i in fhd_svg.semantic_check(layout, figure)}


@pytest.mark.parametrize("include", [INCLUDE, BUDGET])
def test_lora_pinned_glyph_ink_bounds_are_pairwise_clear(include):
    _, _, _, layout = candidate(include)
    bounds = []
    for text in layout.texts:
        left, top, right, bottom = font_at(text["size"], text["label"]).getbbox(text["text"], anchor="ls")
        bounds.append((text["x"] + left, text["y"] + top, text["x"] + right, text["y"] + bottom))
    for i, a in enumerate(bounds):
        assert all(separated(a, b) for b in bounds[i + 1:])


def test_lora_new_square_bar_support_does_not_change_default_node_paint():
    _, _, figure, layout = candidate()
    drawing = ET.fromstring(fhd_svg.svg_document(layout, figure, "test"))
    for node in [e for e in drawing.iter() if "data-node" in e.attrib]:
        assert node.attrib["rx"] == "12"
        assert "data-value" not in node.attrib and "data-encoding" not in node.attrib

