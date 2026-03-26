# Non-Interactive CLI Parameters

**Issue:** [#278](https://github.com/itdove/devaiflow/issues/278) - Add CLI parameters for all interactive prompts in session creation commands

## Overview

All DevAIFlow session creation and management commands now support non-interactive automation through CLI parameters. This enables full scriptability for CI/CD pipelines, automated workflows, and batch operations.

## Global Flag

### `--non-interactive`

**Global flag** available on all commands. Enables non-interactive mode by setting `DAF_NON_INTERACTIVE=1` environment variable.

```bash
daf --non-interactive new PROJ-123 --goal "..." --path /workspace/project
```

**Behavior:**
- Errors if required parameters are missing (no prompts)
- Automatically enabled in CI environments (CI, GITHUB_ACTIONS, GITLAB_CI, JENKINS_HOME, TRAVIS, CIRCLECI)
- Also enabled by `--json` flag
- Can be set manually via `DAF_NON_INTERACTIVE=1` environment variable

## Parameter Priority

When multiple sources provide the same parameter:

```
CLI Parameter > Config Setting > Prompt > Error (in non-interactive mode)
```

**Examples:**
- `--create-branch` overrides config `auto_create_branch` setting
- `--source-branch main` overrides default base branch detection
- If no parameter and no config, error in `--non-interactive` mode

## Command-Specific Parameters

### `daf new` - Session Creation

**Branch creation parameters:**

```bash
--create-branch                  # Create new branch (skip prompt)
--no-create-branch              # Don't create branch (skip prompt)
--source-branch BRANCH          # Source branch to create from (default: base branch)
--on-branch-exists STRATEGY     # Action when branch exists: error|use-existing|add-suffix|skip
--allow-uncommitted             # Allow uncommitted changes when switching branches
--sync-upstream                 # Sync with upstream before creating branch
--no-sync-upstream              # Don't sync with upstream
```

**Workspace and session parameters:**

```bash
--auto-workspace                # Auto-select workspace without prompting
--session-index N               # Select existing session by index (for multi-session selection)
```

**Complete non-interactive example:**

```bash
daf new PROJ-12345 \
  --goal "Implement caching layer" \
  --path ~/workspace/backend-api \
  --workspace production \
  --create-branch \
  --source-branch main \
  --on-branch-exists use-existing \
  --allow-uncommitted \
  --sync-upstream \
  --auto-workspace \
  --non-interactive
```

#### `--on-branch-exists` Strategies

| Strategy | Behavior |
|----------|----------|
| `error` | Fail with error if branch already exists (default) |
| `use-existing` | Checkout existing branch without creating new one |
| `add-suffix` | Create branch with suffix (e.g., `feature-123-v2`) |
| `skip` | Don't create or checkout branch, use current branch |

### `daf open` - Resume Session

**All branch creation parameters from `daf new`, plus:**

```bash
--sync-strategy STRATEGY        # Strategy for syncing with upstream: merge|rebase|skip
```

**Complete non-interactive example:**

```bash
daf open PROJ-12345 \
  --path backend-api \
  --workspace production \
  --sync-upstream \
  --sync-strategy merge \
  --auto-workspace \
  --non-interactive
```

**Adding projects to session:**

```bash
daf open PROJ-12345 \
  --workspace production \
  --projects backend,frontend,shared \
  --create-branch \
  --source-branch main \
  --on-branch-exists use-existing \
  --non-interactive
```

### `daf jira new` - JIRA Ticket Creation

**Multi-project and temp clone parameters:**

```bash
--projects REPO1,REPO2,...      # Comma-separated list of repository names (requires --workspace)
--temp-clone                     # Clone to temporary directory for clean analysis
--no-temp-clone                  # Don't use temporary clone (use current directory)
```

**Complete non-interactive example:**

```bash
daf jira new story \
  --parent PROJ-100 \
  --goal "Implement Redis caching" \
  --workspace production \
  --projects backend-api,frontend-app \
  --no-temp-clone \
  --non-interactive
```

### `daf git new` - GitHub/GitLab Issue Creation

**Same parameters as `daf jira new`:**

```bash
--projects REPO1,REPO2,...      # Multi-project mode
--temp-clone / --no-temp-clone  # Temporary directory cloning
```

**Complete non-interactive example:**

```bash
daf git new enhancement \
  --goal "Add caching layer" \
  --workspace production \
  --path backend-api \
  --no-temp-clone \
  --non-interactive
```

### `daf investigate` - Investigation Session

**Same parameters as `daf jira new` and `daf git new`:**

```bash
--projects REPO1,REPO2,...      # Multi-project mode
--temp-clone / --no-temp-clone  # Temporary directory cloning
```

**Complete non-interactive example:**

```bash
daf investigate \
  --goal "Research caching options" \
  --workspace production \
  --projects backend-api,shared-lib \
  --temp-clone \
  --non-interactive
```

## Use Cases

### Complete Workflow Automation

Create session, work, and complete entirely via CLI:

```bash
# 1. Create session
daf --non-interactive new feature-123 \
  --goal "Implement feature 123" \
  --path ~/workspace/backend-api \
  --workspace main \
  --create-branch \
  --source-branch main \
  --on-branch-exists use-existing

# 2. Work in session (AI agent does the work)
# ... Claude Code launches automatically and works on the feature ...

# 3. Complete session
daf --non-interactive complete feature-123 \
  --commit-message "Implement feature 123" \
  # (Additional parameters would be added in Phase 2)
```

### CI/CD Pipeline

Automated ticket creation and analysis in CI:

```bash
#!/bin/bash
set -e

# Create investigation session
daf --non-interactive jira new epic \
  --parent PROJ-100 \
  --goal "Implement caching layer" \
  --path /workspace/project \
  --no-temp-clone

# After analysis, create actual ticket
daf --non-interactive jira create story \
  --summary "Implement Redis caching" \
  --parent PROJ-100 \
  --field workstream=backend \
  --description "..." \
  # (Additional parameters would be added in Phase 3)
```

### Bulk Operations

```bash
#!/bin/bash

# Create sessions for multiple projects
for project in backend frontend shared; do
  daf --non-interactive new PROJ-$project \
    --goal "Upgrade dependencies" \
    --path ~/workspace/$project \
    --workspace production \
    --create-branch \
    --source-branch main \
    --on-branch-exists add-suffix
done
```

### Multi-Project Analysis

Analyze multiple repositories simultaneously:

```bash
daf --non-interactive investigate \
  --goal "Analyze API consistency across services" \
  --workspace production \
  --projects backend-api,frontend-api,mobile-api \
  --temp-clone
```

## Backward Compatibility

All new parameters are **optional** and **backward compatible**:

- ✅ Existing commands work without new parameters
- ✅ Interactive prompts appear when parameters not provided
- ✅ No breaking changes to existing scripts or workflows
- ✅ Config settings continue to work as defaults

**Example - old syntax still works:**

```bash
# Still works - will prompt interactively
daf new PROJ-123 --goal "Add feature"

# Explicit non-interactive mode
daf --non-interactive new PROJ-123 --goal "Add feature" --path /workspace/project
```

## Environment Detection

DevAIFlow automatically detects non-interactive environments:

### CI/CD Environments

Automatically enables non-interactive mode when these environment variables are set:

- `CI=1` (generic CI indicator)
- `GITHUB_ACTIONS=true` (GitHub Actions)
- `GITLAB_CI=true` (GitLab CI)
- `JENKINS_HOME=<path>` (Jenkins)
- `TRAVIS=true` (Travis CI)
- `CIRCLECI=true` (Circle CI)

### Manual Control

Force non-interactive mode in any environment:

```bash
# Via global flag
daf --non-interactive <command>

# Via environment variable
export DAF_NON_INTERACTIVE=1
daf <command>

# Via JSON mode (also enables non-interactive)
daf <command> --json
```

## Error Handling

In non-interactive mode, commands **fail with clear errors** instead of prompting:

```bash
$ daf --non-interactive new PROJ-123 --goal "Add feature"
✗ Required parameter missing: --path or --workspace

  Use --path to specify project directory:
    daf --non-interactive new PROJ-123 --path /workspace/project

  Or use --workspace for multi-project mode:
    daf --non-interactive new PROJ-123 --workspace production --projects backend

Exit code: 1
```

## Testing

Comprehensive test coverage in `tests/test_non_interactive_params.py`:

```bash
# Run all non-interactive parameter tests
pytest tests/test_non_interactive_params.py -v

# Run specific test class
pytest tests/test_non_interactive_params.py::TestDafNewNonInteractiveParams -v
```

**Test coverage includes:**

- ✅ Global `--non-interactive` flag
- ✅ All `daf new` parameters
- ✅ All `daf open` parameters
- ✅ All `daf jira new`, `daf git new`, `daf investigate` parameters
- ✅ Parameter validation and error handling
- ✅ Backward compatibility
- ✅ CI environment detection

## Implementation Status

### Phase 1: Core Session Commands ✅ COMPLETE

- ✅ `daf new` - All 7 parameters implemented
- ✅ `daf open` - All 7 parameters implemented
- ✅ `daf jira new`, `daf git new`, `daf investigate` - All 2 parameters implemented
- ✅ Global `--non-interactive` flag
- ✅ Comprehensive test coverage (32 tests, all passing)
- ✅ Documentation

### Phase 2: Completion Command ⏳ PLANNED

- ⏳ `daf complete` - Add missing parameters (`--yes`, `--commit-message`, etc.)
- ⏳ Full automation of completion workflow

### Phase 3: JIRA Operations ⏳ PLANNED

- ⏳ `daf jira create` - Improve field validation in non-interactive mode
- ⏳ `daf jira add-comment` - Add `--yes` flag

### Phase 4: Management Commands ⏳ PLANNED

- ⏳ `daf delete` - Add `--yes` flag
- ⏳ `daf import`, `daf import-session` - Add parameters

## References

- **Issue:** [itdove/devaiflow#278](https://github.com/itdove/devaiflow/issues/278)
- **Tests:** `tests/test_non_interactive_params.py`
- **Implementation:**
  - `devflow/cli/main.py` - Global flag and command definitions
  - `devflow/cli/commands/new_command.py` - Session creation parameters
  - `devflow/cli/commands/open_command.py` - Session opening parameters
  - `devflow/cli/commands/jira_new_command.py` - JIRA ticket creation parameters
  - `devflow/cli/commands/git_new_command.py` - GitHub/GitLab issue parameters
  - `devflow/cli/commands/investigate_command.py` - Investigation parameters

## See Also

- [Command Reference](./07-commands.md) - Complete command documentation
- [Configuration Guide](./03-configuration.md) - Config settings for defaults
- [CI/CD Integration](./ci-cd-integration.md) - Using DevAIFlow in pipelines
