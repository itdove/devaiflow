# DevAIFlow Agent Workflow Guide

This file defines the workflow and behavioral constraints for Claude agents working within DevAIFlow (daf) sessions.

**What is daf?** A Claude Code session manager that organizes development work, tracks time, and integrates with JIRA.

---

## External Documentation

**For CLI command syntax:** Consult the **daf-cli skill** in `.claude/skills/daf-cli/`
- All daf command documentation (syntax, flags, options, examples)
- Available commands in Claude sessions vs restricted commands

**For JIRA field intelligence:** See **daf-jira-fields skill** in `.claude/skills/daf-jira-fields/`
- Field mapping structure and validation rules
- System vs custom field handling
- Default value application
- Discovering YOUR JIRA's custom fields

**For JIRA templates:** See **ORGANIZATION.md**
- JIRA Wiki markup syntax requirements
- Issue templates (Epic, Story, Spike, Bug, Task)
- Organization-specific JIRA policies and field mappings

---

## JIRA Integration Workflow

DevAIFlow provides two complementary approaches for JIRA operations:

### 1. Reading JIRA Issues - Use Atlassian MCP

For **fast JIRA reads** (viewing tickets, checking status), use the Atlassian MCP server:

```
mcp__atlassian__getTeamworkGraphObject
```

**Advantages:**
- Faster than CLI commands
- Direct API access
- Rich structured data

**When to use:**
- Reading JIRA ticket details
- Checking issue status and fields
- Viewing comments and history

### 2. JIRA Operations - Use daf CLI

For **creating/updating JIRA issues**, use `daf jira` commands (documented in daf-cli skill):

```bash
daf jira create story --summary "..." --parent PROJ-1234
daf jira update PROJ-12345 --field custom_field=value
daf jira add-comment PROJ-12345 "Progress update"
```

**When to use:**
- Creating new JIRA issues
- Updating issue fields
- Adding comments
- Complex operations requiring validation

### 3. Field Mappings - Use daf-jira-fields Skill

**CRITICAL**: Before creating/updating JIRA issues, understand field mappings:

```bash
# Discover YOUR JIRA's custom fields
daf config show --fields
```

The **daf-jira-fields skill** teaches you:
- System fields vs custom fields (CRITICAL distinction)
- Required fields for each issue type
- Allowed values for select fields
- How defaults are applied

**Common mistakes to avoid:**
```bash
# ❌ WRONG - System field with --field
daf jira create bug --field components=backend

# ✅ CORRECT - System field with dedicated option
daf jira create bug --components backend

# ❌ WRONG - Using customfield ID directly
daf jira create story --field customfield_12345=value

# ✅ CORRECT - Using mapped field name
daf jira create story --field team_assignment=value
```

**Workflow example:**
1. Read field mappings: `daf config show --fields`
2. Identify required fields for issue type (e.g., Story)
3. Use correct syntax (system options vs `--field`)
4. Create issue with all required fields

---

## Understanding Multi-Project Sessions

DevAIFlow supports multi-project sessions where a single session can span multiple related repositories. This is useful when working on features that require coordinated changes across multiple codebases (e.g., backend API + frontend UI).

### Viewing Projects in the Current Session

To see which projects are included in the current session, use:

```bash
daf active
```

**What it shows:**
- DAF Session name
- Session type (single-project or multi-project with count)
- Workspace path
- Goal/description
- Time tracked for this work session
- Status (in_progress, paused, complete)
- **List of all projects** in the session with their git branches

**Example output:**
```
╭────────────────────── ▶ Currently Active Conversation ───────────────────────╮
│                                                                              │
│  DAF Session: feature-x                                                      │
│  Type: Multi-project (2 projects)                                            │
│  Workspace: /Users/user/development                                          │
│  Goal: Implement caching layer across backend and frontend                   │
│  Time (this work session): 1h 23m                                            │
│  Status: in_progress                                                         │
│                                                                              │
│  Projects in this session:                                                   │
│    • backend-api (branch: feature-x)                                         │
│    • frontend-app (branch: feature-x)                                        │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

**Use this command to:**
- Verify which repositories are part of the current session
- Check which git branch each project is using
- Confirm you're working in the correct session before making changes
- See session status and time tracking

### Multi-Project Context

When working in a multi-project session:

1. **Each project has its own git repository and branch** - Changes in one project don't affect the git state of another
2. **You're working in ONE project at a time** - Your current working directory is in one specific project
3. **Shared context across projects** - The AI agent has shared context and can understand how changes relate across projects
4. **Coordinated branching** - All projects typically use the same branch name for consistency

**Before making changes, always:**
1. Run `daf active` to see which projects are in the session
2. Verify your current working directory to confirm which project you're in
3. Understand how your changes might affect other projects in the session

---

## Workflow: Standard Development Sessions

When working in sessions opened by the user (via `daf open`), follow this workflow:

### 1. Session Start - Read Acceptance Criteria

**CRITICAL FIRST STEP:**
- Read the JIRA ticket immediately to understand acceptance criteria
- Plan your work to address each criterion
- Track which criteria you'll address as you work

**Why:** Acceptance criteria define what "done" means for this task.

### 2. During Development

**Focus on:**
- Making code changes to implement the requested feature/fix
- Verifying each acceptance criterion as you complete related work
- Testing that criteria are actually met (run tests, check implementation manually)
- Tracking progress using `daf note` or `daf jira add-comment`

**Documenting Progress:**
- ✅ **`daf note`** - Add local session notes (works inside Claude sessions)
  - Use for implementation details, decisions, and progress tracking
  - Example: `daf note "Completed API endpoint implementation"`
- ✅ **`daf jira add-comment`** - Add JIRA comments for stakeholder visibility
  - Use for team communication and progress updates
  - Example: `daf jira add-comment PROJ-123 "Fixed authentication bug"`

**Do NOT:**
- ❌ Create git commits or run git commands (see git-cli skill for why)
- ❌ Create pull requests or merge requests (see gh-cli/glab-cli skills for why)
- ❌ Run any `daf` commands that are user-facing (new, open, complete, config, init, upgrade)

**Why:** The user runs `daf complete` outside Claude sessions to handle ALL git and PR/MR operations. Manual operations interfere with session tracking and proper attribution.

### 3. Before Exiting Session

**Final review:**
- Review all acceptance criteria one final time
- Update JIRA to tick off completed criteria
- If any criteria are incomplete, document why in a note

**Why:** This ensures JIRA accurately reflects progress and blockers are documented.

---

## Workflow: Ticket Creation Sessions

For sessions opened by the user via `daf jira new` (investigation sessions for creating tickets):

**Purpose:** Analyze the codebase to create a well-informed JIRA ticket

**Constraints:**
- ❌ DO NOT modify any code or files
- ❌ DO NOT run git commands (see git-cli skill for restrictions)
- ✅ ONLY read files, search code, and analyze architecture
- ✅ Create JIRA ticket when analysis is complete

**Workflow:**
1. Analyze the codebase to understand implementation approach
2. Read relevant files, search for patterns, understand architecture
3. Create detailed JIRA ticket based on your analysis
4. Include acceptance criteria based on what you discovered

**Why:** These sessions are analysis-only. Git operations are skipped entirely.

---

## Command Usage Guidelines

**Consult the appropriate skill for command documentation:**
- **daf-cli skill** - daf command syntax, flags, and examples
- **git-cli skill** - git command restrictions and why they're not allowed in sessions
- **gh-cli skill** - GitHub PR/MR restrictions and workflow
- **glab-cli skill** - GitLab MR restrictions and workflow

**Key principle:**
- Use daf commands for JIRA operations and session tracking
- Defer all git/PR/MR operations to the user (who runs `daf complete` outside sessions)
