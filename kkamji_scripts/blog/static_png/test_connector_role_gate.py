import unittest
from playwright.sync_api import sync_playwright
from connector_audit import inspect_connectors


class ConnectorRoleGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def inspect(self, body, extra_css=""):
        page = self.browser.new_page()
        try:
            page.set_content(
                """<style>*{box-sizing:border-box}figure{width:400px;margin:0}.sd-node{padding:8px;border:1px solid gray}.sd-flow{display:grid;gap:12px;margin-bottom:8px}.sd-arrow{display:flex;flex-direction:column;align-items:center;gap:8px;min-height:36px;margin-block:8px}.sd-flow>.sd-arrow{margin:0}.sd-edge-label{font-size:14px;line-height:21px}.sd-arrow::after{content:"";display:block;width:8px;height:8px;border-bottom:2px solid teal;border-right:2px solid teal;transform:rotate(45deg)}"""
                + extra_css
                + '</style><figure class="sd" id="fixture">'
                + body
                + "</figure>"
            )
            return inspect_connectors(page, "#fixture")
        finally:
            page.close()

    def test_explicit_continuation_resolves_following_parent_group(self):
        result = self.inspect(
            """<div class="sd-flow"><div class="sd-node">Source</div><div class="sd-arrow" data-connector-role="continuation"><span class="sd-edge-label">Alternatives</span></div></div><div class="sd-grid"><div class="sd-node">Target A or B</div></div>"""
        )
        self.assertEqual(result["issues"], [])

    def test_named_reference_resolves_remote_source_without_fake_bus(self):
        result = self.inspect(
            """<div class="sd-node" id="source">Source</div><section><div class="sd-arrow" data-connector-role="reference" data-from="source" data-to="target"><span class="sd-edge-label">Source to Target</span></div><div class="sd-node" id="target">Target</div></section>"""
        )
        self.assertEqual(result["issues"], [])

    def test_reference_note_missing_target_is_not_silently_ignored(self):
        result = self.inspect(
            """<div class="sd-node" id="source">Source</div><div class="sd-note sd-reference" data-connector-role="reference-note" data-from="source" data-to="missing">Source / Target</div>"""
        )
        self.assertTrue(result["issues"])

    def test_hidden_marker_is_not_silently_dropped(self):
        result = self.inspect(
            '<div class="sd-node">Source</div><div class="sd-arrow"></div><div class="sd-node">Target</div>',
            ".sd-arrow{display:none}",
        )
        self.assertTrue(result["issues"])

    def test_unknown_role_is_not_silently_ignored(self):
        result = self.inspect(
            '<div class="sd-note" data-connector-role="unknown">Unknown relation</div>'
        )
        self.assertTrue(result["issues"])

    def test_reference_note_has_no_painted_arrowhead(self):
        body = """<div class="sd-node" id="source">Source</div><div class="sd-node" id="target">Target</div><div class="sd-note sd-reference" data-connector-role="reference-note" data-from="source" data-to="target">Source / Target</div>"""
        self.assertEqual(self.inspect(body)["issues"], [])
        bad = self.inspect(
            body,
            '.sd-reference::after{content:"";display:block;width:8px;height:8px;border-right:2px solid teal;border-bottom:2px solid teal;transform:rotate(45deg)}',
        )
        self.assertTrue(bad["issues"])


if __name__ == "__main__":
    unittest.main()
