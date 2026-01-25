"""Configuration validation for detecting placeholder values and completeness issues."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

console = Console()


@dataclass
class ValidationIssue:
    """Represents a single configuration validation issue."""

    file: str  # Config file name (e.g., "backends/jira.json", "organization.json")
    field: str  # Field path (e.g., "url", "jira_project")
    issue_type: str  # "placeholder", "null_required", "invalid_url"
    message: str  # Human-readable description
    suggestion: str  # Actionable fix suggestion
    severity: str = "warning"  # "warning" or "error"


@dataclass
class ValidationResult:
    """Result of configuration validation."""

    is_complete: bool
    issues: List[ValidationIssue]

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.issues) > 0

    def get_issues_by_severity(self, severity: str) -> List[ValidationIssue]:
        """Get issues filtered by severity."""
        return [issue for issue in self.issues if issue.severity == severity]


class ConfigValidator:
    """Validates configuration files for placeholder values and completeness."""

    # Patterns that indicate placeholder values
    PLACEHOLDER_PATTERNS = [
        r"^TODO:",  # URLs starting with "TODO:"
        r"TODO:",  # Any TODO: anywhere in the value
        r"YOUR_",  # Placeholder like "YOUR_PROJECT_KEY"
        r"your-.*-instance",  # Patterns like "your-jira-instance.com"
        r"example\.com",  # Generic example.com URLs
        r"jira\.example\.com",  # JIRA-specific example URLs
    ]

    # Required fields by config file
    REQUIRED_FIELDS = {
        "backends/jira.json": {
            "url": "JIRA instance URL (e.g., 'https://jira.company.com' or 'https://company.atlassian.net')"
        },
        "organization.json": {
            "jira_project": "JIRA project key (e.g., 'PROJ', 'ENG')"
        },
        # Team and user configs have no strictly required fields
    }

    def __init__(self, config_dir: Path):
        """Initialize validator.

        Args:
            config_dir: Directory containing config files (usually ~/.daf-sessions or DEVAIFLOW_HOME)
        """
        self.config_dir = config_dir

    def validate_merged_config(self, config: "Config") -> ValidationResult:
        """Validate merged configuration from all sources.

        Args:
            config: Merged Config object

        Returns:
            ValidationResult with detected issues
        """
        issues: List[ValidationIssue] = []

        # Check JIRA URL for placeholders
        if config.jira and config.jira.url:
            url_issues = self._check_placeholder_value(
                "backends/jira.json",
                "url",
                config.jira.url,
                "Set url in backends/jira.json to your JIRA instance URL"
            )
            issues.extend(url_issues)

        # Check for null required fields
        if config.jira and not config.jira.project:
            issues.append(ValidationIssue(
                file="organization.json",
                field="jira_project",
                issue_type="null_required",
                message="jira_project is null (required for creating issues and field discovery)",
                suggestion="Set jira_project in organization.json to your JIRA project key (e.g., 'PROJ') - limited functionality without it",
                severity="warning"
            ))

        # Check workspace paths
        if config.repos and config.repos.workspaces:
            for workspace in config.repos.workspaces:
                workspace_path = Path(workspace.path).expanduser()
                if not workspace_path.exists():
                    issues.append(ValidationIssue(
                        file="config.json",
                        field=f"repos.workspaces[{workspace.name}]",
                        issue_type="invalid_path",
                        message=f"workspace directory does not exist: {workspace.path}",
                        suggestion=f"Create the directory: mkdir -p {workspace.path}",
                        severity="warning"
                    ))

        is_complete = len(issues) == 0
        return ValidationResult(is_complete=is_complete, issues=issues)

    def validate_split_config_files(self) -> ValidationResult:
        """Validate individual config files (4-file format).

        Returns:
            ValidationResult with detected issues
        """
        import json

        issues: List[ValidationIssue] = []

        # Check backends/jira.json
        backend_file = self.config_dir / "backends" / "jira.json"
        if backend_file.exists():
            try:
                with open(backend_file, "r") as f:
                    backend_data = json.load(f)

                # Check URL for placeholders
                if "url" in backend_data:
                    url_issues = self._check_placeholder_value(
                        "backends/jira.json",
                        "url",
                        backend_data["url"],
                        "Set url in backends/jira.json to your JIRA instance URL"
                    )
                    issues.extend(url_issues)

                # Check for null URL
                if not backend_data.get("url"):
                    issues.append(ValidationIssue(
                        file="backends/jira.json",
                        field="url",
                        issue_type="null_required",
                        message="url is null or empty (required)",
                        suggestion="Set url in backends/jira.json to your JIRA instance URL",
                        severity="warning"
                    ))

                # Check transition placeholder values
                transitions = backend_data.get("transitions", {})
                for trans_name, trans_config in transitions.items():
                    if isinstance(trans_config, dict):
                        # Check 'to' field
                        to_value = trans_config.get("to", "")
                        if to_value:
                            to_issues = self._check_placeholder_value(
                                "backends/jira.json",
                                f"transitions.{trans_name}.to",
                                to_value,
                                f"Customize the target status for '{trans_name}' transition or leave empty to prompt"
                            )
                            issues.extend(to_issues)
            except Exception as e:
                issues.append(ValidationIssue(
                    file="backends/jira.json",
                    field="<file>",
                    issue_type="invalid_json",
                    message=f"Failed to parse file: {e}",
                    suggestion="Fix JSON syntax errors in backends/jira.json",
                    severity="error"
                ))

        # Check organization.json
        org_file = self.config_dir / "organization.json"
        if org_file.exists():
            try:
                with open(org_file, "r") as f:
                    org_data = json.load(f)

                # Check jira_project for placeholders
                if "jira_project" in org_data and org_data["jira_project"]:
                    project_issues = self._check_placeholder_value(
                        "organization.json",
                        "jira_project",
                        org_data["jira_project"],
                        "Set jira_project in organization.json to your JIRA project key"
                    )
                    issues.extend(project_issues)

                # Check for null jira_project
                if not org_data.get("jira_project"):
                    issues.append(ValidationIssue(
                        file="organization.json",
                        field="jira_project",
                        issue_type="null_required",
                        message="jira_project is null (required for ticket creation)",
                        suggestion="Set jira_project in organization.json to your JIRA project key (e.g., 'PROJ')",
                        severity="warning"
                    ))

                # Check sync filter statuses
                sync_filters = org_data.get("sync_filters", {})
                if "sync" in sync_filters:
                    sync_config = sync_filters["sync"]
                    statuses = sync_config.get("status", [])
                    for status in statuses:
                        if isinstance(status, str):
                            status_issues = self._check_placeholder_value(
                                "organization.json",
                                "sync_filters.sync.status",
                                status,
                                "Customize JIRA statuses in sync_filters.sync.status"
                            )
                            issues.extend(status_issues)
            except Exception as e:
                issues.append(ValidationIssue(
                    file="organization.json",
                    field="<file>",
                    issue_type="invalid_json",
                    message=f"Failed to parse file: {e}",
                    suggestion="Fix JSON syntax errors in organization.json",
                    severity="error"
                ))

        # Check team.json
        team_file = self.config_dir / "team.json"
        if team_file.exists():
            try:
                with open(team_file, "r") as f:
                    team_data = json.load(f)
            except Exception as e:
                issues.append(ValidationIssue(
                    file="team.json",
                    field="<file>",
                    issue_type="invalid_json",
                    message=f"Failed to parse file: {e}",
                    suggestion="Fix JSON syntax errors in team.json",
                    severity="error"
                ))

        # Check config.json (user config)
        config_file = self.config_dir / "config.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    user_data = json.load(f)

                # Check workspace paths
                if "repos" in user_data and "workspaces" in user_data["repos"]:
                    for workspace in user_data["repos"]["workspaces"]:
                        workspace_path = Path(workspace["path"]).expanduser()
                        if not workspace_path.exists():
                            issues.append(ValidationIssue(
                                file="config.json",
                                field=f"repos.workspaces[{workspace['name']}]",
                                issue_type="invalid_path",
                                message=f"workspace directory does not exist: {workspace['path']}",
                                suggestion=f"Create the directory: mkdir -p {workspace['path']}",
                                severity="warning"
                            ))
            except Exception as e:
                issues.append(ValidationIssue(
                    file="config.json",
                    field="<file>",
                    issue_type="invalid_json",
                    message=f"Failed to parse file: {e}",
                    suggestion="Fix JSON syntax errors in config.json",
                    severity="error"
                ))

        is_complete = len(issues) == 0
        return ValidationResult(is_complete=is_complete, issues=issues)

    def _check_placeholder_value(
        self,
        file: str,
        field: str,
        value: Any,
        suggestion: str
    ) -> List[ValidationIssue]:
        """Check if a value contains placeholder patterns.

        Args:
            file: Config file name
            field: Field name
            value: Field value to check
            suggestion: Suggestion for fixing the issue

        Returns:
            List of ValidationIssue objects (empty if no issues)
        """
        issues: List[ValidationIssue] = []

        if not isinstance(value, str):
            return issues

        # Check each placeholder pattern
        for pattern in self.PLACEHOLDER_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                issues.append(ValidationIssue(
                    file=file,
                    field=field,
                    issue_type="placeholder",
                    message=f"{field} contains placeholder value: '{value}'",
                    suggestion=suggestion,
                    severity="warning"
                ))
                break  # Only report once per field

        return issues

    def print_validation_result(
        self,
        result: ValidationResult,
        verbose: bool = True
    ) -> None:
        """Print validation result to console.

        Args:
            result: ValidationResult to display
            verbose: If True, show all details. If False, show summary only.
        """
        if result.is_complete:
            console.print("[green]✓[/green] Configuration is complete")
            return

        # Show summary
        warning_count = len(result.get_issues_by_severity("warning"))
        error_count = len(result.get_issues_by_severity("error"))

        console.print(f"\n[yellow]⚠[/yellow] Configuration has {len(result.issues)} issue(s)")
        if warning_count > 0:
            console.print(f"  [yellow]• {warning_count} warning(s)[/yellow]")
        if error_count > 0:
            console.print(f"  [red]• {error_count} error(s)[/red]")
        console.print()

        if not verbose:
            console.print("[dim]Run 'daf config show --validate' for details[/dim]\n")
            return

        # Group issues by file
        issues_by_file: Dict[str, List[ValidationIssue]] = {}
        for issue in result.issues:
            if issue.file not in issues_by_file:
                issues_by_file[issue.file] = []
            issues_by_file[issue.file].append(issue)

        # Display issues grouped by file
        for file_name, file_issues in sorted(issues_by_file.items()):
            console.print(f"[bold]{file_name}:[/bold]")
            for issue in file_issues:
                icon = "[red]✗[/red]" if issue.severity == "error" else "[yellow]⚠[/yellow]"
                console.print(f"  {icon} {issue.message}")
                console.print(f"     [dim]→ {issue.suggestion}[/dim]")
            console.print()

    def print_validation_warnings_on_load(self, result: ValidationResult) -> None:
        """Print non-intrusive validation warnings when config is loaded.

        Shows a brief summary if there are issues, directing users to run
        'daf config show --validate' for details.

        Args:
            result: ValidationResult from validation
        """
        # Don't print warnings in JSON mode (corrupts JSON output)
        try:
            from devflow.cli.utils import is_json_mode
            if is_json_mode():
                return
        except ImportError:
            pass  # If utils not available, continue with warnings

        # Don't print warnings in mock mode (tests use placeholder configs)
        try:
            from devflow.utils import is_mock_mode
            if is_mock_mode():
                return
        except ImportError:
            pass

        if result.is_complete:
            return  # No warnings needed

        # Count critical issues (placeholders and null required fields)
        critical_issues = [
            issue for issue in result.issues
            if issue.issue_type in ("placeholder", "null_required")
        ]

        if not critical_issues:
            return  # Only show warnings for critical issues on load

        console.print()
        console.print("[yellow]⚠ Configuration Warning:[/yellow] " +
                     f"Found {len(critical_issues)} configuration issue(s)")

        # Show first 2 issues as examples
        for issue in critical_issues[:2]:
            console.print(f"  [dim]• {issue.file}: {issue.message}[/dim]")

        if len(critical_issues) > 2:
            console.print(f"  [dim]• ... and {len(critical_issues) - 2} more[/dim]")

        console.print("[dim]Run 'daf config show --validate' for details and suggestions[/dim]")
        console.print()
