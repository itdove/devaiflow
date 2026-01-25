# DevAIFlow Tool Usage Guide for Claude

This file provides essential instructions for using the `daf` tool (DevAIFlow) within Claude Code sessions. It is automatically loaded as context when you open a session via `daf open`.

**What is daf?** The `daf` tool (DevAIFlow) is a Claude Code session manager that helps organize development work, track time, and optionally integrate with JIRA for ticket management.

**When to use this guide:** This file is automatically read when sessions are opened. Refer to it when you need to:
- Understand JIRA issue template requirements (see Templates section below)
- Get project-specific context about daf tool usage

**Note**: Examples use generic placeholders (PROJECT, YourWorkstream). Actual values are configured in `~/.daf-sessions/config.json`.

---

## Detailed CLI Usage Documentation

For comprehensive CLI tool usage, refer to the **DevAIFlow skills** deployed to your workspace:

- **daf-cli skill** - Complete daf command reference, session management, JIRA integration
- **git-cli skill** - Git version control commands and workflows
- **gh-cli skill** - GitHub CLI for PR creation and GitHub operations
- **glab-cli skill** - GitLab CLI for MR creation and GitLab operations

**Deploying skills:** Run `daf upgrade` to deploy/update skills to your workspace's `.claude/skills/` directory.

**Accessing skills:** Skills are automatically available in Claude Code sessions. Claude will use them as needed for CLI operations.

---

## JIRA Issue Templates

**IMPORTANT**: See **ORGANIZATION.md** for:
- JIRA Wiki markup syntax requirements (mandatory for all JIRA fields)
- Complete JIRA issue templates for all issue types (Epic, Story, Spike, Bug, Task)
- Organization-specific JIRA policies and standards (if configured)

ORGANIZATION.md is automatically loaded as context when you open sessions via `daf open` or `daf jira new`.

---

## Quick Reference

For complete command documentation, see the **daf-cli skill**.

**Common Commands:**
```bash
# Session Management
daf new --name "feature-name" --goal "Description"
daf open <session-name-or-jira-key>
daf open <session-name> --path <repo-path>  # Multi-conversation: auto-select repo
daf open <session-name> --new-conversation  # Archive current, start fresh
daf open <session-name> --json  # Non-interactive mode for automation/CI-CD
daf complete <session-name>

# JIRA Operations
daf jira view PROJ-12345
daf jira create {bug|story|task} --summary "..." --parent PROJ-1234
daf jira update PROJ-12345 --description "..."
daf jira update PROJ-12345 --field <field_name>=<value>  # Update custom field

# Configuration
daf config tui  # Interactive configuration editor
daf config show-fields  # List available custom fields
daf config refresh-jira-fields  # Refresh field mappings from JIRA

# Workspace Management (AAP-63377)
daf workspace list                              # List all workspaces (CAN run in sessions)
daf new -w <name>                               # Create session in specific workspace (quick switch)
daf open <session> -w <name>                    # Override session workspace (quick switch)
# Config commands (RESTRICTED - run outside sessions):
daf workspace add <name> <path> --default       # Add workspace to config
daf workspace add <path>                        # Auto-derive name from path (e.g., ~/dev/my-project → my-project)
daf workspace remove <name>                     # Remove workspace from config
daf workspace rename <old-name> <new-name>      # Rename workspace (updates all sessions)
daf workspace set-default <name>                # Change global default (NOT for switching!)
```

**Multi-Conversation Sessions:**
When working on tasks that span multiple repositories, you can use `--path` to specify which repository to work on:
```bash
# Auto-select conversation by repository path
daf open PROJ-12345 --path /path/to/repo
daf open PROJ-12345 --path repo-name  # Repository name from workspace

# Without --path, you'll be prompted to select which conversation to open
daf open PROJ-12345  # Shows interactive conversation selection menu
```

**Workspaces (AAP-63377):**
Workspaces enable concurrent multi-branch development by organizing repositories into named locations (similar to VSCode workspaces):

- **Use Case**: Work on the same project in different workspaces simultaneously without conflicts
- **Example**: `primary` workspace for main development, `feat-caching` for experimental branch, `product-a` for specific product
- **Session Memory**: Sessions remember their workspace and automatically use it on reopen
- **Concurrent Sessions**: You can have active sessions in different workspaces on the same project
- **Priority**: `--workspace` flag > session stored workspace > default workspace > interactive prompt

```bash
# View workspaces (can run inside sessions)
daf workspace list

# Switch workspace per-session with -w flag (RECOMMENDED)
daf new --name AAP-123 -w feat-caching    # Create in feat-caching
daf new --name AAP-456 -w product-a       # Create in product-a
daf open AAP-123 -w primary               # Override to primary temporarily

# Sessions remember workspace automatically
daf open AAP-123  # Uses feat-caching (remembered from creation)
daf open AAP-456  # Uses product-a (remembered from creation)

# set-default changes GLOBAL default (not for switching per-session)
# Only use this for permanent config changes, not for switching workspaces
daf workspace set-default primary  # (RESTRICTED - run outside sessions)
```

**Important**: Use the `-w` (or `--workspace`) flag to switch workspaces per-session. Don't use `set-default` for switching - it changes the global default for all new sessions.

**Note**: Workspace management commands (`add`, `remove`, `rename`, `set-default`) are **RESTRICTED** and must be run outside Claude Code sessions. Only `daf workspace list` can run inside sessions.

For detailed usage, workflow examples, and troubleshooting, refer to the **daf-cli skill**.

---

## Discovering Custom Fields

**IMPORTANT**: Custom fields are organization-specific and configured via field_mappings in `organization.json`.

### How to Find Available Custom Fields

**Method 1: Use the show-fields command (RECOMMENDED)**
```bash
# Display all available custom fields in a readable format
daf config show-fields

# Get JSON output for programmatic use
daf config show-fields --json
```

**Method 2: Read the organization configuration**
```bash
# View the organization.json file to see all field mappings
cat ~/.daf-sessions/ORGANIZATION.md
# Look for the "field_mappings" section which shows available field names
```

**Method 3: Check field_mappings in organization.json**
The configuration file at `~/.daf-sessions/organization.json` contains a `field_mappings` section:
```json
{
  "field_mappings": {
    "field_name_1": {
      "id": "customfield_12345",
      "name": "Display Name",
      "type": "string",
      "allowed_values": ["Value1", "Value2"]
    },
    "field_name_2": {
      "id": "customfield_67890",
      "name": "Another Field"
    }
  }
}
```

**Method 4: Refresh field mappings from JIRA**
```bash
# This command fetches the latest field definitions from JIRA
daf config refresh-jira-fields

# Then view the updated fields
daf config show-fields
```

### Using Custom Fields

Once you know the field names from field_mappings, use them with the `--field` parameter:

```bash
# Create issue with custom fields
daf jira create bug --summary "..." --parent PROJ-1234 \
  --field field_name_1="Value1" \
  --field field_name_2="Some value"

# Update custom fields
daf jira update PROJ-12345 --field field_name_1="NewValue"

# Filter sessions by custom fields
daf list --field field_name_1="Value1"
daf sync --field field_name_1="Value1"
```

**Key Points:**
- Custom field names come from the `field_mappings` configuration
- Use the **field name** (not the customfield ID) with `--field`
- Field names are organization-specific and must be configured
- If a field has `allowed_values`, only those values are valid
- Run `daf config refresh-jira-fields` to update field definitions from JIRA

### Understanding Sync Filters

When using `daf sync`, tickets are filtered based on configuration in `organization.json`:

**To see sync filter configuration:**
```bash
daf config show-sync-filters
daf config show-sync-filters --json
```

**Sync filters control:**
- `status`: Which JIRA statuses to sync (e.g., "To Do", "In Progress")
- `required_fields`: Fields that MUST be present on tickets (uses field names from field_mappings)
- `assignee`: Filter by assignee ("currentUser()", username, or null for all)

**Example:**
If `required_fields: ["sprint", "workstream"]`, only tickets that have BOTH sprint AND workstream set will be synced.

---

## Development Workflow with daf Tool

**IMPORTANT FOR CLAUDE AGENTS**: When working in sessions opened via `daf open`, follow this workflow:

### During the Session (daf open)

**CRITICAL - FIRST STEP: Read Acceptance Criteria**
- **IMMEDIATELY** after session opens, run: `daf jira view <JIRA-KEY>`
- **READ** and **UNDERSTAND** all acceptance criteria checkboxes
- **PLAN** your work to address each criterion
- **TRACK** progress on each criterion as you work

**Development Work:**
- Focus on making code changes and implementing features
- **VERIFY** each acceptance criterion as you complete related work
- **TEST** that criteria are actually met (run tests, check implementation)
- Use `daf note` to track acceptance criteria progress: `daf note <JIRA-KEY> "Completed AC #1: [description]"`
- Do NOT create git commits manually
- Do NOT create PRs or MRs using gh/glab commands
- Do NOT use git add, git commit, or git push commands

**Before Exiting Session:**
- **REVIEW** all acceptance criteria one final time
- **UPDATE** JIRA to tick completed criteria: `daf jira update <JIRA-KEY> --acceptance-criteria "- [x] criterion 1\n- [x] criterion 2\n- [] pending criterion 3"`
- If any criteria are incomplete, document why in a note

### Completing the Session (daf complete)
The `daf complete` command handles ALL git operations automatically:
- Commits all changes with AI-generated commit messages
- Pushes branch to remote
- Creates draft PR/MR with proper template
- Updates JIRA ticket with session summary
- Marks session as complete

**Why this matters**: The daf tool manages the complete development workflow. Manual git operations can interfere with session tracking, proper attribution (Co-Authored-By), and JIRA integration.

### Common Workflow
```bash
# 1. User opens session (outside Claude Code)
daf open PROJ-12345

# 2. Claude IMMEDIATELY reads ticket and acceptance criteria
daf jira view PROJ-12345
# Claude identifies all acceptance criteria checkboxes and plans work

# 3. Claude makes code changes in the session
# - Edit files as requested
# - Run tests to verify acceptance criteria are met
# - Track AC progress: daf note PROJ-12345 "Completed AC #1: [description]"
# - Verify each criterion as work progresses

# 4. Before exiting, Claude updates JIRA with completed criteria
daf jira update PROJ-12345 --acceptance-criteria "- [x] criterion 1
- [x] criterion 2
- [] pending criterion 3"

# 5. User exits Claude Code

# 6. User completes session (outside Claude Code)
daf complete PROJ-12345
# This handles: commit, push, PR/MR creation, JIRA update
```

**Exception**: For ticket_creation sessions (`daf jira new`), git operations are skipped entirely as these are analysis-only sessions.

---

## Additional Resources

- **daf-cli skill** - Complete daf command reference
- **git-cli skill** - Git workflow and commands
- **gh-cli skill** - GitHub PR creation
- **glab-cli skill** - GitLab MR creation
- Run `daf --help` or `daf <command> --help` for command-specific help
- Full documentation: [DevAIFlow Documentation](https://github.com/itdove/devaiflow/tree/main/docs)
