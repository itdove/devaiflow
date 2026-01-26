# Configuration Reference

Complete reference for configuring DevAIFlow.

## JSON Schema Validation

DevAIFlow provides a JSON Schema file (`config.schema.json`) that can be used to:
- **Validate** your config.json file automatically
- **Get editor support** with autocomplete and inline documentation (VSCode, IntelliJ, etc.)
- **Prevent errors** before they occur

**Validate your configuration:**
```bash
daf config validate
```

**Regenerate schema from models:**
```bash
daf config generate-schema
```

**Enable VSCode validation:** Add this to `.vscode/settings.json`:
```json
{
  "json.schemas": [{
    "fileMatch": ["$DEVAIFLOW_HOME/config.json"],
    "url": "/path/to/devaiflow/config.schema.json"
  }]
}
```

The schema is auto-generated from Pydantic models, ensuring it's always in sync with the validation code.

## Quick Configuration

**Interactive TUI** (Recommended):
```bash
daf config edit    # Launch full-screen configuration editor
daf config tui     # Alias for the above
```

The TUI provides:
- Tabbed interface for all configuration sections (JIRA, Repository, Prompts, Context Files, etc.)
- Context file management (add/edit/remove files with path validation)
- Input validation (URLs, paths, required fields)
- Tri-state prompt controls (Always/Never/Prompt each time)
- Preview mode before saving (Ctrl+P)
- Automatic backups
- Help screen (press `?`)
- Keyboard shortcuts (Ctrl+S to save, Tab to navigate)

**Command Line**:
```bash
daf init                          # Interactive setup wizard
daf config show                   # View current configuration
daf config set-jira-url <url>    # Set specific values
```

## Configuration File

Location: `$DEVAIFLOW_HOME/config.json`

Create with: `daf init` or `daf config edit`

### For Other Organizations

DevAIFlow is fully generic and works with any JIRA instance. You have two options for configuration:

**Option 1: User Configuration (Quick Start)**
- Edit `$DEVAIFLOW_HOME/*.json` files directly with your settings
- Use `daf init` for interactive setup wizard
- Use `daf config tui` for the interactive TUI editor
- Settings stored locally in `$DEVAIFLOW_HOME/` directory

**Option 2: Workspace Configuration (Team Collaboration - Recommended)**
- Copy configuration templates to your workspace root
- Customize for your team (JIRA URL, project, custom field defaults)
- Commit to git for team sharing
- See [Multi-File Configuration System](#multi-file-configuration-system) section below
- Template location: `docs/config-templates/`

**Note**: The examples below use example organization settings (this tool's development team).
For other organizations, simply replace with your own JIRA URL, project keys, and field names.

## Complete Example

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
        "prompt": true,
        "on_fail": "warn"
      }
    },
    "time_tracking": true,
    "default_sprint": "current",
    "field_cache_auto_refresh": true,
    "field_cache_max_age_hours": 24,
    "comment_visibility_type": "group",
    "comment_visibility_value": "Example Group"
  },
  "repos": {
    "workspace": "/Users/your-username/development/myorg",
    "detection": {
      "method": "keyword_match",
      "fallback": "prompt"
    },
    "keywords": {
      "myorg-management-service": ["backup", "restore", "subscription", "api"],
      "myorg-admin-console": ["ui", "frontend", "dashboard", "react"],
      "myorg-sops": ["terraform", "github", "infrastructure", "devops"]
    },
    "default_branch_pattern": "{issue_key}-{name}"
  },
  "ai": {
    "enabled": true,
    "model": "claude-3-5-sonnet-20241022",
    "summary_on_complete": true,
    "add_to_jira": true
  },
  "git": {
    "auto_create_branch": true,
    "auto_checkout": true,
    "branch_from": "main"
  },
  "backup": {
    "conversation_backups": true,
    "max_backups_per_session": 5,
    "backup_before_cleanup": true
  },
  "ui": {
    "theme": "dark",
    "show_icons": true,
    "verbose": false
  }
}
```

## JIRA Configuration

### jira.url

**Type:** string
**Required:** Yes (for JIRA features)
**Description:** URL of your JIRA instance

**Examples:**
```json
{
  "jira": {
    "url": "https://jira.example.com"
  }
}
```

```json
{
  "jira": {
    "url": "https://yourcompany.atlassian.net"
  }
}
```

### jira.user

**Type:** string
**Required:** Yes (for JIRA features)
**Description:** Your JIRA username or email

**Example:**
```json
{
  "jira": {
    "user": "your-username"
  }
}
```

### jira.transitions

**Type:** object
**Required:** No
**Description:** Configure automatic JIRA status transitions

#### transitions.on_start

**Type:** object
**Description:** Transition when opening a session

**Fields:**
- **from** (array of strings) - List of statuses to transition from
- **to** (string) - Target status
- **prompt** (boolean) - Ask before transitioning (default: false)
- **on_fail** (string) - What to do if transition fails ("warn" or "block", default: "warn")

**Examples:**

Automatic transition without prompt:
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

Prompt before transition:
```json
{
  "transitions": {
    "on_start": {
      "from": ["New", "To Do", "Backlog"],
      "to": "In Progress",
      "prompt": true,
      "on_fail": "block"
    }
  }
}
```

#### transitions.on_complete

**Type:** object
**Description:** Transition when completing a session

**Fields:**
- **prompt** (boolean) - Ask for target status (default: true)
- **options** (array of strings) - List of available target statuses
- **on_fail** (string) - What to do if transition fails ("warn" or "block", default: "warn")

**Examples:**

**Option 1: Interactive prompt with dynamic transitions (recommended)**
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

When `prompt: true`, the tool will:
1. Fetch available transitions from the JIRA API based on the ticket's current status
2. Display a menu of valid transitions for the user to choose from
3. Apply the selected transition

**Note:** Available transitions are dynamically fetched from the JIRA API, so you always see only valid options for the ticket's current state.

**Option 2: Automatic transition to a specific status**
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

When `prompt: false`, the tool will:
1. Automatically transition the ticket to the status specified in `to`
2. No user interaction required
3. Skip transition if the target status is not available

### jira.time_tracking

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Enable time tracking for JIRA tickets

**Example:**
```json
{
  "jira": {
    "time_tracking": true
  }
}
```

### jira.default_sprint

**Type:** string
**Required:** No
**Default:** "current"
**Description:** Default sprint for `daf sync` command

**Values:**
- "current" - Current active sprint
- "next" - Next upcoming sprint
- "{sprint-name}" - Specific sprint name

**Example:**
```json
{
  "jira": {
    "default_sprint": "current"
  }
}
```

### jira.project

**Type:** string
**Required:** No
**Default:** "PROJ"
**Description:** Default JIRA project key for field discovery and issue creation

**Example:**
```json
{
  "jira": {
    "project": "PROJ"
  }
}
```

### jira.custom_field_defaults

**Type:** object (dictionary)
**Required:** No
**Default:** null
**Description:** Default values for custom fields used during issue creation. Any custom field can be specified here (e.g., workstream, team, severity, size). Fields are auto-discovered from your JIRA instance.

**Example:**
```json
{
  "jira": {
    "custom_field_defaults": {
      "workstream": "Platform",
      "team": "Backend",
      "severity": "Medium"
    }
  }
}
```

**CLI Command:**
```bash
daf config tui
# Navigate to "JIRA Integration" tab
# Set "Custom Field Defaults" field
```

### jira.affected_version

**Type:** string
**Required:** No (but required for bug creation)
**Default:** None
**Description:** Default affected version value for bug creation

When creating bugs with `daf jira create bug`, this value is used automatically for the affected version field. If not configured, the command will prompt you to enter it and save it for future use.

**Example:**
```json
{
  "jira": {
    "affected_version": "myorg-ga"
  }
}
```

**CLI Command:**
```bash
# Set affected version (one-time configuration)
daf config tui <version>

# Example for specific version
daf config tui myorg-ga
```

**Behavior:**
- If configured: Used automatically for all `daf jira create bug` commands
- If not configured: Command prompts you to enter it and saves to config
- Override per-bug: Use `--affected-version` flag when creating a specific bug

**Important:** Claude (the AI agent) will check if this is configured before creating bugs and ask you about it if not set.

### jira.field_mappings

**Type:** object
**Required:** No (auto-populated by `daf init`)
**Description:** Cached JIRA custom field mappings discovered during initialization

This field is automatically populated when you run `daf init` or `daf config refresh-jira-fields`.
It maps human-readable field names to JIRA custom field IDs, eliminating the need to remember
complex field IDs like `customfield_12319275`.

**Example:**
```json
{
  "jira": {
    "field_mappings": {
      "workstream": {
        "id": "customfield_12319275",
        "name": "Workstream",
        "type": "array",
        "schema": "option",
        "allowed_values": ["Platform", "Hosted Services", "Tower"],
        "required_for": ["Bug", "Story"]
      },
      "epic_link": {
        "id": "customfield_12311140",
        "name": "Epic Link",
        "type": "string",
        "schema": "epic",
        "allowed_values": [],
        "required_for": []
      },
      "acceptance_criteria": {
        "id": "customfield_12315940",
        "name": "Acceptance Criteria",
        "type": "string",
        "schema": "text",
        "allowed_values": [],
        "required_for": ["Story"]
      }
    }
  }
}
```

**Refreshing Field Mappings:**

Run this command to update field mappings when:
- New custom fields are added to your JIRA instance
- Field configurations change
- Switching to a different JIRA project

```bash
daf config refresh-jira-fields
```

### jira.field_cache_timestamp

**Type:** string (ISO 8601 timestamp)
**Required:** No (auto-populated)
**Description:** Timestamp of when field mappings were last discovered

**Example:**
```json
{
  "jira": {
    "field_cache_timestamp": "2025-11-23T02:00:00Z"
  }
}
```

The tool uses this to detect stale field caches and trigger auto-refresh.

### jira.field_cache_auto_refresh

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Automatically refresh JIRA field mappings when they become stale

When enabled, the tool will automatically refresh field mappings in the background before each command if they are older than `field_cache_max_age_hours`. This ensures you always have up-to-date field definitions without manual intervention.

**Example:**
```json
{
  "jira": {
    "field_cache_auto_refresh": true
  }
}
```

**Behavior:**
- Auto-refresh runs silently before each command
- Shows brief notification when refreshing ("Refreshing JIRA field mappings...")
- Failures are handled gracefully with warnings (commands continue with cached data)
- Does not run if `JIRA_API_TOKEN` is not set
- Skips refresh if cache is still fresh (younger than `field_cache_max_age_hours`)

**Disable auto-refresh:**
```json
{
  "jira": {
    "field_cache_auto_refresh": false
  }
}
```

When disabled, you must manually refresh with `daf config refresh-jira-fields` when needed.

### jira.field_cache_max_age_hours

**Type:** integer
**Required:** No
**Default:** 24
**Description:** Maximum age in hours before field cache is considered stale

Field mappings older than this value will be automatically refreshed (if `field_cache_auto_refresh` is enabled).

**Examples:**

Default 24-hour refresh:
```json
{
  "jira": {
    "field_cache_max_age_hours": 24
  }
}
```

Refresh every 12 hours:
```json
{
  "jira": {
    "field_cache_max_age_hours": 12
  }
}
```

Weekly refresh (7 days):
```json
{
  "jira": {
    "field_cache_max_age_hours": 168
  }
}
```

**Recommended Values:**
- **24 hours** (default) - Good for most teams with occasional field changes
- **12 hours** - For fast-paced teams with frequent JIRA configuration changes
- **72 hours** - For stable JIRA instances with rare field changes
- **168 hours (7 days)** - Legacy behavior, only use if JIRA fields rarely change

**Note:** Shorter intervals may increase API calls to JIRA, but the impact is minimal since refresh only happens when commands are run.

### jira.comment_visibility_type

**Type:** string
**Required:** No
**Default:** "group"
**Description:** Visibility type for JIRA comments added by the tool

Controls how comment visibility is restricted in JIRA. Valid values are:
- `"group"` - Restrict visibility by JIRA group membership
- `"role"` - Restrict visibility by JIRA role

**Examples:**

Default group-based visibility:
```json
{
  "jira": {
    "comment_visibility_type": "group"
  }
}
```

Role-based visibility:
```json
{
  "jira": {
    "comment_visibility_type": "role"
  }
}
```

**CLI Command:**
```bash
daf config tui --type <group|role> --value <name>
```

### jira.comment_visibility_value

**Type:** string
**Required:** No
**Default:** "Example Group"
**Description:** Visibility value (group or role name) for JIRA comments

Specifies the group or role name that should have access to comments added by the tool.
The value depends on the `comment_visibility_type`:
- If type is `"group"`, this should be a JIRA group name
- If type is `"role"`, this should be a JIRA role name

**Examples:**

Default Example Group group:
```json
{
  "jira": {
    "comment_visibility_type": "group",
    "comment_visibility_value": "Example Group"
  }
}
```

Custom internal group:
```json
{
  "jira": {
    "comment_visibility_type": "group",
    "comment_visibility_value": "Engineering Team"
  }
}
```

Role-based restriction:
```json
{
  "jira": {
    "comment_visibility_type": "role",
    "comment_visibility_value": "Administrators"
  }
}
```

**CLI Command:**
```bash
# Set both type and value with flags
daf config tui --type group --value "Engineering Team"

# Or use interactive prompts
daf config tui
```

**When to Change:**
- Your organization uses different group names for internal visibility
- You need to restrict comments to a specific role instead of a group
- You're using JIRA Cloud or Server with custom visibility settings

**Note:** Make sure the specified group or role exists in your JIRA instance, otherwise comment creation may fail.

## Repository Configuration

### repos.workspaces (AAP-63377)

**Type:** array of WorkspaceDefinition objects
**Required:** No
**Description:** Multiple named workspaces for concurrent multi-branch development

Workspaces enable you to organize repositories into named locations (similar to VSCode workspaces), allowing concurrent sessions on the same project in different workspaces without conflicts.

**WorkspaceDefinition Fields:**
- **name** (string, required) - Unique workspace identifier
- **path** (string, required) - Directory path (supports ~ expansion)

**RepoConfig Fields:**
- **workspaces** (array, required) - List of workspace definitions
- **last_used_workspace** (string, optional) - Name of the last used workspace

**Example:**
```json
{
  "repos": {
    "workspaces": [
      {
        "name": "primary",
        "path": "/Users/username/development"
      },
      {
        "name": "product-a",
        "path": "/Users/username/repos/product-a"
      },
      {
        "name": "feat-caching",
        "path": "/Users/username/workspaces/caching"
      }
    ],
    "last_used_workspace": "primary"
  }
}
```

**CLI Commands:**
```bash
# List all workspaces
daf workspace list

# Add a workspace
daf workspace add primary ~/development --default
daf workspace add product-a ~/repos/product-a

# Set default workspace
daf workspace set-default primary

# Remove a workspace
daf workspace remove feat-caching
```

**Using Workspaces:**
```bash
# Create session in specific workspace (recommended)
daf new --name AAP-123 -w feat-caching

# Override workspace when reopening
daf open AAP-123 -w product-a

# Sessions remember their workspace automatically
daf open AAP-123  # Uses remembered workspace
```

**Workspace Selection Priority:**
1. `-w`/`--workspace` flag (highest priority)
2. Session's stored workspace_name
3. Last used workspace (last_used_workspace)
4. Interactive prompt

**Use Cases:**
- Work on same project in different workspaces simultaneously
- Separate experimental branches from main development
- Group repositories by product or feature
- Enable concurrent multi-branch development

### repos.detection

**Type:** object
**Required:** No
**Description:** How to detect which repository to use

**Fields:**
- **method** (string) - Detection method ("keyword_match", "prompt", "git_detect")
- **fallback** (string) - What to do if detection fails ("prompt", "error")

**Methods:**
- **keyword_match** - Match JIRA summary/goal against keyword lists
- **prompt** - Always ask user
- **git_detect** - Use current git repository

**Examples:**

Keyword matching with prompt fallback:
```json
{
  "repos": {
    "detection": {
      "method": "keyword_match",
      "fallback": "prompt"
    }
  }
}
```

Always prompt:
```json
{
  "repos": {
    "detection": {
      "method": "prompt",
      "fallback": "prompt"
    }
  }
}
```

### repos.keywords

**Type:** object
**Required:** No (but needed for keyword_match)
**Description:** Keywords for repository detection

**Format:** Repository name → array of keywords

**Example:**
```json
{
  "repos": {
    "keywords": {
      "myorg-management-service": [
        "backup",
        "restore",
        "subscription",
        "api",
        "backend"
      ],
      "myorg-admin-console": [
        "ui",
        "frontend",
        "dashboard",
        "react",
        "console"
      ],
      "myorg-sops": [
        "terraform",
        "github",
        "infrastructure",
        "devops",
        "deployment"
      ]
    }
  }
}
```

When creating a session with goal "Implement backup API", the tool will suggest "myorg-management-service" because it contains the keyword "backup".

### repos.default_branch_pattern

**Type:** string
**Required:** No
**Default:** "{issue_key}-{name}"
**Description:** Pattern for git branch names

**Variables:**
- `{issue_key}` - JIRA ticket key (e.g., "PROJ-12345")
- `{name}` - Session name
- `{date}` - Current date (YYYYMMDD)
- `{username}` - Your username

**Examples:**

Default pattern:
```json
{
  "repos": {
    "default_branch_pattern": "{issue_key}-{name}"
  }
}
```
Creates: `PROJ-12345-backup`

With username:
```json
{
  "repos": {
    "default_branch_pattern": "feature/{username}/{issue_key}"
  }
}
```
Creates: `feature/john/PROJ-12345`

With date:
```json
{
  "repos": {
    "default_branch_pattern": "{issue_key}-{date}"
  }
}
```
Creates: `PROJ-12345-20251120`

## AI Configuration

### ai.enabled

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Enable AI-powered features (summaries, analysis)

**Example:**
```json
{
  "ai": {
    "enabled": true
  }
}
```

### ai.model

**Type:** string
**Required:** No
**Default:** "claude-3-5-sonnet-20241022"
**Description:** Claude model to use for AI features

**Supported models:**
- "claude-3-5-sonnet-20241022" (recommended)
- "claude-3-opus-20240229"
- "claude-3-haiku-20240307"

**Example:**
```json
{
  "ai": {
    "model": "claude-3-5-sonnet-20241022"
  }
}
```

### ai.summary_on_complete

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Offer to generate AI summary when completing sessions

**Example:**
```json
{
  "ai": {
    "summary_on_complete": true
  }
}
```

### ai.add_to_jira

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Offer to add AI summary to JIRA ticket

**Example:**
```json
{
  "ai": {
    "add_to_jira": true
  }
}
```

## GCP Vertex AI Configuration

### gcp_vertex_region

**Type:** string (optional)
**Required:** No
**Default:** None (uses Claude's default region)
**Description:** GCP Vertex AI region for Claude Code when using Google Cloud Platform

**Availability:** This setting is only available when `CLAUDE_CODE_USE_VERTEX` environment variable is set, indicating Claude Code is configured to use GCP Vertex AI.

When configured, the `CLOUD_ML_REGION` environment variable is exported before launching Claude Code, allowing you to control which GCP region handles your API requests.

**Supported regions:**

Claude models on Vertex AI are currently available in a limited set of regions:

- `global` - Global endpoint with dynamic routing (recommended for most users)
- `us-east5` - US East 5 (Columbus, Ohio)
- `europe-west1` - Europe West 1 (Belgium)
- `asia-east1` - Asia East 1 (Taiwan)
- `asia-southeast1` - Asia Southeast 1 (Singapore)

**Note:** Not all GCP regions support Claude models. The list above represents the regions where Claude is confirmed to be available as of January 2025. For the most up-to-date list, check the [official Claude on Vertex AI documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/use-claude).

**Configuration in TUI:**
```bash
daf config edit
# Navigate to "Claude" tab
# Under "GCP Vertex AI" section
# Select region from dropdown (only visible when CLAUDE_CODE_USE_VERTEX is set)
```

**Configuration via JSON:**
```json
{
  "gcp_vertex_region": "us-central1"
}
```

**Example with all fields:**
```json
{
  "ai": {
    "enabled": true,
    "model": "claude-3-5-sonnet-20241022"
  },
  "gcp_vertex_region": "europe-west4"
}
```

**Notes:**
- If not set, Claude Code uses its default region behavior
- Invalid region values will cause Claude Code to fail with a region error
- The region selector appears in the TUI only when `CLAUDE_CODE_USE_VERTEX` environment variable is set
- This setting applies to all Claude Code launches from `daf open`, `daf new`, and `daf jira new`

## Update Checker Configuration

### update_checker_timeout

**Type:** integer
**Required:** No
**Default:** 10
**Range:** 1-60 seconds
**Description:** Timeout in seconds for checking GitLab for new version releases

The update checker runs automatically before each command to notify you of new versions. This setting controls how long to wait for the GitLab API to respond before timing out.

**Use Cases:**
- **Slow network connections:** Increase timeout to 15-30 seconds to prevent false "VPN not connected" warnings
- **Fast network connections:** Reduce timeout to 5 seconds for quicker command execution
- **VPN/corporate networks:** Adjust based on your network latency to GitLab

**Configuration via TUI:**
1. Run `daf config tui`
2. Navigate to the **Advanced** tab
3. Set "Update Checker Timeout (seconds)" field
4. Save changes (Ctrl+S)

**Configuration via JSON:**
```json
{
  "update_checker_timeout": 15
}
```

**Example with explanation:**
```json
{
  "update_checker_timeout": 20
}
```
*Note: A 20-second timeout is recommended for slow VPN connections to avoid false warnings*

**Notes:**
- Default is 10 seconds (increased from 5 seconds to reduce false warnings)
- Timeout errors are handled silently and do NOT show VPN warning
- Only actual connection errors (VPN/network issues) show the VPN warning
- HTTP errors, SSL errors, and other failures are handled silently
- Valid range: 1-60 seconds (enforced by TUI validation)

**Related Settings:**
- Update checks run once per 24 hours (cached)
- Update checks are disabled in development/editable installs
- Use `--json` flag to suppress all update notifications for scripting

## Git Configuration

### git.auto_create_branch

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Automatically create git branches for new sessions

**Example:**
```json
{
  "git": {
    "auto_create_branch": true
  }
}
```

### git.auto_checkout

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Automatically checkout branch when opening session

**Example:**
```json
{
  "git": {
    "auto_checkout": true
  }
}
```

### git.branch_from

**Type:** string
**Required:** No
**Default:** "main"
**Description:** Which branch to create new branches from

**Example:**
```json
{
  "git": {
    "branch_from": "develop"
  }
}
```

## Hierarchical Context Files

DevAIFlow supports hierarchical context files that are automatically loaded when creating or opening Claude Code sessions. These files provide context at different organizational levels and are only loaded if they physically exist on disk.

### Context Loading Order

When you create or open a session, context files are loaded in this order:

1. **Default files** (from project directory):
   - `AGENTS.md` (agent-specific instructions)
   - `CLAUDE.md` (project guidelines and standards)
   - `DAF_AGENTS.md` (daf tool usage guide)

2. **Backend context** (from DEVAIFLOW_HOME):
   - `backends/JIRA.md` (JIRA-specific integration rules)

3. **Organization context** (from DEVAIFLOW_HOME):
   - `ORGANIZATION.md` (organization-wide coding standards)

4. **Team context** (from DEVAIFLOW_HOME):
   - `TEAM.md` (team-specific conventions and workflows)

5. **User context** (from DEVAIFLOW_HOME):
   - `CONFIG.md` (personal notes and preferences)

6. **User-configured files** (from config.json):
   - Files configured via `daf config context add`

7. **Skills** (from workspace):
   - `.claude/skills/` (deployed via `daf upgrade`)

**CRITICAL**: Files are only loaded if they physically exist on disk. Missing files are silently skipped with no errors.

### File Locations

All hierarchical context files are stored in your DEVAIFLOW_HOME directory:

- **Default**: `$DEVAIFLOW_HOME/` (or `$DEVAIFLOW_HOME/` for backward compatibility)
- **Custom**: Set via `DEVAIFLOW_HOME` environment variable

**Directory Structure:**
```
$DEVAIFLOW_HOME/
├── backends/
│   └── JIRA.md              # Backend-specific context
├── ORGANIZATION.md          # Organization-level context
├── TEAM.md                  # Team-level context
└── CONFIG.md                # User-level context
```

### Creating Context Files

#### 1. Backend Context (backends/JIRA.md)

Backend-specific integration rules for JIRA.

**Use for:**
- JIRA Wiki markup requirements
- Backend-specific formatting rules
- Integration guidelines specific to JIRA

**Example:**
```bash
mkdir -p $DEVAIFLOW_HOME/backends
cp docs/context-templates/JIRA.md $DEVAIFLOW_HOME/backends/JIRA.md
# Edit to customize for your JIRA instance
```

**Template includes:**
- JIRA Wiki markup syntax reference
- Common mistakes to avoid
- When to use Wiki markup vs Markdown

#### 2. Organization Context (ORGANIZATION.md)

Organization-wide coding standards and architecture principles.

**Use for:**
- Coding standards that apply to all projects
- Architecture principles and patterns
- Security and compliance requirements
- Organization-wide git workflows

**Example:**
```bash
cp docs/context-templates/ORGANIZATION.md $DEVAIFLOW_HOME/ORGANIZATION.md
# Edit to match your organization's standards
```

**Template includes:**
- Code quality standards
- Architecture principles
- Git workflow conventions
- Documentation requirements

#### 3. Team Context (TEAM.md)

Team-specific conventions and workflows.

**Use for:**
- Team-specific branch naming conventions
- Code review practices
- Communication channels and schedules
- Team tools and resources

**Example:**
```bash
cp docs/context-templates/TEAM.md $DEVAIFLOW_HOME/TEAM.md
# Edit to match your team's practices
```

**Template includes:**
- Team workflow and ceremonies
- Development practices
- Communication channels
- Tools and conventions

#### 4. User Context (CONFIG.md)

Personal development notes and preferences.

**Use for:**
- Personal reminders and checklists
- Favorite commands and shortcuts
- Project-specific notes
- Learning goals and ideas

**Example:**
```bash
cp docs/context-templates/CONFIG.md $DEVAIFLOW_HOME/CONFIG.md
# Edit to add your personal notes
```

**Template includes:**
- Current focus and learning goals
- Personal conventions
- Reminders and useful commands
- Technical debt notes

### Context File Templates

All templates are provided in `docs/context-templates/`:

- `JIRA.md` - Backend-specific JIRA integration rules
- `ORGANIZATION.md` - Organization coding standards
- `TEAM.md` - Team conventions and workflows
- `CONFIG.md` - Personal development notes
- `README.md` - Complete guide to hierarchical context

### Best Practices

**1. Keep Files Focused**
- Backend context: Integration rules only
- Organization context: Standards that apply to all projects
- Team context: Team-specific conventions only
- User context: Personal notes and reminders

**2. Avoid Duplication**
- Don't repeat information already in AGENTS.md or CLAUDE.md
- Reference other files when appropriate
- Use hierarchical levels appropriately

**3. Keep Files Up-to-Date**
- Review periodically (quarterly or when standards change)
- Remove outdated information
- Update when team members join or leave

**4. Conditional Loading**
- Only create the files you need
- Missing files are silently skipped
- No errors if files don't exist
- Gradual adoption - start with one file, add more later

### Verifying Context Loading

To verify which context files are being loaded:

1. Create a test session:
   ```bash
   daf new --name test-context --goal "Test context loading"
   ```

2. Check the initial prompt that Claude receives - it will list all context files that were found and loaded.

3. Files are listed in the order shown above (defaults → backend → organization → team → user → configured → skills).

### Migration Path

In the future, backend, organization, and team context files will be stored in a centralized database:
- Easier sharing across team members
- Versioning and change tracking
- Centralized management
- User context (CONFIG.md) will remain local

The current filesystem-based approach provides:
- Simple setup and management
- No external dependencies
- Privacy for personal notes
- Easy version control (can commit to git if desired)

### See Also

- Context file templates: `docs/context-templates/`
- User-configured context: See section below on managing context files via config.json
- Project-specific context: AGENTS.md, CLAUDE.md in project directory

## Prompts Configuration

The `prompts` section allows you to configure automatic answers for common prompts, eliminating repetitive questions during workflow commands (`daf new`, `daf open`, `daf complete`).

**Managing via TUI:**
The easiest way to configure prompts is through the interactive TUI:
```bash
daf config edit
```
Navigate to the **Prompts** tab and use the dropdown selects for each setting.

### Understanding Prompt Values

All prompt settings support three states:
- **`true`** - "Always do this action" (skip prompt, auto-yes)
- **`false`** - "Never do this action" (skip prompt, auto-no)
- **`null`** (or omitted) - "Prompt each time" (ask interactively) - **DEFAULT**

### prompts.auto_commit_on_complete

**Type:** boolean (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf complete`
**Description:** Automatically commit uncommitted changes when completing a session

**Values:**
- `true` - Always commit changes without asking
- `false` - Never commit changes, skip the prompt
- `null` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "auto_commit_on_complete": true
  }
}
```

### prompts.auto_create_pr_on_complete

**Type:** boolean (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf complete`
**Description:** Automatically create PR/MR when completing a session

**Values:**
- `true` - Always create PR/MR without asking
- `false` - Never create PR/MR, skip the prompt
- `null` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "auto_create_pr_on_complete": false
  }
}
```

### prompts.auto_create_pr_status

**Type:** string
**Required:** No
**Default:** "prompt"
**Used by:** `daf complete`
**Description:** Controls whether PR/MR is created as draft or ready for review

**Values:**
- `"draft"` - Always create as draft (requires explicit marking as ready)
- `"ready"` - Always create ready for review
- `"prompt"` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "auto_create_pr_status": "draft"
  }
}
```

**Configuration:**
```bash
# Set via CLI
daf config tui --auto-create-pr-status draft

# Or via interactive wizard
daf config tui
```

**Notes:**
- This setting only applies when `auto_create_pr_on_complete` is `true` or when manually creating a PR/MR during `daf complete`
- Invalid values automatically fall back to `"prompt"`
- The TUI config editor provides a dropdown with all valid choices

### prompts.auto_accept_ai_commit_message

**Type:** boolean (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf complete`
**Description:** Automatically accept AI-generated commit messages without prompting

When `daf complete` creates a commit, it generates a commit message using AI based on:
- Changed files and git diff
- Session goal and JIRA ticket details
- Conversation context (if available)

This setting controls whether to accept that AI-generated message automatically or prompt for review.

**Values:**
- `true` - Always accept AI commit message without asking
- `false` - Never accept AI message, always prompt for manual input
- `null` - Show AI message and ask "Use this commit message?" (default)

**Example:**
```json
{
  "prompts": {
    "auto_accept_ai_commit_message": true
  }
}
```

**Note:** This setting only applies when `auto_commit_on_complete` is enabled or when you confirm to commit. If set to `false`, you'll always be prompted to write/edit the commit message.

### prompts.auto_add_issue_summary

**Type:** boolean (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf complete`
**Description:** Automatically add session summary as a JIRA comment when completing

**Values:**
- `true` - Always add summary without asking
- `false` - Never add summary, skip the prompt
- `null` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "auto_add_issue_summary": true
  }
}
```

### prompts.auto_update_jira_pr_url

**Type:** boolean (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf complete`
**Description:** Automatically update JIRA ticket with PR URL when PR is created

**Values:**
- `true` - Always update JIRA ticket with PR URL without asking
- `false` - Never update JIRA ticket, skip the prompt
- `null` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "auto_update_jira_pr_url": true
  }
}
```

### prompts.auto_launch_claude

**Type:** boolean (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf new`, `daf open`
**Description:** Automatically launch Claude Code when creating or opening sessions

**Values:**
- `true` - Always launch Claude Code without asking
- `false` - Never launch Claude Code, skip the prompt
- `null` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "auto_launch_claude": true
  }
}
```

### prompts.auto_checkout_branch

**Type:** boolean (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf open`
**Description:** Automatically checkout the session's branch when opening

**Values:**
- `true` - Always checkout branch without asking
- `false` - Never checkout branch, skip the prompt
- `null` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "auto_checkout_branch": true
  }
}
```

### prompts.auto_sync_with_base

**Type:** string (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf open`
**Description:** Automatically sync session branch with base branch when opening

**Values:**
- `"always"` - Always sync with base branch
- `"never"` - Never sync with base branch
- `null` or `"prompt"` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "auto_sync_with_base": "always"
  }
}
```

### prompts.auto_complete_on_exit

**Type:** boolean (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf open`
**Description:** Automatically run `daf complete` when Claude Code session exits

This setting controls whether the session completion workflow is triggered when you exit Claude Code. When enabled, it will automatically run `daf complete` to handle:
- Committing uncommitted changes
- Updating or creating PRs
- Adding session summaries to JIRA
- Transitioning JIRA tickets

**Values:**
- `true` - Always run `daf complete` after Claude Code exits
- `false` - Never run `daf complete` (manual completion required)
- `null` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "auto_complete_on_exit": true
  }
}
```

**Workflow Note:** This setting works in conjunction with other prompt settings in `daf complete`:
- If `auto_complete_on_exit` is `true` and `auto_commit_on_complete` is also `true`, sessions will be automatically completed and committed without prompts
- If `auto_complete_on_exit` is `true` but `auto_commit_on_complete` is `false`, you'll still be prompted during the completion workflow

### prompts.default_branch_strategy

**Type:** string (optional)
**Required:** No
**Default:** null (prompt each time)
**Used by:** `daf new`
**Description:** Default strategy for creating new branches

**Values:**
- `"from_default"` - Create from default branch (main/master)
- `"from_current"` - Create from current branch
- `null` - Ask each time (default)

**Example:**
```json
{
  "prompts": {
    "default_branch_strategy": "from_default"
  }
}
```

### prompts.show_prompt_unit_tests

**Type:** boolean
**Required:** No
**Default:** `true`
**Used by:** `daf new`, `daf open`
**Description:** Show unit testing instructions in the initial Claude prompt for development sessions

When enabled, Claude will be instructed to:
- Run `pytest` after making code changes
- Create tests for new methods before or during implementation
- Parse test output and identify failures
- Fix all failing tests before marking tasks complete
- Report test results clearly to the user

**Values:**
- `true` - Show testing instructions (default)
- `false` - Hide testing instructions

**Note:** Testing instructions are only shown for development sessions, not for ticket_creation or other session types.

**Example:**
```json
{
  "prompts": {
    "show_prompt_unit_tests": true
  }
}
```

**CLI Commands:**
```bash
# Enable testing prompt (default)
daf config tui --show-prompt-unit-tests yes

# Disable testing prompt
daf config tui --show-prompt-unit-tests no

# Reset to default (true)
daf config unset-prompts --show-prompt-unit-tests
```

### Complete Prompts Example

```json
{
  "prompts": {
    "auto_commit_on_complete": true,
    "auto_accept_ai_commit_message": true,
    "auto_create_pr_on_complete": false,
    "auto_add_issue_summary": true,
    "auto_launch_claude": true,
    "auto_checkout_branch": true,
    "auto_sync_with_base": "always",
    "auto_complete_on_exit": true,
    "default_branch_strategy": "from_default",
    "show_prompt_unit_tests": true
  }
}
```

**Workflow Example:**
With the configuration above:
- `daf new` will automatically launch Claude Code and create branches from default
- `daf open` will automatically checkout the branch, sync with base, and launch Claude Code
- When Claude Code exits, `daf complete` will automatically run
- `daf complete` will automatically commit changes with AI-generated messages, skip PR creation, and add JIRA summary

## Backup Configuration

### backup.conversation_backups

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Enable automatic backups before cleanup

**Example:**
```json
{
  "backup": {
    "conversation_backups": true
  }
}
```

### backup.max_backups_per_session

**Type:** integer
**Required:** No
**Default:** 5
**Description:** Maximum number of backups to keep per session

**Example:**
```json
{
  "backup": {
    "max_backups_per_session": 10
  }
}
```

Older backups are automatically deleted when this limit is exceeded.

### backup.backup_before_cleanup

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Always create backup before conversation cleanup

**Example:**
```json
{
  "backup": {
    "backup_before_cleanup": true
  }
}
```

## UI Configuration

### ui.theme

**Type:** string
**Required:** No
**Default:** "dark"
**Description:** Color theme for CLI output

**Values:**
- "dark" - Dark theme (recommended for dark terminals)
- "light" - Light theme
- "auto" - Auto-detect from terminal

**Example:**
```json
{
  "ui": {
    "theme": "dark"
  }
}
```

### ui.show_icons

**Type:** boolean
**Required:** No
**Default:** true
**Description:** Show emoji icons in output

**Example:**
```json
{
  "ui": {
    "show_icons": true
  }
}
```

Set to `false` if your terminal doesn't support emojis.

### ui.verbose

**Type:** boolean
**Required:** No
**Default:** false
**Description:** Show verbose output (useful for debugging)

**Example:**
```json
{
  "ui": {
    "verbose": true
  }
}
```

## Environment Variables

Some settings can be overridden with environment variables:

### DEVAIFLOW_HOME

**Optional** (Recommended)

Customize the directory where DevAIFlow stores session data and configuration.

**Default:** `$DEVAIFLOW_HOME`

```bash
export DEVAIFLOW_HOME="~/my-custom-sessions"
```

This variable supports:
- Tilde expansion (e.g., `~/custom/path`)
- Absolute paths (e.g., `/var/lib/devaiflow-sessions`)
- Relative paths (resolved to absolute)

**Use Cases:**
- **Team Configuration:** Point to a shared configuration directory in your workspace that's tracked in git
- **Multi-Environment:** Switch between different configuration sets (dev, staging, prod)
- **Project-Specific:** Use different configurations for different projects

**Example - Team Collaboration:**
```bash
# In your workspace root, create a .daf-config directory
mkdir ~/workspace/.daf-config

# Copy config templates
cp -r docs/config-templates/* ~/workspace/.daf-config/

# Point DEVAIFLOW_HOME to your workspace config
export DEVAIFLOW_HOME="~/workspace/.daf-config"

# Now daf will use workspace configs instead of $DEVAIFLOW_HOME
daf config show
```


### JIRA_API_TOKEN

**Required for JIRA features**

Your JIRA API token or Personal Access Token.

```bash
export JIRA_API_TOKEN="your-token-here"
```

### JIRA_AUTH_TYPE

**Required for JIRA features**

Authentication type for JIRA CLI.

```bash
export JIRA_AUTH_TYPE="bearer"  # or "basic"
```

### ANTHROPIC_API_KEY

**Required for AI features**

Your Anthropic API key for Claude.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### AI_AGENT_SESSION_ID

**Set automatically by daf tool**

Do not set this manually. The tool sets it when launching Claude Code.

## Configuration Validation

DevAIFlow provides multiple levels of configuration validation to help you identify and fix issues before they cause problems.

### Automatic Validation on Load

When you run any `daf` command, the configuration is automatically validated. If placeholder values or missing required fields are detected, you'll see warnings:

```
⚠ Configuration Warning: Found 2 configuration issue(s)
  • backends/jira.json: url contains placeholder value: 'TODO: https://your-jira-instance.com'
  • organization.json: jira_project is null (required for ticket creation)
Run 'daf config show --validate' for details and suggestions
```

These warnings are non-fatal - commands will still run, but you should fix the issues for proper functionality.

### Detailed Validation Report

Get a comprehensive validation report with actionable suggestions:

```bash
daf config show --validate
```

This command checks for:
- **Placeholder values:** URLs starting with "TODO:", "example.com", "your-jira-instance", etc.
- **Null required fields:** Missing values for `jira_project`, `url`, etc.
- **Invalid paths:** Non-existent workspace directories
- **Malformed JSON:** Syntax errors in configuration files

**Example output:**
```
Configuration Validation Report

⚠ Configuration has 3 issue(s)
  • 2 warning(s)
  • 1 error(s)

backends/jira.json:
  ⚠ url contains placeholder value: 'TODO: https://your-jira-instance.com'
     → Set url in backends/jira.json to your JIRA instance URL
  ⚠ transitions.on_start.to contains placeholder value: 'TODO: Set your status'
     → Customize the target status for 'on_start' transition or leave empty to prompt

organization.json:
  ⚠ jira_project is null (required for ticket creation)
     → Set jira_project in organization.json to your JIRA project key (e.g., 'PROJ', 'PROJ')
```

### Required vs Optional Fields

**Required fields** (must be set for full functionality):
- `backends/jira.json`:
  - `url` - JIRA instance URL (e.g., `https://jira.company.com`)
- `organization.json`:
  - `jira_project` - JIRA project key for ticket creation (e.g. `PROJ`)

**Optional fields** (can be null or left as defaults):
- `jira_custom_field_defaults` - Default values for custom fields (e.g., `{"workstream": "Platform", "team": "Backend"}`)
- `jira_affected_version` - Default affected version for bugs
- All prompt configuration values
- All time tracking settings

### Validate with JSON Schema

**For advanced validation,** use the JSON Schema validator:

```bash
daf config validate
```

This validates your configuration against the JSON Schema, ensuring:
- All required fields are present
- Field values match expected types
- Enums have valid values
- Field relationships are correct

**JSON output for scripting:**
```bash
daf config validate --json
```

### Check JSON Syntax

```bash
python -m json.tool $DEVAIFLOW_HOME/config.json
```

Validates JSON syntax and pretty-prints (basic check only, use `daf config show --validate` for full validation).

### Common Mistakes

1. **Trailing commas** - Not allowed in JSON
   ```json
   {
     "jira": {
       "url": "...",  // ✗ Remove this comma
     }
   }
   ```

2. **Single quotes** - Must use double quotes
   ```json
   {
     "jira": {
       "url": 'https://...'  // ✗ Use double quotes
     }
   }
   ```

3. **Missing commas** - Between fields
   ```json
   {
     "url": "..."
     "user": "..."  // ✗ Add comma after previous line
   }
   ```

## Configuration Examples

### Minimal Configuration (No JIRA)

```json
{
  "repos": {
    "workspace": "/Users/you/projects"
  },
  "git": {
    "auto_create_branch": true
  }
}
```

### JIRA with Automatic Transitions

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
        "prompt": false,
        "to": "Done",
        "on_fail": "warn"
      }
    }
  }
}
```

### Multi-Repo Development

```json
{
  "repos": {
    "workspace": "/Users/you/development",
    "detection": {
      "method": "keyword_match",
      "fallback": "prompt"
    },
    "keywords": {
      "backend-api": ["api", "backend", "server", "database"],
      "frontend-app": ["ui", "frontend", "react", "components"],
      "mobile-app": ["ios", "android", "mobile", "app"],
      "docs": ["documentation", "readme", "guide"]
    },
    "default_branch_pattern": "feature/{issue_key}-{name}"
  },
  "git": {
    "auto_create_branch": true,
    "branch_from": "develop"
  }
}
```

### Conservative JIRA Integration

```json
{
  "jira": {
    "url": "https://yourcompany.atlassian.net",
    "user": "your-email@company.com",
    "transitions": {
      "on_start": {
        "from": ["To Do"],
        "to": "In Progress",
        "prompt": true,
        "on_fail": "block"
      },
      "on_complete": {
        "prompt": true
      }
    },
    "time_tracking": true
  },
  "prompts": {
    "auto_add_issue_summary": false
  }
}
```

Prompts before transitions and doesn't add JIRA summaries automatically.

### AI-Powered Workflow

```json
{
  "ai": {
    "enabled": true,
    "model": "claude-3-5-sonnet-20241022",
    "summary_on_complete": true,
    "add_to_jira": true
  },
  "prompts": {
    "auto_add_issue_summary": true
  }
}
```

Generates AI summaries and adds them to JIRA automatically.

## Multi-File Configuration System

DevAIFlow uses a multi-file configuration system for better organization, security, and team collaboration.

### Configuration Files

Configuration is split across 4 separate files based on purpose:

**backends/jira.json** - JIRA Backend Configuration
- JIRA instance URL and authentication
- Field mappings (custom field IDs)
- JIRA workflow transitions
- Field cache settings
- Parent field mappings

**organization.json** - Organization Settings
- JIRA project key
- Field aliases (acceptance criteria, epic link)
- Sync filters (which tickets to sync)
- Affected version defaults
- Field requirements and enforcement

**team.json** - Team-Specific Settings
- Default custom field values (e.g., workstream, team, component)
- Comment visibility restrictions
- Time tracking preferences
- Team-specific field overrides

**config.json** - User Personal Preferences
- Repository workspace paths
- Prompts (auto-commit, auto-PR, etc.)
- Context files for Claude sessions
- Templates and summaries
- Personal workflow preferences

### Configuration Discovery

DevAIFlow automatically discovers and loads configuration files based on your working directory:

1. **Workspace Configuration** (Highest Priority)
   - Looks for config files in workspace root
   - Enables team collaboration via git
   - Example: `~/workspace/myproject/*.json`

2. **User Configuration**
   - Fallback to `$DEVAIFLOW_HOME/` directory
   - Personal preferences and local settings

3. **Built-in Defaults** (Lowest Priority)
   - Minimal defaults for new installations

### Workspace Configuration

**What is it?**
Team-shared configuration stored in your workspace directory and committed to git.

**Why use it?**
- Share JIRA settings across the team
- Version control your team's configuration
- No manual setup required for new team members
- Consistent workflow across the team

**How to set up:**

```bash
# Option 1: Use templates
cp -r /path/to/devaiflow/docs/config-templates/* ~/workspace/myproject/

# Edit for your team
vim ~/workspace/myproject/backends/jira.json      # JIRA URL, transitions
vim ~/workspace/myproject/organization.json       # Project key
vim ~/workspace/myproject/team.json               # Workstream

# Commit to git
git add *.json backends/
git commit -m "Add DevAIFlow workspace configuration"

# Option 2: Use organization-specific configuration repos (if available)
git clone <your-enterprise-git-repo>/your-org-devflow-config ~/workspace/your-org-devflow-config
# Or for specific projects:
git clone <your-enterprise-git-repo>/your-org-devflow-config-aap ~/workspace/your-org-devflow-config-aap
```

**How it works:**

```bash
# Work from any subdirectory
cd ~/workspace/myproject/src/feature-x

# Config files automatically discovered from workspace root
daf open PROJ-123
```

### Configuration Priority

When multiple config sources exist, they merge with this priority:

1. **Workspace config** (~/workspace/myproject/*.json) - Highest priority
2. **User config** ($DEVAIFLOW_HOME/*.json)
3. **Built-in defaults** - Lowest priority

**Example:**
- Workspace sets `jira_project: "MYAPP"`
- User sets `jira_custom_field_defaults: {"team": "Backend"}`
- Both settings are active (merged)

### Viewing Configuration

```bash
# Show merged configuration (default)
daf config show

# Show split configuration files separately
daf config show --format split

# Show as JSON
daf config show --json

# Show where each setting comes from
daf config show --format split
```

### Configuration Templates

Generic templates with detailed comments are available in `docs/config-templates/`:

```bash
# View templates
ls docs/config-templates/

# Files:
# - backends/jira.json - JIRA backend template
# - organization.json - Organization settings template
# - team.json - Team settings template
# - README.md - Complete setup guide
```

Each template includes:
- TODO markers for required fields
- Comment fields explaining each option
- Examples and default values
- Validation and troubleshooting tips

## Updating Configuration

### Edit Configuration

```bash
nano $DEVAIFLOW_HOME/config.json
```

or

```bash
code $DEVAIFLOW_HOME/config.json
```

### Reload Configuration

Configuration is loaded on each command, so changes take effect immediately.

### Reset to Defaults

```bash
# Backup current config
cp $DEVAIFLOW_HOME/config.json $DEVAIFLOW_HOME/config.json.backup

# Create new default config
daf init
```

## Configuration Best Practices

### 1. Start Simple

Begin with minimal config and add features as needed:
```json
{
  "repos": {
    "workspace": "/Users/you/projects"
  }
}
```

### 2. Use Warn Mode for Transitions

Start with `"on_fail": "warn"` to avoid blocking workflow:
```json
{
  "transitions": {
    "on_start": {
      "on_fail": "warn"
    }
  }
}
```

Switch to "block" once confident.

### 3. Customize Branch Patterns

Match your team's conventions:
```json
{
  "repos": {
    "default_branch_pattern": "feature/{username}/{issue_key}"
  }
}
```

### 4. Configure Keywords Carefully

Add keywords that appear in JIRA summaries/goals:
```json
{
  "keywords": {
    "backend-api": ["api", "endpoint", "server", "database", "migration"]
  }
}
```

### 5. Keep Backups

Before major config changes:
```bash
cp $DEVAIFLOW_HOME/config.json $DEVAIFLOW_HOME/config.json.backup
```

### 6. Document Custom Settings

Add comments in a separate file if needed (JSON doesn't support comments).

## Troubleshooting Configuration

### Invalid JSON

**Error:** `JSONDecodeError`

**Solution:**
```bash
python -m json.tool $DEVAIFLOW_HOME/config.json
```

Fix syntax errors shown.

### Config Not Found

**Error:** `Config file not found`

**Solution:**
```bash
daf init
```

### JIRA Features Not Working

**Check:**
1. `jira.url` is correct
2. `jira.user` is set
3. Environment variables are set:
   ```bash
   echo $JIRA_API_TOKEN
   echo $JIRA_AUTH_TYPE
   ```

### Repository Detection Failing

**Check:**
1. `repos.workspace` points to correct directory
2. Keywords match your JIRA summaries/goals
3. Try `"method": "prompt"` to bypass detection

## Next Steps

- [Session Management](04-session-management.md) - Using configured features
- [JIRA Integration](05-jira-integration.md) - JIRA-specific configuration
- [Commands Reference](07-commands.md) - Commands using configuration
- [Workflows](08-workflows.md) - Configuration in practice
