"""Example tests showing how to use the JIRA mock."""

import subprocess

import pytest


def test_jira_issue_view_success(mock_jira_cli):
    """Test that JIRA issue view command works with mock."""
    # Setup: Configure a mock ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "customfield_12310243": 5,  # Story points
        }
    })

    # Execute: Run JIRA CLI command
    result = subprocess.run(
        ["jira", "issue", "view", "PROJ-12345", "--plain"],
        capture_output=True,
        text=True
    )

    # Verify: Command succeeded and returned ticket data
    assert result.returncode == 0
    assert "PROJ-12345" in result.stdout
    assert "Test ticket" in result.stdout


def test_jira_issue_view_not_found(mock_jira_cli):
    """Test that JIRA issue view fails for non-existent ticket."""
    # Execute: Try to view ticket that doesn't exist
    result = subprocess.run(
        ["jira", "issue", "view", "PROJ-99999", "--plain"],
        capture_output=True,
        text=True
    )

    # Verify: Command failed
    assert result.returncode == 1
    assert "not found" in result.stderr


def test_jira_issue_comment(mock_jira_cli):
    """Test adding a comment to a issue tracker ticket."""
    # Setup: Configure a mock ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test ticket"}
    })

    # Execute: Add a comment
    result = subprocess.run(
        ["jira", "issue", "comment", "PROJ-12345", "Test comment"],
        capture_output=True,
        text=True
    )

    # Verify: Command succeeded
    assert result.returncode == 0
    assert "PROJ-12345" in result.stdout

    # Verify: Comment was recorded
    assert "PROJ-12345" in mock_jira_cli.comments
    assert "Test comment" in mock_jira_cli.comments["PROJ-12345"]


def test_jira_issue_attach(mock_jira_cli):
    """Test attaching a file to a issue tracker ticket."""
    # Setup: Configure a mock ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test ticket"}
    })

    # Execute: Attach a file
    result = subprocess.run(
        ["jira", "issue", "attach", "PROJ-12345", "/tmp/test.tar.gz"],
        capture_output=True,
        text=True
    )

    # Verify: Command succeeded
    assert result.returncode == 0

    # Verify: Attachment was recorded
    assert "PROJ-12345" in mock_jira_cli.attachments
    assert "/tmp/test.tar.gz" in mock_jira_cli.attachments["PROJ-12345"]


def test_jira_issue_move(mock_jira_cli):
    """Test transitioning a issue tracker ticket status."""
    # Setup: Configure a mock ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"}
        }
    })

    # Execute: Move ticket to In Progress
    result = subprocess.run(
        ["jira", "issue", "move", "PROJ-12345", "In Progress"],
        capture_output=True,
        text=True
    )

    # Verify: Command succeeded
    assert result.returncode == 0

    # Verify: Transition was recorded
    assert mock_jira_cli.transitions["PROJ-12345"] == "In Progress"

    # Verify: Ticket status was updated
    assert mock_jira_cli.tickets["PROJ-12345"]["fields"]["status"]["name"] == "In Progress"


def test_jira_command_failure(mock_jira_cli):
    """Test that JIRA commands can be forced to fail."""
    # Setup: Configure a mock ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test ticket"}
    })

    # Setup: Make next 'issue view' command fail
    mock_jira_cli.fail_next_command("issue view")

    # Execute: Try to view ticket
    result = subprocess.run(
        ["jira", "issue", "view", "PROJ-12345"],
        capture_output=True,
        text=True
    )

    # Verify: Command failed
    assert result.returncode == 1
    assert "failed" in result.stderr


def test_non_jira_commands_pass_through(mock_jira_cli):
    """Test that non-JIRA commands are not intercepted."""
    # Execute: Run a non-JIRA command
    result = subprocess.run(
        ["echo", "test"],
        capture_output=True,
        text=True
    )

    # Verify: Command worked normally
    assert result.returncode == 0
    assert "test" in result.stdout
