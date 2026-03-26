# DevAIFlow - AI-Optimized Summary

Comprehensive overview for AI tools (NotebookLM, Claude, etc.) to understand DevAIFlow capabilities.

## What is DevAIFlow?

Session management tool for AI coding assistants with optional JIRA/GitHub/GitLab integration. Organizes development work, tracks time, and coordinates multi-repository projects.

**Core Value:** Bridges issue trackers and AI-assisted development with context management, time tracking, and workflow automation.

## Key Capabilities

1. **Session Management** - Organize AI sessions with goals, time tracking, progress notes
2. **Multi-AI Assistant Support** - Claude Code (fully tested), GitHub Copilot, Cursor, Windsurf (experimental)
3. **Alternative Model Providers** - Run with local models (llama.cpp) or cloud providers (OpenRouter, Vertex AI) - save up to 98% on costs or run offline
4. **Issue Tracker Integration** - JIRA, GitHub Issues, GitLab Issues (or none)
5. **Multi-Repository Support** - Work across repos with shared AI context
6. **Automatic Time Tracking** - Per session/ticket tracking
7. **Team Collaboration** - Export/import sessions for handoffs
8. **Workflow Automation** - Auto commits, PR/MR creation, ticket transitions

## Core Concepts

**Session:** Focused work on one task (one JIRA ticket/GitHub issue)
- Unique name/ID, time tracking, progress notes
- Can span multiple repositories (multi-project)
- States: created → in_progress → complete

**Conversation:** Claude Code conversation within a session
- Multi-project: ONE conversation with SHARED CONTEXT across all projects
- Legacy: Separate conversations per repository
- Each has own git branch

**Workspace:** Named directory for repositories (enables concurrent multi-branch development)

## Three Essential Workflows

### 1. Create Tickets with Analysis (New Work)

**JIRA:**
```bash
daf jira new story --parent PROJ-123 --goal "Add feature X"
# Claude analyzes codebase (read-only), creates informed ticket
daf complete <session>
daf open PROJ-12345
```

**GitHub/GitLab:**
```bash
daf git new --goal "Add feature X"
# Claude analyzes, creates issue
daf complete <session>
daf open owner-repo-123
```

### 2. Sync Existing Tickets (Assigned Work)

**JIRA:**
```bash
daf sync --sprint current
daf open PROJ-12345
daf complete PROJ-12345
```

**GitHub/GitLab:**
```bash
daf sync
daf open owner-repo-123
daf complete owner-repo-123
```

### 3. Multi-Project Development

**Declarative:**
```bash
daf new PROJ-123 --projects backend-api,frontend-app,shared-lib
# ONE conversation with SHARED CONTEXT across all 3 projects
daf complete PROJ-123  # Creates 3 PRs
```

**Iterative:**
```bash
daf open PROJ-123    # Select backend-api
daf open PROJ-123    # Add frontend-app
daf complete PROJ-123  # Creates 2 PRs
```

## Essential Commands

### Session
```bash
daf new --name "..." --goal "..."
daf open <session>
daf complete <session>
daf list / daf list --active
daf status
```

### Ticket Creation
```bash
daf jira new <type> --parent <key> --goal "..."
daf git new --goal "..."
daf jira create <type> --summary "..." --parent <key>
daf git create --summary "..."
```

### Sync
```bash
daf sync
daf sync --workspace <name>
daf sync --sprint current
daf sync --type Story
```

### Progress
```bash
daf note <session> "Update"
daf notes <session>
daf summary <session>
daf time <session>
```

### Issue Tracker
```bash
daf jira view <key>
daf jira add-comment <key> "..."
daf git view "owner/repo#123"
daf git add-comment "owner/repo#123" "..."
```

### Maintenance
```bash
daf maintenance cleanup-conversation <session> --older-than 8h
daf export <session> --output file.tar.gz
daf import file.tar.gz
daf template save <session> <name>
```

## Architecture

**Single-Session:**
```
Session: PROJ-12345
└── Conversation (backend-api)
    ├── Git branch
    ├── Claude session
    └── Time tracking
```

**Multi-Project:**
```
Session: PROJ-12345
└── Conversation (SHARED CONTEXT)
    ├── backend-api (branch)
    ├── frontend-app (branch)
    ├── shared-lib (branch)
    └── Unified time tracking
```

## Issue Tracker Support

| Backend | CLI | Features |
|---------|-----|----------|
| JIRA | JIRA CLI/API | Workflow automation, custom fields, sprints |
| GitHub | `gh` | Issue sync, PR creation, comments |
| GitLab | `glab` | Issue sync, MR creation, comments |
| None | - | Local session management |

## Key Features

### Codebase Analysis Before Tickets
Claude analyzes code BEFORE creating tickets → better descriptions and acceptance criteria

### Multi-Project Shared Context
ONE conversation across all repos → Claude coordinates changes (not separate conversations)

### Concurrent Development
Different workspaces = same project, different branches, no conflicts

### Session Templates
```bash
daf template save PROJ-12345 backend-api
daf new --template backend-api --goal "..."
```

### Team Handoffs
```bash
daf export PROJ-12345 --output handoff.tar.gz
daf import handoff.tar.gz
```

## Use Cases

1. Sprint work with JIRA (sync tickets, track time, auto PR/status)
2. Open source GitHub (sync issues, multi-repo changes, create PRs)
3. Multi-repo features (backend + frontend in one session)
4. Personal projects (no issue tracker, just sessions)
5. Team handoffs (export/import with full context)
6. Code investigations (analyze before creating tickets)

## Comparison: Traditional vs DevAIFlow

**Traditional:**
1. Create ticket (no code context)
2. Open IDE, read code
3. Code
4. Manual time tracking
5. Create PR
6. Update ticket

**DevAIFlow:**
1. `daf jira new` → Claude analyzes, creates informed ticket
2. `daf open` → Start with full context
3. Auto time tracking
4. `daf complete` → Commits, PR, ticket update auto

## Important Notes

**Session Naming:**
- JIRA: `PROJ-12345`
- GitHub session: `owner-repo-123` (no quotes)
- GitHub issue key: `"owner/repo#123"` (quotes required, # starts comments in bash)

**Multi-Project:**
- Declarative (`--projects`): Faster, all at once
- Iterative (multiple opens): Flexible, discover as you go

**Configuration:**
```
$DEVAIFLOW_HOME/
├── config.json
├── backends/jira.json
├── organization.json
├── team.json
└── sessions/<session-name>/
```

## Alternative Model Providers

DevAIFlow supports running Claude Code with alternative AI models for cost savings or offline use:

**Local Models (100% offline):**
- llama.cpp - Run models completely locally, no internet required
- LM Studio - Alternative local model runner

**Cloud Providers (98% cheaper):**
- OpenRouter - Access multiple models at lower cost
- Vertex AI - Google Cloud AI models
- Minimax - Chinese market AI provider

**Configuration:** Use `daf config edit` to configure model provider profiles. See [docs/alternative-model-providers.md](reference/alternative-model-providers.md) for setup instructions.

**⚠️ Note:** Ollama is NOT compatible with Claude Code. Use llama.cpp instead.

## Quick Links

- [QUICKREF.md](../QUICKREF.md) - Command reference
- [WORKFLOWS.md](workflows/WORKFLOWS.md) - Complete workflows
- [docs/03-quick-start.md](getting-started/quick-start.md) - Getting started
- [docs/alternative-model-providers.md](reference/alternative-model-providers.md) - Alternative AI models
- [docs/ai-agent-support-matrix.md](reference/ai-agent-support-matrix.md) - AI assistant compatibility
- [docs/07-commands.md](reference/commands.md) - Full documentation
