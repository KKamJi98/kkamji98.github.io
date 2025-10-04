#!/usr/bin/env bash
set -euo pipefail

# 현재 디렉토리에 필요한 스크립트가 있는지 확인
if [[ ! -f "./fix_md_h2_rules.py" ]]; then
  echo "Error: fix_md_h2_rules.py not found in current directory." >&2
  exit 1
fi

if [[ ! -f "./renumber_headers.py" ]]; then
  echo "Error: renumber_headers.py not found in current directory." >&2
  exit 1
fi

echo "Running: python fix_md_h2_rules.py --no-backup --verbose"
python fix_md_h2_rules.py --no-backup --verbose

echo "Running: python renumber_headers.py"
python renumber_headers.py

echo "All done."

