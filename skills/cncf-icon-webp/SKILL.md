---
name: cncf-icon-webp
description: Create CNCF project icon images with white backgrounds and export to webp, matching a reference image's canvas size and logo scale. Use when converting CNCF artwork icons (e.g., Istio) to blog cover images or aligning new icons to an existing banner template.
---

# CNCF Icon WebP

## Overview

Generate a webp cover image from a CNCF project icon by flattening transparency onto a white background, scaling to match the reference logo area, and centering on a canvas sized to a reference image.

## Workflow

1) Collect inputs: icon URL or local file, reference image path, output path.
2) Run the script to build a centered webp with matching size.
3) Verify output size and alpha channel.

## Script: scripts/generate_cncf_icon_webp.py

Requirements:
- python3
- pillow (`python3 -m pip install pillow`)
- optional: `cwebp` (preferred webp encoder)

Example:

```bash
python3 scripts/generate_cncf_icon_webp.py \
  --icon-url https://raw.githubusercontent.com/cncf/artwork/main/projects/istio/icon/color/istio-icon-color.png \
  --reference assets/img/kubernetes/kubernetes.webp \
  --output assets/img/kubernetes/istio/istio.webp
```

Common options:
- `--icon-path` to use a local icon file
- `--bbox-threshold` to adjust non-white detection (default: 250)
- `--fallback-scale` when reference has no non-white pixels (default: 0.7)
- `--background` to change the canvas color (default: `#ffffff`)
- `--no-cwebp` to force Pillow for encoding

## Verification

Optional checks:

```bash
sips -g pixelWidth -g pixelHeight assets/img/kubernetes/istio/istio.webp
webpinfo -summary assets/img/kubernetes/istio/istio.webp
```

## Notes

- If Pillow cannot read webp on your machine, convert the reference to PNG first (macOS example: `sips -s format png reference.webp --out /tmp/reference.png`).
- Prefer `cwebp` if available for consistent encoding output.
