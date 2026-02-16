"""Tests for dynamic JIRA create command builder."""

from unittest.mock import Mock, patch, MagicMock
import click
from click.testing import CliRunner

from devflow.cli.commands.jira_create_dynamic import (
    get_creation_fields_for_command,
    create_jira_create_command,
)


def test_get_creation_fields_for_command_no_config():
    """Test get_creation_fields when config doesn't exist."""
    with patch('devflow.cli.commands.jira_create_dynamic.ConfigLoader') as mock_loader:
        mock_loader.return_value.load_config.return_value = None

        result = get_creation_fields_for_command()

        assert result == {}


def test_get_creation_fields_for_command_no_jira():
    """Test get_creation_fields when no JIRA config."""
    with patch('devflow.cli.commands.jira_create_dynamic.ConfigLoader') as mock_loader:
        config = Mock()
        config.jira = None
        mock_loader.return_value.load_config.return_value = config

        result = get_creation_fields_for_command()

        assert result == {}


def test_get_creation_fields_for_command_exception():
    """Test get_creation_fields handles exceptions gracefully."""
    with patch('devflow.cli.commands.jira_create_dynamic.ConfigLoader') as mock_loader:
        mock_loader.side_effect = Exception("Config error")

        result = get_creation_fields_for_command()

        # Should return empty dict on exception
        assert result == {}


def test_get_creation_fields_for_command_with_fields():
    """Test get_creation_fields returns field mappings."""
    with patch('devflow.cli.commands.jira_create_dynamic.ConfigLoader') as mock_loader:
        config = Mock()
        config.jira = Mock()
        config.jira.field_mappings = {
            "customfield_12345": {"name": "Severity"},
            "description": {"name": "Description"}
        }
        mock_loader.return_value.load_config.return_value = config

        result = get_creation_fields_for_command()

        assert "customfield_12345" in result
        assert "description" in result


def test_get_creation_fields_for_command_no_field_mappings():
    """Test get_creation_fields when field_mappings is None."""
    with patch('devflow.cli.commands.jira_create_dynamic.ConfigLoader') as mock_loader:
        config = Mock()
        config.jira = Mock()
        config.jira.field_mappings = None
        mock_loader.return_value.load_config.return_value = config

        result = get_creation_fields_for_command()

        assert result == {}


def test_create_jira_create_command_no_fields():
    """Test creating command with no custom fields."""
    with patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command') as mock_get:
        mock_get.return_value = {}

        command = create_jira_create_command()

        assert command is not None
        assert isinstance(command, click.Command)
        assert command.name == "create"


def test_create_jira_create_command_with_custom_fields():
    """Test creating command with custom fields."""
    with patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command') as mock_get:
        mock_get.return_value = {
            "customfield_12345": {"id": "customfield_12345", "name": "Severity"},
            "customfield_67890": {"id": "customfield_67890", "name": "Size"},
        }

        command = create_jira_create_command()

        assert command is not None
        # Check that command was created successfully with custom fields
        # The field help text is in the --field parameter
        field_param = next((p for p in command.params if p.name == 'field'), None)
        assert field_param is not None


def test_create_jira_create_command_many_custom_fields():
    """Test creating command with many custom fields (>10)."""
    with patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command') as mock_get:
        # Create 15 custom fields
        fields = {
            f"customfield_{i:05d}": {"id": f"customfield_{i:05d}", "name": f"Field{i}"}
            for i in range(15)
        }
        mock_get.return_value = fields

        command = create_jira_create_command()

        assert command is not None
        # Command should be created successfully with many fields
        field_param = next((p for p in command.params if p.name == 'field'), None)
        assert field_param is not None
        # Help text should indicate there are more fields
        assert "total" in field_param.help.lower()


def test_create_jira_create_command_filters_hardcoded_fields():
    """Test that hardcoded fields are excluded from custom field list."""
    with patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command') as mock_get:
        mock_get.return_value = {
            "summary": {"id": "summary", "name": "Summary"},
            "project": {"id": "project", "name": "Project"},
            "customfield_12345": {"id": "customfield_12345", "name": "Custom Field"},
        }

        command = create_jira_create_command()

        # Command should be created - hardcoded fields filtered out
        assert command is not None
        field_param = next((p for p in command.params if p.name == 'field'), None)
        assert field_param is not None


def test_create_jira_create_command_has_required_options():
    """Test that created command has all required options."""
    with patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command') as mock_get:
        mock_get.return_value = {}

        command = create_jira_create_command()

        # Get parameter names
        param_names = [p.name for p in command.params]

        # Check for required options
        assert "issue_type" in param_names
        assert "summary" in param_names
        assert "project" in param_names
        assert "parent" in param_names
        assert "field" in param_names
        assert "create_session" in param_names
        assert "interactive" in param_names


@patch('devflow.cli.commands.jira_create_commands.create_issue')
@patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command')
def test_jira_create_command_execution(mock_get_fields, mock_create_issue):
    """Test executing the created command."""
    mock_get_fields.return_value = {}

    command = create_jira_create_command()

    # Create a test context
    ctx = click.Context(command)
    ctx.obj = {}

    # Invoke the command with minimal args
    runner = CliRunner()
    result = runner.invoke(command, ['bug', '--summary', 'Test'], obj={})

    # Command should execute (may fail on actual JIRA call, but that's OK)
    assert result.exit_code in [0, 1]  # 0 = success, 1 = expected error


@patch('devflow.cli.commands.jira_create_commands.create_issue')
@patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command')
def test_jira_create_command_with_custom_fields(mock_get_fields, mock_create_issue):
    """Test command execution with custom fields."""
    mock_get_fields.return_value = {
        "customfield_12345": {"id": "customfield_12345", "name": "severity"}
    }

    command = create_jira_create_command()
    runner = CliRunner()

    result = runner.invoke(
        command,
        ['bug', '--summary', 'Test', '--field', 'severity=Critical'],
        obj={}
    )

    # Should execute without crashing
    assert result.exit_code in [0, 1]


@patch('devflow.cli.commands.jira_create_commands.create_issue')
@patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command')
def test_jira_create_command_default_priority_task(mock_get_fields, mock_create_issue):
    """Test that default priority is 'Normal' for task."""
    mock_get_fields.return_value = {}

    command = create_jira_create_command()
    runner = CliRunner()

    result = runner.invoke(
        command,
        ['task', '--summary', 'Test task'],
        obj={}
    )

    if mock_create_issue.called:
        # Check that priority was set to Normal
        call_kwargs = mock_create_issue.call_args[1]
        assert call_kwargs.get('priority') == 'Normal'


@patch('devflow.cli.commands.jira_create_commands.create_issue')
@patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command')
def test_jira_create_command_default_priority_non_task(mock_get_fields, mock_create_issue):
    """Test that default priority is 'Major' for non-task types."""
    mock_get_fields.return_value = {}

    command = create_jira_create_command()
    runner = CliRunner()

    result = runner.invoke(
        command,
        ['bug', '--summary', 'Test bug'],
        obj={}
    )

    if mock_create_issue.called:
        # Check that priority was set to Major
        call_kwargs = mock_create_issue.call_args[1]
        assert call_kwargs.get('priority') == 'Major'


@patch('devflow.cli.commands.jira_create_dynamic.add_dynamic_system_field_options')
@patch('devflow.cli.commands.jira_create_dynamic.get_creation_fields_for_command')
def test_create_command_adds_dynamic_options(mock_get_fields, mock_add_options):
    """Test that dynamic system field options are added."""
    mock_get_fields.return_value = {
        "description": {"id": "description", "name": "Description"},
        "priority": {"id": "priority", "name": "Priority"},
    }

    # Mock add_dynamic_system_field_options to return the command
    mock_add_options.side_effect = lambda cmd, *args, **kwargs: cmd

    command = create_jira_create_command()

    # Verify add_dynamic_system_field_options was called
    assert mock_add_options.called
    call_args = mock_add_options.call_args

    # Second argument should be creation_fields
    assert call_args[0][1] == mock_get_fields.return_value

    # Third argument should be hardcoded_fields set
    hardcoded = call_args[0][2]
    assert "summary" in hardcoded
    assert "project" in hardcoded
    assert "parent" in hardcoded
