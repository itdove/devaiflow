---
description: GitLab CLI (glab) tool for creating merge requests, managing MRs, fetching files from private repositories, and GitLab API operations used by daf tool
---

# GitLab CLI (glab) Reference for daf tool

The `glab` CLI is used by daf tool for GitLab operations, particularly MR (Merge Request) creation and fetching files from private repositories.

## Installation

```bash
# macOS
brew install glab

# Linux
# Download from releases: https://gitlab.com/gitlab-org/cli/-/releases

# Windows
scoop install glab

# Other platforms
# https://gitlab.com/gitlab-org/cli
```

## Authentication

### Interactive Authentication

```bash
# Interactive login (for GitLab.com)
glab auth login

# Interactive login for self-hosted GitLab
glab auth login --hostname gitlab.example.com

# Check authentication status
glab auth status

# Logout
glab auth logout
```

### Token Authentication

For Your organization's internal GitLab (or other enterprise instances), use full authentication:

```bash
# Full authentication with explicit parameters
# Replace gitlab.example.com with your GitLab instance hostname
glab auth login --hostname gitlab.example.com \
  --api-host gitlab.example.com \
  --api-protocol https \
  --git-protocol git \
  -t $GITLAB_TOKEN

# Check remote URL to determine git-protocol
git remote -v
# If using git@gitlab.example.com:..., use --git-protocol git
# If using https://gitlab.example.com/..., use --git-protocol https
```

### Creating Personal Access Token

1. Go to GitLab Settings > Access Tokens
2. Create a token with `api` scope
3. Save the token securely
4. Set as `GITLAB_TOKEN` environment variable

```bash
export GITLAB_TOKEN="your-gitlab-token"
```

## Merge Request Operations

### Creating Merge Requests

```bash
# Create MR with title and description
glab mr create --title "Add feature" --description "Description"

# Create draft MR
glab mr create --draft --title "WIP: Feature" --description "Description"

# Create MR with template
glab mr create --draft --title "Title" --description "$(cat <<'EOF'
Jira Issue: https://jira.example.com/browse/PROJ-12345

## Description

Brief description of changes

## Testing

### Steps to test
1. Pull down the MR
2. Test scenario

### Scenarios tested
- [ ] Test 1
- [ ] Test 2

## Deployment considerations
- [ ] This code change is ready for deployment on its own

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Create MR to specific target project (for forks)
glab mr create --draft \
  --title "Title" \
  --description "Body" \
  --target-project upstream-group/upstream-repo

# Create MR to specific target branch
glab mr create --target-branch develop \
  --title "Title" \
  --description "Body"

# Create MR interactively (prompts for details)
glab mr create --fill

# Create MR and open in browser
glab mr create --web
```

### daf tool Usage Pattern

The daf tool creates MRs using this pattern (devflow/cli/commands/complete_command.py:1504):

```bash
# Basic MR creation
glab mr create --draft --title "Title" --description "Description"

# Fork detection - create MR to upstream
glab mr create --draft \
  --title "Title" \
  --description "Description" \
  --target-project upstream-group/upstream-repo
```

### Managing Merge Requests

```bash
# List MRs
glab mr list
glab mr list --state opened
glab mr list --state merged
glab mr list --state closed
glab mr list --author @me

# View MR details
glab mr view 123
glab mr view --web  # Open in browser

# Check MR status
glab mr status

# Edit MR
glab mr update 123 --title "New title"
glab mr update 123 --description "New description"
glab mr update 123 --add-label bug
glab mr update 123 --remove-label enhancement

# Merge MR
glab mr merge 123
glab mr merge 123 --squash
glab mr merge 123 --rebase

# Close MR
glab mr close 123

# Reopen MR
glab mr reopen 123

# Mark MR ready for review
glab mr update 123 --ready

# Convert to draft
glab mr update 123 --draft
```

### MR Checks and Reviews

```bash
# View MR pipelines
glab mr ci view 123

# View MR diff
glab mr diff 123

# Approve MR
glab mr approve 123

# Revoke approval
glab mr revoke 123

# Add note/comment
glab mr note 123 -m "Looks good"

# Checkout MR locally
glab mr checkout 123
```

## Project Operations

### Project Information

```bash
# View project
glab repo view
glab repo view group/project

# Clone project
glab repo clone group/project

# Create project
glab repo create my-project --public
glab repo create my-project --private

# Fork project
glab repo fork group/project

# List projects
glab repo list
```

### Project Settings

```bash
# View project in browser
glab repo view --web

# Archive project
glab repo archive group/project
```

## Fetching Files from Private Repositories

### Using API to Fetch Files

Similar to GitHub, use glab API for private repository file access:

```bash
# Fetch file contents (raw)
glab api "projects/group%2Fproject/repository/files/path%2Fto%2Ffile/raw?ref=main"

# Fetch file contents (base64)
glab api "projects/group%2Fproject/repository/files/path%2Fto%2Ffile?ref=main"

# Note: URL encode the project path (/ becomes %2F)
# group/project -> group%2Fproject
# path/to/file -> path%2Fto%2Ffile
```

### URL Encoding

```bash
# Convert project path for API
# group/subgroup/project -> group%2Fsubgroup%2Fproject

# Example for multi-level groups
glab api "projects/group%2Fsubgroup%2Fproject/repository/files/README.md/raw?ref=main"
```

## GitLab API Operations

### Generic API Calls

```bash
# Make GET request
glab api projects/123

# Make POST request
glab api -X POST projects/123/issues \
  -f title="Issue title" \
  -f description="Issue body"

# Make PUT request
glab api -X PUT projects/123/issues/1 \
  -f state_event="close"

# Output as JSON
glab api projects/123 -F json
```

### Common API Endpoints

```bash
# Get project info
glab api projects/group%2Fproject

# List issues
glab api projects/group%2Fproject/issues

# Get issue
glab api projects/group%2Fproject/issues/1

# List merge requests
glab api projects/group%2Fproject/merge_requests

# Get merge request
glab api projects/group%2Fproject/merge_requests/1

# Get file contents
glab api "projects/group%2Fproject/repository/files/path%2Fto%2Ffile/raw?ref=main"

# List releases
glab api projects/group%2Fproject/releases

# Get latest release
glab api projects/group%2Fproject/releases | jq '.[0]'
```

## Pipeline Operations

### CI/CD Pipelines

```bash
# List pipelines
glab pipeline list

# View pipeline
glab pipeline status

# View pipeline details
glab pipeline ci view

# Run pipeline
glab pipeline run

# Retry pipeline
glab pipeline retry 12345

# Cancel pipeline
glab pipeline cancel 12345

# View job logs
glab pipeline ci trace 12345
```

## Release Operations

```bash
# List releases
glab release list

# View release
glab release view v1.0.0

# Create release
glab release create v1.0.0 --name "Version 1.0.0" --notes "Release notes"

# Upload assets
glab release upload v1.0.0 dist/*.tar.gz

# Download release
glab release download v1.0.0

# Delete release
glab release delete v1.0.0
```

## Issue Operations

```bash
# List issues
glab issue list
glab issue list --state opened
glab issue list --label bug
glab issue list --assignee @me

# View issue
glab issue view 123

# Create issue
glab issue create --title "Bug title" --description "Description"

# Edit issue
glab issue update 123 --title "New title"
glab issue update 123 --add-label bug

# Close issue
glab issue close 123

# Reopen issue
glab issue reopen 123
```

## Common Patterns in daf tool

### 1. Creating MRs After Completing Session

From `devflow/cli/commands/complete_command.py:1504`:

```bash
# Auto-detect fork and create MR
glab mr create --draft \
  --title "PROJ-12345: Add feature" \
  --description "$(cat <<'EOF'
Jira Issue: https://jira.example.com/browse/PROJ-12345

## Description
...

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# If fork detected, add --target-project flag
glab mr create --draft \
  --title "Title" \
  --description "Body" \
  --target-project upstream-group/upstream-repo
```

### 2. Checking MR Status

```bash
# Check if MR exists for current branch
glab mr status

# List MRs for current project
glab mr list --source-branch $(git branch --show-current)
```

### 3. Detecting Existing MRs

The daf tool checks for existing MRs before creating new ones:

```bash
# Check for MR with current branch
glab mr list -F json | jq '.[] | select(.source_branch == "'$(git branch --show-current)'")'
```

## MR Template Format

Standard MR template used by daf tool:

```markdown
Jira Issue: https://jira.example.com/browse/PROJ-XXXXX

## Description

[Brief description of changes]

Assisted-by: Claude (Anthropic)

## Testing

### Steps to test
1. Pull down the MR
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
# GitLab token (required for private repos and MR creation)
export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"

# GitLab instance URL (for self-hosted)
export GITLAB_HOST="gitlab.example.com"

# Default project
export GLAB_PROJECT="group/project"

# Editor for interactive commands
export EDITOR="vim"
```

## Configuration

```bash
# Set default editor
glab config set editor vim

# Set default protocol
glab config set git_protocol ssh

# Set default hostname
glab config set host gitlab.example.com

# View configuration
glab config get

# Config location
~/.config/glab-cli/config.yml
```

## Troubleshooting

### Authentication Issues

```bash
# Check auth status
glab auth status

# Re-authenticate
glab auth logout
glab auth login --hostname gitlab.example.com

# For enterprise GitLab with full parameters
# Replace gitlab.example.com with your GitLab instance hostname
glab auth login --hostname gitlab.example.com \
  --api-host gitlab.example.com \
  --api-protocol https \
  --git-protocol git \
  -t $GITLAB_TOKEN
```

### MR Creation Failures

```bash
# Check if authenticated
glab auth status

# Verify project access
glab repo view

# Check current branch
git branch --show-current

# Verify remote is set
git remote -v
```

### Fork Detection

```bash
# Check if project is a fork
glab repo view -F json | jq '.forked_from_project'

# List remotes to see upstream
git remote -v

# Add upstream remote if missing
git remote add upstream git@gitlab.example.com:original-group/repo.git
```

### JSON Output Not Working

**IMPORTANT**: The `--json` flag is NOT supported in glab. Use `-F json` instead:

```bash
# WRONG - This doesn't work
glab mr list --json

# CORRECT - Use -F json
glab mr list -F json
```

From daf tool fix (PROJ-60247):
```bash
# Detect existing MR - use -F json, not --json
glab mr list -F json | jq '.[] | select(.source_branch == "feature-branch")'
```

## Important Notes

### glab vs gh Syntax Differences

| Operation | GitHub (gh) | GitLab (glab) |
|-----------|-------------|---------------|
| JSON output | `--json` | `-F json` (NOT `--json`) |
| Create PR/MR | `gh pr create --body` | `glab mr create --description` |
| Fork target | `--repo owner/repo` | `--target-project group/repo` |
| Hostname | N/A (uses gh CLI default) | `--hostname` (NEVER in mr create) |

### Common Mistakes to Avoid

1. **Don't use `--json`** - Use `-F json` instead
2. **Don't use `--hostname` with `mr create`** - Configured via `glab auth login`
3. **URL encode project paths in API calls** - `group/project` → `group%2Fproject`
4. **Use `--description` not `--body`** - Different from gh syntax

## Tips for daf tool Usage

1. **Always authenticate before using** - Run `glab auth login` or set `GITLAB_TOKEN`
2. **Use draft MRs** - Default for daf tool to allow review before marking ready
3. **Include Co-Authored-By** - Required for AI-assisted commits
4. **Check token scopes** - Ensure `api` scope is enabled
5. **Handle forks properly** - Use `--target-project` flag to specify upstream
6. **Use `-F json` not `--json`** - Common syntax difference from gh
7. **Don't use `--hostname` in mr create** - Only for auth, not MR operations

## See Also

- daf tool operations: See daf-cli skill
- Git operations: See git-cli skill
- GitHub PR creation: See gh-cli skill
- GitLab CLI documentation: https://gitlab.com/gitlab-org/cli/-/tree/main/docs
