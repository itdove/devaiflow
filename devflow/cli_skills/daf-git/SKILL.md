---
name: daf-git
description: Manage GitHub/GitLab issues and sessions
---

Complete workflow for managing GitHub Issues and GitLab Issues in DevAIFlow.
Automatically detects the platform from your git repository.

## Quick Start

**View issue details:**
```bash
daf git view
daf git view 123
daf git view owner/repo#123 --comments
```
Auto-detects current session or accepts explicit issue key.

## All Commands

### daf git create
Create a new GitHub/GitLab issue (standalone, without session).

**Syntax:** `daf git create [TYPE] --summary "..."`

TYPE is an optional positional argument.

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

**Workflow: Working on existing issue**
```bash
# 1. View issue details
daf git view

# 2. Add status comment
daf git add-comment 456 "Started implementation"

# 3. Work on implementation
# ... do work in Claude Code session ...
```

**Workflow: Create issue without session**
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
