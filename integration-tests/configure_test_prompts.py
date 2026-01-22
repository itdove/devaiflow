#!/usr/bin/env python3
"""Configure prompt settings for integration tests.

This script modifies the config.json in DEVAIFLOW_HOME to set all auto_* prompt
settings to non-interactive values, preventing tests from hanging on user input.

Usage:
    python configure_test_prompts.py

Environment:
    DEVAIFLOW_HOME: Path to DAF configuration directory (defaults to ~/.daf-sessions)
"""

import json
import os
import sys
from pathlib import Path


def configure_test_prompts():
    """Configure prompt settings for non-interactive testing."""
    # Get DEVAIFLOW_HOME from environment or use default
    devaiflow_home = os.environ.get('DEVAIFLOW_HOME')
    if not devaiflow_home:
        devaiflow_home = str(Path.home() / '.daf-sessions')

    config_path = Path(devaiflow_home) / 'config.json'

    # Check if config exists
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}", file=sys.stderr)
        print("Run 'daf init' first to create the configuration", file=sys.stderr)
        sys.exit(1)

    # Load current config
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error reading config file: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure prompts section exists
    if 'prompts' not in config:
        config['prompts'] = {}

    # Configure all auto_* settings for non-interactive testing
    config['prompts']['auto_launch_agent'] = False  # Don't launch AI agent during tests
    config['prompts']['auto_commit_on_complete'] = False  # Don't auto-commit (tests use --no-commit)
    config['prompts']['auto_accept_ai_commit_message'] = True  # If commit happens, don't prompt
    config['prompts']['auto_create_pr_on_complete'] = False  # Don't create PR (tests use --no-pr)
    config['prompts']['auto_add_issue_summary'] = False  # Don't prompt for issue summary
    config['prompts']['auto_update_jira_pr_url'] = False  # Don't prompt for JIRA PR URL update
    config['prompts']['auto_push_to_remote'] = False  # Don't push to remote
    config['prompts']['auto_checkout_branch'] = True  # Auto-checkout branches (no prompt)
    config['prompts']['auto_sync_with_base'] = 'never'  # Never sync with base (no prompt)
    config['prompts']['auto_complete_on_exit'] = False  # Don't auto-complete on exit
    config['prompts']['auto_create_pr_status'] = 'draft'  # Use draft status (no prompt)
    config['prompts']['show_prompt_unit_tests'] = False  # Don't show testing instructions
    config['prompts']['auto_load_related_conversations'] = False  # Don't prompt to load conversations

    # Save updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Configured non-interactive prompt settings in {config_path}")
        return 0
    except Exception as e:
        print(f"Error saving config file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(configure_test_prompts())
