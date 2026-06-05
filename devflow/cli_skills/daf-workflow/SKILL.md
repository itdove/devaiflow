---
name: daf-workflow
description: DevAIFlow session context loader. Activates when DAF_SESSION_NAME env var is set. Reads session metadata, issue tracker tickets, and context files to understand the current task. Provides per-command workflow guidance for daf open, daf new, daf git new, daf jira new, and daf investigate.
user-invocable: true
---

# DevAIFlow Session Context

Check the `DAF_SESSION_NAME` environment variable. If set, this is a managed DevAIFlow session — follow the initialization steps below. If not set, skip to the **Standalone Workflow Guide** section at the bottom.

---

## Session Initialization

When `DAF_SESSION_NAME` is set, perform these steps **before doing any other work**:

### 1. Read Session Metadata

```bash
daf info $DAF_SESSION_NAME
```

This shows: session name, goal, issue key, status, working directory, branch, workspace, session type, and conversation history.

### 2. Read Issue Tracker Ticket

If `daf info` shows an issue key (e.g., `owner/repo#123` or `PROJ-456`), read the ticket using that key:

```bash
# For GitHub issues (use the issue number from daf info)
gh issue view <number> --comments

# For GitLab issues
glab issue view <number> --comments

# For JIRA tickets (use the issue key from daf info)
daf jira view <issue_key> --comments
```

Replace `<number>` or `<issue_key>` with the actual value shown in `daf info` output.

### 3. Read Context Files

Read the hierarchical context files if they exist:
- `~/.daf-sessions/ENTERPRISE.md` (enterprise-wide policies and standards)
- `~/.daf-sessions/ORGANIZATION.md` (organization coding standards)
- `~/.daf-sessions/TEAM.md` (team conventions and workflows)
- `~/.daf-sessions/USER.md` (personal notes and preferences)

### 4. Read Skill Files

Check for additional skills loaded in this session:
- Enterprise/organization/team/user skills in `~/.daf-sessions/.claude/skills/`
- Project-level skills in the project's `.claude/skills/` directory

Read any that are relevant to the session.

### 5. Sync Temp Directory (if applicable)

If the session uses a temporary directory clone (`ticket_creation`, `investigation`, or issue creation sessions like `daf git new` / `daf jira new`), the cloned repo may be stale — it was cloned at session creation time and may not have the latest changes from the remote.

**How to detect:** Check `daf info` output for:
- Session type: `ticket_creation` or `investigation`
- Project path containing `/tmp/` or `/var/folders/`
- `DAF_COMMAND` is `git-new`, `jira-new`, or `investigate`

**Before starting analysis**, pull the latest changes:
```bash
git fetch origin && git rebase origin/main
```

- If rebase succeeds, proceed with analysis on the latest code
- If rebase has conflicts, inform the user — the temp directory can be safely deleted and re-cloned by reopening the session
- This does NOT apply to development sessions (`daf new`, `daf open`) which use the real workspace and handle branch sync during `daf open`

### 6. Follow Command-Specific Workflow

Check `DAF_COMMAND` environment variable and follow the matching section below.

---

## Development Sessions (DAF_COMMAND = open | new)

Standard development session. Resume or start work on a task.

**Workflow:**
1. Read the issue tracker ticket and identify acceptance criteria
2. Plan your work to address each criterion
3. Make code changes, run tests, verify acceptance criteria
4. Track progress with `daf note "Completed AC #1: ..."`
5. Before exiting: update issue tracker to tick completed criteria:
   ```bash
   # JIRA (use issue key from daf info)
   daf jira update <issue_key> --field acceptance_criteria="- [x] Done\n- [] Pending"
   daf jira add-comment <issue_key> "Progress update"
   
   # GitHub/GitLab (use issue key from daf info)
   daf git update <issue_key> --labels done
   daf git add-comment <issue_key> "Progress update"
   ```

**Testing Requirements:**
- Identify the project's testing framework from the codebase
- Run the project's test suite after making code changes
- Create tests for new methods before or during implementation
- Fix all failing tests before marking tasks complete

**Multi-project sessions:**
- Run `daf active` to see which projects are in this session
- Verify your current working directory before making changes
- Each project has its own git repository and branch

**Do NOT:**
- Create git commits (handled by `daf complete`)
- Create pull/merge requests (handled by `daf complete`)
- Run user-facing daf commands (new, open, complete, config, init, upgrade)

---

## GitHub/GitLab Issue Creation (DAF_COMMAND = git-new)

Analysis-only session for creating a GitHub/GitLab issue.

**Temp directory session** — run `git fetch origin && git rebase origin/main` before analysis (see Step 5).

**CRITICAL CONSTRAINTS:**
- DO NOT modify any code or create/checkout git branches
- DO NOT make any file changes — only READ and ANALYZE
- Focus on understanding the codebase to write a good issue

**Workflow:**
1. Sync temp directory: `git fetch origin && git rebase origin/main`
2. Analyze the codebase to understand the goal from `daf info`
3. Read relevant files, search for patterns, understand architecture
4. Create the issue using `daf git create`:
   ```bash
   daf git create {bug|story|task} \
     --summary "..." \
     --description "<your analysis>" \
     --acceptance-criteria "..."
   ```
5. Include detailed description and acceptance criteria based on analysis

Read the **daf-git skill** for correct command syntax.

After creating the issue, the session is automatically renamed to `creation-<issue_number>`.

---

## JIRA Ticket Creation (DAF_COMMAND = jira-new)

Analysis-only session for creating a JIRA ticket.

**Temp directory session** — run `git fetch origin && git rebase origin/main` before analysis (see Step 5).

**CRITICAL CONSTRAINTS:**
- DO NOT modify any code or create/checkout git branches
- DO NOT make any file changes — only READ and ANALYZE
- Focus on understanding the codebase to write a good JIRA ticket

**Workflow:**
1. Sync temp directory: `git fetch origin && git rebase origin/main`
2. Analyze the codebase to understand the goal from `daf info`
3. Read relevant files, search for patterns, understand architecture
4. Check field defaults: `daf config show`
5. Create the ticket using `daf jira create`:
   ```bash
   daf jira create {story|bug|task|epic|spike} \
     --summary "..." \
     --description "<your analysis in JIRA Wiki markup>" \
      --field acceptance_criteria="- [] criterion 1\n- [] criterion 2"
   ```
6. Use JIRA Wiki markup (NOT Markdown) for description field
7. Include acceptance criteria in checkbox format

Read the **daf-jira skill** and **daf-jira-fields skill** for field rules and syntax.

After creating the ticket, the session is automatically renamed to `creation-<ticket_key>`.

---

## Investigation (DAF_COMMAND = investigate)

Read-only investigation and analysis session.

**Temp directory session** — run `git fetch origin && git rebase origin/main` before analysis (see Step 5).

**CRITICAL CONSTRAINTS:**
- DO NOT modify any code or create/checkout git branches
- DO NOT make any file changes — only READ and ANALYZE
- Focus on understanding the codebase and documenting findings

**Workflow:**
1. Sync temp directory: `git fetch origin && git rebase origin/main`
2. Read the session goal from `daf info`
3. Investigate the codebase: read files, search patterns, analyze architecture
4. Analyze feasibility and identify implementation approaches
5. Document findings and recommendations
6. If you discover bugs or improvements, you MAY create tickets:
   - JIRA: `daf jira create`
   - GitHub/GitLab: `daf git create`

**When investigation is complete:**
- Provide a clear summary of findings
- List key files and components involved
- Suggest implementation approaches
- Note concerns or blockers
- The user saves findings with `daf note` or exports them

---

## Standalone Workflow Guide

When `DAF_SESSION_NAME` is **not set**, you are running outside a managed DevAIFlow session. Use this reference for daf commands.

### Issue Tracker Integration

DevAIFlow auto-detects your issue tracker from git remote URLs:
- `github.com` → GitHub Issues (`daf git` commands)
- `gitlab.com` → GitLab Issues (`daf git` commands)
- `JIRA_URL` env var → JIRA (`daf jira` commands)

### Command Quick Reference

| Action | JIRA | GitHub/GitLab |
|--------|------|---------------|
| Ticket creation session | `daf jira new` | `daf git new` |
| Create ticket (no session) | `daf jira create` | `daf git create` |
| View ticket | `daf jira view` | `gh issue view` / `glab issue view` |
| Update ticket | `daf jira update` | `daf git update` |
| Add comment | `daf jira add-comment` | `daf git add-comment` |

### Session Information

```bash
daf active                      # Show currently active conversation
daf info [SESSION|--latest]     # Session details
daf status                      # Status dashboard
daf list [--active]             # List all sessions
daf notes                       # View session notes
```

### Configuration

```bash
daf config show                 # Merged configuration
daf config show --fields        # Custom fields (JIRA)
daf config refresh-jira-fields  # Refresh from JIRA API
```

### Best Practices

1. Always read acceptance criteria first — understand what "done" means
2. Use issue tracker for team visibility — add comments for progress
3. Use `daf note` for local implementation details
4. Verify work meets acceptance criteria before exiting
5. Run `daf active` before making changes in multi-project sessions
6. Defer git commits and PR/MR creation to `daf complete`

**For detailed command syntax:** See **daf-cli skill**
**For JIRA field rules:** See **daf-jira-fields skill**
**For project standards:** See **AGENTS.md** and **CLAUDE.md**
