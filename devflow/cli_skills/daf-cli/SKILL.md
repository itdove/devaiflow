---
name: daf-cli
description: Commands that work inside Claude Code sessions for JIRA integration, notes, and session management
user-invocable: false
---

# DAF CLI - Commands for Claude Code Sessions

Commands that work **inside Claude Code sessions**. For field intelligence, see **daf-jira-fields skill**.

## JIRA Commands

**Read JIRA:** Use Atlassian MCP `mcp__atlassian__getTeamworkGraphObject`

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
daf info [PROJ-12345|--latest]  # Session details
daf list [--active]              # List sessions
daf status                       # Status dashboard
```

## Configuration

```bash
daf config show                  # Merged configuration
daf config show --fields         # YOUR JIRA's custom fields
daf config refresh-jira-fields   # Refresh from JIRA API
```

## Key Principles

1. **Fields:** See **daf-jira-fields skill** for system vs custom field syntax
2. **Discover:** Run `daf config show --fields` to see YOUR custom fields
3. **Read JIRA:** Use Atlassian MCP for fast reads
4. **JIRA markup:** Use JIRA Wiki markup (NOT Markdown)

## See Also

- **daf-jira-fields skill** - Field mapping and validation rules
- **Atlassian MCP** - Fast JIRA reads
- **DAF_AGENTS.md** - Workflows and templates
