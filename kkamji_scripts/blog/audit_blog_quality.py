#!/usr/bin/env python3
"""Audit kkamji.net blog post quality.

The script is intentionally dependency-free so it can run in a fresh WSL or
GitHub Actions environment. It scans Jekyll posts, checks objective quality
signals, and writes Markdown plus CSV reports under .hermes/reports/.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
POSTS_DIR = ROOT / "_posts"
REPORT_DIR = ROOT / ".hermes" / "reports"
MD_REPORT = REPORT_DIR / "blog-quality-audit.md"
CSV_REPORT = REPORT_DIR / "blog-quality-audit.csv"

REQUIRED_FRONTMATTER = ["title", "date", "author", "categories", "tags", "comments"]
FORBIDDEN_CHARS = {"\u00b7": "middle dot", "\u2192": "right arrow"}
FOOTER_SNIPPET = "Written with [KKamJi](https://www.linkedin.com/in/taejikim/)"
REFERENCE_HEADING_RE = re.compile(r"^##\s+(?:\d+[.)]?\s*)?(?:Reference|References|참고|참고 자료)\s*$", re.I | re.M)
H2_RE = re.compile(r"^##\s+", re.M)
H3_RE = re.compile(r"^###\s+", re.M)
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((/[^)\s#]+)(?:#[^)]*)?\)")
MD_LINK_RE = re.compile(r"\[[^\]]+\]\((/posts/[^)#\s]+/?)(?:#[^)]*)?\)")
EXTERNAL_LINK_RE = re.compile(r"https?://[^\s)<>]+")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
EXCLUDED_REFERENCE_HOSTS = {
    "localhost",
    "127.0.0.1",
    "kkamji.net",
    "www.kkamji.net",
    "linkedin.com",
    "www.linkedin.com",
    "private-user-images.githubusercontent.com",
}
EXCLUDED_REFERENCE_HOST_PARTS = ["github.com/kkamji98/", "github.com/KKamJi98/"]


def clean_url(url: str) -> str:
    return url.rstrip(".,;:")


def should_require_reference(url: str) -> bool:
    cleaned = clean_url(url)
    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return False
    host = parsed.netloc.lower()
    host_no_www = host[4:] if host.startswith("www.") else host
    if host in EXCLUDED_REFERENCE_HOSTS or host_no_www in EXCLUDED_REFERENCE_HOSTS:
        return False
    lowered = cleaned.lower()
    return not any(part.lower() in lowered for part in EXCLUDED_REFERENCE_HOST_PARTS)


@dataclass
class PostAudit:
    path: Path
    title: str = ""
    date: str = ""
    categories: str = ""
    tags: str = ""
    line_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    code_fence_count: int = 0
    image_count: int = 0
    external_link_count: int = 0
    has_reference: bool = False
    has_footer: bool = False
    has_tldr: bool = False
    missing_frontmatter: list[str] = field(default_factory=list)
    missing_images: list[str] = field(default_factory=list)
    missing_post_links: list[str] = field(default_factory=list)
    forbidden_chars: list[str] = field(default_factory=list)
    score: int = 0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def rel(self) -> str:
        return self.path.relative_to(ROOT).as_posix()


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---") or text.count("---") < 2:
        return {}, text
    parts = text.split("---", 2)
    raw_fm = parts[1]
    body = parts[2]
    data: dict[str, str] = {}
    current_key = None
    for line in raw_fm.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")) and ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            data[current_key] = value.strip()
        elif current_key:
            data[current_key] += "\n" + line
    return data, body


def post_slug(path: Path) -> str:
    stem = path.stem
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
    return f"/posts/{slug}/"


def parse_listish(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def score_post(audit: PostAudit) -> None:
    score = 100

    penalties = [
        (audit.missing_frontmatter, 8, "missing frontmatter"),
        (audit.missing_images, 12, "missing image"),
        (audit.missing_post_links, 12, "missing internal post link"),
        (audit.forbidden_chars, 10, "forbidden character"),
    ]
    for values, weight, label in penalties:
        if values:
            score -= min(30, len(values) * weight)
            audit.issues.append(f"{label}: {len(values)}")

    if audit.external_link_count and not audit.has_reference:
        score -= 12
        audit.issues.append("external links but no Reference section")

    if not audit.has_footer:
        score -= 8
        audit.issues.append("missing standard footer")

    if audit.line_count > 120 and not audit.has_tldr:
        score -= 6
        audit.suggestions.append("add TL;DR callout")

    if audit.line_count > 350 and audit.h2_count < 5:
        score -= 6
        audit.suggestions.append("split long post into clearer H2 sections")

    if audit.line_count > 450:
        audit.suggestions.append("consider section-end summaries")

    if audit.h2_count == 0 and audit.line_count > 80:
        score -= 8
        audit.issues.append("long post without H2 headings")

    if audit.code_fence_count == 0 and any(term in audit.tags for term in ["kubernetes", "aws", "java", "spring", "terraform", "helm"]):
        audit.suggestions.append("consider adding concrete config or command examples")

    audit.score = max(0, min(100, score))


def audit_posts() -> list[PostAudit]:
    posts = sorted(POSTS_DIR.glob("**/*.md"))
    slugs = {post_slug(p) for p in posts}
    audits: list[PostAudit] = []

    for path in posts:
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        scan_text = HTML_COMMENT_RE.sub("", text)
        scan_body = HTML_COMMENT_RE.sub("", body)
        audit = PostAudit(path=path)
        audit.title = fm.get("title", "").strip().strip('"')
        audit.date = fm.get("date", "").strip()
        audit.categories = parse_listish(fm.get("categories", ""))
        audit.tags = parse_listish(fm.get("tags", ""))
        audit.line_count = len(body.splitlines())
        audit.h2_count = len(H2_RE.findall(body))
        audit.h3_count = len(H3_RE.findall(body))
        audit.code_fence_count = body.count("```") // 2
        audit.image_count = len(MD_IMAGE_RE.findall(scan_text))
        audit.external_link_count = len([url for url in EXTERNAL_LINK_RE.findall(scan_body) if should_require_reference(url)])
        audit.has_reference = bool(REFERENCE_HEADING_RE.search(scan_body))
        audit.has_footer = FOOTER_SNIPPET in scan_body
        audit.has_tldr = "TL;DR" in scan_body or "요약" in scan_body[:1500]

        audit.missing_frontmatter = [key for key in REQUIRED_FRONTMATTER if key not in fm]

        for char, name in FORBIDDEN_CHARS.items():
            if char in scan_text:
                audit.forbidden_chars.append(name)

        for img in MD_IMAGE_RE.findall(scan_text):
            if not (ROOT / img.lstrip("/")).exists():
                audit.missing_images.append(img)

        for link in MD_LINK_RE.findall(scan_text):
            normalized = link if link.endswith("/") else f"{link}/"
            if normalized not in slugs:
                audit.missing_post_links.append(link)

        score_post(audit)
        audits.append(audit)

    return audits


def bucket(audits: Iterable[PostAudit], predicate) -> list[PostAudit]:
    return [audit for audit in audits if predicate(audit)]


def write_csv(audits: list[PostAudit]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_REPORT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "score",
            "path",
            "title",
            "date",
            "categories",
            "tags",
            "lines",
            "h2",
            "h3",
            "code_blocks",
            "images",
            "external_links",
            "has_reference",
            "has_footer",
            "has_tldr",
            "issues",
            "suggestions",
        ])
        for audit in sorted(audits, key=lambda item: (item.score, item.rel)):
            writer.writerow([
                audit.score,
                audit.rel,
                audit.title,
                audit.date,
                audit.categories,
                audit.tags,
                audit.line_count,
                audit.h2_count,
                audit.h3_count,
                audit.code_fence_count,
                audit.image_count,
                audit.external_link_count,
                audit.has_reference,
                audit.has_footer,
                audit.has_tldr,
                "; ".join(audit.issues),
                "; ".join(audit.suggestions),
            ])


def write_markdown(audits: list[PostAudit]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    total = len(audits)
    avg_score = mean(a.score for a in audits) if audits else 0
    med_score = median(a.score for a in audits) if audits else 0
    line_avg = mean(a.line_count for a in audits) if audits else 0
    missing_images = bucket(audits, lambda a: bool(a.missing_images))
    missing_links = bucket(audits, lambda a: bool(a.missing_post_links))
    missing_fm = bucket(audits, lambda a: bool(a.missing_frontmatter))
    forbidden = bucket(audits, lambda a: bool(a.forbidden_chars))
    no_ref_with_links = bucket(audits, lambda a: a.external_link_count > 0 and not a.has_reference)
    no_footer = bucket(audits, lambda a: not a.has_footer)
    long_posts = sorted(bucket(audits, lambda a: a.line_count >= 450), key=lambda a: a.line_count, reverse=True)
    lowest = sorted(audits, key=lambda a: (a.score, -a.line_count, a.rel))[:25]
    high_impact = sorted(
        audits,
        key=lambda a: (
            a.score,
            -sum(word in a.tags.lower() + a.categories.lower() for word in ["kubernetes", "aws", "spring", "datadog", "observability", "terraform", "helm", "istio"]),
            -a.line_count,
        ),
    )[:30]

    lines: list[str] = []
    lines.append("# Blog Quality Audit")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Posts | {total} |")
    lines.append(f"| Average score | {avg_score:.1f} |")
    lines.append(f"| Median score | {med_score:.1f} |")
    lines.append(f"| Average body lines | {line_avg:.1f} |")
    lines.append(f"| Missing frontmatter posts | {len(missing_fm)} |")
    lines.append(f"| Missing image posts | {len(missing_images)} |")
    lines.append(f"| Missing internal link posts | {len(missing_links)} |")
    lines.append(f"| Forbidden character posts | {len(forbidden)} |")
    lines.append(f"| Posts with external links but no Reference | {len(no_ref_with_links)} |")
    lines.append(f"| Posts missing standard footer | {len(no_footer)} |")
    lines.append("")

    def add_section(title: str, rows: list[PostAudit], detail) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not rows:
            lines.append("None.")
            lines.append("")
            return
        lines.append("| Score | Post | Detail |")
        lines.append("| ---: | --- | --- |")
        for audit in rows:
            lines.append(f"| {audit.score} | `{audit.rel}` | {detail(audit)} |")
        lines.append("")

    add_section("Mechanical Issues - Missing Images", missing_images, lambda a: ", ".join(a.missing_images))
    add_section("Mechanical Issues - Missing Internal Links", missing_links, lambda a: ", ".join(a.missing_post_links))
    add_section("Mechanical Issues - Missing Frontmatter", missing_fm, lambda a: ", ".join(a.missing_frontmatter))
    add_section("Mechanical Issues - Forbidden Characters", forbidden, lambda a: ", ".join(a.forbidden_chars))
    add_section("Reference Normalization Candidates", no_ref_with_links[:40], lambda a: f"external links: {a.external_link_count}")
    add_section("Long Posts That May Need Section Summaries", long_posts[:25], lambda a: f"lines: {a.line_count}, H2: {a.h2_count}")
    add_section("Lowest Score Posts", lowest, lambda a: "; ".join(a.issues + a.suggestions) or "review")
    add_section("High Impact Refresh Candidates", high_impact, lambda a: f"tags: {a.tags}; issues: {'; '.join(a.issues + a.suggestions) or 'review depth'}")

    lines.append("## Next Actions")
    lines.append("")
    lines.append("1. Fix missing images and broken internal links first.")
    lines.append("2. Normalize Reference sections in high-impact posts.")
    lines.append("3. Add TL;DR or section-end summaries to long posts.")
    lines.append("4. Refresh high-impact posts one at a time with fact-checking.")
    lines.append("5. Promote this audit into the pre-publish quality gate once stable.")
    lines.append("")

    MD_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    audits = audit_posts()
    write_csv(audits)
    write_markdown(audits)
    print(f"Audited {len(audits)} posts")
    print(f"Markdown report: {MD_REPORT.relative_to(ROOT)}")
    print(f"CSV report: {CSV_REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
