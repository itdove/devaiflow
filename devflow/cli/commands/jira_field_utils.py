"""Common utilities for JIRA field processing in dynamic commands."""

import sys
from typing import Dict, Any, Tuple
from rich.console import Console

console = Console()


def parse_field_options(
    field_options: tuple,
    field_mappings: Dict[str, Dict[str, Any]]
) -> Dict[str, str]:
    """Parse --field options and validate they are custom fields only.

    This function validates that:
    - Field format is correct (field_name=value)
    - System fields are NOT used via --field (ERROR and exit)
    - Only custom fields (customfield_*) can be set via --field

    Args:
        field_options: Tuple of field strings from --field options
        field_mappings: Dictionary of field mappings from config

    Returns:
        Dict of valid custom field name -> value pairs

    Raises:
        SystemExit: If any system field is used via --field
    """
    custom_fields = {}

    if not field_options:
        return custom_fields

    for field_str in field_options:
        # Validate format
        if '=' not in field_str:
            console.print(
                f"[red]✗[/red] Invalid field format: '{field_str}'. "
                f"Expected format: field_name=value"
            )
            sys.exit(1)

        field_name, field_value = field_str.split('=', 1)
        field_name = field_name.strip()
        field_value = field_value.strip()

        # Get field info to check if it's a custom field
        field_info = field_mappings.get(field_name, {})
        field_id = field_info.get("id", "")

        # Only allow custom fields via --field
        # System fields should use dedicated CLI options (--reporter, --assignee, etc.)
        if field_id and not field_id.startswith("customfield_"):
            console.print(
                f"[red]✗[/red] '{field_name}' is a system field. "
                f"Use --{field_name.replace('_', '-')} option instead of --field"
            )
            console.print(
                f"[dim]Example: --{field_name.replace('_', '-')} {field_value}[/dim]"
            )
            console.print(
                f"[dim]Note: --field is only for custom fields (customfield_*)[/dim]"
            )
            sys.exit(1)

        custom_fields[field_name] = field_value

    return custom_fields


def should_skip_field_for_dynamic_option(field_name: str, field_id: str, hardcoded_fields: set) -> bool:
    """Determine if a field should be skipped for dynamic CLI option generation.

    Args:
        field_name: Normalized field name (e.g., "reporter", "component/s")
        field_id: JIRA field ID (e.g., "reporter", "customfield_12345")
        hardcoded_fields: Set of field names that have hardcoded CLI options

    Returns:
        True if field should be skipped, False if it should generate a dynamic option
    """
    # Skip custom fields - they use --field instead
    if field_id.startswith("customfield_"):
        return True

    # Skip fields that already have dedicated hardcoded options in the base command
    if field_name in hardcoded_fields:
        return True

    return False


def add_dynamic_system_field_options(command, field_mappings: Dict[str, Dict[str, Any]], hardcoded_fields: set):
    """Add dynamic CLI options for JIRA system fields.

    This function generates CLI options for system fields (non-custom fields) that don't
    have hardcoded options. Custom fields (customfield_*) are handled via --field key=value.

    Args:
        command: Click command to add options to
        field_mappings: Dictionary of field mappings from config
        hardcoded_fields: Set of field names that have hardcoded CLI options

    Returns:
        Updated command with dynamic options added
    """
    import click

    if not field_mappings:
        return command

    for field_name, field_info in field_mappings.items():
        field_id = field_info.get("id", "")

        # Skip fields that shouldn't generate dynamic options
        if should_skip_field_for_dynamic_option(field_name, field_id, hardcoded_fields):
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
        command = click.option(
            option_name,
            field_id,  # Use field ID (e.g., "components") as the parameter name
            help=help_text,
            multiple=is_list,
            default=None
        )(command)

    return command
