# Enterprise Model Provider Enforcement Guide

This guide explains how enterprise administrators can enforce approved model providers company-wide for compliance, cost control, and security.

## Table of Contents

1. [Overview](#overview)
2. [Why Enforce Model Providers?](#why-enforce-model-providers)
3. [Configuration Structure](#configuration-structure)
4. [Setting Up Enforcement](#setting-up-enforcement)
5. [Cost Tracking and Budgeting](#cost-tracking-and-budgeting)
6. [Audit Logging and Compliance](#audit-logging-and-compliance)
7. [User Experience](#user-experience)
8. [Team-Level Enforcement](#team-level-enforcement)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

## Overview

Enterprise Model Provider Enforcement allows administrators to:

- **Enforce** approved AI model providers company-wide
- **Prevent** users from using unapproved or expensive models
- **Track** model usage and costs via audit logs
- **Budget** and forecast AI costs across teams
- **Comply** with data governance and security policies

When enforcement is active, users cannot override the enterprise configuration via:
- ❌ CLI flags (`--model-profile`)
- ❌ Environment variables (`MODEL_PROVIDER_PROFILE`)
- ❌ User config files (`config.json`)
- ❌ TUI configuration editor (UI disabled with warning)

## Why Enforce Model Providers?

### Cost Control

**Problem**: Users might choose expensive models without realizing the cost impact.

**Solution**: Enforce cost-effective models (e.g., Vertex AI at $3/M tokens vs Anthropic API at $15/M tokens).

**Savings**: Up to 80% cost reduction with enforced provider selection.

### Compliance and Security

**Problem**: Data governance policies may require:
- Data residency (EU data must stay in EU)
- Private cloud deployment (no external APIs)
- Approved vendor lists (only certain cloud providers)

**Solution**: Enforce Vertex AI in specific regions or internal llama.cpp servers.

### Budget Management

**Problem**: Unpredictable AI costs across teams.

**Solution**: Set monthly budget limits per profile and track usage via audit logs.

### Standardization

**Problem**: Inconsistent model quality and behavior across teams.

**Solution**: Enforce standardized model configurations for consistent results.

## Configuration Structure

Enterprise enforcement uses a hierarchical configuration system:

```
~/.daf-sessions/
├── enterprise.json     # Enterprise-wide enforcement (highest priority)
├── team.json          # Team-level defaults (can enforce if enterprise doesn't)
├── organization.json  # Organization settings (no enforcement for model_provider)
└── config.json        # User preferences (overridden by enforcement)
```

**Hierarchy**: Enterprise > Team > User

When `enterprise.json` defines `model_provider`, it takes absolute precedence.

## Setting Up Enforcement

### Step 1: Create Enterprise Configuration

Create or edit `~/.daf-sessions/enterprise.json`:

```json
{
  "model_provider": {
    "default_profile": "vertex-prod",
    "profiles": {
      "vertex-prod": {
        "name": "Vertex AI Production",
        "use_vertex": true,
        "vertex_project_id": "company-gcp-project",
        "vertex_region": "us-east5",
        "cost_per_million_input_tokens": 3.00,
        "cost_per_million_output_tokens": 15.00,
        "monthly_budget_usd": 5000.00,
        "cost_center": "ENG-PLATFORM"
      }
    }
  }
}
```

**Field Descriptions:**

| Field | Required | Description |
|-------|----------|-------------|
| `default_profile` | Yes | Profile to use by default |
| `profiles` | Yes | Dictionary of available profiles |
| `name` | Yes | Human-readable profile name |
| `use_vertex` | No | Set to `true` for Google Vertex AI |
| `vertex_project_id` | If Vertex | GCP project ID |
| `vertex_region` | If Vertex | GCP region (e.g., `us-east5`) |
| `base_url` | No | Custom API endpoint (for llama.cpp, etc.) |
| `auth_token` | No | Authentication token override |
| `api_key` | No | API key override (use `""` to disable) |
| `model_name` | No | Specific model name |
| `env_vars` | No | Additional environment variables |

### Step 2: Add Cost Tracking (Optional)

Add cost tracking fields to each profile:

```json
{
  "cost_per_million_input_tokens": 3.00,
  "cost_per_million_output_tokens": 15.00,
  "monthly_budget_usd": 5000.00,
  "cost_center": "ENG-PLATFORM"
}
```

**Benefits:**
- Track estimated costs in audit logs
- Set budget alerts
- Attribution to cost centers for chargeback
- Enterprise-wide cost analysis

### Step 3: Deploy Configuration

**Option A: Shared Config Directory (Recommended)**

```bash
# Mount shared config directory
export DEVAIFLOW_HOME=/mnt/shared-config/.daf-sessions

# All users read enterprise.json from shared location
daf open PROJ-123
```

**Option B: Configuration Management**

Use Ansible, Puppet, or similar to deploy `enterprise.json` to user home directories:

```yaml
# Ansible example
- name: Deploy DAF enterprise config
  copy:
    src: enterprise.json
    dest: ~/.daf-sessions/enterprise.json
    owner: "{{ ansible_user }}"
    mode: 0644
```

**Option C: Git Repository**

Store configurations in a git repository:

```bash
# Organization repo: github.com/mycompany/daf-configs
# Users clone to ~/.daf-sessions/
git clone git@github.com:mycompany/daf-configs.git ~/.daf-sessions
```

### Step 4: Verify Enforcement

```bash
# Users should see enforcement message
daf config edit
# "⚠ Model provider configuration is enforced by enterprise configuration"

# Verify profile cannot be changed
daf open PROJ-123 --model-profile llama-cpp
# Should still use enforced profile (vertex-prod), not llama-cpp
```

## Cost Tracking and Budgeting

### Estimating Costs

Cost tracking fields enable automatic cost estimation based on token usage:

```json
{
  "cost_per_million_input_tokens": 3.00,   # $3 per million input tokens
  "cost_per_million_output_tokens": 15.00  # $15 per million output tokens
}
```

**Example Calculation:**
- Session uses 100K input tokens + 50K output tokens
- Input cost: (100,000 / 1,000,000) × $3.00 = $0.30
- Output cost: (50,000 / 1,000,000) × $15.00 = $0.75
- **Total cost: $1.05**

### Setting Budget Limits

```json
{
  "monthly_budget_usd": 5000.00
}
```

Budget limits are informational and logged in audit logs. Future versions will support:
- Budget alerts when 80% threshold reached
- Budget enforcement (block new sessions when budget exhausted)
- Budget rollover tracking

### Cost Center Attribution

```json
{
  "cost_center": "ENG-PLATFORM"
}
```

Cost centers enable chargeback and cross-departmental cost attribution:

```bash
# Analyze costs by cost center
cat ~/.daf-sessions/audit.log | jq 'select(.cost_center == "ENG-PLATFORM")'
```

## Audit Logging and Compliance

All model provider usage is automatically logged to `~/.daf-sessions/audit.log`.

### Log Format

Logs are structured JSON (one entry per line):

```json
{
  "timestamp": "2026-03-24T20:15:30.123456",
  "event_type": "session_created",
  "category": "model_provider",
  "session_name": "PROJ-123",
  "profile_name": "vertex-prod",
  "enforcement_source": "enterprise",
  "model_name": null,
  "base_url": null,
  "use_vertex": true,
  "vertex_region": "us-east5",
  "cost_per_million_input_tokens": 3.0,
  "cost_per_million_output_tokens": 15.0,
  "cost_center": "ENG-PLATFORM",
  "additional_data": {
    "issue_key": "PROJ-123",
    "goal": "Implement feature X",
    "working_directory": "myproject"
  }
}
```

### Analyzing Audit Logs

**Count sessions by profile:**
```bash
cat ~/.daf-sessions/audit.log | jq -r .profile_name | sort | uniq -c
```

**Find non-compliant sessions (if any bypass enforcement):**
```bash
cat ~/.daf-sessions/audit.log | jq 'select(.enforcement_source == null)'
```

**Calculate total cost by cost center:**
```bash
cat ~/.daf-sessions/audit.log | \
  jq -r '[.cost_center, .cost_per_million_input_tokens] | @tsv' | \
  awk '{sum[$1]+=$2} END {for (cc in sum) print cc, sum[cc]}'
```

**Export for BI tools:**
```bash
cat ~/.daf-sessions/audit.log | \
  jq -r '[.timestamp, .session_name, .profile_name, .cost_center, .enforcement_source] | @csv' \
  > audit_export.csv
```

### Log Rotation

Audit logs use Python's `RotatingFileHandler`:
- Maximum size: 10MB per file
- Backup count: 5 files
- Total storage: ~50MB

Old logs are automatically rotated to:
- `audit.log.1`
- `audit.log.2`
- `audit.log.3`
- `audit.log.4`
- `audit.log.5`

## User Experience

When enforcement is active, users see:

### TUI Configuration Editor

```
⚠ Model provider configuration is enforced by enterprise configuration
Users cannot modify model provider profiles or default profile selection.
Contact your enterprise administrator to request changes.

Available Profiles
┌─────────────────────────┐
│ Vertex AI Production ⭐ │  [Set Default] [Edit] [Delete]
│ us-e5                   │  (all buttons disabled)
└─────────────────────────┘

[Add Profile]  (button disabled)
```

### Command Line

```bash
$ daf config show
# Shows merged configuration with enterprise-enforced profiles

$ MODEL_PROVIDER_PROFILE=llama-cpp daf open PROJ-123
# Ignores environment variable, uses enforced profile

$ daf open PROJ-123 --model-profile llama-cpp
# Ignores CLI flag, uses enforced profile
```

### No Error Messages

Users do NOT see error messages when they try to override. The system silently uses the enforced profile to avoid confusion.

## Team-Level Enforcement

Teams can enforce profiles if enterprise hasn't:

`~/.daf-sessions/team.json`:

```json
{
  "model_provider": {
    "default_profile": "llama-cpp-shared",
    "profiles": {
      "llama-cpp-shared": {
        "name": "Team llama.cpp Server",
        "base_url": "http://llama-cpp.internal.company.com:8000",
        "auth_token": "llama-cpp",
        "api_key": "",
        "model_name": "Qwen3-Coder",
        "cost_per_million_input_tokens": 0.0,
        "cost_per_million_output_tokens": 0.0,
        "cost_center": "ENG-BACKEND-TEAM"
      }
    }
  }
}
```

**Use Case**: Teams can standardize on a shared infrastructure without enterprise-wide enforcement.

**Hierarchy**: Team enforcement is overridden if enterprise defines `model_provider`.

## Best Practices

### 1. Start with Recommendations, Not Enforcement

**Phase 1**: Deploy profiles via `team.json` (no enforcement)
- Users can choose from provided profiles
- Monitor adoption via audit logs

**Phase 2**: After 80%+ adoption, enforce via `enterprise.json`
- Smooth transition for users
- Fewer support requests

### 2. Provide Multiple Profiles

```json
{
  "profiles": {
    "vertex-prod": {
      "name": "Vertex AI (Production)",
      "use_vertex": true,
      "cost_per_million_input_tokens": 3.00,
      "monthly_budget_usd": 10000.00
    },
    "vertex-dev": {
      "name": "Vertex AI (Development - Budget Limited)",
      "use_vertex": true,
      "cost_per_million_input_tokens": 3.00,
      "monthly_budget_usd": 1000.00
    }
  }
}
```

Users feel less restricted if they have choices within approved options.

### 3. Communicate Cost Savings

```
┌─────────────────────────────────────────┐
│ Enterprise Model Configuration          │
├─────────────────────────────────────────┤
│ Using: Vertex AI Production (enforced) │
│ Cost: $3/M tokens                       │
│ Savings: 80% vs Anthropic API          │
│ Monthly Budget: $5,000                  │
└─────────────────────────────────────────┘
```

Help users understand WHY enforcement exists (cost savings).

### 4. Monitor Audit Logs

Set up automated monitoring:

```bash
# Daily report of model provider usage
cat ~/.daf-sessions/audit.log | \
  jq -r 'select(.timestamp | startswith("2026-03-24"))' | \
  jq -s 'group_by(.profile_name) | .[] | {profile: .[0].profile_name, count: length}'
```

Alert on:
- Budget threshold exceeded (>80% of monthly_budget_usd)
- Non-compliant sessions (enforcement_source == null)
- Unusual usage patterns

### 5. Document for Users

Create internal documentation:

```markdown
# Using DevAIFlow at [Company]

We use Google Vertex AI for all AI-assisted development to:
- Save 80% on AI costs ($3/M vs $15/M tokens)
- Keep data within our GCP environment
- Meet compliance requirements

Your configuration is managed centrally. If you need changes,
contact #devtools-support.
```

### 6. Version Control Configurations

```bash
# Store in git
git init ~/.daf-sessions
git add enterprise.json team.json
git commit -m "Enforce Vertex AI company-wide"
git tag v1.0-enforce-vertex
```

Benefits:
- Audit trail of configuration changes
- Easy rollback if needed
- Change management process

## Troubleshooting

### Users Report Configuration Not Enforced

**Symptom**: Users can still change profiles in TUI

**Cause**: Enterprise config not loaded

**Fix**:
```bash
# Verify enterprise.json exists
ls -la ~/.daf-sessions/enterprise.json

# Verify it contains model_provider
cat ~/.daf-sessions/enterprise.json | jq .model_provider

# Verify it's being loaded
daf config show --json | jq .model_provider
```

### Audit Logs Not Generated

**Symptom**: `~/.daf-sessions/audit.log` does not exist

**Cause**: Session creation not triggering audit log

**Fix**:
```bash
# Create a test session to trigger logging
daf new --name test-audit --goal "Test audit logging"

# Verify log was created
ls -la ~/.daf-sessions/audit.log
cat ~/.daf-sessions/audit.log | jq .
```

### Cost Tracking Not in Logs

**Symptom**: Audit log missing cost_per_million_* fields

**Cause**: Profile doesn't have cost tracking fields

**Fix**: Add cost tracking to profile in `enterprise.json`:
```json
{
  "cost_per_million_input_tokens": 3.00,
  "cost_per_million_output_tokens": 15.00
}
```

### Users See Wrong Profile

**Symptom**: Users report using different profile than enforced

**Cause 1**: Session has old model_profile stored

**Fix**:
```bash
# Clear session model_profile
daf config show  # Check which profile is active
# Delete and recreate session if needed
```

**Cause 2**: Multiple config directories

**Fix**:
```bash
# Verify DEVAIFLOW_HOME
echo $DEVAIFLOW_HOME

# Should use standard location
unset DEVAIFLOW_HOME
```

### Enterprise Config Overridden by User

**Symptom**: User config changes persist despite enforcement

**Cause**: Bug in save logic (should not save user model_provider when enforced)

**Fix**: Verify ConfigLoader._save_new_format_config() prevents user overrides:
```python
if enterprise_config.model_provider or team_config.model_provider:
    # Model provider is enforced - don't save user override
    user_model_provider = None
```

## Summary

Enterprise Model Provider Enforcement provides:

✅ **Cost Control**: Enforce cost-effective models and track spending
✅ **Compliance**: Meet data governance and security requirements
✅ **Visibility**: Audit all model provider usage
✅ **Standardization**: Consistent model behavior across teams
✅ **Flexibility**: Team-level customization when needed

**Next Steps:**

1. Define your enterprise model provider strategy
2. Create `enterprise.json` with approved profiles
3. Add cost tracking fields
4. Deploy configuration to users
5. Monitor audit logs for compliance and cost
6. Iterate based on usage patterns

For questions or support, refer to:
- [Alternative Model Providers Guide](../reference/alternative-model-providers.md)
- [Configuration Reference](../reference/configuration.md)
- DevAIFlow GitHub Issues: https://github.com/itdove/devaiflow/issues
