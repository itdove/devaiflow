"""Tests for --json flag across all commands."""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.config.models import Session, WorkSession
from devflow.session.manager import SessionManager


@pytest.fixture
def temp_daf_home(tmp_path, monkeypatch):
    """Set up temporary sessions directory."""
    cs_home = tmp_path / ".daf-sessions"
    cs_home.mkdir()
    monkeypatch.setenv("DEVAIFLOW_HOME", str(cs_home))
    return cs_home


@pytest.fixture
def sample_session(temp_daf_home):
    """Create a sample session for testing."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a test session
    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/tmp/test",
        branch="main",
        issue_key="PROJ-12345",
    )

    # Add some work time
    session.work_sessions.append(
        WorkSession(start=datetime.now(), end=datetime.now())
    )
    session_manager.update_session(session)

    return session


class TestJSONOutputList:
    """Tests for 'daf list --json' command."""

    def test_list_json_empty(self, temp_daf_home):
        """Test list --json with no sessions (--json after command)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Parse only the JSON part (before any warnings)
        output_lines = result.output.strip().split('\n')
        json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
        output = json.loads(json_part)
        assert output["success"] is True
        assert output["data"]["sessions"] == []
        assert output["data"]["total_count"] == 0
        assert "filters_applied" in output["metadata"]

    def test_list_json_with_sessions(self, sample_session):
        """Test list --json with sessions (--json after command)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

        assert result.exit_code == 0
        # Parse only the JSON part (before any warnings)
        output_lines = result.output.strip().split('\n')
        json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
        output = json.loads(json_part)
        assert output["success"] is True
        assert len(output["data"]["sessions"]) == 1
        assert output["data"]["total_count"] == 1
        assert output["data"]["sessions"][0]["name"] == "test-session"
        assert output["data"]["sessions"][0]["issue_key"] == "PROJ-12345"

    def test_list_json_with_pagination(self, sample_session):
        """Test list --json with pagination (--json at end)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--limit", "10", "--page", "1", "--json"], catch_exceptions=False)

        assert result.exit_code == 0
        # Parse only the JSON part (before any warnings)
        output_lines = result.output.strip().split('\n')
        json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
        output = json.loads(json_part)
        assert output["success"] is True
        assert "pagination" in output["metadata"]
        assert output["metadata"]["pagination"]["page"] == 1
        assert output["metadata"]["pagination"]["limit"] == 10
        assert output["metadata"]["pagination"]["total_pages"] == 1

    def test_list_json_with_filters(self, sample_session):
        """Test list --json with filters applied (--json at end)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--status", "created", "--json"], catch_exceptions=False)

        assert result.exit_code == 0
        # Parse only the JSON part (before any warnings)
        output_lines = result.output.strip().split('\n')
        json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
        output = json.loads(json_part)
        assert output["success"] is True
        assert output["metadata"]["filters_applied"]["status"] == "created"


class TestJSONOutputStatus:
    """Tests for 'daf status --json' command."""

    def test_status_json_empty(self, temp_daf_home):
        """Test status --json with no sessions (--json at end)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--json"], catch_exceptions=False)

        assert result.exit_code == 0
        # Parse only the JSON part (before any warnings)
        output_lines = result.output.strip().split('\n')
        json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
        output = json.loads(json_part)
        assert output["success"] is True
        assert output["data"]["sessions"] == []
        assert output["data"]["summary"]["total_sessions"] == 0

    def test_status_json_with_sessions(self, sample_session):
        """Test status --json with sessions (--json at end)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--json"], catch_exceptions=False)

        assert result.exit_code == 0
        # Parse only the JSON part (before any warnings)
        output_lines = result.output.strip().split('\n')
        json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
        output = json.loads(json_part)
        assert output["success"] is True
        assert output["data"]["summary"]["total_sessions"] == 1
        assert "sprints" in output["data"]
        assert "no_sprint_sessions" in output["data"]


class TestJSONOutputValidation:
    """Tests for JSON output validation."""

    def test_json_is_valid(self, sample_session):
        """Test that JSON output is valid and parseable."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

        assert result.exit_code == 0
        # Parse only the JSON part (before any warnings)
        output_lines = result.output.strip().split('\n')
        json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
        # Should not raise JSONDecodeError
        output = json.loads(json_part)
        assert isinstance(output, dict)

    def test_json_has_required_keys(self, sample_session):
        """Test that JSON output has required top-level keys."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

        # Parse only the JSON part (before any warnings)
        output_lines = result.output.strip().split('\n')
        json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
        output = json.loads(json_part)
        assert "success" in output
        assert "data" in output
        assert "metadata" in output

    def test_json_datetime_serialization(self, sample_session):
        """Test that datetime fields are properly serialized."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

        # Parse only the JSON part (before any warnings)
        output_lines = result.output.strip().split('\n')
        json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
        output = json.loads(json_part)
        session = output["data"]["sessions"][0]

        # Check that datetime fields are ISO 8601 strings
        assert "created" in session
        assert isinstance(session["created"], str)
        # Should be parseable as ISO 8601
        datetime.fromisoformat(session["created"])
