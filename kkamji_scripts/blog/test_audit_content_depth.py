#!/usr/bin/env python3
"""Deterministic tests for the advisory content-depth harness.

All tests operate on in-memory post text or an isolated temporary directory, so
they never read from or write to the real repository content.

Run: python3 kkamji_scripts/blog/test_audit_content_depth.py
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_content_depth as acd  # noqa: E402


def make_post(body: str, **frontmatter: str) -> str:
    """Build post text with a minimal but valid Jekyll frontmatter block."""
    base = {
        "title": "테스트 글",
        "date": "2025-01-01 00:00:00 +0900",
        "author": "kkamji",
        "categories": "[Test]",
        "tags": "[test]",
        "comments": "true",
    }
    base.update(frontmatter)
    fm_lines = "\n".join(f"{k}: {v}" for k, v in base.items())
    return f"---\n{fm_lines}\n---\n\n{body}\n"


STANDARD_FOOTER = (
    "> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  \n"
    "> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  \n"
    "{: .prompt-info}"
)


def korean_prose(sentences: int) -> str:
    """Generate deterministic Korean prose long enough to look substantive."""
    unit = "이 문단은 개념을 설명하고 배경을 정리하며 독자의 이해를 돕는 서술형 문장입니다. "
    return (unit * sentences).strip()


class GenreExemptionTests(unittest.TestCase):
    def test_cheatsheet_by_path_has_no_depth_signals(self) -> None:
        body = "명령어를 정리한 아키텍처 구조 흐름 요약입니다.\n\n## 명령어\n\n간단한 설명."
        audit = acd.analyze(
            "_posts/cheat-sheet/2025-01-01-x.md",
            make_post(body, title="쿠버네티스 완벽 가이드 아키텍처"),
        )
        self.assertEqual(audit.genre, "cheatsheet")
        self.assertEqual(audit.signals, [])

    def test_cheatsheet_by_tag_has_no_depth_signals(self) -> None:
        audit = acd.analyze(
            "_posts/2025/01/2025-01-01-x.md",
            make_post("아키텍처 흐름 구조 설명.", tags="[git, cheat-sheet]", title="git 가이드"),
        )
        self.assertEqual(audit.genre, "cheatsheet")
        self.assertEqual(audit.signals, [])

    def test_exempt_frontmatter_has_no_depth_signals(self) -> None:
        body = korean_prose(60) + "\n\n아키텍처 흐름 구조를 다룹니다."
        audit = acd.analyze(
            "_posts/2025/01/2025-01-01-x.md",
            make_post(body, title="완벽 가이드 아키텍처", content_quality_exempt="true"),
        )
        self.assertEqual(audit.genre, "exempt")
        self.assertEqual(audit.confidence, "n/a")
        self.assertEqual(audit.signals, [])


class ProseExtractionTests(unittest.TestCase):
    def test_code_fence_excluded_from_prose(self) -> None:
        fenced_korean = "\n".join("이 줄은 코드 블록 안에 있는 한국어 문장입니다." for _ in range(20))
        body = (
            "짧은 서술입니다.\n\n"
            "```python\n"
            f"# {fenced_korean}\n"
            "print('hello world example code line')\n"
            "```\n\n"
            "끝."
        )
        audit = acd.analyze("_posts/2025/01/2025-01-01-x.md", make_post(body))
        # Only the two short prose sentences count; fenced Korean is excluded.
        self.assertLess(audit.korean_chars, 40)
        self.assertGreaterEqual(audit.code_lines, 4)  # 2 fences + 2 code lines
        self.assertNotIn("hello", " ".join(str(v) for v in [audit.latin_words]))
        self.assertEqual(audit.latin_words, 0)


class AdvisorySignalTests(unittest.TestCase):
    def test_broad_short_explainer_enrich(self) -> None:
        body = "짧은 소개 문장입니다.\n\n## 개요\n\n한 줄 설명."
        audit = acd.analyze(
            "_posts/2025/01/2025-01-01-x.md",
            make_post(body, title="쿠버네티스 완벽 가이드"),
        )
        self.assertEqual(audit.genre, "explainer")
        self.assertLess(audit.est_minutes_estimate, acd.ENRICH_MAX_MINUTES)
        self.assertIn("ENRICH", audit.signals)

    def test_visualize_and_cite_fire_without_visual_or_reference(self) -> None:
        body = (
            "다음은 시스템 아키텍처와 데이터 흐름 구조를 설명하는 글입니다.\n\n"
            "## 본문\n\n" + korean_prose(80)
        )
        audit = acd.analyze(
            "_posts/2025/01/2025-01-01-x.md", make_post(body, title="시스템 아키텍처 설명")
        )
        self.assertGreaterEqual(audit.est_minutes_estimate, acd.SUBSTANTIVE_MINUTES)
        self.assertIn("VISUALIZE", audit.signals)
        self.assertIn("CITE", audit.signals)

    def test_visualize_and_cite_suppressed_with_image_and_reference(self) -> None:
        body = (
            "다음은 시스템 아키텍처와 데이터 흐름 구조를 설명하는 글입니다.\n\n"
            "![아키텍처 다이어그램](/assets/img/x.png)\n\n"
            "## 본문\n\n" + korean_prose(80) + "\n\n"
            "## References\n\n- [Docs - Guide](https://example.com/guide)"
        )
        audit = acd.analyze(
            "_posts/2025/01/2025-01-01-x.md", make_post(body, title="시스템 아키텍처 설명")
        )
        self.assertEqual(audit.inline_visuals, 1)
        self.assertTrue(audit.has_reference)
        self.assertNotIn("VISUALIZE", audit.signals)
        self.assertNotIn("CITE", audit.signals)


class MechanicalCheckTests(unittest.TestCase):
    def test_invalid_content_kind_is_mechanical(self) -> None:
        audit = acd.analyze(
            "_posts/2025/01/2025-01-01-x.md",
            make_post("본문 " + korean_prose(3), content_kind="tutorial"),
        )
        self.assertTrue(any("invalid content_kind" in m for m in audit.mechanical))

    def test_valid_content_kind_is_not_mechanical(self) -> None:
        audit = acd.analyze(
            "_posts/2025/01/2025-01-01-x.md",
            make_post("본문 " + korean_prose(3), content_kind="announcement"),
        )
        self.assertEqual(audit.genre, "announcement")
        self.assertFalse(any("content_kind" in m for m in audit.mechanical))

    def test_duplicate_footer_is_mechanical(self) -> None:
        body = korean_prose(5) + "\n\n" + STANDARD_FOOTER + "\n\n" + STANDARD_FOOTER
        audit = acd.analyze("_posts/2025/01/2025-01-01-x.md", make_post(body))
        self.assertEqual(audit.footer_count, 2)
        self.assertTrue(any("duplicate standard footer" in m for m in audit.mechanical))

    def test_wrong_footer_marker_is_mechanical(self) -> None:
        wrong = STANDARD_FOOTER.replace("prompt-info", "prompt-tip")
        body = korean_prose(5) + "\n\n" + wrong
        audit = acd.analyze("_posts/2025/01/2025-01-01-x.md", make_post(body))
        self.assertEqual(audit.footer_count, 1)
        self.assertEqual(audit.footer_marker, "prompt-tip")
        self.assertTrue(any("footer marker must be .prompt-info" in m for m in audit.mechanical))

    def test_single_correct_footer_is_clean(self) -> None:
        body = korean_prose(5) + "\n\n" + STANDARD_FOOTER
        audit = acd.analyze("_posts/2025/01/2025-01-01-x.md", make_post(body))
        self.assertEqual(audit.footer_count, 1)
        self.assertEqual(audit.footer_marker, "prompt-info")
        self.assertEqual(audit.mechanical, [])

    def test_missing_image_alt_is_mechanical(self) -> None:
        body = "설명입니다.\n\n![](/assets/img/no-alt.png)\n\n" + korean_prose(3)
        audit = acd.analyze("_posts/2025/01/2025-01-01-x.md", make_post(body))
        self.assertTrue(any("image missing alt text" in m for m in audit.mechanical))

    def test_present_image_alt_is_clean(self) -> None:
        body = "설명입니다.\n\n![유효한 대체 텍스트](/assets/img/ok.png)\n\n" + korean_prose(3)
        audit = acd.analyze("_posts/2025/01/2025-01-01-x.md", make_post(body))
        self.assertFalse(any("image missing alt text" in m for m in audit.mechanical))


class DeterminismAndCliTests(unittest.TestCase):
    def test_analysis_is_repeatable(self) -> None:
        text = make_post(korean_prose(40) + "\n\n## 본문\n\n아키텍처 흐름 구조 설명.")
        first = acd.analyze("_posts/2025/01/2025-01-01-x.md", text)
        second = acd.analyze("_posts/2025/01/2025-01-01-x.md", text)
        self.assertEqual(first, second)

    def test_cli_advisory_returns_zero_and_mechanical_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            post_dir = root / "_posts" / "2025" / "01"
            post_dir.mkdir(parents=True)
            # Advisory-only post (broad + thin -> ENRICH) with no mechanical issue.
            (post_dir / "2025-01-01-advisory.md").write_text(
                make_post("짧은 설명.\n\n## 개요\n\n한 줄.", title="완벽 가이드"),
                encoding="utf-8",
            )
            # Post with a mechanical violation (duplicate footer).
            (post_dir / "2025-01-02-mech.md").write_text(
                make_post(korean_prose(5) + "\n\n" + STANDARD_FOOTER + "\n\n" + STANDARD_FOOTER),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                advisory_code = acd.run(root, only=None, fail_on="none")
                mechanical_code = acd.run(root, only=None, fail_on="mechanical")
            self.assertEqual(advisory_code, 0)
            self.assertEqual(mechanical_code, 1)

            reports = root / ".hermes" / "reports"
            self.assertTrue((reports / "blog-content-depth.md").exists())
            self.assertTrue((reports / "blog-content-depth.csv").exists())
            self.assertTrue((reports / "blog-content-depth.json").exists())

    def test_only_glob_filters_posts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            post_dir = root / "_posts" / "2025" / "01"
            post_dir.mkdir(parents=True)
            (post_dir / "2025-01-01-keep.md").write_text(make_post(korean_prose(3)), encoding="utf-8")
            (post_dir / "2025-01-02-skip.md").write_text(make_post(korean_prose(3)), encoding="utf-8")
            audits = acd.audit_all(root, only="*keep*")
            self.assertEqual(len(audits), 1)
            self.assertIn("keep", audits[0].path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
