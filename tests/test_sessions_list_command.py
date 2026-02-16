"""Tests for sessions list command."""

from datetime import datetime
from unittest.mock import patch

from devflow.cli.commands.sessions_list_command import sessions_list
from devflow.config.loader import ConfigLoader
from devflow.config.models import Conversation, ConversationContext
from devflow.session.manager import SessionManager


def test_sessions_list_session_not_found(temp_daf_home):
    """Test sessions list with non-existent session."""
    sessions_list(identifier="non-existent")
    # Should display error message


def test_sessions_list_session_not_found_json(temp_daf_home):
    """Test sessions list with non-existent session in JSON mode."""
    with patch('devflow.cli.commands.sessions_list_command.json_output') as mock_json:
        sessions_list(identifier="non-existent", output_json=True)
        mock_json.assert_called_once()
        args = mock_json.call_args[1]
        assert args['success'] is False
        assert 'error' in args


def test_sessions_list_no_conversations(temp_daf_home):
    """Test sessions list when session has no conversations."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )
    # Clear conversations
    session.conversations = {}
    session_manager.update_session(session)

    sessions_list(identifier="test-session")
    # Should display "No conversations found"


def test_sessions_list_with_active_conversation(temp_daf_home):
    """Test sessions list with an active conversation."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-active",
    )
    session.issue_key = "PROJ-123"
    session_manager.update_session(session)

    sessions_list(identifier="test-session")
    # Should display conversation table


def test_sessions_list_with_archived_conversations(temp_daf_home):
    """Test sessions list with archived conversations."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-active",
    )

    # Add archived conversation
    archived_conv = ConversationContext(
        ai_agent_session_id="uuid-archived",
        project_path="/path/to/project",
        branch="main",
        base_branch="main",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=10,
        prs=[],
        archived=True,
        conversation_history=[],
        summary="Completed feature X",
    )

    if "test-dir" in session.conversations:
        session.conversations["test-dir"].archived_sessions.append(archived_conv)
        session_manager.update_session(session)

    sessions_list(identifier="test-session")
    # Should display both active and archived conversations


def test_sessions_list_json_output(temp_daf_home):
    """Test sessions list with JSON output."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )
    session.issue_key = "PROJ-456"
    session_manager.update_session(session)

    with patch('devflow.cli.commands.sessions_list_command.json_output') as mock_json:
        sessions_list(identifier="test-session", output_json=True)
        mock_json.assert_called_once()
        args = mock_json.call_args[1]
        assert args['success'] is True
        assert 'data' in args
        assert args['data']['session_name'] == "test-session"
        assert args['data']['issue_key'] == "PROJ-456"
        assert 'repositories' in args['data']


def test_sessions_list_multiple_repositories(temp_daf_home):
    """Test sessions list with conversations in multiple repositories."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="multi-repo",
        goal="Multi-repo work",
        working_directory="repo1",
        project_path="/path/to/repo1",
        ai_agent_session_id="uuid-repo1",
    )

    # Add conversation for second repository
    conv2 = Conversation(
        active_session=ConversationContext(
            ai_agent_session_id="uuid-repo2",
            project_path="/path/to/repo2",
            branch="develop",
            base_branch="main",
            created=datetime.now(),
            last_active=datetime.now(),
            message_count=5,
            prs=[],
            archived=False,
            conversation_history=["uuid-repo2"],
        ),
        archived_sessions=[],
    )
    session.conversations["repo2"] = conv2
    session_manager.update_session(session)

    sessions_list(identifier="multi-repo")
    # Should display conversations from both repositories


def test_sessions_list_with_pr_links(temp_daf_home):
    """Test sessions list displays PR links."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="pr-session",
        goal="PR work",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Set PR links on the active conversation
    if "test-dir" in session.conversations:
        session.conversations["test-dir"].active_session.prs = [
            "https://github.com/owner/repo/pull/123"
        ]
        session_manager.update_session(session)

    with patch('devflow.cli.commands.sessions_list_command.json_output') as mock_json:
        sessions_list(identifier="pr-session", output_json=True)
        args = mock_json.call_args[1]
        repos = args['data']['repositories']
        assert len(repos[0]['conversations'][0]['prs']) == 1


def test_sessions_list_with_long_summary(temp_daf_home):
    """Test sessions list truncates long summaries."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="summary-session",
        goal="Test summary",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add archived conversation with long summary
    long_summary = "This is a very long summary " * 10  # Over 80 characters
    archived_conv = ConversationContext(
        ai_agent_session_id="uuid-archived",
        project_path="/path/to/project",
        branch="main",
        base_branch="main",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=15,
        prs=[],
        archived=True,
        conversation_history=[],
        summary=long_summary,
    )

    if "test-dir" in session.conversations:
        session.conversations["test-dir"].archived_sessions.append(archived_conv)
        session_manager.update_session(session)

    # Should truncate summary in display
    sessions_list(identifier="summary-session")


def test_sessions_list_json_output_with_multiple_conversations(temp_daf_home):
    """Test JSON output includes all conversation details."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="detailed-session",
        goal="Detailed test",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-active",
    )

    # Add multiple archived conversations
    for i in range(3):
        archived_conv = ConversationContext(
            ai_agent_session_id=f"uuid-archived-{i}",
            project_path="/path/to/project",
            branch="feature-branch",
            base_branch="main",
            created=datetime.now(),
            last_active=datetime.now(),
            message_count=i + 5,
            prs=[],
            archived=True,
            conversation_history=[],
            summary=f"Summary {i}",
        )

        if "test-dir" in session.conversations:
            session.conversations["test-dir"].archived_sessions.append(archived_conv)

    session_manager.update_session(session)

    with patch('devflow.cli.commands.sessions_list_command.json_output') as mock_json:
        sessions_list(identifier="detailed-session", output_json=True)
        args = mock_json.call_args[1]
        repos = args['data']['repositories']
        # Should have 1 active + 3 archived = 4 total conversations
        assert len(repos[0]['conversations']) == 4
