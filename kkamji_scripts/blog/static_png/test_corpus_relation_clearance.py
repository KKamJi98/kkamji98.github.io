"""Seven exact-source scopes, including four round3 contact/topology repairs.

Run with the pinned blog venv Python and pytest -p no:cacheprovider. Native
pixels, browser glyph containment and landing the compiler hook belong to Main.
"""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "kkamji_scripts/blog"))
import fhd_svg as compiler

SCOPES = {
    112: "diagrams/static/ci-cd/ci-cd-study/jenkins-ci-workflow.html",
    117: "diagrams/static/ci-cd/ci-cd-study/kubernetes-gitops-loop.html",
    215: "diagrams/static/kubernetes/horizontal-pod-autoscaling.html",
    227: "diagrams/static/kubernetes/mysql-kubernetes-deployment.html",
    231: "diagrams/static/kubernetes/pod-identity-workflow.html",
    265: "diagrams/static/project/rememberme/waf_alarm_workflow.html",
    297: "diagrams/static/sap-c02/dns-global-traffic-decision-layers.html",
}
EDGE = "root.0.2.1.2.3"


def helper():
    return importlib.import_module("corpus_relation_clearance")


def state(layout):
    return deepcopy({key: getattr(layout, key) for key in (
        "boxes", "groups", "group_bounds", "connectors", "texts", "images",
        "profile", "label_size", "detail_size", "gap", "padding")})


def capture_author(repaired):
    protected = [path for include in SCOPES.values() for path in (
        ROOT / "_includes" / include,
        ROOT / "assets/img/diagrams/fhd-svg" / include.removeprefix("diagrams/").replace(".html", ".svg"))]
    original_bytes = {path: path.read_bytes() for path in protected}
    captures = {}
    includes = {}
    original_manual = compiler.manual_relation_fixes
    original_svg = compiler.svg_document
    original_flow = compiler.corpus_flow_balance_profile
    addon = helper() if repaired else None

    def profile(include):
        return original_flow(include)

    def manual(layout, figure, include):
        additions = addon.scoped_profile(include) if addon else {}
        if additions:
            # Preserve the confirmed source density while exercising the REAL
            # measure/draw profile. The unmocked production author loop has
            # its own integration test below; this is the isolated source probe.
            scoped = deepcopy(layout.profile)
            for key, value in additions.items():
                scoped[key] = {**scoped.get(key, {}), **value}
            measured = compiler.Layout(layout.font, layout.label_size, layout.detail_size,
                                       layout.gap, layout.padding, scoped)
            height = measured.measure(figure, compiler.WIDTH - 128)
            assert height <= compiler.HEIGHT - 128
            measured.draw(figure, 64, 64 + (compiler.HEIGHT - 128 - height) / 2,
                          compiler.WIDTH - 128)
            measured.resolve_boundary_edges(figure)
            layout.__dict__.update(measured.__dict__)
        original_manual(layout, figure, include)
        includes[id(layout)] = include
        if addon:
            addon.repair_relations(layout, figure, include)

    def svg(layout, figure, digest, *args, **kwargs):
        result = original_svg(layout, figure, digest, *args, **kwargs)
        captures[includes[id(layout)]] = (layout, figure, result)
        ET.fromstring(result)
        return result

    def no_write(*args, **kwargs):
        raise AssertionError("author(check=True) must not write files")

    with patch.object(compiler, "manual_relation_fixes", manual), \
         patch.object(compiler, "corpus_flow_balance_profile", profile), \
         patch.object(compiler, "svg_document", svg), \
         patch.object(compiler, "repair_relations", lambda layout, *_: layout, create=True), \
         patch.object(compiler, "scoped_profile", lambda *_: {}, create=True), \
         patch.object(Path, "write_text", no_write), \
         patch.object(Path, "write_bytes", no_write):
        compiler.author(ROOT, check=True, report=None)
    assert all(path.read_bytes() == raw for path, raw in original_bytes.items()), "read-only author changed source/SVG bytes"
    catalog = json.loads((ROOT / "docs/diagram-catalog.json").read_text())["diagrams"]
    assert set(captures) == {row["include"] for row in catalog}
    assert all(catalog[index]["include"] == include for index, include in SCOPES.items())
    return captures


@pytest.fixture(scope="module")
def baseline():
    return capture_author(False)


@pytest.fixture(scope="module")
def candidate():
    return capture_author(True)


def test_gitops_moves_only_cd_paragraph_34px_without_rerouting(baseline, candidate):
    old = baseline[SCOPES[117]][0]
    new = candidate[SCOPES[117]][0]
    cluster = next(b for b in old.boxes if b["source"] == "root.0.2.1.2.4")
    cd = [t for t in old.texts if t["source"] == EDGE and t["x"] == cluster["x"]]
    assert [t["y"] for t in cd] == pytest.approx([722.3, 746.6])
    route = next(e for e in old.connectors if e["source"] == EDGE)
    route_y = route["points"][2][1]
    assert cd[0]["y"] < route_y < cd[-1]["y"], "the current line cuts the CD paragraph"
    expected = state(old)
    pull = next(e for e in expected['connectors'] if e['source'].endswith('.image-pull'))
    for point in pull['points'][-2:]:
        point[1] -= 24
    for text in expected["texts"]:
        if text["source"] == EDGE and text["x"] == cluster["x"]:
            text["y"] = round(text["y"] - 34, 3)
    # Round3 additionally wraps only the separate TOP Pull Request caption.
    expected["texts"] = [t for t in expected["texts"] if t["source"] != "root.0.2.1.1"]
    actual = state(new)
    actual["texts"] = [t for t in actual["texts"] if t["source"] != "root.0.2.1.1"]
    assert actual == expected, "retain the 34px CD repair and all routes/cards"
    moved = [t for t in new.texts if t["source"] == EDGE and t["x"] == cluster["x"]]
    assert [t["y"] for t in moved] == pytest.approx([688.3, 712.6])
    # Conservative authored baseline model, including half of the 3px stroke.
    assert route["points"][2][1] - 1.5 - max(t["y"] + t["size"] * .25 for t in moved) >= 9


def test_jenkins_workflow_splits_only_the_two_source_labels(baseline, candidate):
    old, figure, _ = baseline[SCOPES[112]]
    new, _, svg = candidate[SCOPES[112]]
    target = "root.0.2.1.2.4"
    incoming = [e for e in new.connectors if e.get("to") == [target]]
    assert len([e for e in old.connectors if e.get("to") == [target]]) == 1
    assert len(incoming) == 2, "Registry input is missing from the current source model"
    by_key = {e["source"]: e for e in incoming}
    cd, pull = by_key[EDGE], by_key[EDGE + ".image-pull"]
    assert cd["from"] == ["root.0.2.1.2.2"]
    assert pull["from"] == ["root.0.2.0.2.2"]
    assert cd["to"] == pull["to"] == [target]
    assert pull["origin"] == EDGE
    assert cd["label"] == "Argo CD -> K8S: sync (삭제는 prune 설정 시)"
    assert pull["label"] == "Container image registry -> K8S: image pull"
    assert pull["points"] == [[886, 618.5], [960, 618.5], [960, 785.1], [1034, 785.1]]
    original_cd = next(e for e in old.connectors if e["source"] == EDGE)
    assert cd["points"] == original_cd["points"]
    for key in ("boxes", "groups", "group_bounds", "images", "profile"):
        assert getattr(new, key) == getattr(old, key)
    assert [e for e in new.connectors if e["source"] not in by_key] == [e for e in old.connectors if e["source"] != EDGE]
    assert [t for t in new.texts if t["source"] != EDGE] == [t for t in old.texts if t["source"] != EDGE]
    for label in (cd["label"], pull["label"]):
        assert "".join(label.split()) in "".join(t["text"].replace(" ", "") for t in new.texts if t["source"] == EDGE)
    assert all(t["source"] != pull["source"] for t in new.texts)
    assert cd["meaning_bounds"] != pull["meaning_bounds"]
    note = " ".join(t["text"] for t in new.texts if t["source"] == "root.0.3")
    assert "kubectl set image" in note and "0.0.3" in note
    assert "Jenkinsfile에는 manifest 갱신이나 Argo CD 연동이 없습니다." in note
    assert "실습 미구현" in figure.text()
    xml = ET.fromstring(svg)
    path = next(e for e in xml if e.get("data-edge") == pull["source"])
    assert path.get("data-from") == "root.0.2.0.2.2" and path.get("data-to") == target
    assert compiler.check_layout(new) == []
    assert compiler.semantic_check(new, figure) == []
    original = compiler.source_fragment((ROOT / "_includes" / SCOPES[112]).read_text())
    assert compiler.visible_text_coverage(new, original) == []


def glyph_bbox(text):
    # Font advances alone were the original false-negative: measure real pinned
    # glyph ink, not the compiler's approximate stored width. This is NOT PNG QA.
    from PIL import ImageFont
    font = ImageFont.truetype(str(ROOT / compiler.FONT), 2000, layout_engine=ImageFont.Layout.RAQM)
    font.set_variation_by_axes([700 if text["label"] else 400])
    left, top, right, bottom = font.getbbox(text["text"], anchor="ls")
    scale = text["size"] / 2000
    return (text["x"] + left * scale, text["y"] + top * scale,
            text["x"] + right * scale, text["y"] + bottom * scale)


@pytest.mark.parametrize("index,key,width,from_key,to_key,caption", [
    (215, "root.0.1.3", 168, "root.0.1.2", "root.0.1.4", "current replicas x current/target"),
    (265, "root.0.1.7", 180, "root.0.1.6", "root.0.1.8", "Slack delivery"),
])
def test_premeasure_profiles_clear_real_glyphs_without_changing_relations(
        baseline, candidate, index, key, width, from_key, to_key, caption):
    old, _, _ = baseline[SCOPES[index]]
    new, figure, _ = candidate[SCOPES[index]]
    old_target = next(b for b in old.boxes if b["source"] == to_key)
    assert max(glyph_bbox(t)[2] for t in old.texts if t["source"] == key) > old_target["x"]
    assert new.profile.get("edge_widths", {}).get("root.0.1") == width, "profile must be merged BEFORE measure"
    assert new.profile["edge_label_insets"][key] == 12
    boxes = {b["source"]: b for b in new.boxes}
    source, target = boxes[from_key], boxes[to_key]
    assert target["x"] - source["x"] - source["width"] == pytest.approx(width)
    edge = next(e for e in new.connectors if e["source"] == key)
    assert edge["label"] == caption and edge["from"] == [from_key] and edge["to"] == [to_key]
    assert edge["points"][0][0] == source["x"] + source["width"] + 12
    assert edge["points"][-1][0] == target["x"] - 12
    runs = [t for t in new.texts if t["source"] == key]
    assert " ".join(t["text"] for t in runs) == caption
    for text in runs:
        left, _, right, _ = glyph_bbox(text)
        assert left - source["x"] - source["width"] >= 12 - .001
        assert target["x"] - right >= 12 - .001
    if index == 265:
        assert len(runs) == 1
    else:
        lower_old = next(e for e in old.connectors if e["source"] == "root.0.1.7")
        lower_new = next(e for e in new.connectors if e["source"] == "root.0.1.7")
        for field in ("source", "from", "to", "label", "both"):
            assert lower_new[field] == lower_old[field]
        assert [(t["text"], t["size"]) for t in new.texts if t["source"] == "root.0.1.7"] == [(t["text"], t["size"]) for t in old.texts if t["source"] == "root.0.1.7"]
    assert compiler.check_layout(new) == []
    assert compiler.semantic_check(new, figure) == []


def test_pod_identity_extends_only_outer_frame_not_external_note(baseline, candidate):
    old, _, _ = baseline[SCOPES[231]]
    new, _, _ = candidate[SCOPES[231]]
    key = "root.0.2.1"
    prior = next(g for g in old.groups if g["source"] == key)
    frame = next(g for g in new.groups if g["source"] == key)
    assert (prior["x"], prior["y"], prior["width"], prior["height"]) == (64, 430, 1792, 514)
    note = [t for t in old.texts if t["source"] == "root.0.5"]
    assert len(note) == 2 and not "root.0.5".startswith(key + ".")
    assert max(glyph_bbox(t)[3] for t in note) > prior["y"] + prior["height"] - 1
    expected = state(old)
    next(g for g in expected["groups"] if g["source"] == key)["height"] = 530
    expected["group_bounds"][key]["height"] = 530
    for text in expected["texts"]:
        if text['source'] == 'root.0.2.1.2.0.2':
            text['x'] += 24
            text['y'] -= 6
        if text["source"] in ("root.0.2.1.2.0.1.1", "root.0.2.1.2.0.1.1.legend.meaning"):
            text["x"] += 24
            text["y"] -= 24
    assert state(new) == expected, "only the frame, worker note and approved A legend pair may move"
    assert new.group_bounds[key] == frame
    assert (frame["height"], frame["y"] + frame["height"]) == (530, 960)
    assert frame["y"] + frame["height"] - 1 - max(glyph_bbox(t)[3] for t in note) >= 12
    assert len(new.groups) == 7 and len(new.connectors) == 13
    pairs = [(g["source"], r["source"]) for g in new.groups for r in new.groups + new.boxes
             if r["source"].startswith(g["source"] + ".")]
    assert len(pairs) == 41
    s3 = next(b for b in new.boxes if b["source"] == "root.0.4")
    assert (s3["x"], s3["y"], s3["width"], s3["height"]) == (710, 968, 1146, 67.7)
    assert s3["y"] - 1 - (frame["y"] + frame["height"] + 1) == 6
    signed = next(e for e in new.connectors if e["source"] == "root.0.3")
    assert signed["from"] == ["root.0.2.1.2.0.1.4"] and signed["to"] == ["root.0.4"]
    assert signed["points"][1][0] == signed["points"][2][0] == 668


def test_cloudfront_moves_only_its_external_bus_16px(baseline, candidate):
    old, _, _ = baseline[SCOPES[297]]
    new, _, svg = candidate[SCOPES[297]]
    key = "root.0.2.2.3.0"
    edge = next(e for e in old.connectors if e["source"] == key)
    frame = next(g for g in old.groups if g["source"] == "root.0.2.2")
    assert edge["points"][1][0] == edge["points"][2][0] == frame["x"] + frame["width"] == 1856
    expected = state(old)
    expected_edge = next(e for e in expected["connectors"] if e["source"] == key)
    expected_edge["points"][1][0] = expected_edge["points"][2][0] = 1872
    assert state(new) == expected, "DNS and Global Accelerator relations must not change"
    changed = next(e for e in new.connectors if e["source"] == key)
    assert changed["from"] == ["root.0.2.2.1"] and changed["to"] == ["root.0.2.2.3.1"]
    assert changed["label"] == "CloudFront 캐시 미스일 때"
    assert changed["points"][0] == [1844, pytest.approx(426.25)]
    assert changed["points"][-1] == [1844, pytest.approx(841.85)]
    assert changed["points"][1][0] == changed["points"][2][0] == 1872 < compiler.WIDTH - 32
    for endpoint, point in zip(changed["from"] + changed["to"], (changed["points"][0], changed["points"][-1])):
        box = next(b for b in new.boxes if b["source"] == endpoint)
        assert point[0] - box["x"] - box["width"] == pytest.approx(12)
    xml = ET.fromstring(svg)
    path = next(e for e in xml if e.get("data-edge") == key)
    assert "1872.000" in path.get("d", "") and "1856.000" not in path.get("d", "")


@pytest.mark.parametrize("index", sorted(SCOPES))
def test_real_source_coverage_geometry_and_svg_metadata(candidate, index):
    layout, figure, svg = candidate[SCOPES[index]]
    original = compiler.source_fragment((ROOT / "_includes" / SCOPES[index]).read_text())
    assert compiler.check_layout(layout) == []
    assert compiler.semantic_check(layout, figure) == []
    assert compiler.visible_text_coverage(layout, original) == []
    xml = ET.fromstring(svg)
    assert (xml.get("width"), xml.get("height"), xml.get("viewBox")) == ("1920", "1080", "0 0 1920 1080")
    paths = {e.get("data-edge"): e for e in xml if e.get("data-edge")}
    assert set(paths) == {e["source"] for e in layout.connectors if "points" in e}
    for edge in layout.connectors:
        if "points" in edge:
            path = paths[edge["source"]]
            assert path.get("data-from") == " ".join(edge["from"])
            assert path.get("data-to") == " ".join(edge["to"])
            assert path.get("d") == " ".join(("M" if i == 0 else "L") + f" {x:.3f} {y:.3f}" for i, (x, y) in enumerate(edge["points"]))
    if index == 117:
        cd = [t for t in layout.texts if t["source"] == EDGE and t["x"] == 1040]
        route = next(e for e in layout.connectors if e["source"] == EDGE)
        assert route["points"][2][1] - 1.5 - max(glyph_bbox(t)[3] for t in cd) >= 12


def test_all_unselected_sources_and_svg_bytes_are_unchanged(baseline, candidate):
    untouched = set(baseline) - set(SCOPES.values())
    assert len(untouched) == len(baseline) - len(SCOPES)
    for include in sorted(untouched):
        old, _, old_svg = baseline[include]
        new, figure, new_svg = candidate[include]
        assert state(new) == state(old), include
        assert new_svg == old_svg, include
        assert helper().scoped_profile(include) == {}
        prior = dict(vars(new))
        assert helper().repair_relations(new, figure, include) is new
        assert vars(new) == prior


@pytest.mark.parametrize("index", sorted(SCOPES))
def test_repair_is_idempotent_after_label_completion(candidate, index):
    layout, figure, svg = candidate[SCOPES[index]]
    prior, attrs = state(layout), set(vars(layout))
    assert helper().repair_relations(layout, figure, SCOPES[index]) is layout
    compiler.complete_relation_labels(layout)
    assert state(layout) == prior
    assert set(vars(layout)) == attrs
    assert compiler.svg_document(layout, figure, ET.fromstring(svg).get("data-source-sha256")) == svg


def test_profiles_are_exact_fresh_and_do_not_reduce_font_budgets():
    addon = helper()
    assert addon is not None
    assert addon.SCOPES == SCOPES
    assert addon.scoped_profile(SCOPES[215]) == {"edge_widths": {"root.0.1": 168}, "edge_label_insets": {"root.0.1.3": 12}}
    assert addon.scoped_profile(SCOPES[265]) == {"edge_widths": {"root.0.1": 180}, "edge_label_insets": {"root.0.1.7": 12}}
    for include in SCOPES.values():
        value = addon.scoped_profile(include)
        assert set(value) <= {"edge_widths", "edge_label_insets"}
        if value:
            value["edge_widths"]["root.0.1"] = 1
            assert addon.scoped_profile(include)["edge_widths"]["root.0.1"] > 1
        for altered in (include + ".backup", "_includes/" + include, include.upper()):
            assert addon.scoped_profile(altered) == {}


@pytest.mark.parametrize("index", [112, 117, 227, 231, 297])
def test_wrong_figure_is_rejected_before_any_mutation(baseline, index):
    from copy import copy
    original, figure, _ = baseline[SCOPES[index]]
    layout = copy(original)
    layout.__dict__.update(state(original))
    wrong = copy(figure)
    wrong.attrs = {**figure.attrs, "id": "unrelated-figure"}
    prior = state(layout)
    with pytest.raises(ValueError, match="figure"):
        helper().repair_relations(layout, wrong, SCOPES[index])
    assert state(layout) == prior and not hasattr(layout, "_relation_clearance_repaired")


@pytest.mark.parametrize("index", [112, 117, 227, 231, 297])
def test_source_only_namespace_node_variants_keep_keys_and_duck_type(baseline, candidate, index):
    from copy import copy

    class Namespace:
        class Node:
            def __init__(self, element, parent=None):
                self.key, self.attrs, self.classes = element.key, dict(element.attrs), set(element.classes)
                self.tag, self.parent, self._text = element.tag, parent, element.text()
                self.children = [Namespace.Node(child, self) for child in element.children]

            def text(self):
                return self._text

            def descendants(self):
                for child in self.children:
                    yield child
                    yield from child.descendants()

    original, figure, _ = baseline[SCOPES[index]]
    layout = copy(original)
    layout.__dict__.update(state(original))
    source = Namespace.Node(figure)
    assert [e.key for e in source.descendants()] == [e.key for e in figure.descendants()]
    helper().repair_relations(layout, source, SCOPES[index])
    compiler.complete_relation_labels(layout)
    assert state(layout) == state(candidate[SCOPES[index]][0])




def test_missing_registry_box_cannot_create_an_independent_component(baseline):
    from copy import copy
    original, figure, _ = baseline[SCOPES[112]]
    layout = copy(original)
    layout.__dict__.update(state(original))
    layout.boxes = [b for b in layout.boxes if b["source"] != "root.0.2.0.2.2"]
    prior = state(layout)
    with pytest.raises(ValueError, match="Registry"):
        helper().repair_relations(layout, figure, SCOPES[112])
    assert state(layout) == prior and not hasattr(layout, "_relation_clearance_repaired")


def test_wrong_origin_bus_is_rejected_without_partial_changes(baseline):
    from copy import copy
    original, figure, _ = baseline[SCOPES[297]]
    layout = copy(original)
    layout.__dict__.update(state(original))
    edge = next(e for e in layout.connectors if e["source"] == "root.0.2.2.3.0")
    edge["points"][1][0] = edge["points"][2][0] = 1700
    prior = state(layout)
    with pytest.raises(ValueError, match="CloudFront"):
        helper().repair_relations(layout, figure, SCOPES[297])
    assert state(layout) == prior and not hasattr(layout, "_relation_clearance_repaired")


def test_jenkins_pull_caption_is_below_painted_left_lane(candidate):
    layout = candidate[SCOPES[112]][0]
    lane = next(g for g in layout.groups if g["source"] == "root.0.2.0")
    runs = [t for t in layout.texts if t["source"] == EDGE and t["x"] == 579]
    assert len(runs) == 2
    assert min(glyph_bbox(t)[1] for t in runs) - (lane["y"] + lane["height"] + 1) >= 12
    assert max(glyph_bbox(t)[3] for t in runs) < 900


def test_gitops_top_caption_has_real_font_frame_and_flow_insets(candidate):
    layout = candidate[SCOPES[117]][0]
    runs = [t for t in layout.texts if t["source"] == "root.0.2.1.1"]
    frame = next(g for g in layout.groups if g["source"] == "root.0.2.1")
    flow = next(g for g in layout.groups if g["source"] == "root.0.2.1.2")
    assert frame["x"] + frame["width"] - 1 - max(glyph_bbox(t)[2] for t in runs) >= 24
    assert flow["y"] - 1 - max(glyph_bbox(t)[3] for t in runs) >= 12
    assert [t["text"] for t in runs] == ["CI (Pipeline) -> Config Git Repository:", "Pull Request"]
    assert {t["size"] for t in runs} == {18}


def test_mysql_injection_targets_actual_pod_not_middle_service(baseline, candidate):
    old, _, _ = baseline[SCOPES[227]]
    new, figure, svg = candidate[SCOPES[227]]
    old_edge = next(e for e in old.connectors if e["source"] == "root.0.3")
    edge = next(e for e in new.connectors if e["source"] == "root.0.3")
    pod = next(b for b in new.boxes if b["source"] == "root.0.4.0")
    assert old_edge["to"] == ["root.0.4"] and old_edge["points"][-1][0] == 960
    assert edge["to"] == [pod["source"]], "injection must not target the Service-centered flow group"
    assert edge["from"] == ["root.0.2"] and edge["label"] == old_edge["label"]
    assert edge["points"][0] == old_edge["points"][0]
    assert edge["points"][-1] == [pod["x"] + pod["width"] / 2, pod["y"] - 12]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(edge["points"], edge["points"][1:]))
    assert not any(g["source"] == "root.0.4" for g in new.groups)
    assert new.groups == [g for g in old.groups if g["source"] != "root.0.4"]
    assert new.boxes == old.boxes and new.texts == old.texts
    assert [e for e in new.connectors if e["source"] != "root.0.3"] == [e for e in old.connectors if e["source"] != "root.0.3"]
    assert "실제 접속 요청은 Client에서 Service 이름을 거쳐 MySQL Pod로 향합니다." in figure.text()
    xml = ET.fromstring(svg)
    assert next(e for e in xml if e.get("data-edge") == "root.0.3").get("data-to") == pod["source"]


def test_pod_identity_worker_note_keeps_real_ink_inside_frame(candidate):
    layout = candidate[SCOPES[231]][0]
    worker = next(g for g in layout.groups if g['source'] == 'root.0.2.1.2.0')
    note = next(t for t in layout.texts if t['source'] == 'root.0.2.1.2.0.2')
    left, top, right, bottom = glyph_bbox(note)
    assert left - (worker['x'] + 1) >= 12
    assert worker['x'] + worker['width'] - 1 - right >= 12
    assert worker['y'] + worker['height'] - 1 - bottom >= 12
    assert note['size'] == 14


def test_pod_identity_a_legend_clears_both_frames_without_moving_b(candidate):
    layout = candidate[SCOPES[231]][0]
    key = "root.0.2.1.2.0.1.1"
    runs = [t for t in layout.texts if t["source"] in (key, key + ".legend.meaning")]
    outer = next(g for g in layout.groups if g["source"] == "root.0.2.1")
    worker = next(g for g in layout.groups if g["source"] == "root.0.2.1.2.0")
    assert len(runs) == 2
    assert outer["y"] + outer["height"] - 1 - max(glyph_bbox(t)[3] for t in runs) >= 12
    assert min(glyph_bbox(t)[1] for t in runs) - (worker["y"] + worker["height"] + 1) >= 12
    assert min(glyph_bbox(t)[0] for t in runs) - (outer["x"] + 1) >= 12
    assert [(t["text"], t["x"], t["y"], t["size"]) for t in runs] == [
        ("A", 88, 940, 14), ("retrieve credentials", 104, 940, 14)]
    b = [t for t in layout.texts if t["source"] in (
        "root.0.2.1.2.0.1.3", "root.0.2.1.2.0.1.3.legend.meaning")]
    assert [(t["text"], t["x"], t["y"]) for t in b] == [
        ("B", 64, 990), ("temporary credentials", 80, 990)]


@pytest.mark.parametrize("owned", [False, True])
def test_mysql_post_boundary_repair_removes_only_unlabelled_synthetic_frame(baseline, owned):
    from copy import copy
    original, original_figure, _ = baseline[SCOPES[227]]
    layout, figure = copy(original), deepcopy(original_figure)
    layout.__dict__.update(state(original))
    frame = next(g for g in layout.groups if g["source"] == "root.0.4")
    assert frame["relation_boundary"] is True
    if owned:
        source_flow = next(e for e in figure.descendants() if e.key == "root.0.4")
        source_flow.attrs["aria-label"] = "explicit ownership boundary"
    helper().repair_relations(layout, figure, SCOPES[227])
    compiler.complete_group_boundaries(layout)
    assert (frame in layout.groups) == owned
    assert {g["source"] for g in layout.groups} >= {"root.0.2", "root.0.2.0", "root.0.2.1"}
    assert compiler.check_layout(layout) == []
    assert compiler.semantic_check(layout, figure) == []


@pytest.mark.parametrize("malformation", ["missing-pod", "wrong-input", "wrong-caption"])
def test_mysql_bad_input_is_rejected_without_partial_changes(baseline, malformation):
    from copy import copy
    original, figure, _ = baseline[SCOPES[227]]
    layout = copy(original)
    layout.__dict__.update(state(original))
    edge = next(e for e in layout.connectors if e["source"] == "root.0.3")
    if malformation == "missing-pod":
        layout.boxes = [b for b in layout.boxes if b["source"] != "root.0.4.0"]
    elif malformation == "wrong-input":
        edge["from"] = ["root.0.4.2"]
    else:
        edge["label"] = "literal reference is not a data-flow relation"
    prior = state(layout)
    with pytest.raises(ValueError, match="MySQL"):
        helper().repair_relations(layout, figure, SCOPES[227])
    assert state(layout) == prior and not hasattr(layout, "_relation_clearance_repaired")


def test_helper_does_not_import_compiler():
    import ast
    module = ast.parse((ROOT / "kkamji_scripts/blog/corpus_relation_clearance.py").read_text())
    names = [n.module for n in ast.walk(module) if isinstance(n, ast.ImportFrom)]
    names += [a.name for n in ast.walk(module) if isinstance(n, ast.Import) for a in n.names]
    assert not any(name and "fhd_svg" in name for name in names)


def test_compiler_integration_requires_all_scoped_repairs_not_injected(baseline):
    """Exercise Main's live author hooks, with no profile/manual replacement.

    Candidate fixtures cannot prove the real premeasure density negotiation or
    the post-complete_group_boundaries synthetic-frame removal ordering.
    """
    captured = {}
    id_to_include = {baseline[include][1].attrs["id"]: include for include in SCOPES.values()}
    original_svg = compiler.svg_document

    def svg(layout, figure, *args, **kwargs):
        if figure.attrs.get("id") in id_to_include:
            captured[id_to_include[figure.attrs["id"]]] = layout
        return original_svg(layout, figure, *args, **kwargs)

    def no_write(*args, **kwargs):
        raise AssertionError("integration check must not write artwork")

    with patch.object(compiler, "svg_document", svg), \
         patch.object(Path, "write_text", no_write), \
         patch.object(Path, "write_bytes", no_write):
        compiler.author(ROOT, check=True, report=None)
    expected = candidate_conditions(captured)
    assert all(expected.values()), f"Main-owned compiler integration missing: {expected}"


def candidate_conditions(captured):
    conditions = {}
    workflow = captured[SCOPES[112]]
    conditions[112] = any(e["source"] == EDGE + ".image-pull" and e["from"] == ["root.0.2.0.2.2"] for e in workflow.connectors)
    gitops = captured[SCOPES[117]]
    conditions[117] = [t["y"] for t in gitops.texts if t["source"] == EDGE and t["x"] == 1040] == [688.3, 712.6]
    for index, key, width in [(215, "root.0.1.3", 168), (265, "root.0.1.7", 180)]:
        profile = captured[SCOPES[index]].profile
        conditions[index] = profile.get("edge_widths", {}).get("root.0.1") == width and profile.get("edge_label_insets", {}).get(key) == 12
    mysql = captured[SCOPES[227]]
    conditions[227] = (next(e for e in mysql.connectors if e["source"] == "root.0.3")["to"] == ["root.0.4.0"]
                       and not any(g["source"] == "root.0.4" for g in mysql.groups))
    identity = captured[SCOPES[231]]
    conditions[231] = (next(g for g in identity.groups if g["source"] == "root.0.2.1")["height"] == 530
                       and all(t["y"] == 940 for t in identity.texts if t["source"] in (
                           "root.0.2.1.2.0.1.1", "root.0.2.1.2.0.1.1.legend.meaning")))
    conditions[297] = next(e for e in captured[SCOPES[297]].connectors if e["source"] == "root.0.2.2.3.0")["points"][1][0] == 1872
    top = [t for t in gitops.texts if t["source"] == "root.0.2.1.1"]
    conditions["117-top"] = [t["text"] for t in top] == [
        "CI (Pipeline) -> Config Git Repository:", "Pull Request"]
    pull = [t for t in workflow.texts if t["source"] == EDGE and t["x"] == 579]
    lane = next(g for g in workflow.groups if g["source"] == "root.0.2.0")
    conditions["112-pull"] = bool(pull) and min(glyph_bbox(t)[1] for t in pull) - (lane["y"] + lane["height"] + 1) >= 12
    return conditions
