#!/usr/bin/env python3
"""Check homepage ordering for curated learning series.

Jekyll renders posts in descending front matter datetime order. For learning
series, the first lesson should appear above the next lesson on the homepage.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POSTS_DIR = ROOT / "_posts"
TITLE_RE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.M)
DATE_RE = re.compile(r"^date:\s*(.+)$", re.M)
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S %z"

SERIES: dict[str, list[str]] = {
    "RAG": [
        "rag-overview-concept-and-pipeline",
        "rag-chunking-embedding-contextual-retrieval",
        "rag-vector-database-and-index",
        "rag-hybrid-search-and-reranking",
        "rag-security-and-access-control",
        "rag-latency-optimization-and-evaluation",
        "rag-llm-api-and-advanced",
    ],
    "AWS Analytics": [
        "aws-analytics-stack-overview",
        "distributed-sql-engine-trino-presto",
        "aws-athena-glue-catalog",
        "apache-iceberg-table-format",
        "aws-s3-tables-catalog-federation",
        "aws-lake-formation",
        "aws-lake-formation-permissions-deep-dive",
    ],
    "Spring JVM": [
        "spring-ioc-di-container",
        "spring-request-lifecycle",
        "spring-mvc-dispatcherservlet",
        "spring-boot-autoconfiguration",
        "gradle-maven-build",
        "spring-transactional-propagation",
        "jpa-persistence-context",
        "jpa-n-plus-1",
        "spring-security-basics",
        "mvc-vs-webflux",
        "reactive-reactor-basics",
        "spring-webflux-netty-event-loop",
        "jvm-memory-model",
        "gc-basics-g1gc",
        "gc-tuning-jdk-versions",
        "buildpack-memory-calculator",
        "jvm-spring-capstone",
    ],
    "GCP Basics": [
        "what-is-gcp",
        "gcp-resource-hierarchy",
        "gcp-iam",
    ],
}


def slug_from_path(path: Path) -> str:
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)


def post_info(path: Path) -> tuple[str, datetime, str]:
    text = path.read_text(encoding="utf-8")
    title_match = TITLE_RE.search(text)
    date_match = DATE_RE.search(text)
    if not title_match or not date_match:
        raise ValueError(f"missing title or date: {path.relative_to(ROOT).as_posix()}")
    date_text = date_match.group(1).strip().strip('"\'')
    return title_match.group(1).strip(), datetime.strptime(date_text, DATETIME_FORMAT), date_text


def main() -> None:
    by_slug: dict[str, tuple[Path, str, datetime, str]] = {}
    for path in sorted(POSTS_DIR.glob("**/*.md")):
        slug = slug_from_path(path)
        if slug not in {item for slugs in SERIES.values() for item in slugs}:
            continue
        title, parsed_date, date_text = post_info(path)
        by_slug[slug] = (path, title, parsed_date, date_text)

    failures: list[str] = []
    for name, expected_slugs in SERIES.items():
        missing = [slug for slug in expected_slugs if slug not in by_slug]
        if missing:
            failures.append(f"{name}: missing posts: {', '.join(missing)}")
            continue

        actual_slugs = [
            slug
            for slug in sorted(
                expected_slugs,
                key=lambda item: by_slug[item][2],
                reverse=True,
            )
        ]
        if actual_slugs != expected_slugs:
            failures.append(f"{name}: order mismatch")
            failures.append(f"  expected: {', '.join(expected_slugs)}")
            failures.append(f"  actual:   {', '.join(actual_slugs)}")

    if failures:
        print("Series order check failed:")
        for failure in failures:
            print(failure)
        raise SystemExit(1)

    print(f"Series order check passed: {len(SERIES)} curated series")


if __name__ == "__main__":
    main()
