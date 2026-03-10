#!/bin/bash
# Real demo using tmux to automate DevAIFlow GitHub workflow
# This executes actual daf commands against itdove/devaiflow-demos repository

set -e

# Configuration
DEMO_REPO="itdove/devaiflow-demos"
DEMO_REPO_PATH="../../devaiflow-demos"
SESSION_NAME="daf-demo"
LOG_FILE="./demo-github-workflow-$(date +%Y%m%d-%H%M%S).log"
TYPING_DELAY=0.05
COMMAND_DELAY=2

# Colors for informational output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Track buffer length to detect new content
LAST_BUFFER_LENGTH=0

# Function to send keys with typing simulation
send_command() {
    local cmd="$1"
    local delay="${2:-$COMMAND_DELAY}"

    # Type the command character by character
    for ((i=0; i<${#cmd}; i++)); do
        char="${cmd:$i:1}"
        tmux send-keys -t "$SESSION_NAME" -l "$char"
        sleep "$TYPING_DELAY"
    done

    # Press Enter
    tmux send-keys -t "$SESSION_NAME" C-m

    # Wait for command to complete
    sleep "$delay"
}

# Function to extract issue number from tmux pane
extract_issue_number() {
    local pane_content=$(tmux capture-pane -t "$SESSION_NAME" -p | sed 's/\x1b\[[0-9;]*m//g')
    local issue_number=$(echo "$pane_content" | grep -oE "${DEMO_REPO}#[0-9]+" | tail -1 | grep -oE "[0-9]+")

    if [ -n "$issue_number" ]; then
        echo "$issue_number"
        return 0
    else
        echo -e "${YELLOW}Warning: Could not extract issue number${NC}" >&2
        return 1
    fi
}

# Function to extract session name from tmux pane
extract_session_name() {
    local debug="${1:-false}"
    local pane_content=$(tmux capture-pane -t "$SESSION_NAME" -p | sed 's/\x1b\[[0-9;]*m//g')

    if [ "$debug" = "true" ]; then
        echo -e "${DIM}=== Pane content for session extraction ===${NC}" >&2
        echo "$pane_content" >&2
        echo -e "${DIM}=========================================${NC}" >&2
    fi

    # Pattern: "Created session: SESSION_NAME (itdove/devaiflow-demos#NNN)"
    local session_name=$(echo "$pane_content" | grep -oE "Created session: [^ ]+ \(" | sed 's/Created session: //; s/ ($//')

    if [ -n "$session_name" ]; then
        echo "$session_name"
        return 0
    else
        echo -e "${YELLOW}Warning: Could not extract session name${NC}" >&2
        if [ "$debug" = "true" ]; then
            echo -e "${DIM}Looking for pattern: 'Created session: [^ ]+ (' ${NC}" >&2
        fi
        return 1
    fi
}

# Function to wait for specific text in tmux pane (searches only new content)
wait_for_prompt() {
    local prompt_text="$1"
    local timeout="${2:-30}"
    local elapsed=0
    local debug="${3:-false}"
    local conditional="${4:-false}"

    if [ "$conditional" != "true" ]; then
        echo -e "${YELLOW}Waiting for: ${prompt_text}${NC}"
    fi

    while [ $elapsed -lt $timeout ]; do
        # Capture entire scrollback history and strip ANSI color codes
        # -S - means start from beginning of scrollback history
        local pane_content=$(tmux capture-pane -t "$SESSION_NAME" -p -S - | sed 's/\x1b\[[0-9;]*m//g')

        # Get total length of content
        local current_length=${#pane_content}

        if [ "$debug" = "true" ]; then
            echo -e "${DIM}Buffer length: $LAST_BUFFER_LENGTH -> $current_length${NC}"
            echo -e "${DIM}New content: ${pane_content:$LAST_BUFFER_LENGTH:200}${NC}"
            echo -e "${DIM}---${NC}"
        fi

        # Only search new content added since last check
        local new_content="${pane_content:$LAST_BUFFER_LENGTH}"

        # Check if prompt_text exists in the new content
        if [[ "$new_content" == *"$prompt_text"* ]]; then
            # Find position of match in new_content
            local before_match="${new_content%%$prompt_text*}"
            local match_pos_in_new=$((${#before_match}))

            # Update buffer length to position after the match
            LAST_BUFFER_LENGTH=$((LAST_BUFFER_LENGTH + match_pos_in_new + ${#prompt_text}))

            if [ "$conditional" != "true" ]; then
                echo -e "${GREEN}✓ Found prompt at position $LAST_BUFFER_LENGTH${NC}"
            fi
            return 0
        fi

        sleep 0.5
        elapsed=$((elapsed + 1))
    done

    # On timeout
    if [ "$conditional" = "true" ]; then
        # Conditional mode: silently return false
        return 1
    else
        # Default mode: show error and return false
        echo -e "${YELLOW}Timeout waiting for: $prompt_text${NC}"
        echo -e "${DIM}Last 500 chars of new content (from position $LAST_BUFFER_LENGTH):${NC}"
        local pane_content=$(tmux capture-pane -t "$SESSION_NAME" -p -S - | sed 's/\x1b\[[0-9;]*m//g')
        echo "${pane_content:$LAST_BUFFER_LENGTH:500}"
        return 1
    fi
}

# Cleanup function
cleanup() {
    echo -e "${YELLOW}Cleaning up tmux session...${NC}"
    # Stop logging
    tmux pipe-pane -t "$SESSION_NAME" -o 2>/dev/null || true
    tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
    echo -e "${GREEN}Log file saved: $LOG_FILE${NC}"
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${YELLOW}Error: tmux is not installed${NC}"
    echo "Install with: brew install tmux"
    exit 1
fi

# Check if daf is installed
if ! command -v daf &> /dev/null; then
    echo -e "${YELLOW}Error: daf is not installed${NC}"
    echo "Install DevAIFlow first"
    exit 1
fi

echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${CYAN}  DevAIFlow - GitHub Issue Workflow Demo${NC}"
echo -e "${BOLD}${CYAN}  Repository: ${DEMO_REPO}${NC}"
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "This demo will:"
echo "  1. Create a new task with 'daf git new task'"
echo "     - Capture the created issue number"
echo "     - Assign the issue to yourself using gh CLI"
echo "  2. Sync the issue with 'daf sync'"
echo "     - Capture the new session name"
echo "  3. Open the session with 'daf open <session-name>'"
echo "  4. Exit the session"
echo ""
echo -e "${YELLOW}Press Enter to start the demo, or Ctrl+C to cancel...${NC}"
read -r

# Kill any existing session
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# Create new tmux session
echo -e "${GREEN}Creating tmux session: $SESSION_NAME${NC}"
tmux new-session -d -s "$SESSION_NAME" -x 120 -y 30

# Start logging tmux output
echo -e "${GREEN}Logging output to: $LOG_FILE${NC}"
tmux pipe-pane -t "$SESSION_NAME" -o "cat >> '$LOG_FILE'"

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}To watch the demo live, open a new terminal and run:${NC}"
echo -e "${BOLD}${CYAN}  tmux attach -t $SESSION_NAME -r${NC}"
echo -e "${DIM}(The -r flag makes it read-only so you can just watch)${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Press Enter to start sending commands...${NC}"
read -r

# Set up the environment
tmux send-keys -t "$SESSION_NAME" "cd $DEMO_REPO_PATH" C-m
sleep 1

# Clear screen
tmux send-keys -t "$SESSION_NAME" "clear" C-m
sleep 1

echo ""
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  STEP 1: Create new task${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Create a new task with daf git new
send_command "daf git new task -w ai --goal \"increment counter in the demo_counter.txt file\"" 2

# Wait for working directory prompt and send selection
wait_for_prompt "Selection:" 10
send_command "devaiflow-demos"

# Wait for git branch creation prompt
wait_for_prompt "Clone project in a temporary directory to ensure analysis is based on main branch? [y/n] (y):" 10
tmux send-keys -t "$SESSION_NAME" "y" C-m

# Wait for base branch
wait_for_prompt "1. main (default - from origin" 10
tmux send-keys -t "$SESSION_NAME" "1" C-m

# Wait for trust folder prompt
wait_for_prompt "Yes, I trust this folder" 30
tmux send-keys -t "$SESSION_NAME" C-m

# Wait for authorization to create ticket
wait_for_prompt "Bash(daf git create" 360
wait_for_prompt "Do you want to proceed?" 10
sleep 1
tmux send-keys -t "$SESSION_NAME" C-m

if wait_for_prompt "Bash(daf git view" 30 true true; then
    wait_for_prompt "Do you want to proceed?" 120
    sleep 1
    tmux send-keys -t "$SESSION_NAME" C-m
fi

# Wait for issue to be created and capture the issue number
sleep 3
echo -e "${CYAN}Extracting issue number...${NC}"
ISSUE_NUMBER=$(extract_issue_number)

if [ -n "$ISSUE_NUMBER" ]; then
    echo -e "${GREEN}✓ Captured issue number: #${ISSUE_NUMBER}${NC}"
else
    echo -e "${YELLOW}⚠ Could not capture issue number${NC}"
fi

sleep 7
tmux send-keys -t "$SESSION_NAME" "exit" C-m

# Assign the issue to yourself using gh CLI
if [ -n "$ISSUE_NUMBER" ]; then
    echo ""
    echo -e "${CYAN}Assigning issue #${ISSUE_NUMBER} to yourself...${NC}"
    gh issue edit "$ISSUE_NUMBER" --repo "$DEMO_REPO" --add-assignee "@me"
    echo -e "${GREEN}✓ Issue assigned${NC}"
fi

sleep 10
tmux send-keys -t "$SESSION_NAME" "y" C-m

echo -e "${GREEN}✓ Task created${NC}"
echo ""

echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  STEP 2: Synchronization${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

# Step 3: Sync
send_command "daf sync -w ai --repo $DEMO_REPO" 2

# Wait for sync to complete and capture session name
sleep 10
echo -e "${CYAN}Extracting session name...${NC}"
DAF_SESSION_NAME=$(extract_session_name true)

if [ -n "$DAF_SESSION_NAME" ]; then
    echo -e "${GREEN}✓ Captured session name: ${DAF_SESSION_NAME}${NC}"
else
    echo -e "${YELLOW}⚠ Could not capture session name${NC}"
fi

echo -e "${GREEN}✓ Task synced${NC}"
echo ""

echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  STEP 3: Open Session${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

# Step 3: Open the session
if [ -n "$DAF_SESSION_NAME" ]; then
    send_command "daf open $DAF_SESSION_NAME" 2
    echo -e "${GREEN}✓ Session opened${NC}"
else
    echo -e "${YELLOW}⚠ Skipping open - no session name captured${NC}"
fi
echo ""

# Wait for working directory prompt and send selection
wait_for_prompt "Selection:" 10
send_command "devaiflow-demos"

# Wait for working directory prompt and send selection
wait_for_prompt "Would you like to create a new branch? [y/n] (y):" 10
tmux send-keys -t "$SESSION_NAME" "y" C-m

# Wait for working directory prompt and send selection
wait_for_prompt "Enter branch name" 10
tmux send-keys -t "$SESSION_NAME" C-m

# Wait for working directory prompt and send selection
wait_for_prompt "Enter source branch" 10
tmux send-keys -t "$SESSION_NAME" C-m

wait_for_prompt "daf git view itdove/devaiflow-demos" 120
sleep 1
tmux send-keys -t "$SESSION_NAME" C-m

wait_for_prompt "./increment_counter.sh" 120
wait_for_prompt "Do you want to proceed?" 120
sleep 1
tmux send-keys -t "$SESSION_NAME" C-m

wait_for_prompt "git add demo_counter.txt" 120
wait_for_prompt "Do you want to proceed?" 120
sleep 1
tmux send-keys -t "$SESSION_NAME" C-m

wait_for_prompt "git commit -m" 120
wait_for_prompt "Do you want to proceed?" 120
sleep 1
tmux send-keys -t "$SESSION_NAME" C-m

wait_for_prompt "daf git add-comment" 120
wait_for_prompt "Do you want to proceed?" 120
sleep 1
tmux send-keys -t "$SESSION_NAME" C-m

sleep 5
tmux send-keys -t "$SESSION_NAME" "exit" C-m

echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  STEP 4: Complete${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

wait_for_prompt "daf complete" 120
tmux send-keys -t "$SESSION_NAME" "y" C-m


echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  STEP 5: Exit${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

# Step 4: Exit
# send_command "exit" 2

echo -e "${GREEN}✓ Exited${NC}"
echo ""

echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}  Demo Complete!${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "The demo completed:"
echo "  ✅ Created task with 'daf git new task'"
echo "  ✅ Captured issue number: #${ISSUE_NUMBER}"
echo "  ✅ Assigned issue to yourself"
echo "  ✅ Synced with 'daf sync'"
echo "  ✅ Captured session name: ${DAF_SESSION_NAME}"
echo "  ✅ Exited"
echo ""
echo -e "${CYAN}📝 Full output logged to: ${LOG_FILE}${NC}"
echo ""
echo -e "${YELLOW}Press Enter to attach to the tmux session to see the results...${NC}"
read -r

# Attach to the session
tmux attach -t "$SESSION_NAME"
