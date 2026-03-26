"""Integration tests for CLAUDE_CONFIG_DIR environment variable support.

These tests verify that DevAIFlow respects the official Claude Code
environment variable CLAUDE_CONFIG_DIR for skill installation and session
operations.
"""

import os
from pathlib import Path

import pytest

from devflow.agent.claude_agent import ClaudeAgent
from devflow.utils.claude_commands import install_or_upgrade_reference_skills
from devflow.utils.paths import get_claude_config_dir


class TestClaudeConfigDirIntegration:
    """Integration tests for CLAUDE_CONFIG_DIR support."""

    def test_get_claude_config_dir_respects_env_var(self, tmp_path, monkeypatch):
        """Test that get_claude_config_dir respects CLAUDE_CONFIG_DIR."""
        custom_path = tmp_path / "custom-claude-config"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_path))

        result = get_claude_config_dir()

        assert result == custom_path

    def test_skill_installation_respects_claude_config_dir(self, tmp_path, monkeypatch):
        """Test that skill installation uses CLAUDE_CONFIG_DIR."""
        custom_path = tmp_path / "custom-claude-config"
        custom_path.mkdir(parents=True)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_path))

        # Install skills
        changed, up_to_date, failed = install_or_upgrade_reference_skills(dry_run=False, quiet=True)

        # Verify skills were installed to custom directory
        skills_dir = custom_path / "skills"
        assert skills_dir.exists()

        # Verify at least one skill was installed
        assert len(list(skills_dir.iterdir())) > 0

    def test_claude_agent_respects_claude_config_dir(self, tmp_path, monkeypatch):
        """Test that ClaudeAgent uses CLAUDE_CONFIG_DIR."""
        custom_path = tmp_path / "custom-claude-config"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_path))

        agent = ClaudeAgent()

        assert agent.claude_dir == custom_path
        assert agent.projects_dir == custom_path / "projects"

    def test_claude_agent_with_custom_dir_overrides_env(self, tmp_path, monkeypatch):
        """Test that ClaudeAgent's custom dir parameter overrides env var."""
        env_path = tmp_path / "env-claude-config"
        custom_path = tmp_path / "custom-claude-config"

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(env_path))

        # Pass custom_path to constructor - should override env var
        agent = ClaudeAgent(claude_dir=custom_path)

        assert agent.claude_dir == custom_path
        assert agent.claude_dir != env_path

    def test_skill_installation_in_custom_dir_creates_directory(self, tmp_path, monkeypatch):
        """Test that skill installation creates CLAUDE_CONFIG_DIR if needed."""
        custom_path = tmp_path / "non-existent" / "claude-config"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_path))

        # Directory should not exist yet
        assert not custom_path.exists()

        # Install skills
        changed, up_to_date, failed = install_or_upgrade_reference_skills(dry_run=False, quiet=True)

        # Verify directory was created
        assert custom_path.exists()
        assert (custom_path / "skills").exists()

    def test_default_behavior_without_env_var(self, tmp_path, monkeypatch):
        """Test that default behavior is preserved when CLAUDE_CONFIG_DIR is not set."""
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = get_claude_config_dir()
        expected = tmp_path / ".claude"

        assert result == expected

    def test_multiple_agents_share_same_claude_config_dir(self, tmp_path, monkeypatch):
        """Test that multiple ClaudeAgent instances use the same CLAUDE_CONFIG_DIR."""
        custom_path = tmp_path / "shared-claude-config"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_path))

        agent1 = ClaudeAgent()
        agent2 = ClaudeAgent()

        assert agent1.claude_dir == agent2.claude_dir
        assert agent1.claude_dir == custom_path
