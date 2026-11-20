"""Focused tests for the Kilo CLI adapter."""

import json
import subprocess
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.exceptions import Exit

from devflow.agent.factory import (
    create_agent_client,
    generate_agent_session_id,
    get_agent_metadata,
    is_self_id_backend,
    launch_and_capture,
)
from devflow.agent.kilo_agent import (
    KiloAgent,
    KiloCompatibilityError,
    KiloSessionQueryError,
)
from devflow.cli.commands.info_command import _get_conversation_file_path
from devflow.cli.commands.open_command import _refuse_unverified_opencode_session


@pytest.fixture
def agent() -> KiloAgent:
    client = KiloAgent()
    client._kilo_version = (7, 8, 27)
    return client


def test_kilo_is_registered_as_a_distinct_native_id_backend():
    client = create_agent_client("kilo")

    assert isinstance(client, KiloAgent)
    assert client.get_agent_name() == "kilo"
    assert is_self_id_backend("kilo")
    assert generate_agent_session_id("kilo") == "pending-capture"
    metadata = get_agent_metadata("kilo")
    assert metadata["cli_binary"] == "kilo"
    assert metadata["features"]["session_title"] is True
    assert metadata["features"]["conversation_export"] is False


def test_kilo_version_is_parsed_and_rejects_unknown_versions(monkeypatch):
    agent = KiloAgent()
    monkeypatch.setattr(
        "devflow.agent.kilo_agent.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "7.8.27\n", ""),
    )

    assert agent.get_kilo_version() == (7, 8, 27)
    assert agent.get_kilo_version() == (7, 8, 27)

    agent = KiloAgent()
    monkeypatch.setattr(
        "devflow.agent.kilo_agent.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "Kilo nightly", ""
        ),
    )
    with pytest.raises(KiloCompatibilityError, match="unrecognized version"):
        agent.get_kilo_version()


def test_kilo_version_rejects_nonzero_cli(monkeypatch):
    monkeypatch.setattr(
        "devflow.agent.kilo_agent.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "failure"),
    )

    with pytest.raises(KiloCompatibilityError, match="version detection failed"):
        KiloAgent().get_kilo_version()


def test_launch_session_uses_full_tui_and_persists_precreated_id(
    agent, monkeypatch, tmp_path
):
    process = Mock()
    popen = Mock(return_value=process)
    monkeypatch.setattr("devflow.agent.kilo_agent.require_tool", lambda *args: None)
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.Popen", popen)
    monkeypatch.setattr(
        agent,
        "_create_session_with_title",
        lambda title, path, env, callback: callback("ses_created") or "ses_created",
    )
    captured = []

    assert (
        agent.launch_session(
            str(tmp_path),
            env={"KILO_TEST": "present"},
            display_name="daf-session",
            on_session_id=captured.append,
        )
        is process
    )

    args, kwargs = popen.call_args
    assert args[0] == ["kilo", "--session", "ses_created"]
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["env"] == {"KILO_TEST": "present"}
    assert captured == ["ses_created"]


def test_launch_session_uses_full_tui_when_title_precreation_fails(
    agent, monkeypatch, tmp_path
):
    popen = Mock(return_value=Mock())
    monkeypatch.setattr("devflow.agent.kilo_agent.require_tool", lambda *args: None)
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.Popen", popen)
    monkeypatch.setattr(agent, "_create_session_with_title", lambda *args: None)

    agent.launch_session(str(tmp_path), env={}, display_name="daf-session")

    assert popen.call_args.args[0] == ["kilo"]


def test_launch_session_uses_provider_model_with_full_tui(agent, monkeypatch, tmp_path):
    popen = Mock(return_value=Mock())
    monkeypatch.setattr("devflow.agent.kilo_agent.require_tool", lambda *args: None)
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.Popen", popen)

    agent.launch_session(
        str(tmp_path),
        model_provider_profile={
            "name": "provider-profile",
            "provider": "openai",
            "agent_backend": "kilo",
            "model_name": "model-a",
        },
    )

    assert popen.call_args.args[0] == ["kilo", "--model", "openai/model-a"]


def test_interactive_launch_uses_full_tui_with_prompt_and_profile(
    agent, monkeypatch, tmp_path, caplog
):
    popen = Mock(return_value=Mock())
    monkeypatch.setattr("devflow.agent.kilo_agent.require_tool", lambda *args: None)
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.Popen", popen)
    monkeypatch.setattr(
        "devflow.agent.model_config.get_agent_model_config",
        lambda *args, **kwargs: {"model": None, "reasoning_effort": "high"},
    )
    monkeypatch.setattr(
        agent,
        "_create_session_with_title",
        lambda title, path, env, callback: callback("ses_created") or "ses_created",
    )
    captured = []

    agent.launch_with_prompt(
        str(tmp_path),
        "initial prompt",
        "pending-capture",
        model_provider_profile={
            "name": "provider-profile",
            "provider": "openai",
            "agent_backend": "kilo",
            "model_name": "model-a",
        },
        env={"EXISTING": "yes"},
        auto_approve=True,
        display_name="daf-session",
        isolated_workspace=True,
        on_session_id=captured.append,
    )

    command = popen.call_args.args[0]
    assert command == [
        "kilo",
        "--session",
        "ses_created",
        "--model",
        "openai/model-a",
        "--auto",
        "--prompt",
        "initial prompt",
    ]
    assert "run" not in command
    assert "--interactive" not in command
    assert popen.call_args.kwargs["env"] == {
        "EXISTING": "yes",
        "KILO_NO_DAEMON": "1",
    }
    assert captured == ["ses_created"]
    assert "does not support a launch-time reasoning variant" in caplog.text


def test_headless_launch_uses_json_events_and_qualified_model(
    agent, monkeypatch, tmp_path
):
    popen = Mock(return_value=Mock())
    launched = Mock()
    monkeypatch.setattr("devflow.agent.kilo_agent.require_tool", lambda *args: None)
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.Popen", popen)
    monkeypatch.setattr(agent, "_create_session_with_title", lambda *args: None)

    agent.launch_with_prompt(
        str(tmp_path),
        "initial prompt",
        "pending-capture",
        model_provider_profile={
            "name": "provider-profile",
            "provider": "openai",
            "agent_backend": "kilo",
            "model_name": "model-a",
            "reasoning_effort": "high",
        },
        env={"EXISTING": "yes"},
        headless=True,
        auto_approve=True,
        display_name="daf-session",
        isolated_workspace=True,
        on_launch=launched,
    )

    args, kwargs = popen.call_args
    command = args[0]
    assert command == [
        "kilo",
        "run",
        "--format",
        "json",
        "--title",
        "daf-session",
        "--model",
        "openai/model-a",
        "--variant",
        "high",
        "--auto",
        "initial prompt",
    ]
    assert kwargs["env"] == {"EXISTING": "yes", "KILO_NO_DAEMON": "1"}
    launched.assert_called_once_with()


def test_managed_clone_environment_disables_daemon_attachment(agent):
    assert agent._environment({"PATH": "/bin"}, isolated_workspace=True) == {
        "PATH": "/bin",
        "KILO_NO_DAEMON": "1",
    }


def test_managed_clone_launch_isolated_and_persists_launch_proven_kilo_id(
    agent, monkeypatch, tmp_path
):
    calls = []
    process = Mock(returncode=0)
    launch_kwargs = {}
    agent.get_existing_sessions = Mock(return_value=set())
    agent.wait_for_exit = Mock()
    agent.cleanup_after_exit = Mock()

    def fake_launch(project_path, **kwargs):
        launch_kwargs.update(kwargs)
        kwargs["on_launch"]()
        calls.append("launch")
        kwargs["on_session_id"]("ses_launch")
        calls.append("id")
        return process

    agent.launch_with_prompt = fake_launch
    monkeypatch.setattr(
        "devflow.agent.factory.temporary_directory_lock",
        lambda path: nullcontext(),
    )
    monkeypatch.setattr(
        "devflow.utils.clone_cache.CloneCache",
        lambda config: SimpleNamespace(use=Mock()),
    )
    conversation = SimpleNamespace(
        ai_agent_session_id="pending-capture",
        temp_directory=str(tmp_path),
        worktree_path=None,
    )

    launch_and_capture(
        agent,
        "kilo",
        str(tmp_path),
        conversation,
        initial_prompt="prompt",
        session_id="pending-capture",
        env={"EXISTING": "yes"},
    )

    assert launch_kwargs["isolated_workspace"] is True
    assert conversation.ai_agent_session_id == "ses_launch"
    assert calls == ["launch", "id"]
    agent.wait_for_exit.assert_called_once_with(process, False)


def test_resume_session_uses_kilo_session_flag_and_updates_title(
    agent, monkeypatch, tmp_path
):
    popen = Mock(return_value=Mock())
    update_title = Mock(return_value=True)
    monkeypatch.setattr("devflow.agent.kilo_agent.require_tool", lambda *args: None)
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.Popen", popen)
    monkeypatch.setattr(agent, "update_session_title", update_title)

    agent.resume_session(
        "ses_existing",
        str(tmp_path),
        env={},
        model_provider_profile={
            "provider": "openai",
            "agent_backend": "kilo",
            "model_name": "model-a",
        },
        display_name="daf-session",
        isolated_workspace=True,
    )

    assert popen.call_args.args[0] == [
        "kilo",
        "--model",
        "openai/model-a",
        "--session",
        "ses_existing",
    ]
    assert popen.call_args.kwargs["env"] == {"KILO_NO_DAEMON": "1"}
    update_title.assert_called_once_with(
        "ses_existing", "daf-session", str(tmp_path), {"KILO_NO_DAEMON": "1"}
    )


def test_resume_session_rejects_invalid_native_id(agent, monkeypatch, tmp_path):
    popen = Mock()
    monkeypatch.setattr("devflow.agent.kilo_agent.require_tool", lambda *args: None)
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.Popen", popen)

    with pytest.raises(ValueError, match="invalid Kilo session ID"):
        agent.resume_session("ses/other", str(tmp_path))
    popen.assert_not_called()


def test_native_session_creation_requires_matching_project_directory(
    agent, monkeypatch, tmp_path
):
    monkeypatch.setattr(
        agent,
        "_session_api_request",
        lambda *args: {"id": "ses_new", "directory": str(tmp_path)},
    )
    captured = []

    assert (
        agent._create_session_with_title(
            "daf-session", str(tmp_path), {}, captured.append
        )
        == "ses_new"
    )
    assert captured == ["ses_new"]

    monkeypatch.setattr(
        agent,
        "_session_api_request",
        lambda *args: {"id": "ses_wrong", "directory": str(tmp_path / "other")},
    )
    assert agent._create_session_with_title("daf-session", str(tmp_path), {}) is None


def test_kilo_session_list_accepts_empty_stdout_and_scopes_directory(
    agent, monkeypatch, tmp_path
):
    project = tmp_path / "project"
    project.mkdir()
    alias = tmp_path / "project-alias"
    alias.symlink_to(project, target_is_directory=True)
    rows = [
        {"id": "ses_here", "directory": str(project)},
        {"id": "ses_alias", "directory": str(alias)},
        {"id": "ses_elsewhere", "directory": str(tmp_path / "other")},
        {"id": "ses_missing_directory"},
        {"id": "bad-id", "directory": str(project)},
        "not-a-session",
    ]
    run = Mock(
        return_value=subprocess.CompletedProcess(["kilo"], 0, json.dumps(rows), "")
    )
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.run", run)

    assert agent.get_existing_sessions(str(project), strict=True) == {
        "ses_here",
        "ses_alias",
    }
    assert run.call_args.args[0] == [
        "kilo",
        "session",
        "list",
        "--format",
        "json",
        "--all",
    ]

    run.return_value = subprocess.CompletedProcess(["kilo"], 0, "", "")
    assert agent.get_existing_sessions(str(project), strict=True) == set()


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (subprocess.CompletedProcess(["kilo"], 1, "", "failed"), "exit code 1"),
        (subprocess.CompletedProcess(["kilo"], 0, "not json", ""), "invalid JSON"),
    ],
)
def test_kilo_session_list_fails_closed_for_command_or_json_errors(
    agent, monkeypatch, tmp_path, result, message
):
    monkeypatch.setattr(
        "devflow.agent.kilo_agent.subprocess.run",
        lambda *args, **kwargs: result,
    )

    with pytest.raises(KiloSessionQueryError, match=message):
        agent.get_existing_sessions(str(tmp_path), strict=True)
    assert agent.get_existing_sessions(str(tmp_path), strict=False) == set()


def test_session_exists_propagates_query_failures(agent, monkeypatch, tmp_path):
    monkeypatch.setattr(
        agent,
        "get_existing_sessions",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            KiloSessionQueryError("query failed")
        ),
    )

    with pytest.raises(KiloSessionQueryError, match="query failed"):
        agent.session_exists("ses_existing", str(tmp_path))


def test_kilo_message_count_uses_native_export_json(agent, monkeypatch, tmp_path):
    listing = json.dumps([{"id": "ses_existing", "directory": str(tmp_path)}])
    run = Mock(
        side_effect=[
            subprocess.CompletedProcess(["kilo"], 0, listing, ""),
            subprocess.CompletedProcess(
                ["kilo"], 0, json.dumps({"messages": [{}, {}, {}]}), ""
            ),
        ]
    )
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.run", run)

    assert agent.get_session_message_count("ses_existing", str(tmp_path)) == 3
    assert run.call_args_list[1].args[0] == ["kilo", "export", "ses_existing"]


def test_generate_text_parses_kilo_json_events_and_provider_model(agent, monkeypatch):
    result = subprocess.CompletedProcess(
        ["kilo"],
        0,
        "\n".join(
            [
                json.dumps({"type": "text", "part": {"text": "Use"}}),
                json.dumps({"type": "text", "part": {"text": " a clear title"}}),
                json.dumps({"type": "step-finish", "part": {"text": "ignored"}}),
            ]
        ),
        "",
    )
    run = Mock(return_value=result)
    monkeypatch.setattr("devflow.agent.kilo_agent.require_tool", lambda *args: None)
    monkeypatch.setattr(agent, "get_kilo_version", lambda **kwargs: (7, 8, 27))
    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.run", run)
    monkeypatch.setattr(
        "devflow.agent.model_config.get_agent_model_config",
        lambda *args, **kwargs: {"model": None, "reasoning_effort": "high"},
    )

    text = agent.generate_text(
        "write a commit title",
        model_provider_profile={
            "provider": "openai",
            "agent_backend": "kilo",
            "command_models": {"commit_message": "model-a"},
            "api_key": "example-token",
        },
    )

    assert text == "Use a clear title"
    command = run.call_args.args[0]
    assert command == [
        "kilo",
        "run",
        "--format",
        "json",
        "--model",
        "openai/model-a",
        "--variant",
        "high",
        "write a commit title",
    ]
    assert run.call_args.kwargs["env"]["OPENAI_API_KEY"] == "example-token"
    assert run.call_args.kwargs["env"]["KILO_NO_DAEMON"] == "1"


def test_kilo_storage_paths_and_unsupported_statistics(agent, monkeypatch, tmp_path):
    database = tmp_path / "kilo.db"
    monkeypatch.setattr(
        "devflow.agent.kilo_agent.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, f"{database}\n", ""
        ),
    )
    assert agent.get_session_file_path("ses_id", str(tmp_path)) == database
    assert agent.get_agent_name() == "kilo"
    assert agent.extract_token_usage("ses_id", str(tmp_path)) is None
    assert agent.uses_file_based_sessions() is False
    assert agent.uses_tui() is True
    assert agent.supports_permission_prompts() is True
    assert agent.get_manual_resume_command("ses_id", str(tmp_path)) == (
        "kilo --session ses_id"
    )


def test_unverified_kilo_identity_refusal_is_backend_specific(capsys):
    with pytest.raises(Exit):
        _refuse_unverified_opencode_session(
            "daf-session",
            "the saved native ID was not found in this project",
            False,
            backend="kilo",
        )

    output = " ".join(capsys.readouterr().out.split())
    assert "Cannot safely resume Kilo" in output
    assert "Kilo's" in output and "session list" in output
    assert "No replacement conversation was launched" in output


def test_info_reports_database_storage_without_exposing_database_as_transcript(
    agent, monkeypatch, tmp_path
):
    agent.uses_file_based_sessions = Mock(return_value=False)
    agent.get_session_file_path = Mock(return_value=tmp_path / "kilo.db")
    monkeypatch.setattr(
        "devflow.cli.commands.info_command.create_agent_client",
        lambda _backend: agent,
    )

    result = _get_conversation_file_path(str(tmp_path), "ses_id", "kilo")

    assert "native database storage; not a transcript file" in result
    assert str(tmp_path / "kilo.db") in result
    agent.get_session_file_path.assert_called_once_with("ses_id", str(tmp_path))
