# Known Bugs

## Integration Test Blockers (Parent: AAP-62787)

### AAP-63884: `daf open --json` prompts for interactive input

**Parent**: AAP-62787
**Status**: New
**Severity**: Medium
**Component**: CLI - open command
**Affects**: Test 7 (test_multi_repo.sh), CI/CD automation
**URL**: https://issues.redhat.com/browse/AAP-63884

### Description
The `daf open` command with `--json` flag still prompts for interactive user input, preventing non-interactive/automated usage.

### Current Behavior
When running `daf open <session> --path <path> --json`, the command prompts:
```
✓ Detected git repository
Create git branch for this session? [y/n] (y):
```

This causes the command to hang waiting for stdin input, even when `--json` flag is specified.

### Expected Behavior
When `--json` flag is used, the command should:
1. Not prompt for any interactive input
2. Use default values for all prompts (e.g., default "y" for branch creation)
3. Return pure JSON output without any console formatting

### Steps to Reproduce
```bash
export DAF_MOCK_MODE=1
export DEVAIFLOW_HOME="/tmp/daf-test"
mkdir -p "$DEVAIFLOW_HOME"

# Create session
cd /path/to/repo1
daf new --name "test-session" --goal "Test" --path "." --branch "test" --json
daf sync

# Try to open in another repo - this hangs
cd /path/to/repo2
daf open "test-session" --path "." --json
# Hangs waiting for input: "Create git branch for this session? [y/n] (y):"
```

### Impact
- Blocks integration test `test_multi_repo.sh` from completing
- Prevents use in CI/CD pipelines where stdin is not available
- Makes automated multi-repository workflows difficult to test

### Workaround
None found. Using `yes "y" | daf open --json` with timeout still hangs.

### Suggested Fix
In `devflow/cli/commands/open_command.py` (or wherever the branch prompt occurs):
1. Check if `output_json` mode is active
2. If JSON mode, skip all interactive prompts and use defaults
3. Ensure consistent behavior across all `--json` commands

### Related
- Similar issue was fixed for `daf new --json` which now properly suppresses console output
- All commands with `--json` flag should be non-interactive

---

### AAP-63885: `daf link` command has interactive prompt blocking automation

**Parent**: AAP-62787
**Status**: New
**Severity**: Medium
**Component**: CLI - link command
**Affects**: Test 8 (test_session_lifecycle.sh), session management automation
**URL**: https://issues.redhat.com/browse/AAP-63885

#### Description
The `daf link` command prompts for user confirmation when replacing an existing JIRA association, preventing non-interactive/automated usage.

#### Current Behavior
When running `daf link` on a session that already has a JIRA association, the command prompts:
```
⚠ Session group 'test-session' is already linked to PROJ-1
Replace PROJ-1 with PROJ-2? [y/n]:
```

This causes the command to hang waiting for stdin input.

#### Expected Behavior
The `daf link` command should support `--json` or `--force` flag to:
1. Skip interactive prompts and use default behavior
2. Return pure JSON output when `--json` is used
3. Allow automation in CI/CD pipelines

#### Code Location
`devflow/cli/commands/link_command.py:91`
```python
if not Confirm.ask(f"Replace {existing_jira} with {issue_key}?", default=False):
    console.print("[dim]Link operation cancelled[/dim]")
    sys.exit(0)
```

#### Impact
- Blocks integration test `test_session_lifecycle.sh` from completing
- Prevents automated session management workflows
- Makes CI/CD pipeline integration difficult

---

### AAP-63886: Investigation sessions created with `daf investigate` do not appear in `daf list`

**Parent**: AAP-62787
**Status**: New
**Severity**: Medium
**Component**: CLI - investigate/list commands
**Affects**: Test 9 (test_investigation.sh), session discovery
**URL**: https://issues.redhat.com/browse/AAP-63886

#### Description
Sessions created using the `daf investigate` command are not displayed when running `daf list`, making them invisible to users.

#### Current Behavior
When running `daf list` after creating an investigation session:
- Investigation session does not appear in the session list
- `daf list` output is empty or shows only other session types
- Session metadata is created (verified with direct file inspection)
- Session can be accessed by name with `daf open spike-redis-cache`

#### Expected Behavior
Investigation sessions created with `daf investigate` should:
1. Appear in `daf list` output
2. Show session type as "investigation" or similar indicator
3. Be displayed alongside regular sessions
4. Support all standard listing filters (`--all`, `--status`, etc.)

#### Code Location
Test failure: `integration-tests/test_investigation.sh:230-236`

#### Possible Root Causes
- Session listing query filters out investigation type
- Investigation sessions not properly indexed
- Display logic skips investigation sessions
- Session type field not set correctly during `daf investigate`

#### Impact
- Blocks integration test `test_investigation.sh` from completing
- Users cannot see their investigation sessions in the list
- Makes session discovery and management difficult

---

### AAP-63887: `daf open` does not fail with proper exit code for non-existent sessions

**Parent**: AAP-62787
**Status**: New
**Severity**: Medium
**Component**: CLI - error handling
**Affects**: Test 10 (test_error_handling.sh), automation reliability
**URL**: https://issues.redhat.com/browse/AAP-63887

#### Description
The `daf open` command does not exit with a non-zero exit code when attempting to open a non-existent session. This breaks error handling validation and prevents proper automation failure detection.

#### Current Behavior
When running `daf open` with a non-existent session:
- Command either succeeds (exit code 0) or prompts for input
- No clear error message indicating session not found
- Automated scripts cannot detect the failure condition

#### Expected Behavior
The `daf open` command should:
1. Exit with non-zero exit code (1) when session does not exist
2. Display clear error message: "Session 'name' not found"
3. Not prompt for any input when session doesn't exist
4. Behavior should be consistent across all session lookup commands

#### Code Location
Test failure: `integration-tests/test_error_handling.sh:136-138`

#### Affected Commands
The same issue may affect other commands:
- `daf info <non-existent>` - should fail with non-zero exit code
- `daf delete <non-existent>` - should fail with non-zero exit code
- `daf complete <non-existent>` - should fail with non-zero exit code
- `daf note <non-existent>` - should fail with non-zero exit code

#### Impact
- Blocks integration test `test_error_handling.sh` from completing
- Prevents proper error detection in automation scripts
- Makes CI/CD pipeline failure detection unreliable
- Inconsistent with standard CLI error handling patterns
