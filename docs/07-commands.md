# Commands Reference

Complete reference for all CLI commands with examples.

## Table of Contents

- [Core Session Commands](#core-session-commands)
- [JIRA Integration Commands](#jira-integration-commands)
- [Notes and Progress](#notes-and-progress)
- [Time Tracking](#time-tracking)
- [Backup and Export](#backup-and-export)
- [Maintenance Commands](#maintenance-commands)
- [Utility Commands](#utility-commands)
- [Using Slash Commands in Multi-Conversation Sessions](#using-slash-commands-in-multi-conversation-sessions)

## Core Session Commands

### daf sync - Sync JIRA Tickets (Recommended Start)

**Most common command for JIRA users** - automatically creates sessions from your assigned tickets.

```bash
daf sync [OPTIONS]
```

**Examples:**
```bash
# Sync current sprint tickets
daf sync --sprint current

# Sync all assigned tickets
daf sync

# Preview what would be synced
daf sync --dry-run

# Sync specific types
daf sync --type Story
daf sync --type Bug

# Sync by epic
daf sync --epic PROJ-36419
```

**What it does:**
1. Fetches your assigned JIRA tickets
2. Filters by sprint/type if specified
3. Creates session groups for new tickets
4. Updates existing sessions with latest JIRA data
5. Shows summary of work ahead

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
- `--name` - Session group name
- `--goal` - What you're trying to accomplish (required; supports file:// paths and http(s):// URLs)
- `--jira` - JIRA ticket key (optional)
- `--path` - Project path (auto-detected if not specified)
- `--branch` - Git branch name (optional)
- `--template` - Template name to use (optional)

**Goal Input Formats:**
- **Plain text**: Any multi-word text is treated as plain text
- **File path (with prefix)**: `file:///path/to/file.md` - reads file content
- **Bare file path**: `/path/to/file.md` or `requirements.md` - must be a single token (no spaces)
- **URL**: `https://example.com/spec.txt` - fetches content from URL

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

# Goal from local file (bare path - must be single token, no spaces)
daf new --name "complex-feature" --goal "/path/to/requirements.md"
daf new --name "complex-feature" --goal "~/Documents/requirements.md"
daf new --name "complex-feature" --goal "requirements.md"

# Goal from URL
daf new --name "spec-impl" --goal "https://docs.example.com/specification.txt"

# Multi-word text with special characters is always treated as plain text
daf new --name "bug-fix" --goal "Fix error in help.py when using --output flag"
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

---

### Multi-Conversation vs Multi-Session Architecture

Understanding the difference between multi-conversation and multi-session is critical for organizing your work effectively.

#### Architecture Overview

The daf tool organizes work into a **3-level hierarchy**:

```
Level 1: Session Group (name: "PROJ-12345")
    │
    ├── Level 2: Session #1 (session_id: 1)
    │   │
    │   ├── Level 3: Conversation (working_dir: backend-api)
    │   │             - project_path: ~/dev/backend-api
    │   │             - branch: aap-12345-backup-feature
    │   │             - ai_agent_session_id: uuid-1a
    │   │
    │   ├── Level 3: Conversation (working_dir: frontend-app)
    │   │             - project_path: ~/dev/frontend-app
    │   │             - branch: aap-12345-backup-feature
    │   │             - ai_agent_session_id: uuid-1b
    │   │
    │   └── Level 3: Conversation (working_dir: shared-lib)
    │                 - project_path: ~/dev/shared-lib
    │                 - branch: aap-12345-backup-feature
    │                 - ai_agent_session_id: uuid-1c
    │
    └── Level 2: Session #2 (session_id: 2)
        │
        ├── Level 3: Conversation (working_dir: backend-api)
        │             - project_path: ~/dev/backend-api
        │             - branch: aap-12345-alternative
        │             - ai_agent_session_id: uuid-2a
        │
        └── Level 3: Conversation (working_dir: docs)
                      - project_path: ~/dev/docs
                      - branch: aap-12345-alternative
                      - ai_agent_session_id: uuid-2b
```

**Key Concepts:**
- **Level 1 - Session Group**: Named container identified by session name or JIRA key (e.g., "PROJ-12345")
  - Groups all related work under one name
  - Can contain multiple sessions (#1, #2, #3...)

- **Level 2 - Session**: Specific work stream with incremental ID (1, 2, 3...)
  - Has its own metadata (goal, status, notes, time tracking)
  - Can have multiple conversations (one per repository)

- **Level 3 - Conversation**: Work in one repository
  - Has its own working directory, project path, branch, and Claude session UUID
  - One conversation = one `.jsonl` file in Claude Code

**What `daf list` shows:**
```bash
daf list
# Output shows SESSIONS (Level 2) with ALL conversations (Level 3):
# Status  Name             JIRA       Summary              Conversations                      Time
# ───────────────────────────────────────────────────────────────────────────────────────────────
#   ⏸    PROJ-12345 (#1)   PROJ-12345  Backup feature       3: backend-api, frontend, sops     2h 30m
#   ▶    PROJ-12345 (#2)   PROJ-12345  Alternative approach 1: backend-api                     1h 15m
```

- Each row is ONE session (Level 2)
- "Conversations" shows COUNT and LIST of all conversation directories (Level 3)
- Active conversation (if session is active) is shown in **bold**
- Use `daf info PROJ-12345` to see detailed information about each conversation

#### Multi-Conversation (Default Behavior)

**What it is:** One logical work session spanning multiple repositories.

**When `daf new` creates a conversation:**
- When you run `daf new --name <NAME>` and a session with that name already exists
- The command adds a NEW conversation to the EXISTING session
- All conversations share the same session metadata (goal, JIRA link, notes, time tracking)

**Example:**
```bash
# First command - creates session #1 with conversation in backend-api
daf new --name PROJ-12345 --goal "Add auth feature" --path ~/projects/backend-api

# Second command - adds conversation to session #1 in frontend-app
daf new --name PROJ-12345 --goal "Add auth feature" --path ~/projects/frontend-app

# Result: 1 session with 2 conversations
daf list
# Shows 1 row:
# PROJ-12345  |  Session #1  |  2 conversations  |  in_progress

daf info PROJ-12345
# Shows:
#   Session #1
#   Conversations:
#     1. backend-api (active)
#     2. frontend-app
```

**Why use multi-conversation:**
- ✅ **Most common use case** - work naturally spans multiple repos
- ✅ Feature touches backend API + frontend + shared library
- ✅ Bug fix requires changes in multiple services
- ✅ Keep all related work in one logical session
- ✅ Unified notes and time tracking across all repos
- ✅ Export/import handles all repos together
- ✅ Use slash commands (`/daf list-conversations`, `/daf read-conversation`) to share context between Claude conversations

**Cross-conversation context sharing:**
See [Using Slash Commands in Multi-Conversation Sessions](#using-slash-commands-in-multi-conversation-sessions) for details on how to use `/daf list-conversations` and `/daf read-conversation` to share context between repositories.

#### Multi-Session (Use `--new-session` flag)

**What it is:** Multiple separate work streams in the same session group.

**When `daf new` creates a session:**
- When you run `daf new --name <NAME> --new-session`
- The command creates a NEW session (increments session_id)
- Each session has its own metadata, notes, and time tracking

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
- `--new-conversation` - Archive current Claude Code conversation and start fresh with a new one
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

# JSON output for automation
daf open PROJ-12345 --json
```

**What happens:**
1. **First time opening:**
   - Prompts for working directory (if not set)
   - Generates Claude session UUID
   - Creates git branch (if configured)
     - **Handles branch conflicts (PROJ-60715)** - See branch conflict resolution above
   - Sends initial prompt to Claude with goal
   - Starts time tracking

2. **Resuming existing:**
   - Loads Claude conversation
   - Checks out git branch
   - **Syncs branch with remote (for imported sessions - PROJ-59820)**
     - Fetches branch from remote if missing locally
     - Merges remote changes if local branch is behind
     - Handles missing remote branches gracefully
   - **Checks if branch is behind base branch (PROJ-59821)**
     - Prompts to sync with base branch (merge or rebase)
     - Auto-fetches to ensure up-to-date comparison
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

List all sessions with optional filtering and pagination.

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
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┓
┃ Status   ┃ Name            ┃ JIRA       ┃ Summary                  ┃ Working Dir ┃  Time ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━┩
│ Active   │ session1 (#1)   │ PROJ-12345  │ Implement backup feature │ backend-api │ 5h 45m│
│ Complete │ session2 (#2)   │ PROJ-12346  │ Fix login bug            │ frontend    │ 1h 20m│
└──────────┴─────────────────┴────────────┴──────────────────────────┴─────────────┴───────┘

Total: 2 sessions | 7h 5m tracked
```

When interactive pagination is active (more than limit sessions):
```
Your Sessions
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┓
┃ Status   ┃ Name            ┃ JIRA       ┃ Summary                  ┃ Working Dir ┃  Time ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━┩
│ Active   │ session1 (#1)   │ PROJ-12345  │ Implement backup feature │ backend-api │ 5h 45m│
│ Complete │ session2 (#2)   │ PROJ-12346  │ Fix login bug            │ frontend    │ 1h 20m│
└──────────┴─────────────────┴────────────┴──────────────────────────┴─────────────┴───────┘

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

**Configuration:**
```bash
daf config set-pr-template-url https://github.com/org/repo/blob/main/PULL_REQUEST_TEMPLATE.md
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
- Session directory (~/.daf-sessions/sessions/<NAME>/)
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
3. Links ticket to session group (prompts if already linked, unless --force or --json is used)
4. Updates all sessions in the group

**Automation support:**
- `--force` flag skips interactive prompts, automatically replacing existing links
- `--json` flag returns machine-readable JSON output and bypasses all prompts
- Both flags enable non-interactive usage in CI/CD pipelines and scripts

---

### daf unlink - Remove JIRA Link

Remove JIRA association from a session.

```bash
daf unlink <NAME-or-JIRA>
```

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

Show currently active Claude Code conversation (if any).

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
- `--goal <TEXT>` - Goal/description for the ticket (supports file:// paths and http(s):// URLs)

**Optional Options:**
- `--name <NAME>` - Session name (auto-generated from goal if not provided)
- `--path <PATH>` - Project path (bypasses interactive repository selection for non-interactive/automation use)
- `--json` - Output in JSON format (for automation and scripting)

**Goal Input Formats:**
- **Plain text**: Any multi-word text is treated as plain text
- **File path (with prefix)**: `file:///path/to/file.md` - reads file content
- **Bare file path**: `/path/to/file.md` or `requirements.md` - must be a single token (no spaces)
- **URL**: `https://example.com/spec.txt` - fetches content from URL

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

# Goal from local requirements file (bare path - must be single token, no spaces)
daf jira new story --parent PROJ-59038 --goal "/path/to/requirements.md"
daf jira new story --parent PROJ-59038 --goal "~/Documents/requirements.md"
daf jira new story --parent PROJ-59038 --goal "requirements.md"

# Goal from remote documentation URL
daf jira new task --parent PROJ-59038 --goal "https://docs.example.com/feature-spec.txt"

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
- `--goal <TEXT>` - Goal/description for the investigation (supports file:// paths and http(s):// URLs)

**Optional Options:**
- `--parent <KEY>` - Optional parent JIRA key (for tracking investigation under an epic)
- `--name <NAME>` - Session name (auto-generated from goal if not provided)
- `--path <PATH>` - Project path (bypasses interactive repository selection)
- `--json` - Output in JSON format (for automation and scripting)

**Goal Input Formats:**
- **Plain text**: Any multi-word text is treated as plain text
- **File path (with prefix)**: `file:///path/to/file.md` - reads file content
- **Bare file path**: `/path/to/file.md` or `requirements.md` - must be a single token (no spaces)
- **URL**: `https://example.com/spec.txt` - fetches content from URL

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

# Goal from local requirements file (bare path)
daf investigate --goal "/path/to/research-notes.md"
daf investigate --goal "~/Documents/investigation-plan.md"

# Goal from remote documentation URL
daf investigate --goal "https://docs.example.com/requirements.txt"

# Non-interactive mode for automation (with --path and --json)
daf investigate \
  --goal "Research database scaling options" \
  --path /path/to/project \
  --json
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

3. **Save findings** using notes (exit Claude Code first):
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
- `--workstream` - Workstream (prompts to save if not in config)
- `--parent` - Parent issue key to link to (epic for story/task/bug, parent for sub-task)
- `--affected-version` - Affected version (bugs only) [default: myproject-ga]
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

# Specify workstream (prompts to save if different from config)
daf jira create bug --summary "Login error" --workstream "Hosted Services"

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

**Workstream Handling:**

1. If workstream in config → uses config value
2. If `--workstream` flag differs from config → prompts to update config
3. If no workstream configured → prompts user, saves to config

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
- Configurable workstream with prompts
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
- `--workstream` - Update workstream
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

# Update workstream
daf jira update PROJ-12345 --workstream Platform

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

The default comment visibility is configured in `~/.daf-sessions/config.json`:

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
daf config tui
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

> **Important:** This command must be run **outside** Claude Code to prevent data conflicts. Exit Claude Code first before adding notes. Inside Claude Code, use `/daf-notes` to view notes (read-only).

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
- Always saved locally in `~/.daf-sessions/sessions/{NAME}/notes.md`
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

Show detailed session information including Claude Code session UUIDs. Displays all conversations (with active and archived Claude sessions) for multi-conversation sessions.

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
  Notes File: ~/.daf-sessions/sessions/implement-backup-feature/notes.md
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
daf repair-conversation $UUID

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

### daf sessions list - View Conversation History

Show all conversations (active + archived) for a session, revealing the full history of Claude Code sessions in each repository.

```bash
daf sessions list <NAME-or-JIRA>
```

**Examples:**
```bash
# View all conversations for a JIRA ticket
daf sessions list PROJ-12345

# View all conversations for a session name
daf sessions list my-session
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
2. **Diagnostic logs are restored** to `~/.daf-sessions/logs/imported/{timestamp}/` (PROJ-60657)
   - Logs are namespaced with a timestamp to avoid conflicts with your current logs
   - This preserves diagnostic history for debugging any issues from the exported session
3. Run `daf open <SESSION>` to select which conversation to work on
4. Tool automatically syncs git branch for the selected conversation (PROJ-61023):
   - **If branch doesn't exist locally**: Automatically fetches and checks out from remote (no prompt to create)
   - **If branch exists locally but is behind**: Prompts to merge or rebase with remote changes
   - **If merge conflicts occur**: Aborts operation with clear resolution instructions
   - Only prompts to create new branch if it doesn't exist on remote either
5. Continue work where teammate left off, with full context from their notes

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
- **Diagnostic logs** (~/.daf-sessions/logs/) - for debugging (PROJ-60657)

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
- **Diagnostic logs are restored** to `~/.daf-sessions/logs/imported/{timestamp}/` (PROJ-60657)
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
- [docs/08-release-management.md](08-release-management.md) - Release management guide
- [CHANGELOG.md](../CHANGELOG.md) - Version history

---

### daf repair-conversation - Repair Corrupted Conversations

Repair corrupted Claude Code conversation files by fixing JSON errors, removing invalid surrogates, and truncating oversized content.

```bash
daf repair-conversation [IDENTIFIER] [OPTIONS]
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
daf repair-conversation PROJ-60039

# Repair by session name
daf repair-conversation my-session

# Repair by UUID (useful when session metadata is missing)
daf repair-conversation f545206f-480f-4c2d-8823-c6643f0e693d

# Repair specific conversation in multi-conversation session
daf repair-conversation PROJ-60039 --conversation-id 1

# Check all sessions for corruption (dry run)
daf repair-conversation --check-all

# Repair all corrupted sessions automatically
daf repair-conversation --all

# Custom truncation size (increase if needed)
daf repair-conversation PROJ-60039 --max-size 15000

# Preview changes without modifying file
daf repair-conversation PROJ-60039 --dry-run
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

### daf cleanup-conversation - Clean Conversation History

Clean up Claude Code conversation history to reduce size and avoid 413 errors.

**CRITICAL:** Must run OUTSIDE of Claude Code (after exiting).

```bash
daf cleanup-conversation <NAME-or-JIRA> [OPTIONS]
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
daf cleanup-conversation PROJ-12345 --older-than 8h

# Keep only last 100 messages
daf cleanup-conversation PROJ-12345 --keep-last 100

# Preview what would be cleaned
daf cleanup-conversation PROJ-12345 --older-than 1d --dry-run

# Clean without confirmation
daf cleanup-conversation PROJ-12345 --older-than 8h --force

# List all backups
daf cleanup-conversation PROJ-12345 --list-backups

# Restore from specific backup
daf cleanup-conversation PROJ-12345 --restore-backup 20251120-163147
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

### daf cleanup-sessions - Fix Orphaned Sessions

Find and fix sessions with missing conversation files.

```bash
daf cleanup-sessions [OPTIONS]
```

**Options:**
- `--dry-run` - Preview what would be cleaned
- `--force` - Skip confirmation

**Examples:**
```bash
# Preview orphaned sessions
daf cleanup-sessions --dry-run

# Clean with confirmation
daf cleanup-sessions

# Clean without confirmation
daf cleanup-sessions --force
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

### daf purge-mock-data - Clear Mock Data

Purge all mock data used for integration testing.

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
```

**What it clears:**
- Mock sessions (`~/.daf-sessions/mocks/sessions.json`)
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

**Note:** This command is specifically for development and testing. It has no effect on production sessions or data.

---

## Utility Commands

### daf check - Check Dependencies

Verify that all required and optional external tools are installed and available.

```bash
daf check [OPTIONS]
```

**Options:**
- `--json` - Output in JSON format for automation

**Examples:**
```bash
# Check all dependencies
daf check

# JSON output for scripting
daf check --json
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

### daf discover - Discover Existing Sessions

Find existing Claude Code sessions not managed by daf tool.

```bash
daf discover
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
- `--goal <GOAL>` - Session goal
- `--name <NAME>` - Session name

**Examples:**
```bash
# Interactive import
daf import-session 7a0bca58-c6c6-4b02-8fbf-9c223cd52a57

# Non-interactive import
daf import-session 7a0bca58... --jira PROJ-12345 --goal "Feature work"
```

**Workflow:**
1. Run `daf discover` to find sessions
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

### daf edit - Edit Session Metadata Interactively

Launch an interactive TUI (Text User Interface) to edit session metadata, manage conversations, and update JIRA integration settings.

```bash
daf edit <NAME-or-JIRA>
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
daf edit PROJ-60989

# Edit by session name
daf edit my-feature-session

# Edit most recent session
daf list  # Get session name
daf edit <session-name>
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
1. Launch editor with `daf edit <identifier>`
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
daf edit my-session
# → Navigate to JIRA Integration tab
# → Update JIRA key field
# → Save
```

**Update Session Goal:**
```bash
# Goal needs clarification
daf edit PROJ-12345
# → Navigate to Core Metadata tab
# → Edit goal field
# → Save
```

**Manage Multi-Repository Conversations:**
```bash
# Working on feature across multiple repos
daf edit cross-repo-feature
# → Navigate to Conversations tab
# → Click "Add Conversation"
# → Enter Claude session UUID, path, and branch
# → Save
```

**Change Session Type:**
```bash
# Converting ticket_creation session to development
daf edit PROJ-60989
# → Navigate to Core Metadata tab
# → Change "Session Type" dropdown
# → Save
```

**Fix Corrupted Metadata:**
```bash
# Session has invalid or missing fields
daf edit broken-session
# → Review and correct fields
# → Validation will show errors
# → Fix errors and save
```

**Notes:**
- Always creates a backup in `~/.daf-sessions/backups/` before saving
- Backup filename format: `session-{name}-{timestamp}.json`
- Validation prevents saving invalid data
- Can cancel changes without saving (no backup created if cancelled)
- Multi-conversation sessions show all conversations in Conversations tab

**See Also:**
- `daf update` - CLI-based metadata updates (simpler, scriptable)
- `daf info` - View current session metadata
- `daf repair-conversation` - Fix corrupted conversation files

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

See [Installation Guide](02-installation.md) for setup instructions.

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
1. Creates `~/.daf-sessions/config.json` with default settings
2. Detects JIRA API token from environment
3. Discovers and caches JIRA custom field mappings (if token available)
4. Prompts to configure project and workstream

**Refresh mode (`--refresh`):**

When config exists, use `daf init --refresh` to update automatically discovered data:
- Refreshes JIRA custom field mappings from JIRA API
- Updates `field_cache_timestamp` in config.json
- **Preserves all user-provided configuration** (URL, workstream, workspace, etc.)
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

Reviewing configuration values...
Current values shown as defaults. Press Enter to keep, or type new value.

=== JIRA Configuration ===

JIRA URL [https://jira.example.com]: https://jira.example.com
JIRA Project Key [PROJ]: MYPROJ
JIRA Username [your-username]: myuser
Which workstream do you work on? [Platform]: Platform

=== Repository Workspace ===

Workspace path [~/development/myproject]: ~/dev/projects

=== Keyword Mappings ===

Current keywords:
  - management: myproject-management-service
  - console: myproject-admin-console

Update keywords? [n]: n

Discovering JIRA custom field mappings...
✓ Found 4 custom fields

✓ Configuration updated
Location: ~/.daf-sessions/config.json

Changes:
  • JIRA URL: https://jira.example.com → https://jira.example.com
  • JIRA Project: PROJ → MYPROJ
  • JIRA User: your-username → myuser
  • Workstream: Platform → Platform
  • Workspace: ~/development/myproject → ~/dev/projects
```

**When to use each mode:**
- `daf init` - First-time setup or switching JIRA instances
- `daf init --refresh` - When JIRA custom fields change (updates mappings only)
- `daf init --reset` - When you need to update multiple configuration values (URL, workstream, workspace, etc.)

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

### daf upgrade - Upgrade Bundled Slash Commands

Install or upgrade the bundled Claude Code slash commands to your workspace.

```bash
daf upgrade [OPTIONS]
```

**Options:**
- `--dry-run` - Preview what would be upgraded without making changes
- `--commands-only` - Upgrade only bundled slash commands (default for now)

**What This Does:**

The `daf upgrade` command manages bundled slash commands that provide helpful prompts for multi-conversation sessions:
- **Installs** commands if they don't exist yet
- **Upgrades** commands if they're outdated
- **Skips** commands that are already up-to-date

Commands are installed to `<workspace>/.claude/commands/` directory.

**Examples:**

```bash
# Upgrade all commands
daf upgrade

# Preview what would be upgraded
daf upgrade --dry-run
```

**Sample Output:**

```
Upgrading bundled slash commands...
Workspace: ~/development/myproject

Results:
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Command                   ┃ Status Before ┃ Status After ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ cs-list-conversations.md  │ not installed │ installed   │
│ cs-read-conversation.md   │ not installed │ installed   │
└───────────────────────────┴───────────────┴─────────────┘

✓ Updated 2 command(s)
Commands location: ~/development/myproject/.claude/commands
```

**Bundled Commands:**

The following slash commands are bundled with the tool (PROJ-60516):

**Multi-Conversation Commands:**
1. **`/daf list-conversations`** - List all conversations in multi-project session
2. **`/daf read-conversation`** - Read conversation history from other repositories

**Session Management Commands:**
3. **`/daf list`** - List all sessions with status and time tracking
4. **`/daf info`** - Show detailed information about current session
5. **`/daf active`** - Show currently active conversation details
6. **`/daf notes`** - View all progress notes for current session (read-only)

**JIRA & Sprint Commands:**
7. **`/daf jira`** - View JIRA ticket details for current session
8. **`/daf status`** - Show sprint status and progress dashboard

**Help & Reference:**
9. **`/daf help`** - Show available daf commands and quick reference
10. **`/daf config`** - View current configuration (JIRA, workspace, prompts)

All commands are READ-ONLY and safe to run inside Claude Code sessions.

**Note:** These commands follow Claude Code plugin documentation standards with YAML frontmatter metadata, ensuring proper integration with Claude Code's `/help` command and future plugin features.

**Alternative: Upgrade via TUI**

You can also upgrade commands using the interactive TUI:

```bash
daf config tui
```

Navigate to the **Claude & AI** tab and click the **Upgrade Commands** button.

**Managing Commands:**

**Installation:**
- Commands are installed automatically when you run `daf upgrade`
- No configuration needed - commands are installed to `<workspace>/.claude/commands/`
- Workspace must be configured first (via `daf init` or `daf config tui`)

**Removal:**
If you want to remove the bundled commands:

```bash
# Remove all bundled commands
rm <workspace>/.claude/commands/cs-*.md

# Or remove specific command
rm <workspace>/.claude/commands/cs-list-conversations.md

# Example (replace with your workspace path):
rm ~/development/myproject/.claude/commands/cs-*.md
```

**Custom Commands:**
You can also create your own custom slash commands by adding `.md` files to the `.claude/commands/` directory. See the [Claude Code documentation](https://docs.anthropic.com/claude/docs/claude-code) for details on command syntax.

**Note:** In the future, `daf upgrade` will also upgrade the daf tool itself. For now, it only manages bundled slash commands.

---

## Using Slash Commands in Multi-Conversation Sessions

When working on features that span multiple repositories, you'll use **multi-conversation sessions** (see [Multi-Conversation vs Multi-Session Architecture](#multi-conversation-vs-multi-session-architecture) for details).

**What is multi-conversation:**
- ONE session with MULTIPLE conversations (one per repository)
- All conversations share the same session metadata (goal, JIRA link, notes)
- Each conversation has its own git branch and Claude Code session
- This is the DEFAULT behavior when running `daf new` with an existing session

**The bundled slash commands** help Claude understand work done in other repositories without losing context in the current conversation. They work WITHIN a single session that has multiple conversations (NOT across multiple sessions).

### Available Slash Commands

After running `daf upgrade`, the following commands are available in Claude Code:

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
daf config tui
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

1. **Always run `daf upgrade`** after updating the tool to get latest slash commands
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
- Tabbed interface for different configuration sections (JIRA, Repository, Prompts, Context Files)
- Input validation for URLs, paths, and required fields
- Tri-state prompt controls (Always/Never/Prompt each time) for workflow automation
- Preview mode before saving (Ctrl+P)
- Automatic backup creation
- Help screen (press `?`)
- Keyboard shortcuts (Ctrl+S to save)

**Configuration Tabs:**
- **JIRA** - JIRA server URL, project, workstream, field mappings, transitions
- **Repository** - Workspace directory, repository detection settings, keywords
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

**Alternative:** Use `daf config tui` (alias for this command)

---

### daf config tui - Interactive Configuration Editor (Alias)

Alias for `daf config edit`. See [daf config edit](#daf-config-edit---interactive-configuration-editor) for details.

```bash
daf config tui
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

### Essential Commands (Daily Use)

```bash
daf sync --sprint current    # Start of sprint
daf status                   # Check sprint progress
daf open PROJ-12345          # Start working
daf note PROJ-12345 "..."    # Track progress (exit Claude first)
daf complete PROJ-12345      # Finish work
```

### Setup Commands (One-Time)

```bash
daf init                    # Initialize config
daf completion              # Setup auto-completion
```

### Maintenance (As Needed)

```bash
daf cleanup-conversation    # Fix 413 errors
daf cleanup-sessions        # Fix orphaned sessions
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
| **Maintenance** |
| `daf cleanup-conversation` | Clean history | No |
| `daf cleanup-sessions` | Fix orphaned | No |
| `daf purge-mock-data` | Clear mock data | No |
| **Configuration** |
| `daf init` | Initialize config | No |
| `daf init --refresh` | Refresh field mappings | Yes |
| `daf init --reset` | Review/update config | No |
| `daf upgrade` | Upgrade slash commands | No |
| `daf config tui` | Interactive configuration | No |
| `daf config refresh-jira-fields` | Refresh field mappings | Yes |
| **Utilities** |
| `daf search` | Search sessions | No |
| `daf discover` | Find sessions | No |
| `daf template` | Manage templates | No |
| `daf edit` | Interactive metadata editor | No |
| `daf update` | CLI metadata updates | No |
| `daf completion` | Auto-completion | No |

## Next Steps

- [Workflows](08-workflows.md) - Step-by-step workflows using these commands
- [Advanced Features](09-advanced.md) - Advanced command usage
- [Troubleshooting](11-troubleshooting.md) - Command errors and solutions

---

## Configuration Management

### Overview

The `daf config set-*` commands have been removed as of version 2.0. Use the alternatives below to configure DevAIFlow.

### Recommended Alternatives

#### Option 1: Use the TUI (Interactive Users)


```bash
daf config tui
```

Features:
- Tab navigation between configuration sections
- Input validation (workstream allowed values, path existence, etc.)
- Real-time error feedback
- Save/cancel workflow
- Shows repo count after workspace changes

#### Option 2: Direct JSON Editing (Automation/Scripts)

For scripts and automation, edit `~/.daf-sessions/config.json` directly:

```bash
# Using jq (recommended for automation)
jq '.jira.project = "PROJ"' ~/.daf-sessions/config.json > /tmp/cfg.json
mv /tmp/cfg.json ~/.daf-sessions/config.json

# Or edit manually
vi ~/.daf-sessions/config.json
```

### Configuration Mapping Reference

| Configuration Setting | TUI Location | JSON Path | Notes |
|-----------------------|--------------|-----------|-------|
| JIRA Project | JIRA Integration → Project Key | `.jira.project` | Normalized to uppercase |
| JIRA Workstream | JIRA Integration → Workstream | `.jira.workstream` | Validated against allowed_values |
| Workspace Directory | Repository → Workspace | `.repos.workspace` | Shows repo count in TUI |
| Affected Version | JIRA Integration → Affected Version | `.jira.affected_version` | - |
| Acceptance Criteria Field | JIRA Integration → Acceptance Criteria Field | `.jira.acceptance_criteria_field` | - |
| Workstream Field | JIRA Integration → Workstream Field | `.jira.workstream_field` | - |
| Epic Link Field | JIRA Integration → Epic Link Field | `.jira.epic_link_field` | - |
| Comment Visibility | JIRA Integration → Comment Visibility | `.jira.comment_visibility_type`, `.jira.comment_visibility_value` | - |
| Transition On Start | JIRA Transitions → On Start | `.jira.transitions.on_start` | JiraTransitionConfig object |
| Transition On Complete | JIRA Transitions → On Complete | `.jira.transitions.on_complete` | JiraTransitionConfig object |
| Prompts | Prompts → Various | `.prompts.*` | Multiple fields |

### Configuration Examples

#### Example 1: Setting JIRA Project

**Using TUI:**
```bash
daf config tui
# Navigate to "JIRA Integration" tab
# Set "Project Key" field to "PROJ"
# Press Save
```

**Direct editing:**
```bash
jq '.jira.project = "PROJ"' ~/.daf-sessions/config.json > /tmp/cfg.json
mv /tmp/cfg.json ~/.daf-sessions/config.json
```

#### Example 2: Setting Workstream with Validation

**Using TUI:**
```bash
daf config tui
# Navigate to "JIRA Integration" tab
# Use dropdown for "Workstream" field (validates against allowed_values)
# Select "Platform"
# Press Save
```

**Direct editing:**
```bash
# Note: No validation when editing directly - ensure value is in allowed_values
jq '.jira.workstream = "Platform"' ~/.daf-sessions/config.json > /tmp/cfg.json
mv /tmp/cfg.json ~/.daf-sessions/config.json
```

#### Example 3: Setting Workspace Directory

**Using TUI:**
```bash
daf config tui
# Navigate to "Repository" tab
# Set "Workspace" field to "~/development"
# TUI shows repo count after save
# Press Save
```

**Direct editing:**
```bash
jq '.repos.workspace = "~/development"' ~/.daf-sessions/config.json > /tmp/cfg.json
mv /tmp/cfg.json ~/.daf-sessions/config.json
```

#### Example 4: Complex Configuration (Transitions)

**Using TUI:**
```bash
daf config tui
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

jq '.jira.transitions.on_start = input' ~/.daf-sessions/config.json /tmp/transition.json > /tmp/cfg.json
mv /tmp/cfg.json ~/.daf-sessions/config.json
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
cat > ~/.daf-sessions/config.json << 'JSON'
{
  "jira": {
    "url": "https://jira.example.com",
    "project": "PROJ",
    "workstream": "Platform"
  },
  "repos": {
    "workspace": "/tmp"
  }
}
JSON
```

**Approach 2: jq for selective updates**
```bash
jq '.jira.project = "PROJ" | .jira.workstream = "Platform" | .repos.workspace = "/tmp"' \
  ~/.daf-sessions/config.json > /tmp/cfg.json && mv /tmp/cfg.json ~/.daf-sessions/config.json
```

### Removal Notice

- **v2.0+**: Commands have been removed entirely

### Getting Help

If you encounter issues during migration:
- Check the [Configuration Guide](06-configuration.md) for detailed config.json schema
- Use `daf config show` to view current configuration
- Use `daf config validate` to check for errors
- Report issues: https://github.com/itdove/devaiflow/issues
