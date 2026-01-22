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
        "summary", "description", "priority", "project", "workstream",
        "parent", "epic_link", "affected_version"
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
    @click.option("--workstream", help="Workstream (prompts to save if not in config)")
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
        workstream: str,
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

        # Merge with any dynamic options from kwargs
        custom_fields.update(kwargs)

        # Extract output_json from context
        output_json = ctx.obj.get('output_json', False) if ctx.obj else False

        create_issue(
            issue_type=issue_type.lower(),
            summary=summary,
            priority=priority,
            project=project,
            workstream=workstream,
            parent=parent,
            affected_version=affected_version,
            description=description,
            description_file=description_file,
            interactive=interactive,
            create_session=create_session,
            linked_issue=linked_issue,
            issue=issue,
            custom_fields=custom_fields,
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
        daf jira create story --summary "New feature" --project PROJ --workstream Platform
        daf jira create bug --summary "Critical bug" --field severity=Critical --field size=L
        daf jira create story --summary "New story" --acceptance-criteria "- Criterion 1"
        daf jira create story --summary "Alternative" --field acceptance_criteria="- Criterion 1"
    """

    # Add dynamic options for creation fields (excluding already hardcoded ones)
    for field_name, field_info in creation_fields.items():
        # Skip hardcoded fields
        if field_name in hardcoded_fields:
            continue

        # Skip system fields
        if not field_info.get("id", "").startswith("customfield_"):
            continue

        # Create CLI-friendly option name (e.g., "story_points" -> "--story-points")
        # Click option names can only contain alphanumeric characters, underscores, and hyphens
        # and must not start with a number
        import re

        # Step 1: Replace common separators with hyphens
        sanitized_name = field_name.replace('_', '-').replace('/', '-').replace('.', '-')

        # Step 2: Remove all characters that aren't alphanumeric or hyphens
        sanitized_name = re.sub(r"[^a-zA-Z0-9-]", '', sanitized_name)

        # Step 3: Collapse multiple consecutive hyphens into one
        sanitized_name = re.sub(r'-+', '-', sanitized_name)

        # Step 4: Remove leading/trailing hyphens
        sanitized_name = sanitized_name.strip('-')

        # Step 5: If name starts with a number or is empty, prefix with 'field-'
        if not sanitized_name or sanitized_name[0].isdigit():
            sanitized_name = f"field-{sanitized_name}"

        option_name = f"--{sanitized_name}"

        # Build help text
        field_display_name = field_info.get("name", field_name)
        help_text = f"Set {field_display_name}"

        # Add allowed values to help text if available
        allowed_values = field_info.get("allowed_values", [])
        if allowed_values:
            help_text += f" (choices: {', '.join(allowed_values[:5])}{'...' if len(allowed_values) > 5 else ''})"

        # Add required info to help text
        required_for = field_info.get("required_for", [])
        if required_for:
            help_text += f" [required for: {', '.join(required_for)}]"

        # Add the dynamic option
        jira_create_base = click.option(
            option_name,
            help=help_text,
            default=None
        )(jira_create_base)

    return jira_create_base
