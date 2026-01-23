# Overview

## What is DevAIFlow?

DevAIFlow (`daf`) is a command-line tool that helps you manage Claude Code sessions with optional JIRA ticket integration. It solves the problem of managing multiple concurrent coding tasks by organizing each piece of work into isolated sessions with full context preservation.

## Quick Decision Guide

### ✅ Use This Tool If You...

- **Work on multiple JIRA tickets** and want to keep Claude conversations separate per ticket
- **Switch between tasks frequently** and need to resume with full context
- **Work across multiple repositories** for the same feature (backend + frontend + infrastructure)
- **Need time tracking** to understand how long tasks actually take
- **Want automated JIRA updates** (status transitions, time logging, comments)
- **Share work with teammates** and need to export conversation history
- **Use Claude Code regularly** and want better organization
- **Use GitHub or GitLab** and want automated PR/MR creation with AI-filled templates

### ❌ Don't Use This Tool If You...

- **Only work on one task at a time** - native Claude Code is simpler
- **Don't need session isolation** - if mixing contexts doesn't bother you
- **Prefer GUI tools** - this is a CLI-first tool (though it has a TUI for config)
- **Don't use git branches** - the tool assumes branch-per-task workflow

### 🤔 Still Deciding?

Start simple: `daf new --name "test" --goal "Try out the tool"`. You don't need JIRA or any special setup. Create a session, work on it, then decide if the organization helps you.

## The Problem It Solves

When working on multiple tasks or JIRA tickets, you face several challenges:

1. **Context Switching** - Losing mental context when jumping between tasks
2. **Session Confusion** - Mixing work from different tickets in the same Claude session
3. **Lost History** - Difficulty tracking what was done for each ticket
4. **No JIRA Integration** - Manually updating JIRA tickets and tracking time
5. **Poor Organization** - No systematic way to organize Claude sessions

## How It Helps

DevAIFlow provides:

### 🎯 One Session Per Task
- Create isolated Claude Code sessions for each piece of work
- Keep conversations focused and organized
- Resume exactly where you left off

### 🔗 Optional JIRA Integration
- Link sessions to JIRA tickets (or don't - it's optional!)
- Automatic status transitions (New → In Progress → Done)
- Sync assigned tickets to create sessions automatically
- Add session notes as JIRA comments

### ⏱️ Automatic Time Tracking
- Track time spent on each session
- Automatic start/stop when opening/closing Claude Code
- View time reports per session or sprint

### 📝 Session Management
- Organize sessions into groups
- Add progress notes
- Search and filter sessions
- Export sessions for documentation or team sharing

### 🌿 Git Integration
- Auto-create git branches per session
- Checkout the right branch when resuming
- Branch naming based on JIRA keys

### 🧹 Conversation Cleanup
- Manage conversation history to avoid "413 Prompt too long" errors
- Automatic backups before cleanup
- Restore from previous conversation states

## Core Concepts

Understanding the relationship between JIRA tickets, sessions, conversations, and Claude Code is key to using this tool effectively.

### The Hierarchy: JIRA → Session → Conversations → Claude Code

```
┌─────────────────────────────────────────────────────────────────┐
│ JIRA Ticket (PROJ-12345)                                         │
│ "Implement user authentication"                                 │
│                                                                  │
│   ┌─────────────────────────────────────────────────────┐      │
│   │ Session: "PROJ-12345" or "auth-feature"              │      │
│   │ • Metadata (goal, branch, time tracking)            │      │
│   │ • Progress notes                                     │      │
│   │                                                      │      │
│   │   ┌──────────────────────────────────────┐          │      │
│   │   │ Conversation #1: Backend Repo        │          │      │
│   │   │ ~/myorg-management-service    │          │      │
│   │   │                                       │          │      │
│   │   │   ┌──────────────────────────┐       │          │      │
│   │   │   │ Claude Code Session      │       │          │      │
│   │   │   │ UUID: abc-123-def        │       │          │      │
│   │   │   │ File: abc-123-def.jsonl  │       │          │      │
│   │   │   └──────────────────────────┘       │          │      │
│   │   └──────────────────────────────────────┘          │      │
│   │                                                      │      │
│   │   ┌──────────────────────────────────────┐          │      │
│   │   │ Conversation #2: Frontend Repo       │          │      │
│   │   │ ~/myorg-admin-console         │          │      │
│   │   │                                       │          │      │
│   │   │   ┌──────────────────────────┐       │          │      │
│   │   │   │ Claude Code Session      │       │          │      │
│   │   │   │ UUID: xyz-456-ghi        │       │          │      │
│   │   │   │ File: xyz-456-ghi.jsonl  │       │          │      │
│   │   │   └──────────────────────────┘       │          │      │
│   │   └──────────────────────────────────────┘          │      │
│   └─────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### Sessions

A **session** is the core organizational unit - it represents one piece of work:

**What's Included:**
- **Metadata** - Goal, JIRA key, branch name, created date
- **Conversations** - One or more Claude Code conversation UUIDs
- **Time Tracking** - Work sessions with start/stop times
- **Progress Notes** - Local notes, optionally synced to JIRA
- **Git Branch** - Associated branch (auto-created if needed)

**Storage Location:** `~/.daf-sessions/sessions/{session-name}/metadata.json`

### Conversations vs Sessions

**Important Distinction:**

- **Session** = Your organizational wrapper (metadata, notes, time)
- **Conversation** = The actual Claude Code `.jsonl` file with message history

**One Session, Multiple Conversations:**
When working on the same JIRA ticket across multiple repositories, you create one conversation per repository, all linked to the same session.

```
Session "PROJ-12345" contains:
  Conversation 1: Backend work (~/backend/.claude/...abc.jsonl)
  Conversation 2: Frontend work (~/frontend/.claude/...xyz.jsonl)
  Conversation 3: Docs work (~/docs/.claude/...123.jsonl)
```


### Session Lifecycle

```
┌─────────┐      ┌────────────┐      ┌──────────┐
│ Created │ ───> │ In Progress│ ───> │ Complete │
└─────────┘      └────────────┘      └──────────┘
     │                 │                   │
     ▼                 ▼                   ▼
  daf new           daf open             daf complete
  • Set goal       • Launch Claude     • Add summary
  • Link JIRA      • Track time        • Transition JIRA
  • Create branch  • Add notes         • Create PR/MR
                   • Make commits      • Export (optional)
```

**Lifecycle Commands:**

1. **Create** - `daf new` or `daf sync`
   - Initialize session metadata
   - Create git branch (optional)
   - Transition JIRA to "In Progress" (if linked)

2. **Work** - `daf open`
   - Launch Claude Code with conversation
   - Start time tracking
   - Auto-load context (AGENTS.md, CLAUDE.md, JIRA ticket)

3. **Track Progress** - `daf note`, `daf pause`, `daf resume`
   - Add notes (exit Claude Code first)
   - Pause/resume time tracking
   - Optionally sync notes to JIRA comments

4. **Complete** - `daf complete`
   - Mark session as done
   - Generate or add summary
   - Transition JIRA ticket status
   - Optionally create PR/MR
   - Export for team handoff (optional)

## Key Features

### ✅ Implemented Features

**Core Session Management:**
- Create, open, list, delete sessions
- Session groups (multiple sessions per name/JIRA)
- Progress notes with optional JIRA sync
- Session summaries (local stats or AI-powered)
- Search and filter sessions

**JIRA Integration (Optional):**
- Link/unlink JIRA tickets
- Auto-sync assigned tickets
- Auto-transition ticket status
- Add notes as JIRA comments
- Sprint dashboard

**Time Tracking:**
- Automatic tracking on open/close
- Manual pause/resume
- Time reports per session
- Multi-user support

**Git Integration:**
- Auto-create branches
- Branch checkout on resume
- Configurable branch naming
- GitHub PR creation with AI-filled templates
- GitLab MR creation with AI-filled templates
- Automatic PR/MR linking to JIRA tickets

**Export & Backup:**
- Export sessions (always includes conversations + git sync)
- Complete system backup (no git sync)
- Import/restore sessions
- Session templates for reuse

**Conversation Management:**
- Cleanup old messages (avoid 413 errors)
- Automatic backups with retention
- List and restore from backups
- Fix orphaned sessions

### 🚧 Planned Features

- TUI (Terminal UI) mode for interactive management
- Advanced analytics and reporting
- Session archiving with compression
- Team collaboration features

## How This Fits Your Workflow

DevAIFlow integrates with your existing tools without replacing them:

```
Your Workflow              DAF Tool Integration           What It Does
─────────────────────────────────────────────────────────────────────
JIRA Board                 daf sync                       Pull assigned tickets
  │                          │                            Create sessions auto
  │                          ▼
  └──> Ticket PROJ-12345    daf open PROJ-12345             Launch Claude Code
                             │                            Load ticket context
                             ▼                            Start time tracking
       Claude Code         (works normally)              AI pair programming
         │                   │
         ▼                   ▼
       Git commits         daf note "progress"            Track what you did
         │                   │                            (exit Claude first)
         │                   │                            Optional JIRA comment
         ▼                   ▼
       Push branch         daf complete                   Generate summary
         │                   │                            Transition JIRA
         └──────────────────┴───> Create PR/MR           Link PR to ticket
                                   │
                                   ▼
                                 Code Review              Normal git workflow
```

### Integration Points

**1. JIRA (Optional)**
- **Reads:** Ticket summary, description, acceptance criteria
- **Writes:** Status transitions, comments, time logs, PR links
- **When:** On `daf sync`, `daf open`, `daf note --sync`, `daf complete`

**2. Claude Code (Required)**
- **Reads:** Conversation history from `.jsonl` files
- **Writes:** New conversations when you work
- **When:** On `daf open` (launches Claude), conversation export/import

**3. Git (Optional)**
- **Reads:** Current branch, repo status, remote branches
- **Writes:** Creates branches, commits (during `daf complete`)
- **When:** On `daf new`, `daf open`, `daf complete --commit`

**4. GitHub/GitLab (Optional)**
- **Reads:** Existing PRs/MRs for the branch, PR/MR templates from repositories
- **Writes:** Creates PRs/MRs with AI-filled templates, links PRs/MRs to JIRA tickets
- **When:** On `daf complete --create-pr` or `daf complete --create-mr`
- **Features:**
  - Automatic PR/MR creation with template support
  - AI-powered template filling using session context and git changes
  - Automatic JIRA ticket linking in PR/MR description
  - Support for both GitHub (via `gh` CLI) and GitLab (via `glab` CLI)

### What DAF Does NOT Do

To avoid confusion, here's what the tool explicitly does **not** do:

- ❌ **Replace Claude Code** - You still use Claude Code normally, DAF just organizes it
- ❌ **Modify conversations** - It tracks them but doesn't change message content
- ❌ **Manage JIRA tickets** - It updates status/comments but doesn't create/delete tickets
- ❌ **Replace git commands** - You still commit/push normally, DAF just automates branch creation
- ❌ **Lock you in** - Sessions are just JSON metadata, your code/conversations are untouched

## Use Cases

### Personal Development

```bash
# Working on a personal experiment
daf new --name "redis-cache-test" --goal "Test Redis caching approach"
daf open redis-cache-test
# ... work in Claude Code ...
daf complete redis-cache-test
```

### JIRA-Driven Development

```bash
# Start work on a JIRA ticket
daf new --jira PROJ-12345 --goal "Implement backup feature"

# Or sync all assigned tickets
daf sync --sprint current

# Work on the session
daf open PROJ-12345

# Add progress notes
daf note PROJ-12345 "Completed backend API, starting UI"

# Complete and auto-transition JIRA
daf complete PROJ-12345 --status "Code Review"
```

### Multi-Repository Work

```bash
# Create session for backend
cd ~/myorg-management-service
daf new --name "backup" --jira PROJ-12345 --goal "Backend API"

# Add session for frontend (same group name)
cd ~/myorg-admin-console
daf new --name "backup" --jira PROJ-12345 --goal "UI components"

# Add session for infrastructure
cd ~/myorg-sops
daf new --name "backup" --jira PROJ-12345 --goal "S3 bucket config"

# Open specific session
daf open backup
# Prompts to select: #1 (backend), #2 (frontend), or #3 (infra)
```

### Team Collaboration

```bash
# Export session for teammate (always includes conversations and git sync)
daf export PROJ-12345 --output ~/handoff.tar.gz

# Teammate imports
daf import ~/handoff.tar.gz

# They can now see full context and continue work
daf open PROJ-12345
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CLI Interface (daf)                 │
│                     Click Framework                     │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼──────┐  ┌────────▼────────┐
│    Session     │  │    JIRA     │  │   Git Utils     │
│    Manager     │  │  Integration │  │                 │
│                │  │              │  │                 │
│ • CRUD ops     │  │ • Sync       │  │ • Branch ops    │
│ • Time track   │  │ • Transitions│  │ • Repo detect   │
│ • Notes        │  │ • Comments   │  │                 │
└────────────────┘  └──────────────┘  └─────────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼──────┐  ┌────────▼────────┐
│   Local        │  │   Claude    │  │  JIRA CLI       │
│   Storage      │  │   Code      │  │  (optional)     │
│                │  │             │  │                 │
│ ~/.claude-     │  │ • Launch    │  │ • Ticket ops    │
│  sessions/     │  │ • Resume    │  │ • Status sync   │
│                │  │ • Capture   │  │                 │
└────────────────┘  └─────────────┘  └─────────────────┘
```

## Data Storage

All session data is stored locally in `~/.daf-sessions/`:

```
~/.daf-sessions/
├── config.json              # Configuration
├── sessions.json            # Session index
├── sessions/                # Per-session data
│   └── {SESSION-NAME}/
│       ├── metadata.json    # Session details
│       ├── notes.md         # Progress notes
│       └── memory.md        # Context hints
└── backups/                 # Conversation backups
    └── {SESSION-UUID}/
        ├── 20251120-140000.jsonl
        └── 20251120-150000.jsonl
```

Claude Code's conversation files remain in their original location:
```
~/.claude/projects/{encoded-path}/{session-uuid}.jsonl
```

## Why Use This Tool?

### ✅ Better Organization
- Stop mixing work from different tickets
- Find sessions easily by name or JIRA key
- See what you worked on and when

### ✅ Save Time
- Auto-create git branches
- Auto-transition JIRA tickets
- Auto-track time spent
- Resume with full context

### ✅ Team Benefits
- Export sessions for handoffs
- Share templates for common setups
- Track time for sprint planning
- Document work with session summaries

### ✅ Flexibility
- Works with or without JIRA
- Use as much or as little as you need
- Doesn't lock you in - sessions are just metadata

## Next Steps

- [Installation Guide](02-installation.md) - Set up the tool
- [Quick Start](03-quick-start.md) - Create your first session
- [Commands Reference](07-commands.md) - Learn all available commands
