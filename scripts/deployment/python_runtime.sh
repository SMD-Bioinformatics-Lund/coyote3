#!/usr/bin/env bash
# Shared host interpreter selection; container commands retain their image's Python.

select_deployment_python() {
  local repository="$1" candidate resolved
  local candidates=()
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    candidates=("$PYTHON_BIN")
  else
    candidates=("$repository/.venv/bin/python" python3 python3.14 python3.13 python3.12)
  fi
  for candidate in "${candidates[@]}"; do
    if resolved="$(command -v "$candidate")" && \
      "$resolved" -c 'import sys, tomllib; sys.exit(sys.version_info < (3, 12))' \
        >/dev/null 2>&1; then
      # Preserve virtual-environment symlinks when making the path absolute.
      PYTHON_BIN="$(cd "$(dirname "$resolved")" && pwd)/$(basename "$resolved")"
      export PYTHON_BIN
      return 0
    fi
  done
  echo "ERROR: Host deployment requires Python 3.12 or later. Set PYTHON_BIN to a supported interpreter; tomllib is part of Python, not a package to install." >&2
  return 1
}
