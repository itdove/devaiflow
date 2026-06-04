---
name: daf-git
description: GitHub/GitLab issue operations (create, update, comment) with Markdown syntax reference
user-invocable: true
argument-hint: "[ISSUE-NUMBER|owner/repo#number]"
---

Complete workflow for managing GitHub Issues and GitLab Issues in DevAIFlow.
Automatically detects the platform from your git repository.

## Quick Start

**View issue details (use gh/glab CLI directly):**
```bash
# GitHub
gh issue view 123
gh issue view 123 --comments

# GitLab
glab issue view 123
glab issue view 123 --comments
```

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

### Viewing Issues

Use the `gh` or `glab` CLI directly to view issues:

```bash
# GitHub
gh issue view 123                          # View issue
gh issue view 123 --comments              # Include comments
gh issue view 123 -R owner/repo           # Cross-repo

# GitLab
glab issue view 123                        # View issue
glab issue view 123 --comments            # Include comments
glab issue view 123 -R owner/repo         # Cross-repo
```

**Tip:** The issue key is available from `daf info` or `daf status`.

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

## GitHub/GitLab Markdown Syntax

**CRITICAL:** GitHub and GitLab issues use **Markdown syntax**, NOT JIRA Wiki markup.

When using `daf git create`, `daf git add-comment`, or `daf git update` commands, all text fields (descriptions, comments) **MUST** use standard **Markdown** formatting.

### Syntax Reference

| Element | Markdown (CORRECT) | JIRA Wiki (WRONG) |
|---------|--------------------|--------------------|
| Header 2 | `## Header` | `h2. Header` |
| Header 3 | `### Header` | `h3. Header` |
| Bold | `**bold**` | `*bold*` |
| Italic | `*italic*` | `_italic_` |
| Code block | ` ```bash\ncode\n``` ` | `{code:bash}\ncode\n{code}` |
| Inline code | `` `code` `` | `{{code}}` |
| Unordered list | `- item` | `* item` |
| Ordered list | `1. item` | `# item` |
| Link | `[text](url)` | `[text\|url]` |
| Checkbox | `- [ ] item` | N/A |
| Checked box | `- [x] item` | N/A |

### When to Use Each Syntax

**Use Markdown for GitHub/GitLab operations:**
- `daf git create` - Creating GitHub/GitLab issues
- `daf git add-comment` - Adding comments to issues
- `daf git update` - Updating issue descriptions
- Pull request descriptions and comments

**Use JIRA Wiki markup for JIRA operations:**
- `daf jira create` / `daf jira add-comment` / `daf jira update`

## Ticket Creation Sessions

Create analysis-only sessions for creating GitHub/GitLab issues:

```bash
# Create ticket creation session
daf git new enhancement --goal "Add caching layer"
daf git new bug --goal "Fix timeout in API"
daf git new task --goal "Refactor auth module" --parent "#123"
```

**Purpose:** Analyze the codebase to create a well-informed issue

**Constraints:**
- DO NOT modify code or files
- DO NOT run git commands
- ONLY read files, search code, analyze architecture
- Create issue when analysis is complete using `daf git create`

**See also:** daf-workflow skill for complete ticket creation workflow.

---

## GitHub Operations

### Authentication

```bash
# Interactive login
gh auth login

# Check status
gh auth status

# Token-based login
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
gh auth login --with-token < <(echo $GITHUB_TOKEN)
```

**Fine-grained tokens:** Some organizations require fine-grained tokens instead of classic tokens.

When you see: "forbids access via a personal access token (classic)":
1. Go to: https://github.com/settings/personal-access-tokens/new
2. Select "Only select repositories" and choose the specific repo
3. Grant permissions: Contents (R/W), Issues (R/W), Pull requests (R/W)
4. Authenticate: `gh auth login` and paste the token

**Pre-flight auth check:**
```bash
# Auto-detect repository from git remote
daf git check-auth

# Or specify repository explicitly
daf git check-auth owner/repo
```

### PR Creation (daf complete pattern)

```bash
# Basic PR creation
gh pr create --draft --title "Title" --body "Description"

# Fork detection - create PR to upstream
gh pr create --draft --title "Title" --body "Description" --repo upstream-owner/upstream-repo

# Create PR with template
gh pr create --draft --title "PROJ-123: Feature" --body "$(cat <<'EOF'
## Description
...

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**Fork detection:**
```bash
# Check if repository is a fork
gh repo view --json isFork,parent

# List remotes to see upstream
git remote -v
```

### Fetching Files from Private Repos

```bash
# Fetch file contents (raw)
gh api \
  -H "Accept: application/vnd.github.raw" \
  "/repos/owner/repo/contents/path/to/file"

# Fetch from specific branch
gh api \
  -H "Accept: application/vnd.github.raw" \
  "/repos/owner/repo/contents/path/to/file?ref=branch-name"

# Fetch PR template from organization .github repo
gh api \
  -H "Accept: application/vnd.github.raw" \
  "/repos/YOUR-ORG/.github/contents/.github/PULL_REQUEST_TEMPLATE.md"
```

---

## GitLab Operations

### Authentication

```bash
# Interactive login (GitLab.com)
glab auth login

# Self-hosted GitLab (full parameters)
glab auth login --hostname gitlab.example.com \
  --api-host gitlab.example.com \
  --api-protocol https \
  --git-protocol git \
  -t $GITLAB_TOKEN

# Check status
glab auth status
```

**Token:** Create at GitLab Settings > Access Tokens with `api` scope.

### MR Creation (daf complete pattern)

```bash
# Basic MR creation
glab mr create --draft --title "Title" --description "Description"

# Fork detection - create MR to upstream
glab mr create --draft \
  --title "Title" \
  --description "Description" \
  --target-project upstream-group/upstream-repo

# Create MR to specific target branch
glab mr create --target-branch develop --title "Title" --description "Body"
```

**Fork detection:**
```bash
# Check if project is a fork
glab repo view -F json | jq '.forked_from_project'

# List remotes to see upstream
git remote -v
```

### Fetching Files from Private Repos

```bash
# Fetch file contents (raw) - URL encode paths with %2F
glab api "projects/group%2Fproject/repository/files/path%2Fto%2Ffile/raw?ref=main"

# Multi-level groups
glab api "projects/group%2Fsubgroup%2Fproject/repository/files/README.md/raw?ref=main"
```

---

## gh vs glab Syntax Differences

| Operation | GitHub (`gh`) | GitLab (`glab`) |
|-----------|---------------|-----------------|
| JSON output | `--json` | `-F json` (NOT `--json`) |
| Create PR/MR | `gh pr create --body` | `glab mr create --description` |
| Fork target | `--repo owner/repo` | `--target-project group/repo` |
| Hostname | N/A (default) | `--hostname` (auth only, NEVER in mr create) |
| Check MR | `gh pr list --head branch` | `glab mr list -F json \| jq` |
| Ready for review | `gh pr ready 123` | `glab mr update 123 --ready` |
| Approve | `gh pr review 123 --approve` | `glab mr approve 123` |

**Common mistakes:**
- Using `--json` with glab (use `-F json`)
- Using `--body` with glab mr create (use `--description`)
- Using `--hostname` with glab mr create (only for `glab auth login`)

## PR/MR Template

Standard template used by daf tool:

```markdown
## Description

[Brief description of changes]

## Testing

### Steps to test
1. Pull down the PR/MR
2. [Add specific test steps]

### Scenarios tested
- [ ] Test scenario 1
- [ ] Test scenario 2

## Deployment considerations
- [ ] This code change is ready for deployment on its own
- [ ] This code change requires considerations before being deployed:

Co-Authored-By: Claude <noreply@anthropic.com>
```

**GitLab addition:** Add `Jira Issue: https://jira.example.com/browse/PROJ-XXXXX` at the top if using JIRA.

## GitHub/GitLab vs JIRA

**Key differences:**
- **Issue types**: Uses labels (bug, enhancement, task) instead of native JIRA types
- **Priority**: Convention-based labels (`priority: high`, `priority: critical`)
- **Story points**: Labels (`points: 3`, `points: 5`, `points: 8`)
- **Workflows**: Binary state (open/closed) + optional status labels
- **Sprints**: Uses milestones instead
- **Attachments**: GitHub doesn't support files, GitLab does

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

## Typical Workflows

**Working on existing issue:**
```bash
# 1. View issue details
gh issue view 456 --comments    # or: glab issue view 456 --comments

# 2. Add status comment
daf git add-comment 456 "Started implementation"

# 3. Work on implementation...
```

**Create issue without session:**
```bash
daf git create task --summary "Refactor auth module" \
  --assignee teammate \
  --labels "refactor,backend"
```
