#!/usr/bin/env python3
"""Check that every numbered step badge sits in the same place.

    python3 kkamji_scripts/blog/audit_diagram_badges.py [dir]

Two things go wrong with step badges and neither shows up in the drawio
validator: a badge drifting to a different offset than its neighbours, and a
badge landing on the label of the container it sits inside. Both are visible
only in the raster, so this reads the geometry instead.

Exits non-zero if either is found.
"""

from __future__ import annotations

import collections
import pathlib
import re
import sys

LABEL_BAND = 28  # what a container label occupies at fontSize 13 plus spacing
CELL = re.compile(
    r'<mxCell id="([^"]+)"[^>]*?style="([^"]*)"[^>]*?vertex="1"[^>]*?>\s*'
    r'<mxGeometry x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)"'
)


def cells(text: str):
    for m in CELL.finditer(text):
        yield (m.group(1), m.group(2), *(float(v) for v in m.groups()[2:]))


def is_container(style: str) -> bool:
    if "mxgraph.aws4.group" in style:
        return True
    return (
        "align=left" in style and "verticalAlign=top" in style and "text;" not in style
    )


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "assets/img")
    overlaps: list[str] = []
    offsets: collections.Counter = collections.Counter()

    for path in sorted(root.rglob("*.drawio")):
        found = list(cells(path.read_text(encoding="utf-8")))
        badges = {c[0][:-5]: c for c in found if c[0].endswith("-step")}
        if not badges:
            continue
        nodes = {c[0]: c for c in found if not c[0].endswith("-step")}
        groups = [c for c in found if is_container(c[1])]
        for nid, b in badges.items():
            for g in groups:
                if (
                    g[2] <= b[2] + b[4]
                    and b[2] <= g[2] + g[4]
                    and g[3] < b[3] + b[5]
                    and b[3] < g[3] + LABEL_BAND
                ):
                    overlaps.append(f"{path}  {nid}-step sits on the '{g[0]}' label")
            node = nodes.get(nid)
            if node:
                offsets[(round(node[2] - b[2]), round(node[3] - b[3]))] += 1

    total = sum(offsets.values())
    print(f"{total} step badge(s) across {root}")
    for offset, count in sorted(offsets.items(), key=lambda kv: -kv[1]):
        print(f"  offset {offset}: {count}")
    if len(offsets) > 1:
        print("badges do not share one offset")
    for line in overlaps:
        print(f"  OVERLAP {line}")
    if overlaps or len(offsets) > 1:
        return 1
    print("all badges share one offset and none sit on a container label")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
