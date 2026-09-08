import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib

from downloads import main as downloads_main, source_snapshot
from pipeline import fingerprint
from release_manifest import verify_staged


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("docs", "_posts", "_includes/diagrams", "assets/css"):
            (self.root / name).mkdir(parents=True)
        self.css = self.root / "assets/css/jekyll-theme-chirpy.scss"
        self.css.write_text("original style\n")
        (self.root / "_posts/example.md").write_text(
            "{% include diagrams/example.html %}\n"
        )
        source = self.root / "_includes/diagrams/example.html"
        source.write_text(
            '<figure class="sd" id="example"><figcaption>Example</figcaption></figure>'
        )
        catalog = {
            "summary": {"post_references": 1, "posts": 1},
            "diagrams": [
                {
                    "include": "diagrams/example.html",
                    "posts": ["_posts/example.md"],
                    "reference_count": 1,
                }
            ],
        }
        (self.root / "docs/diagram-catalog.json").write_text(json.dumps(catalog))
        downloads_main(["wire", "--root", str(self.root)])
        plan = json.loads((self.root / "docs/diagram-downloads.json").read_text())
        entry = plan["entries"][0]
        self.png = self.root / entry["png"].lstrip("/")
        self.png.parent.mkdir(parents=True)

        def chunk(kind, body):
            return (
                struct.pack(">I", len(body))
                + kind
                + body
                + struct.pack(">I", zlib.crc32(kind + body))
            )

        raw = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
            + chunk(b"IEND", b"")
        )
        self.png.write_bytes(raw)
        self.manifest = self.root / "docs/diagram-export-release.json"
        self.data = {
            "schema": 1,
            "status": "export-and-check-passed",
            "reference_count": 1,
            "post_count": 1,
            "source_fingerprint": fingerprint(source_snapshot(self.root)),
            "entries": [dict(entry, png_sha256=hashlib.sha256(raw).hexdigest())],
        }
        self.manifest.write_text(json.dumps(self.data))
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.stage()

    def stage(self):
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)

    def test_trigger_is_scoped_to_diagram_changes(self):
        from unittest.mock import patch
        from release_manifest import staged_requires_verification

        with patch(
            "release_manifest.subprocess.check_output",
            return_value="assets/css/jekyll-theme-chirpy.scss\n",
        ):
            self.assertTrue(staged_requires_verification(self.root))
        with patch(
            "release_manifest.subprocess.check_output",
            side_effect=["_posts/example.md\n", "+ordinary prose\n"],
        ):
            self.assertFalse(staged_requires_verification(self.root))
        with patch(
            "release_manifest.subprocess.check_output",
            side_effect=[
                "_posts/example.md\n",
                "+{% include diagrams/example.html %}\n",
            ],
        ):
            self.assertTrue(staged_requires_verification(self.root))

    def test_ignored_jekyll_artifacts_and_local_lock_are_not_public_inputs(self):
        (self.root / ".gitignore").write_text("Gemfile.lock\n.jekyll-cache/\n_site/\n")
        (self.root / "Gemfile.lock").write_text("local dependency snapshot")
        cache = self.root / "assets/img/_site/cache.png"
        cache.parent.mkdir()
        cache.write_bytes(b"local cache")
        self.data["source_fingerprint"] = fingerprint(source_snapshot(self.root))
        self.manifest.write_text(json.dumps(self.data))
        self.stage()
        verify_staged(self.root)

    def test_ignored_real_image_still_requires_index_presence(self):
        (self.root / ".gitignore").write_text("assets/img/required.png\n")
        image = self.root / "assets/img/required.png"
        image.write_bytes(b"real source image")
        self.data["source_fingerprint"] = fingerprint(source_snapshot(self.root))
        self.manifest.write_text(json.dumps(self.data))
        self.stage()
        with self.assertRaisesRegex(ValueError, "absent from index"):
            verify_staged(self.root)

    def test_current_staged_release_passes(self):
        verify_staged(self.root)

    def test_css_change_requires_new_verified_manifest(self):
        self.css.write_text("changed connector geometry\n")
        self.stage()
        with self.assertRaisesRegex(ValueError, "source fingerprint"):
            verify_staged(self.root)

    def test_corrupt_png_fails(self):
        self.png.write_bytes(b"corrupt")
        self.stage()
        with self.assertRaises(ValueError):
            verify_staged(self.root)

    def test_missing_entry_fails(self):
        self.data["entries"] = []
        self.manifest.write_text(json.dumps(self.data))
        self.stage()
        with self.assertRaises(ValueError):
            verify_staged(self.root)

    def test_unstaged_input_cannot_validate_different_index(self):
        self.css.write_text("unstaged input\n")
        self.data["source_fingerprint"] = fingerprint(source_snapshot(self.root))
        self.manifest.write_text(json.dumps(self.data))
        subprocess.run(
            ["git", "add", "docs/diagram-export-release.json"],
            cwd=self.root,
            check=True,
        )
        with self.assertRaisesRegex(ValueError, "index"):
            verify_staged(self.root)


if __name__ == "__main__":
    unittest.main()
