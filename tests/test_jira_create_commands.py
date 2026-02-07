"""Tests for daf jira create command module (jira_create_commands.py)."""

import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path

from devflow.cli.commands.jira_create_commands import (
    _ensure_field_mappings,
    _get_required_custom_fields,
    _get_project,
    _get_affected_version,
    _get_description,
    create_issue,
)

# Test template for _get_description tests
TEST_TEMPLATE = "*Description*\n\nTest template content"
from devflow.config.models import Config, JiraConfig
from devflow.jira.field_mapper import JiraFieldMapper
from devflow.jira.exceptions import JiraValidationError, JiraAuthError, JiraApiError


@pytest.fixture
def mock_config():
    """Create a mock config object."""
    config = Mock(spec=Config)
    config.jira = Mock(spec=JiraConfig)
    config.jira.url = "https://jira.example.com"
    config.jira.project = "PROJ"
    config.jira.custom_field_defaults = {"workstream": "Platform"}
    config.jira.system_field_defaults = None  # Add system_field_defaults attribute
    config.jira.affected_version = "v1.0.0"
    config.jira.field_mappings = {}
    config.jira.field_cache_timestamp = None
    # Add issue templates from config
    config.jira.issue_templates = {
        "Bug": "*Description*\n\nTest bug template",
        "Story": "h3. *User Story*\n\nTest story template",
        "Task": "h3. *Problem Description*\n\nTest task template",
        "Epic": "h2. *Background*\n\nTest epic template",
        "Spike": "h3. *User Story*\n\nTest spike template",
    }
    return config


@pytest.fixture
def mock_config_loader(mock_config):
    """Create a mock config loader."""
    loader = Mock()
    loader.load_config.return_value = mock_config
    loader.save_config = Mock()
    return loader


@pytest.fixture
def mock_field_mapper():
    """Create a mock field mapper."""
    mapper = MagicMock(spec=JiraFieldMapper)
    mapper.is_cache_stale.return_value = False
    mapper.discover_fields.return_value = {"workstream": {"id": "customfield_12319275"}}
    mapper.get_field_id.return_value = "customfield_12319275"
    return mapper


@pytest.fixture
def mock_jira_client():
    """Create a mock JIRA client."""
    client = Mock()
    client.create_issue.return_value = "PROJ-12345"
    client.get_ticket.return_value = {"status": "New"}
    client.link_issues = Mock()
    return client


class TestEnsureFieldMappings:
    """Tests for _ensure_field_mappings function."""

    def test_use_cached_mappings_when_fresh(self, mock_config, mock_config_loader, monkeypatch):
        """Test that cached field mappings are used when fresh."""
        from datetime import datetime

        # Set up cached mappings
        mock_config.jira.field_mappings = {"workstream": {"id": "customfield_12319275"}}
        mock_config.jira.field_cache_timestamp = datetime.now().isoformat()

        with patch('devflow.cli.commands.jira_create_commands.JiraClient'):
            with patch('devflow.cli.commands.jira_create_commands.JiraFieldMapper') as mock_mapper_class:
                mock_mapper = Mock()
                mock_mapper.is_cache_stale.return_value = False
                mock_mapper_class.return_value = mock_mapper

                result = _ensure_field_mappings(mock_config, mock_config_loader)

                assert result == mock_mapper
                mock_mapper.is_cache_stale.assert_called_once()

    def test_discover_fields_when_no_cache(self, mock_config, mock_config_loader, monkeypatch):
        """Test that fields are discovered when cache doesn't exist."""
        from datetime import datetime

        # No cached mappings
        mock_config.jira.field_mappings = None
        mock_config.jira.field_cache_timestamp = None

        with patch('devflow.cli.commands.jira_create_commands.JiraClient') as mock_client_class:
            with patch('devflow.cli.commands.jira_create_commands.JiraFieldMapper') as mock_mapper_class:
                mock_mapper = Mock()
                mock_mapper.discover_fields.return_value = {"test": {"id": "field_123"}}
                mock_mapper_class.return_value = mock_mapper

                result = _ensure_field_mappings(mock_config, mock_config_loader)

                mock_mapper.discover_fields.assert_called_once_with(mock_config.jira.project)
                mock_config_loader.save_config.assert_called_once()
                assert mock_config.jira.field_mappings == {"test": {"id": "field_123"}}

    def test_discover_fields_when_cache_stale(self, mock_config, mock_config_loader, monkeypatch):
        """Test that fields are discovered when cache is stale."""
        from datetime import datetime, timedelta

        # Stale cache
        old_timestamp = (datetime.now() - timedelta(days=10)).isoformat()
        mock_config.jira.field_mappings = {"old": {"id": "field_old"}}
        mock_config.jira.field_cache_timestamp = old_timestamp

        with patch('devflow.cli.commands.jira_create_commands.JiraClient'):
            with patch('devflow.cli.commands.jira_create_commands.JiraFieldMapper') as mock_mapper_class:
                mock_mapper = Mock()
                mock_mapper.is_cache_stale.return_value = True
                mock_mapper.discover_fields.return_value = {"new": {"id": "field_new"}}
                mock_mapper_class.return_value = mock_mapper

                result = _ensure_field_mappings(mock_config, mock_config_loader)

                mock_mapper.discover_fields.assert_called_once()
                assert mock_config.jira.field_mappings == {"new": {"id": "field_new"}}

    def test_handles_discovery_exception(self, mock_config, mock_config_loader, monkeypatch):
        """Test that discovery exceptions are handled gracefully."""
        mock_config.jira.field_mappings = None

        with patch('devflow.cli.commands.jira_create_commands.JiraClient'):
            with patch('devflow.cli.commands.jira_create_commands.JiraFieldMapper') as mock_mapper_class:
                mock_mapper = Mock()
                mock_mapper.discover_fields.side_effect = Exception("Discovery failed")
                mock_mapper_class.return_value = mock_mapper

                result = _ensure_field_mappings(mock_config, mock_config_loader)

                # Should return mapper with empty cache instead of failing
                assert result is not None


# TestGetWorkstream removed - workstream is now handled generically via _get_required_custom_fields


class TestGetProject:
    """Tests for _get_project function."""

    def test_use_flag_value_when_provided(self, mock_config, mock_config_loader, monkeypatch):
        """Test that flag value is used when provided."""
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: True)

        result = _get_project(mock_config, mock_config_loader, "PROJ")

        assert result == "PROJ"

    def test_use_config_value_when_no_flag(self, mock_config, mock_config_loader):
        """Test that config value is used when no flag provided."""
        mock_config.jira.project = "PROJ"

        result = _get_project(mock_config, mock_config_loader, None)

        assert result == "PROJ"

    def test_prompt_user_when_no_flag_or_config(self, mock_config, mock_config_loader, monkeypatch):
        """Test that user is prompted when no flag or config value."""
        mock_config.jira.project = None
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.Prompt.ask', lambda *args: "NEWPROJ")

        result = _get_project(mock_config, mock_config_loader, None)

        assert result == "NEWPROJ"
        assert mock_config.jira.project == "NEWPROJ"
        mock_config_loader.save_config.assert_called_once()

    def test_return_none_when_user_cancels_prompt(self, mock_config, mock_config_loader, monkeypatch):
        """Test that None is returned when user provides empty input."""
        mock_config.jira.project = None
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.Prompt.ask', lambda *args: "")

        result = _get_project(mock_config, mock_config_loader, None)

        assert result is None


class TestGetAffectedVersion:
    """Tests for _get_affected_version function."""

    def test_use_flag_value_when_provided(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test that flag value is used when provided."""
        # No field_mappings set, so any version is allowed
        mock_field_mapper.field_mappings = {}
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: True)

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, "custom-version", issue_type="Bug")

        assert result == "custom-version"

    def test_use_config_value_when_no_flag(self, mock_config, mock_config_loader, mock_field_mapper):
        """Test that config value is used when no flag provided."""
        mock_config.jira.affected_version = "v1.0.0"
        # No field_mappings set, so any version is allowed
        mock_field_mapper.field_mappings = {}

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, None, issue_type="Bug")

        assert result == "v1.0.0"

    def test_use_default_when_no_flag_or_config_and_required(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test that default is used when no flag or config value and field is required for Bug."""
        mock_config.jira.affected_version = None
        # Mark field as required for Bug
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "required_for": ["Bug"],
                "allowed_values": []
            }
        }
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: True)

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, None, issue_type="Bug")

        assert result == "v1.0.0"

    def test_returns_none_when_optional_and_not_provided(self, mock_config, mock_config_loader, mock_field_mapper):
        """Test that None is returned when field is not required for this issue type and not provided."""
        mock_config.jira.affected_version = None
        # Field exists but not required for Story
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "required_for": ["Bug"],  # Required for Bug, but not for Story
                "allowed_values": ["2.5.0", "2.4.0"]
            }
        }

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, None, issue_type="Story")

        assert result is None

    def test_prompt_with_allowed_versions_number_selection(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test prompting with allowed versions and selecting by number."""
        mock_config.jira.affected_version = None
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "required_for": ["Bug"],
                "allowed_values": ["2.5.0", "2.4.0", "2.3.0"]
            }
        }
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.Prompt.ask', lambda *args, **kwargs: "2")

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, None, issue_type="Bug")

        assert result == "2.4.0"
        mock_config_loader.save_config.assert_called_once()

    def test_prompt_with_allowed_versions_name_selection(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test prompting with allowed versions and selecting by name."""
        mock_config.jira.affected_version = None
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "required_for": ["Bug"],
                "allowed_values": ["2.5.0", "2.4.0", "2.3.0"]
            }
        }
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.Prompt.ask', lambda *args, **kwargs: "2.5.0")

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, None, issue_type="Bug")

        assert result == "2.5.0"
        mock_config_loader.save_config.assert_called_once()

    def test_prompt_with_allowed_versions_rejects_invalid_then_accepts_valid(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test prompting with allowed versions rejects invalid input then accepts valid."""
        mock_config.jira.affected_version = None
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "required_for": ["Bug"],
                "allowed_values": ["2.5.0", "2.4.0", "2.3.0"]
            }
        }
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)

        # Simulate user entering invalid version first, then valid version
        call_count = [0]
        def mock_prompt(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return "3.0.0-beta"  # Invalid version
            else:
                return "2.5.0"  # Valid version

        monkeypatch.setattr('devflow.jira.utils.Prompt.ask', mock_prompt)

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, None, issue_type="Bug")

        assert result == "2.5.0"
        mock_config_loader.save_config.assert_called_once()

    def test_prompt_without_allowed_versions_fallback(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test fallback to free-text prompt when no allowed_values but field is required."""
        mock_config.jira.affected_version = None
        # Field is required but has no allowed_values
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "required_for": ["Bug"],
                "allowed_values": []
            }
        }
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)
        monkeypatch.setattr('devflow.jira.utils.Prompt.ask', lambda *args, **kwargs: "v1.2.3")

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, None, issue_type="Bug")

        assert result == "v1.2.3"
        mock_config_loader.save_config.assert_called_once()

    def test_prompt_with_invalid_number_selection(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test handling invalid number selection loops until valid."""
        mock_config.jira.affected_version = None
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "required_for": ["Bug"],
                "allowed_values": ["2.5.0", "2.4.0", "2.3.0"]
            }
        }
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)

        # Simulate user entering invalid number first, then valid number
        call_count = [0]
        def mock_prompt(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return "99"  # Invalid number (out of range)
            else:
                return "1"  # Valid selection

        monkeypatch.setattr('devflow.jira.utils.Prompt.ask', mock_prompt)

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, None, issue_type="Bug")

        # Should accept valid selection after rejecting invalid
        assert result == "2.5.0"
        mock_config_loader.save_config.assert_called_once()

    def test_fallback_search_finds_version_field(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test fallback search finds version field not in hardcoded list."""
        mock_config.jira.affected_version = None
        # Use a field name not in the hardcoded list but containing "version"
        mock_field_mapper.field_mappings = {
            "fix_version/s": {
                "required_for": ["Bug"],
                "allowed_values": ["3.0.0", "2.9.0", "2.8.0"]
            },
            "some_other_field": {
                "allowed_values": ["foo", "bar"]
            }
        }
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)
        monkeypatch.setattr('devflow.jira.utils.Prompt.ask', lambda *args, **kwargs: "1")

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, None, issue_type="Bug")

        # Should find fix_version/s via fallback search and select first version
        assert result == "3.0.0"
        mock_config_loader.save_config.assert_called_once()

    def test_flag_value_validated_against_allowed_versions(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test flag value is validated against allowed_values and rejects invalid."""
        mock_config.jira.affected_version = None
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "allowed_values": ["2.5.0", "2.4.0", "2.3.0"]
            }
        }
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)

        # Try to use invalid flag value
        with pytest.raises(SystemExit):
            _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, "invalid-version", issue_type="Bug")

    def test_flag_value_accepts_valid_version(self, mock_config, mock_config_loader, mock_field_mapper, monkeypatch):
        """Test flag value accepts version from allowed_values."""
        mock_config.jira.affected_version = None
        mock_field_mapper.field_mappings = {
            "affects_version/s": {
                "allowed_values": ["2.5.0", "2.4.0", "2.3.0"]
            }
        }
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.is_json_mode', lambda: False)

        result = _get_affected_version(mock_config, mock_config_loader, mock_field_mapper, "2.4.0", issue_type="Bug")

        assert result == "2.4.0"
        # Should not save to config when flag is provided
        mock_config_loader.save_config.assert_not_called()


class TestGetDescription:
    """Tests for _get_description function."""

    def test_use_description_from_file(self, tmp_path):
        """Test reading description from file."""
        desc_file = tmp_path / "desc.txt"
        desc_file.write_text("Description from file")

        result = _get_description(None, str(desc_file), TEST_TEMPLATE, False)

        assert result == "Description from file"

    def test_use_description_from_argument(self):
        """Test using description from argument."""
        result = _get_description("Direct description", None, TEST_TEMPLATE, False)

        assert result == "Direct description"

    def test_use_template_when_no_input(self):
        """Test using template when no input provided."""
        result = _get_description(None, None, TEST_TEMPLATE, False)

        assert result == TEST_TEMPLATE

    def test_file_read_error_exits(self, tmp_path):
        """Test that file read error causes exit."""
        nonexistent_file = tmp_path / "nonexistent.txt"

        with pytest.raises(SystemExit):
            _get_description(None, str(nonexistent_file), TEST_TEMPLATE, False)

    def test_interactive_mode_reads_stdin(self, monkeypatch):
        """Test interactive mode reads from stdin."""
        lines = ["Line 1", "Line 2", "Line 3"]
        line_iter = iter(lines)

        def mock_input():
            try:
                return next(line_iter)
            except StopIteration:
                raise EOFError()

        monkeypatch.setattr('builtins.input', mock_input)

        result = _get_description(None, None, TEST_TEMPLATE, True)

        assert result == "Line 1\nLine 2\nLine 3"


class TestCreateIssue:
    """Tests for create_issue function."""

    def test_create_bug_successfully(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test successful bug creation."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                    with patch('devflow.cli.commands.jira_create_commands._get_required_custom_fields', return_value={"workstream": "Platform"}):
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            with patch('devflow.cli.commands.jira_create_commands._get_affected_version', return_value="v1.0.0"):
                                with patch('devflow.jira.utils.validate_jira_ticket', return_value={"key": "PROJ-100"}):
                                    mock_mapper = Mock()
                                    mock_ensure.return_value = mock_mapper

                                    create_issue(
                                        issue_type="bug",
                                        summary="Test bug",
                                        priority="Major",
                                        project="PROJ",
                                        parent="PROJ-100",
                                        affected_version="v1.0.0",
                                        description="Bug description",
                                        description_file=None,
                                        interactive=False,
                                        create_session=False,
                                    )

                                    mock_jira_client.create_issue.assert_called_once()

    def test_create_story_successfully(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test successful story creation."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            with patch('devflow.jira.utils.validate_jira_ticket', return_value={"key": "PROJ-100"}):
                                mock_mapper = Mock()
                                mock_ensure.return_value = mock_mapper

                                create_issue(
                                    issue_type="story",
                                    summary="Test story",
                                    priority="Major",
                                    project="PROJ",
                                    parent="PROJ-100",
                                    affected_version="",
                                    description="Story description",
                                    description_file=None,
                                    interactive=False,
                                    create_session=False,
                                )

                                mock_jira_client.create_issue.assert_called_once()

    def test_create_task_successfully(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test successful task creation."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            with patch('devflow.jira.utils.validate_jira_ticket', return_value={"key": "PROJ-100"}):
                                mock_mapper = Mock()
                                mock_ensure.return_value = mock_mapper

                                create_issue(
                                    issue_type="task",
                                    summary="Test task",
                                    priority="Major",
                                    project="PROJ",
                                    parent="PROJ-100",
                                    affected_version="",
                                    description="Task description",
                                    description_file=None,
                                    interactive=False,
                                    create_session=False,
                                )

                                mock_jira_client.create_issue.assert_called_once()

    def test_invalid_issue_type_exits(self, mock_config, mock_config_loader):
        """Test that invalid issue type causes exit."""
        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with pytest.raises(SystemExit):
                create_issue(
                    issue_type="invalid_type",
                    summary="Test",
                    priority="Major",
                    project="PROJ",
                                        parent=None,
                    affected_version="",
                    description="Test",
                    description_file=None,
                    interactive=False,
                    create_session=False,
                )

    def test_missing_config_exits(self, monkeypatch):
        """Test that missing config causes exit."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = None

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_loader):
            with pytest.raises(SystemExit):
                create_issue(
                    issue_type="bug",
                    summary="Test",
                    priority="Major",
                    project="PROJ",
                                        parent=None,
                    affected_version="",
                    description="Test",
                    description_file=None,
                    interactive=False,
                    create_session=False,
                )

    def test_validates_parent_ticket(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test that parent ticket is validated."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            with patch('devflow.jira.utils.validate_jira_ticket') as mock_validate:
                                mock_mapper = Mock()
                                mock_ensure.return_value = mock_mapper
                                mock_validate.return_value = {"key": "PROJ-100"}

                                create_issue(
                                    issue_type="story",
                                    summary="Test story",
                                    priority="Major",
                                    project="PROJ",
                                                                        parent="PROJ-100",
                                    affected_version="",
                                    description="Story description",
                                    description_file=None,
                                    interactive=False,
                                    create_session=False,
                                )

                                mock_validate.assert_called_once_with("PROJ-100", client=None)

    def test_invalid_parent_exits(self, mock_config, mock_config_loader, monkeypatch):
        """Test that invalid parent causes exit."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings'):
                    with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                        with patch('devflow.jira.utils.validate_jira_ticket', return_value=None):
                            with pytest.raises(SystemExit):
                                create_issue(
                                    issue_type="story",
                                    summary="Test story",
                                    priority="Major",
                                    project="PROJ",
                                                                        parent="INVALID-100",
                                    affected_version="",
                                    description="Story description",
                                    description_file=None,
                                    interactive=False,
                                    create_session=False,
                                )

    def test_links_issues_when_requested(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test that issues are linked when --linked-issue and --issue provided."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            with patch('devflow.jira.utils.validate_jira_ticket') as mock_validate:
                                mock_mapper = Mock()
                                mock_ensure.return_value = mock_mapper
                                # Return valid response for both parent and linked issue validation
                                mock_validate.side_effect = [{"key": "PROJ-100"}, {"key": "PROJ-999"}]

                                create_issue(
                                    issue_type="story",
                                    summary="Test story",
                                    priority="Major",
                                    project="PROJ",
                                                                        parent="PROJ-100",
                                    affected_version="",
                                    description="Story description",
                                    description_file=None,
                                    interactive=False,
                                    create_session=False,
                                    linked_issue="blocks",
                                    issue="PROJ-999",
                                )

                                mock_jira_client.link_issues.assert_called_once()

    def test_json_output_mode(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test JSON output mode."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            with patch('devflow.cli.commands.jira_create_commands.json_output') as mock_json_out:
                                with patch('devflow.jira.utils.validate_jira_ticket', return_value={"key": "PROJ-100"}):
                                    mock_mapper = Mock()
                                    mock_ensure.return_value = mock_mapper

                                    create_issue(
                                        issue_type="story",
                                        summary="Test story",
                                        priority="Major",
                                        project="PROJ",
                                                                                parent="PROJ-100",
                                        affected_version="",
                                        description="Story description",
                                        description_file=None,
                                        interactive=False,
                                        create_session=False,
                                        output_json=True,
                                    )

                                    mock_json_out.assert_called_once()
                                    call_args = mock_json_out.call_args
                                    assert call_args[1]['success'] is True
                                    assert 'issue_key' in call_args[1]['data']


class TestCreateBug:
    """Tests for creating bugs using create_issue function."""

    def test_create_bug_prompts_for_summary(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test that create_issue for bugs prompts for summary when not provided."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
        monkeypatch.setattr('devflow.cli.commands.jira_create_commands.Prompt.ask', lambda *args: "Prompted bug summary")

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                    with patch('devflow.cli.commands.jira_create_commands._get_required_custom_fields', return_value={"workstream": "Platform"}):
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            with patch('devflow.cli.commands.jira_create_commands._get_affected_version', return_value="v1.0.0"):
                                mock_mapper = Mock()
                                mock_ensure.return_value = mock_mapper

                                create_issue(
                                    issue_type="bug",
                                    summary=None,
                                    priority="Major",
                                    project=None,
                                    parent=None,
                                    affected_version="v1.0.0",
                                    description="Bug description",
                                    description_file=None,
                                    interactive=False,
                                    create_session=False,
                                )

                                # Verify bug was created with prompted summary
                                call_args = mock_jira_client.create_issue.call_args
                                assert call_args[1]['summary'] == "Prompted bug summary"


class TestCreateStory:
    """Tests for creating stories using create_issue function."""

    def test_create_story_with_epic(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test creating a story linked to an epic."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                    with patch('devflow.cli.commands.jira_create_commands._get_required_custom_fields', return_value={"workstream": "Platform"}):
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            with patch('devflow.jira.utils.validate_jira_ticket', return_value={"key": "PROJ-100"}):
                                mock_mapper = Mock()
                                mock_ensure.return_value = mock_mapper

                                create_issue(
                                    issue_type="story",
                                    summary="Test story",
                                    priority="Major",
                                    project=None,
                                    parent="PROJ-100",
                                    affected_version=None,
                                    description="Story description",
                                    description_file=None,
                                    interactive=False,
                                    create_session=False,
                                )

                                call_args = mock_jira_client.create_issue.call_args
                                assert call_args[1]['parent'] == "PROJ-100"


class TestCreateTask:
    """Tests for create_task function."""

    def test_create_task_handles_validation_error(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test that create_task handles validation errors properly."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        # Make create_issue raise a validation error
        mock_jira_client.create_issue.side_effect = JiraValidationError(
            "Validation failed",
            field_errors={"summary": "Summary is required"},
            error_messages=["Invalid data"]
        )

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            mock_mapper = Mock()
                            mock_ensure.return_value = mock_mapper

                            with pytest.raises(SystemExit):
                                create_issue(
                                    issue_type="task",
                                    summary="Test task",
                                    priority="Major",
                                    project=None,
                                    parent=None,
                                    affected_version=None,
                                    description="Task description",
                                    description_file=None,
                                    interactive=False,
                                    create_session=False,
                                )


class TestIssueTypeCaseSensitivity:
    """Tests for AAP-64472: Custom fields silently skipped due to case mismatch."""

    def test_lowercase_issue_type_matches_titlecase_field_metadata(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test that lowercase 'bug' matches title-case 'Bug' in field metadata.

        Regression test for AAP-64472: Custom fields were silently skipped when
        comparing lowercase issue_type="bug" against title-case required_for=["Bug"].
        The fix normalizes issue_type to title-case at the entry point.
        """
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        # Set up field mappings with title-case "Bug" in required_for
        mock_config.jira.field_mappings = {
            "workstream": {
                "id": "customfield_12345",
                "name": "Workstream",
                "type": "option",
                "required_for": ["Bug", "Story", "Task"],  # Title-case
                "available_for": ["Bug", "Story", "Task"],
                "allowed_values": ["Platform", "SaaS"]
            }
        }

        # Configure mock to return field value
        mock_config.jira.custom_field_defaults = {"workstream": "Platform"}

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                    with patch('devflow.cli.commands.jira_create_commands._get_required_custom_fields', return_value={"workstream": "SaaS"}):
                        with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="PROJ"):
                            with patch('devflow.cli.commands.jira_create_commands._get_affected_version', return_value="v1.0.0"):
                                with patch('devflow.jira.utils.validate_jira_ticket', return_value={"key": "PROJ-100"}):
                                    mock_mapper = Mock()
                                    mock_mapper.field_mappings = mock_config.jira.field_mappings
                                    mock_ensure.return_value = mock_mapper

                                    # Call create_issue with lowercase "bug" issue type
                                    create_issue(
                                        issue_type="bug",
                                        summary="Test bug",
                                        priority="Major",
                                        project=None,
                                        parent="PROJ-100",
                                        affected_version="v1.0.0",
                                        description="Bug description",
                                        description_file=None,
                                        interactive=False,
                                        create_session=False,
                                        custom_fields={"workstream": "SaaS"},  # Explicitly provide custom field
                                    )

                            # Verify the bug was created successfully
                            assert mock_jira_client.create_issue.called

                            # Verify workstream field was included in the call
                            call_kwargs = mock_jira_client.create_issue.call_args[1]
                            # The workstream field should be added by its field ID (customfield_12345)
                            # This proves that the issue_type was normalized correctly - if it wasn't,
                            # the field wouldn't have been identified as required and wouldn't be here
                            assert call_kwargs.get('customfield_12345') == "SaaS"

    def test_versions_field_passed_to_jira_client(self, mock_config, mock_config_loader, mock_jira_client, monkeypatch):
        """Test that versions field is correctly passed to JIRA client when creating a bug.

        This test verifies the fix for the issue where --affects-versions was not being
        passed to the JIRA API, causing "Affects Version/s is required" errors.
        """
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        # Configure field mappings
        mock_config.jira.field_mappings = {
            "component/s": {
                "id": "components",
                "name": "Component/s",
                "type": "array",
                "required_for": [],
                "available_for": []  # Not available for any issue type to avoid requirement
            },
            "affects_version/s": {
                "id": "versions",
                "name": "Affects Version/s",
                "type": "array",
                "required_for": ["Bug"],
                "available_for": ["Bug"],
                "allowed_values": ["ansible-saas-ga", "2.5.0", "2.4.0"]
            }
        }

        with patch('devflow.cli.commands.jira_create_commands.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.jira_create_commands.JiraClient', return_value=mock_jira_client):
                with patch('devflow.cli.commands.jira_create_commands._ensure_field_mappings') as mock_ensure:
                    with patch('devflow.cli.commands.jira_create_commands._get_project', return_value="AAP"):
                        with patch('devflow.cli.commands.jira_create_commands._get_required_custom_fields', return_value={}):
                            with patch('devflow.cli.commands.jira_create_commands._get_required_system_fields', return_value={}):
                                with patch('devflow.jira.utils.validate_jira_ticket', return_value={"key": "AAP-64025"}):
                                    mock_mapper = Mock()
                                    mock_mapper.field_mappings = mock_config.jira.field_mappings
                                    mock_ensure.return_value = mock_mapper

                                    # Simulate passing --affects-versions ansible-saas-ga via system_fields
                                    # This is what jira_create_dynamic.py does on line 113-115
                                    system_fields = {"versions": "ansible-saas-ga"}

                                    # Call create_issue with system_fields containing versions
                                    create_issue(
                                        issue_type="bug",
                                        summary="Test bug with version",
                                        priority="Major",
                                        project="AAP",
                                        parent="AAP-64025",
                                        affected_version="ansible-saas-ga",
                                        description="Bug description",
                                        description_file=None,
                                        interactive=False,
                                        create_session=False,
                                        system_fields=system_fields,
                                    )

                                    # Verify the bug was created
                                    assert mock_jira_client.create_issue.called

                                    # Verify versions field was included in the call
                                    call_kwargs = mock_jira_client.create_issue.call_args[1]
                                    # The versions field should be present in the kwargs
                                    assert 'versions' in call_kwargs, "versions field should be passed to JIRA client"
                                    assert call_kwargs['versions'] == "ansible-saas-ga", "versions should have the correct value"
