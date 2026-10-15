"""Pod Identity painted-boundary regression; source/artwork writes are forbidden.

Static geometry and semantics only. Main owns compiler integration, native glyph
containment and original-raster visual review.
"""

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fhd_svg as compiler
from corpus_pod_identity import PAINTED_GROUPS, repair_pod_identity_clearance

ROOT = Path(__file__).resolve().parents[3]
INCLUDE = "diagrams/static/kubernetes/pod-identity-workflow.html"
SOURCE_SHA256 = "68ea84894777cabafe63bf360f96fc8dbb6d7fb3ddab1fbfa587144f67e69946"
CONFIRMED = (
    ("root.0.2.0", "root.0.2.0.1.1", 5),
    ("root.0.2.0.1.0", "root.0.2.0.1.0.1.2", 8),
    ("root.0.2.1.1", "root.0.2.1.1.1.6", 8),
    ("root.0.2.1.2.1", "root.0.2.1.2.1.1.8", 8),
)


@pytest.fixture(scope="module")
def source():
    original = compiler.source_fragment((ROOT / "_includes" / INCLUDE).read_text())
    figure = next(e for e in compiler.Parse(original).root.descendants()
                  if e.tag == "figure" and "sd" in e.classes)
    return original, figure


@pytest.fixture(scope="module")
def font():
    return compiler.Font(ROOT / compiler.FONT)


def baseline(font, source):
    typography = json.loads((ROOT / "kkamji_scripts/blog/static_png/fhd-font-budgets.json").read_text())["sources"].get(INCLUDE)
    # Preserve a real baseline after Main imports the helper into the builder.
    with patch.object(compiler, "repair_pod_identity_clearance", lambda layout, *_: layout, create=True):
        return compiler.pod_identity_layout(font, source[1], typography)


def insets(parent, child):
    return (child["x"] - parent["x"], child["y"] - parent["y"],
            parent["x"] + parent["width"] - child["x"] - child["width"],
            parent["y"] + parent["height"] - child["y"] - child["height"])


@pytest.mark.parametrize("parent,child,old_gap", CONFIRMED)
def test_repair_reserves_24px_for_confirmed_painted_children(font, source, parent, child, old_gap):
    layout = baseline(font, source)
    layout = repair_pod_identity_clearance(layout, source[1])
    painted = {r["source"]: r for r in layout.groups + layout.boxes}
    assert min(insets(painted[parent], painted[child])) >= 24 - 0.001, (
        parent, child, insets(painted[parent], painted[child]))


@pytest.mark.parametrize("parent,child,old_gap", CONFIRMED)
def test_original_5px_and_8px_gaps_are_real_despite_generic_pass(font, source, parent, child, old_gap):
    layout = baseline(font, source)
    painted = {r["source"]: r for r in layout.groups + layout.boxes}
    assert min(insets(painted[parent], painted[child])) == pytest.approx(old_gap)
    assert compiler.check_layout(layout) == []


def test_every_target_is_a_real_source_group_and_all_painted_descendants_have_24px(font, source):
    layout = repair_pod_identity_clearance(baseline(font, source), source[1])
    elements = {e.key: e for e in [source[1], *source[1].descendants()]}
    assert set(PAINTED_GROUPS) == {e.key for e in elements.values()
                                  if e.classes & {"sd-band", "sd-lane"}}
    assert all(layout.kind(elements[key]) == "group" for key in PAINTED_GROUPS)
    pairs = []
    for group in layout.groups:
        assert layout.group_bounds[group["source"]] == group
        for child in layout.groups + layout.boxes:
            if child["source"].startswith(group["source"] + "."):
                gaps = insets(group, child)
                assert min(gaps) >= 24 - 0.001, (group, child, gaps)
                assert min(gaps) - 2 >= 22 - 0.001
                pairs.append((group["source"], child["source"]))
    assert len(pairs) == 41
    # Unrelated siblings, not merely cards, must not overlap either.
    rects = layout.groups + layout.boxes
    for i, first in enumerate(rects):
        for second in rects[i + 1:]:
            if (first["source"].startswith(second["source"] + ".")
                    or second["source"].startswith(first["source"] + ".")):
                continue
            overlap_x = min(first["x"] + first["width"], second["x"] + second["width"]) - max(first["x"], second["x"])
            overlap_y = min(first["y"] + first["height"], second["y"] + second["height"]) - max(first["y"], second["y"])
            assert min(overlap_x, overlap_y) <= 0


def test_fhd_generic_semantics_and_exact_visible_text_coverage(font, source):
    layout = repair_pod_identity_clearance(baseline(font, source), source[1])
    assert (compiler.WIDTH, compiler.HEIGHT) == (1920, 1080)
    assert compiler.check_layout(layout) == []
    assert compiler.semantic_check(layout, source[1]) == []
    assert compiler.visible_text_coverage(layout, source[0]) == []


def test_existing_post_builder_compiler_completion_preserves_the_repair(font, source):
    layout = repair_pod_identity_clearance(baseline(font, source), source[1])
    before = deepcopy((layout.boxes, layout.groups, layout.texts, layout.connectors))
    compiler.manual_relation_fixes(layout, source[1], INCLUDE)
    compiler.complete_group_boundaries(layout)
    compiler.complete_relation_labels(layout)
    assert (layout.boxes, layout.groups, layout.texts, layout.connectors) == before
    assert compiler.check_layout(layout) == []
    assert compiler.semantic_check(layout, source[1]) == []
    assert compiler.visible_text_coverage(layout, source[0]) == []


def edge_identity(layout):
    return sorted((e["source"], e.get("origin"), tuple(e["from"]),
                   tuple(e["to"]), bool(e.get("both")), e["label"])
                  for e in layout.connectors)


def test_all_13_directed_source_endpoints_and_12px_anchors_are_preserved(font, source):
    old = baseline(font, source)
    before = edge_identity(old)
    layout = repair_pod_identity_clearance(old, source[1])
    assert edge_identity(layout) == before
    elements = {e.key: e for e in [source[1], *source[1].descendants()]}
    expected = []
    for key, element in elements.items():
        if layout.kind(element) != "edge":
            continue
        if key == "root.0.3":
            start, end = "root.0.2.1.2.0.1.4", "root.0.4"
        else:
            siblings = element.parent.children
            index = siblings.index(element)
            start, end = siblings[index - 1].key, siblings[index + 1].key
        expected.append((key, None, (start,), (end,),
                         "sd-arrow--both" in element.classes, element.text()))
    assert len(expected) == 13
    assert edge_identity(layout) == sorted(expected)
    boxes = {b["source"]: b for b in layout.boxes}
    for edge in layout.connectors:
        start, end = boxes[edge["from"][0]], boxes[edge["to"][0]]
        assert edge["points"][0] == pytest.approx([start["x"] + start["width"] + 12,
                                                  start["y"] + start["height"] / 2])
        assert edge["points"][-1] == pytest.approx([end["x"] - 12,
                                                   end["y"] + end["height"] / 2])
        if edge["source"] == "root.0.3":
            assert len(edge["points"]) == 4
            assert edge["points"][1][0] == edge["points"][2][0] == 668
            assert edge["to"] == ["root.0.4"]


def test_no_card_resizing_word_loss_font_change_or_source_write(font, source):
    path = ROOT / "_includes" / INCLUDE
    raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert hashlib.sha256(source[0].encode()).hexdigest() == SOURCE_SHA256
    old = baseline(font, source)
    cards = {b["source"]: (b["x"], b["width"], b["height"], b["label"], b["classes"])
             for b in old.boxes}
    text_runs = [(t["source"], t["text"], t["size"], t["width"], t["label"])
                 for t in old.texts]
    layout = repair_pod_identity_clearance(old, source[1])
    assert cards == {b["source"]: (b["x"], b["width"], b["height"], b["label"], b["classes"])
                     for b in layout.boxes}
    assert text_runs == [(t["source"], t["text"], t["size"], t["width"], t["label"])
                         for t in layout.texts]
    assert (layout.label_size, layout.detail_size, layout.padding, layout.gap) == (16, 14, 8, 8)
    assert all(t["size"] >= (16 if t["label"] else 14) for t in layout.texts)
    assert "pods.eks.amazonaws.com" in "".join(t["text"] for t in layout.texts
                                               if t["source"] == "root.0.2.0.1.0.1.2")
    mutated = "".join(t["text"] for t in layout.texts if t["source"] == "root.0.2.1.1.1.6")
    assert "AWS_CONTAINER_CREDENTIALS_FULL_URI" in mutated
    assert "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE" in mutated
    assert hashlib.sha256(path.read_bytes()).hexdigest() == raw_hash


def test_external_legends_remain_external_and_api_explanations_are_not_deleted(font, source):
    old = baseline(font, source)
    before = deepcopy(old.texts)
    layout = repair_pod_identity_clearance(old, source[1])
    for edge in ("root.0.2.1.2.0.1.1", "root.0.2.1.2.0.1.3"):
        for key in (edge, edge + ".legend.meaning"):
            assert [t for t in layout.texts if t["source"] == key] == [t for t in before if t["source"] == key]
    frames = {g["source"]: g for g in layout.groups}
    for i in (1, 3, 5, 7):
        key = "root.0.2.1.2.1.1." + str(i)
        legend = next(t for t in layout.texts if t["source"] == key)
        frame = frames["root.0.2.1.2.1"]
        assert legend["y"] - legend["size"] > frame["y"] + frame["height"]
    for key in ("root.0.2.0.1.1.1.1", "root.0.2.0.1.1.2.1"):
        assert [t["text"] for t in layout.texts if t["source"] == key] == [t["text"] for t in before if t["source"] == key]


def test_painted_svg_rectangles_retain_exact_source_ids_and_2px_strokes(font, source):
    layout = repair_pod_identity_clearance(baseline(font, source), source[1])
    svg = ET.fromstring(compiler.svg_document(layout, source[1], SOURCE_SHA256))
    assert svg.attrib["width"] == "1920" and svg.attrib["height"] == "1080"
    assert svg.attrib["viewBox"] == "0 0 1920 1080"
    assert svg.attrib["data-source-sha256"] == SOURCE_SHA256
    groups = {r.attrib["data-source"]: r.attrib for r in svg
              if r.tag.endswith("rect") and "data-source" in r.attrib}
    nodes = {r.attrib["data-node"]: r.attrib for r in svg
             if r.tag.endswith("rect") and "data-node" in r.attrib}
    assert set(groups) == set(PAINTED_GROUPS)
    assert set(nodes) == {b["source"] for b in layout.boxes}
    for group in layout.groups:
        for attr in ("x", "y", "width", "height"):
            assert float(groups[group["source"]][attr]) == pytest.approx(group[attr], abs=0.001)
    assert all(r["stroke-width"] == "2" for r in list(groups.values()) + list(nodes.values()))


def test_repair_is_in_place_idempotent_and_does_not_share_a_profile(font, source):
    first = baseline(font, source)
    second = baseline(font, source)
    original_profile = deepcopy(second.profile)
    assert repair_pod_identity_clearance(first, source[1]) is first
    after = deepcopy((first.boxes, first.groups, first.group_bounds, first.texts,
                      first.connectors, first.profile))
    assert repair_pod_identity_clearance(first, source[1]) is first
    assert (first.boxes, first.groups, first.group_bounds, first.texts,
            first.connectors, first.profile) == after
    assert second.profile == original_profile


@pytest.mark.parametrize("missing", ("frame", "card", "edge"))
def test_missing_source_identity_fails_before_geometry_mutation(font, source, missing):
    layout = baseline(font, source)
    {"frame": layout.groups, "card": layout.boxes, "edge": layout.connectors}[missing].pop()
    before = deepcopy((layout.groups, layout.boxes, layout.texts, layout.connectors, layout.group_bounds))
    with pytest.raises(ValueError, match="every original"):
        repair_pod_identity_clearance(layout, source[1])
    assert (layout.groups, layout.boxes, layout.texts, layout.connectors, layout.group_bounds) == before


def test_other_semantic_figure_is_rejected(font, source):
    figure = deepcopy(source[1])
    figure.attrs["id"] = "pod-identity-workflow-other"
    with pytest.raises(ValueError, match="exact semantic figure"):
        repair_pod_identity_clearance(baseline(font, source), figure)


def test_compiler_integration_requires_the_same_clearance_without_test_injection(font, source):
    """The one intentional RED until Main calls the helper in the custom builder."""
    typography = json.loads((ROOT / "kkamji_scripts/blog/static_png/fhd-font-budgets.json").read_text())["sources"].get(INCLUDE)
    layout = compiler.pod_identity_layout(font, source[1], typography)
    assert set(layout.profile.get("group_insets", {})) >= set(PAINTED_GROUPS)
    for group in layout.groups:
        for child in layout.groups + layout.boxes:
            if child["source"].startswith(group["source"] + "."):
                assert min(insets(group, child)) >= 24 - 0.001, (group, child)
    assert compiler.check_layout(layout) == []
