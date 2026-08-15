#!/usr/bin/env bash
# Rebuild every diagram that has a spec: spec -> .drawio -> .webp, then validate.
#
#   kkamji_scripts/blog/rebuild_diagrams.sh assets/img/aws
#   kkamji_scripts/blog/rebuild_diagrams.sh assets/img          # everything
#
# Exits non-zero if any spec fails to compile or any diagram fails validation.
set -uo pipefail

ROOT="${1:-assets/img}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL="${DRAWIO_SKILL_DIR:-$HOME/.claude/skills/drawio-generate-diagram}"
fails=0

specs=$(find "$ROOT" -name "*.spec.json" | sort)
[ -n "$specs" ] || { echo "no specs under $ROOT"; exit 0; }

for spec in $specs; do
  target="${spec%.spec.json}.drawio"
  name=$(basename "$target" .drawio)
  if ! python3 "$HERE/build_aws_diagram.py" "$spec" -o "$target" >/dev/null; then
    echo "BUILD FAIL  $name"; fails=$((fails + 1)); continue
  fi
  # aws_diagram_tokens.py is a hand-kept mirror of the skill's drawio_tokens.py.
  # Normalising here means a skill token change lands on the next rebuild instead
  # of waiting for someone to notice the mirror has gone stale.
  if ! python3 "$SKILL/scripts/normalize-drawio.py" --write "$target" >/dev/null; then
    echo "NORMALIZE FAIL  $name"; fails=$((fails + 1)); continue
  fi
  margins=$(bash "$HERE/export_diagram.sh" "$target" 2 110 2>&1 | tail -1)
  verdict=$(bash "$SKILL/scripts/validate-drawio.sh" "$target" 2>&1 | grep -cE "FAIL: [1-9]")
  if [ "$verdict" != "0" ] || [ "$margins" != "equal margins: OK" ]; then
    echo "CHECK FAIL  $name  ($margins)"; fails=$((fails + 1)); continue
  fi
  printf 'ok  %-46s %s\n' "$name" "$margins"
done

echo "--- corpus lint ---"
python3 "$SKILL/scripts/lint-corpus.py" "$ROOT" 2>&1 | tail -3
[ "$fails" -eq 0 ] || { echo "$fails diagram(s) failed"; exit 1; }
