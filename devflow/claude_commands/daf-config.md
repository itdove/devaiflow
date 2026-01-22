---
description: View current configuration (read-only)
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
daf config show-prompts       # Show only prompt configuration
daf config context list       # List available context files
daf config context show       # Show context file contents
```

**Modify configuration (must run OUTSIDE Claude Code):**
```bash
# Exit Claude Code first, then:
daf config tui
daf config tui
daf config tui
daf config edit               # Interactive TUI editor
```

**Related commands:**
```bash
/daf help                     # Quick reference of all daf commands
daf config --help             # Full list of config subcommands
```

**Important:**
- This is a READ-ONLY command - safe to run inside Claude Code
- To modify config, exit Claude Code and use `daf config set-*` commands
- Configuration is stored in ~/.daf-sessions/config.yaml
