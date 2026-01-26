# Testing Collaboration Workflow: 2-Developer Emulation

This document describes how to test the DevAIFlow collaboration features by emulating 2 developers working together on your own laptop.

## Overview

The DevAIFlow supports team collaboration through session export/import functionality. This allows developers to hand off work by exporting sessions with full conversation history and git branches, and teammates can import and continue the work seamlessly.

This guide shows you how to **test this workflow yourself** on a single machine by simulating two different developers.

## Two Testing Approaches

You can test the collaboration workflow in two ways:

### Approach 1: With Mock Mode (Recommended for Testing)
- ✅ **Fast and automated**: Run `test_collaboration_workflow.sh`
- ✅ **No real JIRA tickets**: Uses mock JIRA data
- ✅ **Claude Code skipped**: Faster testing
- ✅ **Perfect for CI/CD**: Isolated and repeatable
- 📘 **See Section A below** for mock mode testing

### Approach 2: Without Mock Mode (For Real Integration Testing)
- ✅ **Real Claude Code**: Tests actual Claude Code integration
- ✅ **Real JIRA tickets**: Creates actual tickets (requires cleanup)
- ✅ **Full conversation export/import**: Validates complete workflow
- ✅ **Manual testing**: Step-by-step guided workflow
- 📘 **See Section B below** for no-mock mode testing

---

# Section A: Testing WITH Mock Mode

This section describes testing with `DAF_MOCK_MODE=1` enabled.

## Prerequisites (Mock Mode)

1. **DevAIFlow installed**: `daf` command available
2. **Git repository**: A test repository to work with
3. **Mock mode enabled**: `DAF_MOCK_MODE=1`
4. **Two separate config directories**: To simulate different developers

## What You'll Test (Mock Mode)

- ✅ Developer A can create a session, make progress, and export it
- ✅ Developer B can import the session and continue work seamlessly
- ✅ Conversation history is preserved (empty in mock mode)
- ✅ Git branches are properly synchronized
- ✅ Session notes and metadata are maintained
- ✅ Time tracking switches to the new user
- ✅ Mock JIRA integration works

**Automated Test Available**: Run [test_collaboration_workflow.sh](test_collaboration_workflow.sh) for fully automated testing.

## Setup: Creating Two Developer Environments

### Option 1: Using Different DEVAIFLOW_HOME Directories (Recommended)

This is the simplest approach - use different `DEVAIFLOW_HOME` environment variables to simulate two developers with completely separate configurations.

```bash
# Developer A's environment
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a"
export DAF_MOCK_MODE=1

# Developer B's environment
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
export DAF_MOCK_MODE=1
```

### Option 2: Using Different Workspaces (Alternative)

You can also keep the same `DEVAIFLOW_HOME` but configure different workspace paths. This simulates developers with different repository locations.

```bash
# Developer A
export DAF_MOCK_MODE=1
daf config set-workspace ~/projects/dev-a

# Developer B
export DAF_MOCK_MODE=1
daf config set-workspace ~/projects/dev-b
```

**For this guide, we'll use Option 1 (separate DEVAIFLOW_HOME directories)** as it provides complete isolation.

## Test Scenario: Simple Single-Conversation Handoff

This is the simplest test case: one session, one conversation, one repository.

### Cleanup: Restarting from Scratch

If you need to restart the test from the beginning, clean up all test data:

```bash
# Clean Developer A's environment
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a"
export DAF_MOCK_MODE=1
daf purge-mock-data --force
rm -rf $DEVAIFLOW_HOME-dev-a

# Clean Developer B's environment
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
export DAF_MOCK_MODE=1
daf purge-mock-data --force
rm -rf $DEVAIFLOW_HOME-dev-b

# Clean up any git branches created during testing
cd ~/development/workspace/devaiflow
git branch | grep -E 'aap-[0-9]+-' | xargs -r git branch -D

# Clean up test files
rm -f ~/development/workspace/devaiflow/auth.py
rm -f /tmp/*-session-export.tar.gz
```

**Note**: The JIRA tickets created during testing (e.g., PROJ-12345) will remain in JIRA. These are harmless test tickets, but you may want to close or delete them manually if desired.

### Step 1: Initialize Developer A's Environment

```bash
# Set up Developer A's environment
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a"
export DAF_MOCK_MODE=1

# Initialize configuration (if first time)
daf init

# Configure required settings
daf config set-project PROJ
daf config set-workstream Platform
daf config set-workspace ~/development/workspace

# Verify configuration
daf config show
```

**Expected Output**:
```
✓ Initialized configuration at: $DEVAIFLOW_HOME-dev-a/config.json
Project: PROJ
Workstream: Platform
Workspace: /Users/yourname/development/workspace
```

### Step 2: Developer A Creates and Works on Session

```bash
# Still as Developer A (DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a")
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a"
export DAF_MOCK_MODE=1

# Create JIRA ticket and session in one command
# Note: Even in mock mode, daf jira new creates a REAL JIRA ticket (not mocked)
# Using a fake parent ticket for this example
daf jira new story \
  --parent PROJ-99999 \
  --goal "Implement user authentication feature" \
  --json

# Extract the ticket key from the JSON output
# Example output: {"success": true, "data": {"issue_key": "PROJ-12345", ...}}
# Save the actual ticket key for use throughout this test
TICKET_KEY=$(daf jira new story --parent PROJ-99999 --goal "Implement user authentication feature" --json 2>&1 | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['issue_key'])")

echo "Created ticket: $TICKET_KEY"
```

**What Happens**:
1. A real JIRA ticket is created (e.g., PROJ-12345) even though mock mode is enabled
2. The ticket key is automatically extracted and saved in `$TICKET_KEY`
3. Session is created in `$DEVAIFLOW_HOME-dev-a/sessions/PROJ-12345/` (using actual ticket key)
4. You'll be prompted to select a working directory (choose your test repository)
5. Git branch is created (e.g., `aap-12345-implement-user-authentication-feature`)
6. Claude Code is launched (or simulated in mock mode)

**Simulated Work in Claude Code**:
Since we're testing the handoff mechanism (not actual Claude Code interaction), we'll simulate that Developer A made some progress:

```bash
# Simulate Developer A making changes
cd ~/development/workspace/devaiflow  # or your test repo
echo "# Authentication module" > auth.py
echo "def login(username, password):" >> auth.py
echo "    # TODO: implement" >> auth.py
echo "    pass" >> auth.py

# Add and commit changes
git add auth.py
git commit -m "WIP: Add authentication module skeleton"

# Add notes to the session
daf note "$TICKET_KEY" "Created auth.py with login function skeleton. Still need to implement password hashing and session management."
```

**Expected Output**:
```
✓ Note added to 'aap-12345-add-authentication' (PROJ-12345) (#1)
```

### Step 3: Developer A Exports Session

```bash
# Still as Developer A
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a"
export DAF_MOCK_MODE=1

# Complete session and export (using the ticket key variable)
daf complete "$TICKET_KEY" --attach-to-jira
```

**Interactive Prompts (if auto-commit prompts not configured)**:
```
Commit all changes before completing? [y/n]: y
Create PR/MR? [y/n]: n  # Skip PR for this test
Add session summary to JIRA ticket? [y/n]: y
```

**Expected Output** (example with PROJ-12345):
```
✓ Committed changes: WIP: Session work for PROJ-12345
✓ Exported session to: /tmp/PROJ-12345-session-export.tar.gz
✓ Session marked as complete
✓ Added summary to JIRA ticket
```

**Verify Export File** (replace PROJ-12345 with your actual ticket key):
```bash
ls -lh /tmp/${TICKET_KEY}-session-export.tar.gz
tar -tzf /tmp/${TICKET_KEY}-session-export.tar.gz | head -20
```

**Expected Contents**:
```
export-metadata.json
sessions.json
sessions/PROJ-12345/metadata.json
sessions/PROJ-12345/notes.md
conversations/
conversations/<project-hash>/<session-uuid>.jsonl
logs/
```

### Step 4: Initialize Developer B's Environment

Now switch to Developer B's environment:

```bash
# Set up Developer B's environment
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
export DAF_MOCK_MODE=1

# Initialize configuration (if first time)
daf init

# Configure required settings (same project settings)
daf config set-project PROJ
daf config set-workstream Platform
daf config set-workspace ~/development/workspace  # Same workspace for this test

# Verify configuration
daf config show
```

**Expected Output**:
```
✓ Initialized configuration at: $DEVAIFLOW_HOME-dev-b/config.json
Project: PROJ
Workstream: Platform
Workspace: /Users/yourname/development/workspace
```

**Important**: Developer B should have **no sessions** yet:

```bash
daf list
```

**Expected Output**:
```
No sessions found
```

### Step 5: Developer B Imports Session

```bash
# Still as Developer B (DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b")
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
export DAF_MOCK_MODE=1

# You need to know the ticket key from Developer A
# If you don't have it in a variable, replace PROJ-12345 with the actual ticket key
# For this example, let's say Developer A shared it was PROJ-12345
TICKET_KEY="PROJ-12345"  # Replace with actual ticket key from Developer A

# Import the session export
daf import /tmp/${TICKET_KEY}-session-export.tar.gz
```

**Expected Output** (example with PROJ-12345):
```
✓ Imported session: PROJ-12345
✓ Restored 1 session
✓ Restored conversation history
✓ Restored session notes
✓ Restored diagnostic logs
```

**Note**: If the repository doesn't exist in Developer B's workspace, you'll see a warning message (PROJ-60693):

```
⚠  Missing repositories detected

The following repositories are referenced by imported sessions but not found in your workspace:

  Repository: devaiflow
  Expected path: /Users/devb/development/workspace/devaiflow
  Session: PROJ-12345 (aap-12345-implement-user-authentication-feature)

  Please clone this repository before opening the session:

    Option 1 - Clone to workspace (recommended):
      cd /Users/devb/development/workspace
      git clone https://github.com/org/repo.git devaiflow

    Option 2 - Use existing clone elsewhere:
      When you run 'daf open PROJ-12345', you'll be prompted to select the directory

  → Tip: Ask your teammate for the git remote URL and preferred branch

You can still work with imported sessions, but you'll need to clone the repositories before opening them.
```

This is a non-blocking warning - the import succeeds, but you're informed about repositories that need to be cloned. If the repository already exists in the expected location, no warning is shown.

**Verify Import**:
```bash
# List sessions
daf list

# View session details
daf info "$TICKET_KEY"
```

**Expected Output** (example with PROJ-12345):
```
Active Sessions:
  PROJ-12345: Implement user authentication feature
    Status: completed
    Branch: aap-12345-implement-user-authentication-feature
    Last active: 2025-12-13 10:30:00
    Messages: 5
```

### Step 6: Developer B Opens and Continues Session

```bash
# Still as Developer B
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
export DAF_MOCK_MODE=1

# Open the imported session
daf open "$TICKET_KEY"
```

**Expected Behavior**:
1. Session is reopened (status changes from "completed" to "active")
2. Git branch is checked out (already exists from Developer A's work)
3. Claude Code launches with **full conversation history** from Developer A
4. Session notes from Developer A are available

**Verify Session Notes Preserved**:
```bash
daf notes "$TICKET_KEY"
```

**Expected Output** (example with PROJ-12345):
```
# Session Notes: aap-12345-add-authentication
*JIRA:* PROJ-12345

## <timestamp> - Session #1
- Created auth.py with login function skeleton. Still need to implement password hashing and session management.
```

### Step 7: Developer B Continues Work

Simulate Developer B making additional progress:

```bash
# Make more changes
cd ~/development/workspace/devaiflow
echo "from hashlib import sha256" >> auth.py
echo "" >> auth.py
echo "def hash_password(password):" >> auth.py
echo "    return sha256(password.encode()).hexdigest()" >> auth.py

# Commit changes
git add auth.py
git commit -m "Add password hashing function"

# Add notes
daf note "$TICKET_KEY" "Implemented password hashing using SHA-256"
```

**Expected Output** (example with PROJ-12345):
```
✓ Added note to session PROJ-12345
```

### Step 8: Verify Complete Workflow

Now verify that the handoff was successful:

**Check Conversation History**:
```bash
# As Developer B
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
export DAF_MOCK_MODE=1

daf info "$TICKET_KEY"
```

**Expected Output** (example with PROJ-12345):
```
Session: PROJ-12345
Goal: PROJ-12345: Implement user authentication feature
Status: active
Branch: aap-12345-implement-user-authentication-feature
Claude Session ID: <uuid>
Messages: 5  # Original messages from Developer A
Created: 2025-12-13 10:15:00
Last Active: 2025-12-13 10:45:00  # Updated when Developer B opened
```

**Check Git History** (replace branch name with your actual branch):
```bash
cd ~/development/workspace/devaiflow
# Get the branch name from session info, or use the pattern
git log --oneline aap-12345-implement-user-authentication-feature
```

**Expected Output**:
```
abcd123 Add password hashing function
efgh456 WIP: Add authentication module skeleton
```

**Check Combined Notes**:
```bash
daf notes "$TICKET_KEY"
```

**Expected Output** (example with PROJ-12345):
```
# Session Notes: aap-12345-add-authentication
*JIRA:* PROJ-12345

## <timestamp> - Session #1
- Created auth.py with login function skeleton. Still need to implement password hashing and session management.

## <timestamp> - Session #1
- Implemented password hashing using SHA-256
```

## Verification Checklist

Use this checklist to confirm the collaboration workflow succeeded:

- [ ] **Export Created**: Developer A successfully exported session to `.tar.gz` file
- [ ] **Import Succeeded**: Developer B imported without errors
- [ ] **Session Visible**: `daf list` shows the JIRA ticket (e.g., PROJ-12345) in Developer B's environment
- [ ] **Conversation History**: Session includes original Claude conversation from Developer A
- [ ] **Git Branch**: Branch exists and contains Developer A's commits
- [ ] **Session Notes**: Notes from Developer A are visible to Developer B
- [ ] **Metadata Preserved**: Session metadata (goal, JIRA key, timestamps) intact
- [ ] **Continuation Works**: Developer B can open session and continue work
- [ ] **Time Tracking**: Time tracking switches to Developer B's username
- [ ] **Isolation**: Developer A's and B's environments remain separate (different `DEVAIFLOW_HOME`)
- [ ] **Diagnostic Logs**: Diagnostic logs included in export/import for debugging

**Important Notes**:
- Even in mock mode, `daf jira new` creates a **real JIRA ticket**. The ticket key will be a real PROJ-XXXXX number.
- Make sure to use the actual ticket key returned from the `daf jira new` command throughout the test.
- The fake parent ticket PROJ-99999 is used for demonstration purposes only.
- You can clean up test data using the cleanup commands in the "Cleanup: Restarting from Scratch" section.

## Troubleshooting

### Export File Not Found

**Problem**: `daf complete --attach-to-jira` doesn't create export file

**Solution**:
```bash
# Export manually (use the actual ticket key from $TICKET_KEY)
daf export "$TICKET_KEY" -o /tmp/session-export.tar.gz
```

### Import Shows "No sessions found"

**Problem**: Import completes but `daf list` shows nothing

**Solution**: Check that you're using the correct `DEVAIFLOW_HOME`:
```bash
echo $DEVAIFLOW_HOME  # Should be $DEVAIFLOW_HOME-dev-b
ls -la $DEVAIFLOW_HOME/sessions/  # Should show the ticket directory
```

### Git Branch Conflicts

**Problem**: Developer B's git branch conflicts with Developer A's work

**Solution**: This shouldn't happen in mock mode since both developers share the same git repository. If it does:
```bash
# Sync branch from Developer A's commits
cd ~/development/workspace/devaiflow
git fetch origin
git checkout <branch-name>  # Use the actual branch name
git pull origin <branch-name>
```

### Conversation History Missing

**Problem**: Claude Code doesn't show previous conversation when Developer B opens session

**Solution**:
1. Verify export includes conversation:
   ```bash
   tar -tzf /tmp/<ticket-key>-session-export.tar.gz | grep conversations
   ```
2. Check session info shows Claude Session ID:
   ```bash
   daf info <ticket-key>
   ```

### Real JIRA Ticket Created

**Problem**: I don't want to create real JIRA tickets during testing

**Solution**: Unfortunately, `daf jira new` is not currently mocked and will create real JIRA tickets even with `DAF_MOCK_MODE=1`. If you want to avoid creating real tickets:
- Use `daf new` instead to create a session without a JIRA ticket
- Or, clean up the created test tickets after the scenario test is complete

### Missing Repository Warning After Import

**Problem**: After importing, I see a warning that the repository is missing

**Solution**: This is expected behavior when importing sessions to a machine where the repository isn't cloned yet (PROJ-60693). You have two options:

1. **Clone the repository** (recommended):
   ```bash
   cd ~/development/workspace  # Your workspace
   git clone <remote-url> <repo-name>
   ```

2. **Use existing clone elsewhere**: When you run `daf open <ticket-key>`, you'll be prompted to select the directory where you already have the repository cloned.

The warning message includes the git remote URL (if it was captured during export) and provides clone instructions. This is a non-blocking warning - import succeeds, and you can clone the repository whenever you're ready to work on the session.

## Advanced Testing Scenarios

### Testing Multi-Conversation Sessions

Test sessions with multiple conversations across different repositories:

1. Developer A creates session with conversations in multiple repos
2. Export includes all conversations
3. Developer B imports and can see all conversations
4. Each conversation's working directory is preserved

### Testing with Real Git Remotes

Test with actual git push/pull (not mock mode):

1. Use a real git repository with remote
2. Developer A pushes branch before export
3. Developer B fetches branch after import
4. Verify branch synchronization works

### Testing Portable Paths

Test session export between machines with different workspace structures:

1. Developer A: `~/projects/workspace/`
2. Developer B: `~/dev/work/workspace/`
3. Both configure workspace with `daf config set-workspace`
4. Export/import uses relative paths to reconstruct full paths

---

# Section B: Testing WITHOUT Mock Mode

This section describes testing **without** `DAF_MOCK_MODE` - using real Claude Code and real JIRA integration.

## Overview (No-Mock Testing)

The collaboration workflow can also be tested **WITHOUT** `DAF_MOCK_MODE`, which enables:
- ✅ **Real Claude Code Integration**: Claude Code actually launches and creates conversation files
- ✅ **Real JIRA Integration**: JIRA tickets are created and accessed via API
- ✅ **Real Conversation Export/Import**: Full conversation history is preserved and restored

This is useful for validating the complete end-to-end workflow with actual Claude Code sessions.

### What's Different Without Mock Mode

| Aspect | With Mock Mode | Without Mock Mode |
|--------|---------------|-------------------|
| Claude Code Launch | ❌ Skipped | ✅ Launches (if display available) |
| JIRA Tickets | ✅ Real tickets created | ✅ Real tickets created |
| Conversation Files | ❌ Not created | ✅ Created in `~/.claude/projects/` |
| Git Operations | ✅ Works | ✅ Works |
| Session Export/Import | ✅ Works | ✅ Works (includes conversations) |

**Important**: Even in mock mode, `daf jira new` creates REAL JIRA tickets. The mock mode only affects Claude Code launching behavior.

### Prerequisites for No-Mock Testing

1. **JIRA API Access**: Set `JIRA_API_TOKEN` and `JIRA_AUTH_TYPE` environment variables
2. **Display Environment** (optional): For Claude Code to launch, you need a graphical display
   - On macOS/Linux desktops: Works normally
   - On headless servers/CI: Claude Code won't launch (expected)
3. **Same as Mock Mode**: Same `DEVAIFLOW_HOME` isolation approach works

### Quick Start: Manual Testing Without Mock Mode

The simplest way to test without mock mode is to follow the manual steps below. This gives you full control and lets you see the real Claude Code behavior.

**Prerequisites**:
```bash
# Ensure DAF_MOCK_MODE is NOT set
unset DAF_MOCK_MODE

# Ensure JIRA credentials are set
export JIRA_API_TOKEN="your-token-here"
export JIRA_AUTH_TYPE="Bearer"
```

# Create a dummy repo in your own github

### Step-by-Step Manual Testing

Follow these steps to test the collaboration workflow without mock mode:

#### Developer A: Create and Work on Session

```bash
# 1. Set up Developer A's environment
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a"
# DO NOT set DAF_MOCK_MODE

# 2. Initialize configuration
daf init
daf config set-project PROJ
daf config set-workstream Platform
daf config set-workspace ~/development/workspace

# 3. Create JIRA ticket and session
daf jira new story \
  --parent PROJ-59038 \
  --goal "Test ticket which just ask to add a file named test-<timestamp> in the root directory of the project"
# This will:
# - Create a REAL JIRA ticket (e.g., PROJ-12345)
# - Create a session
# - Launch Claude Code (work on your task)

# Exit the claude session and complete the task

# 4. When ready to hand off, sync and export
# Set points, sprint and assign to you the ticket. 
daf sync PROJ-12345  # Sync conversation back to session
daf open PROJ-12345 # Start the implementation
daf export PROJ-12345 # accept the default value for the output
```

**What Developer A does in Claude Code**:
- Make code changes
- Add commits
- Add session notes via `daf note PROJ-12345 "Your notes here"`
- Exit Claude Code when done

#### Developer B: Import and Continue

```bash
# 1. Set up Developer B's environment (different DEVAIFLOW_HOME)
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
# DO NOT set DAF_MOCK_MODE

# 2. Initialize configuration
daf init
daf config set-project PROJ
daf config set-workstream Platform
daf config set-workspace ~/development/workspace  # Can be same or different

# 3. Import the session from Developer A
daf import /tmp/PROJ-12345-session-export.tar.gz

# 4. Open and continue working
daf open PROJ-12345
# This will:
# - Launch Claude Code with FULL conversation history from Developer A
# - Let you continue where Developer A left off
# - Track your time separately

# 5. When done, complete the session
daf complete PROJ-12345
```

**What Developer B sees**:
- ✅ Complete conversation history from Developer A
- ✅ All git commits from Developer A
- ✅ All session notes from Developer A
- ✅ Same JIRA ticket and context
- ✅ Can continue work seamlessly

### Claude Code Conversation File Sharing

**Important Understanding**: When testing on a single laptop, both Developer A and B share the same `~/.claude/projects/` directory (Claude Code's own storage). This is **acceptable** for testing because:

1. **Session UUIDs are unique**: Each Claude Code conversation has a unique UUID
2. **No conflicts occur**: Different sessions have different UUIDs, so files don't overwrite
3. **Export/import works correctly**: The workflow handles conversation files properly

**In production** (different laptops):
- Developer A exports session → conversation files packaged in `.tar.gz`
- Developer B imports session → conversation files extracted to their `~/.claude/projects/`
- Both developers have separate `~/.claude/projects/` directories naturally

### Workspace Considerations for No-Mock Testing

You have two options for repository setup:

**Option 1: Shared Repository with Different Branches** (Simpler)
```bash
# Both developers use the same repo
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a"
daf config set-workspace ~/development/workspace

export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
daf config set-workspace ~/development/workspace

# Each developer works on their own branch (created automatically by daf)
# No conflicts because branches are different
```

**Option 2: Separate Repository Clones** (More realistic)
```bash
# Developer A
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a"
daf config set-workspace ~/dev-a/projects

# Developer B
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
daf config set-workspace ~/dev-b/projects

# Clone the same repo in both locations
# Simulates two developers on different machines
```

The automated test (`test_collaboration_workflow_no_mock.sh`) uses a temporary repository in `/tmp` that both developers share.

### Cleanup After No-Mock Testing

**Temporary Files**: Automatically cleaned up by test script

**JIRA Tickets**: Must be manually cleaned up
```bash
# Option 1: Close the ticket
daf jira update PROJ-XXXXX --status 'Closed'

# Option 2: Delete in JIRA web interface
# Visit: https://jira.example.com/browse/PROJ-XXXXX
```

**Git Branches**: Clean up test branches if needed
```bash
cd ~/development/workspace/your-repo
git branch | grep -E 'aap-[0-9]+-test' | xargs -r git branch -D
```

**Claude Code Conversations**: Optional cleanup
```bash
# Remove test conversation files from ~/.claude/projects/
# (Only if you want to clean up after testing)
```

### Troubleshooting No-Mock Testing

#### Claude Code Doesn't Launch

**Expected Behavior**: In CI or headless environments, Claude Code won't launch. This is normal!

**Solution**: The test will still validate session export/import, git operations, and JIRA integration. Conversation files won't be created, but that's expected without a display.

#### "JIRA_API_TOKEN not set" Error

**Problem**: Missing JIRA credentials

**Solution**:
```bash
export JIRA_API_TOKEN="your-personal-access-token"
export JIRA_AUTH_TYPE="Bearer"
```

#### DAF_MOCK_MODE is Set

**Problem**: Test detects `DAF_MOCK_MODE` environment variable

**Solution**:
```bash
unset DAF_MOCK_MODE
./test_collaboration_workflow_no_mock.sh
```

#### Multiple Conversation Files in ~/.claude/projects/

**Problem**: Concerned about file pollution from testing

**This is normal**: Each test creates new conversation files with unique UUIDs. They won't conflict with your actual work sessions. You can safely delete test conversation files after testing if desired.

### Verification Checklist

After completing the manual test, verify these aspects worked correctly:

- [ ] **JIRA ticket created**: Real ticket exists in JIRA
- [ ] **Session created**: Developer A has session in their DEVAIFLOW_HOME
- [ ] **Claude Code launched**: Developer A worked in real Claude Code session
- [ ] **Git commits**: Changes were committed to git branch
- [ ] **Session notes**: Notes were added and visible
- [ ] **Export succeeded**: .tar.gz file created with session data
- [ ] **Import succeeded**: Developer B imported without errors
- [ ] **Conversation preserved**: Developer B sees Developer A's conversation history in Claude Code
- [ ] **Notes preserved**: Developer B can see Developer A's session notes
- [ ] **Git branch exists**: Developer B has access to git branch with commits
- [ ] **Completion works**: Developer B can complete the session
- [ ] **JIRA updated**: Session completion updates JIRA ticket

---

# Related Documentation

- **Session Export/Import**: See `docs/07-commands.md` (daf export/import commands)
- **Team Collaboration Demo**: See `DEMO_SCENARIOS.md` (Section 3: Team Collaboration)
- **Mock Services**: See `README.md` (Mock Services for Testing)
- **Configuration**: See `docs/06-configuration.md` (DEVAIFLOW_HOME and workspace settings)

## Implementation References

- **Export Manager**: `devflow/export/manager.py` - Session export/import logic
- **Portable Paths**: PROJ-60537 - Relative path support
- **Git Synchronization**: PROJ-59820, PROJ-59821 - Branch sync features
- **Multi-Conversation**: Architecture supports multiple repos per session
- **Diagnostic Logs**: PROJ-60657 - Logs included in export/import
- **No-Mock Testing**: PROJ-60694 - Testing collaboration without mock mode

---

# Summary

This scenario guide demonstrates two ways to test the collaboration workflow:

### With Mock Mode (Automated)
- ✅ Run `test_collaboration_workflow.sh` for automated testing
- ✅ Fast, isolated, no real JIRA tickets
- ✅ Perfect for CI/CD and development

### Without Mock Mode (Manual)
- ✅ Follow the step-by-step manual guide above
- ✅ Tests real Claude Code integration
- ✅ Full conversation export/import validation
- ✅ Real JIRA integration (requires cleanup)

**Both approaches validate**:
1. Developer A: Creates session → Works on feature → Exports session
2. Developer B: Imports session → Opens session → Continues work seamlessly
3. All context preserved: conversation, git, notes, metadata, logs

By following this guide, you can confidently test the team handoff workflow on your own laptop using `DEVAIFLOW_HOME` to simulate multiple developers.
