"""Tests for dependency checking utilities."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from devflow.exceptions import ToolNotFoundError
from devflow.utils.dependencies import (
    check_tool_available,
    get_tool_version,
    require_tool,
    get_all_tools_status,
    TOOL_INFO,
)


def test_check_tool_available_git_exists():
    """Test that git is detected as available (assuming it's installed in test environment)."""
    # Git should be available in CI/test environments
    with patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/git"
        assert check_tool_available("git") is True
        mock_which.assert_called_once_with("git")


def test_check_tool_available_missing_tool():
    """Test that a non-existent tool is detected as unavailable."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        assert check_tool_available("nonexistent-tool-xyz") is False
        mock_which.assert_called_once_with("nonexistent-tool-xyz")


def test_get_tool_version_success():
    """Test getting version for a tool that supports --version."""
    with patch("shutil.which") as mock_which, \
         patch("subprocess.run") as mock_run:
        mock_which.return_value = "/usr/bin/git"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="git version 2.39.0\n"
        )

        version = get_tool_version("git")
        assert version == "git version 2.39.0"
        mock_which.assert_called_once_with("git")


def test_get_tool_version_missing_tool():
    """Test getting version for a tool that doesn't exist."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        assert get_tool_version("nonexistent-tool") is None
        mock_which.assert_called_once_with("nonexistent-tool")


def test_get_tool_version_no_version_flag():
    """Test getting version when tool doesn't support version flags."""
    with patch("shutil.which") as mock_which, \
         patch("subprocess.run") as mock_run:
        mock_which.return_value = "/usr/bin/tool"
        # Tool returns error for all version flags
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        version = get_tool_version("tool")
        # Should return "installed" when tool exists but version is unknown
        assert version == "installed"


def test_require_tool_success():
    """Test require_tool when tool is available."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/git"
        # Should not raise exception
        require_tool("git", "test operation")
        mock_which.assert_called_once_with("git")


def test_require_tool_raises_exception():
    """Test require_tool raises ToolNotFoundError when tool is missing."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None

        with pytest.raises(ToolNotFoundError) as exc_info:
            require_tool("git", "test operation")

        error = exc_info.value
        assert error.tool == "git"
        assert error.operation == "test operation"
        assert "git-scm.com" in error.install_url
        assert "git command not found" in str(error)
        assert "Required for: test operation" in str(error)
        assert "Install from:" in str(error)


def test_require_tool_with_unknown_tool():
    """Test require_tool with a tool not in TOOL_INFO."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None

        with pytest.raises(ToolNotFoundError) as exc_info:
            require_tool("unknown-tool", "some operation")

        error = exc_info.value
        assert error.tool == "unknown-tool"
        assert error.operation == "some operation"
        assert error.install_url == ""  # No install URL for unknown tools


def test_get_all_tools_status_all_available():
    """Test get_all_tools_status when all tools are available."""
    with patch("shutil.which") as mock_which, \
         patch("subprocess.run") as mock_run:
        # All tools are available
        mock_which.return_value = "/usr/bin/tool"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="version 1.0.0\n"
        )

        status = get_all_tools_status()

        # Check that all tools from TOOL_INFO are present
        assert set(status.keys()) == set(TOOL_INFO.keys())

        # Check that all are marked as available
        for tool, info in status.items():
            assert info["available"] == "true"
            assert info["version"] != ""
            assert info["description"] == TOOL_INFO[tool]["description"]
            assert info["required"] == TOOL_INFO[tool]["required"]


def test_get_all_tools_status_some_missing():
    """Test get_all_tools_status when some tools are missing."""
    def which_side_effect(tool):
        # Only git and claude are available
        if tool in ["git", "claude"]:
            return f"/usr/bin/{tool}"
        return None

    with patch("shutil.which", side_effect=which_side_effect), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="version 1.0.0\n"
        )

        status = get_all_tools_status()

        # Check git and claude are available
        assert status["git"]["available"] == "true"
        assert status["claude"]["available"] == "true"

        # Check gh and glab are not available
        assert status["gh"]["available"] == "false"
        assert status["glab"]["available"] == "false"
        assert status["pytest"]["available"] == "false"

        # Check that unavailable tools have empty version
        assert status["gh"]["version"] == ""
        assert status["glab"]["version"] == ""


def test_tool_info_contains_required_fields():
    """Test that TOOL_INFO has all required fields for each tool."""
    required_fields = ["description", "install_url", "required"]

    for tool, info in TOOL_INFO.items():
        for field in required_fields:
            assert field in info, f"Tool {tool} missing field {field}"

        # Check that required field is either "true" or "false"
        assert info["required"] in ["true", "false"], \
            f"Tool {tool} has invalid required value: {info['required']}"


def test_tool_info_required_tools():
    """Test that git and claude are marked as required."""
    assert TOOL_INFO["git"]["required"] == "true"
    assert TOOL_INFO["claude"]["required"] == "true"


def test_tool_info_optional_tools():
    """Test that gh, glab, and pytest are marked as optional."""
    assert TOOL_INFO["gh"]["required"] == "false"
    assert TOOL_INFO["glab"]["required"] == "false"
    assert TOOL_INFO["pytest"]["required"] == "false"


def test_tool_info_install_urls():
    """Test that all tools have valid install URLs."""
    for tool, info in TOOL_INFO.items():
        install_url = info.get("install_url", "")
        assert install_url != "", f"Tool {tool} has empty install URL"
        assert install_url.startswith("http"), \
            f"Tool {tool} has invalid install URL: {install_url}"


def test_get_tool_version_timeout():
    """Test get_tool_version handles timeout gracefully."""
    import subprocess

    with patch("shutil.which") as mock_which, \
         patch("subprocess.run") as mock_run:
        mock_which.return_value = "/usr/bin/git"
        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

        # Should return "installed" when timeout occurs
        version = get_tool_version("git")
        assert version == "installed"


def test_get_tool_version_tries_multiple_flags():
    """Test that get_tool_version tries multiple version flags."""
    with patch("shutil.which") as mock_which, \
         patch("subprocess.run") as mock_run:
        mock_which.return_value = "/usr/bin/tool"

        # First call fails, second call succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=""),  # --version fails
            MagicMock(returncode=0, stdout="version 1.0\n"),  # -v succeeds
        ]

        version = get_tool_version("tool")
        assert version == "version 1.0"

        # Verify it tried multiple flags
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0] == ["tool", "--version"]
        assert mock_run.call_args_list[1][0][0] == ["tool", "-v"]
