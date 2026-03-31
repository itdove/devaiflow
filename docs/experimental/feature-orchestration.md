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

Auto-discover child tickets using `--parent-url` with full issue URLs (works from any directory):

```bash
# GitHub URL
daf --experimental feature create my-feature \
  --parent-url "https://github.com/itdove/devaiflow/issues/305" \
  --auto-order

# GitLab URL
daf --experimental feature create my-feature \
  --parent-url "https://gitlab.com/group/project/-/issues/42" \
  --auto-order

# JIRA URL
daf --experimental feature create my-feature \
  --parent-url "https://redhat.atlassian.net/browse/AAP-70183" \
  --auto-order
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
- `--parent-url`: Parent issue URL for auto-discovery (GitHub/GitLab/JIRA)
- `--branch`: Shared git branch (default: `feature/<name>`)
- `--base-branch`: Base branch to create from (auto-detected from API)
- `--verify`: Verification mode (`auto`, `manual`, `skip`)
- `--auto-order`: Order sessions by dependency relationships
- `--filter-status`: Filter children by status (default: "To Do,New")
- `--dry-run`: Preview without creating

**Parent Discovery:**

Use `--parent-url` with full issue URLs:

| Backend | URL Format | Works From Any Dir? |
|---------|-----------|---------------------|
| GitHub | `https://github.com/owner/repo/issues/123` | ✅ Yes |
| GitLab | `https://gitlab.com/group/project/-/issues/42` | ✅ Yes |
| JIRA | `https://domain.atlassian.net/browse/AAP-123` | ✅ Yes |

**Why URLs?**
- No ambiguity (GitHub vs GitLab use same `owner/repo#123` format)
- Works from any directory (no git repository required)
- Fetches repository metadata (default branch) from API
- Consistent across all backends

**Examples:**

```bash
# Auto-discover from GitHub URL
daf --experimental feature create my-feature \
  --parent-url "https://github.com/owner/repo/issues/123" \
  --auto-order

# Auto-discover from JIRA URL with dry-run preview
daf --experimental feature create my-feature \
  --parent-url "https://redhat.atlassian.net/browse/AAP-70183" \
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

### `daf feature sync`

Sync a feature with its parent ticket to add new children.

**REQUIRES a parent ticket** - Re-discovers children from the parent and adds any that now meet sync criteria.

**Parent URL is optional** - By default, uses the parent URL from feature metadata (set during `daf feature create`).

**What does sync do?**

Sync re-queries the parent ticket to discover all its children, then:
1. Identifies children that NOW meet sync criteria (were previously excluded)
2. Creates sessions for those newly-eligible children
3. Adds them to the feature
4. Updates external session statuses (for team collaboration)

This is NOT for adding arbitrary sessions - it specifically re-discovers from the parent ticket.

**Use Cases:**
- You created a feature with `--parent-url`, but some children were excluded (missing assignee, required fields, etc.)
- You later updated those tickets in the issue tracker (assigned yourself, added required fields, changed status)
- You want to add them to the existing feature without recreating it

**When you need `--parent-url`:**
- Feature was created with `--sessions` (manual, no parent) and you want to add a parent now
- You want to sync from a different parent (rare edge case)

**Note:** When `--parent-url` is provided, it's saved to feature metadata for future syncs.

**Examples:**

```bash
# Most common: sync using stored parent (feature created with --parent-url)
daf --experimental feature sync my-feature

# Preview what would be added (dry-run)
daf --experimental feature sync my-feature --dry-run

# Sync and reorder by dependencies
daf --experimental feature sync my-feature --auto-order

# Add parent to feature created with --sessions (saves for future syncs)
daf --experimental feature sync my-feature \
  --parent-url "https://github.com/owner/repo/issues/100"
```

**Important:** Features created with `--sessions` (manual session list, no parent) cannot sync without providing `--parent-url` to add a parent first.

**What it does:**
1. Re-discovers all children from the parent ticket
2. Applies sync criteria filtering
3. Identifies children not already in the feature
4. Shows which new children will be added
5. Creates sessions for new children (if needed)
6. Adds them to the feature
7. Optionally reorders by dependencies (`--auto-order`)

### `daf feature run`

Start executing a feature's sessions. **Automatically opens the first session** to enforce execution order.

```bash
daf --experimental feature run my-feature
```

**What happens:**
1. Shows execution order (which sessions are pending/completed)
2. Automatically opens the first pending session
3. Enforces session order (can't skip sessions)

**Workflow:**
```bash
# Start feature
daf -e feature run my-feature

# → First session opens automatically (no manual daf open needed)
# → Work with Claude on session 1
# → Complete: daf complete <session-1>
# → Prompted: "Open next session <session-2>?"
#   - Yes → Opens session 2
#   - No → Resume later with: daf -e feature resume my-feature
```

**Auto-Advance Mode:**

Use `--auto-advance` to skip prompts between sessions for a continuous workflow:

```bash
daf --experimental feature run my-feature --auto-advance
```

**Behavior with --auto-advance:**
- Opens first session automatically (same as without flag)
- After each `daf complete`, **automatically** opens next session (no prompts)
- Continuous workflow until all sessions complete
- Still stops at verification failures

**Comparison:**

| Mode | First Session | Between Sessions | Use Case |
|------|---------------|------------------|----------|
| Default | Auto-opens | Prompts each time | Want control, can pause anytime |
| `--auto-advance` | Auto-opens | Auto-opens (no prompt) | Trust workflow, reduce overhead |

### `daf feature resume`

Smart resume that continues where you left off. Handles different scenarios automatically.

```bash
daf --experimental feature resume my-feature
```

**What it does:**

1. **If session is paused/failed** (verification failed):
   - Re-runs verification
   - If passes → Opens next session
   - If still fails → Opens same session to fix issues

2. **If session is completed** (forgot to advance):
   - Advances to next session
   - Opens the next session

3. **If session is running/pending** (just continuing work):
   - Opens the current session

4. **If all sessions complete**:
   - Shows "Feature complete!" message
   - Suggests: `daf -e feature complete my-feature`

**Use cases:**
```bash
# Closed Claude mid-session - continue where you left off
daf -e feature resume my-feature

# Fixed verification issues - retry
daf -e feature resume my-feature

# Completed a session but didn't open next - advance
daf -e feature resume my-feature
```

### `daf feature reorder`

Reorder sessions in a feature.

**Modes:**
- **Interactive mode**: Shows current order and prompts for changes
- **Move mode**: Move a specific session to a position
- **Direct mode** (`--order`): Specify complete new order

**Note:** To reorder based on JIRA blocking relationships, use `daf feature sync --parent <parent> --auto-order` instead.

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

# Dry-run preview
daf --experimental feature reorder my-feature \
  --order "session2,session1,session3" \
  --dry-run
```

### `daf feature delete`

Delete a feature orchestration.

By default, only removes the feature metadata. Sessions and branches are preserved.

**Options:**
- `--delete-sessions` - Also delete all sessions in the feature
- `--delete-branch` - Also delete the git branch

**Examples:**

```bash
# Delete feature only (sessions and branch preserved)
daf --experimental feature delete my-feature

# Delete feature and all sessions
daf --experimental feature delete my-feature --delete-sessions

# Delete everything (useful for testing)
daf --experimental feature delete my-feature --delete-sessions --delete-branch
```

**What gets deleted:**

| Command | Feature Metadata | Sessions | Git Branch |
|---------|-----------------|----------|------------|
| `delete` | ✓ | ✗ | ✗ |
| `delete --delete-sessions` | ✓ | ✓ | ✗ |
| `delete --delete-branch` | ✓ | ✗ | ✓ |
| `delete --delete-sessions --delete-branch` | ✓ | ✓ | ✓ |

## Parent Ticket Discovery

Feature orchestration auto-discovers child tickets from parent tickets using `--parent-url` with full URLs.

### Specifying Parent Issues

Use `--parent-url` with full issue URLs (works from any directory):

```bash
# GitHub
--parent-url "https://github.com/owner/repo/issues/123"

# GitLab
--parent-url "https://gitlab.com/group/project/-/issues/42"

# GitLab Enterprise
--parent-url "https://gitlab.cee.redhat.com/group/project/-/issues/123"

# JIRA
--parent-url "https://redhat.atlassian.net/browse/AAP-70183"
```

**Why Full URLs?**

Previously, feature creation supported issue keys like `owner/repo#123`, but this format is ambiguous:
- GitHub uses: `owner/repo#123`
- GitLab uses: `group/project#123` (identical format!)

Without the hostname, there's no way to distinguish GitHub from GitLab. Full URLs eliminate this ambiguity and work from any directory (no git repository required).

### Backend-Specific Discovery

**JIRA:**
- Uses native parent-child relationships (Epic → Story, Story → Task/Sub-task)
- Fetches all children via JIRA API

**GitHub/GitLab:**
- Parses issue references from parent issue description and comments
- Supported reference formats in parent description:
  - `#123` - Same repository
  - `owner/repo#456` - Cross-repository
  - `GH-123`, `GL-123` - Prefixed format
- Ordering: Description mentions first, then comment mentions chronologically

**Repository Metadata:**
- When using URLs, fetches repository metadata (default branch) from API
- No git repository required on your local machine

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

## Complete Workflow Example

### Step-by-Step Execution

```bash
# 1. Create feature (auto-discovers children, creates sessions)
daf -e feature create web-ui --parent "owner/repo#305" --auto-order

# 2. Start feature (automatically opens first session)
daf -e feature run web-ui
# → First session opens automatically
# → No need for manual 'daf open'

# 3. Work with Claude on session 1
# ... make changes, commit code ...

# 4. Complete session 1
daf complete itdove/devaiflow#306
# → Runs verification
# → Prompts: "Open next session 'itdove/devaiflow#307'?"
# → Choose Yes or No

# 5. Work with Claude on session 2
# ... make changes, commit code ...

# 6. Complete session 2
daf complete itdove/devaiflow#307
# → Prompts for next session

# 7. Continue until all sessions complete...

# 8. Last session triggers final PR
daf complete itdove/devaiflow#313
# → All sessions verified
# → Prompts: "Create final PR/MR for feature?"
# → Creates single PR with all changes
```

### Resuming After Break

If you close Claude or need to pause:

```bash
# Resume where you left off (smart resume)
daf -e feature resume web-ui

# → If session paused: Re-runs verification
# → If session running: Opens current session
# → If session completed: Opens next session
# → If all complete: Shows "Feature complete!"
```

## Workflow Integration

### `daf open`

When you manually open a session that's part of a feature, you'll get a warning:

```bash
daf open itdove/devaiflow#306
```

**Warning shown:**
```
⚠️  Warning: Feature Orchestration Detected
Feature: web-ui
Session: itdove/devaiflow#306 (Session 1 of 8)
Status: Current session in workflow

Recommendation: Use daf -e feature resume web-ui instead
This ensures proper workflow continuation and verification.

Reasons to continue anyway:
  • Making fixes to already-completed work
  • Investigating code in this session
  • You know what you're doing

Continue opening this session manually? [y/N]:
```

**Why the warning?**
- Opening sessions manually can break the execution order
- Skips verification checkpoints
- May cause workflow confusion

**When to continue anyway:**
- Making fixes to completed sessions
- Investigating code without running full workflow
- Debugging specific issues

**Note:** When sessions are opened via `daf feature run` or `daf feature resume`, this warning is automatically skipped.

**What happens when you open:**
- Uses the shared feature branch (not per-session branch)
- Creates the branch from correct base if needed
- Shows feature context in the output

Example output:
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

Automatically:
1. Skips individual PR creation (final PR created after all sessions)
2. Runs verification
3. Prompts to open next session (if verification passes)
   - With `--auto-advance`: Opens automatically (no prompt)
   - Without: Asks "Open next session?"
4. Creates final PR when last session completes

## Team Collaboration

Feature orchestration supports multi-user workflows where team members work on different stories within the same feature.

### How It Works

When creating a feature from a parent epic:
1. **Imports ALL child stories** (not just yours)
2. **Creates sessions only for your stories** (assigned to you)
3. **Tracks external stories** in `feature.external_sessions` for dependency management
4. **Runtime filtering** skips stories blocked by teammates' incomplete work

### Example: Team Epic

Epic PROJ-100 has 5 stories:
- PROJ-101 (assigned to you) - depends on nothing
- PROJ-102 (assigned to you) - **blocked by** PROJ-103
- PROJ-103 (assigned to Bob) - depends on nothing
- PROJ-104 (assigned to Alice) - depends on nothing
- PROJ-105 (assigned to you) - **blocked by** PROJ-104

```bash
# Create feature (imports all, creates sessions for yours only)
daf -e feature create web-ui --parent "PROJ-100" --auto-order

# Shows:
# Your sessions: 3 (PROJ-101, PROJ-102, PROJ-105)
# External sessions (tracked for dependencies): 2 (PROJ-103, PROJ-104)

# Run feature
daf -e feature run web-ui

# Opens PROJ-101 (not blocked)
# Skips PROJ-102 (blocked by Bob's PROJ-103)
# Skips PROJ-105 (blocked by Alice's PROJ-104)
```

### Handing Off Incomplete Work (Export)

When you need to reassign a story to a teammate:

```bash
# You have feature with PROJ-102 in your sessions (incomplete)
# Realize Bob should work on it instead

# Export the session
daf export PROJ-102

# Auto-detects feature handoff:
# Session PROJ-102 is part of feature 'web-ui'
# Session status: paused, Feature status: pending
# Issue tracker status: To Do
#
# ⚠ Feature Handoff Detected
# Feature: web-ui
# Session: PROJ-102
# Status: paused (incomplete)
#
# You're exporting incomplete work. Options:
#   1. Mark as external (handing off to teammate)
#      → Removes from your sessions
#      → Tracks as external dependency
#      → Dependent sessions may be blocked
#   2. Keep in your sessions (you'll continue working on it)
#      → Share for review/collaboration only
#
# Hand off PROJ-102 to teammate (mark as external)? [y/N]: y
# Teammate's name/username: Bob
# Using issue tracker status: To Do

# After accepting:
# ✓ Moved PROJ-102 to external sessions
# ✓ Assigned to: Bob
# ✓ Updated feature 'web-ui'

# Share tarball with Bob
# Send: session-export-PROJ-102.tar.gz
```

**What happens:**
- Checks actual session status and issue tracker status
- Only offers handoff for incomplete sessions
- Session moves from `feature.sessions` → `feature.external_sessions`
- Blocking relationships preserved
- Uses real status from issue tracker (not hardcoded "In Progress")
- You can track progress via `daf feature sync`

**For completed sessions:**
```bash
# Export completed session
daf export PROJ-101

# No handoff prompt:
# Session PROJ-101 is part of feature 'web-ui'
# Session status: completed, Feature status: completed
# Issue tracker status: Done
# Exporting completed work (no handoff needed)
```

### Importing Teammate's Completed Work (Import)

When a teammate completes their story and shares it with you:

**Teammate's workflow:**
```bash
# Bob completes PROJ-103
daf complete PROJ-103

# Export for sharing
daf export PROJ-103
# Creates: session-export-PROJ-103.tar.gz

# Share tarball with you (Slack, email, etc.)
```

**Your workflow:**
```bash
# Import Bob's completed session
daf import session-export-PROJ-103.tar.gz

# Auto-detects feature integration:
# ⚠ Feature Integration Detected
# Feature: web-ui
# Session: PROJ-103
# Status: This session is tracked as an external dependency
#
# Add PROJ-103 to feature 'web-ui'? [Y/n]: y
#
# Session status: completed → Feature status: completed
# Issue tracker status: done
# Using issue tracker status: completed

# After accepting:
# ✓ Added PROJ-103 to feature 'web-ui'
# ✓ Status: completed
# ✓ Removed from external dependencies
# 🎉 Unblocked 1 session(s):
#   • PROJ-102

# Resume feature (now PROJ-102 is unblocked!)
daf -e feature resume web-ui
```

**For incomplete imports:**
```bash
# Import Bob's incomplete session (he needs your help)
daf import session-export-PROJ-103.tar.gz

# ⚠ Feature Integration Detected
# Add PROJ-103 to feature 'web-ui'? [Y/n]: y
#
# Session status: paused → Feature status: paused
# Issue tracker status: In Progress

# After accepting:
# ✓ Added PROJ-103 to feature 'web-ui'
# ✓ Status: paused
# ✓ Removed from external dependencies
#
# Note: Session is paused, not completed yet
# Dependent sessions remain blocked until completion
```

**What happens:**
- Checks actual session status and issue tracker status
- Session moves from `feature.external_sessions` → `feature.sessions`
- Uses real status (completed, paused, pending, etc.) instead of assuming
- Blocking relationships preserved
- Dependent sessions only unblocked if status is "completed"

### Syncing External Session Status

Update external session statuses without importing:

```bash
# Re-fetch parent epic to update external session statuses
daf -e feature sync web-ui

# Uses parent from feature metadata (no --parent needed)
# Updates external_sessions with latest status from issue tracker
# Shows which sessions are now unblocked
```

### Complete Workflow: Work Handoff & Integration

**Full team collaboration scenario:**

```bash
# You: Create feature from epic (5 stories: 3 yours, 2 external)
daf -e feature create web-ui --parent "PROJ-100" --auto-order
# Your sessions: PROJ-101, PROJ-102, PROJ-105
# External: PROJ-103 (Bob), PROJ-104 (Alice)

# You: Complete PROJ-101
daf complete PROJ-101

# You: Start PROJ-102, realize Bob should do it instead
daf export PROJ-102
# ⚠ Feature Handoff Detected
# Hand off PROJ-102 to teammate? [y/N]: y
# Teammate's name: Bob
# ✓ Moved PROJ-102 to external sessions
# Now: Your sessions: PROJ-101, PROJ-105
#      External: PROJ-102 (Bob), PROJ-103 (Bob), PROJ-104 (Alice)

# Send session-export-PROJ-102.tar.gz to Bob

# Bob: Import and work on PROJ-102
daf import session-export-PROJ-102.tar.gz
daf open PROJ-102
# ... makes changes ...
daf complete PROJ-102

# Bob: Export completed work
daf export PROJ-102
# Send back to you: session-export-PROJ-102.tar.gz

# You: Import Bob's completed work
daf import session-export-PROJ-102.tar.gz
# ⚠ Feature Integration Detected
# Add PROJ-102 to feature 'web-ui'? [Y/n]: y
# ✓ Added PROJ-102 to feature
# ✓ Marked as completed
# 🎉 Unblocked 0 session(s)
# (PROJ-105 still blocked by PROJ-104)

# You: Check status
daf -e feature status web-ui
# Sessions: 3
#   ✓ PROJ-101 (completed)
#   ✓ PROJ-102 (completed)
#   ○ PROJ-105 (pending, blocked by PROJ-104)
# External: 2
#   PROJ-103 (Bob, In Progress)
#   PROJ-104 (Alice, In Progress)

# You: Update external status from issue tracker
daf -e feature sync web-ui
# Alice marked PROJ-104 as Done in JIRA
# ✓ Updated 2 external sessions
# 🎉 Unblocked 1 session(s):
#   • PROJ-105

# You: Resume and complete last session
daf -e feature resume web-ui
# Opens PROJ-105 (now unblocked!)
```

### Dependency Checking

Feature orchestration checks blocking relationships across team members:

```bash
# If all your pending sessions are blocked by teammates:
daf -e feature run web-ui

# Shows:
# ⚠ All remaining sessions are blocked by external dependencies
#
# Blocked sessions:
#   • PROJ-102
#     Blocked by: PROJ-103
#   • PROJ-105
#     Blocked by: PROJ-104
#
# Tip: Run 'daf -e feature sync web-ui' to update external session statuses
```

## Storage Structure

```
$DEVAIFLOW_HOME/
├── features.json              # Index of all features
└── features/
    └── <feature-name>/
        ├── metadata.json      # Feature configuration
        │                      # - blocking_relationships (yours)
        │                      # - external_sessions (teammates)
        ├── state.md           # Current state (human-readable)
        ├── progress.md        # Session completion log
        └── verification/
            ├── session1.md    # Verification report
            ├── session2.md
            └── session3.md
```

## Known Limitations

- Verification is best-effort (may have false positives/negatives)
- GitHub/GitLab parent discovery relies on issue references in description/comments
- No automatic rollback on verification failure
- External session status updates require manual `daf feature sync` (not automatic)

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
