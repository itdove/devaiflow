---
name: daf-cli
description: Commands that work inside Claude Code sessions for JIRA integration, notes, and session management
user-invocable: false
---

# DAF CLI - Commands for Claude Code Sessions

**IMPORTANT**: You are currently inside an active Claude Code session. This skill documents commands that are ALLOWED to run inside sessions.

Commands that work **inside Claude Code sessions**. For field intelligence, see **daf-jira-fields skill**.

## JIRA Commands

**Read JIRA:** Use Atlassian MCP `mcp__atlassian__getJiraIssue`

**Create/Update:** Use daf CLI commands (see **daf-jira-fields skill** for field syntax)

```bash
# View
daf jira view PROJ-12345 [--history] [--comments] [--children]

# Create (see daf-jira-fields skill for field rules)
daf jira create {bug|story|task|epic|spike} \
  --summary "..." \
  --parent PROJ-1234 \
  --components backend \
  --field custom_field=value

# Update
daf jira update PROJ-12345 \
  --priority Major \
  --field custom_field=value

# Comment
daf jira add-comment PROJ-12345 "Comment text"
```

## Session Notes

```bash
daf note "Progress update"      # Add note (auto-detects session)
daf notes                        # View notes
```

## Session Info

```bash
daf active                       # Show currently active conversation
daf info [PROJ-12345|--latest]  # Session details
daf list [--active]              # List sessions
daf status                       # Status dashboard
daf summary [PROJ-12345|--latest] # Session summary
daf summary --detail             # Detailed summary with all files
daf summary --ai-summary         # AI-powered summary
daf time [PROJ-12345|--latest]  # Time tracking details
```

## Configuration

```bash
daf config show                  # Merged configuration
daf config show --fields         # YOUR JIRA's custom fields
daf config refresh-jira-fields   # Refresh from JIRA API
daf config context list          # List context files
```

## Templates

```bash
daf template list                # List all templates
daf template show <name>         # Show template details
```

## Workspaces

```bash
daf workspace list               # List all workspaces
```

## Git Integration (GitHub/GitLab Issues)

DevAIFlow auto-detects GitHub vs GitLab from your git remote URLs.

```bash
# View issue details
daf git view                     # Current session's issue
daf git view 123                 # Specific issue
daf git view owner/repo#123 --comments

# Create new issue (standalone, without session)
daf git create bug --summary "Fix timeout bug"
daf git create enhancement --summary "Add caching" --parent "#123"

# Update issue fields
daf git update 123 --labels "priority: high,backend"
daf git update 123 --assignee username

# Add comment
daf git add-comment 123 "Work in progress"
```

**Important:** Use `--summary` flag (NOT `--title`) when creating issues.

**See also:** **daf-git skill** for complete GitHub/GitLab documentation and Markdown syntax.

## Safety Warnings: Commands Blocked Inside Sessions

**CRITICAL**: The following commands are BLOCKED inside Claude Code sessions to prevent data corruption and nested session issues:

**Session lifecycle** (run from regular terminal):
- `daf new`, `daf open`, `daf complete`, `daf delete`
- `daf update`, `daf sync`, `daf link`, `daf unlink`
- `daf jira new` (creates new sessions)

**Data operations** (run from regular terminal):
- `daf export`, `daf import`, `daf backup`, `daf restore`

**Maintenance operations** (run from regular terminal):
- `daf maintenance` group: `cleanup-conversation`, `cleanup-sessions`, `discover`, `rebuild-index`, `repair-conversation`

**Configuration changes** (run from regular terminal):
- `daf context add/remove/reset`
- `daf template save/delete`
- `daf workspace add/remove/rename/set-default`
- `daf pause`, `daf resume`

**Why this matters:**
Running these commands inside Claude Code can cause:
- Nested session creation and confusion
- Concurrent modifications to session metadata
- Session state corruption
- Lost work from conflicting updates

**If you need these commands:** Exit Claude Code and run them from a regular terminal.

## Key Principles

1. **Fields:** See **daf-jira-fields skill** for system vs custom field syntax
2. **Discover:** Run `daf config show --fields` to see YOUR custom fields
3. **Read JIRA:** Use Atlassian MCP for fast reads

## See Also

- **daf-jira-fields skill** - Field mapping and validation rules
- **Atlassian MCP** - Fast JIRA reads
- **DAF_AGENTS.md** - Workflows and templates
