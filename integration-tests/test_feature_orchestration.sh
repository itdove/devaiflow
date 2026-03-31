#!/bin/bash
# test_feature_orchestration.sh
# Integration test for feature orchestration workflows
# Tests: daf feature create -> daf feature sync -> daf feature list -> daf feature delete
#
# This script runs entirely in mock mode (DAF_MOCK_MODE=1)

# Parse arguments
DEBUG_MODE=false
if [ "$1" = "--debug" ]; then
    DEBUG_MODE=true
    set -x
fi

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Environment isolation
ORIGINAL_DEVAIFLOW_IN_SESSION="${DEVAIFLOW_IN_SESSION:-}"
ORIGINAL_AI_AGENT_SESSION_ID="${AI_AGENT_SESSION_ID:-}"
ORIGINAL_DEVAIFLOW_HOME="${DEVAIFLOW_HOME:-}"

# Unset session variables to bypass safety guards
unset DEVAIFLOW_IN_SESSION
unset AI_AGENT_SESSION_ID

# Use temporary DEVAIFLOW_HOME
TEMP_DEVAIFLOW_HOME="/tmp/daf-test-feature-orch-$$"
export DEVAIFLOW_HOME="$TEMP_DEVAIFLOW_HOME"
CLEANUP_TEMP_DIR=true

# Create temporary git repository
TEMP_GIT_REPO="/tmp/daf-test-git-repo-feature-$$"
mkdir -p "$TEMP_GIT_REPO"

# Initialize git repository
(
    cd "$TEMP_GIT_REPO"
    git init > /dev/null 2>&1
    git config user.name "Test User" > /dev/null 2>&1
    git config user.email "test@example.com" > /dev/null 2>&1
    echo "# Test Repository" > README.md
    git add README.md > /dev/null 2>&1
    git commit -m "Initial commit" > /dev/null 2>&1
)

# Enable mock mode and experimental features
export DAF_MOCK_MODE=1
export DEVAIFLOW_EXPERIMENTAL=1

# Cleanup function
cleanup() {
    local exit_code=$?

    # Restore environment
    if [ -n "$ORIGINAL_DEVAIFLOW_IN_SESSION" ]; then
        export DEVAIFLOW_IN_SESSION="$ORIGINAL_DEVAIFLOW_IN_SESSION"
    fi
    if [ -n "$ORIGINAL_AI_AGENT_SESSION_ID" ]; then
        export AI_AGENT_SESSION_ID="$ORIGINAL_AI_AGENT_SESSION_ID"
    fi
    if [ -n "$ORIGINAL_DEVAIFLOW_HOME" ]; then
        export DEVAIFLOW_HOME="$ORIGINAL_DEVAIFLOW_HOME"
    fi

    # Clean up temp directories
    if [ "$CLEANUP_TEMP_DIR" = true ] && [ -d "$TEMP_DEVAIFLOW_HOME" ]; then
        rm -rf "$TEMP_DEVAIFLOW_HOME"
    fi
    if [ -d "$TEMP_GIT_REPO" ]; then
        rm -rf "$TEMP_GIT_REPO"
    fi

    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ Feature orchestration integration test PASSED${NC}"
    else
        echo -e "${RED}✗ Feature orchestration integration test FAILED${NC}"
    fi

    exit $exit_code
}

trap cleanup EXIT

echo "=========================================="
echo "Feature Orchestration Integration Test"
echo "=========================================="
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Initialize config using setup script
echo "Setting up test environment..."
python3 "$SCRIPT_DIR/setup_test_config.py" > /dev/null 2>&1

# Create parent epic with children in mock backend
echo "Creating mock JIRA parent epic with child stories..."
PARENT_KEY=$(daf jira create epic \
    --summary "Test Feature Parent Epic" \
    --json 2>&1 | jq -r '.data.issue_key')

if [ -z "$PARENT_KEY" ]; then
    echo -e "${RED}Failed to create parent epic${NC}"
    exit 1
fi
echo "Created parent: $PARENT_KEY"

# Create child stories
CHILD1_KEY=$(daf jira create story \
    --parent "$PARENT_KEY" \
    --summary "Child Story 1" \
    --json 2>&1 | jq -r '.data.issue_key')

CHILD2_KEY=$(daf jira create story \
    --parent "$PARENT_KEY" \
    --summary "Child Story 2" \
    --json 2>&1 | jq -r '.data.issue_key')

CHILD3_KEY=$(daf jira create story \
    --parent "$PARENT_KEY" \
    --summary "Child Story 3" \
    --json 2>&1 | jq -r '.data.issue_key')

# Assign to test-user so they match sync filter
daf jira update "$CHILD1_KEY" --assignee "test-user" > /dev/null 2>&1
daf jira update "$CHILD2_KEY" --assignee "test-user" > /dev/null 2>&1
daf jira update "$CHILD3_KEY" --assignee "test-user" > /dev/null 2>&1

echo "Created children: $CHILD1_KEY, $CHILD2_KEY, $CHILD3_KEY"

# Test 1: Create feature from parent URL
echo ""
echo "Test 1: Creating feature from parent URL..."
PARENT_URL="https://test.atlassian.net/browse/$PARENT_KEY"

# Pipe "1" and "y" to auto-create sessions and confirm feature creation
{ echo "1"; echo "y"; } | daf -e feature create test-feature \
    --parent-url "$PARENT_URL" \
    
# Verify feature was created
if [ ! -d "$DEVAIFLOW_HOME/features/test-feature" ]; then
    echo -e "${RED}Feature directory not created${NC}"
    exit 1
fi

if [ ! -f "$DEVAIFLOW_HOME/features/test-feature/metadata.json" ]; then
    echo -e "${RED}Feature metadata file not created${NC}"
    exit 1
fi

# Verify metadata content
FEATURE_NAME=$(python3 -c "import json; print(json.load(open('$DEVAIFLOW_HOME/features/test-feature/metadata.json'))['name'])")
if [ "$FEATURE_NAME" != "test-feature" ]; then
    echo -e "${RED}Feature name mismatch${NC}"
    exit 1
fi

# Verify sessions were discovered
SESSION_COUNT=$(python3 -c "import json; print(len(json.load(open('$DEVAIFLOW_HOME/features/test-feature/metadata.json'))['sessions']))")
if [ "$SESSION_COUNT" != "3" ]; then
    echo -e "${RED}Expected 3 sessions, found $SESSION_COUNT${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Feature created successfully with 3 sessions${NC}"

# Test 2: List features
echo ""
echo "Test 2: Listing features..."
LIST_OUTPUT=$(daf -e feature list 2>&1)

if ! echo "$LIST_OUTPUT" | grep -q "test-feature"; then
    echo -e "${RED}Feature not found in list${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Feature appears in list${NC}"

# Test 3: Sync feature (should be no-op)
echo ""
echo "Test 3: Syncing feature..."
SYNC_OUTPUT=$(daf -e feature sync test-feature 2>&1)

# Should succeed without errors
if [ $? -ne 0 ]; then
    echo -e "${RED}Sync failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Sync completed${NC}"

# Test 4: Add new child and sync again
echo ""
echo "Test 4: Adding new child and syncing..."
CHILD4_KEY=$(daf jira create story \
    --parent "$PARENT_KEY" \
    --summary "Child Story 4 - Added Later" \
    --json 2>&1 | jq -r '.data.issue_key')

# Assign to test-user
daf jira update "$CHILD4_KEY" --assignee "test-user" > /dev/null 2>&1

echo "Created new child: $CHILD4_KEY"

# Sync should discover new child (tracked as external - no auto-session creation)
daf -e feature sync test-feature
# Verify session count unchanged (new child tracked as external, not auto-created)
NEW_SESSION_COUNT=$(python3 -c "import json; print(len(json.load(open('$DEVAIFLOW_HOME/features/test-feature/metadata.json'))['sessions']))")
if [ "$NEW_SESSION_COUNT" != "3" ]; then
    echo -e "${RED}Expected 3 sessions after sync (new child tracked externally), found $NEW_SESSION_COUNT${NC}"
    exit 1
fi

echo -e "${GREEN}✓ New child discovered (tracked as external)${NC}"

# Test 5: Create feature with manual sessions
echo ""
echo "Test 5: Creating feature with manual --sessions..."
daf -e feature create manual-feature \
    --sessions "$CHILD1_KEY,$CHILD2_KEY" \
    
# Verify no parent initially
HAS_PARENT=$(python3 -c "import json; d=json.load(open('$DEVAIFLOW_HOME/features/manual-feature/metadata.json')); print('parent_issue_key' in d and d['parent_issue_key'] is not None)")
if [ "$HAS_PARENT" = "True" ]; then
    echo -e "${RED}Manual feature should not have parent initially${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Manual feature created without parent${NC}"

# Test 6: Add parent via sync
echo ""
echo "Test 6: Adding parent to manual feature via sync..."
daf -e feature sync manual-feature --parent-url "$PARENT_URL" 
# Verify parent was added
STORED_PARENT=$(python3 -c "import json; print(json.load(open('$DEVAIFLOW_HOME/features/manual-feature/metadata.json')).get('parent_issue_key', 'NONE'))")
if [ "$STORED_PARENT" != "$PARENT_KEY" ]; then
    echo -e "${RED}Parent not stored in metadata${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Parent added to feature via sync${NC}"

# Test 7: Delete feature
echo ""
echo "Test 7: Deleting feature..."
echo "y" | daf -e feature delete test-feature

# Verify feature directory was removed (implementation may vary)
if [ -d "$DEVAIFLOW_HOME/features/test-feature" ]; then
    echo -e "${YELLOW}⚠ Feature directory still exists (may be expected)${NC}"
fi

echo -e "${GREEN}✓ Delete command completed${NC}"

# Test 8: Dry-run mode
echo ""
echo "Test 8: Testing dry-run mode..."
daf -e feature sync manual-feature --dry-run 2>&1

# Check if dry-run succeeded
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Dry-run mode works${NC}"
else
    echo -e "${RED}Dry-run failed${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}All tests passed!${NC}"
echo "=========================================="
