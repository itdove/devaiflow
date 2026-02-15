---
name: daf-info
description: Show detailed information about the current session
---

Display detailed session information including all conversations, branches, and Claude Code session UUIDs.

```bash
daf info
```

**Auto-detects current session:**
The command will automatically detect the current Claude Code session and display comprehensive details.

**Explicit session lookup:**
```bash
daf info PROJ-12345
daf info my-session
```

**What it shows:**

**Session Overview:**
- Session name and JIRA key
- Session status and goal
- Creation date and last active time
- Total time tracked

**All Conversations:**
For each conversation in the session:
- Working directory (repository name)
- Project path
- Git branch
- Claude Code session UUID
- Conversation file location
- PR/MR links (if created)
- Message count
- Last active time

**Example output:**
```
Session Information

Name: implement-backup-feature
JIRA: PROJ-60039
Summary: Implement config patch system
Status: in_progress
Goal: PROJ-60039: Implement config patch system

Conversations: 2

#1 (active)
  Working Directory: backend-api
  Project Path: /path/to/backend-api
  Branch: feature-backup
  Claude Session UUID: f545206f-480f-4c2d-8823-c6643f0e693d
  Conversation File: ~/.claude/projects/.../f545206f-...jsonl
  Created: 2025-12-05 13:07:00
  Last Active: 2025-12-05 18:30:15
  Messages: 45
  PRs: https://github.com/org/repo/pull/123

#2
  Working Directory: frontend-app
  Project Path: /path/to/frontend-app
  Branch: feature-backup
  Claude Session UUID: be07636e-44c3-41fb-a3b6-dc9c0a530806
  ...

Time Tracked: 5h 45m
Notes: 12 entries
```

**Use this to:**
- See all conversations in current session
- Find Claude session UUIDs for debugging
- Check which branch each conversation uses
- Verify conversation file locations
- See PR/MR links associated with session
- Understand multi-repository structure

**Related commands:**
```bash
/daf list-conversations    # Simpler list of conversations
/daf active                # Show only active conversation
```
