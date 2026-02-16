"""Tests for daf link and unlink commands with JIRA validation."""

import json
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


def test_link_with_force_flag(mock_jira_cli, temp_daf_home):
    """Test linking with --force flag skips confirmation."""
    # Setup tickets
    mock_jira_cli.set_ticket("PROJ-111", {"key": "PROJ-111", "fields": {"summary": "Original"}})
    mock_jira_cli.set_ticket("PROJ-222", {"key": "PROJ-222", "fields": {"summary": "Replacement"}})

    runner = CliRunner()

    # Create session with JIRA
    result = runner.invoke(cli, ["new", "--name", "test", "--goal", "Test", "--jira", "PROJ-111", "--path", str(temp_daf_home / "project")], input="n\n")
    assert result.exit_code == 0

    # Replace with --force (no confirmation prompt)
    result = runner.invoke(cli, ["link", "test", "--jira", "PROJ-222", "--force"])

    assert result.exit_code == 0
    # Should not prompt for confirmation
    assert "?" not in result.output

    # Verify replacement
    config_loader = ConfigLoader()
    sessions = config_loader.load_sessions().get_sessions("test")
    assert sessions[0].issue_key == "PROJ-222"


def test_link_replace_existing_jira_confirmed(mock_jira_cli, temp_daf_home):
    """Test replacing existing JIRA link with confirmation."""
    mock_jira_cli.set_ticket("PROJ-111", {"key": "PROJ-111", "fields": {"summary": "Original"}})
    mock_jira_cli.set_ticket("PROJ-222", {"key": "PROJ-222", "fields": {"summary": "Replacement"}})

    runner = CliRunner()

    # Create session with JIRA
    result = runner.invoke(cli, ["new", "--name", "test", "--goal", "Test", "--jira", "PROJ-111", "--path", str(temp_daf_home / "project")], input="n\n")
    assert result.exit_code == 0

    # Replace with confirmation
    result = runner.invoke(cli, ["link", "test", "--jira", "PROJ-222"], input="y\n")

    assert result.exit_code == 0
    assert "Replace" in result.output or "replace" in result.output

    # Verify replacement
    config_loader = ConfigLoader()
    sessions = config_loader.load_sessions().get_sessions("test")
    assert sessions[0].issue_key == "PROJ-222"


def test_link_replace_existing_jira_cancelled(mock_jira_cli, temp_daf_home):
    """Test cancelling replacement of existing JIRA link."""
    mock_jira_cli.set_ticket("PROJ-111", {"key": "PROJ-111", "fields": {"summary": "Original"}})
    mock_jira_cli.set_ticket("PROJ-222", {"key": "PROJ-222", "fields": {"summary": "Replacement"}})

    runner = CliRunner()

    # Create session with JIRA
    result = runner.invoke(cli, ["new", "--name", "test", "--goal", "Test", "--jira", "PROJ-111", "--path", str(temp_daf_home / "project")], input="n\n")
    assert result.exit_code == 0

    # Cancel replacement
    result = runner.invoke(cli, ["link", "test", "--jira", "PROJ-222"], input="n\n")

    assert result.exit_code == 0
    assert "cancelled" in result.output.lower() or "canceled" in result.output.lower()

    # Verify original remains
    config_loader = ConfigLoader()
    sessions = config_loader.load_sessions().get_sessions("test")
    assert sessions[0].issue_key == "PROJ-111"


def test_link_session_not_found(mock_jira_cli, temp_daf_home):
    """Test linking to non-existent session."""
    runner = CliRunner()

    result = runner.invoke(cli, ["link", "nonexistent", "--jira", "PROJ-123"])

    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_unlink_with_force_flag(mock_jira_cli, temp_daf_home):
    """Test unlinking with --force flag skips confirmation."""
    mock_jira_cli.set_ticket("PROJ-12345", {"key": "PROJ-12345", "fields": {"summary": "Test"}})

    runner = CliRunner()

    # Create session with JIRA
    result = runner.invoke(cli, ["new", "--name", "test", "--goal", "Test", "--jira", "PROJ-12345", "--path", str(temp_daf_home / "project")], input="n\n")
    assert result.exit_code == 0

    # Unlink with --force
    result = runner.invoke(cli, ["unlink", "test", "--force"])

    assert result.exit_code == 0
    # Should not prompt
    assert "?" not in result.output

    # Verify unlinked
    config_loader = ConfigLoader()
    sessions = config_loader.load_sessions().get_sessions("test")
    assert sessions[0].issue_key is None


def test_unlink_session_not_found(temp_daf_home):
    """Test unlinking non-existent session."""
    runner = CliRunner()

    result = runner.invoke(cli, ["unlink", "nonexistent"])

    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_unlink_session_without_jira(mock_jira_cli, temp_daf_home):
    """Test unlinking session that has no JIRA."""
    runner = CliRunner()

    # Create session without JIRA
    result = runner.invoke(cli, ["new", "--name", "test", "--goal", "Test", "--path", str(temp_daf_home / "project")], input="n\n")
    assert result.exit_code == 0

    # Try to unlink
    result = runner.invoke(cli, ["unlink", "test"])

    assert result.exit_code == 0
    assert "no JIRA" in result.output or "no jira" in result.output


def test_unlink_cancelled(mock_jira_cli, temp_daf_home):
    """Test cancelling unlink operation."""
    mock_jira_cli.set_ticket("PROJ-12345", {"key": "PROJ-12345", "fields": {"summary": "Test"}})

    runner = CliRunner()

    # Create session with JIRA
    result = runner.invoke(cli, ["new", "--name", "test", "--goal", "Test", "--jira", "PROJ-12345", "--path", str(temp_daf_home / "project")], input="n\n")
    assert result.exit_code == 0

    # Cancel unlink
    result = runner.invoke(cli, ["unlink", "test"], input="n\n")

    assert result.exit_code == 0
    assert "cancelled" in result.output.lower() or "canceled" in result.output.lower()

    # Verify still linked
    config_loader = ConfigLoader()
    sessions = config_loader.load_sessions().get_sessions("test")
    assert sessions[0].issue_key == "PROJ-12345"


def test_link_updates_session_goal(mock_jira_cli, temp_daf_home):
    """Test that linking updates session goal with JIRA summary."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Implement amazing feature", "status": {"name": "New"}}
    })

    runner = CliRunner()

    # Create session with simple goal
    result = runner.invoke(cli, ["new", "--name", "feature", "--goal", "Simple goal", "--path", str(temp_daf_home / "project")], input="n\n")
    assert result.exit_code == 0

    # Link JIRA
    result = runner.invoke(cli, ["link", "feature", "--jira", "PROJ-12345"])
    assert result.exit_code == 0

    # Verify goal updated with concatenated format
    config_loader = ConfigLoader()
    sessions = config_loader.load_sessions().get_sessions("feature")
    assert sessions[0].goal == "PROJ-12345: Implement amazing feature"


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


def test_link_with_force_flag_replaces_without_prompt(mock_jira_cli, temp_daf_home):
    """Test that --force flag skips confirmation when replacing existing link (AAP-63885)."""
    # Setup: Configure mock issue tracker tickets
    mock_jira_cli.set_ticket("PROJ-1", {
        "key": "PROJ-1",
        "fields": {
            "summary": "First ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })
    mock_jira_cli.set_ticket("PROJ-2", {
        "key": "PROJ-2",
        "fields": {
            "summary": "Second ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    runner = CliRunner()

    # Step 1: Create a session and link to PROJ-1
    result = runner.invoke(cli, [
        "new",
        "--name", "test-session",
        "--goal", "Test",
        "--jira", "PROJ-1",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude
    assert result.exit_code == 0

    # Step 2: Link to PROJ-2 with --force (should not prompt)
    result = runner.invoke(cli, [
        "link",
        "test-session",
        "--jira", "PROJ-2",
        "--force"
    ])

    # Verify: Command succeeded without prompting
    assert result.exit_code == 0
    assert "PROJ-2" in result.output

    # Verify: Session now has PROJ-2
    config_loader = ConfigLoader()
    sessions_index = config_loader.load_sessions()
    sessions = sessions_index.get_sessions("test-session")
    assert sessions is not None
    assert len(sessions) > 0
    assert sessions[0].issue_key == "PROJ-2"
    assert sessions[0].goal == "PROJ-2: Second ticket"


def test_link_with_json_flag_non_interactive(mock_jira_cli, temp_daf_home):
    """Test that --json flag returns valid JSON without prompting (AAP-63885)."""
    # Setup: Configure mock issue tracker tickets
    mock_jira_cli.set_ticket("PROJ-1", {
        "key": "PROJ-1",
        "fields": {
            "summary": "First ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })
    mock_jira_cli.set_ticket("PROJ-2", {
        "key": "PROJ-2",
        "fields": {
            "summary": "Second ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    runner = CliRunner()

    # Step 1: Create a session and link to PROJ-1
    result = runner.invoke(cli, [
        "new",
        "--name", "test-session",
        "--goal", "Test",
        "--jira", "PROJ-1",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude
    assert result.exit_code == 0

    # Step 2: Link to PROJ-2 with --json (should not prompt, auto-replace)
    result = runner.invoke(cli, [
        "link",
        "test-session",
        "--jira", "PROJ-2",
        "--json"
    ])

    # Verify: Command succeeded
    assert result.exit_code == 0

    # Verify: Output is valid JSON
    output_data = json.loads(result.output)
    assert output_data["success"] is True
    assert output_data["data"]["issue_key"] == "PROJ-2"
    assert output_data["data"]["session_group"] == "test-session"
    assert output_data["data"]["replaced"] == "PROJ-1"

    # Verify: Session now has PROJ-2
    config_loader = ConfigLoader()
    sessions_index = config_loader.load_sessions()
    sessions = sessions_index.get_sessions("test-session")
    assert sessions is not None
    assert len(sessions) > 0
    assert sessions[0].issue_key == "PROJ-2"


def test_link_json_error_for_invalid_session(mock_jira_cli, temp_daf_home):
    """Test that --json flag returns valid JSON error for invalid session (AAP-63885)."""
    # Setup: Configure mock issue tracker ticket
    mock_jira_cli.set_ticket("PROJ-1", {
        "key": "PROJ-1",
        "fields": {"summary": "Test", "status": {"name": "New"}}
    })

    runner = CliRunner()

    # Try to link to non-existent session with --json
    result = runner.invoke(cli, [
        "link",
        "nonexistent-session",
        "--jira", "PROJ-1",
        "--json"
    ])

    # Verify: Command failed
    assert result.exit_code != 0

    # Verify: Output is valid JSON error
    output_data = json.loads(result.output)
    assert output_data["success"] is False
    assert "error" in output_data
    assert output_data["error"]["code"] == "NOT_FOUND"
    assert "not found" in output_data["error"]["message"].lower()


def test_link_json_error_for_invalid_jira(mock_jira_cli, temp_daf_home):
    """Test that --json flag returns valid JSON error for invalid JIRA ticket (AAP-63885)."""
    runner = CliRunner()

    # Step 1: Create a session
    result = runner.invoke(cli, [
        "new",
        "--name", "test-session",
        "--goal", "Test",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude
    assert result.exit_code == 0

    # Step 2: Try to link to non-existent JIRA ticket with --json
    result = runner.invoke(cli, [
        "link",
        "test-session",
        "--jira", "PROJ-99999",
        "--json"
    ])

    # Verify: Command failed
    assert result.exit_code != 0

    # Verify: Output is valid JSON error
    output_data = json.loads(result.output)
    assert output_data["success"] is False
    assert "error" in output_data
    assert output_data["error"]["code"] == "VALIDATION_ERROR"
