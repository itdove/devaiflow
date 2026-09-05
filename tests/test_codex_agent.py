"""Tests for the Codex agent adapter."""

from unittest.mock import Mock, patch

from devflow.agent.codex_agent import CodexAgent


def test_launch_env_drops_parent_codex_session_markers():
    env = {
        "PATH": "/bin",
        "CODEX_CI": "1",
        "CODEX_PERMISSION_PROFILE": ":workspace",
        "CODEX_THREAD_ID": "parent-thread",
        "CODEX_SESSION_ID": "parent-session",
        "CODEX_SANDBOX_NETWORK_DISABLED": "1",
    }

    launch_env = CodexAgent._build_launch_env(env)

    assert launch_env == {"PATH": "/bin"}
    assert env["CODEX_THREAD_ID"] == "parent-thread"


@patch("devflow.agent.codex_agent.require_tool")
@patch("devflow.agent.codex_agent.subprocess.Popen")
def test_launch_with_prompt_starts_independent_interactive_session(mock_popen, mock_require):
    process = Mock()
    mock_popen.return_value = process
    env = {
        "PATH": "/bin",
        "CODEX_CI": "1",
        "CODEX_PERMISSION_PROFILE": ":workspace",
        "CODEX_THREAD_ID": "parent-thread",
        "CODEX_SESSION_ID": "parent-session",
    }

    result = CodexAgent().launch_with_prompt(
        project_path="/tmp/project-a",
        initial_prompt="Read the project instructions",
        session_id="pending-capture",
        model_provider_profile={"model_name": "test-model"},
        env=env,
    )

    assert result is process
    mock_require.assert_called_once_with("codex", "launch Codex AI assistant")
    args, kwargs = mock_popen.call_args
    assert args[0] == [
        "codex",
        "Read the project instructions",
        "--model",
        "test-model",
    ]
    assert kwargs["env"] == {"PATH": "/bin"}


def test_get_existing_sessions_uses_rollout_files_when_database_is_unavailable(tmp_path):
    thread_id = "12345678-1234-1234-1234-123456789abc"
    rollout = tmp_path / "sessions" / "2026" / "01" / "01" / f"rollout-2026-01-01T00-00-00-{thread_id}.jsonl"
    rollout.parent.mkdir(parents=True)
    rollout.write_text("{}\n")

    sessions = CodexAgent(codex_dir=tmp_path).get_existing_sessions("/tmp/project-a")

    assert sessions == {thread_id}


def test_codex_home_overrides_other_home_resolution(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert CodexAgent().codex_dir == tmp_path / "codex-home"
