---
name: daf-cli
description: Commands that work inside Claude Code sessions for JIRA integration, notes, and session management
---

# DAF CLI - Commands for Claude Code Sessions

This skill documents `daf` commands that work **inside Claude Code sessions**. Commands that launch Claude sessions (like `daf open`, `daf new`, `daf investigate`) are not included here.

## JIRA Integration

### View JIRA Tickets

```bash
# View ticket details in Claude-friendly format
daf jira view PROJ-12345

# View with changelog/history
daf jira view PROJ-12345 --history

# View with child issues
daf jira view PROJ-12345 --children

# JSON output
daf jira view PROJ-12345 --json
```

**Why use this instead of curl:**
- Formats data for Claude to read easily
- Handles authentication automatically
- Shows all relevant fields including custom fields

### Create JIRA Issues

```bash
# Create issues (remember: use JIRA Wiki markup in descriptions!)
daf jira create bug --summary "Bug title" --priority Major --parent PROJ-1234 --description "..."
daf jira create story --summary "Story title" --parent PROJ-1234 --description "..."
daf jira create task --summary "Task title" --parent PROJ-1234 --description "..."

# Create with acceptance criteria (separate field)
daf jira create story \
  --summary "Add Redis caching to API" \
  --parent PROJ-1234 \
  --description "h3. User Story\n..." \
  --acceptance-criteria "h3. Requirements\n..."

# Create with issue links
daf jira create bug --summary "Critical bug" --parent PROJ-1234 --linked-issue "blocks" --issue PROJ-5678

# Use custom fields (use field names from organization.json field_mappings)
daf jira create bug --summary "..." --field field_name1=value1 --field field_name2=value2

# JSON output for automation
daf jira create story --summary "..." --parent PROJ-1234 --json
```

**CRITICAL:** ALL JIRA text fields MUST use JIRA Wiki markup, NOT Markdown.

#### JIRA Wiki Markup Syntax

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

### Update JIRA Issues

```bash
# Update issue fields
daf jira update PROJ-12345 --description "New description"
daf jira update PROJ-12345 --priority Major --field field_name=value
daf jira update PROJ-12345 --status "In Progress"
daf jira update PROJ-12345 --git-pull-request "https://github.com/..."

# Link issues
daf jira update PROJ-12345 --linked-issue "blocks" --issue PROJ-5678
daf jira update PROJ-12345 --linked-issue "is blocked by" --issue PROJ-9999
daf jira update PROJ-12345 --linked-issue "relates to" --issue PROJ-1111

# Update custom fields (use field names from organization.json field_mappings)
daf jira update PROJ-12345 --field field_name=value

# JSON output
daf jira update PROJ-12345 --status "In Progress" --json
```

### Add JIRA Comments

```bash
# Add comment to JIRA issue
daf jira add-comment PROJ-12345 "Fixed the issue"

# From file
daf jira add-comment PROJ-12345 --file notes.txt

# From stdin
echo "Update from CI" | daf jira add-comment PROJ-12345 --stdin

# Make comment public (requires confirmation)
daf jira add-comment PROJ-12345 "Public announcement" --public

# JSON output
daf jira add-comment PROJ-12345 "Comment text" --json
```

**Default:** Comments are restricted to project team visibility. Use `--public` to make visible to all.

## Session Notes

```bash
# Add progress note to current session
daf note PROJ-12345 "Completed API implementation"
daf note --latest "Fixed bug in authentication"

# View all notes for a session
daf notes PROJ-12345
daf notes --latest

# JSON output
daf note PROJ-12345 "Note text" --json
daf notes PROJ-12345 --json
```

## Session Information

```bash
# Show session details
daf info PROJ-12345
daf info --latest

# Get only the Claude session UUID
daf info PROJ-12345 --uuid-only

# Show specific conversation
daf info PROJ-12345 --conversation-id 1

# JSON output
daf info PROJ-12345 --json
```

```bash
# List all sessions
daf list
daf list --active
daf list --status in_progress,complete
daf list --working-directory backend-api
daf list --since "last week"

# JSON output
daf list --json
```

```bash
# Show status dashboard (with configured grouping/totals)
daf status
daf status --json
```

```bash
# View all conversations for a session
daf sessions list PROJ-12345
daf sessions list --latest
daf sessions list PROJ-12345 --json
```

## Linking JIRA to Sessions

```bash
# Link JIRA ticket to existing session
daf link session-name --jira PROJ-12345

# Replace existing link without confirmation
daf link session-name --jira PROJ-67890 --force

# JSON output
daf link session-name --jira PROJ-12345 --json

# Unlink JIRA from session
daf unlink session-name
daf unlink session-name --json
```

## Session Summary

```bash
# Show session summary
daf summary PROJ-12345
daf summary --latest

# Show detailed summary
daf summary PROJ-12345 --detail

# Generate AI-powered summary
daf summary PROJ-12345 --ai-summary

# JSON output
daf summary PROJ-12345 --json
```

## Time Tracking

```bash
# Show time tracking
daf time PROJ-12345
daf time --latest

# Pause time tracking
daf pause PROJ-12345
daf pause --latest

# Resume time tracking
daf resume PROJ-12345
daf resume --latest

# JSON output
daf time PROJ-12345 --json
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

## Exit Codes

All commands follow standard Unix conventions:
- `0` - Success
- `1` - Error (operation failed)

**Usage in scripts:**
```bash
# Check if session exists
if daf info PROJ-12345 --uuid-only > /dev/null 2>&1; then
    echo "Session exists"
else
    echo "Session not found"
    exit 1
fi
```

## Acceptance Criteria Field

**IMPORTANT:** When creating JIRA issues with `daf jira create`, there are **TWO separate fields**:

| Field | Purpose | Content Type |
|-------|---------|--------------|
| `--description` | Background/context/user story | JIRA Wiki markup describing problem, context |
| `--acceptance-criteria` | **Separate custom field** | Functional requirements + test scenarios |

**Best Practices:**
- For story/epic/spike: Both fields should be populated
- Do NOT put acceptance criteria in the description field
- Acceptance criteria should include functional requirements and test scenarios

**Example:**
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

## Syncing JIRA Tickets

The `daf sync` command creates daf sessions for JIRA tickets that match filter criteria configured in organization.json.

```bash
# Sync tickets based on configured filters
daf sync

# Filter by custom fields (uses field names from field_mappings)
daf sync --field workstream="Platform"
daf sync --field sprint="Sprint 2025-02"

# Filter by ticket type
daf sync --type story
daf sync --type bug

# Filter by epic
daf sync --epic AAP-12345

# JSON output
daf sync --json
```

### Understanding Sync Filters

Sync filters are configured in `organization.json` under `jira.filters.sync` section:

```json
{
  "jira": {
    "filters": {
      "sync": {
        "status": ["To Do", "In Progress"],
        "required_fields": ["sprint", "workstream"],
        "assignee": "currentUser()"
      }
    }
  }
}
```

**To see your current sync filter configuration:**
```bash
daf config show-sync-filters
daf config show-sync-filters --json
```

**Filter settings:**
- `status`: JIRA statuses to sync (e.g., "To Do", "In Progress")
- `required_fields`: Fields that must be present on tickets (uses field names from field_mappings)
- `assignee`: Filter by assignee
  - `"currentUser()"` - Only your assigned tickets
  - `"username"` - Specific user's tickets
  - `null` - All tickets (no assignee filter)

**How required_fields works:**
- Tickets MUST have ALL specified fields set to be synced
- Uses field names from `field_mappings` configuration
- Example: If `required_fields: ["sprint", "workstream"]`, tickets without sprint OR workstream will be skipped
- Use `daf config show-fields` to see available field names

**Command-line filters:**
- Command-line `--field` filters are ADDED to the configured filters
- Example: `daf sync --field severity="Critical"` will sync only tickets that:
  - Match configured status/assignee/required_fields filters
  - AND have severity="Critical"

## Understanding Custom Fields

**IMPORTANT:** The `--field` parameter uses **field names** from your organization's `field_mappings` configuration, NOT customfield IDs.

**How it works:**
1. Your organization.json contains a `field_mappings` section that maps friendly names to JIRA customfield IDs
2. Example mapping:
   ```json
   "field_mappings": {
     "severity": {"id": "customfield_12345", "name": "Severity"},
     "team": {"id": "customfield_67890", "name": "Team"}
   }
   ```
3. You use the mapped name in commands: `--field severity=Critical` (NOT `--field customfield_12345=Critical`)

**Why this matters:**
- Customfield IDs are organization-specific and hard to remember
- Field mappings provide consistent, readable names
- If a field name is not in field_mappings, the command will fail

**To see available field names:**
- **RECOMMENDED:** Run `daf config show-fields` to list all available custom fields
- Read DAF_AGENTS.md section "Discovering Custom Fields" (automatically loaded in sessions)
- Check `~/.daf-sessions/organization.json` field_mappings section
- Run `daf config refresh-jira-fields` to update field definitions from JIRA
- Use `daf jira create <type> --help` to see discovered fields for that issue type

## Tips for Claude Code Sessions

1. **ALWAYS use JIRA Wiki markup in issue descriptions** - NOT Markdown
2. **Use `daf jira view` to read tickets** - More reliable than curl
3. **Always use `--parent` when creating issues** - Links to epic/parent
4. **Use separate --acceptance-criteria field** - Don't put in description
5. **Add notes regularly** - Track progress with `daf note`
6. **Check session type** - Read-only constraints enforced for ticket_creation and investigation
7. **Use field names from field_mappings** - `--field` takes mapped names, not customfield IDs
8. **Refer to DAF_AGENTS.md for templates** - Project-specific JIRA issue templates
9. **Use `--json` for automation** - All commands support JSON output

## See Also

- Git operations: See git-cli skill
- GitHub PR creation: See gh-cli skill
- GitLab MR creation: See glab-cli skill
- Session launching: Use `daf open`, `daf new`, `daf investigate` (outside Claude)
- Full documentation: `docs/07-commands.md` in project repository
