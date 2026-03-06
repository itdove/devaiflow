# Quick Start Guide

Get up and running with DevAIFlow in 5 minutes.

## Prerequisites

- DevAIFlow installed ([Installation Guide](02-installation.md))
- Claude Code CLI installed and working
- (Optional) JIRA CLI configured if using JIRA integration
- (Optional) GitHub CLI (`gh`) authenticated if using GitHub integration
- (Optional) GitLab CLI (`glab`) authenticated if using GitLab integration

## Your First Session (With GitHub)

### 1. Create a Well-Researched Issue (Recommended!)

The best way to start with GitHub is to create a well-researched issue using Claude's codebase analysis:

```bash
# Create an issue with Claude's help
daf git new --goal "Add user authentication to API"
```

This will:
1. Create an analysis-only session (no code changes, no branches)
2. Launch Claude to analyze your codebase
3. Help you create a detailed GitHub issue with proper context

**Why this is better:**
- Claude analyzes the codebase first, understanding implementation complexity
- Creates issues with accurate descriptions and acceptance criteria
- Safe read-only exploration prevents accidental code changes
- One command handles everything: session creation + Claude launch

**Example workflow:**
```bash
# 1. Create issue with analysis
daf git new --goal "Add two-factor authentication"

# 2. Claude will analyze the codebase and you can ask questions like:
#    - "What authentication libraries are currently used?"
#    - "Where should I add the 2FA code?"
#    - "What tests already exist for authentication?"

# 3. When ready, Claude creates the issue using:
daf git create \
  --summary "Add two-factor authentication support" \
  --description "..." \
  --acceptance-criteria "User can enable 2FA" \
  --acceptance-criteria "Supports TOTP apps like Google Authenticator"
```

**Note:** GitHub doesn't have issue types like JIRA. The `--type` flag is optional and only adds a label (bug, enhancement, task) if specified.

### Alternative: Sync Existing Issues

If you already have assigned issues, you can sync them instead:

```bash
# Sync GitHub issues from all configured workspaces
daf sync
```

This automatically creates sessions for all your assigned GitHub issues across all repositories in your configured workspaces.

### 2. Open a Session

```bash
# Recommended: Use session name (created by daf sync)
daf open owner-repo-60

# Alternative: Use issue key with quotes (bash requires quotes due to #)
daf git open "owner/repo#60"
```

On first open, you'll be prompted to select a working directory if it can't be auto-detected from the issue repository.

> **Tip:** Session names use dashes (e.g., `owner-repo-60`) because they're used as directory names. Always use quotes when referencing issue keys with `#` in bash commands to prevent the `#` from being treated as a comment.

### 3. Work and Track Progress

Exit Claude Code first, then add notes:

```bash
# Add notes (saved locally)
daf note owner-repo-60 "Completed login endpoint"

# Add note AND GitHub comment (use quotes around issue key)
daf git add-comment "owner/repo#60" "Ready for code review"
```

> **Note:** `daf note` cannot be run inside Claude Code. Exit first, then add notes. Inside Claude Code, use `/daf-notes` to view notes (read-only).

### 4. Check Your Status

```bash
daf list --active
```

Output:
```
Sessions (2):

📋 owner-repo-60
   🎯 owner/repo#60: Add two-factor authentication
   📁 my-app
   📊 in_progress
   ⏱️  2h 30m

📋 owner-repo-61
   🎯 owner/repo#61: Fix password reset
   📁 my-app
   📊 in_progress
   ⏱️  1h 15m
```

### 5. Complete and Close Issue

```bash
daf complete owner-repo-60
```

The tool will:
1. Ask if you want to commit changes
2. Ask if you want to create a PR
3. Ask if you want to close the GitHub issue (default: No)
4. Generate an AI summary (optional)
5. Add the summary as a GitHub comment
6. Mark the session complete

**GitHub closing behavior:**
- By default, issues remain open (you can close via PR)
- Prompts you to close: `Close GitHub issue owner/repo#60? (y/N)`
- Or configure auto-close: `config.github.auto_close_on_complete = true`

## Your First Session (With JIRA)

### 1. Create a Well-Researched Ticket (Recommended!)

The best way to start with JIRA is to create a well-researched ticket using Claude's codebase analysis:

```bash
# Create a story ticket with Claude's help
daf jira new story --parent PROJ-12345 --goal "Add user authentication to API"
```

This will:
1. Create an analysis-only session (no code changes, no branches)
2. Launch Claude to analyze your codebase
3. Help you create a detailed JIRA ticket with proper context

**Why this is better:**
- Claude analyzes the codebase first, understanding implementation complexity
- Creates tickets with accurate descriptions and acceptance criteria
- Safe read-only exploration prevents accidental code changes
- One command handles everything: session creation + Claude launch

**Example workflow:**
```bash
# 1. Create ticket with analysis
daf jira new story --parent PROJ-59038 --goal "Add two-factor authentication"

# 2. Claude will analyze the codebase and you can ask questions like:
#    - "What authentication libraries are currently used?"
#    - "Where should I add the 2FA code?"
#    - "What tests already exist for authentication?"

# 3. When ready, Claude creates the ticket using:
daf jira create story \
  --summary "Add two-factor authentication support" \
  --parent PROJ-59038 \
  --description "..." \
  --acceptance-criteria "..."
```

### Alternative: Sync Existing Tickets

If you already have assigned tickets, you can sync them instead:

```bash
# See what tickets you have assigned
daf sync --dry-run

# Actually sync them
daf sync --sprint current
```

This automatically creates sessions for all your assigned tickets (including tickets you just created in the previous step, once they're assigned to you, pointed, and added to a sprint).

### 2. Open a Session

```bash
# Open by JIRA key (works for both synced and created tickets)
daf open PROJ-12345
```

On first open, you'll be prompted to select a working directory. The tool suggests repositories based on the JIRA ticket summary.

### 3. Work and Track Progress

Exit Claude Code first, then add notes:

```bash
# Add notes (saved locally)
daf note PROJ-12345 "Completed login endpoint"

# Add note AND sync to JIRA
daf note PROJ-12345 "Ready for code review" --jira
```

> **Note:** `daf note` cannot be run inside Claude Code. Exit first, then add notes. Inside Claude Code, use `/daf-notes` to view notes (read-only).

### 4. Check Your Sprint Status

```bash
daf status
```

Output:
```
Current Sprint: 2025-01

In Progress:
🚧 PROJ-12345  User authentication       5 pts | 2h 30m
🚧 PROJ-12346  Fix password reset        3 pts | 1h 15m

Ready to Start:
🆕 PROJ-12347  Add 2FA support          8 pts
```

### 5. Complete and Transition JIRA

```bash
daf complete PROJ-12345
```

The tool will:
1. Ask if you want to transition the JIRA ticket
2. Show available transitions (e.g., "In Progress → Code Review")
3. Generate an AI summary (optional)
4. Add the summary as a JIRA comment
5. Mark the session complete

## Your First Session (Without JIRA)

### 1. Create a Session

```bash
# Navigate to your project
cd ~/projects/my-app

# Create a new session
daf new --name "api-optimization" --goal "Optimize database queries"
```

You'll see:
```
✓ Created session for api-optimization (#1)

📋 Session: api-optimization (#1)
🎯 Goal: Optimize database queries
📁 Working Directory: my-app
📂 Path: /Users/you/projects/my-app
🆔 Claude Session ID: abc123...

Launch Claude Code now? [Y/n]:
```

Press `y` to launch Claude Code.

### 2. Work in Claude Code

Claude Code will open with your goal as the initial prompt. Work on your task as normal.

### 3. Add Progress Notes

Exit Claude Code, then add notes:

```bash
daf note "api-optimization" "Identified slow queries in UserController"
daf note "api-optimization" "Added database indexes for user lookups"
```

> **Note:** `daf note` must be run outside Claude Code to prevent data conflicts. Inside Claude Code, use `/daf-notes` to view notes.

### 4. View Your Sessions

```bash
daf list
```

Output:
```
Sessions (1):

📋 api-optimization (#1)
   🎯 Optimize database queries
   📁 my-app
   📊 in_progress
   ⏱️  45m
```

### 5. Resume Later

Close Claude Code when done. Resume anytime:

```bash
daf open api-optimization
```

### 6. Complete the Session

When finished:

```bash
daf complete api-optimization
```

## Common Scenarios

### Scenario 1: Start of Sprint (JIRA Users)

Two common workflows for JIRA users:

#### Workflow A: Create New Tickets (Recommended for new features)

Use this when planning new work items or breaking down epics into stories:

```bash
# 1. Create a well-researched story with Claude's analysis
daf jira new story --parent PROJ-59038 --goal "Add pagination to user list API"

# 2. Claude analyzes codebase and helps you understand:
#    - Current API patterns
#    - Pagination implementations already in use
#    - Testing patterns
#    - Complexity and dependencies

# 3. Create the ticket with informed description and acceptance criteria
# (Claude will guide you through using daf jira create command)

# 4. Complete the analysis session
daf complete <session-name>

# 5. Now open the created ticket to implement it
daf open PROJ-12345  # The ticket you just created
```

**When to use this workflow:**
- Planning new features or enhancements
- Breaking down epics into detailed stories
- Need to understand codebase before estimating effort
- Want accurate acceptance criteria based on actual architecture

#### Workflow B: Work on Assigned Tickets

Use this when you already have assigned tickets from sprint planning:

```bash
# 1. Beginning of sprint - sync all your assigned tickets
daf sync --sprint current

# 2. See your sprint status
daf status

# 3. Start working on a ticket
daf open PROJ-12345

# 4. Work, exit Claude, add notes, complete
# (Exit Claude Code before running daf note)
daf note PROJ-12345 "Implemented feature X"
daf complete PROJ-12345
```

**When to use this workflow:**
- Working on tickets already created by PM/team
- Sprint has pre-defined backlog
- Implementing well-defined requirements
- Bug fixes with clear reproduction steps

### Scenario 1b: Start of Sprint (GitHub Users)

Similar to JIRA workflows, GitHub users have two approaches:

#### Workflow A: Create New Issues (Recommended for new features)

Use this when planning new work items:

```bash
# 1. Create a well-researched issue with Claude's analysis
daf git new --goal "Add pagination to user list API"

# 2. Claude analyzes codebase and helps you understand:
#    - Current API patterns
#    - Pagination implementations already in use
#    - Testing patterns
#    - Complexity and dependencies

# 3. Create the issue with informed description and acceptance criteria
# (Claude will guide you through using daf git create command)

# 4. Complete the analysis session
daf complete <session-name>

# 5. Now open the created issue to implement it
daf open owner-repo-123  # The issue you just created
```

**When to use this workflow:**
- Planning new features or enhancements
- Need to understand codebase before implementing
- Want accurate acceptance criteria based on actual architecture
- Working in open-source projects where you create your own issues

#### Workflow B: Work on Assigned Issues

Use this when you already have assigned issues:

```bash
# 1. Sync all your assigned issues from configured workspaces
daf sync

# 2. See your active sessions
daf list --active

# 3. Start working on an issue
daf open owner-repo-123

# 4. Work, exit Claude, add notes, complete
# (Exit Claude Code before running daf note)
daf note owner-repo-123 "Implemented feature X"
daf complete owner-repo-123
```

**When to use this workflow:**
- Working on issues assigned by maintainers/team
- Contributing to projects with established issue tracking
- Bug fixes with clear reproduction steps
- Issues created during planning meetings

### Scenario 2: Working Across Multiple Repositories (Multi-Conversation Sessions)

**Common Use Case:** One JIRA ticket requires changes in multiple repositories (e.g., backend API + frontend UI).

**Recommended Approach:** Use multi-conversation sessions to keep all related work under one session with unified time tracking.

```bash
# Create or sync the session
daf sync --sprint current
# Or: daf new --jira PROJ-12345 --goal "Add user profile feature"

# First time: Open for backend work
daf open PROJ-12345

# You'll be prompted to select a repository:
Available repositories (8):
  1. backend-api
  2. frontend-app
  3. mobile-app
  ...

Which project? [1-8]: 1

# Work in backend, make changes, then exit Claude Code...

# Continue same session in frontend repository
daf open PROJ-12345

# You'll see the existing conversation and option to create new one:
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
  3. mobile-app
  ...

Which project? [1-3]: 2

# Now working in frontend with separate conversation...
```

**Result:** One session (PROJ-12345) with multiple conversations:
- Unified time tracking across all repositories
- Single JIRA ticket link
- Separate Claude Code conversation history per repository
- Easy to switch between with `daf open PROJ-12345`

**Benefits:**
- All work for one ticket stays together
- Time tracking counts work across all repositories
- Easier to manage with `daf status`, `daf list`
- Each repository gets its own Git branch

### Scenario 3: Quick Experiment (No JIRA)

```bash
cd ~/experiments
daf new --name "test-redis" --goal "Test Redis caching performance"
daf open test-redis
# ... experiment ...
daf delete test-redis  # Clean up when done
```

### Scenario 4: Resume Yesterday's Work

```bash
# List recent sessions
daf list --since "yesterday"

# Open one
daf open PROJ-12345

# See what you did
daf summary PROJ-12345
```

### Scenario 5: Long-Running Session (Cleanup)

If you hit "413 Prompt too long" errors:

```bash
# 1. Exit Claude Code first!
# 2. Clean up old messages
daf cleanup-conversation PROJ-12345 --older-than 8h

# 3. Reopen
daf open PROJ-12345
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

### JIRA Integration

```bash
daf jira new <type> --parent <key> --goal "..."  # Create ticket with analysis
daf sync                                          # Sync assigned tickets
daf sync --sprint current                         # Sync current sprint
daf jira view PROJ-12345                          # View JIRA ticket details
daf link <name> --jira PROJ-12345                 # Link JIRA to session
daf unlink <name>                                # Remove JIRA link
daf status                                        # Sprint dashboard
```

### GitHub/GitLab Integration

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
