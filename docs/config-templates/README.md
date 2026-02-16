# Configuration Templates

## Quick Start for New Users

1. Copy these template files to your workspace root directory
2. Replace all `TODO:` placeholders with your values
3. Remove comment fields (starting with `_`) - they're for guidance only
4. Test with `daf config show` to verify

## Required Configuration

**Minimum required fields to get started:**

### backends/jira.json
- `url`: Your JIRA instance URL (e.g., `https://jira.example.com`)

### organization.json
- `jira_project`: Your JIRA project key (e.g., `MYAPP`, `ENG`, `PROJ`)
- `transitions.on_start.to`: Status to transition to when starting work (or leave empty to prompt)
- `transitions.on_complete.to`: Status to transition to when completing work (or leave empty to prompt)

All other fields are optional and will use sensible defaults.

## Optional Configuration

### Field Mappings (Auto-Discovery)

DevAIFlow automatically discovers JIRA field IDs on first use. You only need to manually configure `field_mappings` if:
- Auto-discovery fails
- You want to mark specific fields as required for certain issue types

Example manual field mapping:
```json
{
  "field_mappings": {
    "acceptance_criteria": {
      "id": "customfield_12345",
      "required_for": ["Story", "Epic"]
    },
    "story_points": {
      "id": "customfield_12346"
    }
  }
}
```

### Parent Field Mapping

Maps issue types to their parent link field names. Configure in `organization.json`:
```json
{
  "parent_field_mapping": {
    "story": "epic_link",
    "task": "epic_link",
    "bug": "epic_link",
    "epic": "epic_link",
    "sub-task": "parent"
  }
}
```

This is organization-specific hierarchy policy. Leave null for auto-discovery.

### Sync Filters

Control which tickets are synced when running `daf sync`:

```json
{
  "sync_filters": {
    "sync": {
      "status": ["To Do", "In Progress"],
      "required_fields": ["sprint"],
      "assignee": "currentUser()"
    }
  }
}
```

Options:
- `status`: List of JIRA statuses to sync (e.g., `["To Do", "In Progress", "Review"]`)
- `required_fields`: Fields that must be present for ticket creation
- `assignee`: Filter by assignee
  - `"currentUser()"` - Only your assigned tickets
  - `"john.doe"` - Specific user's tickets
  - `null` - All tickets

### Comment Visibility

Restrict who can see comments added by DevAIFlow:

```json
{
  "jira_comment_visibility_type": "group",
  "jira_comment_visibility_value": "jira-developers"
}
```

Or for role-based:
```json
{
  "jira_comment_visibility_type": "role",
  "jira_comment_visibility_value": "Developers"
}
```

Leave both null for public comments.

## Installation

### Option 1: Workspace Configuration (Recommended)

Copy template files to your workspace root:

```bash
# From your project workspace
cp -r /path/to/devaiflow/docs/config-templates/* .

# Edit the files
vim backends/jira.json
vim organization.json
vim team.json

# Remove comment fields (optional cleanup)
# Use a JSON formatter or manually remove lines starting with "_"

# Verify
daf config show
```

**How it works:** DevAIFlow automatically discovers and loads config files from your workspace when you run `daf` commands from any subdirectory.

### Option 2: User Configuration (Alternative)

Copy template files to `$DEVAIFLOW_HOME/`:

```bash
cp -r /path/to/devaiflow/docs/config-templates/backends $DEVAIFLOW_HOME/
cp /path/to/devaiflow/docs/config-templates/organization.json $DEVAIFLOW_HOME/
cp /path/to/devaiflow/docs/config-templates/team.json $DEVAIFLOW_HOME/

# Edit the files
vim $DEVAIFLOW_HOME/backends/jira.json
vim $DEVAIFLOW_HOME/organization.json
vim $DEVAIFLOW_HOME/team.json

# Verify
daf config show
```

**Note:** Workspace config takes precedence over user config.

## Organization-Specific Configuration

If your organization provides pre-configured repositories, **don't use these templates**. Instead:

1. Clone your organization's base configuration repository (if available):
   ```bash
   git clone <your-enterprise-git-repo>/devflow-for-red-hatters ~/workspace/devflow-for-red-hatters
   ```

2. Or for project-specific configuration (includes all organization settings):
   ```bash
   git clone <your-enterprise-git-repo>/devflow-for-red-hatters-aap ~/workspace/devflow-for-red-hatters-aap
   ```

These repositories would have all organization-specific JIRA settings pre-configured.

## Configuration Priority

DevAIFlow merges configuration from multiple sources:

1. **Workspace config** (highest priority) - Config files in your workspace directory
2. **User config** - `$DEVAIFLOW_HOME/` directory
3. **Built-in defaults** (lowest priority)

Example: If `organization.json` exists in both workspace and `$DEVAIFLOW_HOME/`, the workspace version takes precedence.

## Validation

After configuration, validate with:

```bash
# Show merged configuration
daf config show

# Show split configuration files
daf config show --format split

# Test JIRA connection
daf jira view MYAPP-123
```

## Troubleshooting

### "Invalid JIRA project key"
- Check `organization.json` has correct `jira_project` value
- Verify the project exists in your JIRA instance

### "Field not found: acceptance_criteria"
- Field mappings are auto-discovered on first use
- If auto-discovery fails, manually add field ID to `backends/jira.json`
- Check field name in JIRA admin settings

### "Transition failed"
- Verify `transitions.on_start.to` and `transitions.on_complete.to` in `organization.json` match your JIRA workflow
- Use `prompt: true` to manually select status during transitions

### "Configuration not loaded"
- Verify files are in the correct location (workspace root or `$DEVAIFLOW_HOME/`)
- Check JSON syntax is valid: `python -m json.tool < organization.json`
- Ensure files are named exactly: `organization.json`, `team.json`, `backends/jira.json`

## Support

- Documentation: https://github.com/itdove/devaiflow
- Issues: https://github.com/itdove/devaiflow/issues
