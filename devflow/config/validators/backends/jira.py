"""Validator for backends/jira.json configuration file."""

from pathlib import Path
from typing import Any, Dict, List

from devflow.config.validators.backends.base import BaseBackendValidator
from devflow.config.validators.base import ValidationIssue


class JiraBackendValidator(BaseBackendValidator):
    """Validator for backends/jira.json configuration file."""

    schema_path = Path(__file__).parent.parent.parent / "schemas" / "backends" / "jira.schema.json"
    config_file = "backends/jira.json"

    # JIRA-specific placeholder patterns
    PLACEHOLDER_PATTERNS = BaseBackendValidator.PLACEHOLDER_PATTERNS + [
        r"jira\.example\.com",
        r"your-jira-instance",
        r"TODO:.*jira",
    ]

    def validate_dict(self, data: Dict[str, Any]):
        """Validate JIRA backend config, but skip placeholder warnings if using default.

        If the JIRA URL is still the default placeholder, we assume the user is not
        using JIRA and suppress all placeholder-related warnings for this file.
        """
        from devflow.config.validators.base import ValidationResult

        # Check if JIRA is actually configured (not just placeholder)
        jira_url = data.get("url", "")
        is_placeholder_url = not jira_url or "example.com" in jira_url

        if is_placeholder_url:
            # Don't warn about placeholders in jira.json if the URL itself is a placeholder
            # This means the user is likely using GitHub/GitLab and hasn't configured JIRA
            issues = []
            # Still do schema validation
            issues.extend(self._validate_with_schema(data))
            # Still do custom validations (but skip placeholder checks)
            issues.extend(self.custom_validations(data))
            is_complete = len(issues) == 0
            return ValidationResult(is_complete=is_complete, issues=issues)
        else:
            # JIRA is configured, do full validation including placeholder checks
            return super().validate_dict(data)

    def custom_validations(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """JIRA-specific validations.

        Args:
            data: JIRA backend configuration dictionary

        Returns:
            List of validation issues
        """
        issues = []

        # Validate JIRA URL format
        url = data.get("url")
        if url:
            if not url.startswith("https://"):
                issues.append(
                    ValidationIssue(
                        file=self.config_file,
                        field="url",
                        issue_type="invalid_url",
                        message="JIRA URL must use HTTPS",
                        suggestion="Change to https://...",
                        severity="error",
                    )
                )

            # Check for common JIRA URL patterns
            if ".atlassian.net" in url or "jira" in url.lower():
                # Valid JIRA URL patterns
                pass
            else:
                issues.append(
                    ValidationIssue(
                        file=self.config_file,
                        field="url",
                        issue_type="suspicious_url",
                        message="URL doesn't look like a JIRA instance",
                        suggestion="Verify this is your JIRA URL",
                        severity="warning",
                    )
                )

        # Validate transitions structure
        transitions = data.get("transitions", {})
        if transitions:
            for event, config in transitions.items():
                if "from" not in config:
                    issues.append(
                        ValidationIssue(
                            file=self.config_file,
                            field=f"transitions.{event}.from",
                            issue_type="missing_field",
                            message=f"Transition '{event}' missing 'from' field",
                            suggestion="Add 'from' array with source statuses",
                            severity="error",
                        )
                    )

                if "to" not in config:
                    issues.append(
                        ValidationIssue(
                            file=self.config_file,
                            field=f"transitions.{event}.to",
                            issue_type="missing_field",
                            message=f"Transition '{event}' missing 'to' field",
                            suggestion="Add 'to' field with target status",
                            severity="error",
                        )
                    )

                if "prompt" not in config:
                    issues.append(
                        ValidationIssue(
                            file=self.config_file,
                            field=f"transitions.{event}.prompt",
                            issue_type="missing_field",
                            message=f"Transition '{event}' missing 'prompt' field",
                            suggestion="Add 'prompt' boolean field",
                            severity="error",
                        )
                    )

        # Validate field_cache_max_age_hours
        max_age = data.get("field_cache_max_age_hours")
        if max_age is not None:
            if not isinstance(max_age, int) or max_age < 1:
                issues.append(
                    ValidationIssue(
                        file=self.config_file,
                        field="field_cache_max_age_hours",
                        issue_type="invalid_value",
                        message=f"field_cache_max_age_hours must be >= 1, got: {max_age}",
                        suggestion="Use a positive integer (e.g., 24 for 24 hours)",
                        severity="error",
                    )
                )

        return issues
