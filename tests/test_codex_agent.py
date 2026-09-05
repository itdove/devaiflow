"""Tests for the Codex agent adapter."""

import sqlite3
from unittest.mock import Mock, patch

from devflow.agent.codex_agent import CodexAgent
from devflow.agent.factory import PENDING_CAPTURE_PLACEHOLDER, launch_and_capture


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


@patch("devflow.agent.codex_agent.require_tool")
@patch("devflow.agent.codex_agent.subprocess.Popen")
def test_launch_with_prompt_resumes_fresh_investigation_clone(
    mock_popen, mock_require, tmp_path
):
    """Resume a UUID-backed session in the selected clone without a cwd prompt."""
    process = Mock()
    mock_popen.return_value = process
    project_path = str(tmp_path / "fresh-investigation-clone")
    session_id = "01a072a1-9c95-7ef0-b1e0-1690bb31122d"

    result = CodexAgent().launch_with_prompt(
        project_path=project_path,
        initial_prompt="Continue the investigation",
        session_id=session_id,
        model_provider_profile={"model_name": "test-model"},
    )

    assert result is process
    mock_require.assert_called_once_with("codex", "launch Codex AI assistant")
    args, kwargs = mock_popen.call_args
    assert args[0] == [
        "codex",
        "resume",
        "--cd",
        project_path,
        "-c",
        'tui.resume_cwd="current"',
        "--model",
        "test-model",
        session_id,
    ]
    assert kwargs["cwd"] == project_path


@patch("devflow.agent.codex_agent.require_tool")
@patch("devflow.agent.codex_agent.subprocess.Popen")
def test_launch_and_capture_persists_codex_session_id(
    mock_popen, mock_require, tmp_path
):
    """Capture the real Codex ID after launching from the pending placeholder."""
    process = Mock()
    mock_popen.return_value = process
    project_path = str(tmp_path / "fresh-investigation-clone")
    real_session_id = "01a072a1-9c95-7ef0-b1e0-1690bb31122d"
    active_conversation = Mock()
    active_conversation.ai_agent_session_id = PENDING_CAPTURE_PLACEHOLDER
    agent = CodexAgent(codex_dir=tmp_path / "codex")

    with patch.object(
        agent,
        "get_existing_sessions",
        side_effect=[set(), {real_session_id}],
    ):
        launch_and_capture(
            agent,
            "codex",
            project_path,
            active_conversation,
            initial_prompt="Start the investigation",
            session_id=PENDING_CAPTURE_PLACEHOLDER,
        )

    assert active_conversation.ai_agent_session_id == real_session_id


@patch("devflow.agent.codex_agent.require_tool")
@patch("devflow.agent.codex_agent.subprocess.Popen")
def test_launch_and_capture_ignores_sessions_from_other_projects(
    mock_popen, mock_require, tmp_path
):
    """Capture the session created for DAF's project, not a newer global session."""
    project_path = str(tmp_path / "project-a")
    other_project_path = str(tmp_path / "project-b")
    linked_session_id = "11111111-1111-1111-1111-111111111111"
    newer_unrelated_session_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    sessions_dir = tmp_path / "codex" / "sessions" / "2026" / "01" / "01"
    sessions_dir.mkdir(parents=True)

    unrelated_rollout = sessions_dir / (
        f"rollout-2026-01-01T00-00-00-{newer_unrelated_session_id}.jsonl"
    )
    unrelated_rollout.write_text(
        f'{{"type":"session_meta","payload":{{"cwd":"{other_project_path}"}}}}\n'
    )

    process = Mock()
    agent = CodexAgent(codex_dir=tmp_path / "codex")
    active_conversation = Mock()
    active_conversation.ai_agent_session_id = PENDING_CAPTURE_PLACEHOLDER

    def launch_and_create_rollout(*args, **kwargs):
        linked_rollout = sessions_dir / (
            f"rollout-2026-01-01T00-00-01-{linked_session_id}.jsonl"
        )
        linked_rollout.write_text(
            f'{{"type":"session_meta","payload":{{"cwd":"{project_path}"}}}}\n'
        )
        return process

    mock_popen.side_effect = launch_and_create_rollout
    with patch.object(agent, "wait_for_exit"):
        launch_and_capture(
            agent,
            "codex",
            project_path,
            active_conversation,
            initial_prompt="Start the investigation",
            session_id=PENDING_CAPTURE_PLACEHOLDER,
        )

    assert active_conversation.ai_agent_session_id == linked_session_id


def test_get_existing_sessions_uses_rollout_files_when_database_is_unavailable(tmp_path):
    thread_id = "12345678-1234-1234-1234-123456789abc"
    rollout = tmp_path / "sessions" / "2026" / "01" / "01" / f"rollout-2026-01-01T00-00-00-{thread_id}.jsonl"
    rollout.parent.mkdir(parents=True)
    rollout.write_text("{}\n")

    sessions = CodexAgent(codex_dir=tmp_path).get_existing_sessions("/tmp/project-a")

    assert sessions == {thread_id}


def test_get_existing_sessions_scopes_rollouts_to_project_path(tmp_path):
    project_a = "/tmp/project-a"
    project_b = "/tmp/project-b"
    session_a = "12345678-1234-1234-1234-123456789abc"
    session_b = "abcdefab-cdef-abcd-efab-cdefabcdefab"
    sessions_dir = tmp_path / "sessions" / "2026" / "01" / "01"
    sessions_dir.mkdir(parents=True)

    for session_id, project_path in ((session_a, project_a), (session_b, project_b)):
        rollout = sessions_dir / f"rollout-2026-01-01T00-00-00-{session_id}.jsonl"
        rollout.write_text(
            f'{{"type":"session_meta","payload":{{"session_id":"{session_id}",'
            f'"cwd":"{project_path}"}}}}\n'
        )

    agent = CodexAgent(codex_dir=tmp_path)

    assert agent.get_existing_sessions(project_a) == {session_a}
    assert agent.get_existing_sessions(project_b) == {session_b}


def test_get_existing_sessions_falls_back_to_database_without_rollouts(tmp_path):
    session_id = "12345678-1234-1234-1234-123456789abc"
    db_path = tmp_path / "thread_history_1.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE thread_turns (thread_id TEXT NOT NULL, turn_id TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO thread_turns(thread_id, turn_id) VALUES (?, ?)",
        (session_id, "turn-1"),
    )
    connection.commit()
    connection.close()

    assert CodexAgent(codex_dir=tmp_path).get_existing_sessions("/tmp/project-a") == {
        session_id
    }


def test_codex_home_overrides_other_home_resolution(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert CodexAgent().codex_dir == tmp_path / "codex-home"


@patch("devflow.agent.codex_agent.require_tool")
@patch("devflow.agent.codex_agent.subprocess.Popen")
def test_resume_session_uses_selected_project_directory_without_cwd_prompt(
    mock_popen, mock_require, tmp_path
):
    project_path = str(tmp_path / "fresh-investigation-clone")
    session_id = "01a072a1-9c95-7ef0-b1e0-1690bb31122d"
    mock_process = Mock()
    mock_popen.return_value = mock_process

    result = CodexAgent().resume_session(session_id, project_path)

    assert result is mock_process
    mock_require.assert_called_once_with("codex", "resume Codex AI assistant")
    args, kwargs = mock_popen.call_args
    assert args[0] == [
        "codex",
        "resume",
        "--cd",
        project_path,
        "-c",
        "tui.resume_cwd=\"current\"",
        session_id,
    ]
    assert kwargs["cwd"] == project_path


def test_manual_resume_command_uses_selected_project_directory():
    command = CodexAgent().get_manual_resume_command(
        "01a072a1-9c95-7ef0-b1e0-1690bb31122d",
        "/tmp/fresh investigation clone",
    )

    assert command == (
        "codex resume --cd '/tmp/fresh investigation clone' "
        "-c 'tui.resume_cwd=\"current\"' "
        "01a072a1-9c95-7ef0-b1e0-1690bb31122d"
    )
