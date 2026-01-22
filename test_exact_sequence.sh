#!/bin/bash
set -e

export DAF_MOCK_MODE=1
export DEVAIFLOW_HOME="/tmp/test-exact-$$"
mkdir -p "$DEVAIFLOW_HOME"

# Same as test script
TEST_SESSION="readonly-test"
TEST_GOAL="Test read-only commands"

echo "Step 1: Setup config"
python3 integration-tests/setup_test_config.py > /dev/null 2>&1

echo "Step 2: Create session"
SESSION_JSON=$(daf new --name "$TEST_SESSION" --goal "$TEST_GOAL" --path "." --branch test-branch --json 2>&1)

echo "Step 3: Extract AI_AGENT_SESSION_ID"
AI_AGENT_SESSION_ID=$(echo "$SESSION_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    session = data.get('data', {}).get('session', {})
    conversations = session.get('conversations', {})
    for conv in conversations.values():
        active = conv.get('active_session', {})
        print(active.get('ai_agent_session_id', ''))
        break
except:
    pass
" 2>/dev/null)

if [ -z "$AI_AGENT_SESSION_ID" ]; then
    echo "Failed to extract AI_AGENT_SESSION_ID"
    exit 1
fi

echo "AI_AGENT_SESSION_ID: ${AI_AGENT_SESSION_ID:0:8}..."

echo "Step 4: Export AI_AGENT_SESSION_ID"
export AI_AGENT_SESSION_ID

echo "Step 5: Run daf note (should be blocked)"
echo "Command: daf note \"$TEST_SESSION\" \"This should fail\""
NOTE_OUTPUT=$(timeout 10 daf note "$TEST_SESSION" "This should fail" 2>&1)
NOTE_EXIT=$?

echo ""
echo "Exit code: $NOTE_EXIT"
echo "Output:"
echo "$NOTE_OUTPUT"

rm -rf "$DEVAIFLOW_HOME"
