---
name: daf-config
description: View current configuration (read-only)
user-invocable: true
argument-hint: "show [--fields|--sync-filters|--prompts]"
---

Display the current daf configuration including JIRA settings, workspace paths, and prompt defaults.

```bash
daf config show
```

**What it shows:**

**JIRA Configuration:**
- Project key
- Workstream
- Custom field mappings (epic link, workstream, acceptance criteria)
- Comment visibility settings
- Transition rules (on start, on complete)

**Paths & Directories:**
- Workspace directory
- Repository paths
- PR template URL

**Prompt Configuration:**
- Whether prompts are enabled/disabled for various operations
- Memory management settings
- Git auto-operations

**Example output:**
```
DevAIFlow Configuration

JIRA Settings:
  Project: PROJ
  Workstream: WORK
  Epic Link Field: customfield_10014
  Workstream Field: customfield_10015
  Acceptance Criteria Field: customfield_10016
  Transition on Start: In Progress
  Transition on Complete: Code Review

Repositories:
  Workspace: ~/development/workspace
  Paths:
    - backend-api: ~/development/workspace/backend-api
    - frontend-app: ~/development/workspace/frontend-app

PR Template:
  URL: https://github.com/YOUR-ORG/.github/blob/main/.github/PULL_REQUEST_TEMPLATE.md

Model Provider:
  The default profile supplies the provider credentials and the model choices for
  `new`, `open`, `git_new`, `jira_new`, `investigation`, `commit_message`, and
  `pr_template`.

  Each profile declares its agent/IDE adapter as well as provider credentials.
  `--model-profile` selects a different profile for a session. There is no
  separate AI-backend selector. `--model` overrides the model for a session command only; commit-message
  and PR-template generation always use their configured utility models.

Example profile configuration:
```json
{
  "model_provider": {
    "default_profile": "local-ollama",
    "profiles": {
      "local-ollama": {
        "name": "local-ollama",
        "provider": "ollama",
        "agent_backend": "ollama",
        "api_url": "http://localhost:11434",
        "models": {
          "new": "qwen3-coder",
          "open": "qwen3-coder",
          "commit_message": "llama3.2",
          "pr_template": "llama3.2"
        },
        "reasoning_efforts": {
          "new": "high",
          "open": "medium",
          "commit_message": "low",
          "pr_template": "medium"
        }
      }
    }
  }
}
```

Only local providers (`llama.cpp`, `ollama`, and `mlx`) require an API URL.

Prompt Configuration:
  Prompts Enabled: Yes
  Memory Per Session: Default (system managed)
```

**Use this to:**
- Verify JIRA integration is configured correctly
- Check workspace and repository paths
- See custom field mappings
- Understand transition rules
- Debug configuration issues

**View specific configuration subsets:**
```bash
daf config show --prompts       # Show only prompt configuration
daf config show --fields        # Show available JIRA custom fields
daf config show --sync-filters  # Show sync filter configuration
daf config context list         # List available context files
daf config context show         # Show context file contents
```

**Related commands:**
```bash
/daf help                     # Quick reference of all daf commands
daf config --help             # Full list of config subcommands
```

**Important:**
- This is a READ-ONLY command - safe to run inside Claude Code
- To modify config, exit Claude Code and use `daf config set-*` commands
- Configuration is stored in $DEVAIFLOW_HOME/config.yaml
