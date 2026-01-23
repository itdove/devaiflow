# Session Management

Complete guide to managing sessions and conversations.

## Understanding Sessions and Conversations

### Session (DAF Session)

A **session** represents one focused piece of work (typically one JIRA ticket) with:
- Session name and ID
- Goal/description
- JIRA ticket link (optional)
- Time tracking data (shared across all conversations)
- Progress notes
- Status (created, in_progress, paused, complete)
- **One or more conversations** (one per project directory)

### Conversation (Claude Code Conversation)

A **conversation** represents work in a specific project directory with:
- **Active conversation** - Your current Claude Code conversation
  - Claude Code conversation history
  - Project path (repository directory)
  - Git branch
  - Claude session ID (UUID)
  - Last active timestamp
- **Archived conversations** - Previous Claude Code conversations in the same repository
  - Full conversation history preserved
  - Summary of what was accomplished
  - Can be viewed with `daf sessions list`

**Key Points:**
- One session can have multiple conversations - one for each project/repository you work in for that ticket
- Each conversation can have multiple Claude Code sessions (active + archived) for starting fresh while preserving history

### Session States

Sessions progress through these states:

```
created → in_progress → complete
```

Status values (as displayed in `daf list` and other commands):
- **created** - Session exists but hasn't been opened yet
- **in_progress** - Currently working on (or worked on recently)
- **paused** - Session paused (time tracking stopped)
- **complete** - Work finished, session archived

**Note:** Status values are shown as-is in all outputs and match the filter values used with `--status` flag.

## Working Across Multiple Repositories

**Recommended: Use Multi-Conversation Sessions (New!)**

The modern approach is to create one session with multiple conversations - one per repository. This keeps all related work under a single session with unified time tracking.

### Example: Multi-Repository Work (Recommended)

```bash
# Create session - you'll be prompted to select a repository
daf new --name "user-profile" --jira PROJ-12345 --goal "Add user profile feature"

# You'll see:
Available repositories (8):
  1. backend-api
  2. frontend-app
  3. mobile-app
  ...

Which project? [1-8]: 1

# Work in backend, then exit Claude Code...

# Continue same session in different repository
daf open PROJ-12345

# You'll see:
Found 1 conversation(s) for PROJ-12345:

  1. backend-api
     Path: /Users/you/workspace/backend-api
     Branch: feature/PROJ-12345
     Last active: 15m ago

  2. → Create new conversation (in a different project)

Which conversation? [1-2]: 2

# Select frontend repository
Available projects:
  1. backend-api (already has conversation)
  2. frontend-app
  3. mobile-app
  ...

Which project? [1-3]: 2

# Now working in frontend with separate conversation...
```

**Result:** One session (PROJ-12345) with multiple conversations:
```
PROJ-12345 (session)
  ├─ Conversation: backend-api
  │  └─ Claude Code history, branch: feature/PROJ-12345
  └─ Conversation: frontend-app
     └─ Claude Code history, branch: feature/PROJ-12345-ui
```

**Benefits:**
- Unified time tracking across all repositories
- Single JIRA ticket link
- Easier to manage with `daf active`, `daf list`, `daf status`
- All conversations share the same goal and context


### Understanding the Relationship

```
JIRA Ticket: PROJ-12345
       ↓
Session: PROJ-12345 (one session per ticket)
       ├─ Conversation: backend-api
       │  ├─ Repository: /workspace/backend-api
       │  ├─ Branch: feature/PROJ-12345
       │  ├─ Active Claude session (current work)
       │  └─ Archived Claude sessions (history)
       │
       └─ Conversation: frontend-app
          ├─ Repository: /workspace/frontend-app
          ├─ Branch: feature/PROJ-12345-ui
          ├─ Active Claude session (current work)
          └─ Archived Claude sessions (history)
```

**Important:**
- **1 JIRA ticket** = **1 Session**
- **1 Project directory** = **1 Conversation** (with active + archived Claude sessions)
- Each conversation has its **own git branch** and **own Claude Code history**
- Time tracking is **shared** across all conversations in the session

## Starting Fresh: Archiving Conversations

Sometimes you need to start a fresh Claude Code conversation while preserving your previous work. This is useful when:
- The conversation history gets too long (causing 413 errors)
- You want to take a different approach but keep the old one for reference
- You've completed one part and want a clean slate for the next

### Archive and Start Fresh

```bash
# Open session and archive current conversation
daf open PROJ-12345 --new-conversation

# This will:
# 1. Archive your current Claude Code conversation
# 2. Create a new Claude Code session with fresh history
# 3. Preserve all your previous conversation history
```

**What gets preserved:**
- All previous conversation history (.jsonl files)
- Git branch and commits
- Summary of what was accomplished

**What's new:**
- Fresh Claude Code conversation (new UUID)
- Empty conversation history (clean start)
- Same project, same branch

### View Conversation History

See all conversations (active + archived) for a session:

```bash
daf sessions list PROJ-12345
```

**Example output:**
```
Session: PROJ-12345
Conversations (2 repositories):

#1 backend-api (active)
  Claude Session: a7b3c4d5-1234-...
  Branch: feature/PROJ-12345
  Messages: 45
  Created: 2026-01-15 09:30
  Last Active: 2026-01-21 14:30

  Archived (1):
    UUID: f8e9d0a1-5678-...
    Summary: Initial implementation of user auth
    Messages: 123
    Created: 2026-01-10 10:00
    Archived: 2026-01-15 09:30

#2 frontend-app (active)
  Claude Session: b8c4d5e6-2345-...
  Branch: feature/PROJ-12345-ui
  Messages: 28
  Created: 2026-01-18 11:00
  Last Active: 2026-01-20 16:45
```

**Use Cases:**
- Review what was tried before
- Reference previous approaches
- Understand conversation progression
- Verify nothing was lost

### Checking Active Conversation

Use `daf active` to see which conversation is currently active:

```bash
daf active

# Output when working in backend-api:
┌─ ▶ Currently Active ───────────────────────────────┐
│ DAF Session: PROJ-12345 (#1)                         │
│ JIRA: PROJ-12345                                    │
│ Conversation: backend-api                          │
│ Project: /workspace/backend-api                    │
│ Goal: Add user profile API and UI                 │
│ Branch: feature/PROJ-12345                          │
│ Time (this session): 1h 23m                        │
│ Status: in_progress                                │
│                                                     │
│ Other conversations in this session:               │
│   • frontend-app (branch: feature/PROJ-12345-ui)    │
└────────────────────────────────────────────────────┘
```

**Key features:**
- Shows current conversation's project and branch
- Lists other conversations with their branches
- Displays session-level time tracking
- Helps prevent working in wrong project

### Visual Indicators in `daf list`

Active conversations are marked with ▶ symbol:

```
Status      Name              JIRA       Summary              Working Dir    Time
▶ 🚧        PROJ-12345 (#1)   PROJ-12345  User profile work    backend-api    3h 45m
  🆕        PROJ-12346 (#1)   PROJ-12346  Fix login bug        frontend       0h 0m
```

The ▶ indicator shows which conversation is currently open in Claude Code.

## Creating Sessions

### Recommended: Sync from JIRA (JIRA Users)

The easiest way to create sessions is to sync from JIRA:

```bash
# Sync all assigned tickets in current sprint
daf sync --sprint current

# Or sync all assigned tickets
daf sync
```

This automatically creates sessions for all your JIRA tickets. No need to manually create sessions!

See the [JIRA Integration Guide](05-jira-integration.md) for complete sync documentation.

### Basic Session (No JIRA)

For personal experiments or work not tied to a ticket:

```bash
daf new --name "redis-test" --goal "Test Redis caching approach"
```

### Session with JIRA (Manual Creation)

If you need to manually create a JIRA-linked session (less common):

```bash
daf new --jira PROJ-12345 --goal "Implement backup feature"
```

You'll be prompted for the session name:
```
Session name [PROJ-12345]:
```

Press Enter to use the JIRA key, or type a custom name.

**Note:** For most workflows, use `daf sync` instead of manually creating sessions.

### Session with Specific Path

```bash
daf new --name "api-test" --goal "Test new endpoint" --path /Users/you/projects/backend
```

Override automatic repository detection.

### Session from Template

```bash
daf new --name "new-feature" --goal "Build API" --template my-backend-template
```

Reuse configuration from a saved template.

## Session Metadata

Each session stores:

### Core Metadata
- **name** - Session name (identifier)
- **session_id** - Unique numeric ID within the session
- **goal** - What you're trying to accomplish
- **status** - created, in_progress, or complete
- **working_directory** - Repository name (e.g., "backend-api")
- **project_path** - Full path to repository
- **branch** - Git branch name
- **ai_agent_session_id** - UUID for Claude Code conversation

### JIRA Metadata (Optional)
- **issue_key** - JIRA ticket key (e.g., "PROJ-12345")
- **jira_summary** - Ticket title/summary
- **jira_status** - Ticket status
- **jira_assignee** - Who it's assigned to
- **sprint** - Sprint name/ID

### Tracking Metadata
- **created_at** - When session was created
- **updated_at** - Last modified time
- **work_sessions** - List of start/stop times
- **total_time_seconds** - Total time spent
- **tags** - Custom tags for organization

### Stored Data
Each session has a directory at `~/.daf-sessions/sessions/{SESSION-NAME}/`:
- **metadata.json** - All metadata above
- **notes.md** - Progress notes
- **memory.md** - Context hints (optional)

## Opening Sessions

### Open by Name

```bash
daf open redis-test
```

### Open by JIRA Key

```bash
daf open PROJ-12345
```

### What Happens When Opening

1. **First Time (New Session)**:
   - Generates Claude session UUID
   - Creates git branch (if configured)
   - Sends initial prompt to Claude with goal
   - Starts time tracking
   - Sets status to `in_progress`

2. **Resuming Existing Session**:
   - Loads Claude conversation from UUID
   - Checks out git branch
   - Resumes time tracking
   - Updates `updated_at` timestamp

3. **Orphaned Session (UUID exists but file missing)**:
   - Detects missing conversation file
   - Generates new UUID
   - Treats as first-time launch
   - User sees explanation message

### Initial Prompt

When creating a session, Claude receives:
```
Work on: PROJ-12345: Implement backup feature

Please start by reading the following context files if they exist:
- AGENTS.md (agent-specific instructions)
- CLAUDE.md (project guidelines and standards)

Also read the JIRA ticket: jira issue view PROJ-12345
```

This ensures Claude has full context before starting work.

## Listing Sessions

### All Sessions

```bash
daf list
```

Output:
```
Sessions (5):

📋 backup (#1, #2)
   🎯 Implement backup feature
   🔗 PROJ-12345
   📁 backend-api, frontend-app
   📊 in_progress
   ⏱️  3h 45m

📋 redis-test (#1)
   🎯 Test Redis caching approach
   📁 experiments
   📊 complete
   ⏱️  1h 20m
```

### Active Sessions Only

```bash
daf list --active
```

Shows only sessions with status `in_progress`.

### Filter by Repository

```bash
daf list --working-directory backend-api
```

Shows only sessions in the specified repository.

### Filter by Sprint

```bash
daf list --sprint "2025-01"
```

Shows only sessions in the specified sprint.

### Filter by Status

```bash
daf list --status complete
```

Shows sessions with specific status. Valid values: `created`, `in_progress`, `paused`, `complete`.

You can filter by multiple statuses:
```bash
daf list --status in_progress,paused
```

## Progress Notes

> **Important:** `daf note` must be run **outside** Claude Code to prevent data conflicts. Exit Claude Code first before adding notes. Inside Claude Code, use `/daf-notes` to view notes (read-only).

### Add a Note (Local Only)

```bash
daf note backup "Implemented upload endpoint"
```

Saved to `~/.daf-sessions/sessions/backup/notes.md`:
```markdown
## 2025-11-20 14:30:00

Implemented upload endpoint
```

### Add Note and Sync to JIRA

```bash
daf note backup "Backend complete, ready for review" --jira
```

This:
1. Saves note locally (always happens)
2. Adds note as JIRA comment (if linked and JIRA CLI available)

If JIRA sync fails, note is still saved locally.

### Note on Most Recent Session

```bash
daf note "Quick update on current work"
```

Uses the most recently updated session.

### View Notes

Notes are stored in markdown format:

```bash
cat ~/.daf-sessions/sessions/backup/notes.md
```

## Session Summaries

### Quick Summary (Local Mode)

```bash
daf summary backup
```

Output:
```
Session: backup (#1)
Goal: Implement backup feature
JIRA: PROJ-12345 - "Customer backup and restore"
Status: in_progress
Time: 3h 45m (5 work sessions)

Files Created: 12
Files Modified: 8
Commands Run: 24
Notes: 6
```

Fast, offline, statistical summary.

### Detailed Summary

```bash
daf summary backup --detail
```

Shows full file lists and commands.

### AI-Powered Summary

```bash
daf summary backup --ai-summary
```

Uses Claude API to generate intelligent natural language summary:
```
Session: backup (#1)

Summary:
Implemented a comprehensive backup system for customer data. Created new
backup service with upload endpoint, S3 integration, and encryption. Added
validation for backup metadata and implemented retry logic for failed uploads.
Still need to add restore functionality and write tests.

Key Accomplishments:
- Backup upload API endpoint with authentication
- S3 bucket integration with encryption
- Metadata validation and storage
- Error handling and retry logic

Next Steps:
- Implement restore endpoint
- Add comprehensive test coverage
- Update documentation
```

## Completing Sessions

### Basic Completion

```bash
daf complete backup
```

Prompts:
1. Mark session as complete?
2. Generate AI summary? (if configured)
3. Add summary to JIRA? (if linked)
4. Transition JIRA ticket? (if configured)

### Complete with Status Transition

```bash
daf complete backup --status "Code Review"
```

Marks complete and transitions JIRA ticket to "Code Review" state.

### What Happens on Completion

1. **Status Update**: Session status → `complete`
2. **Time Tracking**: Stops active time tracking
3. **AI Summary** (optional): Generates summary of work done
4. **JIRA Comment** (optional): Adds summary to JIRA ticket
5. **JIRA Transition** (optional): Moves ticket to new status

## Deleting Sessions

### Delete Single Session

```bash
daf delete backup
```

Prompts for confirmation:
```
Delete session 'backup' (#1)?
This will remove all session data including notes and metadata.
Conversation history in Claude will NOT be deleted.

Continue? [y/N]:
```

### Delete Without Confirmation

```bash
daf delete backup --force
```

### Delete All Sessions

```bash
daf delete --all
```

Complete reset - deletes all sessions. Prompts for confirmation.

### Delete All Without Confirmation

```bash
daf delete --all --force
```

### What Gets Deleted

- Session metadata (`~/.daf-sessions/sessions/{NAME}/`)
- Progress notes
- Memory files
- Session entry in sessions.json

**What is NOT deleted**:
- Claude Code conversation files (`~/.claude/projects/...`)
- Git branches
- JIRA tickets

## Searching Sessions

### Search by Keyword

```bash
daf search "backup"
```

Searches in:
- Session names
- Goals
- JIRA summaries
- Progress notes

### Search with Filters

```bash
daf search "api" --working-directory backend-api
daf search "bug" --tag urgent
```

## Time Tracking

### View Time for Session

```bash
daf time backup
```

Output:
```
Time Tracking for: backup (#1)

Work Sessions:
  1. 2025-11-20 09:00:00 → 11:30:00  (2h 30m)
  2. 2025-11-20 14:00:00 → 15:15:00  (1h 15m)
  3. (active) 16:00:00 → now         (45m)

Total Time: 4h 30m
Status: in_progress
```

### Pause Time Tracking

```bash
daf pause backup
```

Stops the active work session without closing Claude Code.

### Resume Time Tracking

```bash
daf resume backup
```

Starts a new work session.

### How Time Tracking Works

- **Automatic Start**: When `daf open` launches Claude Code
- **Automatic Stop**: When Claude Code exits (captured via process monitoring)
- **Manual Control**: Use `daf pause` and `daf resume` for breaks

Time data stored in `work_sessions` array:
```json
{
  "work_sessions": [
    {
      "start": "2025-11-20T09:00:00",
      "end": "2025-11-20T11:30:00"
    }
  ]
}
```

## Linking JIRA Tickets

### Link JIRA to Existing Session

```bash
daf link backup --jira PROJ-12345
```

This:
1. Validates JIRA ticket exists
2. Fetches ticket metadata
3. Links ticket to session
4. Updates all conversations in the session

### Unlink JIRA

```bash
daf unlink backup
```

Removes JIRA association but keeps session data.

## Session Templates

### Save Session as Template

```bash
daf template save backup my-backend-template
```

Creates reusable template with:
- Working directory pattern
- Git branch pattern
- Tags
- JIRA key pattern (optional)

### List Templates

```bash
daf template list
```

### Use Template

```bash
daf new --name "new-api" --goal "Build endpoint" --template my-backend-template
```

Applies template configuration to new session.

### Delete Template

```bash
daf template delete my-backend-template
```

## Orphaned Sessions

### What Are Orphaned Sessions?

Sessions where:
- `ai_agent_session_id` is set
- But conversation file doesn't exist at `~/.claude/projects/.../`

This happens when:
- Session creation interrupted
- Claude Code crashed
- Conversation files manually deleted

### Detecting Orphaned Sessions

```bash
daf cleanup-sessions --dry-run
```

Output:
```
Found 2 orphaned session(s):

Session             Session ID  JIRA      Missing UUID      Status
backup (#1)         1           PROJ-12345 4ff5a139...       in_progress
test (#1)           1           -         8ab2c4e7...       created
```

### Cleaning Up Orphaned Sessions

```bash
daf cleanup-sessions
```

This:
1. Clears orphaned `ai_agent_session_id` from metadata
2. Next `daf open` will generate new UUID
3. No session data lost

### Automatic Fix on Open

When you run `daf open` on an orphaned session:
```
⚠ Conversation file not found for session 4ff5a139-113d-4e5a-abf1-92873fd96b7a
This can happen if the session was interrupted or Claude Code failed to start.

First-time launch for session: backup
Generated new session ID: 7c8d9e0f-1234-5678-9abc-def012345678
```

The orphan is automatically fixed.

## Best Practices

### 1. Use Descriptive Names

Good:
```bash
daf new --name "user-auth-api" --goal "Implement OAuth2"
```

Bad:
```bash
daf new --name "test123" --goal "stuff"
```

### 2. Add Notes Regularly

Document progress (exit Claude Code first):
```bash
daf note "Completed login endpoint"
daf note "Found bug in token refresh, fixing"
daf note "Ready for code review"
```

### 3. Complete Sessions When Done

Don't leave sessions in `in_progress` forever:
```bash
daf complete user-auth-api
```

### 4. Use Multi-Conversation Sessions for Multi-Repo Work

Keep related work organized:
```bash
# All conversations in one session for one JIRA ticket
daf new --name "backup" --jira PROJ-12345 --goal "Backend API"
daf new --name "backup" --jira PROJ-12345 --goal "Frontend UI"
daf new --name "backup" --jira PROJ-12345 --goal "Infrastructure"
```

### 5. Clean Up Old Sessions

Periodically review and delete completed work:
```bash
daf list --status complete
daf delete old-session-1
daf delete old-session-2
```

Or export them first:
```bash
daf export old-session-1 old-session-2 --output archive.tar.gz
daf delete old-session-1 old-session-2 --force
```

### 6. Use Templates for Consistency

Save successful session configs:
```bash
daf template save successful-project my-template
daf new --name "next-project" --goal "..." --template my-template
```

### 7. Leverage AI Summaries

Before completing, check progress:
```bash
daf summary backup --ai-summary
```

Use for completion:
```bash
daf complete backup  # Will offer AI summary
```

## Troubleshooting

### Session Won't Open

**Problem**: "No conversation found with session ID: ..."

**Solution**: Session is orphaned. Either:
```bash
# Automatic fix - just open it
daf open session-name

# Or manual cleanup
daf cleanup-sessions
daf open session-name
```

### Multiple Sessions When Opening

**Problem**: Prompted to select from multiple conversations

**Cause**: Session has multiple conversations (by design for multi-repo work)

**Solution**: Select the one you want to work on, or use specific conversation:
```bash
daf open session-name  # Interactive selection
```

### Can't Find Session

**Problem**: "Session 'name' not found"

**Solution**:
```bash
# List all sessions
daf list --all

# Search for it
daf search "keyword"

# Check by JIRA key
daf list | grep PROJ-12345
```

### Time Tracking Not Working

**Problem**: Time doesn't update

**Cause**: Process monitoring may have failed

**Solution**:
```bash
# Manual pause/resume
daf pause session-name
daf resume session-name
```

## Next Steps

- [JIRA Integration](05-jira-integration.md) - Learn JIRA workflows
- [Configuration Reference](06-configuration.md) - Configure session behavior
- [Commands Reference](07-commands.md) - All available commands
