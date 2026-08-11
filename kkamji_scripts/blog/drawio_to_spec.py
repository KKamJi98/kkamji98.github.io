#!/usr/bin/env python3
"""Bootstrap an AWS-style spec from an existing .drawio file.

    python3 kkamji_scripts/blog/drawio_to_spec.py assets/img/aws/foo.drawio

Reads the current diagram, recovers what it *means* - the boxes, their grid
positions, which boxes wrap which, and the arrows between them - and writes
``foo.spec.json`` next to it.

The output is a starting point, not a finished diagram. Geometry is thrown away
and re-derived by ``build_aws_diagram.py``; what survives is content. Expect to
edit the result: pick service icons, choose container kinds, write the title and
subtitle, and add step numbers.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TITLE_IDS = {"title", "subtitle", "frame", "footnote", "legend"}


def style_of(cell: ET.Element) -> str:
    return cell.get("style") or ""


def geom_of(cell: ET.Element):
    g = cell.find("mxGeometry")
    if g is None:
        return None
    try:
        return (
            float(g.get("x", "nan")),
            float(g.get("y", "nan")),
            float(g.get("width", "0")),
            float(g.get("height", "0")),
        )
    except ValueError:
        return None


def clean(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value)
    text = re.sub(r"<[^>]+>", "", text)
    for entity, char in (
        ("&nbsp;", " "),
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
    ):
        text = text.replace(entity, char)
    return text.strip()


def cluster(values: list[float], tolerance: float) -> dict[float, int]:
    """Map each coordinate to an index, merging anything within tolerance."""
    out: dict[float, int] = {}
    index = -1
    previous = None
    for value in sorted(set(values)):
        if previous is None or value - previous > tolerance:
            index += 1
        out[value] = index
        previous = value
    return out


def convert(path: Path) -> dict:
    root = ET.parse(path).getroot()
    cells = root.iter("mxCell")

    vertices, edges = [], []
    for cell in cells:
        cid = cell.get("id") or ""
        if cell.get("edge") == "1":
            src, tgt = cell.get("source"), cell.get("target")
            if src and tgt:
                edges.append(
                    {
                        "id": cid,
                        "source": src,
                        "target": tgt,
                        "dashed": "dashed=1" in style_of(cell),
                    }
                )
            continue
        if cell.get("vertex") != "1" or cid in TITLE_IDS:
            continue
        geom = geom_of(cell)
        style = style_of(cell)
        if geom is None or geom[2] <= 0 or "text;" in style and geom[3] < 26:
            continue
        label = clean(cell.get("value"))
        vertices.append({"id": cid, "geom": geom, "label": label, "style": style})

    if not vertices:
        raise SystemExit(f"{path}: no usable vertices found")

    # A vertex that geometrically wraps others is a container.
    def wraps(outer, inner) -> bool:
        ox, oy, ow, oh = outer["geom"]
        ix, iy, iw, ih = inner["geom"]
        return (
            ox - 2 <= ix
            and oy - 2 <= iy
            and ox + ow + 2 >= ix + iw
            and oy + oh + 2 >= iy + ih
            and (ow * oh) > (iw * ih) * 1.05
        )

    contains = {
        v["id"]: [w["id"] for w in vertices if w is not v and wraps(v, w)]
        for v in vertices
    }
    container_ids = {vid for vid, kids in contains.items() if kids}
    leaves = [v for v in vertices if v["id"] not in container_ids]

    widths = [v["geom"][2] for v in leaves]
    heights = [v["geom"][3] for v in leaves]
    col_tol = max(24.0, min(widths) * 0.6) if widths else 40.0
    row_tol = max(20.0, min(heights) * 0.6) if heights else 40.0
    col_of = cluster([v["geom"][0] + v["geom"][2] / 2 for v in leaves], col_tol)
    row_of = cluster([v["geom"][1] + v["geom"][3] / 2 for v in leaves], row_tol)

    nodes = []
    for v in leaves:
        x, y, w, h = v["geom"]
        label, _, detail = v["label"].partition("\n")
        node = {
            "id": v["id"],
            "kind": "box",
            "label": label or v["id"],
            "col": col_of[x + w / 2],
            "row": row_of[y + h / 2],
        }
        if detail:
            node["detail"] = detail
        nodes.append(node)
    nodes.sort(key=lambda n: (n["row"], n["col"]))

    # Nest containers: a container's members are its direct children only.
    containers = []
    for cid in sorted(container_ids, key=lambda c: -len(contains[c])):
        direct = [
            k
            for k in contains[cid]
            if not any(k in contains[o] for o in contains[cid] if o in container_ids)
        ]
        containers.append(
            {
                "id": cid,
                "kind": "plain",
                "label": next(v["label"] for v in vertices if v["id"] == cid) or cid,
                "members": direct,
            }
        )

    leaf_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in leaf_ids and e["target"] in leaf_ids]
    for e in edges:
        if not e["dashed"]:
            del e["dashed"]

    spec = {
        "schema_version": 1,
        "id": path.stem,
        "title": "TODO state the claim, not the topic",
        "subtitle": "TODO one sentence of context, or delete this key",
    }
    if containers:
        spec["containers"] = containers
    spec["nodes"] = nodes
    if edges:
        spec["edges"] = edges
    return spec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("drawio", nargs="+", type=Path)
    ap.add_argument("--force", action="store_true", help="overwrite an existing spec")
    args = ap.parse_args()
    for src in args.drawio:
        out = src.with_suffix("").with_suffix(".spec.json")
        if out.exists() and not args.force:
            print(f"skip {out} (exists)")
            continue
        try:
            spec = convert(src)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"FAIL {src}: {exc}", file=sys.stderr)
            continue
        out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", "utf-8")
        n = len(spec["nodes"])
        c = len(spec.get("containers", []))
        e = len(spec.get("edges", []))
        print(f"{out}  nodes={n} containers={c} edges={e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
