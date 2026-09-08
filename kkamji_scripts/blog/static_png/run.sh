#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PY="${DIAGRAM_PYTHON:-python3}"
# Supply an existing environment through DIAGRAM_PYTHON/PYTHONPATH. Never install.
if [[ "${1:-}" == test ]]; then
  exec "$PY" -m unittest discover -s "$ROOT" -p 'test_*.py' -v
elif [[ "${1:-}" == corpus ]]; then
  shift
  exec "$PY" "$ROOT/corpus.py" "$@"
fi
exec "$PY" "$ROOT/pipeline.py" "$@"
