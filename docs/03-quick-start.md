# Quick Start Guide

Get up and running with DevAIFlow in 5 minutes.

## Prerequisites

- DevAIFlow installed ([Installation Guide](02-installation.md))
- Claude Code CLI installed and working
- (Optional) JIRA CLI configured if using JIRA integration
- (Optional) GitHub CLI (`gh`) authenticated if using GitHub integration
- (Optional) GitLab CLI (`glab`) authenticated if using GitLab integration

## Core Concepts

Before diving in, understand these key concepts:

### Session Types

**Single-Project Sessions**
- Work on one repository at a time
- One Git branch per session
- Simplest workflow for focused tasks

**Multi-Project Sessions**
- Work across multiple repositories for one task
- Shared context across all projects
- Each project gets its own Git branch
- Unified time tracking

> **When to use multi-project?** When a single JIRA ticket or GitHub issue requires changes in multiple repositories (e.g., backend API + frontend UI + shared library).

### Entry Points: Create vs Sync

**Path A: Create New Tickets** (Recommended for new work)
```bash
# GitHub
daf git new --goal "Add user authentication to API"

# JIRA
daf jira new story --parent PROJ-12345 --goal "Add user authentication to API"
```

**Why this is better:**
- Claude analyzes the codebase first, understanding implementation complexity
- Creates tickets with accurate descriptions and acceptance criteria
- Safe read-only exploration prevents accidental code changes
- One command handles everything: session creation + Claude launch

**Path B: Sync Existing Tickets** (For already-assigned work)
```bash
# Sync GitHub/GitLab issues from all configured workspaces
daf sync

# Sync JIRA tickets from current sprint
daf sync --sprint current
```

**When to use sync:**
- Working on tickets already created by PM/team
- Sprint has pre-defined backlog
- Bug fixes with clear reproduction steps

> **🔑 Key Difference:** `daf git new`/`daf jira new` creates new tickets WITH Claude's analysis. `daf sync` imports existing assigned tickets.

### Backends

DevAIFlow supports three issue tracker backends:

| Backend | CLI Required | Best For |
|---------|-------------|----------|
| **GitHub Issues** | `gh` (GitHub CLI) | Open source projects, GitHub-centric teams |
| **GitLab Issues** | `glab` (GitLab CLI) | GitLab-centric teams, self-hosted needs |
| **JIRA** | JIRA CLI or API token | Enterprise teams, complex workflows |
| **None** | - | Personal experiments, no ticket tracking |

All backends support the same core features: time tracking, progress notes, session management, and PR/MR creation.

## Your First Session

Choose your path based on whether you're creating new work or working on assigned tickets.

### Path A: Create New Tickets (Recommended!)

This approach uses Claude to analyze your codebase BEFORE creating the ticket, resulting in better-informed issues.

**With GitHub:**
```bash
# 1. Create issue with Claude's analysis
daf git new --goal "Add two-factor authentication"

# 2. Claude analyzes and you ask questions:
#    - "What authentication libraries are currently used?"
#    - "Where should I add the 2FA code?"
#    - "What tests already exist for authentication?"

# 3. Claude creates the issue using:
daf git create \
  --summary "Add two-factor authentication support" \
  --description "..." \
  --acceptance-criteria "User can enable 2FA" \
  --acceptance-criteria "Supports TOTP apps like Google Authenticator"

# 4. Complete the analysis session
daf complete <session-name>

# 5. Open the created issue to implement it
daf open owner-repo-123
```

**With JIRA:**
```bash
# 1. Create ticket with Claude's analysis
daf jira new story --parent PROJ-59038 --goal "Add two-factor authentication"

# 2. Claude analyzes and you ask questions:
#    - "What authentication libraries are currently used?"
#    - "Where should I add the 2FA code?"
#    - "What tests already exist for authentication?"

# 3. Claude creates the ticket using:
daf jira create story \
  --summary "Add two-factor authentication support" \
  --parent PROJ-59038 \
  --description "..." \
  --acceptance-criteria "..."

# 4. Complete the analysis session
daf complete <session-name>

# 5. Open the created ticket to implement it
daf open PROJ-12345
```

**Without Issue Tracker:**
```bash
# Navigate to your project
cd ~/projects/my-app

# Create and open session
daf new --name "api-optimization" --goal "Optimize database queries"
```

### Path B: Sync Existing Tickets

If you already have assigned tickets from sprint planning, sync them:

**With GitHub:**
```bash
# 1. Sync all assigned issues from configured workspaces
daf sync

# 2. See your active sessions
daf list --active

# 3. Open an issue (use session name - no quotes needed!)
daf open owner-repo-123

# 4. Work, exit Claude, add notes
daf note owner-repo-123 "Completed login endpoint"

# 5. Complete the session
daf complete owner-repo-123
```

**With JIRA:**
```bash
# 1. Preview what tickets will be synced
daf sync --dry-run

# 2. Sync current sprint tickets
daf sync --sprint current

# 3. See your sprint status
daf status

# 4. Open a ticket
daf open PROJ-12345

# 5. Work, exit Claude, add notes
daf note PROJ-12345 "Completed login endpoint"

# 6. Complete the session
daf complete PROJ-12345
```

> **💡 Tip:** Session names use dashes (e.g., `owner-repo-60` or `PROJ-12345`) and don't need quotes. Only use quotes when referencing GitHub issue keys with `#` (e.g., `"owner/repo#60"`).

### Work and Track Progress

Once you're in a session, track your progress:

```bash
# Add notes (works inside Claude Code now!)
daf note <session-name> "Completed feature X"

# Add note AND sync to JIRA/GitHub
daf note PROJ-12345 "Ready for review" --jira           # JIRA
daf git add-comment "owner/repo#60" "Ready for review"  # GitHub (needs quotes)
```

### Complete and Close

```bash
daf complete <session-name>
```

The tool will:
1. Ask if you want to commit changes
2. Ask if you want to create a PR/MR
3. Ask if you want to close/transition the ticket
4. Generate an AI summary (optional)
5. Add the summary as a comment
6. Mark the session complete

## Multi-Project Sessions

Work across multiple repositories in a single session with shared context.

### When to Use Multi-Project Sessions

**Common use cases:**
- One JIRA ticket requires changes in multiple repositories (backend API + frontend UI)
- Coordinated updates across microservices
- Shared library changes that affect multiple consumers

**Benefits:**
- All work for one ticket stays together
- Unified time tracking across repositories
- Claude has shared context across all projects
- Each repository gets its own Git branch
- One `daf complete` creates PRs/MRs for all projects

### Creating Multi-Project Sessions

**Declarative Approach** (All at once):
```bash
# Create session spanning multiple projects
daf new PROJ-123 -w primary --projects backend-api,frontend-app,shared-lib

# System prompts for base branch per project:
#   backend-api: branch from main
#   frontend-app: branch from develop
#   shared-lib: branch from main
```

**Iterative Approach** (Add as you go):
```bash
# 1. First open: Select backend repository
daf open PROJ-12345
# Prompts: Which project? Select "backend-api"

# Work in backend, then exit Claude Code...

# 2. Second open: Add frontend repository
daf open PROJ-12345
# Shows existing conversations and option to create new one
# Select "Create new conversation (in a different project)"
# Prompts: Which project? Select "frontend-app"

# Work in frontend, then exit Claude Code...

# 3. Complete creates PRs for both projects
daf complete PROJ-12345
```

### Comparison: Declarative vs Iterative

| Approach | When to Use | Pros | Cons |
|----------|-------------|------|------|
| **Declarative** (`--projects` flag) | You know all repositories upfront | Faster setup, all branches created at once | Requires workspace configuration |
| **Iterative** (sequential opens) | Discover repositories as you work | More flexible, add repositories on-demand | Manual per-repository setup |

> **💡 Recommendation:** Use declarative for planned multi-repo work. Use iterative for exploratory work where you discover dependencies as you go.

### Viewing Multi-Project Sessions

```bash
# See all projects in current session
daf active

# List all conversations in session
/daf-list-conversations  # Inside Claude Code
```

Example output:
```
╭────────────────────── ▶ Currently Active ──────────────────────╮
│                                                                 │
│  DAF Session: PROJ-12345 (#1)                                  │
│  Type: Multi-project (2 projects)                              │
│  Workspace: /Users/you/development                             │
│  Goal: Add user profile feature across stack                  │
│  Time (this work session): 2h 15m                             │
│  Status: in_progress                                           │
│                                                                 │
│  Projects in this session:                                     │
│    • backend-api (branch: feature/PROJ-12345)                  │
│    • frontend-app (branch: feature/PROJ-12345-ui)              │
│                                                                 │
╰─────────────────────────────────────────────────────────────────╯
```

## Common Scenarios

These scenarios demonstrate advanced workflows. Most users can skip this section initially.

### Scenario 1: Quick Experiment (No Issue Tracker)

```bash
cd ~/experiments
daf new --name "test-redis" --goal "Test Redis caching performance"
daf open test-redis
# ... experiment ...
daf delete test-redis  # Clean up when done
```

### Scenario 2: Resume Yesterday's Work

```bash
# List recent sessions
daf list --since "yesterday"

# Open one
daf open PROJ-12345

# See what you did
daf summary PROJ-12345
```

### Scenario 3: Long-Running Session (Cleanup)

If you hit "413 Prompt too long" errors:

```bash
# 1. Exit Claude Code first!
# 2. Clean up old messages
daf cleanup-conversation PROJ-12345 --older-than 8h

# 3. Reopen
daf open PROJ-12345
```

### Scenario 4: Session Templates

```bash
# Save successful session as template
daf template save backend-api my-backend-template

# Reuse for similar work
daf new --name "new-endpoint" --goal "..." --template my-backend-template
```

## Useful Commands

### Session Management

```bash
daf new --name "..." --goal "..."           # Create session
daf open <name-or-jira>                     # Resume session
daf list                                    # List all sessions
daf list --active                           # List active only
daf delete <name-or-jira>                   # Delete session
```

### Notes and Progress

```bash
daf note <name> "Your note"                 # Add local note (run outside Claude Code)
daf note <name> "Your note" --jira          # Add note + JIRA comment (run outside Claude Code)
daf summary <name>                          # View session summary
daf time <name>                             # View time spent
```

### Issue Tracker Integration

**JIRA:**
```bash
daf jira new <type> --parent <key> --goal "..."  # Create ticket with analysis
daf sync                                          # Sync assigned tickets
daf sync --sprint current                         # Sync current sprint
daf jira view PROJ-12345                          # View JIRA ticket details
daf link <name> --jira PROJ-12345                 # Link JIRA to session
daf unlink <name>                                # Remove JIRA link
daf status                                        # Sprint dashboard
```

**GitHub/GitLab:**
```bash
daf git new --goal "..."                             # Create issue with analysis
daf git create --summary "..." --description "..."   # Create issue directly
daf sync                                             # Sync assigned issues from all repos
daf git view "owner/repo#123"                        # View issue details (quotes required)
daf git open "owner/repo#123"                        # Open issue in new session (quotes required)
daf git update "owner/repo#123" --comment "..."      # Add comment to issue (quotes required)
daf git add-comment "owner/repo#123" "..."           # Add comment (quotes required)
```

### Utilities

```bash
daf cleanup-conversation <name> --older-than 8h    # Clean old messages
daf cleanup-sessions                               # Fix orphaned sessions
daf export <name> --output session.tar.gz          # Export session
daf template save <name> my-template               # Save as template
```

## Tips for Success

### 1. Use Descriptive Names

Good:
```bash
daf new --name "user-auth-api" --goal "..."
```

Bad:
```bash
daf new --name "test123" --goal "..."
```

### 2. Always Quote GitHub Issue Keys

The `#` character starts comments in bash, so always quote issue keys:

Good:
```bash
daf git open "owner/repo#60"
daf git add-comment "owner/repo#60" "Fixed bug"
```

Bad:
```bash
daf git open owner/repo#60  # This won't work! Everything after # is a comment
```

Better: Use session names (no quotes needed):
```bash
daf open owner-repo-60      # Session name - safe, no quotes required
```

### 3. Add Notes Regularly

Notes help you remember what you did (exit Claude Code first):
```bash
daf note "Completed database migration"
daf note "Found bug in UserService.authenticate()"
```

### 4. Use Templates for Similar Work

```bash
# Save successful session as template
daf template save backend-api my-backend-template

# Reuse for similar work
daf new --name "new-endpoint" --goal "..." --template my-backend-template
```

### 5. Clean Up Completed Sessions

Review and delete old sessions periodically:
```bash
daf list --status complete
daf delete old-session-name
```

Or export them first:
```bash
daf export --all --output backup.tar.gz
daf delete --all
```

### 6. Use --dry-run to Preview

Many commands support `--dry-run`:
```bash
daf sync --dry-run
daf cleanup-conversation PROJ-12345 --older-than 8h --dry-run
daf cleanup-sessions --dry-run
```

## Troubleshooting Quick Issues

**Session won't open:**
```bash
# Check if conversation file exists
daf cleanup-sessions --dry-run

# Fix orphaned sessions
daf cleanup-sessions
```

**JIRA sync not working:**
```bash
# Test JIRA CLI
jira me

# Check config
cat $DEVAIFLOW_HOME/config.json
```

**GitHub sync not working:**
```bash
# Test GitHub CLI authentication
gh auth status

# Re-authenticate if needed
gh auth login

# Check if you have assigned issues
gh issue list --assignee @me
```

**GitLab sync not working:**
```bash
# Test GitLab CLI authentication
glab auth status

# Re-authenticate if needed
glab auth login

# Check if you have assigned issues
glab issue list --assignee @me
```

**Can't find session:**
```bash
# List all sessions
daf list --all

# Search by keyword
daf search "auth"
```

## Next Steps

- [Session Management Guide](04-session-management.md) - Deep dive into sessions
- [JIRA Integration](05-2-jira-integration.md) - Learn JIRA workflows
- [GitHub Integration](github-integration.md) - Learn GitHub/GitLab workflows
- [Commands Reference](07-commands.md) - All available commands
- [Common Workflows](08-workflows.md) - Step-by-step guides
