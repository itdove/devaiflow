"""Tests for daf list --json token usage data (itdove/devaiflow#400)."""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.cli.commands.list_command import (
    _compute_session_token_usage,
    _serialize_sessions_with_tokens,
)
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def _parse_json_output(output):
    """Parse JSON from CLI output, filtering out warning lines."""
    output_lines = output.strip().split('\n')
    json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
    return json.loads(json_part)


# --- Unit tests for _compute_session_token_usage ---


def test_compute_token_usage_no_conversations():
    """Token usage returns None when session has no conversations."""
    session = MagicMock()
    session.conversations = {}
    agent = MagicMock()

    result = _compute_session_token_usage(session, agent)
    assert result is None


def test_compute_token_usage_single_conversation():
    """Token usage aggregates data from a single conversation."""
    session = MagicMock()
    conv = MagicMock()
    conv.project_path = "/path/to/project"
    conv.ai_agent_session_id = "uuid-123"
    # Simulate new format (Conversation with active_session)
    conv_wrapper = MagicMock()
    conv_wrapper.active_session = conv
    session.conversations = {"repo1": conv_wrapper}

    agent = MagicMock()
    agent.extract_token_usage.return_value = {
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 200,
        "total_tokens": 1500,
        "message_count": 5,
    }

    result = _compute_session_token_usage(session, agent)

    assert result is not None
    assert result["total_tokens"] == 1500
    assert result["input_tokens"] == 1000
    assert result["output_tokens"] == 500
    assert result["cache_creation_input_tokens"] == 100
    assert result["cache_read_input_tokens"] == 200


def test_compute_token_usage_multiple_conversations():
    """Token usage aggregates data across multiple conversations."""
    session = MagicMock()

    # First conversation
    conv1 = MagicMock()
    conv1.project_path = "/path/to/repo1"
    conv1.ai_agent_session_id = "uuid-1"
    conv1_wrapper = MagicMock()
    conv1_wrapper.active_session = conv1

    # Second conversation
    conv2 = MagicMock()
    conv2.project_path = "/path/to/repo2"
    conv2.ai_agent_session_id = "uuid-2"
    conv2_wrapper = MagicMock()
    conv2_wrapper.active_session = conv2

    session.conversations = {"repo1": conv1_wrapper, "repo2": conv2_wrapper}

    agent = MagicMock()
    agent.extract_token_usage.side_effect = [
        {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_creation_input_tokens": 50,
            "cache_read_input_tokens": 100,
            "total_tokens": 1500,
        },
        {
            "input_tokens": 2000,
            "output_tokens": 800,
            "cache_creation_input_tokens": 75,
            "cache_read_input_tokens": 150,
            "total_tokens": 2800,
        },
    ]

    result = _compute_session_token_usage(session, agent)

    assert result is not None
    assert result["total_tokens"] == 4300  # (1000+2000) + (500+800)
    assert result["input_tokens"] == 3000
    assert result["output_tokens"] == 1300
    assert result["cache_creation_input_tokens"] == 125
    assert result["cache_read_input_tokens"] == 250


def test_compute_token_usage_no_data_returns_none():
    """Token usage returns None when agent returns None for all conversations."""
    session = MagicMock()
    conv = MagicMock()
    conv.project_path = "/path/to/project"
    conv.ai_agent_session_id = "uuid-123"
    conv_wrapper = MagicMock()
    conv_wrapper.active_session = conv
    session.conversations = {"repo1": conv_wrapper}

    agent = MagicMock()
    agent.extract_token_usage.return_value = None

    result = _compute_session_token_usage(session, agent)
    assert result is None


def test_compute_token_usage_missing_project_path():
    """Token usage skips conversations without project_path."""
    session = MagicMock()
    conv = MagicMock()
    conv.project_path = None
    conv.ai_agent_session_id = "uuid-123"
    conv_wrapper = MagicMock()
    conv_wrapper.active_session = conv
    session.conversations = {"repo1": conv_wrapper}

    agent = MagicMock()

    result = _compute_session_token_usage(session, agent)
    assert result is None
    agent.extract_token_usage.assert_not_called()


def test_compute_token_usage_missing_session_id():
    """Token usage skips conversations without ai_agent_session_id."""
    session = MagicMock()
    conv = MagicMock()
    conv.project_path = "/path/to/project"
    conv.ai_agent_session_id = None
    conv_wrapper = MagicMock()
    conv_wrapper.active_session = conv
    session.conversations = {"repo1": conv_wrapper}

    agent = MagicMock()

    result = _compute_session_token_usage(session, agent)
    assert result is None
    agent.extract_token_usage.assert_not_called()


def test_compute_token_usage_exception_silenced():
    """Token usage silently ignores exceptions from extract_token_usage."""
    session = MagicMock()
    conv = MagicMock()
    conv.project_path = "/path/to/project"
    conv.ai_agent_session_id = "uuid-123"
    conv_wrapper = MagicMock()
    conv_wrapper.active_session = conv
    session.conversations = {"repo1": conv_wrapper}

    agent = MagicMock()
    agent.extract_token_usage.side_effect = IOError("File not found")

    result = _compute_session_token_usage(session, agent)
    assert result is None


def test_compute_token_usage_partial_failure():
    """Token usage aggregates data even when some conversations fail."""
    session = MagicMock()

    conv1 = MagicMock()
    conv1.project_path = "/path/to/repo1"
    conv1.ai_agent_session_id = "uuid-1"
    conv1_wrapper = MagicMock()
    conv1_wrapper.active_session = conv1

    conv2 = MagicMock()
    conv2.project_path = "/path/to/repo2"
    conv2.ai_agent_session_id = "uuid-2"
    conv2_wrapper = MagicMock()
    conv2_wrapper.active_session = conv2

    session.conversations = {"repo1": conv1_wrapper, "repo2": conv2_wrapper}

    agent = MagicMock()
    agent.extract_token_usage.side_effect = [
        {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_creation_input_tokens": 50,
            "cache_read_input_tokens": 100,
            "total_tokens": 1500,
        },
        IOError("File not found"),
    ]

    result = _compute_session_token_usage(session, agent)

    assert result is not None
    assert result["total_tokens"] == 1500
    assert result["input_tokens"] == 1000
    assert result["output_tokens"] == 500


def test_compute_token_usage_old_format_conversation():
    """Token usage works with old ConversationContext format (no active_session)."""
    session = MagicMock()
    # Old format: conversation IS the context directly (no active_session attribute)
    conv = MagicMock(spec=["project_path", "ai_agent_session_id", "last_active"])
    conv.project_path = "/path/to/project"
    conv.ai_agent_session_id = "uuid-123"
    session.conversations = {"repo1": conv}

    agent = MagicMock()
    agent.extract_token_usage.return_value = {
        "input_tokens": 500,
        "output_tokens": 200,
        "cache_creation_input_tokens": 10,
        "cache_read_input_tokens": 20,
        "total_tokens": 700,
    }

    result = _compute_session_token_usage(session, agent)

    assert result is not None
    assert result["total_tokens"] == 700


def test_compute_token_usage_missing_cache_fields():
    """Token usage handles missing cache fields gracefully (defaults to 0)."""
    session = MagicMock()
    conv = MagicMock()
    conv.project_path = "/path/to/project"
    conv.ai_agent_session_id = "uuid-123"
    conv_wrapper = MagicMock()
    conv_wrapper.active_session = conv
    session.conversations = {"repo1": conv_wrapper}

    agent = MagicMock()
    # Some agents (e.g., OpenCode) may not return cache fields
    agent.extract_token_usage.return_value = {
        "input_tokens": 1000,
        "output_tokens": 500,
        "total_tokens": 1500,
    }

    result = _compute_session_token_usage(session, agent)

    assert result is not None
    assert result["total_tokens"] == 1500
    assert result["cache_creation_input_tokens"] == 0
    assert result["cache_read_input_tokens"] == 0


# --- Unit tests for _serialize_sessions_with_tokens ---


@patch("devflow.cli.commands.list_command.create_agent_client")
@patch("devflow.cli.commands.list_command._compute_session_token_usage")
@patch("devflow.cli.commands.list_command.serialize_session")
def test_serialize_sessions_with_tokens(mock_serialize, mock_compute, mock_create_agent):
    """Serialize sessions includes token_usage field for each session."""
    mock_agent = MagicMock()
    mock_create_agent.return_value = mock_agent

    session1 = MagicMock()
    session2 = MagicMock()

    mock_serialize.side_effect = [
        {"name": "session1", "status": "in_progress"},
        {"name": "session2", "status": "complete"},
    ]

    mock_compute.side_effect = [
        {"total_tokens": 1500, "input_tokens": 1000, "output_tokens": 500,
         "cache_creation_input_tokens": 50, "cache_read_input_tokens": 100},
        None,  # session2 has no token data
    ]

    result = _serialize_sessions_with_tokens([session1, session2], "claude")

    assert len(result) == 2
    assert result[0]["name"] == "session1"
    assert result[0]["token_usage"] is not None
    assert result[0]["token_usage"]["total_tokens"] == 1500
    assert result[1]["name"] == "session2"
    assert result[1]["token_usage"] is None


@patch("devflow.cli.commands.list_command.create_agent_client")
@patch("devflow.cli.commands.list_command._compute_session_token_usage")
@patch("devflow.cli.commands.list_command.serialize_session")
def test_serialize_sessions_with_tokens_empty_list(mock_serialize, mock_compute, mock_create_agent):
    """Serialize empty list of sessions returns empty list."""
    mock_create_agent.return_value = MagicMock()

    result = _serialize_sessions_with_tokens([], "claude")
    assert result == []


# --- Integration tests with CLI ---


@patch("devflow.cli.commands.list_command.create_agent_client")
def test_list_json_includes_token_usage_field(mock_create_agent, temp_daf_home):
    """Test that daf list --json includes token_usage field (itdove/devaiflow#400)."""
    # Mock agent to return token data
    mock_agent = MagicMock()
    mock_agent.extract_token_usage.return_value = {
        "input_tokens": 100000,
        "output_tokens": 25000,
        "cache_creation_input_tokens": 5000,
        "cache_read_input_tokens": 10000,
        "total_tokens": 125000,
        "message_count": 42,
    }
    mock_create_agent.return_value = mock_agent

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="token-test-session",
        goal="Test token usage in JSON",
        working_directory="test-repo",
        project_path="/path/to/repo",
        ai_agent_session_id="uuid-token-test",
        issue_key="PROJ-400",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

    assert result.exit_code == 0
    output = _parse_json_output(result.output)

    assert output["success"] is True
    assert len(output["data"]["sessions"]) == 1

    session_data = output["data"]["sessions"][0]
    assert "token_usage" in session_data, "token_usage field must be present in JSON output"

    token_usage = session_data["token_usage"]
    assert token_usage is not None
    assert token_usage["total_tokens"] == 125000
    assert token_usage["input_tokens"] == 100000
    assert token_usage["output_tokens"] == 25000
    assert token_usage["cache_creation_input_tokens"] == 5000
    assert token_usage["cache_read_input_tokens"] == 10000


@patch("devflow.cli.commands.list_command.create_agent_client")
def test_list_json_token_usage_null_when_no_data(mock_create_agent, temp_daf_home):
    """Test that token_usage is null when no token data available (itdove/devaiflow#400)."""
    mock_agent = MagicMock()
    mock_agent.extract_token_usage.return_value = None
    mock_create_agent.return_value = mock_agent

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="no-token-session",
        goal="Test no token data",
        working_directory="test-repo",
        project_path="/path/to/repo",
        ai_agent_session_id="uuid-no-tokens",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

    assert result.exit_code == 0
    output = _parse_json_output(result.output)

    session_data = output["data"]["sessions"][0]
    assert "token_usage" in session_data
    assert session_data["token_usage"] is None


@patch("devflow.cli.commands.list_command.create_agent_client")
def test_list_json_token_usage_multiple_sessions(mock_create_agent, temp_daf_home):
    """Test token_usage with multiple sessions, some with data, some without (itdove/devaiflow#400)."""
    token_data = {
        "input_tokens": 50000,
        "output_tokens": 10000,
        "cache_creation_input_tokens": 1000,
        "cache_read_input_tokens": 2000,
        "total_tokens": 60000,
    }

    def extract_side_effect(session_id, project_path):
        """Return token data only for the session with tokens."""
        if session_id == "uuid-with-tokens":
            return token_data
        return None

    mock_agent = MagicMock()
    mock_agent.extract_token_usage.side_effect = extract_side_effect
    mock_create_agent.return_value = mock_agent

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="session-with-tokens",
        goal="Has tokens",
        working_directory="repo1",
        project_path="/path/to/repo1",
        ai_agent_session_id="uuid-with-tokens",
    )
    session_manager.create_session(
        name="session-no-tokens",
        goal="No tokens",
        working_directory="repo2",
        project_path="/path/to/repo2",
        ai_agent_session_id="uuid-no-tokens",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

    assert result.exit_code == 0
    output = _parse_json_output(result.output)

    sessions = output["data"]["sessions"]
    assert len(sessions) == 2

    sessions_by_name = {s["name"]: s for s in sessions}

    # Session with tokens has token data
    assert sessions_by_name["session-with-tokens"]["token_usage"] is not None
    assert sessions_by_name["session-with-tokens"]["token_usage"]["total_tokens"] == 60000

    # Session without tokens has null token data
    assert sessions_by_name["session-no-tokens"]["token_usage"] is None


@patch("devflow.cli.commands.list_command.create_agent_client")
def test_list_json_token_usage_with_pagination(mock_create_agent, temp_daf_home):
    """Test token_usage works correctly with pagination (itdove/devaiflow#400)."""
    mock_agent = MagicMock()
    mock_agent.extract_token_usage.return_value = {
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "total_tokens": 1500,
    }
    mock_create_agent.return_value = mock_agent

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 5 sessions
    for i in range(5):
        session_manager.create_session(
            name=f"paginated-session-{i}",
            goal=f"Goal {i}",
            working_directory=f"repo{i}",
            project_path=f"/path/to/repo{i}",
            ai_agent_session_id=f"uuid-page-{i}",
        )

    runner = CliRunner()
    # Request page 1 with limit 2
    result = runner.invoke(cli, ["list", "--json", "--limit", "2", "--page", "1"], catch_exceptions=False)

    assert result.exit_code == 0
    output = _parse_json_output(result.output)

    # Should only have 2 sessions on page 1
    assert len(output["data"]["sessions"]) == 2
    assert output["data"]["total_count"] == 5

    # Both sessions should have token_usage
    for session_data in output["data"]["sessions"]:
        assert "token_usage" in session_data
        assert session_data["token_usage"] is not None
        assert session_data["token_usage"]["total_tokens"] == 1500


@patch("devflow.cli.commands.list_command.create_agent_client")
def test_list_json_no_sessions_no_token_usage(mock_create_agent, temp_daf_home):
    """Test that empty session list in JSON output works correctly (itdove/devaiflow#400)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

    assert result.exit_code == 0
    output = _parse_json_output(result.output)

    assert output["success"] is True
    assert output["data"]["sessions"] == []
    assert output["data"]["total_count"] == 0
    # create_agent_client should not be called when there are no sessions
    mock_create_agent.assert_not_called()


@patch("devflow.cli.commands.list_command.create_agent_client")
def test_list_json_token_usage_session_without_conversations(mock_create_agent, temp_daf_home):
    """Test token_usage for sessions without conversations (e.g., ticket_creation) (itdove/devaiflow#400)."""
    mock_agent = MagicMock()
    mock_create_agent.return_value = mock_agent

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session and manually clear conversations to simulate edge case
    session = session_manager.create_session(
        name="empty-conv-session",
        goal="No conversations",
        working_directory="test-repo",
        project_path="/path/to/repo",
        ai_agent_session_id="uuid-empty",
    )
    session.conversations = {}
    session_manager.update_session(session)

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

    assert result.exit_code == 0
    output = _parse_json_output(result.output)

    session_data = output["data"]["sessions"][0]
    assert "token_usage" in session_data
    assert session_data["token_usage"] is None
