---
name: daf-help
description: Show available daf commands and quick reference
user-invocable: true
---

Display a quick reference of commonly used daf commands.

```bash
daf --help
```

**Core Session Commands:**

**During work:**
```bash
daf status                   # Check progress dashboard
daf active                   # Show currently active conversation
daf list                     # List all sessions
```

**JIRA Integration:**
```bash
daf jira view PROJ-12345 --comments   # View ticket details with comments
daf jira create bug --summary "..."   # Create new JIRA bug
daf jira create story --summary "..." # Create new JIRA story
daf jira update PROJ-12345 --priority Major  # Update ticket
```

**Multi-Conversation Sessions:**
```bash
/daf list-conversations      # List all conversations in session
/daf read-conversation       # Read work done in other repositories
```

**Configuration:**
```bash
daf config show              # View current configuration
daf skills                   # List all available skills
daf skills <skill-name>      # Inspect specific skill
```

**Getting Help:**
```bash
daf --help                   # Main help
daf <command> --help         # Command-specific help
daf jira create bug --help   # See available options
```

**Quick Reference:**
- Session = work on one JIRA ticket
- Conversation = work in one repository
- Multi-conversation = one session across multiple repos (default)
- Multi-session = separate approaches to same ticket (use `--new-session`)

**Common Workflows:**

**Multi-repo feature:**
```bash
# Work in current repository
/daf read-conversation      # Read work from other repositories in this session
# ... work in current repository with context from other repos ...
```

**Full documentation:**
- Commands: See docs/07-commands.md
- Workflows: See docs/14-workflows.md
- Troubleshooting: See docs/11-troubleshooting.md
