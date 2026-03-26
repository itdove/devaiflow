# Multi-Agent Skill Installation Guide

DevAIFlow supports installing bundled skills to multiple AI coding assistants simultaneously. This guide explains how to use multi-agent skill installation to maintain consistent tooling across different AI agents.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Supported Agents](#supported-agents)
- [Installation Levels](#installation-levels)
- [Use Cases](#use-cases)
- [Skill Directory Locations](#skill-directory-locations)
- [Compatibility](#compatibility)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

## Overview

DevAIFlow includes bundled skills that provide:
- **Slash commands**: Interactive commands like `/daf-help`, `/daf-list`, `/daf-active`
- **Reference skills**: Auto-loaded documentation (daf-cli, gh-cli, git-cli, glab-cli)

These skills can be installed to multiple AI agents using the `daf skills` command with multi-agent flags.

## Quick Start

```bash
# Install to all supported agents
daf skills --all-agents

# Install to specific agents
daf skills --agent cursor

# Install to project directory (for team sharing)
daf skills --level project --project-path .

# Install to both global and project
daf skills --level both --project-path .
```

## Supported Agents

| Agent | Status | Global Directory | Project Directory | Env Variable |
|-------|--------|------------------|-------------------|--------------|
| **Claude Code** | ✅ Fully Tested | `~/.claude/skills/` | `<project>/.claude/skills/` | `$CLAUDE_CONFIG_DIR` |
| **GitHub Copilot** | ⚠️ Experimental | `~/.copilot/skills/` | `<project>/.github-copilot/skills/` | `$COPILOT_HOME` |
| **Cursor** | ⚠️ Experimental | `~/.cursor/skills/` | `<project>/.cursor/skills/` | _(none)_ |
| **Windsurf** | ⚠️ Experimental | `~/.codeium/windsurf/skills/` | `<project>/.windsurf/skills/` | _(none)_ |
| **Aider** | ⚠️ Experimental | `~/.aider/skills/` | `<project>/.aider/skills/` | _(none)_ |
| **Continue** | ⚠️ Experimental | `~/.continue/skills/` | `<project>/.continue/skills/` | _(none)_ |

**Notes:**
- ✅ **Fully Tested**: Claude Code has native skill support and has been thoroughly tested
- ⚠️ **Experimental**: Other agents may support skills as context files, but functionality is not guaranteed

## Installation Levels

### Global Installation (default)

Installs skills to the agent's global configuration directory (e.g., `~/.claude/skills/`).

**Pros:**
- Available in all projects automatically
- No need to commit to version control
- Good for personal development

**Cons:**
- Not shared with team members
- Different versions on different machines

**Example:**
```bash
daf skills --agent cursor
```

### Project Installation

Installs skills to the project directory (e.g., `<project>/.claude/skills/`).

**Pros:**
- Can be committed to git and shared with team
- Consistent versions across team
- Project-specific skill customization

**Cons:**
- Needs to be installed in each project
- Takes up space in repository

**Example:**
```bash
cd /path/to/project
daf skills --level project --project-path .
git add .claude/skills .cursor/skills
git commit -m "Add DevAIFlow skills for team"
```

### Both Levels

Installs to both global and project directories.

**Pros:**
- Skills always available (from global)
- Project-specific versions can override
- Best of both worlds

**Cons:**
- Duplicate installation
- May cause confusion about which version is active

**Example:**
```bash
daf skills --level both --project-path .
```

## Use Cases

### Personal Development

**Scenario**: You use multiple AI agents and want DevAIFlow skills available in all of them.

```bash
# Install to all agents globally
daf skills --all-agents
```

Now all skills are available in Claude Code, Cursor, Windsurf, etc.

### Team Collaboration

**Scenario**: Your team wants to ensure everyone has the same skills when working on a project.

```bash
# Project lead installs to project
cd /path/to/shared-project
daf skills --level project --project-path . --all-agents

# Commit to git
git add .claude/skills .cursor/skills .windsurf/skills
git commit -m "Add DevAIFlow skills for all agents"
git push

# Team members get skills automatically on next git pull
```

### Switching Between Agents

**Scenario**: You primarily use Claude Code but sometimes use Cursor for pair programming.

```bash
# You already have skills for Claude (from daf skills)
# Now add them for Cursor
daf skills --agents cursor
```

### Experimenting with New Agents

**Scenario**: You want to try out a new AI agent and need DevAIFlow skills.

```bash
# Try Windsurf with DevAIFlow skills
daf skills --agent windsurf

# Launch a session
daf open PROJ-123
# (system launches Windsurf if configured as agent_backend)
```

## Skill Directory Locations

DevAIFlow installs skills to agent-specific directories. Here's where they go:

### Global Directories

| Agent | Default Path | Customizable via |
|-------|-------------|------------------|
| Claude Code | `~/.claude/skills/` | `$CLAUDE_CONFIG_DIR/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `$COPILOT_HOME/skills/` |
| Cursor | `~/.cursor/skills/` | _(hardcoded)_ |
| Windsurf (Unix) | `~/.codeium/windsurf/skills/` | _(hardcoded)_ |
| Windsurf (Windows) | `%APPDATA%\Codeium\Windsurf\skills\` | _(hardcoded)_ |
| Aider | `~/.aider/skills/` | _(hardcoded)_ |
| Continue | `~/.continue/skills/` | _(hardcoded)_ |

### Project Directories

Project-level installations follow a consistent pattern:

| Agent | Project Path |
|-------|-------------|
| Claude Code | `<project>/.claude/skills/` |
| GitHub Copilot | `<project>/.github-copilot/skills/` |
| Cursor | `<project>/.cursor/skills/` |
| Windsurf | `<project>/.windsurf/skills/` |
| Aider | `<project>/.aider/skills/` |
| Continue | `<project>/.continue/skills/` |

### Environment Variables

**Claude Code** and **GitHub Copilot** support environment variables to override the default config directory:

```bash
# Claude Code
export CLAUDE_CONFIG_DIR=/custom/claude
daf skills --agents claude
# Installs to /custom/claude/skills/

# GitHub Copilot
export COPILOT_HOME=/custom/copilot
daf skills --agents copilot
# Installs to /custom/copilot/skills/
```

## Compatibility

### Native Skill Support

**Claude Code** and **Ollama** have native skill support:
- ✅ Slash commands work (`/daf-help`, `/daf-list`, etc.)
- ✅ Reference skills auto-loaded as context
- ✅ Full functionality guaranteed

### Context File Support (Experimental)

Other agents may support skills as context files or documentation:
- ⚠️ **GitHub Copilot**: May use skills as context in chat
- ⚠️ **Cursor**: May use skills as context in composer/chat
- ⚠️ **Windsurf**: May use skills as context in Cascade
- ⚠️ **Aider**: Can read skills with `--read` flag
- ⚠️ **Continue**: May use skills as context files

**Note**: Slash commands (`/daf-*`) will NOT work in agents without native skill support. Only the documentation content may be useful.

## Advanced Usage

### Dry Run (Preview Changes)

Preview what would be installed without making changes:

```bash
daf skills --all-agents --dry-run
```

Output:
```
Checking for updates (dry run)...

Installing to claude (/Users/user/.claude/skills)...
  ✓ daf-active (up-to-date)
  ✓ daf-help (up-to-date)
  ...

Installing to cursor (/Users/user/.cursor/skills)...
  ✓ Would install daf-active
  ✓ Would install daf-help
  ...

Dry run complete. No changes were made.
```

### Selective Agent Installation

Install to only the agents you use:

```bash
# Just Claude and Cursor
daf skills --agent cursor

# Just Windsurf
daf skills --agent windsurf
```

### Combining Flags

Combine multiple flags for complex scenarios:

```bash
# Install to all agents, both global and project
daf skills --all-agents --level both --project-path .

# Install to specific agents, project only
daf skills --agent cursor --level project --project-path .

# Preview all-agents installation to project
daf skills --all-agents --level project --project-path . --dry-run
```

### Upgrading Existing Installations

When you run `daf skills`, it automatically:
- **Installs** skills that don't exist
- **Upgrades** skills that are outdated
- **Skips** skills that are already up-to-date

```bash
# Update all agents to latest skills
daf skills --all-agents
```

## Troubleshooting

### Skills Not Working in Agent

**Problem**: Installed skills to Cursor/Windsurf but slash commands don't work.

**Solution**: Only Claude Code and Ollama have native slash command support. Other agents may only use skills as documentation/context.

**Workaround**: Use the skills as reference by reading the SKILL.md files manually.

### Installation Failed

**Problem**: `daf skills --agents cursor` fails with error.

**Possible Causes**:
1. Agent name misspelled (use `claude`, `cursor`, `windsurf`, `copilot`, `aider`, `continue`)
2. Permission issues with agent's config directory
3. Agent config directory doesn't exist

**Solution**:
```bash
# Check agent name
daf skills --help | grep -A 3 "all-agents"

# Check/create directory
ls -la ~/.cursor/skills/
mkdir -p ~/.cursor/skills/

# Try with dry-run first
daf skills --agents cursor --dry-run
```

### Skills Not Found by Agent

**Problem**: Installed skills but agent doesn't see them.

**For Claude Code**:
- Restart the Claude session (`daf open <session>` again)
- Skills are NOT hot-reloaded on `--resume`
- Check `~/.claude/skills/` directory exists and has content

**For Other Agents**:
- Check agent's documentation for context file support
- Verify skills directory is in the expected location
- Agent may need to be restarted

### Wrong Installation Location

**Problem**: Skills installed to wrong directory.

**For Claude Code with Custom Config**:
```bash
# If you use CLAUDE_CONFIG_DIR
echo $CLAUDE_CONFIG_DIR
daf skills --agents claude
# Installs to $CLAUDE_CONFIG_DIR/skills/, not ~/.claude/skills/
```

**For GitHub Copilot with Custom Home**:
```bash
# If you use COPILOT_HOME
echo $COPILOT_HOME
daf skills --agents copilot
# Installs to $COPILOT_HOME/skills/, not ~/.copilot/skills/
```

### Cleaning Up Old Installations

Remove old/unwanted skill installations:

```bash
# Remove from all agents
rm -rf ~/.claude/skills/daf-* \
       ~/.copilot/skills/daf-* \
       ~/.cursor/skills/daf-* \
       ~/.codeium/windsurf/skills/daf-* \
       ~/.aider/skills/daf-* \
       ~/.continue/skills/daf-*

# Then reinstall fresh
daf skills --all-agents
```

## See Also

- [AI Agent Support Matrix](../reference/ai-agent-support-matrix.md) - Detailed agent comparison
- [Commands Reference](../reference/commands.md) - Full `daf skills` documentation
- [Hierarchical Skills](hierarchical-skills.md) - Organization-specific skill management
