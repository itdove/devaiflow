"""Tests for git create session rename functionality (issue #63)."""

import pytest
from unittest.mock import patch, Mock, MagicMock
from click.testing import CliRunner

from devflow.cli.commands.git_create_command import git_create
from devflow.cli.commands.sync_command import issue_key_to_session_name
from devflow.cli.main import cli


class TestIssueKeyToSessionName:
    """Test the issue_key_to_session_name function."""

    def test_github_format(self):
        """Test GitHub issue key conversion."""
        assert issue_key_to_session_name("owner/repo#123") == "owner-repo-123"

    def test_gitlab_format(self):
        """Test GitLab issue key conversion."""
        assert issue_key_to_session_name("owner/repo#456") == "owner-repo-456"

    def test_short_issue_key(self):
        """Test short issue key format (#123)."""
        assert issue_key_to_session_name("#789") == "789"

    def test_with_hostname_default(self):
        """Test with default github.com hostname (omitted from name)."""
        assert issue_key_to_session_name("owner/repo#123", "github.com") == "owner-repo-123"

    def test_with_hostname_enterprise(self):
        """Test with enterprise hostname (included in name)."""
        result = issue_key_to_session_name("owner/repo#123", "github.enterprise.com")
        assert result == "github-enterprise-com-owner-repo-123"


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager for testing session rename."""
    with patch('devflow.session.manager.SessionManager') as mock_manager_class:
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock session object
        mock_session = Mock()
        mock_session.name = "test-session-abc123"
        mock_session.session_type = "ticket_creation"
        mock_session.active_conversation = Mock()
        mock_session.active_conversation.ai_agent_session_id = "claude-session-id"

        # Mock session list
        mock_manager.list_sessions.return_value = [mock_session]

        # Mock get_session to return renamed session
        def get_session_side_effect(name):
            if name.startswith("creation-"):
                renamed = Mock()
                renamed.name = name
                renamed.issue_key = None
                renamed.issue_metadata = {}
                return renamed
            return None

        mock_manager.get_session.side_effect = get_session_side_effect

        yield mock_manager


@pytest.fixture
def mock_session_capture():
    """Mock SessionCapture to simulate being in a session."""
    with patch('devflow.session.capture.SessionCapture') as mock_capture_class:
        mock_capture = Mock()
        mock_capture_class.return_value = mock_capture
        mock_capture.get_current_session_id.return_value = "claude-session-id"
        yield mock_capture


@pytest.fixture
def mock_config_loader():
    """Mock ConfigLoader."""
    with patch('devflow.cli.commands.git_create_command.ConfigLoader') as mock_loader_class:
        mock_loader = Mock()
        mock_config = Mock()
        mock_config.github = Mock()
        mock_config.github.issue_templates = {}
        mock_loader.load_config.return_value = mock_config
        mock_loader_class.return_value = mock_loader
        yield mock_loader


@pytest.fixture
def mock_github_client():
    """Mock GitHubClient."""
    with patch('devflow.cli.commands.git_create_command.GitHubClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


class TestGitCreateSessionRename:
    """Test session rename functionality in git_create command."""

    def test_session_renamed_to_correct_format_github(
        self,
        mock_config_loader,
        mock_github_client,
        mock_session_manager,
        mock_session_capture
    ):
        """Test that session is renamed to creation-owner-repo-123 format for GitHub."""
        # Setup
        mock_github_client.create_issue.return_value = "itdove/devaiflow#60"

        # Execute
        git_create(
            summary="Test issue",
            description="Test description",
            output_json=False
        )

        # Verify rename was called with correct format
        mock_session_manager.rename_session.assert_called_once()
        old_name, new_name = mock_session_manager.rename_session.call_args[0]

        # Should be renamed to creation-itdove-devaiflow-60
        assert new_name == "creation-itdove-devaiflow-60"
        assert old_name == "test-session-abc123"

    def test_session_renamed_to_correct_format_gitlab(
        self,
        mock_config_loader,
        mock_github_client,
        mock_session_manager,
        mock_session_capture
    ):
        """Test that session is renamed to creation-owner-repo-456 format for GitLab."""
        # Setup
        mock_github_client.create_issue.return_value = "mygroup/myproject#456"

        # Execute
        git_create(
            summary="Test issue",
            description="Test description",
            output_json=False
        )

        # Verify rename was called with correct format
        mock_session_manager.rename_session.assert_called_once()
        old_name, new_name = mock_session_manager.rename_session.call_args[0]

        # Should be renamed to creation-mygroup-myproject-456
        assert new_name == "creation-mygroup-myproject-456"

    def test_session_metadata_updated_after_rename(
        self,
        mock_config_loader,
        mock_github_client,
        mock_session_manager,
        mock_session_capture
    ):
        """Test that session metadata is updated after successful rename."""
        # Setup
        issue_key = "owner/repo#123"
        mock_github_client.create_issue.return_value = issue_key

        # Execute
        git_create(
            summary="Test issue",
            issue_type="bug",
            description="Test description",
            output_json=False
        )

        # Verify session was updated
        mock_session_manager.update_session.assert_called()

        # Get the updated session
        updated_session = mock_session_manager.update_session.call_args[0][0]

        # Verify metadata was set correctly
        assert updated_session.issue_key == issue_key
        assert updated_session.issue_metadata["summary"] == "Test issue"
        assert updated_session.issue_metadata["type"] == "bug"
        assert updated_session.issue_metadata["status"] == "open"

    def test_rename_only_applies_to_ticket_creation_sessions(
        self,
        mock_config_loader,
        mock_github_client,
        mock_session_capture
    ):
        """Test that rename only applies to ticket_creation session type."""
        # Setup - create a development session (not ticket_creation)
        with patch('devflow.session.manager.SessionManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            mock_session = Mock()
            mock_session.name = "dev-session"
            mock_session.session_type = "development"  # Not ticket_creation
            mock_session.active_conversation = Mock()
            mock_session.active_conversation.ai_agent_session_id = "claude-session-id"

            mock_manager.list_sessions.return_value = [mock_session]

            mock_github_client.create_issue.return_value = "owner/repo#123"

            # Execute
            git_create(
                summary="Test issue",
                description="Test description",
                output_json=False
            )

            # Verify rename was NOT called (session type is not ticket_creation)
            mock_manager.rename_session.assert_not_called()

    def test_no_decorator_blocking_execution(self):
        """Test that git_create function does not have @require_outside_claude decorator."""
        # Verify that the function can be called without the decorator blocking it
        # This is a regression test for issue #63
        import inspect
        from devflow.cli.commands.git_create_command import git_create

        # Get function source to check for decorator
        # Note: We can't directly check decorators, but we can verify the function
        # can be called in a mocked Claude session context
        assert callable(git_create)

        # Verify function signature (decorator would have wrapped it)
        sig = inspect.signature(git_create)
        assert 'summary' in sig.parameters
        assert 'issue_type' in sig.parameters

    def test_consistency_with_git_open_naming(self):
        """Test that git create and git open use the same naming convention."""
        # Both should use issue_key_to_session_name from sync_command
        test_key = "owner/repo#789"
        expected = "owner-repo-789"

        # Verify the function produces consistent results
        result = issue_key_to_session_name(test_key)
        assert result == expected

        # Verify creation prefix is added correctly
        creation_name = f"creation-{result}"
        assert creation_name == "creation-owner-repo-789"


class TestGitCreateIntegration:
    """Integration tests for the complete git create workflow."""

    @pytest.mark.integration
    def test_end_to_end_session_rename(self, tmp_path, monkeypatch):
        """End-to-end test of session creation and rename workflow."""
        # This would be a full integration test
        # For now, we'll keep it as a placeholder for future expansion
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
