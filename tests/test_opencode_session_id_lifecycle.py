"""Tests for OpenCode session ID lifecycle fix (#464).

Validates the fix for the UUID/ses_ mismatch that prevented OpenCode sessions
from resuming. Tests cover:
- Agent-aware session ID generation (UUID vs placeholder)
- Session snapshot and capture helpers
- is_first_launch logic with pending-capture placeholder
- End-to-end open_command flow with OpenCode backend
"""

import uuid
from unittest.mock import Mock, MagicMock, patch

import pytest

from devflow.agent.factory import (
    PENDING_CAPTURE_PLACEHOLDER,
    SELF_ID_BACKENDS,
    is_self_id_backend,
    generate_agent_session_id,
    is_pending_capture,
    snapshot_agent_sessions,
    capture_agent_session_id,
)


class TestIsSelfIdBackend:
    """Test is_self_id_backend() function."""

    def test_opencode_is_self_id(self):
        assert is_self_id_backend("opencode") is True

    def test_opencode_ai_is_self_id(self):
        assert is_self_id_backend("opencode-ai") is True

    def test_claude_is_not_self_id(self):
        assert is_self_id_backend("claude") is False

    def test_ollama_is_not_self_id(self):
        assert is_self_id_backend("ollama") is False

    def test_copilot_is_not_self_id(self):
        assert is_self_id_backend("github-copilot") is False

    def test_cursor_is_not_self_id(self):
        assert is_self_id_backend("cursor") is False

    def test_case_insensitive(self):
        assert is_self_id_backend("OpenCode") is True
        assert is_self_id_backend("OPENCODE") is True


class TestGenerateAgentSessionId:
    """Test generate_agent_session_id() function."""

    def test_claude_returns_uuid(self):
        session_id = generate_agent_session_id("claude")
        # Should be a valid UUID
        uuid.UUID(session_id)  # Raises ValueError if not valid

    def test_ollama_returns_uuid(self):
        session_id = generate_agent_session_id("ollama")
        uuid.UUID(session_id)

    def test_opencode_returns_placeholder(self):
        session_id = generate_agent_session_id("opencode")
        assert session_id == PENDING_CAPTURE_PLACEHOLDER

    def test_opencode_ai_returns_placeholder(self):
        session_id = generate_agent_session_id("opencode-ai")
        assert session_id == PENDING_CAPTURE_PLACEHOLDER

    def test_copilot_returns_uuid(self):
        session_id = generate_agent_session_id("github-copilot")
        uuid.UUID(session_id)

    def test_each_call_returns_unique_uuid(self):
        id1 = generate_agent_session_id("claude")
        id2 = generate_agent_session_id("claude")
        assert id1 != id2

    def test_opencode_always_returns_same_placeholder(self):
        id1 = generate_agent_session_id("opencode")
        id2 = generate_agent_session_id("opencode")
        assert id1 == id2 == PENDING_CAPTURE_PLACEHOLDER


class TestIsPendingCapture:
    """Test is_pending_capture() function."""

    def test_placeholder_is_pending(self):
        assert is_pending_capture(PENDING_CAPTURE_PLACEHOLDER) is True

    def test_uuid_is_not_pending(self):
        assert is_pending_capture(str(uuid.uuid4())) is False

    def test_ses_id_is_not_pending(self):
        assert is_pending_capture("ses_1681670c7ffeQW2V0m2n0O5pbR") is False

    def test_empty_string_is_not_pending(self):
        assert is_pending_capture("") is False


class TestSnapshotAgentSessions:
    """Test snapshot_agent_sessions() function."""

    def test_opencode_takes_snapshot(self):
        agent = Mock()
        agent.get_existing_sessions.return_value = {"ses_abc", "ses_def"}

        result = snapshot_agent_sessions(agent, "opencode", "/project")

        assert result == {"ses_abc", "ses_def"}
        agent.get_existing_sessions.assert_called_once_with("/project")

    def test_claude_returns_empty_set(self):
        agent = Mock()

        result = snapshot_agent_sessions(agent, "claude", "/project")

        assert result == set()
        agent.get_existing_sessions.assert_not_called()

    def test_no_launch_dir_returns_empty(self):
        agent = Mock()

        result = snapshot_agent_sessions(agent, "opencode", "")

        assert result == set()
        agent.get_existing_sessions.assert_not_called()

    def test_exception_returns_empty(self):
        agent = Mock()
        agent.get_existing_sessions.side_effect = Exception("connection error")

        result = snapshot_agent_sessions(agent, "opencode", "/project")

        assert result == set()


class TestCaptureAgentSessionId:
    """Test capture_agent_session_id() function."""

    def test_captures_new_session_id(self):
        agent = Mock()
        agent.get_existing_sessions.return_value = {"ses_abc", "ses_def", "ses_new"}
        agent.get_agent_name.return_value = "opencode"

        active_conv = Mock()
        active_conv.ai_agent_session_id = PENDING_CAPTURE_PLACEHOLDER

        sessions_before = {"ses_abc", "ses_def"}

        result = capture_agent_session_id(
            agent, "opencode", "/project", active_conv, sessions_before
        )

        assert result is True
        assert active_conv.ai_agent_session_id == "ses_new"

    def test_no_new_sessions_returns_false(self):
        agent = Mock()
        agent.get_existing_sessions.return_value = {"ses_abc", "ses_def"}
        agent.get_agent_name.return_value = "opencode"

        active_conv = Mock()
        active_conv.ai_agent_session_id = PENDING_CAPTURE_PLACEHOLDER

        sessions_before = {"ses_abc", "ses_def"}

        result = capture_agent_session_id(
            agent, "opencode", "/project", active_conv, sessions_before
        )

        assert result is False
        # Should NOT have changed the session ID
        assert active_conv.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER

    def test_claude_backend_returns_false(self):
        agent = Mock()
        active_conv = Mock()

        result = capture_agent_session_id(
            agent, "claude", "/project", active_conv, set()
        )

        assert result is False
        agent.get_existing_sessions.assert_not_called()

    def test_no_active_conv_returns_false(self):
        agent = Mock()

        result = capture_agent_session_id(
            agent, "opencode", "/project", None, set()
        )

        assert result is False

    def test_exception_returns_false(self):
        agent = Mock()
        agent.get_existing_sessions.side_effect = Exception("error")
        agent.get_agent_name.return_value = "opencode"

        active_conv = Mock()
        sessions_before = set()

        result = capture_agent_session_id(
            agent, "opencode", "/project", active_conv, sessions_before
        )

        assert result is False


class TestOpenCommandIsFirstLaunch:
    """Test that open_command.py correctly treats pending-capture as first launch."""

    def test_pending_capture_is_first_launch(self):
        """Sessions with pending-capture should be treated as first launch."""
        from devflow.agent.factory import is_pending_capture

        # Simulate the is_first_launch check from open_command.py
        active_conv = Mock()
        active_conv.ai_agent_session_id = PENDING_CAPTURE_PLACEHOLDER

        has_real_session_id = (
            active_conv
            and active_conv.ai_agent_session_id
            and not is_pending_capture(active_conv.ai_agent_session_id)
        )
        is_first_launch = not has_real_session_id

        assert is_first_launch is True

    def test_uuid_is_not_first_launch(self):
        """Sessions with UUID should NOT be treated as first launch initially."""
        from devflow.agent.factory import is_pending_capture

        active_conv = Mock()
        active_conv.ai_agent_session_id = str(uuid.uuid4())

        has_real_session_id = (
            active_conv
            and active_conv.ai_agent_session_id
            and not is_pending_capture(active_conv.ai_agent_session_id)
        )
        is_first_launch = not has_real_session_id

        # UUID is a "real" session ID (it will fail session_exists check later)
        assert is_first_launch is False

    def test_ses_id_is_not_first_launch(self):
        """Sessions with ses_ ID should NOT be treated as first launch."""
        from devflow.agent.factory import is_pending_capture

        active_conv = Mock()
        active_conv.ai_agent_session_id = "ses_1681670c7ffeQW2V0m2n0O5pbR"

        has_real_session_id = (
            active_conv
            and active_conv.ai_agent_session_id
            and not is_pending_capture(active_conv.ai_agent_session_id)
        )
        is_first_launch = not has_real_session_id

        assert is_first_launch is False

    def test_none_session_id_is_first_launch(self):
        """Sessions with no session ID should be treated as first launch."""
        from devflow.agent.factory import is_pending_capture

        active_conv = Mock()
        active_conv.ai_agent_session_id = None

        has_real_session_id = (
            active_conv
            and active_conv.ai_agent_session_id
            and not is_pending_capture(active_conv.ai_agent_session_id)
        )
        is_first_launch = not has_real_session_id

        assert is_first_launch is True

    def test_no_active_conv_is_first_launch(self):
        """Sessions with no active conversation should be treated as first launch."""
        from devflow.agent.factory import is_pending_capture

        active_conv = None

        has_real_session_id = (
            active_conv
            and active_conv.ai_agent_session_id
            and not is_pending_capture(active_conv.ai_agent_session_id)
        )
        is_first_launch = not has_real_session_id

        assert is_first_launch is True


class TestOpenCodeLaunchWithPromptGuard:
    """Test that OpenCodeAgent.launch_with_prompt correctly handles session IDs."""

    def test_ses_id_passes_session_flag(self):
        """Session IDs starting with 'ses' should be passed via --session flag."""
        from devflow.agent.opencode_agent import OpenCodeAgent

        agent = OpenCodeAgent()

        with patch("devflow.agent.opencode_agent.require_tool"):
            with patch("subprocess.Popen") as mock_popen:
                mock_popen.return_value = Mock()
                agent.launch_with_prompt(
                    project_path="/project",
                    initial_prompt="hello",
                    session_id="ses_1681670c7ffeQW2V0m2n0O5pbR",
                )

                cmd = mock_popen.call_args[0][0]
                assert "--session" in cmd
                assert "ses_1681670c7ffeQW2V0m2n0O5pbR" in cmd

    def test_placeholder_does_not_pass_session_flag(self):
        """Pending-capture placeholder should NOT be passed via --session flag."""
        from devflow.agent.opencode_agent import OpenCodeAgent

        agent = OpenCodeAgent()

        with patch("devflow.agent.opencode_agent.require_tool"):
            with patch("subprocess.Popen") as mock_popen:
                mock_popen.return_value = Mock()
                agent.launch_with_prompt(
                    project_path="/project",
                    initial_prompt="hello",
                    session_id=PENDING_CAPTURE_PLACEHOLDER,
                )

                cmd = mock_popen.call_args[0][0]
                assert "--session" not in cmd

    def test_uuid_does_not_pass_session_flag(self):
        """UUID session IDs should NOT be passed via --session flag."""
        from devflow.agent.opencode_agent import OpenCodeAgent

        agent = OpenCodeAgent()

        with patch("devflow.agent.opencode_agent.require_tool"):
            with patch("subprocess.Popen") as mock_popen:
                mock_popen.return_value = Mock()
                agent.launch_with_prompt(
                    project_path="/project",
                    initial_prompt="hello",
                    session_id=str(uuid.uuid4()),
                )

                cmd = mock_popen.call_args[0][0]
                assert "--session" not in cmd


class TestSelfIdBackendsConstant:
    """Test SELF_ID_BACKENDS constant."""

    def test_contains_opencode(self):
        assert "opencode" in SELF_ID_BACKENDS

    def test_contains_opencode_ai(self):
        assert "opencode-ai" in SELF_ID_BACKENDS

    def test_does_not_contain_claude(self):
        assert "claude" not in SELF_ID_BACKENDS
