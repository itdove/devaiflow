"""Tests for the Pi agent adapter."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from devflow.agent import PiAgent, create_agent_client
from devflow.agent.factory import PENDING_CAPTURE_PLACEHOLDER, is_self_id_backend
from devflow.session.discovery import SessionDiscovery

PROJECT_PATH = "/tmp/project-a"
SESSION_ID = "01a0d843-d177-7547-8bd6-13c50ee236c8"


def _session_file(agent: PiAgent) -> Path:
    session_dir = agent.get_session_dir(PROJECT_PATH)
    session_dir.mkdir(parents=True)
    path = session_dir / f"2026-01-01T00-00-00-000Z_{SESSION_ID}.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"type": "session", "id": SESSION_ID, "cwd": PROJECT_PATH}),
                json.dumps(
                    {
                        "type": "message",
                        "id": "message-1",
                        "message": {"role": "user", "content": "Inspect the project"},
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "id": "message-2",
                        "message": {
                            "role": "assistant",
                            "provider": "test-provider",
                            "model": "test-model",
                            "usage": {
                                "input": 100,
                                "output": 25,
                                "cacheRead": 10,
                                "cacheWrite": 5,
                                "totalTokens": 140,
                            },
                        },
                    }
                ),
            ]
        )
        + "\n"
    )
    return path


class TestPiAgent:
    def test_init_and_storage_paths(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PI_CODING_AGENT_DIR", str(tmp_path / "pi-agent"))
        agent = PiAgent()

        assert agent.pi_dir == tmp_path / "pi-agent"
        assert agent.session_dir == tmp_path / "pi-agent" / "sessions"
        assert agent.encode_project_path(PROJECT_PATH) == "--tmp-project-a--"
        assert agent.get_agent_name() == "pi"
        assert agent.uses_file_based_sessions() is True

    @patch("devflow.agent.pi_agent.require_tool")
    @patch("devflow.agent.pi_agent.subprocess.Popen")
    def test_launch_with_prompt_builds_pi_command(
        self, mock_popen, mock_require, tmp_path
    ):
        process = Mock()
        mock_popen.return_value = process
        agent = PiAgent(tmp_path / "pi-agent")

        result = agent.launch_with_prompt(
            project_path=PROJECT_PATH,
            initial_prompt="Inspect the project",
            session_id=PENDING_CAPTURE_PLACEHOLDER,
            model_provider_profile={
                "provider": "test-provider",
                "model_name": "test-model",
                "reasoning_effort": "high",
            },
            skills_dirs=["/tmp/project-a/.pi/skills"],
            headless=True,
            auto_approve=True,
        )

        assert result is process
        mock_require.assert_called_once_with("pi", "launch Pi AI assistant")
        command = mock_popen.call_args.args[0]
        assert command == [
            "pi",
            "--print",
            "--provider",
            "test-provider",
            "--model",
            "test-model",
            "--thinking",
            "high",
            "--skill",
            "/tmp/project-a/.pi/skills",
            "--approve",
            "--",
            "Inspect the project",
        ]
        assert mock_popen.call_args.kwargs["cwd"] == PROJECT_PATH
        assert mock_popen.call_args.kwargs["env"]["PI_CODING_AGENT_DIR"] == str(
            tmp_path / "pi-agent"
        )

    @patch("devflow.agent.pi_agent.require_tool")
    @patch("devflow.agent.pi_agent.subprocess.Popen")
    def test_resume_session_uses_session_flag(self, mock_popen, mock_require, tmp_path):
        process = Mock()
        mock_popen.return_value = process
        agent = PiAgent(tmp_path / "pi-agent")

        assert agent.resume_session(SESSION_ID, PROJECT_PATH) is process
        mock_require.assert_called_once_with("pi", "resume Pi AI assistant")
        assert mock_popen.call_args.args[0] == ["pi", "--session", SESSION_ID]

    @patch("devflow.agent.pi_agent.require_tool")
    @patch("devflow.agent.pi_agent.subprocess.Popen")
    def test_launch_with_prompt_uses_exact_session_id_flag(
        self, mock_popen, mock_require, tmp_path
    ):
        mock_popen.return_value = Mock()
        agent = PiAgent(tmp_path / "pi-agent")

        agent.launch_with_prompt(
            project_path=PROJECT_PATH,
            initial_prompt="Inspect the project",
            session_id=SESSION_ID,
        )

        assert mock_popen.call_args.args[0] == [
            "pi",
            "--session-id",
            SESSION_ID,
            "--",
            "Inspect the project",
        ]

    def test_session_storage_and_usage(self, tmp_path):
        agent = PiAgent(tmp_path / "pi-agent")
        path = _session_file(agent)

        assert agent.get_existing_sessions(PROJECT_PATH) == {SESSION_ID}
        assert agent.session_exists(SESSION_ID, PROJECT_PATH) is True
        assert agent.get_session_file_path(SESSION_ID, PROJECT_PATH) == path
        assert agent.get_session_message_count(SESSION_ID, PROJECT_PATH) == 2
        assert (
            agent.get_session_model_id(SESSION_ID, PROJECT_PATH)
            == "test-provider/test-model"
        )
        assert agent.extract_token_usage(SESSION_ID, PROJECT_PATH) == {
            "input_tokens": 100,
            "output_tokens": 25,
            "cache_creation_input_tokens": 5,
            "cache_read_input_tokens": 10,
            "total_tokens": 140,
            "message_count": 1,
        }

    def test_session_discovery_reads_pi_files(self, tmp_path):
        agent = PiAgent(tmp_path / "pi-agent")
        _session_file(agent)

        discovered = SessionDiscovery(agent=agent).discover_sessions()

        assert len(discovered) == 1
        assert discovered[0].uuid == SESSION_ID
        assert discovered[0].project_path == PROJECT_PATH
        assert discovered[0].message_count == 2
        assert discovered[0].first_message == "Inspect the project"

    def test_capture_session_id_detects_new_file(self, tmp_path):
        agent = PiAgent(tmp_path / "pi-agent")
        session_dir = agent.get_session_dir(PROJECT_PATH)
        session_dir.mkdir(parents=True)
        new_file = session_dir / f"2026-01-01T00-00-00-000Z_{SESSION_ID}.jsonl"

        calls = 0

        def sessions(_project_path):
            nonlocal calls
            calls += 1
            if calls == 2:
                new_file.write_text("{}\n")
            return set() if calls == 1 else {SESSION_ID}

        with patch.object(agent, "get_existing_sessions", side_effect=sessions):
            captured = agent.capture_session_id(
                PROJECT_PATH, timeout=1, poll_interval=0
            )

        assert captured == SESSION_ID

    @patch("devflow.agent.pi_agent.subprocess.run")
    def test_generate_text_uses_print_mode(self, mock_run, tmp_path):
        mock_run.return_value = Mock(returncode=0, stdout="Generated result\n")
        agent = PiAgent(tmp_path / "pi-agent")

        result = agent.generate_text(
            "Write a short summary",
            model_provider_profile={
                "provider": "test-provider",
                "model_name": "test-model",
                "reasoning_effort": "minimal",
                "api_key": "test-key",
            },
        )

        assert result == "Generated result"
        command = mock_run.call_args.args[0]
        assert command == [
            "pi",
            "--print",
            "--provider",
            "test-provider",
            "--model",
            "test-model",
            "--thinking",
            "minimal",
            "--api-key",
            "test-key",
            "--",
            "Write a short summary",
        ]

    def test_factory_and_self_id_registry(self, tmp_path):
        agent = create_agent_client("pi", agent_home=tmp_path / "pi-agent")

        assert isinstance(agent, PiAgent)
        assert is_self_id_backend("pi") is True
        assert PENDING_CAPTURE_PLACEHOLDER == "pending-capture"
        assert agent.get_manual_resume_command(SESSION_ID, PROJECT_PATH) == (
            f"pi --session {SESSION_ID}"
        )
