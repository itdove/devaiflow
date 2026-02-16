"""Tests for base configuration validator."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import jsonschema
import pytest

from devflow.config.validators.base import (
    BaseConfigValidator,
    ValidationIssue,
    ValidationResult,
)


class TestValidationResult:
    """Test ValidationResult model methods."""

    def test_has_errors_returns_true_when_errors_exist(self):
        """Test has_errors returns True when error-level issues exist."""
        result = ValidationResult(
            is_complete=False,
            issues=[
                ValidationIssue(
                    file="test.json",
                    field="field1",
                    issue_type="error",
                    message="Error message",
                    suggestion="Fix it",
                    severity="error",
                )
            ],
        )

        assert result.has_errors() is True

    def test_has_errors_returns_false_when_only_warnings(self):
        """Test has_errors returns False when only warnings exist."""
        result = ValidationResult(
            is_complete=False,
            issues=[
                ValidationIssue(
                    file="test.json",
                    field="field1",
                    issue_type="warning",
                    message="Warning message",
                    suggestion="Fix it",
                    severity="warning",
                )
            ],
        )

        assert result.has_errors() is False


class ConcreteValidator(BaseConfigValidator):
    """Concrete implementation for testing."""

    def __init__(self, schema_path: Path):
        self.schema_path = schema_path
        self.config_file = "test.json"
        super().__init__()


class TestBaseConfigValidator:
    """Test BaseConfigValidator class."""

    @pytest.fixture
    def temp_schema(self, tmp_path):
        """Create a temporary JSON schema file."""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name"],
        }
        schema_file = tmp_path / "schema.json"
        with open(schema_file, "w") as f:
            json.dump(schema, f)
        return schema_file

    def test_load_schema_missing_file(self, tmp_path):
        """Test _load_schema raises FileNotFoundError when schema doesn't exist."""
        missing_schema = tmp_path / "missing_schema.json"

        with pytest.raises(FileNotFoundError, match="Schema file not found"):
            validator = ConcreteValidator(missing_schema)

    def test_validate_file_missing_file(self, temp_schema):
        """Test validate_file handles missing configuration file."""
        validator = ConcreteValidator(temp_schema)
        missing_file = Path("/nonexistent/config.json")

        result = validator.validate_file(missing_file)

        assert result.is_complete is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "missing_file"
        assert result.issues[0].severity == "error"

    def test_validate_file_generic_exception(self, temp_schema, tmp_path):
        """Test validate_file handles generic exceptions during file read."""
        validator = ConcreteValidator(temp_schema)
        config_file = tmp_path / "test.json"
        config_file.write_text("{}")

        # Mock open to raise a generic exception
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = validator.validate_file(config_file)

            assert result.is_complete is False
            assert len(result.issues) == 1
            assert result.issues[0].issue_type == "read_error"
            assert result.issues[0].severity == "error"
            assert "permissions" in result.issues[0].suggestion.lower()

    def test_check_placeholders_in_list(self, temp_schema, tmp_path):
        """Test _check_placeholders detects placeholders in list items."""
        validator = ConcreteValidator(temp_schema)

        data = {
            "names": ["John", "TODO: Add name", "Jane"],
            "urls": ["https://example.com", "https://valid.org"],
        }

        issues = validator._check_placeholders(data)

        # Should find placeholder in list
        assert len(issues) >= 1
        assert any("TODO:" in issue.message for issue in issues)

    def test_check_placeholders_nested_dict_in_list(self, temp_schema):
        """Test _check_placeholders handles nested dicts in lists."""
        validator = ConcreteValidator(temp_schema)

        data = {
            "items": [
                {"url": "https://example.com"},
                {"url": "https://valid.com"},
            ]
        }

        issues = validator._check_placeholders(data)

        # Should find placeholder in nested dict within list
        assert len(issues) >= 1
        assert any("example.com" in issue.message for issue in issues)

    def test_validate_with_schema_error(self, temp_schema):
        """Test _validate_with_schema handles SchemaError."""
        validator = ConcreteValidator(temp_schema)

        # Mock jsonschema.validate to raise SchemaError
        with patch("jsonschema.validate", side_effect=jsonschema.SchemaError("Invalid schema")):
            issues = validator._validate_with_schema({})

            assert len(issues) == 1
            assert issues[0].issue_type == "invalid_schema"
            assert issues[0].severity == "error"

    def test_get_schema_suggestion_type_error(self, temp_schema):
        """Test _get_schema_suggestion for type validation errors."""
        validator = ConcreteValidator(temp_schema)

        error = MagicMock(spec=jsonschema.ValidationError)
        error.validator = "type"
        error.validator_value = "string"

        suggestion = validator._get_schema_suggestion(error)

        assert "type" in suggestion.lower()
        assert "string" in suggestion

    def test_get_schema_suggestion_enum_error(self, temp_schema):
        """Test _get_schema_suggestion for enum validation errors."""
        validator = ConcreteValidator(temp_schema)

        error = MagicMock(spec=jsonschema.ValidationError)
        error.validator = "enum"
        error.validator_value = ["option1", "option2", "option3"]

        suggestion = validator._get_schema_suggestion(error)

        assert "Allowed values" in suggestion
        assert "option1" in suggestion

    def test_get_schema_suggestion_additional_properties(self, temp_schema):
        """Test _get_schema_suggestion for additionalProperties errors."""
        validator = ConcreteValidator(temp_schema)

        error = MagicMock(spec=jsonschema.ValidationError)
        error.validator = "additionalProperties"
        error.validator_value = False

        suggestion = validator._get_schema_suggestion(error)

        assert "unknown fields" in suggestion.lower() or "spelling" in suggestion.lower()

    def test_get_schema_suggestion_unknown_validator(self, temp_schema):
        """Test _get_schema_suggestion for unknown validator types."""
        validator = ConcreteValidator(temp_schema)

        error = MagicMock(spec=jsonschema.ValidationError)
        error.validator = "someUnknownValidator"
        error.validator_value = "value"

        suggestion = validator._get_schema_suggestion(error)

        assert "documentation" in suggestion.lower()

    def test_custom_validations_returns_empty_by_default(self, temp_schema):
        """Test custom_validations returns empty list by default."""
        validator = ConcreteValidator(temp_schema)

        issues = validator.custom_validations({})

        assert issues == []
