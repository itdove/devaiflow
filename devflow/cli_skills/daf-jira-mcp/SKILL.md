---
name: daf-jira-mcp
description: Using MCP JIRA tools with DevAIFlow validation logic and field intelligence
user-invocable: false
---

# MCP JIRA Integration with DevAIFlow Intelligence

When using MCP JIRA tools (e.g., `mcp__mcp-atlassian__jira_*`), you can leverage DevAIFlow's configuration intelligence to build validated, compliant JIRA operations.

## Core Concept

**DevAIFlow stores JIRA field metadata that MCP tools need:**
- Field IDs (customfield_12345) mapped to friendly names
- Required fields per issue type
- Allowed values for select/option fields
- Field availability per issue type
- Team/organization defaults

**Get this data:** `daf config show --json`

## Step-by-Step: Using MCP with daf Intelligence

### Step 1: Get Configuration Metadata

```bash
# Get complete JIRA configuration
daf config show --json > /tmp/daf-config.json
```

**Key sections in the output:**
```json
{
  "jira": {
    "project": "AAP",
    "custom_field_defaults": {
      "workstream": "SaaS"
    },
    "system_field_defaults": {
      "components": ["ansible-saas"],
      "labels": ["backend"]
    },
    "field_mappings": {
      "acceptance_criteria": {
        "id": "customfield_10718",
        "name": "Acceptance Criteria",
        "type": "string",
        "required_for": ["Bug", "Story", "Task", "Epic"],
        "available_for": ["Bug", "Story", "Task", "Epic"],
        "allowed_values": []
      },
      "workstream": {
        "id": "customfield_12345",
        "name": "Workstream",
        "type": "option",
        "required_for": ["Story", "Task"],
        "available_for": ["Story", "Task", "Epic"],
        "allowed_values": ["Platform", "SaaS", "Services"]
      }
    }
  }
}
```

### Step 2: Apply Validation Logic

**Before calling MCP, validate:**

1. **Field Availability Check**
   ```python
   issue_type = "Story"
   field_name = "workstream"
   
   # Check if field is available for this issue type
   if issue_type not in field_mappings[field_name]["available_for"]:
       raise Error(f"{field_name} not available for {issue_type}")
   ```

2. **Required Fields Check**
   ```python
   # Get all required fields for issue type
   required_fields = [
       field_name 
       for field_name, config in field_mappings.items()
       if issue_type in config.get("required_for", [])
   ]
   
   # Verify all required fields are provided
   missing = [f for f in required_fields if f not in provided_fields]
   if missing:
       raise Error(f"Missing required fields: {missing}")
   ```

3. **Allowed Values Check**
   ```python
   # For select/option fields, validate value
   allowed = field_mappings["workstream"]["allowed_values"]
   if value not in allowed:
       raise Error(f"Invalid value '{value}'. Allowed: {allowed}")
   ```

### Step 3: Apply Defaults

```python
# Apply custom field defaults (ONLY for required fields)
for field_name, default_value in custom_field_defaults.items():
    if field_name not in provided_fields:
        field_config = field_mappings.get(field_name, {})
        if issue_type in field_config.get("required_for", []):
            # Apply default only for required fields
            provided_fields[field_name] = default_value

# Apply system field defaults (components, labels)
if "components" not in provided_fields:
    provided_fields["components"] = system_field_defaults.get("components", [])
```

### Step 4: Map to JIRA Field IDs

```python
# Convert friendly names to JIRA field IDs
additional_fields = {}

for field_name, value in provided_fields.items():
    field_config = field_mappings.get(field_name)
    if field_config:
        field_id = field_config["id"]
        field_type = field_config["type"]
        
        # Format value based on field type
        if field_type == "option":
            additional_fields[field_id] = {"value": value}
        elif field_type == "array":
            additional_fields[field_id] = [{"name": v} for v in value]
        elif field_type == "user":
            additional_fields[field_id] = {"name": value}
        else:
            additional_fields[field_id] = value
```

### Step 5: Build MCP Call

```python
import json

# Build additional_fields JSON for MCP
additional_fields_json = json.dumps(additional_fields)

# Call MCP with validated, formatted fields
mcp__mcp-atlassian__jira_create_issue(
    project_key="AAP",
    summary="Add caching layer",
    issue_type="Story",
    description="Implementation details...",
    additional_fields=additional_fields_json
)
```

## Complete Example: Create Story with Validation

```python
# Step 1: Load config
import json
with open('/tmp/daf-config.json') as f:
    config = json.load(f)

field_mappings = config["jira"]["field_mappings"]
custom_defaults = config["jira"]["custom_field_defaults"]
system_defaults = config["jira"]["system_field_defaults"]

# Step 2: Define issue
issue_type = "Story"
provided = {
    "summary": "Add Redis caching",
    "description": "h3. Overview\n\nImplement caching...",
    "workstream": "Platform",  # Will validate against allowed_values
    "acceptance_criteria": "- [] Tests pass\n- [] Performance targets met"
}

# Step 3: Validate required fields
required = [
    name for name, cfg in field_mappings.items()
    if issue_type in cfg.get("required_for", [])
]

missing = [f for f in required if f not in provided]
if missing:
    print(f"ERROR: Missing required fields: {missing}")
    # Should include: components (from required_for)

# Step 4: Apply defaults for missing required fields
for field_name in required:
    if field_name not in provided:
        # Check custom defaults first
        if field_name in custom_defaults:
            provided[field_name] = custom_defaults[field_name]
        # Check system defaults
        elif field_name in system_defaults:
            provided[field_name] = system_defaults[field_name]

# Step 5: Validate allowed values
for field_name, value in provided.items():
    cfg = field_mappings.get(field_name, {})
    allowed = cfg.get("allowed_values", [])
    if allowed and value not in allowed:
        print(f"ERROR: Invalid value '{value}' for {field_name}")
        print(f"Allowed: {allowed}")

# Step 6: Map to JIRA IDs and format
additional_fields = {}

for field_name, value in provided.items():
    if field_name in ["summary", "description", "issue_type"]:
        continue  # These are direct parameters
    
    cfg = field_mappings[field_name]
    field_id = cfg["id"]
    field_type = cfg["type"]
    
    # Format based on type
    if field_type == "option":
        additional_fields[field_id] = {"value": value}
    elif field_type == "array":
        if isinstance(value, list):
            additional_fields[field_id] = [{"name": v} for v in value]
        else:
            additional_fields[field_id] = [{"name": value}]
    elif field_type == "string":
        additional_fields[field_id] = value
    else:
        additional_fields[field_id] = value

# Step 7: Call MCP
additional_fields_json = json.dumps(additional_fields)

mcp__mcp-atlassian__jira_create_issue(
    project_key="AAP",
    summary=provided["summary"],
    issue_type="Story",
    description=provided["description"],
    additional_fields=additional_fields_json
)
```

## Quick Reference: Field Type Formatting

| Type | Config | MCP Format |
|------|--------|------------|
| **string** | `"type": "string"` | `"customfield_123": "value"` |
| **option** | `"type": "option"` | `"customfield_123": {"value": "Option1"}` |
| **array** | `"type": "array"` | `"customfield_123": [{"name": "Item1"}, {"name": "Item2"}]` |
| **user** | `"type": "user"` | `"customfield_123": {"name": "username"}` |
| **version** | `"type": "version"` | `"customfield_123": [{"name": "1.0.0"}]` |
| **number** | `"type": "number"` | `"customfield_123": 42` |

## Validation Checklist

Before calling MCP JIRA tools, verify:

- [ ] **Field availability**: All fields in `available_for` for issue type
- [ ] **Required fields**: All fields in `required_for` are provided or have defaults
- [ ] **Allowed values**: Values match `allowed_values` (case-sensitive)
- [ ] **Field IDs**: Using JIRA field IDs (customfield_*), not friendly names
- [ ] **Field types**: Values formatted correctly for field type
- [ ] **Defaults applied**: Custom/system defaults applied to required fields only

## Error Messages to Watch For

**From MCP (indicates validation was missed):**
```
Field 'customfield_12345' is not on the appropriate screen, or unknown
→ Field not available_for this issue type

Field 'customfield_12345' is required
→ Missing required field

Invalid value 'High' for field 'customfield_12345'
→ Value not in allowed_values
```

**Better approach:** Validate BEFORE calling MCP using daf config intelligence.

## When to Use daf Commands Instead

**Use `daf jira create/update` when:**
- ✅ You want automatic validation (no manual checking)
- ✅ You want friendly field names (no field ID mapping)
- ✅ You want session integration (links issue to current session)
- ✅ You're creating issues frequently (daf handles all this automatically)

**Use MCP with daf intelligence when:**
- ✅ You need advanced JIRA operations not in daf (e.g., sprint management)
- ✅ You want direct API access with validation
- ✅ You're exploring JIRA data (searches, complex queries)
- ✅ You understand the field mapping and validation process

## See Also

- **daf-jira skill** - daf commands for validated JIRA operations
- **daf-jira-fields skill** - Field mapping reference and validation rules
- **daf-config skill** - How to view and manage daf configuration

## Issue Type Templates

DevAIFlow supports issue type templates that provide standardized descriptions for different issue types.

**Get templates from config:**

```bash
daf config show --json | jq '.organization.jira_issue_templates'
```

**Example templates in config:**
```json
{
  "organization": {
    "jira_issue_templates": {
      "Bug": "h3. Problem\n\n[Describe the bug]\n\nh3. Expected Behavior\n\n[What should happen]\n\nh3. Actual Behavior\n\n[What actually happens]\n\nh3. Reproduction Steps\n\n# Step 1\n# Step 2\n\nh3. Environment\n\n[Version, OS, browser, etc.]",
      "Story": "h3. User Story\n\nAs a [user type]\nI want [goal]\nSo that [benefit]\n\nh3. Acceptance Criteria\n\n- [] Criterion 1\n- [] Criterion 2\n\nh3. Technical Notes\n\n[Implementation details]",
      "Task": "h3. Objective\n\n[What needs to be done]\n\nh3. Tasks\n\n# Task 1\n# Task 2\n\nh3. Dependencies\n\n[Related tickets or blockers]",
      "Epic": "h3. Epic Goal\n\n[High-level objective]\n\nh3. Success Criteria\n\n- [] Outcome 1\n- [] Outcome 2\n\nh3. Scope\n\n*In Scope:*\n* Item 1\n\n*Out of Scope:*\n* Item 1"
    }
  }
}
```

### Using Templates with MCP

```python
# Load templates
templates = config["organization"]["jira_issue_templates"]

# Get template for issue type
issue_type = "Story"
description_template = templates.get(issue_type, "")

# Customize description
description = description_template.replace("[goal]", "cache API responses")
description = description.replace("[benefit]", "improve performance by 50%")

# Use in MCP call
mcp__mcp-atlassian__jira_create_issue(
    project_key="AAP",
    summary="Add Redis caching",
    issue_type="Story",
    description=description,
    additional_fields=additional_fields_json
)
```

**Benefits of using templates:**
- ✅ Consistent issue format across team
- ✅ Ensures all required information is captured
- ✅ Saves time (don't write descriptions from scratch)
- ✅ Matches team/org standards

**Note:** Templates use JIRA Wiki markup syntax (see daf-jira skill for syntax reference).

