"""Extended tests for template models."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from devflow.templates.models import NameExtractionConfig, SessionTemplate, TemplateIndex


def test_add_template_duplicate_name():
    """Test that adding duplicate template raises ValueError."""
    index = TemplateIndex()

    template1 = SessionTemplate(
        name="test-template",
        working_directory="test",
        last_used=datetime.now(),
    )

    index.add_template(template1)

    # Try to add another template with same name
    template2 = SessionTemplate(
        name="test-template",
        working_directory="other",
        last_used=datetime.now(),
    )

    with pytest.raises(ValueError, match="Template 'test-template' already exists"):
        index.add_template(template2)


def test_update_template_not_found():
    """Test that updating non-existent template raises ValueError."""
    index = TemplateIndex()

    template = SessionTemplate(
        name="nonexistent",
        working_directory="test",
        last_used=datetime.now(),
    )

    with pytest.raises(ValueError, match="Template 'nonexistent' not found"):
        index.update_template(template)


def test_find_matching_template_by_working_directory():
    """Test finding template by working directory match."""
    index = TemplateIndex()

    template1 = SessionTemplate(
        name="backend-api",
        working_directory="backend-api",
        last_used=datetime.now(),
    )

    template2 = SessionTemplate(
        name="frontend",
        working_directory="frontend",
        last_used=datetime.now(),
    )

    index.add_template(template1)
    index.add_template(template2)

    # Test matching path
    current_dir = Path("/Users/test/projects/backend-api")
    result = index.find_matching_template(current_dir)

    assert result is not None
    assert result.name == "backend-api"


def test_find_matching_template_no_match():
    """Test finding template when no match exists."""
    index = TemplateIndex()

    template = SessionTemplate(
        name="backend-api",
        working_directory="backend-api",
        last_used=datetime.now(),
    )

    index.add_template(template)

    # Test non-matching path
    current_dir = Path("/Users/test/projects/other-project")
    result = index.find_matching_template(current_dir)

    assert result is None


def test_find_matching_template_returns_most_recently_used():
    """Test that when multiple templates match, most recently used is returned."""
    index = TemplateIndex()

    now = datetime.now()

    # Older template
    template1 = SessionTemplate(
        name="old-template",
        working_directory="service",
        last_used=now - timedelta(days=10),
    )

    # Newer template
    template2 = SessionTemplate(
        name="new-template",
        working_directory="service",
        last_used=now - timedelta(days=1),
    )

    index.add_template(template1)
    index.add_template(template2)

    # Both templates match "service" in the path
    current_dir = Path("/Users/test/projects/my-service")
    result = index.find_matching_template(current_dir)

    assert result is not None
    assert result.name == "new-template"


def test_find_matching_template_with_never_used():
    """Test finding template when some templates have never been used."""
    index = TemplateIndex()

    now = datetime.now()

    # Template that's been used
    template1 = SessionTemplate(
        name="used-template",
        working_directory="api",
        last_used=now,
    )

    # Template that's never been used (last_used is None)
    template2 = SessionTemplate(
        name="never-used",
        working_directory="api",
        last_used=None,
    )

    index.add_template(template1)
    index.add_template(template2)

    current_dir = Path("/Users/test/projects/my-api")
    result = index.find_matching_template(current_dir)

    assert result is not None
    # Should return the used template
    assert result.name == "used-template"


def test_find_matching_template_partial_match():
    """Test that template matches when working_directory is contained in path."""
    index = TemplateIndex()

    template = SessionTemplate(
        name="api",
        working_directory="api",
        last_used=datetime.now(),
    )

    index.add_template(template)

    # "api" is contained in "backend-api"
    current_dir = Path("/Users/test/backend-api")
    result = index.find_matching_template(current_dir)

    assert result is not None
    assert result.name == "api"


def test_find_matching_template_no_working_directory():
    """Test that templates without working_directory don't match."""
    index = TemplateIndex()

    template = SessionTemplate(
        name="no-dir",
        working_directory=None,
        last_used=datetime.now(),
    )

    index.add_template(template)

    current_dir = Path("/Users/test/projects/any-project")
    result = index.find_matching_template(current_dir)

    assert result is None


def test_extract_template_name_with_prefix():
    """Test extracting template name with prefix removal."""
    index = TemplateIndex()
    config = NameExtractionConfig(remove_prefixes=["workspace-", "test-"])

    project_path = Path("/Users/dvernier/development/workspace/workspace-management-service")
    result = index.extract_template_name(project_path, config)

    assert result == "management-service"


def test_extract_template_name_with_shorter_prefix():
    """Test extracting template name with shorter prefix."""
    index = TemplateIndex()
    config = NameExtractionConfig(remove_prefixes=["workspace-", "test-"])

    project_path = Path("/Users/dvernier/development/workspace/test-sops")
    result = index.extract_template_name(project_path, config)

    assert result == "sops"


def test_extract_template_name_no_prefix():
    """Test extracting template name when no prefix matches."""
    index = TemplateIndex()
    config = NameExtractionConfig(remove_prefixes=["workspace-", "test-"])

    project_path = Path("/Users/dvernier/projects/my-app")
    result = index.extract_template_name(project_path, config)

    assert result == "my-app"


def test_extract_template_name_with_suffix():
    """Test extracting template name with suffix removal."""
    index = TemplateIndex()
    config = NameExtractionConfig(
        remove_prefixes=[],
        remove_suffixes=["-service", "-api"],
    )

    project_path = Path("/Users/dvernier/projects/my-app-service")
    result = index.extract_template_name(project_path, config)

    assert result == "my-app"


def test_extract_template_name_with_prefix_and_suffix():
    """Test extracting template name with both prefix and suffix removal."""
    index = TemplateIndex()
    config = NameExtractionConfig(
        remove_prefixes=["workspace-"],
        remove_suffixes=["-service"],
    )

    project_path = Path("/Users/dvernier/development/workspace/workspace-management-service")
    result = index.extract_template_name(project_path, config)

    assert result == "management"


def test_extract_template_name_prefix_priority():
    """Test that only the first matching prefix is removed."""
    index = TemplateIndex()
    config = NameExtractionConfig(
        remove_prefixes=["workspace-", "test-"],
    )

    # Should match "workspace-" first and stop
    project_path = Path("/Users/dvernier/development/workspace-test-something")
    result = index.extract_template_name(project_path, config)

    assert result == "test-something"


def test_extract_template_name_suffix_priority():
    """Test that only the first matching suffix is removed."""
    index = TemplateIndex()
    config = NameExtractionConfig(
        remove_prefixes=[],
        remove_suffixes=["-service", "-api"],
    )

    # Should match "-service" first and stop
    project_path = Path("/Users/dvernier/projects/my-app-service-api")
    result = index.extract_template_name(project_path, config)

    assert result == "my-app-service"


def test_extract_template_name_empty_config():
    """Test extracting template name with empty config (no transformations)."""
    index = TemplateIndex()
    config = NameExtractionConfig(
        remove_prefixes=[],
        remove_suffixes=[],
    )

    project_path = Path("/Users/dvernier/projects/backend-api")
    result = index.extract_template_name(project_path, config)

    assert result == "backend-api"
