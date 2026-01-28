"""Dynamic command builder for daf jira create with field discovery."""

import click
from typing import Dict, Any
from devflow.config.loader import ConfigLoader
from devflow.cli.commands.jira_field_utils import (
    parse_field_options,
    add_dynamic_system_field_options,
)


def get_creation_fields_for_command() -> Dict[str, Dict[str, Any]]:
    """Get creation field mappings for command option generation.

    Returns:
        Dictionary of creation field mappings, or empty dict if not cached
    """
    try:
        config_loader = ConfigLoader()
        config = config_loader.load_config()

        if not config or not config.jira:
            return {}

        # Use cached creation field mappings
        return config.jira.field_mappings or {}

    except Exception:
        # Fail silently - the command will still work with --field option
        return {}


def create_jira_create_command():
    """Create the jira create command with dynamic options for custom fields.

    Returns:
        Click command with dynamically generated options from cached creation fields
    """
    # Get available creation fields from config cache
    creation_fields = get_creation_fields_for_command()

    # Build dynamic list of field names for --field option
    # Only truly hardcoded options that won't be generated dynamically
    # Based on JIRA REST API requirements: only project and summary are mandatory
    # See: https://developer.atlassian.com/server/jira/platform/jira-rest-api-example-create-issue-7897248/
    hardcoded_fields = {
        "summary", "project"
    }

    # Get custom field names (excluding hardcoded ones and system fields)
    custom_field_names = sorted([
        field_name for field_name, field_info in creation_fields.items()
        if field_name not in hardcoded_fields
        and field_info.get("id", "").startswith("customfield_")
    ])

    # Build the field names list for help text
    if custom_field_names:
        field_names_text = ", ".join(custom_field_names[:10])
        if len(custom_field_names) > 10:
            field_names_text += f", ... ({len(custom_field_names)} total)"
    else:
        field_names_text = "(run 'daf config refresh-jira-fields' to discover)"

    # Build help text for --field option with available field names
    field_help = f"Set custom field (format: field_name=value). Available fields: {field_names_text}. Example: --field severity=Critical --field size=L"

    # Import json_option decorator
    from devflow.cli.main import json_option

    # Define the base command
    # Only hardcode JIRA API mandatory fields (project, summary) plus special DAF options
    @click.command(name="create")
    @click.argument("issue_type", type=click.Choice(["epic", "spike", "story", "task", "bug"], case_sensitive=False))
    @json_option
    @click.option("--summary", help="Issue summary (will prompt if not provided)")
    @click.option("--project", help="JIRA project key (prompts to save if not in config)")
    @click.option("--parent", help="Parent issue key (epic for story/task/bug, parent epic for epic)")
    @click.option("--description-file", type=click.Path(exists=True), help="File with description (companion to --description)")
    @click.option("--linked-issue", help="Type of relationship (e.g., 'blocks', 'is blocked by', 'relates to'). Use with --issue")
    @click.option("--issue", help="Issue key to link to (e.g., PROJ-12345). Use with --linked-issue")
    @click.option("--field", "-f", multiple=True, help=field_help)
    @click.option("--create-session", is_flag=True, help="Create daf session immediately")
    @click.option("--interactive", is_flag=True, help="Interactive template mode")
    def jira_create_base(
        ctx: click.Context,
        issue_type: str,
        summary: str,
        project: str,
        parent: str,
        description_file: str,
        linked_issue: str,
        issue: str,
        field: tuple,
        create_session: bool,
        interactive: bool,
        **kwargs  # Capture ALL dynamic options (description, priority, components, labels, versions, etc.)
    ):
        from devflow.cli.commands.jira_create_commands import create_issue
        from rich.console import Console

        console = Console()

        # Parse --field options into custom_fields dict
        # Only allow custom fields (customfield_*), not system fields
        # Will exit with error if any system field is used via --field
        creation_fields = get_creation_fields_for_command()
        custom_fields = parse_field_options(field, creation_fields)

        # Separate system fields from kwargs (non-customfield_* fields)
        # These come from dynamically generated CLI options like --description, --priority, --parent, --components, --labels
        system_fields = {}
        for field_name, field_value in kwargs.items():
            if field_value is not None:  # Only include if value was provided
                system_fields[field_name] = field_value

        # Extract output_json from context
        output_json = ctx.obj.get('output_json', False) if ctx.obj else False

        # Extract formerly hardcoded fields from system_fields (now dynamic)
        # Note: DON'T pop these yet - create_issue() needs them in system_fields for validation
        # They will be extracted inside create_issue() after _get_required_system_fields() runs
        # Exception: parent is still a hardcoded parameter because it has special mapping logic
        priority = system_fields.get('priority', None)
        description = system_fields.get('description', None)
        affected_version = system_fields.get('versions', None)

        # Unwrap tuple from Click's multiple=True option if needed
        # --affects-versions creates a tuple like ('ansible-saas-ga',) even with single value
        if affected_version and isinstance(affected_version, tuple) and len(affected_version) > 0:
            affected_version = affected_version[0]

        # Convert components tuple to list (Click's multiple=True creates tuples)
        # --components ansible-saas creates ('ansible-saas',) but we need ['ansible-saas']
        if 'components' in system_fields:
            components_value = system_fields['components']
            if isinstance(components_value, tuple):
                system_fields['components'] = list(components_value)

        # Convert labels tuple to list
        if 'labels' in system_fields:
            labels_value = system_fields['labels']
            if isinstance(labels_value, tuple):
                system_fields['labels'] = list(labels_value)

        # Set default priority based on issue type if not specified
        if not priority:
            priority = "Normal" if issue_type.lower() == "task" else "Major"
            # Add default priority to system_fields so it's available for validation
            system_fields['priority'] = priority

        create_issue(
            issue_type=issue_type.lower(),
            summary=summary,
            priority=priority,
            project=project,
            parent=parent,
            affected_version=affected_version,
            description=description,
            description_file=description_file,
            interactive=interactive,
            create_session=create_session,
            linked_issue=linked_issue,
            issue=issue,
            custom_fields=custom_fields,
            system_fields=system_fields,
            output_json=output_json,
        )

    # Set the docstring dynamically with field names
    jira_create_base.__doc__ = f"""Create a JIRA issue using templates from AGENTS.md.

    ISSUE_TYPE can be: epic, spike, story, task, or bug

    This command dynamically discovers custom fields from your JIRA instance.
    Custom fields are shown below as dedicated options (e.g., --acceptance-criteria).

    You can also use --field with these field names:
      {field_names_text}

    To refresh custom fields: daf config refresh-jira-fields

    \\b
    Examples:
        daf jira create bug --summary "Customer backup fails" --priority Major
        daf jira create story --summary "Implement backup feature" --interactive
        daf jira create task --summary "Update documentation" --parent PROJ-59038
        daf jira create bug --summary "Login error" --create-session
        daf jira create story --summary "New feature" --project PROJ --field workstream=Platform
        daf jira create bug --summary "Critical bug" --field severity=Critical --field size=L
        daf jira create story --summary "New story" --field workstream=Platform --field team=Backend
        daf jira create bug --summary "Production issue" --field workstream=Core --field priority=P1
    """

    # Dynamically add CLI options for JIRA system fields (non-custom fields)
    # Custom fields (customfield_*) are handled via --field key=value
    # System fields (description, priority, components, labels, versions, etc.) get dedicated CLI options
    # Exclude from dynamic generation:
    # - JIRA API mandatory fields: project, summary
    # - issuetype: CLI argument (not option)
    # - parent: Special hardcoded option with mapping logic (maps to epic_link, parent_link, etc. based on issue type)
    hardcoded_fields = {
        "summary", "project", "parent", "issuetype", "issue_type",
        "epic_link", "parent_link"  # Don't generate these - parent option handles them
    }
    jira_create_base = add_dynamic_system_field_options(
        jira_create_base,
        creation_fields,
        hardcoded_fields
    )

    return jira_create_base
