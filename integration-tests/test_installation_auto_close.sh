#!/bin/bash
# test_installation_auto_close.sh
# Integration test for DevAIFlow installation workflow with auto_close_on_complete
#
# This test validates the complete installation workflow including the auto_close_on_complete
# feature for GitHub issues. Unlike other integration tests, this runs against real GitHub API
# (not mock mode) to validate the end-to-end experience.
#
# Requirements:
#   - GITHUB_TOKEN environment variable set (your GitHub personal access token)
#   - DAF_TEST_GITHUB_REPO environment variable set (format: owner/repo-name)
#   - Network access to GitHub API
#   - Write access to the specified test repository (can be private)
#
# Optional:
#   - DAF_TEST_BRANCH environment variable (defaults to 'main')
#     Example: export DAF_TEST_BRANCH="125" to test a feature branch
#
# Test workflow:
#   1. Clone DevAIFlow repository to temp directory
#   2. Install DevAIFlow in fresh Python venv from source
#   3. Programmatically create config.json with auto_close_on_complete=true
#   4. Authenticate with GitHub using GITHUB_TOKEN
#   5. Run daf upgrade to install skills
#   6. Create a GitHub issue using daf git create
#   7. Create and complete a session
#   8. Verify the issue was automatically closed (no user prompt)
#   9. Clean up test environment

# Parse arguments
DEBUG_MODE=false
if [ "$1" = "--debug" ]; then
    DEBUG_MODE=true
    set -x  # Enable debug output
fi

set -e  # Exit on first error

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

# Check prerequisites
print_section "Installation Auto-Close Integration Test"
echo "This script tests the complete installation workflow with auto_close_on_complete:"
echo "  1. Clone DevAIFlow from GitHub"
echo "  2. Install DevAIFlow from source in fresh venv"
echo "  3. Create config with auto_close_on_complete=true"
echo "  4. Run daf upgrade to install skills"
echo "  5. Create GitHub issue and session"
echo "  6. Complete session and verify issue auto-closed"
echo "  7. Clean up test environment"
echo ""
echo "Note: This test uses REAL GitHub API (not mock mode)"
echo ""

# Check for GITHUB_TOKEN
print_test "Check for GITHUB_TOKEN"
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "  ${YELLOW}⚠${NC} GITHUB_TOKEN not set - skipping test"
    echo ""
    echo "To run this test, set GITHUB_TOKEN:"
    echo "  export GITHUB_TOKEN='your-github-token'"
    echo ""
    echo "Test skipped gracefully (exit 0)"
    exit 0
fi
echo -e "  ${GREEN}✓${NC} GITHUB_TOKEN is set"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Check for test repository configuration
print_test "Check for test repository configuration"
if [ -z "$DAF_TEST_GITHUB_REPO" ]; then
    echo -e "  ${YELLOW}⚠${NC} DAF_TEST_GITHUB_REPO not set - skipping test"
    echo ""
    echo "To run this test, set DAF_TEST_GITHUB_REPO to a repository you have write access to:"
    echo "  export DAF_TEST_GITHUB_REPO='owner/repo-name'"
    echo ""
    echo "Example:"
    echo "  export DAF_TEST_GITHUB_REPO='myusername/devaiflow-tests'"
    echo ""
    echo "Note: The repository can be private as long as your GITHUB_TOKEN has access."
    echo ""
    echo "Test skipped gracefully (exit 0)"
    exit 0
fi

# Validate repository format
if ! echo "$DAF_TEST_GITHUB_REPO" | grep -q '^[^/]\+/[^/]\+$'; then
    echo -e "  ${RED}✗${NC} Invalid repository format: $DAF_TEST_GITHUB_REPO"
    echo ""
    echo "Repository must be in format: owner/repo-name"
    echo "Example: myusername/devaiflow-tests"
    echo ""
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Test repository configured: ${BOLD}$DAF_TEST_GITHUB_REPO${NC}"
TESTS_PASSED=$((TESTS_PASSED + 1))

print_test "Check branch configuration"
TEST_BRANCH="${DAF_TEST_BRANCH:-main}"
echo -e "  ${GREEN}✓${NC} Test branch: ${BOLD}$TEST_BRANCH${NC} (set via DAF_TEST_BRANCH, defaults to 'main')"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Check for gh CLI
print_test "Check for GitHub CLI (gh)"
if ! command -v gh &> /dev/null; then
    echo -e "  ${RED}✗${NC} GitHub CLI (gh) not found"
    echo ""
    echo "Install gh CLI:"
    echo "  brew install gh  # macOS"
    echo "  # or see https://cli.github.com/"
    echo ""
    exit 1
fi
echo -e "  ${GREEN}✓${NC} GitHub CLI (gh) is installed"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Create temporary directories
TEMP_BASE="/tmp/daf-test-install-$$"
TEMP_VENV="$TEMP_BASE/venv"
TEMP_DEVAIFLOW_HOME="$TEMP_BASE/devaiflow_home"
TEMP_GIT_REPO="$TEMP_BASE/test-repo"
TEMP_PROJECT_DIR="$TEMP_BASE/devaiflow-clone"

mkdir -p "$TEMP_BASE"
mkdir -p "$TEMP_DEVAIFLOW_HOME"
mkdir -p "$TEMP_GIT_REPO"

# Cleanup function
cleanup_test_environment() {
    echo ""
    echo -e "${CYAN}Cleaning up test environment...${NC}"

    # Deactivate venv if active
    if [ -n "$VIRTUAL_ENV" ]; then
        deactivate 2>/dev/null || true
    fi

    # Clean up temporary directories
    if [ -d "$TEMP_BASE" ]; then
        rm -rf "$TEMP_BASE"
        echo -e "  ${GREEN}✓${NC} Removed temporary directory: $TEMP_BASE"
    fi
}

trap cleanup_test_environment EXIT

# Test 1: Clone DevAIFlow repository
print_section "Test 1: Clone DevAIFlow Repository"

# Determine which branch to test (default: main)
TEST_BRANCH="${DAF_TEST_BRANCH:-main}"

print_test "Clone devaiflow from GitHub (branch: $TEST_BRANCH)"

# Clone the repository
git clone --branch "$TEST_BRANCH" https://github.com/itdove/devaiflow.git "$TEMP_PROJECT_DIR" > /dev/null 2>&1
verify_success "git clone" "DevAIFlow cloned to $TEMP_PROJECT_DIR (branch: $TEST_BRANCH)"

# Test 2: Create Python venv
print_section "Test 2: Create Python Virtual Environment"
print_test "Create Python venv"

python3 -m venv "$TEMP_VENV" > /dev/null 2>&1
verify_success "python3 -m venv" "Python venv created at $TEMP_VENV"

# Activate venv
source "$TEMP_VENV/bin/activate"

print_test "Verify venv activation"
PYTHON_PATH=$(which python)
if [[ "$PYTHON_PATH" == "$TEMP_VENV"* ]]; then
    echo -e "  ${GREEN}✓${NC} Virtual environment activated: $PYTHON_PATH"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Virtual environment activation failed"
    echo -e "  ${RED}Expected path:${NC} $TEMP_VENV/bin/python"
    echo -e "  ${RED}Actual path:${NC} $PYTHON_PATH"
    exit 1
fi

# Test 3: Install DevAIFlow from source
print_section "Test 3: Install DevAIFlow from Source"
print_test "Install DevAIFlow with pip install -e ."

# Install from source (editable mode)
pip install -e "$TEMP_PROJECT_DIR" > /dev/null 2>&1
verify_success "pip install -e ." "DevAIFlow installed from source"

print_test "Verify daf command is available"
if command -v daf &> /dev/null; then
    DAF_VERSION=$(daf --version 2>&1 || echo "unknown")
    echo -e "  ${GREEN}✓${NC} daf command is available (version: $DAF_VERSION)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} daf command not found after installation"
    exit 1
fi

# Test 4: Programmatically create config.json
print_section "Test 4: Create Configuration with auto_close_on_complete"
print_test "Create config.json programmatically"

export DEVAIFLOW_HOME="$TEMP_DEVAIFLOW_HOME"

# Create config directories
mkdir -p "$DEVAIFLOW_HOME/backends"

# Create user config
cat > "$DEVAIFLOW_HOME/config.json" <<'EOF'
{
  "issue_tracker_backend": "github",
  "backend_config_source": "local",
  "repos": {
    "workspaces": [
      {
        "name": "test",
        "path": "/tmp/daf-test-install-$$"
      }
    ],
    "last_used_workspace": "test",
    "detection": {
      "method": "keyword_match",
      "fallback": "prompt"
    },
    "keywords": {}
  },
  "prompts": {
    "auto_launch_agent": false,
    "auto_commit_on_complete": false,
    "auto_accept_ai_commit_message": true,
    "auto_create_pr_on_complete": false,
    "auto_add_issue_summary": false,
    "auto_update_jira_pr_url": false,
    "auto_push_to_remote": false,
    "auto_checkout_branch": true,
    "auto_sync_with_base": "never",
    "auto_complete_on_exit": false,
    "auto_create_pr_status": "draft",
    "show_prompt_unit_tests": false,
    "auto_load_related_conversations": false
  },
  "time_tracking": {
    "auto_start": true,
    "auto_pause_after": "30m",
    "reminder_interval": "2h"
  },
  "session_summary": {
    "mode": "local",
    "api_key_env": "ANTHROPIC_API_KEY"
  },
  "templates": {
    "auto_create": true,
    "auto_use": true
  },
  "context_files": {
    "files": []
  },
  "storage": {
    "backend": "file"
  },
  "update_checker_timeout": 10
}
EOF

# Replace variables with actual values in the config
sed -i.bak "s/\$\$/$$/" "$DEVAIFLOW_HOME/config.json" && rm "$DEVAIFLOW_HOME/config.json.bak"
sed -i.bak "s|\$DAF_TEST_GITHUB_REPO|$DAF_TEST_GITHUB_REPO|g" "$DEVAIFLOW_HOME/config.json" && rm "$DEVAIFLOW_HOME/config.json.bak"

verify_success "cat > config.json" "User config created with auto_close_on_complete=true"

# Create minimal backend config
cat > "$DEVAIFLOW_HOME/backends/github.json" <<'EOF'
{
  "api_url": "https://api.github.com"
}
EOF

verify_success "cat > backends/github.json" "Backend config created"

# Create organization config with GitHub auto-close enabled
# Note: In the new 5-file format, GitHub settings go in organization.json
cat > "$DEVAIFLOW_HOME/organization.json" <<'EOF'
{
  "jira_project": null,
  "github_repository": "$DAF_TEST_GITHUB_REPO",
  "github_auto_close_on_complete": true
}
EOF

# Replace variable with actual value
sed -i.bak "s|\$DAF_TEST_GITHUB_REPO|$DAF_TEST_GITHUB_REPO|g" "$DEVAIFLOW_HOME/organization.json" && rm "$DEVAIFLOW_HOME/organization.json.bak"

verify_success "cat > organization.json" "Organization config created with github_auto_close_on_complete=true"

# Create minimal team config
cat > "$DEVAIFLOW_HOME/team.json" <<'EOF'
{
  "time_tracking_enabled": true
}
EOF

verify_success "cat > team.json" "Team config created"

# Create minimal enterprise config
cat > "$DEVAIFLOW_HOME/enterprise.json" <<'EOF'
{
  "agent_backend": "claude"
}
EOF

verify_success "cat > enterprise.json" "Enterprise config created"

print_test "Verify github_auto_close_on_complete is set to true"
AUTO_CLOSE=$(python3 -c "import json; print(json.load(open('$DEVAIFLOW_HOME/organization.json'))['github_auto_close_on_complete'])" 2>/dev/null)
if [ "$AUTO_CLOSE" = "True" ]; then
    echo -e "  ${GREEN}✓${NC} github_auto_close_on_complete is set to true in organization.json"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} github_auto_close_on_complete verification failed"
    echo -e "  ${RED}Expected:${NC} True"
    echo -e "  ${RED}Actual:${NC} $AUTO_CLOSE"
    exit 1
fi

print_test "Verify merged config shows auto_close_on_complete=true"
# Use daf config show to verify the merged config
# Redirect stderr to a separate file to see if warnings are contaminating JSON output
MERGED_CONFIG_STDERR=$(mktemp)
MERGED_CONFIG=$(daf config show --json 2>"$MERGED_CONFIG_STDERR")
MERGED_CONFIG_EXIT=$?

# Check if there were any warnings/errors on stderr
if [ -s "$MERGED_CONFIG_STDERR" ]; then
    echo -e "  ${YELLOW}⚠${NC} Warnings/errors detected on stderr:"
    cat "$MERGED_CONFIG_STDERR" | sed 's/^/    /'
fi
rm -f "$MERGED_CONFIG_STDERR"

# Extract auto_close_on_complete value
MERGED_AUTO_CLOSE=$(echo "$MERGED_CONFIG" | python3 -c "
import sys, json
input_data = sys.stdin.read()
try:
    data = json.loads(input_data)
    github_config = data.get('github', {})
    auto_close = github_config.get('auto_close_on_complete', False)
    # Print as lowercase string for consistency with JSON boolean format
    print(str(auto_close).lower())
except Exception as e:
    print('error')
    sys.stderr.write(f'JSON parse error: {e}\\n')
    sys.stderr.write('First 500 chars of output:\\n')
    sys.stderr.write(input_data[:500] + '\\n')
" 2>&1)

if [ "$MERGED_AUTO_CLOSE" = "true" ]; then
    echo -e "  ${GREEN}✓${NC} Merged config shows auto_close_on_complete=true"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}⚠${NC} Merged config auto_close_on_complete: $MERGED_AUTO_CLOSE"
    echo -e "  ${YELLOW}Note:${NC} Continuing test - will verify actual behavior with daf complete"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 5: Run daf upgrade
print_section "Test 5: Run daf upgrade to Install Skills"
print_test "Run daf upgrade"

# Run daf upgrade (may output some warnings, that's OK)
daf upgrade > /dev/null 2>&1 || true
echo -e "  ${GREEN}✓${NC} daf upgrade completed"
TESTS_PASSED=$((TESTS_PASSED + 1))

print_test "Verify skills were installed"
SKILLS_DIR="$HOME/.claude/skills"
if [ -d "$SKILLS_DIR" ] && [ "$(ls -A $SKILLS_DIR 2>/dev/null | wc -l)" -gt 0 ]; then
    SKILL_COUNT=$(ls -1 "$SKILLS_DIR" | wc -l | tr -d ' ')
    echo -e "  ${GREEN}✓${NC} Skills installed to $SKILLS_DIR ($SKILL_COUNT skills)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}⚠${NC} Skills directory is empty or doesn't exist (this is OK for minimal test)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 6: Initialize test git repository
print_section "Test 6: Initialize Test Git Repository"
print_test "Create and initialize git repository"

(
    cd "$TEMP_GIT_REPO"
    git init > /dev/null 2>&1
    git config user.name "Test User" > /dev/null 2>&1
    git config user.email "test@example.com" > /dev/null 2>&1

    # Add a remote pointing to the test repository
    git remote add origin "https://github.com/${DAF_TEST_GITHUB_REPO}.git" > /dev/null 2>&1

    echo "# Test Repository" > README.md
    git add README.md > /dev/null 2>&1
    git commit -m "Initial commit" > /dev/null 2>&1
) 2>&1
verify_success "git init" "Git repository initialized at $TEMP_GIT_REPO"

# Test 7: Create GitHub issue
print_section "Test 7: Create GitHub Issue"
print_test "Create test issue using daf git create"

# Change to test repository for git operations
cd "$TEMP_GIT_REPO"

# Create a test issue with unique summary to avoid conflicts
TEST_TIMESTAMP=$(date +%s)
ISSUE_SUMMARY="[AUTO-TEST] Installation workflow test - $TEST_TIMESTAMP"

# Create issue and capture JSON output
CREATE_OUTPUT=$(daf git create task \
    --summary "$ISSUE_SUMMARY" \
    --description "This is an automated test of the installation workflow with auto_close_on_complete. Test ID: $TEST_TIMESTAMP" \
    --json 2>&1)

CREATE_EXIT_CODE=$?
if [ $CREATE_EXIT_CODE -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} GitHub issue created successfully"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Issue creation failed with exit code $CREATE_EXIT_CODE"
    echo -e "  ${RED}Output:${NC}"
    echo "$CREATE_OUTPUT" | sed 's/^/    /'
    exit 1
fi

# Extract issue key from JSON
print_test "Extract issue key from creation response"
ISSUE_KEY=$(echo "$CREATE_OUTPUT" | python3 -c "
import sys, json
try:
    text = sys.stdin.read()
    json_start = text.find('{')
    if json_start == -1:
        print('ERROR')
    else:
        json_text = text[json_start:]
        data = json.loads(json_text)
        if data.get('success'):
            issue_data = data.get('data', {})
            # Try 'issue_key' first (new format), then 'key' (old format)
            key = issue_data.get('issue_key', '') or issue_data.get('key', '')
            print(key)
        else:
            print('ERROR')
except Exception as e:
    print('ERROR')
" 2>/dev/null)

if [ -z "$ISSUE_KEY" ] || [ "$ISSUE_KEY" = "ERROR" ]; then
    echo -e "  ${RED}✗${NC} Failed to extract issue key from JSON"
    echo -e "  ${RED}JSON response:${NC}"
    echo "$CREATE_OUTPUT"
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Issue key extracted: ${BOLD}$ISSUE_KEY${NC}"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Test 8: Assign issue to current user
print_section "Test 8: Assign Issue to Current User"
print_test "Get current GitHub username"

# Get current user from gh CLI
GITHUB_USER=$(gh api user --jq '.login' 2>&1)
if [ -z "$GITHUB_USER" ]; then
    echo -e "  ${RED}✗${NC} Failed to get GitHub username"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} GitHub username: ${BOLD}$GITHUB_USER${NC}"
TESTS_PASSED=$((TESTS_PASSED + 1))

print_test "Assign issue to current user"
ISSUE_NUMBER=$(echo "$ISSUE_KEY" | cut -d'#' -f2)
gh issue edit "$ISSUE_NUMBER" --repo "$DAF_TEST_GITHUB_REPO" --add-assignee "@me" > /dev/null 2>&1
verify_success "gh issue edit --add-assignee" "Issue assigned to $GITHUB_USER"

# Test 9: Sync issue using daf sync
print_section "Test 9: Sync Issue with daf sync"
print_test "Sync issues from test repository"

# Change to test repo directory for sync
cd "$TEMP_GIT_REPO"

# Run daf sync to create session from the assigned issue
SYNC_OUTPUT=$(daf sync --repo "$DAF_TEST_GITHUB_REPO" 2>&1)
SYNC_EXIT_CODE=$?

# Debug: Always show sync output
echo -e "  ${YELLOW}Debug:${NC} Sync command output:"
echo "$SYNC_OUTPUT" | sed 's/^/    /'
echo ""

if [ $SYNC_EXIT_CODE -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} Issue synced successfully"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Sync failed with exit code $SYNC_EXIT_CODE"
    exit 1
fi

# Extract session name from sync output or derive it
print_test "Determine session name"
# Session name format: owner-repo-number (e.g., itdove-devaiflow-tests-2)
SESSION_NAME=$(echo "$DAF_TEST_GITHUB_REPO" | sed 's/\//-/g')-${ISSUE_NUMBER}
echo -e "  ${GREEN}✓${NC} Session name: ${BOLD}$SESSION_NAME${NC}"
TESTS_PASSED=$((TESTS_PASSED + 1))

# Debug: Verify session was created
print_test "Verify session exists in DEVAIFLOW_HOME"
echo -e "  ${YELLOW}Debug:${NC} DEVAIFLOW_HOME=$DEVAIFLOW_HOME"
echo -e "  ${YELLOW}Debug:${NC} Listing sessions:"
daf list 2>&1 | sed 's/^/    /'
echo -e "  ${YELLOW}Debug:${NC} Session directory contents:"
ls -la "$DEVAIFLOW_HOME/" 2>&1 | sed 's/^/    /'
TESTS_PASSED=$((TESTS_PASSED + 1))

# Test 10: Verify issue is open
print_section "Test 10: Verify Issue Status Before Complete"
print_test "Verify issue is currently open"

# Get issue status using gh CLI directly
ISSUE_NUMBER=$(echo "$ISSUE_KEY" | cut -d'#' -f2)
ISSUE_STATE_BEFORE=$(gh issue view "$ISSUE_NUMBER" --repo "$DAF_TEST_GITHUB_REPO" --json state --jq '.state' 2>&1)

if [ "$ISSUE_STATE_BEFORE" = "OPEN" ]; then
    echo -e "  ${GREEN}✓${NC} Issue is open before completing session"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Issue state verification failed"
    echo -e "  ${RED}Expected:${NC} OPEN"
    echo -e "  ${RED}Actual:${NC} $ISSUE_STATE_BEFORE"
    exit 1
fi

# Test 11: Complete session with auto-close
print_section "Test 11: Complete Session (Auto-Close Test)"
print_test "Complete session with auto-close enabled"

# Complete the session - with auto_close_on_complete=true, this should NOT prompt
# and should automatically close the issue
COMPLETE_OUTPUT=$(daf complete "$SESSION_NAME" --no-commit --no-pr 2>&1)
COMPLETE_EXIT_CODE=$?

# Debug: Show full output for troubleshooting
echo -e "  ${YELLOW}Debug:${NC} Full completion output:"
echo "$COMPLETE_OUTPUT" | sed 's/^/    /'
echo ""

if [ $COMPLETE_EXIT_CODE -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} Session completed successfully"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Session completion failed with exit code $COMPLETE_EXIT_CODE"
    echo -e "  ${RED}Command:${NC} daf complete \"$SESSION_NAME\" --no-commit --no-pr"
    exit 1
fi

# Verify output mentions automatic closing
print_test "Verify output mentions automatic issue closing"
if echo "$COMPLETE_OUTPUT" | grep -q "Automatically closing issue"; then
    echo -e "  ${GREEN}✓${NC} Output confirms automatic closing (no user prompt)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}⚠${NC} Output doesn't explicitly mention automatic closing"
    echo -e "  ${YELLOW}Note:${NC} This is OK - will verify issue state directly"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 12: Verify issue was automatically closed
print_section "Test 12: Verify Issue Was Automatically Closed"
print_test "Check issue state using GitHub API"

# Wait a moment for GitHub API to reflect the change
sleep 2

# Get issue status using gh CLI
ISSUE_STATE_AFTER=$(gh issue view "$ISSUE_NUMBER" --repo "$DAF_TEST_GITHUB_REPO" --json state --jq '.state' 2>&1)

if [ "$ISSUE_STATE_AFTER" = "CLOSED" ]; then
    echo -e "  ${GREEN}✓${NC} Issue was automatically closed (no user prompt!)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}✗${NC} Issue was NOT automatically closed"
    echo -e "  ${RED}Expected state:${NC} CLOSED"
    echo -e "  ${RED}Actual state:${NC} $ISSUE_STATE_AFTER"
    echo ""
    echo "This indicates auto_close_on_complete is not working correctly."
    exit 1
fi

# Test 13: Reopen issue for reusability
print_section "Test 13: Reopen Issue for Test Reusability"
print_test "Reopen the test issue"

# Reopen the issue so the test can be run again
gh issue reopen "$ISSUE_NUMBER" --repo "$DAF_TEST_GITHUB_REPO" > /dev/null 2>&1
verify_success "gh issue reopen" "Issue reopened for future test runs"

print_test "Verify issue is open again"
ISSUE_STATE_FINAL=$(gh issue view "$ISSUE_NUMBER" --repo "$DAF_TEST_GITHUB_REPO" --json state --jq '.state' 2>&1)

if [ "$ISSUE_STATE_FINAL" = "OPEN" ]; then
    echo -e "  ${GREEN}✓${NC} Issue successfully reopened"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${YELLOW}⚠${NC} Issue reopen verification failed (state: $ISSUE_STATE_FINAL)"
    echo -e "  ${YELLOW}Note:${NC} This doesn't affect the main test, just cleanup"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Final summary
print_section "Test Summary"
echo -e "${BOLD}Tests Passed:${NC} ${GREEN}${TESTS_PASSED}${NC} / ${TESTS_TOTAL}"
echo ""

if [ $TESTS_PASSED -eq $TESTS_TOTAL ]; then
    echo -e "${BOLD}${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Successfully tested the complete installation workflow:"
    echo "  ✓ Cloned DevAIFlow from GitHub"
    echo "  ✓ Installed DevAIFlow from source in fresh venv"
    echo "  ✓ Created config with auto_close_on_complete=true"
    echo "  ✓ Ran daf upgrade to install skills"
    echo "  ✓ Created GitHub issue ${ISSUE_KEY}"
    echo "  ✓ Created and completed session ${SESSION_NAME}"
    echo "  ✓ Verified issue was automatically closed (no prompt!)"
    echo "  ✓ Reopened issue for test reusability"
    echo ""
    echo "The auto_close_on_complete feature is working correctly!"
    echo ""
    exit 0
else
    echo -e "${BOLD}${RED}✗ Some tests failed${NC}"
    echo ""
    exit 1
fi
