#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEVAIFLOW_HOST_CONFIG_MOUNTED:-false}" == "true" ]]; then
    /usr/local/bin/devaiflow-stage
fi

exec /sandbox/.venv/bin/daf "$@"
