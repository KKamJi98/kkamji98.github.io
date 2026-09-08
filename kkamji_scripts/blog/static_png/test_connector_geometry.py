import copy
import unittest

from connector_geometry import classify


class ConnectorGeometryTests(unittest.TestCase):
    def svg_case(self):
        common = dict(
            cls="",
            parent="",
            text=[],
            known=False,
            svg=True,
            style={"borders": [{"width": 0}] * 4},
            box={"x": 0, "y": 0, "w": 12, "h": 22},
        )
        root = dict(
            common,
            id="svg",
            tag="svg",
            svgData={"path": None, "strokeWidth": None, "dasharray": None},
        )
        path = dict(
            common,
            id="path",
            tag="path",
            svgData={"path": "M6 1v20", "strokeWidth": "2", "dasharray": "3 3"},
        )
        return {
            "figure": "sd-blockchain-operator-health-ladder",
            "elements": [root, path],
        }

    def test_svg_exception_requires_exact_reviewed_path(self):
        changed = self.svg_case()
        changed["elements"][1]["svgData"]["path"] = "M0 0h100"
        classify(changed)
        self.assertTrue(changed["unresolved"])

    def test_reviewed_dashed_marker_is_retained(self):
        reviewed = self.svg_case()
        classify(reviewed)
        self.assertEqual(reviewed["unresolved"], [])

    def test_renderer_code_change_invalidates_build_snapshot(self):
        import json
        from pathlib import Path
        import tempfile
        from downloads import source_snapshot

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/diagram-downloads.json").write_text(
                json.dumps({"entries": []})
            )
            helper = root / "kkamji_scripts/blog/static_png/connector_geometry.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("original renderer\n")
            before = source_snapshot(root)
            helper.write_text("changed renderer\n")
            self.assertNotEqual(before, source_snapshot(root))

    def test_collect_does_not_mutate_canonical_html(self):
        from playwright.sync_api import sync_playwright
        from connector_audit import collect_geometry

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.set_content(
                """<style>.sd-arrow{width:24px;height:24px}.sd-arrow::after{content:"";display:block;width:8px;height:8px;border-right:2px solid teal;border-bottom:2px solid teal;transform:rotate(45deg)}</style><figure class="sd" id="fixture"><div class="sd-arrow"></div></figure>"""
            )
            before = page.locator("#fixture").evaluate("e=>e.outerHTML")
            geometry = collect_geometry(page, "#fixture")
            self.assertTrue(geometry["elements"])
            self.assertEqual(
                before, page.locator("#fixture").evaluate("e=>e.outerHTML")
            )
            self.assertEqual(page.locator("[data-audit-id]").count(), 0)
            browser.close()


if __name__ == "__main__":
    unittest.main()
