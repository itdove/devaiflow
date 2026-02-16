---
name: daf-help
description: Show available daf commands and quick reference
---

Display a quick reference of commonly used daf commands.

```bash
daf --help
```

**Core Session Commands:**

**Starting work:**
```bash
daf sync --field <field_name>=<value>  # Filter by custom field (name from field_mappings)
daf new --name "..." --goal "..."      # Create new session
daf open PROJ-12345                    # Open/resume session
```

**During work:**
```bash
daf note "..."               # Add progress note
daf status                   # Check progress dashboard
daf active                   # Show currently active conversation
daf list                     # List all sessions
```

**Finishing work:**
```bash
daf complete PROJ-12345       # Complete session (commit, PR, JIRA update)
daf complete --latest        # Complete most recent session
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
daf init                     # Initialize configuration
daf config tui
daf config tui
daf config tui
daf upgrade                  # Upgrade slash commands
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

**Daily workflow:**
```bash
daf sync --field <field_name>=<value>  # Filter by field name (from field_mappings)
daf open PROJ-12345                    # Open a ticket to work on
# ... do work in Claude Code ...
daf note "Milestone reached"            # Add progress note
daf complete PROJ-12345                # End of work: commit, PR, update JIRA
```

**Multi-repo feature:**
```bash
daf new --name PROJ-12345 --goal "..." --path ~/backend
# ... work in backend ...
daf new --name PROJ-12345 --goal "..." --path ~/frontend  # Add conversation
/daf read-conversation      # Read backend work
# ... work in frontend with backend context ...
```

**Full documentation:**
- Commands: See docs/07-commands.md
- Workflows: See docs/14-workflows.md
- Troubleshooting: See docs/11-troubleshooting.md
