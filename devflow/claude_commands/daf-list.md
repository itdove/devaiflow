---
name: daf-list
description: List all DevAIFlow sessions
---

List all daf sessions with their status and time tracking.

This helps you see all available sessions, their JIRA associations, working directories, and time spent.

```bash
daf list --active
```

**Common options:**
- `--active` - Show only active sessions
- `--status in_progress` - Filter by session status
- `--field <field_name>=<value>` - Filter by custom field name (e.g., `--field my_field=value`)
  - Uses field names from organization.json field_mappings configuration
  - Example: `--field grouping_field="Group A"`
- `--working-directory <dir>` - Filter by repository
- `--since "last week"` - Sessions active since time

**Example output:**
```
Your Sessions
┏━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━┓
┃ Status ┃ Name        ┃ JIRA    ┃ Summary          ┃ Working Dir┃ Time ┃
┡━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━┩
│ Active │ PROJ-12345   │ PROJ... │ Backup feature   │ backend    │ 5h   │
│ Paused │ PROJ-12346   │ PROJ... │ Login bug        │ frontend   │ 1h   │
└────────┴─────────────┴─────────┴──────────────────┴────────────┴──────┘

Total: 2 sessions | 6h tracked
```

**What it shows:**
- Session status (Active, Paused, Complete)
- Session name or JIRA key
- Summary/goal
- Working directory (repository)
- Time tracked

**Use this to:**
- Check which sessions are active
- Find a session to resume with `daf open`
- See time spent on each task
- Filter sessions by sprint or repository
