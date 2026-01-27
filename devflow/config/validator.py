"""Configuration validation for detecting placeholder values and completeness issues."""

from pathlib import Path
from typing import Dict, List

from rich.console import Console

from devflow.config.validators import (
    EnterpriseConfigValidator,
    OrganizationConfigValidator,
    TeamConfigValidator,
    UserConfigValidator,
    ValidationIssue,
    ValidationResult,
)
from devflow.config.validators.backends.jira import JiraBackendValidator

console = Console()

# Re-export for backward compatibility with existing code
__all__ = ["ConfigValidator", "ValidationIssue", "ValidationResult"]


class ConfigValidator:
    """Orchestrates validation across all configuration files using file-specific validators."""

    def __init__(self, config_dir: Path):
        """Initialize validator with config directory.

        Args:
            config_dir: Directory containing config files (usually ~/.daf-sessions or DEVAIFLOW_HOME)
        """
        self.config_dir = config_dir

        # Initialize file-specific validators
        self.enterprise_validator = EnterpriseConfigValidator()
        self.organization_validator = OrganizationConfigValidator()
        self.team_validator = TeamConfigValidator()
        self.user_validator = UserConfigValidator()
        self.jira_backend_validator = JiraBackendValidator()

    def validate_split_config_files(self) -> ValidationResult:
        """Validate all configuration files individually.

        Returns:
            ValidationResult with issues from all files
        """
        all_issues: List[ValidationIssue] = []

        # Validate enterprise.json
        enterprise_file = self.config_dir / "enterprise.json"
        if enterprise_file.exists():
            result = self.enterprise_validator.validate_file(enterprise_file)
            all_issues.extend(result.issues)

        # Validate organization.json
        org_file = self.config_dir / "organization.json"
        if org_file.exists():
            result = self.organization_validator.validate_file(org_file)
            all_issues.extend(result.issues)

        # Validate team.json
        team_file = self.config_dir / "team.json"
        if team_file.exists():
            result = self.team_validator.validate_file(team_file)
            all_issues.extend(result.issues)

        # Validate config.json (user)
        user_file = self.config_dir / "config.json"
        if user_file.exists():
            result = self.user_validator.validate_file(user_file)
            all_issues.extend(result.issues)

        # Validate backends/jira.json
        jira_file = self.config_dir / "backends" / "jira.json"
        if jira_file.exists():
            result = self.jira_backend_validator.validate_file(jira_file)
            all_issues.extend(result.issues)

        # Validation is complete if there are no issues at all
        is_complete = len(all_issues) == 0

        return ValidationResult(is_complete=is_complete, issues=all_issues)

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single configuration file.

        Useful for central DB: validate before saving.

        Args:
            file_path: Path to configuration file

        Returns:
            ValidationResult for the specified file

        Raises:
            ValueError: If file type is unknown
        """
        file_name = file_path.name

        if file_name == "enterprise.json":
            return self.enterprise_validator.validate_file(file_path)
        elif file_name == "organization.json":
            return self.organization_validator.validate_file(file_path)
        elif file_name == "team.json":
            return self.team_validator.validate_file(file_path)
        elif file_name == "config.json":
            return self.user_validator.validate_file(file_path)
        elif file_path.parent.name == "backends" and file_name == "jira.json":
            return self.jira_backend_validator.validate_file(file_path)
        else:
            raise ValueError(f"Unknown config file: {file_path}")

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
