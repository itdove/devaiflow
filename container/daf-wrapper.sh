#!/usr/bin/env bash
set -euo pipefail

# Released DevAIFlow versions before split-XDG support only understand
# DEVAIFLOW_HOME. Keep those versions on the mounted data directory while
# allowing XDG-aware wheels to use all four mounted roots independently.
PYTHON="${DEVAIFLOW_PYTHON:-/sandbox/.venv/bin/python}"
if [[ -z "${DEVAIFLOW_HOME:-}" ]] && [[ -x "$PYTHON" ]]; then
    if ! "$PYTHON" -c 'from devflow.utils.paths import get_cs_config_home' >/dev/null 2>&1; then
        export DEVAIFLOW_HOME=/sandbox/.local/share/devaiflow
    fi
fi

if [[ "${DEVAIFLOW_HOST_CONFIG_MOUNTED:-false}" == "true" ]]; then
    /usr/local/bin/devaiflow-stage
fi

exec /sandbox/.venv/bin/daf-real "$@"
