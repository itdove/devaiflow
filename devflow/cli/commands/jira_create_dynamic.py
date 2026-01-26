"""Dynamic command builder for daf jira create with field discovery."""

import click
from typing import Dict, Any
from devflow.config.loader import ConfigLoader


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
    hardcoded_fields = {
        "summary", "description", "priority", "project",
        "parent", "affected_version"
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

    # Define the base command (same as before)
    @click.command(name="create")
    @click.argument("issue_type", type=click.Choice(["epic", "spike", "story", "task", "bug"], case_sensitive=False))
    @json_option
    @click.option("--summary", help="Issue summary (will prompt if not provided)")
    @click.option("--description", help="Issue description")
    @click.option("--description-file", type=click.Path(exists=True), help="File with description")
    @click.option("--priority", type=click.Choice(["Critical", "Major", "Normal", "Minor"]), help="Issue priority (default: Major for bug/story, Normal for task)")
    @click.option("--project", help="JIRA project key (prompts to save if not in config)")
    @click.option("--parent", help="Parent issue key to link to (epic for story/task/bug, parent for sub-task)")
    @click.option("--affected-version", help="Affected version (bugs only, uses config default if not specified)")
    @click.option("--linked-issue", help="Type of relationship (e.g., 'blocks', 'is blocked by', 'relates to'). Use with --issue")
    @click.option("--issue", help="Issue key to link to (e.g., PROJ-12345). Use with --linked-issue")
    @click.option("--field", "-f", multiple=True, help=field_help)
    @click.option("--create-session", is_flag=True, help="Create daf session immediately")
    @click.option("--interactive", is_flag=True, help="Interactive template mode")
    def jira_create_base(
        ctx: click.Context,
        issue_type: str,
        summary: str,
        description: str,
        description_file: str,
        priority: str,
        project: str,
        parent: str,
        affected_version: str,
        linked_issue: str,
        issue: str,
        field: tuple,
        create_session: bool,
        interactive: bool,
        **kwargs  # Capture dynamic options
    ):
        from devflow.cli.commands.jira_create_commands import create_issue
        from rich.console import Console

        console = Console()

        # Set default priority based on issue type if not specified
        if not priority:
            priority = "Normal" if issue_type.lower() == "task" else "Major"

        # Parse --field options into custom_fields dict
        custom_fields = {}
        if field:
            for field_str in field:
                if '=' not in field_str:
                    console.print(f"[yellow]⚠[/yellow] Invalid field format: '{field_str}'. Expected format: field_name=value")
                    continue

                field_name, field_value = field_str.split('=', 1)
                custom_fields[field_name.strip()] = field_value.strip()

        # Separate system fields from kwargs (non-customfield_* fields)
        # These come from dynamically generated CLI options like --components, --labels
        system_fields = {}
        for field_name, field_value in kwargs.items():
            if field_value is not None:  # Only include if value was provided
                system_fields[field_name] = field_value

        # Extract output_json from context
        output_json = ctx.obj.get('output_json', False) if ctx.obj else False

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
    # System fields (components, labels, etc.) get dedicated CLI options

    if creation_fields:
        for field_name, field_info in creation_fields.items():
            field_id = field_info.get("id", "")

            # Skip custom fields - they use --field instead
            if field_id.startswith("customfield_"):
                continue

            # Skip fields that already have dedicated options (summary, description, priority, etc.)
            if field_name in ["summary", "description", "priority", "project", "issuetype", "issue_type", "reporter", "assignee"]:
                continue

            # Add CLI option for this system field
            # Normalize field name for CLI: remove slashes, replace underscores with hyphens
            normalized_field_name = field_name.replace('/', '').replace('_', '-')
            option_name = f"--{normalized_field_name}"
            field_display_name = field_info.get("name", field_name)
            field_type = field_info.get("type", "string")

            # Determine if this is a list field
            is_list = field_type in ["array", "list"]

            help_text = f"{field_display_name}"
            if field_info.get("allowed_values"):
                # Extract component names from allowed_values (which are dict strings)
                # Skip this for now - allowed_values format is complex
                pass

            # Add the option - use field_id as the parameter name since that's what JIRA expects
            jira_create_base = click.option(
                option_name,
                field_id,  # Use field ID (e.g., "components") as the parameter name
                help=help_text,
                multiple=is_list,
                default=None
            )(jira_create_base)

    return jira_create_base
