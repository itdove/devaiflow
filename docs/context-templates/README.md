# Hierarchical Context Files

DevAIFlow supports hierarchical context files that are automatically loaded when starting Claude Code sessions. These files provide context at different organizational levels.

## Overview

Context files are loaded in this order:

1. **Default files** (from project directory):
   - AGENTS.md (agent-specific instructions)
   - CLAUDE.md (project guidelines and standards)
   - DAF_AGENTS.md (daf tool usage guide)

2. **Backend context** (from DEVAIFLOW_HOME):
   - `backends/JIRA.md` - JIRA-specific integration rules

3. **Organization context** (from DEVAIFLOW_HOME):
   - `ORGANIZATION.md` - Organization-wide coding standards

4. **Team context** (from DEVAIFLOW_HOME):
   - `TEAM.md` - Team-specific conventions and workflows

5. **User context** (from DEVAIFLOW_HOME):
   - `CONFIG.md` - Personal notes and preferences

6. **User-configured files** (from config.json):
   - Files configured via `daf config context add`

7. **Skills** (from workspace):
   - .claude/skills/ (deployed via `daf upgrade`)

**IMPORTANT**: Files are only loaded if they physically exist on disk. Missing files are silently skipped (no errors).

## File Locations

All hierarchical context files are stored in your DEVAIFLOW_HOME directory:

- Default: `~/.daf-sessions/` (or `~/.daf-sessions/` for backward compatibility)
- Custom: Set via `DEVAIFLOW_HOME` environment variable

Directory structure:
```
~/.daf-sessions/
├── backends/
│   └── JIRA.md              # Backend-specific context
├── ORGANIZATION.md          # Organization-level context
├── TEAM.md                  # Team-level context
└── CONFIG.md                # User-level context
```

## Creating Context Files

### 1. Backend Context (backends/JIRA.md)

Backend-specific integration rules. Currently only JIRA backend is supported.

**When to use:**
- JIRA Wiki markup requirements
- Backend-specific formatting rules
- Integration guidelines specific to JIRA

**Example:**
```bash
mkdir -p ~/.daf-sessions/backends
cp docs/context-templates/JIRA.md ~/.daf-sessions/backends/JIRA.md
# Edit to customize for your JIRA instance
```

### 2. Organization Context (ORGANIZATION.md)

Organization-wide coding standards and architecture principles.

**When to use:**
- Coding standards that apply to all projects
- Architecture principles and patterns
- Security and compliance requirements
- Organization-wide git workflows

**Example:**
```bash
cp docs/context-templates/ORGANIZATION.md ~/.daf-sessions/ORGANIZATION.md
# Edit to match your organization's standards
```

### 3. Team Context (TEAM.md)

Team-specific conventions and workflows.

**When to use:**
- Team-specific branch naming conventions
- Code review practices
- Communication channels and schedules
- Team tools and resources

**Example:**
```bash
cp docs/context-templates/TEAM.md ~/.daf-sessions/TEAM.md
# Edit to match your team's practices
```

### 4. User Context (CONFIG.md)

Personal development notes and preferences.

**When to use:**
- Personal reminders and checklists
- Favorite commands and shortcuts
- Project-specific notes
- Learning goals and ideas

**Example:**
```bash
cp docs/context-templates/CONFIG.md ~/.daf-sessions/CONFIG.md
# Edit to add your personal notes
```

## Usage

Context files are automatically loaded when you create or open a session:

```bash
# Create new session
daf new --name "feature-work" --goal "Add caching layer"

# Open JIRA ticket
daf open PROJ-12345
```

Claude will automatically read all existing context files in the hierarchical order listed above.

### Required: Claude Code Permissions

**IMPORTANT**: Claude Code must be configured to allow reading files from `~/.daf-sessions/` and `~/.daf-sessions/` directories. Without this permission, context files cannot be loaded and the tool will fail.

**Quick setup:**

Add to `~/.claude/settings.json`:
```json
{
  "file_access": {
    "read": [
      "~/.daf-sessions/**/*",
      "~/.daf-sessions/**/*"
    ]
  }
}
```

**For detailed instructions**, see [Installation Guide - Configuring Claude Code Permissions](../02-installation.md#configuring-claude-code-permissions).

## Customizing Templates

The templates in this directory are starting points. Customize them to match your:
- Organization's coding standards
- Team's workflows and conventions
- Personal preferences and notes

## Best Practices

### 1. Keep Files Focused
- Backend context: Integration rules only
- Organization context: Standards that apply to all projects
- Team context: Team-specific conventions only
- User context: Personal notes and reminders

### 2. Avoid Duplication
- Don't repeat information already in AGENTS.md or CLAUDE.md
- Reference other files when appropriate
- Use hierarchical levels appropriately (don't put team-specific info in organization file)

### 3. Keep Files Up-to-Date
- Review periodically (quarterly or when standards change)
- Remove outdated information
- Update when team members join or leave

### 4. Use Clear Formatting
- Use headers for organization
- Use bullet points for lists
- Use code blocks for examples
- Keep content concise

## Conditional Loading

Files are only loaded if they exist. This means:
- ✅ You can create only the files you need
- ✅ Missing files are silently skipped
- ✅ No errors if files don't exist
- ✅ Gradual adoption - start with one file, add more later

Examples:
```bash
# Only backend context
mkdir -p ~/.daf-sessions/backends
echo "# JIRA Rules" > ~/.daf-sessions/backends/JIRA.md

# Only user context
echo "# My Notes" > ~/.daf-sessions/CONFIG.md

# All levels
mkdir -p ~/.daf-sessions/backends
cp docs/context-templates/*.md ~/.daf-sessions/
# Edit each file as needed
```

## Migration Path

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

## Troubleshooting

### Files Not Being Loaded

Check that:
1. File exists in correct location: `ls -la ~/.daf-sessions/`
2. File has correct name (case-sensitive): `ORGANIZATION.md`, not `organization.md`
3. File is readable: `cat ~/.daf-sessions/ORGANIZATION.md`
4. Path is correct (check DEVAIFLOW_HOME if custom)

### Verify Loading

Check the initial prompt when opening a session to see which files are listed.

### Testing

Create test files to verify loading:
```bash
mkdir -p ~/.daf-sessions/backends
echo "# Test JIRA" > ~/.daf-sessions/backends/JIRA.md
echo "# Test Org" > ~/.daf-sessions/ORGANIZATION.md
echo "# Test Team" > ~/.daf-sessions/TEAM.md
echo "# Test User" > ~/.daf-sessions/CONFIG.md

# Create session and check initial prompt
daf new --name test-context --goal "Test context loading"
```

## See Also

- Configuration guide: `docs/06-configuration.md`
- User-configured context: `daf config context --help`
- AGENTS.md: Project-specific agent instructions
- CLAUDE.md: Project guidelines and standards
- DAF_AGENTS.md: DevAIFlow tool usage guide
