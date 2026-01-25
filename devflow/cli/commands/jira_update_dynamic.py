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

        # Use cached editable mappings if available
        if config.jira.field_mappings_editable:
            return config.jira.field_mappings_editable

        # Otherwise use regular field mappings as fallback
        return config.jira.field_mappings or {}

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

        # Merge with any dynamic options from kwargs
        custom_fields.update(kwargs)

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
            **custom_fields
        )

    # Add dynamic options for editable fields (excluding already hardcoded ones)
    hardcoded_fields = {
        "description", "summary", "priority", "assignee",
        "git_pull_request"
    }

    for field_name, field_info in editable_fields.items():
        # Skip hardcoded fields
        if field_name in hardcoded_fields:
            continue

        # Skip system fields (summary, description, etc. are already handled)
        if not field_info.get("id", "").startswith("customfield_"):
            continue

        # Create CLI-friendly option name (e.g., "epic_link" -> "--epic-link")
        option_name = f"--{field_name.replace('_', '-')}"

        # Build help text
        field_display_name = field_info.get("name", field_name)
        help_text = f"Update {field_display_name}"

        # Add allowed values to help text if available
        allowed_values = field_info.get("allowed_values", [])
        if allowed_values:
            help_text += f" (choices: {', '.join(allowed_values[:5])}{'...' if len(allowed_values) > 5 else ''})"

        # Add the dynamic option
        # Click will automatically convert option_name to parameter name
        # (e.g., "--epic-link" becomes "epic_link")
        jira_update_base = click.option(
            option_name,
            help=help_text,
            default=None
        )(jira_update_base)

    return jira_update_base
