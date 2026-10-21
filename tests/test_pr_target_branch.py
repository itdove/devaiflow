"""Tests for PR/MR target branch selection functionality."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devflow.cli.commands.complete_command import (
    BranchPrefetchResult,
    _create_github_pr,
    _create_gitlab_mr,
    _create_pr_mr,
    _generate_pr_description,
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
    def mock_get_default_branch(path, remote=None):
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


def test_select_target_branch_filters_current_branch(monkeypatch, tmp_path):
    """Test current branch is excluded from target branch selection list."""
    def mock_list_remote_branches(path, remote):
        return ["main", "develop", "feature-branch", "release/2.5"]

    def mock_get_default_branch(path, remote=None):
        return "main"

    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list_remote_branches)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)

    # Mock Prompt.ask to simulate user selecting first option (main)
    def mock_prompt_ask(prompt_text, choices, default):
        # Verify current branch is not in choices
        # choices should be ["1", "2", "3", "4"] (4 branches - 1 current = 3, + skip = 4)
        assert choices == ["1", "2", "3", "4"]
        return "1"

    monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt_ask)

    # Create config with auto_select_target_branch=None (prompt mode)
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=None)
    )

    # Call with current_branch="feature-branch"
    result = _select_target_branch(tmp_path, config, upstream_info=None, current_branch="feature-branch")

    # Should return selected branch (main in this case)
    assert result == "main"


def test_select_target_branch_filters_current_when_default(monkeypatch, tmp_path, clean_ci_env):
    """Test filtering works when current branch IS the default branch."""
    def mock_list_remote_branches(path, remote):
        return ["main", "develop", "release/2.5"]

    def mock_get_default_branch(path, remote=None):
        return "main"

    monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda **kw: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list_remote_branches)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)

    # Mock Prompt.ask to simulate user selecting first option (develop)
    def mock_prompt_ask(prompt_text, choices, default):
        # Should have 2 branches (main filtered out) + skip = 3 options
        assert choices == ["1", "2", "3"]
        return "1"

    monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt_ask)

    # Create config
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=None)
    )

    # Call with current_branch="main" (which is also the default)
    result = _select_target_branch(tmp_path, config, upstream_info=None, current_branch="main")

    # Should return develop (first available after filtering)
    assert result == "develop"


def test_select_target_branch_empty_after_filtering(monkeypatch, tmp_path):
    """Test empty list after filtering (only current branch exists remotely)."""
    def mock_list_remote_branches(path, remote):
        # Only the current branch exists
        return ["feature-branch"]

    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list_remote_branches)

    # Create config
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=None)
    )

    # Call with current_branch="feature-branch"
    result = _select_target_branch(tmp_path, config, upstream_info=None, current_branch="feature-branch")

    # Should return None (no branches available after filtering)
    assert result is None


def test_select_target_branch_fork_filters_current(monkeypatch, tmp_path, clean_ci_env):
    """Test fork scenario - current local branch filtered from both upstream and origin branches."""
    def mock_list_remote_branches(path, remote):
        # Return different branches for different remotes
        if remote == "upstream":
            return ["main", "develop", "feature-x", "release/2.5"]
        elif remote == "origin":
            return ["main", "develop", "release/2.5"]
        return []

    def mock_get_default_branch(path, remote=None):
        return "main"

    def mock_get_remote_name_for_url(path, url):
        return "upstream"

    monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda **kw: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list_remote_branches)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_remote_name_for_url", mock_get_remote_name_for_url)

    # Mock Prompt.ask to simulate user selecting first option
    def mock_prompt_ask(prompt_text, choices, default):
        # upstream: 3 branches (feature-x filtered out) + origin: 3 branches = 6 branches + skip = 7 options
        assert choices == ["1", "2", "3", "4", "5", "6", "7"]
        return "1"

    monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt_ask)

    # Create config
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=None)
    )

    # Mock upstream info (fork scenario)
    upstream_info = {
        'upstream_url': 'https://github.com/upstream/repo.git',
        'upstream_owner': 'upstream',
        'upstream_repo': 'repo',
    }

    # Call with current_branch="feature-x"
    result = _select_target_branch(tmp_path, config, upstream_info=upstream_info, current_branch="feature-x")

    # Should return upstream/main (first available after filtering, with remote prefix)
    assert result == "upstream/main"


def test_create_github_pr_strips_remote_prefix_from_target_branch(monkeypatch, tmp_path):
    """Test GitHub PR creation strips remote prefix from target_branch (e.g., 'origin/main' -> 'main')."""
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/owner/repo/pull/123"
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

    # Call with target_branch containing remote prefix
    result = _create_github_pr(
        session=session,
        title="Test PR",
        description="Test description",
        working_dir=tmp_path,
        config=config,
        target_branch="origin/main",  # Remote prefix should be stripped
        upstream_info=None
    )

    # Verify PR URL returned
    assert result == "https://github.com/owner/repo/pull/123"

    # Verify gh pr create command was called with --base main (not origin/main)
    gh_commands = [cmd for cmd in captured_commands if cmd[0] == "gh"]
    assert len(gh_commands) >= 1
    gh_cmd = [cmd for cmd in gh_commands if "create" in cmd][0]

    # Verify command structure
    assert "gh" in gh_cmd
    assert "pr" in gh_cmd
    assert "create" in gh_cmd
    assert "--draft" in gh_cmd
    assert "--base" in gh_cmd
    # Remote prefix should be stripped
    assert "main" in gh_cmd
    assert "origin/main" not in gh_cmd


def test_create_gitlab_mr_strips_remote_prefix_from_target_branch(monkeypatch, tmp_path):
    """Test GitLab MR creation strips remote prefix from target_branch (e.g., 'origin/develop' -> 'develop')."""
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "https://gitlab.example.com/group/project/-/merge_requests/123"
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

    # Call with target_branch containing remote prefix
    result = _create_gitlab_mr(
        session=session,
        title="Test MR",
        description="Test description",
        working_dir=tmp_path,
        config=config,
        target_branch="upstream/develop",  # Remote prefix should be stripped
        upstream_info=None
    )

    # Verify MR URL returned
    assert result == "https://gitlab.example.com/group/project/-/merge_requests/123"

    # Verify glab mr create command was called with --target-branch develop (not upstream/develop)
    glab_commands = [cmd for cmd in captured_commands if cmd[0] == "glab"]
    assert len(glab_commands) >= 1
    glab_cmd = [cmd for cmd in glab_commands if "create" in cmd][0]

    # Verify command structure
    assert "glab" in glab_cmd
    assert "mr" in glab_cmd
    assert "create" in glab_cmd
    assert "--draft" in glab_cmd
    assert "--target-branch" in glab_cmd
    # Remote prefix should be stripped
    assert "develop" in glab_cmd
    assert "upstream/develop" not in glab_cmd


def test_select_target_branch_shows_both_upstream_and_origin(monkeypatch, tmp_path, clean_ci_env):
    """Test that branch selection shows branches from both upstream and origin when upstream exists."""

    # Mock git utilities
    def mock_list_remote_branches(path, remote):
        # Return different branches for different remotes
        if remote == "upstream":
            return ["main", "develop", "release/2.5"]
        elif remote == "origin":
            return ["main", "develop", "feature-a", "feature-b"]
        return []

    def mock_get_default_branch(path, remote=None):
        return "main"

    def mock_get_remote_name_for_url(path, url):
        # Return "upstream" for upstream URL
        if "upstream" in url:
            return "upstream"
        return None

    monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda **kw: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list_remote_branches)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_remote_name_for_url", mock_get_remote_name_for_url)

    # Mock Prompt.ask to verify the options presented
    selected_branch = None
    def mock_prompt_ask(prompt_text, choices, default):
        nonlocal selected_branch
        # Verify we have branches from both remotes
        # upstream: main, develop, release/2.5 (3 branches, but main is current so filtered = 2)
        # origin: main, develop, feature-a, feature-b (4 branches, but main is current so filtered = 3)
        # Total: 2 (upstream) + 3 (origin) = 5 branches + 1 skip = 6 options
        assert choices == ["1", "2", "3", "4", "5", "6"], f"Expected 6 choices, got {choices}"
        # Select the first option (upstream/develop)
        selected_branch = "1"
        return "1"

    monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt_ask)

    # Create config
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=None)
    )

    # Mock upstream info (fork scenario)
    upstream_info = {
        'upstream_url': 'https://github.com/upstream/repo.git',
        'upstream_owner': 'upstream',
        'upstream_repo': 'repo',
    }

    # Call with current_branch="main" (to filter it out)
    result = _select_target_branch(tmp_path, config, upstream_info=upstream_info, current_branch="main")

    # Should return a branch with remote prefix format (e.g., "upstream/develop")
    assert result is not None
    assert "/" in result  # Should have remote prefix when multiple remotes


def test_select_target_branch_origin_only_no_prefix(monkeypatch, tmp_path, clean_ci_env):
    """Test that branch selection shows branches without prefix when only origin exists (no upstream)."""

    # Mock git utilities
    def mock_list_remote_branches(path, remote):
        # Only origin exists
        if remote == "origin":
            return ["main", "develop", "feature-a"]
        return []

    def mock_get_default_branch(path, remote=None):
        return "main"

    monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda **kw: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list_remote_branches)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)

    # Mock Prompt.ask
    def mock_prompt_ask(prompt_text, choices, default):
        # 3 branches total (main filtered out leaves 2) + skip = 3 options
        assert choices == ["1", "2", "3"]
        return "1"

    monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt_ask)

    # Create config
    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=None)
    )

    # No upstream info (not a fork)
    result = _select_target_branch(tmp_path, config, upstream_info=None, current_branch="main")

    # Should return a branch WITHOUT remote prefix when only one remote
    assert result is not None
    # When only origin exists, branches should not have "origin/" prefix
    assert result in ["develop", "feature-a"]


def test_select_target_branch_non_interactive_uses_base_branch(monkeypatch, tmp_path):
    """Test non-interactive mode prefers base_branch over detected default."""
    monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda **kw: True)

    def mock_get_default_branch(path, remote=None):
        return "main"

    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)

    config = _create_minimal_config_mock()
    result = _select_target_branch(tmp_path, config, base_branch="develop")

    assert result == "develop"


def test_select_target_branch_non_interactive_falls_back_without_base_branch(monkeypatch, tmp_path):
    """Test non-interactive mode falls back to detected default when no base_branch."""
    monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda **kw: True)

    def mock_get_default_branch(path, remote=None):
        return "main"

    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)

    config = _create_minimal_config_mock()
    result = _select_target_branch(tmp_path, config, base_branch=None)

    assert result == "main"


def test_select_target_branch_auto_select_uses_base_branch(monkeypatch, tmp_path):
    """Test auto_select_target_branch=True prefers base_branch over detected default."""
    def mock_get_default_branch(path, remote=None):
        return "main"

    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)

    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=True)
    )
    result = _select_target_branch(tmp_path, config, base_branch="staging")

    assert result == "staging"


def test_select_target_branch_auto_select_falls_back_without_base_branch(monkeypatch, tmp_path):
    """Test auto_select_target_branch=True falls back to detected default when no base_branch."""
    def mock_get_default_branch(path, remote=None):
        return "main"

    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)

    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=True)
    )
    result = _select_target_branch(tmp_path, config, base_branch=None)

    assert result == "main"


def test_select_target_branch_interactive_defaults_to_base_branch(monkeypatch, tmp_path, clean_ci_env):
    """Test interactive mode uses base_branch as default selection."""
    def mock_list_remote_branches(path, remote):
        return ["main", "develop", "staging"]

    def mock_get_default_branch(path, remote=None):
        return "main"

    monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda **kw: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list_remote_branches)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", mock_get_default_branch)

    captured_default = {}

    def mock_prompt_ask(prompt_text, choices, default):
        captured_default["value"] = default
        return default

    monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt_ask)

    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_select_target_branch=None)
    )

    result = _select_target_branch(tmp_path, config, upstream_info=None, current_branch="feature-x", base_branch="develop")

    # The default choice should correspond to "develop", not "main"
    # develop is at index 2 in the branch list (main=1, develop=2, staging=3)
    assert captured_default["value"] == "2"
    assert result == "develop"


@pytest.mark.parametrize(
    ("base_branch", "repo_default", "expected", "default_choice"),
    [
        (None, "main", "main", "2"),
        ("release/old", "main", "main", "2"),
        ("release/current", "main", "release/current", "3"),
        ("feature/current", "main", "main", "2"),
        ("release/current", None, "release/current", "3"),
        ("release/old", "feature/current", None, "4"),
        ("release/old", "missing", None, "4"),
        (None, None, None, "4"),
    ],
)
def test_select_target_branch_recommends_available_target(
    monkeypatch, tmp_path, capsys, base_branch, repo_default, expected, default_choice
):
    """The highlighted option and Enter choice must resolve to an available target."""
    monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda: False)
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.GitUtils.list_remote_branches",
        lambda path, remote: ["bugfix/other", "feature/current", "main", "release/current"],
    )
    detect_default = Mock(return_value=repo_default)
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.GitUtils.get_default_branch", detect_default
    )
    prompt = Mock(side_effect=lambda *args, **kwargs: kwargs["default"])
    monkeypatch.setattr("rich.prompt.Prompt.ask", prompt)
    config = _create_minimal_config_mock(PromptsConfig(auto_select_target_branch=None))

    result = _select_target_branch(
        tmp_path, config, current_branch="feature/current", base_branch=base_branch
    )

    assert result == expected
    assert prompt.call_args.kwargs["default"] == default_choice
    detect_default.assert_called_once_with(tmp_path, remote="origin")
    output = capsys.readouterr().out
    assert "feature/current" not in output
    recommended = [line for line in output.splitlines() if "(default)" in line]
    if expected is None:
        assert recommended == []
        assert "No recommended target branch is available" in output
    else:
        assert len(recommended) == 1
        assert f"{default_choice}. {expected} (default)" in recommended[0]
    if repo_default == "main":
        assert "main" in output
        assert "(repository default)" in output


@pytest.mark.parametrize("upstream_remote", ["upstream", "parent"])
@pytest.mark.parametrize("base_branch", ["release/old", "release/current"])
def test_select_target_branch_fork_recommends_destination_remote(
    monkeypatch, tmp_path, capsys, upstream_remote, base_branch
):
    """A saved base found only in the fork must not override the upstream default."""
    monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda: False)
    branch_lists = {
        "origin": ["bugfix/other", "release/current", "trunk"],
        upstream_remote: ["bugfix/other", "feature/current", "trunk"],
    }
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.GitUtils.list_remote_branches",
        lambda path, remote: branch_lists[remote],
    )
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.GitUtils.get_remote_name_for_url",
        lambda path, url: upstream_remote,
    )
    detect_default = Mock(return_value="trunk")
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.GitUtils.get_default_branch", detect_default
    )
    prompt = Mock(side_effect=lambda *args, **kwargs: kwargs["default"])
    monkeypatch.setattr("rich.prompt.Prompt.ask", prompt)
    config = _create_minimal_config_mock(PromptsConfig(auto_select_target_branch=None))

    result = _select_target_branch(
        tmp_path,
        config,
        upstream_info={"upstream_url": "https://github.com/parent/repo.git"},
        current_branch="feature/current",
        base_branch=base_branch,
    )

    assert result == f"{upstream_remote}/trunk"
    detect_default.assert_called_once_with(tmp_path, remote=upstream_remote)
    recommended = [line for line in capsys.readouterr().out.splitlines() if "(default)" in line]
    assert len(recommended) == 1
    assert f"{upstream_remote}/trunk" in recommended[0]


@pytest.mark.parametrize(
    ("non_interactive", "auto_select", "expected"),
    [
        (False, False, None),
        (False, True, "release/old"),
        (True, False, "release/old"),
        (True, None, "release/old"),
    ],
)
def test_select_target_branch_automatic_modes_do_not_validate_remote_targets(
    monkeypatch, tmp_path, non_interactive, auto_select, expected
):
    """Preserve the existing automatic/skip contracts without interactive discovery."""
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.is_non_interactive", lambda: non_interactive
    )
    list_branches = Mock()
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.GitUtils.list_remote_branches", list_branches
    )
    prompt = Mock()
    monkeypatch.setattr("rich.prompt.Prompt.ask", prompt)
    config = _create_minimal_config_mock(PromptsConfig(auto_select_target_branch=auto_select))

    result = _select_target_branch(tmp_path, config, base_branch="release/old")

    assert result == expected
    list_branches.assert_not_called()
    prompt.assert_not_called()


@pytest.mark.parametrize(
    ("create_pr_mr", "target_option", "repo_option", "result_url"),
    [
        (_create_github_pr, "--base", "--repo", "https://github.com/parent/repo/pull/42"),
        (
            _create_gitlab_mr,
            "--target-branch",
            "--target-project",
            "https://gitlab.com/parent/repo/-/merge_requests/42",
        ),
    ],
)
@pytest.mark.parametrize("upstream_remote", ["upstream", "parent"])
@pytest.mark.parametrize("branch", ["main", "release/2.5"])
def test_create_pr_mr_resolves_upstream_remote_prefix(
    monkeypatch,
    tmp_path,
    create_pr_mr,
    target_option,
    repo_option,
    result_url,
    upstream_remote,
    branch,
):
    """A recommendation on a custom-named parent remote must target that branch."""
    run = Mock(return_value=subprocess.CompletedProcess([], 0, result_url, ""))
    monkeypatch.setattr("devflow.cli.commands.complete_command.subprocess.run", run)
    monkeypatch.setattr("devflow.cli.commands.complete_command.require_tool", lambda *args: None)
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.GitUtils.get_remote_name_for_url",
        lambda path, url: upstream_remote,
    )
    config = _create_minimal_config_mock(PromptsConfig(auto_create_pr_status="draft"))

    result = create_pr_mr(
        session=Mock(),
        title="Test change",
        description="Test description",
        working_dir=tmp_path,
        config=config,
        target_branch=f"{upstream_remote}/{branch}",
        upstream_info={
            "upstream_url": "https://example.com/parent/repo.git",
            "upstream_owner": "parent",
            "upstream_repo": "repo",
            "detection_method": "gh_cli",
        },
    )

    assert result == result_url
    command = run.call_args.args[0]
    assert command[command.index(target_option) + 1] == branch
    assert command[command.index(repo_option) + 1] == "parent/repo"


@pytest.mark.parametrize("repo_type", ["github", "gitlab"])
@pytest.mark.parametrize("use_prefetch", [False, True])
@pytest.mark.parametrize("stored_base", [None, "main", "master", "release/old", "release/current"])
def test_create_pr_mr_proposes_destination_default_unless_base_is_explicit_and_available(
    monkeypatch, tmp_path, repo_type, use_prefetch, stored_base
):
    """An inferred origin default is not an explicit base for a fork's parent."""
    module = "devflow.cli.commands.complete_command"
    monkeypatch.setattr(f"{module}.is_non_interactive", lambda: False)
    monkeypatch.setattr(f"{module}.GitUtils.detect_repo_type", lambda path: repo_type)
    monkeypatch.setattr(f"{module}.GitUtils.has_unpushed_branch_commits", lambda *args: False)
    monkeypatch.setattr(f"{module}._generate_pr_description", lambda *args, **kwargs: "Description")
    monkeypatch.setattr(f"{module}._generate_pr_title", lambda *args: "Test change")
    upstream_info = {"upstream_url": "https://example.com/parent/repo.git"}
    monkeypatch.setattr(
        f"{module}.GitUtils.get_fork_upstream_info", lambda *args, **kwargs: upstream_info
    )
    monkeypatch.setattr(f"{module}.GitUtils.get_remote_name_for_url", lambda *args: "parent")
    monkeypatch.setattr(
        f"{module}.GitUtils.get_default_branch",
        lambda path, remote=None: "trunk" if remote == "parent" else "main",
    )
    branches = {
        "origin": ["bugfix/other", "main", "release/current"],
        "parent": ["bugfix/other", "feature/current", "main", "release/current", "trunk"],
    }
    monkeypatch.setattr(
        f"{module}.GitUtils.list_remote_branches", lambda path, remote: branches[remote]
    )
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *args, **kwargs: kwargs["default"])
    create = Mock(return_value="https://example.com/parent/repo/pull/42")
    monkeypatch.setattr(
        f"{module}.{'_create_github_pr' if repo_type == 'github' else '_create_gitlab_mr'}", create
    )
    session = Mock()
    session.name = "session-42"
    session.active_conversation = Mock(branch="feature/current", base_branch=stored_base, prs=[])
    session_manager = Mock()
    session_manager.config_loader.load_config.return_value = _create_minimal_config_mock(
        PromptsConfig(auto_select_target_branch=None)
    )
    prefetch = Mock() if use_prefetch else None
    if prefetch:
        prefetch.resolve.return_value = BranchPrefetchResult(
            remote_branches=branches, upstream_info=upstream_info, completed=True
        )

    result = _create_pr_mr(session, tmp_path, session_manager, branch_prefetch=prefetch)

    assert result == create.return_value
    expected = "release/current" if stored_base == "release/current" else "trunk"
    assert create.call_args.args[5] == f"parent/{expected}"
    session_manager.update_session.assert_called_once_with(session)


@pytest.mark.parametrize(
    ("repo_type", "create_pr_mr", "body_option", "pr_url"),
    [
        ("github", _create_github_pr, "--body", "https://github.com/owner/repo/pull/42"),
        ("gitlab", _create_gitlab_mr, "--description", "https://gitlab.com/owner/repo/-/merge_requests/42"),
    ],
)
def test_headingless_ai_output_reaches_github_and_gitlab_cli_as_filled_template(
    monkeypatch, tmp_path, repo_type, create_pr_mr, body_option, pr_url
):
    """Completion must pass the deterministic template fallback to either host CLI."""
    template = """## Description
<!-- Summarize the change. -->

## Related issue
<!-- Link the related issue or write N/A. -->

## Testing
<!-- Describe test evidence. -->

## Commands run
```text
# Record command evidence here
```
"""
    template_path = tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md"
    template_path.parent.mkdir()
    template_path.write_text(template, encoding="utf-8")

    session = Mock()
    session.name = "session-42"
    session.issue_key = "owner/repo#42"
    session.issue_tracker = repo_type
    session.goal = "Fix the parser regression"
    session.agent_backend = "claude"
    session.model_profile = None
    session.active_conversation = Mock(branch="fix/parser")

    config_loader = Mock()
    config_loader.load_config.return_value = None
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command._try_discover_org_template",
        lambda _working_dir: None,
    )
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.GitUtils.get_commit_log",
        lambda *_args: "fix: handle malformed input",
    )
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.GitUtils.get_changed_files",
        lambda *_args: ["src/parser.py", "tests/test_parser.py"],
    )

    captured_commands = []

    def mock_run(command, *args, **kwargs):
        captured_commands.append(command)
        result = Mock()
        result.returncode = 0
        result.stdout = pr_url
        result.stderr = ""
        return result

    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.subprocess.run", mock_run
    )
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.require_tool",
        lambda *_args: None,
    )

    with (
        patch("devflow.git.pr_template.ConfigLoader") as mock_config_loader_class,
        patch("devflow.agent.factory.resolve_agent_backend", return_value="claude"),
        patch("devflow.agent.create_agent_client") as mock_create_agent,
    ):
        mock_agent = Mock()
        mock_agent.generate_text.return_value = (
            "Test command evidence was not captured."
        )
        mock_agent.get_agent_name.return_value = "claude"
        mock_create_agent.return_value = mock_agent

        mock_loader = Mock()
        mock_loader.config_file.exists.return_value = False
        mock_config_loader_class.return_value = mock_loader

        description = _generate_pr_description(
            session,
            tmp_path,
            config_loader,
            target_branch="main",
            display_name="session-42_pr",
        )

    config = _create_minimal_config_mock(
        prompts_config=PromptsConfig(auto_create_pr_status="draft")
    )
    result = create_pr_mr(
        session=session,
        title="Fix the parser regression",
        description=description,
        working_dir=tmp_path,
        config=config,
        target_branch="main",
        upstream_info={},
    )

    assert result == pr_url
    assert len(captured_commands) == 1
    command = captured_commands[0]
    assert command[command.index(body_option) + 1] == description
    assert "## Description" in description
    assert "## Related issue" in description
    assert "## Testing" in description
    assert "## Commands run" in description
    assert "Fix the parser regression" in description
    assert "<!--" not in description
