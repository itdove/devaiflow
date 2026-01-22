"""Tests for daf release command functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from devflow.release.version import Version
from devflow.cli.commands.release_command import suggest_release, create_release


class TestSuggestReleaseCommand:
    """Test the suggest_release() command function."""

    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    def test_suggest_release_with_dev_version_suggests_current_version(
        self, mock_console, mock_manager_class
    ):
        """Test that -dev versions suggest the current version (without -dev).

        Bug: PROJ-XXXXX
        When main is at 0.2.0-dev (working toward 0.2.0), suggesting a minor
        release should propose 0.2.0, not 1.0.0.
        """
        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock suggest_release_type to return minor
        mock_manager.suggest_release_type.return_value = (
            "minor",
            "Found features since v0.1.0",
            {'breaking': [], 'features': ['feat: something'], 'fixes': [], 'other': []}
        )

        # Mock read_current_version to return 0.2.0-dev
        mock_manager.read_current_version.return_value = ("0.2.0-dev", "0.2.0-dev")

        # Execute
        suggest_release()

        # Verify that the suggested command shows 0.2.0 (not 1.0.0)
        # We need to check the console.print calls
        print_calls = [str(call) for call in mock_console.print.call_args_list]

        # Find the call that contains "daf release"
        release_cmd_found = False
        for call in print_calls:
            if "daf release 0.2.0" in call:
                release_cmd_found = True
                break

        assert release_cmd_found, f"Expected 'daf release 0.2.0' in output, but got: {print_calls}"

    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    def test_suggest_release_without_dev_version_bumps_version(
        self, mock_console, mock_manager_class
    ):
        """Test that released versions (without -dev) properly bump the version.

        When main is at 0.1.0 (a released version), suggesting a minor release
        should propose 0.2.0 (bump minor).
        """
        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock suggest_release_type to return minor
        mock_manager.suggest_release_type.return_value = (
            "minor",
            "Found features since v0.1.0",
            {'breaking': [], 'features': ['feat: something'], 'fixes': [], 'other': []}
        )

        # Mock read_current_version to return 0.1.0 (no -dev suffix)
        mock_manager.read_current_version.return_value = ("0.1.0", "0.1.0")

        # Execute
        suggest_release()

        # Verify that the suggested command shows 0.2.0 (bumped from 0.1.0)
        print_calls = [str(call) for call in mock_console.print.call_args_list]

        release_cmd_found = False
        for call in print_calls:
            if "daf release 0.2.0" in call:
                release_cmd_found = True
                break

        assert release_cmd_found, f"Expected 'daf release 0.2.0' in output, but got: {print_calls}"

    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    def test_suggest_release_major_with_dev_version(
        self, mock_console, mock_manager_class
    ):
        """Test that -dev versions with major suggestion use current version.

        When main is at 1.0.0-dev and we suggest a major release,
        it should propose 1.0.0 (not 2.0.0).
        """
        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock suggest_release_type to return major
        mock_manager.suggest_release_type.return_value = (
            "major",
            "Found breaking changes",
            {'breaking': ['feat!: breaking'], 'features': [], 'fixes': [], 'other': []}
        )

        # Mock read_current_version to return 1.0.0-dev
        mock_manager.read_current_version.return_value = ("1.0.0-dev", "1.0.0-dev")

        # Execute
        suggest_release()

        # Verify that the suggested command shows 1.0.0 (not 2.0.0)
        print_calls = [str(call) for call in mock_console.print.call_args_list]

        release_cmd_found = False
        for call in print_calls:
            if "daf release 1.0.0" in call:
                release_cmd_found = True
                break

        assert release_cmd_found, f"Expected 'daf release 1.0.0' in output, but got: {print_calls}"

    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    def test_suggest_release_patch_with_dev_version(
        self, mock_console, mock_manager_class
    ):
        """Test that -dev versions with patch suggestion use current version.

        When a release branch is at 0.2.1-dev and we suggest a patch release,
        it should propose 0.2.1 (not 0.2.2).
        """
        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock suggest_release_type to return patch
        mock_manager.suggest_release_type.return_value = (
            "patch",
            "Found bug fixes",
            {'breaking': [], 'features': [], 'fixes': ['fix: bug'], 'other': []}
        )

        # Mock read_current_version to return 0.2.1-dev
        mock_manager.read_current_version.return_value = ("0.2.1-dev", "0.2.1-dev")

        # Execute
        suggest_release()

        # Verify that the suggested command shows 0.2.1 (not 0.2.2)
        print_calls = [str(call) for call in mock_console.print.call_args_list]

        release_cmd_found = False
        for call in print_calls:
            if "daf release 0.2.1" in call:
                release_cmd_found = True
                break

        assert release_cmd_found, f"Expected 'daf release 0.2.1' in output, but got: {print_calls}"

    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    def test_suggest_release_major_without_dev_bumps_major(
        self, mock_console, mock_manager_class
    ):
        """Test that released versions with major suggestion bump major version.

        When main is at 0.2.0 (released) and we suggest a major release,
        it should propose 1.0.0 (bump major from 0.2.0).
        """
        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock suggest_release_type to return major
        mock_manager.suggest_release_type.return_value = (
            "major",
            "Found breaking changes",
            {'breaking': ['feat!: breaking'], 'features': [], 'fixes': [], 'other': []}
        )

        # Mock read_current_version to return 0.2.0 (no -dev)
        mock_manager.read_current_version.return_value = ("0.2.0", "0.2.0")

        # Execute
        suggest_release()

        # Verify that the suggested command shows 1.0.0 (bumped major)
        print_calls = [str(call) for call in mock_console.print.call_args_list]

        release_cmd_found = False
        for call in print_calls:
            if "daf release 1.0.0" in call:
                release_cmd_found = True
                break

        assert release_cmd_found, f"Expected 'daf release 1.0.0' in output, but got: {print_calls}"

    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    def test_suggest_release_patch_without_dev_bumps_patch(
        self, mock_console, mock_manager_class
    ):
        """Test that released versions with patch suggestion bump patch version.

        When a release branch is at 0.2.0 (released) and we suggest a patch,
        it should propose 0.2.1 (bump patch from 0.2.0).
        """
        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock suggest_release_type to return patch
        mock_manager.suggest_release_type.return_value = (
            "patch",
            "Found bug fixes",
            {'breaking': [], 'features': [], 'fixes': ['fix: bug'], 'other': []}
        )

        # Mock read_current_version to return 0.2.0 (no -dev)
        mock_manager.read_current_version.return_value = ("0.2.0", "0.2.0")

        # Execute
        suggest_release()

        # Verify that the suggested command shows 0.2.1 (bumped patch)
        print_calls = [str(call) for call in mock_console.print.call_args_list]

        release_cmd_found = False
        for call in print_calls:
            if "daf release 0.2.1" in call:
                release_cmd_found = True
                break

        assert release_cmd_found, f"Expected 'daf release 0.2.1' in output, but got: {print_calls}"


class TestCreateReleaseClaudeGuard:
    """Test the create_release() safety guard for Claude Code sessions."""

    def test_create_release_blocks_when_inside_claude_code(self, monkeypatch):
        """Test that create_release (without --dry-run) is blocked inside Claude Code.

        This prevents integration tests from running forbidden commands (daf export,
        daf import, daf open, daf complete) when inside a Claude Code session.
        """
        # Set DEVAIFLOW_IN_SESSION to simulate running inside an AI agent session
        monkeypatch.setenv("DEVAIFLOW_IN_SESSION", "1")

        # Attempt to run create_release without dry-run flag
        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            create_release("1.0.0", dry_run=False)

        assert exc_info.value.code == 1

    def test_create_release_allows_dry_run_inside_claude_code(self, monkeypatch, tmp_path):
        """Test that create_release with --dry-run is ALLOWED inside Claude Code.

        Dry-run mode is read-only and skips integration tests, so it's safe
        to run inside Claude Code sessions.
        """
        # Set AI_AGENT_SESSION_ID to simulate running inside Claude Code
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-session-123")

        # Create a temporary git repository
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        # Mock the ReleaseManager and other dependencies
        with patch("devflow.cli.commands.release_command.check_release_permission") as mock_perm:
            with patch("devflow.cli.commands.release_command.ReleaseManager"):
                with patch("devflow.cli.commands.release_command.Path.cwd") as mock_cwd:
                    mock_cwd.return_value = repo_path
                    mock_perm.return_value = (True, "User has permission")

                    # Should NOT raise SystemExit when dry_run=True
                    # (Will fail with other errors since we're not fully mocking,
                    # but it should NOT fail with the Claude Code guard)
                    try:
                        create_release("1.0.0", dry_run=True)
                    except SystemExit as e:
                        # If it exits, it should NOT be with code 1 (Claude guard)
                        assert e.code != 1, "Should not block dry-run mode inside Claude Code"
                    except Exception:
                        # Other exceptions are fine - we're testing the guard specifically
                        pass

    def test_create_release_allows_outside_claude_code(self, monkeypatch, tmp_path):
        """Test that create_release works normally when NOT inside Claude Code."""
        # Ensure AI_AGENT_SESSION_ID is not set
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        # Create a temporary git repository
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        # Mock the ReleaseManager and other dependencies
        with patch("devflow.cli.commands.release_command.check_release_permission") as mock_perm:
            with patch("devflow.cli.commands.release_command.ReleaseManager"):
                with patch("devflow.cli.commands.release_command.Path.cwd") as mock_cwd:
                    mock_cwd.return_value = repo_path
                    mock_perm.return_value = (True, "User has permission")

                    # Should NOT raise SystemExit with code 1 (Claude guard)
                    try:
                        create_release("1.0.0", dry_run=False)
                    except SystemExit as e:
                        assert e.code != 1, "Should not block when outside Claude Code"
                    except Exception:
                        # Other exceptions are fine - we're testing the guard specifically
                        pass

    def test_suggest_release_allowed_inside_claude_code(self, monkeypatch):
        """Test that suggest_release is ALLOWED inside Claude Code.

        suggest_release is read-only (doesn't run tests or modify anything),
        so it's safe to run inside Claude Code sessions.
        """
        # Set AI_AGENT_SESSION_ID to simulate running inside Claude Code
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-session-123")

        # Mock the ReleaseManager
        with patch("devflow.cli.commands.release_command.ReleaseManager") as mock_manager_class:
            with patch("devflow.cli.commands.release_command.console"):
                mock_manager = Mock()
                mock_manager_class.return_value = mock_manager
                mock_manager.suggest_release_type.return_value = (
                    "minor",
                    "Test explanation",
                    {'breaking': [], 'features': ['feat: test'], 'fixes': [], 'other': []}
                )
                mock_manager.read_current_version.return_value = ("0.1.0", "0.1.0")

                # Should NOT raise SystemExit
                try:
                    suggest_release()
                except SystemExit as e:
                    pytest.fail(f"suggest_release should not exit when inside Claude Code, but got exit code {e.code}")


class TestApproveReleaseCommand:
    """Test the approve_release() command function."""

    @patch("devflow.cli.utils.check_outside_ai_session")
    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    @patch("devflow.cli.commands.release_command.click.confirm")
    @patch("devflow.release.permissions.get_git_remote_url")
    @patch("devflow.release.permissions.parse_git_remote")
    def test_approve_release_validates_and_pushes_for_minor_release(
        self, mock_parse_remote, mock_get_remote_url, mock_confirm, mock_console, mock_manager_class, mock_check_outside
    ):
        """Test approve_release validates and pushes for a minor release."""
        from devflow.release.permissions import Platform
        from devflow.cli.commands.release_command import approve_release

        # Mock check_outside_ai_session to not exit
        mock_check_outside.return_value = None

        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock validation returning success with release branch
        mock_manager.validate_release_prepared.return_value = (
            True,
            "Release preparation validated",
            "release/0.2"
        )

        # Mock push operations
        mock_manager.push_to_remote.return_value = (True, "Pushed successfully")

        # Mock platform detection
        mock_get_remote_url.return_value = "git@gitlab.example.com:group/repo.git"
        mock_parse_remote.return_value = (Platform.GITLAB, "group", "repo")

        # Mock GitLab release creation
        mock_manager.create_gitlab_release.return_value = (
            True,
            "Created GitLab release",
            "https://gitlab.example.com/group/repo/-/releases/v0.2.0"
        )

        # Mock main merge
        mock_manager.merge_to_main_and_bump.return_value = (
            True,
            "Merged to main and bumped to 1.0.0-dev"
        )

        # Mock confirmation
        mock_confirm.return_value = True

        # Execute
        approve_release(version="0.2.0", dry_run=False)

        # Verify validation called
        mock_manager.validate_release_prepared.assert_called_once()

        # Verify push called for branch and tag
        assert mock_manager.push_to_remote.call_count == 2

        # Verify GitLab release created
        mock_manager.create_gitlab_release.assert_called_once()

        # Verify main merge called
        mock_manager.merge_to_main_and_bump.assert_called_once_with(
            "release/0.2", Version(0, 2, 0, False), dry_run=False
        )

    @patch("devflow.cli.utils.check_outside_ai_session")
    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    def test_approve_release_fails_when_validation_fails(
        self, mock_console, mock_manager_class, mock_check_outside
    ):
        """Test approve_release exits when validation fails."""
        from devflow.cli.commands.release_command import approve_release

        # Mock check_outside_ai_session to not exit
        mock_check_outside.return_value = None

        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock validation returning failure
        mock_manager.validate_release_prepared.return_value = (
            False,
            "Tag 'v0.2.0' does not exist",
            None
        )

        # Execute
        approve_release(version="0.2.0", dry_run=False)

        # Verify that push operations were NOT called
        mock_manager.push_to_remote.assert_not_called()
        mock_manager.create_gitlab_release.assert_not_called()
        mock_manager.create_github_release.assert_not_called()
        mock_manager.merge_to_main_and_bump.assert_not_called()

    @patch("devflow.cli.utils.check_outside_ai_session")
    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    @patch("devflow.cli.commands.release_command.click.confirm")
    @patch("devflow.release.permissions.get_git_remote_url")
    @patch("devflow.release.permissions.parse_git_remote")
    def test_approve_release_handles_patch_release(
        self, mock_parse_remote, mock_get_remote_url, mock_confirm, mock_console, mock_manager_class, mock_check_outside
    ):
        """Test approve_release handles patch releases (no main merge)."""
        from devflow.release.permissions import Platform
        from devflow.cli.commands.release_command import approve_release

        # Mock check_outside_ai_session to not exit
        mock_check_outside.return_value = None

        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock validation returning success with no release branch (patch)
        mock_manager.validate_release_prepared.return_value = (
            True,
            "Release preparation validated",
            None  # No release branch for patch
        )

        # Mock push operations
        mock_manager.push_to_remote.return_value = (True, "Pushed successfully")

        # Mock platform detection
        mock_get_remote_url.return_value = "git@github.com:owner/repo.git"
        mock_parse_remote.return_value = (Platform.GITHUB, "owner", "repo")

        # Mock GitHub release creation
        mock_manager.create_github_release.return_value = (
            True,
            "Created GitHub release",
            "https://github.com/owner/repo/releases/tag/v0.1.1"
        )

        # Mock confirmation
        mock_confirm.return_value = True

        # Execute
        approve_release(version="0.1.1", dry_run=False)

        # Verify validation called
        mock_manager.validate_release_prepared.assert_called_once()

        # Verify push called only for tag (not branch)
        assert mock_manager.push_to_remote.call_count == 1

        # Verify GitHub release created
        mock_manager.create_github_release.assert_called_once()

        # Verify main merge NOT called (patch release)
        mock_manager.merge_to_main_and_bump.assert_not_called()

    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    def test_approve_release_dry_run_does_not_execute(
        self, mock_console, mock_manager_class
    ):
        """Test approve_release with dry_run does not execute operations."""
        from devflow.cli.commands.release_command import approve_release

        # Setup
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock validation
        mock_manager.validate_release_prepared.return_value = (
            True,
            "Release preparation validated",
            "release/0.2"
        )

        # Mock operations returning dry-run messages
        mock_manager.push_to_remote.return_value = (True, "Would push")
        mock_manager.create_github_release.return_value = (True, "Would create release", None)
        mock_manager.merge_to_main_and_bump.return_value = (True, "Would merge to main")

        # Execute with dry_run=True
        approve_release(version="0.2.0", dry_run=True)

        # Verify validation called
        mock_manager.validate_release_prepared.assert_called_once()

        # Verify operations called with dry_run=True
        for call in mock_manager.push_to_remote.call_args_list:
            assert call[1]['dry_run'] is True

    @patch("devflow.cli.utils.check_outside_ai_session")
    @patch("devflow.cli.commands.release_command.ReleaseManager")
    @patch("devflow.cli.commands.release_command.console")
    def test_approve_release_handles_invalid_version(
        self, mock_console, mock_manager_class, mock_check_outside
    ):
        """Test approve_release handles invalid version format."""
        from devflow.cli.commands.release_command import approve_release

        # Mock check_outside_ai_session to not exit
        mock_check_outside.return_value = None

        # Execute with invalid version
        approve_release(version="invalid", dry_run=False)

        # Verify manager was not created (error handled early)
        # Manager is created before version parsing, so it will be created
        # But validation should not be called
        mock_manager_class.return_value.validate_release_prepared.assert_not_called()
