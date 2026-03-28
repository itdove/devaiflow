# Commands Reference

Complete reference for all CLI commands with examples.

## Table of Contents

- [Core Session Commands](#core-session-commands)
- [Workspace Management](#workspace-management)
- [Agent Management](#agent-management)
- [JIRA Integration Commands](#jira-integration-commands)
- [Notes and Progress](#notes-and-progress)
- [Time Tracking](#time-tracking)
- [Backup and Export](#backup-and-export)
- [Maintenance Commands](#maintenance-commands)
- [Utility Commands](#utility-commands)
- [Experimental Features](#experimental-features)
- [Using Slash Commands in Multi-Repository Sessions](#using-slash-commands-in-multi-repository-sessions)

## Core Session Commands

### daf sync - Smart Sync (Recommended Start)

**Smart sync automatically determines what to sync** based on your parameters and configuration.

```bash
daf sync [OPTIONS]
```

**Smart Sync Behavior:**

The sync command intelligently decides what to sync based on your parameters:

| Command | With JIRA URL | Without JIRA URL | What Gets Synced |
|---------|---------------|------------------|------------------|
| `daf sync` | ✅ | ❌ | JIRA tickets only |
| `daf sync` | ❌ | ✅ | All workspaces |
| `daf sync -w workspace` | ✅ or ❌ | ✅ or ❌ | Workspace only |
| `daf sync --repository repo` | ✅ or ❌ | ✅ or ❌ | Repository only |
| `daf sync --field/--type/--epic` | ✅ | ❌ | JIRA only (errors if no JIRA) |
| `daf sync --jira` | ✅ | ❌ | JIRA only (errors if no JIRA) |
| `daf sync --jira -w workspace` | ✅ | ❌ | Both JIRA and workspace |

**Examples:**

```bash
# Smart sync (with JIRA configured) → Syncs JIRA tickets only
daf sync

# Smart sync (no JIRA configured) → Syncs all workspaces
daf sync

# Sync JIRA with filters → JIRA only
daf sync --type Story
daf sync --field sprint="Sprint 1"
daf sync --epic PROJ-36419

# Sync specific workspace → Workspace only
daf sync --workspace primary

# Sync specific repository → Repository only
daf sync --repository owner/repo

# Force JIRA sync → JIRA only
daf sync --jira

# Sync both JIRA and workspace → Both
daf sync --jira --workspace primary
daf sync --jira --repository owner/repo
```

**Options:**
- `--field` - Filter JIRA tickets by custom field (format: field_name=value)
- `--type` - Filter JIRA tickets by type (Story, Bug, Task, etc.)
- `--epic` - Filter JIRA tickets by epic
- `-w, --workspace` - Sync specific workspace only
- `--repository, --repo` - Sync specific repository only
- `--jira` - Force JIRA sync (can combine with workspace/repository)

**What it does:**
1. **Determines sync mode** based on parameters (see table above)
2. **Syncs JIRA tickets** (if sync mode includes JIRA)
3. **Scans workspaces** for git repositories (if sync mode includes workspaces)
4. **Syncs GitHub/GitLab issues** from discovered repositories
5. **Creates sessions** for new issues/tickets
6. **Updates existing sessions** with latest data
7. **Shows summary** of synced sessions

**Output example:**
```
Would create sessions for:

  PROJ-12345: Implement customer backup
    Type: Story | Points: 5 | Status: To Do
    Sprint: 2025-01

  PROJ-12346: Fix password reset bug
    Type: Bug | Status: In Progress
    Sprint: 2025-01

Total: 2 tickets (5 story points)
```

---

### daf new - Create Session

Create a new session manually (use `daf sync` instead for JIRA tickets).

```bash
daf new --name <NAME> --goal "..." [OPTIONS]
```

**Options:**
- `--name` - Session name
- `--goal` - What you're trying to accomplish (supports auto-detection of file:// paths and http(s):// URLs)
- `--goal-file` - Explicit file path or URL for goal input (mutually exclusive with `--goal`)
- `--jira` - JIRA ticket key (optional)
- `--path` - Project path (auto-detected if not specified; mutually exclusive with `--projects`)
- `--projects` - Comma-separated list of projects for multi-project session (e.g., "backend,frontend,docs")
- `--branch` - Git branch name (optional)
- `--template` - Template name to use (optional)
- `-w, --workspace` - Workspace name to use (overrides session default and config default)
- `--model-profile` - Model provider profile to use (e.g., "vertex", "llama-cpp"; stored in session for future use)

**Goal Input Formats:**

**Using --goal (with auto-detection):**
- **Plain text**: Any multi-word text is treated as plain text
- **File path (with prefix)**: `file:///path/to/file.md` - reads file content
- **Bare file path**: `/path/to/file.md` or `requirements.md` - must be a single token (no spaces)
- **URL**: `https://example.com/spec.txt` - fetches content from URL

**Using --goal-file (explicit file/URL input):**
- **File path**: `requirements.md`, `~/docs/spec.txt`, `/absolute/path/to/file.md` - reads file content
- **URL**: `https://example.com/spec.txt` - fetches content from URL
- **Validation**: Ensures input is actually a file path or URL (not plain text)
- **Mutual exclusion**: Cannot use both `--goal` and `--goal-file` together

**Examples:**
```bash
# Personal work (no JIRA)
daf new --name "redis-test" --goal "Test Redis caching approach"

# With JIRA (manual creation)
daf new --jira PROJ-12345 --goal "Implement backup feature"

# With specific path
daf new --name "api-test" --goal "Test endpoint" --path ~/projects/backend

# From template
daf new --name "new-feature" --goal "Build API" --template my-backend-template

# Goal from local file (with file:// prefix)
daf new --name "complex-feature" --goal "file:///path/to/requirements.md"

# Goal from local file using --goal (bare path - must be single token, no spaces)
daf new --name "complex-feature" --goal "/path/to/requirements.md"
daf new --name "complex-feature" --goal "~/Documents/requirements.md"
daf new --name "complex-feature" --goal "requirements.md"

# Goal from local file using --goal-file (explicit, allows any path)
daf new --name "complex-feature" --goal-file "requirements.md"
daf new --name "complex-feature" --goal-file "~/Documents/spec.txt"
daf new --name "complex-feature" --goal-file "/absolute/path/to/requirements.md"

# Goal from URL
daf new --name "spec-impl" --goal "https://docs.example.com/specification.txt"

# Goal from URL using --goal-file (explicit)
daf new --name "spec-impl" --goal-file "https://docs.example.com/specification.txt"

# Multi-word text with special characters is always treated as plain text
daf new --name "bug-fix" --goal "Fix error in help.py when using --output flag"

# Use alternative model provider (e.g., local llama.cpp for testing)
daf new --name "experiment" --goal "Test new feature" --model-profile llama-cpp

# Use Vertex AI profile for production work
daf new --name PROJ-789 --goal "Deploy feature" --model-profile vertex

# Create multi-project session from the start
daf new --name "user-profile" --jira PROJ-12345 -w primary --projects backend,frontend,shared
```

**When to use:**
- Personal experiments or prototypes
- Work not tied to JIRA
- When you need custom session setup before syncing with JIRA

**Branch Conflict Resolution (PROJ-60715):**

When creating a branch, if the suggested branch name already exists, you'll be prompted with options:

```bash
✓ Detected git repository

Suggested branch name: aap-12345-fix-bug

⚠ Branch 'aap-12345-fix-bug' already exists

Options:
1. Add suffix to branch name (e.g., aap-12345-fix-bug-v2)
2. Use existing branch (switch to it)
3. Provide custom branch name
4. Skip branch creation

Select [1]: 1

Enter suffix [v2]: retry

Creating branch: aap-12345-fix-bug-retry...
✓ Created and switched to branch: aap-12345-fix-bug-retry
```

**Why this matters:**
- **Reusing work**: Option 2 lets you continue from an existing branch (useful if you merged work but want to add more)
- **Multiple attempts**: Option 1 helps track different approaches to the same ticket
- **Safety**: Never deletes existing branches to preserve history
- **Flexibility**: Option 3 gives full control over branch naming

**Uncommitted Changes Check:**

Before creating a new branch, daf init --checks if you have uncommitted changes in the current branch:

```bash
✓ Detected git repository

⚠ Warning: You have uncommitted changes in the current branch

Uncommitted changes:
  M devflow/cli/commands/new_command.py
  M tests/test_open_command.py
  ?? new_file.txt

Creating a new branch with uncommitted changes may cause issues.
Consider committing, stashing, or discarding your changes first.

Continue anyway? [y/n] (n):
```

**What happens:**
- **Default = No**: By default, the operation is cancelled if you say "n" (protects your work)
- **Show changes**: Lists all modified (M), added (A), and untracked (??) files
- **Give context**: Explains why uncommitted changes can cause problems
- **Cancel safely**: Returns you to terminal without creating session/opening

**If you say "n" (recommended):**
```bash
Branch creation cancelled
Tip: Commit your changes with 'git commit' or stash them with 'git stash' before creating a new branch

Session creation cancelled
```

**If you say "y" (continue anyway):**
- Branch is created with uncommitted changes
- Changes remain uncommitted in the new branch
- May cause confusion when switching branches later

**Auto mode behavior (daf open):**
When using `daf open` (auto mode), uncommitted changes are logged but don't block the operation:
```bash
⚠ Warning: You have uncommitted changes in the current branch
...
Proceeding with branch creation despite uncommitted changes (auto mode)
```

**Why this matters:**
- **Prevent lost work**: Uncommitted changes can be lost when switching branches
- **Avoid confusion**: Keeps your work organized by branch
- **Clear warnings**: Shows exactly what files are affected
- **Recommended workflow**: Commit or stash before creating new branches

**Multi-Project Workflow (Issue #149):**

Create sessions that work across multiple repositories simultaneously with the `--projects` flag:

```bash
# Multi-project session (requires --workspace)
daf new PROJ-123 -w primary --projects backend-api,frontend-app,shared-lib
```

**What happens:**
1. **Prompts for shared branch name** - Same branch name used across all projects
2. **Prompts for base branch per project** - Each project can branch from different bases
   - Example: backend-api from `main`, frontend-app from `develop`, shared-lib from `main`
3. **Creates branches in all projects** - Same name, different base branches
4. **Creates conversations for each project** - All tracked in a single session
5. **Launches Claude Code at workspace level** - Access to all projects

**Example workflow:**
```bash
# Step 1: Create multi-project session
$ daf new PROJ-12345 -w primary --projects backend-api,frontend-app

Creating multi-project session:
  Session: PROJ-12345
  Workspace: primary
  Projects (2):
    • backend-api
    • frontend-app

Branch name for all projects: PROJ-12345-add-auth

Select base branch for each project:

backend-api (default: main)
  1. main (default)
  2. develop
  3. staging
Select option [1]: 1
  → Will create branch from: main

frontend-app (default: develop)
  1. main
  2. develop (default)
  3. staging
Select option [2]: 2
  → Will create branch from: develop

Creating branches...

Processing backend-api...
  ✓ Created and switched to branch: PROJ-12345-add-auth

Processing frontend-app...
  ✓ Created and switched to branch: PROJ-12345-add-auth

✓ Multi-project session created: PROJ-12345

Projects (2):
  • backend-api
    Branch: PROJ-12345-add-auth
    Base: main
  • frontend-app
    Branch: PROJ-12345-add-auth
    Base: develop
```

**Completing multi-project sessions:**
```bash
# When you run daf complete, it processes ALL projects:
$ daf complete PROJ-12345

Processing 2 projects:

→ backend-api
  ✓ Changes committed
  ✓ Pushed to remote
  ✓ Created PR/MR: https://github.com/org/backend-api/pull/123

→ frontend-app
  ✓ Changes committed
  ✓ Pushed to remote
  ✓ Created PR/MR: https://github.com/org/frontend-app/pull/456

✓ Processed all 2 projects
```

**Key benefits:**
- **Single session** - One Claude Code session for cross-repository work
- **Consistent branch names** - Same branch name across all projects
- **Flexible base branches** - Each project can branch from appropriate base
- **Automatic PR creation** - Creates PR/MR for each project using correct base branch
- **Workspace-level context** - Claude has access to all project files

**When to use:**
- Features spanning multiple repositories (e.g., API + UI changes)
- Cross-cutting concerns (e.g., shared library updates affecting multiple consumers)
- Coordinated releases across microservices

**Requirements:**
- Must specify `--workspace` flag
- All specified projects must exist in the workspace
- Each project must be a git repository

---

### Multi-Conversation vs Multi-Session Architecture

Understanding the difference between multi-conversation and multi-session is critical for organizing your work effectively.

#### Architecture Overview

The daf tool organizes work into a **3-level hierarchy**:

```
Level 1: SESSION (issue_key: "PROJ-12345")
    │
    ├── Level 2: Conversation (working_dir: backend-api)
    │   │         - project_path: ~/dev/backend-api
    │   │         - branch: aap-12345-backup-feature
    │   │         - ai_agent_session_id: uuid-1a (active)
    │   │
    │   └── Level 3: Archived Conversations
    │                 - Previous Claude sessions (.jsonl files)
    │
    ├── Level 2: Conversation (working_dir: frontend-app)
    │   │         - project_path: ~/dev/frontend-app
    │   │         - branch: aap-12345-backup-feature
    │   │         - ai_agent_session_id: uuid-1b (active)
    │   │
    │   └── Level 3: Archived Conversations
    │                 - Previous Claude sessions (.jsonl files)
    │
    └── Level 2: Conversation (working_dir: shared-lib)
        │         - project_path: ~/dev/shared-lib
        │         - branch: aap-12345-backup-feature
        │         - ai_agent_session_id: uuid-1c (active)
        │
        └── Level 3: Archived Conversations
                      - Previous Claude sessions (.jsonl files)
```

**Key Concepts:**
- **Level 1 - SESSION**: Container identified by session name or JIRA key (e.g., "PROJ-12345")
  - Has session-level metadata (goal, status, notes, time tracking)
  - Can contain multiple conversations (one per repository)

- **Level 2 - Conversation**: Work in specific repository with unique Claude session
  - Has conversation-specific data (ai_agent_session_id, project_path, branch, message_count)
  - Can have archived conversations (previous Claude sessions for same repo)

- **Level 3 - Archived Conversations**: Previous Claude sessions for same repository
  - Preserved when starting fresh with `--new-conversation`
  - Accessible via `daf list` command

**What `daf list` shows:**
```bash
daf list
# Output shows SESSIONS (Level 1) with ALL conversations (Level 2):
# Status  Name           JIRA       Summary              Conversations                      Time
# ───────────────────────────────────────────────────────────────────────────────────────────────
#   ⏸    PROJ-12345      PROJ-12345  Backup feature       3: backend-api, frontend, sops     2h 30m
```

- Each row is ONE session (Level 1)
- "Conversations" shows COUNT and LIST of all conversation directories (Level 2)
- Active conversation (if session is active) is shown in **bold**
- Use `daf info PROJ-12345` to see detailed information about each conversation

#### Multi-Conversation Sessions (Default Behavior)

**What it is:** One session spanning multiple repositories.

**When `daf new` creates a conversation:**
- When you run `daf new --name <NAME>` and a session with that name already exists
- The command adds a NEW conversation to the EXISTING session
- All conversations share the same session metadata (goal, JIRA link, notes, time tracking)

**Example:**
```bash
# First command - creates session with conversation in backend-api
daf new --name PROJ-12345 --goal "Add auth feature" --path ~/projects/backend-api

# Second command - adds conversation to same session in frontend-app
daf new --name PROJ-12345 --goal "Add auth feature" --path ~/projects/frontend-app

# Result: 1 session with 2 conversations
daf list
# Shows 1 row:
# PROJ-12345  |  2 conversations  |  in_progress

daf info PROJ-12345
# Shows:
#   Session: PROJ-12345
#   Conversations:
#     1. backend-api (active)
#     2. frontend-app
```

**Why use multi-conversation sessions:**
- ✅ **Most common use case** - work naturally spans multiple repos
- ✅ Feature touches backend API + frontend + shared library
- ✅ Bug fix requires changes in multiple services
- ✅ Keep all related work in one logical session
- ✅ Unified notes and time tracking across all repos
- ✅ Export/import handles all repos together
- ✅ Use slash commands (`/daf list-conversations`, `/daf read-conversation`) to share context between Claude conversations

**Cross-conversation context sharing:**
See [Using Slash Commands in Multi-Conversation Sessions](#using-slash-commands-in-multi-conversation-sessions) for details on how to use `/daf list-conversations` and `/daf read-conversation` to share context between repositories.

#### Starting Fresh with --new-conversation

**What it is:** Archive current conversation and start fresh Claude session in same repository.

**When to use:**
- Conversation history too long (causing 413 errors)
- Want clean slate but preserve old approach for reference
- Completed one part, want fresh context for next

**Example:**
```bash
# First command - creates session #1
daf new --name PROJ-12345 --goal "Try Redis approach" --path ~/projects/backend

# Second command - creates session #2 (separate work stream)
daf new --name PROJ-12345 --new-session --goal "Try Memcached approach" --path ~/projects/backend

# Result: 2 separate sessions
daf list
# Shows 2 rows:
# PROJ-12345  |  Session #1  |  1 conversation  |  complete
# PROJ-12345  |  Session #2  |  1 conversation  |  in_progress

daf info PROJ-12345
# Prompts: Which session? (shows both)
```

**When to use multi-session:**
- 🔄 **Different approaches/experiments** - Try Redis vs Memcached, compare solutions
- 📅 **Incremental/phased work** - Phase 1 (MVP) vs Phase 2 (Polish) as separate sessions
- 🐛 **Bug fix vs feature enhancement** - Separate the hotfix from the feature work
- 🔀 **Abandoned/restart work** - Mark first session complete/abandoned, start fresh with new session
- 🎯 **Parallel work streams** - Two developers working on same JIRA ticket in different ways

**How to create multi-session:**
```bash
# Approach 1: Use --new-session flag
daf new --name PROJ-12345 --new-session --goal "Alternative approach"

# Approach 2: Interactive prompt (when multiple sessions exist)
daf new --name PROJ-12345 --goal "Add feature"
# Prompts:
#   Found 2 existing sessions for 'PROJ-12345':
#   1. Session #1 (Goal: Try Redis approach)
#   2. Session #2 (Goal: Try Memcached approach)
#   3. → Create new conversation (separate work stream)
#
#   Add to which session? [1]: 3
# Choosing option 3 creates session #3
```

#### When Sessions Already Exist

**Scenario: 1 existing session**
```bash
daf new --name PROJ-12345 --goal "Add feature" --path ~/projects/frontend
# Automatically adds conversation to session #1
# No prompt shown
```

**Scenario: Multiple existing sessions**
```bash
daf new --name PROJ-12345 --goal "Add feature" --path ~/projects/frontend
# Interactive prompt:
#   Found 2 existing sessions for 'PROJ-12345':
#   1. Session #1 - paused
#      Goal: Try Redis approach
#      Conversations: backend-api
#
#   2. Session #2 - in_progress
#      Goal: Try Memcached approach
#      Conversations: backend-api, worker-service
#
#   3. → Create new conversation (separate work stream)
#
#   Add to which session? [1]:

# Option 1: Adds conversation to session #1
# Option 2: Adds conversation to session #2
# Option 3: Creates new session #3
```

#### Best Practices

**Default to multi-conversation:**
- Most work spans multiple repos naturally
- Simpler to manage (one session per JIRA ticket)
- Unified notes and time tracking
- Export/import handles all repos together

**Use multi-session only when:**
- Explicitly trying different approaches
- Need to separate work phases clearly
- Want independent time tracking per approach
- Abandoning one approach and starting fresh

**Avoid these anti-patterns:**
- ❌ Creating new session for each repository (use multi-conversation instead)
- ❌ Creating new session every time you resume work (use `daf open` instead)
- ❌ Creating session #2, #3, #4 without clear reason (clutters `daf list` output)

#### Impact on Other Commands

**Commands organized by hierarchy level:**

**Level 1 (Group) - Commands that affect ALL sessions in the group:**
- `daf delete <NAME>` - Deletes ALL sessions in group (with confirmation)

**Level 2 (Session) - Commands that work on a specific session:**
- `daf list` - Shows ALL sessions as separate rows (filters available)
- `daf open <NAME>` - If multiple sessions exist, prompts to select which session
- `daf complete <NAME>` - Marks specific session as complete (prompts if multiple)
- `daf info <NAME>` - Shows specific session details with ALL conversations (prompts if multiple)
- `daf export <NAME>` - Exports specific session with ALL its conversations

**Level 3 (Conversation) - Commands that work per-conversation:**
- `daf new <NAME>` - Adds conversation to existing session (or creates new session)
- Claude Code session - Each conversation has its own `.jsonl` file
- `/daf list-conversations` - Lists ALL conversations in current session
- `/daf read-conversation` - Reads specific conversation from current session

**Example showing all 3 levels:**
```bash
# List all sessions (Level 2)
daf list
# Shows: PROJ-12345 (#1), PROJ-12345 (#2)

# View details of session #1 (Level 2) including all conversations (Level 3)
daf info PROJ-12345
# Prompts: Select session: 1 or 2
# Shows all conversations in selected session

# Delete entire group (Level 1)
daf delete PROJ-12345
# Deletes BOTH session #1 AND session #2 with all their conversations
```

---

### daf open - Resume Session

Open an existing session to continue work.

```bash
daf open <NAME-or-JIRA> [OPTIONS]
```

**Options:**
- `-w, --workspace` - Workspace name to use (overrides and persists to session)
- `--path` - Specific project path to open (selects conversation for that project)
- `--projects` - Comma-separated list of projects to add to session (e.g., "backend,frontend"; mutually exclusive with `--path`; requires `-w`)
- `--new-conversation` - Archive current Claude Code conversation and start fresh with a new one
- `--model-profile` - Model provider profile to use (overrides session default; stored in session for future use)
- `--json` - Return JSON output (non-interactive mode). Suppresses all interactive prompts (branch creation, branch strategy selection, etc.) and uses sensible defaults. Suitable for automation, CI/CD pipelines, and integration tests.

**Examples:**
```bash
# Open by JIRA key
daf open PROJ-12345

# Open by session name
daf open redis-test

# Open most recent session
daf open

# Start fresh conversation (archive current, create new)
daf open PROJ-12345 --new-conversation

# Override model provider for this session
daf open PROJ-12345 --model-profile llama-cpp

# JSON output for automation
daf open PROJ-12345 --json

# Add multiple projects to session (doesn't launch Claude)
daf open PROJ-12345 -w primary --projects backend,frontend,docs

# Open specific project conversation
daf open PROJ-12345 --path backend-api
```

**Multi-Repository Workflow Example:**

When working on a ticket that requires changes in multiple repositories (e.g., backend + frontend):

```bash
# First time: Work in backend repository
daf open PROJ-12345

# Prompted to select repository:
Available repositories (8):
  1. backend-api
  2. frontend-app
  ...
Which project? [1-8]: 1

# Work in backend, exit Claude Code when done...

# Continue same ticket in frontend repository
daf open PROJ-12345

# Shows existing conversation and option to create new:
Found 1 conversation(s) for PROJ-12345:

  1. backend-api
     Path: /Users/you/workspace/backend-api
     Branch: feature/PROJ-12345
     Last active: 15m ago

  2. → Create new conversation (in a different project)

Which conversation? [1-2]: 2

# Select frontend repository:
Available projects:
  1. backend-api (already has conversation)
  2. frontend-app
  ...
Which project? [1-3]: 2

# Now working in frontend with separate conversation...
```

**Result:** One session tracks all work for PROJ-12345 across both repositories with unified time tracking.

**What happens:**
1. **First time opening:**
   - Prompts for working directory (if not set)
   - Generates Claude session UUID
   - Creates git branch (if configured)
     - **Handles branch conflicts (PROJ-60715)** - See branch conflict resolution above
   - Sends initial prompt to Claude with goal
   - Starts time tracking

2. **Resuming existing:**
   - **Checks workspace context (AAP-64497, #320)**
     - If current directory is in a different workspace than session's saved workspace:
       - Prompts to select workspace with session's previous workspace as default:
         1. Session's previous workspace [DEFAULT] (continue with workspace where session was created)
         2. Detected workspace (update session to use current workspace)
         3. Other configured workspaces
         4. Cancel (exit without opening session)
       - **Default selection:** Session's previous workspace (pressing Enter accepts this)
       - **Rationale:** Sessions remember their workspace for consistency across reopens
     - Workspace mismatch check is skipped when:
       - `--workspace` flag is explicitly provided (intentional override)
       - `--json` flag is used (non-interactive mode defaults to session workspace)
       - Session doesn't have a saved workspace (old sessions or new sessions)
   - Loads Claude conversation
   - Checks out git branch
   - **Syncs branch with remote (for imported sessions - PROJ-59820)**
     - Fetches branch from remote if missing locally
     - Merges remote changes if local branch is behind
     - Handles missing remote branches gracefully
   - **Checks if branch is behind base branch (PROJ-59821, AAP-65177)**
     - Prompts to sync with base branch (merge, rebase, or skip)
     - Auto-fetches to ensure up-to-date comparison
     - Skip option allows deferring sync until later
   - Resumes time tracking
   - Shows recent notes and activity

3. **Starting fresh with `--new-conversation`:**
   - Archives current Claude Code conversation (preserves full history)
   - Generates new Claude session UUID
   - Creates fresh conversation with empty history
   - Keeps same git branch and project directory
   - Useful when:
     - Conversation history gets too long (causing 413 errors)
     - You want a clean slate but preserve old approach for reference
     - You've completed one part and want fresh context for the next

**Note:** Sessions created via `daf sync` or imported from teammates may not have a branch yet. When you first open such a session, it will create a branch and handle any conflicts using the same resolution flow as `daf new` (see Branch Conflict Resolution above).

4. **When Claude Code exits (PROJ-60241):**
   - **Prompts to run `daf complete`** (configurable via `prompts.auto_complete_on_exit`)
     - `true` - Automatically runs `daf complete` workflow
     - `false` - Skips completion, session remains open for manual completion
     - `null` - Asks "Run 'daf complete' now?" (default)
   - If you confirm or auto-complete is enabled:
     - Commits uncommitted changes (if `auto_commit_on_complete` is configured)
     - Updates or creates PR/MR (if `auto_create_pr_on_complete` is configured)
     - Adds session summary to JIRA (if `auto_add_issue_summary` is configured)
     - Transitions JIRA ticket to appropriate status

**With multiple sessions in the same group:**
```
Found 2 sessions for PROJ-12345:

  1. backend-api (/Users/you/projects/backend-api)
     🎯 Add backup endpoint
     📊 in_progress | ⏱️ 2h 30m

  2. frontend-app (/Users/you/projects/frontend-app)
     🎯 Add backup UI
     📊 created | ⏱️ 0h

Which session? [1-2]:
```

**With multiple conversations in a session (PROJ-61031):**

When a session has multiple conversations (multi-conversation architecture), `daf open` will ALWAYS prompt you to select which conversation to open:

```bash
daf open PROJ-12345

Found 2 conversation(s) for PROJ-12345:

  1. backend-api
     Path: /Users/you/projects/backend-api
     Branch: aap-12345-backup-feature
     Last active: 2h ago

  2. frontend-app
     Path: /Users/you/projects/frontend-app
     Branch: aap-12345-backup-feature
     Last active: 30m ago

  3. → Create new conversation

Which conversation? [1-3] (1):
```

This allows you to easily switch between repositories in a multi-repo session. The selection happens EVERY time you run `daf open` with a multi-conversation session, ensuring you always know which conversation you're opening.

**Exit Codes:**
- `0` - Session opened successfully
- `1` - Session not found or cannot be opened

---

### daf list - List Sessions

List all sessions with token usage statistics, optional filtering, and pagination.

```bash
daf list [OPTIONS]
```

**Options:**
- `--active` - Only show active sessions
- `--status <STATUS>` - Filter by status (created, in_progress, complete)
- `--jira-status <STATUS>` - Filter by JIRA ticket status
- `--working-directory <DIR>` - Filter by repository
- `--sprint <SPRINT>` - Filter by sprint
- `--since <TIME>` - Sessions active since time
- `--before <TIME>` - Sessions active before time
- `--limit <N>` - Number of sessions to show per page (default: 25)
- `--page <N>` - Page number to display (activates non-interactive mode)
- `--all` - Show all sessions without pagination

**Interactive Pagination (Default Behavior):**

By default (when `--page` is not specified), `daf list` uses **interactive mode** that allows you to browse through pages by pressing Enter. This provides a better user experience for exploring large session lists:

1. First page is displayed automatically
2. You're prompted: "Press Enter to continue to next page, or 'q' to quit"
3. Press Enter to view the next page
4. Press 'q' to quit and return to the command prompt
5. Continue until all pages are viewed or you quit

To use **non-interactive mode** (the old behavior), specify a `--page` number explicitly.

**Examples:**
```bash
# All sessions (default pagination: 25 per page)
daf list

# Only active sessions
daf list --active

# Filter by status
daf list --status in_progress
daf list --status complete

# Filter by repository
daf list --working-directory backend-api

# Filter by sprint
daf list --sprint current
daf list --sprint "2025-01"

# Time-based filtering
daf list --since "last week"
daf list --since "3 days ago"
daf list --since "2025-01-01"

# Pagination examples
daf list                         # Interactive mode: browse with Enter/'q' (default)
daf list --limit 10              # Interactive mode: 10 sessions per page
daf list --page 2                # Non-interactive: show only page 2
daf list --limit 10 --page 2     # Non-interactive: show 10 sessions on page 2
daf list --all                   # Show all sessions without pagination

# Combine filters with pagination
daf list --status in_progress --sprint current --limit 5
daf list --working-directory backend-api --since "yesterday" --page 2
```

**Output:**

When listing with default settings (fewer than 25 sessions):
```
Your Sessions
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Status   ┃ Name            ┃ Issue      ┃ Summary                  ┃ Working Dir ┃  Time ┃ Tokens ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ Active   │ session1 (#1)   │ PROJ-12345  │ Implement backup feature │ backend-api │ 5h 45m│  1.2M  │
│ Complete │ session2 (#2)   │ PROJ-12346  │ Fix login bug            │ frontend    │ 1h 20m│ 450.5K │
└──────────┴─────────────────┴────────────┴──────────────────────────┴─────────────┴───────┴────────┘

Total: 2 sessions | 7h 5m tracked
```

**Note:** Token usage column shows total tokens (input + output) for the active conversation when using Claude Code. Displayed with K/M suffixes for readability. Shows "-" for agents that don't support token tracking.

When interactive pagination is active (more than limit sessions):
```
Your Sessions
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Status   ┃ Name            ┃ Issue      ┃ Summary                  ┃ Working Dir ┃  Time ┃ Tokens ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ Active   │ session1 (#1)   │ PROJ-12345  │ Implement backup feature │ backend-api │ 5h 45m│  1.2M  │
│ Complete │ session2 (#2)   │ PROJ-12346  │ Fix login bug            │ frontend    │ 1h 20m│ 450.5K │
└──────────┴─────────────────┴────────────┴──────────────────────────┴─────────────┴───────┴────────┘

Showing 1-25 of 50 sessions (page 1/2) | 7h 5m on this page

Press Enter to continue to next page, or 'q' to quit:
```

---

### daf complete - Complete Session

Mark a session as complete with automatic commit prompts, PR/MR creation, JIRA transition, and AI summary.

```bash
daf complete <NAME-or-JIRA> [OPTIONS]
daf complete --latest [OPTIONS]
```

**Options:**
- `--latest` - Complete the most recently active session (no identifier needed)
- `--status <STATUS>` - JIRA status to transition to
- `--attach-to-issue` - Export and attach session to JIRA ticket
- `--no-commit` - Skip git commit (don't commit changes) [PROJ-60972]
- `--no-pr` - Skip PR/MR creation (don't create pull request) [PROJ-60972]
- `--no-issue-update` - Skip JIRA updates (don't add summary or update fields) [PROJ-60972]

**Examples:**
```bash
# Interactive completion (recommended)
daf complete PROJ-12345

# Complete most recently active session (PROJ-60098)
daf complete --latest

# Complete with specific JIRA status
daf complete PROJ-12345 --status "Code Review"

# Complete and attach session export to JIRA
daf complete PROJ-12345 --attach-to-issue

# Complete latest session and attach to JIRA
daf complete --latest --attach-to-issue

# Automated completion (skip all prompts for CI/CD, integration tests)
daf complete PROJ-12345 --no-commit --no-pr --no-issue-update

# Skip only PR creation (useful when manually creating PRs)
daf complete PROJ-12345 --no-pr

# Skip only JIRA updates (useful when JIRA is down or for debugging)
daf complete PROJ-12345 --no-issue-update
```

**Using --latest flag:**

The `--latest` option automatically selects the most recently active session for completion, saving you from having to remember session names or JIRA keys. This is particularly useful when:
- You've been working on only one session
- You want to complete whichever session you worked on most recently
- You're done with your current work and ready to wrap up

When using `--latest`, the tool will:
1. Find your most recently active session (based on `last_active` timestamp)
2. Display session details for confirmation (name, JIRA key, goal, last active time)
3. Prompt you to confirm before proceeding
4. If confirmed, complete the session with all the standard workflow

**Example output:**
```
Completing most recently active session:
  Session: implement-backup-feature (PROJ-59123) (#2)
  Working directory: backend-api
  Status: In Progress
  Goal: PROJ-59123: Implement backup and restore feature
  Last active: 2025-01-15 14:30:15

Continue? [Y/n]: y
✓ Session 'implement-backup-feature' (PROJ-59123) (#2) marked as complete
✓ Total time tracked: 3h 45m
```

**Interactive workflow:**
```
✓ Session 'my-session' (PROJ-12345) marked as complete
✓ Total time tracked: 5h 45m

⚠  You have uncommitted changes:
  M  src/backup.py
  M  tests/test_backup.py
  ?? docs/backup.md

Commit these changes now? [Y/n]: y
Analyzing conversation to generate commit message...

Suggested commit message:
Add customer backup system with S3 integration

- Implement S3 backup service with encryption support
- Add automatic retry logic with exponential backoff
- Create backup scheduling system with cron integration
- Update API endpoints for backup management

Use this commit message? [Y/n]: y

✓ Changes committed

No PR/MR found for this session.
Create a PR/MR now? [Y/n]: y

Repository type detected: GITHUB

Push branch 'aap-12345-implement-backup' to remote? [Y/n]: y
Pushing aap-12345-implement-backup to origin...
✓ Pushed branch to origin

Creating draft GITHUB PR/MR...
✓ Created PR: https://github.com/org/repo/pull/123

Update JIRA ticket PROJ-12345 with PR URL? [Y/n]: y
✓ Updated JIRA Git Pull Request field

Add session summary to JIRA? [Y/n]: y

Analyzing conversation history...

Session Summary:
Implemented comprehensive backup system with S3 integration...

✓ Session summary added to JIRA

Transition JIRA ticket?
  1. Code Review
  2. Done
  3. Testing
  4. (skip)

Select [1-4]: 1

✓ Transitioned PROJ-12345: In Progress → Code Review
```

**What `daf complete` does:**

1. **Ends time tracking**
2. **Verifies you're on the correct git branch (PROJ-60262)**
   - Checks if current branch matches the session's branch
   - If on wrong branch with uncommitted changes: displays error and aborts
   - If on wrong branch without uncommitted changes: auto-checkouts session branch
   - Prevents accidentally committing session changes to wrong branch
3. **Marks session as complete**
4. **Checks for uncommitted changes** in git repository (development sessions only)
   - **Skipped for ticket_creation sessions** (PROJ-60429)
   - If found, prompts to commit them
   - **AI-generates detailed commit message** by analyzing conversation history
   - Creates multi-line message with title + 2-4 bullet points
   - Analyzes files changed, keywords, and actual work accomplished
   - Falls back to session goal if AI analysis unavailable
   - User can accept or customize the generated message
   - Uses standard commit message format with Claude Code attribution
5. **Checks for PR/MR** (development sessions only)
   - **Skipped for ticket_creation sessions** (PROJ-60429)
   - If no PR/MR exists, prompts to create one
   - Auto-detects GitHub or GitLab repository
   - **Auto-detects fork and targets upstream repository** (see Fork Support below)
   - Pushes branch to remote if not already pushed
   - Creates draft PR/MR with auto-generated description
   - Updates JIRA Git Pull Request field with PR URL
6. **Generates AI-powered summary** from conversation history (optional)
7. **Adds summary to JIRA** as a comment (optional)
8. **With `--attach-to-issue`: Syncs branch for team handoff (PROJ-59820)**
   - Prompts to commit uncommitted changes with WIP message
   - Pushes branch to remote for teammate access
   - Exports session and attaches to JIRA ticket
9. **Transitions JIRA ticket** to new status (optional)

**Fork Support for PR/MR Creation:**

When working in a fork (e.g., you forked an organization's repository to your personal account), `daf complete` automatically detects this and creates the PR/MR targeting the **upstream repository** instead of within your fork.

**Git Remote Conventions:**

The tool follows standard git remote naming conventions:
- **`origin`** - Your primary remote (typically your fork or main repository)
- **`upstream`** - The parent repository (where you want to create PRs/MRs)

⚠️ **Important**: These are conventions, not requirements. If your git setup uses different remote names, the tool will prompt you to specify which remote is which.

**How fork detection works:**

1. **GitHub CLI** - Uses `gh repo view --json parent` to detect fork parent (automatic)
2. **GitLab CLI** - Uses `glab repo view --json` to detect `forked_from_project` (automatic)
3. **Git remote** - Checks for `upstream` remote following git conventions
4. **User prompt** - If auto-detection fails, asks which remote points to upstream

**Example fork PR creation:**
```bash
# You're working in your fork: https://github.com/alice/myproject
# Upstream is: https://github.com/upstream-org/myproject

daf complete PROJ-12345

Create a PR/MR now? [Y/n]: y
Repository type detected: GITHUB
Detected fork - creating PR to upstream: upstream-org/myproject

Pushing branch to origin...
✓ Pushed branch to origin

Creating draft GITHUB PR...
✓ Created PR: https://github.com/upstream-org/myproject/pull/456
# ↑ Note: PR created in upstream repo, not your fork
```

**Why this matters:**
- **Without fork detection**: PR would be created as `alice/myproject:main ← alice/myproject:feature` (wrong - PR within your fork)
- **With fork detection**: PR is created as `upstream-org/myproject:main ← alice/myproject:feature` (correct - PR to upstream)

**Example with custom remote names:**
```bash
# Your remotes don't follow standard conventions
git remote -v
# main-repo    https://github.com/upstream-org/myproject.git (fetch)
# my-fork      https://github.com/alice/myproject.git (fetch)

daf complete PROJ-12345

Create a PR/MR now? [Y/n]: y

Could not auto-detect upstream repository for fork
Available remotes:
  - main-repo: https://github.com/upstream-org/myproject.git
  - my-fork: https://github.com/alice/myproject.git

Which remote points to the upstream (parent) repository?
Common convention: 'upstream' for parent repo, 'origin' for your fork
Upstream remote name [none]: main-repo

✓ Created PR: https://github.com/upstream-org/myproject/pull/456
```

**Upstream detection methods:**
- **Recommended**: Use `gh`/`glab` CLI - automatic fork parent detection
- **Alternative**: Add `upstream` remote manually:
  ```bash
  git remote add upstream https://github.com/upstream-org/myproject.git
  ```
- **Fallback**: Tool will prompt you to select from available remotes

The tool will automatically use whichever detection method succeeds first.

---

**Target Branch Selection:**

When creating a PR/MR, `daf complete` allows you to select which branch to target (e.g., `main`, `release/2.5`, `release/3.0`) instead of always using the repository's default branch. This is particularly useful for teams working on multiple release branches.

**How it works:**

1. Before creating the PR/MR, the tool lists all available remote branches
2. The default branch is highlighted as recommended
3. You select the target branch interactively
4. The appropriate flag is added to the `gh`/`glab` command:
   - **GitHub**: `--base <branch>` flag
   - **GitLab**: `--target-branch <branch>` flag

**Example with target branch selection:**
```bash
daf complete PROJ-12345

Create a PR/MR now? [Y/n]: y
Repository type detected: GITHUB

Select target branch for PR/MR (remote: origin):

Available branches:
1. main (default)
2. release/2.5
3. release/3.0
4. develop
5. Skip - use repository default

Select option [1/2/3/4/5] (1): 2

Pushing branch to origin...
✓ Pushed branch to origin

Creating draft GITHUB PR...
✓ Created PR: https://github.com/org/myproject/pull/123
# ↑ Note: PR targets release/2.5 branch
```

**Configuration:**

You can configure automatic target branch selection using the `prompts.auto_select_target_branch` setting:

- **`null`** (default) - Always prompt to select target branch
- **`true`** - Automatically use the default branch without prompting
- **`false`** - Skip target branch selection entirely (backward compatible, no `--base`/`--target-branch` flag)

**Example configuration:**
```json
{
  "prompts": {
    "auto_select_target_branch": true
  }
}
```

**Why this matters:**
- **Without target selection**: PRs always target the repository's default branch (usually `main`)
- **With target selection**: You can create PRs to any branch (e.g., `release/2.5`, `hotfix/1.0.1`, `develop`)
- Eliminates the need to manually change the target branch in GitHub/GitLab UI after PR creation

**Edge cases:**
- If the remote branch list is empty, the tool gracefully falls back to not specifying a target branch
- For fork scenarios, branch selection happens after fork detection, so you can select from upstream branches

---

**Session Type Behavior:**

The completion workflow varies based on session type:

- **Development sessions** (`session_type="development"`, default):
  - Full workflow including git operations (commit, PR/MR creation)
  - Branch verification and checkout
  - Commit uncommitted changes with AI-generated messages
  - Create or update PR/MR
  - Add summary to JIRA
  - Transition JIRA ticket

- **Ticket creation sessions** (`session_type="ticket_creation"`):
  - **Skips all git operations** (no commit prompts, no PR/MR creation)
  - Only performs session completion, summary, and JIRA transition
  - Used for analysis-only workflows like creating detailed JIRA tickets
  - Created via `daf jira new` command

**PR/MR Auto-Generation:**

The tool automatically:
- Detects repository type (GitHub or GitLab)
- Uses `gh` CLI for GitHub or `glab` CLI for GitLab
- Generates PR/MR description from session data
- Includes JIRA link, goal, test checklist, and deployment considerations
- Creates as **draft** PR/MR by default
- Stores PR URL in session metadata
- Updates JIRA ticket with PR link (customfield_12310220)

**Requirements:**
- For GitHub: `gh` CLI ([install](https://cli.github.com/))
- For GitLab: `glab` CLI ([install](https://gitlab.com/gitlab-org/cli))
- Both CLIs must be authenticated

**PR Template Fetching:**

The tool can automatically fetch and fill PR/MR templates from your repository. For GitHub repositories, a three-tier fallback system is used:

1. **gh CLI (authenticated)** - First choice, supports private repos, 5000 req/hr rate limit
2. **GitHub REST API (unauthenticated)** - Fallback for public repos, 60 req/hr rate limit
3. **Raw GitHub URL (direct)** - Final fallback for public repos

**Supported URL formats:**
- GitHub blob URL: `https://github.com/owner/repo/blob/main/PULL_REQUEST_TEMPLATE.md`
- GitHub raw URL: `https://raw.githubusercontent.com/owner/repo/main/PULL_REQUEST_TEMPLATE.md`
- GitLab blob URL: `https://gitlab.com/group/project/-/blob/main/.gitlab/merge_request_templates/default.md`

**For public GitHub repositories:**
- No `gh` CLI required - automatically falls back to unauthenticated API
- Works seamlessly without any authentication setup

**For private GitHub repositories:**
- Requires `gh` CLI installed and authenticated
- Provides higher rate limits (5000 vs 60 requests/hour)

**PR Template Auto-Discovery:**

Templates are automatically discovered in this priority order:
1. Organization `.github` repository (enforced, cannot be overridden)
2. Repository `.github/`, `docs/`, or root directory
3. User-configured URL in `config.json` (for testing)
4. Default built-in template

Manual configuration (optional, for testing):
```bash
# Edit ~/.daf-sessions/config.json:
# "pr_template_url": "https://github.com/org/repo/blob/main/PULL_REQUEST_TEMPLATE.md"
```

**Benefits:**
- Never forget to commit changes before closing session
- Streamlined PR/MR creation workflow
- Automatic JIRA linking (no manual field updates)
- Consistent PR/MR descriptions using session data
- Saves time on repetitive git/PR operations

---

### daf delete - Delete Session

Delete a session or all sessions.

```bash
daf delete <NAME-or-JIRA>
daf delete --all
```

**Options:**
- `--force` - Skip confirmation prompt
- `--all` - Delete all sessions
- `--keep-metadata` - Keep session files (notes, metadata) on disk

**Examples:**
```bash
# Delete specific session (with confirmation)
daf delete redis-test

# Delete without confirmation
daf delete redis-test --force

# Delete all sessions
daf delete --all

# Delete session but keep notes and metadata files
daf delete PROJ-12345 --keep-metadata
```

**Default Behavior (prevents orphaned metadata - PROJ-59815):**

By default, `daf delete` removes **both** the session index entry and session files (notes.md, metadata.json, etc.). This prevents orphaned metadata that could cause inconsistent state during re-sync.

**What gets deleted by default:**
- Session entry in index (sessions.json)
- Session directory ($DEVAIFLOW_HOME/sessions/<NAME>/)
  - Progress notes (notes.md)
  - Metadata files (metadata.json)
  - Memory files (memory.md)
  - Any other session-specific files

**What is NOT deleted:**
- Claude Code conversation files (~/.claude/projects/)
- Git branches
- JIRA tickets

**Using --keep-metadata flag:**

Use `--keep-metadata` when you want to preserve notes for reference while removing the session from your active list. This is useful for:

1. **Re-syncing after accidental deletion** - Keep notes when deleting, then run `daf sync` to recreate
2. **Archiving completed work** - Clean up active sessions but preserve documentation
3. **Switching approaches** - Start fresh while keeping notes from previous attempt as reference
4. **Session corruption** - Reset a problematic session while preserving progress notes

**Example with --keep-metadata:**
```bash
# Delete session from index but keep notes for reference
daf delete PROJ-59815 --keep-metadata

# Later, re-sync from JIRA (creates fresh session, old notes still available)
daf sync

# Or create a new session manually (old notes preserved in session directory)
daf new --name PROJ-59815 --goal "Fresh approach" --jira PROJ-59815
```

**Exit Codes:**
- `0` - Session deleted successfully
- `1` - Session not found or no identifier provided

---

## Workspace Management

### What are Workspaces?

Workspaces enable concurrent multi-branch development by organizing repositories into named locations (similar to VSCode workspaces). Each workspace can have active sessions without conflicts, allowing you to work on the same project in different workspaces simultaneously.

**Key Benefits:**
- Work on the same project with different branches in parallel (e.g., main development + experimental feature)
- Organize repositories by product, team, or workflow
- Sessions remember their workspace and automatically reuse it on reopen
- No conflicts between concurrent sessions in different workspaces

**Use Cases:**
- **Concurrent multi-branch development**: `primary` workspace for main development + `feat-caching` for experimental branch
- **Product organization**: `product-a` workspace for Product A repos + `product-b` for Product B repos + `product-c` for Product C repos
- **Team vs personal work**: `personal` workspace for experiments + `team` for production work
- **Client projects**: `client-acme` workspace + `client-globex` workspace for different client codebases

---

### daf workspace list - List Workspaces

View all configured workspaces and their paths.

```bash
daf workspace list
```

**What it shows:**
- Workspace name (used with -w flag)
- Full path to workspace directory
- Default workspace marker (✓)

**Output:**
```
                Configured Workspaces
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Name        ┃ Path                        ┃ Default ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ primary     │ /Users/john/development     │ ✓       │
│ product-a   │ /Users/john/repos/product-a │         │
│ feat-cache  │ /Users/john/work/caching    │         │
└─────────────┴─────────────────────────────┴─────────┘
```

**When to use:**
- See available workspaces before creating a session
- Check which workspace is set as default
- Verify workspace paths are correct
- Find workspace names to use with `-w` flag

**Notes:**
- This command CAN run inside Claude Code sessions (read-only)
- The default workspace is used when no `-w` flag is provided
- Sessions remember their workspace for automatic reuse

---

### daf workspace add - Add Workspace

**⚠️ RESTRICTED**: This command must be run OUTSIDE Claude Code sessions.

Add a new named workspace to your configuration.

```bash
daf workspace add <NAME> <PATH> [--default]
daf workspace add <PATH> [--default]     # Auto-derive name from path
```

**Arguments:**
- `<NAME>` - Unique workspace name (alphanumeric, hyphens allowed) - optional if path provided
- `<PATH>` - Absolute or home-relative path to workspace directory

**Options:**
- `--default` - Set this workspace as the default for new sessions

**Auto-Derive Name from Path:**
When only a path is provided (contains `/`), the workspace name is automatically derived from the last directory component.

**Examples:**
```bash
# Explicit name and path
daf workspace add product-a ~/repos/product-a

# Add workspace and set as default
daf workspace add primary ~/development --default

# Auto-derive name from path (name becomes "my-project")
daf workspace add ~/development/my-project

# Auto-derive with --default flag (name becomes "experiments")
daf workspace add ~/repos/experiments --default

# Interactive mode (prompts for name and path)
daf workspace add
```

**What it does:**
1. Auto-derives workspace name from path if only path provided
2. Validates workspace name (unique, valid format)
3. Expands and validates path (creates directory if missing)
4. Adds workspace to config.json
5. Optionally sets as default workspace
6. Shows confirmation with workspace details

**Validation:**
- Workspace name must be unique
- Path must be valid (will be created if missing)
- Only one workspace can be default (automatically updates previous default)

**When to use:**
- Setting up workspaces for the first time
- Adding a new product or project workspace
- Creating workspace for experimental branches
- Quickly adding workspaces without thinking of a name

---

### daf workspace remove - Remove Workspace

**⚠️ RESTRICTED**: This command must be run OUTSIDE Claude Code sessions.

Remove a workspace from configuration.

```bash
daf workspace remove <NAME> [--force]
```

**Arguments:**
- `<NAME>` - Workspace name to remove

**Options:**
- `--force` - Skip confirmation prompt

**Examples:**
```bash
# Remove workspace (with confirmation)
daf workspace remove old-project

# Remove without confirmation
daf workspace remove temp-workspace --force
```

**What it does:**
1. Checks if workspace exists
2. Warns if workspace is the default
3. Prompts for confirmation (unless --force)
4. Removes workspace from config.json
5. Shows confirmation

**Safety:**
- Prompts for confirmation before removal (unless --force)
- Warns if removing the default workspace
- Does NOT delete files on disk (only removes from configuration)
- Cannot remove if it's the only workspace

**When to use:**
- Cleaning up workspaces no longer in use
- Removing temporary experimental workspaces
- Reorganizing workspace configuration

**Important:** This only removes the workspace from configuration. Files on disk are NOT deleted.

---

### daf workspace set-default - Set Default Workspace

**⚠️ RESTRICTED**: This command must be run OUTSIDE Claude Code sessions.

Set a workspace as the default for new sessions.

```bash
daf workspace set-default <NAME>
```

**Arguments:**
- `<NAME>` - Workspace name to set as default

**Examples:**
```bash
# Set primary as default
daf workspace set-default primary

# Switch default to product workspace
daf workspace set-default product-a
```

**What it does:**
1. Validates workspace exists
2. Updates previous default to non-default
3. Sets specified workspace as default
4. Saves changes to config.json
5. Shows confirmation

**When to use:**
- Changing your default workspace permanently
- Setting up initial workspace configuration

**Important - When NOT to use:**
- ❌ **NOT for switching between workspaces per-session**
- ❌ **NOT for going back and forth between workspaces**

**For switching workspaces, use the `-w` flag instead:**
```bash
# Switch per-session with -w flag (RECOMMENDED)
daf new --name AAP-123 -w feat-caching    # Create in feat-caching
daf open AAP-123 -w primary               # Override to primary

# Sessions remember workspace automatically
daf open AAP-123  # Uses feat-caching (remembered from creation)
```

**Why?** The `-w` flag provides per-session workspace selection, while `set-default` changes the global default for ALL new sessions. Use `set-default` only for permanent configuration changes.

---

### daf workspace rename - Rename Workspace

**⚠️ RESTRICTED**: This command must be run OUTSIDE Claude Code sessions.

Rename an existing workspace. This command automatically updates all sessions that use the old workspace name.

```bash
daf workspace rename <OLD_NAME> <NEW_NAME>
daf workspace rename                        # Interactive mode
```

**Arguments:**
- `<OLD_NAME>` - Current workspace name
- `<NEW_NAME>` - New workspace name

**Examples:**
```bash
# Rename workspace
daf workspace rename old-name new-name

# Rename with better naming
daf workspace rename temp-workspace product-b

# Interactive mode (prompts for selection and new name)
daf workspace rename
```

**What it does:**
1. Validates old workspace exists
2. Validates new name is unique
3. Renames workspace in config.json
4. **Automatically updates all sessions** that use the old workspace name
5. Shows confirmation with number of sessions updated

**Example output:**
```
✓ Renamed workspace: temp-workspace → product-b
Updated 3 session(s) to use new workspace name
```

**When to use:**
- Reorganizing workspace naming conventions
- Fixing typos in workspace names
- Better categorizing workspaces

**Important:** All sessions using the old workspace name are automatically updated to use the new name, so you don't lose any session associations.

---

### Workspace Selection Priority

When opening or creating a session, workspace is resolved in this order:

1. **`-w, --workspace` flag** - Explicit workspace selection (highest priority)
2. **Session stored workspace** - Workspace remembered from session creation
3. **Default workspace** - Workspace marked as default in config
4. **Interactive prompt** - User selects from available workspaces

**Examples:**

```bash
# Priority 1: -w flag overrides everything
daf new --name AAP-123 -w product-a      # Uses product-a
daf open AAP-123 -w primary              # Uses primary (overrides stored workspace)

# Priority 2: Session remembers workspace
daf new --name AAP-456 -w feat-caching   # Creates in feat-caching
daf open AAP-456                         # Uses feat-caching (remembered)

# Priority 3: Default workspace (no -w flag, no stored workspace)
daf new --name AAP-789                   # Uses default workspace

# Priority 4: Interactive prompt (no default configured)
daf new --name AAP-999                   # Prompts user to select workspace
```

**Concurrent Sessions:**

You can have active sessions for the same project in different workspaces:

```bash
# Terminal 1: Work on main branch in primary workspace
daf new --name PROJ-123 -w primary --path ~/development/myproject
# Active session in primary/myproject

# Terminal 2: Work on experimental branch in different workspace
daf new --name PROJ-123 -w experiments --path ~/experiments/myproject
# Active session in experiments/myproject (no conflict!)
```

The tool uses `(project_path, workspace_name)` tuple for concurrent session checking, allowing parallel work in different workspaces.

---

## Agent Management

### What are Agents?

Agents are AI coding assistants that integrate with DevAIFlow. DevAIFlow supports multiple agent backends, allowing you to choose the AI assistant that best fits your needs.

**Supported Agents:**
- **Claude Code** (fully tested) - Anthropic's official Claude Code CLI
- **Ollama + Claude Code** (fully tested) - Local models via Ollama
- **GitHub Copilot** (experimental) - GitHub Copilot in VS Code
- **Cursor** (experimental) - Cursor AI editor
- **Windsurf** (experimental) - Windsurf (Codeium) editor
- **Aider** (experimental) - AI pair programming in terminal
- **Continue** (experimental) - VS Code extension for AI assistance

**Note:** Only Claude Code and Ollama have been fully tested. Other agents are experimental and may have limitations.

---

### daf agent list - List Available Agents

View all supported AI agents with their installation status and capabilities.

```bash
daf agent list
daf agent list --json
```

**What it shows:**
- Agent name and description
- Installation status (✓ installed or ✗ not installed)
- Testing status (Stable or Experimental)
- Default agent marker

**Output example:**
```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┓
┃ Agent              ┃ Description             ┃ Status       ┃ Installed ┃ Default ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━┩
│ Claude Code        │ Anthropic's official... │ Stable       │ ✓         │ ✓       │
│ Ollama + Claude... │ Local models via Oll... │ Stable       │ ✓         │         │
│ GitHub Copilot     │ GitHub Copilot in VS... │ Experimental │ ✗         │         │
│ Cursor             │ Cursor AI editor        │ Experimental │ ✗         │         │
└────────────────────┴─────────────────────────┴──────────────┴───────────┴─────────┘

Legend:
  Stable - Fully tested and supported
  Experimental - Limited testing, may have issues
```

**When to use:**
- Check which agents are installed on your system
- See which agent is currently set as default
- Understand agent capabilities and testing status
- Before setting a default agent

---

### daf agent active - Show Active Agent

Show the currently active/default agent configuration.

```bash
daf agent active
daf agent active --json
```

**What it shows:**
- Agent name and description
- Installation status and CLI path
- Version information
- Supported features
- Additional requirements (if any)

**Output example:**
```
Claude Code
Anthropic's official Claude Code CLI

Status: Stable
✓ Installed: /Users/user/.local/bin/claude
  Version: 2.1.83 (Claude Code)

Installation:
  https://docs.claude.com/en/docs/claude-code/installation

Supported Features:
  ✓ Session Management
  ✓ Conversation Export
  ✓ Message Counting
  ✓ Resume Support
  ✓ Skills Support
```

**When to use:**
- Quick check of which agent is currently active
- Verify agent installation and version
- Confirm agent capabilities before starting a session

**Equivalent to:**
```bash
daf agent info  # Without specifying an agent name
```

---

### daf agent set-default - Set Default Agent

Set the default AI agent backend for DevAIFlow sessions.

```bash
daf agent set-default <NAME>
daf agent set-default        # Interactive mode
```

**Arguments:**
- `<NAME>` - Agent to use (e.g., "claude", "ollama", "cursor")

**Examples:**
```bash
# Set Claude Code as default
daf agent set-default claude

# Set Ollama for local models
daf agent set-default ollama

# Set Cursor editor
daf agent set-default cursor

# Interactive mode (prompts for selection)
daf agent set-default
```

**What it does:**
1. Validates agent name
2. Checks if agent is installed
3. Verifies all requirements are met
4. Updates config.agent_backend
5. Shows confirmation

**Validation:**
- Agent must be a supported backend
- Agent CLI must be installed and available in PATH
- Additional requirements must be met (e.g., Ollama requires both `ollama` and `claude`)

**When to use:**
- Switching between different AI assistants
- Setting up DevAIFlow for the first time
- Experimenting with different agents

**Common errors:**
```
✗ Agent 'Cursor' is not installed
  Install from: https://cursor.sh/

✗ Missing requirements:
  - claude (Claude Code CLI)
```

---

### daf agent test - Test Agent Availability

Test if an agent is available and ready to use.

```bash
daf agent test <NAME>
daf agent test              # Test default agent
```

**Arguments:**
- `<NAME>` - Agent to test (optional, defaults to configured default)

**Examples:**
```bash
# Test Claude Code
daf agent test claude

# Test Ollama
daf agent test ollama

# Test default agent
daf agent test
```

**What it shows:**
- CLI availability and path
- Version information (if available)
- Requirements check
- Overall readiness status

**Output example:**
```
Testing Claude Code

✓ CLI available: /usr/local/bin/claude
  Version: 1.2.3
✓ All requirements met

✓ Claude Code is ready to use
```

**With missing requirements:**
```
Testing Ollama + Claude Code

✓ CLI available: /usr/local/bin/ollama
  Version: 0.1.0
✗ Missing requirements:
  - claude (Claude Code CLI)

✗ Ollama + Claude Code is not ready
```

**When to use:**
- Before setting a new default agent
- Troubleshooting agent installation issues
- Verifying environment setup
- In CI/CD to check prerequisites

---

### daf agent info - Show Agent Details

Show detailed information about an agent including installation instructions, features, and requirements.

```bash
daf agent info <NAME>
daf agent info              # Show default agent
```

**Arguments:**
- `<NAME>` - Agent to show info for (optional, defaults to configured default)

**Examples:**
```bash
# Show Claude Code info
daf agent info claude

# Show Ollama info
daf agent info ollama

# Show default agent info
daf agent info
```

**What it shows:**
- Full agent name and description
- Testing status (Stable or Experimental)
- Installation status and CLI path
- Version information
- Installation URL
- Supported features (session management, conversation export, etc.)
- Additional requirements
- Notes and limitations

**Output example:**
```
Claude Code
Anthropic's official Claude Code CLI

Status: Stable
✓ Installed: /usr/local/bin/claude
  Version: 1.2.3

Installation:
  https://docs.claude.com/en/docs/claude-code/installation

Supported Features:
  ✓ Session Management
  ✓ Conversation Export
  ✓ Message Counting
  ✓ Resume Support
  ✓ Skills Support
```

**For experimental agents:**
```
Cursor
Cursor AI editor

Status: Experimental
✗ Not installed
  CLI command: cursor

Installation:
  https://cursor.sh/

Supported Features:
  ✗ Session Management
  ✗ Conversation Export
  ✗ Message Counting
  ✗ Resume Support
  ✗ Skills Support

Notes:
  Limited integration - experimental support only
```

**When to use:**
- Learning about available agents
- Understanding agent capabilities
- Getting installation instructions
- Checking feature support before switching

---

## JIRA Integration Commands

### daf link - Link JIRA to Session

Link a JIRA ticket to an existing session.

```bash
daf link <NAME> --jira <JIRA-KEY> [--force] [--json]
```

**Options:**
- `--force` - Skip confirmation prompts (auto-replace existing links)
- `--json` - Return JSON output (non-interactive, auto-replace existing links)

**Example:**
```bash
# Basic usage
daf link redis-test --jira PROJ-12345

# Replace existing link without confirmation
daf link redis-test --jira PROJ-67890 --force

# JSON output for automation
daf link redis-test --jira PROJ-12345 --json
```

**What it does:**
1. Validates JIRA ticket exists
2. Fetches ticket metadata (title, status, sprint)
3. Links ticket to session (prompts if already linked, unless --force or --json is used)
4. Updates all conversations in the session

**Automation support:**
- `--force` flag skips interactive prompts, automatically replacing existing links
- `--json` flag returns machine-readable JSON output and bypasses all prompts
- Both flags enable non-interactive usage in CI/CD pipelines and scripts

---

### daf unlink - Remove JIRA Link

Remove JIRA association from a session.

```bash
daf unlink <NAME-or-JIRA> [--force]
```

**Options:**
- `--force` - Skip confirmation prompt (useful for scripts and automation)

**Example:**
```bash
daf unlink redis-test
```

Keeps all session data, just removes the JIRA link.

---

### daf status - Sprint Dashboard

View sprint progress and status.

```bash
daf status
```

**Output:**
```
Current Sprint: 2025-01

In Progress:
🚧 PROJ-12345  Customer backup          5 pts | 5h 45m | 75%
🚧 PROJ-12346  Fix password reset       3 pts | 1h 20m | 40%

Ready to Start:
🆕 PROJ-12347  Add 2FA support          8 pts | 0h     | 0%

Code Review:
✅ PROJ-12344  User profile API         5 pts | 4h 10m | 100%

Done:
✓ PROJ-12343  Login endpoint           3 pts | 2h 30m | 100%

Sprint Progress:
  Completed: 8 pts (30%)
  In Progress: 8 pts (30%)
  Remaining: 10 pts (40%)
  Total: 26 pts

Time Spent: 13h 45m
Estimated Remaining: ~16h
```

---

### daf active - Show Active Conversation

Show currently active Claude Code conversation with token usage statistics (if any).

```bash
daf active
```

**When active conversation exists:**
```
┌─ ▶ Currently Active ───────────────────────────────┐
│ DAF Session: PROJ-12345 (#1)                         │
│ JIRA: PROJ-12345                                    │
│ Conversation: backend-api                          │
│ Project: /workspace/backend-api                    │
│ Goal: Add user profile API and UI                 │
│ Branch: feature/PROJ-12345                          │
│ Time (this session): 1h 23m                        │
│ Status: in_progress                                │
│ Tokens: 1,234,567                                  │
│                                                     │
│ Other conversations in this session:               │
│   • frontend-app (branch: feature/PROJ-12345-ui)    │
└────────────────────────────────────────────────────┘

To pause: Exit Claude Code
To switch: daf open PROJ-12345 (and select different conversation)
```

**When no active conversation:**
```
No active conversation

Recent conversations:
  PROJ-12345#1 (backend) - paused 15m ago
  PROJ-12346#1 (frontend) - paused 2h ago

To resume: daf open <name>
```

**What it does:**
- Detects active conversation via AI_AGENT_SESSION_ID environment variable
- Shows current conversation's project and git branch
- Lists other conversations in the session with their branches
- Displays session-level time tracking
- If no active conversation, shows recently paused conversations

**Use cases:**
- Check which conversation is currently active
- See which git branch you're working on
- Verify you're in the correct project before making changes
- View all conversations and their branches in a multi-project session
- Find recently paused conversations to resume

**Why this matters for multi-project sessions:**
- Each conversation has its own git repository and branch
- Making changes in the wrong conversation can cause lost work
- Use `daf active` to confirm you're in the right project before coding

---

### daf jira view - View JIRA Ticket

View JIRA ticket details in Claude-friendly format.

```bash
daf jira view <JIRA-KEY> [--history]
```

**Options:**
- `--history`: Show changelog/history of status transitions and field changes

**Example:**
```bash
# View ticket without history
daf jira view PROJ-12345

# View ticket with changelog/history
daf jira view PROJ-12345 --history
```

**Output (without --history):**
```
Key: PROJ-12345
Summary: Implement customer backup and restore
Status: In Progress
Type: Story
Priority: Major
Assignee: John Doe
Epic: PROJ-59038
Sprint: Sprint 42
Story Points: 5

Description:
As a user, I want to backup my data so that I can restore it later.

Acceptance Criteria:
- Backup functionality implemented
- Restore functionality implemented
- Tests added
```

**Output (with --history):**
```
Key: PROJ-12345
Summary: Implement customer backup and restore
Status: In Progress
... (ticket details shown above)

Changelog/History:
--------------------------------------------------------------------------------
2025-11-22 14:30:12 | John Doe             | status: New → In Progress
2025-11-22 14:30:45 | John Doe             | assignee: (empty) → John Doe
2025-11-22 15:15:30 | John Doe             | Story Points: (empty) → 5
2025-11-23 10:20:15 | Jane Smith           | priority: Normal → Major
2025-11-23 10:20:15 | Jane Smith           | Sprint: (empty) → Sprint 42
```

**Notes:**
- The changelog shows the last 10-15 changes by default
- Each line shows: timestamp | user | field: old value → new value
- History is optional and not shown by default to avoid clutter
```

**What it does:**
- Fetches ticket details via JIRA REST API
- Displays in human-readable format
- More reliable than curl (handles authentication automatically)
- Used by initial prompts in `daf new` and `daf open`

**Benefits over curl:**
- Simple command (no authentication headers needed)
- Better formatted output for Claude to read
- Automatic error handling
- Consistent with daf tool ecosystem

---

### daf jira new - Create JIRA Issue with Analysis Session

Create a JIRA ticket with a dedicated analysis-only session that helps you gather codebase context before creating the ticket.

```bash
daf jira new <TYPE> --parent <PARENT> --goal <GOAL> [OPTIONS]
```

**Issue Types:**
- `epic` - JIRA epic issue
- `story` - JIRA story issue
- `task` - JIRA task issue
- `bug` - JIRA bug issue

**Required Options:**
- `--parent <KEY>` - Parent JIRA key (epic for story/task/bug, story for subtask)
- `--goal <TEXT>` - Goal/description for the ticket (auto-detection of file:// paths and http(s):// URLs)
- `--goal-file <PATH|URL>` - Explicit file path or URL for goal input (mutually exclusive with `--goal`)

**Optional Options:**
- `--name <NAME>` - Session name (auto-generated from goal if not provided)
- `--path <PATH>` - Project path (bypasses interactive repository selection for non-interactive/automation use)
- `--json` - Output in JSON format (for automation and scripting)

**Goal Input Formats:**

**Using --goal (with auto-detection):**
- **Plain text**: Any multi-word text is treated as plain text
- **File path (with prefix)**: `file:///path/to/file.md` - reads file content
- **Bare file path**: `/path/to/file.md` or `requirements.md` - must be a single token (no spaces)
- **URL**: `https://example.com/spec.txt` - fetches content from URL

**Using --goal-file (explicit file/URL input):**
- **File path**: `requirements.md`, `~/docs/spec.txt`, `/absolute/path/to/file.md` - reads file content
- **URL**: `https://example.com/spec.txt` - fetches content from URL
- **Validation**: Ensures input is actually a file path or URL (not plain text)
- **Mutual exclusion**: Cannot use both `--goal` and `--goal-file` together

**What This Command Does:**

1. Creates a session with `session_type="ticket_creation"` (analysis-only)
2. Automatically skips branch creation (no git operations)
3. Launches Claude with analysis-only constraints:
   - DO NOT modify any code or files
   - DO NOT create/checkout git branches
   - Only READ and ANALYZE the codebase
4. Session persists with the same constraints when reopened

**Examples:**

```bash
# Create story session (session name auto-generated)
daf jira new story --parent PROJ-59038 --goal "Add retry logic to subscription API"

# Create bug session with custom name
daf jira new bug --parent PROJ-60000 --goal "Fix timeout in backup operation" --name fix-backup-timeout

# Create task session
daf jira new task --parent PROJ-59038 --goal "Update backup documentation"

# Create epic session
daf jira new epic --parent PROJ-59038 --goal "Implement advanced monitoring features"

# Goal from local requirements file (with file:// prefix)
daf jira new story --parent PROJ-59038 --goal "file:///path/to/requirements.md"

# Goal from local requirements file using --goal (bare path - must be single token, no spaces)
daf jira new story --parent PROJ-59038 --goal "/path/to/requirements.md"
daf jira new story --parent PROJ-59038 --goal "~/Documents/requirements.md"
daf jira new story --parent PROJ-59038 --goal "requirements.md"

# Goal from local requirements file using --goal-file (explicit, allows any path)
daf jira new story --parent PROJ-59038 --goal-file "requirements.md"
daf jira new story --parent PROJ-59038 --goal-file "~/Documents/spec.txt"
daf jira new story --parent PROJ-59038 --goal-file "/absolute/path/to/requirements.md"

# Goal from remote documentation URL
daf jira new task --parent PROJ-59038 --goal "https://docs.example.com/feature-spec.txt"

# Goal from remote documentation URL using --goal-file (explicit)
daf jira new task --parent PROJ-59038 --goal-file "https://docs.example.com/feature-spec.txt"

# Multi-word text with special characters is always treated as plain text
daf jira new bug --parent PROJ-59038 --goal "Fix error in help.py when using --output flag"

# Non-interactive mode for automation/CI (with --path and --json)
daf jira new story \
  --parent PROJ-59038 \
  --goal "Add retry logic" \
  --path /path/to/project \
  --json
```

**Workflow:**

1. **Launch Analysis Session:**
   ```bash
   daf jira new story --parent PROJ-59038 --goal "Add retry logic"
   ```

2. **Claude analyzes codebase** (read-only):
   - Searches for relevant files
   - Understands existing patterns
   - Identifies integration points
   - No code modifications allowed

3. **Claude creates JIRA ticket** using `daf jira create`:
   ```bash
   # Claude runs this command for you:
   daf jira create story --summary "Add retry logic to subscription API" \
     --parent PROJ-59038 \
     --description "..." \
     --acceptance-criteria "..."
   ```

   **Note**: Uses `--parent` parameter which automatically maps to the correct JIRA field per issue type (epic_link for stories/tasks/bugs, parent for sub-tasks).

4. **Session auto-renamed** (PROJ-60665):
   - After ticket creation, the session is automatically renamed to `creation-<TICKET_KEY>`
   - Example: `add-retry-logic` → `creation-PROJ-12345`
   - Simplifies finding the session later without complex metadata
   - Only happens when running inside a Claude Code session

5. **Reopen Later** (same constraints apply):
   ```bash
   daf open creation-PROJ-12345  # Auto-renamed session name
   # Still in analysis-only mode!
   ```

**Benefits:**

- **No Manual Constraints**: Automatic analysis-only mode enforced by session type
- **Persistent**: Constraints remembered when reopening sessions
- **No Branch Creation**: Skips branch prompts automatically
- **Better JIRA Tickets**: Claude analyzes codebase to write detailed, accurate tickets
- **Safe**: Cannot accidentally modify code during analysis

**When to Use:**

- Creating well-researched JIRA tickets based on codebase analysis
- Investigating features before writing detailed specifications
- Understanding implementation complexity before estimation
- Documenting existing code patterns in ticket descriptions

**Non-Interactive Mode (for Automation/CI/CD):**

For automated testing, CI/CD pipelines, or scripting, use the `--path` flag to bypass interactive repository selection:

```bash
# In automated environments with DAF_MOCK_MODE=1
DAF_MOCK_MODE=1 daf jira new story \
  --parent PROJ-59038 \
  --goal "Add retry logic" \
  --path /path/to/project \
  --json

# Returns JSON output suitable for parsing:
# {
#   "success": true,
#   "data": {
#     "ticket_key": "PROJ-12345",
#     "session_name": "creation-PROJ-12345",  # Auto-renamed
#     "session": {...}
#   }
# }
```

**Key Points:**
- `--path` bypasses interactive repository selection
- `--json` provides machine-readable output
- Combines with `DAF_MOCK_MODE=1` for testing workflows without creating real JIRA tickets
- No interactive prompts when all required flags are provided

**Session Type:**

Sessions created with `daf jira new` have `session_type="ticket_creation"`. This is different from regular `session_type="development"` sessions:

| Feature | development | ticket_creation | investigation |
|---------|-------------|-----------------|---------------|
| Branch creation | ✓ Prompted | ✗ Skipped | ✗ Skipped |
| Code modifications | ✓ Allowed | ✗ Forbidden | ✗ Forbidden |
| Initial prompt | Standard | Analysis-only | Investigation-only |
| Reopen behavior | Standard | Analysis-only | Investigation-only |
| Ticket creation | No | Yes (daf jira create) | No |

---

### daf investigate - Create Investigation-Only Session

Create an investigation-only session for codebase exploration without ticket creation. Use this when you want to research feasibility or explore approaches before committing to creating a JIRA ticket.

```bash
daf investigate --goal <GOAL> [OPTIONS]
```

**Required Options:**
- `--goal <TEXT>` - Goal/description for the investigation (auto-detection of file:// paths and http(s):// URLs)
- `--goal-file <PATH|URL>` - Explicit file path or URL for goal input (mutually exclusive with `--goal`)

**Optional Options:**
- `--parent <KEY>` - Optional parent JIRA key (for tracking investigation under an epic)
- `--name <NAME>` - Session name (auto-generated from goal if not provided)
- `--path <PATH>` - Project path (bypasses interactive repository selection)
- `--model-profile <PROFILE>` - Model provider profile to use (e.g., "vertex", "llama-cpp"; stored in session for future use)
- `--json` - Output in JSON format (for automation and scripting)

**Goal Input Formats:**

**Using --goal (with auto-detection):**
- **Plain text**: Any multi-word text is treated as plain text
- **File path (with prefix)**: `file:///path/to/file.md` - reads file content
- **Bare file path**: `/path/to/file.md` or `requirements.md` - must be a single token (no spaces)
- **URL**: `https://example.com/spec.txt` - fetches content from URL

**Using --goal-file (explicit file/URL input):**
- **File path**: `requirements.md`, `~/docs/spec.txt`, `/absolute/path/to/file.md` - reads file content
- **URL**: `https://example.com/spec.txt` - fetches content from URL
- **Validation**: Ensures input is actually a file path or URL (not plain text)
- **Mutual exclusion**: Cannot use both `--goal` and `--goal-file` together

**What This Command Does:**

1. Creates a session with `session_type="investigation"` (analysis-only)
2. Automatically skips branch creation (no git operations)
3. Launches Claude with investigation-only constraints:
   - DO NOT modify any code or files
   - DO NOT create/checkout git branches
   - Focus on understanding and documenting findings
   - MAY create JIRA tickets for bugs or improvements discovered during investigation
4. Session persists for future reopening with same constraints

**Examples:**

```bash
# Basic investigation session (session name auto-generated)
daf investigate --goal "Research Redis caching options for subscription API"

# Investigation with parent tracking
daf investigate --goal "Investigate timeout issue in backup service" --parent PROJ-59038

# Investigation with custom session name
daf investigate --goal "Explore API refactoring approaches" --name api-refactor-research

# Goal from local requirements file (with file:// prefix)
daf investigate --goal "file:///path/to/research-notes.md"

# Goal from local requirements file using --goal (bare path)
daf investigate --goal "/path/to/research-notes.md"
daf investigate --goal "~/Documents/investigation-plan.md"

# Goal from local requirements file using --goal-file (explicit)
daf investigate --goal-file "research-notes.md"
daf investigate --goal-file "~/Documents/investigation-plan.md"
daf investigate --goal-file "/absolute/path/to/research-notes.md"

# Goal from remote documentation URL
daf investigate --goal "https://docs.example.com/requirements.txt"

# Goal from remote documentation URL using --goal-file (explicit)
daf investigate --goal-file "https://docs.example.com/requirements.txt"

# Non-interactive mode for automation (with --path and --json)
daf investigate \
  --goal "Research database scaling options" \
  --path /path/to/project \
  --json

# Use local model for cost-free investigation
daf investigate --goal "Explore API design patterns" --model-profile llama-cpp
```

**Workflow:**

1. **Launch Investigation Session:**
   ```bash
   daf investigate --goal "Research Redis caching options"
   ```

2. **Claude investigates codebase** (read-only):
   - Searches for relevant files
   - Understands existing patterns
   - Analyzes feasibility and trade-offs
   - Documents findings and recommendations
   - No code modifications or ticket creation

3. **Save findings** using notes:
   ```bash
   daf note "Found 3 possible approaches: 1) Redis as session store, 2) Redis for cache layer, 3) Hybrid approach. Recommend approach 2 due to..."
   ```

4. **Export or complete session:**
   ```bash
   daf complete <session-name>
   # OR
   daf export-md -i <session-name> --output-dir ./research
   ```

5. **Reopen later** (same constraints apply):
   ```bash
   daf open <session-name>
   # Still in investigation-only mode!
   ```

**Comparison with daf jira new:**

| Feature | `daf investigate` | `daf jira new` |
|---------|-------------------|----------------|
| Purpose | Research/exploration only | Create JIRA ticket with analysis |
| Session type | `investigation` | `ticket_creation` |
| Ticket creation | No - forbidden | Yes - via `daf jira create` |
| Parent tracking | Optional (for reference) | Required |
| Branch creation | No | No |
| Code modifications | No | No |
| Use case | Pre-ticket feasibility research | Detailed ticket creation |

**When to Use:**

- **Use `daf investigate`** when:
  - You're exploring whether something is feasible
  - You want to research different approaches before committing
  - You need to understand a complex codebase area
  - You're investigating a bug or issue to understand root cause
  - You don't want to create a JIRA ticket yet

- **Use `daf jira new`** when:
  - You know you need to create a JIRA ticket
  - You want Claude to help write detailed requirements
  - You're ready to commit to the work
  - You need structured ticket creation workflow

**Key Points:**
- Sessions are READ-ONLY - no code changes allowed
- No branch creation or git operations
- Parent is optional and only for tracking purposes
- Findings can be captured using `daf note` commands
- Session can be completed without creating tickets
- Ideal for spike/research work before committing to implementation

---

### daf jira create - Create JIRA Issue

Create a JIRA issue (bug, story, or task) from command line.

```bash
daf jira create <TYPE> [OPTIONS]
```

**Issue Types:**
- `bug` - JIRA bug issue
- `story` - JIRA story issue
- `task` - JIRA task issue

**Options:**
- `--summary` - Issue summary (prompts if not provided)
- `--description` - Issue description text
- `--description-file <PATH>` - File containing description
- `--priority` - Priority (Critical, Major, Normal, Minor) [default: Major for bug/story, Normal for task]
- `--parent` - Parent issue key to link to (epic for story/task/bug, parent for sub-task)
- `--affected-version` - Affected version (bugs only) [default: myproject-ga]
- `--field` / `-f` - Set custom field value (format: field_name=value, can be used multiple times)
- `--create-session` - Create daf session immediately after creation
- `--interactive` - Interactive template mode (prompts for summary + description)

**Examples:**

```bash
# Create epic
daf jira create epic --summary "Backup and Restore Feature" --priority Major

# Create spike with parent epic
daf jira create spike --summary "Research backup strategies" --parent PROJ-59038

# Create story with parent link
daf jira create story --summary "Implement backup feature" --parent PROJ-59038

# Create task with session
daf jira create task --summary "Update documentation" --create-session

# Create bug with summary
daf jira create bug --summary "Customer backup fails" --priority Major

# Interactive mode (prompts for both summary and description)
daf jira create bug --interactive

# Specify custom fields
daf jira create bug --summary "Login error" --field workstream="Hosted Services" --field severity=High

# Load description from file
daf jira create story --summary "New feature" --description-file story_desc.txt
```

**Issue Type Templates:**

**Epic Template:**
```
h2. *Background*
<fill out any context, value prop, description needed>

h2. *User Stories*
Format: "as a <type of user> I want <some goal> so that <some reason>"

h2. *Supporting documentation*
<include links to technical docs, diagrams, etc>

h2. *Definition of Done*
*Should be reviewed and updated by the team*
 * Item 1
 * Item 2

h2. *Acceptance Criteria*
h3. Requirements
<functional requirements to deliver this work>
 * Item 1
 * Item 2
 * Item 3

h3. End to End Test
<at least one end-to-end test from customer perspective>
 # Step 1
 # Step 2
 # Step 3
 # Step 4
```

**Spike Template:**
```
h3. *User Story*
Format: "as a <type of user> I want <some goal> so that <some reason>"

h3. *Supporting documentation*
<include links to technical docs, diagrams, etc>

h3. *Definition of Done*
*Should be reviewed and updated by the team*
 * Item 1
 * Item 2

h3. *Acceptance Criteria*
h3. Requirements
<functional requirements to deliver this work>
 * Item 1
 * Item 2
 * Item 3

h3. End to End Test
<at least one end-to-end test from customer perspective>
 # Step 1
 # Step 2
 # Step 3
 # Step 4
```

**Story Template:**
```
h3. *User Story*
Format: "as a <type of user> I want <some goal> so that <some reason>"

h3. *Supporting documentation*
<include links to technical docs, diagrams, etc>
```

**Task Template:**
```
h3. *Problem Description*
<what is the issue, what is being asked, what is expected>

h3. *Supporting documentation*
```

**Bug Template:**
```
*Description*
<what is happening, why are you requesting this update>

*Steps to Reproduce*
<list explicit steps to reproduce>

*Actual Behavior*
<what is currently happening>

*Expected Behavior*
<what should happen>

*Additional Context*
<Provide any related communication on this issue>
```

**Custom Field Handling:**

Custom field values can be provided via:
1. Config defaults (`jira.custom_field_defaults`) - used if not specified in command
2. `--field` options - override config defaults for specific fields
3. Multiple `--field` options can be used for different custom fields

**Field Discovery:**

On first use, automatically discovers and caches JIRA custom field mappings in `config.json`. This enables:
- Using human-readable field names instead of cryptic IDs
- Support for any JIRA instance (not hardcoded)
- Offline operation after initial discovery

**Benefits:**
- Quick JIRA issue creation from CLI
- Unified command for all issue types
- No need to navigate web interface
- Uses JIRA templates from AGENTS.md
- Automatic field discovery and caching
- Configurable custom field defaults
- Optional immediate session creation
- Fully interactive mode (no flags required)

---

### daf jira update - Update JIRA Issue Fields

Update JIRA issue fields from the command line.

```bash
daf jira update <ISSUE-KEY> [OPTIONS]
```

**Options:**
- `--description` - Update issue description
- `--description-file <PATH>` - Read description from file
- `--priority` - Update priority (Critical, Major, Normal, Minor)
- `--assignee` - Update assignee (username or "none" to clear)
- `--summary` - Update issue summary
- `--acceptance-criteria` - Update acceptance criteria
- `--status` - Transition ticket to a new status (e.g., 'In Progress', 'Review', 'Closed')
- `--git-pull-request` - Add PR/MR URL(s) (comma-separated, auto-appends to existing)
- `--field` / `-f` - Update any custom field (format: field_name=value)
- **Dynamic options** - Run `daf jira update <ISSUE-KEY> --help` to see all editable fields for that specific issue

**Examples:**
```bash
# Update description
daf jira update PROJ-12345 --description "New description text"

# Update description from file
daf jira update PROJ-12345 --description-file /path/to/description.txt

# Update priority and assignee
daf jira update PROJ-12345 --priority Major --assignee jdoe

# Update summary
daf jira update PROJ-12345 --summary "New summary text"

# Update acceptance criteria
daf jira update PROJ-12345 --acceptance-criteria "- New criterion 1\n- New criterion 2"

# Clear assignee
daf jira update PROJ-12345 --assignee none

# Update multiple fields at once
daf jira update PROJ-12345 --summary "Updated summary" --priority Critical --description "Updated description"

# Add PR/MR link (auto-appends to existing links)
daf jira update PROJ-12345 --git-pull-request "https://github.com/org/repo/pull/123"

# Update custom fields using --field option
daf jira update PROJ-12345 --field severity=Critical --field size=L

# Use dynamic options (discovered when viewing help)
daf jira update PROJ-12345 --epic-link PROJ-59000 --story-points 5

# Transition ticket status
daf jira update PROJ-12345 --status "In Progress"

# Transition status and update other fields together
daf jira update PROJ-12345 --status "Review" --priority Major --assignee jdoe
```

**Dynamic Field Discovery:**

To see all editable fields for a specific issue, run:
```bash
daf jira update PROJ-12345 --help
```

This command:
1. Detects the issue key from the command
2. Calls the JIRA editmeta API for that issue
3. Discovers all editable fields for that issue's current state
4. Shows dynamic CLI options with field names and allowed values

Example output:
```
Options:
  --description TEXT              Update issue description
  --priority [Critical|Major|Normal|Minor]
                                  Update priority
  --epic-link TEXT                Update Epic Link
  --story-points TEXT             Update Story Points
  --sprint TEXT                   Update Sprint
  --blocked TEXT                  Update Blocked (choices: True, False)
  --blocked-reason TEXT           Update Blocked Reason
  --severity TEXT                 Update Severity (choices: Critical, High, Medium, Low)
  ...
```

The help output is customized for each issue, showing only fields that can be edited for that issue's workflow state.

**What it does:**
- Updates specified JIRA issue fields via REST API
- Uses field mapper for human-readable custom field names
- Validates field values when possible
- Provides detailed error messages if update fails
- Shows confirmation of updated fields

**Benefits:**
- Quick field updates without JIRA web interface
- Support for both standard and custom fields
- Human-readable field names (no need for field IDs)
- Multiple fields can be updated in single command
- Consistent with daf jira create commands

**Common use cases:**
- Update descriptions with latest findings
- Adjust priority based on severity
- Update acceptance criteria as requirements evolve
- Change assignee for handoff
- Bulk update fields for issue management
- Transition ticket status through workflow

**Status Transitions:**

The `--status` option allows you to transition tickets through JIRA workflow states:

```bash
# Transition ticket to In Progress
daf jira update PROJ-12345 --status "In Progress"

# Transition to Review
daf jira update PROJ-12345 --status "Review"

# Transition to Closed
daf jira update PROJ-12345 --status "Closed"
```

**How status transitions work:**
1. The command fetches available transitions from JIRA API for the ticket
2. Matches the requested status (case-insensitive) to available transitions
3. Executes the transition if valid
4. Shows error with available transitions if status is not available

**Error handling:**
- If the requested status is not available for transition, the command shows all available transitions
- If the transition requires additional fields (e.g., resolution when closing), the error message shows which fields are required
- Status transitions can be combined with other field updates in a single command

**Example error output:**
```
✗ Status 'Closed' not available for PROJ-12345. Available transitions: In Progress, Review, Blocked
```

---

### daf jira add-comment - Add Comment to JIRA Issue

Add a comment to a JIRA issue with automatic Example Group visibility restriction.

```bash
daf jira add-comment <ISSUE-KEY> [COMMENT] [OPTIONS]
```

**Arguments:**
- `<ISSUE-KEY>` - JIRA issue key (e.g., PROJ-12345)
- `[COMMENT]` - Comment text (optional if using --file or --stdin)

**Options:**
- `--file <PATH>` - Read comment text from a file
- `--stdin` - Read comment text from stdin
- `--public` - Make comment public (visible to all, requires confirmation)
- `--json` - Output in JSON format

**Examples:**

```bash
# Add simple comment (Example Group visibility by default)
daf jira add-comment PROJ-12345 "Fixed the authentication bug"

# Add comment from file
daf jira add-comment PROJ-12345 --file progress-notes.txt

# Add comment from stdin (useful in automation)
echo "Deployment completed successfully" | daf jira add-comment PROJ-12345 --stdin

# Add comment with JIRA Wiki markup
daf jira add-comment PROJ-12345 "h3. Update\n\nFixed the issue.\n\n{code:bash}\nnpm test\n{code}"

# Add public comment (requires confirmation)
daf jira add-comment PROJ-12345 "Public announcement" --public

# JSON output for automation
daf jira add-comment PROJ-12345 "Automated update" --json
```

**What it does:**
- Adds a comment to the specified JIRA issue
- By default, restricts comment visibility to "Example Group" group
- Uses visibility settings from config.json (comment_visibility_type and comment_visibility_value)
- Supports JIRA Wiki markup for formatting
- Validates issue exists before adding comment
- Provides clear error messages for authentication or API failures

**Visibility Configuration:**

The default comment visibility is configured in `$DEVAIFLOW_HOME/config.json`:

```json
{
  "jira": {
    "comment_visibility_type": "group",
    "comment_visibility_value": "Example Group"
  }
}
```

To change default visibility:
```bash
daf config edit
# Navigate to "JIRA Integration" tab
# Set "Comment Visibility Type" to "group"
# Set "Comment Visibility Value" to "Developers"
```

**Public Comments:**

Use `--public` to make a comment visible to everyone (no visibility restriction). This requires confirmation to prevent accidental public disclosure:

```bash
$ daf jira add-comment PROJ-12345 "Public update" --public
Make comment PUBLIC (visible to all)? [y/N]: y
✓ Comment added to PROJ-12345 (Public)
```

**Benefits:**
- Quick comment addition without JIRA web interface
- Automatic visibility restriction for security
- Supports long comments from files
- Pipeline-friendly with stdin and JSON output
- Consistent with daf tool ecosystem

**Common use cases:**
- Add progress updates to JIRA issues
- Document findings during debugging
- Automate comment creation in CI/CD pipelines
- Share updates with team while preserving visibility controls
- Add formatted code snippets or logs to issues

---

## Notes and Progress

### daf note - Add Progress Note

Add a note to track progress.

> **Tip:** This command now works inside Claude Code! Add notes anytime to document your work. Use `/daf-notes` to view all notes.

```bash
daf note <NAME-or-JIRA> "Note text" [--jira]
daf note "Note text"  # Uses current session
```

**Options:**
- `--jira` - Also add note as JIRA comment
- `--latest` - Use the most recently active session

**Examples:**
```bash
# Local note only (fast, offline)
daf note PROJ-12345 "Completed upload endpoint"

# Note + JIRA comment
daf note PROJ-12345 "Backend complete, ready for review" --jira

# Use most recent session
daf note "Fixed validation bug"

# Explicitly use latest session
daf note --latest "Fixed validation bug"
```

**Notes storage:**
- Always saved locally in `$DEVAIFLOW_HOME/sessions/{NAME}/notes.md`
- With `--jira`: also added as comment on JIRA ticket
- If JIRA sync fails, note is still saved locally

**When to use `daf note` vs `daf jira add-comment`:**

`daf note` is session-focused and local-first (with optional JIRA sync):
- ✓ You're actively working on a daf session
- ✓ You want to track progress locally (works offline)
- ✓ You want notes stored with session metadata
- ✓ You might review notes later with `daf notes`
- ✓ JIRA comment is optional/secondary

`daf jira add-comment` is JIRA-focused and always posts to JIRA:
- ✓ You just need to comment on a JIRA issue
- ✓ The issue might not have a daf session
- ✓ You're automating JIRA comments (CI/CD)
- ✓ You need specific visibility control
- ✓ You're reading from files/stdin

**Quick comparison:**

| Feature | `daf note` | `daf jira add-comment` |
|---------|-----------|----------------------|
| Local storage | ✓ Always | ✗ None |
| JIRA posting | Optional (`--jira`) | ✓ Always |
| Requires session | ✓ Yes | ✗ No |
| Works offline | ✓ Yes | ✗ No |
| Visibility control | Uses default | Configurable + `--public` |
| Input methods | Argument only | Argument, file, stdin |

**Exit Codes:**
- `0` - Note added successfully
- `1` - Session not found or empty note text

---

### daf notes - View Session Notes

View all notes for a session in chronological order.

```bash
daf notes [NAME-or-JIRA] [--latest]
daf notes  # Uses most recent session
```

**Options:**
- `--latest` - View notes for the most recently active session

**Examples:**
```bash
# View notes by JIRA key
daf notes PROJ-12345

# View notes by session name
daf notes my-session

# View notes for most recent session
daf notes

# Explicitly use latest session
daf notes --latest
```

**Output:**
- Displays notes in markdown format with timestamps
- Shows JIRA key if associated
- Notes are organized by session ID
- Chronological order from oldest to newest

**Exit Codes:**
- `0` - Notes displayed successfully (or no notes found for existing session)
- `1` - Session not found

---

### daf summary - View Session Summary

Display session summary without opening Claude Code.

```bash
daf summary <NAME-or-JIRA> [OPTIONS]
```

**Options:**
- `--detail` - Show full file lists and commands
- `--ai-summary` - Use AI to generate intelligent summary

**Examples:**
```bash
# Quick summary (local, fast)
daf summary PROJ-12345

# Detailed summary
daf summary PROJ-12345 --detail

# AI-powered summary
daf summary PROJ-12345 --ai-summary
```

**Output (local mode):**
```
Session: PROJ-12345 (#1)
Goal: Implement customer backup
JIRA: PROJ-12345 - "Customer backup and restore"
Status: in_progress
Time: 5h 45m (3 work sessions)

Files Created: 8
Files Modified: 5
Commands Run: 12
Notes: 4
```

**Output (AI mode):**
```
Session: PROJ-12345

Summary:
Implemented comprehensive backup system with S3 integration. Created
backup service with upload/download endpoints, metadata validation,
and encryption. Added retry logic and error handling.

Key Accomplishments:
- Backup upload API endpoint with authentication
- S3 bucket integration with encryption
- Metadata validation and storage
- Error handling and retry logic

Next Steps:
- Implement restore endpoint
- Add comprehensive tests
- Update documentation
```

---

### daf info - Display Session Details

Show detailed session information including Claude Code session UUIDs, token usage statistics, and cost estimates. Displays all conversations (with active and archived Claude sessions) for multi-conversation sessions.

**Token usage tracking** (Claude Code only):
- Shows total tokens (input + output), cache creation/reads, and cache efficiency
- Estimates session cost based on model pricing (when configured)
- Token statistics automatically hidden for agents that don't support tracking

```bash
daf info [NAME-or-JIRA] [OPTIONS]
```

**Options:**
- `--uuid-only` - Output only the Claude session UUID (for scripting)
- `--conversation-id <N>` - Show specific conversation by number (1, 2, 3...)

**Examples:**
```bash
# Show most recent session
daf info

# Show by JIRA key
daf info PROJ-60039

# Show by session name
daf info my-session

# Get UUID for scripting
daf info PROJ-60039 --uuid-only

# Show specific conversation
daf info PROJ-60039 --conversation-id 1
```

**Output (full display):**
```
Session Information

Name: implement-backup-feature
JIRA: PROJ-60039
Summary: Implement backup and restore functionality
JIRA Status: In Progress
Status: in_progress
Goal: PROJ-60039: Implement backup and restore functionality

Conversations: 2

#1 (active)
  Working Directory: backend-api
  Project Path: /path/to/backend-api
  Branch: feature-backup
  Claude Session UUID: f545206f-480f-4c2d-8823-c6643f0e693d
  Conversation File: ~/.claude/projects/.../f545206f-480f-4c2d-8823-c6643f0e693d.jsonl
  Created: 2025-12-05 13:07:00
  Last Active: 2025-12-05 18:30:15
  Messages: 45
  Token Usage:
    Total: 1,234,567 (Input: 890,123 | Output: 344,444)
    Cache: 234,567 created, 456,789 read (66.1% efficiency)
    Estimated Cost: $4.23
  PRs: https://github.com/org/repo/pull/123

  Archived Sessions (1):
    UUID: a1b2c3d4-5678-...
    Summary: Initial backup implementation approach
    Messages: 89
    Created: 2025-12-01 10:00:00
    Archived: 2025-12-05 13:07:00

#2
  Working Directory: frontend-app
  Project Path: /path/to/frontend-app
  Branch: feature-backup
  Claude Session UUID: be07636e-44c3-41fb-a3b6-dc9c0a530806
  Conversation File: ~/.claude/projects/.../be07636e-44c3-41fb-a3b6-dc9c0a530806.jsonl
  Created: 2025-12-05 14:00:00
  Last Active: 2025-12-05 17:00:00

Time Tracked: 5h 45m
  By user:
    alice: 3h 30m
    bob: 2h 15m

Notes: 12 entries
  Notes File: $DEVAIFLOW_HOME/sessions/implement-backup-feature/notes.md
```

**Output (--uuid-only):**
```
f545206f-480f-4c2d-8823-c6643f0e693d
```

**Use Cases:**

*Troubleshooting corrupted sessions:*
```bash
# Find session UUID and conversation file location
daf info PROJ-60039
# Inspect or repair the conversation file
```

*Scripting workflows:*
```bash
# Get UUID and use with repair tools
UUID=$(daf info PROJ-60039 --uuid-only)
daf maintenance repair-conversation $UUID

# Open conversation file directly
cat ~/.claude/projects/*/$(daf info PROJ-60039 --uuid-only).jsonl | jq
```

*Multi-repository sessions:*
```bash
# View all conversations in a session
daf info PROJ-60039

# Get UUID of specific conversation
daf info PROJ-60039 --conversation-id 2 --uuid-only
```

**Exit Codes:**
- `0` - Session information displayed successfully
- `1` - Session not found or invalid conversation ID

---

### daf sessions list - View Conversation History (REMOVED)

**This command has been removed.** Use `daf list` instead.

The deprecated `daf sessions` command group has been removed to simplify the CLI. All functionality is available through `daf list`.

**Migration:**
```bash
# Old (removed)
daf sessions list PROJ-12345

# New (use this instead)
daf list PROJ-12345
```

**Output:**
```
Session: PROJ-12345
Conversations (2 repositories):

#1 backend-api (active)
  Claude Session: a7b3c4d5-1234-...
  Branch: feature/PROJ-12345
  Messages: 45
  Created: 2026-01-15 09:30
  Last Active: 2026-01-21 14:30

  Archived (1):
    UUID: f8e9d0a1-5678-...
    Summary: Initial implementation of user auth
    Messages: 123
    Created: 2026-01-10 10:00
    Archived: 2026-01-15 09:30

#2 frontend-app (active)
  Claude Session: b8c4d5e6-2345-...
  Branch: feature/PROJ-12345-ui
  Messages: 28
  Created: 2026-01-18 11:00
  Last Active: 2026-01-20 16:45
```

**Use Cases:**

*Review conversation history:*
- See what approaches were tried before
- Understand progression of work across multiple fresh starts
- Verify archived conversation history is preserved

*Understand multi-session structure:*
- Each conversation can have multiple Claude Code sessions (active + archived)
- Archived sessions preserve full conversation history with summaries
- Use `daf open --new-conversation` to archive current and start fresh

---

### daf session add-project - Add Project to Session

Add one or more projects (repositories) to an existing session.

```bash
daf session add-project <SESSION> <PROJECT> -w <WORKSPACE> [OPTIONS]
daf session add-project <SESSION> --projects <PROJ1,PROJ2,...> -w <WORKSPACE> [OPTIONS]
```

**Options:**
- `-w, --workspace WORKSPACE` - Workspace containing the projects (required)
- `--projects PROJECTS` - Comma-separated list of projects (alternative to single project)
- `--branch BRANCH` - Shared branch name for all projects (optional, will prompt if not provided)

**Examples:**
```bash
# Add single project to session
daf session add-project PROJ-12345 backend-api -w primary

# Add multiple projects at once
daf session add-project PROJ-12345 --projects frontend,docs,mobile -w primary

# Add project with specific branch name
daf session add-project PROJ-12345 backend-api -w primary --branch feature/api-v2
```

**What happens:**
1. Validates workspace and project paths exist
2. Prompts for branch name once (if not provided via `--branch`)
3. Sets up git branches in each project repository
4. Creates new conversation for each project
5. Shows `[project-name]` prefix in all prompts for clarity
6. Skips projects that already have conversations in the session

**Use cases:**
- Started with one project, need to add more later
- Session scope expanded to include additional repositories
- Adding frontend after starting with backend-only session

---

### daf session remove-project - Remove Project from Session

Remove a project (conversation) from an existing session.

```bash
daf session remove-project <SESSION> <PROJECT> [OPTIONS]
```

**Options:**
- `--force` - Skip confirmation prompt

**Examples:**
```bash
# Remove project (with confirmation)
daf session remove-project PROJ-12345 old-service

# Remove without confirmation
daf session remove-project PROJ-12345 legacy-api --force
```

**What happens:**
1. Shows project details (branch, path, message count)
2. Prompts for confirmation (unless `--force`)
3. Removes the conversation from the session
4. Auto-switches active conversation if removing current project
5. Shows list of remaining projects

**Use cases:**
- Project no longer needed for this ticket
- Cleaning up old/deprecated services
- Narrowing session scope

---

## Time Tracking

### daf time - View Time Tracking

Display time tracking information for a session.

```bash
daf time <NAME-or-JIRA>
```

**Output:**
```
Time Tracking for: PROJ-12345

Work Sessions:
  Session #1 (backend-api):
    1. 2025-11-20 09:00:00 → 11:30:00  (2h 30m)
    2. 2025-11-20 14:00:00 → 15:15:00  (1h 15m)
    3. (active) 16:00:00 → now         (1h 00m)

Total Time: 4h 45m
Status: in_progress
Sprint: 2025-01
```

---

### daf pause / daf resume - Control Time Tracking

Pause or resume time tracking for a session.

```bash
daf pause <NAME-or-JIRA>
daf resume <NAME-or-JIRA>
```

**Examples:**
```bash
# Pause (taking a break)
daf pause PROJ-12345

# Resume (back to work)
daf resume PROJ-12345
```

**Use cases:**
- Taking breaks without closing Claude Code
- Switching to different task temporarily
- Manual time tracking control

---

## Backup and Export

### daf export - Export Sessions

Export complete session(s) for team handoff.

**Always includes:**
- Session metadata and **session notes** (notes.md) - preserves work history across team handoffs (PROJ-60697)
- **ALL conversations** (all projects) - one session = one JIRA ticket
- **ALL conversation history** (.jsonl files)
- Git branch sync for all conversations

**Excluded for portability (AAP-63987):**
- `workspace_name` - Machine-specific configuration, not portable across team members

**Note:** Diagnostic logs are NOT included in exports (PROJ-60802). These are global system logs containing information from ALL sessions and would leak sensitive data about other tickets. For full system backups with diagnostic logs, use `daf backup` instead.

```bash
daf export <NAME-or-JIRA>... [OPTIONS]
```

**Options:**
- `--output <PATH>` - Custom output path
- `--all` - Export all sessions

**Examples:**
```bash
# Export single session (includes ALL conversations)
daf export PROJ-12345

# Export multiple sessions
daf export PROJ-12345 PROJ-12346 PROJ-12347

# Export all sessions
daf export --all --output ~/backup.tar.gz

# Custom output path
daf export PROJ-12345 --output ~/session-handoff.tar.gz
```

**Why conversations are always included:**
- Each session represents **one JIRA ticket**
- A JIRA ticket has **one assignee** at a time
- When handing off work, the teammate needs **complete context** across all repositories
- Exporting without conversations would be incomplete handoff

**Multi-Conversation Sessions:**
When exporting a session with multiple conversations (e.g., PROJ-12345 with both backend and frontend work):
- **ALL conversations are exported** (one session export includes all project conversations)
- Each conversation's git branch is automatically synced before export (PROJ-60772)
- Teammate gets complete context for the entire JIRA ticket

**Automatic Git Branch Synchronization (PROJ-60772):**
Before creating the export, `daf export` automatically:
1. **Checks out the session branch** - Ensures you're on the correct branch
2. **Fetches from origin** - Gets latest remote changes
3. **Pulls latest changes** - Merges teammate's updates (if branch exists on remote)
4. **Commits all changes** - Creates WIP commit (NO prompt, REQUIRED)
5. **Pushes to remote** - Makes branch available to teammate (NO prompt, REQUIRED)

These operations are **REQUIRED** for successful export. Export will fail with clear errors if:
- Cannot checkout branch (e.g., branch doesn't exist)
- Merge conflicts occur during pull (must resolve before export)
- Cannot commit changes (e.g., git error)
- Cannot push to remote (e.g., no permissions, network issue)

**Example Multi-Project Export:**
```bash
daf export PROJ-12345

# Output shows automatic sync for ALL conversations:
Syncing 2 conversation(s) for PROJ-12345

→ backend-api (branch: feature/PROJ-12345)
Checking out branch feature/PROJ-12345...
✓ Checked out feature/PROJ-12345
Fetching latest from origin...
Pulling latest changes...
✓ Branch up to date with remote
⚠ Uncommitted changes detected:
  M file1.py
  M file2.py
Committing all changes for export...
✓ Committed all changes
Pushing latest commits to remote...
✓ Branch synced with remote

→ frontend-app (branch: feature/PROJ-12345-ui)
Fetching latest from origin...
Branch 'feature/PROJ-12345-ui' is not on remote
Pushing feature/PROJ-12345-ui to origin...
✓ Pushed branch to origin

✓ Export created successfully
```

**Why this matters for JIRA ticket handoff:**
- One JIRA ticket = One session = One export (regardless of how many projects)
- Teammate gets all work across all repositories
- All git branches are automatically committed and pushed (no manual intervention)
- Nothing is left behind
- Export fails early if git operations fail (prevents incomplete handoffs)

**Archive Type Protection:**
Export archives contain a metadata marker (`"archive_type": "export"`) that prevents them from being used with `daf restore` (which expects backup files). Use `daf import` to import export files.

**Troubleshooting Export Failures:**

If export fails, you'll see clear error messages explaining what went wrong and how to resolve:

1. **Cannot checkout branch**:
   ```
   ValueError: Cannot checkout branch 'feature/PROJ-12345' in backend-api
   ```
   **Resolution**: Ensure branch exists. Check if you have uncommitted changes preventing checkout.

2. **Merge conflicts during pull**:
   ```
   ValueError: Merge conflicts in backend-api:
     file1.py, file2.py
   Resolve conflicts and try export again.
   ```
   **Resolution**:
   ```bash
   cd backend-api
   git checkout feature/PROJ-12345
   # Resolve conflicts in listed files
   git add .
   git commit -m "Resolve merge conflicts"
   # Try export again
   daf export PROJ-12345
   ```

3. **Failed to commit changes**:
   ```
   ValueError: Failed to commit changes in backend-api
   Cannot export without committing all changes.
   ```
   **Resolution**: Check git status for errors. Ensure git is configured properly (`git config user.name`, `git config user.email`).

4. **Failed to push to remote**:
   ```
   ValueError: Failed to push branch 'feature/PROJ-12345' to remote
   Teammate needs branch on remote to import session.
   Common causes: No remote configured, no push permissions, network issues
   ```
   **Resolution**:
   ```bash
   # Check remote configuration
   cd backend-api
   git remote -v

   # If no remote, add one
   git remote add origin <URL>

   # Check network and permissions
   git push -u origin feature/PROJ-12345
   ```

5. **Multi-conversation export fails if ANY conversation fails**:
   - Export is atomic: if any conversation's branch sync fails, entire export fails
   - This prevents partial/incomplete handoffs
   - Fix the failing conversation and retry export

---

### daf import - Import Sessions

Import sessions from export file.

```bash
daf import <FILE> [OPTIONS]
```

**Options:**
- `--replace` - Replace conflicting sessions
- `--force` - Skip confirmation
- `--merge` - Merge with existing (default)

**Examples:**
```bash
# Import and merge
daf import ~/session-handoff.tar.gz

# Import and replace conflicts
daf import ~/session-handoff.tar.gz --replace

# Import without confirmation
daf import ~/backup.tar.gz --force
```

**Team Handoff Workflow:**

When importing a session exported by a teammate:
1. Import extracts session metadata, **session notes**, and **ALL conversation histories** (PROJ-60697)
   - Session notes (notes.md) are fully preserved, allowing you to see all previous work notes
   - You can continue adding notes after import using `daf note` command
2. **Diagnostic logs are restored** to `$DEVAIFLOW_HOME/logs/imported/{timestamp}/` (PROJ-60657)
   - Logs are namespaced with a timestamp to avoid conflicts with your current logs
   - This preserves diagnostic history for debugging any issues from the exported session
3. **Workspace selection happens on first open** (AAP-63987):
   - Imported sessions have no `workspace_name` (excluded for portability)
   - When you run `daf open`, workspace is selected using standard priority: `--workspace` flag > default workspace > interactive prompt
   - After first open, session remembers your workspace choice for future opens
4. Run `daf open <SESSION>` to select which conversation to work on
5. Tool automatically syncs git branch for the selected conversation (PROJ-61023, AAP-65177):
   - **If branch doesn't exist locally**: Automatically fetches and checks out from remote (no prompt to create)
   - **If branch exists locally but is behind**: Prompts to merge, rebase, or skip sync
   - **If merge conflicts occur**: Aborts operation with clear resolution instructions
   - Only prompts to create new branch if it doesn't exist on remote either
6. Continue work where teammate left off, with full context from their notes

**Multi-Conversation Import Example:**
```bash
daf import ~/PROJ-12345-export.tar.gz

✓ Imported session: PROJ-12345
  - 2 conversations imported:
    • backend-api (branch: feature/PROJ-12345)
    • frontend-app (branch: feature/PROJ-12345-ui)

daf open PROJ-12345

Found 2 conversation(s) for PROJ-12345:

  1. backend-api
     Path: /workspace/backend-api
     Branch: feature/PROJ-12345
     Last active: 2h ago

  2. frontend-app
     Path: /workspace/frontend-app
     Branch: feature/PROJ-12345-ui
     Last active: 1h ago

Which conversation? [1-2]: 1

# Branch feature/PROJ-12345 synced automatically...
# Continue working in backend-api
```

**Important for multi-project sessions:**
- Import restores **all conversations** for the session
- Each conversation has its own git repository and branch
- Use `daf open` to select which project to work on
- All conversation history is preserved

**Archive Type Validation:**

The import command validates that the provided file is an export archive (not a backup). If you try to import a backup file created with `daf backup`, you'll get an error:

```
This is a backup archive created by 'daf backup'.
Use 'daf restore' to restore backup files.
For team handoff, use 'daf export' instead.
```

This prevents accidentally using the wrong command and ensures you're using the correct workflow for team collaboration (export/import with git sync) vs personal disaster recovery (backup/restore).

**Example team handoff:**
```bash
# Teammate A exports and attaches to JIRA
daf complete PROJ-12345 --attach-to-issue
# → Commits changes, pushes branch, exports session

# Download export from JIRA ticket
# Teammate B imports
daf import PROJ-12345-20251201-143000.tar.gz

# Open session (automatic branch sync)
daf open PROJ-12345
# → Fetches branch from remote
# → Checks out teammate's branch
# → Merges any remote changes
# → Ready to continue work
```

**Fork Support for Cross-Organization Collaboration:**

The export/import workflow supports collaboration across different forks (e.g., when teammates work in different GitHub/GitLab organizations):

**Git Remote Conventions:**

The tool follows standard git remote naming conventions:
- **`origin`** - Your primary remote (typically your fork)
- **`upstream`** - The parent repository (where PRs/MRs are created)
- **`<teammate>`** - Additional remotes for collaborator forks (e.g., `alice`, `bob`)

⚠️ **Important**: These are conventions, not requirements. If your git setup uses different remote names, the tool will prompt you to specify which remote is which.

**Scenario:**
- Alice works in fork: `https://github.com/alice/repo.git` (Alice's `origin`)
- Bob works in fork: `https://github.com/bob/repo.git` (Bob's `origin`)
- They're different forks, but working on the same JIRA ticket

**How it works:**

1. **Export captures remote URL** - When Alice exports, the tool captures the remote URL where each branch was pushed
2. **Import detects fork differences** - When Bob imports, the tool compares remote URLs
3. **Automatic remote management** - If the remote URLs differ (different forks), Bob is prompted to add Alice's fork as a new remote
4. **Custom remote name support** - If Bob's repository doesn't have `origin`, the tool will prompt for the correct remote name

**Fork Import Example:**
```bash
# Bob imports Alice's session export
daf import ~/PROJ-12345-alice-export.tar.gz
daf open PROJ-12345

Syncing branch for imported session...

⚠ This branch is from a different fork: https://github.com/alice/repo.git
Your origin: https://github.com/bob/repo.git

Add remote 'alice' for this fork? [Y/n]: y
✓ Added remote 'alice': https://github.com/alice/repo.git

Fetching latest from alice...
✓ Fetched and checked out branch: feature/PROJ-12345

# Bob now has:
# - Local branch tracking alice/feature/PROJ-12345
# - Can fetch Alice's updates from 'alice' remote
# - Can push his own changes to 'origin' (his fork)
```

**Benefits:**
- **Seamless fork collaboration** - No manual remote setup required
- **Automatic remote detection** - Tool detects and handles different fork URLs
- **Preserves remote references** - Each conversation remembers where its branch originated
- **Works across organizations** - Supports GitHub, GitLab, and any git hosting

**Remote management:**
- Remote name is auto-suggested from fork URL (e.g., "alice" from alice/repo)
- You can customize the remote name during import
- Existing remotes are reused if they match the fork URL
- All subsequent `daf open` commands will fetch from the correct remote

**Example with custom remote names:**
```bash
# Bob's repository uses 'my-fork' instead of 'origin'
git remote -v
# my-fork      https://github.com/bob/repo.git (fetch)
# upstream     https://github.com/upstream-org/repo.git (fetch)

daf open PROJ-12345

Syncing branch for imported session...

No 'origin' remote found
Available remotes:
  - my-fork: https://github.com/bob/repo.git
  - upstream: https://github.com/upstream-org/repo.git

Which remote should be used as your primary remote?
Common convention: 'origin' points to your fork or main repository
Primary remote name [my-fork]: my-fork

⚠ This branch is from a different fork: https://github.com/alice/repo.git
Your origin: https://github.com/bob/repo.git

Add remote 'alice' for this fork? [Y/n]: y
✓ Added remote 'alice': https://github.com/alice/repo.git
✓ Fetched and checked out branch: feature/PROJ-12345
```

---

### daf backup - Complete System Backup

Create complete backup of all sessions and conversations.

```bash
daf backup [--output <PATH>]
```

**Examples:**
```bash
# Backup to default location
daf backup

# Backup to specific location
daf backup --output ~/backups/cs-backup-20251120.tar.gz
```

**What's included:**
- ALL sessions (metadata, notes, data)
- ALL conversation history (.jsonl files)
- Session index (sessions.json)
- All session directories
- **Diagnostic logs** ($DEVAIFLOW_HOME/logs/) - for debugging (PROJ-60657)

**Backup vs Export - Key Differences:**

| Aspect | daf backup | daf export |
|--------|-----------|-----------|
| **Purpose** | Personal disaster recovery | Team collaboration (JIRA handoff) |
| **Scope** | ALL sessions (always) | Specific session(s) |
| **Git Sync** | ❌ None (as-is snapshot) | ✅ Commits + pushes ALL branches |
| **Conversations** | ✅ Always included | ✅ Always included (1 ticket = all work) |
| **Diagnostic Logs** | ✅ Included (full system state) | ❌ Excluded (privacy/security) |
| **Use When** | "Save my work state" | "Hand off JIRA ticket to teammate" |

**When to use backup:**
- Regular personal backups (weekly, before major changes)
- Disaster recovery (computer crash, accidental deletion)
- Moving to new machine (backup old, restore on new)
- Preserving exact state including uncommitted changes

**When to use export:**
- Handing off JIRA ticket to teammate
- Sharing specific session with collaborator
- Attaching work to JIRA ticket for review
- Any scenario requiring git branch sync

**Archive Type Protection:**
Backup archives contain a metadata marker (`"archive_type": "backup"`) that prevents them from being used with `daf import` (which expects export files). Use `daf restore` to restore backup files.

---

### daf restore - Restore from Backup

Restore complete system from backup.

```bash
daf restore <FILE> [OPTIONS]
```

**Options:**
- `--merge` - Merge with existing sessions
- `--force` - Skip confirmation

**Examples:**
```bash
# Restore (replaces everything - prompts for confirmation)
daf restore ~/backup.tar.gz

# Restore and merge
daf restore ~/backup.tar.gz --merge

# Restore without confirmation
daf restore ~/backup.tar.gz --force
```

**Diagnostic Logs Restoration:**

When restoring from a backup:
- **Diagnostic logs are restored** to `$DEVAIFLOW_HOME/logs/imported/{timestamp}/` (PROJ-60657)
- Logs are namespaced with a timestamp to avoid conflicts with your current logs
- This preserves diagnostic history for debugging

**Archive Type Validation:**

The restore command validates that the provided file is a backup archive (not an export). If you try to restore an export file created with `daf export`, you'll get an error:

```
This is an export archive created by 'daf export'.
Use 'daf import' to import exported sessions.
For complete system backup, use 'daf backup' instead.
```

This prevents accidentally using the wrong command and ensures you're using the correct workflow for team collaboration (export/import) vs personal disaster recovery (backup/restore).

---

### daf export-md - Export to Markdown

Export session(s) to Markdown documentation.

```bash
daf export-md <NAME-or-JIRA>... [OPTIONS]
```

**Options:**
- `--output-dir <DIR>` - Output directory (default: current directory)
- `--ai-summary` - Use AI-powered summary
- `--combined` - Export to single file
- `--no-activity` - Exclude activity summary
- `--no-statistics` - Exclude detailed statistics

**Examples:**
```bash
# Export single session
daf export-md PROJ-12345

# Export multiple sessions
daf export-md PROJ-12345 PROJ-12346

# Export to specific directory
daf export-md PROJ-12345 --output-dir ./docs

# Export with AI summary
daf export-md PROJ-12345 --ai-summary

# Export multiple to single file
daf export-md PROJ-12345 PROJ-12346 --combined
```

**Use cases:**
- Create handoff documents
- Generate sprint reports
- Document completed work
- Share knowledge with team

---

## Maintenance Commands

### daf release - Create New Release

**⚠️ Maintainer/Owner Only**: This command requires Maintainer (GitLab 40) or Owner (GitLab 50) access, or "maintain"/"admin" permission on GitHub.

Automates the mechanical parts of creating a new release (minor, major, or patch) following the process documented in RELEASING.md.

```bash
daf release VERSION [OPTIONS]
```

**Arguments:**
- `VERSION` - Target version (e.g., `0.2.0`, `1.0.0`, `0.1.1`)

**Options:**
- `--suggest` - Analyze commits and suggest release type (no version needed)
- `--from TAG` - Base tag for patches (e.g., `--from v0.1.0`)
- `--dry-run` - Preview changes without executing
- `--auto-push` - Push to remote without confirmation (use with caution)
- `--force` - Force release even if tests fail (emergency use only)

**Examples:**
```bash
# Get suggestion first (recommended)
daf release --suggest

# Minor release (auto-detects from version numbers)
daf release 0.2.0

# Major release
daf release 1.0.0

# Patch release from specific tag
daf release 0.1.1 --from v0.1.0

# Preview what would happen
daf release 0.2.0 --dry-run

# Emergency release (bypass test failure prompts)
daf release 0.2.0 --force
```

**What it does:**
1. ✅ Checks release permissions (Maintainer/Owner only)
2. ✅ Creates appropriate branch (`release/X.Y` or `hotfix/X.Y.Z`)
3. ✅ Updates version in `cs/__init__.py` and `setup.py`
4. ✅ Updates `CHANGELOG.md` with new version section
5. ✅ Commits version bump with professional message
6. ✅ Runs complete unit test suite (blocks if failed)
7. ✅ Runs integration tests (prompts if failed)
8. ✅ Creates annotated git tag (`vX.Y.Z`)
9. ✅ Bumps to next dev version on release branch
10. ✅ Shows summary with next steps

**What it does NOT do:**
- ❌ Fix bugs (you fix bugs before running command)
- ❌ Push to remote (you review first, then push manually)
- ❌ Create GitLab/GitHub releases (done separately via UI/CLI)
- ❌ Merge back to main (done manually after review)

**Release Type Auto-Detection:**
- **Minor**: `0.1.x-dev` → `0.2.0` (minor version bump)
- **Major**: `0.x.x` → `1.0.0` (major version bump)
- **Patch**: `0.1.0` → `0.1.1` (patch version bump)

**Security Features:**
- Cross-platform permission checking (GitLab & GitHub)
- Cannot run from inside Claude Code sessions
- Validates version file synchronization
- Checks for uncommitted changes
- Confirmation prompts before execution

**Integration Tests:**
- Automatically runs all integration tests:
  - `integration-tests/test_collaboration_workflow.sh`
  - `integration-tests/test_jira_green_path.sh`
- If tests fail, prompts user to continue or abort
- Use `--force` to bypass prompts (emergency only)

**See Also:**
- [RELEASING.md](../RELEASING.md) - Complete technical release process
- [docs/08-release-management.md](../developer/release-management.md) - Release management guide
- [CHANGELOG.md](../CHANGELOG.md) - Version history

---

## Maintenance Commands

The `daf maintenance` command group contains repair and cleanup utilities for advanced troubleshooting. These commands are hidden from the main help to reduce clutter but remain fully functional.

```bash
daf maintenance --help
```

**Available maintenance commands:**
- `daf maintenance cleanup-conversation` - Clean conversation history to reduce context size
- `daf maintenance cleanup-sessions` - Fix orphaned sessions with missing conversation files
- `daf maintenance discover` - Discover existing Claude Code sessions not managed by daf
- `daf maintenance rebuild-index` - Rebuild sessions.json index from session directories
- `daf maintenance repair-conversation` - Repair corrupted conversation files

**Backward compatibility:** All commands are still accessible via their original names (e.g., `daf maintenance repair-conversation`) but these are hidden from `daf --help`. Use `daf maintenance <command>` for consistency.

---

### daf maintenance repair-conversation - Repair Corrupted Conversations

**Also available as:** `daf maintenance repair-conversation` (hidden)

Repair corrupted Claude Code conversation files by fixing JSON errors, removing invalid surrogates, and truncating oversized content.

```bash
daf maintenance repair-conversation [IDENTIFIER] [OPTIONS]
```

**Identifier Types:**
- Session name (e.g., `implement-backup-feature`)
- JIRA key (e.g., `PROJ-60039`)
- Claude UUID (e.g., `f545206f-480f-4c2d-8823-c6643f0e693d`)

**Options:**
- `--conversation-id <N>` - Repair specific conversation by number (1, 2, 3...)
- `--max-size <SIZE>` - Maximum size for content truncation (default: 10000 chars)
- `--check-all` - Check all sessions for corruption (dry run)
- `--all` - Repair all corrupted sessions found
- `--dry-run` - Report issues without making changes

**Examples:**
```bash
# Repair by JIRA key
daf maintenance repair-conversation PROJ-60039

# Repair by session name
daf maintenance repair-conversation my-session

# Repair by UUID (useful when session metadata is missing)
daf maintenance repair-conversation f545206f-480f-4c2d-8823-c6643f0e693d

# Repair specific conversation in multi-conversation session
daf maintenance repair-conversation PROJ-60039 --conversation-id 1

# Check all sessions for corruption (dry run)
daf maintenance repair-conversation --check-all

# Repair all corrupted sessions automatically
daf maintenance repair-conversation --all

# Custom truncation size (increase if needed)
daf maintenance repair-conversation PROJ-60039 --max-size 15000

# Preview changes without modifying file
daf maintenance repair-conversation PROJ-60039 --dry-run
```

**What it repairs:**
- **Invalid JSON lines** - Fixes or skips lines with JSON syntax errors
- **Unicode surrogates** - Removes invalid surrogate pairs that cause encoding errors
- **Oversized content** - Truncates large tool results/outputs to configurable size
- **Validates repair** - Ensures repaired file is valid JSON

**Repair process:**
1. **Detects corruption** - Scans for invalid JSON, surrogates, and oversized content
2. **Creates backup** - Automatically creates `.jsonl.backup-TIMESTAMP` file
3. **Repairs file** - Fixes issues while preserving valid content
4. **Reports results** - Shows what was fixed (line numbers, truncation stats)

**When to use:**
- Claude Code session crashes or freezes
- Error messages about corrupted conversation files
- Unable to resume a session
- Session file contains invalid JSON
- Tool results are excessively large and causing issues

**Important notes:**
- **Automatic backups** created before any repair (`.jsonl.backup-TIMESTAMP`)
- **Restart required** - Must restart Claude Code for changes to take effect
- **UUID fallback** - Can repair even when session metadata is corrupted
- **Safe operation** - Original file is backed up, restore possible if needed

**Output example:**
```
Found session: implement-backup-feature (PROJ-60039)
  2 conversations found

Repairing conversation #1 (f545206f-480f-4c2d-8823-c6643f0e693d):
File: ~/.claude/projects/-Users-...-project/f545206f-480f-4c2d-8823.jsonl
⚠ Corruption detected:
  - Found 1 lines with content exceeding 10KB

Content requiring truncation:
  Line 119: tool_result (24,279 chars)

✓ Repaired 1 line(s)
Backup created: f545206f-480f-4c2d-8823.jsonl.backup-20251205-150000
Truncated 1 content block(s):
  Line 119: 24,279 → 10,050 chars

Validated 199 lines

All conversations processed
```

---

### daf maintenance cleanup-conversation - Clean Conversation History

**Also available as:** `daf maintenance cleanup-conversation` (hidden)

Clean up Claude Code conversation history to reduce size and avoid 413 errors.

**CRITICAL:** Must run OUTSIDE of Claude Code (after exiting).

```bash
daf maintenance cleanup-conversation <NAME-or-JIRA> [OPTIONS]
```

**Options:**
- `--older-than <DURATION>` - Remove messages older than duration (e.g., "2h", "1d")
- `--keep-last <N>` - Keep only last N messages
- `--dry-run` - Preview changes without applying
- `--force` - Skip confirmation
- `--list-backups` - List all available backups
- `--restore-backup <TIMESTAMP>` - Restore from backup

**Examples:**
```bash
# Clean messages older than 8 hours
daf maintenance cleanup-conversation PROJ-12345 --older-than 8h

# Keep only last 100 messages
daf maintenance cleanup-conversation PROJ-12345 --keep-last 100

# Preview what would be cleaned
daf maintenance cleanup-conversation PROJ-12345 --older-than 1d --dry-run

# Clean without confirmation
daf maintenance cleanup-conversation PROJ-12345 --older-than 8h --force

# List all backups
daf maintenance cleanup-conversation PROJ-12345 --list-backups

# Restore from specific backup
daf maintenance cleanup-conversation PROJ-12345 --restore-backup 20251120-163147
```

**Critical workflow:**
1. **Exit Claude Code** completely (close session)
2. **Run cleanup** from terminal
3. **Reopen session** with `daf open`

**When to use:**
- "413 Prompt is too long" errors
- Long-running sessions with many messages
- To optimize Claude Code performance

**Backup management:**
- Automatic backup before each cleanup
- Keeps last 5 backups per session
- Restore capability from any backup
- Safe restore (backs up current before restoring)

---

### daf maintenance cleanup-sessions - Fix Orphaned Sessions

**Also available as:** `daf maintenance cleanup-sessions` (hidden)

Find and fix sessions with missing conversation files.

```bash
daf maintenance cleanup-sessions [OPTIONS]
```

**Options:**
- `--dry-run` - Preview what would be cleaned
- `--force` - Skip confirmation

**Examples:**
```bash
# Preview orphaned sessions
daf maintenance cleanup-sessions --dry-run

# Clean with confirmation
daf maintenance cleanup-sessions

# Clean without confirmation
daf maintenance cleanup-sessions --force
```

**What it does:**
1. Scans all sessions for orphaned UUIDs
2. Checks if conversation files exist
3. Clears orphaned UUIDs from metadata
4. Next `daf open` generates new UUIDs

**When to use:**
- After session creation interrupted
- After Claude Code crash
- Periodic database cleanup

---

### daf purge-mock-data - Clear Mock Data (Hidden)

**Hidden developer utility** - This command is hidden from `daf --help` but still available for developers and automated testing.

```bash
daf purge-mock-data [OPTIONS]
```

**Options:**
- `--force` - Skip confirmation prompt

**Examples:**
```bash
# Purge with confirmation
daf purge-mock-data

# Purge without confirmation
daf purge-mock-data --force

# Alternative: manually delete mock data directory
rm -rf $DEVAIFLOW_HOME/mocks/
```

**What it clears:**
- Mock sessions (`$DEVAIFLOW_HOME/mocks/sessions.json`)
- Mock JIRA tickets, comments, transitions
- Mock GitHub pull requests
- Mock GitLab merge requests
- Mock Claude Code sessions

**Safety features:**
- Shows clear warning about what will be deleted
- Requires confirmation unless `--force` is used
- Never affects real production data (separate storage location)

**When to use:**
- Start fresh with integration testing
- Clear test data between test runs
- Reset mock environment for demos
- Clean up after development work

**Note:** This command is hidden from the main command list to reduce CLI complexity. It's specifically for development and testing, and has no effect on production sessions or data. You can also manually delete the `$DEVAIFLOW_HOME/mocks/` directory to achieve the same result.

---

## Utility Commands

### daf init --check - Check Dependencies

Verify that all required and optional external tools are installed and available.

```bash
daf init --check [OPTIONS]
```

**Options:**
- `--json` - Output in JSON format for automation

**Examples:**
```bash
# Check all dependencies
daf init --check

# JSON output for scripting
daf init --check --json
```

**What it checks:**
- **Required tools:**
  - `git` - Git version control (for branch management, commits)
  - `claude` - Claude Code CLI (for session launching)
- **Optional tools:**
  - `gh` - GitHub CLI (for PR creation)
  - `glab` - GitLab CLI (for MR creation)
  - `pytest` - Python testing (for running unit tests)

**Output example:**
```
Checking dependencies for DevAIFlow...

Required Dependencies:
┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Tool   ┃ Status ┃ Version         ┃ Description          ┃
┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ git    │ ✓      │ git version ... │ Git version control  │
│ claude │ ✓      │ claude 1.2.3    │ Claude Code CLI      │
└────────┴────────┴─────────────────┴──────────────────────┘

Optional Dependencies:
┏━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Tool  ┃ Status ┃ Version       ┃ Description               ┃
┡━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ gh    │ ✓      │ gh 2.40.1     │ GitHub CLI                │
│ glab  │ ✗      │               │ GitLab CLI                │
│       │        │               │ Install: https://...      │
│ pytest│ ✓      │ pytest 7.4.3  │ Python testing framework  │
└───────┴────────┴───────────────┴───────────────────────────┘

✓ All required dependencies available
⚠ Some optional features unavailable: glab
```

**Exit codes:**
- `0` - All required dependencies available
- `1` - One or more required dependencies missing

**When to use:**
- After installing daf tool (verify setup)
- When encountering dependency errors
- Before running operations that require external tools
- In CI/CD pipelines to verify environment

**Just-in-time dependency checking:**

The daf tool automatically checks for required tools when needed:
- `git` - Checked before branch creation, commits, and push operations
- `claude` - Checked before launching or resuming Claude Code sessions
- `gh` - Checked before GitHub PR creation (graceful failure with instructions)
- `glab` - Checked before GitLab MR creation (graceful failure with instructions)

If a required tool is missing, you'll see a clear error message with installation instructions.

---

### daf search - Search Sessions

Search sessions by keyword, tags, or working directory.

```bash
daf search <QUERY> [OPTIONS]
```

**Options:**
- `--tag <TAG>` - Search by tag
- `--working-directory <DIR>` - Filter by repository

**Examples:**
```bash
# Search by keyword
daf search "backup"

# Search by tag
daf search --tag documentation

# Search in specific repository
daf search "api" --working-directory backend-api
```

---

### daf maintenance discover - Discover Existing Sessions

**Also available as:** `daf maintenance discover` (hidden)

Find existing Claude Code sessions not managed by daf tool.

```bash
daf maintenance discover
```

**Output:**
```
Unmanaged Claude Sessions (3):

UUID                                  Project               Messages  Last Active
7a0bca58-c6c6-4b02-8fbf-9c223cd52a57 backend-api           45        2025-11-19
3d8f2e1a-9b7c-4f5e-a2d6-1c8e9f0a3b2c frontend-app          23        2025-11-18
...

Use 'daf import-session <UUID>' to manage these sessions.

Managed Sessions (5):
...
```

---

### daf import-session - Import Existing Session

Import a discovered session into daf tool.

```bash
daf import-session <UUID> [OPTIONS]
```

**Options:**
- `--jira <KEY>` - Link to JIRA ticket
- `--goal <GOAL>` - Session goal (auto-detection of file:// paths and http(s):// URLs)
- `--goal-file <PATH|URL>` - Explicit file path or URL for goal input (mutually exclusive with `--goal`)
- `--name <NAME>` - Session name

**Examples:**
```bash
# Interactive import
daf import-session 7a0bca58-c6c6-4b02-8fbf-9c223cd52a57

# Non-interactive import with plain text goal
daf import-session 7a0bca58... --jira PROJ-12345 --goal "Feature work"

# Non-interactive import with goal from file
daf import-session 7a0bca58... --jira PROJ-12345 --goal-file "requirements.md"

# Non-interactive import with goal from URL
daf import-session 7a0bca58... --jira PROJ-12345 --goal-file "https://docs.example.com/spec.txt"
```

**Workflow:**
1. Run `daf maintenance discover` to find sessions
2. Copy UUID of session you want
3. Run `daf import-session <UUID>`
4. Follow prompts to set name, goal, JIRA link

---

### daf template - Manage Templates

Save and reuse session configurations.

```bash
daf template save <NAME> <TEMPLATE-NAME>
daf template list
daf template show <TEMPLATE-NAME>
daf template delete <TEMPLATE-NAME>
```

**Examples:**
```bash
# Save session as template
daf template save backend-api my-backend-template

# List all templates
daf template list

# Show template details
daf template show my-backend-template

# Delete template
daf template delete my-backend-template

# Use template when creating session
daf new --name "new-api" --goal "Build endpoint" --template my-backend-template
```

**What gets saved:**
- Working directory pattern
- Git branch pattern
- JIRA key pattern
- Tags

---

### daf update - Update Session Metadata

Update session metadata fields via CLI.

```bash
daf update <NAME-or-JIRA> [OPTIONS]
```

**Options:**
- `--goal <GOAL>` - Update goal
- `--status <STATUS>` - Update status
- `--working-directory <DIR>` - Update repository
- `--project-path <PATH>` - Update path
- `--branch <BRANCH>` - Update git branch

**Example:**
```bash
daf update PROJ-12345 --goal "Updated goal description"
```

---

### daf open --edit - Edit Session Metadata Interactively

Launch an interactive TUI (Text User Interface) to edit session metadata, manage conversations, and update JIRA integration settings.

```bash
daf open --edit <NAME-or-JIRA>
```

**What it does:**
- Opens an interactive terminal UI for session editing
- Provides tabbed interface for different metadata sections
- Validates input before saving
- Creates automatic backups before changes
- Supports multi-conversation management

**Features:**

**Core Metadata Tab:**
- Edit session goal and description
- Change session type (development, ticket_creation)
- Update session status
- View read-only fields (name, session ID, creation date)

**Conversations Tab:**
- View all conversations for the session
- Add new conversations (for multi-repository work)
- Edit conversation details (UUID, path, branch)
- Remove conversations
- Manage per-conversation settings

**JIRA Integration Tab:**
- Update JIRA key association
- View JIRA sync status

**Time Tracking Tab:**
- View work sessions summary
- Toggle time tracking state
- See time breakdown by user

**Examples:**
```bash
# Edit by JIRA key
daf open --edit PROJ-60989

# Edit by session name
daf open --edit my-feature-session

# Edit most recent session
daf list  # Get session name
daf open --edit <session-name>
```

**Keyboard Shortcuts:**
- `Tab` / `Shift+Tab` - Navigate between fields
- `Arrow Keys` - Navigate tabs and fields
- `Enter` - Activate button/select
- `Escape` - Cancel/close modals
- `Ctrl+S` - Save changes
- `?` - Show help screen
- `Q` / `Ctrl+C` - Quit

**Workflow:**
1. Launch editor with `daf open --edit <identifier>`
2. Navigate tabs to find fields to edit
3. Make changes to metadata
4. Press `Ctrl+S` or click "Save Changes" button
5. Automatic backup is created before saving
6. Changes are validated before committing

**Validation:**
- JIRA keys must match format: `PROJECT-NUMBER`
- Claude session UUIDs must be valid UUID format
- Project paths are validated for existence
- Required fields are enforced
- Read-only fields cannot be modified

**Use Cases:**

**Fix Incorrect JIRA Association:**
```bash
# Session was linked to wrong ticket
daf open --edit my-session
# → Navigate to JIRA Integration tab
# → Update JIRA key field
# → Save
```

**Update Session Goal:**
```bash
# Goal needs clarification
daf open --edit PROJ-12345
# → Navigate to Core Metadata tab
# → Edit goal field
# → Save
```

**Manage Multi-Repository Conversations:**
```bash
# Working on feature across multiple repos
daf open --edit cross-repo-feature
# → Navigate to Conversations tab
# → Click "Add Conversation"
# → Enter Claude session UUID, path, and branch
# → Save
```

**Change Session Type:**
```bash
# Converting ticket_creation session to development
daf open --edit PROJ-60989
# → Navigate to Core Metadata tab
# → Change "Session Type" dropdown
# → Save
```

**Fix Corrupted Metadata:**
```bash
# Session has invalid or missing fields
daf open --edit broken-session
# → Review and correct fields
# → Validation will show errors
# → Fix errors and save
```

**Notes:**
- Always creates a backup in `$DEVAIFLOW_HOME/backups/` before saving
- Backup filename format: `session-{name}-{timestamp}.json`
- Validation prevents saving invalid data
- Can cancel changes without saving (no backup created if cancelled)
- Multi-conversation sessions show all conversations in Conversations tab

**See Also:**
- `daf update` - CLI-based metadata updates (simpler, scriptable)
- `daf info` - View current session metadata
- `daf maintenance repair-conversation` - Fix corrupted conversation files

---

### daf completion - Shell Auto-Completion

Install shell auto-completion for daf command.

```bash
daf completion [SHELL]
```

**Supported shells:** bash, zsh, fish

**Examples:**
```bash
# Auto-detect shell
daf completion

# Specific shell
daf completion bash
daf completion zsh
daf completion fish
```

**Features:**
- Auto-complete session names and JIRA keys
- Auto-complete working directories, sprints, tags
- File path completion for exports/imports

See [Installation Guide](../getting-started/installation.md) for setup instructions.

---

### daf init - Initialize Configuration

Create default configuration file with automatic JIRA field discovery, refresh automatically discovered data, or review and update all configuration values.

```bash
daf init [OPTIONS]
```

**Options:**
- `--refresh` - Refresh automatically discovered data (custom field mappings)
- `--reset` - Re-prompt for all configuration values
- `--skip-jira-discovery` - Skip JIRA field discovery during init

**Examples:**
```bash
# Interactive initialization with field discovery
daf init

# Skip field discovery
daf init --skip-jira-discovery

# Refresh automatically discovered data
daf init --refresh

# Review and update all configuration values
daf init --reset
```

**First-time setup:**

When config doesn't exist, `daf init` (without flags):
1. Creates `$DEVAIFLOW_HOME/config.json` with default settings
2. Detects JIRA API token from environment
3. Prompts for essential configuration:
   - JIRA URL and project key
   - Comment visibility (who can see DevAIFlow's JIRA comments)
   - Workspace path (repository directory)
   - Optional: Keyword mappings for multi-repo suggestions
   - Optional: PR/MR template URL
4. Discovers and caches JIRA custom field mappings (if token available)

**Refresh mode (`--refresh`):**

When config exists, use `daf init --refresh` to update automatically discovered data:
- Refreshes JIRA custom field mappings from JIRA API
- Updates `field_cache_timestamp` in config.json
- **Preserves all user-provided configuration** (URL, custom field defaults, workspace, etc.)
- **Does NOT prompt** for any configuration values
- **Does NOT modify** user data (sessions, templates, backups)

**Reset mode (`--reset`):**

When config exists, use `daf init --reset` to review and update all configuration values:
- Prompts for each configuration value
- **Shows current values as defaults** (press Enter to keep)
- **Automatically refreshes JIRA field mappings** after prompts
- Updates `config.json` with new values
- Shows summary of changes made
- **Preserves user data** (sessions, templates, backups)
- **Does NOT delete** any configuration data

**Reset mode workflow:**
```
$ daf init --reset

DevAIFlow Configuration Wizard

All settings can be changed later using 'daf config edit'

=== JIRA Configuration ===

The project key is the short identifier for your JIRA project (e.g., 'PROJ', 'ENG', 'DEVOPS')
You can find it in your JIRA URL: https://jira.company.com/browse/PROJ-123 → 'PROJ'
Can be set later, but required for: creating issues, field discovery

JIRA URL (https://jira.example.com):
JIRA Project Key (optional, press Enter to skip) (PROJ):

=== JIRA Comment Visibility ===

Control who can see comments that DevAIFlow adds to JIRA tickets.
Can be set later via 'daf config edit'.

Choose visibility type:
  1. group - Restrict by JIRA group membership (most common)
  2. role - Restrict by JIRA role

Visibility type [group/role] (group):

Enter the JIRA group name (e.g., 'Engineering Team', 'Developers')
Group name (Engineering Team):

=== Repository Workspace ===

Workspace path (~/development/myproject):

=== Keyword Mappings ===

Optional: Keywords help suggest repositories when working across multiple repos.
DevAIFlow learns from your usage patterns, so keywords are only needed if you want
explicit routing rules. You can skip this and configure later via 'daf config edit'.

Configure keyword mappings now? [y/n] (n): n

=== PR/MR Template Configuration ===

Optional: Configure how AI generates PR/MR descriptions.
Templates are auto-discovered from organization and repository locations.
Manual configuration can be added later via 'daf config edit' or by editing config.json.

You have three options for generating PR/MR descriptions:
  1. Provide a template URL - AI will fill your organization's template
  2. Leave empty - AI will generate descriptions automatically
  3. Add template guidance to AGENTS.md/ORGANIZATION.md/TEAM.md files

Configure PR/MR template URL? [y/n] (n): n

Discovering JIRA custom field mappings...
✓ Found 4 custom fields

✓ Configuration saved
Location: $DEVAIFLOW_HOME/config.json
```

**When to use each mode:**
- `daf init` - First-time setup or switching JIRA instances
- `daf init --refresh` - When JIRA custom fields change (updates mappings only)
- `daf init --reset` - When you need to update multiple configuration values (URL, custom field defaults, workspace, etc.)

**Field Discovery:**

When `JIRA_API_TOKEN` is set, `daf init` automatically:
- Fetches all custom fields for your JIRA project
- Maps human-readable names (e.g., "workstream") to field IDs (e.g., "customfield_12319275")
- Caches field metadata including types, allowed values, and required status
- Stores mappings in `config.json` for future use

**Benefits:**
- No need to remember cryptic custom field IDs
- Supports any JIRA instance (not hardcoded to specific instance)
- Makes future JIRA integrations easier
- Cached for offline use
- Easy refresh when JIRA custom fields change

**When to run:**
- `daf init` - After first installation, when switching JIRA instances, or when resetting configuration
- `daf init --refresh` - When JIRA custom field IDs change (rare), or to ensure field mappings are current

**Alternative to --refresh:**

You can also use `daf config refresh-jira-fields` to refresh field mappings specifically.

---

### daf skills - Manage AI Agent Skills

Install, upgrade, uninstall, or list bundled skills for multiple AI agents.

```bash
daf skills [SKILL_NAME] [OPTIONS]
```

**Arguments:**
- `SKILL_NAME` - (Optional) Specific skill to install/uninstall (e.g., `daf-help`, `gh-cli`)

**Options:**
- `--install` - Install skills (default action)
- `--upgrade` - Upgrade skills (same as --install)
- `--uninstall` - Uninstall skills
- `--list` - List available or installed skills
- `--available` - Show available bundled skills (use with --list)
- `--installed` - Show installed skills (use with --list)
- `--dry-run` - Preview what would be changed without making changes
- `--agent TEXT` - AI agent to target (claude, cursor, windsurf, copilot, aider, continue)
- `--level [global|project|both]` - Installation level (default: global)
- `--all-agents` - Target all supported agents
- `--project-path PATH` - Project directory for project-level operations

**What This Does:**

The `daf skills` command manages bundled skills that provide helpful prompts and reference documentation:
- **Installs** skills if they don't exist yet
- **Upgrades** skills if they're outdated
- **Skips** skills that are already up-to-date
- **Supports multiple AI agents** - Install to Claude, Cursor, Windsurf, Copilot, Aider, and Continue

By default, skills are installed globally to `~/.claude/skills/` and are available in all Claude Code sessions.

**Requirements:**
- **Claude Code 2.1.3 or higher** is required for slash command support (for Claude)
- Other agents may have different skill/context file support

**Examples:**

```bash
# Install all skills (default: Claude only, global)
daf skills

# List available bundled skills
daf skills --list --available

# List installed skills for all agents
daf skills --list --installed --all-agents

# Install specific skill to Claude
daf skills daf-help

# Install specific skill to Cursor
daf skills daf-help --agent cursor

# Preview what would be upgraded
daf skills --dry-run

# Install to a specific agent
daf skills --agent cursor
daf skills --agent windsurf

# Install to all supported agents
daf skills --all-agents

# Install to project directory (can be committed to git for team)
daf skills --level project --project-path .

# Install to both global and project
daf skills --level both --project-path .

# Uninstall all skills from Cursor
daf skills --uninstall --agent cursor

# Uninstall specific skill from all agents
daf skills daf-help --uninstall --all-agents
```

**Sample Output:**

```
Upgrading bundled skills...

Slash Commands:
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Skill                     ┃ Status Before ┃ Status After ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ daf-help                  │ not installed │ installed   │
│ daf-list                  │ not installed │ installed   │
│ daf-active                │ not installed │ installed   │
└───────────────────────────┴───────────────┴─────────────┘

Reference Skills:
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Skill                     ┃ Status Before ┃ Status After ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ daf-cli                   │ not installed │ installed   │
│ gh-cli                    │ not installed │ installed   │
└───────────────────────────┴───────────────┴─────────────┘

✓ Updated 11 slash command(s)
✓ Updated 4 reference skill(s)
Skills location: ~/.claude/skills/
```

**Bundled Skills:**

DevAIFlow includes two types of skills:

**1. Slash Commands** (invokable with `/daf-*` in Claude Code):

**Multi-Conversation Commands:**
- **`/daf-list-conversations`** - List all conversations in multi-project session
- **`/daf-read-conversation`** - Read conversation history from other repositories

**Session Management Commands:**
- **`/daf-list`** - List all sessions with status and time tracking
- **`/daf-info`** - Show detailed information about current session
- **`/daf-active`** - Show currently active conversation details
- **`/daf-notes`** - View all progress notes for current session (read-only)

**JIRA & Sprint Commands:**
- **`/daf-jira`** - View JIRA ticket details for current session
- **`/daf-status`** - Show sprint status and progress dashboard

**Workspace & Configuration:**
- **`/daf-workspace`** - List configured workspaces for multi-branch development
- **`/daf-config`** - View current configuration (JIRA, workspace, prompts)

**Help & Reference:**
- **`/daf-help`** - Show available daf commands and quick reference

**2. Reference Skills** (auto-loaded, not invokable):

These skills provide reference documentation that Claude reads automatically:
- **`daf-cli`** - Complete daf tool command reference
- **`gh-cli`** - GitHub CLI reference for PR operations
- **`git-cli`** - Git workflow guidance
- **`glab-cli`** - GitLab CLI reference for MR operations

All slash commands are READ-ONLY and safe to run inside Claude Code sessions.

**How Skills Work:**

**Slash Commands vs Reference Skills:**
- **Slash commands** have a `name:` field in their YAML frontmatter → invokable as `/daf-help`
- **Reference skills** have NO `name:` field → auto-loaded as context, not invokable

**Skills vs Commands:**
- Claude Code 2.1.3+ unified slash commands and skills into a single system
- Legacy `.claude/commands/` directory is no longer used
- All skills use the `.claude/skills/` directory structure with `SKILL.md` files

**Managing Skills:**

**Installation:**
- **Global**: Skills are installed to `~/.claude/skills/` (or `~/.agent/skills/` for other agents)
- **Project**: Skills can be installed to `<project>/.claude/skills/` for team sharing
- Available in all sessions automatically
- **Multi-agent support**: Install to multiple AI agents with `--all-agents` flag

**Installation Locations by Agent:**
- Claude Code: `~/.claude/skills/` or `<project>/.claude/skills/`
- GitHub Copilot: `~/.copilot/skills/` or `<project>/.github-copilot/skills/`
- Cursor: `~/.cursor/skills/` or `<project>/.cursor/skills/`
- Windsurf: `~/.codeium/windsurf/skills/` or `<project>/.windsurf/skills/`
- Aider: `~/.aider/skills/` or `<project>/.aider/skills/`
- Continue: `~/.continue/skills/` or `<project>/.continue/skills/`

**Removal:**
If you want to remove the bundled skills:

```bash
# Remove all bundled skills from Claude
rm -rf ~/.claude/skills/daf-* ~/.claude/skills/gh-cli ~/.claude/skills/git-cli ~/.claude/skills/glab-cli

# Remove from specific agent
rm -rf ~/.cursor/skills/daf-*

# Remove from all agents
rm -rf ~/.claude/skills/daf-* ~/.copilot/skills/daf-* ~/.cursor/skills/daf-* ~/.codeium/windsurf/skills/daf-* ~/.aider/skills/daf-* ~/.continue/skills/daf-*
```

**Custom Skills:**
You can create your own custom skills by adding skill directories to `~/.claude/skills/`. See the [Agent Skills Documentation](https://agentskills.io) for the open standard, or the [Claude Code documentation](https://docs.anthropic.com/claude/docs/claude-code) for Claude-specific details.

**Note:** Skills are only loaded when Claude Code sessions start. Changes to skills require restarting the session (closing and reopening with `daf open`) to take effect - they are NOT hot-reloaded on `--resume`.

**Deprecated Command:**

⚠️ **`daf upgrade` is deprecated** and will be removed in version 3.0. Use `daf skills` instead.

The `daf upgrade` command still works for backward compatibility but shows a deprecation warning. All functionality has been moved to `daf skills` with additional features:
- Install specific skills by name: `daf skills daf-help`
- Uninstall skills: `daf skills --uninstall`
- List available and installed skills: `daf skills --list --available`

**Migration:**
- `daf upgrade` → `daf skills`
- `daf upgrade --agent cursor` → `daf skills --agent cursor`
- `daf upgrade --all-agents` → `daf skills --all-agents`

---

## Experimental Features

⚠️ **EXPERIMENTAL** - These features are under active development and subject to change.

### Enabling Experimental Features

Use the `-e` or `--experimental` flag **before** the command:

```bash
# Enable experimental features (short form - recommended)
daf -e feature list

# Enable experimental features (long form)
daf --experimental feature list

# Environment variable (persistent)
export DEVAIFLOW_EXPERIMENTAL=1
daf feature list
```

**Important:** The `-e` flag must come **before** the command name, not after.

### daf feature - Multi-Session Feature Orchestration

**Status:** EXPERIMENTAL

Orchestrate multiple sessions sequentially on a shared branch with automated verification between sessions.

**Enable with:** `daf -e feature <command>` or `export DEVAIFLOW_EXPERIMENTAL=1`

**Commands:**

```bash
# Create feature from parent ticket (auto-discovers children)
daf -e feature create my-feature --parent "PROJ-100" --auto-order

# Create feature with manual session list
daf -e feature create my-feature --sessions "PROJ-101,PROJ-102,PROJ-103"

# List all features
daf -e feature list

# Show feature status
daf -e feature status my-feature

# Run feature workflow
daf -e feature run my-feature

# Resume paused feature
daf -e feature resume my-feature

# Reorder sessions (multiple modes)
daf -e feature reorder my-feature                    # Interactive
daf -e feature reorder my-feature PROJ-102 1         # Move session to position
daf -e feature reorder my-feature --sync-jira        # Sync from JIRA blocking relationships
daf -e feature reorder my-feature --order "s2,s1,s3" # Direct order

# Delete feature
daf -e feature delete my-feature
```

**Key Features:**
- **Auto-discovery**: Parse parent tickets to find all child tickets
- **Dependency ordering**: Topological sort based on blocking relationships
- **Automated verification**: Run tests and validate artifacts between sessions
- **JIRA integration**: Sync blocking relationships from JIRA
- **Session auto-creation**: Create missing sessions automatically
- **Shared branch**: All sessions work on same feature branch
- **Integrated PR**: Single PR for entire feature at completion

**Documentation:** See [../experimental/feature-orchestration.md](../experimental/feature-orchestration.md) for complete guide.

**Report Issues:** https://github.com/itdove/devaiflow/issues

---

## Using Slash Commands in Multi-Repository Sessions

**Multi-Project Sessions (NEW):** When you create sessions with `--projects`, you get ONE conversation with SHARED CONTEXT across all repositories. Claude can already see all projects, so these slash commands are typically not needed.

**Legacy Multi-Conversation Sessions:** Older sessions have separate conversations per repository (no shared context). These slash commands help Claude understand work done in other repositories.

**What is multi-conversation (legacy):**
- ONE session with MULTIPLE separate conversations (one per repository)
- Each conversation is isolated (no shared context)
- All conversations share the same session metadata (goal, JIRA link, notes)
- Each conversation has its own git branch and Claude Code session

**The bundled slash commands** help Claude in legacy sessions understand work done in other repositories. They work WITHIN a single session that has multiple conversations (NOT across multiple sessions).

**Note:** If you're using new multi-project sessions (`--projects`), you don't need these commands since Claude already has shared context.

### Available Slash Commands

After running `daf skills`, the following commands are available in Claude Code:

#### `/daf list-conversations`

Lists all conversations in the current multi-project session.

**What it does:**
- Shows all repositories in the session
- Displays working directory names, branches, and Claude session UUIDs
- Helps you see what work has been done where

**When to use:**
- You need to see all repositories involved in this feature
- You want to check which branches are being used
- You need the UUID to read another conversation

**How Claude uses it:**
Run `daf info` to see conversation details, then relay information to the user.

#### `/daf read-conversation`

Reads the conversation history from another repository in the session.

**What it does:**
- Allows Claude to read work done in other repositories
- Maintains consistency across multi-repository implementations
- Excludes the current conversation (no duplication)

**When to use:**
- You need to know what API changes were made in the backend
- You want to see what data models were defined in another repo
- You need to maintain consistency across repositories

**How Claude uses it:**
1. Use `/daf list-conversations` to see available conversations
2. Find the conversation you need to read (NOT the current one)
3. Use `daf info` to get the Claude session UUID
4. Read the conversation file at `~/.claude/projects/<encoded-path>/<uuid>.jsonl`

**Important:** You cannot read your own conversation (the current one) - you already have that context.

### Enabling Auto-Load Prompts

You can configure Claude to automatically be prompted to read related conversations when opening a multi-project session.

**Via TUI:**
```bash
daf config edit
```

Navigate to **Prompts** tab → **Multi-Conversation Sessions** → Set "Auto-load related conversations prompt" to **Enable**.

**What this does:**
When you open a conversation in a multi-project session, Claude will see a prompt like:

```
⚠️  CROSS-REPOSITORY CONTEXT:
   • This session has work in multiple repositories
   • Other repositories: frontend-ui, infrastructure

   RECOMMENDED: Use the /daf list-conversations slash command to see all conversations
   Use the /daf read-conversation slash command to read work done in other repositories

   This helps maintain consistency across the multi-repository feature implementation.
```

**When to enable:**
- You frequently work on features spanning multiple repositories
- You want Claude to proactively consider context from other repos
- You're working on complex integrations that require cross-repo awareness

**When to disable (default):**
- You mostly work in single repositories
- You prefer to manually invoke slash commands when needed
- You want minimal prompt clutter

### Example Multi-Conversation Workflow

**Scenario:** Implementing a backup feature across 3 repositories within ONE session (PROJ-52470).

**Repositories:**
1. **Backend API** (myproject-management-service)
2. **Frontend UI** (myproject-admin-console)
3. **Infrastructure** (myproject-sops)

**Important:** All 3 conversations below are part of SESSION #1. You're NOT creating 3 separate sessions.

**Workflow:**

```bash
# Step 1: Create session with first conversation (backend)
daf new --name PROJ-52470 --goal "Implement backup feature" --path ~/dev/myproject-management-service

# Claude implements backup API endpoints in backend repo
# ... work happens in backend conversation ...
# Exit Claude Code (Ctrl+D)

# Step 2: Add second conversation to SAME session (frontend)
daf new --name PROJ-52470 --goal "Implement backup feature" --path ~/dev/myproject-admin-console
# ✓ Automatically adds conversation to existing session #1 (multi-conversation)
# NO prompt shown - this is the default behavior

# Claude is now in frontend conversation
# Use slash command to read backend work:
# > /daf list-conversations
# Claude sees:
#   1. myproject-management-service (backend)
#   2. myproject-admin-console (current)
#
# > /daf read-conversation
# Claude reads the backend conversation history
# Implements frontend UI that calls the correct endpoints
# ... work happens in frontend conversation ...
# Exit Claude Code (Ctrl+D)

# Step 3: Add third conversation to SAME session (infrastructure)
daf new --name PROJ-52470 --goal "Implement backup feature" --path ~/dev/myproject-sops
# ✓ Automatically adds conversation to existing session #1

# Claude reads both previous conversations using /daf read-conversation
# Implements infrastructure changes consistently
```

**Verify multi-conversation:**
```bash
daf info PROJ-52470
# Shows:
#   Session #1 - in_progress
#   Goal: Implement backup feature
#   Conversations:
#     1. myproject-management-service
#     2. myproject-admin-console
#     3. myproject-sops

daf list
# Shows 1 row (not 3):
# PROJ-52470  |  Session #1  |  3 conversations  |  in_progress
```

**Benefits:**
- ✅ Claude knows what API endpoints were created in backend
- ✅ Claude knows what UI components were added in frontend
- ✅ Claude can ensure infrastructure changes align with both
- ✅ No manual copying/pasting of implementation details between conversations
- ✅ All work tracked in ONE session (unified notes, time tracking, export)

### Best Practices

1. **Always run `daf skills`** after updating the tool to get latest slash commands
2. **Use multi-conversation (default)** - Don't use `--new-session` flag when adding work to other repos
3. **Use `/daf list-conversations`** first to see what's available
4. **Only read other conversations**, not your current one
5. **Enable auto-load** if you frequently work on multi-repo features
6. **Document decisions** in each conversation so other conversations can reference them

### Important: Multi-Conversation vs Multi-Session

**Slash commands work ONLY with multi-conversation** (one session with multiple conversations in different repos).

**They do NOT work across multi-session** (multiple sessions in the same group). Each session has its own isolated conversations.

If you accidentally created multiple sessions (using `--new-session` flag), you'll need to manually read the other session's conversations. See [Multi-Conversation vs Multi-Session Architecture](#multi-conversation-vs-multi-session-architecture) for details on the difference.

---

### daf config edit - Interactive Configuration Editor

Launch a full-screen TUI (Text User Interface) for managing all configuration settings.

```bash
daf config edit
```

**Features:**
- Tabbed interface for different configuration sections (JIRA, Repository, Model Providers, Prompts, Context Files)
- **Model Provider management** - Visual editor for alternative AI models (llama.cpp, Vertex AI, OpenRouter)
- Input validation for URLs, paths, and required fields
- Tri-state prompt controls (Always/Never/Prompt each time) for workflow automation
- Preview mode before saving (Ctrl+P)
- Automatic backup creation
- Help screen (press `?`)
- Keyboard shortcuts (Ctrl+S to save)

**Configuration Tabs:**
- **JIRA** - JIRA server URL, project, custom field defaults, field mappings, transitions
- **Repository** - Workspace directory, repository detection settings, keywords
- **Model Providers** - Configure AI model profiles (llama.cpp, Vertex AI, OpenRouter, etc.) for Claude Code
- **Prompts** - Automatic answers for `daf new`, `daf open`, `daf complete` prompts
- **Context Files** - Additional context files for initial prompts (read-only, use CLI to manage)

**Keyboard Shortcuts:**
- `Tab/Shift+Tab` - Navigate between fields
- `Arrow Keys` - Navigate tabs and fields, move through dropdown options
- `Enter` - Activate button/select dropdown option
- `Space` - Toggle checkbox
- `Escape` - Cancel/close modal or dropdown
- `Ctrl+S` - Save configuration
- `Ctrl+P` - Preview changes before saving
- `?` - Show help screen
- `Q/Ctrl+C` - Quit without saving

**When to use:**
- First-time configuration
- Updating multiple settings at once
- Visual review of all settings
- When you prefer GUI over command line

**Alternative:** Use `daf config edit` (alias for this command)

---

### daf config edit - Interactive Configuration Editor (Alias)

Alias for `daf config edit`. See [daf config edit](#daf-config-edit---interactive-configuration-editor) for details.

```bash
daf config edit
```

---

### daf config refresh-jira-fields - Refresh JIRA Field Mappings

Update cached JIRA custom field mappings.

```bash
daf config refresh-jira-fields
```

**What it does:**
1. Fetches current custom field metadata from JIRA
2. Updates field mappings in `config.json`
3. Updates cache timestamp

**When to use:**
- New custom fields added to your JIRA instance
- Field configurations changed (e.g., allowed values updated)
- Switching to a different JIRA project
- Field mappings feel outdated (older than 7 days)

**Example output:**
```
Discovering JIRA custom fields for project PROJ...
✓ Found 45 custom fields
✓ Cached field mappings to config
```

**Requirements:**
- `JIRA_API_TOKEN` environment variable must be set
- Valid JIRA configuration in `config.json`

---

### daf config export - Export Configuration for Team Onboarding

Export all configuration files to a tar.gz archive for sharing with teammates.

```bash
daf config export [--output PATH] [--force]
```

**Options:**
- `-o, --output PATH` - Output file path (default: `~/config-export.tar.gz`)
- `-f, --force` - Skip confirmation prompts

**What it exports:**
- `config.json` - User preferences
- `enterprise.json` - Enterprise settings
- `organization.json` - Organization settings
- `team.json` - Team defaults
- `backends/jira.json` - JIRA backend configuration

**What it does:**
1. Scans for local paths that won't work on other machines
2. Displays warnings about `file://` URLs and absolute workspace paths
3. Suggests converting to GitHub/GitLab URLs
4. Creates tar.gz archive with all config files
5. Includes metadata with warnings and suggestions

**Examples:**
```bash
# Export with default path
daf config export

# Export to specific location
daf config export --output /tmp/team-config.tar.gz

# Skip confirmation prompts (for automation)
daf config export --force
```

**Security:**
- API tokens (JIRA_API_TOKEN, GITHUB_TOKEN) are NOT exported
- Only configuration files are included (no secrets)

**When to use:**
- Onboarding new team members
- Sharing organization/team standards
- Creating backup of configuration

---

### daf config import - Import Configuration from Export

Import configuration files from an export archive.

```bash
daf config import EXPORT_FILE [--merge|--replace] [--force]
```

**Options:**
- `--merge` - Merge with existing config, preserving workspace paths (default)
- `--replace` - Replace existing config entirely
- `-f, --force` - Skip confirmation prompts

**Import modes:**

**Merge mode (default):**
- Imports organization policies and field mappings
- Preserves your local workspace paths
- Deep merges JSON objects

**Replace mode:**
- Replaces all configuration files
- Use for fresh setup or complete reset

**What it does:**
1. Validates export file
2. Shows preview of what will be imported
3. Prompts for confirmation
4. Imports configuration files
5. Suggests running `daf skills` to install skills

**Examples:**
```bash
# Import and merge (preserves workspace paths)
daf config import config-export.tar.gz

# Import and replace everything
daf config import config-export.tar.gz --replace

# Skip confirmation prompts
daf config import config-export.tar.gz --force

# After import, install skills
daf skills
```

**Typical onboarding workflow:**
1. Team member exports: `daf config export --output team-config.tar.gz`
2. New user imports: `daf config import team-config.tar.gz`
3. New user adjusts workspace paths: `daf config edit`
4. New user installs skills: `daf skills`

**When to use:**
- Onboarding to a new project
- Restoring configuration
- Syncing team settings

---

### Essential Commands (Daily Use)

```bash
daf sync --sprint current    # Start of sprint
daf status                   # Check sprint progress
daf open PROJ-12345          # Start working
daf note PROJ-12345 "..."    # Track progress
daf complete PROJ-12345      # Finish work
```

### Setup Commands (One-Time)

```bash
daf init                    # Initialize config
daf completion              # Setup auto-completion
```

### Maintenance (As Needed)

```bash
daf maintenance cleanup-conversation    # Fix 413 errors
daf maintenance cleanup-sessions        # Fix orphaned sessions
daf backup                  # Backup everything
```

## Quick Reference Table

| Command | Purpose | JIRA Required |
|---------|---------|--------------|
| **Daily Use** |
| `daf sync` | Sync JIRA tickets | Yes |
| `daf open` | Resume session | No |
| `daf note` | Add note | No |
| `daf notes` | View notes | No |
| `daf complete` | Finish session | No |
| `daf status` | Sprint dashboard | Yes |
| **Session Management** |
| `daf new` | Create session | No |
| `daf list` | List sessions | No |
| `daf delete` | Delete session | No |
| `daf summary` | View summary | No |
| `daf info` | Show session details & UUIDs | No |
| `daf time` | View time | No |
| **JIRA Integration** |
| `daf link` | Link JIRA | Yes |
| `daf unlink` | Remove JIRA | Yes |
| `daf jira view` | View JIRA ticket | Yes |
| `daf jira create epic` | Create JIRA epic | Yes |
| `daf jira create spike` | Create JIRA spike | Yes |
| `daf jira create story` | Create JIRA story | Yes |
| `daf jira create task` | Create JIRA task | Yes |
| `daf jira create bug` | Create JIRA bug | Yes |
| `daf jira update` | Update JIRA fields | Yes |
| **Backup/Export** |
| `daf export` | Export sessions | No |
| `daf import` | Import sessions | No |
| `daf backup` | Full backup | No |
| `daf restore` | Restore backup | No |
| `daf export-md` | Export to Markdown | No |
| **Maintenance** (Hidden Group) |
| `daf maintenance cleanup-conversation` | Clean history | No |
| `daf maintenance cleanup-sessions` | Fix orphaned | No |
| `daf maintenance discover` | Find unmanaged sessions | No |
| `daf maintenance rebuild-index` | Rebuild sessions index | No |
| `daf maintenance repair-conversation` | Fix corrupted files | No |
| `daf purge-mock-data` | Clear mock data (hidden) | No |
| **Configuration** |
| `daf init` | Initialize config | No |
| `daf init --refresh` | Refresh field mappings | Yes |
| `daf init --reset` | Review/update config | No |
| `daf skills` | Manage AI agent skills | No |
| `daf config edit` | Interactive configuration | No |
| `daf config refresh-jira-fields` | Refresh field mappings | Yes |
| **Utilities** |
| `daf search` | Search sessions | No |
| `daf maintenance discover` | Find sessions | No |
| `daf template` | Manage templates | No |
| `daf open --edit` | Interactive metadata editor | No |
| `daf update` | CLI metadata updates | No |
| `daf completion` | Auto-completion (hidden) | No |
| `daf check` | Check dependencies (hidden) | No |
| `daf edit` | Metadata editor (hidden, use daf open --edit) | No |

## Next Steps

- [Workflows](08-workflows.md) - Step-by-step workflows using these commands
- [Advanced Features](09-advanced.md) - Advanced command usage
- [Troubleshooting](../guides/troubleshooting.md) - Command errors and solutions

---

## Configuration Management

### Overview

The `daf config set-*` commands have been removed as of version 2.0. Use the alternatives below to configure DevAIFlow.

### Recommended Alternatives

#### Option 1: Use the TUI (Interactive Users)


```bash
daf config edit
```

Features:
- Tab navigation between configuration sections
- Input validation (path existence, JSON format, etc.)
- Real-time error feedback
- Save/cancel workflow
- Shows repo count after workspace changes

#### Option 2: Direct JSON Editing (Automation/Scripts)

For scripts and automation, edit `$DEVAIFLOW_HOME/config.json` directly:

```bash
# Using jq (recommended for automation)
jq '.jira.project = "PROJ"' $DEVAIFLOW_HOME/config.json > /tmp/cfg.json
mv /tmp/cfg.json $DEVAIFLOW_HOME/config.json

# Or edit manually
vi $DEVAIFLOW_HOME/config.json
```

### Configuration Mapping Reference

| Configuration Setting | TUI Location | JSON Path | Notes |
|-----------------------|--------------|-----------|-------|
| JIRA Project | JIRA Integration → Project Key | `.jira.project` | Normalized to uppercase |
| Workspace Directory | Repository → Workspace | `.repos.workspace` | Shows repo count in TUI |
| Affected Version | JIRA Integration → Affected Version | `.jira.affected_version` | - |
| Comment Visibility | JIRA Integration → Comment Visibility | `.jira.comment_visibility_type`, `.jira.comment_visibility_value` | - |
| Transition On Start | JIRA Transitions → On Start | `.jira.transitions.on_start` | JiraTransitionConfig object |
| Transition On Complete | JIRA Transitions → On Complete | `.jira.transitions.on_complete` | JiraTransitionConfig object |
| Prompts | Prompts → Various | `.prompts.*` | Multiple fields |

### Configuration Export and Import

For user onboarding and team collaboration, DevAIFlow provides commands to export and import configuration files.

#### daf config export - Export Configuration

Export all configuration files to a tar.gz archive for sharing with teammates.

```bash
daf config export [OPTIONS]
```

**Options:**
- `-o, --output PATH` - Output file path (default: `~/config-export.tar.gz`)
- `-f, --force` - Skip confirmation prompts

**What it exports:**
- `config.json` - User preferences
- `enterprise.json` - Enterprise settings
- `organization.json` - Organization settings
- `team.json` - Team defaults
- `backends/jira.json` - JIRA backend configuration

**What it scans for:**
- Absolute workspace paths (e.g., `/Users/alice/development`)
- `file://` URLs in `context_files`, `pr_template_url`, `hierarchical_config_source`
- Displays warnings with suggestions to convert to GitHub/GitLab URLs

**Examples:**
```bash
# Export with default path
daf config export

# Export to specific location
daf config export --output /tmp/team-config.tar.gz

# Skip confirmation prompts (for automation)
daf config export --force
```

**Important Notes:**
- API tokens (JIRA_API_TOKEN, GITHUB_TOKEN) are NOT exported (they're in environment variables)
- Warns about local paths that won't work on other machines
- Suggests converting `file://` URLs to repository URLs

#### daf config import - Import Configuration

Import configuration from an export archive.

```bash
daf config import EXPORT_FILE [OPTIONS]
```

**Options:**
- `--merge` - Merge with existing config, preserving workspace paths (default)
- `--replace` - Replace existing config entirely
- `-f, --force` - Skip confirmation prompts

**Import modes:**

**Merge mode (default):**
- Imports organization policies and field mappings
- Preserves your local workspace paths
- Merges with existing configuration

**Replace mode:**
- Replaces all configuration files
- Use for fresh setup or complete reset

**Examples:**
```bash
# Import and merge (preserves workspace paths)
daf config import config-export.tar.gz

# Import and replace everything
daf config import config-export.tar.gz --replace

# Skip confirmation prompts
daf config import config-export.tar.gz --force
```

**After importing:**
```bash
# Install skills and update field mappings
daf skills
```

**Typical onboarding workflow:**
1. Team member exports their config: `daf config export --output team-config.tar.gz`
2. New user receives the archive
3. New user imports: `daf config import team-config.tar.gz`
4. New user adjusts workspace paths if needed: `daf config edit`
5. New user installs skills: `daf skills`

### Configuration Examples

#### Example 1: Setting JIRA Project

**Using TUI:**
```bash
daf config edit
# Navigate to "JIRA Integration" tab
# Set "Project Key" field to "PROJ"
# Press Save
```

**Direct editing:**
```bash
jq '.jira.project = "PROJ"' $DEVAIFLOW_HOME/config.json > /tmp/cfg.json
mv /tmp/cfg.json $DEVAIFLOW_HOME/config.json
```

#### Example 2: Setting Workspace Directory

**Using TUI:**
```bash
daf config edit
# Navigate to "Repository" tab
# Set "Workspace" field to "~/development"
# TUI shows repo count after save
# Press Save
```

**Direct editing:**
```bash
jq '.repos.workspaces = [{"name": "default", "path": "~/development"}] | .repos.last_used_workspace = "default"' $DEVAIFLOW_HOME/config.json > /tmp/cfg.json
mv /tmp/cfg.json $DEVAIFLOW_HOME/config.json
```

#### Example 4: Complex Configuration (Transitions)

**Using TUI:**
```bash
daf config edit
# Navigate to "JIRA Transitions" tab
# Configure "On Start" section
# Press Save
```

**Direct editing:**
```bash
cat > /tmp/transition.json << 'JSON'
{
  "from_status": ["New", "To Do"],
  "to": "In Progress",
  "prompt": false,
  "on_fail": "warn"
}
JSON

jq '.jira.transitions.on_start = input' $DEVAIFLOW_HOME/config.json /tmp/transition.json > /tmp/cfg.json
mv /tmp/cfg.json $DEVAIFLOW_HOME/config.json
```

### Validation Differences

| Feature | TUI | Direct Editing |
|---------|-----|----------------|
| Workstream allowed_values | ✅ Validated | ❌ No validation |
| Path existence | ✅ Checked | ❌ No validation |
| Repo count display | ✅ Shown | ❌ Not shown |
| Field type validation | ✅ Full | ❌ No validation |
| Real-time feedback | ✅ Yes | ❌ No |

### Integration Test Updates

Integration tests should be updated to use one of these approaches:

**Approach 1: Direct JSON creation (recommended for speed)**
```bash
cat > $DEVAIFLOW_HOME/config.json << 'JSON'
{
  "jira": {
    "url": "https://jira.example.com",
    "project": "PROJ"
  },
  "repos": {
    "workspaces": [{"name": "default", "path": "/tmp"}],
    "last_used_workspace": "default"
  }
}
JSON
```

**Approach 2: jq for selective updates**
```bash
jq '.jira.project = "PROJ" | .repos.workspaces = [{"name": "default", "path": "/tmp"}] | .repos.last_used_workspace = "default"' \
  $DEVAIFLOW_HOME/config.json > /tmp/cfg.json && mv /tmp/cfg.json $DEVAIFLOW_HOME/config.json
```

### Removal Notice

- **v2.0+**: Commands have been removed entirely

### Getting Help

If you encounter issues during migration:
- Check the [Configuration Guide](configuration.md) for detailed config.json schema
- Use `daf config show` to view current configuration
- Use `daf config validate` to check for errors
- Report issues: https://github.com/itdove/devaiflow/issues

## Model Provider Management

Manage model provider profiles for alternative AI providers (Vertex AI, llama.cpp, OpenRouter, etc.).

See also: [Alternative Model Providers Guide](alternative-model-providers.md) for detailed setup instructions.

### daf provider list - List Profiles

List all configured model provider profiles.

```bash
daf provider list [OPTIONS]
```

**Options:**
- `--json` - Output in JSON format

**Examples:**
```bash
# List all profiles
daf provider list

# JSON output for automation
daf provider list --json
```

**Output example:**
```
┌─ Configured Model Provider Profiles ─────┐
│ Name         Base URL              Type  │
│ anthropic    -                     Anthropic │
│ vertex       -                     Vertex AI │
│ llama-cpp    http://localhost:8000 Custom    │
└──────────────────────────────────────────┘
```

### daf provider active - Show Active Profile

Show the currently active/default model provider profile.

```bash
daf provider active [OPTIONS]
```

**Options:**
- `--json` - Output in JSON format

**Examples:**
```bash
# Show active profile
daf provider active

# JSON output
daf provider active --json
```

**Output example:**
```
Profile: vertex
✓ Default profile

Type: Google Vertex AI

Configuration:
  Vertex Project ID: my-project-123
  Vertex Region: us-east5
```

**When to use:**
- Quick check of which profile is currently active
- Verify current model provider configuration
- Confirm settings before starting a session

**Equivalent to:**
```bash
daf provider show  # Without specifying a profile name
```

### daf provider add - Add Profile

Add a new model provider profile with interactive wizard.

```bash
daf provider add [NAME] [OPTIONS]
```

**Arguments:**
- `NAME` - Profile name (optional, will prompt if not provided)

**Options:**
- `--json` - Output in JSON format

**Examples:**
```bash
# Interactive wizard (recommended)
daf provider add llama-cpp
# - Choose provider type
# - Configure settings interactively
# - Optionally set as default

# Non-interactive (name only, then prompts for details)
daf provider add vertex
```

**Supported Provider Types:**
1. **Anthropic Claude** - Default cloud provider
2. **Google Vertex AI** - Enterprise cloud (requires GCP project)
3. **Local llama.cpp** - Local model server (free, offline)
4. **Custom** - OpenRouter, custom endpoints, etc.

### daf provider remove - Remove Profile

Remove a model provider profile.

```bash
daf provider remove [NAME] [OPTIONS]
```

**Arguments:**
- `NAME` - Profile name (optional, will show list if not provided)

**Options:**
- `--json` - Output in JSON format

**Examples:**
```bash
# Remove specific profile
daf provider remove old-profile

# Interactive selection
daf provider remove
```

**Notes:**
- Requires confirmation before removing
- If removing default profile, automatically sets a new default

### daf provider set-default - Set Default Profile

Set a profile as the default.

```bash
daf provider set-default [NAME] [OPTIONS]
```

**Arguments:**
- `NAME` - Profile name (optional, will show list if not provided)

**Options:**
- `--json` - Output in JSON format

**Examples:**
```bash
# Set specific profile as default
daf provider set-default llama-cpp

# Interactive selection
daf provider set-default
```

**Notes:**
- Default profile is used when no `--model-profile` flag is provided
- Can be overridden per-session with `--model-profile` flag

### daf provider show - Show Profile Configuration

Display configuration for a specific profile.

```bash
daf provider show [NAME] [OPTIONS]
```

**Arguments:**
- `NAME` - Profile name (optional, shows default profile if not provided)

**Options:**
- `--json` - Output in JSON format

**Examples:**
```bash
# Show specific profile
daf provider show vertex

# Show default profile
daf provider show

# JSON output
daf provider show llama-cpp --json
```

**Output example:**
```
Profile: llama-cpp
✓ Default profile

Type: Custom

Configuration:
  Base URL: http://localhost:8000
  Auth Token: llama-cpp
  API Key: (empty)
  Model Name: Qwen3-Coder
```

### daf provider test - Test Profile

Test and validate a profile configuration.

```bash
daf provider test [NAME] [OPTIONS]
```

**Arguments:**
- `NAME` - Profile name (optional, tests default profile if not provided)

**Options:**
- `--json` - Output in JSON format

**Examples:**
```bash
# Test specific profile
daf provider test vertex

# Test default profile
daf provider test

# JSON output
daf provider test llama-cpp --json
```

**What it validates:**
- Required fields are present
- URL formats are correct
- Configuration is internally consistent
- Provider-specific requirements (Vertex AI project ID, etc.)

**Notes:**
- Only validates configuration, does not test actual connectivity
- To test connectivity, use the profile with `daf open` or `daf new`

### Using Profiles

After configuring profiles, use them in daf commands:

```bash
# Use specific profile for a session
daf new PROJ-123 --model-profile llama-cpp

# Profile is remembered - next open uses same profile
daf open PROJ-123

# Override with different profile
daf open PROJ-123 --model-profile vertex

# Environment variable override
MODEL_PROVIDER_PROFILE=llama-cpp daf open PROJ-123
```

**Profile Selection Priority** (highest to lowest):
1. `--model-profile` CLI flag
2. `session.model_profile` (stored from previous `--model-profile`)
3. `MODEL_PROVIDER_PROFILE` environment variable
4. `config.model_provider.default_profile` (set with `daf provider set-default`)
5. Anthropic API (fallback)

### Configuration Location

Model provider profiles are stored in:
- **User**: `~/.daf-sessions/config.json` (`.model_provider`)
- **Team**: `~/.daf-sessions/team.json` (`.model_provider`)
- **Organization**: `~/.daf-sessions/organization.json` (`.model_provider`)
- **Enterprise**: `~/.daf-sessions/enterprise.json` (`.model_provider`)

Profiles merge across levels with user > team > organization > enterprise priority.

### See Also

- [Alternative Model Providers Guide](alternative-model-providers.md) - Detailed setup instructions
- [Configuration Guide](configuration.md) - Configuration hierarchy and schema
- `daf config show` - View merged configuration
