"""Tests for daf jira open command.

This test file verifies that `daf jira open` correctly prompts to clone
repositories to temporary directories for clean analysis, matching the
behavior of `daf jira new`.
"""

import os
import subprocess
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock git repository for testing."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Create initial commit
    (repo_path / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    return repo_path


def test_jira_open_prompts_to_clone_to_temp_directory(temp_daf_home, mock_git_repo):
    """Test that `daf jira open` prompts to clone repository to temporary directory.

    This is the main test for PROJ-62987. Verifies that:
    1. Command checks if current directory is a git repository
    2. Prompts user to clone to temp directory for clean analysis
    3. Stores temp_directory and original_project_path in session metadata
    4. Session type is set to "ticket_creation"
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    runner = CliRunner()

    # Mock JIRA client and ticket validation
    mock_ticket = {
        "key": "PROJ-99999",
        "summary": "Test ticket for cloning",
        "type": "Story",
        "status": "New",
    }

    temp_dir = "/tmp/test-jira-open-temp"

    with patch("devflow.jira.JiraClient") as mock_jira_class, \
         patch("devflow.jira.utils.validate_jira_ticket") as mock_validate, \
         patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
         patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
         patch("tempfile.mkdtemp", return_value=temp_dir), \
         patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
         patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value="main"), \
         patch("devflow.utils.temp_directory.GitUtils.get_current_branch", return_value="main"), \
         patch("devflow.utils.temp_directory.GitUtils.is_git_repository", return_value=True), \
         patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False):

        # Setup JIRA mock
        mock_validate.return_value = mock_ticket

        # Run command (Path.cwd() will be mocked to return mock_git_repo)
        with patch("pathlib.Path.cwd", return_value=mock_git_repo):
            result = runner.invoke(cli, ["jira", "open", "PROJ-99999"], catch_exceptions=False)

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

        # Verify the output indicates cloning was prompted
        assert "Clone project in a temporary directory" in result.output or "Using temporary clone" in result.output, \
            f"Expected clone prompt in output. Got:\n{result.output}"

        # Verify session was created with correct metadata
        session_manager = SessionManager(config_loader)
        session = session_manager.get_session("creation-PROJ-99999")

        assert session is not None, "Session should be created"
        assert session.session_type == "ticket_creation", "Session type should be ticket_creation"
        assert session.issue_key == "PROJ-99999", "issue key should be set"

        # Verify temp directory metadata is stored
        if session.active_conversation:
            # Use 'in' to handle macOS /tmp -> /private/tmp symlink
            assert temp_dir in session.active_conversation.temp_directory, \
                f"Temp directory should be stored. Expected {temp_dir}, got {session.active_conversation.temp_directory}"
            assert session.active_conversation.original_project_path == str(mock_git_repo.absolute()), \
                "Original project path should be stored"


def test_jira_open_skips_clone_prompt_when_user_declines(temp_daf_home, mock_git_repo):
    """Test that `daf jira open` uses current directory when user declines cloning."""
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    runner = CliRunner()

    mock_ticket = {
        "key": "PROJ-99998",
        "summary": "Test ticket without cloning",
        "type": "Story",
        "status": "New",
    }

    with patch("devflow.jira.JiraClient") as mock_jira_class, \
         patch("devflow.jira.utils.validate_jira_ticket") as mock_validate, \
         patch("devflow.utils.temp_directory.Confirm.ask", return_value=False), \
         patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False):

        # Setup JIRA mock
        mock_validate.return_value = mock_ticket

        with patch("pathlib.Path.cwd", return_value=mock_git_repo):
            result = runner.invoke(cli, ["jira", "open", "PROJ-99998"], catch_exceptions=False)

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

        # Verify the output indicates user declined
        assert "Using current directory" in result.output, \
            f"Expected 'Using current directory' message. Got:\n{result.output}"

        # Verify session was created WITHOUT temp directory metadata
        session_manager = SessionManager(config_loader)
        session = session_manager.get_session("creation-PROJ-99998")

        assert session is not None, "Session should be created"
        assert session.session_type == "ticket_creation", "Session type should be ticket_creation"

        # Verify temp directory is NOT set
        if session.active_conversation:
            assert session.active_conversation.temp_directory is None, \
                "Temp directory should not be set when user declines"


def test_jira_open_skips_clone_prompt_in_json_mode(temp_daf_home, mock_git_repo):
    """Test that `daf jira open --json` skips interactive clone prompt."""
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    runner = CliRunner()

    mock_ticket = {
        "key": "PROJ-99997",
        "summary": "Test ticket for JSON mode",
        "type": "Story",
        "status": "New",
    }

    with patch("devflow.jira.JiraClient") as mock_jira_class, \
         patch("devflow.jira.utils.validate_jira_ticket") as mock_validate, \
         patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False), \
         patch("devflow.cli.commands.jira_open_command.is_json_mode", return_value=True):

        # Setup JIRA mock
        mock_validate.return_value = mock_ticket

        # Patch is_json_mode to return True (simulates --json flag)
        with patch("pathlib.Path.cwd", return_value=mock_git_repo):
            result = runner.invoke(cli, ["jira", "open", "PROJ-99997"], catch_exceptions=False)

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

        # Verify the output indicates non-interactive mode
        assert "Non-interactive mode" in result.output or not ("Clone project" in result.output), \
            f"Should skip clone prompt in JSON mode. Got:\n{result.output}"


def test_jira_open_existing_session_delegates_to_daf_open(temp_daf_home, mock_git_repo):
    """Test that `daf jira open` delegates to `daf open` when session already exists."""
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    # Create existing session with conversation metadata
    session_manager = SessionManager(config_loader)
    session = session_manager.create_session(
        name="creation-PROJ-88888",
        goal="PROJ-88888: Existing ticket",
        working_directory=mock_git_repo.name,
        project_path=str(mock_git_repo),
    )
    session.issue_key = "PROJ-88888"
    session.session_type = "ticket_creation"

    # Add a conversation so it's a complete session
    ai_agent_session_id = str(uuid.uuid4())
    session.add_conversation(
        working_dir=mock_git_repo.name,
        ai_agent_session_id=ai_agent_session_id,
        project_path=str(mock_git_repo),
        branch="main",
        workspace=config.repos.get_default_workspace_path(),
    )

    session_manager.update_session(session)

    runner = CliRunner()

    with patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False), \
         patch("devflow.cli.commands.open_command.check_concurrent_session", return_value=True), \
         patch("pathlib.Path.cwd", return_value=mock_git_repo):
        result = runner.invoke(cli, ["jira", "open", "PROJ-88888"], catch_exceptions=False)

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

        # Verify it found existing ticket creation session
        assert "Found existing ticket creation session" in result.output, \
            f"Expected 'Found existing ticket creation session' message. Got:\n{result.output}"

        # Should NOT create a new session (no "Creating session" message for new creation)
        assert "Creating session: creation-PROJ-88888" not in result.output


def test_jira_open_validates_ticket_before_creating_session(temp_daf_home, mock_git_repo):
    """Test that `daf jira open` validates issue tracker ticket exists before creating session."""
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    runner = CliRunner()

    from devflow.jira.exceptions import JiraNotFoundError

    with patch("devflow.jira.JiraClient") as mock_jira_class, \
         patch("devflow.jira.utils.validate_jira_ticket") as mock_validate:

        # Setup JIRA mock to return None for invalid ticket
        mock_validate.return_value = None

        with patch("pathlib.Path.cwd", return_value=mock_git_repo):
            result = runner.invoke(cli, ["jira", "open", "PROJ-00000"])

        # Verify session was NOT created (the key validation check)
        session_manager = SessionManager(config_loader)
        session = session_manager.get_session("creation-PROJ-00000")
        assert session is None, "Session should not be created for invalid ticket"


def test_jira_open_does_not_transition_ticket_status(temp_daf_home, mock_git_repo):
    """Test that `daf jira open` NEVER transitions issue tracker ticket status.

    This test verifies the fix for PROJ-62995. When reopening an existing session
    via `daf jira open`, the command should:
    1. Find the existing session (creation-PROJ-XXXX with session_type="ticket_creation")
    2. Delegate to `daf open`
    3. Skip JIRA status transition (because session_type is "ticket_creation")

    This prevents unwanted status changes when using `daf jira open` for
    analysis and ticket creation workflows.
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    # Create existing ticket_creation session (as created by daf jira open or daf jira new)
    session_manager = SessionManager(config_loader)
    session = session_manager.create_session(
        name="creation-PROJ-77777",
        goal="PROJ-77777: Ticket creation session",
        working_directory=mock_git_repo.name,
        project_path=str(mock_git_repo),
    )
    session.issue_key = "PROJ-77777"
    session.session_type = "ticket_creation"  # Set as ticket_creation session

    # Add conversation metadata
    ai_agent_session_id = str(uuid.uuid4())
    session.add_conversation(
        working_dir=mock_git_repo.name,
        ai_agent_session_id=ai_agent_session_id,
        project_path=str(mock_git_repo),
        branch="main",
        workspace=config.repos.get_default_workspace_path(),
    )

    session_manager.update_session(session)

    # Verify session_type is set to ticket_creation
    assert session.session_type == "ticket_creation", "Session should have ticket_creation type"

    runner = CliRunner()

    # Mock JIRA client to track if transition is called
    from unittest.mock import call
    mock_jira_instance = MagicMock()
    mock_jira_instance.get_ticket.return_value = {
        "key": "PROJ-77777",
        "status": "New",
        "summary": "Test ticket",
        "type": "Story",
    }

    with patch("devflow.jira.JiraClient", return_value=mock_jira_instance), \
         patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False), \
         patch("devflow.cli.commands.open_command.check_concurrent_session", return_value=True), \
         patch("devflow.cli.commands.open_command.transition_on_start") as mock_transition, \
         patch("pathlib.Path.cwd", return_value=mock_git_repo):

        result = runner.invoke(cli, ["jira", "open", "PROJ-77777"], catch_exceptions=False)

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

        # Verify it found existing ticket creation session
        assert "Found existing ticket creation session" in result.output, \
            f"Expected 'Found existing ticket creation session' message. Got:\n{result.output}"

        # Verify session_type is displayed (not modified)
        assert "Session type: ticket_creation" in result.output, \
            f"Expected session_type display message. Got:\n{result.output}"

        # Verify JIRA transition was NOT called (key assertion for PROJ-62995)
        mock_transition.assert_not_called(), \
            "transition_on_start should not be called for ticket_creation sessions"

        # Verify session_type remains "ticket_creation" (not modified)
        fresh_session_manager = SessionManager(config_loader)
        updated_session = fresh_session_manager.get_session("creation-PROJ-77777")
        assert updated_session is not None, "Session should exist"
        assert updated_session.session_type == "ticket_creation", \
            f"Session type should remain ticket_creation, but got: {updated_session.session_type}"

        # Verify output shows transition was skipped
        assert "Skipping JIRA status transition (session_type: ticket_creation)" in result.output, \
            f"Should show message about skipping transition for ticket_creation. Got:\n{result.output}"


def test_jira_open_reuses_conversation_on_reopen(temp_daf_home, mock_git_repo):
    """Test that `daf jira open` reuses existing conversation UUID on reopen.

    This test verifies the fix for
    1. First open: Creates session with conversation (no UUID initially)
    2. open_session generates UUID and creates conversation file
    3. Second open: Should reuse the same UUID, not generate a new one
    4. Conversation history should be preserved
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    runner = CliRunner()

    # Mock JIRA client and ticket validation
    mock_ticket = {
        "key": "PROJ-66666",
        "summary": "Test conversation reuse on reopen",
        "type": "Story",
        "status": "New",
    }

    temp_dir = "/tmp/test-jira-reopen-temp"

    # FIRST OPEN: Create session and simulate conversation file creation
    with patch("devflow.jira.JiraClient") as mock_jira_class, \
         patch("devflow.jira.utils.validate_jira_ticket") as mock_validate, \
         patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
         patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
         patch("tempfile.mkdtemp", return_value=temp_dir), \
         patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
         patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value="main"), \
         patch("devflow.utils.temp_directory.GitUtils.get_current_branch", return_value="main"), \
         patch("devflow.utils.temp_directory.GitUtils.is_git_repository", return_value=True), \
         patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False):

        # Setup JIRA mock
        mock_validate.return_value = mock_ticket

        # Run first open command
        with patch("pathlib.Path.cwd", return_value=mock_git_repo):
            result = runner.invoke(cli, ["jira", "open", "PROJ-66666"], catch_exceptions=False)

        # Verify first open succeeded
        assert result.exit_code == 0, f"First open failed with output:\n{result.output}"

        # Get session after first open
        session_manager = SessionManager(config_loader)
        session = session_manager.get_session("creation-PROJ-66666")

        assert session is not None, "Session should be created"
        assert session.active_conversation is not None, "Session should have conversation"
        assert session.active_conversation.ai_agent_session_id, "Conversation should have UUID after first open"

        # Store the UUID from first open
        first_open_uuid = session.active_conversation.ai_agent_session_id

        # Simulate conversation file creation at stable location (based on original_project_path)
        from devflow.session.capture import SessionCapture
        capture = SessionCapture()
        stable_session_dir = capture.get_session_dir(session.active_conversation.original_project_path)
        stable_session_dir.mkdir(parents=True, exist_ok=True)
        conversation_file = stable_session_dir / f"{first_open_uuid}.jsonl"
        conversation_file.write_text('{"role": "user", "content": "test message"}\n')

        # Verify conversation file exists
        assert conversation_file.exists(), "Conversation file should be created"
        assert conversation_file.stat().st_size > 0, "Conversation file should not be empty"

    # SECOND OPEN: Reopen session and verify UUID is reused
    with patch("devflow.jira.JiraClient") as mock_jira_class, \
         patch("devflow.jira.utils.validate_jira_ticket") as mock_validate, \
         patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
         patch("tempfile.mkdtemp", return_value="/tmp/test-jira-reopen-temp-2"), \
         patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
         patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value="main"), \
         patch("devflow.utils.temp_directory.GitUtils.get_current_branch", return_value="main"), \
         patch("devflow.utils.temp_directory.GitUtils.is_git_repository", return_value=True), \
         patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False), \
         patch("devflow.cli.commands.open_command.check_concurrent_session", return_value=True):

        # Setup JIRA mock (not needed since session exists, but keep for completeness)
        mock_validate.return_value = mock_ticket

        # Run second open command
        with patch("pathlib.Path.cwd", return_value=mock_git_repo):
            result = runner.invoke(cli, ["jira", "open", "PROJ-66666"], catch_exceptions=False)

        # Verify second open succeeded
        assert result.exit_code == 0, f"Second open failed with output:\n{result.output}"

        # Verify it found existing session
        assert "Found existing ticket creation session" in result.output, \
            f"Should find existing session. Got:\n{result.output}"

        # Get session after second open
        fresh_session_manager = SessionManager(config_loader)
        reopened_session = fresh_session_manager.get_session("creation-PROJ-66666")

        assert reopened_session is not None, "Session should still exist"
        assert reopened_session.active_conversation is not None, "Session should still have conversation"

        # KEY ASSERTION: UUID should be the same (not regenerated)
        second_open_uuid = reopened_session.active_conversation.ai_agent_session_id
        assert second_open_uuid == first_open_uuid, \
            f"UUID should be reused on reopen. First: {first_open_uuid}, Second: {second_open_uuid}"

        # Verify output shows reopening (not first launch)
        assert "Reopening:" in result.output or "Opening:" in result.output, \
            f"Should show reopening message. Got:\n{result.output}"

        # Verify conversation file is still at stable location with original UUID
        assert conversation_file.exists(), "Original conversation file should still exist"
        assert conversation_file.stat().st_size > 0, "Original conversation file should not be empty"


def test_jira_open_reopens_completed_ticket_creation_session(temp_daf_home, mock_git_repo):
    """Test that `daf jira open` reopens a completed ticket_creation session.

    This test verifies that when a ticket_creation session is completed and the user
    runs `daf jira open` again, it should:
    1. Find the existing completed session
    2. Reopen it (not create a new one)
    3. Reuse the same UUID
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    # Create a completed ticket_creation session
    session_manager = SessionManager(config_loader)
    session = session_manager.create_session(
        name="creation-PROJ-55555",
        goal="PROJ-55555: Completed ticket creation session",
        working_directory=mock_git_repo.name,
        project_path=str(mock_git_repo),
    )
    session.issue_key = "PROJ-55555"
    session.session_type = "ticket_creation"
    session.status = "complete"  # Mark as complete

    # Add a conversation with UUID
    original_uuid = str(uuid.uuid4())
    session.add_conversation(
        working_dir=mock_git_repo.name,
        ai_agent_session_id=original_uuid,
        project_path=str(mock_git_repo),
        branch="main",
        workspace=config.repos.get_default_workspace_path(),
    )

    session_manager.update_session(session)

    # Create conversation file so open_command doesn't regenerate UUID
    from devflow.session.capture import SessionCapture
    capture = SessionCapture()
    session_dir = capture.get_session_dir(str(mock_git_repo))
    session_dir.mkdir(parents=True, exist_ok=True)
    conversation_file = session_dir / f"{original_uuid}.jsonl"
    conversation_file.write_text('{"role": "user", "content": "test message"}\n')

    runner = CliRunner()

    # Try to open the completed session via `daf jira open PROJ-55555`
    with patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False), \
         patch("devflow.cli.commands.open_command.check_concurrent_session", return_value=True), \
         patch("pathlib.Path.cwd", return_value=mock_git_repo):
        result = runner.invoke(cli, ["jira", "open", "PROJ-55555"], catch_exceptions=False)

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

        # Verify it found and reopened the existing session (not created a new one)
        assert "Found existing ticket creation session" in result.output, \
            f"Should find existing session. Got:\n{result.output}"
        assert "Session type: ticket_creation, status: complete" in result.output, \
            f"Should show session is complete. Got:\n{result.output}"

        # Verify no new session was created
        fresh_session_manager = SessionManager(config_loader)
        all_sessions = fresh_session_manager.index.get_sessions("creation-PROJ-55555")
        assert len(all_sessions) == 1, \
            f"Should have only 1 session, but found {len(all_sessions)}"

        # Verify the session still has the original UUID
        reopened_session = all_sessions[0]
        assert reopened_session.active_conversation.ai_agent_session_id == original_uuid, \
            f"UUID should be preserved. Expected {original_uuid}, got {reopened_session.active_conversation.ai_agent_session_id}"


def test_jira_open_new_session_sets_branch_none(temp_daf_home, mock_git_repo):
    """Test that daf jira open does not set branch for new ticket_creation sessions (AAP-64347).

    This test verifies the fix for AAP-64347 where creating a new ticket_creation session
    via `daf jira open` was incorrectly setting the branch to the current git branch,
    which would then trigger branch creation prompts when opening the session.

    Steps:
    1. Run daf jira open PROJ-12345 when NO session exists
    2. Command validates JIRA ticket and creates new ticket_creation session
    3. Command recursively calls open_session() to open newly created session
    4. Verify branch is set to None (not current git branch)
    5. Verify _handle_branch_creation is never called
    6. Verify "Skipping branch creation" message is shown
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))
    ]
    config_loader.save_config(config)

    # Ensure no session exists for PROJ-12345
    session_manager = SessionManager(config_loader)
    assert session_manager.get_session("creation-PROJ-12345") is None, "Session should not exist initially"

    # Change to the mock git repository directory
    # This ensures daf jira open uses this as the project_path
    original_cwd = os.getcwd()
    try:
        os.chdir(mock_git_repo)

        runner = CliRunner()

        # Mock JIRA ticket validation and all git operations
        with patch('devflow.jira.JiraClient') as mock_jira_client_class, \
             patch('devflow.jira.utils.validate_jira_ticket') as mock_validate, \
             patch('devflow.utils.temp_directory.should_clone_to_temp', return_value=False), \
             patch('devflow.cli.commands.open_command.GitUtils.get_remote_url', return_value="https://example.com/repo.git"), \
             patch('devflow.cli.commands.open_command.GitUtils.get_current_branch', return_value="main"), \
             patch('devflow.cli.commands.open_command.GitUtils.is_git_repository', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.branch_exists', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.fetch_origin', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.commits_behind', return_value=0), \
             patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False), \
             patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
             patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None), \
             patch('devflow.cli.commands.new_command._handle_branch_creation') as mock_branch_creation:

            # Mock validate_jira_ticket to return ticket data
            mock_validate.return_value = {
                'summary': 'Test ticket for branch creation bug',
                'type': 'Bug',
                'status': 'To Do'
            }

            # Run daf jira open PROJ-12345 (NO existing session)
            result = runner.invoke(cli, ["jira", "open", "PROJ-12345"])

            # Verify the command succeeded
            assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

            # CRITICAL: Verify that _handle_branch_creation was NEVER called
            # This is the core assertion for AAP-64347
            mock_branch_creation.assert_not_called(), \
                f"_handle_branch_creation should not be called for ticket_creation sessions. Output:\n{result.output}"

            # Verify output shows we're skipping branch creation
            assert "Skipping branch creation (session_type: ticket_creation)" in result.output, \
                f"Expected branch creation skip message. Got:\n{result.output}"

            # Verify session was created with correct type and branch=None
            session_manager_check = SessionManager(config_loader)
            session = session_manager_check.get_session("creation-PROJ-12345")
            assert session is not None, "Session should be created"
            assert session.session_type == "ticket_creation", \
                f"Session should be ticket_creation type, got: {session.session_type}"
            assert session.active_conversation.branch is None, \
                f"Branch should be None for ticket_creation sessions, got: {session.active_conversation.branch}"

    finally:
        os.chdir(original_cwd)
