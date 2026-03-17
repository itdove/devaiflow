# Issue #216 Fix Summary

## Problem
In some commands (`daf jira new`, `daf git new`, `daf investigate`), the user was prompted with "Create multi-project session (analyze multiple repos)?" BEFORE seeing the list of available projects in the workspace. This made it impossible for users to make an informed decision about whether they needed multi-project mode without knowing which projects were available.

## Root Cause
The `prompt_repository_selection_with_multiproject` function in `devflow/cli/utils.py` (line 1273) was asking the multi-project question immediately after scanning the workspace, without first displaying the list of available repositories to the user.

## Solution
Modified `devflow/cli/utils.py` to display the project list BEFORE asking the multi-project question, matching the behavior of `daf open`.

### Code Changes

**File:** `devflow/cli/utils.py`
**Lines:** 1271-1281 (updated)

**Before:**
```python
# Multi-project selection (if enabled and multiple repos available)
if allow_multiple and len(repo_options) > 1:
    if Confirm.ask("\nCreate multi-project session (analyze multiple repos)?", default=False):
        # User wants multi-project mode
        project_paths = prompt_multi_project_selection(repo_options, workspace_path, suggested_repo)
```

**After:**
```python
# Multi-project selection (if enabled and multiple repos available)
if allow_multiple and len(repo_options) > 1:
    # Display list of available repositories BEFORE asking multi-project question (Issue #216)
    console.print(f"\n[bold]Available repositories ({len(repo_options)}):[/bold]")
    for i, repo in enumerate(repo_options, 1):
        if suggested_repo and repo == suggested_repo:
            console.print(f"  {i}. {repo} [dim](suggested)[/dim]")
        else:
            console.print(f"  {i}. {repo}")

    if Confirm.ask("\nCreate multi-project session (analyze multiple repos)?", default=False):
        # User wants multi-project mode
        project_paths = prompt_multi_project_selection(repo_options, workspace_path, suggested_repo)
```

### New Test File
Created comprehensive test suite: `tests/test_issue_216_project_list_display.py`

**Tests:**
1. `test_project_list_displayed_before_multiproject_prompt` - Verifies list shown before prompt
2. `test_project_list_shows_count_and_numbers` - Verifies correct format matching `daf open`
3. `test_multiproject_selection_still_works_after_fix` - Ensures multi-project flow still works
4. `test_single_project_fallback_still_works` - Ensures single-project flow still works
5. `test_suggested_repo_marked_in_list` - Verifies suggested repos are marked

## Verification

### Automated Tests
All tests pass (30 tests total):
- ✅ `test_jira_new_multiproject.py` (4 tests)
- ✅ `test_git_new_multiproject.py` (6 tests)
- ✅ `test_investigate_command.py` (15 tests)
- ✅ `test_issue_216_project_list_display.py` (5 tests)

### Manual Testing
Created `manual_test_issue_216.py` to demonstrate the fix works as expected.

**Output shows:**
```
Scanning workspace: /path/to/workspace

Available repositories (2):
  1. devaiflow
  2. devaiflow-demos

Create multi-project session (analyze multiple repos)?  (n):
```

## Affected Commands
The fix applies to these commands:
- ✅ `daf jira new` - Uses `prompt_repository_selection_with_multiproject`
- ✅ `daf git new` - Uses `prompt_repository_selection_with_multiproject`
- ✅ `daf investigate` - Uses `prompt_repository_selection_with_multiproject`
- ✅ `daf open` - Already had correct behavior (unchanged)

## Acceptance Criteria Status

All acceptance criteria from the issue have been met:

- [x] Project list is displayed BEFORE the multi-project yes/no question
- [x] The displayed list shows "Available repositories (N):" with numbered projects matching `daf open` format
- [x] Multi-project prompt appears AFTER the project list is displayed
- [x] Existing multi-project selection behavior is preserved after the prompt
- [x] Existing single-project selection behavior is preserved when user declines
- [x] Fix is applied to `daf jira new` command
- [x] Fix is applied to `daf git new` command
- [x] Fix is applied to `daf investigate` command
- [x] `daf open` behavior remains unchanged (already correct)
- [x] End-to-end test passes: User sees projects before being asked about multi-project mode
- [x] No regression in existing multi-project or single-project workflows

## Impact
- **User Experience:** Users can now see which projects are available before deciding on multi-project mode
- **Consistency:** All commands now follow the same pattern as `daf open`
- **No Breaking Changes:** Existing workflows continue to work exactly as before
- **Test Coverage:** Added 5 new tests specifically for this issue

## Files Modified
1. `devflow/cli/utils.py` - Fixed `prompt_repository_selection_with_multiproject` function

## Files Added
1. `tests/test_issue_216_project_list_display.py` - Comprehensive test suite
2. `manual_test_issue_216.py` - Manual test demonstration
3. `ISSUE_216_FIX_SUMMARY.md` - This summary document
