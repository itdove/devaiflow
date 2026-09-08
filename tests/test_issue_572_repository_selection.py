"""Focused tests for issue-derived repository defaults in ``daf open``."""

import subprocess
from pathlib import Path

import pytest
from rich.prompt import Confirm, Prompt

from devflow.cli.commands.open_command import _prompt_for_working_directory
from devflow.cli.utils import unified_project_selection
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkspaceDefinition
from devflow.session.manager import SessionManager


@pytest.fixture
def workspace_with_repositories(tmp_path):
    """Create a workspace containing two generic git repositories."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    for repository in ("repo-a", "repo-b"):
        repository_path = workspace / repository
        repository_path.mkdir()
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=repository_path,
            capture_output=True,
            check=True,
        )

    return workspace


@pytest.fixture
def config_loader_with_workspace(workspace_with_repositories, temp_daf_home):
    """Create a config loader pointing at the test workspace."""
    config_loader = ConfigLoader()
    config_loader.create_default_config()

    config = config_loader.load_config()
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(workspace_with_repositories))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    return config_loader


def _remember_repository(config_loader, repository: str) -> None:
    """Set the remembered repository for the test workspace."""
    config = config_loader.load_config()
    config.prompts.last_used_repo_per_workspace["default"] = repository
    config_loader.save_config(config)


def test_issue_repository_precedes_remembered_default(
    workspace_with_repositories, config_loader_with_workspace, monkeypatch
):
    """An available issue repository is the default over the remembered repository."""
    _remember_repository(config_loader_with_workspace, "repo-b")

    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: False)
    prompt_defaults = []

    def mock_prompt(prompt, **kwargs):
        prompt_defaults.append(kwargs["default"])
        return kwargs["default"]

    monkeypatch.setattr(Prompt, "ask", mock_prompt)

    selected_paths, is_multi = unified_project_selection(
        workspace_path=str(workspace_with_repositories),
        repo_options=["repo-a", "repo-b"],
        suggested_repo="repo-a",
        suggested_repo_source="from issue",
        allow_multi_project=True,
        config_loader=config_loader_with_workspace,
        workspace_name="default",
    )

    assert prompt_defaults == ["1"]
    assert selected_paths == [str(workspace_with_repositories / "repo-a")]
    assert is_multi is False


def test_missing_issue_repository_preserves_remembered_default(
    workspace_with_repositories, config_loader_with_workspace, monkeypatch
):
    """A missing issue repository falls back to the remembered repository."""
    _remember_repository(config_loader_with_workspace, "repo-b")

    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: False)
    prompt_defaults = []

    def mock_prompt(prompt, **kwargs):
        prompt_defaults.append(kwargs["default"])
        return kwargs["default"]

    monkeypatch.setattr(Prompt, "ask", mock_prompt)

    selected_paths, is_multi = unified_project_selection(
        workspace_path=str(workspace_with_repositories),
        repo_options=["repo-a", "repo-b"],
        suggested_repo="repo-c",
        suggested_repo_source="from issue",
        allow_multi_project=True,
        config_loader=config_loader_with_workspace,
        workspace_name="default",
    )

    assert prompt_defaults == ["2"]
    assert selected_paths == [str(workspace_with_repositories / "repo-b")]
    assert is_multi is False


def test_open_uses_issue_repository_when_remembered_repository_differs(
    workspace_with_repositories, config_loader_with_workspace, monkeypatch
):
    """The open workflow passes the issue-derived repository through as the default."""
    _remember_repository(config_loader_with_workspace, "repo-b")
    session_manager = SessionManager(config_loader_with_workspace)
    session = session_manager.create_session(
        name="test-session",
        goal="Select the issue repository",
        issue_key="owner/repo-a#42",
    )
    session.issue_tracker = "github"
    session_manager.update_session(session)

    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: False)
    monkeypatch.setattr(Prompt, "ask", lambda prompt, default=None: default)

    assert _prompt_for_working_directory(
        session=session,
        config_loader=config_loader_with_workspace,
        session_manager=session_manager,
        selected_workspace_name="default",
    ) is True

    updated_session = session_manager.get_session(session.name)
    assert updated_session.active_conversation is not None
    assert Path(updated_session.active_conversation.project_path).name == "repo-a"
