"""JIRA field validation based on config.jira rules.

This module provides pre-flight validation for JIRA field values before making API calls.
All validation rules come from field_mappings in config.jira (single source of truth).
"""

import sys
from typing import Dict, List, Optional, Any, Tuple
from rich.console import Console

console = Console()


def validate_jira_fields_before_operation(
    issue_type: str,
    custom_fields: Dict[str, Any],
    system_fields: Dict[str, Any],
    field_mappings: Dict[str, Dict[str, Any]],
    output_json: bool = False
) -> None:
    """Validate JIRA fields before create/update operation.

    This is the SINGLE validation entry point used by both create and update commands.
    It validates all fields against config.jira rules and exits if validation fails.

    Args:
        issue_type: JIRA issue type (e.g., "Bug", "Story")
        custom_fields: Custom fields to validate (field_name -> value)
        system_fields: System fields to validate (field_id -> value)
        field_mappings: Field metadata from config.jira.field_mappings
        output_json: Whether to output JSON format

    Raises:
        SystemExit: If validation fails
    """
    from devflow.cli.utils import output_json as json_output

    validator = JiraFieldValidator(field_mappings)
    is_valid, validation_errors = validator.validate_fields(
        issue_type=issue_type,
        custom_fields=custom_fields,
        system_fields=system_fields
    )

    if not is_valid:
        error_msg = validator.format_validation_errors(validation_errors)
        if output_json:
            json_output(
                success=False,
                error={
                    "code": "FIELD_VALIDATION_ERROR",
                    "message": "Field validation failed - check config.jira rules",
                    "validation_errors": validation_errors
                }
            )
        else:
            console.print(error_msg)
        sys.exit(1)


def validate_update_payload(
    issue_key: str,
    payload: Dict[str, Any],
    jira_client,
    field_mapper,
    output_json: bool = False
) -> None:
    """Validate JIRA update payload before API call.

    This helper extracts fields from update payload and validates them.
    Used by update command to avoid code duplication.

    Args:
        issue_key: JIRA issue key being updated
        payload: Update payload with "fields" dict
        jira_client: JiraClient instance to fetch issue type
        field_mapper: JiraFieldMapper instance
        output_json: Whether to output JSON format

    Raises:
        SystemExit: If validation fails or issue can't be fetched
    """
    from devflow.jira.exceptions import JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError

    # Get issue type to validate against
    try:
        issue_data = jira_client.get_ticket(issue_key)
        issue_type = issue_data.get("issue_type", "")
    except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError) as e:
        # If we can't fetch issue, we can't validate - but API will fail anyway
        if not output_json:
            console.print(f"[yellow]⚠[/yellow] Could not fetch issue for validation: {e}")
            console.print("[dim]Skipping pre-flight validation...[/dim]")
        return

    # Extract custom and system fields from payload
    custom_fields = {}
    system_fields = {}

    for field_id, field_value in payload.get("fields", {}).items():
        if field_id.startswith("customfield_"):
            # Custom field - find field name
            field_name = None
            for fname, finfo in field_mapper.field_mappings.items():
                if finfo.get("id") == field_id:
                    field_name = fname
                    break
            if field_name:
                # Convert formatted value back to string for validation
                if isinstance(field_value, dict) and "value" in field_value:
                    custom_fields[field_name] = field_value["value"]
                elif isinstance(field_value, list) and len(field_value) > 0:
                    if isinstance(field_value[0], dict) and "value" in field_value[0]:
                        custom_fields[field_name] = field_value[0]["value"]
                    elif isinstance(field_value[0], dict) and "name" in field_value[0]:
                        custom_fields[field_name] = field_value[0]["name"]
                    else:
                        custom_fields[field_name] = str(field_value[0])
                else:
                    custom_fields[field_name] = str(field_value) if field_value is not None else ""
        else:
            # System field
            system_fields[field_id] = field_value

    # Validate using centralized function
    validate_jira_fields_before_operation(
        issue_type=issue_type,
        custom_fields=custom_fields,
        system_fields=system_fields,
        field_mappings=field_mapper.field_mappings,
        output_json=output_json
    )


class JiraFieldValidator:
    """Validates JIRA fields against config.jira field_mappings.

    This validator enforces rules from field_mappings:
    - required_for: Which issue types require this field
    - available_for: Which issue types can use this field
    - allowed_values: Valid values for this field

    All validation happens BEFORE API call to provide clear error messages.
    """

    def __init__(self, field_mappings: Dict[str, Dict[str, Any]]):
        """Initialize validator with field mappings from config.jira.

        Args:
            field_mappings: Field metadata from config.jira.field_mappings
        """
        self.field_mappings = field_mappings or {}

    def validate_fields(
        self,
        issue_type: str,
        custom_fields: Dict[str, str],
        system_fields: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate all provided fields against config.jira rules.

        Args:
            issue_type: JIRA issue type (e.g., "Bug", "Story")
            custom_fields: Custom fields to validate (field_name -> value)
            system_fields: System fields to validate (field_id -> value)

        Returns:
            Tuple of (is_valid, error_messages)
            - is_valid: True if all validations pass
            - error_messages: List of validation error messages
        """
        errors = []

        # Validate custom fields (customfield_*)
        for field_name, field_value in custom_fields.items():
            field_errors = self._validate_custom_field(
                field_name, field_value, issue_type
            )
            errors.extend(field_errors)

        # Validate system fields (non-customfield_*)
        for field_id, field_value in system_fields.items():
            # Skip None/empty values - they're optional
            if field_value is None or field_value == "" or field_value == []:
                continue

            field_errors = self._validate_system_field(
                field_id, field_value, issue_type
            )
            errors.extend(field_errors)

        return (len(errors) == 0, errors)

    def _validate_custom_field(
        self,
        field_name: str,
        field_value: str,
        issue_type: str
    ) -> List[str]:
        """Validate a custom field against config.jira rules.

        Args:
            field_name: Normalized field name (e.g., "workstream")
            field_value: Field value to validate
            issue_type: JIRA issue type

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check if field exists in mappings
        field_info = self.field_mappings.get(field_name)
        if not field_info:
            errors.append(
                f"Field '{field_name}' not found in field_mappings. "
                f"Run 'daf config show-fields' to see available fields."
            )
            return errors

        # Validate field is available for this issue type
        available_for = field_info.get("available_for", [])
        if available_for and issue_type not in available_for:
            errors.append(
                f"Field '{field_name}' is not available for issue type '{issue_type}'. "
                f"Available for: {', '.join(available_for)}. "
                f"Check config.jira.field_mappings['{field_name}']['available_for']"
            )

        # Validate value against allowed_values
        allowed_values = field_info.get("allowed_values", [])
        if allowed_values and field_value not in allowed_values:
            errors.append(
                f"Invalid value '{field_value}' for field '{field_name}'. "
                f"Allowed values: {', '.join(allowed_values)}. "
                f"Check config.jira.field_mappings['{field_name}']['allowed_values']"
            )

        return errors

    def _validate_system_field(
        self,
        field_id: str,
        field_value: Any,
        issue_type: str
    ) -> List[str]:
        """Validate a system field against config.jira rules.

        Args:
            field_id: JIRA field ID (e.g., "components", "labels")
            field_value: Field value to validate
            issue_type: JIRA issue type

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Find field info by field_id
        field_info = None
        field_name = None
        for name, info in self.field_mappings.items():
            if info.get("id") == field_id:
                field_info = info
                field_name = name
                break

        if not field_info:
            # Field not in mappings - skip validation (might be an API-provided field)
            return errors

        # Validate field is available for this issue type
        available_for = field_info.get("available_for", [])
        if available_for and issue_type not in available_for:
            errors.append(
                f"Field '{field_name}' ({field_id}) is not available for issue type '{issue_type}'. "
                f"Available for: {', '.join(available_for)}. "
                f"Check config.jira.field_mappings['{field_name}']['available_for']"
            )

        # Validate value against allowed_values (for single-value fields)
        allowed_values = field_info.get("allowed_values", [])
        if allowed_values:
            # Handle list values (components, labels, etc.)
            if isinstance(field_value, list):
                for val in field_value:
                    if val not in allowed_values:
                        errors.append(
                            f"Invalid value '{val}' for field '{field_name}'. "
                            f"Allowed values: {', '.join(allowed_values)}. "
                            f"Check config.jira.field_mappings['{field_name}']['allowed_values']"
                        )
            # Handle single values
            elif field_value not in allowed_values:
                errors.append(
                    f"Invalid value '{field_value}' for field '{field_name}'. "
                    f"Allowed values: {', '.join(allowed_values)}. "
                    f"Check config.jira.field_mappings['{field_name}']['allowed_values']"
                )

        return errors

    def get_missing_required_fields(
        self,
        issue_type: str,
        custom_fields: Dict[str, str],
        system_fields: Dict[str, Any]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Get list of required fields that are missing.

        Args:
            issue_type: JIRA issue type
            custom_fields: Provided custom fields
            system_fields: Provided system fields

        Returns:
            List of (field_name, field_info) tuples for missing required fields
        """
        missing = []

        for field_name, field_info in self.field_mappings.items():
            # Check if required for this issue type
            required_for = field_info.get("required_for", [])
            if issue_type not in required_for:
                continue

            # Check if field is provided
            field_id = field_info.get("id")

            # Check custom fields
            if field_id and field_id.startswith("customfield_"):
                if field_name not in custom_fields:
                    missing.append((field_name, field_info))
            # Check system fields
            else:
                if field_id not in system_fields:
                    missing.append((field_name, field_info))

        return missing

    def format_validation_errors(self, errors: List[str]) -> str:
        """Format validation errors for display.

        Args:
            errors: List of error messages

        Returns:
            Formatted error message string
        """
        if not errors:
            return ""

        message = "[red]✗[/red] Validation failed:\n"
        for error in errors:
            message += f"  • {error}\n"

        message += "\nTroubleshooting:\n"
        message += "  1. Run 'daf config show-fields' to see field rules\n"
        message += "  2. Run 'daf config refresh-jira-fields' to update field cache\n"
        message += "  3. Check config.jira.field_mappings for field availability\n"

        return message
