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

ROOT_ARG=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      if [[ $# -lt 2 ]]; then
        echo "Error: --root requires a directory argument." >&2
        exit 1
      fi
      ROOT_ARG=(--root "$2")
      shift 2
      ;;
    *)
      echo "Usage: $0 [--root <directory>]" >&2
      exit 1
      ;;
  esac
done

ROOT_SUFFIX=""
if [[ ${#ROOT_ARG[@]} -gt 0 ]]; then
  ROOT_SUFFIX=" ${ROOT_ARG[*]}"
fi

run_python() {
  local script_path="$1"
  shift

  if [[ ${#ROOT_ARG[@]} -gt 0 ]]; then
    "${PYTHON_BIN}" "${script_path}" "$@" "${ROOT_ARG[@]}"
  else
    "${PYTHON_BIN}" "${script_path}" "$@"
  fi
}

echo "Running: ${PYTHON_BIN} ${FIX_SCRIPT} --no-backup --verbose${ROOT_SUFFIX}"
run_python "${FIX_SCRIPT}" --no-backup --verbose

echo "Running: ${PYTHON_BIN} ${RENUMBER_SCRIPT}${ROOT_SUFFIX}"
run_python "${RENUMBER_SCRIPT}"

echo "All done."
