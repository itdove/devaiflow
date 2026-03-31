"""Tests for daf skills command (discovery and inspection)."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from devflow.cli.commands.skills_discovery_command import (
    _discover_all_skills,
    _discover_skills_in_dir,
    _parse_skill_file,
    _list_skills_json,
    _list_skills_table,
    _inspect_skill,
    skills
)


@pytest.fixture
def mock_skill_dir(tmp_path):
    """Create a mock skill directory with sample skills."""
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()

    # Create a skill with frontmatter
    skill1 = skill_dir / "daf-test"
    skill1.mkdir()
    skill1_file = skill1 / "SKILL.md"
    skill1_file.write_text("""---
name: daf-test
description: Test skill for unit tests
user-invocable: true
---

# Test Skill

This is a test skill.
""")

    # Create a skill without frontmatter
    skill2 = skill_dir / "test-cli"
    skill2.mkdir()
    skill2_file = skill2 / "SKILL.md"
    skill2_file.write_text("""# Test CLI Skill

A skill without frontmatter.
""")

    # Create a non-skill directory (no SKILL.md)
    non_skill = skill_dir / "not-a-skill"
    non_skill.mkdir()

    return skill_dir


def test_parse_skill_file_with_frontmatter(tmp_path):
    """Test parsing a skill file with YAML frontmatter."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("""---
name: test-skill
description: Test description
user-invocable: true
---

# Test Skill

Content here.
""")

    frontmatter, description = _parse_skill_file(skill_file)

    assert frontmatter["name"] == "test-skill"
    assert frontmatter["description"] == "Test description"
    assert frontmatter["user-invocable"] == "true" or frontmatter["user-invocable"] is True
    assert "Test Skill" in description or "Content here" in description


def test_parse_skill_file_without_frontmatter(tmp_path):
    """Test parsing a skill file without frontmatter."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("""# Simple Skill

This is a simple skill without frontmatter.
""")

    frontmatter, description = _parse_skill_file(skill_file)

    assert frontmatter == {} or len(frontmatter) == 0
    assert "simple skill" in description.lower()


def test_discover_skills_in_dir(mock_skill_dir):
    """Test discovering skills in a directory."""
    skills = _discover_skills_in_dir(mock_skill_dir, "user")

    assert len(skills) == 2  # Should find 2 skills (not-a-skill has no SKILL.md)

    skill_names = [s["name"] for s in skills]
    assert "daf-test" in skill_names
    assert "test-cli" in skill_names

    # Verify skill with frontmatter
    daf_test = next(s for s in skills if s["name"] == "daf-test")
    assert daf_test["description"] == "Test skill for unit tests"
    assert daf_test["level"] == "user"
    assert "frontmatter" in daf_test
    assert daf_test["frontmatter"]["name"] == "daf-test"


def test_discover_skills_in_dir_empty(tmp_path):
    """Test discovering skills in an empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    skills = _discover_skills_in_dir(empty_dir, "user")

    assert skills == []


def test_discover_all_skills_user_level(monkeypatch, mock_skill_dir):
    """Test discovering skills at user level."""
    with patch('devflow.cli.commands.skills_discovery_command.get_claude_config_dir', return_value=mock_skill_dir.parent):
        with patch('devflow.cli.commands.skills_discovery_command.get_cs_home', return_value=Path("/nonexistent")):
            # Rename mock_skill_dir to match expected user skills path
            user_skills = mock_skill_dir.parent / "skills"
            if mock_skill_dir != user_skills:
                mock_skill_dir.rename(user_skills)

            skills_by_level = _discover_all_skills(workspace_path=None)

            assert "user" in skills_by_level
            assert len(skills_by_level["user"]) == 2
            assert len(skills_by_level["workspace"]) == 0
            assert len(skills_by_level["hierarchical"]) == 0
            assert len(skills_by_level["project"]) == 0


def test_list_skills_json_output(monkeypatch, mock_skill_dir, capsys):
    """Test JSON output for skills list."""
    skills_by_level = {
        "user": _discover_skills_in_dir(mock_skill_dir, "user"),
        "workspace": [],
        "hierarchical": [],
        "project": []
    }

    _list_skills_json(skills_by_level)

    # Capture stdout
    captured = capsys.readouterr()

    # Verify JSON structure
    output = json.loads(captured.out)
    assert "skills" in output
    assert "total" in output
    assert "levels" in output
    assert output["total"] == 2
    assert len(output["skills"]) == 2

    # Verify skills are sorted by name
    skill_names = [s["name"] for s in output["skills"]]
    assert skill_names == sorted(skill_names)


def test_list_skills_table_output(monkeypatch, mock_skill_dir):
    """Test table output for skills list."""
    skills_by_level = {
        "user": _discover_skills_in_dir(mock_skill_dir, "user"),
        "workspace": [],
        "hierarchical": [],
        "project": []
    }

    with patch('devflow.cli.commands.skills_discovery_command.console') as mock_console:
        with patch('devflow.cli.commands.skills_discovery_command.get_claude_config_dir', return_value=mock_skill_dir.parent):
            with patch('devflow.cli.commands.skills_discovery_command.get_cs_home', return_value=Path("/nonexistent")):
                _list_skills_table(skills_by_level)

                # Verify console.print was called (table was displayed)
                assert mock_console.print.called
                # Verify user-level skills were mentioned
                calls = [str(call) for call in mock_console.print.call_args_list]
                output_text = " ".join(calls)
                assert "daf-test" in output_text or "test-cli" in output_text


def test_inspect_skill_found(monkeypatch, mock_skill_dir):
    """Test inspecting a skill that exists."""
    skills_by_level = {
        "user": _discover_skills_in_dir(mock_skill_dir, "user"),
        "workspace": [],
        "hierarchical": [],
        "project": []
    }

    with patch('devflow.cli.commands.skills_discovery_command.console') as mock_console:
        _inspect_skill("daf-test", skills_by_level, output_json=False)

        # Verify skill details were printed
        assert mock_console.print.called
        calls = [str(call) for call in mock_console.print.call_args_list]
        output_text = " ".join(calls)
        assert "daf-test" in output_text
        assert "Test skill for unit tests" in output_text or "Test Skill" in output_text


def test_inspect_skill_not_found(monkeypatch):
    """Test inspecting a skill that doesn't exist."""
    skills_by_level = {
        "user": [],
        "workspace": [],
        "hierarchical": [],
        "project": []
    }

    with patch('devflow.cli.commands.skills_discovery_command.console') as mock_console:
        _inspect_skill("nonexistent-skill", skills_by_level, output_json=False)

        # Verify error message was printed
        assert mock_console.print.called
        calls = [str(call) for call in mock_console.print.call_args_list]
        output_text = " ".join(calls)
        assert "not found" in output_text.lower()


def test_inspect_skill_json_output(monkeypatch, mock_skill_dir, capsys):
    """Test JSON output for skill inspection."""
    skills_by_level = {
        "user": _discover_skills_in_dir(mock_skill_dir, "user"),
        "workspace": [],
        "hierarchical": [],
        "project": []
    }

    _inspect_skill("daf-test", skills_by_level, output_json=True)

    # Capture stdout
    captured = capsys.readouterr()

    # Verify JSON structure
    output = json.loads(captured.out)
    assert output["name"] == "daf-test"
    assert output["description"] == "Test skill for unit tests"
    assert output["level"] == "user"
    assert "file_path" in output
    assert "frontmatter" in output
    assert "content_preview" in output


def test_inspect_skill_multiple_levels(monkeypatch, mock_skill_dir):
    """Test inspecting a skill that exists at multiple levels."""
    # Create same skill at different levels
    skills_by_level = {
        "user": _discover_skills_in_dir(mock_skill_dir, "user"),
        "hierarchical": _discover_skills_in_dir(mock_skill_dir, "hierarchical"),  # Duplicate
        "workspace": [],
        "project": []
    }

    with patch('devflow.cli.commands.skills_discovery_command.console') as mock_console:
        _inspect_skill("daf-test", skills_by_level, output_json=False)

        # Verify multiple instances were mentioned
        assert mock_console.print.called
        calls = [str(call) for call in mock_console.print.call_args_list]
        output_text = " ".join(calls)
        assert "levels" in output_text.lower() or "instance" in output_text.lower()


def test_skills_command_list_mode(monkeypatch):
    """Test skills command in list mode (no arguments)."""
    runner = CliRunner()
    mock_config = MagicMock()
    mock_config.repos.workspaces = []

    with patch('devflow.cli.commands.skills_discovery_command.ConfigLoader') as mock_loader_class:
        with patch('devflow.cli.commands.skills_discovery_command._discover_all_skills', return_value={"user": [], "workspace": [], "hierarchical": [], "project": []}):
            with patch('devflow.cli.commands.skills_discovery_command._list_all_skills') as mock_list:
                mock_loader = MagicMock()
                mock_loader.load_config.return_value = mock_config
                mock_loader_class.return_value = mock_loader

                result = runner.invoke(skills, [])

                # Verify list function was called
                assert result.exit_code == 0
                mock_list.assert_called_once()


def test_skills_command_inspect_mode(monkeypatch):
    """Test skills command in inspect mode (with skill name)."""
    runner = CliRunner()
    mock_config = MagicMock()
    mock_config.repos.workspaces = []

    with patch('devflow.cli.commands.skills_discovery_command.ConfigLoader') as mock_loader_class:
        with patch('devflow.cli.commands.skills_discovery_command._discover_all_skills', return_value={"user": [], "workspace": [], "hierarchical": [], "project": []}):
            with patch('devflow.cli.commands.skills_discovery_command._inspect_skill') as mock_inspect:
                mock_loader = MagicMock()
                mock_loader.load_config.return_value = mock_config
                mock_loader_class.return_value = mock_loader

                result = runner.invoke(skills, ["test-skill"])

                # Verify inspect function was called
                assert result.exit_code == 0
                mock_inspect.assert_called_once_with("test-skill", {"user": [], "workspace": [], "hierarchical": [], "project": []}, False)


def test_skills_command_json_mode(monkeypatch):
    """Test skills command with JSON output."""
    runner = CliRunner()
    mock_config = MagicMock()
    mock_config.repos.workspaces = []

    with patch('devflow.cli.commands.skills_discovery_command.ConfigLoader') as mock_loader_class:
        with patch('devflow.cli.commands.skills_discovery_command._discover_all_skills', return_value={"user": [], "workspace": [], "hierarchical": [], "project": []}):
            with patch('devflow.cli.commands.skills_discovery_command._list_all_skills') as mock_list:
                mock_loader = MagicMock()
                mock_loader.load_config.return_value = mock_config
                mock_loader_class.return_value = mock_loader

                result = runner.invoke(skills, ["--json"])

                # Verify JSON flag was passed
                assert result.exit_code == 0
                mock_list.assert_called_once()
                args, kwargs = mock_list.call_args
                assert args[1] is True  # output_json parameter
