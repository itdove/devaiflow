---
name: daf-workflow
description: DevAIFlow session context loader — reads session metadata, issue tracker tickets, and context files. Auto-activates when DAF_SESSION_NAME is set. Also useful when asked about current task, session status, or workflow steps for daf open, daf new, daf git new, daf jira new, and daf investigate.
user-invocable: true
---

# DevAIFlow Session Context

This skill is used by every supported AI agent or IDE integration. In this
document, **agent session** means the configured backend for the current
session (for example Claude Code, Codex, GitHub Copilot, Cursor, Windsurf,
Aider, Continue, OpenCode, Crush, or an Ollama-backed adapter). Use an
agent-specific name or path only when the instruction explicitly calls for
backend-specific behavior.

Session identifiers are also backend-specific. Use the active conversation's
agent session ID from `daf active` or `daf info`; do not substitute the most
recently opened session from another agent or repository.

Run this command to check the session environment:

```bash
echo "DAF_SESSION_NAME=$DAF_SESSION_NAME" "DAF_COMMAND=$DAF_COMMAND"
```

**Important:** Use this command exactly as written — the text must match the agent's permission pattern. Do not rephrase or restructure.

If `DAF_SESSION_NAME` is set (non-empty), this is a managed DevAIFlow session — follow the initialization steps below. If empty, skip to the **Standalone Workflow Guide** section at the bottom.

---

## Session Initialization

When `DAF_SESSION_NAME` is set, perform these steps **before doing any other work**:

### 1. Read Session Metadata

```bash
daf info $DAF_SESSION_NAME
```

This shows: session name, goal, issue key, status, working directory, branch, workspace, session type, and conversation history.

#### DAF-managed conversation titles

The **DAF session name** (`Name` in `daf info`) identifies the session; the
**goal** (`--goal`) describes the work; the backend's **LLM conversation title**
is separate display metadata.

For **Claude Code, Pi, and OpenCode**, DAF manages native title setting at launch
and on supported resume paths. The title is the **exact current DAF session
name** from metadata, not the goal, issue summary, or an agent-generated task
summary. This applies to `daf new`, `daf open`, `daf git new`, `daf jira new`,
and `daf investigate`; read-only and ticket-creation constraints still apply.

Do not independently rename the conversation from `--goal`, rename the DAF
session, or duplicate DAF's launch/resume title-setting operations. Other
backends retain their normal agent-managed titles. If a supported backend's
title does not match, report a **title-propagation problem**; do not invent
rename commands, edit backend storage, or use an unverified skill-level fallback.

### 2. Read Issue Tracker Ticket

If `daf info` shows an issue key (e.g., `owner/repo#123` or `PROJ-456`), read the
ticket exactly once using the key and the matching backend. For GitHub, use
structured output so a successful issue with an empty body or no comments is
still distinguishable from a command failure.

```bash
# For GitHub issues with an owner/repo#number key from daf info
gh issue view <number> --repo <owner/repo> --json title,body,comments,labels,url

# For GitHub issues with a #number or number-only key
gh issue view <number> --json title,body,comments,labels,url

# For GitLab issues with an owner/repo#number key
glab issue view <number> -R <owner/repo> --comments

# For GitLab issues with a #number or number-only key
glab issue view <number> --comments

# For JIRA tickets (use the issue key from daf info)
daf jira view <issue_key> --comments
```

Replace placeholders with the values shown in `daf info`. When the GitHub or
GitLab key contains `owner/repo#number`, split at the final `#` and pass the
repository explicitly (`--repo` for `gh`, `-R` for `glab`). Do not first run an
unqualified lookup and then retry with a repository.

Run only one lookup command for the ticket. If it exits non-zero, report the
command and its error clearly, then continue initialization without ticket
contents; do not retry with a different repository, output mode, or CLI command
unless the user explicitly asks. Empty `body` or `comments` fields in a
successful structured response are valid issue data, not a reason to retry.

### 3. Read Context Files

First, discover the DevAIFlow config directory:

```bash
CONFIG_DIR=$(daf config show --paths | grep config_dir | cut -d= -f2)
```

Then read the hierarchical context files if they exist in `CONFIG_DIR`:
- `CONFIG_DIR/ENTERPRISE.md` (enterprise-wide policies and standards)
- `CONFIG_DIR/ORGANIZATION.md` (organization coding standards)
- `CONFIG_DIR/TEAM.md` (team conventions and workflows)
- `CONFIG_DIR/USER.md` (personal notes and preferences)

### 4. Read Skill Files

Using the same `CONFIG_DIR` from Step 3, check for additional skills:
- `CONFIG_DIR/.claude/skills/` (the current DevAIFlow hierarchical skill
  storage for enterprise/organization/team/user skills)
- Project-level skills for the active agent, such as `.claude/skills/`,
  `.codex/skills/`, `.cursor/skills/`, or `.windsurf/skills/` (or the path
  reported by `daf assets --dry-run` for another supported agent)

Global skills are installed in an agent-specific directory by `daf assets`.
Do not assume that a Claude-specific global directory is available when the
session uses another agent.

Read any that are relevant to the session.

### 5. Sync Temp Directory (if applicable)

If the session uses a temporary directory clone (`ticket_creation`, `investigation`, or issue creation sessions like `daf git new` / `daf jira new`), the cloned repo may be stale — it was cloned at session creation time and may not have the latest changes from the remote.

**How to detect:** Check `daf info` output for:
- Session type: `ticket_creation` or `investigation`
- Project path containing `/tmp/` or `/var/folders/`
- `DAF_COMMAND` is `git-new`, `jira-new`, or `investigate`

**Before starting analysis**, pull the latest changes (detect the default branch dynamically — do not assume `main`):
```bash
git fetch origin
git rebase "origin/$(git remote show origin | awk '/HEAD branch/{print $NF}')"
```

- If rebase succeeds, proceed with analysis on the latest code
- If rebase has conflicts, stop and inform the user; preserve local work before any manual clone removal or replacement
- This does NOT apply to development sessions (`daf new`, `daf open`) which use the real workspace and handle branch sync during `daf open`

### 6. Follow Command-Specific Workflow

Use the `DAF_COMMAND` value from the output above and follow the matching section below.

---

## Development Sessions (DAF_COMMAND = open | new)

Standard development session. Resume or start work on a task.

**Initial branch selection:** When DAF needs to create a branch, its source picker
chooses `upstream` when configured, otherwise `origin`, otherwise the first
configured remote alphabetically, and resolves that remote's actual default.
It marks that branch `(default)` and Enter selects it;
remote-qualified selections preserve the source repository's identity. If the
default is unresolved or unavailable in the menu, Enter cancels rather than
selecting an unrelated branch. Explicit selection and custom entry remain available.
If branch discovery fails, DAF names the selected remote and gives a credential-safe
explanation before manual entry; timeout, nonzero Git exit, and startup errors are
distinct from a successful query with no branch heads. Diagnostics use Git transport,
not `gh`/`glab` API authentication, and omit raw Git output and remote URLs. Manual
entry and cancellation remain available; do not infer an affected machine's cause
without its exact installed version, selected remote, and Git diagnostic outcome.
With no remotes, DAF uses a common local base or the current attached branch.
Automatic modes do not prompt or create a branch without a resolved or explicitly
provided source. Multi-project creation cancels if any project has no selected base.

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
   gh issue comment <number> --body "Progress update"  # or: glab issue note <number> -m "Progress update"
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

**When work is complete**, inform the user that all acceptance criteria are met and the session is ready for completion. The user runs `daf complete` outside the active agent session to commit, create PR/MR, and close.

For sessions using temporary clones, the user must first **exit the agent** and
move any terminals out of the clone. Completion from another terminal refuses
to change session status or time tracking while the clone is in use, even if
the native ID is `pending-capture` or time tracking is paused. If an agent starts
during completion and cleanup is deferred, exit the agent and rerun completion
from the original workspace; deferred cleanup is not automatically scheduled.
Normal exit, pause, and completion preserve the clone by default. An existing
saved `concurrency.cleanup_on_complete: true` retains immediate cleanup;
`false` adopts preservation. Explicit session deletion still cleans up clones.

OpenCode v2 clone launches/resumes and session-ID polling use its supported
`--standalone` private-server lifecycle. UI exit is not proof that an older shared
backend's resources exited. Prompted and automatic completion preflight actual
directory holders and report their PID/name/cwd and parent details when accessible.
If shared workspace resources remain, preserve the clone, check ownership and other
clients, and release only an exclusively owned inactive workspace through supported
backend controls before retrying. Do not stop shared services, exempt MCP/security
processes by name, or change security settings. Native conversation identity and
session metadata are preserved on refusal.

OpenCode retains native IDs returned by titled launch rather than rediscovering
them on exit; `daf open` saves that identity before starting the child. Fallback
capture has a two-second total query deadline and fails closed on query errors or
same-project ambiguity. A legacy `pending-capture` reopen cannot prove ownership
without a saved launch ID/baseline, so it stops with verification guidance rather
than silently replacing the conversation. The user can verify the native ID and
canonical directory, then run `daf update <session-name> --session-id <verified-id>`
outside the agent, or deliberately use `daf open <session-name> --new-conversation`.
Do not guess an ID from ordering/titles or edit backend storage to recover it.

Cancelled first-open setup is retryable with ordinary `daf open` when DAF saved
explicit never-launched provenance. That proof is consumed before native creation
or agent launch; unresolved launch attempts still stop safely. For legacy pending
records, an empty branch or zero messages is not proof of no launch. The explicit
`--new-conversation` start-over archives the old identity/history and works even
without a saved branch, retrying initial setup. If that setup is cancelled again,
ordinary reopen retries the new record; do not invent a verified native ID.

All clone allocation/recovery paths share `clone_retention.max_idle_days` (30)
and `clone_retention.max_size_mb` (10240 MiB) limits; `0` disables each independently.
Retention uses the resolved `clone_dir`, legacy `concurrency.auto_clone_path`, or
XDG/unified clone root. It removes eligible expired entries, then deterministic
least-recently-used entries under size pressure, and reconciles usage after cloning.
Live/in-progress clones and local-only Git/worktree data are protected; a warning
explains when the budget cannot be met rather than discarding work. Paused/completed
metadata and other conversation references do not permanently pin safe clones.

Reopening a missing clone warns and restores its recorded origin, branch, and exact
absolute path before agent launch, preserving native conversation identity even
without the original workspace. Attribute a missing clone to retention only when
an eviction record confirms it. A recovery failure must stop safely, preserve
recovery metadata, and never silently switch repositories or replace a recoverable
conversation. Do not delete local work to resolve retention/recovery warnings.

**Do NOT:**
- Create git commits (handled by `daf complete`)
- Create pull/merge requests (handled by `daf complete`)
- Run user-facing daf commands (new, open, complete, config, init, upgrade)

---

## GitHub/GitLab Issue Creation (DAF_COMMAND = git-new)

Analysis-only session for creating a GitHub/GitLab issue.

**Temp directory session** — sync before analysis (see Step 5).

**CRITICAL CONSTRAINTS:**
- DO NOT modify any code or create/checkout git branches
- DO NOT make any file changes — only READ and ANALYZE
- Focus on understanding the codebase to write a good issue

**Workflow:**
1. Sync temp directory (see Step 5)
2. Analyze the codebase to understand the goal from `daf info`
3. Read relevant files, search for patterns, understand architecture
4. Create the issue using `gh issue create` (GitHub) or `glab issue create` (GitLab):
   ```bash
   # GitHub
   gh issue create --title "..." --body "<your analysis>"

   # GitLab
   glab issue create --title "..." --description "<your analysis>"
   ```
5. Include detailed description and acceptance criteria based on analysis
6. Report the created issue URL and key in the final response. GitHub/GitLab
   ticket-creation sessions do not currently have a supported DAF session-link
   operation.
7. After leaving the agent session, reopen it with the session name printed by
   `daf git new`, for example: `daf open <session-name>`.

Read the **daf-git skill** for correct command syntax.

---

## JIRA Ticket Creation (DAF_COMMAND = jira-new)

Analysis-only session for creating a JIRA ticket.

**Temp directory session** — sync before analysis (see Step 5).

**CRITICAL CONSTRAINTS:**
- DO NOT modify any code or create/checkout git branches
- DO NOT make any file changes — only READ and ANALYZE
- Focus on understanding the codebase to write a good JIRA ticket

**Workflow:**
1. Sync temp directory (see Step 5)
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

**Temp directory session** — sync before analysis (see Step 5).

**CRITICAL CONSTRAINTS:**
- DO NOT modify any code or create/checkout git branches
- DO NOT make any file changes — only READ and ANALYZE
- Focus on understanding the codebase and documenting findings

**Workflow:**
1. Sync temp directory (see Step 5)
2. Read the session goal from `daf info`
3. Investigate the codebase: read files, search patterns, analyze architecture
4. Analyze feasibility and identify implementation approaches
5. Document findings and recommendations
6. If you discover bugs or improvements, you MAY create tickets:
   - JIRA: `daf jira create`
   - GitHub/GitLab: `gh issue create` / `glab issue create`

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
| Create ticket (no session) | `daf jira create` | `gh issue create` / `glab issue create` |
| View ticket | `daf jira view` | `gh issue view` / `glab issue view` |
| Update ticket | `daf jira update` | `daf git update` |
| Add comment | `daf jira add-comment` | `gh issue comment` / `glab issue note` |

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
daf config show --paths         # Config, data, state directory paths
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
**For project standards:** See **AGENTS.md** and any project-specific agent
instruction files, such as **CLAUDE.md** when Claude Code is in use.
