#!/usr/bin/env bash
set -euo pipefail

# Stage a host DevAIFlow configuration snapshot into the sandbox-local
# configuration directory.  OpenShell uploads arrive after the canonical
# process starts, so the optional wait is intentionally bounded and enabled
# only when the caller requested staging.

HOST_CONFIG_MOUNTED="${DEVAIFLOW_HOST_CONFIG_MOUNTED:-false}"
HOST_CONFIG_PATH="${DEVAIFLOW_HOST_CONFIG_PATH:-/sandbox/.config/devaiflow.host}"
OPEN_SHELL_STAGING="${DEVAIFLOW_OPEN_SHELL_STAGING:-false}"
WAIT_ATTEMPTS="${DEVAIFLOW_OPEN_SHELL_WAIT_ATTEMPTS:-1200}"
PYTHON="${DEVAIFLOW_PYTHON:-/sandbox/.venv/bin/python}"

if [[ "$HOST_CONFIG_MOUNTED" != "true" ]]; then
    exit 0
fi

_wait_for_upload() {
    local attempts=0

    if [[ -e "$HOST_CONFIG_PATH" ]]; then
        return 0
    fi
    if [[ "$OPEN_SHELL_STAGING" != "true" ]]; then
        echo "Error: host DevAIFlow config is missing: $HOST_CONFIG_PATH" >&2
        exit 1
    fi

    echo "Waiting for OpenShell to upload DevAIFlow config: $HOST_CONFIG_PATH"
    while [[ ! -e "$HOST_CONFIG_PATH" ]]; do
        if (( attempts >= WAIT_ATTEMPTS )); then
            echo "Error: timed out waiting for OpenShell upload: $HOST_CONFIG_PATH" >&2
            exit 1
        fi
        sleep 0.1
        attempts=$((attempts + 1))
    done
}

_active_config_dir() {
    if [[ -n "${DEVAIFLOW_ACTIVE_CONFIG_DIR:-}" ]]; then
        printf '%s\n' "$DEVAIFLOW_ACTIVE_CONFIG_DIR"
        return 0
    fi

    # XDG-aware DevAIFlow exposes get_cs_config_home(). Older pinned releases
    # predate the XDG split and use ~/.daf-sessions instead. Keep the fallback
    # so the image can accept either the stable wheel or a development wheel.
    if [[ -x "$PYTHON" ]]; then
        "$PYTHON" -c \
            'from devflow.utils.paths import get_cs_config_home; print(get_cs_config_home())' \
            2>/dev/null && return 0
    fi
    printf '%s\n' "${HOME:-/sandbox}/.daf-sessions"
}

_wait_for_upload
ACTIVE_CONFIG_DIR="$(_active_config_dir)"
mkdir -p -- "$ACTIVE_CONFIG_DIR"

# A sandbox-local configuration wins, exactly like AI Guardian's host-config
# precedence rule. The uploaded host tree is never written back to the host.
if [[ -f "$ACTIVE_CONFIG_DIR/config.json" ]]; then
    echo "Using sandbox-local DevAIFlow config: $ACTIVE_CONFIG_DIR"
    exit 0
fi

if [[ -d "$HOST_CONFIG_PATH" ]]; then
    cp -a -- "$HOST_CONFIG_PATH"/. "$ACTIVE_CONFIG_DIR"/
elif [[ -f "$HOST_CONFIG_PATH" ]]; then
    install -m 0600 -- "$HOST_CONFIG_PATH" "$ACTIVE_CONFIG_DIR/config.json"
else
    echo "Error: uploaded DevAIFlow config is neither a file nor directory: $HOST_CONFIG_PATH" >&2
    exit 1
fi

echo "Using host DevAIFlow config snapshot: $ACTIVE_CONFIG_DIR"
