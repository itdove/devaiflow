---
name: daf-workspace
description: List configured workspaces for multi-branch development
---

View all configured workspaces and their paths.

Workspaces enable concurrent multi-branch development by organizing repositories into named locations (like VSCode workspaces). Each workspace can have active sessions without conflicts.

```bash
daf workspace list
```

**Example output:**
```
                Configured Workspaces
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Name        ┃ Path                        ┃ Default ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ primary     │ /Users/john/development     │ ✓       │
│ product-a   │ /Users/john/repos/product-a │         │
│ feat-cache  │ /Users/john/work/caching    │         │
└─────────────┴─────────────────────────────┴─────────┘
```

**What it shows:**
- Workspace name (used with --workspace flag)
- Full path to workspace directory
- Default workspace marker (✓)

**Understanding workspaces:**
- The default workspace is used when no --workspace flag is provided
- Sessions remember their workspace for automatic reuse
- You can work on the same project in different workspaces simultaneously
- Each workspace can have one active session per project

**Use this to:**
- See available workspaces before creating a session
- Check which workspace is set as default
- Verify workspace paths are correct
- Find workspace names to use with `--workspace` flag

**Note:** This is a READ-ONLY command showing configured workspaces. Workspace configuration is managed outside Claude Code sessions.
