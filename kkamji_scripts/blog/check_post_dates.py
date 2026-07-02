#!/usr/bin/env python3
"""Check Jekyll post date hygiene.

Fails when:
- A filename date is later than today.
- Front matter date does not match the filename date.

Multiple posts may intentionally share the same filename date. Jekyll sorts posts by
front matter datetime, so same-day series posts should use different times.
"""

from __future__ import annotations

import re
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
    return match.group(1).strip().strip('"\'')


def main() -> None:
    today = date.today()
    checked = 0
    failures: list[str] = []

    for path in sorted(POSTS_DIR.glob("**/*.md")):
        match = POST_NAME_RE.match(path.name)
        if not match:
            continue
        checked += 1
        filename_date = match.group(1)
        rel = path.relative_to(ROOT).as_posix()

        parsed_date = date.fromisoformat(filename_date)
        if parsed_date > today:
            failures.append(f"future filename date: {rel} ({filename_date} > {today.isoformat()})")

        fm_date = frontmatter_date(path)
        if fm_date and not fm_date.startswith(filename_date):
            failures.append(f"frontmatter date mismatch: {rel} filename={filename_date} frontmatter={fm_date}")

    if failures:
        print("Post date hygiene failed:")
        for failure in failures:
            print(failure)
        raise SystemExit(1)

    print(f"Post date hygiene passed: {checked} posts, no future dates, filename dates match front matter dates")


if __name__ == "__main__":
    main()
