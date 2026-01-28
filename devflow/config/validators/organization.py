"""Validator for organization.json configuration file."""

from pathlib import Path
from typing import Any, Dict, List

from devflow.config.validators.base import BaseConfigValidator, ValidationIssue


class OrganizationConfigValidator(BaseConfigValidator):
    """Validator for organization.json configuration file."""

    schema_path = Path(__file__).parent.parent / "schemas" / "organization.schema.json"
    config_file = "organization.json"

    # Organization-specific placeholder patterns
    PLACEHOLDER_PATTERNS = BaseConfigValidator.PLACEHOLDER_PATTERNS + [
        r"PROJ-\d+",  # Example JIRA project key pattern
        r"YOUR_PROJECT_KEY",
    ]

    def custom_validations(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Organization-specific validations.

        Args:
            data: Organization configuration dictionary

        Returns:
            List of validation issues
        """
        issues = []

        # Check for null jira_project (required for functionality)
        jira_project = data.get("jira_project")
        if not jira_project:
            issues.append(
                ValidationIssue(
                    file=self.config_file,
                    field="jira_project",
                    issue_type="null_required",
                    message="jira_project is null (required for ticket creation and field discovery)",
                    suggestion="Set jira_project to your JIRA project key (e.g., 'PROJ', 'ENG')",
                    severity="warning",
                )
            )

        # Validate jira_project format (all caps, alphanumeric + hyphen)
        if jira_project:
            if not jira_project.isupper() or not all(c.isalnum() or c == "-" for c in jira_project):
                issues.append(
                    ValidationIssue(
                        file=self.config_file,
                        field="jira_project",
                        issue_type="invalid_format",
                        message=f"JIRA project key '{jira_project}' should be uppercase alphanumeric",
                        suggestion="Use uppercase letters, numbers, and hyphens (e.g., 'MYAPP', 'PROJ-A')",
                        severity="warning",
                    )
                )

        # Validate sync_filters structure
        sync_filters = data.get("sync_filters", {})
        for filter_name, filter_config in sync_filters.items():
            # Check required fields
            if "status" not in filter_config:
                issues.append(
                    ValidationIssue(
                        file=self.config_file,
                        field=f"sync_filters.{filter_name}.status",
                        issue_type="missing_field",
                        message=f"Filter '{filter_name}' missing 'status' field",
                        suggestion="Add 'status' array with JIRA statuses",
                        severity="error",
                    )
                )

            if "required_fields" not in filter_config:
                issues.append(
                    ValidationIssue(
                        file=self.config_file,
                        field=f"sync_filters.{filter_name}.required_fields",
                        issue_type="missing_field",
                        message=f"Filter '{filter_name}' missing 'required_fields' field",
                        suggestion="Add 'required_fields' array (can be empty)",
                        severity="error",
                    )
                )

            if "assignee" not in filter_config:
                issues.append(
                    ValidationIssue(
                        file=self.config_file,
                        field=f"sync_filters.{filter_name}.assignee",
                        issue_type="missing_field",
                        message=f"Filter '{filter_name}' missing 'assignee' field",
                        suggestion="Add 'assignee' field (use 'currentUser()' for user's tickets)",
                        severity="error",
                    )
                )

        return issues
