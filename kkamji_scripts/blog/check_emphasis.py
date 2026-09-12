#!/usr/bin/env python3
"""Report posts whose body carries no emphasis for the reader to anchor on.

Advisory only. A long post with nothing bolded gives the reader no entry point,
but a post with no judgement worth emphasising is allowed to stay plain. See
``docs/emphasis-and-bold.md`` for where bold belongs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The prompt-info footer is fixed boilerplate; its two bolds are not body emphasis.
FOOTER_BOLD = re.compile(r"\*\*(?:궁금하신 점이나[^*]*|Written with[^*]*)\*\*")
BOLD = re.compile(r"\*\*[^*\n]+\*\*")
CODE_FENCE = re.compile(r"```.*?```", re.S)

MIN_CHARS = 3000
MIN_BOLD = 3


def body_of(text: str) -> str:
    without_code = CODE_FENCE.sub("", text)
    return "\n".join(
        line for line in without_code.splitlines() if not line.startswith("|")
    )


def measure(path: Path) -> tuple[int, int]:
    body = body_of(path.read_text(encoding="utf-8"))
    bold = len(BOLD.findall(body)) - len(FOOTER_BOLD.findall(body))
    chars = len(re.sub(r"\s", "", body))
    return max(bold, 0), chars


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="_posts", help="directory to scan")
    parser.add_argument("--file", help="one post to scan")
    args = parser.parse_args()

    files = [Path(args.file)] if args.file else sorted(Path(args.root).rglob("*.md"))
    if not files:
        print("No Markdown posts found.", file=sys.stderr)
        return 2

    flagged = 0
    for path in files:
        bold, chars = measure(path)
        if chars >= MIN_CHARS and bold < MIN_BOLD:
            flagged += 1
            print(f"{path}: {chars} chars, {bold} bold - below {MIN_BOLD}")

    print(f"Scanned {len(files)} post(s). {flagged} below the emphasis floor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
