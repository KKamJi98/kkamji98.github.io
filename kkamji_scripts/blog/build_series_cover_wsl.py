#!/usr/bin/env python3
"""WSL variant of build_series_cover.py — same 1200x630 monochrome design,
using Noto Sans KR (WSL noto_sans_kr package) instead of macOS system fonts.

    uv run --with pillow python kkamji_scripts/blog/build_series_cover_wsl.py ai-gateway
"""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
SUPERSAMPLE = 3

BG = "#111111"
INK = "#F2F2F2"
INK_FAINT = "#5A5A5A"
EDGE_W = 3
NODE_STROKE = 4
NODE_R = 22
HUB_R = 9
DOT_R = 5
BOX_STROKE = 4

FONT_WORDMARK = ("/usr/share/fonts/truetype/noto_sans_kr/NotoSansKR-Medium.ttf", 0)
FONT_CAPTION = ("/usr/share/fonts/truetype/noto_sans_kr/NotoSansKR-Regular.ttf", 0)

COVERS = {
    "ai-gateway": {
        "glyph": "gateway",
        "wordmark": "AI GATEWAY",
        "caption": "키, 비용, 감사의 관문",
        "out": "assets/img/ai/gateway/ai-gateway.webp",
    },
    "ai-agent-loop": {
        "glyph": "loop",
        "wordmark": "LOOP ENGINEERING",
        "caption": "프롬프트 대신 루프를 설계한다",
        "out": "assets/img/ai/agent/loop-engineering.webp",
    },
    "ai-agent-graph": {
        "glyph": "graph",
        "wordmark": "GRAPH ENGINEERING",
        "caption": "루프를 시스템으로 조직한다",
        "out": "assets/img/ai/agent/graph-engineering.webp",
    },
}


def load_font(spec, size):
    path, index = spec
    if not os.path.isfile(path):
        sys.exit(f"font not found: {path}")
    return ImageFont.truetype(path, size * SUPERSAMPLE, index=index)


def gateway_glyph():
    """A funnel of three app dots on the left converging through a gate box,
    then fanning to three provider dots on the right."""
    apps = [(70, 90), (70, 160), (70, 230)]
    providers = [(330, 90), (330, 160), (330, 230)]
    gate = (200, 160)
    return {
        "nodes": apps + providers,
        "hubs": [],
        "dots": [],
        "boxes": [(gate[0], gate[1], 92, 120, True)],
        "edges": [
            (apps[0], (gate[0] - 46, 110)),
            (apps[1], (gate[0] - 46, gate[1])),
            (apps[2], (gate[0] - 46, 210)),
            ((gate[0] + 46, 110), providers[0]),
            ((gate[0] + 46, gate[1]), providers[1]),
            ((gate[0] + 46, 210), providers[2]),
        ],
    }


def loop_glyph():
    """A circular cycle of four node dots with an arrow-ish gap,
    a verify box as the heaviest station on the ring."""
    pts = [(230, 40), (360, 160), (230, 280), (100, 160)]
    verify = (230, 160)
    return {
        "height": 320,
        "nodes": pts,
        "hubs": [(230, 160)],
        "dots": [],
        "boxes": [(verify[0], verify[1], 96, 56, False)],
        "edges": [
            (pts[0], pts[1]),
            (pts[1], pts[2]),
            (pts[2], pts[3]),
            (pts[3], pts[0]),
        ],
    }


def graph_glyph():
    """Three small loop triangles connected through a central task hub,
    with a state box below holding the shared record."""
    a = (120, 80)
    b = (280, 80)
    c = (200, 170)
    state = (200, 280)
    return {
        "height": 320,
        "nodes": [a, b, c],
        "hubs": [c],
        "dots": [],
        "boxes": [(state[0], state[1], 120, 52, False)],
        "edges": [
            (a, b),
            (b, c),
            (c, a),
            (c, (state[0], state[1] - 26)),
        ],
    }


GLYPHS = {"gateway": gateway_glyph, "loop": loop_glyph, "graph": graph_glyph}


def render(spec) -> Image.Image:
    img = Image.new("RGB", (W * SUPERSAMPLE, H * SUPERSAMPLE), BG)
    draw = ImageDraw.Draw(img)
    glyph = GLYPHS[spec["glyph"]]()
    glyph_w = 400
    gx = 60
    gy = (H - glyph["height"] if "height" in glyph else (H - 320)) // 2

    # glyph occupies left side
    def at(p):
        return (gx * SUPERSAMPLE + p[0] * SUPERSAMPLE, gy * SUPERSAMPLE + p[1] * SUPERSAMPLE)

    for a, b in glyph["edges"]:
        draw.line([at(a), at(b)], fill=INK_FAINT, width=EDGE_W * SUPERSAMPLE)
    for cx, cy, w, h, filled in glyph["boxes"]:
        x0, y0 = at((cx - w / 2, cy - h / 2))
        x1, y1 = at((cx + w / 2, cy + h / 2))
        draw.rectangle(
            [x0, y0, x1, y1],
            fill=INK if filled else BG,
            outline=INK,
            width=BOX_STROKE * SUPERSAMPLE,
        )
    for p in glyph["nodes"]:
        cx, cy = at(p)
        r = NODE_R * SUPERSAMPLE
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BG, outline=INK, width=NODE_STROKE * SUPERSAMPLE)

    # wordmark + caption on the right
    f_word = load_font(FONT_WORDMARK, 64)
    f_cap = load_font(FONT_CAPTION, 30)
    tx = (gx + glyph_w + 60) * SUPERSAMPLE
    word_y = H * SUPERSAMPLE // 2 - 70 * SUPERSAMPLE
    draw.text((tx, word_y), spec["wordmark"], font=f_word, fill=INK)
    draw.text((tx, word_y + 110 * SUPERSAMPLE), spec["caption"], font=f_cap, fill=INK_FAINT)

    return img.resize((W, H), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", choices=sorted(COVERS), default=None)
    args = ap.parse_args()
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for name in args.names or sorted(COVERS):
        spec = COVERS[name]
        out = os.path.join(repo_root, spec["out"])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        render(spec).save(out, "WEBP", quality=92, method=6)
        print(f"{spec['out']}  {W}x{H}  {os.path.getsize(out) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
