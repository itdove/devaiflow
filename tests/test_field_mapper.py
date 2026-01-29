"""Tests for JIRA field mapper."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from devflow.jira.field_mapper import JiraFieldMapper


def test_discover_fields_success(monkeypatch):
    """Test successful field discovery."""
    # Create a mock JIRA client
    mock_client = Mock()

    # Mock the /rest/api/2/field response
    all_fields_response = Mock()
    all_fields_response.status_code = 200
    all_fields_response.json.return_value = [
        {
            "id": "customfield_12319275",
            "name": "Workstream",
            "schema": {"type": "array", "items": "option", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"}
        },
        {
            "id": "customfield_12311140",
            "name": "Epic Link",
            "schema": {"type": "string", "custom": "com.pyxis.greenhopper.jira:gh-epic-link"}
        },
        {
            "id": "customfield_12315940",
            "name": "Acceptance Criteria",
            "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:textarea"}
        }
    ]

    # Mock the /rest/api/2/issue/createmeta/{project}/issuetypes response (new API)
    issuetypes_response = Mock()
    issuetypes_response.status_code = 200
    issuetypes_response.json.return_value = {
        "values": [
            {"id": "1", "name": "Bug"},
            {"id": "17", "name": "Story"},
            {"id": "3", "name": "Task"}
        ]
    }

    # Mock the /rest/api/2/issue/createmeta/{project}/issuetypes/{id} response for Bug
    bug_fields_response = Mock()
    bug_fields_response.status_code = 200
    bug_fields_response.json.return_value = {
        "values": [
            {
                "fieldId": "customfield_12319275",
                "name": "Workstream",
                "required": True,
                "schema": {"type": "array", "items": "option", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"},
                "allowedValues": [
                    {"value": "Platform"},
                    {"value": "Hosted Services"},
                    {"value": "Tower"}
                ]
            }
        ]
    }

    # Mock the /rest/api/2/issue/createmeta/{project}/issuetypes/{id} response for Story
    story_fields_response = Mock()
    story_fields_response.status_code = 200
    story_fields_response.json.return_value = {
        "values": [
            {
                "fieldId": "customfield_12311140",
                "name": "Epic Link",
                "required": False,
                "schema": {"type": "string", "custom": "com.pyxis.greenhopper.jira:gh-epic-link"}
            },
            {
                "fieldId": "customfield_12315940",
                "name": "Acceptance Criteria",
                "required": True,
                "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:textarea"}
            }
        ]
    }

    # Setup the mock client to return these responses
    def mock_api_request(method, endpoint, **kwargs):
        if endpoint == "/rest/api/2/field":
            return all_fields_response
        elif endpoint == "/rest/api/2/issue/createmeta/PROJ/issuetypes":
            return issuetypes_response
        elif endpoint == "/rest/api/2/issue/createmeta/PROJ/issuetypes/1":
            return bug_fields_response
        elif endpoint == "/rest/api/2/issue/createmeta/PROJ/issuetypes/17":
            return story_fields_response
        return Mock(status_code=404)

    mock_client._api_request = mock_api_request

    # Create field mapper and discover fields
    mapper = JiraFieldMapper(mock_client)
    field_mappings = mapper.discover_fields("PROJ")

    # Verify the mappings
    assert "workstream" in field_mappings
    assert field_mappings["workstream"]["id"] == "customfield_12319275"
    assert field_mappings["workstream"]["name"] == "Workstream"
    assert field_mappings["workstream"]["type"] == "array"
    assert "Bug" in field_mappings["workstream"]["required_for"]
    assert "Platform" in field_mappings["workstream"]["allowed_values"]
    assert "Hosted Services" in field_mappings["workstream"]["allowed_values"]

    assert "epic_link" in field_mappings
    assert field_mappings["epic_link"]["id"] == "customfield_12311140"
    assert field_mappings["epic_link"]["name"] == "Epic Link"
    assert field_mappings["epic_link"]["required_for"] == []

    assert "acceptance_criteria" in field_mappings
    assert field_mappings["acceptance_criteria"]["id"] == "customfield_12315940"
    assert "Story" in field_mappings["acceptance_criteria"]["required_for"]


def test_discover_fields_api_failure(monkeypatch):
    """Test that discover_fields raises error on API failure."""
    mock_client = Mock()

    # Mock a failed response
    failed_response = Mock()
    failed_response.status_code = 500
    failed_response.text = "Internal Server Error"

    mock_client._api_request.return_value = failed_response

    mapper = JiraFieldMapper(mock_client)

    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="Failed to fetch JIRA fields"):
        mapper.discover_fields("PROJ")


def test_discover_fields_createmeta_failure(monkeypatch):
    """Test that discover_fields falls back when createmeta fails."""
    mock_client = Mock()

    # Mock successful all_fields response with some fields
    all_fields_response = Mock()
    all_fields_response.status_code = 200
    all_fields_response.json.return_value = [
        {
            "id": "customfield_123",
            "name": "Test Field",
            "schema": {"type": "string"}
        }
    ]

    # Mock failed createmeta response
    createmeta_response = Mock()
    createmeta_response.status_code = 403
    createmeta_response.text = "Forbidden"

    def mock_api_request(method, endpoint, **kwargs):
        if endpoint == "/rest/api/2/field":
            return all_fields_response
        elif endpoint == "/rest/api/2/issue/createmeta":
            return createmeta_response
        return Mock(status_code=404)

    mock_client._api_request = mock_api_request

    mapper = JiraFieldMapper(mock_client)

    # Should fall back to using just the field list
    field_mappings = mapper.discover_fields("PROJ")

    # Verify fallback mappings were created
    assert "test_field" in field_mappings
    assert field_mappings["test_field"]["id"] == "customfield_123"


def test_get_field_id_success():
    """Test getting field ID from human-readable name."""
    mock_client = Mock()

    # Pre-populate cache
    field_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream"
        },
        "epic_link": {
            "id": "customfield_12311140",
            "name": "Epic Link"
        }
    }

    mapper = JiraFieldMapper(mock_client, field_mappings=field_mappings)

    # Test exact match
    assert mapper.get_field_id("workstream") == "customfield_12319275"

    # Test case-insensitive
    assert mapper.get_field_id("Workstream") == "customfield_12319275"
    assert mapper.get_field_id("WORKSTREAM") == "customfield_12319275"

    # Test with spaces instead of underscores
    assert mapper.get_field_id("epic link") == "customfield_12311140"

    # Test not found
    assert mapper.get_field_id("nonexistent") is None


def test_get_field_info_success():
    """Test getting full field metadata."""
    mock_client = Mock()

    field_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream",
            "type": "array",
            "schema": "option",
            "allowed_values": ["Platform", "Tower"],
            "required_for": ["Bug", "Story"]
        }
    }

    mapper = JiraFieldMapper(mock_client, field_mappings=field_mappings)

    info = mapper.get_field_info("workstream")
    assert info is not None
    assert info["id"] == "customfield_12319275"
    assert info["name"] == "Workstream"
    assert info["type"] == "array"
    assert "Platform" in info["allowed_values"]
    assert "Bug" in info["required_for"]

    # Test not found
    assert mapper.get_field_info("nonexistent") is None


def test_is_cache_stale_with_old_timestamp():
    """Test that is_cache_stale detects old timestamps."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    # Create a timestamp from 10 days ago
    old_time = datetime.now() - timedelta(days=10)
    old_timestamp = old_time.isoformat()

    # Should be stale with default max_age_days=7
    assert mapper.is_cache_stale(old_timestamp) is True

    # Should not be stale with max_age_days=15
    assert mapper.is_cache_stale(old_timestamp, max_age_days=15) is False


def test_is_cache_stale_with_recent_timestamp():
    """Test that is_cache_stale detects recent timestamps."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    # Create a timestamp from 2 days ago
    recent_time = datetime.now() - timedelta(days=2)
    recent_timestamp = recent_time.isoformat()

    # Should not be stale
    assert mapper.is_cache_stale(recent_timestamp) is False


def test_is_cache_stale_with_none_timestamp():
    """Test that is_cache_stale returns True for None timestamp."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    assert mapper.is_cache_stale(None) is True


def test_is_cache_stale_with_invalid_timestamp():
    """Test that is_cache_stale handles invalid timestamps."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    # Invalid timestamp format
    assert mapper.is_cache_stale("not-a-timestamp") is True


def test_is_cache_stale_with_z_suffix():
    """Test that is_cache_stale handles timestamps with Z suffix."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    # Create a timestamp from 2 days ago with Z suffix
    recent_time = datetime.now() - timedelta(days=2)
    recent_timestamp = recent_time.isoformat() + "Z"

    # Should not be stale
    assert mapper.is_cache_stale(recent_timestamp) is False


def test_update_cache():
    """Test updating the internal cache."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    # Initially empty cache
    assert mapper.get_field_id("workstream") is None

    # Update cache
    new_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream"
        }
    }
    mapper.update_cache(new_mappings)

    # Should now find the field
    assert mapper.get_field_id("workstream") == "customfield_12319275"


def test_parse_field_metadata_with_multiple_issue_types():
    """Test that parse_field_metadata correctly combines data from multiple issue types."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    all_fields = [
        {
            "id": "customfield_12319275",
            "name": "Workstream"
        }
    ]

    createmeta = {
        "projects": [
            {
                "key": "PROJ",
                "issuetypes": [
                    {
                        "name": "Bug",
                        "fields": {
                            "customfield_12319275": {
                                "name": "Workstream",
                                "required": True,
                                "schema": {"type": "array"},
                                "allowedValues": [{"value": "Platform"}]
                            }
                        }
                    },
                    {
                        "name": "Story",
                        "fields": {
                            "customfield_12319275": {
                                "name": "Workstream",
                                "required": True,
                                "schema": {"type": "array"},
                                "allowedValues": [{"value": "Platform"}]
                            }
                        }
                    }
                ]
            }
        ]
    }

    mappings = mapper._parse_field_metadata(all_fields, createmeta)

    # Should only have one entry for workstream
    assert "workstream" in mappings

    # Should have both Bug and Story in required_for
    assert "Bug" in mappings["workstream"]["required_for"]
    assert "Story" in mappings["workstream"]["required_for"]


def test_parse_field_metadata_handles_missing_fields():
    """Test that parse_field_metadata handles edge cases gracefully."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    all_fields = []

    # Empty createmeta
    createmeta = {"projects": []}

    mappings = mapper._parse_field_metadata(all_fields, createmeta)
    assert mappings == {}

    # Createmeta with no fields
    createmeta = {
        "projects": [
            {
                "key": "PROJ",
                "issuetypes": [
                    {
                        "name": "Bug",
                        "fields": {}
                    }
                ]
            }
        ]
    }

    mappings = mapper._parse_field_metadata(all_fields, createmeta)
    assert mappings == {}


def test_parse_field_metadata_handles_allowed_values_types():
    """Test that parse_field_metadata handles different allowedValues formats."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    all_fields = []

    createmeta = {
        "projects": [
            {
                "key": "PROJ",
                "issuetypes": [
                    {
                        "name": "Bug",
                        "fields": {
                            "customfield_123": {
                                "name": "Test Field",
                                "required": False,
                                "schema": {"type": "string"},
                                "allowedValues": [
                                    {"value": "Option 1"},
                                    {"value": "Option 2"},
                                    "Plain String"  # Non-dict value
                                ]
                            }
                        }
                    }
                ]
            }
        ]
    }

    mappings = mapper._parse_field_metadata(all_fields, createmeta)

    assert "test_field" in mappings
    assert "Option 1" in mappings["test_field"]["allowed_values"]
    assert "Option 2" in mappings["test_field"]["allowed_values"]
    assert "Plain String" in mappings["test_field"]["allowed_values"]


def test_discover_fields_with_createmeta_failure_fallback(monkeypatch):
    """Test that discover_fields falls back when createmeta fails."""
    mock_client = Mock()

    # Mock successful all_fields response
    all_fields_response = Mock()
    all_fields_response.status_code = 200
    all_fields_response.json.return_value = [
        {
            "id": "customfield_12319275",
            "name": "Workstream",
            "schema": {
                "type": "array",
                "items": "option",
                "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"
            }
        },
        {
            "id": "customfield_12311140",
            "name": "Epic Link",
            "schema": {
                "type": "any",
                "custom": "com.pyxis.greenhopper.jira:gh-epic-link"
            }
        }
    ]

    # Mock failed createmeta response (404)
    createmeta_response = Mock()
    createmeta_response.status_code = 404
    createmeta_response.text = '{"errorMessages":["Issue Does Not Exist"],"errors":{}}'

    def mock_api_request(method, endpoint, **kwargs):
        if endpoint == "/rest/api/2/field":
            return all_fields_response
        elif endpoint == "/rest/api/2/issue/createmeta":
            return createmeta_response
        return Mock(status_code=404)

    mock_client._api_request = mock_api_request

    # Create field mapper and discover fields
    mapper = JiraFieldMapper(mock_client)
    field_mappings = mapper.discover_fields("PROJ")

    # Verify the fallback mappings were created
    assert "workstream" in field_mappings
    assert field_mappings["workstream"]["id"] == "customfield_12319275"
    assert field_mappings["workstream"]["name"] == "Workstream"
    assert field_mappings["workstream"]["type"] == "array"
    # Fallback method doesn't have allowed_values
    assert field_mappings["workstream"]["allowed_values"] == []

    assert "epic_link" in field_mappings
    assert field_mappings["epic_link"]["id"] == "customfield_12311140"
    assert field_mappings["epic_link"]["name"] == "Epic Link"


def test_parse_field_metadata_fallback():
    """Test the fallback field metadata parsing."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    all_fields = [
        {
            "id": "customfield_12319275",
            "name": "Workstream",
            "schema": {
                "type": "array",
                "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"
            }
        },
        {
            "id": "customfield_12311140",
            "name": "Epic Link",
            "schema": {
                "type": "any",
                "custom": "com.pyxis.greenhopper.jira:gh-epic-link"
            }
        },
        {
            "id": "summary",
            "name": "Summary",
            "schema": {
                "type": "string"
            }
        }
    ]

    mappings = mapper._parse_field_metadata_fallback(all_fields)

    # Verify all fields are mapped
    assert len(mappings) == 3

    # Verify workstream mapping
    assert "workstream" in mappings
    assert mappings["workstream"]["id"] == "customfield_12319275"
    assert mappings["workstream"]["name"] == "Workstream"
    assert mappings["workstream"]["type"] == "array"
    assert mappings["workstream"]["schema"] == "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"
    assert mappings["workstream"]["allowed_values"] == []
    assert mappings["workstream"]["required_for"] == []

    # Verify epic link mapping
    assert "epic_link" in mappings
    assert mappings["epic_link"]["id"] == "customfield_12311140"

    # Verify standard field mapping
    assert "summary" in mappings
    assert mappings["summary"]["id"] == "summary"


def test_discover_editable_fields_success(monkeypatch):
    """Test successful editable fields discovery."""
    mock_client = Mock()

    # Mock the /rest/api/2/field response
    all_fields_response = Mock()
    all_fields_response.status_code = 200
    all_fields_response.json.return_value = [
        {
            "id": "customfield_12310220",
            "name": "Git Pull Request",
            "schema": {"type": "any", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiurl"}
        },
        {
            "id": "customfield_12319275",
            "name": "Workstream",
            "schema": {"type": "array", "items": "option", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"}
        }
    ]

    # Mock the /rest/api/2/issue/{key}/editmeta response
    editmeta_response = Mock()
    editmeta_response.status_code = 200
    editmeta_response.json.return_value = {
        "fields": {
            "customfield_12310220": {
                "name": "Git Pull Request",
                "schema": {
                    "type": "any",
                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiurl"
                },
                "required": False,
                "operations": ["set"]
            },
            "customfield_12319275": {
                "name": "Workstream",
                "schema": {
                    "type": "array",
                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"
                },
                "required": True,
                "allowedValues": [
                    {"value": "Platform"},
                    {"value": "Hosted Services"}
                ],
                "operations": ["set"]
            }
        }
    }

    def mock_api_request(method, endpoint, **kwargs):
        if endpoint == "/rest/api/2/field":
            return all_fields_response
        elif endpoint == "/rest/api/2/issue/PROJ-12345/editmeta":
            return editmeta_response
        return Mock(status_code=404)

    mock_client._api_request = mock_api_request

    # Create field mapper and discover editable fields
    mapper = JiraFieldMapper(mock_client)
    field_mappings = mapper.discover_editable_fields("PROJ-12345")

    # Verify the mappings
    assert "git_pull_request" in field_mappings
    assert field_mappings["git_pull_request"]["id"] == "customfield_12310220"
    assert field_mappings["git_pull_request"]["name"] == "Git Pull Request"
    assert field_mappings["git_pull_request"]["type"] == "any"
    assert field_mappings["git_pull_request"]["schema"] == "multiurl"
    assert field_mappings["git_pull_request"]["required"] is False

    assert "workstream" in field_mappings
    assert field_mappings["workstream"]["id"] == "customfield_12319275"
    assert field_mappings["workstream"]["name"] == "Workstream"
    assert field_mappings["workstream"]["required"] is True
    assert "Platform" in field_mappings["workstream"]["allowed_values"]
    assert "Hosted Services" in field_mappings["workstream"]["allowed_values"]


def test_discover_editable_fields_api_failure(monkeypatch):
    """Test that discover_editable_fields raises error on API failure."""
    mock_client = Mock()

    # Mock a failed all_fields response
    failed_response = Mock()
    failed_response.status_code = 500
    failed_response.text = "Internal Server Error"

    mock_client._api_request.return_value = failed_response

    mapper = JiraFieldMapper(mock_client)

    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="Failed to fetch JIRA fields"):
        mapper.discover_editable_fields("PROJ-12345")


def test_fetch_editmeta_success():
    """Test successful editmeta fetch."""
    mock_client = Mock()

    editmeta_response = Mock()
    editmeta_response.status_code = 200
    editmeta_response.json.return_value = {
        "fields": {
            "customfield_12310220": {
                "name": "Git Pull Request",
                "schema": {"type": "any", "custom": "multiurl"},
                "required": False
            }
        }
    }

    mock_client._api_request.return_value = editmeta_response

    mapper = JiraFieldMapper(mock_client)
    editmeta = mapper._fetch_editmeta("PROJ-12345")

    assert "fields" in editmeta
    assert "customfield_12310220" in editmeta["fields"]


def test_fetch_editmeta_failure():
    """Test editmeta fetch failure."""
    mock_client = Mock()

    failed_response = Mock()
    failed_response.status_code = 404
    failed_response.text = "Issue not found"

    mock_client._api_request.return_value = failed_response

    mapper = JiraFieldMapper(mock_client)

    with pytest.raises(RuntimeError, match="Failed to fetch editmeta"):
        mapper._fetch_editmeta("PROJ-99999")


def test_parse_editmeta():
    """Test editmeta parsing."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    all_fields = [
        {
            "id": "customfield_12310220",
            "name": "Git Pull Request"
        }
    ]

    editmeta = {
        "fields": {
            "customfield_12310220": {
                "name": "Git Pull Request",
                "schema": {
                    "type": "any",
                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiurl"
                },
                "required": False,
                "operations": ["set"]
            },
            "customfield_12319275": {
                "name": "Workstream",
                "schema": {
                    "type": "array",
                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"
                },
                "required": True,
                "allowedValues": [
                    {"value": "Platform"},
                    {"value": "Tower"}
                ],
                "operations": ["set"]
            }
        }
    }

    mappings = mapper._parse_editmeta(all_fields, editmeta)

    # Verify git_pull_request mapping
    assert "git_pull_request" in mappings
    assert mappings["git_pull_request"]["id"] == "customfield_12310220"
    assert mappings["git_pull_request"]["name"] == "Git Pull Request"
    assert mappings["git_pull_request"]["type"] == "any"
    assert mappings["git_pull_request"]["schema"] == "multiurl"
    assert mappings["git_pull_request"]["required"] is False

    # Verify workstream mapping
    assert "workstream" in mappings
    assert mappings["workstream"]["id"] == "customfield_12319275"
    assert mappings["workstream"]["required"] is True
    assert "Platform" in mappings["workstream"]["allowed_values"]
    assert "Tower" in mappings["workstream"]["allowed_values"]


def test_is_cache_stale_with_hours_parameter():
    """Test is_cache_stale with max_age_hours parameter (PROJ-59812)."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    # Create a timestamp from 30 hours ago
    old_time = datetime.now() - timedelta(hours=30)
    old_timestamp = old_time.isoformat()

    # Should be stale with max_age_hours=24
    assert mapper.is_cache_stale(old_timestamp, max_age_hours=24) is True

    # Should not be stale with max_age_hours=48
    assert mapper.is_cache_stale(old_timestamp, max_age_hours=48) is False

    # Create a timestamp from 12 hours ago
    recent_time = datetime.now() - timedelta(hours=12)
    recent_timestamp = recent_time.isoformat()

    # Should not be stale with max_age_hours=24
    assert mapper.is_cache_stale(recent_timestamp, max_age_hours=24) is False

    # Should not be stale with max_age_hours=12.5 (fractional hours)
    assert mapper.is_cache_stale(recent_timestamp, max_age_hours=12.5) is False


def test_is_cache_stale_hours_takes_precedence_over_days():
    """Test that max_age_hours takes precedence over max_age_days (PROJ-59812)."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    # Create a timestamp from 30 hours ago
    timestamp = (datetime.now() - timedelta(hours=30)).isoformat()

    # When max_age_hours is provided, it should take precedence
    # 30 hours ago is stale for max_age_hours=24 (even though max_age_days=7 would say it's fresh)
    assert mapper.is_cache_stale(timestamp, max_age_days=7, max_age_hours=24) is True

    # 30 hours ago is not stale for max_age_hours=48 (even though max_age_days=1 would say it's stale)
    assert mapper.is_cache_stale(timestamp, max_age_days=1, max_age_hours=48) is False


def test_is_cache_stale_uses_days_when_hours_not_provided():
    """Test that max_age_days is used when max_age_hours is not provided (PROJ-59812)."""
    mock_client = Mock()
    mapper = JiraFieldMapper(mock_client)

    # Create a timestamp from 3 days ago
    timestamp = (datetime.now() - timedelta(days=3)).isoformat()

    # Should use max_age_days when max_age_hours is None
    assert mapper.is_cache_stale(timestamp, max_age_days=7, max_age_hours=None) is False
    assert mapper.is_cache_stale(timestamp, max_age_days=2, max_age_hours=None) is True

    # Should use max_age_days when max_age_hours is not specified
    assert mapper.is_cache_stale(timestamp, max_age_days=7) is False
    assert mapper.is_cache_stale(timestamp, max_age_days=2) is True
