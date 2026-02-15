---
name: daf-active
description: Show information about the currently active conversation
---

Display details about the currently active Claude Code conversation, including session info, branch, and other conversations in the session.

```bash
daf active
```

**What it shows:**

**When a conversation is active:**
- Current DAF session name and JIRA key
- Current conversation (working directory)
- Project path
- Git branch
- Goal
- Session status
- Time tracked for this session
- Other conversations in the session

**Example output:**
```
┌─ ▶ Currently Active ───────────────────────────────┐
│ DAF Session: PROJ-12345 (#1)                        │
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

To pause: Exit Claude Code
To switch: daf open PROJ-12345 (and select different conversation)
```

**When no active conversation:**
```
No active conversation

Recent conversations:
  PROJ-12345#1 (backend) - paused 15m ago
  PROJ-12346#1 (frontend) - paused 2h ago

To resume: daf open <name>
```

**Use this to:**
- Verify which conversation is currently active
- See which git branch you're working on
- Check which project you're in
- View other conversations in the session
- Find recently paused conversations

**Why this matters for multi-conversation sessions:**
- Each conversation has its own git repository and branch
- Making changes in the wrong conversation can cause lost work
- Use `daf active` to confirm you're in the right project before coding

**Related commands:**
```bash
/daf list-conversations    # See all conversations in session
/daf info                  # Detailed session information
daf list --active          # List all active sessions
```
