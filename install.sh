#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

# Public entry point. Deployment logic lives in deploy/installer.
set -euo pipefail
umask 077
repository="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${PYTHON_BIN:-}" ]]; then
  candidates=("$PYTHON_BIN")
else
  candidates=("$repository/.venv/bin/python" python3 python3.14 python3.13 python3.12)
fi
for candidate in "${candidates[@]}"; do
  if interpreter="$(command -v "$candidate")" && \
    "$interpreter" -c 'import sys, tomllib; sys.exit(sys.version_info < (3, 12))' >/dev/null 2>&1; then
    export PYTHONPATH="$repository${PYTHONPATH:+:$PYTHONPATH}"
    export PYTHONDONTWRITEBYTECODE=1
    exec "$interpreter" -P -m deploy.installer "$@"
  fi
done
echo '[ERROR] Installation requires Python 3.12 or later. Set PYTHON_BIN to a supported interpreter.' >&2
exit 1
