"""Tests for daf link and unlink commands with JIRA validation."""

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader


def test_link_jira_to_session_success(mock_jira_cli, temp_daf_home):
    """Test linking a issue tracker ticket to an existing session."""
    # Setup: Configure a mock issue tracker ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Implement backup feature",
            "status": {"name": "New"},
        }
    })

    runner = CliRunner()

    # Step 1: Create a session without JIRA
    result = runner.invoke(cli, [
        "new",
        "--name", "backup-feature",
        "--goal", "Implement backup",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude
    assert result.exit_code == 0

    # Step 2: Link issue tracker ticket to the session
    result = runner.invoke(cli, [
        "link",
        "backup-feature",
        "--jira", "PROJ-12345"
    ])

    # Verify: Command succeeded
    assert result.exit_code == 0
    assert "Linked" in result.output or "linked" in result.output
    assert "PROJ-12345" in result.output

    # Verify: Session now has issue key
    config_loader = ConfigLoader()
    sessions_index = config_loader.load_sessions()
    sessions = sessions_index.get_sessions("backup-feature")
    assert sessions is not None
    assert len(sessions) > 0
    assert sessions[0].issue_key == "PROJ-12345"


def test_link_invalid_jira_fails(mock_jira_cli, temp_daf_home):
    """Test linking an invalid issue tracker ticket fails."""
    runner = CliRunner()

    # Step 1: Create a session without JIRA
    result = runner.invoke(cli, [
        "new",
        "--name", "test-session",
        "--goal", "Testing",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude
    assert result.exit_code == 0

    # Step 2: Try to link non-existent issue tracker ticket
    result = runner.invoke(cli, [
        "link",
        "test-session",
        "--jira", "PROJ-99999"
    ])

    # Verify: Command failed
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_unlink_jira_from_session(mock_jira_cli, temp_daf_home):
    """Test unlinking JIRA from a session."""
    # Setup: Configure a mock issue tracker ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test"}
    })

    runner = CliRunner()

    # Step 1: Create session with JIRA
    result = runner.invoke(cli, [
        "new",
        "--name", "test-session",
        "--goal", "Testing",
        "--jira", "PROJ-12345",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude
    assert result.exit_code == 0

    # Step 2: Unlink issue tracker
    result = runner.invoke(cli, [
        "unlink",
        "test-session"
    ], input="y\n")  # Confirm unlink

    # Verify: Command succeeded
    assert result.exit_code == 0

    # Verify: Session no longer has issue key
    config_loader = ConfigLoader()
    sessions_index = config_loader.load_sessions()
    sessions = sessions_index.get_sessions("test-session")
    assert sessions is not None
    assert len(sessions) > 0
    assert sessions[0].issue_key is None


def test_link_updates_all_sessions_in_group(mock_jira_cli, temp_daf_home):
    """Test that linking JIRA updates the session."""
    # Setup: Configure a mock issue tracker ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Multi-project feature"}
    })

    runner = CliRunner()

    # Step 1: Create session
    result = runner.invoke(cli, [
        "new",
        "--name", "multi-project",
        "--goal", "Backend work",
        "--path", str(temp_daf_home / "backend")
    ], input="y\nn\n")  # Accept session creation, don't launch Claude
    assert result.exit_code == 0

    # Step 2: Link issue tracker to the session
    result = runner.invoke(cli, [
        "link",
        "multi-project",
        "--jira", "PROJ-12345"
    ])
    assert result.exit_code == 0

    # Verify: Session has issue key
    config_loader = ConfigLoader()
    sessions_index = config_loader.load_sessions()
    sessions = sessions_index.get_sessions("multi-project")
    assert len(sessions) == 1
    assert sessions[0].issue_key == "PROJ-12345"


def test_link_updates_goal_with_issue_info(mock_jira_cli, temp_daf_home):
    """Test that linking JIRA updates the goal field with concatenated issue key and title (PROJ-59070)."""
    # Setup: Configure a mock issue tracker ticket
    mock_jira_cli.set_ticket("PROJ-59070", {
        "key": "PROJ-59070",
        "fields": {
            "summary": "Store concatenated goal in session.goal field",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
        }
    })

    runner = CliRunner()

    # Step 1: Create a session without JIRA
    result = runner.invoke(cli, [
        "new",
        "--name", "goal-feature",
        "--goal", "Implement goal concatenation",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude
    assert result.exit_code == 0

    # Verify initial goal (no JIRA)
    config_loader = ConfigLoader()
    sessions_index = config_loader.load_sessions()
    sessions = sessions_index.get_sessions("goal-feature")
    assert sessions[0].goal == "Implement goal concatenation"
    assert sessions[0].issue_key is None

    # Step 2: Link issue tracker ticket to the session
    result = runner.invoke(cli, [
        "link",
        "goal-feature",
        "--jira", "PROJ-59070"
    ])
    assert result.exit_code == 0

    # Verify: Goal is now concatenated with issue key and title
    config_loader = ConfigLoader()
    sessions_index = config_loader.load_sessions()
    sessions = sessions_index.get_sessions("goal-feature")
    assert sessions is not None
    assert len(sessions) > 0
    assert sessions[0].issue_key == "PROJ-59070"
    # Goal should be updated to: "{ISSUE_KEY}: {JIRA_TITLE}"
    assert sessions[0].goal == "PROJ-59070: Store concatenated goal in session.goal field"
