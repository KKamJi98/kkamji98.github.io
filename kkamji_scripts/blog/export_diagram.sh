#!/usr/bin/env bash
# Export a .drawio to the blog's .webp with equal margins on all four sides.
#
#   kkamji_scripts/blog/export_diagram.sh assets/img/aws/foo.drawio [scale] [pad]
#
# drawio's own -b/--crop leaves asymmetric margins, so the ink bbox is trimmed
# and re-padded afterwards. The result is measured before it is reported as
# equal - see references/export-and-margins.md in the drawio-generate-diagram
# skill.
set -euo pipefail

SRC="${1:?usage: export_diagram.sh <file.drawio> [scale] [pad]}"
SCALE="${2:-2}"
PAD="${3:-110}"
OUT="${SRC%.drawio}.webp"
TMP="$(mktemp -t drawio-export-XXXXXX).png"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

trap 'rm -f "$TMP"' EXIT

drawio -x -f png -s "$SCALE" --crop -b 0 --no-sandbox -o "$TMP" "$SRC" >/dev/null 2>&1
[ -s "$TMP" ] || { echo "drawio produced no output for $SRC" >&2; exit 1; }

uv run --quiet --with pillow python "$HERE/pad_diagram_margins.py" "$TMP" "$OUT" --pad "$PAD"
uv run --quiet --with pillow python "$HERE/pad_diagram_margins.py" "$OUT" --verify
