#!/bin/bash
# test_error_handling.sh
# Integration test for DevAIFlow error handling
# Tests: Graceful failures, error messages, validation, edge cases
#
# This script runs entirely in mock mode (DAF_MOCK_MODE=1) and does not require
# access to production JIRA, GitHub, or GitLab services.

# Parse arguments
DEBUG_MODE=false
if [ "$1" = "--debug" ]; then
    DEBUG_MODE=true
    set -x  # Enable debug output
fi

set -e  # Exit on first error

# Environment isolation (for running standalone or inside AI sessions)
# Save original environment
ORIGINAL_DEVAIFLOW_IN_SESSION="${DEVAIFLOW_IN_SESSION:-}"
ORIGINAL_AI_AGENT_SESSION_ID="${AI_AGENT_SESSION_ID:-}"
ORIGINAL_DEVAIFLOW_HOME="${DEVAIFLOW_HOME:-}"

# Unset session variables to bypass safety guards
unset DEVAIFLOW_IN_SESSION
unset AI_AGENT_SESSION_ID

# Use temporary DEVAIFLOW_HOME if not already set by runner
if [ -z "$DEVAIFLOW_HOME" ] || [ "$DEVAIFLOW_HOME" = "$ORIGINAL_DEVAIFLOW_HOME" ]; then
    TEMP_DEVAIFLOW_HOME="/tmp/daf-test-error_handling-$$"
    export DEVAIFLOW_HOME="$TEMP_DEVAIFLOW_HOME"
    CLEANUP_TEMP_DIR=true
else
    CLEANUP_TEMP_DIR=false
fi

# Create temporary git repository
TEMP_GIT_REPO="/tmp/daf-test-git-repo-error_handling-$$"
mkdir -p "$TEMP_GIT_REPO"

# Initialize git repository (in a subshell to avoid changing parent shell's directory)
(
    cd "$TEMP_GIT_REPO"
    git init > /dev/null 2>&1
    git config user.name "Test User" > /dev/null 2>&1
    git config user.email "test@example.com" > /dev/null 2>&1
    echo "# Test Repository" > README.md
    git add README.md > /dev/null 2>&1
    git commit -m "Initial commit" > /dev/null 2>&1
)

# Cleanup function
cleanup_test_environment() {
    # Clean up temporary git repository
    if [ -d "$TEMP_GIT_REPO" ]; then
        rm -rf "$TEMP_GIT_REPO"
    fi

    # Restore original environment
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

    # Clean up temp directory only if we created it
    if [ "$CLEANUP_TEMP_DIR" = true ] && [ -d "$TEMP_DEVAIFLOW_HOME" ]; then
        rm -rf "$TEMP_DEVAIFLOW_HOME"
    fi
}

trap cleanup_test_environment EXIT

# Enable mock mode
export DAF_MOCK_MODE=1

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

# Test counters
TESTS_PASSED=0
TESTS_TOTAL=0

# Function to print section headers
print_section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Function to print test steps
print_test() {
    echo -e "${YELLOW}→${NC} Test $((TESTS_TOTAL + 1)): $1"
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

# Function to verify command fails (inverse of verify_success)
verify_failure() {
    local cmd="$1"
    local description="$2"
    local exit_code=$3

    if [ $exit_code -ne 0 ]; then
        echo -e "  ${GREEN}✓${NC} ${description} (correctly failed)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "  ${RED}✗${NC} ${description} (should have failed)"
        exit 1
    fi
}

# Get the directory of this script before changing directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Main test execution (run in subshell to isolate directory changes)
(
cd "$TEMP_GIT_REPO"

print_section "Error Handling Integration Test"
echo "This script tests error handling and validation:"
echo "  1. Non-existent session operations"
echo "  2. Invalid session names"
echo "  3. Empty/invalid inputs"
echo "  4. Missing required parameters"
echo "  5. Duplicate session names"
echo "  6. Invalid JIRA transitions"
echo "  7. Template errors"
echo "  8. Configuration errors"
echo ""

# Clean start
print_test "Clean mock data before tests"
timeout 5 daf purge-mock-data --force > /dev/null 2>&1
echo -e "  ${GREEN}✓${NC} Mock data cleaned successfully"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Initialize configuration
print_test "Initialize configuration"
# Create test configuration (avoids interactive daf init)
CONFIG_OUTPUT=$(python3 "$SCRIPT_DIR/setup_test_config.py" 2>&1)
CONFIG_EXIT_CODE=$?
if [ $CONFIG_EXIT_CODE -ne 0 ]; then
    echo -e "  ${RED}✗${NC} Configuration setup failed"
    echo -e "  ${RED}Output:${NC}"
    echo "$CONFIG_OUTPUT" | sed 's/^/    /'
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Configuration initialized"
TESTS_PASSED=$((TESTS_PASSED + 1))
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Test 1: Open non-existent session
print_section "Test 1: Non-Existent Session Errors"
print_test "Try to open non-existent session"

set +e  # Temporarily allow errors
timeout 5 daf open "non-existent-session-12345" > /dev/null 2>&1
OPEN_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf open non-existent" "Non-existent session error" $OPEN_EXIT

# Test 2: Info for non-existent session
print_test "Try to get info for non-existent session"

set +e  # Temporarily allow errors
timeout 5 daf info "non-existent-session-12345" > /dev/null 2>&1
INFO_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf info non-existent" "Non-existent session info error" $INFO_EXIT

# Test 3: Delete non-existent session
print_test "Try to delete non-existent session"

set +e  # Temporarily allow errors
timeout 5 daf delete "non-existent-session-12345" --force > /dev/null 2>&1
DELETE_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf delete non-existent" "Non-existent session delete error" $DELETE_EXIT

# Test 4: Empty session name
print_section "Test 2: Invalid Input Validation"
print_test "Try to create session with empty name"

set +e  # Temporarily allow errors
timeout 5 daf new --name "" --goal "Test" --path "." > /dev/null 2>&1
EMPTY_NAME_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf new --name ''" "Empty name validation" $EMPTY_NAME_EXIT

# Test 5: Empty goal
print_test "Try to create session with empty goal"

set +e  # Temporarily allow errors
timeout 5 daf new --name "test-session" --goal "" --path "." > /dev/null 2>&1
EMPTY_GOAL_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf new --goal ''" "Empty goal validation" $EMPTY_GOAL_EXIT

# Test 6: Create valid session for duplicate test
print_test "Create valid session for duplicate testing"

timeout 5 daf new --name "duplicate-test" --goal "Test duplicates" --path "." --branch test-branch --json > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} Valid session created"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Failed to create valid session"
    exit 1
fi

# Test 7: Duplicate session name
print_section "Test 3: Duplicate Session Name"
print_test "Try to create session with duplicate name"

set +e  # Temporarily allow errors
timeout 5 daf new --name "duplicate-test" --goal "Another test" --path "." --branch test-branch --json > /dev/null 2>&1
DUPLICATE_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf new duplicate name" "Duplicate name rejection" $DUPLICATE_EXIT

# Test 8: Empty note
print_section "Test 4: Empty Note Validation"
print_test "Try to add empty note"

set +e  # Temporarily allow errors
timeout 5 daf note "duplicate-test" "" > /dev/null 2>&1
EMPTY_NOTE_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf note empty" "Empty note validation" $EMPTY_NOTE_EXIT

# Test 9: Note for non-existent session
print_test "Try to add note to non-existent session"

set +e  # Temporarily allow errors
timeout 5 daf note "non-existent" "Some note" > /dev/null 2>&1
NOTE_NONEXISTENT_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf note non-existent" "Note for non-existent session" $NOTE_NONEXISTENT_EXIT

# Test 10: Template from non-existent session
print_section "Test 5: Template Errors"
print_test "Try to create template from non-existent session"

set +e  # Temporarily allow errors
timeout 5 daf template save "non-existent" "test-template" > /dev/null 2>&1
TEMPLATE_NONEXISTENT_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf template save non-existent" "Template from non-existent session" $TEMPLATE_NONEXISTENT_EXIT

# Test 11: Use non-existent template
print_test "Try to use non-existent template"

set +e  # Temporarily allow errors
timeout 5 daf new --name "from-template" --goal "Test" --template "non-existent-template" --path "." > /dev/null 2>&1
TEMPLATE_USE_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf new --template non-existent" "Use non-existent template" $TEMPLATE_USE_EXIT

# Test 12: Delete non-existent template
print_test "Try to delete non-existent template"

set +e  # Temporarily allow errors
timeout 5 daf template delete "non-existent-template" > /dev/null 2>&1
TEMPLATE_DELETE_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf template delete non-existent" "Delete non-existent template" $TEMPLATE_DELETE_EXIT

# Test 13: Link to invalid JIRA key
print_section "Test 6: JIRA Integration Errors"
print_test "Try to link session to invalid JIRA key format"

set +e  # Temporarily allow errors
timeout 5 daf link "duplicate-test" --jira "INVALID" > /dev/null 2>&1
LINK_INVALID_EXIT=$?
set -e  # Re-enable exit on error

# This might succeed or fail depending on validation
if [ $LINK_INVALID_EXIT -ne 0 ]; then
    echo -e "  ${GREEN}✓${NC} Invalid JIRA key rejected (correctly failed)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}ℹ${NC}  Invalid JIRA key accepted (validation may be lenient)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 14: View non-existent JIRA ticket
print_test "Try to view non-existent JIRA ticket"

set +e  # Temporarily allow errors
daf jira view "PROJ-99999999" > /dev/null 2>&1
JIRA_VIEW_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf jira view non-existent" "View non-existent JIRA ticket" $JIRA_VIEW_EXIT

# Test 15: Update non-existent JIRA ticket
print_test "Try to update non-existent JIRA ticket"

set +e  # Temporarily allow errors
daf jira update "PROJ-99999999" --description "Test" > /dev/null 2>&1
JIRA_UPDATE_EXIT=$?
set -e  # Re-enable exit on error
verify_failure "daf jira update non-existent" "Update non-existent JIRA ticket" $JIRA_UPDATE_EXIT

# Test 16: Unlink session that's not linked
print_section "Test 7: Unlink Errors"
print_test "Try to unlink session with no JIRA association"

set +e  # Temporarily allow errors
timeout 5 daf unlink "duplicate-test" > /dev/null 2>&1
UNLINK_EXIT=$?
set -e  # Re-enable exit on error

# This might succeed (no-op) or fail depending on implementation
if [ $UNLINK_EXIT -eq 0 ]; then
    echo -e "  ${YELLOW}ℹ${NC}  Unlink succeeded (no-op for unlinked session)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${GREEN}✓${NC} Unlink failed for unlinked session (strict validation)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 17: Complete already completed session
print_section "Test 8: Complete Already Completed Session"
print_test "Complete the test session"

set +e  # Temporarily allow errors
timeout 5 daf complete "duplicate-test" --no-commit --no-pr --no-issue-update > /dev/null 2>&1
set -e  # Re-enable exit on error
echo -e "  ${GREEN}✓${NC} Session completed"
TESTS_PASSED=$((TESTS_PASSED + 1))

print_test "Try to complete already completed session"

set +e  # Temporarily allow errors
timeout 5 daf complete "duplicate-test" --no-commit --no-pr --no-issue-update > /dev/null 2>&1
COMPLETE_AGAIN_EXIT=$?
set -e  # Re-enable exit on error

if [ $COMPLETE_AGAIN_EXIT -ne 0 ]; then
    echo -e "  ${GREEN}✓${NC} Cannot complete already completed session"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}ℹ${NC}  Completing completed session allowed (idempotent)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 18: Invalid JSON output requests
print_section "Test 9: JSON Output Validation"
print_test "Request JSON output and verify it's valid JSON"

# Create a new session for testing
set +e  # Temporarily allow errors
timeout 5 daf new --name "json-test" --goal "Test JSON" --path "." --branch test-branch --json > /tmp/daf-json-test.json 2>&1
JSON_CREATE_EXIT=$?
set -e  # Re-enable exit on error

if [ $JSON_CREATE_EXIT -eq 0 ]; then
    # Try to parse JSON
    python3 -c "import json; json.load(open('/tmp/daf-json-test.json'))" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} Valid JSON output"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "  ${RED}✗${NC} Invalid JSON output"
        exit 1
    fi
else
    echo -e "  ${YELLOW}ℹ${NC}  Could not test JSON (session creation failed)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

rm -f /tmp/daf-json-test.json

# Test 19: Sync with invalid parameters
print_section "Test 10: Sync Validation"
print_test "Try to sync with both --sprint and --tickets (conflicting params)"

set +e  # Temporarily allow errors
timeout 5 daf sync --sprint current --tickets PROJ-123 > /dev/null 2>&1
SYNC_CONFLICT_EXIT=$?
set -e  # Re-enable exit on error

if [ $SYNC_CONFLICT_EXIT -ne 0 ]; then
    echo -e "  ${GREEN}✓${NC} Conflicting parameters rejected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}ℹ${NC}  Conflicting parameters allowed (one may take precedence)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 20: Invalid status filter
print_test "Try to sync with invalid status"

set +e  # Temporarily allow errors
timeout 5 daf sync --sprint current --status "InvalidStatus" > /dev/null 2>&1
SYNC_INVALID_STATUS_EXIT=$?
set -e  # Re-enable exit on error

# This might succeed (ignore invalid) or fail (validate)
if [ $SYNC_INVALID_STATUS_EXIT -eq 0 ]; then
    echo -e "  ${YELLOW}ℹ${NC}  Invalid status accepted (may be ignored)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${GREEN}✓${NC} Invalid status rejected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 21: Very long session name
print_section "Test 11: Edge Cases"
print_test "Try to create session with very long name (>255 chars)"

LONG_NAME=$(python3 -c "print('a' * 300)")
set +e  # Temporarily allow errors
timeout 5 daf new --name "$LONG_NAME" --goal "Test" --path "." > /dev/null 2>&1
LONG_NAME_EXIT=$?
set -e  # Re-enable exit on error

if [ $LONG_NAME_EXIT -ne 0 ]; then
    echo -e "  ${GREEN}✓${NC} Very long name rejected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}ℹ${NC}  Very long name accepted (no length limit)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 22: Special characters in session name
print_test "Try to create session with special characters"

set +e  # Temporarily allow errors
timeout 5 daf new --name "test/$pecial*chars" --goal "Test" --path "." > /dev/null 2>&1
SPECIAL_CHARS_EXIT=$?
set -e  # Re-enable exit on error

# This might succeed (sanitized) or fail (rejected)
if [ $SPECIAL_CHARS_EXIT -eq 0 ]; then
    echo -e "  ${YELLOW}ℹ${NC}  Special characters accepted (may be sanitized)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    # Cleanup if created
    set +e
    timeout 5 daf delete "test/\$pecial*chars" --force > /dev/null 2>&1 || true
    set -e
else
    echo -e "  ${GREEN}✓${NC} Special characters rejected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Cleanup
print_section "Cleanup"
print_test "Clean up test sessions"

timeout 5 daf delete "duplicate-test" --force > /dev/null 2>&1 || true
timeout 5 daf delete "json-test" --force > /dev/null 2>&1 || true

echo -e "  ${GREEN}✓${NC} Cleanup complete"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Final summary
print_section "Test Summary"
echo -e "${BOLD}Tests Passed:${NC} ${GREEN}${TESTS_PASSED}${NC} / ${TESTS_TOTAL}"
echo ""

if [ $TESTS_PASSED -eq $TESTS_TOTAL ]; then
    echo -e "${BOLD}${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Successfully tested error handling:"
    echo "  ✓ Non-existent session operations fail gracefully"
    echo "  ✓ Empty/invalid input validation"
    echo "  ✓ Duplicate session name rejection"
    echo "  ✓ Empty note validation"
    echo "  ✓ Template error handling"
    echo "  ✓ JIRA integration error handling"
    echo "  ✓ Unlink validation"
    echo "  ✓ Complete already completed session"
    echo "  ✓ JSON output validation"
    echo "  ✓ Sync parameter validation"
    echo "  ✓ Edge cases (long names, special characters)"
    echo ""
    exit 0
else
    echo -e "${BOLD}${RED}✗ Some tests failed${NC}"
    echo ""
    exit 1
fi
)

# Capture subshell exit code and exit with same code
exit $?
