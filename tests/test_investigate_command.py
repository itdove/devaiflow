"""Tests for daf investigate command."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from devflow.cli.commands.investigate_command import slugify_goal, create_investigation_session
from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


class TestSlugifyGoal:
    """Test the slugify_goal function for investigation sessions."""

    def test_simple_goal(self):
        """Test slugifying a simple goal."""
        result = slugify_goal("Research caching options")
        # Format: "research-caching-options-{6-hex-chars}"
        assert result.startswith("research-caching-options-")
        # Check that suffix is hex
        suffix = result.split("-")[-1]
        assert len(suffix) == 6
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_goal_with_special_chars(self):
        """Test slugifying goal with special characters."""
        result = slugify_goal("Investigate: timeout in API")
        assert result.startswith("investigate-timeout-in-api-")
        suffix = result.split("-")[-1]
        assert len(suffix) == 6
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_long_goal(self):
        """Test slugifying a long goal (should be truncated)."""
        long_goal = "A very long investigation goal that exceeds the maximum allowed length for session names"
        result = slugify_goal(long_goal)
        # Total length is limited to 50 chars (43 base + 1 hyphen + 6 hex)
        assert len(result) == 50
        assert not result.endswith("-")
        suffix = result.split("-")[-1]
        assert len(suffix) == 6
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_unique_names_for_identical_goals(self):
        """Test that identical goals produce unique session names."""
        goal = "Test identical goal"
        result1 = slugify_goal(goal)
        result2 = slugify_goal(goal)

        # Both should start with same base
        assert result1.startswith("test-identical-goal-")
        assert result2.startswith("test-identical-goal-")

        # But should have different suffixes (random)
        suffix1 = result1.split("-")[-1]
        suffix2 = result2.split("-")[-1]
        assert suffix1 != suffix2


class TestInvestigateCommand:
    """Test the daf investigate command."""

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        manager = MagicMock(spec=SessionManager)
        session = MagicMock()
        session.name = "test-investigation"
        session.session_id = 1
        session.session_type = "investigation"
        session.project_path = "/tmp/test-project"
        manager.create_session.return_value = session
        manager.get_session.return_value = session
        return manager

    def test_investigation_session_creation_mock_mode(self, temp_daf_home, monkeypatch):
        """Test creating an investigation session in mock mode."""
        # Set mock mode
        monkeypatch.setenv("DAF_MOCK_MODE", "1")

        # Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(Path(temp_daf_home) / "workspace"))

        ]
        config_loader.save_config(config)

        # Create workspace directory
        workspace = Path(temp_daf_home) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)

        # Create test project
        test_project = workspace / "test-project"
        test_project.mkdir(exist_ok=True)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "investigate",
            "--goal", "Research caching options",
            "--path", str(test_project),
        ])

        # Should succeed
        assert result.exit_code == 0
        assert "Created session" in result.output
        assert "session_type: investigation" in result.output
        assert "No branch will be created (analysis-only mode)" in result.output

        # Verify session was created
        session_manager = SessionManager(config_loader=config_loader)
        sessions = session_manager.list_sessions()
        assert len(sessions) > 0

        # Find the created session
        created_session = None
        for session in sessions:
            if session.session_type == "investigation":
                created_session = session
                break

        assert created_session is not None
        assert created_session.session_type == "investigation"
        assert "Research caching options" in created_session.goal

    def test_investigation_session_with_parent(self, temp_daf_home, monkeypatch):
        """Test creating an investigation session with parent ticket."""
        # Set mock mode
        monkeypatch.setenv("DAF_MOCK_MODE", "1")

        # Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(Path(temp_daf_home) / "workspace"))

        ]
        config_loader.save_config(config)

        # Create workspace and project
        workspace = Path(temp_daf_home) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        test_project = workspace / "test-project"
        test_project.mkdir(exist_ok=True)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "investigate",
            "--goal", "Research options",
            "--parent", "PROJ-12345",
            "--path", str(test_project),
        ])

        # Should succeed
        assert result.exit_code == 0
        assert "Created session" in result.output
        assert "session_type: investigation" in result.output
        assert "Tracking under: PROJ-12345" in result.output

        # Verify session was created with parent
        session_manager = SessionManager(config_loader=config_loader)
        sessions = session_manager.list_sessions()

        created_session = None
        for session in sessions:
            if session.session_type == "investigation":
                created_session = session
                break

        assert created_session is not None
        assert created_session.issue_key == "PROJ-12345"

    def test_investigation_session_custom_name(self, temp_daf_home, monkeypatch):
        """Test creating an investigation session with custom name."""
        # Set mock mode
        monkeypatch.setenv("DAF_MOCK_MODE", "1")

        # Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(Path(temp_daf_home) / "workspace"))

        ]
        config_loader.save_config(config)

        # Create workspace and project
        workspace = Path(temp_daf_home) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        test_project = workspace / "test-project"
        test_project.mkdir(exist_ok=True)

        custom_name = "my-custom-investigation"

        runner = CliRunner()
        result = runner.invoke(cli, [
            "investigate",
            "--goal", "Research options",
            "--name", custom_name,
            "--path", str(test_project),
        ])

        # Should succeed
        assert result.exit_code == 0
        assert "Created session" in result.output
        assert custom_name in result.output

        # Verify session was created with custom name
        session_manager = SessionManager(config_loader=config_loader)
        session = session_manager.get_session(custom_name)

        assert session is not None
        assert session.name == custom_name
        assert session.session_type == "investigation"

    def test_investigation_session_no_goal_interactive(self, temp_daf_home, monkeypatch):
        """Test creating investigation session without goal (interactive prompt)."""
        # Set mock mode
        monkeypatch.setenv("DAF_MOCK_MODE", "1")

        # Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(Path(temp_daf_home) / "workspace"))

        ]
        config_loader.save_config(config)

        # Create workspace and project
        workspace = Path(temp_daf_home) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        test_project = workspace / "test-project"
        test_project.mkdir(exist_ok=True)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "investigate",
            "--path", str(test_project),
        ], input="Research caching\n")

        # Should succeed
        assert result.exit_code == 0
        assert "Created session" in result.output
        assert "session_type: investigation" in result.output

    def test_investigation_session_invalid_path(self, temp_daf_home, monkeypatch):
        """Test creating investigation session with invalid path."""
        # Set mock mode
        monkeypatch.setenv("DAF_MOCK_MODE", "1")

        # Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config_loader.save_config(config)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "investigate",
            "--goal", "Research options",
            "--path", "/nonexistent/path",
        ])

        # Should fail
        assert result.exit_code != 0 or "does not exist" in result.output


class TestInvestigateCompleteIntegration:
    """Test complete_command.py integration with investigation sessions."""

    def test_complete_skips_git_for_investigation(self, temp_daf_home, monkeypatch):
        """Test that daf complete skips git operations for investigation sessions."""
        # Set mock mode
        monkeypatch.setenv("DAF_MOCK_MODE", "1")

        # Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(Path(temp_daf_home) / "workspace"))

        ]
        config_loader.save_config(config)

        # Create workspace and project
        workspace = Path(temp_daf_home) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        test_project = workspace / "test-project"
        test_project.mkdir(exist_ok=True)

        # Create investigation session
        runner = CliRunner()
        result = runner.invoke(cli, [
            "investigate",
            "--goal", "Research options",
            "--path", str(test_project),
        ])

        assert result.exit_code == 0

        # Get the created session name
        session_manager = SessionManager(config_loader=config_loader)
        sessions = session_manager.list_sessions()
        investigation_session = None
        for session in sessions:
            if session.session_type == "investigation":
                investigation_session = session
                break

        assert investigation_session is not None

        # Now complete the session
        result = runner.invoke(cli, [
            "complete",
            investigation_session.name,
        ], input="n\n")  # No to JIRA summary

        assert result.exit_code == 0
        # Should NOT prompt for git commit or PR
        assert "uncommitted changes" not in result.output.lower()
        assert "create pull request" not in result.output.lower()
        assert "create merge request" not in result.output.lower()
