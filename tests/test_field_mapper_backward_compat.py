"""Tests for JIRA field mapper backward compatibility with old API format."""

from unittest.mock import Mock

import pytest

from devflow.jira.field_mapper import JiraFieldMapper


def test_discover_fields_old_jira_format():
    """Test that discover_fields works with older JIRA API format (uses 'values')."""
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
        }
    ]

    # Mock the /rest/api/2/issue/createmeta/{project}/issuetypes response (OLD API format)
    issuetypes_response = Mock()
    issuetypes_response.status_code = 200
    issuetypes_response.json.return_value = {
        "values": [  # OLD JIRA uses "values"
            {"id": "1", "name": "Bug"},
            {"id": "17", "name": "Story"}
        ]
    }

    # Mock the /rest/api/2/issue/createmeta/{project}/issuetypes/{id} response (OLD API format)
    bug_fields_response = Mock()
    bug_fields_response.status_code = 200
    bug_fields_response.json.return_value = {
        "values": [  # OLD JIRA uses "values"
            {
                "fieldId": "customfield_12319275",
                "name": "Workstream",
                "required": True,
                "schema": {"type": "array", "items": "option", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"},
                "allowedValues": [
                    {"value": "Platform"},
                    {"value": "Hosted Services"}
                ]
            }
        ]
    }

    story_fields_response = Mock()
    story_fields_response.status_code = 200
    story_fields_response.json.return_value = {
        "values": [  # OLD JIRA uses "values"
            {
                "fieldId": "customfield_12311140",
                "name": "Epic Link",
                "required": False,
                "schema": {"type": "string", "custom": "com.pyxis.greenhopper.jira:gh-epic-link"}
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

    # Verify the mappings work with old format
    assert "workstream" in field_mappings
    assert field_mappings["workstream"]["id"] == "customfield_12319275"
    assert field_mappings["workstream"]["name"] == "Workstream"
    assert "Bug" in field_mappings["workstream"]["required_for"]
    assert "Platform" in field_mappings["workstream"]["allowed_values"]

    assert "epic_link" in field_mappings
    assert field_mappings["epic_link"]["id"] == "customfield_12311140"
    assert field_mappings["epic_link"]["name"] == "Epic Link"
    assert field_mappings["epic_link"]["required_for"] == []


def test_discover_fields_new_jira_format():
    """Test that discover_fields works with newer JIRA API format (uses 'issueTypes' and 'fields')."""
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
        }
    ]

    # Mock the /rest/api/2/issue/createmeta/{project}/issuetypes response (NEW API format)
    issuetypes_response = Mock()
    issuetypes_response.status_code = 200
    issuetypes_response.json.return_value = {
        "issueTypes": [  # NEW JIRA uses "issueTypes"
            {"id": "1", "name": "Bug"},
            {"id": "17", "name": "Story"}
        ]
    }

    # Mock the /rest/api/2/issue/createmeta/{project}/issuetypes/{id} response (NEW API format)
    bug_fields_response = Mock()
    bug_fields_response.status_code = 200
    bug_fields_response.json.return_value = {
        "fields": [  # NEW JIRA uses "fields"
            {
                "fieldId": "customfield_12319275",
                "name": "Workstream",
                "required": True,
                "schema": {"type": "array", "items": "option", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect"},
                "allowedValues": [
                    {"value": "Platform"},
                    {"value": "Hosted Services"}
                ]
            }
        ]
    }

    story_fields_response = Mock()
    story_fields_response.status_code = 200
    story_fields_response.json.return_value = {
        "fields": [  # NEW JIRA uses "fields"
            {
                "fieldId": "customfield_12311140",
                "name": "Epic Link",
                "required": False,
                "schema": {"type": "string", "custom": "com.pyxis.greenhopper.jira:gh-epic-link"}
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

    # Verify the mappings work with new format
    assert "workstream" in field_mappings
    assert field_mappings["workstream"]["id"] == "customfield_12319275"
    assert field_mappings["workstream"]["name"] == "Workstream"
    assert "Bug" in field_mappings["workstream"]["required_for"]
    assert "Platform" in field_mappings["workstream"]["allowed_values"]

    assert "epic_link" in field_mappings
    assert field_mappings["epic_link"]["id"] == "customfield_12311140"
    assert field_mappings["epic_link"]["name"] == "Epic Link"
    assert field_mappings["epic_link"]["required_for"] == []
