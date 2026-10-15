"""Scoped stroke-clearance regressions, including a deliberately strict compiler gate.

The compiler gate must fail until author() merges the opt-in profile before
measure(), including its alarm/config builders. No source or artwork is written.
"""

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fhd_svg as compiler
from corpus_clearance import (
    REPAIRS,
    check_corpus_clearance,
    corpus_clearance_profile,
    painted_boundary_contacts,
    stroke_clearance,
)

ROOT = Path(__file__).resolve().parents[3]
CARD_CASE = "diagrams/static/ai/humanize/humanize-route-hint.html"
NESTED_CASES = (
    "diagrams/static/ai/agentic-development-workspace.html",
    "diagrams/static/ai/graph-system-intelligence.html",
    "diagrams/static/ai/hermes-wsl2-agent-flow.html",
)


@pytest.fixture(scope="module")
def font():
    return compiler.Font(ROOT / compiler.FONT)


def source(include):
    original = compiler.source_fragment((ROOT / "_includes" / include).read_text())
    figure = next(e for e in compiler.Parse(original).root.descendants()
                  if e.tag == "figure" and "sd" in e.classes)
    return original, figure


def draw(font, include, opt_in):
    original, figure = source(include)
    typography = json.loads((ROOT / "kkamji_scripts/blog/static_png/fhd-font-budgets.json").read_text())["sources"]
    base = {**compiler.FIXED_LAYOUT_PROFILES.get(include, {}),
            **typography.get(include, {})}
    profile = {**base, **(corpus_clearance_profile(include) if opt_in else {})}
    for label, detail, gap, padding in (
        (28, 22, 24, 24), (24, 20, 20, 20), (20, 18, 16, 16),
        (18, 16, 12, 12), (16, 14, 10, 10), (16, 14, 8, 8),
    ):
        layout = compiler.Layout(font, label, detail, gap, padding, profile)
        measured = layout.measure(figure, 1792)
        if measured > 952:
            continue
        layout.draw(figure, 64, 64 + (952 - measured) / 2, 1792)
        layout.resolve_boundary_edges(figure)
        if any(i["code"] == "source-identifier-split"
               for i in compiler.semantic_check(layout, figure)):
            continue
        compiler.manual_relation_fixes(layout, figure, include)
        compiler.complete_group_boundaries(layout)
        compiler.complete_relation_labels(layout)
        return original, figure, layout, measured
    pytest.fail("no declared density fits: " + include)


def identity(layout):
    return (
        sorted(b["source"] for b in layout.boxes),
        sorted((e["source"], e.get("origin"), tuple(e.get("from", [])),
                tuple(e.get("to", []))) for e in layout.connectors),
        sorted((i["source"], i.get("src")) for i in layout.images),
    )


def test_exact_repair_scope_and_evidence_are_frozen():
    pairs = [(r.include, r.group) for r in REPAIRS]
    assert len(pairs) == len(set(pairs)) == 177
    assert len({include for include, _ in pairs}) == 135
    assert sum(bool(r.cards) for r in REPAIRS) == 76
    assert sum(bool(r.groups) for r in REPAIRS) == 104
    assert sum(len(r.cards) for r in REPAIRS) == 174
    assert sum(len(r.groups) for r in REPAIRS) == 242
    assert hashlib.sha256("\n".join(i + "|" + g for i, g in pairs).encode()).hexdigest() == "6ca58eceea555a5305602b74328cc89b46aa7f53a9931523cc54bef81ae38d2d"
    evidence = [(r.include, r.group, r.inset, r.cards, r.groups) for r in REPAIRS]
    assert hashlib.sha256(json.dumps(evidence, separators=(",", ":")).encode()).hexdigest() == "47dc93d442e6640db30992d1946837af995070859012d31aa9c022e076e0adf3"


def test_all_opt_in_source_ids_still_denote_real_groups(font):
    by_include = {}
    for repair in REPAIRS:
        by_include.setdefault(repair.include, []).append(repair)
    for include, repairs in by_include.items():
        _, figure = source(include)
        elements = {e.key: e for e in [figure, *figure.descendants()]}
        layout = compiler.Layout(font, 28, 22)
        for repair in repairs:
            assert repair.group in elements, (include, repair.group)
            assert layout.kind(elements[repair.group]) == "group"
            for child in repair.cards + repair.groups:
                assert child in elements, (include, child)
                assert child.startswith(repair.group + ".")
                assert layout.kind(elements[child]) == ("node" if child in repair.cards else "group")


def test_profile_is_copy_isolated_and_has_no_unrelated_knobs():
    first = corpus_clearance_profile(CARD_CASE)
    assert set(first) == {"group_insets"}
    assert set(first["group_insets"].values()) <= {24, 28}
    first["group_insets"]["root.0.1"] = 999
    assert corpus_clearance_profile(CARD_CASE)["group_insets"]["root.0.1"] == 24
    assert corpus_clearance_profile("diagrams/static/unknown.html") == {}
    # Do not normalize a malformed identifier into a successful opt-in lookup.
    assert corpus_clearance_profile("_includes/" + CARD_CASE) == {}
    assert corpus_clearance_profile("/" + CARD_CASE) == {}


def rect(key, x, y, width, height, **extra):
    return dict(source=key, x=x, y=y, width=width, height=height, **extra)


def test_stroke_width_is_not_center_coordinate_clearance():
    outer = rect("root.0.1", 0, 0, 200, 200)
    inner = rect("root.0.1.0", 24, 24, 152, 152)
    assert stroke_clearance(outer, inner) == (22, 22, 22, 22)
    inner["stroke_width"] = 4
    assert stroke_clearance(outer, inner) == (21, 21, 21, 21)


def test_contact_detector_requires_painted_ancestral_containment():
    parent = rect("root.0.1", 0, 0, 200, 200)
    nested = rect("root.0.1.0", 0, 0, 100, 200)
    sibling = rect("root.0.10", 0, 0, 100, 200)
    external_legend = rect("root.0.1.legend", 190, 220, 100, 40)
    unpainted = rect("root.0.1.unpainted", 0, 0, 200, 200)
    findings = painted_boundary_contacts([], [parent, nested, sibling, external_legend])
    assert [(f["group"], f["source"], f["kind"]) for f in findings] == [
        ("root.0.1", "root.0.1.0", "group")]
    assert unpainted["source"] not in {f["source"] for f in findings}
    assert findings[0]["clearance_ltrb"] == (-2, -2, 98, -2)


@pytest.mark.parametrize("include", (CARD_CASE,) + NESTED_CASES)
def test_old_contact_is_detected_and_opt_in_measure_draw_fixes_it(font, include):
    original, figure, old, old_height = draw(font, include, False)
    _, _, new, new_height = draw(font, include, True)
    defects = check_corpus_clearance(old, include)
    assert any(i["code"] == "boundary-stroke-clearance" for i in defects)
    assert check_corpus_clearance(new, include) == []
    # A denser compiler fallback may lower total height; compare the same
    # density to prove measure() reserves the added inset before draw().
    same_density = compiler.Layout(font, old.label_size, old.detail_size,
                                   old.gap, old.padding,
                                   {**old.profile, **corpus_clearance_profile(include)})
    assert same_density.measure(figure, 1792) > old_height
    assert identity(old) == identity(new)
    assert compiler.check_layout(new) == []
    assert compiler.semantic_check(new, figure) == []
    assert compiler.visible_text_coverage(new, original) == []
    changed = [(b["x"], b["y"], b["width"], b["height"]) for b in new.boxes]
    assert changed != [(b["x"], b["y"], b["width"], b["height"]) for b in old.boxes]
    # Test the actual painted SVG, not just the profile declaration.
    import xml.etree.ElementTree as ET
    root = ET.fromstring(compiler.svg_document(new, figure, "test"))
    painted = {r.attrib["data-source"]: r.attrib for r in root
               if r.tag.endswith("rect") and "data-source" in r.attrib}
    for repair in (r for r in REPAIRS if r.include == include):
        assert repair.group in painted
        assert painted[repair.group]["stroke-width"] == "2"
        group = next(g for g in new.groups if g["source"] == repair.group)
        element = next(e for e in figure.descendants() if e.key == repair.group)
        assert group["height"] == pytest.approx(new.measure(element, group["width"]))


def test_missing_frame_or_child_is_not_silently_reported_as_clear(font):
    _, _, layout, _ = draw(font, CARD_CASE, True)
    layout.groups = [g for g in layout.groups if g["source"] != "root.0.1"]
    assert any(i["code"] == "boundary-clearance-missing-frame"
               for i in check_corpus_clearance(layout, CARD_CASE))
    _, _, layout, _ = draw(font, CARD_CASE, True)
    layout.boxes = [b for b in layout.boxes if b["source"] != "root.0.1.0"]
    assert any(i["code"] == "boundary-clearance-missing-child"
               for i in check_corpus_clearance(layout, CARD_CASE))


@pytest.mark.parametrize("include", (
    "diagrams/static/ai/jev-decision-pipeline.html",
    "diagrams/static/ai/jev-system-one-banner.html",
    "diagrams/static/ai/rag-04-hybrid-rerank.html",
    "diagrams/static/kubernetes/pod-identity-workflow.html",
))
def test_existing_jev_rag_and_external_pod_identity_legend_are_not_opted_in(include):
    assert corpus_clearance_profile(include) == {}


@pytest.mark.parametrize("include", (
    "diagrams/static/aws/analytics-stack-03-distributed-sql-mpp.html",
    "diagrams/static/kubernetes/metrics-server-collection.html",
))
def test_clearance_retains_fixed_columns_edge_widths_and_width_budgets(font, include):
    original, figure, new, _ = draw(font, include, True)
    for name, value in compiler.FIXED_LAYOUT_PROFILES[include].items():
        assert new.profile[name] == value
    assert check_corpus_clearance(new, include) == []
    assert compiler.check_layout(new) == []
    assert compiler.semantic_check(new, figure) == []
    assert compiler.visible_text_coverage(new, original) == []


@pytest.mark.parametrize("include", (
    "diagrams/static/sap-c02/cloudwatch-alarm-missing-data.html",
    "diagrams/static/sap-c02/config-evaluation-remediation.html",
))
def test_custom_alarm_config_builders_reserve_insets_before_measure(font, include):
    original, figure = source(include)
    typography = json.loads((ROOT / "kkamji_scripts/blog/static_png/fhd-font-budgets.json").read_text())["sources"]

    def build():
        if include.endswith("cloudwatch-alarm-missing-data.html"):
            layout = compiler.alarm_layout(font, figure)
        else:
            layout = compiler.config_layout(font, figure, typography.get(include))
        compiler.manual_relation_fixes(layout, figure, include)
        compiler.complete_group_boundaries(layout)
        compiler.complete_relation_labels(layout)
        return layout

    # Parent integration may already inject a default, so explicitly strip
    # the corpus keys for the negative control without changing Jev profiles.
    init = compiler.Layout.__init__
    opted = corpus_clearance_profile(include)["group_insets"]

    def without_policy(self, font, label, detail, gap=24, padding=24, profile=None):
        profile = dict(profile or {})
        profile["group_insets"] = {key: value for key, value in
                                  profile.get("group_insets", {}).items() if key not in opted}
        init(self, font, label, detail, gap, padding, profile)

    def with_policy(self, font, label, detail, gap=24, padding=24, profile=None):
        profile = dict(profile or {})
        profile["group_insets"] = {**profile.get("group_insets", {}), **opted}
        init(self, font, label, detail, gap, padding, profile)

    with patch.object(compiler.Layout, "__init__", without_policy):
        old = build()
    assert any(i["code"] == "boundary-stroke-clearance"
               for i in check_corpus_clearance(old, include))
    with patch.object(compiler.Layout, "__init__", with_policy):
        new = build()
    assert check_corpus_clearance(new, include) == []
    assert identity(old) == identity(new)
    assert compiler.check_layout(new) == []
    assert compiler.semantic_check(new, figure) == []
    assert compiler.visible_text_coverage(new, original) == []


def test_compiler_integration_applies_policy_before_measure_to_all_catalog_sources():
    # Strict RED until parent integration. check=True and report=None forbid
    # author writes; all selected layouts are inspected before SVG generation.
    checked = []
    failures = []
    current = [None]
    manual = compiler.manual_relation_fixes
    render = compiler.svg_document
    typography = json.loads((ROOT / "kkamji_scripts/blog/static_png/fhd-font-budgets.json").read_text())["sources"]

    def observe_manual(layout, figure, include):
        current[0] = include
        return manual(layout, figure, include)

    def observe_svg(layout, figure, source_hash, instance=""):
        include = current[0]
        assert isinstance(include, str)
        checked.append(include)
        expected = corpus_clearance_profile(include).get("group_insets", {})
        actual = layout.profile.get("group_insets", {})
        if any(actual.get(key, 0) < inset for key, inset in expected.items()):
            failures.append((include, "profile-not-applied-before-measure"))
        for issue in check_corpus_clearance(layout, include):
            failures.append((include, issue))
        base = {**compiler.FIXED_LAYOUT_PROFILES.get(include, {}),
                **typography.get(include, {})} if expected else {}
        # The changed builders must retain their unrelated fixed and
        # typography knobs; unrelated custom layouts own separate profiles.
        for name, value in base.items():
            if layout.profile.get(name) != value:
                failures.append((include, "fixed-profile-knob-lost", name))
        original = compiler.source_fragment((ROOT / "_includes" / include).read_text())
        for issue in (compiler.check_layout(layout)
                      + compiler.semantic_check(layout, figure)
                      + compiler.visible_text_coverage(layout, original)):
            failures.append((include, issue))
        return render(layout, figure, source_hash, instance)

    with patch.object(compiler, "manual_relation_fixes", observe_manual), \
         patch.object(compiler, "svg_document", observe_svg), \
         patch.object(Path, "write_text", side_effect=AssertionError("check mode wrote a file")):
        compiler.author(ROOT, check=True, report=None)
    expected_sources = [row['include'] for row in json.loads((ROOT / 'docs/diagram-catalog.json').read_text())['diagrams']]
    assert checked == expected_sources
    assert len(checked) == len(set(checked)) == len(expected_sources)
    assert not failures, failures[:15]
