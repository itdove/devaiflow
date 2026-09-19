# DevAIFlow OpenShell-Compatible Container

This directory builds a DevAIFlow image on top of the published AI Guardian
OpenShell image. The AI Guardian base supplies the OpenShell filesystem layout,
agent integrations, entrypoint, and security policy. DevAIFlow is installed in
the base image's `/sandbox/.venv` and is available as `daf` for the unprivileged
`sandbox` user.

## Build

The default build installs the pinned stable PyPI release declared by
`DEVAIFLOW_VERSION`:

```bash
podman build \
  -f container/Dockerfile.openshell \
  -t localhost/devaiflow-openshell:latest \
  container/
```

The default is intentionally pinned instead of using a floating PyPI install:

```bash
podman build \
  --build-arg DEVAIFLOW_VERSION=2.2.0 \
  -f container/Dockerfile.openshell \
  -t localhost/devaiflow-openshell:2.2.0 \
  container/
```

To install a local wheel, place exactly one wheel in `container/vendor/` and
pass its filename explicitly:

```bash
python -m build --wheel
cp dist/devaiflow-*.whl container/vendor/
podman build \
  --build-arg DEVAIFLOW_WHEEL=devaiflow-3.0.0.dev0-py3-none-any.whl \
  -f container/Dockerfile.openshell \
  -t localhost/devaiflow-openshell:dev \
  container/
```

`docker build` is also supported. Override `BASE_IMAGE` deliberately when
testing a pinned AI Guardian OpenShell release; the default follows the
published `:latest` image.

The image contains the minimum GitHub read/write OpenShell overlay at
`/usr/share/devaiflow/openshell-github-readwrite-policy.yaml`. It allows the
GitHub REST API for `gh`/`curl` and Git smart HTTP fetch/push for `git`; it does
not contain credentials.

## Host-persistent run

Use `run.sh` for the host-sharing contract:

```bash
container/run.sh \
  --image localhost/devaiflow-openshell:latest \
  --repo "$PWD"
```

The launcher creates missing host directories and mounts only these paths:

| Host path | Container path | Contents |
| --- | --- | --- |
| `${XDG_DATA_HOME:-$HOME/.local/share}/devaiflow` | `/sandbox/.local/share/devaiflow` | sessions, backups, logs |
| `${XDG_CONFIG_HOME:-$HOME/.config}/devaiflow` | `/sandbox/.config/devaiflow` | config, backends, templates, skills, context |
| `${XDG_STATE_HOME:-$HOME/.local/state}/devaiflow` | `/sandbox/.local/state/devaiflow` | audit and runtime state |
| `${XDG_CACHE_HOME:-$HOME/.cache}/devaiflow` | `/sandbox/.cache/devaiflow` | clones and reproducible cache |

Inside the container, the corresponding `XDG_*` variables point at the
`/sandbox` roots above. The image does not set `DEVAIFLOW_HOME`, so fresh hosts
use the normal split XDG layout. For compatibility with the pinned 2.2.0
fallback, the image links `/sandbox/.daf-sessions` into the data directory;
an XDG-aware wheel uses the split paths and an explicit `DEVAIFLOW_HOME` still
takes precedence.

The launcher also starts the AI Guardian daemon on the container's REST port
(63152 by default), publishes that port to a runtime-selected host port, and
adds the `ai-guardian.daemon=true`, `ai-guardian.managed=true`, and
`ai-guardian.rest-port` labels used by the tray/NiceGUI container discovery.
The host port is intentionally selected by Podman/Docker so multiple sessions
can run at once. To use a different daemon port, pass `--port PORT`.

The tray and NiceGUI must use the same host Podman/Docker socket as the
launcher. To verify the mapping from the host, list the managed container and
query its published port:

```bash
podman ps --filter label=ai-guardian.daemon=true
podman port <container-id> 63152/tcp
curl http://127.0.0.1:<host-port>/api/health
```

`/api/health` does not require a token. The tray obtains the generated daemon
token through the container runtime for authenticated status/control calls;
manual NiceGUI targets must use the same token if discovery is unavailable.
Do not point `AI_GUARDIAN_DAEMON_URL` at the container-internal
`127.0.0.1:63152` unless it is also the host-published port.

On SELinux hosts, add the standard container relabel suffix without changing
the host paths:

```bash
DEVAIFLOW_VOLUME_SUFFIX=:Z container/run.sh \
  --image localhost/devaiflow-openshell:latest \
  --repo "$PWD"
```

For Podman, `run.sh` uses `--userns=keep-id` so newly created persistence
directories remain usable by both the host user and the sandbox user. Existing
directories are never copied, deleted, or migrated by the launcher.

## Existing installations

The launcher preserves both supported DevAIFlow storage modes:

* An explicitly set host `DEVAIFLOW_HOME` is mounted at
  `/sandbox/.devaiflow`, and the container receives
  `DEVAIFLOW_HOME=/sandbox/.devaiflow`.
* A valid legacy `$HOME/.daf-sessions` installation (containing
  `config.json` or `sessions.json`) is detected and mounted the same way.
* Otherwise, the four XDG directories above are created and mounted. Empty
  legacy directories do not force unified mode, matching DevAIFlow's path
  resolution rules.

This lets a fresh host start without preparation while an existing host keeps
using its original files. Use the [XDG directory migration guide](../docs/guides/xdg-directories.md)
if you want to migrate a unified installation intentionally.

## OpenShell gateway mode

OpenShell's `sandbox create --upload` transfers a snapshot into the sandbox;
the current CLI does not expose host bind mounts. Therefore live host-shared
XDG persistence uses `run.sh` with Podman or Docker. For an isolated OpenShell
gateway session, use the merged AI Guardian sandbox lifecycle command with
this image:

```bash
ai-guardian sandbox create \
  --runtime openshell \
  --name devaiflow-codex \
  --image localhost/devaiflow-openshell:latest \
  --cli codex \
  --policy ./container/openshell-github-readwrite-policy.yaml \
  --repo "$PWD"
```

The AI Guardian command composes the OpenShell baseline and Codex policy with
the supplied overlay, then creates the gateway-managed `ai-guardian` service
used by tray/NiceGUI discovery. The policy is consumed at sandbox creation, so
pass the repository copy above; keeping a copy inside the image does not apply
it automatically. OpenShell uses its gateway service URL rather than a host
port-forward, and the host tray/NiceGUI must use the same active OpenShell
gateway. The sandbox receives an uploaded repository snapshot, not live XDG
mounts; to retain DAF state, download only the specific DAF directory from the
sandbox and review/merge it on the host. Do not upload or mount the host's
entire home.

Use the gateway lifecycle commands to inspect the target and service:

```bash
ai-guardian sandbox list --runtime openshell
ai-guardian sandbox status devaiflow-codex
openshell service get devaiflow-codex ai-guardian
```

For live XDG persistence and a directly published daemon port, use the
Podman/Docker `container/run.sh` workflow above instead; it uses the container
labels and REST-port mapping described in that section.

The image and `run.sh` never mount the host `$HOME`, `.config/ai-guardian`,
agent credential directories, or unrelated XDG roots. API keys and provider
credentials are not forwarded by `run.sh`; configure them through the
AI Guardian/OpenShell provider flow or an explicit, reviewed engine command.

## Smoke test

After building the image, run:

```bash
DEVAIFLOW_IMAGE=localhost/devaiflow-openshell:latest \
  CONTAINER_ENGINE=podman \
  container/smoke-test.sh
```

The smoke test creates temporary XDG roots, checks `daf` availability and
container-side path resolution, writes a marker through the data mount, and
verifies that a second disposable container can read it. On SELinux-enforcing
Podman hosts it automatically uses `:Z` for those temporary mounts. It removes
only its own temporary test directory on exit.
