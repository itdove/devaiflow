"""Private OpenCode workspace ownership for temporary clones (issue #646)."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from devflow.agent.factory import launch_and_capture
from devflow.agent.opencode_agent import OpenCodeAgent, OpenCodeCompatibilityError


@pytest.mark.parametrize("major", [1, 2])
@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("with_model", [False, True])
@pytest.mark.parametrize("entrypoint", ["launch", "resume", "prompt", "headless"])
def test_clone_launch_owns_private_v2_server_without_changing_native_identity(
    monkeypatch, tmp_path, major, isolated, with_model, entrypoint
):
    """All launch/resume shapes use supported private lifecycle only for v2 clones."""
    agent = OpenCodeAgent()
    monkeypatch.setattr(agent, "get_opencode_version", lambda: major)
    monkeypatch.setattr("devflow.agent.opencode_agent.require_tool", lambda *a: None)
    popen = Mock()
    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.Popen", popen)
    profile = {"arguments": ["--agent", "build"]}
    if with_model:
        profile["model_name"] = "provider/model-a"
    kwargs = {
        "project_path": str(tmp_path),
        "model_provider_profile": profile,
        "env": {"PATH": "/bin"},
        "isolated_workspace": isolated,
    }
    if entrypoint == "launch":
        agent.launch_session(**kwargs)
    elif entrypoint == "resume":
        agent.resume_session("ses_existing", **kwargs)
    else:
        agent.launch_with_prompt(
            initial_prompt="Read project instructions",
            session_id="ses_existing",
            headless=entrypoint == "headless",
            **kwargs,
        )

    command = popen.call_args.args[0]
    assert command.count("--standalone") == int(major == 2 and isolated)
    assert "--server" not in command
    assert command[command.index("--agent") + 1] == "build"
    if entrypoint != "launch":
        assert command[command.index("--session") + 1] == "ses_existing"
    if entrypoint == "headless":
        assert command[:2] == ["opencode", "run"]
        assert command[-1] == "Read project instructions"
    elif major == 2 and with_model:
        assert command[:2] == ["opencode", "mini"]
    else:
        assert command[0] == "opencode" and "mini" not in command
    assert popen.call_args.kwargs == {"cwd": str(tmp_path), "env": {"PATH": "/bin"}}


@pytest.mark.parametrize("entrypoint", ["launch", "resume", "prompt"])
@pytest.mark.parametrize(
    "arguments",
    [
        ["--server", "http://localhost:4096"],
        ["--server=http://localhost:4096"],
        ["--standalone=false"],
    ],
)
def test_private_clone_rejects_explicit_shared_connection_before_side_effects(
    monkeypatch, tmp_path, entrypoint, arguments
):
    """Never override a remote connection or create/rename sessions before refusal."""
    agent = OpenCodeAgent()
    monkeypatch.setattr(agent, "get_opencode_version", lambda: 2)
    monkeypatch.setattr("devflow.agent.opencode_agent.require_tool", lambda *a: None)
    popen = Mock()
    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.Popen", popen)
    create = Mock()
    update = Mock()
    monkeypatch.setattr(agent, "_create_session_with_title", create)
    monkeypatch.setattr(agent, "update_session_title", update)
    kwargs = {
        "project_path": str(tmp_path),
        "model_provider_profile": {"arguments": arguments},
        "isolated_workspace": True,
        "display_name": "session-a",
    }
    with pytest.raises(OpenCodeCompatibilityError, match="private server"):
        if entrypoint == "launch":
            agent.launch_session(**kwargs)
        elif entrypoint == "resume":
            agent.resume_session("ses_existing", **kwargs)
        else:
            agent.launch_with_prompt(initial_prompt="Read", session_id="pending-capture", **kwargs)
    popen.assert_not_called()
    create.assert_not_called()
    update.assert_not_called()


def test_private_option_does_not_duplicate_or_mutate_profile_arguments():
    """Already-private profiles remain private without mutating saved argv."""
    args = ["--standalone", "--agent", "build"]
    assert OpenCodeAgent._workspace_arguments(2, True, args) == args
    assert OpenCodeAgent._workspace_arguments(1, True, ["--server", "address"]) == [
        "--server",
        "address",
    ]
    shared_args = ["--agent", "build"]
    assert OpenCodeAgent._workspace_arguments(2, True, shared_args) == [
        *shared_args,
        "--standalone",
    ]
    assert shared_args == ["--agent", "build"]


@pytest.mark.parametrize("backend", ["opencode", "opencode-ai", "claude", "pi", "codex"])
@pytest.mark.parametrize("temporary", [False, True])
def test_factory_requests_private_ownership_only_for_opencode_clones(
    temp_daf_home, tmp_path, monkeypatch, backend, temporary
):
    """The common lifecycle covers git/jira-new, investigation, and fresh reopen."""
    agent = Mock()
    agent.launch_with_prompt.return_value = Mock(returncode=0)
    conversation = SimpleNamespace(
        ai_agent_session_id="pending-capture",
        temp_directory=str(tmp_path) if temporary else None,
    )
    monkeypatch.setattr("devflow.agent.factory.snapshot_agent_sessions", lambda *a: set())
    monkeypatch.setattr("devflow.agent.factory.capture_agent_session_id", lambda *a, **kw: False)
    launch_and_capture(
        agent,
        backend,
        str(tmp_path),
        conversation,
        initial_prompt="Read project instructions",
        session_id="pending-capture",
    )
    expected = temporary and backend in ("opencode", "opencode-ai")
    assert agent.launch_with_prompt.call_args.kwargs.get("isolated_workspace", False) is expected
    agent.wait_for_exit.assert_called_once()


@pytest.mark.parametrize("major", [1, 2])
def test_session_metadata_polling_never_reopens_shared_v2_workspace(monkeypatch, tmp_path, major):
    """Even after private UI exit, session-ID capture must not retain shared MCPs."""
    agent = OpenCodeAgent()
    agent._opencode_major_version = major
    run = Mock(
        return_value=Mock(
            returncode=0,
            stdout=json.dumps([{"id": "ses_existing", "directory": str(tmp_path)}]),
        )
    )
    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", run)
    assert agent.get_existing_sessions(str(tmp_path)) == {"ses_existing"}
    assert agent.session_exists("ses_existing", str(tmp_path))
    for call in run.call_args_list:
        assert ("--standalone" in call.args[0]) is (major == 2)
        assert call.kwargs["cwd"] == str(tmp_path)
