"""Per-source reuse rejects every changed or missing rendering input."""

import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path

from fhd_reuse import (
    FONT,
    PROOF,
    accepts,
    migrate,
    native_inputs,
    receipt_is_current,
    revalidate,
)
from pipeline import digest, fingerprint


class PerSourceReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root, self.site, self.out, self.metadata = [
            self.base / x for x in ("root", "site", "out", "metadata")
        ]
        for directory in (self.root, self.site, self.out, self.metadata):
            directory.mkdir()
        self.include = "diagrams/static/test.html"
        self.original = '<figure class="sd"><figcaption>Test</figcaption></figure>\n'
        self.renderer = "exact-render-js"
        self.browser = "Aside observed Chrome/153"
        self.svg_rel = "assets/img/diagrams/fhd-svg/static/test.svg"
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080" data-source-sha256="'
            + digest(self.original.encode())
            + '"><image href="/assets/img/example.png"/></svg>\n'
        )
        self.write(self.root / "_includes" / self.include, self.original.encode())
        for directory in (self.root, self.site):
            self.write(directory / self.svg_rel, svg.encode())
            self.write(directory / FONT, b"pinned-font")
            self.write(directory / "assets/img/example.png", b"sealed-image")
        fixture = b"<html><style>exact-render-style</style></html>"
        self.write(self.site / PROOF, fixture)
        self.artifact = self.base / "artifact"
        self.artifact.mkdir()
        self.write(self.artifact / "fixture.html", fixture)
        self.write(self.artifact / "pinned-font.ttf", b"pinned-font")
        exporter = self.metadata / "fhd-export-source.py"
        exporter.write_text('RENDER = "exact-render-js"\n')
        self.stamp = {
            "source": {
                "kkamji_scripts/blog/static_png/fhd_export.py": digest(
                    exporter.read_bytes()
                ),
                self.svg_rel: digest(svg.encode()),
            },
            "html": {PROOF: digest(fixture)},
            "assets": {
                FONT: digest(b"pinned-font"),
                "assets/img/example.png": digest(b"sealed-image"),
            },
        }
        (self.metadata / "build-stamp.json").write_text(json.dumps(self.stamp))
        self.inputs = native_inputs(
            self.root, self.site, self.include, self.browser, self.renderer
        )
        self.directory = self.out / "000"
        self.directory.mkdir()
        png = (
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", 1920, 1080)
            + b"\x08\x06\0\0\0"
        )
        self.write(self.directory / "diagram.png", png)
        self.receipt = {
            "index": 0,
            "include": self.include,
            "automated_status": "passed",
            "metrics": {"issues": [], "browser": self.browser},
            "build_identity": fingerprint(self.stamp),
            "source_sha256": digest(self.original.encode()),
            "svg_sha256": self.inputs["svg_sha256"],
            "font_sha256": self.inputs["font_sha256"],
            "png_sha256": digest(png),
            "artifact": str(self.artifact / "000.png"),
        }
        self.save(self.receipt)
        self.observed = {
            "browser": self.browser,
            "fixture_sha256": digest(fixture),
            "font_sha256": digest(b"pinned-font"),
        }

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def save(self, receipt):
        (self.directory / "receipt.json").write_text(json.dumps(receipt))

    def typed_receipt(self):
        return self.receipt | {
            "per_source_inputs": self.inputs,
            "per_source_fingerprint": fingerprint(self.inputs),
        }

    def test_every_changed_input_is_rejected(self):
        receipt = self.typed_receipt()
        self.assertTrue(accepts(receipt, self.inputs))
        for key in self.inputs:
            with self.subTest(key=key):
                changed = copy.deepcopy(self.inputs)
                changed[key] = (
                    "changed"
                    if key != "images"
                    else {"/assets/img/example.png": "changed"}
                )
                self.assertFalse(accepts(receipt, changed))

    def test_missing_fields_failed_receipt_and_fingerprint_are_rejected(self):
        receipt = self.typed_receipt()
        for key in self.inputs:
            with self.subTest(key=key):
                incomplete = dict(self.inputs)
                del incomplete[key]
                self.assertFalse(accepts(receipt, incomplete))
        self.assertFalse(accepts(receipt | {"automated_status": "failed"}, self.inputs))
        self.assertFalse(
            accepts(receipt | {"per_source_fingerprint": "wrong"}, self.inputs)
        )
        self.assertFalse(
            accepts(receipt | {"metrics": {"issues": ["clipped"]}}, self.inputs)
        )
        self.assertFalse(accepts(self.receipt, self.inputs))

    def test_explicit_migration_preserves_original_receipt_and_render_build(self):
        original = (self.directory / "receipt.json").read_bytes()
        result = migrate(self.root, self.site, self.out, self.metadata, self.renderer)
        self.assertEqual(result, {"migrated": [0], "rerender": []})
        self.assertEqual(
            (self.metadata / "original-receipts/000.json").read_bytes(), original
        )
        migrated = json.loads((self.directory / "receipt.json").read_text())
        self.assertTrue(accepts(migrated, self.inputs))
        self.assertEqual(migrated["build_identity"], fingerprint(self.stamp))

    def test_global_build_change_alone_accepts_same_inputs_and_retains_render_build(
        self,
    ):
        self.save(self.typed_receipt())
        new_stamp = self.stamp | {"unrelated-source": "changed"}
        result = revalidate(
            self.root, self.site, self.out, new_stamp, self.renderer, self.observed
        )
        self.assertEqual(result, {"accepted": [0], "rerender": []})
        receipt = json.loads((self.directory / "receipt.json").read_text())
        self.assertEqual(receipt["build_identity"], fingerprint(self.stamp))
        self.assertEqual(receipt["validated_build_identity"], fingerprint(new_stamp))

    def test_release_revalidation_requires_all_current_inputs_and_fresh_observation(
        self,
    ):
        receipt = self.typed_receipt()
        self.assertTrue(receipt_is_current(receipt, self.inputs, self.stamp))
        new_stamp = self.stamp | {"unrelated": "changed"}
        self.assertFalse(receipt_is_current(receipt, self.inputs, new_stamp))
        receipt |= {
            "validated_build_identity": fingerprint(new_stamp),
            "revalidation_observation": self.observed,
        }
        self.assertTrue(receipt_is_current(receipt, self.inputs, new_stamp))
        receipt["revalidation_observation"] = self.observed | {
            "fixture_sha256": "changed"
        }
        self.assertFalse(receipt_is_current(receipt, self.inputs, new_stamp))

    def test_current_observed_browser_change_requires_rerender(self):
        self.save(self.typed_receipt())
        changed = self.observed | {"browser": "new Aside browser"}
        result = revalidate(
            self.root, self.site, self.out, self.stamp, self.renderer, changed
        )
        self.assertEqual(result["accepted"], [])
        self.assertEqual(len(result["rerender"]), 1)

    def test_missing_actual_http_evidence_requires_rerender_without_mutation(self):
        original = (self.directory / "receipt.json").read_bytes()
        (self.artifact / "fixture.html").unlink()
        result = migrate(self.root, self.site, self.out, self.metadata, self.renderer)
        self.assertEqual(result["migrated"], [])
        self.assertEqual((self.directory / "receipt.json").read_bytes(), original)

    def test_changed_or_missing_built_source_image_svg_and_font_are_rejected(self):
        for relative in ("assets/img/example.png", self.svg_rel, FONT):
            with self.subTest(relative=relative):
                path = self.site / relative
                original = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    native_inputs(
                        self.root, self.site, self.include, self.browser, self.renderer
                    )
                path.write_bytes(original)

    def test_fresh_http_font_observation_and_cached_png_are_required(self):
        self.save(self.typed_receipt())
        for key in ("fixture_sha256", "font_sha256", "browser"):
            missing = dict(self.observed)
            del missing[key]
            with self.assertRaises(ValueError):
                revalidate(
                    self.root, self.site, self.out, self.stamp, self.renderer, missing
                )
        (self.directory / "diagram.png").write_bytes(b"changed")
        result = revalidate(
            self.root, self.site, self.out, self.stamp, self.renderer, self.observed
        )
        self.assertEqual(result["accepted"], [])

    def test_paths_cannot_escape_the_source_or_build_root(self):
        with self.assertRaises(ValueError):
            native_inputs(
                self.root,
                self.site,
                "diagrams/../secret.html",
                self.browser,
                self.renderer,
            )
        svg = (
            (self.root / self.svg_rel)
            .read_text()
            .replace("/assets/img/example.png", "/assets/../../secret")
        )
        for directory in (self.root, self.site):
            (directory / self.svg_rel).write_text(svg)
        with self.assertRaises(ValueError):
            native_inputs(
                self.root, self.site, self.include, self.browser, self.renderer
            )


if __name__ == "__main__":
    unittest.main()
