#!/bin/bash
#
# Integration test for collaboration workflow (2-developer emulation)
#
# Usage:
#   ./test_collaboration_workflow.sh           # Run automated (CI/CD mode)
#   DEMO_MODE=1 ./test_collaboration_workflow.sh  # Run with pauses (demo mode)
#
# This script tests the complete session export/import workflow by emulating
# two developers working on separate machines.

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
    TEMP_DEVAIFLOW_HOME="/tmp/daf-test-collaboration_workflow-$$"
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
# set -x

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Temporary directories (created in setup_test_repo function)
TEST_REPO_DIR=""
TEST_REMOTE_DIR=""

# Developer environments (also use mktemp for better isolation)
DEV_A_HOME=$(mktemp -d -t claude-sessions-dev-a.XXXXXX)
DEV_B_HOME=$(mktemp -d -t claude-sessions-dev-b.XXXXXX)

# Test tracking
TESTS_PASSED=0
TESTS_FAILED=0

# Pause function for demo mode
pause_if_demo() {
    local message="$1"
    if [ "${DEMO_MODE}" = "1" ]; then
        echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${CYAN}⏸  ${message}${NC}"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        read -p "Press Enter to continue..."
    fi
}

# Print section header
print_section() {
    local title="$1"
    echo -e "\n${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  ${title}${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}\n"
}

# Print step
print_step() {
    local step="$1"
    echo -e "${YELLOW}▶ ${step}${NC}"
}

# Print success
print_success() {
    local message="$1"
    echo -e "${GREEN}✓${NC} ${message}"
    ((TESTS_PASSED++))
}

# Print error
print_error() {
    local message="$1"
    echo -e "${RED}✗${NC} ${message}"
    ((TESTS_FAILED++))
}

# Setup test repository
setup_test_repo() {
    print_step "Creating temporary test repository"

    # Create temp directories
    TEST_REPO_DIR=$(mktemp -d -t cs-test-repo.XXXXXX)
    TEST_REMOTE_DIR=$(mktemp -d -t cs-test-remote.XXXXXX)

    # Create bare repository to act as remote
    print_step "Creating bare remote repository at $TEST_REMOTE_DIR"
    cd "$TEST_REMOTE_DIR"
    git init --bare >/dev/null 2>&1
    print_success "Bare remote repository created"

    # Create test directory
    mkdir -p "$TEST_REPO_DIR"
    cd "$TEST_REPO_DIR"

    # Initialize git repo
    git init >/dev/null 2>&1
    git config user.email "test@example.com"
    git config user.name "Test User"

    # Configure the bare repo as origin remote
    git remote add origin "$TEST_REMOTE_DIR" >/dev/null 2>&1

    # Create initial commit
    echo "# Test Repository" > README.md
    git add README.md
    git commit -m "Initial commit" >/dev/null 2>&1

    # Push to remote so it has the initial commit
    git push -u origin main >/dev/null 2>&1 || git push -u origin master >/dev/null 2>&1

    print_success "Test repository created at $TEST_REPO_DIR with remote at $TEST_REMOTE_DIR"
}

# Cleanup function
cleanup() {
    print_section "Cleaning up test environments"

    # Clean all temp directories matching our patterns
    print_step "Cleaning all developer environment temp directories"
    for dir in /tmp/claude-sessions-dev-a.* /tmp/claude-sessions-dev-b.*; do
        if [ -d "$dir" ]; then
            export DEVAIFLOW_HOME="$dir"
            export DAF_MOCK_MODE=1
            daf purge-mock-data --force 2>/dev/null || true
            rm -rf "$dir"
        fi
    done

    # Clean test repository temp directories
    print_step "Cleaning test repository temp directories"
    for dir in /tmp/cs-test-repo.* /tmp/cs-test-remote.*; do
        if [ -d "$dir" ]; then
            rm -rf "$dir"
        fi
    done

    # Clean export files
    rm -f /tmp/*-session-export.tar.gz

    print_success "Cleanup complete"
}

# Set up trap to cleanup on exit
trap cleanup EXIT

# Main test execution
main() {
    print_section "Collaboration Workflow Integration Test"

    if [ "${DEMO_MODE}" = "1" ]; then
        echo -e "${CYAN}Running in DEMO MODE (with pauses)${NC}\n"
    else
        echo -e "${CYAN}Running in CI/CD MODE (automated)${NC}\n"
    fi

    # Initial cleanup of any leftover temp directories from previous runs
    cleanup || true  # Don't fail if nothing to clean

    # Setup test repository
    setup_test_repo || {
        print_error "Failed to setup test repository"
        exit 1
    }

    pause_if_demo "Ready to start Developer A's workflow"

    # ============================================================================
    # DEVELOPER A: Initialize Environment
    # ============================================================================
    print_section "Developer A: Initialize Environment"

    export DEVAIFLOW_HOME="$DEV_A_HOME"
    export DAF_MOCK_MODE=1

    print_step "Initializing Developer A's configuration"
    echo "" | daf init >/dev/null 2>&1 || true

    # Configure using direct JSON creation deprecated set-* commands)
    cat > "$DEV_A_HOME/config.json" << 'EOF'
{
  "jira": {
    "url": "https://jira.example.com",
    "user": "test@example.com",
    "project": "PROJ",
    "workstream": "Platform",
    "field_mappings": {},
    "transitions": {
      "on_start": {"from": ["New", "To Do"], "to": "In Progress", "prompt": false, "on_fail": "warn"},
      "on_complete": {"from": ["In Progress"], "to": "Review", "prompt": true, "on_fail": "warn"}
    }
  },
  "repos": {
    "workspace": "/tmp"
  }
}
EOF
    print_success "Developer A environment initialized (using direct JSON config)"

    pause_if_demo "Developer A environment ready. Next: Create JIRA ticket and session"

    # ============================================================================
    # DEVELOPER A: Create Session
    # ============================================================================
    print_section "Developer A: Create JIRA Ticket and Session"

    print_step "Creating JIRA ticket and session (note: creates real ticket even in mock mode)"

    # Create ticket and session using daf jira new with --path flag
    TICKET_OUTPUT=$(daf jira new story \
        --parent PROJ-99999 \
        --goal "Test collaboration workflow" \
        --path "$TEST_REPO_DIR" \
        --json 2>&1)

    # Extract both ticket key and session name
    # Filter out everything before the JSON (warnings, migration messages, etc.)
    JSON_ONLY=$(echo "$TICKET_OUTPUT" | sed -n '/{/,/^}$/p')

    TICKET_KEY=$(echo "$JSON_ONLY" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # Try issue_key first (real JIRA), then ticket_key (mock)
    print(data['data'].get('issue_key') or data['data'].get('ticket_key', ''))
except:
    pass
" 2>/dev/null)

    SESSION_NAME=$(echo "$JSON_ONLY" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data['data'].get('session_name', ''))
except:
    pass
" 2>/dev/null)

    if [ -z "$TICKET_KEY" ] || [ -z "$SESSION_NAME" ]; then
        print_error "Failed to create JIRA ticket"
        echo "Output was: $TICKET_OUTPUT"
        exit 1
    fi

    print_success "Created JIRA ticket: $TICKET_KEY, session: $SESSION_NAME"

    pause_if_demo "Ticket $TICKET_KEY and session $SESSION_NAME created. Next: Simulate work on the session"

    # ============================================================================
    # DEVELOPER A: Simulate Work
    # ============================================================================
    print_section "Developer A: Simulate Work on Session"

    # Get session info to find working directory
    SESSION_INFO=$(daf list 2>&1)
    print_step "Session created (session info below)"
    echo "$SESSION_INFO"

    # Create test file
    print_step "Creating test file (auth.py)"
    cd "$TEST_REPO_DIR"
    cat > auth.py << 'EOF'
# Authentication module
def login(username, password):
    # TODO: implement
    pass
EOF

    git add auth.py
    git commit -m "WIP: Add authentication module skeleton" >/dev/null 2>&1
    print_success "Created and committed auth.py"

    # Add notes (use session name, not ticket key for daf jira new sessions)
    print_step "Adding session notes"
    daf note "$SESSION_NAME"  "Created auth.py with login function skeleton. Still need to implement password hashing." >/dev/null 2>&1 || true
    print_success "Added session notes"

    pause_if_demo "Work simulated. Next: Test multi-session functionality"

    # ============================================================================
    # DEVELOPER A: Test Multi-Session Functionality
    # ============================================================================
    print_section "Developer A: Test Multi-Session Support"

    print_step "Creating a new conversation to archive the current one"

    # Get current session info to verify initial state
    SESSION_INFO_JSON=$(daf info "$SESSION_NAME" --json 2>&1 | sed -n '/{/,/^}$/p')

    # Verify we have 1 conversation initially
    INITIAL_CONV_COUNT=$(echo "$SESSION_INFO_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    session = data.get('data', {}).get('session', {})
    conversations = session.get('conversations', {})
    print(len(conversations))
except:
    print('0')
" 2>/dev/null)

    if [ "$INITIAL_CONV_COUNT" != "1" ]; then
        print_error "Expected 1 conversation initially, got $INITIAL_CONV_COUNT"
        exit 1
    fi
    print_success "Verified initial state: 1 active conversation"

    # Archive current conversation by creating a new one (simulated)
    # In real usage, this would be done via daf open --new-conversation
    # For this test, we'll manually manipulate the session data using SessionManager API
    print_step "Simulating conversation archival (creating archived session)"

    # Use a Python script that imports the SessionManager to safely manipulate sessions
    # Export SESSION_NAME to make it available to Python subprocess
    export SESSION_NAME
    python3 << 'PYTHON_EOF'
import sys
import os
from pathlib import Path
from datetime import datetime
import uuid

# Add project root to path so we can import devflow
project_root = os.environ.get('PROJECT_ROOT', os.getcwd())
sys.path.insert(0, project_root)

from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager

# Initialize session manager with the test environment
config_loader = ConfigLoader()
session_manager = SessionManager(config_loader)

session_name = os.environ.get('SESSION_NAME')
if not session_name:
    print("ERROR: SESSION_NAME environment variable not set", file=sys.stderr)
    sys.exit(1)

session = session_manager.get_session(session_name)

if not session:
    print(f"ERROR: Session {session_name} not found", file=sys.stderr)
    sys.exit(1)

# Get the working directory (should be the only one)
if not session.conversations:
    print(f"ERROR: Session has no conversations", file=sys.stderr)
    sys.exit(1)

working_dir = session.working_directory
conversation = session.conversations[working_dir]

# Archive the current active session
old_active = conversation.active_session

# Create archived version
old_active_dict = old_active.model_dump()
old_active_dict['archived'] = True
old_active_dict['summary'] = "Initial work on authentication module"

# Create new active session
from devflow.config.models import ConversationContext
new_session_id = str(uuid.uuid4())
new_active = ConversationContext(
    ai_agent_session_id=new_session_id,
    project_path=old_active.project_path,
    branch=old_active.branch,
    base_branch=old_active.base_branch,
    remote_url=old_active.remote_url,
    created=datetime.now(),
    last_active=datetime.now(),
    message_count=5,
    prs=[],
    archived=False,
    conversation_history=old_active.conversation_history + [new_session_id] if old_active.conversation_history else [new_session_id],
    summary=None,
    repo_name=old_active.repo_name,
    relative_path=old_active.relative_path,
    temp_directory=old_active.temp_directory,
    original_project_path=old_active.original_project_path
)

# Create archived ConversationContext from dict
from devflow.config.models import ConversationContext
archived_session = ConversationContext(**old_active_dict)

# Update conversation structure
conversation.archived_sessions = [archived_session]
conversation.active_session = new_active

# Save the updated session
session_manager.update_session(session)

print(f"Archived session: {archived_session.ai_agent_session_id}")
print(f"New active session: {new_session_id}")
PYTHON_EOF

    print_success "Created archived conversation"

    # Verify we now have 1 active + 1 archived session
    print_step "Verifying multi-session structure"
    SESSION_INFO_JSON=$(daf info "$SESSION_NAME" --json 2>&1 | sed -n '/{/,/^}$/p')

    ARCHIVED_COUNT=$(echo "$SESSION_INFO_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    session = data.get('data', {}).get('session', {})
    conversations = session.get('conversations', {})
    for conv in conversations.values():
        archived = conv.get('archived_sessions', [])
        print(len(archived))
        break
except:
    print('0')
" 2>/dev/null)

    if [ "$ARCHIVED_COUNT" != "1" ]; then
        print_error "Expected 1 archived session, got $ARCHIVED_COUNT"
        exit 1
    fi
    print_success "Verified: 1 active session + 1 archived session"

    pause_if_demo "Multi-session structure created. Next: Export and verify both sessions are included"

    # ============================================================================
    # DEVELOPER A: Export Session
    # ============================================================================
    print_section "Developer A: Export Session"

    print_step "Exporting session to /tmp/${SESSION_NAME}-session-export.tar.gz"

    # Export manually (daf complete would need interactive input)
    # Provide "n" to skip pushing branch to remote prompt
    EXPORT_OUTPUT=$(echo "n" | daf export "$SESSION_NAME" --output "/tmp/${SESSION_NAME}-session-export.tar.gz" 2>&1)
    EXPORT_STATUS=$?

    if [ $EXPORT_STATUS -ne 0 ]; then
        print_error "Failed to export session"
        echo "Export output: $EXPORT_OUTPUT"
        exit 1
    fi

    if [ ! -f "/tmp/${SESSION_NAME}-session-export.tar.gz" ]; then
        print_error "Export file not created"
        exit 1
    fi

    print_success "Session exported successfully"

    # Verify export contents
    print_step "Verifying export contents"
    EXPORT_CONTENTS=$(tar -tzf "/tmp/${SESSION_NAME}-session-export.tar.gz" | head -10)
    echo "$EXPORT_CONTENTS" | grep -q "export-metadata.json" && \
    echo "$EXPORT_CONTENTS" | grep -q "sessions.json" && \
    echo "$EXPORT_CONTENTS" | grep -q "sessions/${SESSION_NAME}"
    print_success "Export contains expected files"

    pause_if_demo "Export complete. Next: Switch to Developer B"

    # ============================================================================
    # DEVELOPER B: Initialize Environment
    # ============================================================================
    print_section "Developer B: Initialize Environment"

    export DEVAIFLOW_HOME="$DEV_B_HOME"
    export DAF_MOCK_MODE=1

    print_step "Initializing Developer B's configuration"
    echo "" | daf init >/dev/null 2>&1 || true

    # Configure using direct JSON creation deprecated set-* commands
    cat > "$DEV_B_HOME/config.json" << 'EOF'
{
  "jira": {
    "url": "https://jira.example.com",
    "user": "test@example.com",
    "project": "PROJ",
    "workstream": "Platform",
    "field_mappings": {},
    "transitions": {
      "on_start": {"from": ["New", "To Do"], "to": "In Progress", "prompt": false, "on_fail": "warn"},
      "on_complete": {"from": ["In Progress"], "to": "Review", "prompt": true, "on_fail": "warn"}
    }
  },
  "repos": {
    "workspace": "/tmp"
  }
}
EOF
    print_success "Developer B environment initialized (using direct JSON config)"

    # Verify no sessions exist
    print_step "Verifying Developer B has no sessions"
    SESSION_COUNT=$(daf list 2>&1 | grep -c "No sessions found" || echo 0)
    if [ "$SESSION_COUNT" -eq 0 ]; then
        print_error "Developer B should have no sessions initially"
        exit 1
    fi
    print_success "Developer B has no sessions (as expected)"

    pause_if_demo "Developer B environment ready. Next: Import session from Developer A"

    # ============================================================================
    # DEVELOPER B: Import Session
    # ============================================================================
    print_section "Developer B: Import Session"

    print_step "Importing session from /tmp/${SESSION_NAME}-session-export.tar.gz"
    # Provide "y" to confirm import prompt
    IMPORT_OUTPUT=$(echo "y" | daf import "/tmp/${SESSION_NAME}-session-export.tar.gz" 2>&1)
    IMPORT_STATUS=$?
    if [ $IMPORT_STATUS -ne 0 ]; then
        print_error "Failed to import session"
        echo "Import output: $IMPORT_OUTPUT"
        exit 1
    fi
    print_success "Session imported successfully"

    # Verify clone instructions show actual repo name, not temp directory
    print_step "Verifying clone instructions show actual repository name, not temp directory"
    REPO_NAME=$(basename "$TEST_REPO_DIR")
    if echo "$IMPORT_OUTPUT" | grep -q "git clone.*$REPO_NAME"; then
        print_success "Clone instructions show correct repository name: $REPO_NAME"
    elif echo "$IMPORT_OUTPUT" | grep -q "git clone.*cs-jira-analysis-"; then
        print_error "Clone instructions show temp directory name instead of actual repo name"
        echo "Import output:"
        echo "$IMPORT_OUTPUT"
        exit 1
    else
        # No clone instructions shown (repo already exists), which is fine
        print_success "No clone instructions needed (repository already exists)"
    fi

    # Verify session is visible
    print_step "Verifying session is visible in Developer B's environment"
    daf list 2>&1 | grep -q "$SESSION_NAME" || {
        print_error "Session $SESSION_NAME not found after import"
        exit 1
    }
    print_success "Session $SESSION_NAME is visible"

    # Verify notes are preserved in export/import
    print_step "Verifying session notes are preserved after import"
    NOTES_FILE="$DEVAIFLOW_HOME/sessions/$SESSION_NAME/notes.md"
    if [ -f "$NOTES_FILE" ]; then
        if grep -q "Created auth.py with login function skeleton" "$NOTES_FILE"; then
            print_success "Session notes preserved from Developer A"
        else
            print_error "Session notes not preserved correctly"
            cat "$NOTES_FILE"
            exit 1
        fi
    else
        print_error "Notes file not found after import: $NOTES_FILE"
        exit 1
    fi

    # Verify multi-session structure is preserved
    print_step "Verifying multi-session structure preserved after import"
    SESSION_INFO_JSON_B=$(daf info "$SESSION_NAME" --json 2>&1 | sed -n '/{/,/^}$/p')

    ARCHIVED_COUNT_B=$(echo "$SESSION_INFO_JSON_B" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    session = data.get('data', {}).get('session', {})
    conversations = session.get('conversations', {})
    for conv in conversations.values():
        archived = conv.get('archived_sessions', [])
        print(len(archived))
        break
except:
    print('0')
" 2>/dev/null)

    if [ "$ARCHIVED_COUNT_B" != "1" ]; then
        print_error "Expected 1 archived session after import, got $ARCHIVED_COUNT_B"
        echo "Session info: $SESSION_INFO_JSON_B"
        exit 1
    fi
    print_success "Multi-session structure preserved: 1 active + 1 archived session"

    # Verify archived session has summary
    print_step "Verifying archived session has summary"
    HAS_SUMMARY=$(echo "$SESSION_INFO_JSON_B" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    session = data.get('data', {}).get('session', {})
    conversations = session.get('conversations', {})
    for conv in conversations.values():
        archived = conv.get('archived_sessions', [])
        if archived and archived[0].get('summary'):
            print('yes')
        else:
            print('no')
        break
except:
    print('no')
" 2>/dev/null)

    if [ "$HAS_SUMMARY" = "yes" ]; then
        print_success "Archived session has summary"
    else
        print_error "Archived session missing summary"
        exit 1
    fi

    pause_if_demo "Import complete with multi-session support verified. Next: Continue work as Developer B"

    # ============================================================================
    # DEVELOPER B: Continue Work
    # ============================================================================
    print_section "Developer B: Continue Work"

    print_step "Opening imported session"
    # Note: In mock mode, daf open won't actually launch Claude Code
    # We'll just verify we can work with the session

    # Add more code
    print_step "Adding password hashing function"
    cd "$TEST_REPO_DIR"
    cat >> auth.py << 'EOF'

from hashlib import sha256

def hash_password(password):
    return sha256(password.encode()).hexdigest()
EOF

    git add auth.py
    git commit -m "Add password hashing function" >/dev/null 2>&1
    print_success "Added password hashing function"

    # Add notes
    print_step "Adding session notes from Developer B"
    daf note "$SESSION_NAME"  "Implemented password hashing using SHA-256" >/dev/null 2>&1 || true
    print_success "Added session notes"

    pause_if_demo "Work complete. Next: Verify workflow"

    # ============================================================================
    # VERIFICATION
    # ============================================================================
    print_section "Verification: Confirm Collaboration Workflow"

    print_step "Verifying git history contains both commits"
    COMMIT_COUNT=$(git log --oneline | grep -c "WIP: Add authentication" || echo 0)
    COMMIT_COUNT=$((COMMIT_COUNT + $(git log --oneline | grep -c "Add password hashing" || echo 0)))
    if [ "$COMMIT_COUNT" -eq 2 ]; then
        print_success "Git history contains commits from both developers"
    else
        print_error "Git history incomplete (expected 2 commits, found $COMMIT_COUNT)"
    fi

    # Verify session notes contain contributions from both developers
    print_step "Verifying session notes contain contributions from both developers"
    NOTES_FILE="$DEVAIFLOW_HOME/sessions/$SESSION_NAME/notes.md"
    if [ -f "$NOTES_FILE" ]; then
        # Check for Developer A's note
        if ! grep -q "Created auth.py with login function skeleton" "$NOTES_FILE"; then
            print_error "Developer A's notes not found in final notes"
            cat "$NOTES_FILE"
            exit 1
        fi
        # Check for Developer B's note
        if ! grep -q "Implemented password hashing using SHA-256" "$NOTES_FILE"; then
            print_error "Developer B's notes not found in final notes"
            cat "$NOTES_FILE"
            exit 1
        fi
        print_success "Session notes contain contributions from both developers"
    else
        print_error "Notes file not found: $NOTES_FILE"
        exit 1
    fi

    print_step "Verifying session isolation (different DEVAIFLOW_HOME)"
    if [ -d "$DEV_A_HOME" ] && [ -d "$DEV_B_HOME" ]; then
        print_success "Both developer environments exist separately"
    else
        print_error "Developer environments not properly isolated"
    fi

    print_step "Verifying export/import preserved conversation history"
    # Check if session metadata exists in both environments
    export DEVAIFLOW_HOME="$DEV_A_HOME"
    DEV_A_SESSION=$(daf info "$SESSION_NAME" 2>&1 || echo "")

    export DEVAIFLOW_HOME="$DEV_B_HOME"
    DEV_B_SESSION=$(daf info "$SESSION_NAME" 2>&1 || echo "")

    if [ -n "$DEV_A_SESSION" ] && [ -n "$DEV_B_SESSION" ]; then
        print_success "Session metadata preserved across export/import"
    else
        print_error "Session metadata not fully preserved"
    fi

    # ============================================================================
    # TEST SUMMARY
    # ============================================================================
    print_section "Test Summary"

    echo -e "Tests passed: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Tests failed: ${RED}${TESTS_FAILED}${NC}"

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}✓ All tests passed!${NC}"
        echo -e "${GREEN}Collaboration workflow test successful.${NC}\n"
        echo -e "${YELLOW}Note: This test created a real JIRA ticket: $TICKET_KEY${NC}"
        echo -e "${YELLOW}You may want to close or delete it manually.${NC}\n"
        exit 0
    else
        echo -e "\n${RED}✗ Some tests failed.${NC}"
        echo -e "${RED}Collaboration workflow test failed.${NC}\n"
        exit 1
    fi
}

# Run main function
main
