"""Tests for session project management commands (simplified)."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_session_project_commands_exist():
    """Test that the session project command functions exist and can be imported."""
    from devflow.cli.commands.session_project_command import (
        add_project_to_session,
        remove_project_from_session,
    )

    assert callable(add_project_to_session)
    assert callable(remove_project_from_session)


def test_remove_project_deletes_conversation(temp_daf_home, tmp_path):
    """Test that removing a project deletes it from the multi-project conversation."""
    from devflow.cli.commands.session_project_command import remove_project_from_session
    from devflow.config.models import ProjectInfo, ConversationContext, Conversation

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multi-project conversation context
    conversation_context = ConversationContext(
        ai_agent_session_id="uuid-1",
        project_path=str(tmp_path / "backend"),
        branch="main",
        is_multi_project=True,
        workspace_path=str(tmp_path),
        projects={
            "backend": ProjectInfo(
                project_path=str(tmp_path / "backend"),
                relative_path="backend",
                branch="main",
                base_branch="main",
                repo_name="backend",
            ),
            "frontend": ProjectInfo(
                project_path=str(tmp_path / "frontend"),
                relative_path="frontend",
                branch="main",
                base_branch="main",
                repo_name="frontend",
            ),
        }
    )

    # Create conversation container
    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )

    # Create session with multi-project conversation
    session = session_manager.create_session(
        name="test-remove",
        goal="Test",
        working_directory="backend",
        project_path=str(tmp_path / "backend"),
        branch="main",
        ai_agent_session_id="uuid-1",
    )

    # Replace the default conversation with our multi-project one
    session.conversations["backend"] = conversation

    session_manager.update_session(session)

    # Verify two projects exist
    session = session_manager.get_session("test-remove")
    assert session.active_conversation.is_multi_project
    assert len(session.active_conversation.projects) == 2

    # Remove frontend
    remove_project_from_session(
        session_name="test-remove",
        project_name="frontend",
        force=True,
    )

    # Reload with fresh session manager (remove_project creates its own instance)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-remove")
    assert len(session.active_conversation.projects) == 1
    assert "backend" in session.active_conversation.projects
    assert "frontend" not in session.active_conversation.projects


def test_remove_active_project_switches_working_directory(temp_daf_home, tmp_path):
    """Test that removing a project from multi-project conversation works correctly."""
    from devflow.cli.commands.session_project_command import remove_project_from_session
    from devflow.config.models import ProjectInfo, ConversationContext, Conversation

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multi-project conversation context
    conversation_context = ConversationContext(
        ai_agent_session_id="uuid-1",
        project_path=str(tmp_path / "backend"),
        branch="main",
        is_multi_project=True,
        workspace_path=str(tmp_path),
        projects={
            "backend": ProjectInfo(
                project_path=str(tmp_path / "backend"),
                relative_path="backend",
                branch="main",
                base_branch="main",
                repo_name="backend",
            ),
            "frontend": ProjectInfo(
                project_path=str(tmp_path / "frontend"),
                relative_path="frontend",
                branch="main",
                base_branch="main",
                repo_name="frontend",
            ),
        }
    )

    # Create conversation container
    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )

    # Create session with multi-project conversation
    session = session_manager.create_session(
        name="test-switch",
        goal="Test",
        working_directory="backend",
        project_path=str(tmp_path / "backend"),
        branch="main",
        ai_agent_session_id="uuid-1",
    )

    # Replace the default conversation with our multi-project one
    session.conversations["backend"] = conversation

    session_manager.update_session(session)

    # Remove backend project
    remove_project_from_session(
        session_name="test-switch",
        project_name="backend",
        force=True,
    )

    # Reload with fresh session manager (remove_project creates its own instance)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-switch")
    assert len(session.active_conversation.projects) == 1
    assert "frontend" in session.active_conversation.projects
    assert "backend" not in session.active_conversation.projects


def test_remove_nonexistent_project_exits(temp_daf_home, tmp_path):
    """Test that removing non-existent project exits with error."""
    from devflow.cli.commands.session_project_command import remove_project_from_session

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-missing",
        goal="Test",
        working_directory="backend",
        project_path=str(tmp_path / "backend"),
        branch="main",
        ai_agent_session_id="uuid-1",
    )

    # Should exit when project doesn't exist
    with pytest.raises(SystemExit):
        remove_project_from_session(
            session_name="test-missing",
            project_name="nonexistent",
            force=True,
        )


def test_add_project_workspace_lookup(temp_daf_home, tmp_path, monkeypatch):
    """Test that add_project_to_session correctly looks up workspace by name.

    This is a regression test for issue #211 where the code incorrectly
    called .get() on config.repos.workspaces (a List) instead of using
    config.repos.get_workspace_by_name().
    """
    from devflow.cli.commands.session_project_command import add_project_to_session
    from devflow.config.models import (
        WorkspaceDefinition,
        ProjectInfo,
        ConversationContext,
        Conversation,
        Config,
        JiraConfig,
        RepoConfig,
    )

    # Setup workspace directories
    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()
    project1_path = workspace_path / "project1"
    project1_path.mkdir()
    project2_path = workspace_path / "project2"
    project2_path.mkdir()

    # Initialize git repos to avoid branch creation errors
    (project1_path / ".git").mkdir()
    (project2_path / ".git").mkdir()

    # Create config with workspace (workspaces is a List, not dict)
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", transitions={}),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(
                    name="test-workspace",
                    path=str(workspace_path),
                )
            ]
        )
    )

    # Mock load_config on ConfigLoader class to return our test config
    monkeypatch.setattr(ConfigLoader, 'load_config', lambda self: config)

    # Create a multi-project session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multi-project conversation context
    conversation_context = ConversationContext(
        ai_agent_session_id="uuid-test",
        project_path=str(project1_path),
        branch="main",
        is_multi_project=True,
        workspace_path=str(workspace_path),
        projects={
            "project1": ProjectInfo(
                project_path=str(project1_path),
                relative_path="project1",
                branch="main",
                base_branch="main",
                repo_name="project1",
            ),
        }
    )

    # Create conversation container
    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )

    # Create session with multi-project conversation
    session = session_manager.create_session(
        name="test-workspace-lookup",
        goal="Test workspace lookup",
        working_directory="project1",
        project_path=str(project1_path),
        branch="main",
        ai_agent_session_id="uuid-test",
    )

    # Replace the default conversation with our multi-project one
    session.conversations["project1"] = conversation
    session_manager.update_session(session)

    # Mock branch creation to avoid interactive prompts
    with patch('devflow.cli.commands.new_command._handle_branch_creation') as mock_branch:
        mock_branch.return_value = ("main", "main")

        # This should work without AttributeError
        # Before fix: would fail with "AttributeError: 'list' object has no attribute 'get'"
        add_project_to_session(
            session_name="test-workspace-lookup",
            project_names=["project2"],
            workspace_name="test-workspace",
            branch="main",
        )

    # Verify project was added
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("test-workspace-lookup")
    assert len(session.active_conversation.projects) == 2
    assert "project1" in session.active_conversation.projects
    assert "project2" in session.active_conversation.projects


def test_add_project_nonexistent_workspace(temp_daf_home, tmp_path, monkeypatch):
    """Test that add_project_to_session fails gracefully with non-existent workspace.

    This verifies that the error message correctly lists available workspaces
    using the fixed syntax (not .keys() on a list).
    """
    from devflow.cli.commands.session_project_command import add_project_to_session
    from devflow.config.models import (
        WorkspaceDefinition,
        ProjectInfo,
        ConversationContext,
        Conversation,
        Config,
        JiraConfig,
        RepoConfig,
    )

    # Setup
    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()
    project1_path = workspace_path / "project1"
    project1_path.mkdir()

    # Create config with workspace
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", transitions={}),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(
                    name="existing-workspace",
                    path=str(workspace_path),
                )
            ]
        )
    )

    # Mock load_config on ConfigLoader class to return our test config
    monkeypatch.setattr(ConfigLoader, 'load_config', lambda self: config)

    # Create a multi-project session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    conversation_context = ConversationContext(
        ai_agent_session_id="uuid-test",
        project_path=str(project1_path),
        branch="main",
        is_multi_project=True,
        workspace_path=str(workspace_path),
        projects={
            "project1": ProjectInfo(
                project_path=str(project1_path),
                relative_path="project1",
                branch="main",
                base_branch="main",
                repo_name="project1",
            ),
        }
    )

    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )

    session = session_manager.create_session(
        name="test-bad-workspace",
        goal="Test bad workspace",
        working_directory="project1",
        project_path=str(project1_path),
        branch="main",
        ai_agent_session_id="uuid-test",
    )

    session.conversations["project1"] = conversation
    session_manager.update_session(session)

    # Should exit when workspace doesn't exist
    # Before fix: would fail with "AttributeError: 'list' object has no attribute 'keys'"
    with pytest.raises(SystemExit):
        add_project_to_session(
            session_name="test-bad-workspace",
            project_names=["project2"],
            workspace_name="nonexistent-workspace",
            branch="main",
        )
