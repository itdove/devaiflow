"""Validator for team.json configuration file."""

from pathlib import Path
from typing import Any, Dict, List

from devflow.config.validators.base import BaseConfigValidator, ValidationIssue


class TeamConfigValidator(BaseConfigValidator):
    """Validator for team.json configuration file."""

    schema_path = Path(__file__).parent.parent / "schemas" / "team.schema.json"
    config_file = "team.json"

    def custom_validations(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Team-specific validations.

        Args:
            data: Team configuration dictionary

        Returns:
            List of validation issues
        """
        issues = []

        # Validate agent_backend is a known value
        agent_backend = data.get("agent_backend")
        if agent_backend and agent_backend not in ["claude", "github-copilot"]:
            issues.append(
                ValidationIssue(
                    file=self.config_file,
                    field="agent_backend",
                    issue_type="invalid_value",
                    message=f"Unknown agent_backend: '{agent_backend}'",
                    suggestion="Use 'claude' or 'github-copilot'",
                    severity="error",
                )
            )

        # Validate comment visibility configuration
        visibility_type = data.get("jira_comment_visibility_type")
        visibility_value = data.get("jira_comment_visibility_value")

        if visibility_type and not visibility_value:
            issues.append(
                ValidationIssue(
                    file=self.config_file,
                    field="jira_comment_visibility_value",
                    issue_type="missing_field",
                    message="jira_comment_visibility_value is required when jira_comment_visibility_type is set",
                    suggestion="Add the group or role name for comment visibility",
                    severity="error",
                )
            )

        if visibility_value and not visibility_type:
            issues.append(
                ValidationIssue(
                    file=self.config_file,
                    field="jira_comment_visibility_type",
                    issue_type="missing_field",
                    message="jira_comment_visibility_type is required when jira_comment_visibility_value is set",
                    suggestion="Set to 'group' or 'role'",
                    severity="error",
                )
            )

        if visibility_type and visibility_type not in ["group", "role"]:
            issues.append(
                ValidationIssue(
                    file=self.config_file,
                    field="jira_comment_visibility_type",
                    issue_type="invalid_value",
                    message=f"Invalid visibility type: '{visibility_type}'",
                    suggestion="Use 'group' or 'role'",
                    severity="error",
                )
            )

        return issues
