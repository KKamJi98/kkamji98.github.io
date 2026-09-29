import copy
import unittest

from connector_geometry import classify


def jev_case() -> dict:
    """Reviewed 625px topology expressed as captured CSS boxes and CDP quads."""
    def box(x, y, w, h):
        return dict(x=x, y=y, w=w, h=h)

    bounds = {
        "inputs": box(0, 0, 196, 68),
        "input": box(94, 72, 8, 16),
        "judge": box(0, 92, 196, 74),
        "transferLabel": box(196, 100, 64, 20),
        "transfer": box(202, 128, 52, 2),
        "policy": box(260, 48, 333, 225),
        "policyLabel": box(273, 60, 307, 22),
        "authority": box(273, 91, 307, 74),
        "fork": box(273, 165, 307, 28),
        "stem": box(425.5, 169, 2, 10),
        "bus": box(346.75, 177, 159.5, 2),
        "shadowDrop": box(342.75, 177, 8, 12),
        "escalateDrop": box(502.25, 177, 8, 12),
        "shadow": box(273, 193, 147.5, 68),
        "escalate": box(432.5, 193, 147.5, 68),
    }
    labels = {
        "inputs": "State Typed Questions", "judge": "Jev 실행 권한 없음",
        "transferLabel": "typed answers", "policyLabel": "실행 권한 판단",
        "authority": "Deterministic Policy 코드와 정책이 결정",
        "shadow": "Shadow 실행 없이 비교", "escalate": "Escalate 사람 / 상위 제어",
    }
    anchors = {name: dict(count=1, hidden=False, box=rect, label=labels.get(name, ""))
               for name, rect in bounds.items()}
    classes = {
        "input": "sd-jev-input-link", "transfer": "sd-jev-transfer-line",
        "stem": "sd-jev-fork-stem", "bus": "sd-jev-fork-bus",
        "shadowDrop": "sd-jev-fork-drop sd-jev-fork-drop--shadow",
        "escalateDrop": "sd-jev-fork-drop sd-jev-fork-drop--escalate",
    }
    gradient = "linear-gradient(rgb(51, 65, 85), rgb(51, 65, 85))"
    elements: list[dict] = []
    for name, cls in classes.items():
        rect = bounds[name]
        style = dict(color="rgb(51, 65, 85)", background="none", borders=[])
        if name in ("input", "shadowDrop", "escalateDrop"):
            style.update(background=gradient, backgroundSize="2px 100%",
                         backgroundPosition="50% 50%", backgroundRepeat="no-repeat")
        element = dict(id="jev:" + name, cls=cls, parent="sd-jev-fork",
                       known=True, svg=False, hidden=False, box=rect,
                       style=style, text=[], pseudos=[])
        if name in ("input", "transfer", "shadowDrop", "escalateDrop"):
            horizontal = name == "transfer"
            borders = [dict(width=0, color="rgba(0, 0, 0, 0)", style="none") for _ in range(4)]
            borders[3 if horizontal else 0] = dict(width=6, color="rgb(51, 65, 85)", style="solid")
            for side in ((0, 2) if horizontal else (1, 3)):
                borders[side] = dict(width=4, color="rgba(0, 0, 0, 0)", style="solid")
            if horizontal:
                head = box(rect["x"] + rect["w"] - 6, rect["y"] - 3, 6, 8)
            else:
                head = box(rect["x"], rect["y"] + rect["h"] - 6, 8, 6)
            x, y, w, h = head.values()
            element["after"] = dict(content='""', display="block", visibility="visible",
                                    opacity=1, borders=borders)
            element["pseudos"] = [dict(type="after", quad=[x, y, x+w, y, x+w, y+h, x, y+h])]
        elements.append(element)
    return dict(figure="jev-decision-pipeline", elements=elements, jev=anchors)


def landscape_case(figure="sd-ethereum-account-fields") -> dict:
    """625px landscape row represented by captured computed styles and quads."""
    def box(x, y, w, h):
        return dict(x=x, y=y, w=w, h=h)

    cards = [box(16, 16, 133, 156), box(245, 16, 133, 156), box(474, 16, 135, 156)]
    row = []
    elements = []
    indices = [3, 6, 8, 11, 13]  # figure, caption and flow precede the direct children
    for i in range(5):
        arrow = i in (1, 3)
        rect = box(149 if i == 1 else 378, 16, 96, 156) if arrow else cards[i // 2]
        row.append(dict(cls="sd-arrow" if arrow else "sd-node", index=indices[i],
                        hidden=False, box=rect))
        if not arrow:
            continue
        mid = rect["x"] + 48
        # 10.4px border box after a -45 degree rotation, centered 23.2px right of mid.
        head = box(mid + 23.2 - 7.354, 94 - 7.354, 14.708, 14.708)
        x, y, w, h = head.values()
        borders = [dict(width=0, style="none", color="rgba(0, 0, 0, 0)"),
                   dict(width=2, style="solid", color="rgb(51, 65, 85)"),
                   dict(width=2, style="solid", color="rgb(51, 65, 85)"),
                   dict(width=0, style="none", color="rgba(0, 0, 0, 0)")]
        elements.append(dict(
            id=f"{figure}:{indices[i]}", cls="sd-arrow", parent="sd-flow sd-flow--linear-landscape",
            known=True, hidden=False, svg=False, box=rect, role="", prev=dict(cls="sd-node", box=cards[i // 2], text=[]),
            next=dict(cls="sd-node", box=cards[i // 2 + 1], text=[]),
            text=[box(rect["x"] + 24, 40, 48, 20)],
            style=dict(background="linear-gradient(rgb(51, 65, 85), rgb(51, 65, 85))",
                       backgroundSize="48px 2px", backgroundPosition="50% 50%",
                       backgroundRepeat="no-repeat", borders=[]),
            after=dict(content='""', display="block", visibility="visible", opacity=1,
                       color="rgba(0, 0, 0, 0)",
                       transform="matrix(0.707107, -0.707107, 0.707107, 0.707107, 0, 0)",
                       borders=borders),
            pseudos=[dict(type="after", quad=[x, y, x+w, y, x+w, y+h, x, y+h],
                          innerQuad=[x, y, x+w, y, x+w, y+h, x, y+h])],
        ))
    return dict(figure=figure, landscape=[row], elements=elements)


class ConnectorGeometryTests(unittest.TestCase):
    def test_landscape_two_opted_in_rows_are_retained(self):
        for figure in ("sd-ethereum-account-fields", "jib-build-workflow"):
            with self.subTest(figure=figure):
                sample = landscape_case(figure)
                classify(sample)
                self.assertEqual(sample["status"], "retained", sample)
                self.assertEqual(sample["connectorCount"], 2)
                self.assertEqual(sample["findings"], [])
                self.assertEqual(sample["unresolved"], [])

    def test_landscape_shaft_caret_clearance_and_inventory_mutations(self):
        mutations = {
            "shaft missing": (lambda f: f["elements"][0]["style"].update(background="none"), "missing-or-shifted-shaft"),
            "shaft transparent": (lambda f: f["elements"][1]["style"].update(background="linear-gradient(transparent, transparent)"), "missing-or-shifted-shaft"),
            "shaft shifted": (lambda f: f["elements"][0]["style"].update(backgroundPosition="left center"), "missing-or-shifted-shaft"),
            "shaft resized": (lambda f: f["elements"][1]["style"].update(backgroundSize="24px 2px"), "missing-or-shifted-shaft"),
            "shaft repeated": (lambda f: f["elements"][1]["style"].update(backgroundRepeat="repeat"), "missing-or-shifted-shaft"),
            "caret missing": (lambda f: f["elements"][0].update(pseudos=[]), "missing-or-wrong-caret"),
            "caret invisible": (lambda f: f["elements"][1]["after"].update(opacity=0), "missing-or-wrong-caret"),
            "caret hidden": (lambda f: f["elements"][0]["after"].update(visibility="hidden"), "missing-or-wrong-caret"),
            "caret reversed": (lambda f: f["elements"][1]["after"].update(transform="matrix(-0.707107, 0.707107, -0.707107, -0.707107, 0, 0)"), "missing-or-wrong-caret"),
            "caret unpainted": (lambda f: f["elements"][0]["after"]["borders"][1].update(color="rgba(0, 0, 0, 0)"), "missing-or-wrong-caret"),
            "caret extra pseudo": (lambda f: f["elements"][0]["pseudos"].append(dict(type="before", quad=copy.deepcopy(f["elements"][0]["pseudos"][0]["quad"]))), "unexpected-caret"),
            "caret displaced": (lambda f: f["elements"][1]["pseudos"][0]["quad"].__setitem__(0, 420), "caret-geometry-or-card-clearance"),
            "shaft intersects card": (lambda f: f["landscape"][0][2]["box"].update(x=390), "shaft-card-clearance"),
            "caret intersects card": (lambda f: f["landscape"][0][2]["box"].update(x=447), "caret-geometry-or-card-clearance"),
            "arrow hidden": (lambda f: f["landscape"][0][1].update(hidden=True), "missing-or-hidden-slot"),
            "arrow removed": (lambda f: (f["landscape"][0].pop(1), f["elements"].pop(0)), "inventory"),
            "extra arrow": (lambda f: f["landscape"][0].insert(2, copy.deepcopy(f["landscape"][0][1])), "inventory"),
            "extra arrow outside row": (lambda f: f["elements"].append(copy.deepcopy(f["elements"][0])), "arrow-inventory"),
        }
        for figure in ("sd-ethereum-account-fields", "jib-build-workflow"):
            for name, (mutate, expected) in mutations.items():
                with self.subTest(figure=figure, name=name):
                    sample = landscape_case(figure)
                    mutate(sample)
                    classify(sample)
                    self.assertNotEqual(sample["status"], "retained", sample)
                    self.assertIn("landscape-" + expected,
                                  [finding["type"] for finding in sample["findings"]], sample)

    def test_landscape_does_not_approve_non_target_or_unknown_pseudo(self):
        sample = landscape_case("unreviewed-figure")
        sample["elements"][0]["style"].update(background="none")
        classify(sample)
        self.assertFalse(any(row["type"].startswith("landscape-") for row in sample["findings"]))
        unknown = landscape_case()
        extra = copy.deepcopy(unknown["elements"][0])
        extra.update(id="unreviewed-pseudo", cls="unknown-paint", known=False,
                     prev=None, next=None, text=[])
        unknown["elements"].append(extra)
        classify(unknown)
        self.assertTrue(any(row["id"] == "unreviewed-pseudo" for row in unknown["unresolved"]))

    def test_jev_reviewed_fixture_is_retained(self):
        sample = jev_case()
        classify(sample)
        self.assertEqual(sample["status"], "retained", sample)
        self.assertEqual(sample["connectorCount"], 6)
        self.assertEqual(sample["findings"], [])
        self.assertEqual(sample["unresolved"], [])

    def test_jev_missing_hidden_malformed_and_misaligned_strokes_fail_closed(self):
        mutations = {
            "missing input": lambda f: f["elements"].pop(0),
            "hidden input": lambda f: f["elements"][0].update(hidden=True),
            "shaft removed": lambda f: f["elements"][0]["style"].update(background="none"),
            "shaft shifted": lambda f: f["elements"][0]["style"].update(backgroundPosition="left center"),
            "head removed": lambda f: f["elements"][1].update(pseudos=[]),
            "head invisible": lambda f: f["elements"][1]["after"].update(opacity=0),
            "head malformed": lambda f: f["elements"][4]["after"]["borders"][0].update(width=0),
            "head side removed": lambda f: f["elements"][0]["after"]["borders"][1].update(width=0),
            "head shifted": lambda f: f["elements"][5]["pseudos"][0]["quad"].__setitem__(0, 480),
            "drop arrowhead removed": lambda f: f["elements"][5].update(pseudos=[]),
            "drop shaft removed": lambda f: f["elements"][4]["style"].update(background="none"),
            "transfer off axis": lambda f: f["jev"]["transfer"]["box"].update(y=133),
            "fork missing": lambda f: f["elements"].pop(3),
            "stem missing paint": lambda f: f["elements"][2]["style"].update(color="rgba(0, 0, 0, 0)"),
            "fork severed": lambda f: f["jev"]["bus"]["box"].update(y=185),
            "drop off axis": lambda f: f["jev"]["shadowDrop"]["box"].update(x=360),
            "card intersection": lambda f: f["jev"]["shadow"]["box"].update(y=187),
            "label changed": lambda f: f["jev"]["transferLabel"].update(label="execution allowed"),
            "duplicate transfer": lambda f: f["elements"].append(copy.deepcopy(f["elements"][1])),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                sample = jev_case()
                mutate(sample)
                classify(sample)
                self.assertNotEqual(sample["status"], "retained", sample)
                self.assertTrue(sample["findings"] or sample["unresolved"], sample)

    def test_jev_contract_does_not_approve_other_figures(self):
        sample = jev_case()
        sample["figure"] = "different-figure"
        classify(sample)
        self.assertNotEqual(sample["status"], "retained")

    def test_jev_extra_horizontal_stroke_is_not_dismissed_as_decoration(self):
        for style, dimensions in (
            ({"color": "rgb(51, 65, 85)", "borders": []}, (52, 2)),
            ({"color": "transparent", "borders": [
                {"width": 2, "style": "solid", "color": "rgb(51, 65, 85)"},
                {"width": 0}, {"width": 0}, {"width": 0},
            ]}, (64, 74)),
        ):
            with self.subTest(style=style):
                sample = jev_case()
                sample["elements"].append(dict(
                    id="extra", cls="sd-jev-transfer", parent="sd-jev-flow",
                    known=True, svg=False, hidden=False,
                    box=dict(x=196, y=129, w=dimensions[0], h=dimensions[1]),
                    style=style, text=[], pseudos=[],
                ))
                classify(sample)
                self.assertTrue(any(row["id"] == "extra" for row in sample["unresolved"]))

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
