"""Tests for portable path storage (PROJ-60537)."""

import json
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import ConversationContext, Session
from devflow.export.manager import ExportManager
from devflow.session.manager import SessionManager


def test_conversation_context_stores_relative_path(temp_daf_home):
    """Test that ConversationContext stores both relative and absolute paths."""
    workspace = "/Users/alice/development"
    project_path = "/Users/alice/development/workspace/example-repo"

    # Simulate what happens in Session.add_conversation
    conversation = ConversationContext(
        ai_agent_session_id="test-uuid",
        project_path=project_path,
        branch="main",
        repo_name="example-repo",
        relative_path="workspace/example-repo",
    )

    assert conversation.project_path == project_path
    assert conversation.repo_name == "example-repo"
    assert conversation.relative_path == "workspace/example-repo"


def test_conversation_context_get_project_path_with_workspace(temp_daf_home):
    """Test that get_project_path reconstructs path from workspace and relative_path."""
    conversation = ConversationContext(
        ai_agent_session_id="test-uuid",
        project_path="/Users/alice/development/workspace/example-repo",
        branch="main",
        repo_name="example-repo",
        relative_path="workspace/example-repo",
    )

    # When called with different workspace, should reconstruct path
    new_workspace = "/Users/bob/workspace"
    reconstructed = conversation.get_project_path(new_workspace)

    assert reconstructed == "/Users/bob/workspace/workspace/example-repo"


def test_conversation_context_get_project_path_without_relative(temp_daf_home):
    """Test get_project_path falls back to project_path if no relative_path."""
    conversation = ConversationContext(
        ai_agent_session_id="test-uuid",
        project_path="/Users/alice/development/workspace/example-repo",
        branch="main",
    )

    # Should return stored project_path
    assert conversation.get_project_path() == "/Users/alice/development/workspace/example-repo"




def test_session_add_conversation_with_workspace(temp_daf_home, monkeypatch):
    """Test that Session.add_conversation computes relative path when workspace is provided."""
    # Create a temporary workspace directory
    workspace = temp_daf_home / "workspace"
    workspace.mkdir()
    project_dir = workspace / "workspace" / "example-repo"
    project_dir.mkdir(parents=True)

    session = Session(name="test-session", goal="Test goal")

    session.add_conversation(
        working_dir="example-repo",
        ai_agent_session_id="test-uuid",
        project_path=str(project_dir),
        branch="main",
        workspace=str(workspace),
    )

    # Access active_session
    conversation = session.conversations["example-repo"].active_session
    assert conversation.repo_name == "example-repo"
    assert conversation.relative_path == "workspace/example-repo"
    assert conversation.project_path == str(project_dir)




def test_export_import_portable_paths(temp_daf_home, monkeypatch):
    """Test that export/import preserves portable paths across different workspaces."""
    # Setup Alice's workspace
    alice_workspace = temp_daf_home / "alice" / "development"
    alice_workspace.mkdir(parents=True)
    alice_project = alice_workspace / "workspace" / "example-repo"
    alice_project.mkdir(parents=True)

    # Create config for Alice
    from devflow.config.models import Config, JiraConfig, RepoConfig, TimeTrackingConfig, SessionSummaryConfig, PromptsConfig, JiraTransitionConfig, WorkspaceDefinition
    alice_config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="alice@example.com",
            transitions={"open": JiraTransitionConfig()}
        ),
        repos=RepoConfig(
            workspaces=[WorkspaceDefinition(name="default", path=str(alice_workspace))],
            last_used_workspace="default"
        ),
        time_tracking=TimeTrackingConfig(),
        session_summary=SessionSummaryConfig(),
        prompts=PromptsConfig(),
    )

    alice_config_loader = ConfigLoader()
    alice_config_loader.save_config(alice_config)

    alice_session_manager = SessionManager(alice_config_loader)
    alice_session = alice_session_manager.create_session(
        name="PROJ-12345",
        goal="Test feature",
        working_directory="example-repo",
        project_path=str(alice_project),
        ai_agent_session_id="alice-uuid",
    )

    # Export Alice's session
    export_manager = ExportManager(alice_config_loader)
    export_path = export_manager.export_sessions(identifiers=["PROJ-12345"])

    assert export_path.exists()

    # Clear sessions and setup Bob's workspace
    (temp_daf_home / "sessions.json").unlink()

    bob_workspace = temp_daf_home / "bob" / "workspace"
    bob_workspace.mkdir(parents=True)
    bob_project = bob_workspace / "workspace" / "example-repo"
    bob_project.mkdir(parents=True)

    # Create config for Bob
    bob_config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="bob@example.com",
            transitions={"open": JiraTransitionConfig()}
        ),
        repos=RepoConfig(
            workspaces=[WorkspaceDefinition(name="default", path=str(bob_workspace))],
            last_used_workspace="default"
        ),
        time_tracking=TimeTrackingConfig(),
        session_summary=SessionSummaryConfig(),
        prompts=PromptsConfig(),
    )

    bob_config_loader = ConfigLoader()
    bob_config_loader.save_config(bob_config)

    bob_export_manager = ExportManager(bob_config_loader)
    imported_keys = bob_export_manager.import_sessions(export_path)

    assert "PROJ-12345" in imported_keys

    # Verify Bob's session uses his workspace
    bob_session_manager = SessionManager(bob_config_loader)
    bob_session = bob_session_manager.get_session("PROJ-12345")

    assert bob_session is not None
    # Access active_session
    conversation = bob_session.conversations["example-repo"].active_session

    # Should have reconstructed path using Bob's workspace
    assert conversation.project_path == str(bob_project)
    assert conversation.relative_path == "workspace/example-repo"
    assert conversation.repo_name == "example-repo"

    # Cleanup
    export_path.unlink()
