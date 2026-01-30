#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

FIX_SCRIPT="${SCRIPT_DIR}/fix_md_h2_rules.py"
RENUMBER_SCRIPT="${SCRIPT_DIR}/renumber_headers.py"

if [[ ! -f "${FIX_SCRIPT}" ]]; then
  echo "Error: fix_md_h2_rules.py not found next to run_md_tools.sh." >&2
  exit 1
fi

if [[ ! -f "${RENUMBER_SCRIPT}" ]]; then
  echo "Error: renumber_headers.py not found next to run_md_tools.sh." >&2
  exit 1
fi

ROOT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      if [[ $# -lt 2 ]]; then
        echo "Error: --root requires a directory argument." >&2
        exit 1
      fi
      ROOT_DIR="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--root <directory>]" >&2
      exit 1
      ;;
  esac
done

# Default to _posts if no root specified
if [[ -z "${ROOT_DIR}" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
  ROOT_DIR="${REPO_ROOT}/_posts"
fi

if [[ ! -d "${ROOT_DIR}" ]]; then
  echo "Error: Directory not found: ${ROOT_DIR}" >&2
  exit 1
fi

ROOT_ARG=(--root "${ROOT_DIR}")

run_python() {
  local script_path="$1"
  shift
  "${PYTHON_BIN}" "${script_path}" "$@" "${ROOT_ARG[@]}"
}

# =============================================================================
# 1. Fix blockquote and prompt block format
# =============================================================================
echo "=== Fixing blockquote format (trailing spaces) ==="

fix_blockquote_format() {
  local dir="$1"
  local count=0

  while IFS= read -r -d '' file; do
    local modified=false

    # Fix 1: Add blank line after --- before > **궁금 (prompt-info contact block)
    if perl -0ne 'exit(!/---\n> \*\*궁금/)' "$file" 2>/dev/null; then
      perl -i -0pe 's/---\n(> \*\*궁금)/---\n\n$1/g' "$file"
      modified=true
    fi

    # Fix 2: Remove > before {: .prompt-*} (should not have > prefix)
    if grep -q '^> {: \.prompt-' "$file"; then
      perl -i -pe 's/^> (\{: \.prompt-[^}]+\})$/$1/g' "$file"
      modified=true
    fi

    # Fix 3: Add trailing two spaces to ALL blockquote lines with content
    # Lines starting with "> " followed by content, NOT ending with "  "
    # Exclude lines that are just "> {:" (attribute syntax)
    # Using Python for reliable UTF-8 handling
    "${PYTHON_BIN}" -c "
import re
import sys

with open('$file', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern: lines starting with '> ' followed by content (not {: attribute)
# that don't already end with two spaces
def add_trailing_spaces(match):
    line = match.group(0)
    # Skip attribute lines like '> {: .prompt-info}'
    if line.startswith('> {:'):
        return line
    # Skip if already ends with two spaces
    if line.endswith('  '):
        return line
    return line + '  '

# Match blockquote lines with content
new_content = re.sub(r'^> [^\n]+$', add_trailing_spaces, content, flags=re.MULTILINE)

if new_content != content:
    with open('$file', 'w', encoding='utf-8') as f:
        f.write(new_content)
    sys.exit(0)  # Modified
else:
    sys.exit(1)  # Not modified
" 2>/dev/null && modified=true

    if [[ "$modified" == "true" ]]; then
      echo "Fixed: $file"
      ((count++)) || true
    fi
  done < <(find "$dir" -name "*.md" -print0)

  echo "Fixed ${count} files"
}

fix_blockquote_format "${ROOT_DIR}"

# =============================================================================
# 2. Fix H2 rules (existing)
# =============================================================================
echo ""
echo "=== Running fix_md_h2_rules.py ==="
run_python "${FIX_SCRIPT}" --no-backup --verbose

# =============================================================================
# 3. Renumber headers (existing)
# =============================================================================
echo ""
echo "=== Running renumber_headers.py ==="
run_python "${RENUMBER_SCRIPT}"

echo ""
echo "All done."
