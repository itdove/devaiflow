"""Tests for daf open command."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.cli.commands.new_command import _handle_branch_creation
from devflow.git.utils import GitUtils


def test_open_nonexistent_session(temp_daf_home):
    """Test opening a session that doesn't exist."""
    runner = CliRunner()
    result = runner.invoke(cli, ["open", "nonexistent"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower() or "No sessions found" in result.output


def test_open_session_no_claude_id(temp_daf_home):
    """Test opening a session without Claude session ID."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session without any conversations (simulates old/broken session)
    session = session_manager.create_session(
        name="broken-session",
        goal="Test",
        working_directory="test-dir",
        # Don't pass project_path/ai_agent_session_id so no conversation is created
    )

    runner = CliRunner()
    # Mock auto-detection to avoid triggering new conversation prompt
    with patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None):
        result = runner.invoke(cli, ["open", "broken-session"], input="1\nn\n")

    # First launch should work and create a new session ID
    # Input: 1 to select session, n to cancel actual launch
    assert result.exit_code == 0
    assert "First-time launch" in result.output or "Generated new session ID" in result.output


def test_open_session_cancels_launch(temp_daf_home):
    """Test cancelling session launch."""
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
    # Mock auto-detection to avoid triggering new conversation prompt
    with patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None):
        # Provide 'n' to cancel launch
        result = runner.invoke(cli, ["open", "test-session"], input="n\n")

    assert result.exit_code == 0
    # Should show session info but not launch


def test_open_session_with_multiple_in_group(temp_daf_home):
    """Test that duplicate session names raise ValueError."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session
    session_manager.create_session(
        name="multi-session",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    import pytest
    with pytest.raises(ValueError, match="Session 'multi-session' already exists"):
        session_manager.create_session(
            name="multi-session",
            goal="Second",
            working_directory="dir2",
            project_path="/path2",
            ai_agent_session_id="uuid-2",
        )


def test_open_session_displays_info(temp_daf_home):
    """Test that open displays session information."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="info-test",
        goal="Test display",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
        issue_key="PROJ-12345",
        branch="feature/test",
    )

    runner = CliRunner()
    # Mock auto-detection to avoid triggering new conversation prompt
    with patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None):
        result = runner.invoke(cli, ["open", "info-test"], input="n\n")

    assert result.exit_code == 0
    assert "info-test" in result.output
    assert "PROJ-12345" in result.output
    assert "feature/test" in result.output
    assert "test-dir" in result.output


def test_open_by_issue_key(temp_daf_home):
    """Test opening session by issue key."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="jira-session",
        goal="JIRA test",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
        issue_key="PROJ-99999",
    )

    runner = CliRunner()
    # Mock auto-detection to avoid triggering new conversation prompt
    with patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None):
        result = runner.invoke(cli, ["open", "PROJ-99999"], input="n\n")

    assert result.exit_code == 0
    assert "PROJ-99999" in result.output
    assert "jira-session" in result.output or "JIRA test" in result.output


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_handle_branch_creation_auto_from_default(tmp_path):
    """Test _handle_branch_creation with auto_from_default=True pulls latest changes."""
    # Initialize a git repo with main branch
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit on main
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create a feature branch to simulate we're not on main
    subprocess.run(["git", "checkout", "-b", "old-feature"], cwd=tmp_path, capture_output=True)

    # Mock the git operations to verify they're called in the right order
    with patch.object(GitUtils, 'fetch_origin', return_value=True) as mock_fetch, \
         patch.object(GitUtils, 'get_default_branch', return_value='main') as mock_get_default, \
         patch.object(GitUtils, 'checkout_branch', return_value=True) as mock_checkout, \
         patch.object(GitUtils, 'pull_current_branch', return_value=True) as mock_pull, \
         patch.object(GitUtils, 'create_branch', return_value=True) as mock_create:

        # Call with auto_from_default=True
        branch = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=True
        )

        # Verify the branch was created
        assert branch is not None

        # Verify git operations were called in correct order
        mock_fetch.assert_called_once_with(tmp_path)
        mock_get_default.assert_called_once_with(tmp_path)
        mock_checkout.assert_called_once_with(tmp_path, 'main')
        mock_pull.assert_called_once_with(tmp_path)
        mock_create.assert_called_once()


def test_handle_branch_creation_auto_mode_skips_confirmation(tmp_path):
    """Test auto_from_default=True skips the 'Create branch?' confirmation."""
    # Mock all git operations
    with patch.object(GitUtils, 'is_git_repository', return_value=True), \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'get_default_branch', return_value='main'), \
         patch.object(GitUtils, 'checkout_branch', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True), \
         patch.object(GitUtils, 'create_branch', return_value=True), \
         patch('devflow.cli.commands.new_command.Confirm.ask') as mock_confirm:

        # Call with auto_from_default=True
        branch = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=True
        )

        # Verify Confirm.ask was NOT called (auto mode skips confirmation)
        mock_confirm.assert_not_called()
        assert branch == 'aap-12345-test'


def test_handle_branch_creation_interactive_mode_asks_confirmation(tmp_path):
    """Test auto_from_default=False asks for user confirmation."""
    # Mock all git operations
    with patch.object(GitUtils, 'is_git_repository', return_value=True), \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test'), \
         patch('devflow.cli.commands.new_command.Confirm.ask', return_value=False) as mock_confirm:

        # Call with auto_from_default=False (default)
        branch = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=False
        )

        # Verify Confirm.ask WAS called (interactive mode asks for confirmation)
        mock_confirm.assert_called_once()
        # User said no, so no branch should be created
        assert branch is None


def test_is_closed_status():
    """Test _is_closed_status helper function."""
    from devflow.cli.commands.open_command import _is_closed_status

    # Test closed statuses
    assert _is_closed_status("Done") is True
    assert _is_closed_status("Closed") is True
    assert _is_closed_status("Resolved") is True
    assert _is_closed_status("Complete") is True
    assert _is_closed_status("Release Pending") is True
    assert _is_closed_status("Review") is True

    # Test open statuses
    assert _is_closed_status("New") is False
    assert _is_closed_status("To Do") is False
    assert _is_closed_status("In Progress") is False
    assert _is_closed_status("Selected for Development") is False


def test_handle_closed_ticket_reopen_user_accepts(temp_daf_home):
    """Test _handle_closed_ticket_reopen when user accepts transition."""
    from devflow.cli.commands.open_command import _handle_closed_ticket_reopen
    from devflow.jira import JiraClient
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with closed issue tracker ticket
    session = session_manager.create_session(
        name="closed-ticket-session",
        goal="Test closed ticket",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
        issue_key="PROJ-12345",
    )
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["status"] = "Done"

    # Mock JiraClient methods
    with patch.object(JiraClient, 'transition_ticket', return_value=True) as mock_transition, \
         patch.object(JiraClient, 'add_comment', return_value=True) as mock_comment, \
         patch('devflow.cli.commands.open_command.Confirm.ask', return_value=True):

        jira_client = JiraClient()
        result = _handle_closed_ticket_reopen(session, jira_client)

        assert result is True
        assert session.issue_metadata.get("status") == "In Progress"
        mock_transition.assert_called_once_with("PROJ-12345", "In Progress")
        mock_comment.assert_called_once()


def test_handle_closed_ticket_reopen_user_declines_transition(temp_daf_home):
    """Test _handle_closed_ticket_reopen when user declines transition but continues."""
    from devflow.cli.commands.open_command import _handle_closed_ticket_reopen
    from devflow.jira import JiraClient
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="declined-transition",
        goal="Test decline",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
        issue_key="PROJ-12345",
    )
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["status"] = "Done"

    # Mock: User declines transition, then accepts continuing without update
    with patch('devflow.cli.commands.open_command.Confirm.ask', side_effect=[False, True]):
        jira_client = JiraClient()
        result = _handle_closed_ticket_reopen(session, jira_client)

        assert result is True
        # Status should remain Done since user declined transition
        assert session.issue_metadata.get("status") == "Done"


def test_handle_closed_ticket_reopen_user_cancels(temp_daf_home):
    """Test _handle_closed_ticket_reopen when user cancels entirely."""
    from devflow.cli.commands.open_command import _handle_closed_ticket_reopen
    from devflow.jira import JiraClient
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="cancel-session",
        goal="Test cancel",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
        issue_key="PROJ-12345",
    )
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["status"] = "Done"

    # Mock: User declines transition, then declines continuing
    with patch('devflow.cli.commands.open_command.Confirm.ask', side_effect=[False, False]):
        jira_client = JiraClient()
        result = _handle_closed_ticket_reopen(session, jira_client)

        assert result is False


def test_handle_closed_ticket_reopen_transition_fails(temp_daf_home):
    """Test _handle_closed_ticket_reopen when transition fails."""
    from devflow.cli.commands.open_command import _handle_closed_ticket_reopen
    from devflow.jira import JiraClient
    from devflow.jira.exceptions import JiraApiError
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="failed-transition",
        goal="Test failure",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
        issue_key="PROJ-12345",
    )
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["status"] = "Done"

    # Mock: User accepts transition, transition raises exception, user accepts continuing anyway
    def mock_transition(*args, **kwargs):
        raise JiraApiError("Transition failed", status_code=500)

    with patch.object(JiraClient, 'transition_ticket', side_effect=mock_transition), \
         patch('devflow.cli.commands.open_command.Confirm.ask', side_effect=[True, True]):

        jira_client = JiraClient()
        result = _handle_closed_ticket_reopen(session, jira_client)

        assert result is True  # User chose to continue anyway
        assert session.issue_metadata.get("status") == "Done"  # Status unchanged due to failure


def test_handle_closed_ticket_reopen_transition_fails_user_cancels(temp_daf_home):
    """Test _handle_closed_ticket_reopen when transition fails and user cancels."""
    from devflow.cli.commands.open_command import _handle_closed_ticket_reopen
    from devflow.jira import JiraClient
    from devflow.jira.exceptions import JiraApiError
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="failed-and-cancel",
        goal="Test failure cancel",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
        issue_key="PROJ-12345",
    )
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["status"] = "Done"

    # Mock: User accepts transition, transition raises exception, user declines continuing
    def mock_transition(*args, **kwargs):
        raise JiraApiError("Transition failed", status_code=500)

    with patch.object(JiraClient, 'transition_ticket', side_effect=mock_transition), \
         patch('devflow.cli.commands.open_command.Confirm.ask', side_effect=[True, False]):

        jira_client = JiraClient()
        result = _handle_closed_ticket_reopen(session, jira_client)

        assert result is False  # User cancelled after failure


def test_session_reopening_uses_active_conversation_id(temp_daf_home, tmp_path):
    """Test PROJ-59818: Session reopening uses consistent Claude session ID from active conversation.

    This test verifies that when reopening an existing session:
    1. Conversation file lookup uses active conversation's ai_agent_session_id
    2. No "Session ID is already in use" errors occur
    3. Deprecated session.ai_agent_session_id field is not referenced
    4. All session ID references use session.current_ai_agent_session_id property
    """
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager
    from devflow.session.capture import SessionCapture

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with a conversation (multi-conversation format)
    project_path = str(tmp_path / "test-project")
    Path(project_path).mkdir(parents=True, exist_ok=True)

    session = session_manager.create_session(
        name="PROJ-59812",
        goal="Test session reopening",
        working_directory="test-project",
        project_path=project_path,
        ai_agent_session_id="original-uuid-123",
        branch="aap-59812-test-feature",
    )

    # Get the session ID from active conversation
    active_conv = session.active_conversation
    assert active_conv is not None, "Session should have an active conversation"
    active_id = active_conv.ai_agent_session_id
    assert active_id is not None, "Active conversation should have a session ID"

    # Create a valid conversation file for this session
    capture = SessionCapture()
    session_dir = capture.get_session_dir(project_path)
    session_dir.mkdir(parents=True, exist_ok=True)
    conversation_file = session_dir / f"{active_id}.jsonl"
    conversation_file.write_text('{"type":"test","content":"test message"}\n')

    # Verify the file exists with the active conversation ID
    assert conversation_file.exists(), "Conversation file should exist with active conversation ID"
    assert conversation_file.stat().st_size > 0, "Conversation file should not be empty"

    # Now try to reopen the session - mock the subprocess call
    runner = CliRunner()
    with patch('devflow.cli.commands.open_command.subprocess.run') as mock_run:
        # Mock Confirm.ask to automatically launch
        with patch('devflow.cli.commands.open_command.Confirm.ask', return_value=True):
            result = runner.invoke(cli, ["open", "PROJ-59812"])

    # Verify no errors about session ID conflicts
    assert "Session ID" not in result.output or "already in use" not in result.output.lower(), \
        "Should not have 'Session ID already in use' error"

    # Verify the subprocess was called with the correct session ID
    if mock_run.called:
        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args and len(call_args[0]) > 0 else []

        # Check that --resume was called with the active conversation ID
        if "--resume" in cmd:
            resume_idx = cmd.index("--resume")
            assert resume_idx + 1 < len(cmd), "Resume should have an argument"
            resumed_id = cmd[resume_idx + 1]
            assert resumed_id == active_id, \
                f"Should resume with active conversation ID {active_id}, got {resumed_id}"

    # Verify the session was loaded correctly
    loaded_session = session_manager.get_session("PROJ-59812")
    assert loaded_session is not None, "Session should exist"

    # Verify active conversation has the correct ID
    loaded_active_conv = loaded_session.active_conversation
    assert loaded_active_conv is not None, "Loaded session should have an active conversation"
    assert loaded_active_conv.ai_agent_session_id == active_id, \
        "Active conversation should have the correct session ID"


def test_check_and_sync_with_base_branch_not_git(tmp_path):
    """Test _check_and_sync_with_base_branch with non-git directory."""
    from devflow.cli.commands.open_command import _check_and_sync_with_base_branch

    # Should handle gracefully and not fail
    _check_and_sync_with_base_branch(str(tmp_path), "feature", "main", "test-session")


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_check_and_sync_with_base_branch_up_to_date(tmp_path):
    """Test _check_and_sync_with_base_branch when branch is up-to-date."""
    from devflow.cli.commands.open_command import _check_and_sync_with_base_branch

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    current_branch = GitUtils.get_current_branch(tmp_path)

    # Mock fetch to succeed, commits_behind to return 0
    with patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'commits_behind', return_value=0):

        # Should complete without prompting
        _check_and_sync_with_base_branch(str(tmp_path), current_branch, current_branch, "test-session")


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_check_and_sync_with_base_branch_user_declines(tmp_path):
    """Test _check_and_sync_with_base_branch when user declines sync."""
    from devflow.cli.commands.open_command import _check_and_sync_with_base_branch

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    current_branch = GitUtils.get_current_branch(tmp_path)

    # Mock: fetch succeeds, branch is 5 commits behind, user declines
    with patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'commits_behind', return_value=5), \
         patch('devflow.cli.commands.open_command.Confirm.ask', return_value=False), \
         patch.object(GitUtils, 'merge_branch') as mock_merge, \
         patch.object(GitUtils, 'rebase_branch') as mock_rebase:

        _check_and_sync_with_base_branch(str(tmp_path), current_branch, "main", "test-session")

        # Should not attempt merge or rebase
        mock_merge.assert_not_called()
        mock_rebase.assert_not_called()


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_check_and_sync_with_base_branch_merge_success(tmp_path):
    """Test _check_and_sync_with_base_branch with successful merge."""
    from devflow.cli.commands.open_command import _check_and_sync_with_base_branch

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    current_branch = GitUtils.get_current_branch(tmp_path)

    # Mock: fetch succeeds, branch is 3 commits behind, user accepts and chooses merge
    with patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'commits_behind', return_value=3), \
         patch('devflow.cli.commands.open_command.Confirm.ask', return_value=True), \
         patch('rich.prompt.Prompt.ask', return_value='m'), \
         patch.object(GitUtils, 'merge_branch', return_value=True) as mock_merge:

        _check_and_sync_with_base_branch(str(tmp_path), current_branch, "main", "test-session")

        # Should call merge with origin/main
        mock_merge.assert_called_once_with(tmp_path, "origin/main")


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_check_and_sync_with_base_branch_rebase_success(tmp_path):
    """Test _check_and_sync_with_base_branch with successful rebase."""
    from devflow.cli.commands.open_command import _check_and_sync_with_base_branch

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    current_branch = GitUtils.get_current_branch(tmp_path)

    # Mock: fetch succeeds, branch is 2 commits behind, user accepts and chooses rebase
    with patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'commits_behind', return_value=2), \
         patch('devflow.cli.commands.open_command.Confirm.ask', return_value=True), \
         patch('rich.prompt.Prompt.ask', return_value='r'), \
         patch.object(GitUtils, 'rebase_branch', return_value=True) as mock_rebase:

        _check_and_sync_with_base_branch(str(tmp_path), current_branch, "main", "test-session")

        # Should call rebase with origin/main
        mock_rebase.assert_called_once_with(tmp_path, "origin/main")


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_check_and_sync_with_base_branch_merge_conflict(tmp_path):
    """Test PROJ-60408: _check_and_sync_with_base_branch returns False on merge conflict."""
    from devflow.cli.commands.open_command import _check_and_sync_with_base_branch

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    current_branch = GitUtils.get_current_branch(tmp_path)

    # Mock: fetch succeeds, branch is behind, merge fails with conflict
    with patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'commits_behind', return_value=1), \
         patch('devflow.cli.commands.open_command.Confirm.ask', return_value=True), \
         patch('rich.prompt.Prompt.ask', return_value='m'), \
         patch.object(GitUtils, 'merge_branch', return_value=False) as mock_merge:

        # PROJ-60408: Should return False on merge conflict
        result = _check_and_sync_with_base_branch(str(tmp_path), current_branch, "main", "test-session")

        assert result is False, "Should return False when merge fails"
        mock_merge.assert_called_once()


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_check_and_sync_with_base_branch_rebase_conflict(tmp_path):
    """Test PROJ-60408: _check_and_sync_with_base_branch returns False on rebase conflict."""
    from devflow.cli.commands.open_command import _check_and_sync_with_base_branch

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    current_branch = GitUtils.get_current_branch(tmp_path)

    # Mock: fetch succeeds, branch is behind, rebase fails with conflict
    with patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'commits_behind', return_value=2), \
         patch('devflow.cli.commands.open_command.Confirm.ask', return_value=True), \
         patch('rich.prompt.Prompt.ask', return_value='r'), \
         patch.object(GitUtils, 'rebase_branch', return_value=False) as mock_rebase:

        # PROJ-60408: Should return False on rebase conflict
        result = _check_and_sync_with_base_branch(str(tmp_path), current_branch, "main", "test-session")

        assert result is False, "Should return False when rebase fails"
        mock_rebase.assert_called_once()


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_check_and_sync_with_base_branch_fetch_fails(tmp_path):
    """Test _check_and_sync_with_base_branch when fetch fails."""
    from devflow.cli.commands.open_command import _check_and_sync_with_base_branch

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

    # Mock: fetch fails
    with patch.object(GitUtils, 'fetch_origin', return_value=False), \
         patch.object(GitUtils, 'commits_behind') as mock_commits:

        _check_and_sync_with_base_branch(str(tmp_path), "feature", "main", "test-session")

        # Should skip check if fetch fails
        mock_commits.assert_not_called()


# Tests for PROJ-59839: Auto-detect working directory for multi-conversation sessions


def test_detect_working_directory_from_cwd_git_repo_in_workspace(tmp_path, temp_daf_home):
    """Test _detect_working_directory_from_cwd detects git repo within workspace."""
    from devflow.cli.commands.open_command import _detect_working_directory_from_cwd
    from devflow.config.loader import ConfigLoader

    # Create workspace structure
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo_dir = workspace / "backend-api"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)

    # Create config with workspace
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    if config:
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(workspace))

        ]
        config_loader.save_config(config)

    # Detect from within repo
    detected = _detect_working_directory_from_cwd(repo_dir, config_loader)

    assert detected == "backend-api"


def test_detect_working_directory_from_cwd_not_git_repo(tmp_path, temp_daf_home):
    """Test _detect_working_directory_from_cwd returns None for non-git directory."""
    from devflow.cli.commands.open_command import _detect_working_directory_from_cwd
    from devflow.config.loader import ConfigLoader

    # Create directory but don't initialize git
    non_git_dir = tmp_path / "not-a-repo"
    non_git_dir.mkdir()

    config_loader = ConfigLoader()

    # Should return None for non-git directory
    detected = _detect_working_directory_from_cwd(non_git_dir, config_loader)

    assert detected is None


def test_detect_working_directory_from_cwd_git_repo_outside_workspace(tmp_path, temp_daf_home):
    """Test _detect_working_directory_from_cwd detects git repo outside workspace."""
    from devflow.cli.commands.open_command import _detect_working_directory_from_cwd
    from devflow.config.loader import ConfigLoader

    # Create repo outside workspace
    repo_dir = tmp_path / "standalone-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)

    # Create config with different workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    if config:
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(workspace))

        ]
        config_loader.save_config(config)

    # Detect from repo outside workspace
    detected = _detect_working_directory_from_cwd(repo_dir, config_loader)

    # Should use directory name
    assert detected == "standalone-repo"


def test_handle_conversation_selection_create_new(tmp_path, temp_daf_home, monkeypatch):
    """Test _handle_conversation_selection creates new conversation when user selects 'n'."""
    from devflow.cli.commands.open_command import _handle_conversation_selection
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create session with existing conversation
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    repo1_dir = tmp_path / "backend-api"
    repo1_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo1_dir, capture_output=True)

    session = session_manager.create_session(
        name="PROJ-12345",
        goal="Test multi-repo",
        working_directory="backend-api",
        project_path=str(repo1_dir),
        ai_agent_session_id="uuid-1",
    )

    # Now try to open in different repo
    repo2_dir = tmp_path / "frontend-app"
    repo2_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo2_dir, capture_output=True)

    # Mock user input: 'n' to create new conversation
    monkeypatch.setattr('rich.prompt.Prompt.ask', lambda *args, **kwargs: 'n')

    # Mock template manager to avoid actual template creation
    with patch('devflow.templates.manager.TemplateManager'):
        result = _handle_conversation_selection(
            session,
            "frontend-app",
            repo2_dir,
            session_manager,
            config_loader
        )

    assert result is True
    assert session.working_directory == "frontend-app"
    assert "frontend-app" in session.conversations
    assert session.conversations["frontend-app"].active_session.project_path == str(repo2_dir.absolute())


def test_handle_conversation_selection_select_existing(tmp_path, temp_daf_home, monkeypatch):
    """Test _handle_conversation_selection selects existing conversation when user picks number."""
    from devflow.cli.commands.open_command import _handle_conversation_selection
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create session with multiple conversations
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    repo1_dir = tmp_path / "backend-api"
    repo1_dir.mkdir()
    repo2_dir = tmp_path / "frontend-app"
    repo2_dir.mkdir()

    session = session_manager.create_session(
        name="PROJ-12345",
        goal="Test multi-repo",
        working_directory="backend-api",
        project_path=str(repo1_dir),
        ai_agent_session_id="uuid-1",
    )

    # Add second conversation manually
    session.add_conversation(
        working_dir="frontend-app",
        ai_agent_session_id="uuid-2",
        project_path=str(repo2_dir),
        branch="feature/test"
    )
    session_manager.update_session(session)

    # Try to open in third repo
    repo3_dir = tmp_path / "docs-repo"
    repo3_dir.mkdir()

    # Mock user input: '1' to select first conversation
    monkeypatch.setattr('rich.prompt.Prompt.ask', lambda *args, **kwargs: '1')

    result = _handle_conversation_selection(
        session,
        "docs-repo",
        repo3_dir,
        session_manager,
        config_loader
    )

    assert result is True
    assert session.working_directory == "backend-api"


def test_handle_conversation_selection_user_cancels(tmp_path, temp_daf_home, monkeypatch):
    """Test _handle_conversation_selection returns False when user cancels."""
    from devflow.cli.commands.open_command import _handle_conversation_selection
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    repo_dir = tmp_path / "backend-api"
    repo_dir.mkdir()

    session = session_manager.create_session(
        name="PROJ-12345",
        goal="Test",
        working_directory="backend-api",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-1",
    )

    # Mock user input: 'c' to cancel
    monkeypatch.setattr('rich.prompt.Prompt.ask', lambda *args, **kwargs: 'c')

    result = _handle_conversation_selection(
        session,
        "other-repo",
        tmp_path / "other-repo",
        session_manager,
        config_loader
    )

    assert result is False


def test_create_conversation_for_current_directory(tmp_path, temp_daf_home):
    """Test _create_conversation_for_current_directory creates conversation correctly."""
    from devflow.cli.commands.open_command import _create_conversation_for_current_directory
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session
    repo1_dir = tmp_path / "backend-api"
    repo1_dir.mkdir()

    session = session_manager.create_session(
        name="PROJ-12345",
        goal="Test",
        working_directory="backend-api",
        project_path=str(repo1_dir),
        ai_agent_session_id="uuid-1",
    )

    # Create conversation for new directory
    repo2_dir = tmp_path / "frontend-app"
    repo2_dir.mkdir()

    # Mock template manager to avoid actual template creation
    with patch('devflow.templates.manager.TemplateManager'):
        result = _create_conversation_for_current_directory(
            session,
            "frontend-app",
            repo2_dir,
            session_manager,
            config_loader
        )

    assert result is True
    assert "frontend-app" in session.conversations
    conversation = session.conversations["frontend-app"]
    assert conversation.active_session.project_path == str(repo2_dir.absolute())
    assert conversation.active_session.ai_agent_session_id is not None
    assert conversation.active_session.branch == ""  # Empty initially
    assert session.working_directory == "frontend-app"


def test_open_session_auto_detects_existing_conversation(tmp_path, temp_daf_home):
    """Test that _detect_working_directory_from_cwd and conversation switching works correctly."""
    from devflow.cli.commands.open_command import _detect_working_directory_from_cwd
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create workspace with two repos
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo1_dir = workspace / "backend-api"
    repo1_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo1_dir, capture_output=True)

    repo2_dir = workspace / "frontend-app"
    repo2_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo2_dir, capture_output=True)

    # Configure workspace
    config = config_loader.load_config()
    if config:
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(workspace))

        ]
        config_loader.save_config(config)

    # Create session with conversation for backend-api
    session = session_manager.create_session(
        name="PROJ-12345",
        goal="Test multi-repo",
        working_directory="backend-api",
        project_path=str(repo1_dir),
        ai_agent_session_id="uuid-backend",
    )

    # Add conversation for frontend-app
    session.add_conversation(
        working_dir="frontend-app",
        ai_agent_session_id="uuid-frontend",
        project_path=str(repo2_dir),
        branch="feature/test"
    )
    session_manager.update_session(session)

    # Test detection from frontend-app directory
    detected_repo_name = _detect_working_directory_from_cwd(repo2_dir, config_loader)
    assert detected_repo_name == "frontend-app"

    # Verify conversation exists for detected repo
    existing_conversation = session.get_conversation("frontend-app")
    assert existing_conversation is not None
    assert existing_conversation.project_path == str(repo2_dir)

    # Test switching working directory
    session.working_directory = "frontend-app"
    session_manager.update_session(session)

    # Verify the session switched
    updated_session = session_manager.get_session("PROJ-12345")
    assert updated_session.working_directory == "frontend-app"
    updated_active_conv = updated_session.active_conversation
    assert updated_active_conv is not None
    assert updated_active_conv.ai_agent_session_id == "uuid-frontend"


def test_open_session_prompts_for_new_conversation_in_different_repo(tmp_path, temp_daf_home):
    """Test _create_conversation_for_current_directory creates conversation for new repository."""
    from devflow.cli.commands.open_command import _detect_working_directory_from_cwd, _create_conversation_for_current_directory
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create workspace with two repos
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo1_dir = workspace / "backend-api"
    repo1_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo1_dir, capture_output=True)

    repo2_dir = workspace / "docs-repo"
    repo2_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo2_dir, capture_output=True)

    # Configure workspace
    config = config_loader.load_config()
    if config:
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(workspace))

        ]
        config_loader.save_config(config)

    # Create session with only backend-api conversation
    session = session_manager.create_session(
        name="PROJ-12345",
        goal="Test multi-repo",
        working_directory="backend-api",
        project_path=str(repo1_dir),
        ai_agent_session_id="uuid-backend",
    )

    # Test detection from docs-repo directory
    detected_repo_name = _detect_working_directory_from_cwd(repo2_dir, config_loader)
    assert detected_repo_name == "docs-repo"

    # Verify conversation does NOT exist
    existing_conversation = session.get_conversation("docs-repo")
    assert existing_conversation is None

    # Create new conversation for detected repo
    with patch('devflow.templates.manager.TemplateManager'):
        result = _create_conversation_for_current_directory(
            session,
            "docs-repo",
            repo2_dir,
            session_manager,
            config_loader
        )

    assert result is True
    assert "docs-repo" in session.conversations
    assert session.working_directory == "docs-repo"

    # Verify new conversation was created correctly
    updated_session = session_manager.get_session("PROJ-12345")
    assert "docs-repo" in updated_session.conversations
    docs_conv = updated_session.conversations["docs-repo"]
    assert docs_conv.active_session.project_path == str(repo2_dir.absolute())
    assert docs_conv.active_session.ai_agent_session_id is not None


def test_prompt_for_complete_on_exit_with_config_true(temp_daf_home, monkeypatch):
    """Test auto-complete on exit when configured to always run."""
    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
    from devflow.config.models import Config, PromptsConfig

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create test session
    session = session_manager.create_session(
        name="test-session",
        goal="Test auto-complete",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Create a minimal config with auto_complete_on_exit=True
    from devflow.config.models import JiraConfig, RepoConfig, PromptsConfig, Config
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", user="test", transitions={}),
        repos=RepoConfig(workspace="/tmp/workspace"),
        prompts=PromptsConfig(auto_complete_on_exit=True)
    )

    # Mock complete_session to track if it was called
    complete_called = []
    def mock_complete(identifier, status, attach_to_issue, latest):
        complete_called.append(identifier)

    monkeypatch.setattr('devflow.cli.commands.complete_command.complete_session', mock_complete)

    # Call the function
    _prompt_for_complete_on_exit(session, config)

    # Verify complete_session was called
    assert len(complete_called) == 1
    assert complete_called[0] == "test-session"


def test_prompt_for_complete_on_exit_with_config_false(temp_daf_home, monkeypatch):
    """Test auto-complete on exit when configured to never run."""
    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
    from devflow.config.models import Config, PromptsConfig

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create test session
    session = session_manager.create_session(
        name="test-session",
        goal="Test auto-complete",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Create a minimal config with auto_complete_on_exit=False
    from devflow.config.models import JiraConfig, RepoConfig, PromptsConfig, Config
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", user="test", transitions={}),
        repos=RepoConfig(workspace="/tmp/workspace"),
        prompts=PromptsConfig(auto_complete_on_exit=False)
    )

    # Mock complete_session to track if it was called
    complete_called = []
    def mock_complete(identifier, status, attach_to_issue, latest):
        complete_called.append(identifier)

    monkeypatch.setattr('devflow.cli.commands.complete_command.complete_session', mock_complete)

    # Call the function
    _prompt_for_complete_on_exit(session, config)

    # Verify complete_session was NOT called
    assert len(complete_called) == 0


def test_prompt_for_complete_on_exit_with_user_confirms(temp_daf_home, monkeypatch):
    """Test auto-complete on exit when user confirms the prompt."""
    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create test session
    session = session_manager.create_session(
        name="test-session",
        goal="Test auto-complete",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Create a minimal config with auto_complete_on_exit=None (prompt mode)
    from devflow.config.models import JiraConfig, RepoConfig, PromptsConfig, Config
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", user="test", transitions={}),
        repos=RepoConfig(workspace="/tmp/workspace"),
        prompts=PromptsConfig(auto_complete_on_exit=None)
    )

    # Mock Confirm.ask to return True (user confirms)
    def mock_confirm(prompt, default):
        return True

    monkeypatch.setattr('devflow.cli.commands.open_command.Confirm.ask', mock_confirm)

    # Mock complete_session to track if it was called
    complete_called = []
    def mock_complete(identifier, status, attach_to_issue, latest):
        complete_called.append(identifier)

    monkeypatch.setattr('devflow.cli.commands.complete_command.complete_session', mock_complete)

    # Call the function
    _prompt_for_complete_on_exit(session, config)

    # Verify complete_session was called
    assert len(complete_called) == 1
    assert complete_called[0] == "test-session"


def test_prompt_for_complete_on_exit_with_user_declines(temp_daf_home, monkeypatch):
    """Test auto-complete on exit when user declines the prompt."""
    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create test session
    session = session_manager.create_session(
        name="test-session",
        goal="Test auto-complete",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Create a minimal config with auto_complete_on_exit=None (prompt mode)
    from devflow.config.models import JiraConfig, RepoConfig, PromptsConfig, Config
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", user="test", transitions={}),
        repos=RepoConfig(workspace="/tmp/workspace"),
        prompts=PromptsConfig(auto_complete_on_exit=None)
    )

    # Mock Confirm.ask to return False (user declines)
    def mock_confirm(prompt, default):
        return False

    monkeypatch.setattr('devflow.cli.commands.open_command.Confirm.ask', mock_confirm)

    # Mock complete_session to track if it was called
    complete_called = []
    def mock_complete(identifier, status, attach_to_issue, latest):
        complete_called.append(identifier)

    monkeypatch.setattr('devflow.cli.commands.complete_command.complete_session', mock_complete)

    # Call the function
    _prompt_for_complete_on_exit(session, config)

    # Verify complete_session was NOT called
    assert len(complete_called) == 0


def test_prompt_for_complete_on_exit_handles_exception(temp_daf_home, monkeypatch):
    """Test auto-complete on exit handles exceptions gracefully."""
    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create test session
    session = session_manager.create_session(
        name="test-session",
        goal="Test auto-complete",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Create a minimal config with auto_complete_on_exit=True
    from devflow.config.models import JiraConfig, RepoConfig, PromptsConfig, Config
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", user="test", transitions={}),
        repos=RepoConfig(workspace="/tmp/workspace"),
        prompts=PromptsConfig(auto_complete_on_exit=True)
    )

    # Mock complete_session to raise an exception
    def mock_complete_raises(identifier, status, attach_to_issue, latest):
        raise RuntimeError("Test exception")

    monkeypatch.setattr('devflow.cli.commands.complete_command.complete_session', mock_complete_raises)

    # Call the function - should not raise, but handle exception gracefully
    _prompt_for_complete_on_exit(session, config)


def test_temp_directory_conversation_file_persistence(temp_daf_home, monkeypatch, tmp_path):
    """Test that conversation files are preserved when reopening temp directory sessions (PROJ-60881).

    This test verifies the fix for PROJ-60881 where reopening a daf jira new session
    would generate a new session ID instead of resuming the existing conversation.
    """
    from devflow.session.capture import SessionCapture
    import tempfile

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a temp directory to simulate the initial session
    old_temp_dir = tmp_path / "old-temp-dir"
    old_temp_dir.mkdir()

    # Create a session with temp_directory (simulating daf jira new)
    session_id = "test-uuid-12345"
    session = session_manager.create_session(
        name="test-ticket-creation",
        goal="Test ticket creation",
        working_directory="test-repo",
        project_path=str(old_temp_dir),
        ai_agent_session_id=session_id,
    )

    # Set session_type, temp_directory and original_project_path
    session.session_type = "ticket_creation"
    conv = session.active_conversation
    conv.temp_directory = str(old_temp_dir)
    conv.original_project_path = str(tmp_path / "original-repo")
    session_manager.update_session(session)

    # Create a conversation file at the STABLE location (based on original_project_path)
    # This is where conversation files are stored for ticket_creation sessions (PROJ-61161)
    capture = SessionCapture()
    original_repo_path = tmp_path / "original-repo"
    stable_session_dir = capture.get_session_dir(str(original_repo_path))
    stable_session_dir.mkdir(parents=True, exist_ok=True)
    stable_conversation_file = stable_session_dir / f"{session_id}.jsonl"
    conversation_content = '{"type":"test","content":"Previous conversation"}\n{"type":"test","content":"More history"}\n'
    stable_conversation_file.write_text(conversation_content)

    # Verify conversation file exists at stable location
    assert stable_conversation_file.exists()
    assert stable_conversation_file.stat().st_size > 0

    # Mock GitUtils to return a fake remote URL and simulate successful clone
    def mock_get_remote_url(path):
        return "https://git.example.com/test/repo.git"

    def mock_clone_repository(url, path, branch=None):
        # Create a minimal git repo structure
        path.mkdir(parents=True, exist_ok=True)
        (path / ".git").mkdir(exist_ok=True)
        return True

    def mock_get_default_branch(path):
        return "main"

    monkeypatch.setattr(GitUtils, "get_remote_url", mock_get_remote_url)
    monkeypatch.setattr(GitUtils, "clone_repository", mock_clone_repository)
    monkeypatch.setattr(GitUtils, "get_default_branch", mock_get_default_branch)

    # Mock tempfile.mkdtemp to return a predictable path
    new_temp_dir = tmp_path / "new-temp-dir"
    def mock_mkdtemp(prefix=""):
        new_temp_dir.mkdir(exist_ok=True)
        return str(new_temp_dir)

    monkeypatch.setattr(tempfile, "mkdtemp", mock_mkdtemp)

    # Mock subprocess.run to avoid actually launching Claude
    def mock_subprocess_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0)

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    # Mock console.print to avoid output during test
    def mock_console_print(*args, **kwargs):
        pass

    import devflow.cli.commands.open_command as open_cmd
    monkeypatch.setattr(open_cmd.console, "print", mock_console_print)

    # Import the handler function
    from devflow.cli.commands.open_command import _handle_temp_directory_for_ticket_creation

    # Reload the session to trigger auto-migration
    session = session_manager.get_session("test-ticket-creation")

    # Call the handler (this simulates what happens in daf open)
    _handle_temp_directory_for_ticket_creation(session, session_manager)

    # Verify:
    # 1. Session project_path was updated to new temp directory
    reloaded_session = session_manager.get_session("test-ticket-creation")
    reloaded_active_conv = reloaded_session.active_conversation
    assert reloaded_active_conv is not None
    assert reloaded_active_conv.project_path == str(new_temp_dir)

    # 2. Conversation file exists in new temp directory
    new_session_dir = capture.get_session_dir(str(new_temp_dir))
    new_conversation_file = new_session_dir / f"{session_id}.jsonl"
    assert new_conversation_file.exists(), "Conversation file should exist in new temp directory"
    assert new_conversation_file.stat().st_size > 0, "Conversation file should not be empty"

    # 3. Conversation content was preserved
    new_content = new_conversation_file.read_text()
    assert new_content == conversation_content, "Conversation history should be preserved"

    # 4. Session ID was NOT changed (this is the key fix for PROJ-60881)
    assert reloaded_active_conv.ai_agent_session_id == session_id, "Session ID should not change"


def test_temp_directory_conversation_file_persistence_when_temp_dir_deleted(temp_daf_home, monkeypatch, tmp_path):
    """Test that conversation files are preserved even when temp directory is deleted (PROJ-60881).

    This test verifies that conversation history is preserved even when the temp directory
    itself has been deleted (e.g., by system cleanup). The conversation file is stored in
    ~/.claude/projects/<encoded-path>/ which persists independently of the temp directory.
    """
    from devflow.session.capture import SessionCapture
    import tempfile

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a temp directory to simulate the initial session
    old_temp_dir = tmp_path / "old-temp-dir"
    old_temp_dir.mkdir()

    # Create a session with temp_directory (simulating daf jira new)
    session_id = "test-uuid-67890"
    session = session_manager.create_session(
        name="test-deleted-temp-dir",
        goal="Test with deleted temp dir",
        working_directory="test-repo",
        project_path=str(old_temp_dir),
        ai_agent_session_id=session_id,
    )

    # Set session_type, temp_directory and original_project_path
    session.session_type = "ticket_creation"
    conv = session.active_conversation
    conv.temp_directory = str(old_temp_dir)
    conv.original_project_path = str(tmp_path / "original-repo")
    session_manager.update_session(session)

    # Create a conversation file at the STABLE location (based on original_project_path)
    # This is where conversation files are stored for ticket_creation sessions (PROJ-61161)
    # The conversation file persists independently of the temp directory
    capture = SessionCapture()
    original_repo_path = tmp_path / "original-repo"
    stable_session_dir = capture.get_session_dir(str(original_repo_path))
    stable_session_dir.mkdir(parents=True, exist_ok=True)
    stable_conversation_file = stable_session_dir / f"{session_id}.jsonl"
    conversation_content = '{"type":"test","content":"History from deleted temp dir"}\n'
    stable_conversation_file.write_text(conversation_content)

    # Verify conversation file exists at stable location
    assert stable_conversation_file.exists()

    # NOW DELETE THE TEMP DIRECTORY (simulating system cleanup)
    # The conversation file should still exist at the stable location (NOT tied to temp dir)
    shutil.rmtree(old_temp_dir)
    assert not old_temp_dir.exists(), "Temp directory should be deleted"
    assert stable_conversation_file.exists(), "Conversation file should still exist at stable location"

    # Mock GitUtils to return a fake remote URL and simulate successful clone
    def mock_get_remote_url(path):
        return "https://git.example.com/test/repo.git"

    def mock_clone_repository(url, path, branch=None):
        path.mkdir(parents=True, exist_ok=True)
        (path / ".git").mkdir(exist_ok=True)
        return True

    def mock_get_default_branch(path):
        return "main"

    monkeypatch.setattr(GitUtils, "get_remote_url", mock_get_remote_url)
    monkeypatch.setattr(GitUtils, "clone_repository", mock_clone_repository)
    monkeypatch.setattr(GitUtils, "get_default_branch", mock_get_default_branch)

    # Mock tempfile.mkdtemp to return a predictable path
    new_temp_dir = tmp_path / "new-temp-dir"
    def mock_mkdtemp(prefix=""):
        new_temp_dir.mkdir(exist_ok=True)
        return str(new_temp_dir)

    monkeypatch.setattr(tempfile, "mkdtemp", mock_mkdtemp)

    # Mock subprocess.run to avoid actually launching Claude
    def mock_subprocess_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0)

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    # Mock console.print to avoid output during test
    def mock_console_print(*args, **kwargs):
        pass

    import devflow.cli.commands.open_command as open_cmd
    monkeypatch.setattr(open_cmd.console, "print", mock_console_print)

    # Import the handler function
    from devflow.cli.commands.open_command import _handle_temp_directory_for_ticket_creation

    # Reload the session
    session = session_manager.get_session("test-deleted-temp-dir")

    # Call the handler (this simulates what happens in daf open)
    _handle_temp_directory_for_ticket_creation(session, session_manager)

    # Verify:
    # 1. Conversation file was backed up and restored even though temp dir was deleted
    new_session_dir = capture.get_session_dir(str(new_temp_dir))
    new_conversation_file = new_session_dir / f"{session_id}.jsonl"
    assert new_conversation_file.exists(), "Conversation file should exist in new temp directory"
    assert new_conversation_file.stat().st_size > 0, "Conversation file should not be empty"

    # 2. Conversation content was preserved
    new_content = new_conversation_file.read_text()
    assert new_content == conversation_content, "Conversation history should be preserved"

    # 3. Session ID was NOT changed
    reloaded_session = session_manager.get_session("test-deleted-temp-dir")
    reloaded_active_conv = reloaded_session.active_conversation
    assert reloaded_active_conv is not None
    assert reloaded_active_conv.ai_agent_session_id == session_id, "Session ID should not change"


def test_set_terminal_title_with_issue_key(temp_daf_home, capsys):
    """Test terminal title setting with issue key."""
    from devflow.cli.commands.open_command import _set_terminal_title
    from devflow.config.models import Session

    # Create a mock session with issue key
    session = Session(
        name="test-session",
        issue_key="PROJ-12345",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",        ai_agent_session_id="test-uuid",
    )

    # Call the function
    _set_terminal_title(session)

    # Capture stdout
    captured = capsys.readouterr()

    # Verify ANSI escape sequence was output
    expected_title = "PROJ-12345: test-session"
    expected_sequence = f"\033]0;{expected_title}\007"
    assert expected_sequence in captured.out, f"Expected ANSI sequence not found. Got: {repr(captured.out)}"


def test_set_terminal_title_without_issue_key(temp_daf_home, capsys):
    """Test terminal title setting without issue key."""
    from devflow.cli.commands.open_command import _set_terminal_title
    from devflow.config.models import Session

    # Create a mock session without issue key
    session = Session(
        name="test-session-no-jira",
        issue_key=None,
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",        ai_agent_session_id="test-uuid-2",
    )

    # Call the function
    _set_terminal_title(session)

    # Capture stdout
    captured = capsys.readouterr()

    # Verify ANSI escape sequence was output
    expected_title = "test-session-no-jira"
    expected_sequence = f"\033]0;{expected_title}\007"
    assert expected_sequence in captured.out, f"Expected ANSI sequence not found. Got: {repr(captured.out)}"


def test_open_skips_ticket_creation_session_when_searching_by_issue_key(temp_daf_home):
    """Test that daf open PROJ-12345 does not match creation-PROJ-12345.

    When searching by issue key (e.g., PROJ-12345), daf open should:
    1. Not match ticket_creation sessions (creation-PROJ-12345)
    2. Display helpful message about the creation session
    3. Tell user to use 'daf sync' to create a development session
    4. NOT try to create a new session automatically
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session (like what daf jira open creates)
    session = session_manager.create_session(
        name="creation-PROJ-12345",
        goal="PROJ-12345: Test ticket",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
        issue_key="PROJ-12345",
    )
    session.session_type = "ticket_creation"
    session_manager.update_session(session)

    runner = CliRunner()
    # Try to open by issue key (should NOT match the creation session)
    result = runner.invoke(cli, ["open", "PROJ-12345"])

    # Should NOT open the creation session
    # Should display message about no development session found
    assert "No development session found" in result.output
    # Should mention the creation session exists
    assert "creation-PROJ-12345" in result.output
    # Should tell user to use daf sync
    assert "daf sync" in result.output
    # Should NOT try to validate the issue tracker ticket or create a new session
    assert "issue tracker ticket validated" not in result.output
    assert "creating session" not in result.output.lower()


def test_open_allows_explicit_creation_session_by_full_name(temp_daf_home):
    """Test that daf open creation-PROJ-12345 still works correctly.

    When explicitly opening by the full name (creation-PROJ-12345),
    the session should open normally.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session
    session = session_manager.create_session(
        name="creation-PROJ-12345",
        goal="PROJ-12345: Test ticket",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
        issue_key="PROJ-12345",
    )
    session.session_type = "ticket_creation"
    session_manager.update_session(session)

    runner = CliRunner()
    # Mock auto-detection to avoid triggering new conversation prompt
    with patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None):
        # Try to open by FULL NAME (should work)
        result = runner.invoke(cli, ["open", "creation-PROJ-12345"], input="n\n")

    # Should successfully find the session
    assert result.exit_code == 0
    assert "creation-PROJ-12345" in result.output
    # Should NOT show "not found" error
    assert "No development session found" not in result.output


def test_jira_open_uses_full_session_name_to_avoid_loop(temp_daf_home):
    """Test that daf open PROJ-99999 doesn't create a new session when ticket_creation session exists.

    When a ticket_creation session exists (creation-PROJ-99999):
    1. open_command rejects ticket_creation session when searching by issue key
    2. Shows message telling user to use 'daf sync'
    3. Does NOT call jira_open_session or try to create a new session
    4. Exits cleanly without infinite loop
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session
    session = session_manager.create_session(
        name="creation-PROJ-99999",
        goal="PROJ-99999: Test ticket",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
        issue_key="PROJ-99999",
    )
    session.session_type = "ticket_creation"
    session_manager.update_session(session)

    # Use CliRunner to test the full command flow
    runner = CliRunner()
    result = runner.invoke(cli, ["open", "PROJ-99999"])

    # Verify no infinite loop occurred
    # Should show message about no development session
    assert "No development session found" in result.output
    assert "creation-PROJ-99999" in result.output
    # Should tell user to use daf sync
    assert "daf sync" in result.output
    # Should NOT try to create a new session
    assert "issue tracker ticket validated" not in result.output
    # Should exit with error code (session not found)
    assert result.exit_code == 1


def test_handle_branch_creation_with_uncommitted_changes_cancel(tmp_path):
    """Test that uncommitted changes warning allows user to cancel branch creation."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create uncommitted changes
    (tmp_path / "test.txt").write_text("modified")
    (tmp_path / "new_file.txt").write_text("new content")

    # Mock Confirm.ask to simulate user saying "No" (don't continue)
    with patch('devflow.cli.commands.new_command.Confirm.ask', return_value=False) as mock_confirm:
        # Call function
        branch = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=False
        )

        # Verify the function returned False (explicitly cancelled)
        assert branch is False

        # Verify Confirm.ask was called (asking to continue despite uncommitted changes)
        mock_confirm.assert_called_once()
        call_args = mock_confirm.call_args
        assert "Continue anyway?" in call_args[0][0]


def test_handle_branch_creation_with_uncommitted_changes_continue(tmp_path):
    """Test that uncommitted changes warning allows user to continue anyway."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create uncommitted changes
    (tmp_path / "test.txt").write_text("modified")

    # Create a mock config with default_branch_strategy to avoid Prompt.ask
    from unittest.mock import Mock
    mock_config = Mock()
    mock_config.prompts = Mock()
    mock_config.prompts.default_branch_strategy = "from_default"

    # Mock git operations and Confirm.ask
    # First call: Continue despite uncommitted changes? -> Yes
    # Second call: Create git branch for this session? -> Yes
    with patch('devflow.cli.commands.new_command.Confirm.ask', side_effect=[True, True]) as mock_confirm, \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'get_default_branch', return_value='main'), \
         patch.object(GitUtils, 'checkout_branch', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True), \
         patch.object(GitUtils, 'create_branch', return_value=True):

        # Call function with mock config
        branch = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=False,
            config=mock_config
        )

        # Verify a branch name was returned (user continued)
        assert branch is not None
        assert "proj-12345" in branch.lower()

        # Verify Confirm.ask was called twice
        assert mock_confirm.call_count == 2


def test_handle_branch_creation_no_uncommitted_changes(tmp_path):
    """Test that no warning is shown when there are no uncommitted changes."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit (clean working directory)
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create a mock config with default_branch_strategy to avoid Prompt.ask
    from unittest.mock import Mock
    mock_config = Mock()
    mock_config.prompts = Mock()
    mock_config.prompts.default_branch_strategy = "from_default"

    # Mock git operations and Confirm.ask to simulate user saying "Yes" to creating branch
    with patch('devflow.cli.commands.new_command.Confirm.ask', return_value=True) as mock_confirm, \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'get_default_branch', return_value='main'), \
         patch.object(GitUtils, 'checkout_branch', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True), \
         patch.object(GitUtils, 'create_branch', return_value=True):

        # Call function with mock config
        branch = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=False,
            config=mock_config
        )

        # Verify a branch was created
        assert branch is not None

        # Verify Confirm.ask was called only once (for "Create git branch?")
        # NOT for "Continue anyway?" since there are no uncommitted changes
        assert mock_confirm.call_count == 1
        call_args = mock_confirm.call_args
        assert "Create git branch for this session?" in call_args[0][0]


def test_handle_branch_creation_uncommitted_changes_auto_mode(tmp_path):
    """Test that auto mode proceeds with warning when there are uncommitted changes."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create uncommitted changes
    (tmp_path / "test.txt").write_text("modified")

    # Mock git operations for auto mode
    with patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'get_default_branch', return_value='main'), \
         patch.object(GitUtils, 'checkout_branch', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True), \
         patch.object(GitUtils, 'create_branch', return_value=True):

        # Call with auto_from_default=True (should NOT ask to continue)
        branch = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=True
        )

        # Verify branch was created (auto mode doesn't ask, just proceeds with warning)
        assert branch is not None


