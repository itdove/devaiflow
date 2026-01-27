"""Validator for enterprise.json configuration file."""

from pathlib import Path
from typing import Any, Dict, List

from devflow.config.validators.base import BaseConfigValidator, ValidationIssue


class EnterpriseConfigValidator(BaseConfigValidator):
    """Validator for enterprise.json configuration file."""

    schema_path = Path(__file__).parent.parent / "schemas" / "enterprise.schema.json"
    config_file = "enterprise.json"

    def custom_validations(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Enterprise-specific validations.

        Args:
            data: Enterprise configuration dictionary

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

        # Validate backend_overrides structure
        backend_overrides = data.get("backend_overrides")
        if backend_overrides:
            if not isinstance(backend_overrides, dict):
                issues.append(
                    ValidationIssue(
                        file=self.config_file,
                        field="backend_overrides",
                        issue_type="invalid_type",
                        message="backend_overrides must be an object",
                        suggestion='Use a JSON object: {"field_mappings": {...}}',
                        severity="error",
                    )
                )

        return issues
