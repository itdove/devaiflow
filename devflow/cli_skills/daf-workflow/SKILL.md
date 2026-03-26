---
name: daf-workflow
description: Workflow guidance for development sessions, ticket creation, and multi-project work with DevAIFlow
user-invocable: false
---

# DevAIFlow Workflow Guide

This skill provides comprehensive workflow guidance for AI agents working within DevAIFlow (daf) sessions.

**What is daf?** A session manager for AI coding assistants that organizes development work, tracks time, and integrates with issue trackers (JIRA, GitHub Issues, GitLab Issues).

---

## Quick Reference

**For command syntax:** See **daf-cli skill**
**For JIRA field rules:** See **daf-jira-fields skill**
**For JIRA templates:** See **ORGANIZATION.md** (if using JIRA)
**For project standards:** See **AGENTS.md** and **CLAUDE.md**

---

## Issue Tracker Integration

DevAIFlow auto-detects your issue tracker based on git remote URLs and provides appropriate commands.

### Auto-Detection

DevAIFlow automatically detects your issue tracker:

**GitHub Issues:**
- Detected from: `github.com` in git remote URL
- Commands: `daf git view`, `daf git create`, `daf git update`
- Example: `git remote` → `https://github.com/user/repo.git` → Uses GitHub Issues

**GitLab Issues:**
- Detected from: `gitlab.com` or self-hosted GitLab in git remote URL
- Commands: `daf git view`, `daf git create`, `daf git update`
- Example: `git remote` → `https://gitlab.com/user/repo.git` → Uses GitLab Issues

**JIRA:**
- Detected from: `JIRA_URL` environment variable or config
- Commands: `daf jira view`, `daf jira create`, `daf jira update`
- Example: `JIRA_URL=https://jira.company.com` → Uses JIRA

### Reading vs Creating/Updating Issues

#### For Reading (Fast)

**JIRA:** Use Atlassian MCP for fast reads
```
mcp__atlassian__getTeamworkGraphObject
```

**GitHub/GitLab:** Use `daf git view` command
```bash
daf git view owner/repo#123 --comments
```

**Advantages:**
- Faster than CLI commands
- Direct API access
- Rich structured data

#### For Creating/Updating (With Validation)

**JIRA:** Use `daf jira` commands
```bash
daf jira create story --summary "..." --parent PROJ-1234
daf jira update PROJ-12345 --field custom_field=value
daf jira add-comment PROJ-12345 "Progress update"
```

**GitHub/GitLab:** Use `daf git` commands
```bash
daf git create bug --summary "..." --parent owner/repo#123
daf git update owner/repo#456 --labels bug,priority-high
daf git add-comment owner/repo#789 "Fixed in latest commit"
```

**Advantages:**
- Field validation before API calls
- Consistent interface across backends
- Error handling with helpful messages

### Field Mappings (JIRA Only)

**CRITICAL:** Before creating/updating JIRA issues, understand field mappings.

See **daf-jira-fields skill** for:
- System fields vs custom fields
- Required fields for each issue type
- Allowed values for select fields
- How defaults are applied

**Quick discovery:**
```bash
daf config show --fields
```

---

## Understanding Multi-Project Sessions

DevAIFlow supports multi-project sessions where a single session spans multiple related repositories.

### Viewing Projects in Current Session

```bash
daf active
```

**Shows:**
- Session name and type
- Workspace path
- Goal/description
- Time tracked
- Status
- **All projects** in the session with git branches

**Example output:**
```
╭────────────────────── ▶ Currently Active Conversation ───────────────────────╮
│                                                                              │
│  DAF Session: feature-x                                                      │
│  Type: Multi-project (2 projects)                                            │
│  Workspace: /Users/user/development                                          │
│  Goal: Implement caching layer                                               │
│  Time (this work session): 1h 23m                                            │
│  Status: in_progress                                                         │
│                                                                              │
│  Projects in this session:                                                   │
│    • backend-api (branch: feature-x)                                         │
│    • frontend-app (branch: feature-x)                                        │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### Multi-Project Context

**Key principles:**
1. Each project has its own git repository and branch
2. You're working in ONE project at a time (current working directory)
3. AI agent has shared context across all projects
4. All projects typically use the same branch name

**Before making changes:**
1. Run `daf active` to see which projects are in the session
2. Verify your current working directory
3. Understand how changes might affect other projects

---

## Workflow: Standard Development Sessions

For sessions opened via `daf open`:

### 1. Session Start - Read Acceptance Criteria

**CRITICAL FIRST STEP:**
- Read the issue immediately to understand acceptance criteria
- Plan your work to address each criterion
- Track which criteria you'll address as you work

**Why:** Acceptance criteria define what "done" means.

### 2. During Development

**Focus on:**
- Making code changes to implement the requested feature/fix
- Verifying each acceptance criterion as you complete work
- Testing that criteria are met (run tests, check implementation)
- Tracking progress

**Documenting Progress:**

**Session notes (local):**
```bash
daf note "Completed API endpoint implementation"
```

**Issue tracker comments (team visibility):**
```bash
# JIRA
daf jira add-comment PROJ-123 "Fixed authentication bug"

# GitHub/GitLab
daf git add-comment owner/repo#123 "Fixed authentication bug"
```

**Do NOT:**
- ❌ Create git commits (see **git-cli skill**)
- ❌ Create pull/merge requests (see **gh-cli** and **glab-cli skills**)
- ❌ Run user-facing `daf` commands (new, open, complete, config, init, upgrade)

**Why:** The user runs `daf complete` outside sessions to handle ALL git and PR/MR operations. Manual operations interfere with session tracking.

### 3. Before Exiting Session

**Final review:**
- Review all acceptance criteria
- Update issue tracker to tick off completed criteria
- Document incomplete criteria and blockers

**Why:** Ensures the issue tracker accurately reflects progress.

---

## Choosing Your Issue Tracker

**Before creating tickets, determine which issue tracker to use.**

### Auto-Detection (Recommended)

DevAIFlow automatically detects your issue tracker from git remote URLs:
- `github.com` → GitHub Issues (`daf git` commands)
- `gitlab.com` → GitLab Issues (`daf git` commands)
- `JIRA_URL` env var → JIRA (`daf jira` commands)

### User Confirmation Pattern

**If JIRA is configured (`JIRA_URL` is set), confirm with the user before creating tickets:**

```
I detected GitHub Issues from your git remote, but JIRA is also configured. Should I:
1. Create a GitHub issue (recommended based on git remote)
2. Create a JIRA ticket instead
```

**If JIRA is NOT configured:** Use auto-detected issue tracker from git remote (GitHub or GitLab) - no confirmation needed.

**Why:** Users with both systems configured may prefer one over the other for specific workflows.

### Command Equivalents

Both issue trackers support the same workflows:

| Action | JIRA Command | GitHub/GitLab Command |
|--------|--------------|------------------------|
| Ticket creation session | `daf jira new` | `daf git new` |
| Create ticket (no session) | `daf jira create` | `daf git create` |
| View ticket | `daf jira view` | `daf git view` |
| Update ticket | `daf jira update` | `daf git update` |
| Add comment | `daf jira add-comment` | `daf git add-comment` |

---

## Workflow: Ticket Creation Sessions

**Choose Your Issue Tracker:**
- For JIRA: `daf jira new` (analysis-only sessions)
- For GitHub/GitLab: `daf git new` (analysis-only sessions)

**Before creating a ticket, determine which issue tracker to use:**
1. DevAIFlow auto-detects from git remote URLs
2. If JIRA is also configured, ask the user to confirm or override the detection
3. Use the appropriate command based on their choice

For sessions opened via `daf jira new` or `daf git new` (analysis-only sessions):

**Purpose:** Analyze the codebase to create a well-informed issue

**Constraints:**
- ❌ DO NOT modify code or files
- ❌ DO NOT run git commands
- ✅ ONLY read files, search code, analyze architecture
- ✅ Create issue when analysis is complete

**Workflow:**
1. Analyze the codebase to understand implementation
2. Read relevant files, search patterns, understand architecture
3. Create detailed issue based on analysis
4. Include acceptance criteria based on discoveries

**Creating the issue:**

**JIRA:**
```bash
daf jira create {bug|story|task|epic|spike} \
  --summary "..." \
  --parent PROJ-1234 \
  --description "..." \
  --field acceptance_criteria="- [] criterion 1\n- [] criterion 2"
```

**GitHub/GitLab:**
```bash
daf git create {bug|story|task} \
  --summary "..." \
  --parent owner/repo#123 \
  --description "..."
```

**Why:** These sessions are analysis-only. Git operations are skipped entirely.

---

## Command Usage Guidelines

**See these skills for detailed documentation:**
- **daf-cli skill** - Command syntax, flags, and examples
- **git-cli skill** - Git command restrictions and rationale
- **gh-cli skill** - GitHub PR restrictions and workflow
- **glab-cli skill** - GitLab MR restrictions and workflow

**Key principle:**
- Use `daf` commands for issue tracker operations and session tracking
- Defer all git/PR/MR operations to the user (who runs `daf complete` outside sessions)

---

## Session Information Commands

**Check current session:**
```bash
daf active                      # Show currently active conversation
daf info [PROJ-12345|--latest]  # Session details
daf status                      # Status dashboard
daf list [--active]             # List all sessions
```

**View notes:**
```bash
daf notes                       # View all session notes
```

---

## Configuration

**View configuration:**
```bash
daf config show                 # Merged configuration
daf config show --fields        # YOUR issue tracker's custom fields (JIRA)
```

**Refresh JIRA fields:**
```bash
daf config refresh-jira-fields  # Refresh from JIRA API
```

---

## Best Practices

1. **Always read acceptance criteria first** - Understand what "done" means
2. **Use issue tracker for visibility** - Add comments for team communication
3. **Use session notes for details** - Track implementation decisions locally
4. **Verify your work** - Test that acceptance criteria are actually met
5. **Document blockers** - If stuck, document why in issue tracker
6. **Check multi-project context** - Run `daf active` before making changes
7. **Use correct issue tracker commands** - Auto-detection uses git remote URL

---

## Common Patterns

### Working Across Multiple Repositories

```bash
# Check which projects are in this session
daf active

# Work in current repository
# ... make changes ...

# Add note about cross-repo impact
daf note "Updated API contract in backend, frontend needs update"
```

### Updating Acceptance Criteria

**JIRA (checkbox format):**
```bash
daf jira update PROJ-123 \
  --field acceptance_criteria="- [x] Feature implemented\n- [x] Tests passing\n- [] Docs updated"
```

**GitHub/GitLab (task list in description):**
```bash
daf git update owner/repo#123 \
  --description "...existing description...\n\n## Progress\n- [x] Feature implemented\n- [x] Tests passing\n- [ ] Docs updated"
```

### Checking Issue Status

**JIRA (fast read with MCP):**
```
mcp__atlassian__getTeamworkGraphObject
```

**JIRA (CLI):**
```bash
daf jira view PROJ-123 --comments
```

**GitHub/GitLab:**
```bash
daf git view owner/repo#123 --comments
```

---

## Summary

**Key Takeaways:**
1. DevAIFlow auto-detects issue tracker from git remote
2. Use MCP/`daf git view` for fast reads
3. Use `daf jira`/`daf git` commands for creates/updates
4. Standard sessions: focus on acceptance criteria
5. Ticket creation sessions: analyze only, no code changes
6. Multi-project sessions: check `daf active` before changes
7. Defer git/PR/MR operations to user (`daf complete`)

**For More Information:**
- Commands: **daf-cli skill**
- JIRA fields: **daf-jira-fields skill**
- Project standards: **AGENTS.md**, **CLAUDE.md**
- JIRA templates: **ORGANIZATION.md**
