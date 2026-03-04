# Branch Source Selection Enhancement

## Overview

This enhancement adds the ability to select a specific branch as the source when creating a new branch in DevAIFlow. Previously, users could only choose between creating from the current state or from the default branch (main/master).

## Changes Made

### 1. Added `list_local_branches()` Method

**File**: `devflow/git/utils.py`

Added a new utility method to list all local branches in a repository:

```python
@staticmethod
def list_local_branches(path: Path) -> list[str]:
    """List all local branches in a repository.

    Returns:
        Sorted list of branch names
    """
```

### 2. Enhanced Branch Creation Strategy

**File**: `devflow/cli/commands/new_command.py`

Modified `_handle_branch_creation()` to support three strategies:

1. **From current state** - Stay on current branch (existing)
2. **From default branch** - Checkout main/master first (existing)
3. **From specific branch** - Select and pull a specific branch (NEW)

### 3. Strategy 3: From Specific Branch

When users select strategy 3, the following workflow occurs:

#### Step 1: Check for Uncommitted Changes (CRITICAL)

```
✗ Error: Cannot switch branches with uncommitted changes

Uncommitted changes:
  M file1.txt
  A file2.txt

Please commit, stash, or discard your changes before creating a branch from a specific source.

Options:
  - Commit: git commit -am "Your message"
  - Stash: git stash
  - Discard: git reset --hard HEAD
```

**Important**: Unlike the other strategies, strategy 3 **aborts immediately** if there are uncommitted changes. No option to continue is provided, as switching branches with uncommitted changes would cause issues.

#### Step 2: Fetch Latest Changes

```
Fetching latest from origin...
```

#### Step 3: Display Available Branches

```
Available branches:
1. develop
2. feature/new-ui
3. main (current)
4. release/2.5
```

#### Step 4: User Selects Source Branch

```
Select source branch [1]: 2
```

#### Step 5: Checkout and Pull Selected Branch

```
Checking out feature/new-ui...
Pulling latest feature/new-ui...
```

#### Step 6: Create New Branch

```
Creating branch: aap-12345-my-feature...
✓ Created and switched to branch: aap-12345-my-feature
```

## User Experience

### Interactive Mode

When creating a new session with `daf new`, users now see:

```
Branch creation strategy:
1. From current state (stay on current branch)
2. From default branch (checkout main/master first)
3. From specific branch (select and pull)
Select [2]: 3
```

### Error Handling

If uncommitted changes exist when selecting strategy 3:

```
✗ Error: Cannot switch branches with uncommitted changes

Uncommitted changes:
  M devflow/git/utils.py
  ?? new_file.txt

Please commit, stash, or discard your changes before creating a branch from a specific source.
Options:
  - Commit: git commit -am "Your message"
  - Stash: git stash
  - Discard: git reset --hard HEAD
```

## Testing

### Test Coverage

Created comprehensive tests in `tests/test_branch_from_specific_source.py`:

1. **test_list_local_branches**: Verifies listing local branches
2. **test_handle_branch_creation_from_specific_branch_with_uncommitted_changes**: Verifies abort on uncommitted changes
3. **test_handle_branch_creation_from_specific_branch_success**: Verifies successful branch creation from specific source
4. **test_handle_branch_creation_strategy_options**: Verifies all three strategies are available

### Test Results

```
tests/test_branch_from_specific_source.py::test_list_local_branches PASSED
tests/test_branch_from_specific_source.py::test_handle_branch_creation_from_specific_branch_with_uncommitted_changes PASSED
tests/test_branch_from_specific_source.py::test_handle_branch_creation_from_specific_branch_success PASSED
tests/test_branch_from_specific_source.py::test_handle_branch_creation_strategy_options PASSED

4 passed
```

All existing branch-related tests continue to pass (12 tests in `test_branch_conflict.py`).

## Use Cases

### Use Case 1: Creating Feature Branch from Develop

```bash
$ daf new feature-xyz

Branch creation strategy:
1. From current state (stay on current branch)
2. From default branch (checkout main/master first)
3. From specific branch (select and pull)
Select [2]: 3

Fetching latest from origin...

Available branches:
1. develop
2. main (current)
Select source branch [1]: 1

Checking out develop...
Pulling latest develop...
Creating branch: aap-12345-feature-xyz...
✓ Created and switched to branch: aap-12345-feature-xyz
```

### Use Case 2: Creating Hotfix from Release Branch

```bash
$ daf new hotfix-critical

Branch creation strategy:
1. From current state (stay on current branch)
2. From default branch (checkout main/master first)
3. From specific branch (select and pull)
Select [2]: 3

Fetching latest from origin...

Available branches:
1. main (current)
2. release/2.5
3. release/3.0
Select source branch [1]: 2

Checking out release/2.5...
Pulling latest release/2.5...
Creating branch: aap-67890-hotfix-critical...
✓ Created and switched to branch: aap-67890-hotfix-critical
```

## Technical Details

### Git Commands Executed (Strategy 3)

1. `git fetch origin` - Fetch latest from remote
2. `git branch --format=%(refname:short)` - List local branches
3. `git checkout <selected-branch>` - Switch to selected branch
4. `git pull` - Pull latest changes
5. `git checkout -b <new-branch>` - Create new branch from current state

### Safety Checks

1. **Uncommitted changes check**: Prevents branch switching with dirty working tree
2. **Branch existence check**: Verifies selected branch exists before checkout
3. **Pull failure handling**: Warns if pull fails but continues (non-blocking)

## Configuration

The feature respects existing configuration:

- If `config.prompts.default_branch_strategy` is set to `"from_default"` or `"from_current"`, the configured strategy is used automatically
- Strategy 3 is only available in interactive mode when no default strategy is configured
- JSON mode defaults to strategy 2 (from default branch)

## Backward Compatibility

This enhancement is fully backward compatible:

- Existing workflows continue to work unchanged
- Default behavior (strategy 2) remains the same
- No breaking changes to the API or configuration

## Future Enhancements

Potential future improvements:

1. Add configuration option to set strategy 3 as default with a preferred source branch
2. Remember last selected source branch per repository
3. Support creating from remote branches directly (without local checkout)
4. Add ability to create from a specific commit SHA
