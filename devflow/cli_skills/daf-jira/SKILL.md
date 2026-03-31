---
name: daf-jira
description: JIRA operations (view, create, update, comment) with Wiki markup syntax reference
user-invocable: true
argument-hint: "[TICKET-ID]"
---

## MCP Alternative Available

**If you have a JIRA MCP server configured** (e.g., `mcp-atlassian`), you can use MCP tools directly for JIRA operations.

**Quick comparison:**
- **MCP Tools**: Direct API access, advanced operations, full JIRA capabilities
- **daf Commands**: Validated operations, friendly field names, session integration, team defaults

**For complete MCP integration guide**, see **daf-jira-mcp skill** which shows how to:
- Read field mappings and defaults from `daf config show --json` (for MCP tools)
- Apply DevAIFlow's validation logic manually with MCP tools
- Map friendly field names to JIRA field IDs
- Apply issue type templates

**When to use each:**
- ✅ **Use MCP** for: reading tickets, searching, exploring JIRA data
- ✅ **Use daf** for: creating/updating with validation (auto-applies config, no manual reading needed), session integration, team defaults

**Note:** `daf jira create` commands are self-contained - they automatically load configuration, apply validation, and handle field mappings. You do NOT need to read `daf config show --json` before using daf commands.

---

View the JIRA ticket associated with the current session in Claude-friendly format.

```bash
daf jira view
```

**Auto-detects current session:**
The command will automatically detect the current Claude Code session and display the associated JIRA ticket details.

**Explicit ticket lookup:**
```bash
daf jira view PROJ-12345
daf jira view PROJ-12345 --history    # Include changelog
daf jira view PROJ-12345 --comments   # Include comments
daf jira view PROJ-12345 --history --comments  # Include both
```

**What it shows:**
- Ticket key and summary
- Current status and priority
- Assignee and reporter
- Parent/epic links (if applicable)
- Custom fields (organization-specific)
- Full description
- Acceptance criteria
- Pull request links
- Comments (with `--comments` flag)
- Changelog/history (with `--history` flag)

**Example output:**
```
Key: PROJ-12345
Summary: Implement customer backup and restore
Status: In Progress
Type: Story
Priority: Major
Assignee: John Doe
Parent: PROJ-59038
Custom Field 1: Value A (custom field)
Custom Field 2: Value B (custom field)

Description:
As a user, I want to backup my data so that I can restore it later.

Acceptance Criteria:
- Backup functionality implemented
- Restore functionality implemented
- Tests added
```

**Why use this:**
- More reliable than curl commands (automatic auth)
- Better formatted for Claude to read
- Shows all relevant ticket context
- Consistent with daf tool ecosystem
- Helps understand requirements before coding

**Related commands:**
```bash
daf jira create bug --summary "..."    # Create new JIRA bug (validated)
daf jira create story --summary "..."  # Create new JIRA story (validated)
daf jira update PROJ-12345 --priority Major  # Update ticket fields
```

**Alternative: Use MCP JIRA tools** (see **daf-jira-mcp skill** for validation logic):
```python
mcp__mcp-atlassian__jira_get_issue(issue_key="PROJ-12345")
mcp__mcp-atlassian__jira_create_issue(...)
mcp__mcp-atlassian__jira_update_issue(...)
```

## JIRA Wiki Markup

**CRITICAL:** JIRA uses **Wiki markup syntax**, NOT Markdown.

When using `daf jira create`, `daf jira add-comment`, or `daf jira update` commands, all text fields (descriptions, comments, acceptance criteria) **MUST** use **JIRA Wiki markup** formatting.

### Syntax Reference

| Element | ✅ JIRA Wiki Markup (CORRECT) | ❌ Markdown (WRONG) |
|---------|-------------------------------|---------------------|
| Header 2 | `h2. Header` | `## Header` |
| Header 3 | `h3. Header` | `### Header` |
| Bold | `*bold*` | `**bold**` |
| Italic | `_italic_` | `*italic*` |
| Code block | `{code:bash}\ncode\n{code}` | ` ```bash\ncode\n``` ` |
| Inline code | `{{code}}` | `` `code` `` |
| Unordered list | `* item` | `- item` |
| Ordered list | `# item` | `1. item` |
| Link | `[text|url]` | `[text](url)` |
| Checkbox | `- [] item` | `- [ ] item` |

### Why This Matters

- JIRA will NOT render Markdown correctly
- Using `## Header` will display as plain text, not a header
- Using ` ```bash ` code blocks will not format as code
- Acceptance criteria must use `- []` format (not `- [ ]`)

### Example: Creating JIRA Ticket with Wiki Markup

```bash
# Correct JIRA Wiki markup formatting
daf jira create story --summary "Add caching layer" \
  --description "h3. Overview

Implement Redis caching to improve API performance.

h3. Requirements

* Cache should store subscription lookups
* Configurable TTL (default: 5 minutes)
* Handle cache misses gracefully

h3. Implementation Notes

Use {{redis-py}} client with the following configuration:

{code:python}
redis_client = Redis(
    host='localhost',
    port=6379,
    decode_responses=True
)
{code}

*Target:* 50ms response time" \
  --field acceptance_criteria="- [] Unit tests pass
- [] Integration tests pass
- [] Performance benchmarks meet targets"
```

### Common Mistakes

❌ **DON'T** use Markdown in JIRA tickets:
```bash
# WRONG - Markdown will not render in JIRA
daf jira create bug --description "### Bug Description

**Problem:** API times out

\`\`\`python
# broken code
\`\`\`"
```

✅ **DO** use JIRA Wiki markup:
```bash
# CORRECT - JIRA Wiki markup
daf jira create bug --description "h3. Bug Description

*Problem:* API times out

{code:python}
# broken code
{code}"
```

### When to Use JIRA Wiki Markup

**✅ Use JIRA Wiki markup for all JIRA operations:**
- `daf jira create` - Creating JIRA tickets
- `daf jira add-comment` - Adding JIRA comments
- `daf jira update` - Updating JIRA descriptions

**Note:** For GitHub/GitLab operations (`daf git create`, `daf git add-comment`, `daf git update`), use Markdown syntax instead. See **daf-git skill** for complete Markdown syntax reference.
