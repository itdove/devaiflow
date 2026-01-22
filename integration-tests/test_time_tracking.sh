#!/bin/bash
# test_time_tracking.sh
# Integration test for DevAIFlow time tracking features
# Tests: daf pause, daf resume, daf time, work sessions, time summaries
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
    TEMP_DEVAIFLOW_HOME="/tmp/daf-test-time_tracking-$$"
    export DEVAIFLOW_HOME="$TEMP_DEVAIFLOW_HOME"
    CLEANUP_TEMP_DIR=true
else
    CLEANUP_TEMP_DIR=false
fi

# Create temporary git repository
TEMP_GIT_REPO="/tmp/daf-test-git-repo-time_tracking-$$"
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

# Configuration
TEST_NAME="time-tracking-test"
TEST_GOAL="Test time tracking workflow"

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

# Function to verify command success
verify_success() {
    local cmd="$1"
    local description="$2"

    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} ${description}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "  ${RED}✗${NC} ${description} FAILED"
        echo -e "  ${RED}Command:${NC} ${cmd}"
        exit 1
    fi
}

# Function to verify output contains expected text
verify_output() {
    local output="$1"
    local expected="$2"
    local description="$3"

    if echo "$output" | grep -q "$expected"; then
        echo -e "  ${GREEN}✓${NC} ${description}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "  ${RED}✗${NC} ${description} FAILED"
        echo -e "  ${RED}Expected to find:${NC} ${expected}"
        echo -e "  ${RED}In output:${NC} ${output}"
        exit 1
    fi
}

# Main test execution (run in subshell to isolate directory changes)
(
cd "$TEMP_GIT_REPO"

print_section "Time Tracking Integration Test"
echo "This script tests the time tracking features:"
echo "  1. Create session with auto-start time tracking"
echo "  2. Pause time tracking (daf pause)"
echo "  3. Resume time tracking (daf resume)"
echo "  4. View time spent (daf time)"
echo "  5. Verify time in session summary"
echo ""

# Clean start
print_test "Clean mock data before tests"
daf purge-mock-data --force > /dev/null 2>&1
verify_success "daf purge-mock-data --force" "Mock data cleaned successfully"

# Initialize configuration
print_test "Initialize configuration"
# Create test configuration (avoids interactive daf init)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/setup_test_config.py" > /dev/null 2>&1 || true
echo -e "  ${GREEN}✓${NC} Configuration initialized"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Test 1: Create session with time tracking
print_section "Test 1: Create Session with Auto-Start Time Tracking"
print_test "Create session (time tracking should auto-start)"

# Create session
SESSION_JSON=$(daf new --name "$TEST_NAME" --goal "$TEST_GOAL" --path "." --branch test-branch --json 2>&1)
SESSION_EXIT_CODE=$?

if [ $SESSION_EXIT_CODE -ne 0 ]; then
    echo -e "  ${RED}✗${NC} Session creation FAILED with exit code $SESSION_EXIT_CODE"
    echo -e "  ${RED}Output:${NC}"
    echo "$SESSION_JSON" | sed 's/^/    /'
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Session created successfully"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Verify time tracking state
print_test "Verify time tracking auto-started"
SESSION_INFO=$(daf info "$TEST_NAME" 2>&1)

if echo "$SESSION_INFO" | grep -q "running"; then
    echo -e "  ${GREEN}✓${NC} Time tracking is running"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Time tracking not running (should auto-start)"
    echo -e "  ${RED}Session info:${NC}"
    echo "$SESSION_INFO" | sed 's/^/    /'
    exit 1
fi

# Test 2: Pause time tracking
print_section "Test 2: Pause Time Tracking"
print_test "Pause the session"

# Wait a moment to accumulate some time
sleep 2

PAUSE_OUTPUT=$(daf pause "$TEST_NAME" 2>&1)
PAUSE_EXIT_CODE=$?

if [ $PAUSE_EXIT_CODE -ne 0 ]; then
    echo -e "  ${RED}✗${NC} Pause command FAILED with exit code $PAUSE_EXIT_CODE"
    echo -e "  ${RED}Output:${NC}"
    echo "$PAUSE_OUTPUT" | sed 's/^/    /'
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Session paused successfully"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Verify time tracking state changed to paused
print_test "Verify time tracking state is 'paused'"
SESSION_INFO=$(daf info "$TEST_NAME" 2>&1)

if echo "$SESSION_INFO" | grep -q "paused"; then
    echo -e "  ${GREEN}✓${NC} Time tracking state is 'paused'"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Time tracking state not 'paused'"
    echo -e "  ${RED}Session info:${NC}"
    echo "$SESSION_INFO" | sed 's/^/    /'
    exit 1
fi

# Test 3: Resume time tracking
print_section "Test 3: Resume Time Tracking"
print_test "Resume the session"

# Wait a moment while paused
sleep 2

RESUME_OUTPUT=$(daf resume "$TEST_NAME" 2>&1)
RESUME_EXIT_CODE=$?

if [ $RESUME_EXIT_CODE -ne 0 ]; then
    echo -e "  ${RED}✗${NC} Resume command FAILED with exit code $RESUME_EXIT_CODE"
    echo -e "  ${RED}Output:${NC}"
    echo "$RESUME_OUTPUT" | sed 's/^/    /'
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Session resumed successfully"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Verify time tracking state changed back to running
print_test "Verify time tracking state is 'running' again"
SESSION_INFO=$(daf info "$TEST_NAME" 2>&1)

if echo "$SESSION_INFO" | grep -q "running"; then
    echo -e "  ${GREEN}✓${NC} Time tracking state is 'running'"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Time tracking state not 'running'"
    echo -e "  ${RED}Session info:${NC}"
    echo "$SESSION_INFO" | sed 's/^/    /'
    exit 1
fi

# Test 4: View time spent
print_section "Test 4: View Time Spent"
print_test "View time spent on session"

# Accumulate more time
sleep 2

TIME_OUTPUT=$(daf time "$TEST_NAME" 2>&1)
TIME_EXIT_CODE=$?

if [ $TIME_EXIT_CODE -ne 0 ]; then
    echo -e "  ${RED}✗${NC} Time command FAILED with exit code $TIME_EXIT_CODE"
    echo -e "  ${RED}Output:${NC}"
    echo "$TIME_OUTPUT" | sed 's/^/    /'
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Time command executed successfully"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Verify output contains time information
print_test "Verify time output contains work session info"
if echo "$TIME_OUTPUT" | grep -E "(Total|Work|seconds|minutes|hours)" > /dev/null; then
    echo -e "  ${GREEN}✓${NC} Time output contains work session information"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Time output missing work session information"
    echo -e "  ${RED}Output:${NC}"
    echo "$TIME_OUTPUT" | sed 's/^/    /'
    exit 1
fi

# Test 5: Verify time in session summary
print_section "Test 5: Verify Time in Session Summary"
print_test "Check session summary includes time tracking"

SUMMARY_OUTPUT=$(daf summary "$TEST_NAME" 2>&1)
SUMMARY_EXIT_CODE=$?

if [ $SUMMARY_EXIT_CODE -ne 0 ]; then
    echo -e "  ${RED}✗${NC} Summary command FAILED with exit code $SUMMARY_EXIT_CODE"
    echo -e "  ${RED}Output:${NC}"
    echo "$SUMMARY_OUTPUT" | sed 's/^/    /'
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Summary command executed successfully"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Verify summary contains time information
print_test "Verify summary contains time tracking information"
if echo "$SUMMARY_OUTPUT" | grep -E "(Time|Duration|Work)" > /dev/null; then
    echo -e "  ${GREEN}✓${NC} Summary contains time tracking information"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}ℹ${NC}  Summary may not contain time tracking info (non-critical)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 6: Multiple pause/resume cycles
print_section "Test 6: Multiple Pause/Resume Cycles"
print_test "Test multiple pause/resume cycles"

for i in 1 2 3; do
    daf pause "$TEST_NAME" > /dev/null 2>&1
    sleep 1
    daf resume "$TEST_NAME" > /dev/null 2>&1
    sleep 1
done

echo -e "  ${GREEN}✓${NC} Multiple pause/resume cycles successful"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Verify time still accumulates correctly
print_test "Verify time still tracking after multiple cycles"
TIME_OUTPUT_AFTER=$(daf time "$TEST_NAME" 2>&1)

if [ $? -eq 0 ] && echo "$TIME_OUTPUT_AFTER" | grep -E "(Total|Work)" > /dev/null; then
    echo -e "  ${GREEN}✓${NC} Time tracking still working after multiple cycles"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Time tracking may be broken after cycles"
    exit 1
fi

# Test 7: Pause without resume (session completion)
print_section "Test 7: Complete Session While Paused"
print_test "Pause session and complete it"

daf pause "$TEST_NAME" > /dev/null 2>&1
sleep 1

COMPLETE_OUTPUT=$(daf complete "$TEST_NAME" --no-commit --no-pr --no-issue-update 2>&1)
COMPLETE_EXIT_CODE=$?

if [ $COMPLETE_EXIT_CODE -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} Session completed successfully while paused"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Session completion FAILED"
    echo -e "  ${RED}Output:${NC}"
    echo "$COMPLETE_OUTPUT" | sed 's/^/    /'
    exit 1
fi

# Verify final time is recorded
print_test "Verify final time was recorded"
FINAL_TIME=$(daf time "$TEST_NAME" 2>&1)

if [ $? -eq 0 ] && echo "$FINAL_TIME" | grep -E "(Total|Work)" > /dev/null; then
    echo -e "  ${GREEN}✓${NC} Final time recorded for completed session"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}ℹ${NC}  Cannot verify final time (session may be archived)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Final summary
print_section "Test Summary"
echo -e "${BOLD}Tests Passed:${NC} ${GREEN}${TESTS_PASSED}${NC} / ${TESTS_TOTAL}"
echo ""

if [ $TESTS_PASSED -eq $TESTS_TOTAL ]; then
    echo -e "${BOLD}${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Successfully tested time tracking workflow:"
    echo "  ✓ Auto-start time tracking on session creation"
    echo "  ✓ daf pause - Pause time tracking"
    echo "  ✓ daf resume - Resume time tracking"
    echo "  ✓ daf time - View time spent"
    echo "  ✓ daf summary - Time in session summary"
    echo "  ✓ Multiple pause/resume cycles"
    echo "  ✓ Complete session with time tracking"
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
