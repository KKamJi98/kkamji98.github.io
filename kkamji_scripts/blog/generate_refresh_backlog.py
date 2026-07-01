#!/usr/bin/env python3
"""Generate a prioritized blog refresh backlog from the audit CSV."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / ".hermes" / "reports" / "blog-quality-audit.csv"
OUT = ROOT / "docs" / "blog-refresh-backlog.md"
HIGH_IMPACT_KEYWORDS = [
    "kubernetes",
    "aws",
    "spring",
    "jvm",
    "datadog",
    "observability",
    "terraform",
    "helm",
    "istio",
    "argocd",
    "jenkins",
    "cilium",
]


def load_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(AUDIT.open(encoding="utf-8")))


def impact(row: dict[str, str]) -> int:
    text = " ".join([row.get("path", ""), row.get("title", ""), row.get("categories", ""), row.get("tags", "")]).lower()
    return sum(1 for keyword in HIGH_IMPACT_KEYWORDS if keyword in text)


def reason(row: dict[str, str]) -> str:
    parts = []
    if row.get("issues"):
        parts.append(row["issues"])
    if row.get("suggestions"):
        parts.append(row["suggestions"])
    if not parts:
        parts.append("high-impact topic refresh")
    return "; ".join(parts)


def checkbox(row: dict[str, str]) -> str:
    return f"- [ ] `{row['path']}` - score {row['score']}, {reason(row)}"


def main() -> None:
    rows = load_rows()
    rows_by_score = sorted(rows, key=lambda r: (int(r["score"]), -impact(r), -int(r["lines"])))
    high_impact = [r for r in rows_by_score if impact(r) > 0]
    long_posts = sorted([r for r in rows if int(r["lines"]) >= 450], key=lambda r: int(r["lines"]), reverse=True)
    reference = [r for r in rows_by_score if "external links but no Reference" in r.get("issues", "")]
    tldr = [r for r in rows_by_score if "add TL;DR" in r.get("suggestions", "")]

    lines = [
        "# Blog Refresh Backlog",
        "",
        "이 문서는 `kkamji_scripts/blog/audit_blog_quality.py` 결과를 바탕으로 생성한 리프레시 우선순위다.",
        "전체 글을 한 번에 고치기보다 Tier 1부터 작은 배치로 진행한다.",
        "",
        "## Tier 1 - High impact technical refresh",
        "",
    ]
    lines.extend(checkbox(r) for r in high_impact[:30])
    lines.extend([
        "",
        "## Tier 2 - Reference normalization",
        "",
    ])
    lines.extend(checkbox(r) for r in reference[:40])
    lines.extend([
        "",
        "## Tier 3 - Long-form readability pass",
        "",
    ])
    lines.extend(checkbox(r) for r in long_posts[:30])
    lines.extend([
        "",
        "## Tier 4 - TL;DR candidates",
        "",
    ])
    lines.extend(checkbox(r) for r in tldr[:40])
    lines.extend([
        "",
        "## Execution notes",
        "",
        "- Use `research-deep-research` for posts with factual/version-sensitive claims.",
        "- Use `blog-review-post` after each refresh.",
        "- Run `kkamji_scripts/blog/pre_publish_check.sh` before commit/push.",
        "- Avoid changing slugs unless redirects are planned.",
        "",
    ])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
