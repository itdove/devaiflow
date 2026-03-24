"""Tests for _get_parent_field_id method and parent field fallback behavior."""

import json
import pytest
from unittest.mock import Mock
from pathlib import Path

from devflow.jira.client import JiraClient
from devflow.jira.field_mapper import JiraFieldMapper


@pytest.fixture
def mock_field_mapper():
    """Create a mock field mapper with epic_link mapping."""
    mapper = Mock(spec=JiraFieldMapper)
    # Simulate looking up epic_link custom field ID
    mapper.get_field_id.return_value = "customfield_12311140"
    # Mock field_mappings as empty dict to avoid iteration errors
    mapper.field_mappings = {}
    return mapper


@pytest.fixture
def config_with_parent_mapping(temp_daf_home):
    """Create config with parent_field_mapping configured."""
    from devflow.config.loader import ConfigLoader

    loader = ConfigLoader()
    backends_dir = loader.config_dir / "backends"
    backends_dir.mkdir(exist_ok=True)

    # Backend config
    backend_data = {
        "url": "https://test-jira.example.com",
        "field_mappings": None,
    }
    with open(backends_dir / "jira.json", "w") as f:
        json.dump(backend_data, f, indent=2)

    # Organization config with parent_field_mapping
    org_data = {
        "jira_project": "TEST",
        "parent_field_mapping": {
            "story": "epic_link",
            "task": "epic_link",
            "bug": "epic_link",
            "sub-task": "parent",
            "epic": "parent"
        }
    }
    with open(loader.config_dir / "organization.json", "w") as f:
        json.dump(org_data, f, indent=2)

    # User config (minimal)
    user_data = {"repos": {"workspaces": []}}
    with open(loader.config_dir / "config.json", "w") as f:
        json.dump(user_data, f, indent=2)

    return loader


@pytest.fixture
def config_without_parent_mapping(temp_daf_home):
    """Create config WITHOUT parent_field_mapping configured."""
    from devflow.config.loader import ConfigLoader

    loader = ConfigLoader()
    backends_dir = loader.config_dir / "backends"
    backends_dir.mkdir(exist_ok=True)

    # Backend config (no parent_field_mapping)
    backend_data = {
        "url": "https://test-jira.example.com",
        "field_mappings": None,
    }
    with open(backends_dir / "jira.json", "w") as f:
        json.dump(backend_data, f, indent=2)

    # Organization config WITHOUT parent_field_mapping
    org_data = {
        "jira_project": "TEST",
    }
    with open(loader.config_dir / "organization.json", "w") as f:
        json.dump(org_data, f, indent=2)

    # User config (minimal)
    user_data = {"repos": {"workspaces": []}}
    with open(loader.config_dir / "config.json", "w") as f:
        json.dump(user_data, f, indent=2)

    return loader


def test_get_parent_field_id_without_config_returns_parent(config_without_parent_mapping, mock_field_mapper):
    """Test that _get_parent_field_id returns 'parent' when parent_field_mapping is not configured."""
    client = JiraClient()

    # Test all common issue types
    assert client._get_parent_field_id("story", mock_field_mapper) == "parent"
    assert client._get_parent_field_id("task", mock_field_mapper) == "parent"
    assert client._get_parent_field_id("bug", mock_field_mapper) == "parent"
    assert client._get_parent_field_id("epic", mock_field_mapper) == "parent"
    assert client._get_parent_field_id("sub-task", mock_field_mapper) == "parent"


def test_get_parent_field_id_with_config_uses_epic_link(config_with_parent_mapping, mock_field_mapper):
    """Test that _get_parent_field_id returns custom field ID when parent_field_mapping is configured with epic_link."""
    client = JiraClient()

    # Test issue types mapped to epic_link (should return custom field ID)
    assert client._get_parent_field_id("story", mock_field_mapper) == "customfield_12311140"
    assert client._get_parent_field_id("task", mock_field_mapper) == "customfield_12311140"
    assert client._get_parent_field_id("bug", mock_field_mapper) == "customfield_12311140"

    # Verify field_mapper.get_field_id was called with "epic_link"
    mock_field_mapper.get_field_id.assert_called_with("epic_link")


def test_get_parent_field_id_with_config_uses_parent_for_subtask(config_with_parent_mapping, mock_field_mapper):
    """Test that _get_parent_field_id returns 'parent' for sub-tasks when explicitly mapped."""
    client = JiraClient()

    # Sub-tasks should use standard parent field
    assert client._get_parent_field_id("sub-task", mock_field_mapper) == "parent"
    assert client._get_parent_field_id("epic", mock_field_mapper) == "parent"

    # Field mapper should NOT be called for "parent" logical field
    # Reset the mock to check subsequent calls don't happen for "parent"
    mock_field_mapper.get_field_id.reset_mock()
    client._get_parent_field_id("sub-task", mock_field_mapper)
    mock_field_mapper.get_field_id.assert_not_called()


def test_get_parent_field_id_issue_type_not_in_mapping_returns_parent(config_with_parent_mapping, mock_field_mapper):
    """Test that _get_parent_field_id returns 'parent' for unmapped issue types."""
    client = JiraClient()

    # Test issue types not in the mapping
    assert client._get_parent_field_id("spike", mock_field_mapper) == "parent"
    assert client._get_parent_field_id("custom-type", mock_field_mapper) == "parent"
    assert client._get_parent_field_id("unknown", mock_field_mapper) == "parent"


def test_get_parent_field_id_exception_returns_parent(config_with_parent_mapping, mock_field_mapper):
    """Test that _get_parent_field_id returns 'parent' on any exception."""
    client = JiraClient()

    # Make field_mapper.get_field_id raise an exception
    mock_field_mapper.get_field_id.side_effect = Exception("Field mapper error")

    # Should fall back to "parent" instead of propagating exception
    assert client._get_parent_field_id("story", mock_field_mapper) == "parent"


def test_create_issue_with_parent_without_config(config_without_parent_mapping, mock_field_mapper, monkeypatch):
    """Test that create_issue adds parent link using 'parent' field when config is not set."""
    client = JiraClient()

    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "POST" and "/rest/api/2/issue" in endpoint:
            # Verify parent link is in payload using standard "parent" field with correct object format
            payload = kwargs.get("json", {})
            assert "parent" in payload["fields"], "Parent field should be in payload"
            assert payload["fields"]["parent"] == {"key": "PROJ-10000"}

            response.status_code = 201
            response.json.return_value = {"key": "PROJ-12345"}
        return response

    monkeypatch.setattr(client, "_api_request", mock_api_request)

    issue_key = client.create_issue(
        issue_type="Story",
        summary="Test story with parent",
        description="Story description",
        priority="Medium",
        project_key="PROJ",
        field_mapper=mock_field_mapper,
        parent="PROJ-10000",
    )

    assert issue_key == "PROJ-12345"


def test_create_issue_with_parent_with_epic_link_config(config_with_parent_mapping, mock_field_mapper, monkeypatch):
    """Test that create_issue adds parent link using epic_link custom field when configured."""
    client = JiraClient()

    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "POST" and "/rest/api/2/issue" in endpoint:
            # Verify parent link uses custom field ID from epic_link mapping with correct object format
            payload = kwargs.get("json", {})
            assert "customfield_12311140" in payload["fields"], "Epic link custom field should be in payload"
            assert payload["fields"]["customfield_12311140"] == {"key": "PROJ-10000"}

            response.status_code = 201
            response.json.return_value = {"key": "PROJ-12346"}
        return response

    monkeypatch.setattr(client, "_api_request", mock_api_request)

    issue_key = client.create_issue(
        issue_type="Story",
        summary="Test story with parent (epic_link)",
        description="Story description",
        priority="Medium",
        project_key="PROJ",
        field_mapper=mock_field_mapper,
        parent="PROJ-10000",
    )

    assert issue_key == "PROJ-12346"


def test_backward_compatibility_existing_configs_still_work(config_with_parent_mapping, mock_field_mapper):
    """Test that existing configurations with parent_field_mapping continue to work correctly."""
    client = JiraClient()

    # Organizations with parent_field_mapping should continue using their configured mappings
    assert client._get_parent_field_id("story", mock_field_mapper) == "customfield_12311140"
    assert client._get_parent_field_id("task", mock_field_mapper) == "customfield_12311140"
    assert client._get_parent_field_id("bug", mock_field_mapper) == "customfield_12311140"
    assert client._get_parent_field_id("sub-task", mock_field_mapper) == "parent"
    assert client._get_parent_field_id("epic", mock_field_mapper) == "parent"

    # Verify the custom field lookup was called correctly
    assert mock_field_mapper.get_field_id.call_count >= 3  # At least for story, task, bug
