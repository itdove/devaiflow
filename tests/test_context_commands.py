"""Tests for daf config context commands."""

import pytest
from unittest.mock import MagicMock

from devflow.cli.commands.context_commands import (
    list_context_files,
    add_context_file,
    remove_context_file,
    reset_context_files,
)
from devflow.config.models import Config, ContextFile, ContextFilesConfig


def test_list_context_files_with_defaults_only(temp_daf_home, monkeypatch, capsys):
    """Test listing context files when only defaults exist."""
    from devflow.config.loader import ConfigLoader

    # Create default config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # List context files
    list_context_files()

    captured = capsys.readouterr()
    assert "Default Files (always included):" in captured.out
    assert "AGENTS.md - agent-specific instructions" in captured.out
    assert "CLAUDE.md - project guidelines and standards" in captured.out
    assert "No additional context files configured" in captured.out


def test_list_context_files_with_configured_files(temp_daf_home, monkeypatch, capsys):
    """Test listing context files with additional configured files."""
    from devflow.config.loader import ConfigLoader

    # Create config with additional context files
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = [
        ContextFile(path="ARCHITECTURE.md", description="system architecture"),
        ContextFile(
            path="https://github.com/example-org/.github/blob/main/STANDARDS.md",
            description="coding standards",
        ),
    ]
    config_loader.save_config(config)

    # List context files
    list_context_files()

    captured = capsys.readouterr()
    # Check individual components without worrying about line breaks
    assert "Default Files (always included):" in captured.out
    assert "AGENTS.md" in captured.out
    assert "agent-specific instructions" in captured.out
    assert "CLAUDE.md" in captured.out
    assert "project guidelines and standards" in captured.out
    assert "Additional Configured Files:" in captured.out
    assert "1. ARCHITECTURE.md" in captured.out
    assert "system architecture" in captured.out
    assert "https://github.com/example-org/.github/blob/main/STANDARDS.md" in captured.out
    assert "coding" in captured.out
    assert "standards" in captured.out


def test_add_context_file_local_path(temp_daf_home, monkeypatch, capsys):
    """Test adding a local context file."""
    from devflow.config.loader import ConfigLoader

    # Create default config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Add context file
    add_context_file("ARCHITECTURE.md", "system architecture")

    # Verify it was added
    config = config_loader.load_config()
    assert len(config.context_files.files) == 1
    assert config.context_files.files[0].path == "ARCHITECTURE.md"
    assert config.context_files.files[0].description == "system architecture"

    captured = capsys.readouterr()
    assert "Added context file: ARCHITECTURE.md" in captured.out


def test_add_context_file_url(temp_daf_home, monkeypatch, capsys):
    """Test adding a URL context file."""
    from devflow.config.loader import ConfigLoader

    # Create default config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Add URL context file
    url = "https://github.com/example-org/.github/blob/main/STANDARDS.md"
    add_context_file(url, "coding standards")

    # Verify it was added
    config = config_loader.load_config()
    assert len(config.context_files.files) == 1
    assert config.context_files.files[0].path == url
    assert config.context_files.files[0].description == "coding standards"

    captured = capsys.readouterr()
    assert "Added context file:" in captured.out
    assert url in captured.out


def test_add_context_file_duplicate(temp_daf_home, monkeypatch, capsys):
    """Test adding a duplicate context file."""
    from devflow.config.loader import ConfigLoader

    # Create config with existing file
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = [
        ContextFile(path="ARCHITECTURE.md", description="system architecture")
    ]
    config_loader.save_config(config)

    # Try to add duplicate
    add_context_file("ARCHITECTURE.md", "new description")

    # Verify it was not added
    config = config_loader.load_config()
    assert len(config.context_files.files) == 1
    assert config.context_files.files[0].description == "system architecture"  # Original

    captured = capsys.readouterr()
    assert "Context file already exists: ARCHITECTURE.md" in captured.out


def test_add_context_file_default_file(temp_daf_home, monkeypatch, capsys):
    """Test trying to add a default context file (should warn)."""
    from devflow.config.loader import ConfigLoader

    # Create default config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Try to add AGENTS.md (a default file)
    add_context_file("AGENTS.md", "custom description")

    # Verify it was not added
    config = config_loader.load_config()
    assert len(config.context_files.files) == 0

    captured = capsys.readouterr()
    assert "AGENTS.md is a default context file" in captured.out


def test_add_context_file_interactive(temp_daf_home, monkeypatch, capsys):
    """Test adding context file interactively."""
    from devflow.config.loader import ConfigLoader

    # Create default config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Mock prompts
    prompt_responses = iter(["ARCHITECTURE.md", "system architecture"])
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *args, **kwargs: next(prompt_responses))

    # Add context file (no arguments triggers interactive mode)
    add_context_file(None, None)

    # Verify it was added
    config = config_loader.load_config()
    assert len(config.context_files.files) == 1
    assert config.context_files.files[0].path == "ARCHITECTURE.md"

    captured = capsys.readouterr()
    assert "Added context file: ARCHITECTURE.md" in captured.out


def test_remove_context_file_by_path(temp_daf_home, monkeypatch, capsys):
    """Test removing a context file by path."""
    from devflow.config.loader import ConfigLoader

    # Create config with context files
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = [
        ContextFile(path="ARCHITECTURE.md", description="system architecture"),
        ContextFile(path="DESIGN.md", description="design docs"),
    ]
    config_loader.save_config(config)

    # Remove one file
    remove_context_file("ARCHITECTURE.md")

    # Verify it was removed
    config = config_loader.load_config()
    assert len(config.context_files.files) == 1
    assert config.context_files.files[0].path == "DESIGN.md"

    captured = capsys.readouterr()
    assert "Removed context file: ARCHITECTURE.md" in captured.out


def test_remove_context_file_not_found(temp_daf_home, monkeypatch, capsys):
    """Test removing a context file that doesn't exist when no files are configured."""
    from devflow.config.loader import ConfigLoader

    # Create config (no configured context files)
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Try to remove non-existent file
    remove_context_file("NONEXISTENT.md")

    captured = capsys.readouterr()
    # When no files are configured, it shows this message first
    assert "No configured context files to remove" in captured.out


def test_remove_context_file_interactive(temp_daf_home, monkeypatch, capsys):
    """Test removing context file interactively."""
    from devflow.config.loader import ConfigLoader

    # Create config with context files
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = [
        ContextFile(path="ARCHITECTURE.md", description="system architecture"),
        ContextFile(path="DESIGN.md", description="design docs"),
    ]
    config_loader.save_config(config)

    # Mock prompt to select first file
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *args, **kwargs: "1")

    # Remove context file (no argument triggers interactive mode)
    remove_context_file(None)

    # Verify first file was removed
    config = config_loader.load_config()
    assert len(config.context_files.files) == 1
    assert config.context_files.files[0].path == "DESIGN.md"

    captured = capsys.readouterr()
    assert "Removed context file: ARCHITECTURE.md" in captured.out


def test_reset_context_files(temp_daf_home, monkeypatch, capsys):
    """Test resetting context files to defaults."""
    from devflow.config.loader import ConfigLoader

    # Create config with context files
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = [
        ContextFile(path="ARCHITECTURE.md", description="system architecture"),
        ContextFile(path="DESIGN.md", description="design docs"),
    ]
    config_loader.save_config(config)

    # Mock confirmation
    monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *args, **kwargs: True)

    # Reset
    reset_context_files()

    # Verify all configured files were removed
    config = config_loader.load_config()
    assert len(config.context_files.files) == 0

    captured = capsys.readouterr()
    assert "Reset to default context files" in captured.out


def test_reset_context_files_already_empty(temp_daf_home, monkeypatch, capsys):
    """Test resetting when no configured files exist."""
    from devflow.config.loader import ConfigLoader

    # Create default config (no configured files)
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Reset
    reset_context_files()

    captured = capsys.readouterr()
    assert "No configured context files to reset" in captured.out


def test_reset_context_files_cancelled(temp_daf_home, monkeypatch, capsys):
    """Test cancelling reset."""
    from devflow.config.loader import ConfigLoader

    # Create config with context files
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = [
        ContextFile(path="ARCHITECTURE.md", description="system architecture"),
    ]
    config_loader.save_config(config)

    # Mock confirmation to decline
    monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *args, **kwargs: False)

    # Reset (but cancel)
    reset_context_files()

    # Verify files were not removed
    config = config_loader.load_config()
    assert len(config.context_files.files) == 1

    captured = capsys.readouterr()
    assert "Cancelled" in captured.out
