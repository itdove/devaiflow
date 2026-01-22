#!/usr/bin/env python3
"""Create a minimal test configuration for integration tests.

This script creates a config.json with all necessary settings for non-interactive testing,
avoiding the need to run `daf init` which requires user input.

Usage:
    python setup_test_config.py

Environment:
    DEVAIFLOW_HOME: Path to DAF configuration directory (required)
"""

import json
import os
import sys
from pathlib import Path


def create_test_config():
    """Create minimal test configuration."""
    # Get DEVAIFLOW_HOME from environment
    devaiflow_home = os.environ.get('DEVAIFLOW_HOME')
    if not devaiflow_home:
        print("Error: DEVAIFLOW_HOME environment variable not set", file=sys.stderr)
        sys.exit(1)

    config_dir = Path(devaiflow_home)
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / 'config.json'

    # Minimal configuration for testing
    config = {
        "jira": {
            "url": "https://mock-jira.example.com",
            "user": "test-user",
            "project": "PROJ",  # Set project to avoid warnings in mock mode
            "transitions": {},
            "time_tracking": True,
            "filters": {}
        },
        "repos": {
            "workspace": str(Path.cwd()),  # Use current directory as workspace
            "detection": {
                "method": "keyword_match",
                "fallback": "prompt"
            },
            "keywords": {}
        },
        "prompts": {
            "auto_launch_agent": False,  # Don't launch AI agent during tests
            "auto_commit_on_complete": False,  # Don't auto-commit
            "auto_accept_ai_commit_message": True,  # Don't prompt for commit message
            "auto_create_pr_on_complete": False,  # Don't create PR
            "auto_add_issue_summary": False,  # Don't prompt for issue summary
            "auto_update_jira_pr_url": False,  # Don't prompt for JIRA PR URL
            "auto_push_to_remote": False,  # Don't push to remote
            "auto_checkout_branch": True,  # Auto-checkout branches without prompting
            "auto_sync_with_base": "never",  # Never sync without prompting
            "auto_complete_on_exit": False,  # Don't auto-complete on exit
            "auto_create_pr_status": "draft",  # Use draft status
            "show_prompt_unit_tests": False,  # Don't show testing instructions
            "auto_load_related_conversations": False  # Don't prompt to load conversations
        },
        "time_tracking": {
            "auto_start": True,
            "auto_pause_after": "30m",
            "reminder_interval": "2h"
        },
        "session_summary": {
            "mode": "local",
            "api_key_env": "ANTHROPIC_API_KEY"
        },
        "templates": {
            "auto_create": True,
            "auto_use": True
        },
        "context_files": {
            "files": []
        },
        "storage": {
            "backend": "file"
        },
        "backend_config_source": "local",
        "issue_tracker_backend": "jira",
        "agent_backend": "claude",
        "update_checker_timeout": 10
    }

    # Write config file
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Created test configuration at {config_path}")
        return 0
    except Exception as e:
        print(f"Error writing config file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(create_test_config())
