"""Tests for daf check command."""

import json
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from devflow.cli.commands.check_command import check_dependencies, _display_tools_table


@pytest.fixture
def all_tools_available():
    """Mock status where all tools are available."""
    return {
        "git": {
            "available": "true",
            "version": "git version 2.39.0",
            "description": "Git version control",
            "install_url": "https://git-scm.com/downloads",
            "required": "true",
        },
        "claude": {
            "available": "true",
            "version": "claude 1.2.3",
            "description": "Claude Code CLI",
            "install_url": "https://docs.claude.com/en/docs/claude-code/installation",
            "required": "true",
        },
        "gh": {
            "available": "true",
            "version": "gh 2.40.1",
            "description": "GitHub CLI",
            "install_url": "https://cli.github.com/",
            "required": "false",
        },
        "glab": {
            "available": "true",
            "version": "glab 1.35.0",
            "description": "GitLab CLI",
            "install_url": "https://gitlab.com/gitlab-org/cli",
            "required": "false",
        },
        "pytest": {
            "available": "true",
            "version": "pytest 7.4.3",
            "description": "Python testing framework",
            "install_url": "https://docs.pytest.org/",
            "required": "false",
        },
    }


@pytest.fixture
def some_tools_missing():
    """Mock status where some optional tools are missing."""
    return {
        "git": {
            "available": "true",
            "version": "git version 2.39.0",
            "description": "Git version control",
            "install_url": "https://git-scm.com/downloads",
            "required": "true",
        },
        "claude": {
            "available": "true",
            "version": "claude 1.2.3",
            "description": "Claude Code CLI",
            "install_url": "https://docs.claude.com/en/docs/claude-code/installation",
            "required": "true",
        },
        "gh": {
            "available": "false",
            "version": "",
            "description": "GitHub CLI",
            "install_url": "https://cli.github.com/",
            "required": "false",
        },
        "glab": {
            "available": "false",
            "version": "",
            "description": "GitLab CLI",
            "install_url": "https://gitlab.com/gitlab-org/cli",
            "required": "false",
        },
        "pytest": {
            "available": "true",
            "version": "pytest 7.4.3",
            "description": "Python testing framework",
            "install_url": "https://docs.pytest.org/",
            "required": "false",
        },
    }


@pytest.fixture
def required_tool_missing():
    """Mock status where a required tool is missing."""
    return {
        "git": {
            "available": "false",
            "version": "",
            "description": "Git version control",
            "install_url": "https://git-scm.com/downloads",
            "required": "true",
        },
        "claude": {
            "available": "true",
            "version": "claude 1.2.3",
            "description": "Claude Code CLI",
            "install_url": "https://docs.claude.com/en/docs/claude-code/installation",
            "required": "true",
        },
        "gh": {
            "available": "true",
            "version": "gh 2.40.1",
            "description": "GitHub CLI",
            "install_url": "https://cli.github.com/",
            "required": "false",
        },
        "glab": {
            "available": "true",
            "version": "glab 1.35.0",
            "description": "GitLab CLI",
            "install_url": "https://gitlab.com/gitlab-org/cli",
            "required": "false",
        },
        "pytest": {
            "available": "true",
            "version": "pytest 7.4.3",
            "description": "Python testing framework",
            "install_url": "https://docs.pytest.org/",
            "required": "false",
        },
    }


def test_check_dependencies_all_available_text_output(all_tools_available, capsys):
    """Test check command with all tools available (text output)."""
    with patch("devflow.cli.commands.check_command.get_all_tools_status", return_value=all_tools_available):
        exit_code = check_dependencies(output_json=False)

        # Should return 0 (success)
        assert exit_code == 0

        # Check console output
        captured = capsys.readouterr()
        assert "Checking dependencies" in captured.out
        assert "Required Dependencies:" in captured.out
        assert "Optional Dependencies:" in captured.out
        assert "All required dependencies available" in captured.out
        assert "git" in captured.out
        assert "claude" in captured.out


def test_check_dependencies_some_missing_text_output(some_tools_missing, capsys):
    """Test check command with some optional tools missing (text output)."""
    with patch("devflow.cli.commands.check_command.get_all_tools_status", return_value=some_tools_missing):
        exit_code = check_dependencies(output_json=False)

        # Should return 0 (all required tools are available)
        assert exit_code == 0

        # Check console output
        captured = capsys.readouterr()
        assert "All required dependencies available" in captured.out
        assert "Some optional features unavailable" in captured.out
        assert "gh" in captured.out
        assert "glab" in captured.out


def test_check_dependencies_required_missing_text_output(required_tool_missing, capsys):
    """Test check command with required tool missing (text output)."""
    with patch("devflow.cli.commands.check_command.get_all_tools_status", return_value=required_tool_missing):
        exit_code = check_dependencies(output_json=False)

        # Should return 1 (failure)
        assert exit_code == 1

        # Check console output
        captured = capsys.readouterr()
        assert "Missing required dependencies" in captured.out
        assert "git" in captured.out


def test_check_dependencies_json_output_all_available(all_tools_available, capsys):
    """Test check command with JSON output when all tools are available."""
    with patch("devflow.cli.commands.check_command.get_all_tools_status", return_value=all_tools_available):
        exit_code = check_dependencies(output_json=True)

        # Should return 0 (success)
        assert exit_code == 0

        # Check JSON output
        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is True
        assert "data" in output
        assert "tools" in output["data"]
        assert output["data"]["all_required_available"] is True

        # Verify tools data
        tools = output["data"]["tools"]
        assert "git" in tools
        assert "claude" in tools
        assert tools["git"]["available"] == "true"
        assert tools["claude"]["available"] == "true"


def test_check_dependencies_json_output_some_missing(some_tools_missing, capsys):
    """Test check command with JSON output when some optional tools are missing."""
    with patch("devflow.cli.commands.check_command.get_all_tools_status", return_value=some_tools_missing):
        exit_code = check_dependencies(output_json=True)

        # Should return 0 (all required tools available)
        assert exit_code == 0

        # Check JSON output
        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is True
        assert output["data"]["all_required_available"] is True

        # Verify optional tools are marked as unavailable
        tools = output["data"]["tools"]
        assert tools["gh"]["available"] == "false"
        assert tools["glab"]["available"] == "false"


def test_check_dependencies_json_output_required_missing(required_tool_missing, capsys):
    """Test check command with JSON output when required tool is missing."""
    with patch("devflow.cli.commands.check_command.get_all_tools_status", return_value=required_tool_missing):
        exit_code = check_dependencies(output_json=True)

        # Should return 1 (failure)
        assert exit_code == 1

        # Check JSON output
        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is True  # API call succeeded
        assert output["data"]["all_required_available"] is False  # But required tools missing

        # Verify git is marked as unavailable
        tools = output["data"]["tools"]
        assert tools["git"]["available"] == "false"


def test_display_tools_table(all_tools_available, capsys):
    """Test _display_tools_table function."""
    required_tools = {
        tool: info for tool, info in all_tools_available.items()
        if info["required"] == "true"
    }

    _display_tools_table(required_tools)

    captured = capsys.readouterr()
    # Check that table contains tool names
    assert "git" in captured.out
    assert "claude" in captured.out

    # Check that version info is displayed
    assert "2.39.0" in captured.out or "git version" in captured.out


def test_display_tools_table_with_missing_tool(some_tools_missing, capsys):
    """Test _display_tools_table with missing tools shows install URLs."""
    optional_tools = {
        tool: info for tool, info in some_tools_missing.items()
        if info["required"] == "false"
    }

    _display_tools_table(optional_tools)

    captured = capsys.readouterr()
    # Check that install URLs are shown for missing tools
    assert "cli.github.com" in captured.out  # gh install URL
    # Note: URL may be truncated in table, so check for partial match
    assert "gitlab.com/gitlab-or" in captured.out or "gitlab.com/gitlab-org/cli" in captured.out  # glab install URL


def test_check_dependencies_separates_required_and_optional(all_tools_available, capsys):
    """Test that check command properly separates required and optional tools."""
    with patch("devflow.cli.commands.check_command.get_all_tools_status", return_value=all_tools_available):
        check_dependencies(output_json=False)

        captured = capsys.readouterr()

        # Should have two separate sections
        assert "Required Dependencies:" in captured.out
        assert "Optional Dependencies:" in captured.out

        # Git and claude should be in required section
        # This is hard to test precisely without parsing the table,
        # but we can at least verify both sections exist
        output_parts = captured.out.split("Optional Dependencies:")
        assert len(output_parts) == 2


def test_check_dependencies_exit_code_consistency():
    """Test that exit code matches all_required_available status."""
    # Case 1: All required available - exit code 0
    all_available = {
        "git": {"available": "true", "version": "2.0", "description": "", "install_url": "", "required": "true"},
        "claude": {"available": "true", "version": "1.0", "description": "", "install_url": "", "required": "true"},
        "gh": {"available": "false", "version": "", "description": "", "install_url": "", "required": "false"},
    }

    with patch("devflow.cli.commands.check_command.get_all_tools_status", return_value=all_available):
        exit_code = check_dependencies(output_json=True)
        assert exit_code == 0

    # Case 2: Required tool missing - exit code 1
    required_missing = {
        "git": {"available": "false", "version": "", "description": "", "install_url": "", "required": "true"},
        "claude": {"available": "true", "version": "1.0", "description": "", "install_url": "", "required": "true"},
        "gh": {"available": "true", "version": "2.0", "description": "", "install_url": "", "required": "false"},
    }

    with patch("devflow.cli.commands.check_command.get_all_tools_status", return_value=required_missing):
        exit_code = check_dependencies(output_json=True)
        assert exit_code == 1
