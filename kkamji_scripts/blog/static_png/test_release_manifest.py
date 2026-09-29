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
from release_manifest import staged_requires_verification, verify_staged


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
        for changed_line in (
            "+{% include diagrams/example.html %}\n",
            "+{%  include    diagrams/example.html %}\n",
            "-{%\tinclude\tdiagrams/example.html %}\n",
            "+{% include\n+ diagrams/example.html %}\n",
        ):
            with self.subTest(changed_line=changed_line):
                with patch(
                    "release_manifest.subprocess.check_output",
                    side_effect=["_posts/example.md\n", changed_line],
                ):
                    self.assertTrue(staged_requires_verification(self.root))

    def test_isolated_staged_render_inputs_trigger_and_reject_stale_release(self):
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "commit", "-qm", "baseline"],
            cwd=self.root, check=True,
        )
        sealed_paths = (
            "_includes/header.html",
            "_layouts/default.html",
            "_sass/theme.scss",
            "_plugins/site.rb",
            "_data/navigation.yml",
            "assets/css/extra.scss",
            "assets/js/site.js",
            "assets/fonts/site.woff2",
            "assets/img/icons/source.svg",
            "kkamji_scripts/blog/static_png/extra.py",
            "_config.yml",
            "Gemfile",
            "Gemfile.lock",
            "docs/diagram-catalog.json",
            "docs/diagram-downloads.json",
            "docs/diagram-export-release.json",
        )
        # Catalog, mapping and manifest are tracked already; a modified file must also
        # trigger, not just an added file under a sealed directory.
        for name in sealed_paths:
            with self.subTest(path=name):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("changed render input\n")
                subprocess.run(["git", "add", "--", name], cwd=self.root, check=True)
                staged = subprocess.check_output(
                    ["git", "diff", "--cached", "--name-only"],
                    cwd=self.root, text=True,
                ).splitlines()
                self.assertEqual(staged, [name])
                self.assertTrue(staged_requires_verification(self.root))
                # The already-checked manifest cannot certify this input.
                if name not in (
                    "docs/diagram-catalog.json",
                    "docs/diagram-downloads.json",
                    "docs/diagram-export-release.json",
                ):
                    with self.assertRaisesRegex(ValueError, "source fingerprint"):
                        verify_staged(self.root)
                subprocess.run(["git", "reset", "--hard", "HEAD"],
                               cwd=self.root, check=True, capture_output=True)

    def test_mapped_png_triggers_without_becoming_a_source_input(self):
        self.assertNotIn(self.png.relative_to(self.root).as_posix(), source_snapshot(self.root))
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "commit", "-qm", "baseline"],
            cwd=self.root, check=True,
        )
        self.png.write_bytes(b"changed mapped PNG")
        subprocess.run(["git", "add", "--", str(self.png.relative_to(self.root))],
                       cwd=self.root, check=True)
        self.assertTrue(staged_requires_verification(self.root))
        with self.assertRaisesRegex(ValueError, "public PNG changed"):
            verify_staged(self.root)

    def test_prose_and_unsealed_files_do_not_trigger(self):
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "commit", "-qm", "baseline"],
            cwd=self.root, check=True,
        )
        for name, content in (
            ("_posts/example.md", "ordinary prose\n"),
            ("README.md", "unrelated documentation\n"),
        ):
            with self.subTest(path=name):
                path = self.root / name
                path.write_text(path.read_text() + content if path.exists() else content)
                subprocess.run(["git", "add", "--", name], cwd=self.root, check=True)
                self.assertEqual(
                    subprocess.check_output(["git", "diff", "--cached", "--name-only"],
                                            cwd=self.root, text=True).splitlines(),
                    [name],
                )
                self.assertFalse(staged_requires_verification(self.root))
                subprocess.run(["git", "reset", "--hard", "HEAD"],
                               cwd=self.root, check=True, capture_output=True)

    def test_staged_diagram_include_line_still_triggers(self):
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "commit", "-qm", "baseline"],
            cwd=self.root, check=True,
        )
        post = self.root / "_posts/example.md"
        post.write_text(post.read_text() + "{% include diagrams/another.html %}\n")
        subprocess.run(["git", "add", "--", "_posts/example.md"],
                       cwd=self.root, check=True)
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
