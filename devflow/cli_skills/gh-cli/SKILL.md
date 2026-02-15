---
description: GitHub CLI (gh) tool for creating pull requests, managing PRs, fetching files from private repositories, and GitHub API operations used by daf tool
---

# GitHub CLI (gh) Reference for daf tool

The `gh` CLI is used by daf tool for GitHub operations, particularly PR creation and fetching files from private repositories.

## Installation

```bash
# macOS
brew install gh

# Linux (Debian/Ubuntu)
sudo apt install gh

# Windows
winget install GitHub.cli

# Other platforms
# https://cli.github.com/
```

## Authentication

### Interactive Authentication

```bash
# Interactive login
gh auth login

# Check authentication status
gh auth status

# Logout
gh auth logout
```

### Token Authentication

```bash
# Set token in environment
export GITHUB_TOKEN="your-github-token"

# Login with token
gh auth login --with-token < <(echo $GITHUB_TOKEN)

# Refresh authentication
gh auth refresh
```

### Creating Personal Access Token

1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Click "Generate new token (classic)"
3. Select scopes:
   - `repo` - Full repository access (required for PRs)
   - `read:org` - Read org membership (if using org repos)
   - `workflow` - Update GitHub Actions workflows (optional)
4. Generate and save token securely
5. Set as `GITHUB_TOKEN` environment variable

## Pull Request Operations

### Creating Pull Requests

```bash
# Create PR with title and body
gh pr create --title "Add feature" --body "Description"

# Create draft PR
gh pr create --draft --title "WIP: Feature" --body "Description"

# Create PR with template
gh pr create --draft --title "Title" --body "$(cat <<'EOF'
## Description

Brief description of changes

## Testing

- [ ] Test scenario 1
- [ ] Test scenario 2

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Create PR to specific repository (for forks)
gh pr create --repo owner/repo --title "Title" --body "Body"

# Create PR to specific base branch
gh pr create --base develop --title "Title" --body "Body"

# Create PR interactively (prompts for details)
gh pr create --fill

# Create PR from current branch
gh pr create --web  # Opens browser
```

### daf tool Usage Pattern

The daf tool creates PRs using this pattern (devflow/cli/commands/complete_command.py:1428):

```bash
# Basic PR creation
gh pr create --draft --title "Title" --body "Description"

# Fork detection - create PR to upstream
gh pr create --draft --title "Title" --body "Description" --repo upstream-owner/upstream-repo
```

### Managing Pull Requests

```bash
# List PRs
gh pr list
gh pr list --state open
gh pr list --state closed
gh pr list --author @me

# View PR details
gh pr view 123
gh pr view --web  # Open in browser

# Check PR status
gh pr status

# Edit PR
gh pr edit 123 --title "New title"
gh pr edit 123 --body "New description"
gh pr edit 123 --add-label bug
gh pr edit 123 --remove-label enhancement

# Merge PR
gh pr merge 123
gh pr merge 123 --squash
gh pr merge 123 --rebase
gh pr merge 123 --merge

# Close PR
gh pr close 123

# Reopen PR
gh pr reopen 123

# Mark PR ready for review
gh pr ready 123

# Convert to draft
gh pr ready 123 --undo
```

### PR Checks and Reviews

```bash
# View PR checks
gh pr checks

# View PR diff
gh pr diff 123

# Review PR
gh pr review 123 --approve
gh pr review 123 --request-changes
gh pr review 123 --comment -b "Looks good"

# Checkout PR locally
gh pr checkout 123
```

## Repository Operations

### Repository Information

```bash
# View repository
gh repo view
gh repo view owner/repo

# Clone repository
gh repo clone owner/repo

# Create repository
gh repo create my-repo --public
gh repo create my-repo --private

# Fork repository
gh repo fork owner/repo

# List repositories
gh repo list
gh repo list owner
```

### Repository Settings

```bash
# View repository settings
gh repo view --web

# Edit repository
gh repo edit --description "New description"
gh repo edit --homepage "https://example.com"
gh repo edit --visibility private
```

## Fetching Files from Private Repositories

### Using API to Fetch Files

The daf tool uses `gh api` to fetch files from private GitHub repositories (devflow/cli/commands/complete_command.py:797):

```bash
# Fetch file contents (raw)
gh api \
  -H "Accept: application/vnd.github.raw" \
  "/repos/owner/repo/contents/path/to/file"

# Fetch file contents (base64)
gh api "/repos/owner/repo/contents/path/to/file"

# Fetch from specific branch
gh api \
  -H "Accept: application/vnd.github.raw" \
  "/repos/owner/repo/contents/path/to/file?ref=branch-name"
```

### daf tool Pattern for Fetching Templates

```bash
# Fetch PR template from organization repo
gh api \
  -H "Accept: application/vnd.github.raw" \
  "/repos/YOUR-ORG/.github/contents/.github/PULL_REQUEST_TEMPLATE.md"

# With explicit ref parameter
gh api \
  -H "Accept: application/vnd.github.raw" \
  "/repos/owner/repo/contents/AGENTS.md?ref=main"
```

## GitHub API Operations

### Generic API Calls

```bash
# Make GET request
gh api /repos/owner/repo

# Make POST request
gh api -X POST /repos/owner/repo/issues \
  -f title="Issue title" \
  -f body="Issue body"

# Make PATCH request
gh api -X PATCH /repos/owner/repo/issues/1 \
  -f state="closed"

# With custom headers
gh api -H "Accept: application/vnd.github+json" /repos/owner/repo
```

### Common API Endpoints

```bash
# Get repository info
gh api /repos/owner/repo

# List issues
gh api /repos/owner/repo/issues

# Get issue
gh api /repos/owner/repo/issues/1

# List pull requests
gh api /repos/owner/repo/pulls

# Get pull request
gh api /repos/owner/repo/pulls/1

# Get file contents
gh api /repos/owner/repo/contents/path/to/file

# List releases
gh api /repos/owner/repo/releases

# Get latest release
gh api /repos/owner/repo/releases/latest
```

## Workflow Operations

### GitHub Actions

```bash
# List workflows
gh workflow list

# View workflow
gh workflow view

# Run workflow
gh workflow run workflow.yml

# View workflow runs
gh run list
gh run list --workflow=workflow.yml

# View run details
gh run view 12345

# View run logs
gh run view 12345 --log

# Download run artifacts
gh run download 12345
```

## Release Operations

```bash
# List releases
gh release list

# View release
gh release view v1.0.0

# Create release
gh release create v1.0.0 --title "Version 1.0.0" --notes "Release notes"

# Upload assets
gh release upload v1.0.0 dist/*.tar.gz

# Download release assets
gh release download v1.0.0

# Delete release
gh release delete v1.0.0
```

## Issue Operations

```bash
# List issues
gh issue list
gh issue list --state open
gh issue list --label bug
gh issue list --assignee @me

# View issue
gh issue view 123

# Create issue
gh issue create --title "Bug title" --body "Description"

# Edit issue
gh issue edit 123 --title "New title"
gh issue edit 123 --add-label bug

# Close issue
gh issue close 123

# Reopen issue
gh issue reopen 123
```

## Common Patterns in daf tool

### 1. Creating PRs After Completing Session

From `devflow/cli/commands/complete_command.py:1428`:

```bash
# Auto-detect fork and create PR
gh pr create --draft \
  --title "PROJ-12345: Add feature" \
  --body "$(cat <<'EOF'
## Description
...

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# If fork detected, add --repo flag
gh pr create --draft \
  --title "Title" \
  --body "Body" \
  --repo upstream-owner/upstream-repo
```

### 2. Fetching PR Templates

From `devflow/cli/commands/complete_command.py:797`:

```bash
# Fetch from .github repository
gh api \
  -H "Accept: application/vnd.github.raw" \
  "/repos/YOUR-ORG/.github/contents/.github/PULL_REQUEST_TEMPLATE.md"
```

### 3. Checking PR Status

```bash
# Check if PR exists for current branch
gh pr status

# List PRs for current repository
gh pr list --head $(git branch --show-current)
```

## PR Template Format

Standard PR template used by daf tool:

```markdown
## Description

[Brief description of changes]

## Testing

### Steps to test
1. Pull down the PR
2. [Add specific test steps]
3. [Additional steps]

### Scenarios tested
- [ ] Test scenario 1
- [ ] Test scenario 2

## Deployment considerations
- [ ] This code change is ready for deployment on its own
- [ ] This code change requires the following considerations before being deployed:

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Environment Variables

```bash
# GitHub token (required for private repos and PR creation)
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"

# GitHub enterprise server
export GH_ENTERPRISE_TOKEN="token"
export GH_HOST="github.enterprise.com"

# Default repository
export GH_REPO="owner/repo"

# Editor for interactive commands
export EDITOR="vim"
```

## Configuration

```bash
# Set default editor
gh config set editor vim

# Set default protocol
gh config set git_protocol ssh

# View configuration
gh config list

# Config location
~/.config/gh/config.yml
```

## Troubleshooting

### Authentication Issues

```bash
# Check auth status
gh auth status

# Refresh token
gh auth refresh

# Re-authenticate
gh auth logout
gh auth login
```

### PR Creation Failures

```bash
# Check if authenticated
gh auth status

# Verify repository access
gh repo view

# Check current branch
git branch --show-current

# Verify remote is set
git remote -v
```

### Fork Detection

```bash
# Check if repository is a fork
gh repo view --json isFork,parent

# List remotes to see upstream
git remote -v

# Add upstream remote if missing
git remote add upstream https://github.com/original-owner/repo.git
```

## Tips for daf tool Usage

1. **Always authenticate before using** - Run `gh auth login` or set `GITHUB_TOKEN`
2. **Use draft PRs** - Default for daf tool to allow review before marking ready
3. **Include Co-Authored-By** - Required for AI-assisted commits
4. **Fetch templates with API** - More reliable for private repos than raw URLs
5. **Handle forks properly** - Use `--repo` flag to specify upstream
6. **Check token scopes** - Ensure `repo` scope is enabled for PR operations

## See Also

- daf tool operations: See daf-cli skill
- Git operations: See git-cli skill
- GitLab MR creation: See glab-cli skill
- GitHub CLI documentation: https://cli.github.com/manual/
