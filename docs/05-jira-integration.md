# JIRA Integration

Complete guide to integrating DevAIFlow with JIRA.

## Overview

JIRA integration is **completely optional**. The tool works perfectly fine for local session management without JIRA. However, if you use JIRA for task tracking, this integration provides:

- **Automatic ticket sync** - Discover assigned tickets and create sessions
- **Status transitions** - Auto-move tickets (New → In Progress → Done)
- **Progress comments** - Add session notes to JIRA tickets
- **Sprint dashboard** - View sprint progress with time tracking
- **Ticket metadata** - Enrich sessions with JIRA data

## API Version Compatibility

DevAIFlow supports **both JIRA Cloud and self-hosted JIRA instances** with automatic API version detection:

### Supported Versions

- ✅ **JIRA Cloud (Atlassian Cloud)** - Uses JIRA REST API v3
- ✅ **Self-Hosted JIRA (Server/Data Center)** - Uses JIRA REST API v2

### Automatic Detection

The tool automatically detects which API version to use:

1. **First Request**: Attempts to use API v2 (for self-hosted JIRA)
2. **Cloud Detection**: If the server returns HTTP 410 (endpoint deprecated), automatically switches to API v3
3. **Caching**: The detected version is cached for subsequent requests within the same session

This means you don't need to configure which API version to use - it's handled automatically based on your JIRA instance type.

### Migration from Deprecated Endpoints

As of August 2025, Atlassian Cloud has deprecated the `/rest/api/2/search` endpoint ([CHANGE-2046](https://developer.atlassian.com/changelog/#CHANGE-2046)). DevAIFlow handles this deprecation automatically:

- **Self-hosted JIRA**: Continues using API v2 (`/rest/api/2/search`)
- **Cloud JIRA**: Automatically uses API v3 (`/rest/api/3/search/jql`)

No configuration changes are needed - the migration is transparent to users.

## Prerequisites

### Required for JIRA Features

1. **JIRA API Token** (for Atlassian Cloud) or **Personal Access Token** (for self-hosted JIRA)

2. **Environment Variables**
   ```bash
   export JIRA_API_TOKEN="your-token-here"
   export JIRA_URL="https://jira.example.com"  # Optional, auto-detected
   ```

3. **JIRA CLI** (ankitpokhrel/jira-cli) - **Optional**

   The tool primarily uses the JIRA REST API for most operations. The JIRA CLI is only needed for:
   - `daf sync` - Listing tickets with JQL queries
   - `daf attach` - Attaching files to tickets

   To install JIRA CLI (if needed):
   ```bash
   # macOS
   brew install ankitpokhrel/jira-cli/jira-cli

   # Linux
   wget https://github.com/ankitpokhrel/jira-cli/releases/latest/download/jira_linux_amd64.tar.gz
   tar -xzf jira_linux_amd64.tar.gz
   sudo mv jira /usr/local/bin/
   ```

See [Installation Guide](02-installation.md) for detailed setup instructions.

## Authentication Setup

DevAIFlow supports two authentication methods depending on your JIRA deployment type.

### Atlassian Cloud (Cloud-Hosted JIRA)

Atlassian Cloud requires **Basic Authentication** with base64-encoded credentials.

**Step 1: Get Your JIRA Email Address**

Use the email address associated with your Atlassian account (e.g., `user@company.com`).

**Step 2: Generate API Token**

1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Give it a name (e.g., "DevAIFlow CLI")
4. Copy the generated token (you won't see it again)

**Step 3: Create Base64-Encoded Credentials**

Combine your email and API token with a colon, then encode to base64:

```bash
echo -n "user@company.com:your-api-token" | base64
```

This outputs a base64 string (this becomes your JIRA_API_TOKEN).

**Step 4: Configure Environment Variables**

```bash
# Set authentication type to basic
export JIRA_AUTH_TYPE=basic

# Set the base64-encoded credentials (paste output from step 3)
export JIRA_API_TOKEN="your-jira-token"

# Set your Atlassian Cloud URL
export JIRA_URL="https://yourcompany.atlassian.net"
```

**Step 5: Add to Shell Profile (Permanent)**

Add these to your `~/.zshrc` or `~/.bashrc`:

```bash
# JIRA Configuration (Atlassian Cloud)
export JIRA_AUTH_TYPE=basic
export JIRA_API_TOKEN="your-jira-token"
export JIRA_URL="https://yourcompany.atlassian.net"
```

Then reload:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

**Step 6: Verify Authentication**

```bash
# Test API access
curl -H "Authorization: Basic $JIRA_API_TOKEN" \
     "$JIRA_URL/rest/api/2/myself"
```

If successful, you'll see your user profile data.

### Self-Hosted JIRA (On-Premise)

Self-hosted JIRA uses **Bearer Authentication** with Personal Access Tokens.

**Step 1: Generate Personal Access Token**

1. Log into your JIRA instance
2. Go to: `https://jira.example.com` → **Profile** → **Personal Access Tokens**
3. Click **Create token**
4. Give it a name (e.g., "DevAIFlow CLI")
5. Set expiration (recommend 1 year)
6. Grant scopes: `read:jira-work`, `write:jira-work`
7. Copy the generated token

**Step 2: Configure Environment Variables**

```bash
# Set authentication type to bearer (default)
export JIRA_AUTH_TYPE=bearer

# Set your Personal Access Token
export JIRA_API_TOKEN="your-jira-token"

# Set your self-hosted JIRA URL
export JIRA_URL="https://jira.example.com"
```

**Step 3: Add to Shell Profile (Permanent)**

Add these to your `~/.zshrc` or `~/.bashrc`:

```bash
# JIRA Configuration (Self-Hosted)
export JIRA_AUTH_TYPE=bearer
export JIRA_API_TOKEN="your-jira-token"
export JIRA_URL="https://jira.example.com"
```

Then reload:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

**Step 4: Verify Authentication**

```bash
# Test API access
curl -H "Authorization: Bearer $JIRA_API_TOKEN" \
     "$JIRA_URL/rest/api/2/myself"
```

If successful, you'll see your user profile data.

### Authentication Type Summary

| JIRA Type | Auth Type | Token Format | Environment Variable |
|-----------|-----------|--------------|---------------------|
| **Atlassian Cloud** | `basic` | Base64 of `email:api-token` | `JIRA_AUTH_TYPE=basic` |
| **Self-Hosted** | `bearer` | Personal Access Token | `JIRA_AUTH_TYPE=bearer` |

### Security Best Practices

1. **Never commit tokens to git** - Add `.env` files to `.gitignore`
2. **Rotate tokens regularly** - Regenerate every 90-180 days
3. **Use minimal scopes** - Only grant required permissions
4. **Store securely** - Consider using a password manager
5. **Revoke unused tokens** - Clean up old tokens from your profile

### Troubleshooting Authentication

**Error: "Failed to parse Connect Session Auth Token"**
- You're using Atlassian Cloud but `JIRA_AUTH_TYPE` is not set to `basic`
- Solution: `export JIRA_AUTH_TYPE=basic`

**Error: "401 Unauthorized"**
- Token is invalid or expired
- For cloud: Regenerate base64 credentials with fresh API token
- For self-hosted: Generate new Personal Access Token

**Error: "Invalid token format"**
- For cloud: Verify base64 encoding is correct
- Test: `echo "$JIRA_API_TOKEN" | base64 -d` should show `email:api-token`

### How It Works

The tool uses the **JIRA REST API** for most operations:
- ✅ **Fetching tickets** - `GET /rest/api/2/issue/{key}`
- ✅ **Adding comments** - `POST /rest/api/2/issue/{key}/comment` (with Example Group visibility)
- ✅ **Transitioning tickets** - `POST /rest/api/2/issue/{key}/transitions`
- ✅ **Getting transitions** - `GET /rest/api/2/issue/{key}/transitions`

The JIRA CLI is used as fallback for:
- 🔄 **Listing tickets** - JQL query abstraction
- 📎 **File attachments** - Multipart upload handling

This hybrid approach provides:
- **Reliability** - Direct API control for critical operations
- **Visibility** - Proper comment restriction (Example Group only)
- **Performance** - Faster API calls, fewer timeouts
- **Convenience** - JQL abstraction for complex queries

## Configuration

Edit `$DEVAIFLOW_HOME/config.json`:

```json
{
  "jira": {
    "url": "https://jira.example.com",
    "user": "your-username",
    "transitions": {
      "on_start": {
        "from": ["New", "To Do"],
        "to": "In Progress",
        "prompt": false,
        "on_fail": "warn"
      },
      "on_complete": {
        "prompt": true
      }
    },
    "time_tracking": true
  }
}
```

### Configuration Options

- **url** - Your JIRA instance URL
- **user** - Your JIRA username
- **project** - JIRA project key (e.g., "PROJ") - used for creating issues
- **workstream** - JIRA workstream value (e.g., "Platform") - used for creating issues
- **transitions.on_start** - Auto-transition when opening session
  - **from** - List of statuses to transition from
  - **to** - Target status
  - **prompt** - Ask before transitioning (true/false)
  - **on_fail** - What to do if transition fails ("warn" or "block")
- **transitions.on_complete** - Auto-transition when completing session
  - **prompt** - Ask for target status (true/false)
- **time_tracking** - Enable time tracking for JIRA tickets (true/false)

**Note:** To control whether session summaries are automatically added to JIRA, use `prompts.auto_add_issue_summary` - see [Prompts Configuration](06-configuration.md#prompts-configuration)

### Configuring JIRA Project and Custom Fields

For creating JIRA issues, you need to configure your project and any custom field defaults:

```bash
# Set JIRA project key
daf config tui  # Navigate to JIRA Integration → Project Key PROJ

# Set custom field defaults (e.g., workstream, team, etc.)
daf config tui  # Navigate to JIRA Integration → Custom Field Defaults
                # Example: {"workstream": "Platform", "team": "Backend"}

# Set affected version for bugs (one-time configuration)
daf config tui  # Navigate to JIRA Integration → Affected Version v1.0.0
```

These values are saved to `config.json` and used automatically when creating issues.

**Note:** The affected version is required for bug creation. If not configured, `daf jira create bug` will prompt you to enter it and save it automatically.

Alternatively, provide them via flags:
```bash
daf jira create story \
  --summary "My story" \
  --project PROJ \
  --field workstream=Platform \
  --field team=Backend
```

### Configuring JIRA Transitions

Configure how tickets transition between statuses when you start or complete work:

**Configure on_start transition (when opening a session):**
```bash
# Interactive mode
daf config tui

# Command-line mode
daf config tui
  --from-status "New" \
  --from-status "To Do" \
  --to "In Progress" \
  --no-prompt
```

**Configure on_complete transition (when completing a session):**
```bash
# Interactive mode (recommended)
daf config tui

# Interactive selection from available transitions
daf config tui

# Automatic transition to specific status
daf config tui
  --no-prompt \
  --to "Done"
```

**Note:** For organization-specific JIRA workflows, these settings are pre-configured in organization configuration files. You only need to adjust them if your workflow differs.

## Creating JIRA Issues

**CRITICAL ERROR PREVENTION:**
- ❌ NEVER use `--field` with system fields (reporter, assignee, components, labels)
- ✅ System fields MUST use their dedicated options: `--reporter jdoe`, `--assignee alice`, `--components backend`
- If you use `--field reporter=jdoe`, the command will **EXIT WITH ERROR**
- Error message will tell you: `✗ 'reporter' is a system field. Use --reporter option instead of --field`

**Field Type Guidelines:**
- **System fields** (reporter, assignee, components, labels, security-level, etc.): Use dedicated CLI options
- **Custom fields** (customfield_*): Use `--field field_name=value` format

### Create a Bug

```bash
daf jira create bug \
  --summary "Customer backup fails with timeout" \
  --priority Major \
  --parent PROJ-59038 \
  --description-file /tmp/bug_description.txt

# With system fields (reporter, assignee, components, labels)
daf jira create bug \
  --summary "Production bug" \
  --reporter jdoe \
  --components backend \
  --labels urgent

# With custom fields
daf jira create bug \
  --summary "Critical bug" \
  --field severity=Critical \
  --field size=L
```

### Create a Story

```bash
# Interactive mode (prompts for description)
daf jira create story \
  --summary "Implement backup and restore feature" \
  --priority Major \
  --parent PROJ-59038 \
  --interactive

# With description from file
daf jira create story \
  --summary "Implement backup feature" \
  --parent PROJ-59038 \
  --description-file /tmp/story.txt

# Inline description
daf jira create story \
  --summary "Implement backup feature" \
  --parent PROJ-59038 \
  --description "User story goes here"
```

### Create a Task

```bash
daf jira create task \
  --summary "Update backup documentation" \
  --parent PROJ-59038 \
  --description "Update docs to reflect new backup feature"
```

### Create an Epic

```bash
# Interactive mode (prompts for description)
daf jira create epic \
  --summary "Backup and Restore Feature" \
  --priority Major \
  --interactive

# With description from file
daf jira create epic \
  --summary "Backup and Restore Feature" \
  --description-file /tmp/epic.txt

# Inline description
daf jira create epic \
  --summary "Backup and Restore Feature" \
  --description "h2. *Background*\n\nImplement comprehensive backup and restore capabilities..."
```

**Note:** Epics are typically top-level containers and usually don't have parent links. However, the `--parent` parameter is supported if your JIRA workflow requires it.

### Create a Spike

```bash
# Interactive mode (prompts for description)
daf jira create spike \
  --summary "Research API authentication patterns" \
  --priority Major \
  --parent PROJ-59038 \
  --interactive

# With description from file
daf jira create spike \
  --summary "Research backup strategies" \
  --parent PROJ-59038 \
  --description-file /tmp/spike.txt

# Inline description
daf jira create spike \
  --summary "Research backup strategies" \
  --parent PROJ-59038 \
  --description "h3. *User Story*\n\nAs a developer, I want to research..."
```

**Note:** Spikes should typically be linked to an Epic via the `--parent` parameter.

### Create with Session

Automatically create a `cs` session for the newly created issue:

```bash
daf jira create story \
  --summary "New feature" \
  --parent PROJ-59038 \
  --create-session
```

This creates the JIRA issue and immediately creates a session for it.

### Viewing JIRA Issues

View any JIRA issue in a Claude-friendly format:

```bash
daf jira view PROJ-12345
```

This is more reliable than using curl and handles authentication automatically.

### Updating JIRA Issues

**CRITICAL ERROR PREVENTION:**
- ❌ NEVER use `--field` with system fields (reporter, assignee, components, labels)
- ✅ System fields MUST use their dedicated options: `--reporter jdoe`, `--assignee alice`, `--components backend`
- If you use `--field reporter=jdoe`, the command will **EXIT WITH ERROR**
- Error message will tell you: `✗ 'reporter' is a system field. Use --reporter option instead of --field`

```bash
# Update description
daf jira update PROJ-12345 --description "New description text"

# Update from file
daf jira update PROJ-12345 --description-file /tmp/new_description.txt

# Update multiple fields
daf jira update PROJ-12345 \
  --priority Major \
  --field workstream=Platform \
  --summary "Updated summary"

# Update with system fields (reporter, assignee, components, labels)
daf jira update PROJ-12345 --assignee alice --components ansible-saas --labels backend,urgent
daf jira update PROJ-12345 --reporter jdoe --components backend --security-level Internal
daf jira update PROJ-12345 --assignee bob --reporter alice --components backend

# Update with custom fields (use --field for ALL custom fields)
daf jira update PROJ-12345 --field severity=Critical --field size=L
daf jira update PROJ-12345 --field epic_link=PROJ-59000 --field story_points=5
daf jira update PROJ-12345 --field acceptance_criteria="- Criterion 1\n- Criterion 2"

# Add PR link (auto-appends to existing links)
daf jira update PROJ-12345 --git-pull-request "https://github.com/org/repo/pull/123"
```

### Custom Fields Support

Both `daf jira create` and `daf jira update` support dynamic field discovery with strict separation between system and custom fields:

**IMPORTANT:** ALL custom fields (customfield_*) MUST use `--field field_name=value` format. System fields (reporter, assignee, components, labels) have dedicated CLI options.

#### For Creating Issues (Cached Fields)

```bash
# View available fields (both system and custom)
daf jira create bug --help
# → Shows system field options: --reporter, --assignee, --components, --labels
# → Shows available custom fields in --field help text

# Use system fields with dedicated options
daf jira create bug \
  --summary "Critical bug" \
  --reporter jdoe \
  --assignee alice \
  --components backend \
  --labels urgent

# Use custom fields with --field
daf jira create bug \
  --summary "Critical bug" \
  --field severity=Critical \
  --field size=L \
  --field workstream=Platform
```

Creation fields are discovered once and cached in `$DEVAIFLOW_HOME/config.json`. Refresh with:

```bash
daf config refresh-jira-fields
```

#### For Updating Issues

```bash
# View available fields for a specific issue
daf jira update PROJ-12345 --help
# → Shows system field options: --reporter, --assignee, --components, --labels
# → Shows available custom fields in --field help text

# Use system fields with dedicated options
daf jira update PROJ-12345 \
  --assignee alice \
  --components backend \
  --labels urgent,backend

# Use custom fields with --field
daf jira update PROJ-12345 \
  --field epic_link=PROJ-59000 \
  --field story_points=5 \
  --field severity=Critical
```

**How it works:**

The command dynamically discovers available fields:
1. System fields (non-customfield_*) get dedicated CLI options like `--reporter`, `--assignee`
2. Custom fields (customfield_*) are documented in `--field` help text
3. Trying to use `--field` with system fields will EXIT WITH ERROR
4. This strict separation prevents API errors and makes field types explicit

**Key Principles:**
- **System fields**: Use dedicated options (e.g., `--reporter jdoe`, `--assignee alice`)
- **Custom fields**: Use `--field key=value` (e.g., `--field severity=Critical`)
- **Error prevention**: Mixing field types causes immediate error with helpful message
- **Field discovery**: Run `daf config refresh-jira-fields` to update available custom fields

## Creating Sessions with JIRA

### Session Naming

**For Ticket Creation Sessions (`daf jira new`)** - PROJ-60665:
- Sessions are automatically renamed to `creation-<TICKET_KEY>` after ticket creation
- Example: `my-session` → `creation-PROJ-12345`
- Simplifies finding sessions without complex metadata
- Only happens when running inside a Claude Code session
- Reopen with: `daf open creation-PROJ-12345`

**For Development Sessions (`daf new --jira`):**

#### Interactive Name

```bash
daf new --jira PROJ-12345 --goal "Implement backup feature"
```

Prompts for session name:
```
Session name [PROJ-12345]:
```

Press Enter to use JIRA key, or type a custom name.

#### Explicit Name

```bash
daf new --name "backup" --jira PROJ-12345 --goal "Implement backup feature"
```

Good for multi-repo work where you want the same name across repositories.

### What Happens

1. **Validates JIRA ticket** - Fails fast if ticket doesn't exist
2. **Fetches ticket metadata** - Title, status, sprint, assignee, story points
3. **Creates session** - Links JIRA key to session
4. **Suggests git branch** - Based on JIRA key (e.g., `PROJ-12345-backup`)
5. **Transitions ticket** (if configured) - Moves to "In Progress"

### JIRA Validation

When using `--jira` flag, the tool validates the ticket exists:

```bash
daf new --jira PROJ-99999 --goal "Test"
```

If ticket doesn't exist:
```
Error: JIRA ticket PROJ-99999 not found or you don't have access to it.

Verify:
  1. Ticket key is correct
  2. You have access to the ticket
  3. JIRA CLI is configured: jira issue view PROJ-99999
```

This prevents creating sessions with invalid JIRA keys.

## Linking JIRA to Existing Sessions

### Link JIRA

```bash
daf link redis-test --jira PROJ-12346
```

This:
1. Validates ticket exists
2. Fetches ticket metadata
3. Links ticket to session
4. Updates all conversations in the session

**Options:**
- `--force` - Skip confirmation prompt when replacing existing link (useful for scripts and automation)

### Unlink JIRA

```bash
daf unlink redis-test
```

Removes JIRA association but keeps all session data.

**Options:**
- `--force` - Skip confirmation prompt (useful for scripts and automation)

## Syncing JIRA Tickets

### Sync All Assigned Tickets

```bash
daf sync
```

Discovers all tickets assigned to you and creates sessions:
- Stories (with or without story points)
- Bugs
- Tasks

### Sync Current Sprint Only

```bash
daf sync --sprint current
```

Creates sessions only for tickets in your current sprint.

### Sync Specific Sprint

```bash
daf sync --sprint "2025-01"
```

### Sync by Ticket Type

```bash
daf sync --type Story
daf sync --type Bug
```

### Sync by Epic

```bash
daf sync --epic PROJ-36419
```

Creates sessions for all tickets in the specified epic.

### Dry Run

```bash
daf sync --dry-run
```

Preview what would be synced without creating sessions:
```
Would create sessions for:

  PROJ-12345: Implement customer backup
    Type: Story | Points: 5 | Status: To Do
    Sprint: 2025-01

  PROJ-12346: Fix password reset bug
    Type: Bug | Status: In Progress
    Sprint: 2025-01

  PROJ-12347: Add 2FA support
    Type: Story | Points: 8 | Status: To Do
    Sprint: 2025-01

Total: 3 tickets (13 story points)
```

### What Gets Synced

For each ticket, creates a session with:
- **name** - JIRA key (e.g., "PROJ-12345")
- **goal** - JIRA summary/title
- **issue_key** - JIRA key
- **jira_summary** - Ticket title
- **jira_status** - Current status
- **sprint** - Sprint name/ID
- **jira_assignee** - Assignee username
- **status** - "created" (not started yet)

### Repository Detection

After sync, when you first open a synced session:

```bash
daf open PROJ-12345
```

You'll be prompted to select a working directory:
```
No working directory set for this session.

Detected repositories:
  1. backend-api
  2. frontend-app
  3. mobile-app

Or enter custom path: /path/to/project

Select working directory [1-3]:
```

The tool uses keyword matching based on JIRA summary to suggest repositories.

## Status Transitions

### Automatic Transition on Start

When configured, opening a session transitions the ticket:

```bash
daf open PROJ-12345
```

With this config:
```json
{
  "transitions": {
    "on_start": {
      "from": ["New", "To Do"],
      "to": "In Progress",
      "prompt": false,
      "on_fail": "warn"
    }
  }
}
```

Output:
```
✓ Transitioned PROJ-12345: To Do → In Progress
```

If ticket is not in "New" or "To Do", transition is skipped.

### Reopening Closed Tickets

When you reopen a session for a ticket that was previously marked as Done/Closed, the tool automatically detects this and prompts you to reopen it:

```bash
daf open PROJ-12345
```

If the ticket is in a closed state (Done, Closed, Resolved, Release Pending, or Review):

```
⚠  JIRA ticket PROJ-12345 is currently: Done
You are reopening work on a ticket that was previously marked as complete.

Transition PROJ-12345 back to 'In Progress'? [Y/n]:
```

If you confirm:
```
✓ Transitioned PROJ-12345: Done → In Progress
✓ Added comment to PROJ-12345
```

The tool automatically:
1. Transitions the ticket back to "In Progress"
2. Adds a comment explaining why the ticket was reopened
3. Continues opening your session

**Use Cases:**
- Bug found after closing - Ticket marked Done, bug discovered, need to reopen
- Additional work needed - Ticket closed, customer requests changes
- Review feedback - Ticket in Code Review or Done, feedback requires changes
- Accidentally completed - Ticket marked complete too early, need to continue work

**Flexible Options:**
- If you decline the transition, you can still continue opening the session without updating JIRA
- If the transition fails (e.g., missing required fields), you can choose to continue anyway or cancel

### Automatic Transition on Complete

When configured, completing a session offers to transition:

```bash
daf complete PROJ-12345
```

#### Interactive Transition (prompt: true)

With this config:
```json
{
  "transitions": {
    "on_complete": {
      "prompt": true,
      "on_fail": "warn"
    }
  }
}
```

The tool will dynamically fetch available transitions from the JIRA API and display them:

```
Transition JIRA ticket PROJ-12345?

Current status: In Progress

  1. Skip (keep current status)
  2. New
  3. Refinement
  4. Backlog
  5. Review
  6. Release Pending
  7. Closed

Select target status [1/2/3/4/5/6/7] (1):
```

**Note:** Available transitions are automatically fetched from the JIRA API based on the ticket's current status, so you only see valid transitions for your workflow.

#### Automatic Transition (prompt: false)

For automatic transitions without user interaction:

```json
{
  "transitions": {
    "on_complete": {
      "prompt": false,
      "to": "Done",
      "on_fail": "warn"
    }
  }
}
```

This will automatically transition the ticket to "Done" when you complete the session, without prompting.

### Explicit Status on Complete

```bash
daf complete PROJ-12345 --status "Code Review"
```

Transitions directly without prompting.

### Failure Handling

**on_fail: "warn"** (default)
- Shows warning if transition fails
- Continues with session operation

**on_fail: "block"**
- Shows error if transition fails
- Aborts session operation

Example with "warn":
```
⚠ Failed to transition PROJ-12345: Transition not available
Session marked as complete locally
```

Example with "block":
```
✗ Error: Cannot transition PROJ-12345 to In Progress
Current status 'Code Review' does not allow this transition
Session not opened
```

## Progress Notes with JIRA

> **Important:** `daf note` must be run **outside** Claude Code to prevent data conflicts. Exit Claude Code first before adding notes. Inside Claude Code, use `/daf-notes` to view notes (read-only).

### Local Note Only

```bash
daf note PROJ-12345 "Implemented upload endpoint"
```

Saved to `$DEVAIFLOW_HOME/sessions/PROJ-12345/notes.md` only.

### Note with JIRA Comment

```bash
daf note PROJ-12345 "Backend complete, ready for review" --jira
```

This:
1. Saves note locally (always succeeds)
2. Adds note as JIRA comment (best effort)

If JIRA sync fails, note is still saved locally.

JIRA comment format:
```
[Session Note - 2025-11-20 14:30:00]

Backend complete, ready for review
```

### View Notes in JIRA

Notes added with `--jira` appear as comments on the ticket, visible to your team.

## Sprint Dashboard

### View Sprint Status

```bash
daf status
```

Output:
```
Current Sprint: 2025-01
Sprint Goal: Implement customer backup and restore features

In Progress:
🚧 PROJ-12345  Customer backup          5 pts | 3h 45m | 75%
🚧 PROJ-12346  Fix password reset       3 pts | 1h 20m | 40%

Ready to Start:
🆕 PROJ-12347  Add 2FA support          8 pts | 0h     | 0%
🆕 PROJ-12348  Update documentation     2 pts | 0h     | 0%

Code Review:
✅ PROJ-12344  User profile API         5 pts | 4h 10m | 100%

Done:
✓ PROJ-12343  Login endpoint           3 pts | 2h 30m | 100%

Sprint Progress:
  Completed: 8 pts (30%)
  In Progress: 8 pts (30%)
  Remaining: 10 pts (40%)
  Total: 26 pts

Time Spent: 11h 45m
Estimated Remaining: ~14h
```

### Sprint Metrics

The dashboard shows:
- **Current Status** - Where each ticket is in the workflow
- **Story Points** - From JIRA
- **Time Spent** - Tracked locally by daf tool
- **Progress %** - Estimated based on activity
- **Sprint Totals** - Points and time across all tickets

## Completion with AI Summaries

### Basic Completion

```bash
daf complete PROJ-12345
```

Prompts:
```
Generate AI summary of work done? [Y/n]:
```

If you say yes:
1. Analyzes conversation history
2. Generates natural language summary
3. Offers to add summary to JIRA ticket
4. Offers to transition ticket status

### AI Summary Example

```
Session: PROJ-12345 - Customer backup

Summary:
Implemented comprehensive backup system with S3 integration. Created backup
service with upload/download endpoints, metadata validation, and encryption.
Added retry logic for failed uploads and comprehensive error handling.

Key Accomplishments:
- POST /api/backup/upload endpoint with multipart file handling
- S3 bucket integration with server-side encryption (AES-256)
- Backup metadata storage in PostgreSQL
- Retry mechanism with exponential backoff
- Input validation and error responses

Files Modified:
- src/services/backup.service.ts (new)
- src/controllers/backup.controller.ts (new)
- src/models/backup.model.ts (new)
- src/routes/backup.routes.ts (new)
- src/utils/s3.client.ts (updated)

Tests Added:
- tests/backup.service.test.ts (35 tests)

Next Steps:
- Implement restore endpoint
- Add download progress tracking
- Update API documentation
```

### Add Summary to JIRA

```
Add this summary to JIRA ticket PROJ-12345? [Y/n]:
```

If you say yes, summary is added as a comment on the JIRA ticket.

### Skip AI Summary

```bash
daf complete PROJ-12345 --no-ai-summary
```

Or just say "n" when prompted.

## Time Tracking with JIRA

### Automatic Time Tracking

When configured:
```json
{
  "jira": {
    "time_tracking": true
  }
}
```

Time is tracked for each work session and associated with the JIRA ticket.

### View Time for JIRA Ticket

```bash
daf time PROJ-12345
```

Output:
```
Time Tracking for: PROJ-12345

Work Sessions:
  Session #1 (backend-api):
    1. 2025-11-20 09:00:00 → 11:30:00  (2h 30m)
    2. 2025-11-20 14:00:00 → 15:15:00  (1h 15m)

  Session #2 (frontend-app):
    1. 2025-11-20 16:00:00 → 17:30:00  (1h 30m)

Total Time: 5h 15m
JIRA Status: In Progress
Sprint: 2025-01
```

### Time Across Multiple Conversations

When you have multiple conversations in one session for one JIRA ticket (multi-repo work), time is tracked at the session level across all conversations.

## Multi-Repository JIRA Workflows

### Scenario: One Ticket, Multiple Repos

```bash
# Backend work
cd ~/projects/backend-api
daf new --name "backup" --jira PROJ-12345 --goal "Backend API"

# Frontend work
cd ~/projects/frontend-app
daf new --name "backup" --jira PROJ-12345 --goal "Frontend UI"

# Infrastructure
cd ~/projects/terraform
daf new --name "backup" --jira PROJ-12345 --goal "S3 bucket config"
```

All three sessions linked to PROJ-12345.

### Working Across Sessions

```bash
# Work on backend
daf open backup
# Select #1 (backend-api)

# Later, work on frontend
daf open backup
# Select #2 (frontend-app)
```

### Progress Notes Across Sessions

Exit Claude Code first, then add notes from each repository:

```bash
# From backend repo
daf note backup "Backend API complete" --jira

# From frontend repo
daf note backup "UI in progress" --jira
```

Both notes appear on the same JIRA ticket.

### Completing Multi-Repo Work

```bash
# Complete each session
daf complete backup  # In backend repo
daf complete backup  # In frontend repo
daf complete backup  # In terraform repo
```

When completing the last session, you can:
1. Generate AI summary (combines all sessions)
2. Add summary to JIRA
3. Transition JIRA ticket to Done

## JIRA Search and Filters

### List Sessions by JIRA

```bash
daf list | grep PROJ-12345
```

### Search Sessions

```bash
daf search "backup" --jira-key PROJ-12345
```

### Filter by Sprint

```bash
daf list --sprint "2025-01"
```

### Filter by Status

```bash
daf list --jira-status "In Progress"
```

## Exporting JIRA Sessions

### Export to Markdown

```bash
daf export-md PROJ-12345 --ai-summary
```

Creates `PROJ-12345.md`:
```markdown
# PROJ-12345: Customer backup and restore

**Type:** Story
**Status:** In Progress
**Sprint:** 2025-01
**Story Points:** 5
**Assignee:** your-username
**Link:** https://jira.example.com/browse/PROJ-12345

## Goal

Implement customer backup and restore features

## Summary

Implemented comprehensive backup system...

## Progress Notes

### 2025-11-20 09:30:00
Implemented upload endpoint

### 2025-11-20 14:15:00
Backend complete, ready for review

## Time Tracking

- **Total Time:** 5h 15m
- **Work Sessions:** 3
- **Status:** In Progress
```

Perfect for documentation, handoffs, or sprint reviews.

### Export Multiple Tickets

```bash
daf export-md PROJ-12345 PROJ-12346 PROJ-12347 --combined
```

Creates single file with all tickets.

## Troubleshooting JIRA Integration

### Authentication Failed

**Error:** `401 Unauthorized`, `JIRA_API_TOKEN not set`, or `Authentication failed`

**Solutions:**

1. **Check token is set:**
   ```bash
   echo $JIRA_API_TOKEN
   ```

2. **For self-hosted JIRA:** Use Personal Access Token, not API token
   - Go to https://jira.example.com → Profile → Personal Access Tokens
   - Create new token with `read:jira-work`, `write:jira-work` scopes
   - Set in environment:
     ```bash
     export JIRA_API_TOKEN="your-token-here"
     ```

3. **Add to shell profile:**
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   echo 'export JIRA_API_TOKEN="your-token-here"' >> ~/.zshrc
   source ~/.zshrc
   ```

4. **Test API access:**
   ```bash
   curl -H "Authorization: Bearer $JIRA_API_TOKEN" \
        "https://jira.example.com/rest/api/2/myself"
   ```

### Debug Logging

When troubleshooting JIRA API issues, enable debug logging to see full request/response details:

```bash
# Enable debug logging
export DEVAIFLOW_DEBUG=1

# Run your JIRA command
daf jira create bug --summary "Test" --parent PROJ-123

# Disable when done
unset DEVAIFLOW_DEBUG
```

**What you'll see:**
- Full HTTP method and URL
- Complete request payload (all fields being sent)
- JIRA server response
- HTTP status codes
- Field validation errors from JIRA

**Use cases:**
- Troubleshooting custom field validation errors
- Understanding why JIRA rejects ticket creation
- Debugging field mapping issues
- Verifying what values are being sent to JIRA
- Testing JIRA API integration

**Note:** Debug output is automatically disabled when using `--json` flag.

For more details, see [Troubleshooting Guide - JIRA API Debug Logging](11-troubleshooting.md#jira-api-debug-logging).

### JIRA URL Not Detected

**Error:** API calls fail, or wrong JIRA instance

**Solution:**

Set JIRA URL explicitly:
```bash
export JIRA_URL="https://jira.example.com"
```

The tool auto-detects from:
1. `JIRA_URL` environment variable
2. `~/.config/.jira/.config.yml` (jira-cli config)
3. Defaults to `https://jira.example.com`

### JIRA CLI Not Found (for sync/attach)

**Error:** `jira: command not found` when using `daf sync` or file attachments

**Solution:**
```bash
# Verify installation
which jira

# Install if missing (macOS)
brew install ankitpokhrel/jira-cli/jira-cli

# Test
jira version
```

**Note:** Most JIRA operations (fetch, comment, transition) work without jira-cli using the REST API.

### JIRA Ticket Not Found

**Error:** `JIRA ticket PROJ-12345 not found`

**Solutions:**

1. **Verify ticket exists:**
   ```bash
   jira issue view PROJ-12345
   ```

2. **Check access permissions**

3. **Verify JIRA URL:**
   ```bash
   cat $DEVAIFLOW_HOME/config.json | grep url
   ```

### Transition Failed

**Error:** `Transition not available`

**Causes:**
- Ticket not in expected status
- Workflow doesn't allow transition
- Permissions issue

**Solutions:**

1. **Check current status:**
   ```bash
   jira issue view PROJ-12345
   ```

2. **View available transitions:**
   ```bash
   jira issue move PROJ-12345
   ```

3. **Update config with correct transitions**

4. **Use on_fail: "warn"** to continue despite failures

### Can't Add Comments

**Error:** `Failed to add comment`

**Solutions:**

1. **Check permissions:** Ensure you can comment on the ticket

2. **Test manually:**
   ```bash
   jira issue comment add PROJ-12345 "test comment"
   ```

3. **Check prompts.auto_add_issue_summary setting:**
   ```json
   {
     "prompts": {
       "auto_add_issue_summary": true
     }
   }
   ```
   See [Prompts Configuration](06-configuration.md#promptsauto_add_issue_summary) for details.

### Sync Not Working

**Problem:** `daf sync` returns no tickets

**Solutions:**

1. **Test JIRA CLI:**
   ```bash
   jira me
   jira issue list --assignee $(jira me)
   ```

2. **Check filters:**
   ```bash
   daf sync --dry-run  # See what would be synced
   ```

3. **Verify assigned tickets exist:**
   ```bash
   jira issue list --assignee $(jira me) --type Story
   ```

## Best Practices

### 1. Use Sync for Sprint Planning

Start of sprint:
```bash
daf sync --sprint current
```

Creates sessions for all sprint tickets at once.

### 2. Link JIRA When Ready

Don't rush to link JIRA. You can always link later:
```bash
# Start without JIRA
daf new --name "experiment" --goal "Test approach"

# Link when ready
daf link experiment --jira PROJ-12345
```

### 3. Use Notes for Team Communication

Add notes with `--jira` flag for team visibility (exit Claude Code first):
```bash
daf note PROJ-12345 "Backend complete, needs UI work" --jira
```

### 4. Complete with AI Summaries

Always generate AI summary on completion:
```bash
daf complete PROJ-12345
# Say yes to AI summary
# Say yes to add to JIRA
```

Provides great documentation for team and future reference.

### 5. Configure Transitions Carefully

Start with "warn" mode:
```json
{
  "on_start": {
    "on_fail": "warn"
  }
}
```

Once confident, switch to "block" for strict workflow enforcement.

### 6. Review Sprint Status Regularly

```bash
daf status  # Daily standup
```

Keeps you aware of sprint progress.

### 7. Export Sessions for Documentation

End of sprint:
```bash
daf export-md PROJ-12345 PROJ-12346 --combined --output sprint-report.md
```

## Next Steps

- [Configuration Reference](06-configuration.md) - Detailed config options
- [Commands Reference](07-commands.md) - All JIRA-related commands
- [Workflows](08-workflows.md) - Step-by-step JIRA workflows
- [Troubleshooting](11-troubleshooting.md) - JIRA integration issues
