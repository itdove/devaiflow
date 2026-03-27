"""Tests for issue #184: Commit messages not displayed in multi-project sessions before committing.

This test file validates that commit messages are displayed to users and they have
the opportunity to review/edit them before committing in multi-project sessions,
matching the behavior of single-project sessions.
"""

from pathlib import Path
from unittest.mock import Mock, patch, call
import pytest

from devflow.cli.commands.complete_command import complete_session
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.git.utils import GitUtils


def test_multiproject_workflow_displays_commit_message_before_committing(temp_daf_home, monkeypatch, capsys):
    """Test that multi-project workflow (projects array) displays commit message before committing."""
    # Create session with projects array
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="multiproject-test",
        goal="Add caching layer across backend and frontend",
        working_directory="backend-api",
        project_path="/test/backend-api",
        ai_agent_session_id="uuid-backend",
        issue_key="AAP-12345",
        branch="feature-caching",
    )

    # Configure as multi-project session
    from devflow.config.models import ProjectInfo
    active_conv = session.conversations[session.working_directory].active_session
    active_conv.is_multi_project = True
    active_conv.projects = {
        "backend-api": ProjectInfo(
            project_path="/test/backend-api",
            branch="feature-caching",
            base_branch="main",
            repo_name="backend-api"
        ),
        "frontend-app": ProjectInfo(
            project_path="/test/frontend-app",
            branch="feature-caching",
            base_branch="main",
            repo_name="frontend-app"
        ),
    }
    session_manager.update_session(session)

    # Track all prompts
    prompts_received = []

    def mock_confirm(message, *args, **kwargs):
        prompts_received.append(("confirm", message))
        # Accept commit, decline PR/push
        if "Commit changes" in message:
            return True
        return False

    def mock_prompt(message, *args, **kwargs):
        prompts_received.append(("prompt", message))
        # Return the default message
        return kwargs.get('default', '')

    # Mock git operations
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_current_branch', return_value="feature-caching"), \
         patch('devflow.git.utils.GitUtils.has_uncommitted_changes', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_status_summary', return_value="M  api.py\nM  cache.py"), \
         patch('devflow.git.utils.GitUtils.commit_all', return_value=(True, None)), \
         patch('devflow.git.utils.GitUtils.has_unpushed_commits', return_value=False), \
         patch('devflow.cli.commands.complete_command.Confirm.ask', side_effect=mock_confirm), \
         patch('devflow.cli.commands.complete_command.Prompt.ask', side_effect=mock_prompt), \
         patch('devflow.cli.commands.complete_command._get_pr_for_branch', return_value=None), \
         patch('devflow.cli.commands.complete_command.jira_transition_on_complete', lambda s, c: None):

        complete_session("multiproject-test", no_issue_update=True)

    # Verify commit messages were displayed
    captured = capsys.readouterr()

    # Check that commit message was displayed for backend-api
    assert "Suggested commit message:" in captured.out
    assert "AAP-12345: Add caching layer across backend and frontend (backend-api)" in captured.out

    # Check that commit message was displayed for frontend-app
    assert "AAP-12345: Add caching layer across backend and frontend (frontend-app)" in captured.out

    # Verify user was prompted for confirmation
    prompt_messages = [msg for kind, msg in prompts_received if kind == "confirm"]
    assert any("Use this commit message?" in msg for msg in prompt_messages), \
        "User should be prompted to confirm commit message"

    # Verify commits were made
    assert "Changes committed" in captured.out


def test_multiproject_with_multiple_repos_displays_commit_messages(temp_daf_home, monkeypatch, capsys):
    """Test that multi-project sessions with 2+ repos display commit message for each."""
    # Create session with 2 projects
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="two-repo-test",
        goal="Sync API and UI changes",
        working_directory="api-service",
        project_path="/test/api-service",
        ai_agent_session_id="uuid-api",
        issue_key="AAP-77777",
        branch="sync-changes",
    )

    # Configure as multi-project session with 2 repos
    from devflow.config.models import ProjectInfo
    active_conv = session.conversations[session.working_directory].active_session
    active_conv.is_multi_project = True
    active_conv.projects = {
        "api-service": ProjectInfo(
            project_path="/test/api-service",
            branch="sync-changes",
            base_branch="main",
            repo_name="api-service"
        ),
        "ui-frontend": ProjectInfo(
            project_path="/test/ui-frontend",
            branch="sync-changes",
            base_branch="main",
            repo_name="ui-frontend"
        ),
    }
    session_manager.update_session(session)

    # Track all prompts
    prompts_received = []

    def mock_confirm(message, *args, **kwargs):
        prompts_received.append(("confirm", message))
        # Accept commit, decline PR/push
        if "Commit changes" in message:
            return True
        return False

    def mock_prompt(message, *args, **kwargs):
        prompts_received.append(("prompt", message))
        # Return the default message
        return kwargs.get('default', '')

    # Mock git operations
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_current_branch', return_value="sync-changes"), \
         patch('devflow.git.utils.GitUtils.has_uncommitted_changes', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_status_summary', return_value="M  api.py\nM  routes.py"), \
         patch('devflow.git.utils.GitUtils.commit_all', return_value=(True, None)), \
         patch('devflow.git.utils.GitUtils.has_unpushed_commits', return_value=False), \
         patch('devflow.cli.commands.complete_command.Confirm.ask', side_effect=mock_confirm), \
         patch('devflow.cli.commands.complete_command.Prompt.ask', side_effect=mock_prompt), \
         patch('devflow.cli.commands.complete_command._get_pr_for_branch', return_value=None), \
         patch('devflow.cli.commands.complete_command.jira_transition_on_complete', lambda s, c: None):

        complete_session("two-repo-test", no_issue_update=True)

    # Verify commit messages were displayed
    captured = capsys.readouterr()

    # Check that commit message was displayed for both repos
    assert "Suggested commit message:" in captured.out
    assert "AAP-77777: Sync API and UI changes (api-service)" in captured.out
    assert "AAP-77777: Sync API and UI changes (ui-frontend)" in captured.out

    # Verify user was prompted for confirmation
    prompt_messages = [msg for kind, msg in prompts_received if kind == "confirm"]
    assert any("Use this commit message?" in msg for msg in prompt_messages), \
        "User should be prompted to confirm commit message"

    # Verify commits were made
    assert "Changes committed" in captured.out


def test_multiproject_user_can_decline_and_edit_message(temp_daf_home, monkeypatch, capsys):
    """Test that user can decline suggested message and provide their own in multi-project."""
    # Create session with projects array
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="decline-edit-test",
        goal="Update dependencies",
        working_directory="service",
        project_path="/test/service",
        ai_agent_session_id="uuid-service",
        issue_key="AAP-33333",
        branch="update-deps",
    )

    # Configure as multi-project session
    from devflow.config.models import ProjectInfo
    active_conv = session.conversations[session.working_directory].active_session
    active_conv.is_multi_project = True
    active_conv.projects = {
        "service": ProjectInfo(
            project_path="/test/service",
            branch="update-deps",
            base_branch="main",
            repo_name="service"
        ),
    }
    session_manager.update_session(session)

    # Track prompts
    confirm_calls = []
    prompt_calls = []

    def mock_confirm(message, *args, **kwargs):
        confirm_calls.append(message)
        if "Commit changes" in message:
            return True
        elif "Use this commit message?" in message:
            return False  # User declines suggested message
        return False

    def mock_prompt(message, *args, **kwargs):
        prompt_calls.append(message)
        # User provides custom message
        return "chore: bump package versions"

    commit_messages_used = []

    def mock_commit_all(working_dir, message):
        commit_messages_used.append(message)
        return (True, None)

    # Mock git operations
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_current_branch', return_value="update-deps"), \
         patch('devflow.git.utils.GitUtils.has_uncommitted_changes', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_status_summary', return_value="M  package.json"), \
         patch('devflow.git.utils.GitUtils.commit_all', side_effect=mock_commit_all), \
         patch('devflow.git.utils.GitUtils.has_unpushed_commits', return_value=False), \
         patch('devflow.cli.commands.complete_command.Confirm.ask', side_effect=mock_confirm), \
         patch('devflow.cli.commands.complete_command.Prompt.ask', side_effect=mock_prompt), \
         patch('devflow.cli.commands.complete_command._get_pr_for_branch', return_value=None), \
         patch('devflow.cli.commands.complete_command.jira_transition_on_complete', lambda s, c: None):

        complete_session("decline-edit-test", no_issue_update=True)

    # Verify user was asked to confirm
    assert any("Use this commit message?" in msg for msg in confirm_calls), \
        "User should be asked to confirm commit message"

    # Verify user was prompted to provide custom message
    assert len(prompt_calls) > 0, "User should be prompted to provide custom message"

    # Verify custom message was used
    assert len(commit_messages_used) == 1
    assert "chore: bump package versions" in commit_messages_used[0]


def test_multiproject_allows_user_to_edit_commit_message(temp_daf_home, monkeypatch, capsys):
    """Test that user can edit commit message in multi-project sessions."""
    # Create session with projects array
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="edit-message-test",
        goal="Add Redis caching",
        working_directory="api",
        project_path="/test/api",
        ai_agent_session_id="uuid-api",
        issue_key="AAP-22222",
        branch="add-redis",
    )

    # Configure as multi-project session
    from devflow.config.models import ProjectInfo
    active_conv = session.conversations[session.working_directory].active_session
    active_conv.is_multi_project = True
    active_conv.projects = {
        "api": ProjectInfo(
            project_path="/test/api",
            branch="add-redis",
            base_branch="main",
            repo_name="api"
        ),
    }
    session_manager.update_session(session)

    # Track prompts
    confirm_count = 0

    def mock_confirm(message, *args, **kwargs):
        nonlocal confirm_count
        confirm_count += 1
        # First confirm: commit changes (yes)
        # Second confirm: use suggested message (no - user wants to edit)
        if "Commit changes" in message:
            return True
        elif "Use this commit message?" in message:
            return False  # User declines, will edit message
        return False

    def mock_prompt(message, *args, **kwargs):
        # User provides custom message
        return "Custom commit message from user"

    # Mock git operations
    commit_messages_used = []

    def mock_commit_all(working_dir, message):
        commit_messages_used.append(message)
        return (True, None)

    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_current_branch', return_value="add-redis"), \
         patch('devflow.git.utils.GitUtils.has_uncommitted_changes', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_status_summary', return_value="M  cache.py"), \
         patch('devflow.git.utils.GitUtils.commit_all', side_effect=mock_commit_all), \
         patch('devflow.git.utils.GitUtils.has_unpushed_commits', return_value=False), \
         patch('devflow.cli.commands.complete_command.Confirm.ask', side_effect=mock_confirm), \
         patch('devflow.cli.commands.complete_command.Prompt.ask', side_effect=mock_prompt), \
         patch('devflow.cli.commands.complete_command._get_pr_for_branch', return_value=None), \
         patch('devflow.cli.commands.complete_command.jira_transition_on_complete', lambda s, c: None):

        complete_session("edit-message-test", no_issue_update=True)

    # Verify user's custom message was used
    assert len(commit_messages_used) == 1
    assert "Custom commit message from user" in commit_messages_used[0]
    assert "🤖 Generated with [Claude Code]" in commit_messages_used[0]


def test_single_project_session_still_works_correctly(temp_daf_home, monkeypatch, capsys):
    """Regression test: Verify single-project sessions continue to work correctly."""
    # Create single-project session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="single-test",
        goal="Fix login bug",
        working_directory="webapp",
        project_path="/test/webapp",
        ai_agent_session_id="uuid-webapp",
        issue_key="AAP-99999",
        branch="fix-login",
    )

    # Track prompts
    prompts_received = []

    def mock_confirm(message, *args, **kwargs):
        prompts_received.append(("confirm", message))
        if "Commit these changes" in message:
            return True
        elif "Use this commit message?" in message:
            return True
        return False

    def mock_prompt(message, *args, **kwargs):
        prompts_received.append(("prompt", message))
        return kwargs.get('default', '')

    # Mock git operations and AI message generation
    with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_current_branch', return_value="fix-login"), \
         patch('devflow.git.utils.GitUtils.has_uncommitted_changes', return_value=True), \
         patch('devflow.git.utils.GitUtils.get_status_summary', return_value="M  login.py"), \
         patch('devflow.git.utils.GitUtils.get_uncommitted_diff', return_value="diff --git a/login.py"), \
         patch('devflow.git.utils.GitUtils.commit_all', return_value=(True, None)), \
         patch('devflow.git.utils.GitUtils.has_unpushed_commits', return_value=False), \
         patch('devflow.cli.commands.complete_command.Confirm.ask', side_effect=mock_confirm), \
         patch('devflow.cli.commands.complete_command.Prompt.ask', side_effect=mock_prompt), \
         patch('devflow.cli.commands.complete_command._get_pr_for_branch', return_value=None), \
         patch('devflow.cli.commands.complete_command._generate_commit_message_from_diff', return_value="Fix login validation bug"), \
         patch('devflow.cli.commands.complete_command.jira_transition_on_complete', lambda s, c: None):

        complete_session("single-test", no_issue_update=True)

    # Verify commit message was displayed
    captured = capsys.readouterr()
    assert "Suggested commit message:" in captured.out

    # Verify user was prompted for confirmation
    prompt_messages = [msg for kind, msg in prompts_received if kind == "confirm"]
    assert any("Use this commit message?" in msg for msg in prompt_messages), \
        "Single-project sessions should still prompt for commit message confirmation"
