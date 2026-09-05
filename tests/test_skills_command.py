"""Tests for multi-agent skill installation command selection."""

from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from devflow.cli.commands.skills_command import assets


def _config():
    """Return the smallest config shape required by the command."""
    return SimpleNamespace(
        repos=SimpleNamespace(
            workspaces=[SimpleNamespace(name="default", path="/tmp/workspace")]
        )
    )


def test_assets_without_agent_uses_detected_agents():
    """The default installer target is the detected agent set."""
    runner = CliRunner()
    with patch("devflow.cli.commands.skills_command.ConfigLoader") as loader_class:
        loader_class.return_value.load_config.return_value = _config()
        with patch(
            "devflow.agent.skill_directories.detect_configured_agents",
            return_value=["claude", "codex"],
        ):
            with patch("devflow.cli.commands.skills_command._install_skills") as install:
                result = runner.invoke(assets, ["--dry-run", "--type", "bundled"])

    assert result.exit_code == 0
    assert install.call_args.kwargs["agents"] == ["claude", "codex"]
    assert install.call_args.kwargs["dry_run"] is True


def test_assets_explicit_agent_remains_authoritative():
    """An explicit agent option is not expanded by automatic detection."""
    runner = CliRunner()
    with patch("devflow.cli.commands.skills_command.ConfigLoader") as loader_class:
        loader_class.return_value.load_config.return_value = _config()
        with patch(
            "devflow.agent.skill_directories.detect_configured_agents",
            return_value=["claude", "codex"],
        ) as detect:
            with patch("devflow.cli.commands.skills_command._install_skills") as install:
                result = runner.invoke(assets, ["--agent", "codex", "--dry-run"])

    assert result.exit_code == 0
    assert install.call_args.kwargs["agents"] == ["codex"]
    detect.assert_not_called()
