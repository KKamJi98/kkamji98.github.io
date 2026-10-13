"""Negative acceptance tests for preserved source and native FHD geometry."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from downloads import output_paths, viewer_url
from fhd_export import png_dimensions, unused_png
from fhd_release import unused_outputs
from fhd_svg import (
    FONT,
    Font,
    Layout,
    Parse,
    banner_layout,
    check_layout,
    ci_branch_layout,
    complete_group_boundaries,
    jev_layout,
    pod_identity_layout,
    ray_hits_box,
    segment_crosses_text,
    semantic_check,
    source_fragment,
    svg_document,
    visible_text_coverage,
)


class FHDSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[3]
        cls.font = Font(cls.root / FONT)

    def drawing(self):
        source = '<figure class="sd"><figcaption class="sd-title">조건부 배포</figcaption><div class="sd-flow"><div class="sd-node"><strong class="sd-label">검증</strong><span>실패 시 중지</span></div><span class="sd-arrow">성공 시</span><div class="sd-node"><strong class="sd-label">배포</strong><span>승인된 변경만 적용</span></div></div></figure>'
        figure = next(e for e in Parse(source).root.descendants() if e.tag == "figure")
        layout = Layout(self.font, 28, 22)
        layout.draw(figure, 64, 200, 1792)
        layout.resolve_boundary_edges(figure)
        self.assertEqual(check_layout(layout), [])
        self.assertEqual(semantic_check(layout, figure), [])
        return figure, layout

    def test_removing_condition_is_a_semantic_failure(self):
        figure, layout = self.drawing()
        layout.texts = [t for t in layout.texts if t["text"] != "실패 시 중지"]
        self.assertTrue(
            any(
                r["code"] == "source-text-mismatch"
                for r in semantic_check(layout, figure)
            )
        )

    def test_wrapping_prefers_complete_words_over_filling_a_short_line(self):
        self.assertEqual(
            self.font.wrap("LLM generation", 162, 28), ["LLM", "generation"]
        )
        lines = self.font.wrap("shortlist만 cross-encoder로 함께 읽고 재채점", 202, 22)
        self.assertTrue(any("cross-encoder" in line for line in lines))
        self.assertFalse(any("cross-enc" == line[-9:] for line in lines))

    def test_removing_painted_edge_is_a_semantic_failure(self):
        figure, layout = self.drawing()
        layout.connectors.clear()
        self.assertTrue(
            any(
                r["code"] == "missing-source-edge"
                for r in semantic_check(layout, figure)
            )
        )

    def test_route_across_unrelated_node_is_rejected(self):
        _, layout = self.drawing()
        box = layout.boxes[0]
        layout.connectors.append(
            {
                "source": "bad",
                "from": ["other"],
                "to": ["other"],
                "points": [
                    [box["x"] - 10, box["y"] + 30],
                    [box["x"] + box["width"] + 10, box["y"] + 30],
                ],
            }
        )
        self.assertTrue(
            any(
                r["code"] == "connector-crosses-other-node"
                for r in check_layout(layout)
            )
        )

    def test_connector_through_its_own_caption_is_rejected(self):
        _, layout = self.drawing()
        caption = next(
            t for t in layout.texts if t["source"] == layout.connectors[0]["source"]
        )
        edge = layout.connectors[0]
        edge["points"] = [
            [caption["x"] - 8, caption["y"] - 4],
            [caption["x"] + caption["width"] + 8, caption["y"] - 4],
        ]
        self.assertTrue(
            any(r["code"] == "connector-crosses-text" for r in check_layout(layout))
        )

    def test_diagonal_text_crossings_are_checked_as_finite_segments(self):
        text = {"x": 100, "y": 120, "width": 80, "size": 20}
        self.assertTrue(segment_crosses_text([90, 90], [190, 130], text))
        self.assertTrue(segment_crosses_text([90, 110], [190, 110], text))
        self.assertTrue(segment_crosses_text([140, 80], [140, 140], text))
        self.assertFalse(segment_crosses_text([10, 10], [90, 90], text))
        self.assertFalse(segment_crosses_text([90, 80], [190, 80], text))

    def test_short_product_and_api_words_cannot_be_split_inside(self):
        for word in ("Spectrum", "Consumer", "connector", "resource"):
            with self.subTest(word=word):
                source = (
                    '<figure class="sd"><div class="sd-node">'
                    + word
                    + "</div></figure>"
                )
                figure = next(
                    e for e in Parse(source).root.descendants() if e.tag == "figure"
                )
                layout = Layout(self.font, 28, 22)
                layout.draw(figure, 64, 200, 1792)
                text = layout.texts[0]
                text["text"] = word[:-1]
                layout.texts.append(dict(text, text=word[-1], y=text["y"] + 30))
                self.assertTrue(
                    any(
                        r["code"] == "source-identifier-split"
                        for r in semantic_check(layout, figure)
                    )
                )

    def test_detached_or_mismatched_pod_credentials_legend_is_rejected(self):
        original = source_fragment(
            (
                self.root
                / "_includes/diagrams/static/kubernetes/pod-identity-workflow.html"
            ).read_text()
        )
        figure = next(
            e for e in Parse(original).root.descendants() if e.tag == "figure"
        )
        layout = pod_identity_layout(self.font, figure)
        self.assertEqual(semantic_check(layout, figure), [])
        marker = next(
            t for t in layout.texts if t["source"] == "root.0.2.1.2.0.1.1.meaning"
        )
        marker["text"] = "B"
        self.assertTrue(
            any(
                r["code"] == "legend-edge-mapping-mismatch"
                for r in semantic_check(layout, figure)
            )
        )
        marker["text"] = "A"
        marker["y"] = 100
        self.assertTrue(
            any(
                r["code"] == "legend-edge-mapping-mismatch"
                for r in semantic_check(layout, figure)
            )
        )

    def test_overlapping_text_and_clipped_text_are_rejected(self):
        _, layout = self.drawing()
        layout.texts.append(dict(layout.texts[0], source="duplicate"))
        self.assertTrue(any(r["code"] == "text-overlap" for r in check_layout(layout)))
        layout.texts[0]["x"] = 1910
        self.assertTrue(
            any(r["code"] == "text-outside-canvas" for r in check_layout(layout))
        )

    def test_semantic_fragment_remains_exact_for_complex_and_icon_sources(self):
        for name in [
            "diagrams/static/ai/rag-04-hybrid-rerank.html",
            "diagrams/aws-certification-map.html",
            "diagrams/static/kubernetes/pod-identity-workflow.html",
        ]:
            raw = (self.root / "_includes" / name).read_text()
            restored = source_fragment(raw)
            self.assertNotIn("sd-fhd-artwork", restored)
            self.assertIn("<figure", restored)
            self.assertIn("</figure>", restored)
            self.assertEqual(source_fragment(restored), restored)

    def test_relation_group_endpoints_have_a_painted_common_boundary(self):
        candidates = list((self.root / "_includes/diagrams").rglob("*gcp*org*.html"))
        self.assertTrue(candidates)
        raw = source_fragment(candidates[0].read_text())
        figure = next(e for e in Parse(raw).root.descendants() if e.tag == "figure")
        layout = Layout(self.font, 20, 18, 16, 16)
        layout.draw(figure, 64, 100, 1792)
        layout.resolve_boundary_edges(figure)
        complete_group_boundaries(layout)
        painted = {item["source"] for item in layout.boxes + layout.groups}
        for edge in layout.connectors:
            for key in edge.get("from", []) + edge.get("to", []):
                self.assertIn(key, painted)

    def test_workflow_branches_to_both_jobs_and_joins_both_results(self):
        raw = source_fragment(
            (
                self.root
                / "_includes/diagrams/static/ci-cd/github-actions-workflow-flow.html"
            ).read_text()
        )
        figure = next(e for e in Parse(raw).root.descendants() if e.tag == "figure")
        layout = ci_branch_layout(self.font, figure, workflow=True)
        self.assertEqual(semantic_check(layout, figure), [])
        self.assertEqual(check_layout(layout), [])
        forks = [
            edge for edge in layout.connectors if edge.get("origin") == "root.0.1.3"
        ]
        joins = [
            edge for edge in layout.connectors if edge.get("origin") == "root.0.1.5"
        ]
        self.assertEqual(len(forks), 2)
        self.assertEqual(len(joins), 2)
        self.assertNotEqual(forks[0]["to"], forks[1]["to"])
        self.assertNotEqual(joins[0]["from"], joins[1]["from"])
        self.assertEqual(joins[0]["to"], joins[1]["to"])

    def test_independent_visible_text_check_retains_inline_negation_and_punctuation(
        self,
    ):
        original = '<figure class="sd"><span class="sd-detail"><strong class="sd-label">출력</strong><br><code>noul = yes probability</code><br>별도 <code>confidence</code> 없음</span></figure>'
        figure = next(
            e for e in Parse(original).root.descendants() if e.tag == "figure"
        )
        layout = Layout(self.font, 28, 22)
        layout.draw(figure, 64, 200, 1792)
        self.assertEqual(visible_text_coverage(layout, original), [])
        layout.texts = [t for t in layout.texts if "없음" not in t["text"]]
        self.assertTrue(visible_text_coverage(layout, original))

    def test_jev_preserves_typed_input_transfer_and_two_policy_outcomes(self):
        original = source_fragment(
            (
                self.root / "_includes/diagrams/static/ai/jev-decision-pipeline.html"
            ).read_text()
        )
        figure = next(
            e for e in Parse(original).root.descendants() if e.tag == "figure"
        )
        layout = jev_layout(self.font, figure)
        self.assertEqual(visible_text_coverage(layout, original), [])
        self.assertEqual(len(layout.connectors), 4)
        forks = [e for e in layout.connectors if e.get("origin") == "root.0.0.2.2"]
        self.assertEqual(len(forks), 2)
        self.assertNotEqual(forks[0]["to"], forks[1]["to"])

    def test_named_reference_note_keeps_dashed_paint(self):
        original = '<figure class="sd"><div class="sd-note sd-reference" data-connector-role="reference-note" data-from="shutdown" data-to="socket">shutdown to socket: stop accepting</div></figure>'
        figure = next(
            e for e in Parse(original).root.descendants() if e.tag == "figure"
        )
        layout = Layout(self.font, 28, 22)
        layout.draw(figure, 64, 200, 1792)
        svg = svg_document(layout, figure, "test")
        self.assertIn('stroke-dasharray="10 8"', svg)
        self.assertIn('data-connector-role="reference-note"', svg)
        self.assertIn('data-from="shutdown" data-to="socket"', svg)

    def test_native_refresh_preserves_former_body_cover_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            png = "/assets/img/diagrams/banner--0123456789abcdef.png"
            (root / "docs/diagram-export-release.json").write_text(
                json.dumps(
                    {
                        "entries": [{"include": "diagrams/banner.html", "png": png}],
                        "unused_entries": [],
                    }
                )
            )
            self.assertEqual(
                unused_outputs(root, {"unused_includes": ["diagrams/banner.html"]}),
                [("diagrams/banner.html", png)],
            )
            self.assertEqual(
                unused_outputs(root, {"unused_includes": ["diagrams/new.html"]}),
                [("diagrams/new.html", unused_png("diagrams/new.html"))],
            )

    def test_jev_quality_gate_rejects_group_and_title_misalignment(self):
        original = source_fragment(
            (
                self.root / "_includes/diagrams/static/ai/jev-decision-pipeline.html"
            ).read_text()
        )
        figure = next(
            e for e in Parse(original).root.descendants() if e.tag == "figure"
        )
        layout = jev_layout(self.font, figure)
        self.assertEqual(check_layout(layout), [])
        layout.groups[0]["y"] += 48
        self.assertIn(
            "jev-card-alignment", [issue["code"] for issue in check_layout(layout)]
        )
        layout.groups[0]["y"] -= 48
        next(t for t in layout.texts if t["source"] == "root.0.0.0.2" and t["label"])[
            "y"
        ] += 8
        self.assertIn(
            "jev-title-alignment", [issue["code"] for issue in check_layout(layout)]
        )

    def test_jev_keeps_neon_accent_and_measured_policy_details(self):
        original = source_fragment(
            (
                self.root / "_includes/diagrams/static/ai/jev-decision-pipeline.html"
            ).read_text()
        )
        figure = next(
            e for e in Parse(original).root.descendants() if e.tag == "figure"
        )
        layout = jev_layout(self.font, figure)
        self.assertEqual(semantic_check(layout, figure), [])
        self.assertEqual(visible_text_coverage(layout, original), [])
        svg = svg_document(layout, figure, "test")
        self.assertIn('stop-color="#6e77ff"', svg)
        self.assertIn('stop-color="#2ed6b8"', svg)
        self.assertIn('stroke="url(#jev-neon)"', svg)
        layout.texts = [
            t for t in layout.texts if t["text"] != "blast_radius.confidence < 0.90"
        ]
        self.assertTrue(semantic_check(layout, figure))

    def test_named_source_metadata_does_not_certify_a_disconnected_reference(self):
        original = '<figure class="sd"><div class="sd-node" id="a">Named source</div><div class="sd-arrow" data-connector-role="reference" data-from="a" data-to="b">Remote request</div><div class="sd-node" id="b">Named destination</div></figure>'
        figure = next(
            e for e in Parse(original).root.descendants() if e.tag == "figure"
        )
        layout = Layout(self.font, 28, 22)
        layout.draw(figure, 64, 200, 1792)
        layout.resolve_boundary_edges(figure)
        a, b = layout.boxes
        x = a["x"] + a["width"] / 2
        layout.connectors[0]["points"] = [
            [x, a["y"] + a["height"] + 40],
            [x, b["y"] - 12],
        ]
        self.assertTrue(
            any(
                e["code"] == "named-endpoint-disconnected"
                for e in semantic_check(layout, figure)
            )
        )
        layout.connectors[0]["points"] = [
            [x, a["y"] + a["height"] + 12],
            [x, b["y"] - 12],
        ]
        self.assertEqual(semantic_check(layout, figure), [])

    def test_banner_preserves_word_boundaries_and_four_column_relationships(self):
        original = source_fragment(
            (
                self.root / "_includes/diagrams/static/ai/jev-system-one-banner.html"
            ).read_text()
        )
        figure = next(
            e for e in Parse(original).root.descendants() if e.tag == "figure"
        )
        layout = banner_layout(self.font, figure)
        complete_group_boundaries(layout)
        self.assertEqual(semantic_check(layout, figure), [])
        self.assertEqual(visible_text_coverage(layout, original), [])
        self.assertEqual(check_layout(layout), [])
        painted = [t["text"] for t in layout.texts]
        for original_line in [
            "Tool call + context",
            "command, scope, intent",
            "validated facts",
            "Policy",
            "execute",
            "or escalate",
        ]:
            self.assertIn(original_line, painted)
        self.assertEqual(len(layout.connectors), 3)
        for edge in layout.connectors:
            self.assertLess(edge["points"][0][0], edge["points"][-1][0])
            self.assertEqual(edge["points"][0][1], edge["points"][-1][1])

    def test_near_named_port_rejects_a_target_arrow_pointing_down_or_away(self):
        vault = {"x": 74, "y": 568, "width": 570, "height": 72}
        port = [656, 604]
        self.assertTrue(ray_hits_box(port, [-1, 0], vault))
        self.assertFalse(ray_hits_box(port, [0, 1], vault))
        self.assertFalse(ray_hits_box(port, [1, 0], vault))

    def test_output_paths_and_viewer_keep_occurrence_identity(self):
        png = "/assets/img/diagrams/static/a/example--0123456789abcdef.png"
        self.assertEqual(
            viewer_url(png), "/diagrams/view/static/a/example--0123456789abcdef.html"
        )
        with self.assertRaises(ValueError):
            viewer_url("https://example.invalid/x.png")
        plan = {
            "entries": [{"png": png}],
            "unused_includes": ["diagrams/static/unused.html"],
        }
        self.assertEqual(
            output_paths(plan),
            {png.lstrip("/"), unused_png("diagrams/static/unused.html").lstrip("/")},
        )
        with self.assertRaises(ValueError):
            png_dimensions(b"not PNG")


if __name__ == "__main__":
    unittest.main()
