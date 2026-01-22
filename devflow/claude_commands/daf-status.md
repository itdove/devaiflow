---
description: Show sprint status and progress dashboard
---

Display sprint progress, ticket status breakdown, and time tracking summary.

```bash
daf status
```

**What it shows:**

**Sprint Overview:**
- Current sprint name
- Story points breakdown (completed/in progress/remaining)
- Total time spent this sprint
- Estimated remaining time

**Tickets by Status:**
- In Progress: Active tickets being worked on
- Ready to Start: Assigned tickets not yet started
- Code Review: Tickets awaiting review
- Done: Completed tickets this sprint

**Example output:**
```
Current Sprint: 2025-01

In Progress:
🚧 PROJ-12345  Customer backup          5 pts | 5h 45m | 75%
🚧 PROJ-12346  Fix password reset       3 pts | 1h 20m | 40%

Ready to Start:
🆕 PROJ-12347  Add 2FA support          8 pts | 0h     | 0%

Code Review:
✅ PROJ-12344  User profile API         5 pts | 4h 10m | 100%

Done:
✓ PROJ-12343  Login endpoint           3 pts | 2h 30m | 100%

Sprint Progress:
  Completed: 8 pts (30%)
  In Progress: 8 pts (30%)
  Remaining: 10 pts (40%)
  Total: 26 pts

Time Spent: 13h 45m
```

**Use this to:**
- Check sprint progress at a glance
- See which tickets need attention
- Track time spent vs remaining work
- Report status in standups
- Plan daily work priorities

**Filter by sprint:**
```bash
daf status                    # Current sprint (default)
daf list --sprint "2025-01"   # Specific sprint
daf list --sprint current     # Explicit current sprint
```

**Related commands:**
```bash
daf sync --sprint current     # Sync current sprint tickets
daf list --active             # List only active sessions
daf time PROJ-12345            # Detailed time tracking for ticket
```
