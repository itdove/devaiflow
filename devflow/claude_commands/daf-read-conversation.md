---
description: Read the conversation history from another repository in this multi-project session
---

Read the conversation history from another repository in this multi-project session to understand work done in related codebases.

USAGE:
1. First, run `/daf list-conversations` to see all available conversations
2. Then use this command to read a specific conversation's history

IMPORTANT: You can only read conversations from OTHER repositories, NOT the current one. Reading the current conversation would duplicate the context you already have.

To read a conversation:

```bash
# Get session info to find conversation details
daf info

# The output shows all conversations with their:
# - Working directory name (e.g., "backend-api", "frontend-ui")
# - Repository name
# - Claude Code session UUID
# - Git branch

# Read the conversation file directly using the Claude Code session UUID:
# Conversation files are stored at: ~/.claude/projects/<encoded-path>/<uuid>.jsonl

# Example workflow:
# 1. Get the session UUID for the conversation you want to read
# 2. Find the encoded path for that repository
# 3. Read the .jsonl file

# Note: The .jsonl file contains the full conversation history in JSON Lines format
# Each line is a JSON object representing one message in the conversation
```

MULTI-CHOICE SELECTION:
If there are multiple conversations in this session, you can provide a multi-choice interface:

1. List all conversations EXCEPT the current one
2. User selects which conversation to read
3. You read that conversation's .jsonl file

WHAT TO LOOK FOR:
When reading another conversation, focus on:
- What features were implemented
- API contracts or interfaces defined
- Data models or schemas created
- Configuration changes made
- Dependencies or integration points
- Decisions about implementation approach

This helps maintain consistency across the multi-repository feature implementation.
