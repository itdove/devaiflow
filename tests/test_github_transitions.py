"""Tests for GitHub transitions module."""

from unittest.mock import Mock, patch, MagicMock

import pytest

from devflow.config.models import Config, GitHubConfig, Session
from devflow.github.transitions import transition_on_complete, transition_on_start


@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client."""
    client = Mock()
    client.get_ticket.return_value = {
        'status': 'open',
        'labels': ['status: in-progress']
    }
    client.transition_ticket = Mock()
    client.update_issue = Mock()
    return client


@pytest.fixture
def session():
    """Create a test session."""
    return Session(
        name="test-session",
        goal="Test goal",
        working_directory="/test/dir",
        issue_key="owner/repo#123"
    )


@pytest.fixture
def config_no_auto_close():
    """Config with auto_close_on_complete = False (default)."""
    config = Mock(spec=Config)
    config.github = Mock(spec=GitHubConfig)
    config.github.auto_close_on_complete = False
    config.github.add_status_labels = False
    return config


@pytest.fixture
def config_auto_close_true():
    """Config with auto_close_on_complete = True."""
    config = Mock(spec=Config)
    config.github = Mock(spec=GitHubConfig)
    config.github.auto_close_on_complete = True
    config.github.add_status_labels = False
    return config


@pytest.fixture
def config_no_github():
    """Config without GitHub configuration."""
    config = Mock(spec=Config)
    config.github = None
    return config


class TestTransitionOnCompleteAutoClose:
    """Tests for transition_on_complete auto-close behavior."""

    def test_auto_close_true_closes_without_prompt(self, session, config_auto_close_true, mock_github_client):
        """Test that auto_close_on_complete=True closes issue without prompting."""
        # Act
        result = transition_on_complete(session, config_auto_close_true, client=mock_github_client)

        # Assert
        assert result is True
        # Should close the issue
        mock_github_client.transition_ticket.assert_called_once_with('owner/repo#123', 'closed')
        # Should update labels (remove status labels)
        mock_github_client.update_issue.assert_called_once()

    def test_auto_close_false_prompts_user_yes(self, session, config_no_auto_close, mock_github_client):
        """Test that auto_close_on_complete=False prompts user (user says yes)."""
        with patch('rich.prompt.Confirm') as mock_confirm:
            mock_confirm.ask.return_value = True

            # Act
            result = transition_on_complete(session, config_no_auto_close, client=mock_github_client)

            # Assert
            assert result is True
            # Should prompt user
            mock_confirm.ask.assert_called_once()
            assert "Close GitHub issue owner/repo#123?" in str(mock_confirm.ask.call_args)
            # Should close the issue since user said yes
            mock_github_client.transition_ticket.assert_called_once_with('owner/repo#123', 'closed')

    def test_auto_close_false_prompts_user_no(self, session, config_no_auto_close, mock_github_client):
        """Test that auto_close_on_complete=False prompts user (user says no)."""
        with patch('rich.prompt.Confirm') as mock_confirm:
            mock_confirm.ask.return_value = False

            # Act
            result = transition_on_complete(session, config_no_auto_close, client=mock_github_client)

            # Assert
            assert result is True
            # Should prompt user
            mock_confirm.ask.assert_called_once()
            # Should NOT close the issue since user said no
            mock_github_client.transition_ticket.assert_not_called()

    def test_no_github_config_prompts_user(self, session, config_no_github, mock_github_client):
        """Test that missing GitHub config prompts user."""
        with patch('rich.prompt.Confirm') as mock_confirm:
            mock_confirm.ask.return_value = True

            # Act
            result = transition_on_complete(session, config_no_github, client=mock_github_client)

            # Assert
            assert result is True
            # Should prompt user when config.github is None
            mock_confirm.ask.assert_called_once()
            # Should close since user said yes
            mock_github_client.transition_ticket.assert_called_once_with('owner/repo#123', 'closed')

    def test_no_auto_close_attribute_prompts_user(self, session, mock_github_client):
        """Test that missing auto_close_on_complete attribute prompts user."""
        # Config with github but no auto_close_on_complete attribute
        config = Mock(spec=Config)
        config.github = Mock(spec=GitHubConfig)
        # Don't set auto_close_on_complete attribute at all
        delattr(config.github, 'auto_close_on_complete')

        with patch('rich.prompt.Confirm') as mock_confirm:
            mock_confirm.ask.return_value = False

            # Act
            result = transition_on_complete(session, config, client=mock_github_client)

            # Assert
            assert result is True
            # Should prompt user when attribute doesn't exist
            mock_confirm.ask.assert_called_once()
            # Should NOT close since user said no
            mock_github_client.transition_ticket.assert_not_called()


class TestTransitionOnCompleteEdgeCases:
    """Tests for edge cases in transition_on_complete."""

    def test_no_issue_key_returns_early(self, config_no_auto_close, mock_github_client):
        """Test that missing issue_key returns early."""
        session = Session(
            name="test-session",
            goal="Test goal",
            working_directory="/test/dir",
            issue_key=None
        )

        result = transition_on_complete(session, config_no_auto_close, client=mock_github_client)

        assert result is True
        mock_github_client.get_ticket.assert_not_called()

    def test_no_issue_update_flag_skips_updates(self, session, config_no_auto_close, mock_github_client):
        """Test that no_issue_update flag skips all updates."""
        result = transition_on_complete(session, config_no_auto_close, client=mock_github_client, no_issue_update=True)

        assert result is True
        mock_github_client.get_ticket.assert_not_called()

    def test_already_closed_issue_no_prompt(self, session, config_no_auto_close, mock_github_client):
        """Test that already closed issue doesn't prompt."""
        mock_github_client.get_ticket.return_value = {
            'status': 'closed',
            'labels': []
        }

        with patch('rich.prompt.Confirm') as mock_confirm:
            result = transition_on_complete(session, config_no_auto_close, client=mock_github_client)

            assert result is True
            # Should NOT prompt for already closed issue
            mock_confirm.ask.assert_not_called()
            # Should NOT try to close again
            mock_github_client.transition_ticket.assert_not_called()

    def test_client_initialization_failure(self, session, config_no_auto_close):
        """Test graceful handling of client initialization failure."""
        with patch('devflow.github.transitions.GitHubClient', side_effect=Exception("Auth failed")):
            result = transition_on_complete(session, config_no_auto_close)

            # Should return True even if client init fails (don't block completion)
            assert result is True

    def test_api_error_during_transition(self, session, config_auto_close_true, mock_github_client):
        """Test graceful handling of API errors during transition."""
        from devflow.issue_tracker.exceptions import IssueTrackerApiError

        mock_github_client.transition_ticket.side_effect = IssueTrackerApiError("API error")

        result = transition_on_complete(session, config_auto_close_true, client=mock_github_client)

        # Should return True even if transition fails (don't block completion)
        assert result is True


class TestTransitionOnStart:
    """Tests for transition_on_start."""

    def test_no_issue_key_returns_early(self, config_no_auto_close, mock_github_client):
        """Test that missing issue_key returns early."""
        session = Session(
            name="test-session",
            goal="Test goal",
            working_directory="/test/dir",
            issue_key=None
        )

        result = transition_on_start(session, config_no_auto_close, client=mock_github_client)

        assert result is True
        mock_github_client.get_ticket.assert_not_called()

    def test_reopens_closed_issue(self, session, config_no_auto_close, mock_github_client):
        """Test that closed issue is reopened on start."""
        mock_github_client.get_ticket.return_value = {
            'status': 'closed',
            'labels': []
        }

        result = transition_on_start(session, config_no_auto_close, client=mock_github_client)

        assert result is True
        # Should reopen the issue
        mock_github_client.transition_ticket.assert_called_once_with('owner/repo#123', 'open')

    def test_open_issue_no_status_labels(self, session, config_no_auto_close, mock_github_client):
        """Test that open issue without status labels doesn't update when labels disabled."""
        mock_github_client.get_ticket.return_value = {
            'status': 'open',
            'labels': []
        }

        result = transition_on_start(session, config_no_auto_close, client=mock_github_client)

        assert result is True
        # Should NOT update labels when add_status_labels is False
        mock_github_client.update_issue.assert_not_called()

    def test_adds_status_labels_when_enabled(self, session, mock_github_client):
        """Test that status labels are added when enabled."""
        config = Mock(spec=Config)
        config.github = Mock(spec=GitHubConfig)
        config.github.add_status_labels = True

        mock_github_client.get_ticket.return_value = {
            'status': 'open',
            'labels': []
        }

        result = transition_on_start(session, config, client=mock_github_client)

        assert result is True
        # Should add status: in-progress label
        mock_github_client.update_issue.assert_called_once()
        call_args = mock_github_client.update_issue.call_args
        assert 'status: in-progress' in call_args[0][1]['labels']

    def test_client_initialization_failure_on_start(self, session, config_no_auto_close):
        """Test graceful handling of client initialization failure on start."""
        with patch('devflow.github.transitions.GitHubClient', side_effect=Exception("Auth failed")):
            result = transition_on_start(session, config_no_auto_close)

            # Should return True even if client init fails (don't block session start)
            assert result is True


class TestLabelManagement:
    """Tests for label management in transitions."""

    def test_removes_status_labels_on_close(self, session, config_auto_close_true, mock_github_client):
        """Test that status labels are removed when closing issue."""
        mock_github_client.get_ticket.return_value = {
            'status': 'open',
            'labels': ['status: in-progress', 'bug', 'priority: high']
        }

        result = transition_on_complete(session, config_auto_close_true, client=mock_github_client)

        assert result is True
        # Should remove status labels but keep other labels
        call_args = mock_github_client.update_issue.call_args
        updated_labels = call_args[0][1]['labels']
        assert 'status: in-progress' not in updated_labels
        assert 'bug' in updated_labels
        assert 'priority: high' in updated_labels

    def test_adds_completion_label_when_not_closing(self, session, mock_github_client):
        """Test that completion label is added when not closing issue."""
        config = Mock(spec=Config)
        config.github = Mock(spec=GitHubConfig)
        config.github.auto_close_on_complete = False
        config.github.add_status_labels = True
        config.github.completion_label = 'status: in-review'

        mock_github_client.get_ticket.return_value = {
            'status': 'open',
            'labels': ['status: in-progress', 'bug']
        }

        with patch('rich.prompt.Confirm') as mock_confirm:
            mock_confirm.ask.return_value = False  # User says no to closing

            result = transition_on_complete(session, config, client=mock_github_client)

            assert result is True
            # Should replace status: in-progress with status: in-review
            call_args = mock_github_client.update_issue.call_args
            updated_labels = call_args[0][1]['labels']
            assert 'status: in-progress' not in updated_labels
            assert 'status: in-review' in updated_labels
            assert 'bug' in updated_labels
