"""Tests for configuration validation module."""

import json
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.validator import ConfigValidator, ValidationIssue, ValidationResult


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / ".daf-sessions"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def validator(temp_config_dir):
    """Create a ConfigValidator instance."""
    return ConfigValidator(temp_config_dir)


class TestSplitConfigValidation:
    """Test validation of split configuration files."""

    def test_validate_backend_config_placeholder(self, validator, temp_config_dir):
        """Test detection of placeholder in backends/jira.json."""
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir(parents=True, exist_ok=True)

        backend_data = {
            "url": "TODO: https://your-jira-instance.com",
            "user": "",
            "transitions": {}
        }

        with open(backends_dir / "jira.json", "w") as f:
            json.dump(backend_data, f)

        result = validator.validate_split_config_files()

        assert not result.is_complete
        assert any(
            issue.file == "backends/jira.json" and issue.field == "url"
            for issue in result.issues
        )

    def test_validate_organization_config_placeholder(self, validator, temp_config_dir):
        """Test detection of placeholder in organization.json."""
        org_data = {
            "jira_project": "TODO: YOUR_PROJECT_KEY",
            "sync_filters": {}
        }

        with open(temp_config_dir / "organization.json", "w") as f:
            json.dump(org_data, f)

        result = validator.validate_split_config_files()

        assert not result.is_complete
        assert any(
            issue.file == "organization.json" and issue.field == "jira_project"
            for issue in result.issues
        )

    def test_validate_organization_config_null_project(self, validator, temp_config_dir):
        """Test detection of null jira_project."""
        org_data = {
            "jira_project": None,
            "sync_filters": {}
        }

        with open(temp_config_dir / "organization.json", "w") as f:
            json.dump(org_data, f)

        result = validator.validate_split_config_files()

        assert not result.is_complete
        assert any(
            issue.file == "organization.json" and
            issue.field == "jira_project" and
            issue.issue_type == "null_required"
            for issue in result.issues
        )

    def test_validate_team_config_valid(self, validator, temp_config_dir):
        """Test that valid team.json passes validation."""
        team_data = {
            "jira_custom_field_defaults": {"workstream": "Platform", "team": "Backend"},
            "time_tracking_enabled": True,
            "jira_comment_visibility_type": "group",
            "jira_comment_visibility_value": "Developers"
        }

        with open(temp_config_dir / "team.json", "w") as f:
            json.dump(team_data, f)

        result = validator.validate_split_config_files()

        # team.json fields are not validated for placeholders, only for parseability
        # So this should pass validation
        assert result.is_complete
        assert not any(issue.file == "team.json" for issue in result.issues)

    def test_validate_config_json_invalid_workspace(self, validator, temp_config_dir):
        """Test detection of invalid workspace in config.json."""
        user_data = {
            "repos": {
                "workspaces": [
                    {"name": "default", "path": "/nonexistent/workspace"}
                ],
                "last_used_workspace": "default",
                "detection": {"method": "keyword_match", "fallback": "prompt"},
                "keywords": {}
            },
            "time_tracking": {"auto_start": True},
            "backend_config_source": "local"
        }

        with open(temp_config_dir / "config.json", "w") as f:
            json.dump(user_data, f)

        result = validator.validate_split_config_files()

        assert not result.is_complete
        assert any(
            issue.file == "config.json" and
            "repos.workspaces" in issue.field and
            issue.issue_type == "invalid_path"
            for issue in result.issues
        )

    def test_validate_invalid_json_file(self, validator, temp_config_dir):
        """Test handling of malformed JSON files."""
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir(parents=True, exist_ok=True)

        with open(backends_dir / "jira.json", "w") as f:
            f.write("{ invalid json }")

        result = validator.validate_split_config_files()

        assert not result.is_complete
        assert any(
            issue.file == "backends/jira.json" and issue.issue_type == "invalid_json"
            for issue in result.issues
        )

    def test_validate_transition_placeholder(self, validator, temp_config_dir):
        """Test detection of placeholder in transition config."""
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir(parents=True, exist_ok=True)

        backend_data = {
            "url": "https://jira.company.com",
            "user": "",
            "transitions": {
                "on_start": {
                    "from": ["To Do"],
                    "to": "TODO: Set your status",
                    "prompt": False
                }
            }
        }

        with open(backends_dir / "jira.json", "w") as f:
            json.dump(backend_data, f)

        result = validator.validate_split_config_files()

        assert not result.is_complete
        assert any(
            issue.file == "backends/jira.json" and
            "transitions.on_start.to" in issue.field
            for issue in result.issues
        )


class TestValidationResult:
    """Test ValidationResult dataclass methods."""

    def test_has_warnings(self):
        """Test has_warnings property."""
        result = ValidationResult(
            is_complete=False,
            issues=[
                ValidationIssue(
                    file="test.json",
                    field="field",
                    issue_type="placeholder",
                    message="test",
                    suggestion="fix it",
                    severity="warning"
                )
            ]
        )

        assert result.has_warnings

    def test_no_warnings(self):
        """Test has_warnings when no issues."""
        result = ValidationResult(is_complete=True, issues=[])

        assert not result.has_warnings

    def test_get_issues_by_severity(self):
        """Test filtering issues by severity."""
        result = ValidationResult(
            is_complete=False,
            issues=[
                ValidationIssue(
                    file="test.json",
                    field="field1",
                    issue_type="placeholder",
                    message="warning",
                    suggestion="fix it",
                    severity="warning"
                ),
                ValidationIssue(
                    file="test.json",
                    field="field2",
                    issue_type="invalid_json",
                    message="error",
                    suggestion="fix it",
                    severity="error"
                ),
            ]
        )

        warnings = result.get_issues_by_severity("warning")
        errors = result.get_issues_by_severity("error")

        assert len(warnings) == 1
        assert len(errors) == 1
        assert warnings[0].field == "field1"
        assert errors[0].field == "field2"


class TestValidateFileMethod:
    """Test the validate_file method for individual file validation."""

    def test_validate_enterprise_file(self, validator, temp_config_dir):
        """Test validate_file for enterprise.json."""
        enterprise_file = temp_config_dir / "enterprise.json"
        enterprise_file.write_text(json.dumps({"backend_url": "https://example.com"}))

        result = validator.validate_file(enterprise_file)

        assert isinstance(result, ValidationResult)

    def test_validate_organization_file(self, validator, temp_config_dir):
        """Test validate_file for organization.json."""
        org_file = temp_config_dir / "organization.json"
        org_file.write_text(json.dumps({"jira_project": "PROJ"}))

        result = validator.validate_file(org_file)

        assert isinstance(result, ValidationResult)

    def test_validate_team_file(self, validator, temp_config_dir):
        """Test validate_file for team.json."""
        team_file = temp_config_dir / "team.json"
        team_file.write_text(json.dumps({"time_tracking_enabled": True}))

        result = validator.validate_file(team_file)

        assert isinstance(result, ValidationResult)

    def test_validate_config_file(self, validator, temp_config_dir):
        """Test validate_file for config.json."""
        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps({"repos": {"workspace": str(temp_config_dir)}}))

        result = validator.validate_file(config_file)

        assert isinstance(result, ValidationResult)

    def test_validate_jira_backend_file(self, validator, temp_config_dir):
        """Test validate_file for backends/jira.json."""
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir(parents=True, exist_ok=True)
        jira_file = backends_dir / "jira.json"
        jira_file.write_text(json.dumps({"url": "https://jira.example.com", "user": "test", "transitions": {}}))

        result = validator.validate_file(jira_file)

        assert isinstance(result, ValidationResult)

    def test_validate_file_unknown_type(self, validator, temp_config_dir):
        """Test validate_file raises error for unknown file type."""
        unknown_file = temp_config_dir / "unknown.json"
        unknown_file.write_text(json.dumps({}))

        with pytest.raises(ValueError, match="Unknown config file"):
            validator.validate_file(unknown_file)


class TestPrintValidationResult:
    """Test the print_validation_result method."""

    def test_print_validation_result_complete(self, validator):
        """Test printing result when validation is complete."""
        from unittest.mock import patch

        result = ValidationResult(is_complete=True, issues=[])

        with patch('devflow.config.validator.console') as mock_console:
            validator.print_validation_result(result)

            # Should print success message
            assert mock_console.print.called
            assert any("complete" in str(call) for call in mock_console.print.call_args_list)

    def test_print_validation_result_with_warnings(self, validator):
        """Test printing result with warnings."""
        from unittest.mock import patch

        result = ValidationResult(
            is_complete=False,
            issues=[
                ValidationIssue(
                    file="test.json",
                    field="field1",
                    issue_type="placeholder",
                    message="Placeholder found",
                    suggestion="Replace with actual value",
                    severity="warning"
                )
            ]
        )

        with patch('devflow.config.validator.console') as mock_console:
            validator.print_validation_result(result, verbose=True)

            # Should print warning info
            assert mock_console.print.called
            assert mock_console.print.call_count >= 4  # Summary + file + issue + suggestion

    def test_print_validation_result_with_errors(self, validator):
        """Test printing result with errors."""
        from unittest.mock import patch

        result = ValidationResult(
            is_complete=False,
            issues=[
                ValidationIssue(
                    file="test.json",
                    field="field1",
                    issue_type="invalid_json",
                    message="Invalid JSON",
                    suggestion="Fix JSON syntax",
                    severity="error"
                )
            ]
        )

        with patch('devflow.config.validator.console') as mock_console:
            validator.print_validation_result(result, verbose=True)

            # Should print error info
            assert mock_console.print.called

    def test_print_validation_result_non_verbose(self, validator):
        """Test printing result in non-verbose mode."""
        from unittest.mock import patch

        result = ValidationResult(
            is_complete=False,
            issues=[
                ValidationIssue(
                    file="test.json",
                    field="field1",
                    issue_type="placeholder",
                    message="Issue found",
                    suggestion="Fix it",
                    severity="warning"
                )
            ]
        )

        with patch('devflow.config.validator.console') as mock_console:
            validator.print_validation_result(result, verbose=False)

            # Should print summary only
            assert mock_console.print.called
            # Should suggest running validate command
            assert any("daf config show" in str(call) for call in mock_console.print.call_args_list)

    def test_print_validation_result_multiple_files(self, validator):
        """Test printing result with issues in multiple files."""
        from unittest.mock import patch

        result = ValidationResult(
            is_complete=False,
            issues=[
                ValidationIssue(
                    file="file1.json",
                    field="field1",
                    issue_type="placeholder",
                    message="Issue 1",
                    suggestion="Fix 1",
                    severity="warning"
                ),
                ValidationIssue(
                    file="file2.json",
                    field="field2",
                    issue_type="placeholder",
                    message="Issue 2",
                    suggestion="Fix 2",
                    severity="error"
                ),
            ]
        )

        with patch('devflow.config.validator.console') as mock_console:
            validator.print_validation_result(result, verbose=True)

            # Should print both files
            assert mock_console.print.called


class TestConfigLoaderIntegration:
    """Test integration between ConfigLoader and validator."""

    def test_validation_on_load_new_format(self, temp_config_dir):
        """Test that validation runs when loading new format config."""
        # Create config files with placeholders
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir(parents=True, exist_ok=True)

        with open(backends_dir / "jira.json", "w") as f:
            json.dump({
                "url": "TODO: https://your-jira-instance.com",
                "user": "",
                "transitions": {}
            }, f)

        with open(temp_config_dir / "organization.json", "w") as f:
            json.dump({
                "jira_project": None,
                "sync_filters": {}
            }, f)

        with open(temp_config_dir / "team.json", "w") as f:
            json.dump({
                "time_tracking_enabled": True
            }, f)

        with open(temp_config_dir / "config.json", "w") as f:
            json.dump({
                "repos": {
                    "workspace": str(temp_config_dir),
                    "detection": {"method": "keyword_match", "fallback": "prompt"},
                    "keywords": {}
                },
                "backend_config_source": "local"
            }, f)

        # Load config (should show validation warnings)
        loader = ConfigLoader(temp_config_dir)
        config = loader.load_config()

        # Config should load successfully despite warnings
        assert config is not None
        assert config.jira is not None

    def test_validation_on_load_old_format(self, temp_config_dir):
        """Test that validation runs when loading old format config."""
        config_data = {
            "jira": {
                "url": "TODO: https://example.com",
                "user": "",
                "project": None,
                "transitions": {},
                "filters": {}
            },
            "repos": {
                "workspace": str(temp_config_dir),
                "detection": {"method": "keyword_match", "fallback": "prompt"},
                "keywords": {}
            }
        }

        with open(temp_config_dir / "config.json", "w") as f:
            json.dump(config_data, f)

        # Load config (should show validation warnings)
        loader = ConfigLoader(temp_config_dir)
        config = loader.load_config()

        # Config should load successfully despite warnings
        assert config is not None
        assert config.jira is not None
