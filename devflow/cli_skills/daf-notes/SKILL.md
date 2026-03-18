---
name: daf-notes
description: View all progress notes for the current session
user-invocable: true
argument-hint: "[SESSION-NAME|TICKET-ID]"
---

Display all notes for the current session in chronological order. This is a READ-ONLY view - it does not modify the session.

```bash
daf notes
```

**Auto-detects current session:**
The command will automatically detect the current Claude Code session and display all notes.

**Explicit session lookup:**
```bash
daf notes PROJ-12345
daf notes my-session
daf notes --latest        # Most recently active session
```

**What it shows:**
- All notes in chronological order (oldest to newest)
- Timestamp for each note
- JIRA key association (if present)
- Conversation context for multi-conversation sessions

**Example output:**
```
Notes for session: implement-backup-feature (PROJ-12345)

### 2025-12-18 10:30:00
Completed API endpoint implementation

### 2025-12-18 14:15:00
Added retry logic with exponential backoff

### 2025-12-18 16:45:00
All tests passing - ready for review

Total: 3 notes
```

**Use this to:**
- Review progress history
- Understand what work has been done
- Find specific milestones or decisions
- Prepare status updates
- Refresh context when resuming work

**Important notes:**
- This is a READ-ONLY command - safe to run inside Claude Code
- Notes are stored in $DEVAIFLOW_HOME/sessions/<name>/notes.md
- Notes persist across sessions and exports
- Included in session summaries
- To add notes, use `daf note` (works inside Claude sessions)

**Related commands:**
```bash
daf note "Add progress note"              # Add note to active session (auto-detects)
daf note PROJ-12345 "Add progress note"   # Add note to specific session
daf summary PROJ-12345                    # View session summary with notes
daf info PROJ-12345                       # View session details
```
