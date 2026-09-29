"""Bounded corpus CLI guards; all path fixtures stay in disposable /tmp."""
from contextlib import redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import connector_corpus as corpus


class CorpusSafetyTests(unittest.TestCase):
    def test_corpus_summary_count_is_independent_of_case_widths(self):
        entries = [{"include": "a"}, {"include": "b"}]
        plan = {"reference_count": 2, "unused_includes": []}
        results = [
            {"include": entry["include"], "status": "passed", "width": width}
            for entry in entries for width in (360, 390, 625, 720)
            for _theme in ("light", "dark")
        ]
        summary = corpus.summarize_cases(entries, plan, results)
        self.assertEqual(summary["expected_cases"], 16)
        self.assertEqual(summary["cases"], 16)
        self.assertEqual(summary["components"], 2)
        self.assertEqual(summary["statuses"], {"passed": 16})
        self.assertTrue(summary["passed"])
        broken = [dict(row) for row in results]
        broken[-1]["status"] = "error"
        self.assertFalse(corpus.summarize_cases(entries, plan, broken)["passed"])
        self.assertFalse(corpus.summarize_cases(entries, plan, results[:-1])["passed"])

    def test_fixed_artwork_retains_source_width_without_fake_625_or_720_content(self):
        for figure in corpus.FIXED_CANVAS_FIGURES:
            for requested in (625, 720):
                with self.subTest(figure=figure, requested=requested):
                    self.assertEqual(
                        corpus.content_width_contract(figure, requested, 32),
                        ("fixed-source-content", 593),
                    )
            self.assertEqual(corpus.content_width_contract(figure, 360, 32),
                             ("native-viewport", None))
        for requested in (625, 720):
            self.assertEqual(corpus.content_width_contract("unfixed-figure", requested, 32),
                             ("exact-figure-content", requested))

    def test_protected_output_rejected_before_discovery(self):
        with tempfile.TemporaryDirectory(prefix="corpus-safety-", dir="/tmp") as tmp:
            base = Path(tmp)
            root, site = base / "root", base / "site"
            root.mkdir()
            site.mkdir()
            targets = [
                root,
                site,
                root / "assets/css/jekyll-theme-chirpy.scss",
                site / ".diagram-download-build.json",
                site / "assets/css/jekyll-theme-chirpy.css",
            ]
            for target in targets[2:]:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("protected input")
            (base / "root-alias").symlink_to(root, target_is_directory=True)
            (base / "site-alias").symlink_to(site, target_is_directory=True)
            (base / "report-link.json").symlink_to(targets[3])
            outputs = targets + [
                base / "root-alias/new/report.json",
                base / "site-alias/new/report.json",
                base / "report-link.json",
                base / "outside/../root/new/report.json",
            ]
            with patch.object(corpus, "ROOT", root), patch.object(
                corpus, "validate_source", side_effect=AssertionError("discovery reached")
            ) as discovery, patch.object(corpus, "verify_seal") as seal, patch.object(
                corpus, "ThreadingHTTPServer"
            ) as server:
                for out in outputs:
                    with self.subTest(out=out), redirect_stderr(io.StringIO()) as error:
                        with self.assertRaises(SystemExit) as caught:
                            corpus.main(["--root", str(root), "--site", str(site), "--out", str(out)])
                        self.assertEqual(caught.exception.code, 2)
                        self.assertIn("--out", error.getvalue())
                discovery.assert_not_called()
                seal.assert_not_called()
                server.assert_not_called()
            for target in targets[2:]:
                self.assertEqual(target.read_text(), "protected input")
            self.assertFalse((root / "new").exists())
            self.assertFalse((site / "new").exists())

    def test_external_output_resolves_without_creating_directories(self):
        with tempfile.TemporaryDirectory(prefix="corpus-safety-", dir="/tmp") as tmp:
            base = Path(tmp)
            root, site = base / "root", base / "site"
            root.mkdir()
            site.mkdir()
            alias = base / "external-alias"
            alias.symlink_to(base, target_is_directory=True)
            for out in (base / "root-sibling/report.json", alias / "reports/report.json"):
                with self.subTest(out=out):
                    self.assertEqual(corpus.resolve_output(root, site, out), out.resolve())
                    self.assertFalse(out.parent.exists())

    def test_same_checkout_alias_and_default_root_reach_discovery(self):
        with tempfile.TemporaryDirectory(prefix="corpus-safety-", dir="/tmp") as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            alias = base / "root-alias"
            alias.symlink_to(root, target_is_directory=True)
            for root_args in ([], ["--root", str(root)], ["--root", str(alias)]):
                with self.subTest(root_args=root_args), patch.object(corpus, "ROOT", root), patch.object(
                    corpus, "validate_source", side_effect=RuntimeError("stop at discovery")
                ) as discovery:
                    with self.assertRaisesRegex(RuntimeError, "stop at discovery"):
                        corpus.main(root_args + ["--site", str(base / "site"),
                                                 "--out", str(base / "reports/report.json")])
                    discovery.assert_called_once_with(root)
            self.assertFalse((base / "reports").exists())

    def test_alternate_root_rejected_before_discovery(self):
        with tempfile.TemporaryDirectory(prefix="corpus-safety-", dir="/tmp") as tmp:
            base = Path(tmp)
            root, other = base / "executing-root", base / "other-root"
            root.mkdir()
            other.mkdir()
            alias = base / "other-alias"
            alias.symlink_to(other, target_is_directory=True)
            with patch.object(corpus, "ROOT", root), patch.object(
                corpus, "validate_source", side_effect=AssertionError("discovery reached")
            ) as discovery, patch.object(corpus, "ThreadingHTTPServer") as server:
                for candidate in (other, alias):
                    with self.subTest(root=candidate), redirect_stderr(io.StringIO()) as error:
                        with self.assertRaises(SystemExit) as caught:
                            corpus.main(["--root", str(candidate), "--site", str(base / "site"),
                                         "--out", str(base / "report.json")])
                        self.assertEqual(caught.exception.code, 2)
                        self.assertIn("--root", error.getvalue())
                discovery.assert_not_called()
                server.assert_not_called()
            self.assertFalse((base / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
