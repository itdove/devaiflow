# JIRA Green Path Integration Test

## Overview

`test_jira_green_path.sh` is an automated integration test script that validates the main DevAIFlow workflow in mock mode. It tests the "green path" (happy path) scenario where all commands execute successfully.

## Purpose

This script provides:
- **Automated end-to-end testing** of core user workflows
- **Regression detection** for main workflow commands
- **Mock mode validation** without requiring production JIRA, GitHub, or GitLab access
- **Documentation by example** of the typical user workflow

## What It Tests

The script tests the following workflow sequence:

1. **`daf jira new`** - Create JIRA ticket with analysis session
2. **`daf jira update`** - Update ticket fields
3. **`daf open`** - Open and work on session
4. **`daf complete`** - Complete session workflow

### Note on `daf sync`

The `daf sync` test is currently **skipped** due to mock mode limitations:
- Mock JIRA's editable metadata doesn't include `sprint` and `story_points` fields
- These fields are required by `daf sync` filters to determine sync-eligibility
- This is a known limitation documented for future enhancement

## How to Run

### Basic Usage

```bash
./test_jira_green_path.sh
```

### Requirements

- DevAIFlow installed (`daf` command available)
- No special configuration needed - runs entirely in mock mode

### What Happens

1. **Clean start**: Purges all mock data (`daf purge-mock-data --force`)
2. **Test 1**: Creates a story ticket under PROJ-59038 with `daf jira new`
   - Extracts ticket key (e.g., PROJ-1) from command output
3. **Test 2**: Updates ticket description with `daf jira update`
   - Verifies update succeeded by viewing the ticket
4. **Test 3**: Opens the session with `daf open`
   - Uses session name (not ticket key, since `daf sync` was skipped)
5. **Test 4**: Completes the session with `daf complete`
   - Verifies session appears in completed status

## Mock Mode

The script runs entirely in mock mode by setting:

```bash
export DAF_MOCK_MODE=1
```

This ensures:
- No production data is affected
- No external services are required
- Data is isolated to `~/.daf-sessions/mocks/`
- Visual indicators ("⚠️ MOCK MODE ENABLED") prevent confusion

## Output

### Success Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Test Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tests Passed: 8 / 8

✓ All tests passed!

Successfully tested the workflow:
  ✓ daf jira new - Created ticket PROJ-1
  ✓ daf jira update - Updated ticket description
  ✓ daf open - Opened session (mock mode)
  ✓ daf complete - Completed session workflow
```

### Failure Output

If any test fails, the script:
- Displays a clear error message indicating which test failed
- Shows the expected vs actual values for verification failures
- Exits with code 1

## Technical Details

### JSON Parsing

The script uses Python for JSON parsing (more portable than `jq`):

```bash
# Helper function for JSON parsing
json_get() {
    local json="$1"
    local path="$2"
    echo "$json" | python3 -c "import sys, json; data=json.load(sys.stdin); print($path)" 2>/dev/null || echo ""
}
```

### Commands with JSON Support

The following commands support `--json` flag and are used by this test script:
- ✅ `daf list --json` - List sessions in JSON format (used for session verification)
- ✅ `daf jira view --json` - View JIRA ticket as JSON (used for field verification)
- ✅ `daf jira update --json` - Update JIRA ticket and get JSON response (used for update verification)
- ✅ `daf jira new --json` - Create JIRA ticket and get JSON response (fully implemented)
- ✅ `daf info --json` - Show session info as JSON
- ✅ `daf status --json` - Show status as JSON
- ✅ `daf active --json` - Show active session as JSON

### Ticket Key Extraction

The script uses `--json` and `--path` flags for reliable, machine-readable output:

```bash
# Run daf jira new with --json and --path flags
JIRA_NEW_JSON=$(daf jira new story --parent "$PARENT_TICKET" \
    --goal "$TEST_GOAL" --name "$TEST_NAME" --path "." --json 2>&1)
```

Then extracts the JIRA ticket key by parsing the JSON response:

```bash
TICKET_KEY=$(echo "$JIRA_NEW_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('success'):
        ticket_key = data.get('data', {}).get('ticket_key', '')
        print(ticket_key)
except:
    print('')
")
```

This parses the JSON structure:
```json
{
  "success": true,
  "data": {
    "ticket_key": "PROJ-1",
    "session_name": "test-feature",
    ...
  }
}
```

### Field Update Validation

The script validates field updates by:
1. Running `daf jira update` with new values
2. Fetching ticket with `daf jira view`
3. Grepping output for expected values (text-based parsing)

### Session Verification with JSON

The script uses `daf list --json` for reliable session verification:

```bash
SESSION_JSON=$(daf list --json 2>&1)
# Parse JSON with Python to find session by name
SESSION_COUNT=$(echo "$SESSION_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
sessions = data.get('data', {}).get('sessions', [])
for s in sessions:
    if s.get('name') == '$TEST_NAME':
        print('1')
        sys.exit(0)
print('0')
")
```

This is more reliable than text parsing and won't break if output formatting changes.

### Session Name vs Ticket Key

- `daf jira new` creates a session with a given `--name`
- Without `daf sync`, the session is not linked to the JIRA ticket key
- Therefore, `daf open` and `daf complete` use the session name, not the ticket key

## Known Limitations

1. **No `daf sync` test**: Sprint/story_points fields not available in mock editable metadata
2. **No field ID mapping test**: Field mappings are configured but not extensively tested

## Future Enhancements

### Completed
- ✅ **JSON support for `daf list`**: Now using `daf list --json` for reliable session verification
- ✅ **JSON support for `daf jira view`**: Now using `daf jira view --json` for field verification
- ✅ **JSON support for `daf jira update`**: Now using `daf jira update --json` for update validation
- ✅ **JSON support for `daf jira new`**: Fully implemented and used for ticket key extraction
- ✅ **Python-based JSON parsing**: No external dependencies (jq) required
- ✅ **Reliable ticket key extraction**: Using JSON parsing instead of text/sed patterns

### Pending

- Test `daf sync` workflow with proper field updates (when sprint/story_points become editable in mock)
- Add more comprehensive field validation tests using JSON data structures

## Related Files

- `devflow/cli/commands/jira_new_command.py` - Ticket creation logic
- `devflow/cli/commands/jira_update_command.py` - Update command with `--field` support
- `devflow/cli/commands/sync_command.py` - Sync filtering logic
- `devflow/mocks/jira_mock.py` - Mock JIRA client
- `devflow/jira/client.py` - Real JIRA client (sprint/story_points field references)
- `demos/scripts/simulate-jira-demo.sh` - Workflow reference

## Troubleshooting

### Script hangs on `daf jira new`

**Issue**: The command prompts for repository selection interactively.

**Solution**: The script provides input via `echo "1"` to select the first repository. Ensure you're running from a directory with a valid workspace configured, or the script will default to the current directory.

### Test fails with "Failed to extract ticket key from JSON"

**Issue**: The JSON response structure of `daf jira new --json` changed or is invalid.

**Solution**: Check the actual JSON output and verify the response structure. The test expects:
```json
{
  "success": true,
  "data": {
    "ticket_key": "PROJ-X",
    ...
  }
}
```

### `daf complete` prompts for input

**Issue**: Mock mode should skip prompts, but configuration may cause interactive behavior.

**Solution**: Ensure mock mode is properly enabled and check prompt defaults in config.

## Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed

## Integration with CI/CD

This script can be integrated into CI/CD pipelines:

```yaml
test:
  script:
    - chmod +x test_jira_green_path.sh
    - ./test_jira_green_path.sh
```

The script is self-contained and requires no external setup beyond having `daf` installed.
