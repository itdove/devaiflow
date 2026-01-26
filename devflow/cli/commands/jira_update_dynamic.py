"""Dynamic command builder for daf jira update with field discovery."""

import click
from typing import Dict, Any, Optional
from devflow.config.loader import ConfigLoader
from devflow.jira.client import JiraClient
from devflow.jira.field_mapper import JiraFieldMapper


def get_editable_fields_for_command() -> Dict[str, Dict[str, Any]]:
    """Get editable field mappings for command option generation.

    Returns:
        Dictionary of editable field mappings, or empty dict if discovery fails
    """
    try:
        config_loader = ConfigLoader()
        config = config_loader.load_config()

        if not config or not config.jira:
            return {}

        # Use regular field mappings if available
        if config.jira.field_mappings:
            return config.jira.field_mappings

        # Try loading from backends/jira.json
        from pathlib import Path
        import json
        backends_dir = config_loader.session_home / "backends"
        jira_file = backends_dir / "jira.json"
        if jira_file.exists():
            with open(jira_file) as f:
                jira_config = json.load(f)
                return jira_config.get("field_mappings", {})

        return {}

    except Exception:
        # Fail silently - the command will still work with hardcoded fields
        return {}


def create_jira_update_command():
    """Create the jira update command with dynamic options.

    Returns:
        Click command with dynamically generated options
    """
    # Get available editable fields
    editable_fields = get_editable_fields_for_command()

    # Define the base command
    @click.command(name="update")
    @click.argument("issue_key")
    @click.option("--description", help="Update issue description")
    @click.option("--description-file", type=click.Path(exists=True), help="Read description from file")
    @click.option("--priority", type=click.Choice(["Critical", "Major", "Normal", "Minor"]), help="Update priority")
    @click.option("--assignee", help="Update assignee (username or 'none' to clear)")
    @click.option("--summary", help="Update issue summary")
    @click.option("--git-pull-request", help="Add PR/MR URL(s) to git-pull-request field (comma-separated, auto-appends to existing)")
    @click.option("--linked-issue", help="Type of relationship (e.g., 'blocks', 'is blocked by', 'relates to'). Use with --issue")
    @click.option("--issue", help="Issue key to link to (e.g., PROJ-12345). Use with --linked-issue")
    @click.option("--status", help="Transition ticket to a new status (e.g., 'In Progress', 'Review', 'Closed')")
    @click.option("--field", "-f", multiple=True, help="Update custom field (format: field_name=value). Supports any JIRA field discovered via editmeta API. Example: --field epic_link=PROJ-12345 --field severity=Critical")
    @click.option("--json", "output_json", is_flag=True, help="Output result as JSON")
    def jira_update_base(
        issue_key: str,
        description: Optional[str],
        description_file: Optional[str],
        priority: Optional[str],
        assignee: Optional[str],
        summary: Optional[str],
        git_pull_request: Optional[str],
        status: Optional[str],
        linked_issue: Optional[str],
        issue: Optional[str],
        field: tuple,
        output_json: bool,
        **kwargs
    ):
        """Update JIRA issue fields.

        ISSUE_KEY is the issue tracker key (e.g., PROJ-12345).

        This command dynamically discovers editable fields from your JIRA instance.
        Use --field for any custom field (automatically discovered on first use).

        \b
        Examples:
            daf jira update PROJ-12345 --description "New description text"
            daf jira update PROJ-12345 --description-file /path/to/description.txt
            daf jira update PROJ-12345 --priority Major --assignee jdoe
            daf jira update PROJ-12345 --summary "New summary" --field workstream=Platform
            daf jira update PROJ-12345 --status "In Progress"
            daf jira update PROJ-12345 --status "Review" --priority Major
            daf jira update PROJ-12345 --git-pull-request "https://github.com/org/repo/pull/123"
            daf jira update PROJ-12345 --field epic_link=PROJ-59000
            daf jira update PROJ-12345 -f severity=Critical -f size=L -f workstream=Platform
        """
        from devflow.cli.commands.jira_update_command import update_jira_issue

        # Parse --field options into custom_fields dict
        custom_fields = {}
        if field:
            for field_str in field:
                if '=' not in field_str:
                    from rich.console import Console
                    console = Console()
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

        update_jira_issue(
            issue_key=issue_key,
            description=description,
            description_file=description_file,
            priority=priority,
            assignee=assignee,
            summary=summary,
            git_pull_request=git_pull_request,
            status=status,
            linked_issue=linked_issue,
            issue=issue,
            output_json=output_json,
            custom_fields=custom_fields,
            system_fields=system_fields,
        )

    # Note: We no longer generate dedicated CLI options (like --epic-link, --story-points) for custom fields.
    # All custom fields must be updated using --field field_name=value.
    # This simplifies the CLI and eliminates confusion about which format to use.
    #
    # Old behavior (REMOVED):
    #   daf jira update PROJ-123 --epic-link PROJ-456 --story-points 5
    #
    # New behavior (USE THIS):
    #   daf jira update PROJ-123 --field epic_link=PROJ-456 --field story_points=5

    # Dynamically add CLI options for JIRA system fields (non-custom fields)
    # Custom fields (customfield_*) are handled via --field key=value
    # System fields (components, labels, etc.) get dedicated CLI options

    if editable_fields:
        for field_name, field_info in editable_fields.items():
            field_id = field_info.get("id", "")

            # Skip custom fields - they use --field instead
            if field_id.startswith("customfield_"):
                continue

            # Skip fields that already have dedicated options
            if field_name in ["summary", "description", "priority", "issuetype", "issue_type", "reporter", "assignee", "status"]:
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

            # Add the option - use field_id as the parameter name since that's what JIRA expects
            jira_update_base = click.option(
                option_name,
                field_id,  # Use field ID (e.g., "components") as the parameter name
                help=help_text,
                multiple=is_list,
                default=None
            )(jira_update_base)

    return jira_update_base
