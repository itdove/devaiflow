"""Dynamic jira update command with editable field discovery for --help."""

import click
import sys
from typing import Optional


def create_jira_update_command():
    """Create the jira update command with dynamic options for editable fields.

    When --help is used with an issue key, dynamically discovers and shows
    editable fields for that specific issue.

    Returns:
        Click command with dynamically generated options from editable fields
    """
    # Check if we're in --help mode with an issue key
    editable_fields = {}
    if '--help' in sys.argv and len(sys.argv) >= 4:
        # sys.argv: ['daf', 'jira', 'update', 'PROJ-12345', '--help']
        # Extract issue key (should be at index 3)
        potential_issue_key = sys.argv[3]

        # Check if it looks like a issue key (contains hyphen, not a flag)
        if '-' in potential_issue_key and not potential_issue_key.startswith('--'):
            try:
                from devflow.config.loader import ConfigLoader
                from devflow.jira.client import JiraClient
                from devflow.jira.field_mapper import JiraFieldMapper

                config_loader = ConfigLoader()
                config = config_loader.load_config()

                if config and config.jira:
                    jira_client = JiraClient()
                    field_mapper = JiraFieldMapper(jira_client, config.jira.field_mappings or {})

                    # Discover editable fields for this issue
                    editable_fields = field_mapper.discover_editable_fields(potential_issue_key)
            except Exception:
                # Fail silently - help will still work without dynamic fields
                pass

    # Import json_option decorator
    from devflow.cli.main import json_option

    # Define the base command
    @click.command(name="update")
    @click.argument("issue_key")
    @json_option
    @click.option("--description", help="Update issue description")
    @click.option("--description-file", type=click.Path(exists=True), help="Read description from file")
    @click.option("--priority", type=click.Choice(["Critical", "Major", "Normal", "Minor"]), help="Update priority")
    @click.option("--assignee", help="Update assignee (username or 'none' to clear)")
    @click.option("--summary", help="Update issue summary")
    @click.option("--git-pull-request", help="Add PR/MR URL(s) to git-pull-request field (comma-separated, auto-appends to existing)")
    @click.option("--field", "-f", multiple=True, help="Update custom field (format: field_name=value). Supports any JIRA field. Example: --field epic_link=PROJ-12345 --field severity=Critical")
    def jira_update_base(
        ctx: click.Context,
        issue_key: str,
        description: Optional[str],
        description_file: Optional[str],
        priority: Optional[str],
        assignee: Optional[str],
        summary: Optional[str],
        git_pull_request: Optional[str],
        field: tuple,
        **kwargs  # Capture dynamic options
    ):
        """Update JIRA issue fields.

        ISSUE_KEY is the issue tracker key (e.g., PROJ-12345).

        Use --field for any custom field, or use the dynamically generated options
        shown when you run --help with an issue key (e.g., daf jira update PROJ-12345 --help).

        \b
        Examples:
            daf jira update PROJ-12345 --description "New description text"
            daf jira update PROJ-12345 --description-file /path/to/description.txt
            daf jira update PROJ-12345 --priority Major --assignee jdoe
            daf jira update PROJ-12345 --summary "New summary" --field workstream=Platform
            daf jira update PROJ-12345 --git-pull-request "https://github.com/org/repo/pull/123"
            daf jira update PROJ-12345 --field epic_link=PROJ-59000
            daf jira update PROJ-12345 -f severity=Critical -f size=L -f workstream=Platform

        \b
        To see all editable fields for a specific issue, use:
            daf jira update PROJ-12345 --help
        """
        from devflow.cli.commands.jira_update_command import update_jira_issue
        from rich.console import Console

        console = Console()

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

        # Filter out fields that have explicit parameters to avoid duplicate kwargs
        # Get parameters from locals(), excluding special variables
        explicit_params = set(locals().keys()) - {
            'console', 'custom_fields', 'custom_fields_filtered', 'field_str',
            'field_name', 'field_value', 'field', 'kwargs'
        }

        custom_fields_filtered = {}
        for field_name, field_value in custom_fields.items():
            if field_name in explicit_params:
                # Warn user that this field should use explicit parameter
                console.print(f"[yellow]⚠[/yellow] Field '{field_name}' has a dedicated option. Use --{field_name.replace('_', '-')} instead of --field")
            else:
                # Pass through all other fields
                custom_fields_filtered[field_name] = field_value

        # Extract output_json from context
        output_json = ctx.obj.get('output_json', False) if ctx.obj else False

        update_jira_issue(
            issue_key=issue_key,
            description=description,
            description_file=description_file,
            priority=priority,
            assignee=assignee,
            summary=summary,
            git_pull_request=git_pull_request,
            output_json=output_json,
            **custom_fields_filtered
        )

    # Add dynamic options for editable fields (excluding hardcoded ones)
    hardcoded_fields = {
        "summary", "description", "priority", "assignee",
        "git_pull_request"
    }

    for field_name, field_info in editable_fields.items():
        # Skip hardcoded fields
        if field_name in hardcoded_fields:
            continue

        # Skip non-custom system fields
        if not field_info.get("id", "").startswith("customfield_"):
            continue

        # Create CLI-friendly option name (e.g., "epic_link" -> "--epic-link")
        # Sanitize: remove parentheses and other special chars
        sanitized_name = field_name.replace('_', '-').replace('(', '').replace(')', '').replace('/', '-')
        option_name = f"--{sanitized_name}"

        # Build help text
        field_display_name = field_info.get("name", field_name)
        help_text = f"Update {field_display_name}"

        # Add allowed values to help text if available
        allowed_values = field_info.get("allowed_values", [])
        if allowed_values:
            help_text += f" (choices: {', '.join(allowed_values[:5])}{'...' if len(allowed_values) > 5 else ''})"

        # Add the dynamic option
        jira_update_base = click.option(
            option_name,
            help=help_text,
            default=None
        )(jira_update_base)

    return jira_update_base


# Export the dynamically created command
jira_update = create_jira_update_command()
