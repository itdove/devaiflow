# DevAIFlow Quick Reference

Single-page reference for all essential commands.

## Setup & Installation

```bash
# One-time setup
pip install devaiflow                   # Install devaiflow
daf init                                # Interactive configuration wizard
daf upgrade                             # Install Claude Code skills & commands

# Authentication (if using issue trackers)
gh auth login                           # GitHub CLI
glab auth login                         # GitLab CLI
# JIRA: Set environment variables (see Installation Guide)
```

## Creating Tickets/Issues

```bash
# Analyze codebase, THEN create ticket (recommended)
daf jira new <type> --parent <key> --goal "..."   # JIRA
daf git new --goal "..."                          # GitHub/GitLab

# Create directly (without analysis)
daf jira create <type> --summary "..." --parent <key>  # JIRA
daf git create --summary "..." --description "..."     # GitHub/GitLab
```

## Syncing Tickets/Issues

```bash
# Smart sync (JIRA or GitHub/GitLab based on config)
daf sync                                    # Sync assigned tickets/issues
daf sync --workspace <name>                 # Sync specific workspace
daf sync --sprint current                   # Sync current sprint (JIRA only)

# Filters
daf sync --type Story                       # Filter by type
daf sync --field workstream="Platform"      # Filter by custom field
daf sync --epic PROJ-12345                  # Filter by epic
```

## Working on Sessions

```bash
# Session lifecycle
daf open <session>                          # Start work (launches Claude)
daf complete <session>                      # Finish (commits, PR/MR, transitions)
daf pause <session>                         # Pause session (stop time tracking)
daf resume <session>                        # Resume paused session
daf delete <session>                        # Delete session

# Finding & monitoring
daf list                                    # List all sessions
daf list --active                           # Active sessions only
daf search <keyword>                        # Search sessions by keyword
daf status                                  # Sprint dashboard
daf active                                  # Currently active conversation

# Manual linking (if needed)
daf link <session> --jira PROJ-123          # Link existing session to JIRA
daf unlink <session>                        # Remove JIRA link
```

## Multi-Project Sessions

```bash
# Declarative (all at once)
daf new <session> -w <workspace> --projects repo1,repo2,repo3

# Iterative (add as you go)
daf open <session>                          # Pick project each time
# Select "Create new conversation (in a different project)"
```

## Progress Tracking

```bash
# Notes
daf note <session> "Progress update"       # Add local note
daf notes <session>                         # View all notes

# JIRA/GitHub integration
daf jira view <key>                         # View JIRA ticket
daf jira add-comment <key> "Update"         # Add JIRA comment
daf git view "owner/repo#123"               # View GitHub issue (quotes required!)
daf git add-comment "owner/repo#123" "..."  # Add GitHub comment (quotes required!)

# Session info
daf summary <session>                       # View session summary
daf time <session>                          # View time spent
daf info <session>                          # Detailed session info
```

## Workspace Management

```bash
daf workspace list                          # List workspaces
daf workspace add <name> <path>             # Add workspace
daf workspace set-default <name>            # Set default workspace
```

## Alternative Model Providers

```bash
# Configure alternative AI models (save 98% on costs or run offline)
daf config edit                          # Interactive config editor
# See docs/alternative-model-providers.md for:
# - llama.cpp (local models, 100% offline)
# - OpenRouter (cloud models, 98% cheaper)
# - Vertex AI, Minimax, and more
```

## Maintenance

```bash
# Cleanup
daf cleanup-conversation <session> --older-than 8h  # Remove old messages
daf cleanup-sessions                                # Fix orphaned sessions

# Backup
daf export <session> --output session.tar.gz        # Export session
daf export --all --output backup.tar.gz             # Export all sessions

# Templates
daf template save <session> <name>                  # Save as template
daf new --template <name> --goal "..."              # Use template
```

## Essential Options

```bash
-w, --workspace <name>      # Select workspace
--dry-run                   # Preview without executing
--json                      # JSON output
--help                      # Show help
```

## Quick Tips

**Session Names:**
- JIRA: Use ticket key (e.g., `PROJ-12345`)
- GitHub: Use session name (e.g., `owner-repo-123`) - NO QUOTES
- GitHub issue keys: Always quote `"owner/repo#123"` (# starts comments in bash)

**Multi-Project:**
- Declarative = faster setup, all repos at once
- Iterative = discover repos as you work

**Notes:**
- Add notes frequently to track progress
- `daf note` works inside Claude Code sessions now!

---

**Full Documentation:** See [docs/](docs/) for detailed guides
