#!/usr/bin/env python3
"""Check Jekyll post date hygiene.

Fails when:
- Two or more posts share the same front matter timestamp.
- A filename date is later than today.
- Front matter date does not match the filename date.

Several posts may share a filename date. Jekyll and check_series_order.py both
order on the full front matter timestamp, so a day that carries three posts at
13:00, 13:10 and 13:20 has an unambiguous order. Only an identical timestamp
leaves the order undefined, and that is what fails here.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POSTS_DIR = ROOT / "_posts"
POST_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
FM_DATE_RE = re.compile(r"^date:\s*(.+)$", re.M)


def frontmatter_date(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    match = FM_DATE_RE.search(parts[1])
    if not match:
        return ""
    return match.group(1).strip().strip("\"'")


def main() -> None:
    today = date.today()
    by_timestamp: dict[str, list[str]] = defaultdict(list)
    total = 0
    failures: list[str] = []

    for path in sorted(POSTS_DIR.glob("**/*.md")):
        match = POST_NAME_RE.match(path.name)
        if not match:
            continue
        filename_date = match.group(1)
        rel = path.relative_to(ROOT).as_posix()
        total += 1

        parsed_date = date.fromisoformat(filename_date)
        if parsed_date > today:
            failures.append(
                f"future filename date: {rel} ({filename_date} > {today.isoformat()})"
            )

        fm_date = frontmatter_date(path)
        if fm_date and not fm_date.startswith(filename_date):
            failures.append(
                f"frontmatter date mismatch: {rel} filename={filename_date} frontmatter={fm_date}"
            )

        # A post with no front matter date falls back to the filename date, so
        # two of those on one day still collide.
        by_timestamp[fm_date or filename_date].append(rel)

    for timestamp, rels in sorted(by_timestamp.items()):
        if len(rels) > 1:
            failures.append(f"duplicate post timestamp: {timestamp}")
            failures.extend(f"  - {rel}" for rel in rels)

    if failures:
        print("Post date hygiene failed:")
        for failure in failures:
            print(failure)
        raise SystemExit(1)

    print(
        f"Post date hygiene passed: {total} posts, no duplicate timestamps, no future dates"
    )


if __name__ == "__main__":
    main()
