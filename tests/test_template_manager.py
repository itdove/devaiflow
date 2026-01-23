"""Tests for template management functionality."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from devflow.templates.manager import TemplateManager
from devflow.templates.models import SessionTemplate


def test_template_manager_initialization(temp_daf_home):
    """Test TemplateManager initialization creates necessary directories."""
    manager = TemplateManager()

    assert manager.cs_home == temp_daf_home
    assert manager.templates_dir.exists()
    assert manager.templates_file == temp_daf_home / "templates.json"


def test_save_and_get_template(temp_daf_home):
    """Test saving and retrieving a template."""
    manager = TemplateManager()

    template = SessionTemplate(
        name="backend-api",
        description="Backend API development",
        working_directory="backend-api",
        branch="feature/test-branch",
        tags=["backend", "api"],
        issue_key="PROJ-12345",
    )

    manager.save_template(template)

    # Verify template was saved
    retrieved = manager.get_template("backend-api")
    assert retrieved is not None
    assert retrieved.name == "backend-api"
    assert retrieved.description == "Backend API development"
    assert retrieved.working_directory == "backend-api"
    assert retrieved.branch == "feature/test-branch"
    assert retrieved.tags == ["backend", "api"]
    assert retrieved.issue_key == "PROJ-12345"


def test_get_nonexistent_template(temp_daf_home):
    """Test getting a template that doesn't exist."""
    manager = TemplateManager()

    result = manager.get_template("nonexistent")
    assert result is None


def test_list_templates(temp_daf_home):
    """Test listing all templates."""
    manager = TemplateManager()

    # Initially empty
    templates = manager.list_templates()
    assert len(templates) == 0

    # Add templates
    template1 = SessionTemplate(
        name="template1",
        description="First template",
        working_directory="dir1",
    )
    template2 = SessionTemplate(
        name="template2",
        description="Second template",
        working_directory="dir2",
    )

    manager.save_template(template1)
    manager.save_template(template2)

    # List should now have 2 templates
    templates = manager.list_templates()
    assert len(templates) == 2
    assert {t.name for t in templates} == {"template1", "template2"}


def test_delete_template(temp_daf_home):
    """Test deleting a template."""
    manager = TemplateManager()

    template = SessionTemplate(
        name="to-delete",
        description="Will be deleted",
        working_directory="test-dir",
    )

    manager.save_template(template)
    assert manager.get_template("to-delete") is not None

    # Delete the template
    result = manager.delete_template("to-delete")
    assert result is True
    assert manager.get_template("to-delete") is None


def test_delete_nonexistent_template(temp_daf_home):
    """Test deleting a template that doesn't exist."""
    manager = TemplateManager()

    result = manager.delete_template("nonexistent")
    assert result is False


def test_update_template(temp_daf_home):
    """Test updating an existing template."""
    manager = TemplateManager()

    # Create initial template
    template = SessionTemplate(
        name="updatable",
        description="Original description",
        working_directory="original-dir",
    )
    manager.save_template(template)

    # Update template
    updated_template = SessionTemplate(
        name="updatable",
        description="Updated description",
        working_directory="updated-dir",
        tags=["new-tag"],
    )
    manager.save_template(updated_template)

    # Verify update
    retrieved = manager.get_template("updatable")
    assert retrieved.description == "Updated description"
    assert retrieved.working_directory == "updated-dir"
    assert retrieved.tags == ["new-tag"]


def test_template_persistence(temp_daf_home):
    """Test that templates persist across TemplateManager instances."""
    # Create template with first manager instance
    manager1 = TemplateManager()
    template = SessionTemplate(
        name="persistent",
        description="Should persist",
        working_directory="test-dir",
    )
    manager1.save_template(template)

    # Create new manager instance
    manager2 = TemplateManager()
    retrieved = manager2.get_template("persistent")

    assert retrieved is not None
    assert retrieved.name == "persistent"
    assert retrieved.description == "Should persist"


def test_template_json_serialization(temp_daf_home):
    """Test that templates are correctly serialized to JSON."""
    manager = TemplateManager()

    template = SessionTemplate(
        name="test-json",
        description="Test JSON serialization",
        working_directory="test-dir",
        branch="test-branch",
        tags=["tag1", "tag2"],
        issue_key="PROJ-12345",
    )
    manager.save_template(template)

    # Read the templates.json file directly
    with open(manager.templates_file) as f:
        data = json.load(f)

    assert "templates" in data
    assert "test-json" in data["templates"]

    template_data = data["templates"]["test-json"]
    assert template_data["name"] == "test-json"
    assert template_data["description"] == "Test JSON serialization"
    assert template_data["working_directory"] == "test-dir"
    assert template_data["branch"] == "test-branch"
    assert template_data["tags"] == ["tag1", "tag2"]
    assert template_data["issue_key"] == "PROJ-12345"


def test_auto_create_template(temp_daf_home):
    """Test auto-creating a template from project path."""
    manager = TemplateManager()

    project_path = Path("/path/to/my-project")

    template = manager.auto_create_template(
        project_path=project_path,
        description="Auto-created template",
        default_jira_project="PROJ",
    )

    assert template.name == "my-project"
    assert template.description == "Auto-created template"
    assert template.working_directory == "my-project"
    assert template.issue_key == "PROJ"

    # Verify it was saved
    retrieved = manager.get_template("my-project")
    assert retrieved is not None


def test_update_usage(temp_daf_home):
    """Test updating template usage statistics."""
    manager = TemplateManager()

    template = SessionTemplate(
        name="track-usage",
        description="Track usage",
        working_directory="test-dir",
    )
    manager.save_template(template)

    # Update usage
    manager.update_usage("track-usage")

    # Verify usage was updated
    retrieved = manager.get_template("track-usage")
    assert retrieved.usage_count == 1
    assert retrieved.last_used is not None

    # Use again
    manager.update_usage("track-usage")
    retrieved = manager.get_template("track-usage")
    assert retrieved.usage_count == 2


def test_template_with_all_fields(temp_daf_home):
    """Test template with all optional fields populated."""
    manager = TemplateManager()

    template = SessionTemplate(
        name="full-template",
        description="Complete template with all fields",
        working_directory="full-dir",
        branch="feature/full-branch",
        tags=["tag1", "tag2", "tag3"],
        issue_key="PROJ-99999",
        created_at=datetime(2025, 1, 1, 12, 0, 0),
        usage_count=5,
        last_used=datetime(2025, 1, 15, 10, 30, 0),
    )

    manager.save_template(template)
    retrieved = manager.get_template("full-template")

    assert retrieved.name == "full-template"
    assert retrieved.description == "Complete template with all fields"
    assert retrieved.working_directory == "full-dir"
    assert retrieved.branch == "feature/full-branch"
    assert retrieved.tags == ["tag1", "tag2", "tag3"]
    assert retrieved.issue_key == "PROJ-99999"
    assert retrieved.usage_count == 5
    assert retrieved.last_used is not None


def test_template_with_minimal_fields(temp_daf_home):
    """Test template with only required fields."""
    manager = TemplateManager()

    template = SessionTemplate(
        name="minimal",
        working_directory="minimal-dir",
    )

    manager.save_template(template)
    retrieved = manager.get_template("minimal")

    assert retrieved.name == "minimal"
    assert retrieved.working_directory == "minimal-dir"
    assert retrieved.description is None
    assert retrieved.branch is None
    assert retrieved.tags == []
    assert retrieved.issue_key is None
