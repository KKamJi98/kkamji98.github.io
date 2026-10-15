"""Source-scoped balance regressions; all authoring is read-only/in-memory.

The single compiler integration gate remains RED until Main merges the profile
before measurement and consumes center_partial_rows while drawing. The injected
policy tests prove static fit and semantic identities, not centered native pixels.
"""

import hashlib
import importlib.util
import json
import sys
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import astuple
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fhd_svg as compiler
from corpus_flow_balance import BALANCED_INCLUDES, REPAIRS, corpus_flow_balance_profile

ROOT = Path(__file__).resolve().parents[3]
LOOP = "diagrams/static/ai/loop-anatomy.html"
GCP = "diagrams/static/gcp/gcp-access-stack.html"
DNS = "diagrams/static/sap-c02/dns-global-traffic-decision-layers.html"


def test_five_stage_rail_opts_into_three_columns_and_centered_continuation():
    assert importlib.util.find_spec("corpus_flow_balance") is not None
    assert corpus_flow_balance_profile(LOOP) == {
        "flow_columns": {"root.0.1": 3},
        "center_partial_rows": ["root.0.1"],
    }


def test_repair_scope_source_keys_labels_and_evidence_are_frozen():
    pairs = [(r.include, r.container) for r in REPAIRS]
    assert len(pairs) == len(set(pairs)) == 53
    assert len(BALANCED_INCLUDES) == 52
    assert tuple(dict.fromkeys(r.include for r in REPAIRS)) == BALANCED_INCLUDES
    serialized = json.dumps([astuple(r) for r in REPAIRS], separators=(",", ":"))
    assert hashlib.sha256(serialized.encode()).hexdigest() == (
        "f402a47dbb2ade0d68c97b9e352c04e4aa4a2bc23ff6f18dc3123e8fcaec7610"
    )


@pytest.mark.parametrize("include", (LOOP, GCP, DNS))
def test_profiles_are_copy_isolated_and_do_not_change_fonts_or_other_layout_knobs(include):
    original = corpus_flow_balance_profile(include)
    modified = corpus_flow_balance_profile(include)
    assert set(original) <= {"flow_columns", "columns", "center_partial_rows"}
    for value in modified.values():
        if isinstance(value, dict):
            value["root.fake"] = 99
        else:
            value.append("root.fake")
    assert corpus_flow_balance_profile(include) == original


@pytest.mark.parametrize("include", (
    "not-in-catalog.html",
    "_includes/" + LOOP,
    LOOP.replace(".html", ".svg"),
    "diagrams/static/ai/graph-system-intelligence.html",
    "diagrams/static/ai/agentic-development-workspace.html",
    "diagrams/static/ai/jev-decision-pipeline.html",
    "diagrams/static/kubernetes/pod-identity-workflow.html",
    "diagrams/static/aws/analytics-stack-06-catalog-federation.html",
    "diagrams/static/gcp/gcp-org-tree.html",
    "diagrams/static/blockchain/commitment-tag-compare.html",
))
def test_unreviewed_sources_and_main_owned_meaning_repairs_are_not_selected(include):
    assert corpus_flow_balance_profile(include) == {}


@pytest.fixture(scope="module")
def font():
    return compiler.Font(ROOT / compiler.FONT)


def source(include):
    original = compiler.source_fragment((ROOT / "_includes" / include).read_text())
    figure = next(e for e in compiler.Parse(original).root.descendants()
                  if e.tag == "figure" and "sd" in e.classes)
    return original, figure


@pytest.mark.parametrize("repair", REPAIRS, ids=lambda r: r.include + ":" + r.container)
def test_frozen_targets_are_literal_ordered_rails_or_independent_peer_grids(font, repair):
    _, figure = source(repair.include)
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    layout = compiler.Layout(font, 28, 22)
    container = elements[repair.container]
    assert layout.kind(container) == "group"
    children = layout.items(container)
    atoms = [e for e in children if layout.kind(e) != "edge"]
    edges = [e for e in children if layout.kind(e) == "edge"]
    assert tuple(e.key for e in atoms) == repair.cards
    assert tuple((e.key, e.text()) for e in edges) == repair.edges
    labels = tuple(next((h.text() for h in e.children if h.classes & compiler.HEAD_CLASSES),
                        e.text()) for e in atoms)
    assert labels == repair.card_labels
    assert repair.evidence_ref[0] in {
        "untouched-source-triage-0.json", "untouched-source-triage-1.json",
        "candidate-all-findings-round1.json",
    }
    if repair.mode == "flow":
        assert container.classes & {"sd-flow", "sd-stack", "sd-v2-rail"}
        assert len(edges) == len(atoms) - 1
        assert [layout.kind(e) == "edge" for e in children] == [
            bool(i % 2) for i in range(len(children))
        ]
        assert repair.columns in (0, 3)
    else:
        assert repair.mode == "grid"
        assert container.classes & {"sd-grid", "sd-v2-compare", "sd-v2-fork"}
        assert edges == []  # Inner local relations remain local, never peer chains.
        assert (len(atoms), repair.columns) in ((4, 2), (3, 3))


def merge_profile(base, include):
    """Test-only pre-measure injection; keep every compiler-owned profile knob."""
    merged = dict(base)
    for key, value in corpus_flow_balance_profile(include).items():
        if isinstance(value, dict):
            merged[key] = {**merged.get(key, {}), **value}
        else:
            merged[key] = list(dict.fromkeys([*merged.get(key, []), *value]))
    return merged


def author_in_memory(include, inject, baseline=False):
    """Exercise real author(), its density selection, fixes and semantic gates."""
    real_read = Path.read_text
    catalog = json.loads(real_read(ROOT / "docs/diagram-catalog.json"))
    records = [r for r in catalog["diagrams"] if r["include"] == include]
    assert len(records) == 1
    captured = []
    reports = []
    report_path = ROOT / "virtual-flow-balance-report.json"
    original_init = compiler.Layout.__init__
    original_measure = compiler.Layout.measure
    real_fixes = compiler.manual_relation_fixes
    real_relations = compiler.repair_relations

    def read(path, *args, **kwargs):
        if path == ROOT / "docs/diagram-catalog.json":
            return json.dumps({**catalog, "diagrams": records})
        return real_read(path, *args, **kwargs)

    def init(self, font, label, detail, gap=24, padding=24, profile=None):
        before = deepcopy(profile or {})
        for key, value in compiler.scoped_profile(include).items():
            before[key] = {**before.get(key, {}), **value}
        candidate = merge_profile(before, include) if inject else before
        original_init(self, font, label, detail, gap, padding, candidate)
        self._flow_balance_input_profile = before

    def measure(self, element, width):
        if not hasattr(self, "_flow_balance_first_measure_profile"):
            self._flow_balance_first_measure_profile = deepcopy(self.profile)
        return original_measure(self, element, width)

    def fixes(layout, figure, actual_include):
        real_fixes(layout, figure, actual_include)
        captured.append(layout)

    def relations(layout, figure, actual_include):
        if baseline and actual_include == DNS:
            return layout
        return real_relations(layout, figure, actual_include)

    def capture_report(path, content, *args, **kwargs):
        assert path == report_path, "source/artwork write in read-only author probe"
        reports.append(json.loads(content))
        return len(content)

    without_policy = (
        patch.object(compiler, "corpus_flow_balance_profile", lambda _: {}, create=True)
        if baseline else nullcontext()
    )
    with patch.object(Path, "read_text", read), \
         patch.object(compiler.Layout, "__init__", init), \
         patch.object(compiler.Layout, "measure", measure), \
         patch.object(compiler, "manual_relation_fixes", fixes), \
         patch.object(compiler, "repair_relations", relations), \
         patch.object(Path, "mkdir", return_value=None), \
         patch.object(Path, "write_text", capture_report), without_policy:
        compiler.author(ROOT, check=True, report=report_path)
    assert len(reports) == 1
    payload = reports[0]
    assert len(payload["entries"]) == 1
    result = payload["entries"][0]
    assert "issues" in result, result  # Cannot-fit has no selected layout or issues.
    assert len(captured) == 1, result
    return result, captured[0]


def topology(layout):
    return (
        sorted(b["source"] for b in layout.boxes),
        sorted((e["source"], e.get("origin", ""), tuple(e.get("from", [])),
                tuple(e.get("to", [])), e.get("label", "")) for e in layout.connectors),
        sorted((i["source"], i.get("href", "")) for i in layout.images),
    )


@pytest.mark.parametrize("include", BALANCED_INCLUDES)
def test_pre_measure_policy_fits_without_static_errors_semantic_drift_or_font_shrink(include):
    path = ROOT / "_includes" / include
    before = path.read_bytes()
    baseline_result, baseline = author_in_memory(include, inject=False, baseline=True)
    result, candidate = author_in_memory(include, inject=True)
    assert path.read_bytes() == before
    assert baseline_result["issues"] == []
    assert result["issues"] == []
    assert topology(candidate) == topology(baseline)
    assert candidate.label_size >= baseline.label_size
    assert candidate.detail_size >= baseline.detail_size
    for key, value in candidate._flow_balance_input_profile.items():
        if key in {"columns", "flow_columns", "center_partial_rows"}:
            continue
        assert candidate.profile[key] == value  # Includes phase/font/budget knobs.
    for key, value in compiler.FIXED_LAYOUT_PROFILES.get(include, {}).items():
        for source_key, declaration in value.items() if isinstance(value, dict) else []:
            assert candidate.profile[key][source_key] == declaration
    assert candidate.label_size >= 16 and candidate.detail_size >= 14


def test_four_peer_and_three_peer_comparisons_have_balanced_track_counts():
    assert corpus_flow_balance_profile(GCP) == {"columns": {"root.0.1.1": 2}}
    assert corpus_flow_balance_profile(
        "diagrams/static/sap-c02/deployment-rollback-paths.html"
    ) == {"columns": {"root.0.1": 2}}
    assert corpus_flow_balance_profile(DNS) == {"columns": {"root.0.2": 3}}


def test_merge_keeps_unrelated_columns_phase_flows_fonts_and_group_insets():
    base = {
        "columns": {"root.keep": 1}, "flow_columns": {"root.other": 4},
        "phase_flows": {"root.phase": 3}, "group_insets": {"root.group": 24},
        "regular_width_budget": 1.25, "center_partial_rows": ["root.keep"],
    }
    result = merge_profile(merge_profile(base, GCP), LOOP)
    assert result["columns"] == {"root.keep": 1, "root.0.1.1": 2}
    assert result["flow_columns"] == {"root.other": 4, "root.0.1": 3}
    assert result["center_partial_rows"] == ["root.keep", "root.0.1"]
    for key in ("phase_flows", "group_insets", "regular_width_budget"):
        assert result[key] == base[key]
    assert base["columns"] == {"root.keep": 1}


def test_compiler_integration_merges_before_measure_and_centers_named_partial_rows():
    """One deliberate RED gate until Main integrates both profile and drawing."""
    for include in BALANCED_INCLUDES:
        result, layout = author_in_memory(include, inject=False)
        measured_profile = layout._flow_balance_first_measure_profile
        for key, value in corpus_flow_balance_profile(include).items():
            if isinstance(value, dict):
                for source_key, declaration in value.items():
                    assert measured_profile.get(key, {}).get(source_key) == declaration, (
                        "compiler must merge before measure", include, key, source_key
                    )
            else:
                assert set(value) <= set(measured_profile.get(key, [])), (
                    "compiler must consume exact centering opt-ins", include
                )
        assert result["issues"] == []
        boxes = {b["source"]: b for b in layout.boxes}
        boxes.update(layout.group_bounds)
        for repair in (r for r in REPAIRS if r.include == include and r.center_partial_rows):
            container = boxes[repair.container]
            rows = {}
            for key in repair.cards:
                box = boxes[key]
                cy = round(box["y"] + box["height"] / 2, 6)
                rows.setdefault(cy, []).append(box)
            # Literal row tracks align participant centers; intact nested children
            # are never treated as additional peer cards or flattened stages.
            widest = max(len(row) for row in rows.values())
            for row in rows.values():
                if len(row) >= widest:
                    continue
                left = min(b["x"] for b in row)
                right = max(b["x"] + b["width"] for b in row)
                assert abs((left + right) / 2 - (container["x"] + container["width"] / 2)) < 0.01, (
                    "partial continuation must be centered", include, repair.container
                )
