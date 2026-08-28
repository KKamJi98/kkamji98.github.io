#!/usr/bin/env python3
"""Post-process a drawio file produced by drawio-generate-diagram's build-drawio.py.

Spreads fan-out edge anchors along the side of a tall (rowspan) node so that
edges from/to nodes on different rows attach at their own row height instead
of piling onto the node's vertical center. This removes the 90-degree kinks a
center-anchored fan-out produces.

Usage:
    python3 postprocess_fanout_anchors.py <diagram.drawio> <node-id> [side]

side is "entry" (edges INTO the node) or "exit" (edges OUT OF the node).
Default: entry.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def spread(values: list[float]) -> list[float]:
    n = len(values)
    if n <= 1:
        return [0.5] * n
    return [round(i / (n - 1), 3) for i in range(n)]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    node_id = sys.argv[2]
    side = sys.argv[3] if len(sys.argv) > 3 else "entry"
    if side not in {"entry", "exit"}:
        print(f"unknown side: {side}", file=sys.stderr)
        return 2

    tree = ET.parse(path)
    root = tree.getroot()
    cells = root.findall(".//mxCell")

    attr = "entry" if side == "entry" else "exit"
    key_x, key_y = f"{attr}X", f"{attr}Y"
    other = "target" if side == "entry" else "source"

    matched = [c for c in cells if c.get("edge") == "1" and c.get(other) == node_id]
    # Reading order is not row order; sort by the opposite endpoint's geometry y
    # so the anchors increase top to bottom.
    def endpoint_y(cell: ET.Element) -> float:
        oid = cell.get("source" if side == "entry" else "target") or ""
        for c in cells:
            if c.get("id") == oid:
                g = c.find("mxGeometry")
                if g is not None:
                    return float(g.get("y", "0"))
        return 0.0

    matched.sort(key=endpoint_y)
    ys = spread([0.5] * len(matched))
    for cell, y in zip(matched, ys):
        style = cell.get("style", "")
        style = re.sub(rf"{key_x}=[^;]*", f"{key_x}=0" if attr == "entry" else f"{key_x}=1", style)
        style = re.sub(rf"{key_y}=[^;]*", f"{key_y}={y}", style)
        cell.set("style", style)

    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=False)
    print(f"spread {len(matched)} {side} anchors on {node_id}: {[f'{y}' for y in ys]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
