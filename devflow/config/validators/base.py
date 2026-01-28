"""Base validator class for configuration files."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
from pydantic import BaseModel


class ValidationIssue(BaseModel):
    """Represents a single validation issue."""

    file: str  # Configuration file name
    field: str  # Field path (e.g., "jira_project", "transitions.on_start")
    issue_type: str  # Type of issue (e.g., "missing_field", "invalid_value", "placeholder")
    message: str  # Human-readable error message
    suggestion: str  # Suggested fix
    severity: str  # "error" | "warning"


class ValidationResult(BaseModel):
    """Result of configuration validation."""

    is_complete: bool  # True if no errors (warnings are OK)
    issues: List[ValidationIssue]

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings.

        Returns:
            True if there are warnings or errors
        """
        return len(self.issues) > 0

    def get_issues_by_severity(self, severity: str) -> List[ValidationIssue]:
        """Get all issues with a specific severity.

        Args:
            severity: "error" or "warning"

        Returns:
            List of validation issues with the specified severity
        """
        return [issue for issue in self.issues if issue.severity == severity]

    def has_errors(self) -> bool:
        """Check if there are any error-level issues.

        Returns:
            True if there are errors
        """
        return len(self.get_issues_by_severity("error")) > 0


class BaseConfigValidator:
    """Base class for all configuration validators.

    Provides common validation logic:
    - JSON Schema validation
    - Placeholder detection
    - Required field checking
    - Custom validation hooks
    """

    schema_path: Path  # Path to JSON schema file
    config_file: str  # Config file name (e.g., "enterprise.json")

    # Common placeholder patterns
    PLACEHOLDER_PATTERNS = [
        r"TODO:",
        r"YOUR_",
        r"example\.com",
        r"jira\.example\.com",
    ]

    def __init__(self):
        """Initialize the validator and load JSON schema."""
        self.schema = self._load_schema()

    def _load_schema(self) -> Dict[str, Any]:
        """Load the JSON schema for this configuration file.

        Returns:
            Parsed JSON schema dictionary

        Raises:
            FileNotFoundError: If schema file doesn't exist
            json.JSONDecodeError: If schema is invalid JSON
        """
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

        with open(self.schema_path, "r") as f:
            return json.load(f)

    def validate_dict(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate a configuration dictionary.

        Args:
            data: Configuration dictionary to validate

        Returns:
            ValidationResult with all issues found
        """
        issues = []

        # 1. JSON Schema validation
        issues.extend(self._validate_with_schema(data))

        # 2. Placeholder detection
        issues.extend(self._check_placeholders(data))

        # 3. Required field checking
        issues.extend(self._check_required_fields(data))

        # 4. Custom validations (subclass hook)
        issues.extend(self.custom_validations(data))

        # Validation is complete if there are no issues at all
        is_complete = len(issues) == 0

        return ValidationResult(is_complete=is_complete, issues=issues)

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a configuration file.

        Args:
            file_path: Path to configuration file

        Returns:
            ValidationResult with all issues found
        """
        if not file_path.exists():
            return ValidationResult(
                is_complete=False,
                issues=[
                    ValidationIssue(
                        file=self.config_file,
                        field="",
                        issue_type="missing_file",
                        message=f"Configuration file not found: {file_path}",
                        suggestion=f"Create {self.config_file} using the template",
                        severity="error",
                    )
                ],
            )

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_complete=False,
                issues=[
                    ValidationIssue(
                        file=self.config_file,
                        field="",
                        issue_type="invalid_json",
                        message=f"Invalid JSON: {e}",
                        suggestion="Fix JSON syntax errors",
                        severity="error",
                    )
                ],
            )
        except Exception as e:
            return ValidationResult(
                is_complete=False,
                issues=[
                    ValidationIssue(
                        file=self.config_file,
                        field="",
                        issue_type="read_error",
                        message=f"Failed to read file: {e}",
                        suggestion="Check file permissions",
                        severity="error",
                    )
                ],
            )

        return self.validate_dict(data)

    def _check_placeholders(self, data: Dict[str, Any], path: str = "") -> List[ValidationIssue]:
        """Check for placeholder values (TODO:, YOUR_, example.com).

        Args:
            data: Dictionary to check
            path: Current field path (for nested structures)

        Returns:
            List of validation issues for placeholders found
        """
        issues = []

        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            if isinstance(value, str):
                # Check for placeholder patterns
                for pattern in self.PLACEHOLDER_PATTERNS:
                    if re.search(pattern, value, re.IGNORECASE):
                        issues.append(
                            ValidationIssue(
                                file=self.config_file,
                                field=current_path,
                                issue_type="placeholder",
                                message=f"Placeholder value detected: '{value}'",
                                suggestion=f"Replace with actual value for {current_path}",
                                severity="warning",
                            )
                        )
                        break

            elif isinstance(value, dict):
                # Recurse into nested dictionaries
                issues.extend(self._check_placeholders(value, current_path))

            elif isinstance(value, list):
                # Check list items
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        for pattern in self.PLACEHOLDER_PATTERNS:
                            if re.search(pattern, item, re.IGNORECASE):
                                issues.append(
                                    ValidationIssue(
                                        file=self.config_file,
                                        field=f"{current_path}[{i}]",
                                        issue_type="placeholder",
                                        message=f"Placeholder value detected: '{item}'",
                                        suggestion=f"Replace with actual value",
                                        severity="warning",
                                    )
                                )
                                break
                    elif isinstance(item, dict):
                        issues.extend(self._check_placeholders(item, f"{current_path}[{i}]"))

        return issues

    def _check_required_fields(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Check for null required fields.

        This is handled by JSON Schema validation, but we can add
        custom logic here if needed.

        Args:
            data: Configuration dictionary

        Returns:
            List of validation issues (empty by default)
        """
        # JSON Schema validation handles required fields
        # Subclasses can override this for custom logic
        return []

    def _validate_with_schema(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate against JSON Schema.

        Args:
            data: Configuration dictionary to validate

        Returns:
            List of validation issues from schema validation
        """
        issues = []

        try:
            jsonschema.validate(instance=data, schema=self.schema)
        except jsonschema.ValidationError as e:
            # Convert JSON Schema errors to ValidationIssue objects
            field_path = ".".join(str(p) for p in e.path) if e.path else ""

            issues.append(
                ValidationIssue(
                    file=self.config_file,
                    field=field_path or e.json_path.split("$.")[-1] if hasattr(e, "json_path") else "",
                    issue_type="schema_validation",
                    message=e.message,
                    suggestion=self._get_schema_suggestion(e),
                    severity="error",
                )
            )
        except jsonschema.SchemaError as e:
            # Schema itself is invalid
            issues.append(
                ValidationIssue(
                    file=self.config_file,
                    field="",
                    issue_type="invalid_schema",
                    message=f"Invalid JSON schema: {e}",
                    suggestion="Fix the schema file",
                    severity="error",
                )
            )

        return issues

    def _get_schema_suggestion(self, error: jsonschema.ValidationError) -> str:
        """Generate a helpful suggestion based on schema validation error.

        Args:
            error: JSON Schema validation error

        Returns:
            Suggested fix for the error
        """
        if error.validator == "required":
            missing_field = error.message.split("'")[1] if "'" in error.message else "field"
            return f"Add the required field: {missing_field}"
        elif error.validator == "type":
            expected_type = error.validator_value
            return f"Field must be of type: {expected_type}"
        elif error.validator == "enum":
            allowed_values = ", ".join(str(v) for v in error.validator_value)
            return f"Allowed values: {allowed_values}"
        elif error.validator == "additionalProperties":
            return "Remove unknown fields or check spelling"
        else:
            return "Check the documentation for valid values"

    def custom_validations(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Override for file-specific custom validations.

        Args:
            data: Configuration dictionary

        Returns:
            List of custom validation issues (empty by default)
        """
        return []
