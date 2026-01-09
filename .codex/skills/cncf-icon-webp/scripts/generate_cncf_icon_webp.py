#!/usr/bin/env python3
"""
Generate a white-background CNCF icon webp sized to a reference image.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse
from pathlib import Path

from PIL import Image, ImageOps


def parse_color(value):
    value = value.strip().lower()
    if value.startswith("#"):
        value = value[1:]
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError("background must be a hex color like #ffffff")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def download_icon(url, dest_path):
    with urllib.request.urlopen(url) as response:
        data = response.read()
    dest_path.write_bytes(data)


def find_bbox_size(ref_img, threshold, fallback_scale):
    ref = ref_img.convert("RGB")
    width, height = ref.size
    min_x, min_y = width, height
    max_x, max_y = -1, -1
    pixels = ref.load()

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r < threshold or g < threshold or b < threshold:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y

    if max_x < min_x or max_y < min_y:
        bbox_w = max(1, int(width * fallback_scale))
        bbox_h = max(1, int(height * fallback_scale))
    else:
        bbox_w = max_x - min_x + 1
        bbox_h = max_y - min_y + 1

    return bbox_w, bbox_h


def build_canvas(icon_img, canvas_size, bbox_size, background_rgb):
    icon = icon_img.convert("RGBA")
    background = Image.new("RGBA", icon.size, (*background_rgb, 255))
    icon_flat = Image.alpha_composite(background, icon).convert("RGB")
    icon_scaled = ImageOps.contain(icon_flat, bbox_size, Image.LANCZOS)

    canvas = Image.new("RGB", canvas_size, background_rgb)
    offset_x = (canvas_size[0] - icon_scaled.width) // 2
    offset_y = (canvas_size[1] - icon_scaled.height) // 2
    canvas.paste(icon_scaled, (offset_x, offset_y))
    return canvas


def save_webp(canvas, output_path, quality, prefer_cwebp=True):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cwebp_path = shutil.which("cwebp") if prefer_cwebp else None

    if cwebp_path:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_png = Path(tmpdir) / "canvas.png"
            canvas.save(tmp_png, "PNG")
            subprocess.run(
                [cwebp_path, "-q", str(quality), str(tmp_png), "-o", str(output_path)],
                check=True,
            )
    else:
        canvas.save(output_path, "WEBP", quality=quality, method=6)


def build_icon_path(args, tmpdir):
    if args.icon_path:
        return Path(args.icon_path)

    url_path = Path(urlparse(args.icon_url).path)
    suffix = url_path.suffix or ".png"
    dest = Path(tmpdir) / f"icon{suffix}"
    download_icon(args.icon_url, dest)
    return dest


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a white-background CNCF icon webp matching a reference image."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--icon-url", help="CNCF icon URL (png/svg/etc.)")
    group.add_argument("--icon-path", help="Local CNCF icon file path")
    parser.add_argument("--reference", required=True, help="Reference image path")
    parser.add_argument("--output", required=True, help="Output webp path")
    parser.add_argument("--quality", type=int, default=80, help="webp quality (0-100)")
    parser.add_argument(
        "--bbox-threshold",
        type=int,
        default=250,
        help="RGB threshold for detecting non-white pixels",
    )
    parser.add_argument(
        "--fallback-scale",
        type=float,
        default=0.7,
        help="Scale when reference has no non-white pixels",
    )
    parser.add_argument(
        "--background",
        default="#ffffff",
        help="Background color as hex (default: #ffffff)",
    )
    parser.add_argument(
        "--no-cwebp",
        action="store_true",
        help="Disable cwebp even if available",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not (0 <= args.quality <= 100):
        raise SystemExit("quality must be between 0 and 100")

    output_path = Path(args.output)
    if output_path.suffix.lower() != ".webp":
        raise SystemExit("output must end with .webp")

    background_rgb = parse_color(args.background)

    with tempfile.TemporaryDirectory() as tmpdir:
        icon_path = build_icon_path(args, tmpdir)
        reference_path = Path(args.reference)

        reference_img = Image.open(reference_path)
        icon_img = Image.open(icon_path)

        bbox_size = find_bbox_size(
            reference_img, args.bbox_threshold, args.fallback_scale
        )
        canvas_size = reference_img.size

        canvas = build_canvas(icon_img, canvas_size, bbox_size, background_rgb)
        save_webp(canvas, output_path, args.quality, prefer_cwebp=not args.no_cwebp)

    print(
        f"Saved {output_path} ({canvas_size[0]}x{canvas_size[1]}), "
        f"bbox {bbox_size[0]}x{bbox_size[1]}",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
