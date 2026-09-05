"""Tests for workspace skill installation and agent detection integration."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from devflow.utils.workspace_utils import ensure_workspace_skills_and_commands


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def _mock_results(changed=None, up_to_date=None, failed=None):
    """Build the installer result shape used by workspace utilities."""
    return {"claude": (changed or [], up_to_date or [], failed or [])}


def test_ensure_workspace_skills_success(temp_workspace):
    """Install bundled skills for the detected fallback agent."""
    with patch(
        "devflow.agent.skill_directories.detect_configured_agents",
        return_value=["claude"],
    ) as mock_detect:
        with patch(
            "devflow.utils.claude_commands.install_skills_to_agents",
            return_value=_mock_results(
                changed=["daf-help", "daf-cli"], up_to_date=["daf-active"]
            ),
        ) as mock_install:
            success, error = ensure_workspace_skills_and_commands(
                str(temp_workspace), quiet=True
            )

    assert success is True
    assert error is None
    mock_detect.assert_called_once()
    mock_install.assert_called_once_with(
        agents=["claude"],
        level="global",
        project_path=None,
        skip_confirmation=True,
        dry_run=False,
        quiet=True,
    )


def test_ensure_workspace_skills_nonexistent_workspace(tmp_path):
    """Reject an installation request for a missing workspace."""
    nonexistent = tmp_path / "nonexistent"

    success, error = ensure_workspace_skills_and_commands(str(nonexistent), quiet=True)

    assert success is False
    assert "does not exist" in error.lower()


def test_ensure_workspace_skills_installs_for_multiple_configured_agents(temp_workspace):
    """Use all configured agents and preserve the configured install level."""
    config = SimpleNamespace(
        agent=SimpleNamespace(enabled_agents=["claude", "codex"], install_level="both"),
    )
    with patch(
        "devflow.agent.skill_directories.detect_configured_agents",
        return_value=["claude", "codex"],
    ):
        with patch(
            "devflow.utils.claude_commands.install_skills_to_agents",
            return_value={
                "claude": (["daf-cli"], [], []),
                "codex": (["daf-cli"], [], []),
            },
        ) as mock_install:
            success, error = ensure_workspace_skills_and_commands(
                str(temp_workspace), quiet=True, config=config
            )

    assert success is True
    assert error is None
    mock_install.assert_called_once_with(
        agents=["claude", "codex"],
        level="both",
        project_path=temp_workspace.resolve(),
        skip_confirmation=True,
        dry_run=False,
        quiet=True,
    )


def test_ensure_workspace_skills_with_failures(temp_workspace):
    """Report failures returned for any configured agent."""
    with patch(
        "devflow.agent.skill_directories.detect_configured_agents",
        return_value=["claude", "codex"],
    ):
        with patch(
            "devflow.utils.claude_commands.install_skills_to_agents",
            return_value={
                "claude": (["daf-help"], [], ["daf-broken"]),
                "codex": ([], [], ["daf-cli-broken"]),
            },
        ):
            success, error = ensure_workspace_skills_and_commands(
                str(temp_workspace), quiet=True
            )

    assert success is False
    assert "Failed to install/upgrade" in error
    assert "claude" in error
    assert "codex" in error
    assert "daf-broken" in error
    assert "daf-cli-broken" in error


def test_ensure_workspace_skills_quiet_mode(temp_workspace, capsys):
    """Quiet mode suppresses utility-level output."""
    with patch(
        "devflow.agent.skill_directories.detect_configured_agents",
        return_value=["claude"],
    ):
        with patch(
            "devflow.utils.claude_commands.install_skills_to_agents",
            return_value=_mock_results(changed=["daf-help"]),
        ):
            ensure_workspace_skills_and_commands(str(temp_workspace), quiet=True)

    captured = capsys.readouterr()
    assert captured.out == ""


def test_ensure_workspace_skills_verbose_mode(temp_workspace):
    """Verbose mode reports the detected agents and install scope."""
    with patch(
        "devflow.agent.skill_directories.detect_configured_agents",
        return_value=["claude", "codex"],
    ):
        with patch(
            "devflow.utils.claude_commands.install_skills_to_agents",
            return_value={
                "claude": (["daf-help", "daf-list"], [], []),
                "codex": (["daf-cli"], [], []),
            },
        ):
            with patch("devflow.utils.workspace_utils.console") as mock_console:
                ensure_workspace_skills_and_commands(str(temp_workspace), quiet=False)

    mock_console.print.assert_called()
    call_args = str(mock_console.print.call_args)
    assert "Installed/upgraded" in call_args
    assert "claude, codex" in call_args


def test_ensure_workspace_skills_all_up_to_date(temp_workspace):
    """Return success when every configured agent is already current."""
    with patch(
        "devflow.agent.skill_directories.detect_configured_agents",
        return_value=["claude"],
    ):
        with patch(
            "devflow.utils.claude_commands.install_skills_to_agents",
            return_value=_mock_results(up_to_date=["daf-help", "daf-cli"]),
        ):
            success, error = ensure_workspace_skills_and_commands(
                str(temp_workspace), quiet=True
            )

    assert success is True
    assert error is None


def test_ensure_workspace_skills_exception_handling(temp_workspace):
    """Convert unexpected installer errors to a useful result."""
    with patch(
        "devflow.agent.skill_directories.detect_configured_agents",
        return_value=["claude"],
    ):
        with patch(
            "devflow.utils.claude_commands.install_skills_to_agents",
            side_effect=Exception("Unexpected error"),
        ):
            success, error = ensure_workspace_skills_and_commands(
                str(temp_workspace), quiet=True
            )

    assert success is False
    assert "Error installing skills" in error
    assert "Unexpected error" in error


def test_ensure_workspace_skills_with_tilde_path(tmp_path, monkeypatch):
    """Expand a tilde in the workspace path before validating it."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))

    with patch("pathlib.Path.home", return_value=tmp_path):
        with patch(
            "devflow.agent.skill_directories.detect_configured_agents",
            return_value=["claude"],
        ):
            with patch(
                "devflow.utils.claude_commands.install_skills_to_agents",
                return_value=_mock_results(),
            ):
                success, error = ensure_workspace_skills_and_commands(
                    "~/workspace", quiet=True
                )

    assert success is True
    assert error is None


def test_ensure_workspace_skills_uses_configured_agent_level(temp_workspace):
    """Pass the configured project installation level to the installer."""
    config = SimpleNamespace(
        agent=SimpleNamespace(enabled_agents=["codex"], install_level="project"),
    )
    with patch(
        "devflow.agent.skill_directories.detect_configured_agents",
        return_value=["codex"],
    ):
        with patch(
            "devflow.utils.claude_commands.install_skills_to_agents",
            return_value={"codex": ([], ["daf-cli"], [])},
        ) as mock_install:
            success, error = ensure_workspace_skills_and_commands(
                str(temp_workspace), quiet=True, config=config
            )

    assert success is True
    assert error is None
    mock_install.assert_called_once_with(
        agents=["codex"],
        level="project",
        project_path=temp_workspace.resolve(),
        skip_confirmation=True,
        dry_run=False,
        quiet=True,
    )
