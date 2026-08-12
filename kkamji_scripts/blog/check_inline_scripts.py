#!/usr/bin/env python3
"""Parse every inline <script> in a built site and fail if any is broken.

    JEKYLL_ENV=production bundle exec jekyll build -d /tmp/site_prod
    python3 kkamji_scripts/blog/check_inline_scripts.py /tmp/site_prod

Why this exists: in production `compress_html` collapses each page onto one
line. A `//` comment inside an inline script then swallows the rest of that
script, and the browser reports `SyntaxError: Unexpected end of input` while the
development build stays perfectly fine. Search silently stopped working that
way. Inline scripts must therefore use block comments only.

Requires node on PATH for the syntax check.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", re.S)
LINE_COMMENT = re.compile(r"(?<![:/])//")


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    if not root.is_dir():
        print(f"{root} is not a directory; build the site first", file=sys.stderr)
        return 2

    pages = sorted(root.rglob("*.html"))
    broken: list[str] = []
    hazards: list[str] = []
    checked = 0

    with tempfile.TemporaryDirectory() as tmp:
        probe = pathlib.Path(tmp) / "inline.js"
        for page in pages:
            text = page.read_text(encoding="utf-8", errors="replace")
            for attrs, body in SCRIPT.findall(text):
                if "json" in attrs.lower() or not body.strip():
                    continue
                checked += 1
                probe.write_text(body, encoding="utf-8")
                result = subprocess.run(
                    ["node", "--check", str(probe)], capture_output=True, text=True
                )
                if result.returncode != 0:
                    first = result.stderr.strip().splitlines()
                    reason = next(
                        (ln for ln in first if "Error" in ln), first[-1:] or [""]
                    )
                    broken.append(f"{page.relative_to(root)}: {reason}")
                if body.count("\n") == 0 and LINE_COMMENT.search(body):
                    hazards.append(
                        f"{page.relative_to(root)}: line comment in a one-line script"
                    )

    print(f"checked {checked} inline script(s) across {len(pages)} page(s)")
    for line in broken:
        print(f"  BROKEN {line}")
    for line in dict.fromkeys(hazards):
        print(f"  HAZARD {line}")
    if broken or hazards:
        return 1
    print("every inline script parses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
