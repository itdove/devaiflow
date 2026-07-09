# XDG Base Directory Specification

DevAIFlow follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/) for storing data, configuration, and state files.

## Directory Layout

| Category | XDG Variable | Default Path | Contents |
|----------|-------------|--------------|----------|
| Data | `XDG_DATA_HOME` | `~/.local/share/devaiflow` | Sessions, backups, logs, features |
| Config | `XDG_CONFIG_HOME` | `~/.config/devaiflow` | config.json, backends/, templates/, skills, context .md files |
| State | `XDG_STATE_HOME` | `~/.local/state/devaiflow` | audit.log, cache, dashboard state, suggestions |
| Cache | `XDG_CACHE_HOME` | `~/.cache/devaiflow` | Session clones (`clones/`), reproducible cached artifacts |

## Resolution Priority

DevAIFlow resolves its home directories in this order:

1. **`DEVAIFLOW_HOME` env var** — All files stored in one directory (highest priority)
2. **`~/.daf-sessions` exists** — All files stored in one directory (legacy compatibility)
3. **XDG env vars set** — Files split across XDG directories
4. **XDG defaults** — Files split across `~/.local/share`, `~/.config`, `~/.local/state`

When `DEVAIFLOW_HOME` is set or the legacy `~/.daf-sessions` directory exists, DevAIFlow operates in **unified mode** — all three directory functions return the same path. This ensures zero behavior change for existing users.

## New Installs

New installations (no `~/.daf-sessions`, no `DEVAIFLOW_HOME`) automatically use XDG-compliant paths. No configuration needed.

## Migrating from `~/.daf-sessions`

If you have an existing `~/.daf-sessions` directory and want to adopt XDG layout:

```bash
# Create XDG directories
mkdir -p ~/.local/share/devaiflow ~/.config/devaiflow ~/.local/state/devaiflow ~/.cache/devaiflow

# DATA — sessions, backups, logs, features, mocks
cp -a ~/.daf-sessions/sessions ~/.daf-sessions/sessions.json ~/.local/share/devaiflow/ 2>/dev/null
cp -a ~/.daf-sessions/backups ~/.daf-sessions/logs ~/.daf-sessions/mocks ~/.local/share/devaiflow/ 2>/dev/null
cp -a ~/.daf-sessions/features ~/.daf-sessions/features.json ~/.local/share/devaiflow/ 2>/dev/null

# CONFIG — json configs, backends, templates, skills, context docs
cp -a ~/.daf-sessions/config.json ~/.daf-sessions/enterprise.json ~/.config/devaiflow/ 2>/dev/null
cp -a ~/.daf-sessions/organization.json ~/.daf-sessions/team.json ~/.config/devaiflow/ 2>/dev/null
cp -a ~/.daf-sessions/backends ~/.daf-sessions/templates ~/.daf-sessions/templates.json ~/.config/devaiflow/ 2>/dev/null
cp -a ~/.daf-sessions/.claude ~/.config/devaiflow/ 2>/dev/null
cp -a ~/.daf-sessions/ENTERPRISE.md ~/.daf-sessions/ORGANIZATION.md ~/.config/devaiflow/ 2>/dev/null
cp -a ~/.daf-sessions/TEAM.md ~/.daf-sessions/USER.md ~/.config/devaiflow/ 2>/dev/null

# STATE — audit, cache, suggestions, dashboard
cp -a ~/.daf-sessions/audit.log ~/.local/state/devaiflow/ 2>/dev/null
cp -a ~/.daf-sessions/version_check_cache.json ~/.daf-sessions/suggestions.json ~/.local/state/devaiflow/ 2>/dev/null
cp -a ~/.daf-sessions/state ~/.local/state/devaiflow/ 2>/dev/null

# Remove legacy dir (triggers XDG mode)
rm -rf ~/.daf-sessions
```

Migration is optional. DevAIFlow continues to work with `~/.daf-sessions` indefinitely.

## Staying on Unified Mode

If you prefer keeping everything in one directory, set `DEVAIFLOW_HOME`:

```bash
export DEVAIFLOW_HOME="~/.daf-sessions"
```

This overrides XDG and keeps the legacy behavior permanently.

## Custom XDG Paths

Override individual XDG directories:

```bash
# Store data on a separate drive
export XDG_DATA_HOME="/mnt/data/.local/share"

# Store config in a dotfiles-managed location
export XDG_CONFIG_HOME="~/dotfiles/.config"

# Store state on fast local storage
export XDG_STATE_HOME="/tmp/state"

# Store cache (session clones) on a fast drive
export XDG_CACHE_HOME="/mnt/fast/.cache"
```

DevAIFlow appends `/devaiflow` to each XDG path automatically.

## API Reference

Four functions in `devflow.utils.paths`:

| Function | Returns | Used for |
|----------|---------|----------|
| `get_cs_home()` | Data directory | Sessions, backups, logs |
| `get_cs_config_home()` | Config directory | Configuration files, skills, templates |
| `get_cs_state_home()` | State directory | Audit logs, caches, runtime state |
| `get_cs_cache_home()` | Cache directory | Session clones, reproducible artifacts |

In unified mode (legacy or `DEVAIFLOW_HOME`), all four return the same path.

Additionally, `devflow.utils.temp_directory` provides:

| Function | Returns | Used for |
|----------|---------|----------|
| `get_clone_base_dir(config)` | Clone base directory | `get_cs_cache_home() / "clones"`, or `config.clone_dir` override |
