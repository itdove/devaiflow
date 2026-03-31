# GitHub Issue Integration

**Status**: ✅ Production Ready
**Last Updated**: 2026-03-06

Complete guide to integrating DevAIFlow with GitHub Issues.

## Overview

GitHub integration is **completely optional**. The tool works perfectly fine for local session management without GitHub. However, if you use GitHub Issues for task tracking, this integration provides:

- **Automatic issue sync** - Discover assigned issues and create sessions
- **Issue creation with AI** - Analyze codebase before creating issues
- **Progress comments** - Add session notes to GitHub issues
- **PR integration** - Link pull requests to issues automatically
- **Multi-repository support** - Sync issues across all repos in your workspaces
- **GitLab compatibility** - Same commands work for GitLab via `glab` CLI

## Quick Start

### 1. Prerequisites

- **GitHub CLI (`gh`)** installed and authenticated
  ```bash
  # macOS/Linux
  brew install gh

  # Or download from https://cli.github.com/
  ```

- **Authentication** (one-time setup)
  ```bash
  gh auth login
  ```

### 2. Configure Workspaces

Add your git repositories to workspaces for automatic sync:

```bash
daf config
# Navigate to: Repositories > Workspaces
# Add workspace paths containing your GitHub repositories
```

Example workspace configuration:
```json
{
  "repos": {
    "workspaces": [
      {
        "name": "work",
        "path": "~/projects/work"
      },
      {
        "name": "open-source",
        "path": "~/projects/oss"
      }
    ]
  }
}
```

### 3. Sync Your Issues

```bash
# Sync all assigned issues from all repositories
daf sync

# Preview what would be synced
daf sync --dry-run
```

## Authentication

### GitHub CLI Authentication

DevAIFlow uses the GitHub CLI (`gh`) for all GitHub operations, which handles authentication automatically.

**Initial Setup:**

```bash
# Authenticate with GitHub
gh auth login

# Select authentication method:
# - Login with a web browser (recommended)
# - Paste an authentication token
```

**Verify Authentication:**

```bash
# Check authentication status
gh auth status

# Test API access
gh issue list --assignee @me
```

**Multiple GitHub Accounts:**

```bash
# Switch between accounts
gh auth switch

# Login to additional account
gh auth login --hostname github.enterprise.com
```

### GitLab CLI Authentication

For GitLab integration, use the GitLab CLI (`glab`):

```bash
# Install GitLab CLI
brew install glab

# Authenticate
glab auth login

# Verify
glab auth status
```

## Core Workflows

### Workflow 1: Create Well-Researched Issues

Use Claude to analyze your codebase before creating issues:

```bash
# Create an issue with AI analysis
daf git new --goal "Add user authentication to API"
```

**What happens:**
1. Creates analysis-only session (no code changes)
2. Launches Claude to analyze your codebase
3. Claude helps you understand implementation complexity
4. You create a detailed issue with accurate acceptance criteria

**Inside Claude session:**

```bash
# After analysis, create the issue:
daf git create \
  --summary "Add two-factor authentication support" \
  --description "Analyzed the codebase and found..." \
  --acceptance-criteria "User can enable 2FA" \
  --acceptance-criteria "Supports TOTP apps like Google Authenticator"
```

**Result:**
- Issue created on GitHub with detailed description
- Session automatically renamed to `creation-60` (for issue #60)
- You can reopen with `daf open creation-60`

### Workflow 2: Sync and Work on Assigned Issues

For issues already assigned to you:

```bash
# 1. Sync all assigned issues from configured workspaces
daf sync

# 2. List your active sessions
daf list --active

# 3. Open an issue (use session name - no quotes needed!)
daf open owner-repo-60

# 4. Work in Claude, then exit and add notes
daf note owner-repo-60 "Implemented authentication module"

# 5. Add comment to GitHub issue
daf git add-comment "owner/repo#60" "Ready for review"

# 6. Complete the session
daf complete owner-repo-60
```

### Workflow 3: Create Issues Directly

Skip analysis and create issues directly:

```bash
daf git create bug \
  --summary "Fix login button styling" \
  --description "Button is misaligned on mobile devices" \
  --assignee yourusername
```

## Session Naming

GitHub issue keys contain `/` and `#` which are problematic in bash. DevAIFlow automatically converts them to dash-separated session names:

**Issue Key → Session Name:**
- `owner/repo#60` → `owner-repo-60`
- `github.enterprise.com/owner/repo#60` → `github-enterprise-com-owner-repo-60`

**Using Session Names (Recommended):**

```bash
# ✅ No quotes needed - safe for bash
daf open owner-repo-60
daf complete owner-repo-60
daf note owner-repo-60 "Progress update"
```

**Using Issue Keys (Requires Quotes):**

```bash
# ✅ Quotes required - # starts comments in bash
daf git open "owner/repo#60"
daf git view "owner/repo#60"

# ❌ This won't work - everything after # is a comment!
daf git open owner/repo#60
```

## GitHub-Specific Features

### Label Conventions (Optional)

GitHub doesn't have custom fields like JIRA, but you can use labels for metadata:

**Issue Types:**
- `bug` - Bug reports
- `enhancement` - Feature requests
- `task` - General tasks

**Priority:**
- `priority: critical`
- `priority: high`
- `priority: medium`
- `priority: low`

**Story Points:**
- `points: 1`, `points: 2`, `points: 3`, `points: 5`, `points: 8`

**Status (Optional, disabled by default):**
- `status: in-progress`
- `status: in-review`
- `status: blocked`

**Note:** These labels are **not added automatically**. You must explicitly add them via `--labels` flag or in the GitHub UI.

### Status Labels Configuration

By default, DevAIFlow does **not** add status labels to keep issues clean. You can enable them:

```bash
daf config
# Navigate to: GitHub > Workflow Settings
# Enable "Add status labels"
```

Or in `config.json`:
```json
{
  "github": {
    "add_status_labels": false,  // Default: disabled
    "completion_label": "status: in-review"
  }
}
```

**When enabled:**
- Opening session → Adds `status: in-progress` label
- Completing session → Adds `status: in-review` label

**When disabled (default):**
- No automatic labels added
- Issues remain clean
- You manage labels manually in GitHub UI

### Acceptance Criteria

DevAIFlow supports acceptance criteria as GitHub issue checkboxes:

```bash
daf git create \
  --summary "Add user profile page" \
  --acceptance-criteria "User can view their profile" \
  --acceptance-criteria "User can edit their name and email" \
  --acceptance-criteria "Changes are saved to database"
```

**Result in GitHub:**
```markdown
<!-- ACCEPTANCE_CRITERIA_START -->
- [ ] User can view their profile
- [ ] User can edit their name and email
- [ ] Changes are saved to database
<!-- ACCEPTANCE_CRITERIA_END -->
```

Check off items in the GitHub UI as you complete them!

### Multi-Repository Sync

DevAIFlow automatically scans all repositories in your configured workspaces:

```bash
# Sync issues from all repositories
daf sync

# Example output:
Scanning workspaces for git repositories...
Scanning /Users/you/projects/work...
  • backend-api (github) via origin
  • frontend-app (github) via upstream
  • mobile-app (github) via origin

Found 40 unique repositories

Syncing GitHub issues (40 repositories)...
• backend-api
  Found 3 issues in backend-api
  ✓ Created session: backend-api-123
• frontend-app
  Found 2 issues in frontend-app
  ✓ Created session: frontend-app-456
```

**Deduplication:** If the same repository exists in multiple workspaces, it's only synced once.

### GitHub Enterprise Support

DevAIFlow supports both GitHub.com and self-hosted GitHub Enterprise:

**Authentication:**
```bash
# Authenticate with GitHub Enterprise
gh auth login --hostname github.enterprise.com
```

**Session Names Include Hostname:**

For GitHub.com:
- `owner/repo#60` → `owner-repo-60`

For GitHub Enterprise:
- `github.enterprise.com/owner/repo#60` → `github-enterprise-com-owner-repo-60`

This ensures uniqueness even if you have the same `owner/repo` on multiple GitHub instances.

## Commands Reference

### Creating Issues

```bash
# Create with AI analysis (recommended)
daf git new --goal "Description of what you want to build"

# Create directly
daf git create bug \
  --summary "Issue title" \
  --description "Detailed description" \
  --assignee username \
  --labels "priority: high,backend"

# Create with acceptance criteria
daf git create \
  --summary "Add feature X" \
  --acceptance-criteria "Criterion 1" \
  --acceptance-criteria "Criterion 2" \
  --acceptance-criteria "Criterion 3"
```

### Viewing Issues

```bash
# View issue details (use quotes for issue keys with #)
daf git view "owner/repo#123"

# Or use session name (no quotes needed)
daf git view owner-repo-123
```

### Opening Sessions

```bash
# Recommended: Use session name
daf open owner-repo-60

# Alternative: Use issue key with quotes
daf git open "owner/repo#60"
```

### Adding Comments

```bash
# Add comment to issue (requires quotes around issue key)
daf git add-comment "owner/repo#60" "Comment text here"

# Alternative command name
daf git update "owner/repo#60" --comment "Comment text"
```

### Syncing Issues

```bash
# Sync all assigned issues
daf sync

# Preview sync without creating sessions
daf sync --dry-run
```

### Completing Sessions

```bash
daf complete owner-repo-60
```

**The completion flow:**
1. ✅ Prompt to commit changes
2. ✅ Prompt to create PR
3. ✅ Prompt to close issue (default: No)
4. ✅ Generate AI summary
5. ✅ Add summary as GitHub comment

**Closing behavior:**
- By default, issues remain open (close via PR or manually)
- Prompts: `Close GitHub issue owner/repo#60? (y/N)`
- Configure auto-close: `config.github.auto_close_on_complete = true`

## Configuration Options

### GitHub Configuration

```json
{
  "github": {
    "api_url": "https://api.github.com",
    "repository": "owner/repo",  // Optional default repository
    "default_labels": ["backend", "devaiflow"],  // Labels for all created issues
    "auto_close_on_complete": false,  // Auto-close issues on session complete
    "add_status_labels": false,  // Add status labels (in-progress, in-review)
    "completion_label": "status: in-review",  // Label when completing
    "issue_templates": {
      "bug": "Bug template text...",
      "enhancement": "Feature template text..."
    }
  }
}
```

### Workspace Configuration

```json
{
  "repos": {
    "workspaces": [
      {
        "name": "work",
        "path": "~/projects/work",
        "description": "Work repositories"
      },
      {
        "name": "oss",
        "path": "~/projects/open-source",
        "description": "Open source projects"
      }
    ]
  }
}
```

## Multi-Backend Sync

Sync issues from all backends automatically:

```bash
daf sync

# Syncs:
# 1. JIRA issues (assigned to you)
# 2. GitHub issues (from repos in workspaces)
# 3. GitLab issues (from repos in workspaces)
```

**Workspace Scanning:**
- Scans all repositories in configured workspaces
- Auto-detects GitHub/GitLab from git remotes
- Creates sessions for assigned issues
- Supports multiple repositories

## Transitions

GitHub uses a simpler state model than JIRA:

### On Session Start (`daf open`)

1. If issue is closed → Reopen to "open"
2. Add label: `status: in-progress` (if `add_status_labels: true`)
3. Remove label: `status: blocked` (if present)
4. Non-blocking (won't prevent session start)

### On Session Complete (`daf complete`)

**If `auto_close_on_complete: true`:**
1. Close issue (state: closed)
2. Add label: `status: completed`

**If `auto_close_on_complete: false` (default):**
1. Keep issue open
2. Add label: `status: completed` (if `add_status_labels: true`)
3. Remove label: `status: in-progress`

## Migration from JIRA

### Side-by-Side Operation

No migration needed! Run both backends simultaneously:

```bash
# Continue using JIRA for some projects
daf jira open PROJ-123

# Use GitHub for new projects
daf git open 456

# Sync both backends
daf sync  # Syncs JIRA + GitHub + GitLab
```

### Gradual Migration

1. **Phase 1:** Keep JIRA as default, try GitHub on new projects
2. **Phase 2:** Move active projects to GitHub Issues
3. **Phase 3:** Archive JIRA, switch default backend

```bash
# Switch default backend
daf config set issue_tracker_backend github
```

## Advanced Topics

### Custom Label Mappings

**Note:** Labels are NOT added automatically. This section is for teams that want to customize label naming conventions for labels they add manually in GitHub UI.

If your organization uses different label naming conventions, you can configure custom mappings:

```json
{
  "github": {
    "label_conventions": {
      "bug": "type:bug",              // If you manually add labels, use "type:bug" instead of "bug"
      "enhancement": "type:feature"    // Use "type:feature" for enhancements
    }
  }
}
```

This only affects label recognition when reading issues. DevAIFlow does not automatically add priority or points labels.

### Issue Templates

GitHub issue templates are supported via GitHub's native template system:

```bash
# DevAIFlow respects .github/ISSUE_TEMPLATE/
# Falls back to default template if not available
```

### Acceptance Criteria Storage

Acceptance criteria is stored in issue body with HTML comment delimiters:

```markdown
<!-- ACCEPTANCE_CRITERIA_START -->
- [ ] Criterion 1
- [ ] Criterion 2
<!-- ACCEPTANCE_CRITERIA_END -->
```

DevAIFlow automatically extracts and displays these when viewing issues.

## Limitations

Compared to JIRA, GitHub Issues has some limitations:

1. **No File Attachments** - GitHub API doesn't support file uploads to issues
   - Workaround: Use PR attachments or external links

2. **No Native Hierarchy** - No epic → story → subtask structure
   - Workaround: Use labels and issue references

3. **Binary State** - Only open/closed (no custom workflows)
   - Workaround: Use status labels (status: in-progress)

4. **No Custom Fields** - Only supports labels
   - Workaround: Convention-based label naming

5. **Limited Filtering** - Simpler query capabilities than JIRA JQL
   - Workaround: Use GitHub CLI search features

## Tips and Best Practices

### 1. Always Use Quotes for Issue Keys

The `#` character starts comments in bash:

```bash
# ✅ Good
daf git open "owner/repo#60"

# ❌ Bad - everything after # is ignored!
daf git open owner/repo#60
```

**Better:** Use session names (no quotes needed):
```bash
daf open owner-repo-60
```

### 2. Use AI Analysis for Complex Issues

For features requiring research:

```bash
# Let Claude analyze first
daf git new --goal "Add real-time notifications"

# Claude will help you:
# - Understand existing patterns
# - Identify dependencies
# - Estimate complexity
# - Write accurate acceptance criteria
```

### 3. Leverage Multi-Repository Sessions

One issue spanning multiple repos? Use multi-conversation sessions:

```bash
# Open for backend
daf open owner-backend-api-123
# Select: backend-api repository

# Continue in frontend (same session!)
daf open owner-frontend-app-123
# Select: Create new conversation → frontend-app

# Result: One session with two conversations
# - Unified time tracking
# - Single GitHub issue link
# - Separate conversation history per repo
```

### 4. Keep Issues Clean

Don't clutter with unnecessary labels:

```bash
# ❌ Too many labels
daf git create --summary "Fix bug" --labels "bug,priority: high,points: 3,status: todo,backend,frontend,database"

# ✅ Minimal essential labels
daf git create bug --summary "Fix bug"
```

### 5. Configure Default Labels

For consistent labeling across your team:

```json
{
  "github": {
    "default_labels": ["team-backend", "automated"]
  }
}
```

## GitHub vs JIRA Differences

| Feature | JIRA | GitHub Issues |
|---------|------|---------------|
| **Issue Types** | Native field | Convention-based labels (bug, enhancement, task) |
| **Priority** | Native field | Labels (priority: high, priority: critical) |
| **Story Points** | Custom field | Labels (points: 3, points: 5, points: 8) |
| **Workflow** | Complex state machine | Binary state (open/closed) + status labels |
| **Hierarchy** | Epic → Story → Subtask | Labels + references |
| **Sprints** | Native sprints | Milestones |
| **Attachments** | Supported | Not supported by GitHub API |
| **Custom Fields** | Rich custom fields | Labels only |

## Troubleshooting

### Authentication Issues

```bash
# Check GitHub CLI authentication
gh auth status

# Re-authenticate
gh auth login

# Test API access
gh issue list --assignee @me
```

### Sync Not Finding Issues

```bash
# Verify you have assigned issues
gh issue list --assignee @me --repo owner/repo

# Check workspace configuration
daf config
# Ensure workspace paths are correct

# Try dry-run to see what would sync
daf sync --dry-run
```

### Session Name Conflicts

If you have the same repository on multiple GitHub instances:

```bash
# GitHub.com
owner/repo#60 → owner-repo-60

# GitHub Enterprise
github.enterprise.com/owner/repo#60 → github-enterprise-com-owner-repo-60

# No conflict!
```

### Issue Key Parsing Errors

Always use quotes around issue keys containing `#`:

```bash
# ✅ Correct
daf git open "owner/repo#60"

# ❌ Wrong - bash treats # as comment
daf git open owner/repo#60
```

## GitLab Compatibility

The same commands work for GitLab using `glab` CLI:

```bash
# Install GitLab CLI
brew install glab

# Authenticate
glab auth login

# Commands work the same
daf git new --goal "Add feature"
daf git create --summary "Fix bug"
daf sync
```

**Note:** Replace `gh` commands in this guide with `glab` commands for GitLab-specific operations.

## Related Documentation

- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [GitHub Issues API](https://docs.github.com/en/rest/issues)
- [Issue Templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests)
- [DevAIFlow JIRA Integration](jira-integration.md)
- [Architecture Overview](../developer/issue-tracker-architecture.md)

## Next Steps

- [Quick Start Guide](../getting-started/quick-start.md) - Get started with GitHub workflows
- [JIRA Integration](jira-integration.md) - Compare with JIRA integration
- [Session Management](../guides/session-management.md) - Deep dive into sessions
- [Commands Reference](../reference/commands.md) - All available commands
