---
name: daf-jira-fields
description: JIRA field mapping rules, validation, and defaults for DevAIFlow
user-invocable: false
---

# JIRA Field Intelligence for DevAIFlow

Understanding JIRA field mappings, validation rules, and defaults for creating/updating JIRA issues.

## Quick Discovery

```bash
# Discover YOUR JIRA's custom fields
daf config show --fields

# Refresh from JIRA API
daf config refresh-jira-fields

# View merged config
daf config show
```

## System vs Custom Fields (CRITICAL)

### System Fields
Standard JIRA fields with **dedicated CLI options**:

**Fields:** components, labels, assignee, reporter, priority, security-level, fixVersions, affectedVersions

**Usage:**
```bash
# ✅ CORRECT
daf jira create bug --components backend --labels urgent --assignee jdoe

# ❌ WRONG - Will error
daf jira create bug --field components=backend  # Error: Use --components option
```

**Array syntax:** Comma-separated values
```bash
--components backend,frontend,api
--labels urgent,production
```

### Custom Fields
Organization-specific fields with IDs like `customfield_12345`. Use **--field** with mapped names.

**Discovery:**
```bash
daf config show --fields
```

**Usage:**
```bash
# Use YOUR organization's field names (not generic examples)
daf jira create story \
  --summary "Feature" \
  --parent PROJ-1234 \
  --field <your_field_name>=<value>
```

**Never use customfield IDs directly:**
```bash
# ❌ WRONG
--field customfield_12345=value

# ✅ CORRECT - Use mapped name
--field team_assignment=value
```

## Field Mapping Structure

**Location:** `$DEVAIFLOW_HOME/backends/jira.json`

**Structure:**
```json
{
  "field_mappings": {
    "<field_name>": {
      "id": "customfield_XXXXX",
      "name": "Display Name",
      "type": "option|string|number|array|user|version",
      "required_for": ["Story", "Task"],
      "available_for": ["Story", "Task", "Epic"],
      "allowed_values": ["Value1", "Value2"]
    }
  }
}
```

**Attributes:**
- `id` - JIRA customfield ID
- `type` - Field type (string, number, option, array, user, version)
- `required_for` - Issue types where field is required
- `available_for` - Issue types where field can be used
- `allowed_values` - Valid values (for select fields)

## Validation Rules

DevAIFlow validates **before** calling JIRA API.

### Rule 1: Field Availability
```python
if issue_type not in field_config["available_for"]:
    raise ValidationError("Field not available for this issue type")
```

**Example:**
```bash
# Field config: available_for = ["Story", "Task"]

✅ daf jira create story --field team_field=value  # Valid
❌ daf jira create bug --field team_field=value    # Error
```

### Rule 2: Allowed Values
```python
if value not in field_config["allowed_values"]:
    raise ValidationError("Invalid value")
```

**Example:**
```bash
# Field config: allowed_values = ["Critical", "Major", "Minor"]

✅ daf jira create bug --field severity=Critical  # Valid
❌ daf jira create bug --field severity=High     # Error
```

### Rule 3: Required Fields
```python
for field_name, config in field_mappings.items():
    if issue_type in config["required_for"]:
        if field_name not in provided_fields:
            raise ValidationError("Missing required field")
```

**Example:**
```bash
# Field config: required_for = ["Story"]

❌ daf jira create story --summary "Feature"  # Error: Missing required field
✅ daf jira create story --summary "Feature" --field required_field=value  # Valid
```

## Default Value Application

Defaults from `team.json` apply **ONLY to required fields**.

**Configuration:**
```json
{
  "custom_field_defaults": {
    "field_a": "default_value",
    "field_b": "optional_default"
  }
}
```

**Logic:**
1. If field is required for issue type → apply default (if not provided)
2. If field is optional → skip default

**Example:**
```json
{
  "field_a": {"required_for": ["Story"]},
  "field_b": {"required_for": []}
}
```

```bash
daf jira create story --summary "Feature"
# Applied: field_a = "default_value" (required)
# Skipped: field_b (optional, no auto-default)
```

**Why?** Prevents cluttering issues with optional field defaults.

## Workflow Example

```bash
# Step 1: Discover required fields
daf config show --fields | grep "Required for.*Story"

# Step 2: Check allowed values
# Output example:
#   team_field - Required for: Story, Task
#   effort_field - Required for: Story (allowed: 1,2,3,5,8)

# Step 3: Create with required fields
daf jira create story \
  --summary "Add feature" \
  --parent PROJ-1234 \
  --components backend \
  --field team_field=TeamA \
  --field effort_field=5
```

## Troubleshooting

### Error: Field not available for issue type
```
Field 'custom_field' not available for 'Bug'. Available for: Story, Task
```
**Fix:** Use field only for allowed issue types or update JIRA config.

### Error: Invalid value
```
Invalid value 'High' for 'severity'. Allowed: Critical, Major, Minor
```
**Fix:** Use value from allowed_values list (case-sensitive).

### Error: Missing required field
```
Missing required field 'team_field' for 'Story'
```
**Fix:** Add `--field team_field=value` or configure default in team.json.

### Error: System field with --field
```
'components' is a system field. Use --components option
```
**Fix:** Use `--components backend` not `--field components=backend`.

## Best Practices

1. **Always discover first:** `daf config show --fields`
2. **Validate before creating:** Check required_for, available_for, allowed_values
3. **Use correct syntax:**
   - System fields: `--components`, `--labels`, `--assignee`
   - Custom fields: `--field field_name=value`
4. **Never use customfield IDs:** Always use mapped names
5. **Comma-separated arrays:** `--components a,b,c` not `--components a --components b`

## See Also

- **daf-cli skill** - CLI command syntax
- **Atlassian MCP** - Reading JIRA issues
- **DAF_AGENTS.md** - JIRA templates and workflows
