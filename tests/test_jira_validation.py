"""Tests for JIRA field validation module.

Tests the pre-flight validation that checks fields against config.jira rules
before making API calls.
"""

import pytest
from unittest.mock import Mock

from devflow.jira.validation import (
    JiraFieldValidator,
    validate_jira_fields_before_operation,
    validate_update_payload,
)


class TestJiraFieldValidator:
    """Test JiraFieldValidator class."""

    def test_validates_custom_field_not_in_mappings(self):
        """Test validation skips field not in field_mappings."""
        field_mappings = {}
        validator = JiraFieldValidator(field_mappings)

        is_valid, errors = validator.validate_fields(
            issue_type="Bug",
            custom_fields={"unknown_field": "value"},
            system_fields={}
        )

        # Unknown fields are skipped (can't validate without mappings)
        assert is_valid
        assert len(errors) == 0

    def test_validates_field_not_available_for_issue_type(self):
        """Test validation fails when field not available for issue type."""
        field_mappings = {
            "workstream": {
                "id": "customfield_123",
                "name": "Workstream",
                "available_for": ["Story", "Task"],
                "allowed_values": ["Platform", "Services"]
            }
        }
        validator = JiraFieldValidator(field_mappings)

        is_valid, errors = validator.validate_fields(
            issue_type="Bug",
            custom_fields={"workstream": "Platform"},
            system_fields={}
        )

        assert not is_valid
        assert len(errors) == 1
        assert "not available for issue type 'Bug'" in errors[0]
        assert "Available for: Story, Task" in errors[0]

    def test_validates_invalid_allowed_value(self):
        """Test validation fails for value not in allowed_values."""
        field_mappings = {
            "severity": {
                "id": "customfield_456",
                "name": "Severity",
                "available_for": ["Bug"],
                "allowed_values": ["Critical", "Major", "Minor"]
            }
        }
        validator = JiraFieldValidator(field_mappings)

        is_valid, errors = validator.validate_fields(
            issue_type="Bug",
            custom_fields={"severity": "Invalid"},
            system_fields={}
        )

        assert not is_valid
        assert len(errors) == 1
        assert "Invalid value 'Invalid'" in errors[0]
        assert "Allowed values: Critical, Major, Minor" in errors[0]

    def test_validates_valid_custom_field(self):
        """Test validation passes for valid custom field."""
        field_mappings = {
            "workstream": {
                "id": "customfield_123",
                "name": "Workstream",
                "available_for": ["Story", "Bug"],
                "allowed_values": ["Platform", "Services"]
            }
        }
        validator = JiraFieldValidator(field_mappings)

        is_valid, errors = validator.validate_fields(
            issue_type="Bug",
            custom_fields={"workstream": "Platform"},
            system_fields={}
        )

        assert is_valid
        assert len(errors) == 0

    def test_validates_system_field_not_available(self):
        """Test validation fails for system field not available for issue type."""
        field_mappings = {
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "available_for": ["Bug"],
                "allowed_values": []
            }
        }
        validator = JiraFieldValidator(field_mappings)

        is_valid, errors = validator.validate_fields(
            issue_type="Story",
            custom_fields={},
            system_fields={"versions": ["1.0.0"]}
        )

        assert not is_valid
        assert len(errors) == 1
        assert "not available for issue type 'Story'" in errors[0]

    def test_validates_system_field_with_invalid_list_value(self):
        """Test validation fails for system field with invalid value in list."""
        field_mappings = {
            "component/s": {
                "id": "components",
                "name": "Component/s",
                "available_for": ["Bug", "Story"],
                "allowed_values": ["backend", "frontend", "database"]
            }
        }
        validator = JiraFieldValidator(field_mappings)

        is_valid, errors = validator.validate_fields(
            issue_type="Bug",
            custom_fields={},
            system_fields={"components": ["backend", "invalid"]}
        )

        assert not is_valid
        assert len(errors) == 1
        assert "Invalid value 'invalid'" in errors[0]

    def test_skips_validation_for_empty_field_values(self):
        """Test validation skips None and empty values."""
        field_mappings = {
            "optional_field": {
                "id": "customfield_789",
                "name": "Optional Field",
                "available_for": ["Bug"],
                "allowed_values": ["Yes", "No"]
            }
        }
        validator = JiraFieldValidator(field_mappings)

        # None value in system_fields should be skipped
        is_valid, errors = validator.validate_fields(
            issue_type="Bug",
            custom_fields={},
            system_fields={"customfield_789": None}
        )

        assert is_valid
        assert len(errors) == 0

    def test_handles_mock_field_mappings_gracefully(self):
        """Test validation handles Mock objects in tests gracefully."""
        # Simulate test environment with Mock field_mappings
        field_mappings = Mock()
        validator = JiraFieldValidator(field_mappings)

        is_valid, errors = validator.validate_fields(
            issue_type="Bug",
            custom_fields={"workstream": "Platform"},
            system_fields={}
        )

        # Should skip validation when field_mappings is Mock
        assert is_valid
        assert len(errors) == 0

    def test_handles_mock_available_for_gracefully(self):
        """Test validation handles Mock available_for list."""
        field_mappings = {
            "workstream": {
                "id": "customfield_123",
                "name": "Workstream",
                "available_for": Mock(),  # Mock object instead of list
                "allowed_values": []
            }
        }
        validator = JiraFieldValidator(field_mappings)

        # Should skip validation when available_for is Mock
        is_valid, errors = validator.validate_fields(
            issue_type="Bug",
            custom_fields={"workstream": "Platform"},
            system_fields={}
        )

        assert is_valid
        assert len(errors) == 0

    def test_get_missing_required_fields(self):
        """Test getting list of missing required fields."""
        field_mappings = {
            "workstream": {
                "id": "customfield_123",
                "name": "Workstream",
                "required_for": ["Story", "Bug"],
                "available_for": ["Story", "Bug"],
                "allowed_values": ["Platform", "Services"]
            },
            "severity": {
                "id": "customfield_456",
                "name": "Severity",
                "required_for": ["Bug"],
                "available_for": ["Bug"],
                "allowed_values": ["Critical", "Major"]
            }
        }
        validator = JiraFieldValidator(field_mappings)

        missing = validator.get_missing_required_fields(
            issue_type="Bug",
            custom_fields={},  # No fields provided
            system_fields={}
        )

        assert len(missing) == 2
        field_names = [name for name, info in missing]
        assert "workstream" in field_names
        assert "severity" in field_names

    def test_get_missing_required_fields_with_some_provided(self):
        """Test missing required fields when some are provided."""
        field_mappings = {
            "workstream": {
                "id": "customfield_123",
                "name": "Workstream",
                "required_for": ["Bug"],
                "available_for": ["Bug"],
                "allowed_values": []
            },
            "severity": {
                "id": "customfield_456",
                "name": "Severity",
                "required_for": ["Bug"],
                "available_for": ["Bug"],
                "allowed_values": []
            }
        }
        validator = JiraFieldValidator(field_mappings)

        missing = validator.get_missing_required_fields(
            issue_type="Bug",
            custom_fields={"workstream": "Platform"},  # Provided
            system_fields={}
        )

        assert len(missing) == 1
        assert missing[0][0] == "severity"

    def test_format_validation_errors(self):
        """Test error message formatting."""
        validator = JiraFieldValidator({})

        errors = [
            "Field 'workstream' not available for 'Bug'",
            "Invalid value 'Invalid' for 'severity'"
        ]

        formatted = validator.format_validation_errors(errors)

        assert "Validation failed" in formatted
        assert "workstream" in formatted
        assert "severity" in formatted
        assert "daf config show-fields" in formatted
        assert "Troubleshooting" in formatted

    def test_multiple_validation_errors(self):
        """Test validation collects multiple errors."""
        field_mappings = {
            "workstream": {
                "id": "customfield_123",
                "name": "Workstream",
                "available_for": ["Story"],  # Not available for Bug
                "allowed_values": []
            },
            "severity": {
                "id": "customfield_456",
                "name": "Severity",
                "available_for": ["Bug"],
                "allowed_values": ["Critical", "Major"]  # "Low" not allowed
            }
        }
        validator = JiraFieldValidator(field_mappings)

        is_valid, errors = validator.validate_fields(
            issue_type="Bug",
            custom_fields={
                "workstream": "Platform",
                "severity": "Low"
            },
            system_fields={}
        )

        assert not is_valid
        assert len(errors) == 2


class TestValidateJiraFieldsBeforeOperation:
    """Test validate_jira_fields_before_operation helper function."""

    def test_exits_on_validation_failure(self):
        """Test function exits when validation fails."""
        field_mappings = {
            "workstream": {
                "id": "customfield_123",
                "name": "Workstream",
                "available_for": ["Story"],
                "allowed_values": []
            }
        }

        with pytest.raises(SystemExit) as exc_info:
            validate_jira_fields_before_operation(
                issue_type="Bug",
                custom_fields={"workstream": "Platform"},
                system_fields={},
                field_mappings=field_mappings,
                output_json=False
            )

        assert exc_info.value.code == 1

    def test_continues_on_validation_success(self):
        """Test function returns normally when validation passes."""
        field_mappings = {
            "workstream": {
                "id": "customfield_123",
                "name": "Workstream",
                "available_for": ["Bug"],
                "allowed_values": ["Platform"]
            }
        }

        # Should not raise
        validate_jira_fields_before_operation(
            issue_type="Bug",
            custom_fields={"workstream": "Platform"},
            system_fields={},
            field_mappings=field_mappings,
            output_json=False
        )


class TestValidateUpdatePayload:
    """Test validate_update_payload helper function."""

    def test_validates_update_payload(self, monkeypatch):
        """Test validation of update payload."""
        # Mock jira_client.get_ticket
        mock_client = Mock()
        mock_client.get_ticket.return_value = {"issue_type": "Bug"}

        # Mock field_mapper
        mock_mapper = Mock()
        mock_mapper.field_mappings = {
            "workstream": {
                "id": "customfield_123",
                "name": "Workstream",
                "available_for": ["Story"],  # Not available for Bug
                "allowed_values": []
            }
        }

        payload = {
            "fields": {
                "customfield_123": {"value": "Platform"}
            }
        }

        with pytest.raises(SystemExit):
            validate_update_payload(
                issue_key="PROJ-123",
                payload=payload,
                jira_client=mock_client,
                field_mapper=mock_mapper,
                output_json=False
            )

    def test_skips_validation_if_issue_not_found(self, monkeypatch):
        """Test validation is skipped if issue can't be fetched."""
        from devflow.jira.exceptions import JiraNotFoundError

        mock_client = Mock()
        mock_client.get_ticket.side_effect = JiraNotFoundError("Issue", "PROJ-123")

        mock_mapper = Mock()
        mock_mapper.field_mappings = {}

        payload = {"fields": {}}

        # Should not raise - validation skipped
        validate_update_payload(
            issue_key="PROJ-123",
            payload=payload,
            jira_client=mock_client,
            field_mapper=mock_mapper,
            output_json=True  # Suppress warning output
        )
