"""Tests for configuration validation module."""

import json
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import (
    Config,
    JiraBackendConfig,
    JiraConfig,
    JiraTransitionConfig,
    OrganizationConfig,
    RepoConfig,
    TeamConfig,
)
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


class TestPlaceholderDetection:
    """Test detection of placeholder values in configuration."""

    def test_detect_todo_url(self, validator):
        """Test detection of URLs starting with TODO:."""
        issues = validator._check_placeholder_value(
            "backends/jira.json",
            "url",
            "TODO: https://your-jira-instance.com",
            "Set URL"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == "placeholder"
        assert "TODO:" in issues[0].message

    def test_detect_your_placeholder(self, validator):
        """Test detection of YOUR_ placeholder pattern."""
        issues = validator._check_placeholder_value(
            "organization.json",
            "jira_project",
            "TODO: YOUR_PROJECT_KEY",
            "Set project key"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == "placeholder"

    def test_detect_example_com(self, validator):
        """Test detection of example.com URLs."""
        issues = validator._check_placeholder_value(
            "backends/jira.json",
            "url",
            "https://jira.example.com",
            "Set URL"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == "placeholder"

    def test_detect_your_instance_pattern(self, validator):
        """Test detection of 'your-*-instance' pattern."""
        issues = validator._check_placeholder_value(
            "backends/jira.json",
            "url",
            "https://your-jira-instance.com",
            "Set URL"
        )

        assert len(issues) == 1
        assert issues[0].issue_type == "placeholder"

    def test_no_placeholder_in_valid_url(self, validator):
        """Test that valid URLs are not flagged as placeholders."""
        issues = validator._check_placeholder_value(
            "backends/jira.json",
            "url",
            "https://jira.company.com",
            "Set URL"
        )

        assert len(issues) == 0

    def test_no_placeholder_in_valid_project(self, validator):
        """Test that valid project keys are not flagged."""
        issues = validator._check_placeholder_value(
            "organization.json",
            "jira_project",
            "PROJ",
            "Set project"
        )

        assert len(issues) == 0


class TestMergedConfigValidation:
    """Test validation of merged configuration."""

    def test_validate_complete_config(self, validator, temp_config_dir):
        """Test that complete config has no issues."""
        config = Config(
            jira=JiraConfig(
                url="https://jira.company.com",
                user="test_user",
                project="PROJ",
                transitions={},
            ),
            repos=RepoConfig(workspace=str(temp_config_dir)),
        )

        result = validator.validate_merged_config(config)

        assert result.is_complete
        assert len(result.issues) == 0

    def test_validate_placeholder_url(self, validator, temp_config_dir):
        """Test detection of placeholder URL in merged config."""
        config = Config(
            jira=JiraConfig(
                url="TODO: https://your-jira-instance.com",
                user="test_user",
                project="PROJ",  # Set project to avoid null_required issue
                transitions={},
            ),
            repos=RepoConfig(workspace=str(temp_config_dir)),
        )

        result = validator.validate_merged_config(config)

        assert not result.is_complete
        assert len(result.issues) == 1
        assert result.issues[0].file == "backends/jira.json"
        assert result.issues[0].field == "url"
        assert result.issues[0].issue_type == "placeholder"

    def test_validate_null_required_field(self, validator, temp_config_dir):
        """Test detection of null required field."""
        config = Config(
            jira=JiraConfig(
                url="https://jira.company.com",
                user="test_user",
                project=None,  # Required field
                transitions={},
            ),
            repos=RepoConfig(workspace=str(temp_config_dir)),
        )

        result = validator.validate_merged_config(config)

        assert not result.is_complete
        assert len(result.issues) == 1
        assert result.issues[0].file == "organization.json"
        assert result.issues[0].field == "jira_project"
        assert result.issues[0].issue_type == "null_required"

    def test_validate_invalid_workspace_path(self, validator, temp_config_dir):
        """Test detection of non-existent workspace path."""
        from devflow.config.models import WorkspaceDefinition
        config = Config(
            jira=JiraConfig(
                url="https://jira.company.com",
                user="test_user",
                project="PROJ",
                transitions={},
            ),
            repos=RepoConfig(
                workspaces=[
                    WorkspaceDefinition(name="default", path="/nonexistent/path")
                ]
            ),
        )

        result = validator.validate_merged_config(config)

        assert not result.is_complete
        assert any(issue.issue_type == "invalid_path" for issue in result.issues)

    def test_validate_multiple_issues(self, validator, temp_config_dir):
        """Test detection of multiple issues in config."""
        from devflow.config.models import WorkspaceDefinition
        config = Config(
            jira=JiraConfig(
                url="TODO: https://example.com",
                user="test_user",
                project=None,
                transitions={},
            ),
            repos=RepoConfig(
                workspaces=[
                    WorkspaceDefinition(name="default", path="/nonexistent/path")
                ]
            ),
        )

        result = validator.validate_merged_config(config)

        assert not result.is_complete
        assert len(result.issues) >= 3  # URL placeholder, null project, invalid path


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
