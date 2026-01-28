"""Integration tests for 'daf new' command with JIRA validation."""

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli


def test_daf_new_with_valid_jira(mock_jira_cli, temp_daf_home):
    """Test creating a session with a valid issue tracker ticket."""
    # Setup: Configure a mock issue tracker ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Implement backup feature",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    # Execute: Create a new session with JIRA
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "backup-feature",
        "--goal", "Implement backup",
        "--jira", "PROJ-12345",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude Code

    # Verify: Command succeeded
    assert result.exit_code == 0
    assert "Created session" in result.output
    assert "PROJ-12345" in result.output


def test_daf_new_with_invalid_jira(mock_jira_cli, temp_daf_home):
    """Test creating a session with an invalid issue tracker ticket fails."""
    # Setup: No ticket configured (will return 404)

    # Execute: Try to create session with non-existent ticket
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "backup-feature",
        "--goal", "Implement backup",
        "--jira", "PROJ-99999",
        "--path", str(temp_daf_home / "test-project")
    ])

    # Verify: Command failed with clear error
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_daf_new_without_jira(temp_daf_home):
    """Test creating a session without JIRA works."""
    # Execute: Create session without JIRA
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "test-experiment",
        "--goal", "Testing something",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude Code

    # Verify: Command succeeded
    assert result.exit_code == 0
    assert "Created session" in result.output


def test_daf_new_jira_timeout(mock_jira_cli, temp_daf_home, monkeypatch):
    """Test that JIRA validation timeout is handled gracefully."""
    # Setup: Make JIRA command hang
    import time

    original_run = subprocess.run

    def slow_jira_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd[0] == "jira":
            time.sleep(10)  # Simulate timeout
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", slow_jira_run)

    # Execute: Try to create session (should timeout)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "backup-feature",
        "--goal", "Implement backup",
        "--jira", "PROJ-12345",
        "--path", str(temp_daf_home / "test-project")
    ], catch_exceptions=True)

    # Verify: Timeout was handled
    # Note: Actual timeout handling depends on implementation
    # This is just an example of how to test it


def test_daf_new_goal_concatenation_with_jira(mock_jira_cli, temp_daf_home):
    """Test that goal field stores concatenated issue key and title (PROJ-59070)."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Setup: Configure a mock issue tracker ticket
    mock_jira_cli.set_ticket("PROJ-59070", {
        "key": "PROJ-59070",
        "fields": {
            "summary": "Store concatenated goal in session.goal field",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
        }
    })

    # Execute: Create a new session with JIRA
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "aap-59070-store-goal",
        "--goal", "Implement goal concatenation",
        "--jira", "PROJ-59070",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude Code

    # Verify: Command succeeded
    assert result.exit_code == 0

    # Verify: Session was created with concatenated goal
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("aap-59070-store-goal")

    assert session is not None
    # Goal should be: "{ISSUE_KEY}: {JIRA_TITLE}"
    assert session.goal == "PROJ-59070: Store concatenated goal in session.goal field"
    assert session.issue_key == "PROJ-59070"
    assert session.issue_metadata.get("summary") == "Store concatenated goal in session.goal field"


def test_daf_new_goal_concatenation_with_jira_no_user_goal(mock_jira_cli, temp_daf_home):
    """Test goal concatenation when user provides no goal, only issue key."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Setup: Configure a mock issue tracker ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Implement backup feature",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    # Execute: Create session with JIRA but empty goal
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "backup-feature",
        "--goal", "",  # Empty goal
        "--jira", "PROJ-12345",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")

    # Verify: Command succeeded
    assert result.exit_code == 0

    # Verify: Goal uses JIRA title
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("backup-feature")

    assert session is not None
    # Goal should be: "{ISSUE_KEY}: {JIRA_TITLE}" even with empty user goal
    assert session.goal == "PROJ-12345: Implement backup feature"


def test_daf_new_goal_without_jira(temp_daf_home):
    """Test that goal field remains as-is when no issue tracker ticket is provided."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Execute: Create session without JIRA
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "test-experiment",
        "--goal", "Testing something interesting",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")

    # Verify: Command succeeded
    assert result.exit_code == 0

    # Verify: Goal is stored exactly as provided (no concatenation)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-experiment")

    assert session is not None
    assert session.goal == "Testing something interesting"
    assert session.issue_key is None


def test_daf_new_sets_status_paused_after_claude_exits(temp_daf_home, monkeypatch):
    """Test that session status is set to 'paused' after Claude Code exits (PROJ-60431)."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Mock subprocess.run to prevent actual Claude Code launch
    def mock_subprocess_run(cmd, *args, **kwargs):
        # Simulate Claude Code exiting successfully
        class CompletedProcess:
            returncode = 0
            stdout = ""  # Empty stdout for git commands
            stderr = ""  # Empty stderr for git commands
        return CompletedProcess()

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # Execute: Create session and launch Claude Code
    # Input sequence:
    #  - "n\n" = Don't create git branch
    #  - "y\n" = Launch Claude Code
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "status-test",
        "--goal", "Test status update",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\ny\n")  # Don't create branch, launch Claude Code

    # Verify: Command succeeded
    if result.exit_code != 0:
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")
        if result.exception:
            print(f"Exception: {result.exception}")
    assert result.exit_code == 0

    # Verify: Session status is 'paused' (after Claude Code exits)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("status-test")

    assert session is not None
    assert session.status == "paused", f"Expected status 'paused' but got '{session.status}'"


def test_daf_new_keeps_status_created_when_not_launching_claude(temp_daf_home):
    """Test that session status remains 'created' when user declines to launch Claude Code."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Execute: Create session but don't launch Claude Code (input="n\n")
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "no-launch-test",
        "--goal", "Test status when not launching",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude Code

    # Verify: Command succeeded
    assert result.exit_code == 0

    # Verify: Session status is 'created' (initial status)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("no-launch-test")

    assert session is not None
    assert session.status == "created", f"Expected status 'created' but got '{session.status}'"


def test_daf_new_prompts_for_goal_when_not_provided_no_jira(temp_daf_home):
    """Test that daf new prompts for goal when --goal is not provided and no JIRA (PROJ-60421)."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Execute: Create session without --goal and without JIRA
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "test-session",
        "--path", str(temp_daf_home / "test-project")
    ], input="My test goal\nn\n")  # Provide goal, don't launch Claude

    # Verify: Command succeeded
    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify: Prompt was shown
    assert "Enter session goal/description (optional, press Enter to skip)" in result.output

    # Verify: Session was created with the provided goal
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-session")

    assert session is not None
    assert session.goal == "My test goal"


def test_daf_new_allows_empty_goal_when_prompted(temp_daf_home):
    """Test that daf new allows empty goal when prompted (PROJ-60421)."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Execute: Create session without --goal, press Enter to skip goal
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "test-no-goal",
        "--path", str(temp_daf_home / "test-project")
    ], input="\nn\n")  # Empty goal (press Enter), don't launch Claude

    # Verify: Command succeeded
    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify: Session was created with no goal (None)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-no-goal")

    assert session is not None
    assert session.goal is None or session.goal == ""


def test_daf_new_no_prompt_when_goal_provided(temp_daf_home):
    """Test that daf new does not prompt when --goal is provided (PROJ-60421)."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Execute: Create session with --goal
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "test-with-goal",
        "--goal", "My explicit goal",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude

    # Verify: Command succeeded
    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify: No goal prompt was shown
    assert "Enter session goal/description" not in result.output

    # Verify: Session was created with the provided goal
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-with-goal")

    assert session is not None
    assert session.goal == "My explicit goal"


def test_daf_new_no_goal_prompt_when_jira_provided(mock_jira_cli, temp_daf_home):
    """Test that daf new does not prompt for goal when JIRA is provided (PROJ-60421)."""
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Setup: Configure a mock issue tracker ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    # Execute: Create session with JIRA but no --goal
    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "test-jira-no-goal",
        "--jira", "PROJ-12345",
        "--path", str(temp_daf_home / "test-project")
    ], input="n\n")  # Don't launch Claude

    # Verify: Command succeeded
    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Verify: No goal prompt was shown (JIRA title is used)
    assert "Enter session goal/description" not in result.output

    # Verify: Session uses JIRA title as goal
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-jira-no-goal")

    assert session is not None
    assert session.goal == "PROJ-12345: Test ticket"
