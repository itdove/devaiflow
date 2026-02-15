"""Tests for template CLI commands."""

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.templates.manager import TemplateManager


def test_template_list_empty(temp_daf_home):
    """Test listing templates when none exist."""
    runner = CliRunner()
    result = runner.invoke(cli, ["template", "list"])

    assert result.exit_code == 0
    assert "No templates found" in result.output
    assert "daf template save" in result.output


def test_template_save_and_list(temp_daf_home):
    """Test saving a template and listing it."""
    # Create a session first
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test session for template",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
    )

    # Save template
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["template", "save", "test-session", "my-template", "--description", "Test template"],
    )

    assert result.exit_code == 0
    assert "Template 'my-template' saved successfully" in result.output
    assert "daf new --template my-template" in result.output

    # List templates
    result = runner.invoke(cli, ["template", "list"])

    assert result.exit_code == 0
    assert "my-template" in result.output
    assert "Test template" in result.output


def test_template_save_prompts_for_description(temp_daf_home):
    """Test that save prompts for description if not provided."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="My goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
    )

    # Save template without description - should use goal as default
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["template", "save", "test-session", "my-template"],
        input="\n",  # Accept default description
    )

    assert result.exit_code == 0
    assert "Template 'my-template' saved successfully" in result.output


def test_template_save_with_multiple_sessions(temp_daf_home):
    """Test that attempting to create duplicate session names raises ValueError."""
    import pytest

    # Create first session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="multi-session",
        goal="First session",
        working_directory="dir1",
        project_path="/path/to/project1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    with pytest.raises(ValueError, match="Session 'multi-session' already exists"):
        session_manager.create_session(
            name="multi-session",
            goal="Second session",
            working_directory="dir2",
            project_path="/path/to/project2",
            ai_agent_session_id="uuid-2",
        )


def test_template_save_nonexistent_session(temp_daf_home):
    """Test saving template for session that doesn't exist."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["template", "save", "nonexistent", "my-template"],
    )

    assert result.exit_code == 1
    assert "Session 'nonexistent' not found" in result.output


def test_template_show(temp_daf_home):
    """Test showing template details."""
    # Create a template
    template_manager = TemplateManager()
    from devflow.templates.models import SessionTemplate
    from datetime import datetime

    template = SessionTemplate(
        name="show-me",
        description="Template to show",
        working_directory="show-dir",
        branch="feature/show-branch",
        tags=["tag1", "tag2"],
        issue_key="PROJ-12345",
        created_at=datetime(2025, 1, 1, 12, 0, 0),
    )
    template_manager.save_template(template)

    # Show template
    runner = CliRunner()
    result = runner.invoke(cli, ["template", "show", "show-me"])

    assert result.exit_code == 0
    assert "show-me" in result.output
    assert "Template to show" in result.output
    assert "show-dir" in result.output
    assert "feature/show-branch" in result.output
    assert "tag1, tag2" in result.output
    assert "PROJ-12345" in result.output


def test_template_show_nonexistent(temp_daf_home):
    """Test showing template that doesn't exist."""
    runner = CliRunner()
    result = runner.invoke(cli, ["template", "show", "nonexistent"])

    assert result.exit_code == 0
    assert "Template 'nonexistent' not found" in result.output
    assert "daf template list" in result.output


def test_template_delete_with_confirmation(temp_daf_home):
    """Test deleting template with confirmation prompt."""
    # Create a template
    template_manager = TemplateManager()
    from devflow.templates.models import SessionTemplate

    template = SessionTemplate(
        name="delete-me",
        description="To be deleted",
        working_directory="delete-dir",
    )
    template_manager.save_template(template)

    # Delete with confirmation
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["template", "delete", "delete-me"],
        input="y\n",  # Confirm deletion
    )

    assert result.exit_code == 0
    assert "Template 'delete-me' deleted" in result.output

    # Verify deletion with fresh manager instance
    fresh_manager = TemplateManager()
    assert fresh_manager.get_template("delete-me") is None


def test_template_delete_with_force(temp_daf_home):
    """Test deleting template with --force flag."""
    # Create a template
    template_manager = TemplateManager()
    from devflow.templates.models import SessionTemplate

    template = SessionTemplate(
        name="force-delete",
        description="Force delete",
        working_directory="delete-dir",
    )
    template_manager.save_template(template)

    # Delete with --force (no confirmation)
    runner = CliRunner()
    result = runner.invoke(cli, ["template", "delete", "force-delete", "--force"])

    assert result.exit_code == 0
    assert "Template 'force-delete' deleted" in result.output

    # Verify deletion with fresh manager instance
    fresh_manager = TemplateManager()
    assert fresh_manager.get_template("force-delete") is None


def test_template_delete_cancelled(temp_daf_home):
    """Test cancelling template deletion."""
    # Create a template
    template_manager = TemplateManager()
    from devflow.templates.models import SessionTemplate

    template = SessionTemplate(
        name="keep-me",
        description="Keep this",
        working_directory="keep-dir",
    )
    template_manager.save_template(template)

    # Delete but cancel
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["template", "delete", "keep-me"],
        input="n\n",  # Cancel deletion
    )

    assert result.exit_code == 0
    assert "Cancelled" in result.output

    # Verify template still exists
    assert template_manager.get_template("keep-me") is not None


def test_template_delete_nonexistent(temp_daf_home):
    """Test deleting template that doesn't exist."""
    runner = CliRunner()
    result = runner.invoke(cli, ["template", "delete", "nonexistent"])

    assert result.exit_code == 1
    assert "Template 'nonexistent' not found" in result.output


@pytest.mark.skip(reason="Complex integration test with git operations - needs more mocking")
def test_new_session_with_template(temp_daf_home, monkeypatch):
    """Test creating a new session from a template."""
    # Create a template
    template_manager = TemplateManager()
    from devflow.templates.models import SessionTemplate

    template = SessionTemplate(
        name="backend-template",
        description="Backend template",
        working_directory="backend-service",
        branch="feature/template-branch",
        issue_key="PROJ-99999",
    )
    template_manager.save_template(template)

    # Mock subprocess.run to avoid actually launching Claude
    def mock_run(*args, **kwargs):
        from subprocess import CompletedProcess
        return CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("subprocess.run", mock_run)

    # Create session with template - use Click testing which handles prompts better
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "new",
            "--name", "test-feature",
            "--goal", "Test using template",
            "--template", "backend-template",
            "--path", str(temp_daf_home / "test-project"),  # Use temp path that exists
        ],
        input="y\nn\n",  # Accept current dir, don't launch Claude
    )

    # Verify template was used
    assert result.exit_code == 0
    assert "Using template:" in result.output or "backend-template" in result.output


def test_new_session_with_nonexistent_template(temp_daf_home):
    """Test creating session with template that doesn't exist."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "new",
            "--name", "test-feature",
            "--goal", "Test",
            "--template", "nonexistent",
        ],
    )

    assert result.exit_code != 0
    assert "Template 'nonexistent' not found" in result.output
    assert "daf template list" in result.output


def test_template_save_with_duplicate_name(temp_daf_home):
    """Test saving template with duplicate name triggers ValueError."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test session",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
    )

    # Create first template
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["template", "save", "test-session", "duplicate-name", "--description", "First"],
    )

    assert result.exit_code == 0
    assert "Template 'duplicate-name' saved successfully" in result.output

    # Try to create duplicate template
    result = runner.invoke(
        cli,
        ["template", "save", "test-session", "duplicate-name", "--description", "Second"],
    )

    assert result.exit_code == 0
    assert "already exists" in result.output or "✗" in result.output


def test_template_delete_with_file_not_found_error(temp_daf_home, monkeypatch):
    """Test delete template when file deletion fails with FileNotFoundError."""
    from unittest.mock import Mock
    from devflow.templates.manager import TemplateManager

    # Create a template
    template_manager = TemplateManager()
    from devflow.templates.models import SessionTemplate

    template = SessionTemplate(
        name="delete-error",
        description="Test error",
        working_directory="test-dir",
    )
    template_manager.save_template(template)

    # Mock delete_template to raise FileNotFoundError
    original_delete = TemplateManager.delete_template

    def mock_delete(self, name):
        if name == "delete-error":
            raise FileNotFoundError(f"Template file not found: {name}")
        return original_delete(self, name)

    monkeypatch.setattr(TemplateManager, "delete_template", mock_delete)

    # Try to delete - should catch FileNotFoundError
    runner = CliRunner()
    result = runner.invoke(cli, ["template", "delete", "delete-error", "--force"])

    assert result.exit_code == 1
    assert "not found" in result.output
