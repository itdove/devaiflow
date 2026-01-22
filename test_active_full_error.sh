#!/bin/bash
set -e

export DAF_MOCK_MODE=1
export DEVAIFLOW_HOME="/tmp/test-active-full-$$"
mkdir -p "$DEVAIFLOW_HOME"

python3 integration-tests/setup_test_config.py > /dev/null 2>&1

SESSION_JSON=$(daf new --name "test-session" --goal "Test" --path "." --branch test --json 2>&1)

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

export AI_AGENT_SESSION_ID

echo "=== Running daf active with AI_AGENT_SESSION_ID set ==="
daf active 2>&1

# Cleanup
rm -rf "$DEVAIFLOW_HOME"
