#!/usr/bin/env python3
"""Fail when high-impact technical posts do not have a TL;DR callout."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / ".hermes" / "reports" / "blog-quality-audit.csv"
KEYWORDS = [
    "kubernetes",
    "aws",
    "spring",
    "jvm",
    "terraform",
    "helm",
    "istio",
    "argocd",
    "jenkins",
    "cilium",
    "observability",
    "datadog",
]


def impact(row: dict[str, str]) -> int:
    text = " ".join([row.get("path", ""), row.get("title", ""), row.get("categories", ""), row.get("tags", "")]).lower()
    return sum(1 for keyword in KEYWORDS if keyword in text)


def main() -> None:
    rows = list(csv.DictReader(AUDIT.open(encoding="utf-8")))
    failures = [row for row in rows if impact(row) > 0 and row.get("has_tldr") != "True"]
    if failures:
        print("High-impact TL;DR gate failed:")
        for row in failures[:50]:
            print(f"- {row['path']}: {row['title']}")
        if len(failures) > 50:
            print(f"- ... {len(failures) - 50} more")
        raise SystemExit(1)
    print("High-impact TL;DR gate passed")


if __name__ == "__main__":
    main()
