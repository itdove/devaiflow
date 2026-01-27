# Hierarchical Skills Architecture

DevAIFlow supports a hierarchical skills system that allows organizations to distribute AI agent instructions across multiple levels: **Enterprise**, **Organization**, **Team**, and **User**.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [How It Works](#how-it-works)
4. [Setup Guide](#setup-guide)
5. [Creating Skills](#creating-skills)
6. [Directory Structure](#directory-structure)
7. [Usage Examples](#usage-examples)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### What Are Hierarchical Skills?

Hierarchical skills are organization-specific AI agent instructions that are:
- **Automatically distributed** from a central source to all users
- **Automatically loaded** when users run `daf open` to start sessions
- **Numbered for guaranteed load order**: 01-enterprise → 02-organization → 03-team → 04-user

### Why Use Hierarchical Skills?

**Benefits:**
- **Centralized Management**: Update organization policies in one place
- **Automatic Distribution**: All users get updates via `daf upgrade`
- **Guaranteed Order**: Skills load in priority order (enterprise overrides all)
- **Separation of Concerns**: Policy (config files) vs. Instructions (skills)
- **Version Control**: Store skills in Git for change tracking

**Use Cases:**
- Enterprise-wide coding standards and workflows
- Organization-specific JIRA templates and field requirements
- Team conventions and documentation standards
- User-specific preferences and shortcuts

---

## Architecture

### Two-Level System

The hierarchical skills system has **two levels**:

1. **Config Files** (`.md` files) - Store POLICY and WHAT/WHY
   - `ENTERPRISE.md` - Company-wide policies
   - `ORGANIZATION.md` - Project-specific policies
   - `TEAM.md` - Team conventions
   - `USER.md` - User preferences

2. **Skills** (`SKILL.md` files) - Store EXECUTABLE INSTRUCTIONS and HOW
   - `01-enterprise/SKILL.md` - Enterprise skill instructions
   - `02-organization/SKILL.md` - Organization skill instructions
   - `03-team/SKILL.md` - Team skill instructions
   - `04-user/SKILL.md` - User skill instructions

### Configuration Hierarchy

Settings and skills follow this priority order:

```
┌─────────────────────────────────────────┐
│  1. Enterprise (highest priority)       │  ← Company-wide enforcement
│     ~/.daf-sessions/ENTERPRISE.md       │
│     ~/.daf-sessions/.claude/skills/     │
│       01-enterprise/SKILL.md            │
├─────────────────────────────────────────┤
│  2. Organization                        │  ← Project-specific settings
│     ~/.daf-sessions/ORGANIZATION.md     │
│     ~/.daf-sessions/.claude/skills/     │
│       02-organization/SKILL.md          │
├─────────────────────────────────────────┤
│  3. Team                                │  ← Team conventions
│     ~/.daf-sessions/TEAM.md             │
│     ~/.daf-sessions/.claude/skills/     │
│       03-team/SKILL.md                  │
├─────────────────────────────────────────┤
│  4. User (lowest priority)              │  ← Personal preferences
│     ~/.daf-sessions/USER.md             │
│     ~/.daf-sessions/.claude/skills/     │
│       04-user/SKILL.md                  │
└─────────────────────────────────────────┘
```

### Skill Discovery Order

When Claude Code starts, skills are loaded in this order:

1. **User-level skills** (`~/.claude/skills/`) - Personal skills
2. **Hierarchical skills** (`$DEVAIFLOW_HOME/.claude/skills/01-*`, `02-*`, etc.) - Organization skills
3. **Workspace skills** (`workspace/.claude/skills/`) - Workspace-specific
4. **Project skills** (`project/.claude/skills/`) - Project-specific

---

## How It Works

### Installation Workflow

When you run `daf upgrade`, DevAIFlow:

1. **Reads** `organization.json` to find `hierarchical_config_source`
2. **Downloads** config files (.md) from the source location
3. **Extracts** `skill_url` from each config file's frontmatter
4. **Downloads** skill content from the `skill_url`
5. **Installs** skills to `$DEVAIFLOW_HOME/.claude/skills/XX-level/`
6. **Saves** config files to `$DEVAIFLOW_HOME/`

```
organization.json
  └─ hierarchical_config_source: "file:///path/to/configs"
       ↓
  Downloads ENTERPRISE.md from source
       ↓
  Reads frontmatter: skill_url: ../daf-skills/enterprise
       ↓
  Resolves relative path from SOURCE location
       ↓
  Downloads SKILL.md from /path/to/daf-skills/enterprise/
       ↓
  Installs to ~/.daf-sessions/.claude/skills/01-enterprise/SKILL.md
       ↓
  Saves ENTERPRISE.md to ~/.daf-sessions/ENTERPRISE.md
```

### Relative Path Resolution

**Key Feature**: Skills can use relative paths in config files:

```yaml
---
skill_url: ../daf-skills/enterprise
---
```

**Relative paths are resolved from the SOURCE location**, not the installed location. This ensures portability - the same config files work for all users regardless of their local file system structure.

**Example:**
- Source: `/company/shared/configs/ENTERPRISE.md`
- skill_url: `../daf-skills/enterprise`
- Resolves to: `/company/shared/daf-skills/enterprise/SKILL.md`
- Installs to: `~/.daf-sessions/.claude/skills/01-enterprise/SKILL.md`

---

## Setup Guide

### For Organization Administrators

#### 1. Create Directory Structure

```bash
# Create organization repository
mkdir -p my-org-devaiflow/{configs,daf-skills/{enterprise,organization,team,user}}

cd my-org-devaiflow
```

#### 2. Create Config Files

Create each config file with frontmatter pointing to its skill:

**`configs/ENTERPRISE.md`:**
```yaml
---
skill_url: ../daf-skills/enterprise
---

# Enterprise Guidelines

This document contains enterprise-wide policies...

## AI Agent Backend

All employees must use Claude for AI assistance...
```

**`configs/ORGANIZATION.md`:**
```yaml
---
skill_url: ../daf-skills/organization
---

# Organization Guidelines

This document contains organization-specific policies...

## JIRA Templates

All JIRA tickets must follow these templates...
```

**`configs/TEAM.md`:**
```yaml
---
skill_url: ../daf-skills/team
---

# Team Conventions

## Code Review Standards
...
```

**`configs/USER.md`:**
```yaml
---
skill_url: ../daf-skills/user
---

# User Preferences

## Workspace Configuration
...
```

#### 3. Create Skills

Create skill files with executable instructions for the AI agent:

**`daf-skills/enterprise/SKILL.md`:**
```markdown
# Enterprise Skill

## Field Discovery

When working with JIRA, use these commands to discover available fields:

\`\`\`bash
# List all custom fields
daf config show-fields

# View field configuration
daf config show-fields --json
\`\`\`

## Required Workflow

1. Always run tests before committing
2. Follow enterprise coding standards
3. Use approved AI backend (Claude)
```

**`daf-skills/organization/SKILL.md`:**
```markdown
# Organization Skill

## JIRA Workflow

### Creating Tickets

When creating JIRA tickets, follow this workflow:

1. Read the ticket templates from ORGANIZATION.md
2. Use the appropriate template based on issue type
3. Ensure all required fields are filled

### Acceptance Criteria

**CRITICAL**: Always verify acceptance criteria:

\`\`\`bash
# At session start
daf jira view AAP-12345

# At session end
daf jira update --field acceptance_criteria "$(cat <<'EOF'
- [x] Requirement 1 completed
- [x] Requirement 2 completed
EOF
)"
\`\`\`
```

#### 4. Configure Distribution Source

**Option A: File System** (for shared network drives):
```bash
# Store in shared location
cp -r my-org-devaiflow /company/shared/

# Users configure organization.json
{
  "hierarchical_config_source": "file:///company/shared/my-org-devaiflow/configs"
}
```

**Option B: Git Repository** (recommended):
```bash
# Initialize Git repository
cd my-org-devaiflow
git init
git add .
git commit -m "Initial hierarchical skills"

# Push to company Git server
git remote add origin https://github.com/company/devaiflow-config
git push -u origin main

# Users configure organization.json
{
  "hierarchical_config_source": "https://github.com/company/devaiflow-config/configs"
}
```

**Option C: HTTP Server**:
```bash
# Serve via HTTP
cd my-org-devaiflow
python3 -m http.server 8080

# Users configure organization.json
{
  "hierarchical_config_source": "http://company-server:8080/configs"
}
```

### For End Users

#### 1. Configure Organization Settings

**Option A: During Initial Setup** (Recommended)

When running `daf init` for the first time, you'll be prompted for the hierarchical config source:

```bash
daf init

# ... JIRA configuration prompts ...
# ... Repository configuration prompts ...

=== Hierarchical Configuration ===

Optional: URL to organization-wide config files (ENTERPRISE.md, ORGANIZATION.md, etc.)
This enables automatic distribution of organization policies and AI agent skills.
After setting this, run 'daf upgrade' to download config files and skills.

Examples:
  - file:///company/shared/devaiflow/configs
  - https://github.com/company/devaiflow-config/configs

Configure hierarchical config source now? (y/N): y
Hierarchical config source URL: file:///company/shared/my-org-devaiflow/configs
```

**Option B: Manual Configuration**

Edit `~/.daf-sessions/organization.json`:

```json
{
  "jira_project": "AAP",
  "hierarchical_config_source": "file:///company/shared/my-org-devaiflow/configs"
}
```

**Option C: Using the TUI**

```bash
daf config tui --advanced
# Navigate to Organization tab
# Set "Hierarchical Config Source" field
```

#### 2. Install Skills

```bash
# Install all hierarchical skills
daf upgrade

# Verify installation
ls ~/.daf-sessions/.claude/skills/
# Should see: 01-enterprise/ 02-organization/ 03-team/ 04-user/
```

#### 3. Verify Skills Are Loaded

```bash
# Start a new session
daf open

# Inside Claude Code session, the AI agent will automatically
# have access to all hierarchical skills
```

---

## Creating Skills

### Config File Structure

Config files use **YAML frontmatter** to specify the skill location:

```markdown
---
skill_url: ../daf-skills/enterprise
---

# Document Title

## Policy Section

Policy content here...
```

**Frontmatter Fields:**
- `skill_url` - URL or path to the skill directory containing `SKILL.md`

**Supported URL Types:**
- **Relative paths**: `../daf-skills/enterprise` (recommended for portability)
- **File URLs**: `file:///absolute/path/to/daf-skills/enterprise`
- **HTTP URLs**: `https://github.com/company/repo/daf-skills/enterprise`
- **GitHub URLs**: Auto-converted to raw.githubusercontent.com
- **GitLab URLs**: Auto-converted to /-/raw/ format

### Skill File Structure

Skills are stored in `SKILL.md` files with Markdown formatting:

```markdown
# Skill Name

Brief description of what this skill provides.

## Section 1

Instructions for the AI agent...

### Workflow

1. Step 1
2. Step 2
3. Step 3

## Section 2

More instructions...

\`\`\`bash
# Example commands
daf jira create --type Story
\`\`\`
```

### Best Practices for Skills

**DO:**
- ✅ Provide executable instructions (HOW)
- ✅ Include example commands
- ✅ Reference config files for policy details (WHAT/WHY)
- ✅ Keep skills focused and specific
- ✅ Use code blocks for commands
- ✅ Document workflows step-by-step

**DON'T:**
- ❌ Duplicate field information from config files
- ❌ Mix policy (WHAT) with instructions (HOW)
- ❌ Include organization-specific names in examples
- ❌ Hard-code values that change frequently
- ❌ Create overly long skills (split into sections)

### Example: Referencing Config Instead of Duplicating

**Bad** (duplicates field information):
```markdown
## Custom Fields

Available fields:
- affected_version (customfield_12345)
- story_points (customfield_67890)
- sprint (customfield_11111)
```

**Good** (references config):
```markdown
## Custom Fields

To discover available custom fields, use:

\`\`\`bash
# List all fields
daf config show-fields

# View field mappings
cat ~/.daf-sessions/backends/jira.json
\`\`\`

See ENTERPRISE.md for field requirement policies.
```

---

## Directory Structure

### Organization Repository Layout

```
my-org-devaiflow/
├── configs/
│   ├── ENTERPRISE.md          # Enterprise policy
│   ├── ORGANIZATION.md        # Organization policy
│   ├── TEAM.md                # Team conventions
│   └── USER.md                # User preferences template
├── daf-skills/
│   ├── enterprise/
│   │   └── SKILL.md           # Enterprise skill instructions
│   ├── organization/
│   │   └── SKILL.md           # Organization skill instructions
│   ├── team/
│   │   └── SKILL.md           # Team skill instructions
│   └── user/
│       └── SKILL.md           # User skill instructions
└── README.md                  # Setup documentation
```

### User Installation Layout

After running `daf upgrade`, users will have:

```
~/.daf-sessions/
├── ENTERPRISE.md              # Downloaded from source
├── ORGANIZATION.md            # Downloaded from source
├── TEAM.md                    # Downloaded from source
├── USER.md                    # Downloaded from source
├── organization.json          # User's config with hierarchical_config_source
└── .claude/
    └── skills/
        ├── 01-enterprise/
        │   └── SKILL.md       # Downloaded from source
        ├── 02-organization/
        │   └── SKILL.md       # Downloaded from source
        ├── 03-team/
        │   └── SKILL.md       # Downloaded from source
        └── 04-user/
            └── SKILL.md       # Downloaded from source
```

---

## Usage Examples

### Example 1: File System Source

**Setup:**
```bash
# Admin: Create skills in shared location
mkdir -p /company/shared/devaiflow/{configs,daf-skills/enterprise}

cat > /company/shared/devaiflow/configs/ENTERPRISE.md <<'EOF'
---
skill_url: ../daf-skills/enterprise
---

# Enterprise Standards

All code must follow company coding standards.
EOF

cat > /company/shared/devaiflow/daf-skills/enterprise/SKILL.md <<'EOF'
# Enterprise Skill

## Coding Standards

Before committing, run:
\`\`\`bash
black .
flake8 .
pytest
\`\`\`
EOF
```

**User Configuration:**
```json
{
  "hierarchical_config_source": "file:///company/shared/devaiflow/configs"
}
```

**User Installation:**
```bash
daf upgrade
# ✓ Downloaded ENTERPRISE.md to: ~/.daf-sessions/ENTERPRISE.md
# ✓ Installed enterprise skill to: ~/.daf-sessions/.claude/skills/01-enterprise
```

### Example 2: GitHub Repository Source

**Setup:**
```bash
# Admin: Create GitHub repository
mkdir devaiflow-config
cd devaiflow-config

mkdir -p configs daf-skills/organization

cat > configs/ORGANIZATION.md <<'EOF'
---
skill_url: ../daf-skills/organization
---

# Organization Guidelines

All JIRA tickets must have acceptance criteria.
EOF

cat > daf-skills/organization/SKILL.md <<'EOF'
# Organization Skill

## JIRA Workflow

\`\`\`bash
# Create ticket with acceptance criteria
daf jira create --type Story --field acceptance_criteria "$(cat <<'EOC'
- [] Feature implemented
- [] Tests passing
- [] Documentation updated
EOC
)"
\`\`\`
EOF

git init
git add .
git commit -m "Initial config"
git remote add origin https://github.com/company/devaiflow-config
git push -u origin main
```

**User Configuration:**
```json
{
  "hierarchical_config_source": "https://github.com/company/devaiflow-config/configs"
}
```

**User Installation:**
```bash
daf upgrade
# Downloads from GitHub raw URLs automatically
```

### Example 3: Custom Field Discovery

**ENTERPRISE.md** (Policy):
```markdown
---
skill_url: ../daf-skills/enterprise
---

# Enterprise Configuration

## Custom Fields

Your JIRA instance has custom fields configured.
See the enterprise skill for how to discover available fields.
```

**enterprise/SKILL.md** (Instructions):
```markdown
# Enterprise Skill

## Discovering Custom Fields

\`\`\`bash
# List all custom fields discovered from JIRA
daf config show-fields

# View JSON format
daf config show-fields --json

# Check field mappings
cat ~/.daf-sessions/backends/jira.json | jq '.field_mappings'
\`\`\`
```

### Example 4: Team Conventions

**TEAM.md** (Policy):
```markdown
---
skill_url: ../daf-skills/team
---

# Team Conventions

## Documentation Standards

- Use generic examples only
- Never use organization-specific names
- Follow team code review process
```

**team/SKILL.md** (Instructions):
```markdown
# Team Skill

## Writing Documentation

When writing documentation:

1. Use generic examples:
   - ✅ "my-project", "product-a"
   - ❌ "ansible", "company-internal-name"

2. Before committing documentation:
\`\`\`bash
# Search for organization-specific names
grep -r "ansible" docs/
grep -r "company-name" docs/

# Replace with generic names
sed -i 's/ansible/my-project/g' docs/example.md
\`\`\`
```

---

## Best Practices

### For Administrators

1. **Use Version Control**
   - Store all config files and skills in Git
   - Tag releases for version tracking
   - Use pull requests for changes

2. **Separate Policy from Instructions**
   - Config files (.md) → WHAT and WHY
   - Skills (SKILL.md) → HOW
   - Reference config files from skills, don't duplicate

3. **Use Relative Paths**
   - More portable than absolute paths
   - Works across different file systems
   - Example: `skill_url: ../daf-skills/enterprise`

4. **Test Before Distribution**
   ```bash
   # Test installation locally
   daf upgrade --dry-run

   # Verify skills load correctly
   daf open
   ```

5. **Document Changes**
   - Maintain CHANGELOG.md
   - Notify users of breaking changes
   - Provide migration guides

6. **Validate Regularly**
   ```bash
   # Check for broken skill URLs
   daf upgrade --dry-run

   # Verify all config files are valid
   daf config validate
   ```

### For Users

1. **Keep Skills Updated**
   ```bash
   # Update weekly or when notified
   daf upgrade
   ```

2. **Verify Installation**
   ```bash
   # Check installed skills
   ls ~/.daf-sessions/.claude/skills/

   # Read skill content
   cat ~/.daf-sessions/.claude/skills/01-enterprise/SKILL.md
   ```

3. **Report Issues**
   - If skills fail to install, contact your admin
   - Provide error messages from `daf upgrade`

4. **Customize User Skills**
   - Add personal skills to `~/.claude/skills/`
   - These load before hierarchical skills
   - Don't modify installed hierarchical skills (they'll be overwritten)

---

## Troubleshooting

### Skills Not Installing

**Problem**: `daf upgrade` shows "Failed to install enterprise skill"

**Solution**:
```bash
# Check hierarchical_config_source is set
cat ~/.daf-sessions/organization.json | grep hierarchical_config_source

# Verify source is accessible
ls /path/to/configs/  # For file:// URLs
curl https://github.com/company/repo/configs/ENTERPRISE.md  # For HTTP URLs

# Check dry-run output
daf upgrade --dry-run
```

### Skills Not Loading in Session

**Problem**: Claude Code doesn't seem to have hierarchical skills

**Solution**:
```bash
# Verify skills are installed
ls ~/.daf-sessions/.claude/skills/

# Check SKILL.md files exist
cat ~/.daf-sessions/.claude/skills/01-enterprise/SKILL.md

# Restart Claude Code
daf open
```

### Relative Paths Not Resolving

**Problem**: "Skill file not found: /Users/username/daf-skills/enterprise/SKILL.md"

**Cause**: Relative paths are being resolved from `~/.daf-sessions/` instead of source location

**Solution**:
- Ensure `hierarchical_config_source` is set in organization.json
- Relative paths only work when downloading from a source
- If no source is configured, skills must use absolute paths

**Workaround** (if source not available):
```markdown
---
skill_url: file:///company/shared/devaiflow/daf-skills/enterprise
---
```

### Config Files Out of Sync

**Problem**: Config files in `~/.daf-sessions/` are outdated

**Solution**:
```bash
# Re-download all config files
daf upgrade

# Or manually update
cp /company/shared/devaiflow/configs/*.md ~/.daf-sessions/
```

### Checking Installed Versions

```bash
# View installed config files
ls -la ~/.daf-sessions/{ENTERPRISE,ORGANIZATION,TEAM,USER}.md

# View installed skills
ls -la ~/.daf-sessions/.claude/skills/*/SKILL.md

# Compare with source
diff ~/.daf-sessions/ENTERPRISE.md /company/shared/devaiflow/configs/ENTERPRISE.md
```

### Debugging Installation

Enable debug output to see what's happening:

```bash
# Run with verbose output
daf upgrade --dry-run

# Check the logs
# Look for messages like:
# - "Downloading hierarchical config files from: ..."
# - "Installing enterprise skill from: ..."
# - "✓ Installed enterprise skill to: ..."
```

---

## Advanced Topics

### Remote HTTP Sources

When using HTTP/HTTPS sources, DevAIFlow automatically handles:

**GitHub URLs:**
```
Input:  https://github.com/company/repo/configs
Converts to: https://raw.githubusercontent.com/company/repo/main/configs/ENTERPRISE.md
```

**GitLab URLs:**
```
Input:  https://gitlab.com/company/repo/configs
Converts to: https://gitlab.com/company/repo/-/raw/main/configs/ENTERPRISE.md
```

**Generic HTTP:**
```
Input:  https://company.com/devaiflow/configs
Fetches: https://company.com/devaiflow/configs/ENTERPRISE.md
```

### Skill Update Workflow

**Administrators:**
1. Update skills in source repository
2. Commit and push changes
3. Notify users to run `daf upgrade`
4. (Optional) Tag release: `git tag v1.2.0`

**Automatic Updates (future):**
- Could add `daf upgrade --auto` to crontab
- Check for updates daily
- Notify on changes

### Security Considerations

**File System Sources:**
- Use appropriate file permissions on shared drives
- Restrict write access to administrators only
- Consider read-only mounts for users

**HTTP Sources:**
- Use HTTPS for remote sources
- Consider private GitHub repositories
- Use authentication tokens if needed

**Validation:**
- Skills can execute arbitrary instructions
- Review skills before distribution
- Test in sandbox environment first

---

## Summary

**Key Points:**

1. **Two-Level Architecture**: Config files (.md) contain policy, Skills (SKILL.md) contain instructions
2. **Automatic Distribution**: `daf upgrade` downloads both config and skills from central source
3. **Numbered Loading**: 01-enterprise → 02-organization → 03-team → 04-user
4. **Relative Paths**: Resolved from source location, not installed location
5. **Separation of Concerns**: Don't duplicate - reference config files from skills

**Quick Start for Admins:**
```bash
# 1. Create structure
mkdir -p my-org/{configs,daf-skills/enterprise}

# 2. Create config with frontmatter
echo "---\nskill_url: ../daf-skills/enterprise\n---\n# Policy" > my-org/configs/ENTERPRISE.md

# 3. Create skill
echo "# Instructions\nHow to..." > my-org/daf-skills/enterprise/SKILL.md

# 4. Distribute (share path or push to Git)
```

**Quick Start for Users:**
```bash
# 1. Configure source
daf config tui  # Set hierarchical_config_source

# 2. Install skills
daf upgrade

# 3. Verify
ls ~/.daf-sessions/.claude/skills/
```

**Next Steps:**
- See [Configuration Reference](06-configuration.md) for all config options
- See [Commands Reference](07-commands.md) for `daf upgrade` details
- See example repositories for complete implementations
