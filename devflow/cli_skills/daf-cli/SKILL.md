---
name: daf-cli
description: Quick reference and safety guide for daf commands in Claude Code sessions
user-invocable: false
---

# DAF Quick Reference

**IMPORTANT**: You are currently inside an active Claude Code session. This guide helps you navigate to the right skill documentation.

## Command Reference by Category

### JIRA Operations
**See `daf-jira` skill** for complete JIRA documentation:
- View tickets: `daf jira view`
- Create tickets: `daf jira create`
- Update tickets: `daf jira update`
- Add comments: `daf jira add-comment`
- **CRITICAL**: JIRA uses Wiki markup syntax (see daf-jira skill)

### GitHub/GitLab Operations
**See `daf-git` skill** for complete GitHub/GitLab documentation:
- View issues: `daf git view`
- Create issues: `daf git create`
- Update issues: `daf git update`
- Add comments: `daf git add-comment`
- **CRITICAL**: GitHub/GitLab use Markdown syntax (see daf-git skill)

### Session Notes
**See `daf-notes` skill** for viewing session notes:
- Add note: `daf note "Progress update"`
- View notes: `daf notes`

### Session Information
- **`daf-active` skill**: Show currently active conversation
- **`daf-info` skill**: Detailed session information
- **`daf-status` skill**: Progress dashboard
- **`daf-list` skill**: List all sessions

### Configuration
**See `daf-config` skill** for configuration commands:
- View config: `daf config show`
- View JIRA fields: `daf config show --fields`
- Refresh fields: `daf config refresh-jira-fields`

### Skills Discovery
- List all available skills: `daf skills`
- Inspect specific skill: `daf skills <skill-name>`
- JSON output: `daf skills --json`

### Field Intelligence
**See `daf-jira-fields` skill** for JIRA field mapping and validation rules.

### Workflows
**See `daf-workflow` skill** for development workflows and best practices.

### Workspaces
**See `daf-workspace` skill** for workspace management.

## Safety Warnings: Commands Blocked Inside Sessions

**CRITICAL**: The following commands are BLOCKED inside Claude Code sessions to prevent data corruption and nested session issues:

**Session lifecycle** (run from regular terminal):
- `daf new`, `daf open`, `daf complete`, `daf delete`
- `daf update`, `daf sync`, `daf link`, `daf unlink`
- `daf jira new`, `daf git new` (creates new sessions)

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

## Skills Management

DevAIFlow automatically discovers skills from multiple locations in a specific order:

### Discovery Order (Load Order)

1. **User-level**: `~/.claude/skills/` - Generic skills (daf-cli, git-cli, gh-cli, etc.)
2. **Workspace-level**: `<workspace>/.claude/skills/` - Workspace-specific tools
3. **Hierarchical**: `$DEVAIFLOW_HOME/.claude/skills/` - Organization-specific extensions
4. **Project-level**: `<project>/.claude/skills/` - Project-specific skills

### Precedence Rules

When the same skill exists at multiple levels:

**Project > Hierarchical > Workspace > User**

Later-loaded skills can override or extend earlier ones. This is why generic skills (user-level) are loaded first, and organization-specific skills (hierarchical) are loaded after - they can extend the generic skills.

### Best Practices

1. **Use unique skill names** - Avoid naming conflicts by using unique names per level
2. **Generic skills at user-level** - Place reusable tool documentation in `~/.claude/skills/`
3. **Organization extensions in hierarchical** - Extend generic skills with company-specific details in `$DEVAIFLOW_HOME/.claude/skills/`
4. **Project-specific only when needed** - Only place truly project-specific skills in `<project>/.claude/skills/`

### Why This Order?

Organization-specific skills (hierarchical) **extend** generic skills rather than replace them. For example:
- `~/.claude/skills/daf-cli/` provides generic daf command documentation
- `$DEVAIFLOW_HOME/.claude/skills/01-enterprise/` extends it with Red Hat-specific JIRA fields

Both skills are loaded, but hierarchical skills add organization-specific context.

### Duplicate Prevention

DevAIFlow automatically prevents duplicate loading:
- In single-project sessions, project-level skills are auto-loaded by Claude from `cwd`
- DevAIFlow filters these out of `--add-dir` to prevent duplicates
- Each skill directory is loaded exactly once

**For detailed information**, see the comprehensive Skills Management Guide in `docs/guides/skills-management.md`.

## Critical Reminder

**⚠️ Format Awareness**: When working with issue trackers, remember:
- **JIRA** uses **Wiki markup** (`h3. Header`, `*bold*`, `{code}...{code}`)
- **GitHub/GitLab** use **Markdown** (`### Header`, `**bold**`, ` ```code``` `)

Using the wrong format will cause rendering issues. See the appropriate skill for syntax details.
