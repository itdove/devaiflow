"""Tests for daf search command."""

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_search_empty(temp_daf_home):
    """Test searching sessions when none exist."""
    runner = CliRunner()
    result = runner.invoke(cli, ["search"])

    assert result.exit_code == 0
    assert "No sessions found" in result.output


def test_search_with_none_goal(temp_daf_home):
    """Test searching sessions when goal is None (regression test for TypeError)."""
    # Create sessions with None goal
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with None goal (should not raise TypeError)
    session_manager.create_session(
        name="test-session",
        goal=None,  # Explicitly set to None
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
        issue_key="PROJ-12345",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["search"])

    # Should succeed and display session with "-" for missing goal
    assert result.exit_code == 0
    assert "Found 1 session(s)" in result.output
    assert "PROJ-12345" in result.output
    assert "test-dir" in result.output


def test_search_query_with_none_goal(temp_daf_home):
    """Test searching with query when some sessions have None goal."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with None goal
    session_manager.create_session(
        name="session-no-goal",
        goal=None,
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-111",
    )

    # Create session with actual goal
    session_manager.create_session(
        name="session-with-goal",
        goal="Implement search feature",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
        issue_key="PROJ-222",
    )

    runner = CliRunner()

    # Search for "search" - should find only session-with-goal
    result = runner.invoke(cli, ["search", "search"])

    assert result.exit_code == 0
    assert "Found 1 session(s)" in result.output
    assert "PROJ-222" in result.output
    assert "PROJ-111" not in result.output


def test_search_query_by_name(temp_daf_home):
    """Test searching sessions by name."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="feature-authentication",
        goal="Add auth",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="bugfix-timeout",
        goal="Fix timeout",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "authentication"])

    assert result.exit_code == 0
    assert "Found 1 session(s)" in result.output
    assert "feature-authentication" in result.output


def test_search_query_by_goal(temp_daf_home):
    """Test searching sessions by goal."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="session1",
        goal="Implement caching layer",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="session2",
        goal="Fix database queries",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "caching"])

    assert result.exit_code == 0
    assert "Found 1 session(s)" in result.output
    assert "session1" in result.output
    assert "session2" not in result.output


def test_search_no_results(temp_daf_home):
    """Test searching sessions with no matching results."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "nonexistent"])

    assert result.exit_code == 0
    assert "No sessions found matching criteria" in result.output


def test_search_truncate_long_goal(temp_daf_home):
    """Test that long goals are truncated in search results."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    long_goal = "A" * 100  # Create a goal longer than 50 characters

    session_manager.create_session(
        name="test-session",
        goal=long_goal,
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["search"])

    assert result.exit_code == 0
    assert "Found 1 session(s)" in result.output
    # Should be truncated to 47 chars + "..." (could be unicode ellipsis or ASCII)
    assert ("..." in result.output or "…" in result.output)
    # Full goal should not be in output
    assert long_goal not in result.output


def test_search_filter_by_working_directory(temp_daf_home):
    """Test filtering sessions by working directory."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="session1",
        goal="Goal 1",
        working_directory="backend",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="session2",
        goal="Goal 2",
        working_directory="frontend",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "--working-directory", "backend"])

    assert result.exit_code == 0
    assert "Found 1 session(s)" in result.output
    assert "session1" in result.output
    assert "session2" not in result.output


def test_search_filter_by_tag(temp_daf_home):
    """Test filtering sessions by tag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session1 = session_manager.create_session(
        name="session1",
        goal="Goal 1",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.tags = ["urgent", "bug"]
    session_manager.update_session(session1)

    session2 = session_manager.create_session(
        name="session2",
        goal="Goal 2",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.tags = ["feature"]
    session_manager.update_session(session2)

    runner = CliRunner()
    result = runner.invoke(cli, ["search", "--tag", "urgent"])

    assert result.exit_code == 0
    assert "Found 1 session(s)" in result.output
    assert "session1" in result.output
    assert "session2" not in result.output
