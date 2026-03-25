"""Tests for read-only commands that work inside AI agent sessions.

This test file verifies that read-only commands (summary, template list/show,
context list, workspace list) can run inside AI agent sessions without being
blocked by the @require_outside_claude decorator.

Reference: GitHub issue #244
"""

import pytest
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

from devflow.cli.commands.summary_command import show_summary
from devflow.cli.commands.template_commands import list_templates, show_template
from devflow.cli.commands.context_commands import list_context_files
from devflow.cli.commands.workspace_commands import list_workspaces
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.config.models import Session


class TestSummaryCommandInSession:
    """Tests for daf summary command inside AI agent session."""

    def test_show_summary_works_inside_ai_session(self, monkeypatch, temp_daf_home, tmp_path):
        """Test that show_summary works inside AI agent session (no @require_outside_claude)."""
        # Simulate being inside an AI agent session
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-uuid-1234")

        # Create a session
        session = Session(
            name="test-session",
            issue_key="PROJ-123",
            goal="Test summary in session",
            status="in_progress",
            created=datetime.now(),
            last_active=datetime.now()
        )
        session.add_conversation(
            working_dir="/test",
            ai_agent_session_id="test-uuid-1234",
            project_path="/test/project",
            branch="main"
        )

        mock_summary = Mock()
        mock_summary.files_created = []
        mock_summary.files_modified = []
        mock_summary.files_read = []
        mock_summary.commands_run = []
        mock_summary.last_assistant_message = None
        mock_summary.tool_call_stats = {}

        with patch('devflow.cli.commands.summary_command.ConfigLoader') as mock_loader_class:
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            mock_loader = Mock()
                            mock_loader.get_session_dir.return_value = tmp_path / "session"
                            mock_loader_class.return_value = mock_loader
                            mock_get_session.return_value = session
                            mock_gen_summary.return_value = mock_summary

                            # This should NOT raise an error (no @require_outside_claude decorator)
                            show_summary(identifier="test-session")

                            # Verify summary generation was called
                            mock_gen_summary.assert_called_once_with(session)


class TestTemplateCommandsInSession:
    """Tests for daf template list/show commands inside AI agent session."""

    def test_list_templates_works_inside_ai_session(self, monkeypatch, temp_daf_home):
        """Test that list_templates works inside AI agent session (no @require_outside_claude)."""
        # Simulate being inside an AI agent session
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-uuid-1234")

        with patch('devflow.cli.commands.template_commands.TemplateManager') as mock_tm:
            mock_tm_instance = Mock()
            mock_tm_instance.list_templates.return_value = []
            mock_tm.return_value = mock_tm_instance

            # This should NOT raise an error (no @require_outside_claude decorator)
            list_templates()

            # Verify template manager was called
            mock_tm_instance.list_templates.assert_called_once()

    def test_show_template_works_inside_ai_session(self, monkeypatch, temp_daf_home):
        """Test that show_template works inside AI agent session (no @require_outside_claude)."""
        # Simulate being inside an AI agent session
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-uuid-1234")

        mock_template = Mock()
        mock_template.name = "test-template"
        mock_template.description = "Test template"
        mock_template.issue_key = "PROJ-123"
        mock_template.working_directory = "/test"
        mock_template.branch = "main"
        mock_template.tags = ["test"]
        mock_template.created_at = datetime.now()

        with patch('devflow.cli.commands.template_commands.TemplateManager') as mock_tm:
            mock_tm_instance = Mock()
            mock_tm_instance.get_template.return_value = mock_template
            mock_tm.return_value = mock_tm_instance

            # This should NOT raise an error (no @require_outside_claude decorator)
            show_template("test-template")

            # Verify template was retrieved
            mock_tm_instance.get_template.assert_called_once_with("test-template")


class TestContextCommandsInSession:
    """Tests for daf config context list command inside AI agent session."""

    def test_list_context_files_works_inside_ai_session(self, monkeypatch, temp_daf_home):
        """Test that list_context_files works inside AI agent session (no @require_outside_claude)."""
        # Simulate being inside an AI agent session
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-uuid-1234")

        mock_config = Mock()
        mock_config.context_files.files = []

        with patch('devflow.cli.commands.context_commands.ConfigLoader') as mock_loader_class:
            mock_loader = Mock()
            mock_loader.load_config.return_value = mock_config
            mock_loader_class.return_value = mock_loader

            # This should NOT raise an error (no @require_outside_claude decorator)
            list_context_files()

            # Verify config was loaded
            mock_loader.load_config.assert_called_once()


class TestWorkspaceCommandsInSession:
    """Tests for daf workspace list command inside AI agent session."""

    def test_list_workspaces_works_inside_ai_session(self, monkeypatch, temp_daf_home):
        """Test that list_workspaces works inside AI agent session (no @require_outside_claude)."""
        # Simulate being inside an AI agent session
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-uuid-1234")

        mock_config = Mock()
        mock_config.repos.workspaces = []

        with patch('devflow.cli.commands.workspace_commands.ConfigLoader') as mock_loader_class:
            mock_loader = Mock()
            mock_loader.load_config.return_value = mock_config
            mock_loader_class.return_value = mock_loader

            # This should NOT raise an error (no @require_outside_claude decorator)
            list_workspaces()

            # Verify config was loaded
            mock_loader.load_config.assert_called_once()


class TestWriteCommandsStillBlocked:
    """Verify that write commands still have @require_outside_claude decorator."""

    def test_save_template_blocked_inside_ai_session(self, monkeypatch, temp_daf_home):
        """Test that save_template is blocked inside AI agent session (@require_outside_claude)."""
        from devflow.cli.commands.template_commands import save_template

        # Simulate being inside an AI agent session
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-uuid-1234")

        # Create a session first
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session_manager.create_session(
            name="test-session",
            goal="Test",
            working_directory="test-dir",
            project_path="/path/to/project",
            ai_agent_session_id="test-uuid-123",
        )

        # This SHOULD exit with error message (has @require_outside_claude decorator)
        with pytest.raises(SystemExit) as exc_info:
            save_template("test-session", "my-template", "Test template")

        assert exc_info.value.code == 1

    def test_delete_template_blocked_inside_ai_session(self, monkeypatch, temp_daf_home):
        """Test that delete_template is blocked inside AI agent session (@require_outside_claude)."""
        from devflow.cli.commands.template_commands import delete_template

        # Simulate being inside an AI agent session
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-uuid-1234")

        # This SHOULD exit with error message (has @require_outside_claude decorator)
        with pytest.raises(SystemExit) as exc_info:
            delete_template("test-template", force=True)

        assert exc_info.value.code == 1

    def test_add_context_file_blocked_inside_ai_session(self, monkeypatch, temp_daf_home):
        """Test that add_context_file is blocked inside AI agent session (@require_outside_claude)."""
        from devflow.cli.commands.context_commands import add_context_file

        # Simulate being inside an AI agent session
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-uuid-1234")

        # This SHOULD exit with error message (has @require_outside_claude decorator)
        with pytest.raises(SystemExit) as exc_info:
            add_context_file("ARCHITECTURE.md", "Test architecture")

        assert exc_info.value.code == 1

    def test_add_workspace_blocked_inside_ai_session(self, monkeypatch, temp_daf_home):
        """Test that add_workspace is blocked inside AI agent session (@require_outside_claude)."""
        from devflow.cli.commands.workspace_commands import add_workspace

        # Simulate being inside an AI agent session
        monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-uuid-1234")

        # This SHOULD exit with error message (has @require_outside_claude decorator)
        with pytest.raises(SystemExit) as exc_info:
            add_workspace("test-workspace", "/path/to/workspace")

        assert exc_info.value.code == 1
