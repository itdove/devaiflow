# DevAIFlow Agent Workflow Guide

This file defines the workflow and behavioral constraints for Claude agents working within DevAIFlow (daf) sessions.

**What is daf?** A Claude Code session manager that organizes development work, tracks time, and integrates with JIRA.

---

## External Documentation

**For CLI command syntax:** Consult the **daf-cli skill** in `.claude/skills/daf-cli/`
- All daf command documentation (syntax, flags, options, examples)
- Available commands in Claude sessions vs restricted commands

**For JIRA templates:** See **ORGANIZATION.md**
- JIRA Wiki markup syntax requirements
- Issue templates (Epic, Story, Spike, Bug, Task)
- Organization-specific JIRA policies and field mappings

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
- Tracking progress on acceptance criteria using notes

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
