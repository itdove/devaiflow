#!/usr/bin/env bash
set -euo pipefail

# Run DevAIFlow in the AI Guardian OpenShell-compatible image with a narrow,
# explicit persistence contract. OpenShell's gateway launcher supports
# one-way uploads, not host bind mounts; this Docker/Podman launcher is the
# equivalent invocation for live host-shared XDG directories.

IMAGE="${DEVAIFLOW_IMAGE:-localhost/devaiflow-openshell:latest}"
CONTAINER_ENGINE="${CONTAINER_ENGINE:-podman}"
AGENT="${AI_GUARDIAN_AGENT:-${AI_GUARDIAN_IDE:-codex}}"
REST_PORT="${AI_GUARDIAN_REST_PORT:-63152}"
PROFILE=""
SETUP_SCOPE="${AI_GUARDIAN_SETUP_SCOPE:-selected}"
REPO_PATH=""
VOLUME_SUFFIX="${DEVAIFLOW_VOLUME_SUFFIX:-}"
EXTRA_ARGS=()

_require_option_value() {
    if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "Error: $1 requires a value" >&2
        exit 2
    fi
}

_print_help() {
    echo "Usage: $0 [OPTIONS] [-- COMMAND...]"
    echo ""
    echo "Run DevAIFlow in the AI Guardian OpenShell-compatible image."
    echo ""
    echo "Options:"
    echo "  --image IMAGE             Image to run (default: ${IMAGE})"
    echo "  --agent NAME              AI Guardian agent (default: ${AGENT})"
    echo "  --port PORT               Daemon REST port (default: ${REST_PORT})"
    echo "  --profile @NAME           Bundled AI Guardian profile"
    echo "  --setup-scope SCOPE       selected, cli, or all"
    echo "  --repo DIR                Mount one repository at /sandbox/repo"
    echo "  --                        Run a command instead of bash -l"
    echo ""
    echo "Persistence: host XDG */devaiflow directories are mounted read/write."
    echo "Use DEVAIFLOW_VOLUME_SUFFIX=:Z for SELinux relabeling when needed."
    echo "If host XDG values are temporary, set CONTAINER_ENGINE_HOME and"
    echo "CONTAINER_ENGINE_XDG_* to keep the engine's storage/config location."
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --image|--base)
            _require_option_value "$@"
            IMAGE="$2"
            shift 2
            ;;
        --agent|--ide)
            _require_option_value "$@"
            AGENT="$2"
            shift 2
            ;;
        --port)
            _require_option_value "$@"
            REST_PORT="$2"
            shift 2
            ;;
        --profile)
            _require_option_value "$@"
            PROFILE="$2"
            shift 2
            ;;
        --setup-scope)
            _require_option_value "$@"
            SETUP_SCOPE="$2"
            shift 2
            ;;
        --repo)
            _require_option_value "$@"
            REPO_PATH="$2"
            shift 2
            ;;
        --help|-h)
            _print_help
            exit 0
            ;;
        --)
            shift
            EXTRA_ARGS=("$@")
            break
            ;;
        *)
            echo "Error: unknown option '$1'" >&2
            echo "Run '$0 --help' for usage." >&2
            exit 2
            ;;
    esac
done

case "$SETUP_SCOPE" in
    selected|cli|all)
        ;;
    *)
        echo "Error: --setup-scope must be selected, cli, or all." >&2
        exit 2
        ;;
esac

if [[ -n "$PROFILE" && "$PROFILE" != @* ]]; then
    echo "Error: only bundled @profiles are accepted by this launcher." >&2
    echo "A host profile path is not mounted automatically." >&2
    exit 2
fi

if [[ ${#EXTRA_ARGS[@]} -eq 0 ]]; then
    EXTRA_ARGS=(bash -l)
fi

# Resolve HOME and relative XDG values the same way the Python path helpers do:
# relative values are relative to the current working directory, and a leading
# ~/ is relative to the host HOME. Only the final DevAIFlow directory is ever
# passed to the container engine.
HOST_HOME="${HOME:-${PWD:-.}}"
case "$HOST_HOME" in
    "~")
        HOST_HOME="${PWD:-.}"
        ;;
    "~/"*)
        HOST_HOME="${PWD:-.}/${HOST_HOME#~/}"
        ;;
esac
if [[ "$HOST_HOME" != /* ]]; then
    HOST_HOME="${PWD:-.}/${HOST_HOME}"
fi
if ! HOST_HOME="$(cd -- "$HOST_HOME" 2>/dev/null && pwd -P)"; then
    echo "Error: host HOME does not exist: ${HOME:-$HOST_HOME}" >&2
    exit 2
fi

_expand_host_path() {
    local value="$1"
    case "$value" in
        "~")
            value="$HOST_HOME"
            ;;
        "~/"*)
            value="$HOST_HOME/${value#~/}"
            ;;
    esac
    if [[ "$value" != /* ]]; then
        value="${PWD:-.}/${value}"
    fi
    printf '%s\n' "$value"
}

_prepare_host_dir() {
    local requested="$1"
    local path
    path="$(_expand_host_path "$requested")"
    mkdir -p -- "$path"
    if [[ ! -d "$path" || ! -r "$path" || ! -w "$path" ]]; then
        echo "Error: host DevAIFlow directory must be readable and writable: $path" >&2
        exit 2
    fi
    (cd -- "$path" && pwd -P)
}

PERSISTENCE_MODE="xdg"
HOST_PERSISTENCE_DIRS=()
CONTAINER_PERSISTENCE_DIRS=()

HOST_DEVAIFLOW_HOME="${DEVAIFLOW_HOME:-}"
LEGACY_HOME="${HOST_HOME}/.daf-sessions"
if [[ -z "$HOST_DEVAIFLOW_HOME" && -d "$LEGACY_HOME" && \
    ( -f "$LEGACY_HOME/config.json" || -f "$LEGACY_HOME/sessions.json" ) ]]; then
    HOST_DEVAIFLOW_HOME="$LEGACY_HOME"
fi

if [[ -n "$HOST_DEVAIFLOW_HOME" ]]; then
    PERSISTENCE_MODE="unified"
    HOST_PERSISTENCE_DIRS+=("$(_prepare_host_dir "$HOST_DEVAIFLOW_HOME")")
    CONTAINER_PERSISTENCE_DIRS+=("/sandbox/.devaiflow")
else
    HOST_DATA_ROOT="${XDG_DATA_HOME:-${HOST_HOME}/.local/share}"
    HOST_CONFIG_ROOT="${XDG_CONFIG_HOME:-${HOST_HOME}/.config}"
    HOST_STATE_ROOT="${XDG_STATE_HOME:-${HOST_HOME}/.local/state}"
    HOST_CACHE_ROOT="${XDG_CACHE_HOME:-${HOST_HOME}/.cache}"

    HOST_PERSISTENCE_DIRS+=(
        "$(_prepare_host_dir "${HOST_DATA_ROOT}/devaiflow")"
        "$(_prepare_host_dir "${HOST_CONFIG_ROOT}/devaiflow")"
        "$(_prepare_host_dir "${HOST_STATE_ROOT}/devaiflow")"
        "$(_prepare_host_dir "${HOST_CACHE_ROOT}/devaiflow")"
    )
    CONTAINER_PERSISTENCE_DIRS+=(
        "/sandbox/.local/share/devaiflow"
        "/sandbox/.config/devaiflow"
        "/sandbox/.local/state/devaiflow"
        "/sandbox/.cache/devaiflow"
    )
fi

if [[ -n "$REPO_PATH" ]]; then
    if [[ ! -d "$REPO_PATH" ]]; then
        echo "Error: repository directory not found: $REPO_PATH" >&2
        exit 2
    fi
    REPO_PATH="$(cd -- "$REPO_PATH" && pwd -P)"
fi

env_args=(
    --env "HOME=/sandbox"
    --env "XDG_DATA_HOME=/sandbox/.local/share"
    --env "XDG_CONFIG_HOME=/sandbox/.config"
    --env "XDG_STATE_HOME=/sandbox/.local/state"
    --env "XDG_CACHE_HOME=/sandbox/.cache"
    --env "AI_GUARDIAN_AGENT=${AGENT}"
    --env "AI_GUARDIAN_IDE=${AGENT}"
    --env "AI_GUARDIAN_HOME=/sandbox/.config/ai-guardian"
    --env "AI_GUARDIAN_CONFIG_DIR=/sandbox/.config/ai-guardian"
    --env "AI_GUARDIAN_REST_PORT=${REST_PORT}"
    --env "AI_GUARDIAN_REST_HOST=0.0.0.0"
    --env "AI_GUARDIAN_HOST_CONFIG_MOUNTED=false"
    --env "AI_GUARDIAN_SETUP_SCOPE=${SETUP_SCOPE}"
)
if [[ -n "$PROFILE" ]]; then
    env_args+=(--env "AI_GUARDIAN_PROFILE=${PROFILE}")
fi
if [[ "$PERSISTENCE_MODE" = unified ]]; then
    env_args+=(--env "DEVAIFLOW_HOME=/sandbox/.devaiflow")
fi

volume_args=()
for index in "${!HOST_PERSISTENCE_DIRS[@]}"; do
    volume_args+=(
        --volume
        "${HOST_PERSISTENCE_DIRS[$index]}:${CONTAINER_PERSISTENCE_DIRS[$index]}${VOLUME_SUFFIX}"
    )
done
if [[ -n "$REPO_PATH" ]]; then
    volume_args+=(--volume "${REPO_PATH}:/sandbox/repo${VOLUME_SUFFIX}")
fi

engine_args=()
engine_name="${CONTAINER_ENGINE##*/}"
if [[ "$engine_name" = podman ]]; then
    # Keep newly-created host directories writable by the host user while the
    # image continues to run as its unprivileged sandbox user.
    engine_args+=(--userns=keep-id)
fi
if [[ "$IMAGE" = localhost/* ]]; then
    # A local development tag must never fall back to a registry lookup.
    engine_args+=(--pull=never)
fi
# Publish the daemon's internal REST port on a runtime-selected host port.
# AI Guardian discovery reads the resulting container mapping, which allows
# multiple sandboxes to coexist without guessing a host port.
engine_args+=(
    --publish "$REST_PORT"
    --label "ai-guardian.managed=true"
    --label "ai-guardian.daemon=true"
    --label "ai-guardian.runtime=container"
    --label "ai-guardian.rest-port=${REST_PORT}"
)

# The host XDG variables are used above to locate DevAIFlow's persistence
# directories. They can also affect where Podman stores images, which is
# surprising when a caller supplies temporary XDG roots (as the smoke test
# does). Allow callers to keep the engine's own HOME/XDG environment separate
# without forwarding any additional host paths into the container.
engine_environment_set=()
engine_environment_unset=()
_add_engine_environment_override() {
    local engine_variable="$1"
    local override_variable="$2"
    if [[ -v "$override_variable" ]]; then
        local value="${!override_variable}"
        if [[ -n "$value" ]]; then
            engine_environment_set+=("${engine_variable}=${value}")
        else
            engine_environment_unset+=("$engine_variable")
        fi
    fi
}

_add_engine_environment_override HOME CONTAINER_ENGINE_HOME
_add_engine_environment_override XDG_DATA_HOME CONTAINER_ENGINE_XDG_DATA_HOME
_add_engine_environment_override XDG_CONFIG_HOME CONTAINER_ENGINE_XDG_CONFIG_HOME
_add_engine_environment_override XDG_STATE_HOME CONTAINER_ENGINE_XDG_STATE_HOME
_add_engine_environment_override XDG_CACHE_HOME CONTAINER_ENGINE_XDG_CACHE_HOME

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DevAIFlow OpenShell-Compatible Container"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Image:       ${IMAGE}"
echo "  Engine:      ${CONTAINER_ENGINE}"
echo "  Agent:       ${AGENT}"
echo "  REST port:   ${REST_PORT} (host port selected by ${CONTAINER_ENGINE})"
echo "  Persistence: ${PERSISTENCE_MODE} host mapping"
[[ -n "$REPO_PATH" ]] && echo "  Repo:        ${REPO_PATH} -> /sandbox/repo"
echo ""

engine_command=(
    "$CONTAINER_ENGINE" run --rm -it
    "${engine_args[@]}"
    "${env_args[@]}"
    "${volume_args[@]}"
    "$IMAGE"
    "${EXTRA_ARGS[@]}"
)

if [[ ${#engine_environment_set[@]} -gt 0 || ${#engine_environment_unset[@]} -gt 0 ]]; then
    engine_environment_args=()
    for variable in "${engine_environment_unset[@]}"; do
        engine_environment_args+=(-u "$variable")
    done
    engine_environment_args+=("${engine_environment_set[@]}")
    exec env "${engine_environment_args[@]}" "${engine_command[@]}"
else
    exec "${engine_command[@]}"
fi
