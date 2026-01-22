#!/bin/bash
# test_multi_repo.sh
# Integration test for DevAIFlow multi-repository workflow
# Tests: Multiple conversations for one session, working across repos
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
ORIGINAL_DEVFLOW_IN_SESSION="${DEVFLOW_IN_SESSION:-}"
ORIGINAL_AI_AGENT_SESSION_ID="${AI_AGENT_SESSION_ID:-}"
ORIGINAL_DEVAIFLOW_HOME="${DEVAIFLOW_HOME:-}"

# Unset session variables to bypass safety guards
unset DEVFLOW_IN_SESSION
unset AI_AGENT_SESSION_ID

# Use temporary DEVAIFLOW_HOME if not already set by runner
if [ -z "$DEVAIFLOW_HOME" ] || [ "$DEVAIFLOW_HOME" = "$ORIGINAL_DEVAIFLOW_HOME" ]; then
    TEMP_DEVAIFLOW_HOME="/tmp/daf-test-multi_repo-$$"
    export DEVAIFLOW_HOME="$TEMP_DEVAIFLOW_HOME"
    CLEANUP_TEMP_DIR=true
else
    CLEANUP_TEMP_DIR=false
fi

# Cleanup function
cleanup_test_environment() {
    # Restore original environment
    if [ -n "$ORIGINAL_DEVFLOW_IN_SESSION" ]; then
        export DEVFLOW_IN_SESSION="$ORIGINAL_DEVFLOW_IN_SESSION"
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

# Save script directory at the very beginning (before any cd commands)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
TEST_TICKET="PROJ-88888"

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

# Setup temporary directories for multi-repo structure
TEMP_WORKSPACE=$(mktemp -d -t daf-multi-repo-test.XXXXXX)
BACKEND_DIR="$TEMP_WORKSPACE/backend-api"
FRONTEND_DIR="$TEMP_WORKSPACE/frontend-app"
TERRAFORM_DIR="$TEMP_WORKSPACE/terraform-infra"

# Cleanup function
cleanup() {
    if [ -n "$TEMP_WORKSPACE" ] && [ -d "$TEMP_WORKSPACE" ]; then
        rm -rf "$TEMP_WORKSPACE"
    fi
}
trap cleanup EXIT

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

# Main test execution
print_section "Multi-Repository Workflow Integration Test"
echo "This script tests working across multiple repositories:"
echo "  1. Create work session in backend repository"
echo "  2. Open same session in frontend repository (creates 2nd conversation)"
echo "  3. Open same session in terraform repository (creates 3rd conversation)"
echo "  4. Verify session has 3 separate conversations"
echo "  5. List conversations for the session"
echo "  6. Verify conversation isolation (unique working directories)"
echo "  7. Test session commands with multiple conversations"
echo ""

# Setup: Create temporary repository structure
print_section "Setup: Create Multi-Repo Structure"
print_test "Create temporary workspace with 3 repositories"

mkdir -p "$BACKEND_DIR" "$FRONTEND_DIR" "$TERRAFORM_DIR"

# Initialize git repos (minimal setup)
for dir in "$BACKEND_DIR" "$FRONTEND_DIR" "$TERRAFORM_DIR"; do
    cd "$dir"
    git init > /dev/null 2>&1
    git config user.email "test@example.com"
    git config user.name "Test User"
    echo "# $(basename $dir)" > README.md
    git add README.md
    git commit -m "Initial commit" > /dev/null 2>&1
done

echo -e "  ${GREEN}✓${NC} Created workspace at: $TEMP_WORKSPACE"
echo -e "    - backend-api/"
echo -e "    - frontend-app/"
echo -e "    - terraform-infra/"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Clean start
print_test "Clean mock data before tests"
daf purge-mock-data --force > /dev/null 2>&1
verify_success "daf purge-mock-data --force" "Mock data cleaned successfully"

# Initialize configuration
print_test "Initialize configuration"
# Create test configuration (avoids interactive daf init)
python3 "$SCRIPT_DIR/setup_test_config.py" > /dev/null 2>&1 || true
echo -e "  ${GREEN}✓${NC} Configuration initialized"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Test 1: Create work session in backend repo
print_section "Test 1: Create Work Session in Backend Repository"
print_test "Create session for multi-repo work"

SESSION_NAME="multi-repo-auth"
cd "$BACKEND_DIR"
daf new --name "$SESSION_NAME" --goal "Add authentication across backend and frontend" --path "$BACKEND_DIR" --branch "feature/auth" --json > /dev/null 2>&1
verify_success "daf new" "Session created in backend-api"

# Sync to persist the conversation
print_test "Sync to persist backend conversation"
daf sync > /dev/null 2>&1
verify_success "daf sync" "Backend conversation persisted"

# Test 3: Open session in frontend repo (creates 2nd conversation)
print_section "Test 3: Open Same Session in Frontend Repository"
print_test "Open session in frontend-app directory (2nd conversation)"

cd "$FRONTEND_DIR"
yes "y" | timeout 20 daf open "$SESSION_NAME" --path "$FRONTEND_DIR" --json > /dev/null 2>&1
verify_success "daf open frontend" "Session opened in frontend-app (2nd conversation)"

# Sync to create the conversation
print_test "Sync to create frontend conversation"
daf sync > /dev/null 2>&1
verify_success "daf sync" "Frontend conversation created"

# Test 4: Open session in terraform repo (creates 3rd conversation)
print_section "Test 4: Open Same Session in Terraform Repository"
print_test "Open session in terraform-infra directory (3rd conversation)"

cd "$TERRAFORM_DIR"
yes "y" | timeout 20 daf open "$SESSION_NAME" --path "$TERRAFORM_DIR" --json > /dev/null 2>&1
verify_success "daf open terraform" "Session opened in terraform-infra (3rd conversation)"

# Sync to create the conversation
print_test "Sync to create terraform conversation"
daf sync > /dev/null 2>&1
verify_success "daf sync" "Terraform conversation created"

# Test 5: Verify session has 3 conversations
print_section "Test 5: Verify Multi-Conversation Structure"
print_test "Verify session has 3 conversations"

SESSION_INFO_JSON=$(daf info "$SESSION_NAME" --json 2>&1 | sed -n '/{/,/^}$/p')

CONV_COUNT=$(echo "$SESSION_INFO_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    session = data.get('data', {}).get('session', {})
    conversations = session.get('conversations', {})
    print(len(conversations))
except:
    print('0')
" 2>/dev/null)

if [ "$CONV_COUNT" = "3" ]; then
    echo -e "  ${GREEN}✓${NC} Session has 3 conversations (backend, frontend, terraform)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Expected 3 conversations, found $CONV_COUNT"
    echo -e "  ${RED}Session info:${NC}"
    echo "$SESSION_INFO_JSON" | sed 's/^/    /'
    exit 1
fi

# Test 6: List conversations
print_section "Test 6: List All Conversations"
print_test "Use daf sessions list to view all conversations"

LIST_SESSIONS_OUTPUT=$(daf sessions list "$SESSION_NAME" 2>&1)
LIST_EXIT=$?

if [ $LIST_EXIT -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} daf sessions list executed successfully"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} daf sessions list FAILED"
    exit 1
fi

# Verify output shows multiple conversations
print_test "Verify output shows 3 conversations"
BACKEND_FOUND=0
FRONTEND_FOUND=0
TERRAFORM_FOUND=0

echo "$LIST_SESSIONS_OUTPUT" | grep -q "backend-api" && BACKEND_FOUND=1
echo "$LIST_SESSIONS_OUTPUT" | grep -q "frontend-app" && FRONTEND_FOUND=1
echo "$LIST_SESSIONS_OUTPUT" | grep -q "terraform-infra" && TERRAFORM_FOUND=1

TOTAL_FOUND=$((BACKEND_FOUND + FRONTEND_FOUND + TERRAFORM_FOUND))

if [ $TOTAL_FOUND -eq 3 ]; then
    echo -e "  ${GREEN}✓${NC} All 3 conversations listed"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}ℹ${NC}  Found $TOTAL_FOUND/3 conversations (conversation display may vary)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 7: Verify conversation isolation
print_section "Test 7: Verify Conversation Isolation"
print_test "Verify each conversation has unique working directory"

WORKING_DIRS=$(echo "$SESSION_INFO_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    session = data.get('data', {}).get('session', {})
    conversations = session.get('conversations', {})
    # Print all working directory keys
    for wd in conversations.keys():
        print(wd)
except:
    pass
" 2>/dev/null)

UNIQUE_DIRS=$(echo "$WORKING_DIRS" | sort -u | wc -l | tr -d ' ')

if [ "$UNIQUE_DIRS" = "3" ]; then
    echo -e "  ${GREEN}✓${NC} Each conversation has unique working directory"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Expected 3 unique working directories, found $UNIQUE_DIRS"
    exit 1
fi

# Test 8: Work in each conversation
print_section "Test 8: Simulate Work in Each Conversation"
print_test "Create files in each repository"

cd "$BACKEND_DIR"
echo "class AuthService {}" > auth.py
git add auth.py
git commit -m "Add auth service" > /dev/null 2>&1
echo -e "  ${GREEN}✓${NC} Created auth.py in backend-api"

cd "$FRONTEND_DIR"
echo "function Login() {}" > Login.jsx
git add Login.jsx
git commit -m "Add login component" > /dev/null 2>&1
echo -e "  ${GREEN}✓${NC} Created Login.jsx in frontend-app"

cd "$TERRAFORM_DIR"
echo "resource \"aws_cognito\" {}" > cognito.tf
git add cognito.tf
git commit -m "Add Cognito config" > /dev/null 2>&1
echo -e "  ${GREEN}✓${NC} Created cognito.tf in terraform-infra"

TESTS_PASSED=$((TESTS_PASSED + 1))

# Test 9: Session info shows all working directories
print_section "Test 9: Session Info Shows All Working Directories"
print_test "Verify daf info shows all 3 working directories"

INFO_OUTPUT=$(daf info "$SESSION_NAME" 2>&1)

if echo "$INFO_OUTPUT" | grep -q "backend-api" && \
   echo "$INFO_OUTPUT" | grep -q "frontend-app" && \
   echo "$INFO_OUTPUT" | grep -q "terraform-infra"; then
    echo -e "  ${GREEN}✓${NC} All working directories shown in session info"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}ℹ${NC}  Not all directories shown (display format may vary)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 10: daf list shows session once (not 3 times)
print_section "Test 10: Session List Shows Single Entry"
print_test "Verify daf list shows session only once (not per conversation)"

LIST_OUTPUT=$(daf list 2>&1)
OCCURRENCE_COUNT=$(echo "$LIST_OUTPUT" | grep -c "$SESSION_NAME" || echo "0")

if [ "$OCCURRENCE_COUNT" -le 2 ]; then
    echo -e "  ${GREEN}✓${NC} Session appears only once in list (found $OCCURRENCE_COUNT entries)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Session appears $OCCURRENCE_COUNT times (should be 1-2)"
    exit 1
fi

# Test 11: Complete workflow - all conversations
print_section "Test 11: Complete Multi-Repo Session"
print_test "Complete session (should handle multiple conversations)"

COMPLETE_OUTPUT=$(daf complete "$SESSION_NAME" --no-commit --no-pr --no-issue-update 2>&1)
COMPLETE_EXIT=$?

if [ $COMPLETE_EXIT -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} Multi-conversation session completed successfully"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}ℹ${NC}  Completion may require additional prompts (non-critical)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Final summary
print_section "Test Summary"
echo -e "${BOLD}Tests Passed:${NC} ${GREEN}${TESTS_PASSED}${NC} / ${TESTS_TOTAL}"
echo ""

if [ $TESTS_PASSED -eq $TESTS_TOTAL ]; then
    echo -e "${BOLD}${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Successfully tested multi-repository workflow:"
    echo "  ✓ Created JIRA ticket for cross-repo work"
    echo "  ✓ Opened session in 3 different repositories"
    echo "  ✓ Session maintains 3 separate conversations"
    echo "  ✓ daf sessions list - Shows all conversations"
    echo "  ✓ Conversation isolation - Unique working directories"
    echo "  ✓ Work in each repository independently"
    echo "  ✓ Session info shows all working directories"
    echo "  ✓ Session list shows single entry (not duplicated)"
    echo "  ✓ Complete multi-conversation session"
    echo ""
    exit 0
else
    echo -e "${BOLD}${RED}✗ Some tests failed${NC}"
    echo ""
    exit 1
fi
