# Web Dashboard

The DevAIFlow web dashboard is a browser-based alternative to the Textual TUI, built with [NiceGUI](https://nicegui.io). It provides the same session management, configuration editing, and issue tracker integration in a modern web interface accessible from any browser.

## Installation

The web dashboard requires the `web` optional dependency:

```bash
pip install devaiflow[web]
```

Or install NiceGUI directly:

```bash
pip install nicegui
```

## Launching the Dashboard

```bash
daf dashboard                  # Auto port, auto-open browser
daf dashboard --port 9090      # Specific port
daf dashboard --no-open        # Don't open browser
daf dashboard --reload         # Dev mode with auto-reload
daf dashboard -b               # Run in the background
daf dashboard --background     # Same as -b
```

The dashboard binds to `127.0.0.1` (localhost only) by default for security. A dynamic port is assigned automatically to avoid conflicts.

### Background Mode

Run the dashboard as a background process so it stays running after you close the terminal:

```bash
daf dashboard -b
# Dashboard started in background (pid=12345, port=54321)
#   Open: http://127.0.0.1:54321
#   Stop: daf dashboard stop
```

The dashboard writes its PID and port to state files (`~/.daf-sessions/state/dashboard.pid` and `dashboard.port`) so it can be discovered and stopped later.

If you run `daf dashboard` while a background instance is already running, it tells you the existing URL instead of starting a duplicate.

### Stopping the Dashboard

```bash
daf dashboard stop
# Stopping dashboard (pid=12345, port=54321)...
# Dashboard stopped.
```

This sends SIGTERM to the background process and cleans up the state files.

## Pages

### Dashboard (`/`)

The main page shows:

- **Status summary cards** -- total, in-progress, paused, complete, and created session counts
- **Filter controls** -- filter sessions by status
- **Session table** -- sortable, searchable table with columns: Status, Name, Workspace, Issue Key, Goal, Time, Last Active
- **Auto-refresh** -- session data refreshes every 10 seconds

Click any session row to navigate to its detail page.

### Session Detail (`/session/{name}`)

Full session information:

- **Metadata** -- name, status, type, issue key, workspace, goal, created/last active times
- **Conversations** -- list of AI agent conversations with project paths, branches, session IDs, message counts, and PR links
- **Work Sessions** -- time tracking history with start/end times, duration, and user
- **Notes** -- view existing notes and add new ones directly from the web UI

### Configuration Editor (`/config`)

Supports two modes, matching the Textual TUI:

**Simple Mode** (`/config`) -- 8 topic-based tabs:

| Tab | Fields |
|-----|--------|
| **JIRA Integration** | URL, project key, components (dropdown from field_mappings), comment visibility, dynamic custom field defaults with dropdowns for fields with allowed values, auto-add summary, auto-update PR URL |
| **GitHub/GitLab** | API URL, repository, labels, auto-close, status labels, completion label, GitLab settings |
| **Repository & VCS** | Detection method/fallback, branch checkout, base sync, branch strategy, commit, PR/MR creation and push |
| **Workspaces** | Add/remove/set-default workspaces with name and path |
| **AI** | Agent backend, session summary mode, auto-launch, unit test instructions, context files management |
| **Model Providers** | View and set default model provider profiles |
| **Session Workflow** | Auto-complete on exit, time tracking |
| **Advanced** | Update checker timeout, issue tracker backend, hierarchical config source |

**Advanced Mode** (`/config/advanced`) -- 4 file-based tabs:

| Tab | Content |
|-----|---------|
| **Enterprise** | Read-only view of enterprise.json (agent backend, backend overrides, model provider enforcement) |
| **Organization** | JIRA project key, GitHub issue types, sync filters (read-only), workflow configuration (read-only) |
| **Team** | Read-only view of team defaults (agent backend, custom/system field defaults) |
| **User** | Personal settings: last used workspace, hierarchical config source, personal field defaults |

Click "Switch to Advanced/Simple Mode" in the top-right corner to toggle between modes.

**Actions:**
- **Preview JSON** -- shows full config as JSON with option to confirm and save
- **Save** -- saves config with automatic backup

### Issue Tracker (`/issues`)

- Displays sessions linked to JIRA/GitHub/GitLab tickets
- Shows issue tracker configuration (JIRA URL/project, GitHub repo)
- Sortable, searchable table filtered to sessions with issue keys
- Click any row to view session details

### Time Tracking (`/time`)

- **Summary cards** -- total time, active sessions, sessions with recorded time
- **Bar chart** -- top 15 sessions by time spent (using Highcharts)
- **Detailed table** -- all sessions with total time, sortable by duration

### Workspaces (`/workspaces`)

- Lists all configured workspaces with default indicator
- Shows repository count (discovered via `.git` directories)
- Shows session count per workspace
- Expandable lists for repositories and linked sessions

## Architecture

The web dashboard follows a layered architecture:

```
devflow/web/
├── app.py                    # NiceGUI app entry point, route registration
├── pages/
│   ├── dashboard.py          # Main session overview
│   ├── session_detail.py     # Individual session view
│   ├── config_editor.py      # Configuration editor (8 tabs)
│   ├── issue_tracker.py      # Issue tracker views
│   ├── time_tracking.py      # Time tracking visualization
│   └── workspaces.py         # Workspace management
├── components/
│   ├── nav.py                # Navigation header
│   ├── session_table.py      # Reusable session table
│   └── status_badge.py       # Status/type badges
└── utils/
    └── data_bridge.py        # Bridge to SessionManager/ConfigLoader
```

**Key design principles:**

- **No business logic duplication** -- all data access goes through `DataBridge`, which wraps `SessionManager`, `ConfigLoader`, and `StorageBackend`
- **Fresh reads** -- each page load creates a fresh `SessionManager` to read latest data from disk
- **Lazy page imports** -- page modules are imported inside route handlers for fast startup
- **Presentation layer only** -- the web module is purely UI; data operations use existing layers

## Security

- **Localhost only** -- binds to `127.0.0.1` by default
- **Dynamic port** -- uses OS-assigned port to avoid conflicts and reduce predictability
- **Port file** -- writes assigned port to `~/.daf-sessions/state/dashboard.port` for discovery
- **Security warning** -- logs a warning if `--host` is set to a non-localhost address
- **No authentication** -- designed for local use; remote access is not recommended

## Troubleshooting

### NiceGUI not installed

```
daf dashboard
✗ NiceGUI is required for the web dashboard but is not installed.

Install it with:
  pip install devaiflow[web]
```

### Port already in use

Use a different port:

```bash
daf dashboard --port 9091
```

### Browser doesn't open

Use `--no-open` and navigate manually:

```bash
daf dashboard --no-open
# Note the port from the console output and open http://127.0.0.1:<port>
```
