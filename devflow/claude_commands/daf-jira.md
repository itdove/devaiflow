---
description: View JIRA ticket details for current session
---

View the JIRA ticket associated with the current session in Claude-friendly format.

```bash
daf jira view
```

**Auto-detects current session:**
The command will automatically detect the current Claude Code session and display the associated JIRA ticket details.

**Explicit ticket lookup:**
```bash
daf jira view PROJ-12345
daf jira view PROJ-12345 --history    # Include changelog
```

**What it shows:**
- Ticket key and summary
- Current status and priority
- Assignee and reporter
- Epic and sprint information
- Story points (if set)
- Full description
- Acceptance criteria
- Pull request links
- Changelog/history (with `--history` flag)

**Example output:**
```
Key: PROJ-12345
Summary: Implement customer backup and restore
Status: In Progress
Type: Story
Priority: Major
Assignee: John Doe
Epic: PROJ-59038
Sprint: Sprint 42
Story Points: 5

Description:
As a user, I want to backup my data so that I can restore it later.

Acceptance Criteria:
- Backup functionality implemented
- Restore functionality implemented
- Tests added
```

**Why use this:**
- More reliable than curl commands (automatic auth)
- Better formatted for Claude to read
- Shows all relevant ticket context
- Consistent with daf tool ecosystem
- Helps understand requirements before coding

**Related commands:**
```bash
daf jira create bug --summary "..."    # Create new JIRA bug
daf jira create story --summary "..."  # Create new JIRA story
daf jira update PROJ-12345 --priority Major  # Update ticket fields
```
