# DevAIFlow Complete Workflows

Comprehensive guide to all DevAIFlow workflows with step-by-step examples.

## Table of Contents

1. [Workflow 1: Create Tickets with Codebase Analysis](#workflow-1-create-tickets-with-codebase-analysis)
2. [Workflow 2: Sync and Work on Existing Tickets](#workflow-2-sync-and-work-on-existing-tickets)
3. [Workflow 3: Multi-Project Development](#workflow-3-multi-project-development)
4. [Workflow 4: Team Collaboration via Export/Import](#workflow-4-team-collaboration-via-exportimport)
5. [Workflow 5: Session Templates for Repeated Tasks](#workflow-5-session-templates-for-repeated-tasks)

---

## Workflow 1: Create Tickets with Codebase Analysis

**Best for:** New feature work where you need to understand the codebase first.

**Why this approach:** Claude analyzes your codebase BEFORE creating the ticket, resulting in better-informed issues with accurate descriptions and acceptance criteria.

### With JIRA

```bash
# Step 1: Start analysis session
daf jira new story --parent PROJ-59038 --goal "Add two-factor authentication"

# Step 2: Claude Code launches - ask questions to understand codebase:
#   - "What authentication libraries are currently used?"
#   - "Where should I add the 2FA code?"
#   - "What tests exist for authentication?"

# Step 3: Claude creates the ticket using analysis insights:
daf jira create story \
  --summary "Add two-factor authentication support" \
  --parent PROJ-59038 \
  --components backend \
  --description "h3. *User Story*

As a user, I want two-factor authentication so that my account is more secure.

h3. *Supporting documentation*

Current authentication uses JWT tokens with UserService.authenticate()
Located in: src/auth/user_service.py

h3. Requirements
* TOTP support (Google Authenticator compatible)
* QR code generation for setup
* Backup codes for recovery
* Integration with existing JWT flow

h3. End to End Test
# Step 1: User enables 2FA in settings
# Step 2: System generates QR code
# Step 3: User scans with authenticator app
# Step 4: User enters TOTP code to verify
" \
  --field acceptance_criteria="$(cat <<'EOF'
- [] TOTP authentication integrated with UserService
- [] QR code generation working
- [] Backup codes generated and stored securely
- [] Tests cover TOTP validation and backup codes
- [] End to end test passes: User can enable 2FA
- [] End to end test passes: User can login with TOTP
- [] End to end test passes: User can use backup codes
EOF
)"

# Step 4: Complete analysis session
daf complete <session-name>

# Step 5: Open the created ticket to implement
daf open PROJ-12345
```

### With GitHub/GitLab

```bash
# Step 1: Start analysis session
daf git new --goal "Add two-factor authentication to API"

# Step 2: Claude analyzes codebase (same as JIRA workflow)

# Step 3: Create informed issue
daf git create \
  --summary "Add two-factor authentication support" \
  --description "## Overview

Implement TOTP-based 2FA for user accounts.

### Current State
- Authentication uses JWT tokens
- UserService.authenticate() in src/auth/user_service.py

### Requirements
- TOTP support (Google Authenticator compatible)
- QR code generation
- Backup codes
- Integration with JWT flow

### Testing
- [ ] TOTP validation tests
- [ ] QR code generation tests
- [ ] Backup code tests
- [ ] End-to-end: User can enable 2FA
- [ ] End-to-end: User can login with TOTP
- [ ] End-to-end: User can use backup codes
" \
  --labels "enhancement,backend"

# Step 4: Complete analysis, open issue to implement
daf complete <session-name>
daf open owner-repo-123
```

---

## Workflow 2: Sync and Work on Existing Tickets

**Best for:** Working on tickets already created by PM/team during sprint planning.

### JIRA Workflow

```bash
# Step 1: Preview what will be synced
daf sync --dry-run

# Step 2: Sync assigned tickets from current sprint
daf sync --sprint current

# Expected output:
#   Would create sessions for:
#   PROJ-12345: Implement backup feature (Story, 5 points)
#   PROJ-12346: Fix password reset (Bug)

# Step 3: View sprint dashboard
daf status

# Step 4: Open a ticket
daf open PROJ-12345

# Step 5: Work in Claude Code session
#   - Make code changes
#   - Run tests
#   - Verify acceptance criteria

# Step 6: Track progress (exit Claude first)
daf note PROJ-12345 "Completed backup API endpoint"
daf note PROJ-12345 "Added tests for restore functionality"

# Step 7: Complete session
daf complete PROJ-12345
#   Tool will ask:
#   - Commit changes? (yes/no)
#   - Create PR? (yes/no)
#   - Transition ticket? (yes/no)
#   - Generate AI summary? (yes/no)
```

### GitHub/GitLab Workflow

```bash
# Step 1: Sync all assigned issues from configured workspaces
daf sync

# Expected output:
#   Synced repositories:
#   - owner/backend-api: 2 issues
#   - owner/frontend-app: 1 issue

# Step 2: List active sessions
daf list --active

# Step 3: Open an issue (use session name - no quotes!)
daf open owner-repo-123

# Step 4: Work and track progress (exit Claude first)
daf note owner-repo-123 "Completed login endpoint"
daf git add-comment "owner/repo#123" "Implementation ready for review"

# Step 5: Complete session
daf complete owner-repo-123
#   Creates PR with:
#   - Summary of changes
#   - Links to issue
#   - AI-generated description
```

---

## Workflow 3: Multi-Project Development

**Best for:** One ticket requires changes across multiple repositories (e.g., backend API + frontend UI).

### Approach A: Declarative (All at Once)

**When to use:** You know all required repositories upfront.

```bash
# Step 1: Create multi-project session
daf new PROJ-12345 -w primary --projects backend-api,frontend-app,shared-lib

# System prompts for base branch per project:
#   backend-api: branch from? → main
#   frontend-app: branch from? → develop
#   shared-lib: branch from? → main

# Step 2: Claude Code launches with SHARED CONTEXT across all projects
#   - Can reference code from any project
#   - Coordinate changes across repositories
#   - Maintain consistency

# Step 3: Work across projects
#   Make changes in backend-api, frontend-app, shared-lib
#   Claude understands the full context

# Step 4: Complete creates PRs for all projects
daf complete PROJ-12345
#   Creates 3 PRs:
#   - backend-api: PR #45
#   - frontend-app: PR #67
#   - shared-lib: PR #12
```

### Approach B: Iterative (Add as You Go)

**When to use:** Discover repository dependencies as you work.

```bash
# Step 1: Start with backend
daf open PROJ-12345
#   Prompt: Which project? → backend-api
#   Creates conversation in backend-api

# Work on backend...
# (exit Claude Code)

# Step 2: Add frontend repository
daf open PROJ-12345
#   Shows:
#   - Existing conversations:
#     • backend-api (branch: feature/PROJ-12345)
#   - Create new conversation (in a different project)
#
#   Select: Create new conversation
#   Prompt: Which project? → frontend-app

# Work on frontend...
# (exit Claude Code)

# Step 3: Complete creates PRs for both
daf complete PROJ-12345
#   Creates 2 PRs:
#   - backend-api: PR #45
#   - frontend-app: PR #67
```

### Viewing Multi-Project Sessions

```bash
# See all projects in current session
daf active

# Output:
#   ╭────────────────────── ▶ Currently Active ──────────────────────╮
#   │ DAF Session: PROJ-12345 (#1)                                  │
#   │ Type: Multi-project (3 projects)                              │
#   │ Workspace: /Users/you/development                             │
#   │ Time (this work session): 2h 15m                              │
#   │                                                                 │
#   │ Projects in this session:                                     │
#   │   • backend-api (branch: feature/PROJ-12345)                  │
#   │   • frontend-app (branch: feature/PROJ-12345-ui)              │
#   │   • shared-lib (branch: feature/PROJ-12345-shared)            │
#   ╰─────────────────────────────────────────────────────────────────╯

# List all conversations in session
daf info PROJ-12345
```

---

## Workflow 4: Team Collaboration via Export/Import

**Best for:** Handoff work between team members or backup sessions for review.

### Export Session

```bash
# Export single session
daf export PROJ-12345 --output backup.tar.gz

# Export all sessions
daf export --all --output team-backup-$(date +%Y%m%d).tar.gz

# Export with notes and summaries
daf export PROJ-12345 --include-notes --include-summary --output handoff.tar.gz
```

### Import Session

```bash
# Import session
daf import backup.tar.gz

# Import and resume immediately
daf import handoff.tar.gz
daf open PROJ-12345
```

### Team Handoff Scenario

```bash
# Developer A: Export session
daf export PROJ-12345 --output proj-12345-handoff.tar.gz
# Send file to Developer B

# Developer B: Import and continue
daf import proj-12345-handoff.tar.gz
daf open PROJ-12345
# Continue work with full context
```

---

## Workflow 5: Session Templates for Repeated Tasks

**Best for:** Standardizing common workflows (e.g., backend API endpoints, bug investigations).

### Create Template

```bash
# Step 1: Complete successful session
daf open PROJ-12345
# Work on backend API endpoint...
daf complete PROJ-12345

# Step 2: Save as template
daf template save PROJ-12345 backend-api-endpoint

# Template includes:
#   - Project structure
#   - Common files to modify
#   - Typical workflow steps
```

### Use Template

```bash
# Create new session from template
daf new --name "subscription-endpoint" \
        --goal "Add subscription API endpoint" \
        --template backend-api-endpoint

# Session pre-configured with:
#   - Expected project paths
#   - Common starting files
#   - Standard workflow
```

### List and Manage Templates

```bash
# List available templates
daf template list

# Delete template
daf template delete old-template

# Export template for team
daf template export backend-api-endpoint --output api-template.tar.gz

# Import template
daf template import api-template.tar.gz
```

---

## Common Scenarios

### Resume Yesterday's Work

```bash
# List recent sessions
daf list --since "yesterday"

# Open most recent
daf open <session-name>

# See what you did
daf summary <session-name>
daf notes <session-name>
```

### Long-Running Session Cleanup

If you hit "413 Prompt too long" errors:

```bash
# Step 1: Exit Claude Code

# Step 2: Clean old messages
daf maintenance cleanup-conversation PROJ-12345 --older-than 8h --dry-run
daf maintenance cleanup-conversation PROJ-12345 --older-than 8h

# Step 3: Reopen
daf open PROJ-12345
```

### Quick Experiment (No Issue Tracker)

```bash
# Create experimental session
cd ~/experiments
daf new --name "test-redis" --goal "Test Redis caching performance"

# Work...
daf open test-redis

# Clean up when done
daf delete test-redis
```

### Concurrent Work (Multiple Workspaces)

```bash
# Terminal 1: Main work
daf new PROJ-123 -w primary --path ~/development/myproject
daf open PROJ-123

# Terminal 2: Experimental branch
daf new PROJ-123 -w experiments --path ~/experiments/myproject
daf open PROJ-123

# No conflicts - different workspaces!
```

---

## Workflow Decision Tree

**Starting new work?**
- Known implementation → `daf jira create` / `daf git create`
- Need analysis → `daf jira new` / `daf git new` ✅

**Working on assigned tickets?**
- JIRA → `daf sync --sprint current`
- GitHub/GitLab → `daf sync`

**Single repository?**
- Use standard workflow → `daf open <session>`

**Multiple repositories?**
- Know all repos → Declarative (`--projects`)
- Discover as you go → Iterative (multiple `daf open`)

**Handoff to team?**
- Export session → `daf export`
- Import on other machine → `daf import`

**Repeated task?**
- Save as template → `daf template save`
- Reuse template → `daf new --template`

---

## Quick Tips

1. **Always quote GitHub issue keys**: `"owner/repo#123"` (# starts comments in bash)
2. **Session names don't need quotes**: `daf open owner-repo-123`
3. **Add notes regularly**: `daf note "progress update"` (works in Claude now!)
4. **Use --dry-run**: Preview changes before executing
5. **Clean up completed sessions**: `daf list --status complete`, then `daf delete`

---

**See Also:**
- [QUICKREF.md](../../QUICKREF.md) - Command quick reference
- [docs/07-commands.md](../reference/commands.md) - Complete command documentation
- [docs/03-quick-start.md](../getting-started/quick-start.md) - Getting started guide
