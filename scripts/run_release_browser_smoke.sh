#!/usr/bin/env bash
set -euo pipefail

: "${COYOTE3_E2E_BASE_URL:?Set COYOTE3_E2E_BASE_URL to the deployed SCRIPT_NAME prefix.}"
: "${COYOTE3_E2E_USERNAME:?Set a controlled local validation account.}"
: "${COYOTE3_E2E_PASSWORD:?Set the validation account password outside git.}"
: "${COYOTE3_E2E_DNA_SAMPLE:?Set a controlled DNA validation sample name.}"
: "${COYOTE3_E2E_RNA_SAMPLE:?Set a controlled RNA validation sample name.}"

cd "$(dirname "$0")/../frontend"
npm run test:e2e:real
