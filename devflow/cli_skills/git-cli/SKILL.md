---
name: git-cli
description: Git version control commands used by daf tool for branch management, commits, status checks, merging, rebasing, and remote operations
---

# Git CLI Reference for daf tool

Git commands commonly used by the daf (DevAIFlow) tool for version control operations.

## Branch Management

### Checking Branch Status

```bash
# Get current branch name
git rev-parse --abbrev-ref HEAD

# Check if path is a git repository
git rev-parse --git-dir

# Get default branch (main/master/develop)
git symbolic-ref refs/remotes/origin/HEAD
# Output: refs/remotes/origin/main

# Verify if branch exists
git rev-parse --verify <branch-name>

# List all branches
git branch -a

# Show current branch
git branch --show-current
```

### Creating and Switching Branches

```bash
# Create new branch from current HEAD
git checkout -b <branch-name>

# Create new branch from specific branch
git checkout -b <new-branch> <source-branch>

# Switch to existing branch
git checkout <branch-name>

# Create branch without switching
git branch <branch-name>
```

### Branch Naming Convention

Format: `<JIRA-KEY>-<short-description>`

Examples:
```bash
git checkout -b aap-12345-add-caching-layer
git checkout -b aap-67890-fix-timeout-bug
git checkout -b aap-11111-refactor-api-client
```

Rules:
- Use lowercase with hyphens
- Keep description concise but meaningful
- No spaces or special characters

## Status and Diff

### Checking Repository Status

```bash
# Full status
git status

# Short format (for parsing)
git status --short
git status --porcelain

# Check for uncommitted changes (exits 0 if clean)
git diff --quiet && git diff --cached --quiet
```

### Viewing Differences

```bash
# Show unstaged changes
git diff

# Show staged changes (what would be committed)
git diff --cached
git diff --staged

# Show both staged and unstaged
git diff HEAD

# Diff between branches
git diff main..feature-branch
git diff main...HEAD  # Show changes since branch diverged
```

## Staging and Committing

### Staging Changes

```bash
# Stage all changes
git add -A
git add .

# Stage specific file
git add path/to/file

# Stage interactively
git add -p
```

### Creating Commits

```bash
# Commit with message
git commit -m "Brief summary"

# Commit with detailed message (multiline)
git commit -m "$(cat <<'EOF'
Brief summary of changes (< 50 chars)

More detailed explanation if needed. Explain what and why, not how.
- Bullet points are acceptable
- Use present tense

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Commit all tracked changes (skip staging)
git commit -a -m "Message"

# Amend previous commit
git commit --amend

# Amend without changing message
git commit --amend --no-edit
```

### Commit Message Format (daf tool Standard)

```
Brief summary (imperative mood, < 50 chars)

More detailed explanation if needed. Explain what and why, not how.
- Bullet points are acceptable
- Use present tense

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Remote Operations

### Fetching and Pulling

```bash
# Fetch from origin
git fetch origin

# Fetch all remotes
git fetch --all

# Pull current branch
git pull

# Pull with rebase
git pull --rebase

# Pull specific branch
git pull origin main
```

### Pushing Changes

```bash
# Push current branch to origin
git push

# Push and set upstream
git push -u origin <branch-name>

# Push specific branch
git push origin <branch-name>

# Force push (use with caution)
git push --force

# Safer force push
git push --force-with-lease
```

### Checking Remote Status

```bash
# List remotes
git remote -v

# Show remote information
git remote show origin

# Check if branch is behind remote
git fetch origin
git rev-list HEAD..origin/<branch-name> --count

# Check if branch has remote tracking
git rev-parse --abbrev-ref --symbolic-full-name @{u}
```

## Merging and Rebasing

### Merging

```bash
# Merge branch into current
git merge <branch-name>

# Merge with no fast-forward
git merge --no-ff <branch-name>

# Abort merge
git merge --abort

# Check merge conflicts
git diff --name-only --diff-filter=U
```

### Rebasing

```bash
# Rebase current branch onto main
git rebase main

# Continue after resolving conflicts
git rebase --continue

# Skip current commit
git rebase --skip

# Abort rebase
git rebase --abort

# Interactive rebase
git rebase -i HEAD~3
```

### Conflict Resolution

```bash
# Show conflicted files
git diff --name-only --diff-filter=U

# Show conflict markers
git diff --check

# After resolving conflicts
git add <resolved-file>
git rebase --continue  # or git merge --continue
```

## Repository Information

### Checking Repository State

```bash
# Get remote URL
git config --get remote.origin.url

# Show repository root
git rev-parse --show-toplevel

# List tracked files
git ls-files

# Show last commit
git log -1

# Show commit history
git log --oneline
git log --graph --oneline --all

# Show file history
git log --follow -- path/to/file
```

### Cleaning and Maintenance

```bash
# Remove untracked files (dry run)
git clean -n

# Remove untracked files
git clean -f

# Remove untracked files and directories
git clean -fd

# Discard unstaged changes
git checkout -- <file>

# Discard all unstaged changes
git checkout -- .

# Reset staged changes
git reset HEAD <file>
```

## Usage in daf tool

The daf tool uses git commands for:

1. **Repository Detection** (devflow/git/utils.py:13)
   ```python
   git rev-parse --git-dir  # Check if directory is a git repo
   ```

2. **Branch Management** (devflow/git/utils.py:35-167)
   ```python
   git rev-parse --abbrev-ref HEAD  # Get current branch
   git checkout -b <branch-name>    # Create new branch
   git checkout <branch-name>       # Switch branch
   ```

3. **Status Checks** (devflow/git/utils.py:262-308)
   ```python
   git status --porcelain  # Check for uncommitted changes
   git status --short      # Get status summary
   ```

4. **Diff Operations** (devflow/git/utils.py:311-359)
   ```python
   git diff --cached  # Staged changes
   git diff          # Unstaged changes
   ```

5. **Commit Operations** (devflow/git/utils.py:362-392)
   ```python
   git add -A              # Stage all changes
   git commit -m "..."    # Create commit
   ```

6. **Remote Operations** (devflow/git/utils.py:170-209)
   ```python
   git fetch origin  # Fetch updates
   git pull         # Pull changes
   ```

## Common Git Workflows in DAF

### Opening a Session (daf open)

```bash
# 1. Check if in git repo
git rev-parse --git-dir

# 2. Get current branch
git rev-parse --abbrev-ref HEAD

# 3. Check if branch exists
git rev-parse --verify <branch-name>

# 4. Create branch if needed
git checkout -b <jira-key>-<description>

# 5. Pull latest if existing branch
git fetch origin
git pull
```

### Completing a Session (daf complete)

```bash
# 1. Check for uncommitted changes
git status --porcelain

# 2. View changes
git diff --cached  # Staged
git diff          # Unstaged

# 3. Stage all changes
git add -A

# 4. Create commit
git commit -m "..."

# 5. Push to remote
git push -u origin <branch-name>
```

### Branch Synchronization

```bash
# 1. Fetch latest from remote
git fetch origin

# 2. Check if behind
git rev-list HEAD..origin/main --count

# 3. Merge or rebase
git merge origin/main
# or
git rebase origin/main

# 4. Handle conflicts if any
git diff --name-only --diff-filter=U
```

## Git Safety in CS

### Never Commit to Main

```bash
# daf tool prevents commits to main/master
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$current_branch" = "main" ] || [ "$current_branch" = "master" ]; then
    echo "Error: Cannot commit directly to main/master"
    exit 1
fi
```

### Check Before Destructive Operations

```bash
# Always check for uncommitted changes before switching branches
if git diff --quiet && git diff --cached --quiet; then
    git checkout <branch-name>
else
    echo "Warning: Uncommitted changes detected"
fi
```

### Safe Force Push

```bash
# Use --force-with-lease instead of --force
git push --force-with-lease origin <branch-name>
```

## Troubleshooting

### Detached HEAD State

```bash
# Check if in detached HEAD
git symbolic-ref HEAD || echo "detached HEAD"

# Create branch from detached HEAD
git checkout -b <branch-name>
```

### Merge Conflicts

```bash
# List conflicted files
git diff --name-only --diff-filter=U

# After resolving, mark as resolved
git add <file>

# Continue operation
git merge --continue
# or
git rebase --continue
```

### Reset Operations

```bash
# Undo last commit (keep changes staged)
git reset --soft HEAD~1

# Undo last commit (keep changes unstaged)
git reset HEAD~1

# Discard last commit and changes (destructive)
git reset --hard HEAD~1
```

## See Also

- daf tool operations: See daf-cli skill
- GitHub PR creation: See gh-cli skill
- GitLab MR creation: See glab-cli skill
- Git documentation: https://git-scm.com/docs
