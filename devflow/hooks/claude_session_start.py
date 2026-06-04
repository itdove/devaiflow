#!/usr/bin/env python3
"""Claude Code SessionStart hook for DevAIFlow.

Checks DAF_SESSION_NAME env var. If set, injects instruction to follow
daf-workflow skill. If not set, exits silently (no-op).

Installed to: ~/.claude/hooks/daf-session-start.py
Triggered by: SessionStart hook in ~/.claude/settings.json
"""

import os
import sys


def main():
    session_name = os.environ.get("DAF_SESSION_NAME")
    if not session_name:
        sys.exit(0)

    command = os.environ.get("DAF_COMMAND", "unknown")
    print(
        f"DevAIFlow session active (session: {session_name}, command: {command}). "
        "Follow the daf-workflow skill Session Initialization instructions."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
