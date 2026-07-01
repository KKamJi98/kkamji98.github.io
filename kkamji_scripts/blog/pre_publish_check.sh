#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "${REPO_ROOT}"

echo "=== Blog pre-publish check ==="

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "WARN: gitleaks not found; skipping staged secret scan" >&2
else
  echo "=== gitleaks staged scan ==="
  gitleaks protect --staged --redact --verbose
fi

echo "=== Markdown tools ==="
"${SCRIPT_DIR}/run_md_tools.sh"

echo "=== Quality audit ==="
"${PYTHON_BIN}" "${SCRIPT_DIR}/audit_blog_quality.py"

"${PYTHON_BIN}" - <<'PY'
import csv
from pathlib import Path
report = Path('.hermes/reports/blog-quality-audit.csv')
rows = list(csv.DictReader(report.open(encoding='utf-8')))
failures = []
for row in rows:
    issues = row.get('issues', '')
    if 'missing frontmatter' in issues:
        failures.append((row['path'], 'missing frontmatter'))
    if 'missing image' in issues:
        failures.append((row['path'], 'missing image'))
    if 'missing internal post link' in issues:
        failures.append((row['path'], 'missing internal post link'))
    if 'forbidden character' in issues:
        failures.append((row['path'], 'forbidden character'))
if failures:
    print('Quality gate failed:')
    for path, issue in failures[:50]:
        print(f'- {path}: {issue}')
    if len(failures) > 50:
        print(f'- ... {len(failures) - 50} more')
    raise SystemExit(1)
print('Quality gate passed: no blocking mechanical issues')
PY

echo "=== Git status ==="
git status --short --branch
