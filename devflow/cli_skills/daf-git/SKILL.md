---
name: daf-git
description: Manage GitHub/GitLab issues and sessions
---

Complete workflow for managing GitHub Issues and GitLab Issues in DevAIFlow.
Automatically detects the platform from your git repository.

## Quick Start

**Create issue and start working (recommended):**
```bash
daf git new enhancement --goal "Add caching layer"
```
Creates the issue AND opens a session in one command (in mock mode or with Claude Code).

**Note:** Type is a positional argument (matches `daf jira new` syntax for consistency).

**Work on existing issue:**
```bash
daf git open 123
```
Opens a session for an existing issue (creates session if needed).

**View issue details:**
```bash
daf git view
daf git view 123
daf git view owner/repo#123 --comments
```
Auto-detects current session or accepts explicit issue key.

## All Commands

### daf git new
Create a GitHub/GitLab issue with an analysis-only session.

**Syntax:** `daf git new [TYPE] --goal "..."`

TYPE is an optional positional argument (matches `daf jira new` syntax for consistency).

```bash
# Create issue with type (recommended workflow)
daf git new enhancement --goal "Add authentication"

# Create bug report
daf git new bug --goal "Fix login crash"

# Create task
daf git new task --goal "Update dependencies"

# Create spike (research/investigation)
daf git new spike --goal "Research caching options"

# Create epic
daf git new epic --goal "User authentication system"

# Without type (no type label added)
daf git new --goal "General investigation work"

# With custom name and branch
daf git new enhancement --goal "API refactor" --name "api-work" --branch "feature/api"

# With parent issue
daf git new task --goal "Implement auth" --parent "#123"
daf git new enhancement --goal "Add caching" --parent "owner/repo#456"
```

**Standard Agile Issue Types:**
- **bug** - Defect or error in existing functionality
- **enhancement** - Improvement to existing functionality (GitHub convention)
- **task** - Technical work without direct user-facing value
- **spike** - Time-boxed research or investigation
- **epic** - Large body of work spanning multiple iterations
- **story** - User story delivering end-user value

**Configurable Types:**
Valid issue types are configured in `enterprise.json` or `organization.json`:

```json
{
  "github_issue_types": ["bug", "enhancement", "task", "spike", "epic", "story"]
}
```

**Default types** (if not configured): `["bug", "enhancement", "task", "spike", "epic"]`

**What it does:**
- Creates a GitHub/GitLab issue with the goal as title
- Uses templates based on issue type (if configured)
- Adds type label to the issue (if type provided)
- Automatically renames session to `creation-{number}` (e.g., `creation-123`)
- Sets up session metadata (issue_key, type, status)
- In mock mode: Creates mock issue immediately
- In production: Opens Claude Code to create the issue interactively

### daf git open
Open or create a session for an existing GitHub/GitLab issue.

```bash
# Open session for issue (auto-detects repository)
daf git open 123
daf git open "#123"
daf git open owner/repo#123

# Validates issue exists before creating session
```

**What it does:**
- Validates the issue exists on GitHub/GitLab
- Creates session named like `owner-repo-123`
- Opens Claude Code with issue context
- If session already exists, reopens it

### daf git create
Create a new GitHub/GitLab issue (standalone, without session).

**Syntax:** `daf git create [TYPE] --summary "..."`

TYPE is an optional positional argument (same as `daf git new`).

```bash
# Basic issue creation (note: type is positional argument)
daf git create enhancement --summary "Add caching"

# With description
daf git create bug --summary "Fix bug" --description "Details here"

# With labels, assignee, milestone
daf git create enhancement --summary "New feature" \
  --labels "backend,api" \
  --assignee username \
  --milestone "v1.2.0"

# With acceptance criteria
daf git create enhancement --summary "Auth feature" \
  --acceptance-criteria "OAuth works" \
  --acceptance-criteria "Tests pass"

# Without type (no type label added)
daf git create --summary "General issue"

# With parent issue
daf git create task --summary "Implement auth" --parent "#123"
daf git create enhancement --summary "Add caching" --parent "owner/repo#456"
```

**Note:** Use `daf git new` instead if you want to start working on the issue immediately.

### daf git view
View issue details in Claude-friendly format.

```bash
# View current session's issue
daf git view

# View specific issue
daf git view 123
daf git view owner/repo#123

# Include comments
daf git view 123 --comments
```

**Output shows:**
- Issue number and title
- State (open/closed)
- Type, priority, points (from labels)
- Assignees and milestone
- Description
- Acceptance criteria
- Labels
- Comments (with --comments flag)

### daf git add-comment
Add a comment to a GitHub/GitLab issue.

```bash
# Add comment (note: comment is positional, not a flag)
daf git add-comment 123 "Work in progress"
daf git add-comment "#123" "Merged PR #45"
daf git add-comment owner/repo#123 "Ready for review"
```

**Important:** The comment text is a positional argument, not `--comment`.

### daf git update
Update issue fields.

```bash
# Update labels
daf git update 123 --labels "priority: high,backend"

# Update assignee
daf git update 123 --assignee username

# Update milestone
daf git update 123 --milestone "v2.0"

# Update multiple fields
daf git update 123 --labels "critical" --assignee user --milestone "Sprint 5"

# Link to parent issue
daf git update 123 --parent "#456"
daf git update 123 --parent "owner/repo#789"
```

## Typical Workflows

**Workflow 1: Create new feature (recommended)**
```bash
# 1. Create issue and session (note: type is positional argument)
daf git new enhancement --goal "Add OAuth support"

# 2. Work on it (Claude Code opens automatically)
# ... do work in Claude Code session ...

# 3. Complete when done
daf complete
```

**Workflow 2: Work on existing issue**
```bash
# 1. Open session for existing issue
daf git open 456

# 2. View issue details
daf git view

# 3. Add status comment
daf git add-comment 456 "Started implementation"

# 4. Complete when done
daf complete
```

**Workflow 3: Create issue without session**
```bash
# Create issue for someone else to work on
daf git create --summary "Refactor auth module" \
  --type task \
  --assignee teammate \
  --labels "refactor,backend"
```

## GitHub/GitLab vs JIRA

**Key differences:**
- **Issue types**: Uses labels (bug, enhancement, task) instead of native JIRA types
- **Priority**: Convention-based labels (`priority: high`, `priority: critical`)
- **Story points**: Labels (`points: 3`, `points: 5`, `points: 8`)
- **Workflows**: Binary state (open/closed) + optional status labels
- **Sprints**: Uses milestones instead
- **Attachments**: GitHub doesn't support files, GitLab does

**Label conventions:**
- Type: `bug`, `enhancement`, `task`, `spike`, `epic`
- Priority: `priority: critical`, `priority: high`, `priority: medium`, `priority: low`
- Points: `points: 1`, `points: 2`, `points: 3`, `points: 5`, `points: 8`

## Platform Detection

DevAIFlow automatically detects GitHub vs GitLab from:
1. Git remote URL (github.com vs gitlab.com)
2. Issue key format
3. Repository configuration

Both platforms use `#` format for issues:
- `#123` - Issue in current repository
- `owner/repo#123` - Issue in specific repository

## Requirements

- **GitHub**: GitHub CLI (`gh`) installed and authenticated (`gh auth login`)
- **GitLab**: GitLab CLI (`glab`) installed and authenticated (`glab auth login`)

## Why Use This

- ✅ Automatic authentication via CLI tools
- ✅ Claude-friendly formatted output
- ✅ Integrated with daf session workflow
- ✅ Mock mode for testing
- ✅ Consistent API across GitHub and GitLab
- ✅ Better than raw `gh` or `glab` commands for AI workflows
