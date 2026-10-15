#!/usr/bin/env python3
"""Author fixed-coordinate FHD SVG from the preserved semantic HTML fragments.

This is a repository authoring tool, not a browser or an automatic graph engine.
It uses declared rows, comparison columns and boundary boxes, then stores every
rectangle, text baseline and connector point directly in the inline SVG.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

WIDTH, HEIGHT = 1920, 1080
EDGE_WIDTH = 144
VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
SVG_BEGIN = "<!-- FHD artwork: generated from the preserved semantic source. -->"
SEMANTIC_BEGIN = '<div class="sd-semantic-source">'
FONT = "assets/fonts/deterministic-export/NotoSansKR[wght].ttf"
FIXED_LAYOUT_PROFILES = {
    "diagrams/static/aws/analytics-stack-03-distributed-sql-mpp.html": {
        "columns": {"root.0.1.4": 1}
    },
    "diagrams/static/kubernetes/metrics-server-collection.html": {
        "edge_widths": {"root.0.1": 224}
    },
    "diagrams/static/project/rememberme/budget_alarm_workflow.html": {
        "edge_widths": {"root.0.2": 192}
    },
    "diagrams/static/project/weasel/cicd.html": {"edge_widths": {"root.0.1": 192}},
    "diagrams/static/sap-c02/glue-catalog-lake-formation-access.html": {
        "columns": {"root.0.2.8.0.1": 2}
    },
    "diagrams/static/sap-c02/kinesis-efo-vs-shared-consumers.html": {
        "columns": {"root.0.2.4.0.1.1": 1, "root.0.2.4.1.1.1": 1}
    },
    "diagrams/static/sap-c02/modernization-database-target-selection.html": {
        "edge_widths": {"root.0.2.1.1": 224}
    },
    "diagrams/aws-certification-map.html": {"root_panels": True},
    "diagrams/static/ci-cd/ci-cd-study/jenkins-pipeline.html": {"root_panels": True},
    "diagrams/static/kubernetes/cilium/5w-bgp-control-plane-v2-architecture.html": {
        "root_panels": True
    },
    "diagrams/static/kubernetes/pod-identity-workflow.html": {
        "columns": {"root.0.2": 2}
    },
    "diagrams/static/ci-cd/jenkins/jenkins-operator/jenkins-operator-reconcile-walkthrough.html": {
        "phase_flows": {"root.0.1": 4}
    },
    "diagrams/static/sap-c02/asg-instance-lifecycle-hooks.html": {
        "phase_flows": {"root.0.1": 3}
    },
    "diagrams/static/sap-c02/config-evaluation-remediation.html": {
        "phase_flows": {"root.0.1.0.0.3": 2}
    },
}
NODE_CLASSES = {
    "sd-node",
    "sd-v2-setup",
    "sd-v2-config",
    "sd-v2-group-item",
}
EDGE_CLASSES = {"sd-arrow", "sd-v2-link", "sd-v2-down", "sd-v2-relation"}
HEAD_CLASSES = {
    "sd-title",
    "sd-label",
    "sd-lane-title",
    "sd-band-title",
    "sd-v2-section-title",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Font:
    """Read pinned TrueType advances without installing a font or a package."""

    def __init__(self, path):
        self.raw = path.read_bytes()
        tables = {}
        for i in range(struct.unpack_from(">H", self.raw, 4)[0]):
            tag, _, offset, length = struct.unpack_from(">4sIII", self.raw, 12 + i * 16)
            tables[tag] = self.raw[offset : offset + length]
        self.units = struct.unpack_from(">H", tables[b"head"], 18)[0]
        metrics = struct.unpack_from(">H", tables[b"hhea"], 34)[0]
        self.advances = [
            struct.unpack_from(">H", tables[b"hmtx"], i * 4)[0] for i in range(metrics)
        ]
        cmap = tables[b"cmap"]
        subtables = [
            struct.unpack_from(">HHI", cmap, 4 + i * 8)
            for i in range(struct.unpack_from(">H", cmap, 2)[0])
        ]
        chosen = next(
            offset
            for platform, encoding, offset in subtables
            if struct.unpack_from(">H", cmap, offset)[0] == 12
        )
        groups = struct.unpack_from(">I", cmap, chosen + 12)[0]
        self.glyphs = {}
        for i in range(groups):
            start, end, glyph = struct.unpack_from(">III", cmap, chosen + 16 + i * 12)
            self.glyphs.update(
                (code, glyph + code - start) for code in range(start, end + 1)
            )

    def width(self, text, size):
        return (
            sum(
                self.advances[min(self.glyphs.get(ord(c), 0), len(self.advances) - 1)]
                for c in text
            )
            * size
            / self.units
        )

    def wrap(self, text, width, size):
        lines = []
        for paragraph in text.split("\n"):
            remaining = paragraph.strip()
            while remaining:
                end = 0
                while (
                    end < len(remaining)
                    and self.width(remaining[: end + 1], size) <= width
                ):
                    end += 1
                if not end:
                    raise ValueError("text column cannot fit a single glyph")
                if end < len(remaining):
                    word = remaining.rfind(" ", 0, end + 1)
                    # Prefer a real word boundary even when it leaves a short
                    # line. Filling a card by splitting "LLM generation" into
                    # "LLM generati" / "on" is harder to read.
                    if word > 0:
                        end = word
                    else:
                        boundary = max(
                            remaining.rfind(mark, 0, end)
                            for mark in ("-", "_", ".", ":")
                        )
                        if boundary >= 0:
                            end = boundary + 1
                lines.append(remaining[:end].strip())
                remaining = remaining[end:].strip()
            if not paragraph.strip():
                lines.append("")
        return lines or [""]


class Element:
    def __init__(self, tag, attrs, parent, key):
        self.tag, self.attrs, self.parent, self.key = tag, dict(attrs), parent, key
        self.classes = set(self.attrs.get("class", "").split())
        self.children, self.parts = [], []

    def text(self):
        result = "".join(p.text() if isinstance(p, Element) else p for p in self.parts)
        return "\n".join(" ".join(line.split()) for line in result.split("\n")).strip()

    def descendants(self):
        for child in self.children:
            yield child
            yield from child.descendants()


class Parse(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Element("root", {}, None, "root")
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        parent = self.stack[-1]
        e = Element(tag, attrs, parent, parent.key + "." + str(len(parent.children)))
        parent.children.append(e)
        parent.parts.append(e)
        if tag == "br":
            parent.parts.append("\n")
        if tag not in VOID:
            self.stack.append(e)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, text):
        # Source indentation is not an authored blank text line. Explicit br
        # and pre content retain line breaks; ordinary HTML collapses them.
        if not any(e.tag == "pre" for e in self.stack):
            text = re.sub(r"\s+", " ", text)
        self.stack[-1].parts.append(text)


def source_fragment(raw):
    """Recover byte-for-byte source body after a previous generation."""
    if SEMANTIC_BEGIN not in raw:
        return raw
    opening, tail = raw.split(SEMANTIC_BEGIN, 1)
    body, _ = tail.rsplit("</div>\n" + SVG_BEGIN, 1)
    opening = opening.replace(" sd--fhd", "").replace(
        ' data-canvas-width="1920" data-canvas-height="1080"', ""
    )
    return opening + body + "</figure>\n"


class Layout:
    def __init__(self, font, label_size, detail_size, gap=24, padding=24, profile=None):
        self.font, self.label_size, self.detail_size = font, label_size, detail_size
        self.gap, self.padding = gap, padding
        self.profile = profile or {}
        self.group_bounds = {}
        self.boxes, self.connectors, self.texts, self.groups, self.images = (
            [],
            [],
            [],
            [],
            [],
        )

    def wrap(self, text, width, size, label=False):
        budget = self.profile.get(
            "bold_width_budget" if label else "regular_width_budget", 1
        )
        return self.font.wrap(text, width / budget, size)

    def icon(self, e):
        return next((c for c in e.descendants() if c.tag == "img"), None)

    def kind(self, e):
        c = e.classes
        if c & EDGE_CLASSES:
            return "edge"
        if c & NODE_CLASSES and any(
            child.classes & NODE_CLASSES for child in e.descendants()
        ):
            return "group"
        if (
            c & NODE_CLASSES
            or e.tag in ("td", "th", "pre", "aside")
            or "sd-reference" in c
        ):
            return "node"
        if c & HEAD_CLASSES or c & {"sd-detail", "sd-note", "sd-intro", "sd-caption"}:
            return "text"
        if e.tag == "img":
            return "image"
        if not e.children and e.text():
            return "text"
        return "group"

    def items(self, e):
        return [
            c
            for c in e.children
            if c.text() or self.kind(c) in ("edge", "image") or c.children
        ]

    def row(self, e, width):
        c = e.classes
        if e.key in self.profile.get("vertical_flows", []):
            return False
        items = self.items(e)
        # A literal sequence is a row only when each card retains at least
        # 220px. Nested narrow lanes remain vertical at every viewport width.
        atoms = [x for x in items if self.kind(x) != "edge"]
        sequence = c & {
            "sd-flow",
            "sd-stack",
            "sd-v2-rail",
            "sd-v2-request-row",
            "sd-v2-issuance-row",
        }
        pure = all(
            self.kind(x) == ("edge" if i % 2 else self.kind(x))
            and (self.kind(x) == "edge") == (i % 2 == 1)
            for i, x in enumerate(items)
        )
        minimum = (
            0
            if e.key in self.profile.get("flow_columns", {})
            else 1180
            if any(self.kind(x) == "group" for x in atoms)
            else 528
        )
        return bool(sequence and pure and len(atoms) >= 2 and width >= minimum)

    def flow_columns(self, width, children):
        key = children[0].parent.key if children else ""
        if key in self.profile.get("flow_columns", {}):
            return self.profile["flow_columns"][key]
        if any(self.kind(c) == "group" for c in children):
            return 2
        count = min(
            4,
            sum(self.kind(c) != "edge" for c in children),
            max(2, int((width + EDGE_WIDTH) / (220 + EDGE_WIDTH))),
        )
        parent = children[0].parent if children else None
        edge = self.edge_width(parent) if parent else EDGE_WIDTH
        minimum = 220
        for child in children:
            if self.kind(child) != "node":
                continue
            for element in [child, *child.descendants()]:
                size = (
                    self.label_size
                    if element.classes & HEAD_CLASSES
                    else self.detail_size
                )
                factor = self.profile.get(
                    "bold_width_budget"
                    if element.classes & HEAD_CLASSES
                    else "regular_width_budget",
                    1,
                )
                for part in element.parts:
                    if isinstance(part, str):
                        for word in re.findall(r"[A-Za-z][A-Za-z0-9]{7,}", part):
                            minimum = max(
                                minimum,
                                self.font.width(word, size) * factor
                                + 2 * self.padding
                                + (116 if self.icon(child) else 0),
                            )
        while count > 1 and (width - edge * (count - 1)) / count < minimum:
            count -= 1
        return count

    def edge_width(self, e):
        if e.key in self.profile.get("edge_widths", {}):
            return self.profile["edge_widths"][e.key]
        width = EDGE_WIDTH
        for child in e.children:
            if self.kind(child) == "edge":
                for word in re.findall(r"[A-Za-z][A-Za-z0-9]{7,}", child.text()):
                    width = max(
                        width,
                        self.font.width(word, self.detail_size)
                        * self.profile.get("regular_width_budget", 1)
                        + 24,
                    )
        return width

    def row_heights(self, e, inner, cards, columns, col):
        heights = []
        children = self.items(e)
        for start in range(0, len(cards), columns):
            subset = cards[start : start + columns]
            h = max(self.measure(c, col) for c in subset)
            for index in range(start, start + len(subset) - 1):
                edge = children[index * 2 + 1]
                if edge.key in self.profile.get("legend_edges", []):
                    continue
                label = (
                    self.wrap(
                        edge.text(), max(self.edge_width(e) - 8, 24), self.detail_size
                    )
                    if edge.text()
                    else []
                )
                h = max(h, 2 * (len(label) * self.detail_size * 1.35 + 12))
            heights.append(h)
        return heights

    def columns(self, e):
        if "sd-quality-record" in e.classes:
            return len(e.children)
        if e.key in self.profile.get("columns", {}):
            return self.profile["columns"][e.key]
        if e.tag == "tr":
            return len(e.children)
        if "sd-grid--three" in e.classes:
            return 3
        if e.classes & {"sd-grid", "sd-v2-compare", "sd-v2-fork"}:
            return 2
        if e.tag == "table" or e.tag in ("thead", "tbody"):
            return 1
        return 0

    def panel_items(self, e):
        prefix, panels, suffix, first = [], [], [], True
        for child in self.items(e):
            kind = self.kind(child)
            if kind == "text":
                (prefix if first else suffix).append(child)
            elif kind != "edge":
                panels.append(child)
                first = False
        return prefix, panels, suffix

    def measure_panels(self, e, width):
        prefix, panels, suffix = self.panel_items(e)
        col = (width - 160) / 2
        rows = [
            max(self.measure(c, col) for c in panels[i : i + 2])
            for i in range(0, len(panels), 2)
        ]
        return (
            sum(self.measure(c, width) + self.gap for c in prefix + suffix)
            + sum(rows)
            + 96 * (len(rows) - 1)
        )

    def phase_items(self, e):
        count = self.profile["phase_flows"][e.key]
        split = 2 * count - 1
        prefix = Element("div", {"class": "sd-flow"}, e, e.key + ".phase-prefix")
        prefix.children = e.children[:split]
        prefix.parts = list(prefix.children)
        edge, suffix = e.children[split], e.children[split + 1 :]
        if self.kind(edge) != "edge" or not suffix:
            raise ValueError("declared phase split does not match source")
        return prefix, edge, suffix

    def measure_phase(self, e, width):
        prefix, edge, suffix = self.phase_items(e)
        return (
            self.measure(prefix, width)
            + self.measure(edge, width)
            + sum(self.measure(c, width) for c in suffix)
            + self.gap * (len(suffix) + 1)
        )

    def lines(self, e, width):
        if self.kind(e) == "node":
            labels = [c for c in e.children if c.classes & {"sd-label", "sd-cert-copy"}]
            if labels:
                head = labels[0].text()
                if "sd-cert-copy" in labels[0].classes:
                    head = next(
                        (
                            c.text()
                            for c in labels[0].children
                            if "sd-label" in c.classes
                        ),
                        head,
                    )
                text = e.text()
                start = text.find(head)
                prefix = text[:start].strip() if start >= 0 else ""
                detail = text[start + len(head) :].strip() if start >= 0 else text
                # Numbered steps and comparison field names can precede the
                # bold label. Retain their original reading order.
                if prefix:
                    head = prefix + " " + head
            else:
                head, detail = e.text(), ""
            image = self.icon(e)
            icon_width = (
                96 if image and "sd-cert-badge" in image.classes else 64 if image else 0
            )
            text_width = width - 2 * self.padding - (icon_width + 20 if image else 0)
            return (
                self.wrap(head, text_width, self.label_size, label=True),
                self.wrap(detail, text_width, self.detail_size) if detail else [],
            )
        size = (
            36
            if "sd-title" in e.classes
            else self.label_size
            if e.classes & HEAD_CLASSES
            else self.detail_size
        )
        return self.wrap(
            e.text(), width, size, label=bool(e.classes & HEAD_CLASSES)
        ), []

    def measure(self, e, width):
        kind = self.kind(e)
        if e.tag == "figure" and self.profile.get("root_panels"):
            return self.measure_panels(e, width)
        if e.key in self.profile.get("phase_flows", {}):
            return self.measure_phase(e, width)
        if kind == "edge":
            return max(
                56,
                len(self.wrap(e.text(), max(width / 2 - 36, 60), self.detail_size))
                * (self.detail_size * 1.35)
                + 32,
            )
        if kind in ("node", "text"):
            head, detail = self.lines(e, width)
            if kind == "node":
                height = (
                    len(head) * self.label_size * 1.3
                    + len(detail) * self.detail_size * 1.35
                    + (12 if detail else 0)
                )
                image = self.icon(e)
                if image:
                    icon_width = 96 if "sd-cert-badge" in image.classes else 64
                    height = max(
                        height,
                        icon_width
                        * float(image.attrs.get("height", 1))
                        / float(image.attrs.get("width", 1)),
                    )
                return 2 * self.padding + height
            size = (
                36
                if "sd-title" in e.classes
                else self.label_size
                if e.classes & HEAD_CLASSES
                else self.detail_size
            )
            return len(head) * size * 1.35
        if kind == "image":
            return 96
        children = self.items(e)
        if not children:
            return 0
        pad = max(
            self.profile.get("group_insets", {}).get(e.key, 0),
            self.padding
            if e.classes
            & (
                {"sd-lane", "sd-band", "sd-v2-compare-lane", "sd-v2-group"}
                | NODE_CLASSES
            )
            else 0,
        )
        inner = width - 2 * pad
        if self.row(e, inner):
            cards = [c for c in children if self.kind(c) != "edge"]
            columns = self.flow_columns(inner - 64, children)
            col = (inner - 64 - self.edge_width(e) * (columns - 1)) / columns
            heights = self.row_heights(e, inner, cards, columns, col)
            tail = (
                self.measure(children[-1], inner) + self.gap
                if self.kind(children[-1]) == "edge"
                else 0
            )
            return 2 * pad + sum(heights) + 96 * (len(heights) - 1) + tail
        columns = self.columns(e)
        if columns:
            col = (inner - self.gap * (columns - 1)) / columns
            return (
                2 * pad
                + sum(
                    max(self.measure(c, col) for c in children[i : i + columns])
                    for i in range(0, len(children), columns)
                )
                + self.gap * ((len(children) - 1) // columns)
            )
        return (
            2 * pad
            + sum(self.measure(c, inner) for c in children)
            + self.gap * (len(children) - 1)
            + (72 if "sd-loop" in e.classes else 0)
        )

    def add_text(self, lines, x, y, size, width, key, label=False):
        for line in lines:
            self.texts.append(
                {
                    "source": key,
                    "text": line,
                    "x": round(x, 3),
                    "y": round(y + size, 3),
                    "size": size,
                    "width": round(
                        self.font.width(line, size)
                        * self.profile.get(
                            "bold_width_budget" if label else "regular_width_budget", 1
                        ),
                        3,
                    ),
                    "label": label,
                }
            )
            y += size * (1.3 if label else 1.35)
        return y

    def draw(self, e, x, y, width):
        height, kind = self.measure(e, width), self.kind(e)
        if e.tag == "figure" and self.profile.get("root_panels"):
            return self.draw_panels(e, x, y, width)
        if e.key in self.profile.get("phase_flows", {}):
            return self.draw_phase(e, x, y, width)
        if kind == "edge":
            return {
                "element": e,
                "bounds": [x, y, width, height],
                "nodes": [],
                "edges": [e],
            }
        if kind == "node":
            self.boxes.append(
                {
                    "source": e.key,
                    "label": e.text(),
                    "classes": sorted(e.classes),
                    "connector_role": e.attrs.get("data-connector-role"),
                    "connector_from": e.attrs.get("data-from"),
                    "connector_to": e.attrs.get("data-to"),
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                }
            )
            head, detail = self.lines(e, width)
            image = self.icon(e)
            tx = x + self.padding
            if image:
                icon_width = 96 if "sd-cert-badge" in image.classes else 64
                icon_height = (
                    icon_width
                    * float(image.attrs.get("height", 1))
                    / float(image.attrs.get("width", 1))
                )
                source = image.attrs.get("src", "")
                match = re.search(r'/assets/[^\s\'"}]+', source)
                if not match:
                    raise ValueError(
                        "image source needs explicit local mapping: " + source
                    )
                self.images.append(
                    {
                        "source": image.key,
                        "href": match.group(),
                        "x": tx,
                        "y": y + (height - icon_height) / 2,
                        "width": icon_width,
                        "height": icon_height,
                    }
                )
                tx += icon_width + 20
            t = self.add_text(
                head, tx, y + self.padding, self.label_size, width, e.key, True
            )
            self.add_text(
                detail, tx, t + (12 if detail else 0), self.detail_size, width, e.key
            )
            return {"element": e, "bounds": [x, y, width, height], "nodes": [e.key]}
        if kind == "text":
            head, _ = self.lines(e, width)
            size = (
                36
                if "sd-title" in e.classes
                else self.label_size
                if e.classes & HEAD_CLASSES
                else self.detail_size
            )
            self.add_text(
                head, x, y, size, width, e.key, bool(e.classes & HEAD_CLASSES)
            )
            return {"element": e, "bounds": [x, y, width, height], "nodes": []}
        if kind == "image":
            return {"element": e, "bounds": [x, y, width, height], "nodes": []}
        self.group_bounds[e.key] = {
            "source": e.key,
            "classes": sorted(e.classes),
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
        children = self.items(e)
        pad = max(
            self.profile.get("group_insets", {}).get(e.key, 0),
            self.padding
            if e.classes
            & (
                {"sd-lane", "sd-band", "sd-v2-compare-lane", "sd-v2-group"}
                | NODE_CLASSES
            )
            else 0,
        )
        if pad:
            self.groups.append(
                {
                    "source": e.key,
                    "classes": sorted(e.classes),
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                }
            )
        inner, rows = width - 2 * pad, []
        if self.row(e, inner):
            cards = [c for c in children if self.kind(c) != "edge"]
            columns = self.flow_columns(inner - 64, children)
            edge_width = self.edge_width(e)
            col = (inner - 64 - edge_width * (columns - 1)) / columns
            row_heights = self.row_heights(e, inner, cards, columns, col)
            py = y + pad
            for i, child in enumerate(children):
                if i == len(children) - 1 and self.kind(child) == "edge":
                    rows.append(
                        self.draw(
                            child,
                            x + pad,
                            y + height - pad - self.measure(child, inner),
                            inner,
                        )
                    )
                    continue
                card = i // 2
                row, column = divmod(card, columns)
                if i and i % (2 * columns) == 0:
                    py += row_heights[row - 1] + 96
                w = edge_width if self.kind(child) == "edge" else col
                px = (
                    x
                    + pad
                    + 32
                    + column * (col + edge_width)
                    + (col if self.kind(child) == "edge" else 0)
                )
                h = self.measure(child, w)
                rows.append(self.draw(child, px, py + (row_heights[row] - h) / 2, w))
        elif self.columns(e):
            columns = self.columns(e)
            col = (inner - self.gap * (columns - 1)) / columns
            py = y + pad
            for i in range(0, len(children), columns):
                subset = children[i : i + columns]
                h = max(self.measure(c, col) for c in subset)
                for j, child in enumerate(subset):
                    rows.append(
                        self.draw(child, x + pad + j * (col + self.gap), py, col)
                    )
                py += h + self.gap
        else:
            py = y + pad
            for child in children:
                rows.append(self.draw(child, x + pad, py, inner))
                py += self.measure(child, inner) + self.gap
        for i, row in enumerate(rows):
            if self.kind(row["element"]) != "edge":
                continue
            if i == 0 or i == len(rows) - 1:
                # Boundary-crossing/reference edges need named endpoint review;
                # do not turn missing endpoints into an invented edge.
                self.connectors.append(
                    {
                        "source": row["element"].key,
                        "label": row["element"].text(),
                        "bounds": row["bounds"],
                        "unresolved": "boundary endpoint requires explicit mapping",
                    }
                )
                continue
            previous, following = rows[i - 1], rows[i + 1]
            a, b = previous["bounds"], following["bounds"]
            horizontal = b[0] > a[0] + a[2] - 1
            if horizontal:
                points = [
                    [a[0] + a[2] + 12, a[1] + a[3] / 2],
                    [b[0] - 12, b[1] + b[3] / 2],
                ]
                label_width = max(24, b[0] - a[0] - a[2] - 8)
                tx, ty = (
                    (points[0][0] + points[1][0] - label_width) / 2,
                    min(points[0][1], points[1][1]) - self.detail_size - 12,
                )
            elif self.row(e, inner) and b[1] > a[1]:
                # The row transition is an explicit routed edge, not a change
                # of DOM order or an implied connection between adjacent rows.
                row_index = (i // 2) // columns
                middle = (
                    y + pad + sum(row_heights[: row_index + 1]) + 96 * row_index + 48
                )
                points = [
                    [a[0] + a[2] + 12, a[1] + a[3] / 2],
                    [x + width - pad - 8, a[1] + a[3] / 2],
                    [x + width - pad - 8, middle],
                    [x + pad + 8, middle],
                    [x + pad + 8, b[1] + b[3] / 2],
                    [b[0] - 12, b[1] + b[3] / 2],
                ]
                tx, ty, label_width = x + 40, middle - self.detail_size - 8, width - 80
            else:
                points = [
                    [a[0] + a[2] / 2, a[1] + a[3] + 12],
                    [b[0] + b[2] / 2, b[1] - 12],
                ]
                tx, ty = (
                    points[0][0] + 20,
                    (points[0][1] + points[1][1]) / 2 - self.detail_size / 2,
                )
                label_width = row["bounds"][2] / 2 - 36
            self.connectors.append(
                {
                    "source": row["element"].key,
                    "label": row["element"].text(),
                    "from": [previous["element"].key],
                    "to": [following["element"].key],
                    "points": points,
                    "both": "sd-arrow--both" in row["element"].classes,
                }
            )
            if row["element"].text():
                lines = self.wrap(row["element"].text(), label_width, self.detail_size)
                text_height = len(lines) * self.detail_size * 1.35
                if horizontal:
                    ty = min(points[0][1], points[-1][1]) - text_height - 12
                elif len(points) == 2:
                    ty = (points[0][1] + points[-1][1]) / 2 - text_height / 2
                self.add_text(
                    lines, tx, ty, self.detail_size, label_width, row["element"].key
                )
        return {
            "element": e,
            "bounds": [x, y, width, height],
            "nodes": [n for row in rows for n in row.get("nodes", [])],
        }

    def draw_panels(self, e, x, y, width):
        prefix, panels, suffix = self.panel_items(e)
        height, py = self.measure_panels(e, width), y
        for child in prefix:
            self.draw(child, x, py, width)
            py += self.measure(child, width) + self.gap
        col, positions = (width - 160) / 2, {}
        for i in range(0, len(panels), 2):
            subset = panels[i : i + 2]
            h = max(self.measure(c, col) for c in subset)
            for j, child in enumerate(subset):
                result = self.draw(child, x + 32 + j * (col + 96), py, col)
                positions[child.key] = result["bounds"]
            py += h + 96
        py -= 96
        for child in suffix:
            py += self.gap
            self.draw(child, x, py, width)
            py += self.measure(child, width)
        for i, child in enumerate(e.children):
            if self.kind(child) != "edge":
                continue
            if not i or i == len(e.children) - 1:
                self.connectors.append(
                    {
                        "source": child.key,
                        "label": child.text(),
                        "unresolved": "root edge needs explicit endpoints",
                    }
                )
                continue
            a, b = (
                positions.get(e.children[i - 1].key),
                positions.get(e.children[i + 1].key),
            )
            if not a or not b:
                self.connectors.append(
                    {
                        "source": child.key,
                        "label": child.text(),
                        "unresolved": "root edge needs explicit endpoints",
                    }
                )
                continue
            if b[0] > a[0]:
                sy, ty = a[1] + a[3] / 2, b[1] + b[3] / 2
                points = [[a[0] + a[2] + 12, sy], [b[0] - 12, ty]]
                tx, ty, label_width = a[0] + a[2] + 8, min(sy, ty) - 80, 80
            else:
                previous_bottom = max(
                    p[1] + p[3] for p in positions.values() if abs(p[1] - a[1]) < 0.01
                )
                sy, ty, mid = (
                    a[1] + a[3] / 2,
                    b[1] + b[3] / 2,
                    (previous_bottom + b[1]) / 2,
                )
                points = [
                    [a[0] + a[2] + 12, sy],
                    [x + width - 8, sy],
                    [x + width - 8, mid],
                    [x + 8, mid],
                    [x + 8, ty],
                    [b[0] - 12, ty],
                ]
                tx, ty, label_width = x + 40, mid - self.detail_size - 8, width - 80
            self.connectors.append(
                {
                    "source": child.key,
                    "label": child.text(),
                    "from": [e.children[i - 1].key],
                    "to": [e.children[i + 1].key],
                    "points": points,
                    "both": "sd-arrow--both" in child.classes,
                }
            )
            self.add_text(
                self.wrap(child.text(), label_width, self.detail_size)
                if child.text()
                else [],
                tx,
                ty,
                self.detail_size,
                label_width,
                child.key,
            )
        return {"element": e, "bounds": [x, y, width, height], "nodes": list(positions)}

    def draw_phase(self, e, x, y, width):
        prefix, edge, suffix = self.phase_items(e)
        height, prefix_height = (
            self.measure_phase(e, width),
            self.measure(prefix, width),
        )
        first = self.draw(prefix, x, y, width)
        edge_y = y + prefix_height + self.gap
        py = edge_y + self.measure(edge, width) + self.gap
        results = []
        for child in suffix:
            results.append(self.draw(child, x, py, width))
            py += self.measure(child, width) + self.gap
        source = prefix.children[-1]
        a = next((b for b in self.boxes if b["source"] == source.key), None)
        if a is None:
            raise ValueError("phase source must be an explicit node")
        b = results[0]["bounds"]
        sx, sy = a["x"] + a["width"] / 2, a["y"] + a["height"] + 12
        tx, ty = b[0] + b[2] / 2, b[1] - 12
        middle = edge_y + self.measure(edge, width) / 2
        self.connectors.append(
            {
                "source": edge.key,
                "label": edge.text(),
                "from": [source.key],
                "to": [suffix[0].key],
                "points": [[sx, sy], [sx, middle], [tx, middle], [tx, ty]],
                "both": "sd-arrow--both" in edge.classes,
            }
        )
        self.add_text(
            self.wrap(edge.text(), width / 2 - 40, self.detail_size)
            if edge.text()
            else [],
            x + width / 2 + 20,
            edge_y + 4,
            self.detail_size,
            width / 2 - 40,
            edge.key,
        )
        return {
            "element": e,
            "bounds": [x, y, width, height],
            "nodes": first["nodes"] + [n for r in results for n in r.get("nodes", [])],
        }

    def resolve_boundary_edges(self, figure):
        elements = {e.key: e for e in [figure, *figure.descendants()]}
        ids = {e.attrs["id"]: e for e in elements.values() if e.attrs.get("id")}
        boxes = {b["source"]: b for b in self.boxes + self.groups}

        def box(e):
            if e.key in boxes:
                return boxes[e.key]
            children = [boxes[c.key] for c in e.descendants() if c.key in boxes]
            if not children:
                return None
            return {
                "x": min(c["x"] for c in children),
                "y": min(c["y"] for c in children),
                "width": max(c["x"] + c["width"] for c in children)
                - min(c["x"] for c in children),
                "height": max(c["y"] + c["height"] for c in children)
                - min(c["y"] for c in children),
            }

        for edge in self.connectors:
            if "unresolved" not in edge:
                continue
            e = elements[edge["source"]]
            role, source, target = e.attrs.get("data-connector-role"), None, None
            if role == "continuation":
                siblings = e.parent.children
                source = siblings[siblings.index(e) - 1] if siblings.index(e) else None
                following = e.parent.parent.children
                index = following.index(e.parent)
                target = next(
                    (
                        c
                        for c in following[index + 1 :]
                        if self.kind(c) in ("group", "node")
                    ),
                    None,
                )
            elif role == "reference":
                source, target = (
                    ids.get(e.attrs.get("data-from")),
                    ids.get(e.attrs.get("data-to")),
                )
            elif "sd-v2-relation" in e.classes:
                siblings = e.parent.parent.children
                index = siblings.index(e.parent)
                if index:
                    source = next(
                        (
                            c
                            for c in siblings[index - 1].descendants()
                            if "sd-node--accent" in c.classes
                        ),
                        None,
                    )
                target = next(
                    (c for c in e.parent.children if "sd-node" in c.classes), None
                )
            a, b = box(source) if source else None, box(target) if target else None
            if not a or not b:
                continue
            if role == "reference":
                # The source names a remote incoming reference. Preserve that
                # declared relationship, without inventing a physical source bus.
                cx = b["x"] + b["width"] / 2
                points = [[cx, b["y"] - 36], [cx, b["y"] - 12]]
                edge["remote_reference"] = True
            else:
                sx, sy = a["x"] + a["width"] / 2, a["y"] + a["height"] + 12
                tx, ty = b["x"] + b["width"] / 2, b["y"] - 12
                mid = (sy + ty) / 2
                points = [[sx, sy], [sx, mid], [tx, mid], [tx, ty]]
            edge.update(
                {
                    "from": [source.key],
                    "to": [target.key],
                    "points": points,
                    "both": "sd-arrow--both" in e.classes,
                    "undirected": "sd-v2-relation" in e.classes,
                }
            )
            del edge["unresolved"]
            x, y, width, _height = edge["bounds"]
            lines = (
                self.wrap(e.text(), max(width - 40, 60), self.detail_size)
                if e.text()
                else []
            )
            self.add_text(
                lines, x + 20, y, self.detail_size, max(width - 40, 60), e.key
            )
        for e in elements.values():
            if "sd-loop" in e.classes and e.attrs.get("data-connector-role") == "loop":
                source, target = (
                    ids.get(e.attrs.get("data-from")),
                    ids.get(e.attrs.get("data-to")),
                )
                a, b, enclosure = (
                    box(source) if source else None,
                    box(target) if target else None,
                    box(e),
                )
                edge = {
                    "source": e.key + ".loop",
                    "label": e.attrs.get("aria-label", "반복"),
                    "unresolved": "loop endpoint requires explicit mapping",
                }
                if a and b and enclosure:
                    # A loop travels below its nodes. Routing across their
                    # middle would overwrite the row that it feeds back into.
                    enclosure = self.group_bounds.get(e.key, enclosure)
                    bottom = enclosure["y"] + enclosure["height"] - 40
                    right = enclosure["x"] + enclosure["width"] + 24
                    left = enclosure["x"] - 24
                    sx, sy = a["x"] + a["width"] + 12, a["y"] + a["height"] / 2
                    tx, ty = b["x"] - 12, b["y"] + b["height"] / 2
                    edge = {
                        "source": e.key + ".loop",
                        "label": e.attrs.get("aria-label", "반복"),
                        "from": [source.key],
                        "to": [target.key],
                        "points": [
                            [sx, sy],
                            [right, sy],
                            [right, bottom],
                            [left, bottom],
                            [left, ty],
                            [tx, ty],
                        ],
                        "meaning_bounds": [
                            enclosure["x"] + 24,
                            bottom + 10,
                            enclosure["width"] - 48,
                        ],
                    }
                self.connectors.append(edge)
            if "sd-v2-fork" in e.classes:
                request = e.parent
                source = next(
                    (
                        c
                        for c in request.descendants()
                        if "sd-node--accent" in c.classes
                        and c.parent.classes & {"sd-v2-request-row"}
                    ),
                    None,
                )
                a = box(source) if source else None
                for i, branch in enumerate(e.children):
                    target = next(
                        (c for c in branch.descendants() if "sd-node" in c.classes),
                        None,
                    )
                    b = box(target) if target else None
                    if a and b:
                        sx, sy = a["x"] + a["width"] / 2, a["y"] + a["height"] + 12
                        tx, ty = b["x"] + b["width"] / 2, b["y"] - 12
                        self.connectors.append(
                            {
                                "source": e.key + ".fork-" + str(i),
                                "from": [source.key],
                                "to": [target.key],
                                "label": branch.children[0].text(),
                                "points": [
                                    [sx, sy],
                                    [sx, (sy + ty) / 2],
                                    [tx, (sy + ty) / 2],
                                    [tx, ty],
                                ],
                            }
                        )


def svg_document(layout, figure, source_hash, instance=""):
    out = [
        f'<svg class="sd-fhd-artwork" xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080" aria-hidden="true" data-source-sha256="{source_hash}">',
        '<rect x="0" y="0" width="1920" height="1080" fill="#fff"/>',
    ]
    for g in layout.groups:
        warning = (
            "sd-node--warning" in g.get("classes", [])
            or "sd-lane--warning" in g.get("classes", [])
            or "sd-band--warning" in g.get("classes", [])
        )
        fill, border = ("#fffbeb", "#b45309") if warning else ("#f8fafc", "#cbd5e1")
        if g.get("relation_boundary"):
            fill, border = "none", "#64748b"
        out.append(
            f'<rect data-source="{g["source"]}" x="{g["x"]:.3f}" y="{g["y"]:.3f}" width="{g["width"]:.3f}" height="{g["height"]:.3f}" rx="16" fill="{fill}" stroke="{border}" stroke-width="2"/>'
        )
    for b in layout.boxes:
        warning = "sd-node--warning" in b["classes"]
        accent = "sd-node--accent" in b["classes"]
        border = "#b45309" if warning else "#0f766e" if accent else "#94a3b8"
        fill = "#fffbeb" if warning else "#f0fdfa" if accent else "#fff"
        dash = (
            ' stroke-dasharray="10 8"'
            if b.get("connector_role") == "reference-note"
            else ""
        )
        relation = "".join(
            f' {name}="{html.escape(value, quote=True)}"'
            for name, value in (
                ("data-connector-role", b.get("connector_role")),
                ("data-from", b.get("connector_from")),
                ("data-to", b.get("connector_to")),
            )
            if value
        )
        out.append(
            f'<rect data-node="{b["source"]}"{relation} x="{b["x"]:.3f}" y="{b["y"]:.3f}" width="{b["width"]:.3f}" height="{b["height"]:.3f}" rx="12" fill="{fill}" stroke="{border}" stroke-width="2"{dash}/>'
        )
    for edge in layout.connectors:
        if "points" not in edge:
            continue
        x1, y1 = edge["points"][-2]
        x2, y2 = edge["points"][-1]

        def arrowhead(tip, other, source=edge["source"]):
            dx, dy = tip[0] - other[0], tip[1] - other[1]
            length = math.hypot(dx, dy)
            if not length:
                raise ValueError("zero-length arrowhead segment: " + source)
            ux, uy = dx / length, dy / length
            base = (tip[0] - 10 * ux, tip[1] - 10 * uy)
            points = [
                tip,
                [base[0] - 6 * uy, base[1] + 6 * ux],
                [base[0] + 6 * uy, base[1] - 6 * ux],
            ]
            return " ".join(f"{x:.3f},{y:.3f}" for x, y in points)

        head = arrowhead([x2, y2], [x1, y1])
        route = " ".join(
            ("M" if i == 0 else "L") + f" {x:.3f} {y:.3f}"
            for i, (x, y) in enumerate(edge["points"])
        )
        out.append(
            f'<path data-edge="{edge["source"]}" data-from="{html.escape(" ".join(edge["from"]))}" data-to="{html.escape(" ".join(edge["to"]))}" d="{route}" fill="none" stroke="#475569" stroke-width="3"><title>{html.escape(edge.get("meaning", edge["label"] or "흐름"))}</title></path>'
        )
        if not edge.get("undirected"):
            out.append(
                f'<polygon data-arrowhead="{edge["source"]}" points="{head}" fill="#475569"/>'
            )
        if edge.get("both"):
            reverse = arrowhead(edge["points"][0], edge["points"][1])
            out.append(
                f'<polygon data-arrowhead="{edge["source"]}.reverse" points="{reverse}" fill="#475569"/>'
            )
    for image in layout.images:
        out.append(
            f'<image data-source="{image["source"]}" href="{html.escape(image["href"])}" x="{image["x"]:.3f}" y="{image["y"]:.3f}" width="{image["width"]:.3f}" height="{image["height"]:.3f}" preserveAspectRatio="xMidYMid meet"/>'
        )
    for text in layout.texts:
        weight = 700 if text["label"] else 400
        out.append(
            f'<text data-source="{text["source"]}" x="{text["x"]:.3f}" y="{text["y"]:.3f}" font-size="{text["size"]}" font-weight="{weight}" fill="#111827">{html.escape(text["text"])}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


def segment_crosses_text(a, b, text):
    """Intersect a finite painted segment with the interior of a text box.

    Checking only horizontal/vertical paths misses diagonal arrows through
    labels. The small inset avoids treating a box's empty outer margin as ink.
    """
    low, high = 0.0, 1.0
    bounds = (
        (text["x"] + 2, text["x"] + text["width"] - 2),
        (text["y"] - text["size"] + 2, text["y"] + text["size"] * 0.25 - 2),
    )
    for start, end, (minimum, maximum) in zip(a, b, bounds):
        delta = end - start
        if maximum <= minimum:
            return False
        if abs(delta) < 1e-9:
            if not minimum < start < maximum:
                return False
            continue
        entry, leave = (minimum - start) / delta, (maximum - start) / delta
        low, high = max(low, min(entry, leave)), min(high, max(entry, leave))
    return low < high


def check_layout(layout):
    issues = []
    for b in layout.boxes + layout.groups:
        if (
            min(b["x"], b["y"]) < 32
            or b["x"] + b["width"] > WIDTH - 32.01
            or b["y"] + b["height"] > HEIGHT - 32.01
        ):
            issues.append({"code": "outside-canvas", "source": b["source"]})
    for t in layout.texts:
        if (
            t["x"] < 32
            or t["x"] + t["width"] > WIDTH - 32.01
            or t["y"] > HEIGHT - 32.01
            or t["y"] - t["size"] < 32
        ):
            issues.append(
                {
                    "code": "text-outside-canvas",
                    "source": t["source"],
                    "text": t["text"],
                }
            )
        for b in layout.boxes:
            intersects = (
                min(t["x"] + t["width"], b["x"] + b["width"]) - max(t["x"], b["x"])
                > 0.1
                and min(t["y"] + t["size"] * 0.25, b["y"] + b["height"])
                - max(t["y"] - t["size"], b["y"])
                > 0.1
            )
            if intersects and t["source"] != b["source"]:
                issues.append(
                    {
                        "code": "text-overlaps-other-node",
                        "source": t["source"],
                        "node": b["source"],
                        "text": t["text"],
                    }
                )
    for i, a in enumerate(layout.boxes):
        for b in layout.boxes[i + 1 :]:
            if (
                min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
                > 0.1
                and min(a["y"] + a["height"], b["y"] + b["height"])
                - max(a["y"], b["y"])
                > 0.1
            ):
                issues.append(
                    {
                        "code": "node-overlap",
                        "source": a["source"],
                        "other": b["source"],
                    }
                )
    for i, a in enumerate(layout.texts):
        for b in layout.texts[i + 1 :]:
            if (
                min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]) > 1
                and min(a["y"] + a["size"] * 0.25, b["y"] + b["size"] * 0.25)
                - max(a["y"] - a["size"], b["y"] - b["size"])
                > 1
            ):
                issues.append(
                    {
                        "code": "text-overlap",
                        "source": a["source"],
                        "other": b["source"],
                    }
                )
    for group in layout.groups:
        for node in layout.boxes:
            if node["source"].startswith(group["source"] + ".") and (
                node["x"] < group["x"] - 0.1
                or node["y"] < group["y"] - 0.1
                or node["x"] + node["width"] > group["x"] + group["width"] + 0.1
                or node["y"] + node["height"] > group["y"] + group["height"] + 0.1
            ):
                issues.append(
                    {
                        "code": "node-outside-semantic-boundary",
                        "source": node["source"],
                        "group": group["source"],
                    }
                )
    for edge in layout.connectors:
        if "unresolved" in edge:
            issues.append(
                {
                    "code": "unresolved-edge",
                    "source": edge["source"],
                    "reason": edge["unresolved"],
                }
            )
        for point in edge.get("points", []):
            if (
                point[0] < 32
                or point[0] > WIDTH - 32
                or point[1] < 32
                or point[1] > HEIGHT - 32
            ):
                issues.append(
                    {
                        "code": "connector-outside-canvas",
                        "source": edge["source"],
                        "point": point,
                    }
                )
        for a, b in zip(edge.get("points", []), edge.get("points", [])[1:]):
            for text in layout.texts:
                if segment_crosses_text(a, b, text):
                    issues.append(
                        {
                            "code": "connector-crosses-text",
                            "source": edge["source"],
                            "text_source": text["source"],
                            "text": text["text"],
                        }
                    )
            for node in layout.boxes:
                if node["source"] in edge.get("from", []) + edge.get("to", []):
                    continue
                # All authored corridors are axis aligned except the explicit
                # fork/merge design. Check every straight corridor interior.
                x, y, w, h = node["x"], node["y"], node["width"], node["height"]
                horizontal = (
                    a[1] == b[1]
                    and y + 0.1 < a[1] < y + h - 0.1
                    and max(min(a[0], b[0]), x + 0.1)
                    < min(max(a[0], b[0]), x + w - 0.1)
                )
                vertical = (
                    a[0] == b[0]
                    and x + 0.1 < a[0] < x + w - 0.1
                    and max(min(a[1], b[1]), y + 0.1)
                    < min(max(a[1], b[1]), y + h - 0.1)
                )
                if horizontal or vertical:
                    issues.append(
                        {
                            "code": "connector-crosses-other-node",
                            "source": edge["source"],
                            "node": node["source"],
                        }
                    )
    return issues


class VisibleText(HTMLParser):
    """Independent original HTML data coverage, without the layout atom parser."""

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.data = []
        self.feed(source)

    def handle_data(self, text):
        self.data.append(text)


def visible_text_coverage(layout, original):
    expected = Counter(re.sub(r"\s+", "", "".join(VisibleText(original).data)))
    painted = Counter(
        re.sub(
            r"\s+",
            "",
            "".join(
                t["text"] for t in layout.texts if not t["source"].endswith(".meaning")
            ),
        )
    )
    missing, added = expected - painted, painted - expected
    return (
        [
            {
                "code": "original-visible-text-coverage",
                "missing": dict(missing),
                "added": dict(added),
            }
        ]
        if missing or added
        else []
    )


def ray_hits_box(point, direction, box):
    """A painted port direction must reach the declared rectangle in front."""
    low, high = 0.0, math.inf
    for p, d, start, extent in zip(
        point, direction, (box["x"], box["y"]), (box["width"], box["height"])
    ):
        if abs(d) < 1e-9:
            if not start <= p <= start + extent:
                return False
            continue
        a, b = (start - p) / d, (start + extent - p) / d
        low, high = max(low, min(a, b)), min(high, max(a, b))
    return high >= low and high >= 0


def semantic_check(layout, figure):
    """Check every visible label/detail/condition/image and original edge role."""
    issues, atoms = [], []

    def visit(e):
        kind = layout.kind(e)
        if kind in ("node", "text", "edge", "image"):
            atoms.append(e)
        else:
            for child in layout.items(e):
                visit(child)

    visit(figure)
    normal = lambda text: re.sub(r"\s+", "", text)
    for e in atoms:
        if e.text():
            painted = "".join(t["text"] for t in layout.texts if t["source"] == e.key)
            if normal(painted) != normal(e.text()):
                issues.append(
                    {
                        "code": "source-text-mismatch",
                        "source": e.key,
                        "expected": e.text(),
                        "painted": painted,
                    }
                )
        source_runs = " ".join(
            part
            for element in [e, *e.descendants()]
            for part in element.parts
            if isinstance(part, str)
        )
        for identifier in set(re.findall(r"[A-Za-z][A-Za-z0-9]{6,}", source_runs)):
            if not any(
                identifier in t["text"] for t in layout.texts if t["source"] == e.key
            ):
                issues.append(
                    {
                        "code": "source-identifier-split",
                        "source": e.key,
                        "identifier": identifier,
                    }
                )
        if layout.kind(e) == "edge" and not any(
            edge["source"] == e.key or edge.get("origin") == e.key
            for edge in layout.connectors
        ):
            issues.append({"code": "missing-source-edge", "source": e.key})
    elements = [figure, *figure.descendants()]
    named = {e.attrs["id"]: e.key for e in elements if e.attrs.get("id")}
    boxes = {b["source"]: b for b in layout.boxes + layout.groups}
    for element in elements:
        if element.attrs.get("data-connector-role") in ("reference-note", "loop"):
            continue
        if not all(element.attrs.get(key) for key in ("data-from", "data-to")):
            continue
        edge = next((c for c in layout.connectors if c["source"] == element.key), None)
        if not edge or "points" not in edge:
            continue
        for attr, point in zip(
            ("data-from", "data-to"), (edge["points"][0], edge["points"][-1])
        ):
            key = named.get(element.attrs[attr])
            box = boxes.get(key)
            if box is None:
                issues.append(
                    {
                        "code": "named-endpoint-not-painted",
                        "source": element.key,
                        "endpoint": attr,
                    }
                )
                continue
            distance = math.hypot(
                max(box["x"] - point[0], point[0] - box["x"] - box["width"], 0),
                max(box["y"] - point[1], point[1] - box["y"] - box["height"], 0),
            )
            if distance > 24.01:
                issues.append(
                    {
                        "code": "named-endpoint-disconnected",
                        "source": element.key,
                        "endpoint": attr,
                        "distance": round(distance, 3),
                    }
                )
            adjacent = edge["points"][1] if attr == "data-from" else edge["points"][-2]
            direction = [point[i] - adjacent[i] for i in range(2)]
            if not ray_hits_box(point, direction, box):
                issues.append(
                    {
                        "code": "named-endpoint-direction-mismatch",
                        "source": element.key,
                        "endpoint": attr,
                    }
                )
    for key, marker in layout.profile.get("legend_markers", {}).items():
        edge = next((e for e in layout.connectors if e["source"] == key), None)
        painted = [t for t in layout.texts if t["source"] == key + ".meaning"]
        legend = [t for t in layout.texts if t["source"] == key + ".legend.meaning"]
        if (
            edge is None
            or not edge.get("points")
            or len(painted) != 1
            or len(legend) != 1
            or painted[0]["text"] != marker
            or legend[0]["text"] != marker
            or min(
                math.hypot(painted[0]["x"] - p[0], painted[0]["y"] - p[1])
                for p in edge.get("points", [])
            )
            > 64
        ):
            issues.append({"code": "legend-edge-mapping-mismatch", "source": key})
    expected_images = {e.key for e in figure.descendants() if e.tag == "img"}
    if expected_images != {i["source"] for i in layout.images}:
        issues.append(
            {
                "code": "image-coverage-mismatch",
                "expected": sorted(expected_images),
                "actual": sorted(i["source"] for i in layout.images),
            }
        )
    for text in layout.texts:
        missing = sorted(
            {
                c
                for c in text["text"]
                if ord(c) not in layout.font.glyphs and not c.isspace()
            }
        )
        if missing:
            issues.append(
                {
                    "code": "pinned-font-missing-glyph",
                    "source": text["source"],
                    "characters": missing,
                }
            )
    return issues


def complete_group_boundaries(layout):
    """Paint every group used as an actual relation endpoint at its own bounds.

    These frames do not move any node, text, group, or relation. Transparent
    interiors preserve the existing lane colors and nested group boundaries.
    """
    painted = {item["source"] for item in layout.boxes + layout.groups}
    for edge in layout.connectors:
        for key in edge.get("from", []) + edge.get("to", []):
            if key in layout.group_bounds and key not in painted:
                layout.groups.append(
                    dict(layout.group_bounds[key], relation_boundary=True)
                )
                painted.add(key)


def complete_relation_labels(layout):
    """Name implicit sequence arrows without inventing a technical action."""
    for edge in layout.connectors:
        if "points" not in edge:
            continue
        if edge.get("meaning_at_target") and any(
            text["source"] in edge.get("to", [])
            and text["label"] and text["text"] == edge.get("meaning")
            for text in layout.texts
        ):
            continue
        keys = {edge["source"], edge.get("origin"), edge["source"] + ".meaning"}
        if any(t["source"] in keys for t in layout.texts):
            continue
        meaning = edge.get("meaning") or edge["label"] or "다음 단계"
        edge["meaning"] = meaning
        segments = list(zip(edge["points"], edge["points"][1:]))
        a, b = max(
            segments,
            key=lambda pair: (
                abs(pair[1][0] - pair[0][0]) + abs(pair[1][1] - pair[0][1])
            ),
        )
        horizontal = abs(b[0] - a[0]) >= abs(b[1] - a[1])
        if edge.get("meaning_bounds"):
            x, y, width = edge["meaning_bounds"]
            lines = layout.font.wrap(meaning, width, 14)
        elif horizontal:
            width = max(abs(b[0] - a[0]) - 8, 56)
            x = (a[0] + b[0] - width) / 2
            lines = layout.font.wrap(meaning, width, 14)
            y = min(a[1], b[1]) - len(lines) * 18.9 - 12
        else:
            x, width = b[0] + 20, max(80, min(500, WIDTH - b[0] - 84))
            lines = layout.font.wrap(meaning, width, 14)
            y = (a[1] + b[1]) / 2 - len(lines) * 18.9 / 2
        layout.add_text(lines, x, y, 14, width, edge["source"] + ".meaning")


def manual_relation_fixes(layout, figure, include):
    """Source-backed relations that an HTML grid/sequence alone cannot paint."""
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    boxes = {b["source"]: b for b in layout.boxes}

    def fork(source, targets, key, labels, bus=None):
        a = boxes[source]
        sx = a["x"] + a["width"] / 2
        sy = a["y"] + a["height"] + 12
        ty = min(boxes[t]["y"] for t in targets) - 12
        middle = bus if bus is not None else (sy + ty) / 2
        for index, target in enumerate(targets):
            b = boxes[target]
            tx = b["x"] + b["width"] / 2
            layout.connectors.append(
                {
                    "source": key + "." + str(index),
                    "label": elements[labels[index]].text(),
                    "origin": labels[index],
                    "from": [source],
                    "to": [target],
                    "points": [[sx, sy], [sx, middle], [tx, middle], [tx, b["y"] - 12]],
                }
            )

    if include.endswith("litellm-virtual-key-flow.html"):
        for index in range(2):
            edge = next(
                e
                for e in layout.connectors
                if e["source"] == f"root.0.2.2.fork-{index}"
            )
            # The fork uses the clear strip above both branch headings.
            bus = edge["points"][0][1] + 2
            edge["points"][1][1] = edge["points"][2][1] = bus
            edge["origin"] = f"root.0.2.2.{index}.0"
    elif include.endswith("openid-connect-authorization-code-flow-simplied.html"):
        for text in layout.texts:
            if text["source"] == "root.0.1.9":
                text["x"] = 450
    elif include.endswith("kubernetes-architecture-overview.html"):
        api = boxes["root.0.1.1.0"]
        for index in range(3):
            edge = next(
                e for e in layout.connectors if e["source"] == f"root.0.1.1.1.{index}.0"
            )
            target = boxes[f"root.0.1.1.1.{index}.1"]
            x = target["x"] + target["width"] - 12
            edge["points"] = [[x, api["y"] + api["height"] + 12], [x, target["y"] - 12]]
            edge.pop("remote_reference", None)
        cloud = boxes["root.0.1.1.1.3.1"]
        edge = next(e for e in layout.connectors if e["source"] == "root.0.1.1.1.3.0")
        sy, ty = api["y"] + api["height"] / 2, cloud["y"] + cloud["height"] / 2
        edge["points"] = [
            [api["x"] - 12, sy],
            [48, sy],
            [48, ty],
            [cloud["x"] - 12, ty],
        ]
        edge.pop("remote_reference", None)
        provider = boxes["root.0.3.1.1.1"]
        edge = next(e for e in layout.connectors if e["source"] == "root.0.3.1.1.0")
        ty = provider["y"] + provider["height"] / 2
        edge["points"] = [
            [cloud["x"] + cloud["width"] + 12, sy := cloud["y"] + cloud["height"] / 2],
            [1872, sy],
            [1872, ty],
            [provider["x"] + provider["width"] + 12, ty],
        ]
        edge.pop("remote_reference", None)
    elif include.endswith("vault-secrets-operator.html"):
        controller = boxes["root.0.3.1.2"]
        sy = controller["y"] + controller["height"] + 12
        bus = next(
            g["y"] + g["height"] + 8 for g in layout.groups if g["source"] == "root.0.3"
        )
        vault = boxes["root.0.4.0.1.1"]
        edge = next(e for e in layout.connectors if e["source"] == "root.0.4.0.0")
        vx = vault["x"] + vault["width"] + 12
        vy = vault["y"] + vault["height"] / 2
        edge["points"] = [
            [controller["x"] + 48, sy],
            [controller["x"] + 48, bus],
            [vx + 12, bus],
            [vx + 12, vy],
            [vx, vy],
        ]
        edge.pop("remote_reference", None)
        for index, source_x in [(1, controller["x"] + 248), (2, controller["x"] + 668)]:
            secret = boxes[f"root.0.4.{index}.1.1.0"]
            edge = next(
                e for e in layout.connectors if e["source"] == f"root.0.4.{index}.0"
            )
            x = secret["x"] + secret["width"] - 12
            edge["points"] = [
                [source_x, sy],
                [source_x, bus],
                [x, bus],
                [x, secret["y"] - 12],
            ]
            edge.pop("remote_reference", None)
            pod = boxes[f"root.0.4.{index}.1.1.2"]
            target = boxes[f"root.0.4.{index}.3.1"]
            edge = next(
                e for e in layout.connectors if e["source"] == f"root.0.4.{index}.2"
            )
            edge["from"], edge["to"] = [pod["source"]], [target["source"]]
            edge["points"] = [[x, pod["y"] + pod["height"] + 12], [x, target["y"] - 12]]
    elif include.endswith("dns-global-traffic-decision-layers.html"):
        cloud, origin = boxes["root.0.2.2.1"], boxes["root.0.2.2.3.1"]
        edge = next(e for e in layout.connectors if e["source"] == "root.0.2.2.3.0")
        x = cloud["x"] + cloud["width"] + 24
        sy, ty = cloud["y"] + cloud["height"] / 2, origin["y"] + origin["height"] / 2
        edge["points"] = [
            [cloud["x"] + cloud["width"] + 12, sy],
            [x, sy],
            [x, ty],
            [origin["x"] + origin["width"] + 12, ty],
        ]
        edge.pop("remote_reference", None)
    elif include.endswith("datasync-agent-requirement.html"):
        for lane, count, edge_key in [
            ("root.0.1.0.1", 5, "root.0.1.0.1.5"),
            ("root.0.1.1.1", 4, "root.0.1.1.1.4"),
        ]:
            candidates = [boxes[lane + "." + str(i)] for i in range(count)]
            x = min(b["x"] for b in candidates)
            y = min(b["y"] for b in candidates)
            frame = {
                "source": lane + ".alternatives",
                "classes": [],
                "x": x - 4,
                "y": y - 4,
                "width": max(b["x"] + b["width"] for b in candidates) - x + 8,
                "height": max(b["y"] + b["height"] for b in candidates) - y + 8,
                "relation_boundary": True,
            }
            layout.groups.append(frame)
            edge = next(e for e in layout.connectors if e["source"] == edge_key)
            edge["from"] = [frame["source"]]
    elif include.endswith("modernization-strangler-route-switch.html"):
        fork(
            "root.0.1.4",
            ["root.0.2.0.1", "root.0.2.1.1.0"],
            "route-choice",
            ["root.0.2.0.0", "root.0.2.1.0"],
            bus=boxes["root.0.1.4"]["y"] + boxes["root.0.1.4"]["height"] + 14,
        )
    elif include.endswith("transitive-routing-boundaries.html"):
        prefix = "root.0.1.1.2"
        for box in layout.boxes:
            if box["source"].startswith(prefix):
                box["y"] += 64
        for text in layout.texts:
            if text["source"].startswith(prefix):
                text["y"] += 64
        group = next(g for g in layout.groups if g["source"] == "root.0.1.1")
        group["height"] += 64
        fork(
            "root.0.1.1.1.4",
            [prefix + ".0", prefix + ".1", prefix + ".2"],
            "tgw-routes",
            ["root.0.1.1.0"] * 3,
        )
    elif include.endswith(
        ("spring-01-request-flow.html", "spring-05-dispatcherservlet-sequence.html")
    ):
        edge = next(e for e in layout.connectors if e["source"] == "root.0.1.1")
        target = boxes["root.0.1.2.1.0"]
        a = boxes["root.0.1.0"]
        sy = a["y"] + a["height"] / 2
        ty = target["y"] + target["height"] / 2
        edge.update(
            to=[target["source"]],
            points=[
                [a["x"] + a["width"] + 12, sy],
                [976, sy],
                [976, ty],
                [target["x"] - 12, ty],
            ],
        )
        if include.endswith("spring-05-dispatcherservlet-sequence.html"):
            captions = [t for t in layout.texts if t["source"] == "root.0.1.1"]
            caption_x = 976 - max(t["width"] for t in captions) - 24
            for text in captions:
                text["x"] = round(caption_x, 3)
                text["y"] -= 120
            edge = next(e for e in layout.connectors if e["source"] == "root.0.1.3")
            source = boxes["root.0.1.2.1.6"]
            target = boxes["root.0.1.4"]
            source_point = [
                source["x"] + source["width"] + 12,
                source["y"] + source["height"] / 2,
            ]
            old = edge["points"]
            edge.update(
                {
                    "from": [source["source"]],
                    "points": [source_point, [old[1][0], source_point[1]], *old[2:]],
                }
            )
    elif include.endswith("spring-16-entity-states.html"):
        for box in layout.boxes:
            if box["source"].startswith("root.0.1.3."):
                box["y"] += 40
        for text in layout.texts:
            if text["source"].startswith("root.0.1.3."):
                text["y"] += 40
        for group in layout.groups:
            if group["source"].startswith("root.0.1.3."):
                group["y"] += 40
        for edge in layout.connectors:
            if edge["source"].startswith("root.0.1.3."):
                for point in edge.get("points", []):
                    point[1] += 40
        fork(
            "root.0.1.2",
            ["root.0.1.3.0.1.0", "root.0.1.3.1.1.0", "root.0.1.3.2.1.0"],
            "managed-transition",
            ["root.0.1.3.0.0", "root.0.1.3.1.0", "root.0.1.3.2.0"],
        )


def security_layout(font, figure):
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    layout = Layout(
        font,
        22,
        18,
        16,
        16,
        {
            "flow_columns": {"root.0.1.pipeline": 3},
            "bold_width_budget": 1.25,
            "regular_width_budget": 1.12,
        },
    )
    layout.draw(elements["root.0.0"], 64, 64, 1792)
    sequence = Element("div", {"class": "sd-flow"}, figure, "root.0.1.pipeline")
    sequence.children = elements["root.0.1"].children[:9]
    sequence.parts = list(sequence.children)
    # The explicit profile applies to the preserved child parent's key.
    layout.profile["flow_columns"]["root.0.1"] = 3
    layout.draw(sequence, 64, 200, 1792)
    layout.draw(elements["root.0.1.9"], 64, 792, 1792)
    boxes = {b["source"]: b for b in layout.boxes}
    a = boxes["root.0.1.8"]
    sx = a["x"] + a["width"] / 2
    for i in range(2):
        key = "root.0.1.9." + str(i) + ".1.0"
        b = boxes[key]
        tx = b["x"] + b["width"] / 2
        label = elements["root.0.1.9." + str(i) + ".0"].text()
        layout.connectors.append(
            {
                "source": "security-result." + str(i),
                "from": [a["source"]],
                "to": [key],
                "label": label,
                "points": [
                    [sx, a["y"] + a["height"] + 12],
                    [sx, 732],
                    [tx, 732],
                    [tx, b["y"] - 12],
                ],
                "meaning_bounds": [tx - 80, 752, 160],
            }
        )
    return layout


def alarm_layout(font, figure):
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    layout = Layout(
        font,
        22,
        18,
        16,
        16,
        {
            "bold_width_budget": 1.25,
            "regular_width_budget": 1.12,
            "vertical_flows": ["root.0.1.6.0.1", "root.0.1.6.1.1"],
            "columns": {"root.0.1.6.0.1.2": 2},
        },
    )
    layout.draw(elements["root.0.0"], 64, 64, 1792)
    for key, x in [("root.0.1.0", 64), ("root.0.1.2", 704), ("root.0.1.4", 1344)]:
        layout.draw(elements[key], x, 160, 480)
    boxes = {b["source"]: b for b in layout.boxes}
    for key, a, b in [
        ("root.0.1.1", "root.0.1.0", "root.0.1.2"),
        ("root.0.1.3", "root.0.1.2", "root.0.1.4"),
    ]:
        aa, bb = boxes[a], boxes[b]
        cy = aa["y"] + aa["height"] / 2
        layout.connectors.append(
            {
                "source": key,
                "label": "",
                "from": [a],
                "to": [b],
                "points": [[aa["x"] + aa["width"] + 12, cy], [bb["x"] - 12, cy]],
            }
        )
    for key, x in [("root.0.1.6.0", 64), ("root.0.1.6.1", 1008)]:
        layout.draw(elements[key], x, 420, 848)
    layout.draw(elements["root.0.1.8"], 64, 928, 1792)
    boxes = {b["source"]: b for b in layout.boxes}
    a = boxes["root.0.1.4"]
    sx = a["x"] + a["width"] / 2
    for i in range(2):
        key = "root.0.1.6." + str(i) + ".1.0"
        b = boxes[key]
        tx = b["x"] + b["width"] / 2
        layout.connectors.append(
            {
                "source": "root.0.1.5.branch-" + str(i),
                "origin": "root.0.1.5",
                "label": elements["root.0.1.5"].text(),
                "from": [a["source"]],
                "to": [key],
                "points": [
                    [sx, a["y"] + a["height"] + 12],
                    [sx, 364],
                    [tx, 364],
                    [tx, b["y"] - 12],
                ],
            }
        )
    layout.add_text([elements["root.0.1.5"].text()], 960, 376, 18, 300, "root.0.1.5")
    target = boxes["root.0.1.8"]
    tx = 960
    for i in range(2):
        key = "root.0.1.6." + str(i) + ".1.2.0"
        a = boxes[key]
        left = 40 if i == 0 else 984
        sy = a["y"] + a["height"] / 2
        layout.connectors.append(
            {
                "source": "root.0.1.7.join-" + str(i),
                "origin": "root.0.1.7",
                "label": elements["root.0.1.7"].text(),
                "from": [key],
                "to": [target["source"]],
                "points": [
                    [a["x"] - 12, sy],
                    [left, sy],
                    [left, 888],
                    [tx, 888],
                    [tx, target["y"] - 12],
                ],
            }
        )
    layout.add_text([elements["root.0.1.7"].text()], 700, 850, 18, 600, "root.0.1.7")
    return layout


def decision_layout(font, figure):
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    layout = Layout(
        font, 24, 20, 20, 20, {"bold_width_budget": 1.25, "regular_width_budget": 1.12}
    )
    layout.draw(elements["root.0.0"], 64, 64, 1792)
    positions = {
        "root.0.1.0": (64, 160, 420),
        "root.0.1.2": (704, 160, 600),
        "root.0.1.3.0.1.0": (1440, 160, 416),
        "root.0.1.3.1.1.0": (704, 444, 600),
        "root.0.1.3.1.1.1.0.1.0": (1440, 444, 416),
        "root.0.1.3.1.1.1.1.1.0": (64, 768, 600),
        "root.0.1.3.1.1.1.1.1.1.0.1.0": (800, 768, 480),
        "root.0.1.3.1.1.1.1.1.1.1.1.0": (1376, 768, 480),
    }
    for key, (x, y, width) in positions.items():
        layout.draw(elements[key], x, y, width)
    boxes = {b["source"]: b for b in layout.boxes}

    def connection(source, target, key, label_key=None, corridor=None, text_pos=None):
        a, b = boxes[source], boxes[target]
        if corridor is None:
            sy = a["y"] + a["height"] / 2
            ty = b["y"] + b["height"] / 2
            points = [[a["x"] + a["width"] + 12, sy], [b["x"] - 12, ty]]
        else:
            points = corridor(a, b)
        label = elements[label_key or key].text()
        layout.connectors.append(
            {
                "source": key,
                "origin": label_key,
                "from": [source],
                "to": [target],
                "label": label,
                "points": points,
            }
        )
        x, y, width = text_pos
        layout.add_text(
            layout.wrap(label, width, 20), x, y, 20, width, label_key or key
        )

    connection("root.0.1.0", "root.0.1.2", "root.0.1.1", text_pos=(500, 135, 190))
    connection(
        "root.0.1.2",
        "root.0.1.3.0.1.0",
        "decision-yes-1",
        "root.0.1.3.0.0",
        text_pos=(1324, 135, 100),
    )
    connection(
        "root.0.1.2",
        "root.0.1.3.1.1.0",
        "decision-no-1",
        "root.0.1.3.1.0",
        lambda a, b: [[1004, a["y"] + a["height"] + 12], [1004, b["y"] - 12]],
        (1028, 350, 160),
    )
    connection(
        "root.0.1.3.1.1.0",
        "root.0.1.3.1.1.1.0.1.0",
        "decision-yes-2",
        "root.0.1.3.1.1.1.0.0",
        text_pos=(1324, 405, 100),
    )
    connection(
        "root.0.1.3.1.1.0",
        "root.0.1.3.1.1.1.1.1.0",
        "decision-no-2",
        "root.0.1.3.1.1.1.1.0",
        lambda a, b: [
            [1004, a["y"] + a["height"] + 12],
            [1004, 652],
            [364, 652],
            [364, b["y"] - 12],
        ],
        (700, 674, 200),
    )
    for i, target in enumerate(
        ("root.0.1.3.1.1.1.1.1.1.0.1.0", "root.0.1.3.1.1.1.1.1.1.1.1.0")
    ):
        label_key = "root.0.1.3.1.1.1.1.1.1." + str(i) + ".0"
        connection(
            "root.0.1.3.1.1.1.1.1.0",
            target,
            "decision-last-" + str(i),
            label_key,
            lambda a, b: [
                [a["x"] + a["width"] + 12, a["y"] + a["height"] / 2],
                [720, a["y"] + a["height"] / 2],
                [720, 720],
                [b["x"] + b["width"] / 2, 720],
                [b["x"] + b["width"] / 2, b["y"] - 12],
            ],
            (positions[target][0] + 160, 728, 160),
        )
    return layout


def banner_layout(font, figure):
    """Preserve the original banner's four columns and separate SVG text runs."""
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    layout = Layout(
        font, 38, 30, 32, 28,
        {"bold_width_budget": 1.25, "regular_width_budget": 1.12,
         "group_insets": {"root.0.4.4": 32}},
    )
    for key, y in [
        ("root.0.0", 64),
        ("root.0.1", 132),
        ("root.0.2", 184),
        ("root.0.3", 230),
        ("root.0.5", 952),
    ]:
        layout.draw(elements[key], 64, y, 1792)
    for key, x, width in [
        ("root.0.4.0", 48, 416),
        ("root.0.4.2", 572, 328),
        ("root.0.4.4", 1008, 424),
        ("root.0.4.6", 1540, 328),
    ]:
        element = elements[key]
        layout.draw(element, x, 584 - layout.measure(element, width) / 2, width)
    bounds = {b["source"]: b for b in layout.boxes}
    bounds.update(layout.group_bounds)
    for key, source, target, meaning in [
        ("root.0.4.1", "root.0.4.0", "root.0.4.2", "state input"),
        ("root.0.4.3", "root.0.4.2", "root.0.4.4", "typed answers"),
        ("root.0.4.5", "root.0.4.4", "root.0.4.6", "policy input"),
    ]:
        a, b = bounds[source], bounds[target]
        layout.connectors.append(
            {
                "source": key,
                "label": elements[key].text(),
                "meaning": meaning,
                "from": [source],
                "to": [target],
                "points": [[a["x"] + a["width"] + 12, 584], [b["x"] - 12, 584]],
            }
        )
    return layout


def jev_layout(font, figure):
    """Keep Jev typed data separate from deterministic execution authority."""
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    layout = Layout(
        font, 32, 26, 28, 28, {"bold_width_budget": 1.25, "regular_width_budget": 1.12}
    )
    layout.add_text(
        [figure.attrs["aria-label"]], 64, 64, 36, 1792, "jev-title.meaning", True
    )
    layout.groups.extend(
        [
            {
                "source": "root.0.0.0",
                "classes": [],
                "x": 40,
                "y": 320,
                "width": 848,
                "height": 432,
            },
            {
                "source": "root.0.0.2",
                "classes": [],
                "x": 996,
                "y": 320,
                "width": 860,
                "height": 432,
            },
        ]
    )
    spine = 536
    def on_axis(key, x, width, centre=spine):
        element = elements[key]
        return layout.draw(element, x, centre - layout.measure(element, width) / 2, width)
    inputs = on_axis("root.0.0.0.0", 68, 340)
    judge = on_axis("root.0.0.0.2", 540, 320)
    authority = on_axis("root.0.0.2.1", 1024, 432)
    layout.draw(elements["root.0.0.2.0"], 1024, 352, 804)
    outcomes = [
        on_axis("root.0.0.2.3." + str(i), 1568, 264, centre)
        for i, centre in enumerate((spine - 100, spine + 100))
    ]
    for key, a, b, label in [
        ("root.0.0.0.1", inputs, judge, "입력"),
        ("root.0.0.1", judge, authority, "typed answers"),
    ]:
        aa, bb = a["bounds"], b["bounds"]
        cy = (aa[1] + aa[3] / 2 + bb[1] + bb[3] / 2) / 2
        layout.connectors.append(
            {
                "source": key,
                "from": [a["element"].key],
                "to": [b["element"].key],
                "label": label,
                "points": [[aa[0] + aa[2] + 12, cy], [bb[0] - 12, cy]],
            }
        )
        source_key = key if key == "root.0.0.1" else key + ".meaning"
        label_x = aa[0] + aa[2] + 12
        label_width = bb[0] - aa[0] - aa[2] - 24
        label_size = 22
        if key == "root.0.0.1":
            left, right = layout.groups[:2]
            label_x = left["x"] + left["width"] + 12
            label_width = right["x"] - label_x - 12
            label_size = 20
        layout.add_text(
            layout.wrap(label, label_width, label_size),
            label_x,
            cy - 78,
            label_size,
            label_width,
            source_key,
        )
    a = authority["bounds"]
    sx = a[0] + a[2] + 12
    sy = a[1] + a[3] / 2
    for i, target in enumerate(outcomes):
        b = target["bounds"]
        tx = b[0] - 12
        ty = b[1] + b[3] / 2
        key = "root.0.0.2.2.branch-" + str(i)
        layout.connectors.append(
            {
                "source": key,
                "origin": "root.0.0.2.2",
                "from": [authority["element"].key],
                "to": [target["element"].key],
                "label": ("Shadow 경로" if i == 0 else "Escalate 경로"),
                "meaning": ("Shadow" if i == 0 else "Escalate"),
                "meaning_at_target": True,
                "points": [
                    [sx, sy],
                    [1506, sy],
                    [1506, ty],
                    [tx, ty],
                ],
            }
        )
    return layout


def certification_layout(font, figure):
    """Give all thirteen badges readable card widths without reflow at display."""
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    layout = Layout(
        font,
        22,
        18,
        16,
        16,
        {
            "columns": {"root.0.2.0.1": 1, "root.0.2.1.1": 1},
            "bold_width_budget": 1.25,
            "regular_width_budget": 1.12,
        },
    )
    layout.draw(elements["root.0.0"], 64, 48, 1792)
    y = 128
    for key in ("root.0.1.0", "root.0.1.1", "root.0.1.2"):
        lane = layout.draw(elements[key], 64, y, 1160)
        y += lane["bounds"][3] + 16
    y = 128
    for key in ("root.0.2.0", "root.0.2.1"):
        lane = layout.draw(elements[key], 1256, y, 600)
        y += lane["bounds"][3] + 32
    note = elements["root.0.3"]
    layout.add_text(layout.wrap(note.text(), 1792, 16), 64, 1018, 16, 1792, note.key)
    return layout


def ci_branch_layout(font, figure, workflow=False):
    """Make two explicit source branches and, for workflow jobs, both joins."""
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    layout = Layout(
        font,
        24 if workflow else 20,
        20 if workflow else 18,
        20 if workflow else 16,
        20 if workflow else 16,
        {
            "flow_columns": {"root.0.1.4.0.1": 2, "root.0.1.4.1.1": 2},
            "bold_width_budget": 1.25,
            "regular_width_budget": 1.12,
        },
    )
    layout.draw(elements["root.0.0"], 64, 64, 1792)
    first = layout.draw(elements["root.0.1.0"], 64, 160, 760)
    second = layout.draw(elements["root.0.1.2"], 1096, 160, 760)
    a, b = first["bounds"], second["bounds"]
    cy = max(a[1] + a[3] / 2, b[1] + b[3] / 2)
    layout.connectors.append(
        {
            "source": "root.0.1.1",
            "label": elements["root.0.1.1"].text(),
            "from": [first["element"].key],
            "to": [second["element"].key],
            "points": [[a[0] + a[2] + 12, cy], [b[0] - 12, cy]],
        }
    )
    layout.add_text(
        layout.wrap(elements["root.0.1.1"].text(), 232, 20),
        844,
        cy - 60,
        20,
        232,
        "root.0.1.1",
    )
    lanes = []
    for index, x in enumerate((64, 1024)):
        lane = elements["root.0.1.4." + str(index)]
        lanes.append(layout.draw(lane, x, 400 if workflow else 360, 832))
    layout.add_text(
        layout.wrap(elements["root.0.1.3"].text(), 740, 20),
        64,
        304,
        20,
        740,
        "root.0.1.3",
    )
    sx, sy = b[0] + b[2] / 2, b[1] + b[3] + 12
    for index, lane in enumerate(lanes):
        nodes = [
            n for n in layout.boxes if n["source"].startswith(lane["element"].key + ".")
        ]
        target = nodes[0]
        tx = target["x"] + target["width"] / 2
        layout.connectors.append(
            {
                "source": "root.0.1.3.branch-" + str(index),
                "origin": "root.0.1.3",
                "label": elements["root.0.1.3"].text(),
                "from": [second["element"].key],
                "to": [target["source"]],
                "points": [[sx, sy], [sx, 340], [tx, 340], [tx, target["y"] - 12]],
            }
        )
    if workflow:
        deploy = layout.draw(elements["root.0.1.6"], 760, 852, 400)
        d = deploy["bounds"]
        tx = d[0] + d[2] / 2
        layout.add_text(
            layout.wrap(elements["root.0.1.5"].text(), 720, 20),
            840,
            786,
            20,
            720,
            "root.0.1.5",
        )
        for index, lane in enumerate(lanes):
            nodes = [
                n
                for n in layout.boxes
                if n["source"].startswith(lane["element"].key + ".")
            ]
            source = nodes[-1]
            sx = source["x"] + source["width"] / 2
            layout.connectors.append(
                {
                    "source": "root.0.1.5.join-" + str(index),
                    "origin": "root.0.1.5",
                    "label": elements["root.0.1.5"].text(),
                    "from": [source["source"]],
                    "to": [deploy["element"].key],
                    "points": [
                        [sx, source["y"] + source["height"] + 12],
                        [sx, 826],
                        [tx, 826],
                        [tx, d[1] - 12],
                    ],
                }
            )
    note = elements["root.0.2"]
    layout.add_text(layout.wrap(note.text(), 1792, 16), 64, 980, 16, 1792, note.key)
    return layout


def rag_layout(font, figure):
    """The approved fork/merge design, re-authored at native FHD coordinates."""
    layout = Layout(font, 28, 22, 24, 24)
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    positions = {
        "root.0.1.0": (64, 540, 200),
        "root.0.3.0.1": (350, 330, 280),
        "root.0.3.1.1": (350, 750, 280),
        "root.0.5": (720, 540, 230),
        "root.0.7": (1040, 540, 250),
        "root.0.9": (1380, 540, 200),
        "root.0.11": (1670, 540, 210),
    }
    for key, (x, center, width) in positions.items():
        e = elements[key]
        layout.draw(e, x, center - layout.measure(e, width) / 2, width)
    for key, x, y, width in [
        ("root.0.0", 64, 64, 1792),
        ("root.0.3.0.0", 350, 160, 320),
        ("root.0.3.1.0", 350, 590, 320),
        ("root.0.12", 64, 970, 1792),
    ]:
        layout.draw(elements[key], x, y, width)
    routes = [
        (
            "root.0.2.dense",
            "root.0.1.0",
            "root.0.3.0.1",
            [[276, 540], [310, 540], [310, 330], [338, 330]],
        ),
        (
            "root.0.2.sparse",
            "root.0.1.0",
            "root.0.3.1.1",
            [[276, 540], [310, 540], [310, 750], [338, 750]],
        ),
        (
            "root.0.4.dense",
            "root.0.3.0.1",
            "root.0.5",
            [[642, 330], [685, 330], [685, 540], [708, 540]],
        ),
        (
            "root.0.4.sparse",
            "root.0.3.1.1",
            "root.0.5",
            [[642, 750], [685, 750], [685, 540], [708, 540]],
        ),
        ("root.0.6", "root.0.5", "root.0.7", [[962, 540], [1028, 540]]),
        ("root.0.8", "root.0.7", "root.0.9", [[1302, 540], [1368, 540]]),
        ("root.0.10", "root.0.9", "root.0.11", [[1592, 540], [1658, 540]]),
    ]
    for key, source, target, points in routes:
        origin = key.removesuffix(".dense").removesuffix(".sparse")
        layout.connectors.append(
            {
                "source": key,
                "origin": origin,
                "label": elements[origin].text(),
                "from": [source],
                "to": [target],
                "points": points,
            }
        )
    layout.add_text(
        font.wrap(elements["root.0.2"].text(), 270, 22), 64, 290, 22, 270, "root.0.2"
    )
    layout.add_text(
        font.wrap(elements["root.0.4"].text(), 340, 22), 720, 760, 22, 340, "root.0.4"
    )
    meanings = [
        ("root.0.2.dense", "Dense 검색", 190, 260, 108),
        ("root.0.2.sparse", "BM25 검색", 190, 700, 108),
        ("root.0.4.dense", "순위 결합", 645, 225, 100),
        ("root.0.4.sparse", "순위 결합", 645, 830, 100),
        ("root.0.6", "융합 후보", 962, 430, 70),
        ("root.0.8", "재채점 순위", 1302, 430, 70),
        ("root.0.10", "context 전달", 1592, 430, 70),
    ]
    for key, meaning, x, y, width in meanings:
        edge = next(e for e in layout.connectors if e["source"] == key)
        edge["meaning"] = meaning
        layout.add_text(
            font.wrap(meaning, width, 18), x, y, 18, width, key + ".meaning"
        )
    return layout


def config_layout(font, figure, typography=None):
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    profile = {"phase_flows": {"root.0.1.0.0.3": 2}, **(typography or {})}
    for label, detail, gap, padding in [
        (20, 16, 12, 12),
        (18, 14, 10, 10),
        (16, 14, 8, 8),
    ]:
        layout = Layout(font, label, detail, gap, padding, profile)
        left, right = elements["root.0.1.0.0"], elements["root.0.1.0.1"]
        if layout.measure(left, 1180) <= 888:
            break
    layout.draw(elements["root.0.0"], 64, 64, 1792)
    layout.draw(left, 64, 148, 1180)
    layout.draw(right, 1290, 148, 566)
    y = 148 + layout.measure(right, 566) + 24
    layout.draw(elements["root.0.2"], 1290, y, 566)
    y += layout.measure(elements["root.0.2"], 566) + 24
    layout.draw(elements["root.0.3"], 1290, y, 566)
    layout.resolve_boundary_edges(figure)
    return layout


def jenkins_layout(font, figure):
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    layout = Layout(
        font,
        22,
        18,
        16,
        16,
        {"flow_columns": {"root.0.1": 5}, "edge_widths": {"root.0.1": 120}},
    )
    layout.draw(elements["root.0.0"], 64, 64, 1792)
    for key, x, y, width in [
        ("root.0.1", 64, 150, 1792),
        ("root.0.3", 64, 410, 850),
        ("root.0.5", 1120, 410, 736),
        ("root.0.8", 64, 640, 850),
        ("root.0.7", 64, 860, 1792),
    ]:
        layout.draw(elements[key], x, y, width)
    layout.add_text(
        font.wrap(elements["root.0.9"].text(), 1792, 14), 64, 1010, 14, 1792, "root.0.9"
    )
    checkout = next(b for b in layout.boxes if b["source"] == "root.0.1.8")
    build = next(b for b in layout.groups if b["source"] == "root.0.3")
    test = next(b for b in layout.groups if b["source"] == "root.0.5")
    result = next(b for b in layout.boxes if b["source"] == "root.0.7.0")
    cx, cy = (
        checkout["x"] + checkout["width"] / 2,
        checkout["y"] + checkout["height"] + 12,
    )
    bx = build["x"] + build["width"] / 2
    sy, ty = build["y"] + build["height"] / 2, test["y"] + test["height"] / 2
    tx = test["x"] + test["width"] / 2
    rx = result["x"] + result["width"] / 2
    rows = [
        (
            "root.0.2",
            "root.0.1.8",
            "root.0.3",
            [[cx, cy], [cx, 370], [bx, 370], [bx, 398]],
            900,
            338,
            700,
        ),
        (
            "root.0.4",
            "root.0.3",
            "root.0.5",
            [[926, sy], [1024, sy], [1024, ty], [1108, ty]],
            916,
            474,
            88,
        ),
        (
            "root.0.6",
            "root.0.5",
            "root.0.7.0",
            [
                [tx, test["y"] + test["height"] + 12],
                [tx, 850],
                [rx, 850],
                [rx, result["y"] - 12],
            ],
            1060,
            700,
            740,
        ),
    ]
    for key, source, target, points, x, y, width in rows:
        layout.connectors.append(
            {
                "source": key,
                "label": elements[key].text(),
                "from": [source],
                "to": [target],
                "points": points,
            }
        )
        if key == "root.0.4":
            # The label is attached to the actual Build -> Test corridor.
            layout.add_text(
                layout.wrap(elements[key].text(), 170, 18),
                934,
                min(sy, ty) - 88,
                18,
                170,
                key,
            )
        else:
            layout.add_text(
                font.wrap(elements[key].text(), width, 18), x, y, 18, width, key
            )
    layout.resolve_boundary_edges(figure)
    return layout


def pod_identity_layout(font, figure, typography=None):
    """Control plane, admission and credential paths keep separate boundaries."""
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    profile = {
        "flow_columns": {
            "root.0.2.1.2.0.1": 3,
            "root.0.2.1.2.1.1": 5,
            "root.0.2.0.1.1.1": 2,
            "root.0.2.0.1.1.2": 2,
        },
        "legend_edges": [
            "root.0.2.1.2.0.1.1",
            "root.0.2.1.2.0.1.3",
            "root.0.2.0.1.1.1.1",
            "root.0.2.0.1.1.2.1",
        ],
        "edge_widths": {
            "root.0.2.1.2.0.1": 40,
            "root.0.2.1.2.1.1": 80,
            "root.0.2.0.1.0.1": 80,
            "root.0.2.0.1.1.1": 60,
            "root.0.2.0.1.1.2": 60,
        },
        "legend_markers": {
            "root.0.2.1.2.0.1.1": "A",
            "root.0.2.1.2.0.1.3": "B",
            **{
                "root.0.2.1.2.1.1." + str(i): str(number)
                for number, i in enumerate((1, 3, 5, 7), 1)
            },
        },
    }
    profile.update(typography or {})
    layout = Layout(font, 16, 14, 8, 8, profile)
    layout.draw(elements["root.0.0"], 64, 48, 1792)
    layout.draw(elements["root.0.1"], 64, 100, 1792)
    for key, y, height in [("root.0.2.0", 150, 260), ("root.0.2.1", 430, 514)]:
        layout.groups.append(
            {
                "source": key,
                "classes": sorted(elements[key].classes),
                "x": 64,
                "y": y,
                "width": 1792,
                "height": height,
            }
        )
        layout.draw(elements[key + ".0"], 80, y + 12, 1760)
    layout.draw(elements["root.0.2.0.1.0"], 80, 205, 610)
    key = "root.0.2.0.1.1"
    layout.groups.append(
        {
            "source": key,
            "classes": sorted(elements[key].classes),
            "x": 740,
            "y": 205,
            "width": 1100,
            "height": 200,
        }
    )
    layout.draw(elements[key + ".0"], 756, 216, 1068)
    layout.draw(elements[key + ".1"], 756, 260, 530)
    layout.draw(elements[key + ".2"], 1294, 260, 530)
    # This named bidirectional reference has a full-width explanation rather
    # than squeezing its long API phrase into the small painted arrow corridor.
    for ref, x in [(key + ".1.1", 756), (key + ".2.1", 1294)]:
        layout.texts = [t for t in layout.texts if t["source"] != ref]
        layout.add_text(
            layout.wrap(elements[ref].text(), 530, 14), x, 380, 14, 530, ref
        )
    layout.draw(elements["root.0.2.1.1"], 80, 466, 1760)
    layout.draw(elements["root.0.2.1.2.0"], 80, 656, 570)
    layout.draw(elements["root.0.2.1.2.1"], 680, 656, 1156)
    for index, key in enumerate(["root.0.2.1.2.1.1." + str(i) for i in (1, 3, 5, 7)]):
        edge = next(e for e in layout.connectors if e["source"] == key)
        cx = (edge["points"][0][0] + edge["points"][-1][0]) / 2
        cy = edge["points"][0][1]
        layout.texts = [t for t in layout.texts if t["source"] != key]
        layout.add_text([str(index + 1)], cx - 5, cy - 34, 14, 16, key + ".meaning")
        layout.add_text(
            [str(index + 1)], cx - 123, 858, 14, 16, key + ".legend.meaning"
        )
        layout.add_text(
            layout.wrap(elements[key].text(), 210, 14), cx - 105, 858, 14, 210, key
        )
    for marker, key, y in [
        ("A", "root.0.2.1.2.0.1.1", 950),
        ("B", "root.0.2.1.2.0.1.3", 976),
    ]:
        edge = next(e for e in layout.connectors if e["source"] == key)
        cx = (edge["points"][0][0] + edge["points"][-1][0]) / 2
        cy = edge["points"][0][1]
        layout.add_text([marker], cx - 5, cy - 30, 14, 16, key + ".meaning")
        layout.add_text([marker], 64, y, 14, 16, key + ".legend.meaning")
        layout.texts = [t for t in layout.texts if t["source"] != key]
        layout.add_text(font.wrap(elements[key].text(), 550, 14), 80, y, 14, 550, key)
    layout.draw(elements["root.0.5"], 680, 904, 1156)
    layout.draw(elements["root.0.4"], 710, 968, 1146)
    source = "root.0.2.1.2.0.1.4"
    box = next(b for b in layout.boxes if b["source"] == source)
    target = next(b for b in layout.boxes if b["source"] == "root.0.4")
    sy, ty = box["y"] + box["height"] / 2, target["y"] + target["height"] / 2
    layout.connectors.append(
        {
            "source": "root.0.3",
            "label": elements["root.0.3"].text(),
            "from": [source],
            "to": ["root.0.4"],
            "points": [
                [box["x"] + box["width"] + 12, sy],
                [668, sy],
                [668, ty],
                [698, ty],
            ],
        }
    )
    layout.add_text(
        font.wrap(elements["root.0.3"].text(), 550, 14), 64, 998, 14, 550, "root.0.3"
    )
    layout.resolve_boundary_edges(figure)
    return layout


def arc_layout(font, figure):
    """One fixed horizontal management path plus direct GitHub/runner traffic."""
    named = {e.attrs['id']: e for e in [figure, *figure.descendants()] if e.attrs.get('id')}
    layout = Layout(font, 32, 26, 24, 28, {
        'bold_width_budget': 1.12, 'regular_width_budget': 1.08,
        'no_connector_labels': True,
    })
    layout.draw(named['sd-arc-title'], 60, 50, 1800)
    for key, x, width in [('arc-github', 40, 390), ('arc-kubernetes', 470, 1410)]:
        layout.groups.append({'source': named[key].key, 'classes': [],
                              'x': x, 'y': 155, 'width': width, 'height': 775})
    layout.draw(named['arc-github-title'], 75, 185, 320)
    layout.draw(named['arc-kubernetes-title'], 510, 185, 1300)
    layout.draw(named['arc-scale-set'], 510, 260, 1300)
    nodes = {}
    for key, x, width in [('arc-service', 75, 320), ('arc-listener', 525, 320),
                          ('arc-controller', 975, 320), ('arc-runner', 1425, 390)]:
        nodes[key] = layout.draw(named[key], x, 385, width)
        layout.boxes[-1]['height'] = 230
        nodes[key]['bounds'][3] = 230
    for key, x, y, width in [('arc-management', 525, 655, 780),
                            ('arc-ephemeral', 1425, 655, 390),
                            ('arc-direct', 510, 815, 1300),
                            ('arc-idle', 60, 970, 1800)]:
        layout.draw(named[key], x, y, width)
    routes = {
        'arc-notify': [[407, 500], [513, 500]],
        'arc-replicas': [[857, 500], [963, 500]],
        'arc-create': [[1307, 500], [1413, 500]],
        'arc-job': [[235, 373], [235, 335], [1620, 335], [1620, 373]],
        'arc-result': [[1795, 627], [1795, 770], [235, 770], [235, 627]],
    }
    for key, points in routes.items():
        edge = named[key]
        layout.connectors.append({'source': edge.key,
            'from': [named[edge.attrs['data-from']].key],
            'to': [named[edge.attrs['data-to']].key],
            'label': '', 'meaning': edge.attrs['aria-label'], 'points': points})
    return layout


def author(root, check=False, report=None):
    font = Font(root / FONT)
    catalog = json.loads((root / "docs/diagram-catalog.json").read_text())
    typography = json.loads(
        (root / "kkamji_scripts/blog/static_png/fhd-font-budgets.json").read_text()
    )["sources"]
    results = []
    for record in catalog["diagrams"]:
        path = root / "_includes" / record["include"]
        raw = path.read_text()
        original = source_fragment(raw)
        figure = next(
            e
            for e in Parse(original).root.descendants()
            if e.tag == "figure" and "sd" in e.classes
        )
        # Fixed, authored density profiles. No viewport dimensions participate.
        selected = None
        for label, detail, gap, padding in [
            (28, 22, 24, 24),
            (24, 20, 20, 20),
            (20, 18, 16, 16),
            (18, 16, 12, 12),
            (16, 14, 10, 10),
            (16, 14, 8, 8),
        ]:
            layout = Layout(
                font,
                label,
                detail,
                gap,
                padding,
                {
                    **FIXED_LAYOUT_PROFILES.get(record["include"], {}),
                    **typography.get(record["include"], {}),
                },
            )
            try:
                measured = layout.measure(figure, WIDTH - 128)
            except ValueError:
                continue
            if measured <= HEIGHT - 128:
                y = 64 + (HEIGHT - 128 - measured) / 2
                layout.draw(figure, 64, y, WIDTH - 128)
                layout.resolve_boundary_edges(figure)
                if any(
                    issue["code"] == "source-identifier-split"
                    for issue in semantic_check(layout, figure)
                ):
                    continue
                selected = layout
                break
        if (
            record["include"]
            == "diagrams/static/sap-c02/cloudwatch-alarm-missing-data.html"
        ):
            selected = alarm_layout(font, figure)
        elif record["include"] == "diagrams/static/spring/spring-14-when-to-use.html":
            selected = decision_layout(font, figure)
        elif (
            record["include"]
            == "diagrams/static/spring/spring-23-security-filter-chain.html"
        ):
            selected = security_layout(font, figure)
        elif record["include"] == "diagrams/static/ci-cd/arc-overview.html":
            selected = arc_layout(font, figure)
        elif record["include"] == "diagrams/static/ai/jev-decision-pipeline.html":
            selected = jev_layout(font, figure)
        elif record["include"] == "diagrams/static/ai/jev-system-one-banner.html":
            selected = banner_layout(font, figure)
        elif record["include"] == "diagrams/aws-certification-map.html":
            selected = certification_layout(font, figure)
        elif record["include"] == "diagrams/static/ai/rag-04-hybrid-rerank.html":
            selected = rag_layout(font, figure)
        elif (
            record["include"]
            == "diagrams/static/ci-cd/github-actions-workflow-flow.html"
        ):
            selected = ci_branch_layout(font, figure, workflow=True)
        elif (
            record["include"]
            == "diagrams/static/ci-cd/jenkins/jenkins-operator/jenkins-operator-reconcile-loop.html"
        ):
            selected = ci_branch_layout(font, figure)
        elif (
            record["include"] == "diagrams/static/kubernetes/pod-identity-workflow.html"
        ):
            selected = pod_identity_layout(
                font, figure, typography.get(record["include"])
            )
        elif (
            record["include"]
            == "diagrams/static/sap-c02/config-evaluation-remediation.html"
        ):
            selected = config_layout(font, figure, typography.get(record["include"]))
        elif (
            record["include"]
            == "diagrams/static/ci-cd/ci-cd-study/jenkins-pipeline.html"
        ):
            selected = jenkins_layout(font, figure)
        elif selected is None:
            results.append(
                {
                    "include": record["include"],
                    "status": "needs-layout",
                    "reason": "source requires individual coordinate redesign, no resize or crop applied",
                }
            )
            continue
        manual_relation_fixes(selected, figure, record["include"])
        complete_group_boundaries(selected)
        if not selected.profile.get("no_connector_labels"):
            complete_relation_labels(selected)
        issues = (
            check_layout(selected)
            + semantic_check(selected, figure)
            + visible_text_coverage(selected, original)
        )
        svg = svg_document(selected, figure, sha(original.encode()))
        ET.fromstring(svg)
        opening, body = original.split(">", 1)
        body = body.rsplit("</figure>", 1)[0]
        opening = re.sub(
            r'class="([^"]+)"', lambda m: 'class="' + m.group(1) + ' sd--fhd"', opening
        )
        caption_end = body.find("</figcaption>")
        caption_end = caption_end + len("</figcaption>") if caption_end >= 0 else 0
        prefix, rest = body[:caption_end], body[caption_end:]
        updated = (
            opening
            + ' data-canvas-width="1920" data-canvas-height="1080">'
            + prefix
            + SEMANTIC_BEGIN
            + rest
            + "</div>\n"
            + SVG_BEGIN
            + "\n"
            + svg
            + "\n</figure>\n"
        )
        if source_fragment(updated) != original:
            raise ValueError(
                "semantic source preservation failed: " + record["include"]
            )
        result = {
            "include": record["include"],
            "display": "fixed-fhd-scroll" if record["include"] == "diagrams/static/ci-cd/arc-overview.html" else "responsive-proportional",
            "source_sha256": sha(original.encode()),
            "svg_sha256": sha(svg.encode()),
            "density": {"label": selected.label_size, "detail": selected.detail_size},
            "nodes": len(selected.boxes),
            "edges": len(selected.connectors),
            "issues": issues,
            "status": "draft-needs-review" if issues else "static-geometry-passed",
            "rendered_visual_review": "not-run",
            "semantic_review": "not-run",
        }
        if check:
            result["fresh"] = raw == updated
            if raw != updated:
                result["status"] = "stale"
        else:
            path.write_text(updated)
            svg_path = (
                root
                / "assets/img/diagrams/fhd-svg"
                / record["include"].removeprefix("diagrams/").replace(".html", ".svg")
            )
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text(svg + "\n")
        results.append(result)
    payload = {
        "canvas": [WIDTH, HEIGHT],
        "display": "fixed-fhd-scroll" if results and all(r.get("display") == "fixed-fhd-scroll" for r in results) else "responsive-proportional",
        "display_overrides": {r["include"]: r["display"] for r in results if r.get("display") == "fixed-fhd-scroll"},
        "font_sha256": sha(font.raw),
        "counts": {
            status: sum(r["status"] == status for r in results)
            for status in sorted({r["status"] for r in results})
        },
        "entries": results,
    }
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"count": len(results), **payload["counts"]}, ensure_ascii=False))
    return int(any(r["status"] != "static-geometry-passed" for r in results))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--check", action="store_true")
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    return author(args.root.resolve(), args.check, args.report)


if __name__ == "__main__":
    raise SystemExit(main())
