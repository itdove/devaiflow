"""Tests for configuration data models."""

from datetime import datetime, timedelta

import pytest

from devflow.config.models import ConversationContext, Session, SessionIndex, WorkSession


def test_work_session_duration_seconds():
    """Test calculating work session duration."""
    start = datetime.now() - timedelta(hours=2)
    end = datetime.now()

    ws = WorkSession(start=start, end=end)
    duration = ws.duration_seconds()

    # Should be approximately 2 hours (7200 seconds)
    assert 7190 < duration < 7210


def test_work_session_duration_seconds_no_end():
    """Test calculating duration for active work session."""
    start = datetime.now() - timedelta(minutes=30)

    ws = WorkSession(start=start)  # No end time
    duration = ws.duration_seconds()

    # Should be approximately 30 minutes (1800 seconds)
    assert 1790 < duration < 1810


def test_session_total_time_seconds():
    """Test calculating total time across all work sessions."""
    session = Session(
        name="test",        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Add two completed work sessions
    start1 = datetime.now() - timedelta(hours=3)
    end1 = datetime.now() - timedelta(hours=2)
    session.work_sessions.append(WorkSession(start=start1, end=end1, user="user1"))

    start2 = datetime.now() - timedelta(hours=1)
    end2 = datetime.now()
    session.work_sessions.append(WorkSession(start=start2, end=end2, user="user2"))

    total = session.total_time_seconds()

    # Should be approximately 2 hours total (7200 seconds)
    assert 7190 < total < 7210


def test_session_time_by_user():
    """Test calculating time breakdown by user."""
    session = Session(
        name="test",        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # User1: 1 hour
    start1 = datetime.now() - timedelta(hours=2)
    end1 = datetime.now() - timedelta(hours=1)
    session.work_sessions.append(WorkSession(start=start1, end=end1, user="user1"))

    # User2: 30 minutes
    start2 = datetime.now() - timedelta(minutes=30)
    end2 = datetime.now()
    session.work_sessions.append(WorkSession(start=start2, end=end2, user="user2"))

    # User1 again: 30 minutes
    start3 = datetime.now() - timedelta(hours=3)
    end3 = datetime.now() - timedelta(hours=2, minutes=30)
    session.work_sessions.append(WorkSession(start=start3, end=end3, user="user1"))

    time_by_user = session.time_by_user()

    assert "user1" in time_by_user
    assert "user2" in time_by_user
    # User1 should have ~1.5 hours (5400 seconds)
    assert 5390 < time_by_user["user1"] < 5410
    # User2 should have ~0.5 hours (1800 seconds)
    assert 1790 < time_by_user["user2"] < 1810


def test_session_time_by_user_no_user():
    """Test time tracking when user is not specified."""
    session = Session(
        name="test",        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Work session without user specified
    start = datetime.now() - timedelta(hours=1)
    end = datetime.now()
    session.work_sessions.append(WorkSession(start=start, end=end))

    time_by_user = session.time_by_user()

    assert "unknown" in time_by_user
    assert 3590 < time_by_user["unknown"] < 3610


def test_session_time_by_user_only_active_sessions():
    """Test that only completed work sessions are counted."""
    session = Session(
        name="test",        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Completed work session
    start1 = datetime.now() - timedelta(hours=2)
    end1 = datetime.now() - timedelta(hours=1)
    session.work_sessions.append(WorkSession(start=start1, end=end1, user="user1"))

    # Active work session (no end time)
    start2 = datetime.now() - timedelta(minutes=30)
    session.work_sessions.append(WorkSession(start=start2, user="user1"))

    time_by_user = session.time_by_user()

    # Should only count the completed session (~1 hour)
    assert 3590 < time_by_user["user1"] < 3610


def test_session_index_list_sessions_by_sprint():
    """Test filtering sessions by JIRA sprint."""
    index = SessionIndex()

    session1 = Session(
        name="session1",        goal="Sprint 1 work",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.issue_metadata = {"sprint": "Sprint 42"}

    session2 = Session(
        name="session2",        goal="Sprint 2 work",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.issue_metadata = {"sprint": "Sprint 43"}

    index.sessions["session1"] = session1
    index.sessions["session2"] = session2

    result = index.list_sessions(sprint="Sprint 42")

    assert len(result) == 1
    assert result[0].name == "session1"


def test_session_index_list_sessions_by_jira_status():
    """Test filtering sessions by JIRA status."""
    index = SessionIndex()

    session1 = Session(
        name="session1",        goal="In progress",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.issue_metadata = {"status": "In Progress"}

    session2 = Session(
        name="session2",        goal="Done",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.issue_metadata = {"status": "Done"}

    index.sessions["session1"] = session1
    index.sessions["session2"] = session2

    result = index.list_sessions(issue_status="In Progress")

    assert len(result) == 1
    assert result[0].issue_metadata.get("status") == "In Progress"


def test_session_index_list_sessions_by_multiple_jira_statuses():
    """Test filtering by multiple JIRA statuses (comma-separated)."""
    index = SessionIndex()

    session1 = Session(
        name="session1",        goal="New work",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.issue_metadata = {"status": "New"}

    session2 = Session(
        name="session2",        goal="In progress",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.issue_metadata = {"status": "In Progress"}

    session3 = Session(
        name="session3",        goal="Done",
        working_directory="dir3",
        project_path="/path3",
        ai_agent_session_id="uuid-3",
    )
    session3.issue_metadata = {"status": "Done"}

    index.sessions["session1"] = session1
    index.sessions["session2"] = session2
    index.sessions["session3"] = session3

    result = index.list_sessions(issue_status="New, In Progress")

    assert len(result) == 2
    statuses = {s.issue_metadata.get("status") for s in result}
    assert statuses == {"New", "In Progress"}


def test_session_index_list_sessions_by_date_range():
    """Test filtering sessions by date range."""
    index = SessionIndex()

    now = datetime.now()

    session1 = Session(
        name="recent",        goal="Recent",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.last_active = now - timedelta(days=1)

    session2 = Session(
        name="old",        goal="Old",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.last_active = now - timedelta(days=10)

    index.sessions["recent"] = session1
    index.sessions["old"] = session2

    # Get sessions since 5 days ago
    since = now - timedelta(days=5)
    result = index.list_sessions(since=since)

    assert len(result) == 1
    assert result[0].name == "recent"


def test_session_index_list_sessions_before_date():
    """Test filtering sessions before a certain date."""
    index = SessionIndex()

    now = datetime.now()

    session1 = Session(
        name="recent",        goal="Recent",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.last_active = now - timedelta(days=1)

    session2 = Session(
        name="old",        goal="Old",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.last_active = now - timedelta(days=10)

    index.sessions["recent"] = session1
    index.sessions["old"] = session2

    # Get sessions before 5 days ago
    before = now - timedelta(days=5)
    result = index.list_sessions(before=before)

    assert len(result) == 1
    assert result[0].name == "old"


def test_session_index_list_sessions_sorted_by_last_active():
    """Test that sessions are sorted by last_active (most recent first)."""
    index = SessionIndex()

    now = datetime.now()

    session1 = Session(
        name="oldest",        goal="Oldest",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.last_active = now - timedelta(days=10)

    session2 = Session(
        name="newest",        goal="Newest",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.last_active = now

    session3 = Session(
        name="middle",        goal="Middle",
        working_directory="dir3",
        project_path="/path3",
        ai_agent_session_id="uuid-3",
    )
    session3.last_active = now - timedelta(days=5)

    index.sessions["oldest"] = session1
    index.sessions["newest"] = session2
    index.sessions["middle"] = session3

    result = index.list_sessions()

    assert len(result) == 3
    assert result[0].name == "newest"
    assert result[1].name == "middle"
    assert result[2].name == "oldest"


def test_conversation_context_get_repo_name_with_temp_directory():
    """Test that get_repo_name() prioritizes original_project_path over temp directory."""
    # Case 1: With temp directory - should use original_project_path
    conversation = ConversationContext(
        ai_agent_session_id="uuid-1",
        project_path="/tmp/daf-jira-analysis-xyz123",
        original_project_path="/Users/test/workspace/test-repo",
        branch="feature-branch",
    )

    assert conversation.get_repo_name() == "test-repo"

    # Case 2: Without temp directory - should use project_path
    conversation2 = ConversationContext(
        ai_agent_session_id="uuid-2",
        project_path="/Users/test/workspace/test-repo",
        branch="feature-branch",
    )

    assert conversation2.get_repo_name() == "test-repo"

    # Case 3: With explicit repo_name - should use that
    conversation3 = ConversationContext(
        ai_agent_session_id="uuid-3",
        project_path="/tmp/daf-jira-analysis-xyz123",
        original_project_path="/Users/test/workspace/test-repo",
        repo_name="explicit-repo",
        branch="feature-branch",
    )

    assert conversation3.get_repo_name() == "explicit-repo"


def test_session_add_conversation_with_temp_directory():
    """Test that add_conversation() derives repo_name from original_project_path when using temp directory."""
    session = Session(
        name="test-session",        goal="Test goal",
        working_directory="test-dir",
        project_path="/tmp/daf-jira-analysis-xyz123",
        ai_agent_session_id="uuid-1",
    )

    # Add conversation with temp directory
    conversation = session.add_conversation(
        ai_agent_session_id="conv-uuid-1",
        working_dir="/tmp/daf-jira-analysis-xyz123",
        project_path="/tmp/daf-jira-analysis-xyz123",
        branch="main",
        base_branch="main",
        original_project_path="/Users/test/workspace/test-example-repo",
        temp_directory="/tmp/daf-jira-analysis-xyz123",
        workspace="/Users/test/workspace",
    )

    # Should derive repo_name from original_project_path, not temp directory
    assert conversation.repo_name == "test-example-repo"
    assert conversation.get_repo_name() == "test-example-repo"

    # Add conversation without temp directory
    conversation2 = session.add_conversation(
        ai_agent_session_id="conv-uuid-2",
        working_dir="/Users/test/workspace/another-repo",
        project_path="/Users/test/workspace/another-repo",
        branch="main",
        base_branch="main",
        workspace="/Users/test/workspace",
    )

    # Should derive repo_name from project_path
    assert conversation2.repo_name == "another-repo"
    assert conversation2.get_repo_name() == "another-repo"


def test_config_gcp_vertex_region_field():
    """Test that gcp_vertex_region field can be set and retrieved on Config model."""
    from devflow.config.models import Config, JiraConfig, RepoConfig, RepoDetectionConfig

    # Create a config with gcp_vertex_region set
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="test@example.com",
            transitions={},
        ),
        repos=RepoConfig(
            workspace="/Users/test/workspace",
            detection=RepoDetectionConfig(),
        ),
        gcp_vertex_region="us-central1",
    )

    assert config.gcp_vertex_region == "us-central1"

    # Test with None (default)
    config2 = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="test@example.com",
            transitions={},
        ),
        repos=RepoConfig(
            workspace="/Users/test/workspace",
            detection=RepoDetectionConfig(),
        ),
    )

    assert config2.gcp_vertex_region is None


def test_prompts_config_auto_push_to_remote():
    """Test that auto_push_to_remote field works correctly in PromptsConfig."""
    from devflow.config.models import PromptsConfig

    # Test with True (always push)
    config1 = PromptsConfig(auto_push_to_remote=True)
    assert config1.auto_push_to_remote is True

    # Test with False (never push)
    config2 = PromptsConfig(auto_push_to_remote=False)
    assert config2.auto_push_to_remote is False

    # Test with None (prompt each time - default)
    config3 = PromptsConfig()
    assert config3.auto_push_to_remote is None

    # Test explicit None
    config4 = PromptsConfig(auto_push_to_remote=None)
    assert config4.auto_push_to_remote is None
