"""Validator for config.json (user) configuration file."""

from pathlib import Path
from typing import Any, Dict, List

from devflow.config.validators.base import BaseConfigValidator, ValidationIssue


class UserConfigValidator(BaseConfigValidator):
    """Validator for config.json (user) configuration file."""

    schema_path = Path(__file__).parent.parent / "schemas" / "user.schema.json"
    config_file = "config.json"

    def custom_validations(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """User-specific validations.

        Args:
            data: User configuration dictionary

        Returns:
            List of validation issues
        """
        issues = []

        # Validate repos configuration
        repos = data.get("repos", {})
        workspaces = repos.get("workspaces", [])

        if not workspaces:
            issues.append(
                ValidationIssue(
                    file=self.config_file,
                    field="repos.workspaces",
                    issue_type="missing_field",
                    message="No workspaces defined",
                    suggestion="Add at least one workspace with name and path",
                    severity="error",
                )
            )

        # Validate workspace paths exist
        for i, workspace in enumerate(workspaces):
            workspace_path = workspace.get("path")
            if workspace_path:
                # Expand ~ and check if path exists
                expanded_path = Path(workspace_path).expanduser()
                if not expanded_path.exists():
                    issues.append(
                        ValidationIssue(
                            file=self.config_file,
                            field=f"repos.workspaces[{i}].path",
                            issue_type="invalid_path",
                            message=f"Workspace path does not exist: {workspace_path}",
                            suggestion="Create the directory or update the path",
                            severity="warning",
                        )
                    )

        # Validate last_used_workspace exists in workspaces
        last_used = repos.get("last_used_workspace")
        if last_used:
            workspace_names = [w.get("name") for w in workspaces]
            if last_used not in workspace_names:
                issues.append(
                    ValidationIssue(
                        file=self.config_file,
                        field="repos.last_used_workspace",
                        issue_type="invalid_reference",
                        message=f"last_used_workspace '{last_used}' not found in workspaces",
                        suggestion=f"Use one of: {', '.join(workspace_names)}",
                        severity="warning",
                    )
                )

        # Validate backend_config_source
        backend_source = data.get("backend_config_source")
        if backend_source and backend_source not in ["local", "central_db"]:
            issues.append(
                ValidationIssue(
                    file=self.config_file,
                    field="backend_config_source",
                    issue_type="invalid_value",
                    message=f"Invalid backend_config_source: '{backend_source}'",
                    suggestion="Use 'local' or 'central_db'",
                    severity="error",
                )
            )

        return issues
