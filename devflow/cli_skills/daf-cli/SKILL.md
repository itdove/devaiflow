---
name: daf-cli
description: DevAIFlow CLI tool for managing development sessions with JIRA integration, git branch management, and PR/MR creation workflows
---

# DAF CLI Tool Reference

The `daf` (DevAIFlow) tool helps manage Claude Code sessions with JIRA integration, git branch management, and automated workflows.

## Installation

```bash
# Install from local directory
pip install -e .

# Reinstall after changes
pip install --upgrade --force-reinstall .
```

## Core Session Commands

### Session Creation and Management

```bash
# Sync JIRA tickets assigned to you
daf sync --sprint current

# Create new session (no JIRA)
daf new --name "feature-name" --goal "Description of work"

# Open existing session or create from JIRA ticket
daf open PROJ-12345

# Open with specific repository (multi-conversation sessions)
daf open PROJ-12345 --path /path/to/repo
daf open PROJ-12345 --path repo-name

# Start fresh conversation (archive current, create new)
daf open PROJ-12345 --new-conversation

# Show current status
daf status

# List all sessions
daf list

# Show session details
daf show PROJ-12345
daf show --latest  # Show most recent session

# Get info about session (UUID, metadata)
daf info PROJ-12345

# View conversation history (active + archived sessions)
daf sessions list PROJ-12345
```

### Adding Notes

```bash
# Add progress note to session
daf note PROJ-12345 "Completed API implementation"
daf note --latest "Fixed bug in authentication"

# View all notes for a session
daf notes PROJ-12345
daf notes --latest
```

### Completing Sessions

```bash
# Complete session (commit, PR, JIRA update)
daf complete PROJ-12345
daf complete --latest

# Attach session export to JIRA
daf complete PROJ-12345 --attach-to-jira
```

## JIRA Integration

### Configuration

```bash
# Set JIRA project (one-time setup)
daf config tui

# Set workstream
daf config tui

# Set affected version for bugs
daf config tui

# Refresh JIRA field mappings
daf config refresh-jira-fields
```

### JIRA Wiki Markup Requirements

**CRITICAL:** ALL JIRA issue descriptions and JIRA text fields (description, comments, acceptance criteria, etc.) MUST use JIRA Wiki markup syntax, NOT Markdown. This applies ONLY when writing content that will be sent to JIRA via `daf jira create`, `daf jira update`, or similar commands - documentation files (.md) should remain in Markdown format.

JIRA Wiki markup ensures proper rendering in the JIRA UI. Using Markdown syntax will cause formatting issues.

#### Syntax Comparison

| Element | ❌ Markdown (WRONG) | ✅ JIRA Wiki Markup (CORRECT) |
|---------|---------------------|-------------------------------|
| Header 2 | `## Header` | `h2. Header` |
| Header 3 | `### Header` | `h3. Header` |
| Bold | `**bold**` | `*bold*` |
| Italic | `*italic*` | `_italic_` |
| Code block | ` ```bash\ncode\n``` ` | `{code:bash}\ncode\n{code}` |
| Inline code | `` `code` `` | `{{code}}` |
| Unordered list | `- item` | `* item` |
| Ordered list | `1. item` | `# item` |
| Link | `[text](url)` | `[text|url]` |

#### Common Mistakes to Avoid

❌ **WRONG (Markdown):**
```
## Problem Description

This is **important** and uses `code` examples.

### Steps
1. First step
2. Second step

```bash
run command
```
```

✅ **CORRECT (JIRA Wiki Markup):**
```
h2. Problem Description

This is *important* and uses {{code}} examples.

h3. Steps
# First step
# Second step

{code:bash}
run command
{code}
```

**Note:** Project-specific JIRA issue templates are defined in DAF_AGENTS.md. Always refer to DAF_AGENTS.md for the correct template structure for your project.

### JIRA Operations

```bash
# View ticket details
daf jira view PROJ-12345

# Create JIRA ticket with codebase analysis
daf jira new story --parent PROJ-1234 --goal "Add retry logic to API"
daf jira new bug --parent PROJ-1234 --goal "Fix timeout issue"
daf jira new task --parent PROJ-1234 --goal "Update docs"

# Create JIRA issue directly (remember: use JIRA Wiki markup in descriptions!)
daf jira create bug --summary "Bug title" --priority Major --parent PROJ-1234 --description "..."
daf jira create story --summary "Story title" --parent PROJ-1234 --description "..."
daf jira create task --summary "Task title" --parent PROJ-1234 --description "..."

# Create JIRA issue with link to another issue
daf jira create bug --summary "Critical bug" --parent PROJ-1234 --linked-issue "blocks" --issue PROJ-5678
daf jira create story --summary "New feature" --parent PROJ-1234 --linked-issue "relates to" --issue PROJ-9999

# Update JIRA issue (remember: use JIRA Wiki markup in descriptions!)
daf jira update PROJ-12345 --description "New description"
daf jira update PROJ-12345 --priority Major --workstream Platform
daf jira update PROJ-12345 --status "In Progress"
daf jira update PROJ-12345 --git-pull-request "https://github.com/..."

# Link existing JIRA issues
daf jira update PROJ-12345 --linked-issue "blocks" --issue PROJ-5678
daf jira update PROJ-12345 --linked-issue "is blocked by" --issue PROJ-9999
daf jira update PROJ-12345 --linked-issue "relates to" --issue PROJ-1111
daf jira update PROJ-12345 --linked-issue "duplicates" --issue PROJ-2222

# Use custom fields
daf jira create bug --summary "..." --field severity=Critical --field size=L
daf jira update PROJ-12345 --field severity=Critical
```

## Configuration Commands

```bash
# Initialize configuration
daf init

# Show current configuration
daf config show

# Set configuration values
daf config tui
daf config tui
daf config tui
daf config tui
daf config tui

# Configure prompts
daf config tui
daf config tui

# Context files
daf config context list
daf config context add ARCHITECTURE.md "system architecture"
daf config context remove ARCHITECTURE.md

# Interactive TUI configuration
daf config tui
```

## Upgrade Commands

```bash
# Upgrade slash commands
daf upgrade
daf upgrade --dry-run
```

## Multi-Conversation Sessions

When working on tasks that span multiple repositories, use the `--path` parameter to specify which repository to work on:

```bash
# Auto-select conversation by repository path
daf open PROJ-12345 --path /absolute/path/to/repo
daf open PROJ-12345 --path ~/workspace/repo-name

# Auto-select by repository name (from workspace)
daf open PROJ-12345 --path repo-name

# Without --path, shows interactive menu
daf open PROJ-12345  # Prompts to select conversation
```

**How it works:**
- The `--path` parameter auto-detects which conversation to use based on the repository
- If a conversation exists for the specified path, it switches to that conversation
- If no conversation exists, it creates a new conversation for that repository
- Supports both absolute paths and repository names from your workspace
- Falls back to interactive selection if path is not provided

**Example workflow:**
```bash
# Working on multi-repo feature PROJ-12345
cd ~/workspace/frontend-repo
daf open PROJ-12345 --path .  # Opens conversation for frontend-repo

# Switch to backend work
cd ~/workspace/backend-repo
daf open PROJ-12345 --path .  # Opens conversation for backend-repo
```

## Multi-Session per Conversation

Each conversation can have multiple Claude Code sessions: one **active session** (current work) and **archived sessions** (history). This allows starting fresh while preserving previous work.

### Starting Fresh with --new-conversation

When a conversation becomes too long or you want a clean slate:

```bash
# Archive current conversation and start fresh
daf open PROJ-12345 --new-conversation
```

**What happens:**
- Current Claude Code conversation is archived (preserves full history)
- New Claude session UUID is generated
- Fresh conversation with empty history
- Same git branch and project directory
- Previous work accessible via `daf sessions list`

**Use cases:**
- Conversation history too long (causing 413 errors)
- Want clean slate but preserve old approach for reference
- Completed one part, want fresh context for next

### Viewing Conversation History

```bash
# View all sessions (active + archived) for a conversation
daf sessions list PROJ-12345
```

**Output shows:**
- Active Claude session (current work)
- Archived sessions with summaries
- Message counts, timestamps
- Full conversation progression

**Example:**
```
Session: PROJ-12345
Conversations (1 repository):

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
```

## Session Types

The daf tool supports different session types for specialized workflows:

### Development Session (Default)
```bash
daf new --name "feature-work" --goal "Implement feature"
daf open PROJ-12345
```
- Full git operations (branch, commit, PR)
- Code modifications allowed
- Complete workflow with testing

### Ticket Creation Session
```bash
daf jira new story --parent PROJ-1234 --goal "Research and create story"
```
- Read-only analysis
- No git branch created
- No code modifications
- Completes with `daf jira create` command

## Common Workflows

### Daily Development Workflow
```bash
# 1. Start of day - sync tickets
daf sync --sprint current

# 2. Open a ticket
daf open PROJ-12345

# 3. Work in Claude Code...

# 4. Add progress notes as you work
daf note PROJ-12345 "Completed API layer"

# 5. Complete session (commit, PR, JIRA update)
daf complete PROJ-12345
```

### Creating Well-Researched JIRA Tickets
```bash
# 1. Start analysis session
daf jira new story --parent PROJ-1234 --goal "Add caching layer to API"

# 2. Claude analyzes codebase (read-only)
# - Searches for relevant code
# - Understands existing patterns
# - Identifies integration points

# 3. Create JIRA ticket with informed details
daf jira create story \
  --summary "Add Redis caching to subscription API" \
  --parent PROJ-1234 \
  --description "..." \
  --acceptance-criteria "..."

# 4. Exit Claude - session completes automatically
```

### Multi-Repository Feature Work
```bash
# 1. Create session in backend repo
daf new --name PROJ-12345 --goal "Add API endpoint" --path ~/backend

# 2. Work in backend...

# 3. Add conversation in frontend repo
daf new --name PROJ-12345 --goal "Add UI component" --path ~/frontend

# 4. In frontend Claude session, read backend work
/daf read-conversation  # Shows list of conversations to read

# 5. Complete both when done
daf complete PROJ-12345
```

## Environment Variables

```bash
# JIRA integration (required for JIRA features)
export JIRA_API_TOKEN="your-personal-access-token"
export JIRA_AUTH_TYPE="Bearer"

# Optional: Custom JIRA URL
export JIRA_URL="https://jira.example.com"

# GitHub integration (for private repo access)
export GITHUB_TOKEN="your-github-token"
```

## Data Storage

```bash
# Sessions data
~/.daf-sessions/sessions.json
~/.daf-sessions/sessions/{JIRA-KEY}/

# Configuration
~/.daf-sessions/config.json

# Conversation files (Claude Code)
~/.claude/projects/{encoded-path}/{session-uuid}.jsonl

# Slash commands (deployed by daf upgrade)
<workspace>/.claude/commands/

# Skills (deployed by daf upgrade)
<workspace>/.claude/skills/
```

## Exit Codes

- `0` - Success
- Non-zero - Error (various error conditions)

## Acceptance Criteria Field Requirements

**IMPORTANT:** When creating JIRA issues with `daf jira create`, understand that there are **TWO separate fields**:

### Field Distinctions

| Field | Purpose | Content Type |
|-------|---------|--------------|
| `--description` | Background/context/user story | JIRA Wiki markup describing problem, context, user story |
| `--acceptance-criteria` | **Separate custom field** | Functional requirements + end-to-end test scenarios |

### Best Practices

- **For story/epic/spike**: Both fields should be populated
- **Do NOT** put acceptance criteria content in the description field
- **Acceptance criteria should include:**
  - Functional requirements (what needs to be delivered)
  - End-to-end test scenarios (how to verify it works)
  - Should NOT be just a copy of the description

### Example Usage

```bash
daf jira create story \
  --summary "Add Redis caching to subscription API" \
  --parent PROJ-1234 \
  --description "h3. *User Story*
As a backend developer, I want Redis caching...

h3. *Supporting documentation*
..." \
  --acceptance-criteria "h3. Requirements
* Cache should store subscription lookup results
* Cache TTL configurable (default: 5 min)

h3. End to End Test
# Step 1: Create subscription
# Step 2: Verify cache miss on first call
# Step 3: Verify cache hit on second call..."
```

## Tips for Claude Code Sessions

1. **ALWAYS use JIRA Wiki markup in issue descriptions** - NOT Markdown (see syntax comparison above)
2. **Use `daf jira view` to read tickets** - More reliable than curl
3. **Always use `--parent` when creating issues** - Links to epic/parent
4. **Use separate --acceptance-criteria field** - Don't put acceptance criteria in description
5. **Let `daf complete` handle git operations** - Automated commit/PR workflow
6. **Add notes regularly** - Track progress with `daf note`
7. **Use `daf jira new` for research** - Analysis-only sessions prevent accidents
8. **Check session type** - Read-only constraints enforced for ticket_creation
9. **Use custom fields with `--field`** - Works for any JIRA custom field
10. **Refer to DAF_AGENTS.md for templates** - Project-specific JIRA issue templates

## Error Handling

```bash
# Check if in a git repository
daf open PROJ-12345  # Will prompt to select repo if not in one

# Workspace not configured
daf config tui

# JIRA not configured
daf config tui
daf config tui

# Missing JIRA token
export JIRA_API_TOKEN="your-token"
export JIRA_AUTH_TYPE="Bearer"
```

## See Also

- Git operations: See git-cli skill
- GitHub PR creation: See gh-cli skill
- GitLab MR creation: See glab-cli skill
- Full documentation: `docs/07-commands.md` in project repository
