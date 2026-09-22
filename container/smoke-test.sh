#!/usr/bin/env bash
set -euo pipefail

# Smoke-test a locally built image. The test intentionally creates temporary
# host XDG roots, runs two disposable containers, and verifies that the first
# container's marker is visible to the second one through the documented
# DevAIFlow-only mounts.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
LAUNCHER="${SCRIPT_DIR}/run.sh"
IMAGE="${DEVAIFLOW_IMAGE:-localhost/devaiflow-openshell:latest}"
CONTAINER_ENGINE="${CONTAINER_ENGINE:-podman}"
VOLUME_SUFFIX="${DEVAIFLOW_VOLUME_SUFFIX-}"
if [[ -z "$VOLUME_SUFFIX" && "${CONTAINER_ENGINE##*/}" = podman && \
    -r /sys/fs/selinux/enforce && "$(< /sys/fs/selinux/enforce)" = 1 ]]; then
    VOLUME_SUFFIX=:Z
fi
# Preserve the engine's normal configuration while the launcher uses the
# temporary XDG roots below for DevAIFlow itself.
ENGINE_HOME="${HOME-}"
ENGINE_XDG_DATA_HOME="${XDG_DATA_HOME-}"
ENGINE_XDG_CONFIG_HOME="${XDG_CONFIG_HOME-}"
ENGINE_XDG_STATE_HOME="${XDG_STATE_HOME-}"
ENGINE_XDG_CACHE_HOME="${XDG_CACHE_HOME-}"
SMOKE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/devaiflow-openshell-smoke.XXXXXX")"
trap 'rm -rf -- "$SMOKE_ROOT"' EXIT

if ! command -v "$CONTAINER_ENGINE" >/dev/null 2>&1 && [[ ! -x "$CONTAINER_ENGINE" ]]; then
    echo "Error: container engine not found: ${CONTAINER_ENGINE}" >&2
    exit 2
fi

HOST_HOME="${SMOKE_ROOT}/home"
HOST_DATA_HOME="${SMOKE_ROOT}/xdg-data"
HOST_CONFIG_HOME="${SMOKE_ROOT}/xdg-config"
HOST_STATE_HOME="${SMOKE_ROOT}/xdg-state"
HOST_CACHE_HOME="${SMOKE_ROOT}/xdg-cache"
mkdir -p "$HOST_HOME" "$HOST_DATA_HOME" "$HOST_CONFIG_HOME" "$HOST_STATE_HOME" "$HOST_CACHE_HOME"
# The validation command may run rootful Podman under an elevated test
# harness. Make only these disposable final mount points writable by the
# image's unprivileged sandbox user; normal rootless Podman uses keep-id.
mkdir -p \
    "$HOST_DATA_HOME/devaiflow" \
    "$HOST_CONFIG_HOME/devaiflow" \
    "$HOST_STATE_HOME/devaiflow" \
    "$HOST_CACHE_HOME/devaiflow"
chmod 0777 \
    "$HOST_DATA_HOME/devaiflow" \
    "$HOST_CONFIG_HOME/devaiflow" \
    "$HOST_STATE_HOME/devaiflow" \
    "$HOST_CACHE_HOME/devaiflow"
printf '{"source":"container-smoke-test"}\n' > "$HOST_CONFIG_HOME/devaiflow/config.json"

_run_container() {
    local command="$1"
    (
        unset DEVAIFLOW_HOME
        HOME="$HOST_HOME" \
        XDG_DATA_HOME="$HOST_DATA_HOME" \
        XDG_CONFIG_HOME="$HOST_CONFIG_HOME" \
        XDG_STATE_HOME="$HOST_STATE_HOME" \
        XDG_CACHE_HOME="$HOST_CACHE_HOME" \
        DEVAIFLOW_IMAGE="$IMAGE" \
        CONTAINER_ENGINE="$CONTAINER_ENGINE" \
        DEVAIFLOW_VOLUME_SUFFIX="$VOLUME_SUFFIX" \
        CONTAINER_ENGINE_HOME="$ENGINE_HOME" \
        CONTAINER_ENGINE_XDG_DATA_HOME="$ENGINE_XDG_DATA_HOME" \
        CONTAINER_ENGINE_XDG_CONFIG_HOME="$ENGINE_XDG_CONFIG_HOME" \
        CONTAINER_ENGINE_XDG_STATE_HOME="$ENGINE_XDG_STATE_HOME" \
        CONTAINER_ENGINE_XDG_CACHE_HOME="$ENGINE_XDG_CACHE_HOME" \
        AI_GUARDIAN_AGENT=codex \
        AI_GUARDIAN_SETUP_SCOPE=selected \
        "$LAUNCHER" --agent codex -- bash -lc "$command"
    )
}

_run_container '
set -eu
command -v daf >/dev/null
cmp "$(command -v daf)" /usr/local/bin/daf
daf --version >/dev/null
test "$XDG_CONFIG_HOME" = "/sandbox/.config"
test "$XDG_DATA_HOME" = "/sandbox/.local/share"
test "$XDG_STATE_HOME" = "/sandbox/.local/state"
test "$XDG_CACHE_HOME" = "/sandbox/.cache"
test "$HOME" = "/sandbox"
test -d /sandbox/.config/devaiflow
test -d /sandbox/.local/share/devaiflow
test -d /sandbox/.local/state/devaiflow
test -d /sandbox/.cache/devaiflow
test ! -e /sandbox/.daf-sessions
test -f /sandbox/.config/devaiflow/config.json
if python -c "from devflow.utils.paths import get_cs_config_home" >/dev/null 2>&1; then
    test -f /sandbox/.config/devaiflow/config.json
else
    test -f /sandbox/.local/share/devaiflow/config.json
fi
test -f /usr/share/devaiflow/openshell-github-readwrite-policy.yaml
grep -F "host: api.github.com" /usr/share/devaiflow/openshell-github-readwrite-policy.yaml >/dev/null
grep -F "path: \"/**/git-receive-pack\"" /usr/share/devaiflow/openshell-github-readwrite-policy.yaml >/dev/null
printf "persisted by container smoke test\n" > /sandbox/.local/share/devaiflow/.container-smoke-marker
'

MARKER="${HOST_DATA_HOME}/devaiflow/.container-smoke-marker"
if [[ ! -f "$MARKER" ]]; then
    echo "Error: container did not persist its data mount to the host: ${MARKER}" >&2
    exit 1
fi

_run_container '
set -eu
test -f /sandbox/.local/share/devaiflow/.container-smoke-marker
test "$(cat /sandbox/.local/share/devaiflow/.container-smoke-marker)" = "persisted by container smoke test"
'

echo "OpenShell-compatible DevAIFlow smoke test passed."
