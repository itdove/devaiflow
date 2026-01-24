"""Tests for PROJ-61092: Session not found error when reopening quit daf jira new session.

This test file verifies that when a user creates a session with `daf jira new`, quits it
WITHOUT completing the ticket creation, and then attempts to reopen it using `daf open`,
the session reopens successfully instead of failing with a "No conversation found" error.
"""

import os
import shutil
import tempfile
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
    import subprocess

    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True, check=True)

    # Create initial commit
    (repo_path / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True, check=True)

    return repo_path


def test_reopen_ticket_creation_session_without_conversation_file(temp_daf_home, mock_git_repo):
    """Test reopening a ticket_creation session that was quit before conversation started.

    This is the main test for PROJ-61092. Steps:
    1. Create a ticket_creation session (simulating daf jira new)
    2. Do NOT create a conversation file (simulating user quitting immediately)
    3. Attempt to reopen the session
    4. Verify it succeeds and generates a new session ID instead of failing
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session with temp_directory metadata (as daf jira new does)
    temp_dir = tempfile.mkdtemp(prefix="daf-jira-analysis-")
    try:
        session = session_manager.create_session(
            name="test-ticket-session-abc123",
            goal="Create JIRA story under PROJ-1234: Add retry logic",
            working_directory=mock_git_repo.name,
            project_path=str(mock_git_repo),
        )

        # Set session type to ticket_creation
        session.session_type = "ticket_creation"

        # Add conversation with temp_directory metadata
        ai_agent_session_id = str(uuid.uuid4())
        session.add_conversation(
            working_dir=mock_git_repo.name,
            ai_agent_session_id=ai_agent_session_id,
            project_path=str(mock_git_repo),
            branch="main",
            temp_directory=temp_dir,
            original_project_path=str(mock_git_repo),
            workspace=config.repos.get_default_workspace_path(),
        )

        session_manager.update_session(session)

        # Simulate user quitting: DO NOT create conversation file
        # (normally created by Claude Code when session starts)

        # Now try to reopen the session
        runner = CliRunner()

        # Mock all the git/clone operations that would happen during temp directory recreation
        with patch('devflow.cli.commands.open_command.GitUtils.get_remote_url', return_value="https://example.com/repo.git"), \
             patch('devflow.cli.commands.open_command.GitUtils.clone_repository', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.get_default_branch', return_value="main"), \
             patch('devflow.cli.commands.open_command.GitUtils.get_current_branch', return_value="main"), \
             patch('devflow.cli.commands.open_command.GitUtils.is_git_repository', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.branch_exists', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.fetch_origin', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.commits_behind', return_value=0), \
             patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False), \
             patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
             patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None):

            result = runner.invoke(cli, ["open", "test-ticket-session-abc123"])

            # Verify the command succeeded (no error exit code)
            assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

            # Verify the output indicates conversation file was not restored
            # AND that a new session ID was generated for fresh start
            assert "Conversation file was not restored" in result.output, \
                f"Expected 'Conversation file was not restored' message. Got:\n{result.output}"
            assert "Generating new session ID" in result.output, \
                f"Expected 'Generating new session ID' message. Got:\n{result.output}"

            # Verify it would launch as first-time (not resume)
            # The key fix is that it uses --session-id (first launch) instead of --resume
            assert "First-time launch" in result.output or "Opening:" in result.output, \
                f"Expected first-time launch indicator. Got:\n{result.output}"

            # The actual validation is in the output - if we see these messages, the fix works!
            # The session ID shown in the output should be different from the original,
            # which we can verify from the output logs
            import re
            match = re.search(r"Generated new session ID: ([a-f0-9-]+)", result.output)
            assert match is not None, "Should show generated new session ID in output"
            new_id = match.group(1)
            assert new_id != ai_agent_session_id, f"New ID {new_id} should differ from original {ai_agent_session_id}"

    finally:
        # Clean up temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_reopen_ticket_creation_session_with_conversation_file(temp_daf_home, mock_git_repo):
    """Test reopening a ticket_creation session that has a conversation file.

    This verifies the existing behavior (PROJ-60881) still works correctly:
    when conversation file exists, it should be restored and session resumed.
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session
    temp_dir = tempfile.mkdtemp(prefix="daf-jira-analysis-")
    try:
        session = session_manager.create_session(
            name="test-with-conversation-abc123",
            goal="Create JIRA story under PROJ-1234: Add retry logic",
            working_directory=mock_git_repo.name,
            project_path=str(mock_git_repo),
        )

        session.session_type = "ticket_creation"

        ai_agent_session_id = str(uuid.uuid4())
        session.add_conversation(
            working_dir=mock_git_repo.name,
            ai_agent_session_id=ai_agent_session_id,
            project_path=str(mock_git_repo),
            branch="main",
            temp_directory=temp_dir,
            original_project_path=str(mock_git_repo),
            workspace=config.repos.get_default_workspace_path(),
        )

        session_manager.update_session(session)

        # Create a conversation file (simulate user did some work)
        from devflow.session.capture import SessionCapture
        capture = SessionCapture()
        session_dir = capture.get_session_dir(str(mock_git_repo))
        session_dir.mkdir(parents=True, exist_ok=True)
        conversation_file = session_dir / f"{ai_agent_session_id}.jsonl"

        # Write minimal valid conversation file
        conversation_file.write_text('{"role": "user", "content": "test"}\n')

        # Now try to reopen the session
        runner = CliRunner()

        with patch('devflow.cli.commands.open_command.GitUtils.get_remote_url', return_value="https://example.com/repo.git"), \
             patch('devflow.cli.commands.open_command.GitUtils.clone_repository') as mock_clone, \
             patch('devflow.cli.commands.open_command.GitUtils.get_default_branch', return_value="main"), \
             patch('devflow.cli.commands.open_command.GitUtils.get_current_branch', return_value="main"), \
             patch('devflow.cli.commands.open_command.GitUtils.is_git_repository', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.branch_exists', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.fetch_origin', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.commits_behind', return_value=0), \
             patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False), \
             patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
             patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None):

            # Mock clone to preserve conversation file location
            def mock_clone_side_effect(url, path, branch=None):
                # Copy the conversation file to the new temp directory
                new_session_dir = capture.get_session_dir(str(path))
                new_session_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(conversation_file, new_session_dir / conversation_file.name)
                return True

            mock_clone.side_effect = mock_clone_side_effect

            result = runner.invoke(cli, ["open", "test-with-conversation-abc123"])

            # Verify success
            assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

            # Should NOT generate new session ID (conversation exists)
            assert "Generating new session ID" not in result.output, \
                f"Should not generate new ID when conversation exists. Got:\n{result.output}"

            # Verify session still has original ID
            updated_session = session_manager.get_session("test-with-conversation-abc123")
            assert updated_session is not None
            active_conv = updated_session.active_conversation
            assert active_conv is not None
            assert active_conv.ai_agent_session_id == ai_agent_session_id, \
                "Session should keep original Claude session ID when conversation exists"

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_reopen_normal_session_without_conversation_file(temp_daf_home, mock_git_repo):
    """Test that normal (non-ticket_creation) sessions still handle missing conversation files correctly.

    This ensures our fix doesn't break the existing behavior for normal sessions.
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    session_manager = SessionManager(config_loader)

    # Create a normal development session (NOT ticket_creation)
    ai_agent_session_id = str(uuid.uuid4())
    session = session_manager.create_session(
        name="normal-session",
        goal="Fix bug",
        working_directory=mock_git_repo.name,
        project_path=str(mock_git_repo),
        branch="main",
    )

    # Manually add conversation with explicit ID
    session.add_conversation(
        working_dir=mock_git_repo.name,
        ai_agent_session_id=ai_agent_session_id,
        project_path=str(mock_git_repo),
        branch="main",
        workspace=config.repos.get_default_workspace_path(),
    )
    session_manager.update_session(session)

    # Verify it's NOT a ticket_creation session
    assert session.session_type != "ticket_creation"

    # Do NOT create conversation file (simulate interrupted session)

    # Try to reopen
    runner = CliRunner()

    with patch('devflow.cli.commands.open_command.GitUtils.is_git_repository', return_value=True), \
         patch('devflow.cli.commands.open_command.GitUtils.branch_exists', return_value=True), \
         patch('devflow.cli.commands.open_command.GitUtils.get_current_branch', return_value="main"), \
         patch('devflow.cli.commands.open_command.GitUtils.fetch_origin', return_value=True), \
         patch('devflow.cli.commands.open_command.GitUtils.commits_behind', return_value=0), \
         patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False), \
         patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
         patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None):

        result = runner.invoke(cli, ["open", "normal-session"])

        # Verify success
        assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

        # For normal sessions (non-temp-directory sessions), the existing behavior should work:
        # - Missing conversation file triggers "Conversation file not found" message
        # - Session is treated as first launch
        # - New session ID is generated
        assert "Conversation file not found" in result.output or "Will create a new conversation" in result.output or \
               "First-time launch" in result.output, \
            f"Expected message about missing conversation for normal session. Got:\n{result.output}"

        # The session ID handling for normal sessions is unchanged by PROJ-61092
        # This test just verifies we didn't break the existing behavior


def test_mock_mode_skips_temp_directory_prompt(temp_daf_home, mock_git_repo, monkeypatch):
    """Test that mock mode skips the temp directory prompt (PROJ-62701).

    This verifies that when DAF_MOCK_MODE=1, the interactive prompt to clone
    to a temporary directory is skipped, preventing integration tests from hanging.
    """
    # Set mock mode environment variable
    monkeypatch.setenv("DAF_MOCK_MODE", "1")

    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session WITHOUT temp_directory metadata
    # This simulates the state when daf jira new creates a session in mock mode
    session = session_manager.create_session(
        name="test-mock-mode-session",
        goal="Create JIRA story under PROJ-99999: Test mock mode",
        working_directory=mock_git_repo.name,
        project_path=str(mock_git_repo),
    )

    # Set session type to ticket_creation (as daf jira new does)
    session.session_type = "ticket_creation"

    # Add conversation WITHOUT temp_directory (mock mode skips temp dir creation)
    ai_agent_session_id = str(uuid.uuid4())
    session.add_conversation(
        working_dir=mock_git_repo.name,
        ai_agent_session_id=ai_agent_session_id,
        project_path=str(mock_git_repo),
        branch="main",
        # No temp_directory or original_project_path
        workspace=config.repos.get_default_workspace_path(),
    )

    session_manager.update_session(session)

    # Now try to open the session in mock mode
    runner = CliRunner()

    with patch('devflow.cli.commands.open_command.GitUtils.is_git_repository', return_value=True), \
         patch('devflow.cli.commands.open_command.GitUtils.branch_exists', return_value=True), \
         patch('devflow.cli.commands.open_command.GitUtils.get_current_branch', return_value="main"), \
         patch('devflow.cli.commands.open_command.GitUtils.fetch_origin', return_value=True), \
         patch('devflow.cli.commands.open_command.GitUtils.commits_behind', return_value=0), \
         patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False), \
         patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
         patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None), \
         patch('rich.prompt.Confirm.ask') as mock_prompt:

        # The test: open the session
        result = runner.invoke(cli, ["open", "test-mock-mode-session"])

        # Verify the command succeeded
        assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

        # CRITICAL: Verify the Confirm.ask prompt was NEVER called
        # This is the fix for PROJ-62701 - mock mode should skip the prompt
        mock_prompt.assert_not_called()

        # Verify output shows we're skipping the temp directory prompt
        # Updated for message changed to include reopened session case
        # Use a substring that won't be affected by line wrapping
        assert "skipping temp" in result.output and "directory prompt" in result.output, \
            f"Expected temp directory skip message. Got:\n{result.output}"


def test_reopen_ticket_creation_session_never_prompts_for_branch(temp_daf_home, mock_git_repo):
    """Test that reopening a ticket_creation session never prompts to create a git branch.

    This verifies the fix where reopening a ticket_creation session (created via daf jira new)
    that was quit before conversation started would incorrectly prompt to create a git branch.

    The fix ensures that the session_type check happens BEFORE the is_first_launch condition,
    completely preventing any branch creation prompts for ticket_creation sessions.
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session with temp_directory metadata
    temp_dir = tempfile.mkdtemp(prefix="daf-jira-analysis-")
    try:
        session = session_manager.create_session(
            name="test-branch-prompt-skip",
            goal="Create JIRA bug under Test branch prompt fix",
            working_directory=mock_git_repo.name,
            project_path=str(mock_git_repo),
        )

        # Set session type to ticket_creation (as daf jira new does)
        session.session_type = "ticket_creation"

        # Add conversation WITHOUT a branch (ticket_creation sessions don't have branches)
        ai_agent_session_id = str(uuid.uuid4())
        session.add_conversation(
            working_dir=mock_git_repo.name,
            ai_agent_session_id=ai_agent_session_id,
            project_path=str(mock_git_repo),
            branch="main",  # placeholder branch
            temp_directory=temp_dir,
            original_project_path=str(mock_git_repo),
            workspace=config.repos.get_default_workspace_path(),
        )

        # Clear the branch to simulate ticket_creation session state
        if session.active_conversation:
            session.active_conversation.branch = None

        session_manager.update_session(session)

        # Do NOT create conversation file - this simulates user quitting immediately
        # This is the scenario that triggers is_first_launch=True (lines 274-298)

        # Now try to reopen the session
        runner = CliRunner()

        with patch('devflow.cli.commands.open_command.GitUtils.get_remote_url', return_value="https://example.com/repo.git"), \
             patch('devflow.cli.commands.open_command.GitUtils.clone_repository', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.get_default_branch', return_value="main"), \
             patch('devflow.cli.commands.open_command.GitUtils.get_current_branch', return_value="main"), \
             patch('devflow.cli.commands.open_command.GitUtils.is_git_repository', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.branch_exists', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.fetch_origin', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.commits_behind', return_value=0), \
             patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False), \
             patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
             patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None), \
             patch('devflow.cli.commands.new_command._handle_branch_creation') as mock_branch_creation:

            result = runner.invoke(cli, ["open", "test-branch-prompt-skip"])

            # Verify the command succeeded
            assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

            # CRITICAL: Verify that _handle_branch_creation was NEVER called
            # This is the core fix - ticket_creation sessions should never prompt for branch creation
            mock_branch_creation.assert_not_called()

            # Verify output shows we're skipping branch creation
            assert "Skipping branch creation (session_type: ticket_creation)" in result.output, \
                f"Expected branch creation skip message. Got:\n{result.output}"

    finally:
        # Clean up temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_reopen_ticket_creation_session_skips_jira_transition(temp_daf_home, mock_git_repo):
    """Test that reopening a ticket_creation session skips JIRA status transitions.

    This verifies the fix for the issue where reopening a ticket_creation session
    would incorrectly transition the issue tracker ticket status. Ticket creation sessions
    are analysis-only and should never modify ticket status.
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session with a issue key
    session = session_manager.create_session(
        name="test-jira-transition-skip",
        goal="Create JIRA story under PROJ-12345: Add caching layer",
        working_directory=mock_git_repo.name,
        project_path=str(mock_git_repo),
        issue_key="PROJ-12345",
    )

    # Set session type to ticket_creation
    session.session_type = "ticket_creation"
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["status"] = "To Do"  # Initial status

    # Add conversation
    ai_agent_session_id = str(uuid.uuid4())
    session.add_conversation(
        working_dir=mock_git_repo.name,
        ai_agent_session_id=ai_agent_session_id,
        project_path=str(mock_git_repo),
        branch="main",
        workspace=config.repos.get_default_workspace_path(),
    )

    session_manager.update_session(session)

    # Create conversation file (simulate user did some work)
    from devflow.session.capture import SessionCapture
    capture = SessionCapture()
    session_dir = capture.get_session_dir(str(mock_git_repo))
    session_dir.mkdir(parents=True, exist_ok=True)
    conversation_file = session_dir / f"{ai_agent_session_id}.jsonl"
    conversation_file.write_text('{"role": "user", "content": "test"}\n')

    # Now try to reopen the session
    runner = CliRunner()

    with patch('devflow.cli.commands.open_command.GitUtils.is_git_repository', return_value=True), \
         patch('devflow.cli.commands.open_command.GitUtils.branch_exists', return_value=True), \
         patch('devflow.cli.commands.open_command.GitUtils.get_current_branch', return_value="main"), \
         patch('devflow.cli.commands.open_command.GitUtils.fetch_origin', return_value=True), \
         patch('devflow.cli.commands.open_command.GitUtils.commits_behind', return_value=0), \
         patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False), \
         patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
         patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None), \
         patch('devflow.jira.JiraClient') as mock_jira_client_class:

        # Mock JiraClient to ensure it's never called for ticket_creation sessions
        mock_jira_client = MagicMock()
        mock_jira_client_class.return_value = mock_jira_client

        result = runner.invoke(cli, ["open", "test-jira-transition-skip"])

        # Verify the command succeeded
        assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

        # CRITICAL: Verify that JiraClient was NEVER instantiated for ticket_creation session
        # This proves that JIRA status transitions were completely skipped
        mock_jira_client_class.assert_not_called()

        # Verify output shows we're skipping JIRA transitions
        assert "Skipping JIRA status transition (session_type: ticket_creation)" in result.output, \
            f"Expected JIRA transition skip message. Got:\n{result.output}"

        # Verify session status remained unchanged
        updated_session = session_manager.get_session("test-jira-transition-skip")
        assert updated_session.issue_metadata.get("status") == "To Do", \
            f"JIRA status should remain unchanged for ticket_creation sessions. Got: {updated_session.issue_metadata.get('status')}"


def test_daf_jira_open_resumes_existing_conversation(temp_daf_home, mock_git_repo):
    """Test that daf jira open resumes existing conversation instead of creating new one.

    This is the core test for the issue tracker ticket PROJ-63066. Steps:
    1. Create ticket_creation session via daf jira open (simulating first run)
    2. Create conversation file (simulating user did some work)
    3. Run daf jira open again on same ticket
    4. Verify it resumes the SAME conversation (same session ID)
    5. Verify conversation history is preserved
    """
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    from devflow.config.models import WorkspaceDefinition

    config.repos.workspaces = [

        WorkspaceDefinition(name="default", path=str(mock_git_repo.parent))

    ]
    config_loader.save_config(config)

    session_manager = SessionManager(config_loader)

    # Simulate creating a ticket_creation session via daf jira open PROJ-12345
    # This creates a session named "creation-PROJ-12345"
    temp_dir = tempfile.mkdtemp(prefix="daf-jira-analysis-")
    original_session_id = str(uuid.uuid4())

    try:
        session = session_manager.create_session(
            name="creation-PROJ-12345",
            goal="PROJ-12345: Add retry logic to subscription API",
            working_directory=mock_git_repo.name,
            project_path=str(mock_git_repo),
            issue_key="PROJ-12345",
        )

        # Set session type to ticket_creation (as daf jira open does)
        session.session_type = "ticket_creation"
        if not session.issue_metadata:
            session.issue_metadata = {}
        session.issue_metadata["summary"] = "Add retry logic to subscription API"
        session.issue_metadata["type"] = "Story"
        session.issue_metadata["status"] = "To Do"

        # Add conversation with temp_directory metadata (as daf jira open does)
        session.add_conversation(
            working_dir=mock_git_repo.name,
            ai_agent_session_id=original_session_id,
            project_path=str(mock_git_repo),
            branch="main",
            temp_directory=temp_dir,
            original_project_path=str(mock_git_repo),
            workspace=config.repos.get_default_workspace_path(),
        )

        session_manager.update_session(session)

        # Create conversation file at STABLE location (based on original_project_path)
        # This is where the conversation is stored after user exits Claude
        from devflow.session.capture import SessionCapture
        capture = SessionCapture()
        stable_session_dir = capture.get_session_dir(str(mock_git_repo))
        stable_session_dir.mkdir(parents=True, exist_ok=True)
        stable_conversation_file = stable_session_dir / f"{original_session_id}.jsonl"

        # Write conversation with some history
        conversation_history = [
            '{"role": "user", "content": "Search for subscription API code"}\n',
            '{"role": "assistant", "content": "Found subscription API in src/api/subscription.py"}\n',
            '{"role": "user", "content": "Analyze the retry logic"}\n',
            '{"role": "assistant", "content": "The current implementation does not have retry logic"}\n',
        ]
        stable_conversation_file.write_text(''.join(conversation_history))

        # Now simulate user exiting and then running daf jira open PROJ-12345 again
        # This should find the existing session and resume it
        runner = CliRunner()

        # Mock the JIRA client to simulate ticket validation
        with patch('devflow.jira.JiraClient') as mock_jira_client_class, \
             patch('devflow.jira.utils.validate_jira_ticket') as mock_validate, \
             patch('devflow.cli.commands.open_command.GitUtils.get_remote_url', return_value="https://example.com/repo.git"), \
             patch('devflow.cli.commands.open_command.GitUtils.clone_repository') as mock_clone, \
             patch('devflow.cli.commands.open_command.GitUtils.get_default_branch', return_value="main"), \
             patch('devflow.cli.commands.open_command.GitUtils.get_current_branch', return_value="main"), \
             patch('devflow.cli.commands.open_command.GitUtils.is_git_repository', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.branch_exists', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.fetch_origin', return_value=True), \
             patch('devflow.cli.commands.open_command.GitUtils.commits_behind', return_value=0), \
             patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False), \
             patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
             patch('devflow.cli.commands.open_command._detect_working_directory_from_cwd', return_value=None):

            # Mock validate_jira_ticket to return ticket data (simulating ticket exists)
            mock_validate.return_value = {
                'summary': 'Add retry logic to subscription API',
                'type': 'Story',
                'status': 'To Do'
            }

            # Mock clone to preserve conversation file in new temp directory
            def mock_clone_side_effect(url, path, branch=None):
                new_session_dir = capture.get_session_dir(str(path))
                new_session_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(stable_conversation_file, new_session_dir / stable_conversation_file.name)
                return True

            mock_clone.side_effect = mock_clone_side_effect

            # Run daf jira open PROJ-12345 (should find existing session and resume it)
            result = runner.invoke(cli, ["jira", "open", "PROJ-12345"])

            # Verify the command succeeded
            assert result.exit_code == 0, f"Command failed with output:\n{result.output}"

            # CRITICAL: Verify it found the existing session
            assert "Found existing ticket creation session" in result.output, \
                f"Expected to find existing session. Got:\n{result.output}"

            # CRITICAL: Verify it did NOT generate a new session ID
            assert "Generating new session ID" not in result.output, \
                f"Should not generate new session ID when conversation exists. Got:\n{result.output}"

            # CRITICAL: Verify it found the conversation at stable location
            assert "Checking for conversation file at stable location" in result.output, \
                f"Expected to check stable location for ticket_creation session. Got:\n{result.output}"
            assert "found" in result.output.lower(), \
                f"Expected to find conversation file. Got:\n{result.output}"

            # Verify the session still has the ORIGINAL session ID
            updated_session = session_manager.get_session("creation-PROJ-12345")
            assert updated_session is not None, "Session should still exist"
            active_conv = updated_session.active_conversation
            assert active_conv is not None
            assert active_conv.ai_agent_session_id == original_session_id, \
                f"Session ID should not change on reopen. Expected {original_session_id}, got {active_conv.ai_agent_session_id}"

            # Verify conversation file still exists at stable location
            assert stable_conversation_file.exists(), "Conversation file should still exist at stable location"

            # Verify conversation history is preserved
            conversation_content = stable_conversation_file.read_text()
            assert "Search for subscription API code" in conversation_content, \
                "Conversation history should be preserved"

    finally:
        # Clean up temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
