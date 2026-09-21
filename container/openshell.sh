#!/usr/bin/env bash
set -euo pipefail

# Create an AI Guardian-managed OpenShell sandbox and upload only the DAF
# configuration tree. OpenShell state, cache, and session data remain
# sandbox-local; use container/run.sh when live host XDG persistence is wanted.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SANITIZER="${SCRIPT_DIR}/sanitize-config.py"
IMAGE="${DEVAIFLOW_IMAGE:-localhost/devaiflow-openshell:latest}"
AGENT="${AI_GUARDIAN_AGENT:-${AI_GUARDIAN_IDE:-codex}}"
NAME=""
REPO_PATH=""
CONFIG_DIR_OVERRIDE=""
POLICIES=()
NO_CONNECT=false
EXTRA_COMMAND=()
STAGE_DIR=""
SANDBOX_CREATED=false

_require_option_value() {
    if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "Error: $1 requires a value" >&2
        exit 2
    fi
}

_print_help() {
    echo "Usage: $0 [OPTIONS] [-- COMMAND...]"
    echo ""
    echo "Create an AI Guardian-managed OpenShell sandbox for DevAIFlow."
    echo ""
    echo "Options:"
    echo "  --image|--base IMAGE      Image to run (default: ${IMAGE})"
    echo "  --name NAME               OpenShell sandbox name"
    echo "  --cli|--agent NAME        AI agent (default: ${AGENT})"
    echo "  --repo DIR                Repository snapshot (default: current directory)"
    echo "  --config-dir DIR          Host DAF config directory to upload"
    echo "  --policy FILE             OpenShell policy overlay (repeatable)"
    echo "  --no-connect              Create and stage, but do not open a shell"
    echo "  --                        Execute a command after staging"
    echo ""
    echo "Only the DAF config tree is uploaded. Sessions, state, and cache stay in"
    echo "the sandbox. Use container/run.sh for live host-shared XDG directories."
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --image|--base)
            _require_option_value "$@"
            IMAGE="$2"
            shift 2
            ;;
        --name)
            _require_option_value "$@"
            NAME="$2"
            shift 2
            ;;
        --cli|--agent)
            _require_option_value "$@"
            AGENT="$2"
            shift 2
            ;;
        --repo)
            _require_option_value "$@"
            REPO_PATH="$2"
            shift 2
            ;;
        --config-dir)
            _require_option_value "$@"
            CONFIG_DIR_OVERRIDE="$2"
            shift 2
            ;;
        --policy)
            _require_option_value "$@"
            POLICIES+=("$2")
            shift 2
            ;;
        --no-connect)
            NO_CONNECT=true
            shift
            ;;
        --help|-h)
            _print_help
            exit 0
            ;;
        --)
            shift
            EXTRA_COMMAND=("$@")
            break
            ;;
        *)
            echo "Error: unknown option '$1'" >&2
            echo "Run '$0 --help' for usage." >&2
            exit 2
            ;;
    esac
done

if [[ -z "$NAME" ]]; then
    NAME="devaiflow-${AGENT}"
fi
if (( ${#NAME} > 19 )); then
    echo "Error: OpenShell sandbox names must be at most 19 characters: $NAME" >&2
    echo "Choose a shorter --name so the upload and lifecycle commands use the same name." >&2
    exit 2
fi
if [[ -z "$REPO_PATH" ]]; then
    REPO_PATH="${PWD:?}"
fi
if [[ ! -d "$REPO_PATH" ]]; then
    echo "Error: repository directory not found: $REPO_PATH" >&2
    exit 2
fi
REPO_PATH="$(cd -- "$REPO_PATH" && pwd -P)"

if [[ ${#POLICIES[@]} -eq 0 ]]; then
    POLICIES=("${SCRIPT_DIR}/openshell-github-readwrite-policy.yaml")
fi
for policy in "${POLICIES[@]}"; do
    if [[ ! -f "$policy" ]]; then
        echo "Error: OpenShell policy file not found: $policy" >&2
        exit 2
    fi
done
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required to sanitize the DevAIFlow config snapshot." >&2
    exit 2
fi

HOST_HOME="${HOME:-${PWD:-.}}"
if [[ "$HOST_HOME" != /* ]]; then
    HOST_HOME="${PWD:-.}/${HOST_HOME}"
fi
HOST_HOME="$(cd -- "$HOST_HOME" 2>/dev/null && pwd -P)"

_expand_path() {
    local value="$1"
    case "$value" in
        "~") value="$HOST_HOME" ;;
        "~/"*) value="$HOST_HOME/${value#~/}" ;;
    esac
    if [[ "$value" != /* ]]; then
        value="${PWD:-.}/$value"
    fi
    printf '%s\n' "$value"
}

_host_config_source() {
    if [[ -n "$CONFIG_DIR_OVERRIDE" ]]; then
        _expand_path "$CONFIG_DIR_OVERRIDE"
        return 0
    fi
    if [[ -n "${DEVAIFLOW_HOME:-}" ]]; then
        _expand_path "$DEVAIFLOW_HOME"
        return 0
    fi
    local legacy="${HOST_HOME}/.daf-sessions"
    if [[ -d "$legacy" && ( -f "$legacy/config.json" || -f "$legacy/sessions.json" ) ]]; then
        printf '%s\n' "$legacy"
        return 0
    fi
    _expand_path "${XDG_CONFIG_HOME:-${HOST_HOME}/.config}/devaiflow"
}

_copy_config_entry() {
    local source="$1"
    local destination="$2"
    if [[ -e "$source" || -L "$source" ]]; then
        python3 "$SANITIZER" "$source" "$destination"
        return 0
    fi
    return 1
}

_prepare_config_upload() {
    local source="$1"
    STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/devaiflow-config.XXXXXX")"
    local found=false
    local entry

    if [[ -f "$source" ]]; then
        cp -a -- "$source" "$STAGE_DIR/config.json"
        found=true
    elif [[ -d "$source" ]]; then
        # Keep unified-mode installs narrow: only configuration files and the
        # configuration-owned skill/template trees are uploaded. Session data,
        # logs, state, and clones never cross the OpenShell boundary.
        for entry in \
            config.json enterprise.json organization.json team.json templates.json \
            backends templates .claude ENTERPRISE.md ORGANIZATION.md TEAM.md USER.md; do
            if _copy_config_entry "$source/$entry" "$STAGE_DIR/$entry"; then
                found=true
            fi
        done
    fi

    if [[ "$found" != true ]]; then
        rm -rf -- "$STAGE_DIR"
        STAGE_DIR=""
    fi
}

cleanup() {
    local status=$?
    if [[ -n "$STAGE_DIR" && -d "$STAGE_DIR" ]]; then
        rm -rf -- "$STAGE_DIR"
    fi
    if [[ "$status" -ne 0 && "$SANDBOX_CREATED" == true ]]; then
        openshell sandbox delete "$NAME" >/dev/null 2>&1 || true
    fi
    return "$status"
}
trap cleanup EXIT

HOST_CONFIG_SOURCE="$(_host_config_source)"
_prepare_config_upload "$HOST_CONFIG_SOURCE"

if ! command -v ai-guardian >/dev/null 2>&1; then
    echo "Error: ai-guardian is required on the host." >&2
    exit 2
fi
if ! command -v openshell >/dev/null 2>&1; then
    echo "Error: openshell is required on the host." >&2
    exit 2
fi
if openshell sandbox get "$NAME" --output json >/dev/null 2>&1; then
    echo "Error: OpenShell sandbox already exists: $NAME" >&2
    echo "Choose a new --name so the upload and lifecycle commands remain unambiguous." >&2
    exit 2
fi

CREATE_ARGS=(
    ai-guardian sandbox create
    --runtime openshell
    --name "$NAME"
    --image "$IMAGE"
    --cli "$AGENT"
    --repo "$REPO_PATH"
    --env HOME=/sandbox
    --env XDG_DATA_HOME=/sandbox/.local/share
    --env XDG_CONFIG_HOME=/sandbox/.config
    --env XDG_STATE_HOME=/sandbox/.local/state
    --env XDG_CACHE_HOME=/sandbox/.cache
)
if [[ -n "$STAGE_DIR" ]]; then
    CREATE_ARGS+=(
        --env DEVAIFLOW_HOST_CONFIG_MOUNTED=true
        --env DEVAIFLOW_HOST_CONFIG_PATH=/sandbox/.config/devaiflow.host
        --env DEVAIFLOW_OPEN_SHELL_STAGING=true
    )
else
    CREATE_ARGS+=(--env DEVAIFLOW_HOST_CONFIG_MOUNTED=false)
fi
for policy in "${POLICIES[@]}"; do
    CREATE_ARGS+=(--policy "$policy")
done

# The AI Guardian lifecycle command performs the OpenShell bootstrap and
# exposes the gateway-managed ai-guardian service. An explicit no-op lets this
# script upload DAF's independent config before the user's command/shell starts.
CREATE_ARGS+=(-- /bin/true)
"${CREATE_ARGS[@]}"
SANDBOX_CREATED=true

if [[ -n "$STAGE_DIR" ]]; then
    openshell sandbox upload --no-git-ignore "$NAME" "$STAGE_DIR" \
        /sandbox/.config/devaiflow.host
    openshell sandbox exec --name "$NAME" --no-tty -- /usr/local/bin/devaiflow-stage
    cleanup
    STAGE_DIR=""
fi

if [[ "$NO_CONNECT" == true ]]; then
    echo "OpenShell sandbox is ready: $NAME"
    exit 0
fi

if [[ ${#EXTRA_COMMAND[@]} -gt 0 ]]; then
    EXEC_ARGS=(openshell sandbox exec --name "$NAME")
    if [[ -t 0 && -t 1 ]]; then
        EXEC_ARGS+=(--tty)
    else
        EXEC_ARGS+=(--no-tty)
    fi
    EXEC_ARGS+=(-- "${EXTRA_COMMAND[@]}")
    exec "${EXEC_ARGS[@]}"
fi

exec ai-guardian sandbox connect "$NAME"
