# Web Dashboard

The DevAIFlow web dashboard is a browser-based alternative to the Textual TUI, built with [NiceGUI](https://nicegui.io). It provides the same session management, configuration editing, and issue tracker integration in a modern web interface accessible from any browser.

## Installation

NiceGUI is installed with the main DevAIFlow package:

```bash
pip install devaiflow
```

For a development checkout, install the project normally:

```bash
pip install -e .
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

The dashboard writes its PID and port to `state/dashboard.pid` and `state/dashboard.port` under the XDG-aware DevAIFlow state directory so it can be discovered and stopped later.

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
- **Filter controls** -- filter sessions by status, workspace, and issue tracker
- **Session table** -- server-filtered, searchable table with columns: Status, Name, Workspace, Issue Key, Goal, Time, Last Active
- **Pagination** -- displays 25 sessions per page while preserving newest-first activity ordering
- **Auto-refresh** -- session data and status cards refresh every 10 seconds; each refresh reads the session index once

Click any session row to navigate to its detail page.

### Session Detail (`/session/{name}`)

Full session information:

- **Metadata** -- name, status, type, issue key, workspace, goal, created/last active times
- **Conversations** -- list of active and archived AI agent conversations with project paths, branches, session IDs, message counts, summaries, and PR links
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
| **Workspaces** | Add/edit/remove/set-default workspaces with name and path |
| **AI** | Agent backend, session summary mode, auto-launch, unit test instructions, add/edit/remove context files |
| **Model Providers** | Add/edit/remove/set-default profiles and explicitly validate provider configuration |
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
- **Edit dialogs** -- workspace, context-file, and model-provider changes are marked dirty and saved with the rest of the configuration
- **Provider validation** -- runs the same static and optional remote checks as the Textual TUI without changing profile values or displaying credentials

### Issue Tracker (`/issues`)

- Displays sessions linked to JIRA/GitHub/GitLab tickets
- Shows issue tracker configuration (JIRA URL/project, GitHub repo)
- Sortable, searchable table filtered to sessions with issue keys
- Click any row to load ticket details and comments
- Add comments through the configured issue tracker client
- Open the ticket in the external issue tracker

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
- **Fresh reads** -- each dashboard refresh creates one fresh `SessionManager` snapshot; filter, search, and page changes reuse it
- **Bounded rendering** -- only the visible page is converted to web rows, avoiding serialization of the entire session index
- **Lazy page imports** -- page modules are imported inside route handlers for fast startup
- **Presentation layer only** -- the web module is purely UI; data operations use existing layers

## Security

- **Localhost only** -- binds to `127.0.0.1` by default
- **Dynamic port** -- uses OS-assigned port to avoid conflicts and reduce predictability
- **Port file** -- writes the assigned port to the XDG-aware DevAIFlow state directory for discovery
- **Security warning** -- the application API logs a warning for non-localhost bindings; the CLI intentionally exposes no host override
- **No authentication** -- designed for local use; remote access is not recommended

## Troubleshooting

### NiceGUI not installed

```
daf dashboard
✗ NiceGUI is required for the web dashboard but is not installed.

Install the package with its main dependencies:
  pip install devaiflow
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
