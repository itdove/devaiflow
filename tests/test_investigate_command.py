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

    @patch("devflow.cli.commands.investigate_command.should_launch_claude_code")
    @patch("devflow.cli.commands.investigate_command.subprocess.run")
    @patch("devflow.utils.temp_directory.prompt_and_clone_to_temp")
    @patch("devflow.utils.temp_directory.should_clone_to_temp")
    @patch("devflow.cli.commands.investigate_command.console")
    def test_user_declines_temp_directory(
        self,
        mock_console,
        mock_should_clone,
        mock_prompt_clone,
        mock_subprocess,
        mock_should_launch,
        temp_daf_home,
        tmp_path
    ):
        """Test that declining temp directory doesn't cause TypeError.

        Regression test for bug where answering 'n' to temp directory prompt
        caused TypeError: argument should be a str or an os.PathLike object
        where __fspath__ returns a str, not 'NoneType'.
        """
        # Setup: Create a test directory to use as project path
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        # Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config_loader.save_config(config)

        # Setup mocks
        mock_should_clone.return_value = True  # Indicate temp clone is available
        mock_prompt_clone.return_value = None  # User declines temp directory
        mock_should_launch.return_value = False  # Don't launch Claude

        # Call the function - should NOT raise TypeError
        create_investigation_session(
            goal="Test declining temp directory investigation",
            parent=None,
            name="test-no-temp-investigate",
            path=str(project_dir),
            workspace=None,
        )

        # Verify session was created successfully
        session_manager = SessionManager(config_loader=config_loader)
        session = session_manager.get_session("test-no-temp-investigate")

        assert session is not None, "Session should be created"
        assert session.session_type == "investigation"
        assert "Test declining temp directory investigation" in session.goal
        # Session created but Claude not launched, so no conversation yet
        assert len(session.conversations) == 0


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


class TestMultiProjectInvestigation:
    """Test multi-project investigation session creation (Issue #182)."""

    def test_multi_project_investigation_session_creation(self, temp_daf_home, monkeypatch):
        """Test creating a multi-project investigation session in mock mode."""
        # Set mock mode
        monkeypatch.setenv("DAF_MOCK_MODE", "1")
        # Ensure we're not in an AI session
        monkeypatch.delenv("DEVAIFLOW_IN_SESSION", raising=False)
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

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

        # Create multiple test projects
        project1 = workspace / "backend-api"
        project1.mkdir(exist_ok=True)
        project2 = workspace / "frontend-app"
        project2.mkdir(exist_ok=True)

        # Mock the repository selection to return multiple projects
        with patch("devflow.cli.utils.prompt_repository_selection_with_multiproject") as mock_prompt, \
             patch("devflow.cli.commands.investigate_command.should_launch_claude_code") as mock_launch:
            mock_prompt.return_value = ([str(project1), str(project2)], "default")
            mock_launch.return_value = False  # Don't launch Claude in tests

            runner = CliRunner()
            result = runner.invoke(cli, [
                "investigate",
                "--goal", "Investigate authentication flow across backend and frontend",
            ])

            # Should succeed
            assert result.exit_code == 0
            assert "multi-project investigation" in result.output.lower() or "Creating multi-project" in result.output

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
            assert "authentication flow" in created_session.goal.lower()

            # Verify multi-project conversation structure
            assert created_session.active_conversation is not None
            assert created_session.active_conversation.is_multi_project is True
            assert hasattr(created_session.active_conversation, 'projects')
            assert len(created_session.active_conversation.projects) == 2
            # Verify both projects are in the conversation
            assert 'backend-api' in created_session.active_conversation.projects
            assert 'frontend-app' in created_session.active_conversation.projects

    def test_multi_project_investigation_with_parent(self, temp_daf_home, monkeypatch):
        """Test creating a multi-project investigation session with parent ticket."""
        # Set mock mode
        monkeypatch.setenv("DAF_MOCK_MODE", "1")
        # Ensure we're not in an AI session
        monkeypatch.delenv("DEVAIFLOW_IN_SESSION", raising=False)
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        # Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [
            WorkspaceDefinition(name="default", path=str(Path(temp_daf_home) / "workspace"))
        ]
        config_loader.save_config(config)

        # Create workspace and projects
        workspace = Path(temp_daf_home) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        project1 = workspace / "backend-api"
        project1.mkdir(exist_ok=True)
        project2 = workspace / "frontend-app"
        project2.mkdir(exist_ok=True)

        # Mock the repository selection to return multiple projects
        with patch("devflow.cli.utils.prompt_repository_selection_with_multiproject") as mock_prompt, \
             patch("devflow.cli.commands.investigate_command.should_launch_claude_code") as mock_launch:
            mock_prompt.return_value = ([str(project1), str(project2)], "default")
            mock_launch.return_value = False  # Don't launch Claude in tests

            runner = CliRunner()
            result = runner.invoke(cli, [
                "investigate",
                "--goal", "Investigate caching implementation",
                "--parent", "PROJ-12345",
            ])

            # Should succeed
            assert result.exit_code == 0

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
            assert created_session.session_type == "investigation"

    def test_single_project_fallback_still_works(self, temp_daf_home, monkeypatch):
        """Test that single-project investigation still works (backward compatibility)."""
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

        # Create single test project
        project1 = workspace / "backend-api"
        project1.mkdir(exist_ok=True)

        # Mock the repository selection to return single project
        with patch("devflow.cli.utils.prompt_repository_selection_with_multiproject") as mock_prompt:
            mock_prompt.return_value = ([str(project1)], "default")

            runner = CliRunner()
            result = runner.invoke(cli, [
                "investigate",
                "--goal", "Research caching options",
            ])

            # Should succeed
            assert result.exit_code == 0
            assert "Created session" in result.output
            assert "session_type: investigation" in result.output

            # Verify session was created with single-project structure
            session_manager = SessionManager(config_loader=config_loader)
            sessions = session_manager.list_sessions()
            assert len(sessions) > 0

            created_session = None
            for session in sessions:
                if session.session_type == "investigation":
                    created_session = session
                    break

            assert created_session is not None
            assert created_session.session_type == "investigation"

    def test_multi_project_investigation_prompt_includes_all_projects(self, temp_daf_home, monkeypatch):
        """Test that multi-project investigation prompt includes all selected projects."""
        from devflow.cli.commands.investigate_command import _build_multiproject_investigation_prompt

        # Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()

        # Create test project paths
        workspace = Path(temp_daf_home) / "workspace"
        project_paths = [
            str(workspace / "backend-api"),
            str(workspace / "frontend-app"),
            str(workspace / "shared-lib"),
        ]

        # Build prompt
        prompt = _build_multiproject_investigation_prompt(
            goal="Investigate API integration",
            parent=None,
            config=config,
            name="test-investigation",
            project_paths=project_paths,
            workspace=str(workspace),
        )

        # Verify prompt content
        assert "backend-api" in prompt
        assert "frontend-app" in prompt
        assert "shared-lib" in prompt
        assert "MULTI-PROJECT investigation" in prompt
        assert "3 repositories" in prompt or "3 projects" in prompt
        assert "READ-ONLY" in prompt
        assert "Do NOT modify any code or files in any project" in prompt
        assert "Investigate API integration" in prompt
