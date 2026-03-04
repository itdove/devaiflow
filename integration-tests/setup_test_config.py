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
    """Create minimal test configuration using new format (5 separate files)."""
    # Get DEVAIFLOW_HOME from environment
    devaiflow_home = os.environ.get('DEVAIFLOW_HOME')
    if not devaiflow_home:
        print("Error: DEVAIFLOW_HOME environment variable not set", file=sys.stderr)
        sys.exit(1)

    config_dir = Path(devaiflow_home)
    config_dir.mkdir(parents=True, exist_ok=True)

    # Detect mock mode from environment
    is_mock_mode = os.environ.get('DAF_MOCK_MODE') == '1'

    # 1. User config (config.json)
    user_config = {
        "backend_config_source": "local",
        "repos": {
            "workspaces": [
                {
                    "name": "primary",
                    "path": str(Path.cwd())
                }
            ],
            "last_used_workspace": "primary",
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
        "update_checker_timeout": 10
    }

    # 2. Backend config (backends/jira.json) - API metadata only
    backend_config = {
        "url": "https://mock-jira.example.com",
        "field_mappings": None,
        "field_cache_timestamp": None,
        "field_cache_auto_refresh": True,
        "field_cache_max_age_hours": 24
    }

    # 3. Organization config (organization.json) - Workflow policies
    org_config = {
        "jira_project": "PROJ",
        "transitions": {},  # Minimal transitions for tests
        "parent_field_mapping": {
            "bug": "epic_link",
            "story": "epic_link",
            "task": "epic_link",
            "spike": "epic_link",
            "epic": "epic_link",
            "sub-task": "parent"
        },
        "sync_filters": {
            "sync": {
                "status": ["To Do", "In Progress"],
                "required_fields": [],
                "assignee": "currentUser()"
            }
        }
    }

    # 4. Team config (team.json)
    team_config = {
        "time_tracking_enabled": True
    }

    # 5. Enterprise config (enterprise.json)
    enterprise_config = {
        "agent_backend": "claude"
    }

    # Write all config files
    try:
        # User config
        config_path = config_dir / 'config.json'
        with open(config_path, 'w') as f:
            json.dump(user_config, f, indent=2)
        print(f"✓ Created user configuration at {config_path}")

        # Backend config
        backends_dir = config_dir / 'backends'
        backends_dir.mkdir(exist_ok=True)
        backend_path = backends_dir / 'jira.json'
        with open(backend_path, 'w') as f:
            json.dump(backend_config, f, indent=2)
        print(f"✓ Created backend configuration at {backend_path}")

        # Organization config
        org_path = config_dir / 'organization.json'
        with open(org_path, 'w') as f:
            json.dump(org_config, f, indent=2)
        print(f"✓ Created organization configuration at {org_path}")

        # Team config
        team_path = config_dir / 'team.json'
        with open(team_path, 'w') as f:
            json.dump(team_config, f, indent=2)
        print(f"✓ Created team configuration at {team_path}")

        # Enterprise config
        enterprise_path = config_dir / 'enterprise.json'
        with open(enterprise_path, 'w') as f:
            json.dump(enterprise_config, f, indent=2)
        print(f"✓ Created enterprise configuration at {enterprise_path}")

        return 0
    except Exception as e:
        print(f"Error writing config files: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(create_test_config())
