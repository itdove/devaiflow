# DevAIFlow Integration Tests

This directory contains end-to-end integration tests for DevAIFlow. These tests validate complete workflows using mock mode (`DAF_MOCK_MODE=1`) without requiring access to production services.

## Quick Start

### Run All Tests

```bash
# Normal mode
./run_all_integration_tests.sh

# Debug mode (verbose bash output)
./run_all_integration_tests.sh --debug
```

**Output**: Test results are saved to `/tmp/daf_integration_tests_YYYYMMDD_HHMMSS.log`

### Run Individual Tests

```bash
# Individual tests can be run directly
./test_jira_green_path.sh
./test_time_tracking.sh
# etc.
```

## Can I Run Tests Inside Claude Code?

**Yes!** The test runner script (`run_all_integration_tests.sh`) can be run from inside Claude Code sessions.

**How it works:**
- Automatically unsets `DEVAIFLOW_IN_SESSION` to bypass safety guards
- Automatically unsets `AI_AGENT_SESSION_ID` to isolate from parent session
- Sets `DEVAIFLOW_HOME` to `/tmp/daf-integration-tests-$$` for data isolation
- Restores original environment variables on exit
- Cleans up temporary data directory

This ensures integration tests don't interfere with your actual session.

**Note**: Individual test scripts require running outside Claude Code unless you manually set up the isolated environment.

## Available Tests

| Test Script | Description | Test Scenarios |
|------------|-------------|----------------|
| `test_jira_green_path.sh` | Complete JIRA workflow | JIRA ticket creation → update → session open → complete |
| `test_collaboration_workflow.sh` | Export/import and multi-session | Developer A exports session → Developer B imports and continues |
| `test_time_tracking.sh` | Time tracking features | Auto-start, pause/resume, time command, multiple cycles |
| `test_templates.sh` | Template system | Save template, list, use, reuse, error handling, deletion |
| `test_jira_sync.sh` | JIRA sync features | Sprint sync, ticket sync, session creation, status dashboard |
| `test_readonly_commands.sh` | Read-only commands | Commands that work inside Claude Code (list, info, status, etc.) |
| `test_multi_repo.sh` | Multi-repository workflow | Cross-repo features, conversation isolation, session info |
| `test_session_lifecycle.sh` | Session lifecycle | Create, link to JIRA, unlink, delete operations |
| `test_investigation.sh` | Investigation-only sessions | Read-only mode, no branch creation, research workflow |
| `test_error_handling.sh` | Error handling and validation | Non-existent sessions, invalid inputs, edge cases |

## Test Runner Features

- ✅ Runs all 10 integration tests in sequence
- ✅ Fails fast (exits on first test failure)
- ✅ Debug mode with `--debug` flag (enables `set -x`)
- ✅ Timestamped output to `/tmp` for easy sharing
- ✅ Pre-flight checks to verify all test files exist
- ✅ Color-coded output with progress indicators
- ✅ Final summary showing passed/failed counts and duration
- ✅ Environment isolation for running inside Claude Code
- ✅ Automatic cleanup of temporary data

## Manual Environment Isolation

If you want to run individual test scripts inside an AI agent session:

```bash
# Save original environment
ORIGINAL_DEVAIFLOW_IN_SESSION="${DEVAIFLOW_IN_SESSION:-}"
ORIGINAL_AI_AGENT_SESSION_ID="${AI_AGENT_SESSION_ID:-}"
ORIGINAL_DEVAIFLOW_HOME="${DEVAIFLOW_HOME:-}"

# Set up isolation
unset DEVAIFLOW_IN_SESSION
unset AI_AGENT_SESSION_ID
export DEVAIFLOW_HOME="/tmp/daf-test-$$"

# Run individual test
./test_jira_green_path.sh

# Restore environment
if [ -n "$ORIGINAL_DEVAIFLOW_IN_SESSION" ]; then
    export DEVAIFLOW_IN_SESSION="$ORIGINAL_DEVAIFLOW_IN_SESSION"
fi
if [ -n "$ORIGINAL_AI_AGENT_SESSION_ID" ]; then
    export AI_AGENT_SESSION_ID="$ORIGINAL_AI_AGENT_SESSION_ID"
fi
if [ -n "$ORIGINAL_DEVAIFLOW_HOME" ]; then
    export DEVAIFLOW_HOME="$ORIGINAL_DEVAIFLOW_HOME"
else
    unset DEVAIFLOW_HOME
fi

# Clean up
rm -rf "/tmp/daf-test-$$"
```

## Test Structure

All integration tests follow a common pattern:

1. **Setup**: Enable mock mode, define colors and test counters
2. **Cleanup**: Purge mock data and initialize configuration
3. **Test Sections**: Organized sections with descriptive headers
4. **Verification**: `verify_success()` or `verify_failure()` for each test
5. **Summary**: Final report with passed/failed counts

Example:
```bash
#!/bin/bash
set -e  # Exit on first error
export DAF_MOCK_MODE=1

# ... setup colors and counters ...

print_test "Create JIRA ticket"
TICKET_JSON=$(daf jira new story --goal "Test" --name "test" --json 2>&1)
verify_success "daf jira new" "Ticket created successfully"

# ... more tests ...

print_section "Test Summary"
echo "Tests Passed: ${TESTS_PASSED} / ${TESTS_TOTAL}"
```

## Collaboration Workflow Test

The collaboration workflow test (`test_collaboration_workflow.sh`) has additional features:

### Demo Mode

```bash
# Run with pauses between steps for demonstration
DEMO_MODE=1 ./test_collaboration_workflow.sh
```

### What it tests

- Developer A creates a JIRA ticket and session
- Developer A makes code changes and commits
- Developer A exports session with full context
- Developer B imports the session in a separate environment
- Developer B continues work seamlessly
- All session data is preserved (conversation, git, notes, metadata)

### Manual Testing Guide

See [TEST_COLLABORATION_SCENARIO.md](TEST_COLLABORATION_SCENARIO.md) for a complete step-by-step manual testing guide.

## Troubleshooting

### Tests fail with "command not found"
Make sure you're in the `integration-tests/` directory:
```bash
cd integration-tests
./run_all_integration_tests.sh
```

### Tests fail with safety guard errors
If running individual tests outside the test runner, make sure you've exited Claude Code or set up environment isolation as shown above.

### Tests fail with permission errors
Make sure test scripts are executable:
```bash
chmod +x *.sh
```

### Output file location
Test output is saved to `/tmp/daf_integration_tests_<timestamp>.log`. You can easily share this file for debugging:
```bash
# Find the latest log
ls -lt /tmp/daf_integration_tests_*.log | head -1

# View the latest log
cat $(ls -t /tmp/daf_integration_tests_*.log | head -1)
```

### AI_AGENT_SESSION_ID concerns

**Q**: Won't unsetting `AI_AGENT_SESSION_ID` break the `daf active` command?

**A**: No, it's safe because:
- Integration tests create their own test sessions in mock mode
- `test_readonly_commands.sh` explicitly sets its own `AI_AGENT_SESSION_ID` for testing
- No tests rely on preserving the original `AI_AGENT_SESSION_ID` from the parent session

## Test Environment

All tests use:
- **Mock mode** (`DAF_MOCK_MODE=1`) for isolated testing without external dependencies
- **Temporary directories** for security and isolation
- **Separate DEVAIFLOW_HOME** to avoid interfering with actual sessions
- **Automatic cleanup** to remove all test data after completion

## Contributing

When adding new integration tests:

1. Follow the existing test structure pattern
2. Use mock mode (`export DAF_MOCK_MODE=1`)
3. Include descriptive section headers and test names
4. Add verification for each operation
5. Update `run_all_integration_tests.sh` to include your test:
   - Add to `TESTS` array
   - Add description to `TEST_DESCRIPTIONS` array
6. Update the test list in `AGENTS.md`
7. Update this README with the new test description

Example pattern:
```bash
#!/bin/bash
set -e
export DAF_MOCK_MODE=1

# Colors and counters...
TESTS_PASSED=0
TESTS_TOTAL=0

# Helper functions
print_section() { ... }
print_test() { TESTS_TOTAL=$((TESTS_TOTAL + 1)); ... }
verify_success() { TESTS_PASSED=$((TESTS_PASSED + 1)); ... }

# Main execution
print_section "Test Name"
# ... tests ...

# Summary
print_section "Test Summary"
echo "Tests Passed: ${TESTS_PASSED} / ${TESTS_TOTAL}"
```

## Related Documentation

- [AGENTS.md](../AGENTS.md) - Testing guidelines and integration test reference
- [TEST_COLLABORATION_SCENARIO.md](TEST_COLLABORATION_SCENARIO.md) - Manual collaboration testing guide
- [../docs/07-commands.md](../docs/07-commands.md) - Command reference
- [../DEMO_SCENARIOS.md](../DEMO_SCENARIOS.md) - Demo scenarios
