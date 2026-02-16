"""Tests for JIRA transitions module."""

from unittest.mock import Mock, patch, MagicMock

from devflow.config.models import Config, JiraConfig, JiraTransitionConfig, Session
from devflow.jira.exceptions import (
    JiraAuthError,
    JiraApiError,
    JiraConnectionError,
    JiraNotFoundError,
    JiraValidationError,
)
from devflow.jira.transitions import (
    should_transition_on_start,
    transition_on_start,
    transition_on_complete,
)


def test_should_transition_on_start_no_issue_key():
    """Test should_transition returns False when no issue key."""
    session = Session(name="test", goal="test", working_directory="dir")
    config = Mock(spec=Config)

    result = should_transition_on_start(session, config)
    assert result is False


def test_should_transition_on_start_no_on_start_config():
    """Test should_transition returns False when no on_start config."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {}

    result = should_transition_on_start(session, config)
    assert result is False


def test_should_transition_on_start_wrong_current_status():
    """Test should_transition returns False when current status not in from_status."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"
    session.issue_metadata = {"status": "In Progress"}

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.from_status = ["New", "To Do"]

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_start": transition_config}

    result = should_transition_on_start(session, config)
    assert result is False


def test_should_transition_on_start_valid():
    """Test should_transition returns True when all conditions met."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"
    session.issue_metadata = {"status": "New"}

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.from_status = ["New", "To Do"]

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_start": transition_config}

    result = should_transition_on_start(session, config)
    assert result is True


def test_transition_on_start_should_not_transition():
    """Test transition_on_start returns True when should_transition is False."""
    session = Session(name="test", goal="test", working_directory="dir")
    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {}

    result = transition_on_start(session, config)
    assert result is True


@patch('devflow.utils.is_mock_mode')
@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_start_with_prompt_user_confirms(mock_jira_client, mock_is_mock):
    """Test transition_on_start with prompt and user confirms."""
    mock_is_mock.return_value = False

    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"
    session.issue_metadata = {"status": "New"}

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.from_status = ["New", "To Do"]
    transition_config.to = "In Progress"
    transition_config.prompt = True

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_start": transition_config}

    # Mock JIRA client
    jira_instance = Mock()
    mock_jira_client.return_value = jira_instance

    with patch('devflow.jira.transitions.Confirm.ask', return_value=True):
        result = transition_on_start(session, config)

    assert result is True
    jira_instance.transition_ticket.assert_called_once_with("PROJ-123", "In Progress")


@patch('devflow.utils.is_mock_mode')
def test_transition_on_start_with_prompt_user_declines(mock_is_mock):
    """Test transition_on_start with prompt and user declines."""
    mock_is_mock.return_value = False

    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"
    session.issue_metadata = {"status": "New"}

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.from_status = ["New", "To Do"]
    transition_config.to = "In Progress"
    transition_config.prompt = True

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_start": transition_config}

    with patch('devflow.jira.transitions.Confirm.ask', return_value=False):
        result = transition_on_start(session, config)

    assert result is True


@patch('devflow.utils.is_mock_mode')
@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_start_mock_mode(mock_jira_client, mock_is_mock):
    """Test transition_on_start in mock mode."""
    mock_is_mock.return_value = True

    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"
    session.issue_metadata = {"status": "New"}

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.from_status = ["New", "To Do"]
    transition_config.to = "In Progress"
    transition_config.prompt = True

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_start": transition_config}

    jira_instance = Mock()
    mock_jira_client.return_value = jira_instance

    result = transition_on_start(session, config)

    assert result is True
    jira_instance.transition_ticket.assert_called_once()


@patch('devflow.utils.is_mock_mode')
@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_start_validation_error(mock_jira_client, mock_is_mock):
    """Test transition_on_start handles validation error."""
    mock_is_mock.return_value = False

    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"
    session.issue_metadata = {"status": "New"}

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.from_status = ["New", "To Do"]
    transition_config.to = "In Progress"
    transition_config.prompt = False

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_start": transition_config}

    jira_instance = Mock()
    error = JiraValidationError("Validation failed")
    error.field_errors = {"field1": "error message"}
    error.error_messages = ["general error"]
    jira_instance.transition_ticket.side_effect = error
    mock_jira_client.return_value = jira_instance

    result = transition_on_start(session, config)

    assert result is False


@patch('devflow.utils.is_mock_mode')
@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_start_auth_error(mock_jira_client, mock_is_mock):
    """Test transition_on_start handles auth error."""
    mock_is_mock.return_value = False

    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"
    session.issue_metadata = {"status": "New"}

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.from_status = ["New", "To Do"]
    transition_config.to = "In Progress"
    transition_config.prompt = False

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_start": transition_config}

    jira_instance = Mock()
    jira_instance.transition_ticket.side_effect = JiraAuthError("Auth failed")
    mock_jira_client.return_value = jira_instance

    result = transition_on_start(session, config)

    assert result is False


def test_transition_on_complete_no_issue_key():
    """Test transition_on_complete returns True when no issue key."""
    session = Session(name="test", goal="test", working_directory="dir")
    config = Mock(spec=Config)

    result = transition_on_complete(session, config)
    assert result is True


def test_transition_on_complete_no_config():
    """Test transition_on_complete returns True when no on_complete config."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {}

    result = transition_on_complete(session, config)
    assert result is True


@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_complete_no_prompt_no_target(mock_jira_client):
    """Test transition_on_complete with no prompt and no target status."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.prompt = False
    transition_config.to = None

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_complete": transition_config}

    result = transition_on_complete(session, config)

    assert result is True


@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_complete_no_prompt_with_target(mock_jira_client):
    """Test transition_on_complete with no prompt and target status."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.prompt = False
    transition_config.to = "Done"

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_complete": transition_config}

    jira_instance = Mock()
    mock_jira_client.return_value = jira_instance

    result = transition_on_complete(session, config)

    assert result is True
    jira_instance.transition_ticket.assert_called_once_with("PROJ-123", "Done")


@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_complete_no_prompt_error(mock_jira_client):
    """Test transition_on_complete handles error when no prompt."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.prompt = False
    transition_config.to = "Done"

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_complete": transition_config}

    jira_instance = Mock()
    jira_instance.transition_ticket.side_effect = JiraApiError("API error")
    mock_jira_client.return_value = jira_instance

    result = transition_on_complete(session, config)

    # Should still return True (don't block completion)
    assert result is True


@patch('devflow.jira.transitions.Prompt.ask')
@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_complete_with_prompt_user_skips(mock_jira_client, mock_prompt):
    """Test transition_on_complete with prompt and user skips."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.prompt = True

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_complete": transition_config}

    jira_instance = Mock()
    # Mock API response
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "transitions": [
            {"to": {"name": "Done"}},
            {"to": {"name": "Closed"}},
        ]
    }
    jira_instance._api_request.return_value = response
    mock_jira_client.return_value = jira_instance

    # User chooses option 1 (Skip)
    mock_prompt.return_value = "1"

    result = transition_on_complete(session, config)

    assert result is True
    jira_instance.transition_ticket.assert_not_called()


@patch('devflow.jira.transitions.Prompt.ask')
@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_complete_with_prompt_user_selects(mock_jira_client, mock_prompt):
    """Test transition_on_complete with prompt and user selects status."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.prompt = True

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_complete": transition_config}

    jira_instance = Mock()
    # Mock API response
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "transitions": [
            {"to": {"name": "Done"}},
            {"to": {"name": "Closed"}},
        ]
    }
    jira_instance._api_request.return_value = response
    mock_jira_client.return_value = jira_instance

    # User chooses option 2 (Done)
    mock_prompt.return_value = "2"

    result = transition_on_complete(session, config)

    assert result is True
    jira_instance.transition_ticket.assert_called_once_with("PROJ-123", "Done")


@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_complete_api_error_fetching_transitions(mock_jira_client):
    """Test transition_on_complete handles API error when fetching transitions."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.prompt = True

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_complete": transition_config}

    jira_instance = Mock()
    # Mock API error
    response = Mock()
    response.status_code = 500
    jira_instance._api_request.return_value = response
    mock_jira_client.return_value = jira_instance

    result = transition_on_complete(session, config)

    # Should still return True (don't block completion)
    assert result is True


@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_complete_no_transitions_available(mock_jira_client):
    """Test transition_on_complete when no transitions available."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.prompt = True

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_complete": transition_config}

    jira_instance = Mock()
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"transitions": []}
    jira_instance._api_request.return_value = response
    mock_jira_client.return_value = jira_instance

    result = transition_on_complete(session, config)

    # Should still return True
    assert result is True


@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_complete_exception_fetching_transitions(mock_jira_client):
    """Test transition_on_complete handles exception when fetching transitions."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.prompt = True

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_complete": transition_config}

    jira_instance = Mock()
    jira_instance._api_request.side_effect = Exception("Network error")
    mock_jira_client.return_value = jira_instance

    result = transition_on_complete(session, config)

    # Should still return True (don't block completion)
    assert result is True


@patch('devflow.jira.transitions.Prompt.ask')
@patch('devflow.jira.transitions.JiraClient')
def test_transition_on_complete_transition_fails(mock_jira_client, mock_prompt):
    """Test transition_on_complete when transition fails."""
    session = Session(name="test", goal="test", working_directory="dir")
    session.issue_key = "PROJ-123"

    transition_config = Mock(spec=JiraTransitionConfig)
    transition_config.prompt = True

    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.transitions = {"on_complete": transition_config}

    jira_instance = Mock()
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "transitions": [{"to": {"name": "Done"}}]
    }
    jira_instance._api_request.return_value = response
    jira_instance.transition_ticket.side_effect = JiraConnectionError("Connection failed")
    mock_jira_client.return_value = jira_instance

    # User chooses option 2
    mock_prompt.return_value = "2"

    result = transition_on_complete(session, config)

    # Should still return True (don't block completion)
    assert result is True
