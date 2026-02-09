"""Tests for PR/MR target branch selection functionality."""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from devflow.cli.commands.complete_command import (
    _create_github_pr,
    _create_gitlab_mr,
    _select_target_branch,
)
from devflow.config.models import PromptsConfig


def _create_minimal_config_mock(prompts_config=None):
    """Create a minimal mock config for testing."""
    config = Mock()
    config.prompts = prompts_config or PromptsConfig()
    return config


def test_create_github_pr_with_target_branch(monkeypatch, tmp_path):
    """Test GitHub PR creation includes --base flag when target_branch provided."""
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)
        mock_result = Mock()
        mock_result.returncode = 0

        # Handle different commands
        if "repo" in cmd and "view" in cmd:
            # Fork detection query - return empty (no fork)
            mock_result.stdout = "{}"
        elif "pr" in cmd and "create" in cmd:
            # PR creation - return PR URL
            mock_result.stdout = "https://github.com/owner/repo/pull/123"
        else:
            mock_result.stdout = ""

        mock_result.stderr = ""
        return mock_result

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("devflow.cli.commands.complete_command.require_tool", lambda tool, desc: None)

    # Mock session
    session = Mock()

    # Create config with auto_create_pr_status set to "draft"
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_create_pr_status="draft")
    )

    # Call with target_branch
    result = _create_github_pr(
        session=session,
        title="Test PR",
        description="Test description",
        working_dir=tmp_path,
        config=config,
        target_branch="release/2.5",
        upstream_info=None
    )

    # Verify PR URL returned
    assert result == "https://github.com/owner/repo/pull/123"

    # Verify gh pr create command was called with --base flag
    gh_commands = [cmd for cmd in captured_commands if cmd[0] == "gh"]
    # Should have fork detection + PR creation
    assert len(gh_commands) >= 1
    # Get the PR creation command (last gh command)
    gh_cmd = [cmd for cmd in gh_commands if "create" in cmd][0]

    # Verify command structure
    assert "gh" in gh_cmd
    assert "pr" in gh_cmd
    assert "create" in gh_cmd
    assert "--draft" in gh_cmd
    assert "--base" in gh_cmd
    assert "release/2.5" in gh_cmd


def test_create_github_pr_without_target_branch(monkeypatch, tmp_path):
    """Test GitHub PR creation without --base flag when target_branch is None."""
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)
        mock_result = Mock()
        mock_result.returncode = 0

        # Handle different commands
        if "repo" in cmd and "view" in cmd:
            # Fork detection query - return empty (no fork)
            mock_result.stdout = "{}"
        elif "pr" in cmd and "create" in cmd:
            # PR creation - return PR URL
            mock_result.stdout = "https://github.com/owner/repo/pull/123"
        else:
            mock_result.stdout = ""

        mock_result.stderr = ""
        return mock_result

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("devflow.cli.commands.complete_command.require_tool", lambda tool, desc: None)

    # Mock session
    session = Mock()

    # Create config with auto_create_pr_status set to "draft"
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_create_pr_status="draft")
    )

    # Call without target_branch
    result = _create_github_pr(
        session=session,
        title="Test PR",
        description="Test description",
        working_dir=tmp_path,
        config=config,
        target_branch=None,
        upstream_info=None
    )

    # Verify PR URL returned
    assert result == "https://github.com/owner/repo/pull/123"

    # Verify gh pr create command was called without --base flag
    gh_commands = [cmd for cmd in captured_commands if cmd[0] == "gh"]
    # Should have fork detection + PR creation
    assert len(gh_commands) >= 1
    # Get the PR creation command (last gh command)
    gh_cmd = [cmd for cmd in gh_commands if "create" in cmd][0]

    # Verify command structure
    assert "gh" in gh_cmd
    assert "pr" in gh_cmd
    assert "create" in gh_cmd
    assert "--draft" in gh_cmd
    assert "--base" not in gh_cmd


def test_create_github_pr_with_fork_and_target_branch(monkeypatch, tmp_path):
    """Test GitHub PR creation with both --repo and --base flags for fork scenario."""
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/upstream/repo/pull/123"
        mock_result.stderr = ""
        return mock_result

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("devflow.cli.commands.complete_command.require_tool", lambda tool, desc: None)

    # Mock session
    session = Mock()

    # Create config with auto_create_pr_status set to "draft"
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_create_pr_status="draft")
    )

    # Mock upstream info (fork scenario)
    upstream_info = {
        'upstream_url': 'https://github.com/upstream/repo.git',
        'upstream_owner': 'upstream',
        'upstream_repo': 'repo',
        'detection_method': 'gh_cli'
    }

    # Call with both upstream_info and target_branch
    result = _create_github_pr(
        session=session,
        title="Test PR from Fork",
        description="Test description",
        working_dir=tmp_path,
        config=config,
        target_branch="release/2.5",
        upstream_info=upstream_info
    )

    # Verify PR URL returned
    assert result == "https://github.com/upstream/repo/pull/123"

    # Verify gh pr create command was called with both --repo and --base flags
    gh_commands = [cmd for cmd in captured_commands if cmd[0] == "gh"]
    assert len(gh_commands) == 1
    gh_cmd = gh_commands[0]

    # Verify command structure
    assert "gh" in gh_cmd
    assert "pr" in gh_cmd
    assert "create" in gh_cmd
    assert "--draft" in gh_cmd
    assert "--repo" in gh_cmd
    assert "upstream/repo" in gh_cmd
    assert "--base" in gh_cmd
    assert "release/2.5" in gh_cmd


def test_create_gitlab_mr_with_target_branch(monkeypatch, tmp_path):
    """Test GitLab MR creation includes --target-branch flag when target_branch provided."""
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)
        mock_result = Mock()
        mock_result.returncode = 0

        # Handle different commands
        if "repo" in cmd and "view" in cmd:
            # Fork detection query - return empty (no fork)
            mock_result.stdout = "{}"
        elif "mr" in cmd and "create" in cmd:
            # MR creation - return MR URL
            mock_result.stdout = "https://gitlab.example.com/group/project/-/merge_requests/123"
        else:
            mock_result.stdout = ""

        mock_result.stderr = ""
        return mock_result

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("devflow.cli.commands.complete_command.require_tool", lambda tool, desc: None)

    # Mock session
    session = Mock()

    # Create config with auto_create_pr_status set to "draft"
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_create_pr_status="draft")
    )

    # Call with target_branch
    result = _create_gitlab_mr(
        session=session,
        title="Test MR",
        description="Test description",
        working_dir=tmp_path,
        config=config,
        target_branch="release/3.0",
        upstream_info=None
    )

    # Verify MR URL returned
    assert result == "https://gitlab.example.com/group/project/-/merge_requests/123"

    # Verify glab mr create command was called with --target-branch flag
    glab_commands = [cmd for cmd in captured_commands if cmd[0] == "glab"]
    # Should have fork detection + MR creation
    assert len(glab_commands) >= 1
    # Get the MR creation command (last glab command)
    glab_cmd = [cmd for cmd in glab_commands if "create" in cmd][0]

    # Verify command structure
    assert "glab" in glab_cmd
    assert "mr" in glab_cmd
    assert "create" in glab_cmd
    assert "--draft" in glab_cmd
    assert "--target-branch" in glab_cmd
    assert "release/3.0" in glab_cmd


def test_create_gitlab_mr_without_target_branch(monkeypatch, tmp_path):
    """Test GitLab MR creation without --target-branch flag when target_branch is None."""
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)
        mock_result = Mock()
        mock_result.returncode = 0

        # Handle different commands
        if "repo" in cmd and "view" in cmd:
            # Fork detection query - return empty (no fork)
            mock_result.stdout = "{}"
        elif "mr" in cmd and "create" in cmd:
            # MR creation - return MR URL
            mock_result.stdout = "https://gitlab.example.com/group/project/-/merge_requests/123"
        else:
            mock_result.stdout = ""

        mock_result.stderr = ""
        return mock_result

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("devflow.cli.commands.complete_command.require_tool", lambda tool, desc: None)

    # Mock session
    session = Mock()

    # Create config with auto_create_pr_status set to "draft"
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_create_pr_status="draft")
    )

    # Call without target_branch
    result = _create_gitlab_mr(
        session=session,
        title="Test MR",
        description="Test description",
        working_dir=tmp_path,
        config=config,
        target_branch=None,
        upstream_info=None
    )

    # Verify MR URL returned
    assert result == "https://gitlab.example.com/group/project/-/merge_requests/123"

    # Verify glab mr create command was called without --target-branch flag
    glab_commands = [cmd for cmd in captured_commands if cmd[0] == "glab"]
    # Should have fork detection + MR creation
    assert len(glab_commands) >= 1
    # Get the MR creation command (last glab command)
    glab_cmd = [cmd for cmd in glab_commands if "create" in cmd][0]

    # Verify command structure
    assert "glab" in glab_cmd
    assert "mr" in glab_cmd
    assert "create" in glab_cmd
    assert "--draft" in glab_cmd
    assert "--target-branch" not in glab_cmd


def test_create_gitlab_mr_with_fork_and_target_branch(monkeypatch, tmp_path):
    """Test GitLab MR creation with both --target-project and --target-branch flags."""
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "https://gitlab.example.com/upstream/project/-/merge_requests/123"
        mock_result.stderr = ""
        return mock_result

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("devflow.cli.commands.complete_command.require_tool", lambda tool, desc: None)

    # Mock session
    session = Mock()

    # Create config with auto_create_pr_status set to "draft"
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_create_pr_status="draft")
    )

    # Mock upstream info (fork scenario)
    upstream_info = {
        'upstream_url': 'https://gitlab.example.com/upstream/project.git',
        'upstream_owner': 'upstream',
        'upstream_repo': 'project',
        'detection_method': 'glab_cli'
    }

    # Call with both upstream_info and target_branch
    result = _create_gitlab_mr(
        session=session,
        title="Test MR from Fork",
        description="Test description",
        working_dir=tmp_path,
        config=config,
        target_branch="release/3.0",
        upstream_info=upstream_info
    )

    # Verify MR URL returned
    assert result == "https://gitlab.example.com/upstream/project/-/merge_requests/123"

    # Verify glab mr create command was called with both --target-project and --target-branch flags
    glab_commands = [cmd for cmd in captured_commands if cmd[0] == "glab"]
    assert len(glab_commands) == 1
    glab_cmd = glab_commands[0]

    # Verify command structure
    assert "glab" in glab_cmd
    assert "mr" in glab_cmd
    assert "create" in glab_cmd
    assert "--draft" in glab_cmd
    assert "--target-project" in glab_cmd
    assert "upstream/project" in glab_cmd
    assert "--target-branch" in glab_cmd
    assert "release/3.0" in glab_cmd


def test_select_target_branch_config_false(monkeypatch, tmp_path):
    """Test _select_target_branch with auto_select_target_branch=False (skip selection)."""
    # Create config with auto_select_target_branch=False
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=False)
    )

    # Should return None (skip branch selection)
    result = _select_target_branch(tmp_path, config, upstream_info=None)

    assert result is None


def test_select_target_branch_config_true(monkeypatch, tmp_path):
    """Test _select_target_branch with auto_select_target_branch=True (auto-select default)."""
    def mock_get_default_branch(path):
        return "main"

    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)

    # Create config with auto_select_target_branch=True
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=True)
    )

    # Should return default branch without prompting
    result = _select_target_branch(tmp_path, config, upstream_info=None)

    assert result == "main"


def test_select_target_branch_empty_branch_list(monkeypatch, tmp_path):
    """Test _select_target_branch handles empty branch list gracefully."""
    def mock_list_remote_branches(path, remote):
        return []

    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list_remote_branches)

    # Create config with auto_select_target_branch=None (prompt mode)
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=None)
    )

    # Should return None when no branches found
    result = _select_target_branch(tmp_path, config, upstream_info=None)

    assert result is None
