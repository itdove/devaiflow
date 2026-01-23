# Testing Guide for DevAIFlow

## Quick Start

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest

# Run specific test file
pytest tests/test_link_command.py

# Run with coverage
pytest --cov=devflow --cov-report=html
```

## How to Test daf Commands with Mock JIRA

### Basic Pattern

```python
def test_your_feature(mock_jira_cli, temp_cs_home):
    """Test description."""
    # 1. Setup: Configure mock JIRA tickets
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Your ticket summary",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    # 2. Execute: Run daf command
    from click.testing import CliRunner
    from devflow.cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "test-session",
        "--goal", "Test goal",
        "--jira", "PROJ-12345",
        "--path", str(temp_cs_home / "test-project")
    ])

    # 3. Verify: Check command output
    assert result.exit_code == 0
    assert "PROJ-12345" in result.output

    # 4. Verify: Check JIRA interactions (if applicable)
    # Check if comment was added
    assert "PROJ-12345" in mock_jira_cli.comments
    # Check if status was transitioned
    assert mock_jira_cli.transitions.get("PROJ-12345") == "In Progress"
```

## Common Testing Scenarios

### Testing JIRA Validation

```python
def test_invalid_jira_ticket(mock_jira_cli, temp_cs_home):
    """Test that invalid JIRA tickets are rejected."""
    # Don't set up any tickets - PROJ-99999 doesn't exist

    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "test",
        "--goal", "Test",
        "--jira", "PROJ-99999",  # This ticket doesn't exist
        "--path", str(temp_cs_home / "project")
    ])

    # Should fail with clear error
    assert result.exit_code != 0
    assert "not found" in result.output.lower()
```

### Testing Without JIRA

```python
def test_session_without_jira(temp_cs_home):
    """Test creating session without JIRA."""
    # No mock_jira_cli needed - JIRA is optional

    runner = CliRunner()
    result = runner.invoke(cli, [
        "new",
        "--name", "local-experiment",
        "--goal", "Testing locally",
        "--path", str(temp_cs_home / "project")
    ])

    assert result.exit_code == 0
```

### Testing JIRA Comments

```python
def test_jira_comment_added(mock_jira_cli, temp_cs_home):
    """Test that JIRA comments are added correctly."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test"}
    })

    runner = CliRunner()

    # Create session
    result = runner.invoke(cli, [
        "new", "--name", "test", "--jira", "PROJ-12345",
        "--goal", "Test", "--path", str(temp_cs_home / "project")
    ])
    assert result.exit_code == 0

    # Add note with JIRA sync
    result = runner.invoke(cli, [
        "note", "test", "Important update", "--jira"
    ])
    assert result.exit_code == 0

    # Verify comment was added
    assert "PROJ-12345" in mock_jira_cli.comments
    comments = mock_jira_cli.comments["PROJ-12345"]
    assert any("Important update" in c for c in comments)
```

### Testing JIRA Status Transitions

```python
def test_jira_status_transition(mock_jira_cli, temp_cs_home):
    """Test that JIRA status is transitioned when completing."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test",
            "status": {"name": "In Progress"}
        }
    })

    runner = CliRunner()

    # Create and complete session
    runner.invoke(cli, [
        "new", "--name", "test", "--jira", "PROJ-12345",
        "--goal", "Test", "--path", str(temp_cs_home / "project")
    ])

    result = runner.invoke(cli, [
        "complete", "test"
    ])

    # Verify status transition
    assert "PROJ-12345" in mock_jira_cli.transitions
    new_status = mock_jira_cli.transitions["PROJ-12345"]
    assert new_status in ["Code Review", "Done"]  # Depends on config
```

### Testing JIRA Failures

```python
def test_jira_timeout_handling(mock_jira_cli, temp_cs_home):
    """Test graceful handling of JIRA failures."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test"}
    })

    # Make next JIRA command fail
    mock_jira_cli.fail_next_command("issue comment")

    runner = CliRunner()

    # Create session
    runner.invoke(cli, [
        "new", "--name", "test", "--jira", "PROJ-12345",
        "--goal", "Test", "--path", str(temp_cs_home / "project")
    ])

    # Try to add note with JIRA sync (should fail gracefully)
    result = runner.invoke(cli, [
        "note", "test", "Update", "--jira"
    ])

    # Note should be saved locally even if JIRA fails
    # (Implementation should handle this gracefully)
```

### Testing Multi-Conversation Sessions

```python
def test_multi_conversation_session(mock_jira_cli, temp_cs_home):
    """Test working with multiple conversations in same session."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Multi-project feature"}
    })

    runner = CliRunner()

    # Create multiple sessions in same group
    runner.invoke(cli, [
        "new", "--name", "feature", "--jira", "PROJ-12345",
        "--goal", "Backend", "--path", str(temp_cs_home / "backend")
    ])

    runner.invoke(cli, [
        "new", "--name", "feature", "--jira", "PROJ-12345",
        "--goal", "Frontend", "--path", str(temp_cs_home / "frontend")
    ])

    # List should show both sessions
    result = runner.invoke(cli, ["list"])
    assert "feature" in result.output
    # Implementation should show both sessions
```

## Verifying Test Coverage

```bash
# Run tests with coverage
pytest --cov=devflow --cov-report=html

# Open coverage report
open htmlcov/index.html
```

## Debugging Tests

### Print command output
```python
def test_debug_output(mock_jira_cli, temp_cs_home):
    runner = CliRunner()
    result = runner.invoke(cli, ["new", "--name", "test", ...])

    # Print full output for debugging
    print("\n=== STDOUT ===")
    print(result.output)
    print("\n=== EXIT CODE ===")
    print(result.exit_code)
    if result.exception:
        print("\n=== EXCEPTION ===")
        print(result.exception)
```

### Check session state
```python
def test_verify_state(mock_jira_cli, temp_cs_home):
    runner = CliRunner()
    result = runner.invoke(cli, [...])

    # Load and inspect sessions
    from devflow.config.loader import ConfigLoader
    config_loader = ConfigLoader()
    sessions_index = config_loader.load_sessions()

    print("\n=== SESSIONS ===")
    for group_name, session_list in sessions_index.sessions.items():
        print(f"\nGroup: {group_name}")
        for session in session_list:
            print(f"  Session #{session.session_id}")
            print(f"    JIRA: {session.issue_key}")
            print(f"    Goal: {session.goal}")
```

## Tips

1. **Always use both fixtures together**: `mock_jira_cli` and `temp_cs_home`
2. **Set up tickets before testing**: Configure all JIRA tickets at the start of the test
3. **Use descriptive ticket data**: Make it clear what each ticket represents
4. **Verify both output and state**: Check command output AND session state
5. **Test failure cases**: Don't just test happy paths
6. **Use markers**: Tag tests with `@pytest.mark.jira` for JIRA-specific tests

## Example: Complete Test File

```python
"""Tests for daf complete command."""

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader


@pytest.mark.jira
def test_complete_with_jira_transition(mock_jira_cli, temp_cs_home):
    """Test completing session with JIRA status transition."""
    # Setup
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Implement feature",
            "status": {"name": "In Progress"},
        }
    })

    runner = CliRunner()

    # Create session
    result = runner.invoke(cli, [
        "new", "--name", "test", "--jira", "PROJ-12345",
        "--goal", "Test", "--path", str(temp_cs_home / "project")
    ])
    assert result.exit_code == 0

    # Complete session
    result = runner.invoke(cli, ["complete", "test"])
    assert result.exit_code == 0

    # Verify JIRA transition
    assert mock_jira_cli.transitions["PROJ-12345"] == "Code Review"

    # Verify session state
    config_loader = ConfigLoader()
    sessions = config_loader.load_sessions().get_sessions("test")
    assert sessions[0].status == "complete"


def test_complete_without_jira(temp_cs_home):
    """Test completing session without JIRA."""
    runner = CliRunner()

    # Create session without JIRA
    result = runner.invoke(cli, [
        "new", "--name", "local-test",
        "--goal", "Local work", "--path", str(temp_cs_home / "project")
    ])
    assert result.exit_code == 0

    # Complete session
    result = runner.invoke(cli, ["complete", "local-test"])
    assert result.exit_code == 0

    # Verify session state
    config_loader = ConfigLoader()
    sessions = config_loader.load_sessions().get_sessions("local-test")
    assert sessions[0].status == "complete"
```
