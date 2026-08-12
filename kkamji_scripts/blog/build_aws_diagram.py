#!/usr/bin/env python3
"""Compile a JSON spec into a Draw.io diagram in the AWS official style.

    python3 kkamji_scripts/blog/build_aws_diagram.py spec.json -o diagram.drawio

The spec says what the diagram means. This compiler owns every coordinate:
grid placement, container nesting, orthogonal routing, the title block and all
styles. Hand-computed geometry is what breaks diagrams, so nothing here is left
to the author.

Style comes from ``aws_diagram_tokens.py``, which mirrors the AWS Architecture
Icons deck. Containers are only drawn when the spec asks for them - the AWS
style does not imply a mandatory Cloud/Region/VPC/Subnet nesting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aws_diagram_tokens as T  # noqa: E402

SPEC_KEYS = {
    "schema_version",
    "id",
    "title",
    "subtitle",
    "frame",
    "layout",
    "containers",
    "nodes",
    "edges",
}
NODE_KEYS = {
    "id",
    "kind",
    "service",
    "label",
    "detail",
    "role",
    "col",
    "row",
    "colspan",
    "rowspan",
    "w",
    "h",
    "step",
    "step_at",
}
CONTAINER_KEYS = {"id", "kind", "label", "members", "dashed"}
EDGE_KEYS = {"id", "source", "target", "dashed", "bidirectional", "emphasis", "route"}
LAYOUT_KEYS = {"col_gap", "row_gap", "margin", "icon_cell_w"}

NODE_KINDS = {"service", "box", "text"}


class SpecError(Exception):
    pass


# --------------------------------------------------------------------------
# spec loading
# --------------------------------------------------------------------------
def _reject_unknown(obj: dict, allowed: set, where: str) -> None:
    extra = set(obj) - allowed
    if extra:
        raise SpecError(f"{where}: unknown key(s) {sorted(extra)}")


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    _reject_unknown(spec, SPEC_KEYS, "spec")
    for key in ("id", "title", "nodes"):
        if not spec.get(key):
            raise SpecError(f"spec: '{key}' is required")
    _reject_unknown(spec.get("layout", {}), LAYOUT_KEYS, "layout")

    seen: set[str] = set()
    for node in spec["nodes"]:
        _reject_unknown(node, NODE_KEYS, f"node {node.get('id')}")
        nid = node.get("id")
        if not nid:
            raise SpecError("node: 'id' is required")
        if nid in seen:
            raise SpecError(f"node {nid}: duplicate id")
        seen.add(nid)
        kind = node.setdefault("kind", "box")
        if kind not in NODE_KINDS:
            raise SpecError(f"node {nid}: unknown kind '{kind}'")
        if kind == "service":
            svc = node.get("service") or ""
            family, _, name = svc.partition(":")
            known = (
                name in T.KUBERNETES
                if family == "k8s"
                else name in T.GCP
                if family == "gcp"
                else svc in T.SERVICES and not _
            )
            if not known:
                raise SpecError(f"node {nid}: unknown service '{svc}'")
        if node.get("role") and node["role"] not in T.ROLES:
            raise SpecError(f"node {nid}: unknown role '{node['role']}'")
        for axis in ("col", "row"):
            if not isinstance(node.get(axis), int):
                raise SpecError(f"node {nid}: '{axis}' must be an integer")

    for cont in spec.get("containers", []):
        _reject_unknown(cont, CONTAINER_KEYS, f"container {cont.get('id')}")
        cid = cont.get("id")
        if not cid:
            raise SpecError("container: 'id' is required")
        if cid in seen:
            raise SpecError(f"container {cid}: id collides with a node")
        seen.add(cid)
        kind = cont.setdefault("kind", "plain")
        if kind != "plain" and kind not in T.GROUPS:
            raise SpecError(f"container {cid}: unknown kind '{kind}'")
        if not cont.get("members"):
            raise SpecError(f"container {cid}: 'members' is required")

    node_ids = {n["id"] for n in spec["nodes"]}
    cont_ids = {c["id"] for c in spec.get("containers", [])}
    for cont in spec.get("containers", []):
        for member in cont["members"]:
            if member not in node_ids and member not in cont_ids:
                raise SpecError(f"container {cont['id']}: unknown member '{member}'")

    for edge in spec.get("edges", []):
        _reject_unknown(edge, EDGE_KEYS, f"edge {edge.get('id')}")
        for end in ("source", "target"):
            if edge.get(end) not in node_ids:
                raise SpecError(f"edge: unknown {end} '{edge.get(end)}'")
        if edge["source"] == edge["target"]:
            raise SpecError(f"edge {edge['source']}: self-loop")
        if "label" in edge:
            raise SpecError("edge: labels are not allowed on connectors")
    return spec


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
class Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: float, y: float, w: float, h: float) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def union(self, other: "Rect") -> "Rect":
        x = min(self.x, other.x)
        y = min(self.y, other.y)
        return Rect(x, y, max(self.x2, other.x2) - x, max(self.y2, other.y2) - y)

    def inflate(self, left, top, right, bottom) -> "Rect":
        return Rect(
            self.x - left, self.y - top, self.w + left + right, self.h + top + bottom
        )


def node_label(node: dict) -> str:
    label = node.get("label", "")
    if node.get("detail"):
        return f"{label}\n{node['detail']}" if label else node["detail"]
    return label


def text_extent(text: str, font_size: int) -> tuple[float, float]:
    """Rough Helvetica metrics. Only used to reserve space, so it errs wide."""
    lines = text.split("\n") if text else [""]
    width = max((len(line) for line in lines), default=0) * font_size * 0.58
    return width, len(lines) * (font_size + 4)


def node_footprint(node: dict, icon_cell_w: float) -> tuple[float, float]:
    """Space the node occupies for layout and obstacle checks.

    A service icon is a fixed 48px square, but its caption sits underneath and
    runs as wide as the longest line, so the footprint follows the text.
    """
    if node["kind"] == "service":
        tw, th = text_extent(node_label(node), T.FONT_DETAIL)
        return (
            node.get("w", max(icon_cell_w, tw + 16)),
            node.get("h", T.ICON + 8 + th),
        )
    if node["kind"] == "text":
        tw, th = text_extent(node_label(node), T.FONT_DETAIL)
        return node.get("w", max(T.BOX_W, tw + 12)), node.get("h", max(24, th))
    tw, th = text_extent(node_label(node), T.FONT_DETAIL)
    return node.get("w", max(T.BOX_W, tw + 24)), node.get("h", max(T.BOX_H, th + 18))


def node_shape(node: dict, foot: Rect) -> Rect:
    """The drawn rectangle.

    A service icon is a 48px square. Its caption renders underneath, so the
    icon+caption block is what gets centred in the footprint - otherwise a node
    that spans extra rows would pin its icon to the top and leave the rest of
    the cell empty.
    """
    if node["kind"] == "service":
        _, th = text_extent(node_label(node), T.FONT_DETAIL)
        block = T.ICON + 8 + th
        return Rect(foot.cx - T.ICON / 2, foot.y + (foot.h - block) / 2, T.ICON, T.ICON)
    return Rect(foot.x, foot.y, foot.w, foot.h)


def node_block(node: dict, foot: Rect, shape: Rect) -> Rect:
    """The ink the node actually puts on the canvas.

    For a service this is the icon plus its caption, which is shorter than the
    grid cell whenever the node spans extra rows. Containers and obstacle checks
    use this so a wrapper hugs its contents instead of the reserved space.
    """
    if node["kind"] == "service":
        _, th = text_extent(node_label(node), T.FONT_DETAIL)
        return Rect(foot.x, shape.y, foot.w, T.ICON + 8 + th)
    return Rect(foot.x, foot.y, foot.w, foot.h)


class Layout:
    """Grid placement with container padding reserved at the cell boundaries."""

    def __init__(self, spec: dict) -> None:
        cfg = spec.get("layout", {})
        self.col_gap = cfg.get("col_gap", T.COL_GAP)
        self.row_gap = cfg.get("row_gap", T.ROW_GAP)
        self.margin = cfg.get("margin", T.MARGIN)
        self.icon_cell_w = cfg.get("icon_cell_w", 138)

        self.nodes = {n["id"]: n for n in spec["nodes"]}
        self.containers = {c["id"]: c for c in spec.get("containers", [])}
        self._resolve_membership()
        self._size_grid()
        self._reserve_container_padding()
        self._place(spec)
        self._build_badges()
        self._build_container_rects()
        self._fit_to_content()

    # -- membership -------------------------------------------------------
    def _resolve_membership(self) -> None:
        """Expand each container's members to the transitive set of node ids."""
        self.leaves: dict[str, set[str]] = {}

        def expand(cid: str, seen: frozenset) -> set[str]:
            if cid in seen:
                raise SpecError(f"container {cid}: membership cycle")
            if cid in self.leaves:
                return self.leaves[cid]
            out: set[str] = set()
            for member in self.containers[cid]["members"]:
                if member in self.nodes:
                    out.add(member)
                else:
                    out |= expand(member, seen | {cid})
            self.leaves[cid] = out
            return out

        for cid in self.containers:
            expand(cid, frozenset())

        # Nesting is whatever the spec declared: listing a container id in
        # another container's members nests it. Two containers can then wrap the
        # same nodes (Account around VPC around one instance), which a
        # leaf-set comparison could never tell apart.
        self.parent: dict[str, str | None] = {}
        for cid, cont in self.containers.items():
            for member in cont["members"]:
                if member in self.containers:
                    self.parent[member] = cid
        # Anything not nested explicitly falls back to the smallest container
        # that strictly contains its nodes.
        for cid, mine in self.leaves.items():
            if cid in self.parent:
                continue
            best, best_size = None, None
            for other, theirs in self.leaves.items():
                if other == cid or not mine < theirs:
                    continue
                if best_size is None or len(theirs) < best_size:
                    best, best_size = other, len(theirs)
            self.parent[cid] = best
        self.depth = {cid: self._depth(cid) for cid in self.containers}

    def _depth(self, cid: str) -> int:
        d, cur, seen = 0, self.parent.get(cid), {cid}
        while cur is not None:
            if cur in seen:
                raise SpecError(f"container {cid}: nesting cycle")
            seen.add(cur)
            d += 1
            cur = self.parent.get(cur)
        return d

    # -- grid -------------------------------------------------------------
    def _size_grid(self) -> None:
        self.col_w: dict[int, float] = {}
        self.row_h: dict[int, float] = {}
        spanning = []
        for node in self.nodes.values():
            w, h = node_footprint(node, self.icon_cell_w)
            cs, rs = node.get("colspan", 1), node.get("rowspan", 1)
            if cs > 1 or rs > 1:
                spanning.append((node, w, h, cs, rs))
                for c in range(node["col"], node["col"] + cs):
                    self.col_w.setdefault(c, 0)
                for r in range(node["row"], node["row"] + rs):
                    self.row_h.setdefault(r, 0)
                continue
            c, r = node["col"], node["row"]
            self.col_w[c] = max(self.col_w.get(c, 0), w)
            self.row_h[r] = max(self.row_h.get(r, 0), h)
        for node, w, h, cs, rs in spanning:
            cols = range(node["col"], node["col"] + cs)
            have = sum(self.col_w[c] for c in cols) + self.col_gap * (cs - 1)
            if w > have:
                for c in cols:
                    self.col_w[c] += (w - have) / cs
            rows = range(node["row"], node["row"] + rs)
            have = sum(self.row_h[r] for r in rows) + self.row_gap * (rs - 1)
            if h > have:
                for r in rows:
                    self.row_h[r] += (h - have) / rs

    def _reserve_container_padding(self) -> None:
        """Every container boundary widens the gap it sits on, so a nested box
        never has to overlap its neighbour to fit its own padding.

        Only containers that actually stack along the same line add up. Three
        sibling accounts side by side each need one header, not three, so the
        reservation is the worst single lane rather than the global sum.
        """
        self.span: dict[str, tuple[int, int, int, int]] = {}
        for cid in self.containers:
            members = [self.nodes[n] for n in self.leaves[cid]]
            self.span[cid] = (
                min(n["col"] for n in members),
                max(n["col"] + n.get("colspan", 1) - 1 for n in members),
                min(n["row"] for n in members),
                max(n["row"] + n.get("rowspan", 1) - 1 for n in members),
            )

        cols, rows = sorted(self.col_w), sorted(self.row_h)

        def lane_max(
            edge_idx: int, along, pad: float, vertical: bool
        ) -> dict[int, float]:
            out: dict[int, float] = {}
            for key in cols if vertical else rows:
                best = 0.0
                for lane in along:
                    total = 0.0
                    for sp in self.span.values():
                        if sp[edge_idx] != key:
                            continue
                        lo, hi = (sp[2], sp[3]) if vertical else (sp[0], sp[1])
                        if lo <= lane <= hi:
                            total += pad
                    best = max(best, total)
                out[key] = best
            return out

        self.pad_left = lane_max(0, rows, T.GROUP_PAD, True)
        self.pad_right = lane_max(1, rows, T.GROUP_PAD, True)
        self.pad_top = lane_max(2, cols, T.GROUP_HEADER, False)
        self.pad_bottom = lane_max(3, cols, T.GROUP_PAD, False)

        # A step badge sits above its node, so the row needs that height on top
        # of any container header. Without it the badge lands on the label.
        above, below = set(), set()
        for node in self.nodes.values():
            if node.get("step") is None:
                continue
            if "bottom" in node.get("step_at", "top-left"):
                below.add(node["row"] + node.get("rowspan", 1) - 1)
            else:
                above.add(node["row"])
        for row in above:
            self.pad_top[row] = self.pad_top.get(row, 0) + T.STEP - T.STEP_OVERLAP + 8
        for row in below:
            self.pad_bottom[row] = max(
                self.pad_bottom.get(row, 0),
                T.GROUP_PAD + T.STEP - T.STEP_OVERLAP + 8,
            )

    def _place(self, spec: dict) -> None:
        top = self.margin
        if spec.get("title"):
            top += T.TITLE_H
        if spec.get("subtitle"):
            top += T.SUBTITLE_H
        top += 18
        self.content_top = top

        self.col_x: dict[int, float] = {}
        cursor = self.margin + self.pad_left.get(min(self.col_w), 0)
        for c in sorted(self.col_w):
            if c != min(self.col_w):
                cursor += self.col_gap + self.pad_left.get(c, 0)
            self.col_x[c] = cursor
            cursor += self.col_w[c] + self.pad_right.get(c, 0)
        self.content_w = cursor

        self.row_y: dict[int, float] = {}
        cursor = top + self.pad_top.get(min(self.row_h), 0)
        for r in sorted(self.row_h):
            if r != min(self.row_h):
                cursor += self.row_gap + self.pad_top.get(r, 0)
            self.row_y[r] = cursor
            cursor += self.row_h[r] + self.pad_bottom.get(r, 0)
        self.content_h = cursor

        self.foot: dict[str, Rect] = {}
        self.shape: dict[str, Rect] = {}
        self.block: dict[str, Rect] = {}
        for nid, node in self.nodes.items():
            w, h = node_footprint(node, self.icon_cell_w)
            cs, rs = node.get("colspan", 1), node.get("rowspan", 1)
            cols = range(node["col"], node["col"] + cs)
            rows = range(node["row"], node["row"] + rs)
            cell_x = self.col_x[node["col"]]
            cell_w = sum(self.col_w[c] for c in cols) + self.col_gap * (cs - 1)
            cell_w += sum(
                self.pad_right.get(c, 0) + self.pad_left.get(c, 0)
                for c in list(cols)[1:]
            )
            cell_y = self.row_y[node["row"]]
            cell_h = sum(self.row_h[r] for r in rows) + self.row_gap * (rs - 1)
            cell_h += sum(
                self.pad_bottom.get(r, 0) + self.pad_top.get(r, 0)
                for r in list(rows)[1:]
            )
            if cs > 1 or rs > 1:
                w, h = max(w, cell_w), max(h, cell_h)
            # Service icons in one row sit on a common baseline the way the AWS
            # deck draws them: top-aligned, captions of different lengths
            # hanging below. Everything else centres in its cell.
            top_aligned = node["kind"] == "service" and rs == 1
            rect = Rect(
                cell_x + (cell_w - w) / 2,
                cell_y if top_aligned else cell_y + (cell_h - h) / 2,
                w,
                h,
            )
            self.foot[nid] = rect
            self.shape[nid] = node_shape(node, rect)
            self.block[nid] = node_block(node, rect, self.shape[nid])

    def _build_container_rects(self) -> None:
        self.crect: dict[str, Rect] = {}
        for cid in sorted(self.containers, key=lambda c: -self.depth[c]):
            parts = [self.block[nid] for nid in self.leaves[cid]]
            # Wrap the badges too, so the container label ends up above them
            # instead of underneath one.
            parts += [self.badge[n] for n in self.leaves[cid] if n in self.badge]
            parts += [
                self.crect[other]
                for other, parent in self.parent.items()
                if parent == cid and other in self.crect
            ]
            if not parts:
                raise SpecError(f"container {cid}: no members to wrap")
            rect = parts[0]
            for other in parts[1:]:
                rect = rect.union(other)
            self.crect[cid] = rect.inflate(
                T.GROUP_PAD, T.GROUP_HEADER, T.GROUP_PAD, T.GROUP_PAD
            )

    def _build_badges(self) -> None:
        """Numbered step badges straddle a corner, AWS-deck style."""
        self.badge: dict[str, Rect] = {}
        for nid, node in self.nodes.items():
            if node.get("step") is None:
                continue
            rect = self.shape[nid]
            where = node.get("step_at", "top-left")
            # Pinned to the element's top-left corner, overlapping it slightly,
            # the way the AWS deck places them. One rule for every node, so the
            # badges of a row line up. The badge clears the element's mid-height,
            # which is where incoming arrows land.
            over = T.STEP - T.STEP_OVERLAP
            dy = rect.h - T.STEP_OVERLAP if "bottom" in where else -over
            self.badge[nid] = Rect(rect.x - over, rect.y + dy, T.STEP, T.STEP)

    def _fit_to_content(self) -> None:
        """Shift everything so nothing sits outside the margin.

        A step badge hangs to the left of its node, so the leftmost node in a
        diagram pushes its badge past the canvas edge and the frame clips it.
        Measuring the real bounds afterwards is simpler than trying to predict
        the overhang while placing the grid.
        """
        rects = (
            list(self.block.values())
            + list(self.crect.values())
            + list(self.badge.values())
        )
        bounds = rects[0]
        for rect in rects[1:]:
            bounds = bounds.union(rect)
        dx = max(0.0, self.margin - bounds.x)
        dy = max(0.0, self.content_top - bounds.y)
        if dx or dy:
            for table in (self.foot, self.shape, self.block, self.crect, self.badge):
                for rect in table.values():
                    rect.x += dx
                    rect.y += dy
            bounds = Rect(bounds.x + dx, bounds.y + dy, bounds.w, bounds.h)
        for table in (self.foot, self.shape, self.block, self.crect, self.badge):
            for rect in table.values():
                rect.x, rect.y = round(rect.x), round(rect.y)
                rect.w, rect.h = round(rect.w), round(rect.h)
        self.bounds = bounds

    def widen_to(self, min_width: float) -> None:
        """Grow the canvas for a title wider than the drawing, keeping it centred.

        A tall narrow diagram can easily have a title twice its width; without
        this the title wraps over the subtitle.
        """
        current = self.bounds.x2 + self.margin
        if min_width <= current:
            return
        shift = (min_width - current) / 2
        for table in (self.foot, self.shape, self.block, self.crect, self.badge):
            for rect in table.values():
                rect.x += shift
        self.bounds = Rect(
            self.bounds.x + shift, self.bounds.y, self.bounds.w, self.bounds.h
        )
        self.canvas_width = min_width

    def gutters(self) -> list[float]:
        """Horizontal bands with no ink in them, usable as detour corridors."""
        rects = (
            list(self.block.values())
            + list(self.crect.values())
            + list(self.badge.values())
        )
        edges = sorted({r.y for r in rects} | {r.y2 for r in rects})
        out = []
        for lo, hi in zip(edges, edges[1:]):
            if hi - lo < 16:
                continue
            mid = (lo + hi) / 2
            if not any(r.y < mid < r.y2 for r in rects):
                out.append(round(mid))
        return out

    # -- obstacles --------------------------------------------------------
    def obstacles(self, skip: set[str]) -> list[Rect]:
        out = [r for nid, r in self.block.items() if nid not in skip]
        # A badge is never an anchor, so it stays an obstacle even for the
        # edges of the node it belongs to.
        out += list(self.badge.values())
        # A container's header strip carries its label, so an edge must not run
        # through it - unless the edge starts or ends inside that container, in
        # which case leaving upward has to cross it and there is nothing to
        # avoid.
        for cid, rect in self.crect.items():
            if self.leaves[cid] & skip:
                continue
            out.append(Rect(rect.x, rect.y, rect.w, T.GROUP_HEADER))
        return out


# --------------------------------------------------------------------------
# routing
# --------------------------------------------------------------------------
def _blocked(x1, y1, x2, y2, obstacles: list[Rect], slack: float = 6) -> bool:
    lo_x, hi_x = min(x1, x2) - slack, max(x1, x2) + slack
    lo_y, hi_y = min(y1, y2) - slack, max(y1, y2) + slack
    for o in obstacles:
        if o.x2 <= lo_x or o.x >= hi_x or o.y2 <= lo_y or o.y >= hi_y:
            continue
        return True
    return False


def route(
    src: Rect,
    dst: Rect,
    obstacles: list[Rect],
    prefer: str | None,
    src_bottom_free: bool = True,
    dst_bottom_free: bool = True,
    gutters: list[float] | None = None,
):
    """Return (anchors, waypoints). Never emits a diagonal segment.

    ``*_bottom_free`` is False for a service icon, whose caption hangs directly
    under the 48px square. An arrow leaving or arriving at that edge would run
    straight through its own label, so those anchors are taken off the table and
    the route comes in from a side instead.
    """
    overlap_y = min(src.y2, dst.y2) - max(src.y, dst.y)
    overlap_x = min(src.x2, dst.x2) - max(src.x, dst.x)

    if overlap_y > 12 and prefer != "vh" and prefer != "hv":
        y = (max(src.y, dst.y) + min(src.y2, dst.y2)) / 2
        if dst.cx >= src.cx:
            a = {
                "exitX": 1,
                "exitY": (y - src.y) / src.h,
                "entryX": 0,
                "entryY": (y - dst.y) / dst.h,
            }
            if not _blocked(src.x2, y, dst.x, y, obstacles):
                return a, []
        else:
            a = {
                "exitX": 0,
                "exitY": (y - src.y) / src.h,
                "entryX": 1,
                "entryY": (y - dst.y) / dst.h,
            }
            if not _blocked(dst.x2, y, src.x, y, obstacles):
                return a, []

    if overlap_x > 12 and prefer != "vh" and prefer != "hv":
        x = (max(src.x, dst.x) + min(src.x2, dst.x2)) / 2
        if dst.cy >= src.cy:
            a = {
                "exitX": (x - src.x) / src.w,
                "exitY": 1,
                "entryX": (x - dst.x) / dst.w,
                "entryY": 0,
            }
            if src_bottom_free and not _blocked(x, src.y2, x, dst.y, obstacles):
                return a, []
        else:
            a = {
                "exitX": (x - src.x) / src.w,
                "exitY": 0,
                "entryX": (x - dst.x) / dst.w,
                "entryY": 1,
            }
            if dst_bottom_free and not _blocked(x, dst.y2, x, src.y, obstacles):
                return a, []

    if overlap_x > 12 and not (src_bottom_free and dst_bottom_free):
        # Stacked service icons. The straight vertical would run down through
        # the source's own caption, so step out to one side and come back.
        for sx in (
            max(src.x2, dst.x2) + 26,
            min(src.x, dst.x) - 26,
        ):
            outward = sx > src.cx
            if _blocked(sx, src.cy, sx, dst.cy, obstacles):
                continue
            return (
                {
                    "exitX": 1 if outward else 0,
                    "exitY": 0.5,
                    "entryX": 1 if outward else 0,
                    "entryY": 0.5,
                },
                [(sx, src.cy), (sx, dst.cy)],
            )

    right = dst.cx >= src.cx
    down = dst.cy >= src.cy
    hv = (
        {
            "exitX": 1 if right else 0,
            "exitY": 0.5,
            "entryX": 0.5,
            "entryY": 0 if down else 1,
        },
        [(dst.cx, src.cy)],
        down or dst_bottom_free,
    )
    vh = (
        {
            "exitX": 0.5,
            "exitY": 1 if down else 0,
            "entryX": 0 if right else 1,
            "entryY": 0.5,
        },
        [(src.cx, dst.cy)],
        (not down) or src_bottom_free,
    )
    order = [hv, vh] if prefer != "vh" else [vh, hv]
    for anchors, points, anchor_ok in order:
        px, py = points[0]
        legs_clear = not _blocked(src.cx, src.cy, px, py, obstacles) and not _blocked(
            px, py, dst.cx, dst.cy, obstacles
        )
        if anchor_ok and legs_clear:
            return anchors, points

    # Nothing direct worked. Leave the row entirely, run along an empty band,
    # and come back in. This is what a long backward hop between two lanes
    # needs; a Z route inside the lane would cut through the boxes between.
    for gy in gutters or []:
        if min(src.cy, dst.cy) - 8 < gy < max(src.cy, dst.cy) + 8:
            sx = src.x - 24 if not right else src.x2 + 24
            legs = (
                not _blocked(src.cx, src.cy, sx, src.cy, obstacles)
                and not _blocked(sx, src.cy, sx, gy, obstacles)
                and not _blocked(sx, gy, dst.cx, gy, obstacles)
                and not _blocked(dst.cx, gy, dst.cx, dst.cy, obstacles)
            )
            if legs:
                return (
                    {
                        "exitX": 0 if not right else 1,
                        "exitY": 0.5,
                        "entryX": 0.5,
                        "entryY": 0 if gy < dst.cy else 1,
                    },
                    [(sx, src.cy), (sx, gy), (dst.cx, gy)],
                )

    # Z route through the corridor just before the target.
    mid = (src.x2 + dst.x) / 2 if right else (dst.x2 + src.x) / 2
    return (
        {
            "exitX": 1 if right else 0,
            "exitY": 0.5,
            "entryX": 0 if right else 1,
            "entryY": 0.5,
        },
        [(mid, src.cy), (mid, dst.cy)],
    )


def separate_lanes(routed: list, lay: "Layout") -> None:
    """Give every arrow of a fan-out (or fan-in) its own corridor.

    Two arrows leaving one icon for two boxes in the same column would otherwise
    share both legs and render as a single line with an arrowhead at each end.
    Each gets its own exit height and its own vertical leg in the gutter, so the
    branch is legible as two arrows.
    """
    for role, other in (("source", "target"), ("target", "source")):
        groups: dict[str, list[int]] = {}
        for idx, (edge, _, _) in enumerate(routed):
            groups.setdefault(edge[role], []).append(idx)

        for hub, members in groups.items():
            if len(members) < 2:
                continue
            hub_rect = lay.shape[hub]
            spokes = [lay.shape[routed[i][0][other]] for i in members]
            if not all(s.x >= hub_rect.x2 for s in spokes) and not all(
                s.x2 <= hub_rect.x for s in spokes
            ):
                continue  # not a clean horizontal fan; leave the router's answer
            rightward = spokes[0].x >= hub_rect.x2
            # A corridor may not land on a step badge, which hangs outside the
            # corner it belongs to.
            edges_of = [routed[i][0] for i in members]
            badged = [
                lay.badge[e[other]] for e in edges_of if e[other] in lay.badge
            ] + ([lay.badge[hub]] if hub in lay.badge else [])
            gutter_start = hub_rect.x2 if rightward else min(s.x2 for s in spokes)
            gutter_end = min(s.x for s in spokes) if rightward else hub_rect.x
            span = gutter_end - gutter_start
            if span < 40:
                continue

            def clear_corridor(x: float, y_from: float, y_to: float) -> float:
                """Nudge a corridor off any badge its vertical leg would cross."""
                lo, hi = min(y_from, y_to), max(y_from, y_to)
                for _ in range(8):
                    hit = next(
                        (
                            b
                            for b in badged
                            if b.x - 4 < x < b.x2 + 4 and b.y < hi and lo < b.y2
                        ),
                        None,
                    )
                    if hit is None:
                        return x
                    shifted = hit.x - 10 if rightward else hit.x2 + 10
                    if not gutter_start <= shifted <= gutter_end:
                        shifted = hit.x2 + 10 if rightward else hit.x - 10
                    if not gutter_start <= shifted <= gutter_end:
                        return x
                    x = shifted
                return x

            # A spoke on the hub's own line stays a straight arrow. Only the
            # ones that have to turn get a lane, otherwise the straight arrow
            # picks up an 8px jog for no reason.
            above, below, aligned = [], [], []
            for k, spoke in enumerate(spokes):
                if abs(spoke.cy - hub_rect.cy) < 12:
                    aligned.append(k)
                elif spoke.cy < hub_rect.cy:
                    above.append(k)
                else:
                    below.append(k)
            above.sort(key=lambda k: -spokes[k].cy)
            below.sort(key=lambda k: spokes[k].cy)
            turning = above + below
            if not turning:
                continue

            for k in aligned:
                edge = routed[members[k]][0]
                pair = {edge["source"], edge["target"]}
                y = hub_rect.cy
                if _blocked(gutter_start, y, gutter_end, y, lay.obstacles(pair)):
                    continue  # keep whatever the router worked out
                spoke = spokes[k]
                spoke_frac = round(min(1.0, max(0.0, (y - spoke.y) / spoke.h)), 4)
                if role == "source":
                    anchors = {
                        "exitX": 1 if rightward else 0,
                        "exitY": 0.5,
                        "entryX": 0 if rightward else 1,
                        "entryY": spoke_frac,
                    }
                else:
                    # The hub is the arrow's target, so the spoke owns the exit.
                    anchors = {
                        "exitX": 0 if rightward else 1,
                        "exitY": spoke_frac,
                        "entryX": 1 if rightward else 0,
                        "entryY": 0.5,
                    }
                routed[members[k]][1] = anchors
                routed[members[k]][2] = []

            for lane, k in enumerate(turning):
                spoke = spokes[k]
                side = above if k in above else below
                rank = side.index(k) + 1
                half = 0.5 / (len(side) + 1)
                frac = 0.5 - rank * half if k in above else 0.5 + rank * half
                frac = round(frac, 4)
                hub_y = hub_rect.y + hub_rect.h * frac
                mid = gutter_start + span * (lane + 1) / (len(turning) + 1)
                mid = clear_corridor(mid, hub_y, spoke.cy)
                anchors = {
                    "exitX": 1 if rightward else 0,
                    "exitY": frac,
                    "entryX": 0 if rightward else 1,
                    "entryY": 0.5,
                }
                points = [(mid, hub_y), (mid, spoke.cy)]
                if role == "target":
                    anchors = {
                        "exitX": 0 if rightward else 1,
                        "exitY": 0.5,
                        "entryX": 1 if rightward else 0,
                        "entryY": frac,
                    }
                    points = [(mid, spoke.cy), (mid, hub_y)]
                routed[members[k]][1] = anchors
                routed[members[k]][2] = points


# --------------------------------------------------------------------------
# styles
# --------------------------------------------------------------------------
def service_style(service: str) -> str:
    family, _, name = service.partition(":")
    if family == "k8s":
        shape = f"shape=mxgraph.kubernetes.icon;prIcon={T.KUBERNETES[name]}"
        colour = T.KUBERNETES_BLUE
    elif family == "gcp":
        stencil, colour = T.GCP[name]
        shape = f"shape=mxgraph.gcp2.{stencil}"
    else:
        res_icon, category = T.SERVICES[service]
        shape = f"shape=mxgraph.aws4.resourceIcon;resIcon={res_icon}"
        colour = T.CATEGORY[category]
    return (
        "sketch=0;outlineConnect=0;gradientColor=none;html=0;whiteSpace=nowrap;"
        f"fontSize={T.FONT_DETAIL};fontStyle=0;fontColor={T.INK};"
        "verticalLabelPosition=bottom;verticalAlign=top;align=center;"
        f"labelBackgroundColor=none;fillColor={colour};strokeColor=none;dashed=0;"
        f"aspect=fixed;{shape};"
    )


def container_style(kind: str, dashed_override: bool | None) -> str:
    if kind == "plain":
        dashed = 1 if dashed_override else 0
        return (
            "rounded=0;whiteSpace=wrap;html=0;"
            f"fillColor={T.PLAIN_GROUP_FILL};strokeColor={T.PLAIN_GROUP_STROKE};"
            f"fontColor={T.INK};fontSize={T.FONT_BODY};fontStyle=1;"
            f"align=left;verticalAlign=top;spacingLeft=10;spacingTop=4;"
            f"strokeWidth=1.25;dashed={dashed};"
            + ("dashPattern=6 6;" if dashed else "")
        )
    gr_icon, stroke, fill, dashed = T.GROUPS[kind]
    if dashed_override is not None:
        dashed = 1 if dashed_override else 0
    return (
        "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],"
        "[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]];"
        "outlineConnect=0;gradientColor=none;html=0;whiteSpace=wrap;"
        f"fontSize={T.FONT_BODY};fontStyle=0;container=0;pointerEvents=0;"
        f"collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;grIcon={gr_icon};"
        f"strokeColor={stroke};fillColor={fill};fontColor={T.INK};"
        f"verticalAlign=top;align=left;spacingLeft=32;dashed={dashed};"
    )


def box_style(role: str) -> str:
    fill, stroke = T.ROLES[role]
    return (
        "rounded=0;whiteSpace=wrap;html=0;"
        f"fillColor={fill};strokeColor={stroke};fontColor={T.INK};"
        f"fontSize={T.FONT_DETAIL};fontStyle=0;align=center;verticalAlign=middle;"
        "spacingLeft=6;spacingRight=6;strokeWidth=1.25;"
    )


def text_style(size: int, bold: bool, colour: str, align: str = "center") -> str:
    return (
        f"text;html=0;whiteSpace=wrap;fillColor=none;strokeColor=none;"
        f"fontColor={colour};fontSize={size};fontStyle={1 if bold else 0};"
        f"align={align};verticalAlign=middle;"
    )


def step_style() -> str:
    return (
        "rounded=0;whiteSpace=wrap;html=0;"
        f"fillColor={T.STEP_FILL};strokeColor={T.STEP_FILL};fontColor={T.INK_INVERSE};"
        f"fontSize={T.FONT_BODY};fontStyle=1;align=center;verticalAlign=middle;"
    )


def edge_style(edge: dict, anchors: dict) -> str:
    parts = [
        "edgeStyle=orthogonalEdgeStyle",
        "rounded=0",
        "html=0",
        f"strokeColor={T.EDGE_STROKE}",
        f"strokeWidth={1.5 if edge.get('emphasis') else 1.25}",
        "endArrow=classic",
        "endFill=1",
        "endSize=7",
        f"fontSize={T.FONT_DETAIL}",
        f"fontColor={T.INK}",
        "labelBackgroundColor=none",
        "jettySize=14",
    ]
    if edge.get("dashed"):
        parts += ["dashed=1", "dashPattern=6 6"]
    if edge.get("bidirectional"):
        parts += ["startArrow=classic", "startFill=1", "startSize=7"]
    for key, value in anchors.items():
        parts.append(f"{key}={round(value, 4) if isinstance(value, float) else value}")
    parts += ["exitDx=0", "exitDy=0", "entryDx=0", "entryDy=0"]
    return ";".join(parts) + ";"


def esc(text: str) -> str:
    return escape(str(text), {'"': "&quot;"}).replace("\n", "&#xa;")


# --------------------------------------------------------------------------
# emission
# --------------------------------------------------------------------------
def compile_spec(spec: dict) -> str:
    lay = Layout(spec)
    frame = spec.get("frame", True)

    banner = max(
        text_extent(spec.get("title", ""), T.FONT_TITLE)[0] * 1.08,
        text_extent(spec.get("subtitle", ""), T.FONT_BODY)[0],
    )
    lay.widen_to(banner + 2 * lay.margin)
    width = getattr(lay, "canvas_width", lay.bounds.x2 + lay.margin)
    height = lay.bounds.y2 + lay.margin
    cells: list[str] = []

    def cell(cid, value, style, r: Rect, parent="1"):
        cells.append(
            f'        <mxCell id="{esc(cid)}" value="{esc(value)}" style="{style}" '
            f'vertex="1" parent="{parent}">\n'
            f'          <mxGeometry x="{round(r.x, 2)}" y="{round(r.y, 2)}" '
            f'width="{round(r.w, 2)}" height="{round(r.h, 2)}" as="geometry" />\n'
            f"        </mxCell>"
        )

    if frame:
        cell(
            "frame",
            "",
            f"rounded=0;html=0;fillColor=none;strokeColor={T.EDGE_STROKE};"
            f"fontColor={T.INK};strokeWidth=1.25;",
            Rect(12, 12, width - 24, height - 24),
        )

    y = lay.margin
    if spec.get("title"):
        cell(
            "title",
            spec["title"],
            text_style(T.FONT_TITLE, True, T.INK),
            Rect(lay.margin, y, width - 2 * lay.margin, T.TITLE_H),
        )
        y += T.TITLE_H
    if spec.get("subtitle"):
        cell(
            "subtitle",
            spec["subtitle"],
            text_style(T.FONT_BODY, False, T.INK_MUTED),
            Rect(lay.margin, y, width - 2 * lay.margin, T.SUBTITLE_H),
        )

    # Containers outermost first so nested boxes paint on top.
    for cid in sorted(lay.containers, key=lambda c: lay.depth[c]):
        cont = lay.containers[cid]
        cell(
            cid,
            cont.get("label", ""),
            container_style(cont["kind"], cont.get("dashed")),
            lay.crect[cid],
        )

    for nid, node in lay.nodes.items():
        rect = lay.shape[nid]
        label = node_label(node)
        if node["kind"] == "service":
            cell(nid, label, service_style(node["service"]), rect)
        elif node["kind"] == "text":
            cell(nid, label, text_style(T.FONT_DETAIL, False, T.INK), rect)
        else:
            cell(nid, label, box_style(node.get("role", "surface")), rect)

    for nid, rect in lay.badge.items():
        cell(f"{nid}-step", lay.nodes[nid]["step"], step_style(), rect)

    routed = []
    for edge in spec.get("edges", []):
        src, dst = edge["source"], edge["target"]
        anchors, points = route(
            lay.shape[src],
            lay.shape[dst],
            lay.obstacles({src, dst}),
            edge.get("route"),
            src_bottom_free=lay.nodes[src]["kind"] != "service",
            dst_bottom_free=lay.nodes[dst]["kind"] != "service",
            gutters=lay.gutters(),
        )
        routed.append([edge, anchors, points])
    separate_lanes(routed, lay)

    for edge, anchors, points in routed:
        src, dst = edge["source"], edge["target"]
        eid = edge.get("id", f"{src}-to-{dst}")
        geom = '          <mxGeometry relative="1" as="geometry"'
        if points:
            geom += ' >\n            <Array as="points">\n'
            for px, py in points:
                geom += (
                    f'              <mxPoint x="{round(px, 2)}" y="{round(py, 2)}" />\n'
                )
            geom += "            </Array>\n          </mxGeometry>"
        else:
            geom += " />"
        cells.append(
            f'        <mxCell id="{esc(eid)}" style="{edge_style(edge, anchors)}" '
            f'edge="1" parent="1" source="{esc(src)}" target="{esc(dst)}">\n'
            f"{geom}\n"
            f"        </mxCell>"
        )

    body = "\n".join(cells)
    return f"""<mxfile host="kkamji-blog" type="device">
  <diagram id="{esc(spec["id"])}" name="{esc(spec.get("title", spec["id"]))}">
    <mxGraphModel dx="{int(width)}" dy="{int(height)}" grid="0" gridSize="10" guides="1" \
tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" \
pageWidth="{int(width)}" pageHeight="{int(height)}" math="0" shadow="0" background="#FFFFFF">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
{body}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        spec = load_spec(args.spec)
        xml = compile_spec(spec)
    except SpecError as exc:
        print(f"spec error: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(xml, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
