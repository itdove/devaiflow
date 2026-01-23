#!/bin/bash
# run_all_integration_tests.sh
# Runs all DevAIFlow integration tests in sequence
# Outputs to /tmp for easy analysis
#
# Can be run from inside AI agent sessions - uses isolated environment:
#   - Unsets DEVAIFLOW_IN_SESSION to bypass safety guards
#   - Unsets AI_AGENT_SESSION_ID to isolate from parent session
#   - Sets DEVAIFLOW_HOME to /tmp for data isolation
#
# Usage:
#   ./run_all_integration_tests.sh           # Normal mode
#   ./run_all_integration_tests.sh --debug   # Debug mode (set -x)

set -e  # Exit on first error (fail fast)

# Parse arguments
DEBUG_MODE=false
if [ "$1" = "--debug" ]; then
    DEBUG_MODE=true
    set -x  # Enable debug output
fi

# Save original environment variables
ORIGINAL_DEVAIFLOW_IN_SESSION="${DEVAIFLOW_IN_SESSION:-}"
ORIGINAL_AI_AGENT_SESSION_ID="${AI_AGENT_SESSION_ID:-}"
ORIGINAL_DEVAIFLOW_HOME="${DEVAIFLOW_HOME:-}"

# Unset DEVAIFLOW_IN_SESSION to bypass safety guards
# (Integration tests need to call blocked commands like daf new, daf note, etc.)
#
# Note: AI_AGENT_SESSION_ID is also used by 'daf active' to detect the active conversation.
# This is safe to unset because:
#   - Integration tests create their own test sessions in mock mode
#   - test_readonly_commands.sh explicitly sets its own AI_AGENT_SESSION_ID for testing
#   - No tests rely on preserving the original session ID from parent session
unset DEVAIFLOW_IN_SESSION
unset AI_AGENT_SESSION_ID

# Set temporary DEVAIFLOW_HOME for complete data isolation
# This ensures integration tests don't interfere with actual sessions
TEMP_DEVAIFLOW_HOME="/tmp/daf-integration-tests-$$"
export DEVAIFLOW_HOME="$TEMP_DEVAIFLOW_HOME"

# Cleanup function to restore environment
cleanup_environment() {
    # Restore original DEVAIFLOW_IN_SESSION if it existed
    if [ -n "$ORIGINAL_DEVAIFLOW_IN_SESSION" ]; then
        export DEVAIFLOW_IN_SESSION="$ORIGINAL_DEVAIFLOW_IN_SESSION"
    fi

    # Restore original AI_AGENT_SESSION_ID if it existed
    if [ -n "$ORIGINAL_AI_AGENT_SESSION_ID" ]; then
        export AI_AGENT_SESSION_ID="$ORIGINAL_AI_AGENT_SESSION_ID"
    fi

    # Restore original DEVAIFLOW_HOME if it existed
    if [ -n "$ORIGINAL_DEVAIFLOW_HOME" ]; then
        export DEVAIFLOW_HOME="$ORIGINAL_DEVAIFLOW_HOME"
    else
        unset DEVAIFLOW_HOME
    fi

    # Clean up temporary directory
    if [ -d "$TEMP_DEVAIFLOW_HOME" ]; then
        rm -rf "$TEMP_DEVAIFLOW_HOME"
    fi
}

# Register cleanup on exit
trap cleanup_environment EXIT

# Create timestamped output file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="/tmp/daf_integration_tests_${TIMESTAMP}.log"

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

# Test suite configuration
TESTS=(
    "test_jira_green_path.sh"
    "test_collaboration_workflow.sh"
    "test_time_tracking.sh"
    "test_templates.sh"
    "test_jira_sync.sh"
    "test_readonly_commands.sh"
    "test_multi_repo.sh"
    "test_session_lifecycle.sh"
    "test_investigation.sh"
    "test_error_handling.sh"
)

TEST_DESCRIPTIONS=(
    "Complete JIRA workflow (new → update → open → complete)"
    "Export/import and multi-session support"
    "Time tracking features (pause, resume, time command)"
    "Template system (save, list, use, delete)"
    "JIRA sync features (sprint sync, ticket sync)"
    "Read-only commands that work inside Claude Code"
    # "Multi-repository workflow (cross-repo features)"  # COMMENTED OUT: Blocked by AAP-63884
    "Session lifecycle (link, unlink, delete operations)"
    "Investigation-only sessions (read-only mode)"
    "Error handling and validation (edge cases)"
)

# Counters
TOTAL_TESTS=${#TESTS[@]}
PASSED_TESTS=0
FAILED_TESTS=0

# Function to print section headers
print_section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Function to run a single test
run_test() {
    local test_file=$1
    local description=$2
    local test_number=$3

    echo -e "${YELLOW}→${NC} Running test ${test_number}/${TOTAL_TESTS}: ${test_file}"
    echo -e "  ${description}"
    echo ""

    # Run the test and capture output
    # Pass --debug flag to sub-test if debug mode is enabled
    if [ "$DEBUG_MODE" = true ]; then
        if ./"${test_file}" --debug; then
            echo -e "${GREEN}✓${NC} Test passed: ${test_file}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            return 0
        else
            echo -e "${RED}✗${NC} Test FAILED: ${test_file}"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            return 1
        fi
    else
        if ./"${test_file}"; then
            echo -e "${GREEN}✓${NC} Test passed: ${test_file}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            return 0
        else
            echo -e "${RED}✗${NC} Test FAILED: ${test_file}"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            return 1
        fi
    fi
}

# Main execution
{
    print_section "DevAIFlow Integration Test Suite"
    echo "Running all integration tests..."
    echo "Debug mode: ${DEBUG_MODE}"
    echo "Output file: ${OUTPUT_FILE}"
    echo "Total tests: ${TOTAL_TESTS}"
    echo "Fail fast: ENABLED (will exit on first failure)"
    echo ""
    echo -e "${CYAN}Environment Isolation:${NC}"
    echo "  DEVAIFLOW_IN_SESSION: unset (bypassing safety guards)"
    echo "  AI_AGENT_SESSION_ID: unset (isolated from parent session)"
    echo "  DEVAIFLOW_HOME: ${DEVAIFLOW_HOME}"
    echo "  Data directory: isolated (will be cleaned up on exit)"
    if [ -n "$ORIGINAL_DEVAIFLOW_IN_SESSION" ]; then
        echo "  Running inside AI agent: YES (original session will be restored)"
    else
        echo "  Running inside AI agent: NO"
    fi
    echo ""

    # Change to integration-tests directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"

    echo "Working directory: $(pwd)"
    echo ""

    # Verify all test files exist
    print_section "Pre-flight Checks"
    MISSING_FILES=0
    for test_file in "${TESTS[@]}"; do
        if [ ! -f "$test_file" ]; then
            echo -e "${RED}✗${NC} Missing test file: ${test_file}"
            MISSING_FILES=$((MISSING_FILES + 1))
        else
            echo -e "${GREEN}✓${NC} Found: ${test_file}"
        fi
    done

    if [ $MISSING_FILES -gt 0 ]; then
        echo -e "${RED}✗${NC} ${MISSING_FILES} test file(s) missing. Aborting."
        exit 1
    fi

    echo ""
    echo "All test files found. Starting test execution..."

    # Run all tests
    START_TIME=$(date +%s)

    for i in "${!TESTS[@]}"; do
        test_number=$((i + 1))
        print_section "Test ${test_number}/${TOTAL_TESTS}: ${TESTS[$i]}"

        # Run test (will exit immediately on failure due to set -e)
        run_test "${TESTS[$i]}" "${TEST_DESCRIPTIONS[$i]}" "$test_number"

        echo ""

        # Add delay between tests to allow for cleanup and resource finalization
        # This prevents intermittent hanging issues when tests run in rapid succession
        if [ $test_number -lt $TOTAL_TESTS ]; then
            sleep 2
        fi
    done

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    # Final summary
    print_section "Test Suite Summary"
    echo -e "${BOLD}Total Tests:${NC}  ${TOTAL_TESTS}"
    echo -e "${BOLD}${GREEN}Passed:${NC}       ${PASSED_TESTS}${NC}"
    echo -e "${BOLD}${RED}Failed:${NC}       ${FAILED_TESTS}${NC}"
    echo -e "${BOLD}Duration:${NC}     ${DURATION} seconds"
    echo ""

    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${BOLD}${GREEN}✓ All integration tests passed!${NC}"
        echo ""
        echo "Test suite completed successfully. All features are working correctly."
        echo ""
        exit 0
    else
        echo -e "${BOLD}${RED}✗ ${FAILED_TESTS} test(s) failed${NC}"
        echo ""
        echo "Review the output above for details on failed tests."
        echo ""
        exit 1
    fi

} 2>&1 | tee "${OUTPUT_FILE}"

# Print final message about output file
echo ""
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Test output saved to:${NC} ${OUTPUT_FILE}"
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
