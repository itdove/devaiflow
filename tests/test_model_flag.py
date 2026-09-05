"""Tests for --model CLI flag (Issue #550).

Tests the --model flag added to daf new, daf open, daf investigate,
daf jira new, and daf git new commands.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.utils.model_provider import apply_model_override


class TestApplyModelOverride:
    """Tests for the apply_model_override helper."""

    def test_no_model_returns_profile_unchanged(self):
        profile = {"model_name": "claude-opus-4-6", "base_url": "http://x"}
        result = apply_model_override(profile, None)
        assert result == profile

    def test_no_model_returns_none_unchanged(self):
        assert apply_model_override(None, None) is None

    def test_model_with_existing_profile_overrides_model_name(self):
        profile = {"model_name": "old-model", "base_url": "http://x"}
        result = apply_model_override(profile, "new-model")
        assert result["model_name"] == "new-model"
        assert result["base_url"] == "http://x"

    def test_model_with_existing_profile_does_not_mutate_original(self):
        profile = {"model_name": "old-model", "base_url": "http://x"}
        apply_model_override(profile, "new-model")
        assert profile["model_name"] == "old-model"

    def test_model_with_no_profile_creates_synthetic(self):
        result = apply_model_override(None, "ollama/llama3:70b")
        assert result == {"model_name": "ollama/llama3:70b"}

    def test_empty_model_returns_profile_unchanged(self):
        profile = {"model_name": "keep"}
        assert apply_model_override(profile, "") is profile


class TestModelFlagInHelp:
    """Test --model flag appears in help for all 5 commands."""

    @pytest.mark.parametrize("cmd", [
        ["new", "--help"],
        ["open", "--help"],
        ["investigate", "--help"],
        ["jira", "new", "--help"],
        ["git", "new", "--help"],
    ])
    def test_model_flag_in_help(self, cmd):
        runner = CliRunner()
        result = runner.invoke(cli, cmd)
        assert result.exit_code == 0
        assert "--model " in result.output or "--model TEXT" in result.output

    @pytest.mark.parametrize("cmd", [
        ["jira", "new", "--help"],
        ["git", "new", "--help"],
    ])
    def test_model_profile_flag_in_help(self, cmd):
        runner = CliRunner()
        result = runner.invoke(cli, cmd)
        assert result.exit_code == 0
        assert "--model-profile" in result.output

    @pytest.mark.parametrize("cmd", [
        ["new", "--help"],
        ["open", "--help"],
        ["investigate", "--help"],
        ["jira", "new", "--help"],
        ["git", "new", "--help"],
    ])
    def test_session_commands_do_not_expose_agent_selector(self, cmd):
        runner = CliRunner()
        result = runner.invoke(cli, cmd)
        assert result.exit_code == 0
        assert "--agent" not in result.output


class TestModelFlagPassthrough:
    """Test --model flag is passed through to command handlers."""

    @patch("devflow.cli.commands.new_command.create_new_session")
    def test_new_passes_model(self, mock_create):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "new", "--name", "test", "--goal", "test goal",
            "--model", "claude-sonnet-5",
            "--path", "/tmp/test",
        ], catch_exceptions=False)
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        if "model" in kwargs:
            assert kwargs["model"] == "claude-sonnet-5"
        else:
            args = mock_create.call_args[0]
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get("model") == "claude-sonnet-5"

    @patch("devflow.cli.commands.open_command.open_session")
    def test_open_passes_model(self, mock_open):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "open", "test-session",
            "--model", "ollama/llama3:70b",
        ], catch_exceptions=False)
        mock_open.assert_called_once()
        _, kwargs = mock_open.call_args
        assert kwargs.get("model") == "ollama/llama3:70b"

    @patch("devflow.cli.commands.investigate_command.create_investigation_session")
    def test_investigate_passes_model(self, mock_investigate):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "investigate",
            "--goal", "test investigation",
            "--model", "codex/o3-mini",
        ], catch_exceptions=False)
        mock_investigate.assert_called_once()
        _, kwargs = mock_investigate.call_args
        assert kwargs.get("model") == "codex/o3-mini"

    @patch("devflow.cli.commands.jira_new_command.create_jira_ticket_session")
    @patch("devflow.jira.utils.is_version_field_required", return_value=False)
    @patch("devflow.config.loader.ConfigLoader.load_config")
    def test_jira_new_passes_model_and_profile(self, mock_config, mock_ver, mock_create):
        mock_config.return_value = MagicMock(jira=None)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--goal", "test ticket",
            "--model", "claude-sonnet-5",
            "--model-profile", "vertex",
        ], catch_exceptions=False)
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs.get("model") == "claude-sonnet-5" or "claude-sonnet-5" in str(mock_create.call_args)
        assert kwargs.get("model_profile") == "vertex" or "vertex" in str(mock_create.call_args)

    @patch("devflow.cli.commands.git_new_command.create_git_issue_session")
    def test_git_new_passes_model_and_profile(self, mock_create):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "git", "new",
            "--goal", "test issue",
            "--model", "ollama/qwen:7b",
            "--model-profile", "llama-cpp",
        ], catch_exceptions=False)
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs.get("model") == "ollama/qwen:7b" or "ollama/qwen:7b" in str(mock_create.call_args)
        assert kwargs.get("model_profile") == "llama-cpp" or "llama-cpp" in str(mock_create.call_args)
