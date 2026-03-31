# Skills Management Guide

This guide explains how DevAIFlow discovers and loads skills from multiple locations, how precedence rules work, and best practices for organizing your skills.

## Overview

DevAIFlow automatically discovers skills from four hierarchical locations, allowing you to organize skills by scope (user-level, workspace-specific, organization-specific, or project-specific). Skills are loaded in a specific order to ensure that organization-specific skills can extend generic ones.

## Skills Discovery: The 4-Level Hierarchy

Skills are discovered and loaded in this order:

### 1. User-Level Skills (`~/.claude/skills/`)

**Purpose:** Generic, reusable skills available across all projects.

**Location:** `~/.claude/skills/` (or `$CLAUDE_CONFIG_DIR/skills/`)

**Examples:**
- `daf-cli` - DevAIFlow CLI commands
- `git-cli` - Git command reference
- `gh-cli` - GitHub CLI reference
- `glab-cli` - GitLab CLI reference

**When to use:**
- Skills that apply to all projects
- Tool documentation (git, gh, glab, daf)
- Generic workflows

### 2. Workspace-Level Skills (`<workspace>/.claude/skills/`)

**Purpose:** Workspace-specific tool configurations and workflows.

**Location:** `<workspace>/.claude/skills/`

**Examples:**
- Custom tool configurations for this workspace
- Workspace-specific workflows
- Team collaboration patterns

**When to use:**
- Skills specific to a workspace (group of related projects)
- Team-level tool configurations
- Shared workflows across projects in the workspace

### 3. Hierarchical Skills (`$DEVAIFLOW_HOME/.claude/skills/`)

**Purpose:** Organization-specific skills that **extend** generic skills.

**Location:** `$DEVAIFLOW_HOME/.claude/skills/`

**Naming convention:** Numbered directories (01-enterprise, 02-organization, etc.)

**Examples:**
- `01-enterprise` - Red Hat Enterprise custom fields
- `02-organization` - Red Hat Organization JIRA templates
- `03-team` - Team-specific defaults
- `04-user` - Personal preferences

**When to use:**
- Organization-specific extensions to generic skills
- Company policies and standards
- JIRA field mappings and defaults

**Why numbered?** Ensures load order within the hierarchical level (01 loads before 02, etc.)

### 4. Project-Level Skills (`<project>/.claude/skills/`)

**Purpose:** Project-specific skills and configurations.

**Location:** `<project>/.claude/skills/`

**Examples:**
- Project-specific workflows
- Custom commands for this project
- Project documentation and patterns

**When to use:**
- Skills unique to this project
- Project-specific tooling
- Local development workflows

## Precedence Rules

When the same skill exists at multiple levels, **later-loaded skills override earlier ones**:

```
Project > Hierarchical > Workspace > User
```

### Why This Order?

1. **Generic skills first:** User and workspace skills provide base functionality
2. **Organization extensions second:** Hierarchical skills extend generic skills with company-specific details
3. **Project-specific last:** Project skills can override everything for project-specific needs

### Example: Skill Extension

**User-level skill** (`~/.claude/skills/daf-cli/SKILL.md`):
```markdown
---
name: daf-cli
description: Generic daf CLI commands
---

# DAF CLI Commands

Generic documentation for daf commands...
```

**Hierarchical skill** (`$DEVAIFLOW_HOME/.claude/skills/01-enterprise/SKILL.md`):
```markdown
---
name: 01-enterprise
description: Red Hat Enterprise daf workflows
---

# Red Hat Enterprise DAF Skill

**Extends:** daf-cli

Red Hat-specific JIRA field mappings and workflows...
```

The hierarchical skill **extends** the generic skill, providing organization-specific context.

## Loading Order Table

| Level | Location | Load Order | Precedence | Purpose |
|-------|----------|------------|------------|---------|
| User | `~/.claude/skills/` | 1st (earliest) | Lowest | Generic skills |
| Workspace | `<workspace>/.claude/skills/` | 2nd | Low | Workspace tools |
| Hierarchical | `$DEVAIFLOW_HOME/.claude/skills/` | 3rd | High | Org extensions |
| Project | `<project>/.claude/skills/` | 4th (latest) | Highest | Project-specific |

## Duplicate Prevention

### Single-Project Sessions

When you run `daf open` for a single project:
- Claude Code launches with `cwd = project_path`
- Claude **auto-loads** `<cwd>/.claude/skills/` (the project-level skills)
- DevAIFlow **filters out** project-level skills from `--add-dir` to prevent duplicates

**Result:** Each skill directory is loaded exactly once.

### Multi-Project Sessions

When working across multiple repositories:
- Claude Code launches with `cwd = workspace_path`
- Claude auto-loads `<workspace>/.claude/skills/` (workspace-level skills)
- DevAIFlow adds `--add-dir` for all project-level skills
- Each project's skills are loaded once via `--add-dir`

**Result:** No duplicates, all project skills loaded correctly.

## Best Practices

### 1. Use Unique Skill Names Per Level

**Good practice:**
```
~/.claude/skills/daf-cli/           # Generic daf commands
$DEVAIFLOW_HOME/.claude/skills/
    01-enterprise/                  # Extends daf-cli (Red Hat specific)
    02-organization/                # Extends 01-enterprise
```

**Why:** Unique names make it clear which skill provides which functionality.

### 2. Generic Skills in User-Level

Place tool documentation and reusable skills in `~/.claude/skills/`:
- `daf-cli` - Available everywhere
- `git-cli` - Available everywhere
- `gh-cli` - Available everywhere

### 3. Organization Extensions in Hierarchical

Place company-specific extensions in `$DEVAIFLOW_HOME/.claude/skills/`:
- Use numbered prefixes (01-, 02-, etc.) to control load order
- Reference the skill they extend in frontmatter (`Extends: daf-cli`)

### 4. Project-Specific Skills in Project Directory

Only place truly project-specific skills in `<project>/.claude/skills/`:
- Project-specific workflows
- Custom tooling for this project only

### 5. Don't Duplicate Generic Content

**Avoid:**
```
# DON'T copy entire daf-cli documentation to project/.claude/skills/
project/.claude/skills/daf-cli/SKILL.md  # Duplicate!
```

**Instead:**
```
# DO reference or extend generic skills
~/.claude/skills/daf-cli/SKILL.md        # Generic (source of truth)
project/.claude/skills/project-workflow/SKILL.md  # Project-specific extension
```

## Working Directory Independence

**Important:** You don't need to worry about your current working directory when running daf commands.

DevAIFlow handles skills discovery automatically based on:
1. Your project path (where the code is)
2. Your workspace path (configured in config.json)
3. Your DEVAIFLOW_HOME (hierarchical skills location)

**Example:**
```bash
# Works from any directory:
cd /tmp
daf open PROJ-12345  # DevAIFlow discovers skills correctly

# Also works:
cd ~/development/my-project
daf open PROJ-12345  # Same skill discovery
```

## Optional: CLAUDE_CONFIG_DIR Simplification

### Problem

By default, skills are discovered from multiple locations:
- `~/.claude/skills/` (Claude Code default)
- `$DEVAIFLOW_HOME/.claude/skills/` (DevAIFlow hierarchical)
- `<workspace>/.claude/skills/` (workspace-specific)
- `<project>/.claude/skills/` (project-specific)

This can be confusing if you want a single source of truth.

### Solution: Set CLAUDE_CONFIG_DIR

Set `CLAUDE_CONFIG_DIR` to point to your DevAIFlow home:

```bash
export CLAUDE_CONFIG_DIR=~/.daf-sessions
```

**Result:**
- User-level skills: `~/.daf-sessions/skills/` (instead of `~/.claude/skills/`)
- Hierarchical skills: `~/.daf-sessions/.claude/skills/` (organization extensions)
- All skills in one location!

### When to Use This

**Use CLAUDE_CONFIG_DIR if:**
- You want a single source of truth for skills
- You're managing organization-wide skills
- You want to simplify skills management

**Don't use CLAUDE_CONFIG_DIR if:**
- You have personal skills separate from work skills
- You want to keep Claude Code and DevAIFlow skills separate
- You use multiple skill management strategies

## Skills Installation

### Installing Bundled Skills

DevAIFlow bundles generic skills that can be installed globally:

```bash
# Install to user-level (~/.claude/skills/)
daf skills

# Install to project-level (<project>/.claude/skills/)
daf skills --project-path /path/to/project

# Preview what would be installed
daf skills --dry-run
```

### Installing Hierarchical Skills

Organization-specific skills are installed via `daf upgrade`:

```bash
# Download and install hierarchical skills from configured source
daf upgrade

# Dry-run to preview changes
daf upgrade --dry-run
```

**Configuration:**
Set `hierarchical_config_source` in `config.json`:
```json
{
  "repos": {
    "hierarchical_config_source": "https://github.com/org/devflow-config"
  }
}
```

## Troubleshooting

### Skills Not Loading

**Problem:** Skills don't appear in Claude Code session.

**Solutions:**
1. Check skill file exists: `ls ~/.claude/skills/daf-cli/SKILL.md`
2. Verify skill has correct frontmatter (YAML header with description)
3. Check CLAUDE_CONFIG_DIR if set: `echo $CLAUDE_CONFIG_DIR`
4. Re-install skills: `daf skills --force`

### Duplicate Skills Warning

**Problem:** Claude Code loads the same skill twice.

**Expected behavior:** DevAIFlow automatically prevents duplicates for project-level skills in single-project sessions.

**Check:**
1. Verify you're using DevAIFlow >= 3.0 (includes duplicate prevention)
2. If you see duplicates in multi-project sessions, this is expected and intentional

### Skills Override Not Working

**Problem:** Hierarchical skill doesn't override user-level skill.

**Check precedence:**
1. Verify hierarchical skill is loaded **after** user-level skill
2. Check skill names match (or hierarchical skill references the user-level skill)
3. Hierarchical skills extend, not replace - both skills are loaded

## Summary

**Key takeaways:**
1. Skills are discovered from 4 levels: User → Workspace → Hierarchical → Project
2. Precedence: Project > Hierarchical > Workspace > User
3. Use unique skill names per level for clarity
4. Organization skills (hierarchical) extend generic skills
5. DevAIFlow prevents duplicate loading automatically
6. Working directory doesn't matter - DevAIFlow handles discovery
7. Optional: Use `CLAUDE_CONFIG_DIR` for single source of truth

**Best practice:**
- Generic skills: `~/.claude/skills/`
- Organization extensions: `$DEVAIFLOW_HOME/.claude/skills/` (numbered)
- Project-specific: `<project>/.claude/skills/`
