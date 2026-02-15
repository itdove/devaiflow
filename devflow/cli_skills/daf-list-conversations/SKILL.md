---
name: daf-list-conversations
description: List all conversations in the current multi-project session
---

List all conversations in the current multi-project session.

This session is working across multiple repositories as part of a single feature or epic. Each repository has its own conversation with separate git branch and Claude Code session.

To view available conversations, run:

```bash
daf info
```

Look for the "Conversations" section in the output. Each conversation has:
- Repository name (e.g., "backend-api")
- Working directory name (e.g., "backend-api")
- Git branch name
- Claude Code session UUID
- PR/MR links (if created)

To switch to a different conversation:
1. Exit this Claude Code session
2. Run: `daf open <session-name>`
3. Select the conversation/repository when prompted

IMPORTANT: You are currently working in ONE repository. Do NOT attempt to modify files in other repositories - each has its own branch and conversation context.
