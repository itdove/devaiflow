# DevAIFlow Tool Usage Guide for Claude

This file provides essential instructions for using the `daf` tool (DevAIFlow) within Claude Code sessions. It is automatically loaded as context when you open a session via `daf open`.

**What is daf?** The `daf` tool (DevAIFlow) is a Claude Code session manager that helps organize development work, track time, and optionally integrate with JIRA for ticket management.

**When to use this guide:** This file is automatically read when sessions are opened. Refer to it when you need to:
- Understand JIRA issue template requirements (see Templates section below)
- Get project-specific context about daf tool usage

**Note**: Examples use generic placeholders (PROJECT, YourWorkstream). Actual values are configured in `~/.daf-sessions/config.json`.

---

## Detailed CLI Usage Documentation

For comprehensive CLI tool usage, refer to the **DevAIFlow skills** deployed to your workspace:

- **daf-cli skill** - Complete daf command reference, session management, JIRA integration
- **git-cli skill** - Git version control commands and workflows
- **gh-cli skill** - GitHub CLI for PR creation and GitHub operations
- **glab-cli skill** - GitLab CLI for MR creation and GitLab operations

**Deploying skills:** Run `daf upgrade` to deploy/update skills to your workspace's `.claude/skills/` directory.

**Accessing skills:** Skills are automatically available in Claude Code sessions. Claude will use them as needed for CLI operations.

---

## JIRA Issue Templates

**IMPORTANT**: See **ORGANIZATION.md** for:
- JIRA Wiki markup syntax requirements (mandatory for all JIRA fields)
- Complete JIRA issue templates for all issue types (Epic, Story, Spike, Bug, Task)
- Organization-specific JIRA policies and standards (if configured)

ORGANIZATION.md is automatically loaded as context when you open sessions via `daf open` or `daf jira new`.

---

## Quick Reference

For complete command documentation, see the **daf-cli skill**.

**Common Commands:**
```bash
# Session Management
daf new --name "feature-name" --goal "Description"
daf open <session-name-or-jira-key>
daf open <session-name> --path <repo-path>  # Multi-conversation: auto-select repo
daf open <session-name> --new-conversation  # Archive current, start fresh
daf complete <session-name>

# JIRA Operations
daf jira view PROJ-12345
daf jira create {bug|story|task} --summary "..." --parent PROJ-1234
daf jira update PROJ-12345 --description "..."

# Configuration
daf config tui  # Set Project Key to PROJ
daf config tui  # Set Workstream to WORK
```

**Multi-Conversation Sessions:**
When working on tasks that span multiple repositories, you can use `--path` to specify which repository to work on:
```bash
# Auto-select conversation by repository path
daf open PROJ-12345 --path /path/to/repo
daf open PROJ-12345 --path repo-name  # Repository name from workspace

# Without --path, you'll be prompted to select which conversation to open
daf open PROJ-12345  # Shows interactive conversation selection menu
```

For detailed usage, workflow examples, and troubleshooting, refer to the **daf-cli skill**.

---

## Development Workflow with daf Tool

**IMPORTANT FOR CLAUDE AGENTS**: When working in sessions opened via `daf open`, follow this workflow:

### During the Session (daf open)

**CRITICAL - FIRST STEP: Read Acceptance Criteria**
- **IMMEDIATELY** after session opens, run: `daf jira view <JIRA-KEY>`
- **READ** and **UNDERSTAND** all acceptance criteria checkboxes
- **PLAN** your work to address each criterion
- **TRACK** progress on each criterion as you work

**Development Work:**
- Focus on making code changes and implementing features
- **VERIFY** each acceptance criterion as you complete related work
- **TEST** that criteria are actually met (run tests, check implementation)
- Use `daf note` to track acceptance criteria progress: `daf note <JIRA-KEY> "Completed AC #1: [description]"`
- Do NOT create git commits manually
- Do NOT create PRs or MRs using gh/glab commands
- Do NOT use git add, git commit, or git push commands

**Before Exiting Session:**
- **REVIEW** all acceptance criteria one final time
- **UPDATE** JIRA to tick completed criteria: `daf jira update <JIRA-KEY> --acceptance-criteria "- [x] criterion 1\n- [x] criterion 2\n- [] pending criterion 3"`
- If any criteria are incomplete, document why in a note

### Completing the Session (daf complete)
The `daf complete` command handles ALL git operations automatically:
- Commits all changes with AI-generated commit messages
- Pushes branch to remote
- Creates draft PR/MR with proper template
- Updates JIRA ticket with session summary
- Marks session as complete

**Why this matters**: The daf tool manages the complete development workflow. Manual git operations can interfere with session tracking, proper attribution (Co-Authored-By), and JIRA integration.

### Common Workflow
```bash
# 1. User opens session (outside Claude Code)
daf open PROJ-12345

# 2. Claude IMMEDIATELY reads ticket and acceptance criteria
daf jira view PROJ-12345
# Claude identifies all acceptance criteria checkboxes and plans work

# 3. Claude makes code changes in the session
# - Edit files as requested
# - Run tests to verify acceptance criteria are met
# - Track AC progress: daf note PROJ-12345 "Completed AC #1: [description]"
# - Verify each criterion as work progresses

# 4. Before exiting, Claude updates JIRA with completed criteria
daf jira update PROJ-12345 --acceptance-criteria "- [x] criterion 1
- [x] criterion 2
- [] pending criterion 3"

# 5. User exits Claude Code

# 6. User completes session (outside Claude Code)
daf complete PROJ-12345
# This handles: commit, push, PR/MR creation, JIRA update
```

**Exception**: For ticket_creation sessions (`daf jira new`), git operations are skipped entirely as these are analysis-only sessions.

---

## Additional Resources

- **daf-cli skill** - Complete daf command reference
- **git-cli skill** - Git workflow and commands
- **gh-cli skill** - GitHub PR creation
- **glab-cli skill** - GitLab MR creation
- Run `daf --help` or `daf <command> --help` for command-specific help
- Full documentation: [DevAIFlow Documentation](https://github.com/itdove/devaiflow/tree/main/docs)
