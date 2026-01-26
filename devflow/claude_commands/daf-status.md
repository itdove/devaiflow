---
description: Show status and progress dashboard
---

Display progress, ticket status breakdown, and time tracking summary.

```bash
daf status
```

**What it shows:**

**Overview** (when grouping configured):
- Grouping information (configured via organization.json)
- Totals breakdown if configured (configured via organization.json)
- Total time tracked
- Progress metrics

**Tickets by Status:**
- In Progress: Active tickets being worked on
- Paused: Temporarily stopped tickets
- Created: New tickets not yet started
- Complete: Finished tickets

**Example output (with grouping configured):**
```
Group: Value-A
Progress: 8/26 (totals field)

In Progress:
  🐛 PROJ-12345 (PROJ-12345)  Fix password reset  | 1h 20m
     └─ backend-api | Last: 2025-01-25 14:30

  📋 PROJ-12346 (PROJ-12346)  Add 2FA support  | 2h 15m
     └─ frontend | Last: 2025-01-25 15:00

Complete:
  📋 PROJ-12343 (PROJ-12343)  Login endpoint  | 2h 30m
     └─ backend-api | Last: 2025-01-24 16:00

Summary
  Total sessions: 3
  In progress: 2
  Complete: 1
  Total time tracked: 6h 5m
```

**Use this to:**
- Check progress at a glance
- See which tickets need attention
- Track time spent
- Report status in standups
- Plan daily work priorities

**Filter sessions by custom fields:**
```bash
daf list --field <field_name>=<value>        # Filter by custom field name
daf list --field grouping_field="Value A"    # Uses field name from field_mappings
daf list --field status_field="In Progress"  # Field names configured in organization.json
```

**Note:** Custom field names must be defined in your organization.json `field_mappings` configuration.

**Related commands:**
```bash
daf sync --field <field_name>=<value>   # Sync tickets (field name from field_mappings)
daf list --active                       # List only active sessions
daf time PROJ-12345                     # Detailed time tracking for ticket
```
