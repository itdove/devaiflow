# Feature Orchestration (EXPERIMENTAL)

> ⚠️ **EXPERIMENTAL FEATURE** - This functionality is under active development and subject to change in future releases.

## Overview

Feature orchestration allows you to execute multiple sessions sequentially on a shared branch with automated verification between sessions. This is particularly useful for complex features that span multiple tickets or work items.

## Enabling Experimental Features

To use feature orchestration, you must enable experimental features:

```bash
# Option 1: Use the -e flag (short form) - MUST come before 'feature'
daf -e feature list
daf -e feature create my-feature --parent "PROJ-100"

# Option 2: Use the --experimental flag (long form)
daf --experimental feature list

# Option 3: Set environment variable (persistent)
export DEVAIFLOW_EXPERIMENTAL=1
daf feature list

# ❌ INCORRECT - flag must come BEFORE the command
daf feature list -e           # This will NOT work
daf feature -e list           # This will NOT work
```

**Important:** The `-e` or `--experimental` flag is a global option and must appear **before** the `feature` command in the command line.

## Quick Start

### Auto-discover from Parent Ticket

```bash
# Discover child tickets from a parent epic/story
daf --experimental feature create my-feature \
  --parent "PROJ-100" \
  --auto-order \
  --verify auto
```

This will:
1. Parse the parent ticket's description and comments for issue references
2. Auto-discover all child tickets (#123, owner/repo#456, etc.)
3. Order them by: description mentions first, then comment mentions chronologically
4. Check if all children have sessions (prompts to sync if missing)
5. Create sessions for each child ticket (if needed)
6. Set up verification checkpoints between sessions

**Session Sync Check:**

When creating a feature with `--parent`, the command checks if all discovered children have sessions. If any are missing:
- Shows which children need sessions
- Offers 3 options:
  1. **Auto-create sessions** (recommended) - creates them immediately
  2. **Exit and sync manually** - run `daf sync` first to ensure all children are properly synced
  3. **Cancel** - abort feature creation

This ensures all children have proper session data before creating the feature.

### Manual Session List

```bash
# Specify sessions manually
daf --experimental feature create oauth-integration \
  --sessions "PROJ-101,PROJ-102,PROJ-103" \
  --branch "feature/oauth" \
  --verify auto
```

## Feature Commands

### `daf feature create`

Create a new feature orchestration.

**Options:**
- `--sessions`: Comma-separated list of session names (manual mode)
- `--parent`: Parent ticket key for auto-discovery (JIRA/GitHub/GitLab)
- `--branch`: Shared git branch (default: `feature/<name>`)
- `--base-branch`: Base branch to create from (auto-detected)
- `--verify`: Verification mode (`auto`, `manual`, `skip`)
- `--auto-order`: Order sessions by dependency relationships
- `--filter-status`: Filter children by status (default: "To Do,New")
- `--dry-run`: Preview without creating

**Examples:**

```bash
# Auto-discover with dry-run preview
daf --experimental feature create my-feature \
  --parent "owner/repo#123" \
  --auto-order \
  --dry-run

# Manual session list
daf --experimental feature create my-feature \
  --sessions "session1,session2,session3"
```

### `daf feature list`

List all feature orchestrations.

```bash
# List all features
daf --experimental feature list

# Filter by status
daf --experimental feature list --status running
```

### `daf feature status`

Show detailed status of a feature.

```bash
daf --experimental feature status my-feature
```

### `daf feature run`

Start executing a feature's sessions.

```bash
daf --experimental feature run my-feature
```

### `daf feature resume`

Resume a paused feature (after fixing verification issues).

```bash
daf --experimental feature resume my-feature
```

### `daf feature reorder`

Reorder sessions in a feature.

**Modes:**
- **Interactive mode**: Shows current order and prompts for changes
- **Move mode**: Move a specific session to a position
- **Direct mode** (`--order`): Specify complete new order
- **Sync mode** (`--sync-jira`): Fetch current JIRA blocking relationships and reorder automatically

**Examples:**

```bash
# Interactive mode
daf --experimental feature reorder my-feature

# Move mode - by session name
daf --experimental feature reorder my-feature PROJ-102 1

# Move mode - by session number
daf --experimental feature reorder my-feature 3 1

# Direct mode - full order
daf --experimental feature reorder my-feature \
  --order "session2,session1,session3"

# Sync mode - reorder based on current JIRA blocking relationships
daf --experimental feature reorder my-feature --sync-jira

# Dry-run preview
daf --experimental feature reorder my-feature \
  --order "session2,session1,session3" \
  --dry-run
```

**JIRA Sync Mode:**

The `--sync-jira` flag fetches the current blocking relationships ("Blocks" / "is blocked by" links) from JIRA and reorders sessions using topological sort. This is useful when:
- You've updated JIRA blocking relationships and want to reflect those changes in your feature
- You want to ensure your feature execution order matches the current JIRA dependencies
- You need to reorder sessions after JIRA relationships have changed

The sync will:
1. Fetch issuelinks for all sessions in the feature
2. Extract blocking relationships (only between sessions in the feature)
3. Apply topological sort to determine optimal execution order
4. Detect and warn about dependency cycles
5. Update the feature order (or preview with `--dry-run`)

### `daf feature delete`

Delete a feature orchestration.

```bash
daf --experimental feature delete my-feature
```

## Parent Ticket Discovery

Feature orchestration can auto-discover child tickets from parent tickets:

### JIRA
Uses native parent-child relationships (Epic → Story, Story → Task/Sub-task).

### GitHub/GitLab
Parses issue references from:
1. **Description/body** (first priority)
2. **Comments** (chronological order)

Supported formats:
- `#123` - Same repository
- `owner/repo#456` - Cross-repository
- `GH-123`, `GL-123` - Prefixed format

**Ordering:** Children are ordered by appearance (description mentions first, then comment mentions).

## Verification Between Sessions

After each session completes, automated verification runs:

1. **Acceptance Criteria Checking**
   - Parses criteria from ticket description
   - Searches for related code/tests

2. **Test Suite Execution**
   - Auto-detects test framework (pytest, npm, go, cargo, etc.)
   - Runs tests and reports results

3. **Artifact Validation**
   - Verifies required files exist
   - Checks files are substantial (not empty stubs)

4. **Verification Report**
   - Generates detailed `VERIFICATION.md` report
   - Stored in `$DEVAIFLOW_HOME/features/<name>/verification/`

### Verification Modes

- **`auto`**: Run all verification automatically (default)
- **`manual`**: Prompt user for approval
- **`skip`**: No verification (not recommended)

## Workflow Integration

### `daf open`

When opening a session that's part of a feature:

```bash
daf open session1
```

Displays:
```
🎯 Feature Orchestration:
   Feature: my-feature
   Progress: Session 1 of 3 (33%)
   Status: ⧗ Current session
   Next: session2
   Feature Status: ⧗ running
```

### `daf complete`

When completing a session in a feature:

```bash
daf complete session1
```

Automatically:
1. Skips individual PR creation (final PR created after all sessions)
2. Runs verification
3. Prompts to open next session (if verification passes)
4. Creates final PR when last session completes

## Storage Structure

```
$DEVAIFLOW_HOME/
├── features.json              # Index of all features
└── features/
    └── <feature-name>/
        ├── metadata.json      # Feature configuration
        ├── state.md           # Current state (human-readable)
        ├── progress.md        # Session completion log
        └── verification/
            ├── session1.md    # Verification report
            ├── session2.md
            └── session3.md
```

## Known Limitations

- Feature orchestration is single-user (no concurrent work on same feature)
- Verification is best-effort (may have false positives/negatives)
- GitHub/GitLab parent discovery relies on issue references in description/comments
- No automatic rollback on verification failure

## Feedback

This is an experimental feature under active development. Please report issues, bugs, and feature requests at:

**https://github.com/itdove/devaiflow/issues**

Include:
- `[feature-orchestration]` in the issue title
- Steps to reproduce
- Expected vs actual behavior
- Feature configuration (`metadata.json`)

## See Also

- [Session Management](../guides/session-management.md)
- [JIRA Integration](../workflows/jira-integration.md)
- [GitHub/GitLab Integration](../workflows/github-gitlab-integration.md)
