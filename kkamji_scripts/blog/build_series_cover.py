#!/usr/bin/env python3
"""Render the monochrome series cover images used as post header images.

    uv run --with pillow python kkamji_scripts/blog/build_series_cover.py
    uv run --with pillow python kkamji_scripts/blog/build_series_cover.py llm-wiki

Each cover is a 1200x630 wordmark on a near-black canvas: a line-art glyph on
the left, the series name and a one-line Korean caption on the right. Two inks
only, so the covers sit next to hermes.webp without introducing a new palette.

Shapes are drawn at SUPERSAMPLE times the final size and downsampled, because
ImageDraw does not antialias lines or ellipses. Outlined nodes are filled with
the background so the edges underneath them do not show through the ring.

macOS only: the wordmark uses Helvetica Neue Medium and the caption uses Apple
SD Gothic Neo, both from /System/Library/Fonts.
"""

from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
SUPERSAMPLE = 3

BG = "#111111"
INK = "#FFFFFF"
INK_MUTED = "#9AA0A6"
INK_FAINT = "#5A5D61"
RULE = "#3C3C3C"

WORDMARK_SIZE = 76
WORDMARK_TRACKING = 8  # extra px between glyphs, before supersampling
CAPTION_SIZE = 28
GAP_WORDMARK_RULE = 34
GAP_RULE_CAPTION = 28
GAP_GLYPH_TEXT = 118
RULE_H = 2

NODE_R = 13
HUB_R = 16
DOT_R = 5
NODE_STROKE = 3
BOX_STROKE = 3
EDGE_W = 2

FONT_WORDMARK = ("/System/Library/Fonts/HelveticaNeue.ttc", 10)  # Medium
FONT_CAPTION = ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0)  # Regular

# Glyph geometry in final-image px, relative to the glyph's own origin.
_WIKI_NODES = [(0, -92), (-88, -34), (86, -40), (-72, 86), (74, 78)]
_WIKI_HUB = (-14, 18)
_RAG_HITS = [(-70, -52), (62, -38), (18, 74)]
_RAG_QUERY = (0, 0)
_CHAIN_BOX_W, _CHAIN_BOX_H = 178, 58
_CHAIN_CENTRES = [(0, -88), (0, 0), (0, 88)]
_CHAIN_HALF = _CHAIN_BOX_H / 2

GLYPHS = {
    # A small knowledge graph: notes linked into one hub.
    "graph": {
        "nodes": _WIKI_NODES,
        "hubs": [_WIKI_HUB],
        "dots": [],
        "edges": [
            (_WIKI_NODES[0], _WIKI_NODES[1]),
            (_WIKI_NODES[0], _WIKI_NODES[2]),
            (_WIKI_NODES[1], _WIKI_HUB),
            (_WIKI_NODES[2], _WIKI_HUB),
            (_WIKI_HUB, _WIKI_NODES[3]),
            (_WIKI_HUB, _WIKI_NODES[4]),
            (_WIKI_NODES[1], _WIKI_NODES[3]),
            (_WIKI_NODES[2], _WIKI_NODES[4]),
        ],
    },
    # A vector space: the query pulls its three nearest neighbours out of the field.
    "retrieval": {
        "nodes": _RAG_HITS,
        "hubs": [_RAG_QUERY],
        # Varied radii on purpose: an even ring would read as a halo, not a cloud.
        # fmt: off
        "dots": [
            (-124, -92),
            (-52, -104),
            (26, -126),
            (104, -96),
            (-140, -26),
            (-96, -4),
            (138, -30),
            (112, 26),
            (-112, 58),
            (-40, 112),
            (36, 130),
            (92, 90),
            (-16, -58),
            (78, -84),
            (-84, 40),
            (72, 48),
        ],
        # fmt: on
        "edges": [(_RAG_QUERY, p) for p in _RAG_HITS],
    },
    # A chain of blocks: each one links back to the block above it, and the
    # newest block at the bottom is the tip.
    "chain": {
        "nodes": [],
        "hubs": [],
        "dots": [],
        "boxes": [
            (cx, cy, _CHAIN_BOX_W, _CHAIN_BOX_H, i == len(_CHAIN_CENTRES) - 1)
            for i, (cx, cy) in enumerate(_CHAIN_CENTRES)
        ],
        "edges": [
            ((a[0], a[1] + _CHAIN_HALF), (b[0], b[1] - _CHAIN_HALF))
            for a, b in zip(_CHAIN_CENTRES, _CHAIN_CENTRES[1:])
        ],
    },
}

COVERS = {
    "llm-wiki": {
        "glyph": "graph",
        "wordmark": "LLM WIKI",
        "caption": "AI가 읽는 지식 베이스",
        "out": "assets/img/ai/llm-wiki/llm-wiki.webp",
    },
    "rag": {
        "glyph": "retrieval",
        "wordmark": "RAG",
        "caption": "검색 증강 생성 파이프라인",
        "out": "assets/img/ai/rag/rag.webp",
    },
    "blockchain": {
        "glyph": "chain",
        "wordmark": "BLOCKCHAIN",
        "caption": "해시와 서명으로 검증하는 분산 원장",
        "out": "assets/img/blockchain/blockchain.webp",
    },
}


_FONT_FALLBACKS = {
    FONT_WORDMARK[0]: ["/mnt/c/Windows/Fonts/arialbd.ttf"],
    FONT_CAPTION[0]: ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
}


def load_font(spec, size):
    path, index = spec
    if not os.path.isfile(path):
        for alt in _FONT_FALLBACKS.get(path, []):
            if os.path.isfile(alt):
                return ImageFont.truetype(alt, size * SUPERSAMPLE)
        sys.exit(f"font not found: {path} (macOS fonts or the WSL fallbacks)")
    return ImageFont.truetype(path, size * SUPERSAMPLE, index=index)


def glyph_bbox(glyph):
    """(x0, y0, x1, y1) of the glyph's ink, in unscaled px around its origin."""
    circles = (
        [(x, y, NODE_R + NODE_STROKE / 2) for x, y in glyph["nodes"]]
        + [(x, y, HUB_R) for x, y in glyph["hubs"]]
        + [(x, y, DOT_R) for x, y in glyph["dots"]]
    )
    # A box contributes the same four extremes as a circle of its half-extent,
    # so both shapes can be reduced to one min/max pass.
    spans = [(x - r, y - r, x + r, y + r) for x, y, r in circles] + [
        (
            x - (w + BOX_STROKE) / 2,
            y - (h + BOX_STROKE) / 2,
            x + (w + BOX_STROKE) / 2,
            y + (h + BOX_STROKE) / 2,
        )
        for x, y, w, h, _ in glyph.get("boxes", [])
    ]
    return (
        min(s[0] for s in spans),
        min(s[1] for s in spans),
        max(s[2] for s in spans),
        max(s[3] for s in spans),
    )


def draw_glyph(draw, glyph, origin):
    def at(p):
        return (origin[0] + p[0] * SUPERSAMPLE, origin[1] + p[1] * SUPERSAMPLE)

    def circle(p, radius, fill, outline, width):
        cx, cy = at(p)
        r = radius * SUPERSAMPLE
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=width
        )

    for a, b in glyph["edges"]:
        draw.line([at(a), at(b)], fill=INK_FAINT, width=EDGE_W * SUPERSAMPLE)
    for cx, cy, w, h, filled in glyph.get("boxes", []):
        x0, y0 = at((cx - w / 2, cy - h / 2))
        x1, y1 = at((cx + w / 2, cy + h / 2))
        draw.rectangle(
            [x0, y0, x1, y1],
            fill=INK if filled else BG,
            outline=INK,
            width=BOX_STROKE * SUPERSAMPLE,
        )
    for p in glyph["dots"]:
        circle(p, DOT_R, INK_FAINT, INK_FAINT, 0)
    for p in glyph["nodes"]:
        circle(p, NODE_R, BG, INK, NODE_STROKE * SUPERSAMPLE)
    for p in glyph["hubs"]:
        circle(p, HUB_R, INK, INK, 0)


def tracked_width(draw, text, font, tracking):
    """Width of `text` once `tracking` px are inserted between glyphs."""
    total = sum(draw.textlength(ch, font=font) for ch in text)
    return total + tracking * SUPERSAMPLE * max(len(text) - 1, 0)


def draw_tracked(draw, xy, text, font, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking * SUPERSAMPLE


def render(spec):
    img = Image.new("RGB", (W * SUPERSAMPLE, H * SUPERSAMPLE), BG)
    draw = ImageDraw.Draw(img)

    wordmark_font = load_font(FONT_WORDMARK, WORDMARK_SIZE)
    caption_font = load_font(FONT_CAPTION, CAPTION_SIZE)
    wordmark, caption = spec["wordmark"], spec["caption"]

    # textbbox y0 is the ink offset below the drawing origin, so it has to be
    # subtracted back out when positioning by measured height.
    wm_box = draw.textbbox((0, 0), wordmark, font=wordmark_font)
    cap_box = draw.textbbox((0, 0), caption, font=caption_font)
    wm_h, cap_h = wm_box[3] - wm_box[1], cap_box[3] - cap_box[1]
    wm_w = tracked_width(draw, wordmark, wordmark_font, WORDMARK_TRACKING)
    cap_w = cap_box[2] - cap_box[0]
    text_w = max(wm_w, cap_w)

    glyph = GLYPHS[spec["glyph"]]
    gx0, gy0, gx1, gy1 = glyph_bbox(glyph)
    glyph_w = (gx1 - gx0) * SUPERSAMPLE

    # Centre glyph and text together as one group.
    group_w = glyph_w + GAP_GLYPH_TEXT * SUPERSAMPLE + text_w
    group_left = (W * SUPERSAMPLE - group_w) / 2
    glyph_origin = (
        group_left + (-gx0) * SUPERSAMPLE,
        (H * SUPERSAMPLE) / 2 - ((gy0 + gy1) / 2) * SUPERSAMPLE,
    )
    text_left = group_left + glyph_w + GAP_GLYPH_TEXT * SUPERSAMPLE

    block_h = (
        wm_h + (GAP_WORDMARK_RULE + RULE_H + GAP_RULE_CAPTION) * SUPERSAMPLE + cap_h
    )
    top = (H * SUPERSAMPLE - block_h) / 2

    draw_tracked(
        draw,
        (text_left, top - wm_box[1]),
        wordmark,
        wordmark_font,
        INK,
        WORDMARK_TRACKING,
    )
    rule_y = top + wm_h + GAP_WORDMARK_RULE * SUPERSAMPLE
    draw.rectangle(
        [text_left, rule_y, text_left + text_w, rule_y + RULE_H * SUPERSAMPLE],
        fill=RULE,
    )
    cap_y = rule_y + (RULE_H + GAP_RULE_CAPTION) * SUPERSAMPLE
    draw.text(
        (text_left, cap_y - cap_box[1]), caption, font=caption_font, fill=INK_MUTED
    )

    draw_glyph(draw, glyph, glyph_origin)
    return img.resize((W, H), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", choices=sorted(COVERS), default=None)
    args = ap.parse_args()

    repo_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    for name in args.names or sorted(COVERS):
        spec = COVERS[name]
        out = os.path.join(repo_root, spec["out"])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        render(spec).save(out, "WEBP", quality=92, method=6)
        print(f"{spec['out']}  {W}x{H}  {os.path.getsize(out) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
