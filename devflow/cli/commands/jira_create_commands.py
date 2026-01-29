"""Implementation of 'daf jira create' command."""

import sys
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm

from devflow.cli.utils import output_json as json_output, is_json_mode, console_print, require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.jira.client import JiraClient
from devflow.jira.field_mapper import JiraFieldMapper
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError

console = Console()


# JIRA issue templates from AGENTS.md
BUG_TEMPLATE = """*Description*

_<what is happening, why are you requesting this update>_

*Steps to Reproduce*

_<list explicit steps to reproduce, for docs bugs, include the error/issue>_

*Actual Behavior*

_<what is currently happening, for docs bugs include link(s) to relevant section(s)>_

*Expected Behavior*

_<what should happen? for docs bugs, provide suggestion(s) of how to improve the content>_

*Additional Context*

<_Provide any related communication on this issue._>"""


STORY_TEMPLATE = """h3. *User Story*

Format: "as a <type of user> I want <some goal> so that <some reason>"

h3. *Supporting documentation*

<include links to technical docs, diagrams, etc>"""


TASK_TEMPLATE = """h3. *Problem Description*

<what is the issue, what is being asked, what is expected>

h3. *Supporting documentation*"""


EPIC_TEMPLATE = """h2. *Background*

{color:#0747a6}_Initial completion during New status and then remove this blue text._{color}

<fill out any context, value prop, description needed>
h2. *User Stories*

{color:#0747a6}_Initial completion during New status and then remove this blue text._{color}

Format: "as a <type of user> I want <some goal> so that <some reason>"
h2. *Supporting documentation*

{color:#0747a6}_Initial completion during New status and then remove this blue text._{color}

<include links to technical docs, diagrams, etc>
h2. *Definition of Done*

{color:#0747a6}_Initial completion during Refinement status and then remove this blue text._{color}

*Should be reviewed and updated by the team, based on each team agreement and conversation during backlog refinement.*

*< [REPLACE AND COPY FROM THIS GUIDANCE DOC>|https://docs.google.com/document/d/14vYX4WKLU__2IRUmvrSJ8TvLQjkZAb_eS_aAXxWJ5lM/edit#heading=h.3shchgrvtaaj]*
 * Item 1
 * Item 2

h2. *Acceptance Criteria*

{color:#0747a6}_COPY THIS INTO THE ACCEPTANCE CRITERIA FIELD during New status and then remove this section._ {color}
h3. Requirements

<Replace these with the functional requirements to deliver this work>
 * Item 1
 * Item 2
 * Item 3

h3. End to End Test

<Define at least one end-to-end test that demonstrates how this capability should work from the customers perspective>
 # Step 1
 # Step 2
 # Step 3
 # Step 4

If the previous steps are possible, then the test succeeds.  Otherwise, the test fails."""


SPIKE_TEMPLATE = """h3. *User Story*

Format: "as a <type of user> I want <some goal> so that <some reason>"
h3. *Supporting documentation*

<include links to technical docs, diagrams, etc>
h3. *Definition of Done*

{color:#0747a6}_Initial completion during Refinement status and then remove this blue text._{color}

*Should be reviewed and updated by the team, based on each team agreement and conversation during backlog refinement.*

*< [REPLACE AND COPY FROM THIS GUIDANCE DOC>|https://docs.google.com/document/d/14vYX4WKLU__2IRUmvrSJ8TvLQjkZAb_eS_aAXxWJ5lM/edit#heading=h.3shchgrvtaaj]*
 * Item 1
 * Item 2

h3. *Acceptance Criteria*

{color:#0747a6}_COPY THIS INTO THE ACCEPTANCE CRITERIA FIELD during Refinement status and then remove this section._ {color}
h3. Requirements

<Replace these with the functional requirements to deliver this work>
 * Item 1
 * Item 2
 * Item 3

h3. End to End Test

<Define at least one end-to-end test that demonstrates how this capability should work from the customers perspective>
 # Step 1
 # Step 2
 # Step 3
 # Step 4

If the previous steps are possible, then the test succeeds.  Otherwise, the test fails."""


def _ensure_field_mappings(config, config_loader) -> JiraFieldMapper:
    """Ensure JIRA field mappings exist, discover if needed.

    Args:
        config: Config object
        config_loader: ConfigLoader instance

    Returns:
        JiraFieldMapper instance with loaded/discovered field mappings
    """
    from datetime import datetime

    jira_client = JiraClient()

    # Check if field mappings exist and are fresh
    if config.jira.field_mappings and not JiraFieldMapper(jira_client, config.jira.field_mappings).is_cache_stale(
        config.jira.field_cache_timestamp
    ):
        console_print("[dim]Using cached field mappings from config[/dim]")
        return JiraFieldMapper(jira_client, config.jira.field_mappings)

    # Need to discover fields
    console_print("\nDiscovering JIRA custom field mappings...")

    try:
        field_mapper = JiraFieldMapper(jira_client)
        field_mappings = field_mapper.discover_fields(config.jira.project)

        console_print(f"[green]✓[/green] Discovered and cached {len(field_mappings)} custom fields")

        # Save to config
        config.jira.field_mappings = field_mappings
        config.jira.field_cache_timestamp = datetime.now().isoformat()
        config_loader.save_config(config)

        console_print("[green]ℹ[/green] Field mappings saved to config.json\n")

        return JiraFieldMapper(jira_client, field_mappings)

    except Exception as e:
        console_print(f"[yellow]⚠[/yellow] Could not cache field mappings: {e}")
        console_print("  Continuing with known field defaults...\n")
        # Return mapper with empty cache (will use fallback defaults in create methods)
        return JiraFieldMapper(jira_client, {})


def _get_required_custom_fields(
    config,
    config_loader,
    field_mapper,
    issue_type: str,
    flag_values: Optional[dict] = None
) -> dict:
    """Get all required custom field values for the given issue type.

    This function loops through all custom fields in field_mappings and collects
    values for fields that are required for the specified issue type. It uses
    field_mappings['field_name']['required_for'] to determine which fields are needed.

    Logic for each required field:
    1. If flag value provided, use it (prompt to save if different from config)
    2. Else if value in custom_field_defaults, use it
    3. Else prompt user (using field_mapper for allowed values)

    Args:
        config: Config object
        config_loader: ConfigLoader instance
        field_mapper: JiraFieldMapper instance
        issue_type: JIRA issue type (e.g., "Bug", "Story", "Task")
        flag_values: Optional dict of field values from command flags (e.g., {"workstream": "Platform"})

    Returns:
        Dictionary of {field_name: value} for all required custom fields
    """
    from rich.prompt import Prompt, Confirm

    flag_values = flag_values or {}
    custom_fields = {}

    # Get custom field defaults from config
    config_defaults = config.jira.custom_field_defaults or {}

    # Get all field mappings from the field_mapper
    if not field_mapper.field_mappings:
        return custom_fields

    # Handle case where field_mappings might be a Mock or not a dict
    try:
        field_mappings_dict = dict(field_mapper.field_mappings)
    except (AttributeError, TypeError, ValueError):
        # field_mappings is not a dict (e.g., Mock object in tests)
        return custom_fields

    # JIRA system fields that are handled separately by create_issue function
    # These should NOT be prompted for in _get_required_custom_fields
    # Only include: API mandatory fields (summary, project) + issuetype + special system fields
    system_fields = {
        "summary", "project",
        "issue_type", "issuetype", "reporter", "assignee",
        "affected_version", "fixVersions", "versions", "affects_version/s",  # Version fields
        "components", "component/s", "labels", "label/s",  # System fields with dedicated CLI options
        "description", "priority"  # Already handled as parameters to create_issue
    }

    # Loop through all fields in field_mappings
    for field_name, field_info in field_mappings_dict.items():
        # Skip JIRA system fields - these are handled separately
        if field_name in system_fields:
            continue

        # Check if this field is required for the issue type
        required_for = field_info.get("required_for", [])
        if issue_type not in required_for:
            continue

        # This field is required - get its value
        flag_value = flag_values.get(field_name)
        config_value = config_defaults.get(field_name)

        # Case 1: Flag provided
        if flag_value:
            # Check if different from config
            if config_value and config_value != flag_value:
                console_print(f"[dim]ℹ Current {field_name} in config: \"{config_value}\"[/dim]")
                console_print(f"[dim]ℹ Command uses {field_name}: \"{flag_value}\"[/dim]")
                console_print(f"[dim]Not updating config (use 'daf config tui' to change default)[/dim]")
                console_print()

            custom_fields[field_name] = flag_value
            continue

        # Case 2: Value in config defaults
        if config_value:
            console_print(f"[dim]Using {field_name} from config: \"{config_value}\"[/dim]")
            custom_fields[field_name] = config_value
            continue

        # Case 3: Prompt user (only in interactive mode)
        if not is_json_mode():
            allowed_values = field_info.get("allowed_values", [])

            if allowed_values:
                console_print(f"\n[bold]Available {field_name} values:[/bold]")
                for val in allowed_values:
                    console_print(f"  - {val}")
                console_print()

                field_value = Prompt.ask(
                    f"Select {field_name}",
                    choices=allowed_values,
                    default=allowed_values[0] if allowed_values else None
                )
            else:
                field_value = Prompt.ask(f"Enter {field_name} value")
        else:
            # JSON mode - return error for missing required field
            json_output(
                success=False,
                error={
                    "code": "MISSING_REQUIRED_FIELD",
                    "message": f"Required field '{field_name}' is missing. Use --field {field_name}=value or --{field_name} flag."
                }
            )
            return None

        if field_value:
            # Save to config
            if not config.jira.custom_field_defaults:
                config.jira.custom_field_defaults = {}
            config.jira.custom_field_defaults[field_name] = field_value
            config_loader.save_config(config)
            console_print(f"\n[green]ℹ[/green] {field_name.title()} set to \"{field_value}\" and saved to config")
            console_print(f"[dim]You can change it later with: daf config tui[/dim]\n")

            custom_fields[field_name] = field_value
        else:
            # Field is required but user didn't provide - will fail later
            console_print(f"[red]✗[/red] {field_name.title()} is required for {issue_type} creation")
            return None

    return custom_fields


def _get_project(config, config_loader, flag_value: Optional[str]) -> Optional[str]:
    """Get project value from flag, config, or prompt.

    Logic:
    1. If --project flag provided, use it (prompt to save if different from config)
    2. Else if project in config, use it
    3. Else prompt user for project key

    Args:
        config: Config object
        config_loader: ConfigLoader instance
        flag_value: Value from --project flag (or None)

    Returns:
        Project key to use, or None if cancelled
    """
    # Case 1: Flag provided
    if flag_value:
        # Check if different from config
        if config.jira.project and config.jira.project != flag_value:
            console_print(f"[dim]ℹ Current project in config: \"{config.jira.project}\"[/dim]")
            console_print(f"[dim]ℹ Command uses project: \"{flag_value}\"[/dim]")
            console_print(f"[dim]Not updating config (use 'daf config tui' to change default)[/dim]")
            console_print()

        return flag_value

    # Case 2: Project in config
    if config.jira.project:
        console_print(f"[dim]Using project from config: \"{config.jira.project}\"[/dim]")
        return config.jira.project

    # Case 3: Prompt user
    console_print("\n[yellow]⚠[/yellow] No JIRA project configured.")
    console_print("[dim]Examples: PROJ, DEVOPS[/dim]")
    project_key = Prompt.ask("[bold]Enter JIRA project key[/bold]") if not is_json_mode() else None

    if project_key and project_key.strip():
        project_key = project_key.strip().upper()
        # Save to config
        config.jira.project = project_key
        config_loader.save_config(config)
        console_print(f"\n[green]ℹ[/green] Project set to \"{project_key}\" and saved to config.json")
        console_print(f"[dim]You can change it later with: daf config set --project <PROJECT_KEY>[/dim]\n")
        return project_key

    return None


def _get_required_system_fields(
    config,
    config_loader,
    field_mapper,
    issue_type: str,
    flag_values: Optional[dict] = None
) -> dict:
    """Get all required system field values for the given issue type.

    This function checks field_mappings for system fields (non-custom fields like
    components, labels, etc.) that are marked as required for the specified issue type.

    Logic for each required system field:
    1. If flag value provided, use it (prompt to save if different from config)
    2. Else if value in system_field_defaults, use it
    3. Else prompt user (only in interactive mode)

    Args:
        config: Config object
        config_loader: ConfigLoader instance
        field_mapper: JiraFieldMapper instance
        issue_type: JIRA issue type (e.g., "Bug", "Story", "Task")
        flag_values: Optional dict of field values from command flags (e.g., {"components": ["backend"]})

    Returns:
        Dictionary of {field_name: value} for all required system fields
    """
    from rich.prompt import Prompt, Confirm

    flag_values = flag_values or {}
    system_fields = {}

    # Get system field defaults from config
    config_defaults = config.jira.system_field_defaults or {}

    # Get all field mappings from the field_mapper
    if not field_mapper.field_mappings:
        return system_fields

    # Handle case where field_mappings might be a Mock or not a dict
    try:
        field_mappings_dict = dict(field_mapper.field_mappings)
    except (AttributeError, TypeError, ValueError):
        # field_mappings is not a dict (e.g., Mock object in tests)
        return system_fields

    # Fields that are always provided by the caller or have automatic defaults
    # Based on JIRA REST API: only project and summary are mandatory for issue creation
    # See: https://developer.atlassian.com/server/jira/platform/jira-rest-api-example-create-issue-7897248/
    # - summary, project: API mandatory fields (hardcoded CLI options)
    # - issuetype: Specified as CLI argument (not a flag)
    # - reporter: Automatically set to authenticated user if not provided
    # - assignee: Optional field, automatically set in some JIRA configs
    ALWAYS_PROVIDED_FIELDS = {"summary", "project", "issuetype", "issue_type", "reporter", "assignee"}

    # First pass: Add all fields that were provided via CLI flags (flag_values)
    # This ensures we don't lose CLI-provided values even if fields aren't marked as required
    for field_key, flag_value in flag_values.items():
        # Skip None, empty tuple (from Click multiple=True with no value), and empty list
        if flag_value is not None and flag_value != () and flag_value != [] and flag_value != "":
            system_fields[field_key] = flag_value

    # Second pass: Loop through field_mappings to handle required fields
    for field_name, field_info in field_mappings_dict.items():
        # Get the field ID to determine if it's a system field
        field_id = field_info.get("id")
        if not field_id:
            continue

        # Skip custom fields (customfield_*) - those are handled by _get_required_custom_fields
        if isinstance(field_id, str) and field_id.startswith("customfield_"):
            continue

        # Skip fields that are always provided by the caller
        if field_id in ALWAYS_PROVIDED_FIELDS or field_name in ALWAYS_PROVIDED_FIELDS:
            continue

        # Skip if this field was already added from flag_values in first pass
        field_key = field_id
        # Also check field_name in case the key differs (e.g., "component/s" vs "components")
        if field_key in system_fields or field_name in system_fields or field_id in flag_values or field_name in flag_values:
            continue

        # Check if this field is required for the issue type
        required_for = field_info.get("required_for", [])
        if issue_type not in required_for:
            continue

        # This field is required - get its value
        # Use field_id as the key for system fields (e.g., "components", "labels")
        # Note: flag values are already handled in first pass above
        # Check both field_key (field_id) and field_name to handle cases where config
        # stores the original field_name (e.g., "component/s") but CLI uses normalized
        # field_id (e.g., "components")
        config_value = config_defaults.get(field_key) or config_defaults.get(field_name)

        # Case 1: Value in config defaults
        if config_value is not None:
            console_print(f"[dim]Using {field_key} from config: \"{config_value}\"[/dim]")
            system_fields[field_key] = config_value
            continue

        # Case 2: Prompt user (only in interactive mode)
        if not is_json_mode():
            allowed_values = field_info.get("allowed_values", [])

            if allowed_values:
                console_print(f"\n[bold]Available {field_key} values:[/bold]")
                for val in allowed_values:
                    console_print(f"  - {val}")
                console_print()

                field_value = Prompt.ask(
                    f"Select {field_key}",
                    choices=allowed_values,
                    default=allowed_values[0] if allowed_values else None
                )
            else:
                field_value = Prompt.ask(f"Enter {field_key} value")
        else:
            # JSON mode - return error for missing required field
            json_output(
                success=False,
                error={
                    "code": "MISSING_REQUIRED_FIELD",
                    "message": f"Required field '{field_key}' is missing. Use --{field_key} flag or configure in system_field_defaults."
                }
            )
            return None

        if field_value:
            # Save to config
            if not config.jira.system_field_defaults:
                config.jira.system_field_defaults = {}
            config.jira.system_field_defaults[field_key] = field_value
            config_loader.save_config(config)
            console_print(f"\n[green]ℹ[/green] {field_key.title()} set to \"{field_value}\" and saved to config")
            console_print(f"[dim]You can change it later with: daf config tui[/dim]\n")

            system_fields[field_key] = field_value
        else:
            # Field is required but user didn't provide - will fail later
            console_print(f"[red]✗[/red] {field_key.title()} is required for {issue_type} creation")
            return None

    return system_fields


def _get_affected_version(config, config_loader, field_mapper, flag_value: Optional[str]) -> Optional[str]:
    """Get affected version value from flag, config, or prompt.

    Logic:
    1. If --affected-version flag provided, validate and use it
    2. Else if affected_version in config, validate and use it
    3. Else if field is required, prompt user
    4. Else return None (field is optional and not provided)

    Args:
        config: Config object
        config_loader: ConfigLoader instance
        field_mapper: JiraFieldMapper instance (for accessing allowed_values)
        flag_value: Value from --affected-version flag (or None)

    Returns:
        Affected version to use, or None if field is optional and not provided
    """
    # Case 1: Flag provided
    if flag_value:
        # Validate flag value against allowed_values
        from devflow.jira.utils import validate_affected_version
        if not validate_affected_version(flag_value, field_mapper):
            console_print(f"[red]✗[/red] Invalid affected version: \"{flag_value}\"")
            console_print(f"[dim]This version is not in the allowed versions list.[/dim]")
            console_print(f"[dim]Please check the allowed versions in your JIRA project.[/dim]")
            sys.exit(1)

        # Check if different from config
        if config.jira.affected_version and config.jira.affected_version != flag_value:
            console_print(f"[dim]ℹ Current affected version in config: \"{config.jira.affected_version}\"[/dim]")
            console_print(f"[dim]ℹ Command uses affected version: \"{flag_value}\"[/dim]")
            console_print(f"[dim]Not updating config (use 'daf config tui' to change default)[/dim]")
            console_print()

        return flag_value

    # Case 2: Affected version in config
    if config.jira.affected_version:
        # Validate config value against allowed_values
        from devflow.jira.utils import validate_affected_version
        if not validate_affected_version(config.jira.affected_version, field_mapper):
            console_print(f"[yellow]⚠[/yellow] Configured affected version \"{config.jira.affected_version}\" is not in the allowed versions list.")
            console_print(f"[dim]Please select a valid version from the list below.[/dim]")
            # Fall through to Case 3 (prompt user)
        else:
            console_print(f"[dim]Using affected version from config: \"{config.jira.affected_version}\"[/dim]")
            return config.jira.affected_version

    # Case 3: Check if field is required before prompting
    from devflow.jira.utils import is_version_field_required
    field_required = is_version_field_required(field_mapper)

    # Only prompt if field is required
    if not field_required:
        # Field is optional and not provided - return None
        return None

    # Field is required - prompt user
    # Skip prompt in mock mode (use default silently)
    from devflow.utils import is_mock_mode
    if is_mock_mode():
        affected_version = "v1.0.0"
    elif not is_json_mode():
        # Use common prompt function
        from devflow.jira.utils import prompt_for_affected_version
        affected_version = prompt_for_affected_version(field_mapper)
    else:
        affected_version = "v1.0.0"

    if affected_version and affected_version.strip():
        affected_version = affected_version.strip()
        # Save to config
        config.jira.affected_version = affected_version
        config_loader.save_config(config)
        console_print(f"\n[green]ℹ[/green] Affected version set to \"{affected_version}\" and saved to config.json")
        console_print(f"[dim]You can change it later with: daf config tui <VERSION>[/dim]\n")
        return affected_version

    # Fallback to default if user somehow provides empty string
    return "v1.0.0"


def _get_description(description_arg: Optional[str], description_file: Optional[str], template: str, interactive: bool) -> str:
    """Get issue description from arguments, file, or interactive template.

    Args:
        description_arg: Description from --description flag
        description_file: Path from --description-file flag
        template: Template string to use for interactive mode
        interactive: Whether to use interactive mode

    Returns:
        Description string
    """
    # Priority: description_file > description_arg > interactive mode
    if description_file:
        try:
            with open(description_file, 'r') as f:
                return f.read()
        except Exception as e:
            console.print(f"[red]✗[/red] Could not read file {description_file}: {e}")
            sys.exit(1)

    if description_arg:
        return description_arg

    # Interactive mode or use template
    if interactive:
        console.print("\n[bold]Fill in the template (press Ctrl+D or Ctrl+Z when done):[/bold]")
        console.print(template)
        console.print("\n[dim]Enter your description:[/dim]")

        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass

        return "\n".join(lines)
    else:
        # Use template as-is if no other input provided
        return template


def create_issue(
    issue_type: str,
    summary: Optional[str],
    priority: str,
    project: Optional[str],
    parent: Optional[str],
    affected_version: str,
    description: Optional[str],
    description_file: Optional[str],
    interactive: bool,
    create_session: bool,
    linked_issue: Optional[str] = None,
    issue: Optional[str] = None,
    custom_fields: Optional[dict] = None,
    system_fields: Optional[dict] = None,
    output_json: bool = False,
) -> None:
    """Create a JIRA issue (unified function for bug/story/task).

    Args:
        issue_type: Type of issue (bug, story, task)
        summary: Issue summary (or None to prompt)
        priority: Issue priority
        project: Project key from --project flag (or None)
        parent: Parent issue key to link to (epic for story/task/bug, parent for sub-task)
        affected_version: Affected version (bugs only)
        description: Description from --description flag (or None)
        description_file: Path to description file (or None)
        interactive: Use interactive template mode
        create_session: Create daf session after creation
        linked_issue: Type of relationship (e.g., 'blocks', 'is blocked by', 'relates to')
        issue: Issue key to link to (e.g., PROJ-12345)
        custom_fields: Custom field values from --field options (e.g., {"workstream": "Platform", "team": "Backend"})
        system_fields: JIRA system field values from CLI options (e.g., {"components": ["ansible-saas"], "labels": ["backend"]})
    """
    # Map issue type to template and client method
    ISSUE_TYPE_CONFIG = {
        "epic": {
            "template": EPIC_TEMPLATE,
            "label": "Epic",
            "client_method": "create_epic",
            "uses_affected_version": False,
            "jira_issue_type": "Epic",
        },
        "spike": {
            "template": SPIKE_TEMPLATE,
            "label": "Spike",
            "client_method": "create_spike",
            "uses_affected_version": False,
            "jira_issue_type": "Spike",
        },
        "story": {
            "template": STORY_TEMPLATE,
            "label": "Story",
            "client_method": "create_story",
            "uses_affected_version": False,
            "jira_issue_type": "Story",
        },
        "task": {
            "template": TASK_TEMPLATE,
            "label": "Task",
            "client_method": "create_task",
            "uses_affected_version": False,
            "jira_issue_type": "Task",
        },
        "bug": {
            "template": BUG_TEMPLATE,
            "label": "Bug",
            "client_method": "create_bug",
            "uses_affected_version": True,
            "jira_issue_type": "Bug",
        },
    }

    type_config = ISSUE_TYPE_CONFIG.get(issue_type)
    if not type_config:
        console.print(f"[red]✗[/red] Invalid issue type: {issue_type}")
        sys.exit(1)

    # Normalize issue type to match JIRA's title-case convention
    # JIRA returns issue types as title-case ("Bug", "Story", "Task") in field metadata
    # CLI accepts lowercase ("bug", "story", "task")
    # Normalize once here so all subsequent code uses the correct case
    issue_type = type_config["jira_issue_type"]

    try:
        # Load config
        config_loader = ConfigLoader()
        config = config_loader.load_config()

        if not config or not config.jira:
            console.print("[red]✗[/red] JIRA not configured. Run [cyan]daf init[/cyan] first.")
            sys.exit(1)

        # Get project first (needed for field discovery)
        resolved_project = _get_project(config, config_loader, project)
        if not resolved_project:
            console.print(f"[red]✗[/red] Project is required for {issue_type} creation")
            sys.exit(1)

        # Ensure field mappings
        field_mapper = _ensure_field_mappings(config, config_loader)

        # Get all required system fields for this issue type
        # Pass system_fields from CLI options as flag values
        required_system_fields = _get_required_system_fields(
            config, config_loader, field_mapper, issue_type, system_fields or {}
        )
        if required_system_fields is None:
            # User cancelled or required field missing
            sys.exit(1)

        # Get all required custom fields for this issue type
        # Use custom_fields from --field options as flag values
        # Also include summary if provided (summary might be in field_mappings as a required field)
        flag_values = dict(custom_fields or {})
        if summary:
            flag_values['summary'] = summary
        required_custom_fields = _get_required_custom_fields(
            config, config_loader, field_mapper, issue_type, flag_values
        )
        if required_custom_fields is None:
            # User cancelled or required field missing
            sys.exit(1)

        # Get affected version (for bugs only)
        resolved_affected_version = None
        if type_config["uses_affected_version"]:
            resolved_affected_version = _get_affected_version(config, config_loader, field_mapper, affected_version)

        # Validate parent ticket if provided
        if parent:
            console_print(f"[dim]Validating parent ticket: {parent}[/dim]")
            from devflow.jira.utils import validate_jira_ticket

            parent_ticket = validate_jira_ticket(parent, client=None)
            if not parent_ticket:
                # Error already displayed by validate_jira_ticket
                console_print(f"[red]✗[/red] Cannot create {issue_type} with invalid parent")
                if is_json_mode():
                    json_output(
                        success=False,
                        error={
                            "code": "INVALID_PARENT",
                            "message": f"Parent ticket {parent} not found or validation failed"
                        }
                    )
                sys.exit(1)

            console_print(f"[green]✓[/green] Parent ticket validated: {parent}")

        # Prompt for summary if not provided
        if not summary:
            if not is_json_mode():
                summary = Prompt.ask(f"\n[bold]{type_config['label']} summary[/bold]")
                if not summary or not summary.strip():
                    console.print("[red]✗[/red] Summary is required")
                    sys.exit(1)
                summary = summary.strip()
            else:
                # JSON mode - return error for missing required field
                json_output(
                    success=False,
                    error={
                        "code": "MISSING_REQUIRED_FIELD",
                        "message": "Summary is required. Use --summary flag."
                    }
                )
                sys.exit(1)

        # Get description
        issue_description = _get_description(description, description_file, type_config["template"], interactive)

        # Create issue
        jira_client = JiraClient()
        client_method = getattr(jira_client, type_config["client_method"])

        # Build kwargs based on issue type
        create_kwargs = {
            "summary": summary,
            "description": issue_description,
            "priority": priority,
            "project_key": resolved_project,
            "field_mapper": field_mapper,
            "parent": parent,
            "required_custom_fields": {},  # Empty - custom fields will be passed via **kwargs below
        }

        # Add affected_version only for bugs
        if type_config["uses_affected_version"]:
            create_kwargs["affected_version"] = resolved_affected_version

        # Apply custom field defaults from team.json (merged with CLI --field options)
        # Merge in this order (later values override earlier):
        # 1. config.jira.custom_field_defaults
        # 2. required_custom_fields (from field_mappings required_for)
        # 3. custom_fields (from CLI --field options)
        # Filter out system fields that shouldn't be in custom_field_defaults
        SYSTEM_FIELDS_FILTER = {"issue_type", "issuetype", "project", "summary", "description",
                                "priority", "reporter", "assignee", "created", "updated"}
        merged_custom_fields = {}
        if config.jira.custom_field_defaults:
            for field_name, field_value in config.jira.custom_field_defaults.items():
                if field_name not in SYSTEM_FIELDS_FILTER:
                    merged_custom_fields[field_name] = field_value
        if required_custom_fields:
            merged_custom_fields.update(required_custom_fields)
        if custom_fields:
            merged_custom_fields.update(custom_fields)

        # Handle dynamically discovered custom fields
        if merged_custom_fields:
            # Discover creation fields for this project if not cached
            if not config.jira.field_mappings:
                console.print(f"[dim]Discovering creation fields for {resolved_project}...[/dim]")
                try:
                    from datetime import datetime
                    creation_mappings = field_mapper.discover_fields(resolved_project)
                    # Save to config for future use
                    config.jira.field_mappings = creation_mappings
                    config.jira.field_cache_timestamp = datetime.now().isoformat()
                    config_loader.save_config(config)
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] Could not discover creation fields: {e}")
                    console.print("  Using field_mappings cache instead")

            # Use creation mappings from field_mapper
            try:
                mappings = dict(field_mapper.field_mappings) if field_mapper.field_mappings else {}
            except (TypeError, AttributeError):
                # field_mappings might be a Mock or not iterable
                mappings = {}

            # Process each custom field
            from devflow.cli.commands.jira_update_command import build_field_value
            for field_name, field_value in merged_custom_fields.items():
                # Skip None and empty collections (empty tuples from Click's multiple=True options)
                if field_value is None or field_value == () or field_value == []:
                    continue

                # Get field info from mappings
                field_info = mappings.get(field_name.replace("-", "_"))
                if not field_info:
                    console.print(f"[yellow]⚠[/yellow] Unknown field: {field_name}")
                    console.print(f"  Run [cyan]daf config refresh-jira-fields[/cyan] to discover available fields")
                    continue

                # Validate field is available for this issue type
                available_for = field_info.get("available_for", [])
                if available_for and issue_type not in available_for:
                    console.print(f"[yellow]⚠[/yellow] Field '{field_name}' is not available for {issue_type} issues")
                    console.print(f"  Available for: {', '.join(available_for)}")
                    console.print(f"  [dim]Skipping this field[/dim]")
                    continue

                try:
                    field_id = field_info["id"]
                except (TypeError, KeyError):
                    # field_info might be a Mock or malformed
                    console.print(f"[yellow]⚠[/yellow] Invalid field info for: {field_name}")
                    continue

                # Skip system fields that are already handled by the command
                # These are set via dedicated parameters (summary, description, priority, etc.)
                SYSTEM_FIELDS = {"issue_type", "issuetype", "project", "summary", "description",
                                 "priority", "reporter", "assignee", "created", "updated"}
                if field_id in SYSTEM_FIELDS:
                    continue

                # Build the appropriate value based on field type
                formatted_value = build_field_value(field_info, field_value, field_mapper)

                # Skip invalid field values (config objects, functions, etc.)
                # Valid JIRA field values: str, int, float, bool, list, tuple, dict, None
                if formatted_value is not None and not isinstance(formatted_value, (str, int, float, bool, list, tuple, dict)):
                    console_print(f"[yellow]⚠[/yellow] Skipping invalid custom field '{field_name}': {type(formatted_value).__name__}")
                    continue

                create_kwargs[field_id] = formatted_value

        # Handle system fields (components, labels, etc.)
        # Merge in this order (later values override earlier):
        # 1. config.jira.system_field_defaults (normalize keys to field IDs)
        # 2. required_system_fields (from field_mappings required_for)
        # 3. system_fields (from CLI options)
        merged_system_fields = {}

        # Normalize system_field_defaults keys from field names to field IDs
        # E.g., "component/s" → "components", "affects_version/s" → "versions"
        if config.jira.system_field_defaults:
            try:
                mappings = dict(field_mapper.field_mappings) if field_mapper.field_mappings else {}
            except (TypeError, AttributeError):
                mappings = {}

            for key, value in config.jira.system_field_defaults.items():
                # Try to find the field_id for this key
                field_info = mappings.get(key)
                if field_info and "id" in field_info:
                    # Use field_id instead of field_name
                    normalized_key = field_info["id"]
                else:
                    # No mapping found - use key as-is (might be already a field_id)
                    normalized_key = key
                merged_system_fields[normalized_key] = value

        if required_system_fields:
            merged_system_fields.update(required_system_fields)
        if system_fields:
            merged_system_fields.update(system_fields)

        # Validate that components are provided (required by most JIRA projects)
        # Check if components field exists in field_mappings and is available for this issue type
        components_available = False
        try:
            if config.jira.field_mappings and "component/s" in config.jira.field_mappings:
                components_info = config.jira.field_mappings["component/s"]
                available_for = components_info.get("available_for", [])
                if issue_type.title() in available_for:
                    components_available = True
        except (TypeError, AttributeError):
            # field_mappings might be a Mock or not iterable
            pass

        # If components are available for this issue type but not provided, show error
        if components_available and "components" not in merged_system_fields:
            error_msg = (
                f"Component is required for {issue_type} issues but not configured.\n"
                f"  [dim]Fix by doing ONE of:[/dim]\n"
                f"  [dim]1. Set default in team.json: {{\"jira_system_field_defaults\": {{\"components\": [\"your-component\"]}}}}[/dim]\n"
                f"  [dim]2. Use --components flag: daf jira create {issue_type} --components your-component[/dim]\n"
                f"  [dim]3. Use TUI to set default: daf config tui → JIRA Integration → Component dropdown[/dim]"
            )
            if output_json:
                json_output(
                    success=False,
                    error={
                        "code": "MISSING_REQUIRED_FIELD",
                        "message": "Component is required but not configured",
                        "field": "components",
                        "solutions": [
                            "Set default in team.json: {\"jira_system_field_defaults\": {\"components\": [\"your-component\"]}}",
                            f"Use --components flag: daf jira create {issue_type} --components your-component",
                            "Use TUI: daf config tui"
                        ]
                    }
                )
            else:
                console.print(f"[red]✗[/red] {error_msg}")
            sys.exit(1)

        # Add system fields to create_kwargs (use field IDs directly like "components", "labels")
        # Skip fields that are already handled as dedicated parameters in create_* methods:
        # - components: Dedicated parameter, already added to create_kwargs below
        # - versions: Dedicated parameter (affected_version), already in create_kwargs
        # - priority: Dedicated parameter, already in create_kwargs
        # - description: Dedicated parameter, already in create_kwargs
        DEDICATED_PARAM_FIELDS = {"components", "versions", "priority", "description"}

        for field_name, field_value in merged_system_fields.items():
            # Skip fields with dedicated parameters
            if field_name in DEDICATED_PARAM_FIELDS:
                continue

            # Skip None and empty collections (empty tuples from Click's multiple=True options)
            if field_value is not None and field_value != () and field_value != []:
                # Skip invalid field values (config objects, functions, etc.)
                # Valid JIRA field values: str, int, float, bool, list, tuple, dict
                if not isinstance(field_value, (str, int, float, bool, list, tuple, dict)):
                    console_print(f"[yellow]⚠[/yellow] Skipping invalid system field '{field_name}': {type(field_value).__name__}")
                    continue
                # System fields use their original names (e.g., "labels"), not customfield IDs
                create_kwargs[field_name] = field_value

        # Add components from merged_system_fields to create_kwargs (has dedicated parameter)
        if "components" in merged_system_fields:
            create_kwargs["components"] = merged_system_fields["components"]

        # Create the issue with specific error handling
        try:
            issue_key = client_method(**create_kwargs)
        except JiraValidationError as e:
            # JIRA validation error - show field errors and server messages
            error_msg = str(e)
            if output_json:
                json_output(
                    success=False,
                    error={
                        "code": "VALIDATION_ERROR",
                        "message": error_msg,
                        "field_errors": e.field_errors if hasattr(e, 'field_errors') else {},
                        "error_messages": e.error_messages if hasattr(e, 'error_messages') else []
                    }
                )
            else:
                console.print(f"[red]✗[/red] JIRA Validation Error: {error_msg}")
                if hasattr(e, 'field_errors') and e.field_errors:
                    console.print("  [red]Field errors from JIRA:[/red]")
                    for field, msg in e.field_errors.items():
                        console.print(f"    [red]• {field}: {msg}[/red]")
                if hasattr(e, 'error_messages') and e.error_messages:
                    console.print("  [red]Error messages from JIRA:[/red]")
                    for msg in e.error_messages:
                        console.print(f"    [red]• {msg}[/red]")
            sys.exit(1)
        except JiraAuthError as e:
            # JIRA authentication error
            error_msg = str(e)
            if output_json:
                json_output(
                    success=False,
                    error={"code": "AUTH_ERROR", "message": error_msg}
                )
            else:
                console.print(f"[red]✗[/red] JIRA Authentication Error: {error_msg}")
            sys.exit(1)
        except JiraApiError as e:
            # JIRA API error - show status code and response text
            error_msg = str(e)
            if output_json:
                json_output(
                    success=False,
                    error={
                        "code": "API_ERROR",
                        "message": error_msg,
                        "status_code": e.status_code if hasattr(e, 'status_code') else None,
                        "response_text": e.response_text if hasattr(e, 'response_text') else None
                    }
                )
            else:
                console.print(f"[red]✗[/red] JIRA API Error: {error_msg}")
                if hasattr(e, 'status_code'):
                    console.print(f"  [dim]Status code: {e.status_code}[/dim]")
                if hasattr(e, 'response_text'):
                    console.print(f"  [dim]Server response: {e.response_text}[/dim]")
            sys.exit(1)
        except JiraConnectionError as e:
            # JIRA connection error
            error_msg = str(e)
            if output_json:
                json_output(
                    success=False,
                    error={"code": "CONNECTION_ERROR", "message": error_msg}
                )
            else:
                console.print(f"[red]✗[/red] JIRA Connection Error: {error_msg}")
            sys.exit(1)

        # Link issue if --linked-issue and --issue provided
        if linked_issue or issue:
            # Validate that both options are provided together
            if not linked_issue or not issue:
                error_msg = "Both --linked-issue and --issue must be specified together"
                if output_json:
                    json_output(
                        success=False,
                        error={
                            "code": "INVALID_OPTIONS",
                            "message": error_msg
                        }
                    )
                else:
                    console.print(f"[red]✗[/red] {error_msg}")
                sys.exit(1)

            # Validate that linked issue exists
            console_print(f"[dim]Validating linked issue: {issue}[/dim]")
            from devflow.jira.utils import validate_jira_ticket

            linked_ticket = validate_jira_ticket(issue, client=None)
            if not linked_ticket:
                # Error already displayed by validate_jira_ticket
                error_msg = f"Cannot link to invalid issue: {issue}"
                if output_json:
                    json_output(
                        success=False,
                        error={
                            "code": "INVALID_LINKED_ISSUE",
                            "message": error_msg
                        }
                    )
                else:
                    console.print(f"[red]✗[/red] {error_msg}")
                sys.exit(1)

            console_print(f"[green]✓[/green] Linked issue validated: {issue}")

            # Create the issue link
            console_print(f"[dim]Creating issue link: {issue_key} {linked_issue} {issue}[/dim]")
            try:
                jira_client.link_issues(
                    issue_key=issue_key,
                    link_to_issue_key=issue,
                    link_type_description=linked_issue
                )
                console_print(f"[green]✓[/green] Linked {issue_key} {linked_issue} {issue}")
            except JiraValidationError as e:
                # Link type validation failed - show available types
                error_msg = str(e)
                if output_json:
                    json_output(
                        success=False,
                        error={
                            "code": "INVALID_LINK_TYPE",
                            "message": error_msg,
                            "available_types": e.error_messages
                        }
                    )
                else:
                    console.print(f"[red]✗[/red] {error_msg}")
                    for msg in e.error_messages:
                        console.print(f"  [dim]{msg}[/dim]")
                sys.exit(1)
            except JiraNotFoundError as e:
                error_msg = f"Issue not found when creating link: {e}"
                if output_json:
                    json_output(
                        success=False,
                        error={
                            "code": "ISSUE_NOT_FOUND",
                            "message": error_msg
                        }
                    )
                else:
                    console.print(f"[red]✗[/red] {error_msg}")
                sys.exit(1)
            except JiraApiError as e:
                error_msg = f"Failed to create issue link: {e}"
                if output_json:
                    json_output(
                        success=False,
                        error={
                            "code": "LINK_CREATION_FAILED",
                            "message": error_msg
                        }
                    )
                else:
                    console.print(f"[red]✗[/red] {error_msg}")
                sys.exit(1)

        # Auto-rename ticket_creation sessions to creation-<ticket_key>
        from devflow.session.manager import SessionManager
        from devflow.cli.utils import get_active_session_name
        import logging
        import re

        logger = logging.getLogger(__name__)

        # Get active session name (None if called outside Claude session)
        active_session_name = get_active_session_name()
        logger.debug(f"get_active_session_name() returned: {active_session_name}")

        if active_session_name:  # Only rename if inside a Claude session
            try:
                session_manager = SessionManager(config_loader=config_loader)
                session = session_manager.get_session(active_session_name)
                logger.debug(f"Retrieved session: {session.name if session else None}")

                if session:
                    logger.debug(f"Session type: {session.session_type}")
                    # Extract pattern to avoid f-string backslash issue in Python 3.10/3.11
                    creation_pattern = r'^creation-[A-Z]+-\d+$'
                    matches_pattern = bool(re.match(creation_pattern, active_session_name))
                    logger.debug(f"Session name matches creation pattern: {matches_pattern}")

                # Only rename if:
                # 1. Session exists and is a ticket_creation session (only created by 'daf jira new')
                # 2. Session name doesn't already match creation-* pattern (prevent double-rename)
                # Note: session_type="ticket_creation" is ONLY set by 'daf jira new' command,
                # so this check ensures we only rename sessions from that workflow
                creation_pattern = r'^creation-[A-Z]+-\d+$'
                if (session and
                    session.session_type == "ticket_creation" and
                    not re.match(creation_pattern, active_session_name)):

                    new_name = f"creation-{issue_key}"
                    logger.info(f"Attempting to rename session '{active_session_name}' to '{new_name}'")
                    try:
                        session_manager.rename_session(active_session_name, new_name)

                        # Verify the rename was successful
                        renamed_session = session_manager.get_session(new_name)
                        if renamed_session and renamed_session.name == new_name:
                            # Set JIRA metadata on renamed session
                            renamed_session.issue_key = issue_key
                            if not renamed_session.issue_metadata:
                                renamed_session.issue_metadata = {}
                            renamed_session.issue_metadata["summary"] = summary
                            renamed_session.issue_metadata["type"] = issue_type.capitalize()

                            # Fetch current status from JIRA for accuracy
                            try:
                                ticket_info = jira_client.get_ticket(issue_key)
                                renamed_session.issue_metadata["status"] = ticket_info.get("status", "New")
                            except Exception as e:
                                # Fallback to "New" if we can't fetch status
                                logger.warning(f"Could not fetch JIRA status for {issue_key}: {e}")
                                renamed_session.issue_metadata["status"] = "New"

                            # Save the updated session
                            session_manager.update_session(renamed_session)

                            console_print(f"[green]✓[/green] Renamed session to: [bold]{new_name}[/bold]")
                            console_print(f"   Reopen with: [bold]daf open {new_name}[/bold]")
                            logger.info(f"Successfully renamed session to '{new_name}' and set JIRA metadata")
                        else:
                            # Rename may have failed silently
                            console_print(f"[yellow]⚠[/yellow] Session rename may have failed")
                            console_print(f"   Expected: [bold]{new_name}[/bold]")
                            console_print(f"   Actual: [bold]{active_session_name}[/bold]")
                            console_print(f"   Reopen with: [bold]daf open {active_session_name}[/bold]")
                            logger.warning(f"Rename verification failed: expected '{new_name}', session still named '{active_session_name}'")
                    except ValueError as e:
                        # Session name already exists - this shouldn't happen normally
                        error_msg = str(e)
                        if "already exists" in error_msg:
                            console_print(f"[yellow]⚠[/yellow] Session '[bold]{new_name}[/bold]' already exists")
                            console_print(f"   This means a ticket for [bold]{issue_key}[/bold] was already created in a previous session")
                            console_print(f"   Current session: [bold]{active_session_name}[/bold]")
                            console_print(f"   Existing session: [bold]{new_name}[/bold]")
                            console_print(f"")
                            console_print(f"   [dim]To use the existing session:[/dim] [bold]daf open {new_name}[/bold]")
                            console_print(f"   [dim]To continue with current session:[/dim] [bold]daf open {active_session_name}[/bold]")
                        else:
                            console_print(f"[yellow]⚠[/yellow] Could not rename session: {e}")
                            console_print(f"   Session name: [bold]{active_session_name}[/bold]")
                            console_print(f"   Reopen with: [bold]daf open {active_session_name}[/bold]")
                        logger.warning(f"Failed to rename session: {e}")
                else:
                    # Extract pattern to avoid f-string backslash issue in Python 3.10/3.11
                    already_renamed = bool(re.match(creation_pattern, active_session_name))
                    logger.debug(f"Skipping rename: session={bool(session)}, session_type={session.session_type if session else 'N/A'}, already_renamed={already_renamed}")
            except Exception as e:
                # Don't fail the ticket creation if rename fails
                console_print(f"[yellow]⚠[/yellow] Error during session rename: {e}")
                logger.error(f"Error during session rename: {e}", exc_info=True)

        # JSON output mode
        if output_json:
            output_data = {
                "issue_key": issue_key,
                "issue_type": issue_type,
                "summary": summary,
                "url": f"{config.jira.url}/browse/{issue_key}",
                "project": resolved_project,
                "priority": priority,
            }

            # Add all custom fields to output
            if required_custom_fields:
                output_data["custom_fields"] = required_custom_fields

            if parent:
                output_data["parent"] = parent

            if type_config["uses_affected_version"]:
                output_data["affected_version"] = resolved_affected_version

            # Add session info if created
            if create_session:
                output_data["session_created"] = True
                output_data["session_name"] = issue_key

            json_output(
                success=True,
                data=output_data
            )
            return

        console.print(f"\n[green]✓[/green] Created {issue_type}: [bold]{issue_key}[/bold]")
        console.print(f"   {config.jira.url}/browse/{issue_key}")

        # Optionally create session
        if create_session:
            console.print(f"\n[dim]Creating session for {issue_key}...[/dim]")
            from devflow.cli.commands.new_command import create_new_session
            create_new_session(
                name=issue_key,
                goal=f"{issue_key}: {summary}",
                working_directory=None,
                path=None,
                branch=None,
                issue_key=issue_key,
                template=None,
            )

    except RuntimeError as e:
        if output_json:
            json_output(
                success=False,
                error={"message": str(e), "code": "RUNTIME_ERROR"}
            )
        else:
            console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        if output_json:
            json_output(
                success=False,
                error={"message": f"Unexpected error: {e}", "code": "UNEXPECTED_ERROR", "traceback": traceback.format_exc()}
            )
        else:
            console.print(f"[red]✗[/red] Unexpected error: {e}")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


def create_bug(
    summary: Optional[str],
    priority: str,
    parent: Optional[str],
    affected_version: str,
    description: Optional[str],
    description_file: Optional[str],
    interactive: bool,
    create_session: bool,
    custom_fields: Optional[dict] = None,
) -> None:
    """Create a JIRA bug issue.

    Args:
        summary: Bug summary (or None to prompt)
        priority: Bug priority
        parent: Parent issue key to link to (epic for bugs)
        affected_version: Affected version
        description: Description from --description flag (or None)
        description_file: Path to description file (or None)
        interactive: Use interactive template mode
        create_session: Create daf session after creation
        custom_fields: Custom field values from --field options (e.g., {"workstream": "Platform"})
    """
    try:
        # Load config
        config_loader = ConfigLoader()
        config = config_loader.load_config()

        if not config or not config.jira:
            console.print("[red]✗[/red] JIRA not configured. Run [cyan]daf init[/cyan] first.")
            sys.exit(1)

        # Get project first (needed for field discovery)
        resolved_project = _get_project(config, config_loader, None)  # No --project flag yet
        if not resolved_project:
            console.print("[red]✗[/red] Project is required for bug creation")
            sys.exit(1)

        # Ensure field mappings
        field_mapper = _ensure_field_mappings(config, config_loader)

        # Get all required custom fields for Bug issue type
        required_custom_fields = _get_required_custom_fields(
            config, config_loader, field_mapper, "Bug", custom_fields or {}
        )
        if required_custom_fields is None:
            # User cancelled or required field missing
            sys.exit(1)

        # Prompt for summary if not provided
        if not summary:
            if not is_json_mode():
                summary = Prompt.ask("\n[bold]Bug summary[/bold]")
                if not summary or not summary.strip():
                    console.print("[red]✗[/red] Summary is required")
                    sys.exit(1)
                summary = summary.strip()
            else:
                # JSON mode - return error for missing required field
                json_output(
                    success=False,
                    error={
                        "code": "MISSING_REQUIRED_FIELD",
                        "message": "Summary is required. Use --summary flag."
                    }
                )
                sys.exit(1)

        # Get description
        bug_description = _get_description(description, description_file, BUG_TEMPLATE, interactive)

        # Create bug
        jira_client = JiraClient()
        try:
            issue_key = jira_client.create_bug(
                summary=summary,
                description=bug_description,
                priority=priority,
                project_key=resolved_project,
                field_mapper=field_mapper,
                parent=parent,
                affected_version=affected_version,
                required_custom_fields=required_custom_fields,  # Pass all required custom fields
            )

            console.print(f"\n[green]✓[/green] Created bug: [bold]{issue_key}[/bold]")
            console.print(f"   {config.jira.url}/browse/{issue_key}")
        except JiraValidationError as e:
            if output_json:
                json_output(success=False, error={
                    "code": "VALIDATION_ERROR",
                    "message": str(e),
                    "field_errors": e.field_errors,
                    "error_messages": e.error_messages
                })
            else:
                console.print(f"[red]✗[/red] {e}")
                if e.field_errors:
                    console.print("  [red]Field errors:[/red]")
                    for field, msg in e.field_errors.items():
                        console.print(f"    [red]• {field}: {msg}[/red]")
                if e.error_messages:
                    for msg in e.error_messages:
                        console.print(f"    [red]• {msg}[/red]")
            sys.exit(1)
        except JiraAuthError as e:
            if output_json:
                json_output(success=False, error={"code": "AUTH_ERROR", "message": str(e)})
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except JiraApiError as e:
            if output_json:
                json_output(success=False, error={
                    "code": "API_ERROR",
                    "message": str(e),
                    "status_code": e.status_code
                })
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except JiraConnectionError as e:
            if output_json:
                json_output(success=False, error={"code": "CONNECTION_ERROR", "message": str(e)})
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)

        # Optionally create session
        if create_session:
            console.print(f"\n[dim]Creating session for {issue_key}...[/dim]")
            from devflow.cli.commands.new_command import create_new_session
            create_new_session(
                name=issue_key,
                goal=f"{issue_key}: {summary}",
                working_directory=None,
                path=None,
                branch=None,
                issue_key=issue_key,
                template=None,
            )

    except RuntimeError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        sys.exit(1)


def create_story(
    summary: Optional[str],
    priority: str,
    parent: Optional[str],
    description: Optional[str],
    description_file: Optional[str],
    interactive: bool,
    create_session: bool,
    custom_fields: Optional[dict] = None,
) -> None:
    """Create a JIRA story issue.

    Args:
        summary: Story summary (or None to prompt)
        priority: Story priority
        parent: Parent issue key to link to (epic for stories)
        description: Description from --description flag (or None)
        description_file: Path to description file (or None)
        interactive: Use interactive template mode
        create_session: Create daf session after creation
        custom_fields: Custom field values from --field options (e.g., {"workstream": "Platform"})
    """
    try:
        # Load config
        config_loader = ConfigLoader()
        config = config_loader.load_config()

        if not config or not config.jira:
            console.print("[red]✗[/red] JIRA not configured. Run [cyan]daf init[/cyan] first.")
            sys.exit(1)

        # Get project first (needed for field discovery)
        resolved_project = _get_project(config, config_loader, None)  # No --project flag yet
        if not resolved_project:
            console.print("[red]✗[/red] Project is required for story creation")
            sys.exit(1)

        # Ensure field mappings
        field_mapper = _ensure_field_mappings(config, config_loader)

        # Get all required custom fields for Story issue type
        required_custom_fields = _get_required_custom_fields(
            config, config_loader, field_mapper, "Story", custom_fields or {}
        )
        if required_custom_fields is None:
            # User cancelled or required field missing
            sys.exit(1)

        # Prompt for summary if not provided
        if not summary:
            if not is_json_mode():
                summary = Prompt.ask("\n[bold]Story summary[/bold]")
                if not summary or not summary.strip():
                    console.print("[red]✗[/red] Summary is required")
                    sys.exit(1)
                summary = summary.strip()
            else:
                # JSON mode - return error for missing required field
                json_output(
                    success=False,
                    error={
                        "code": "MISSING_REQUIRED_FIELD",
                        "message": "Summary is required. Use --summary flag."
                    }
                )
                sys.exit(1)

        # Get description
        story_description = _get_description(description, description_file, STORY_TEMPLATE, interactive)

        # Create story
        jira_client = JiraClient()
        try:
            issue_key = jira_client.create_story(
                summary=summary,
                description=story_description,
                priority=priority,
                project_key=resolved_project,
                field_mapper=field_mapper,
                parent=parent,
                required_custom_fields=required_custom_fields,  # Pass all required custom fields
            )

            console.print(f"\n[green]✓[/green] Created story: [bold]{issue_key}[/bold]")
            console.print(f"   {config.jira.url}/browse/{issue_key}")
        except JiraValidationError as e:
            if output_json:
                json_output(success=False, error={
                    "code": "VALIDATION_ERROR",
                    "message": str(e),
                    "field_errors": e.field_errors,
                    "error_messages": e.error_messages
                })
            else:
                console.print(f"[red]✗[/red] {e}")
                if e.field_errors:
                    console.print("  [red]Field errors:[/red]")
                    for field, msg in e.field_errors.items():
                        console.print(f"    [red]• {field}: {msg}[/red]")
                if e.error_messages:
                    for msg in e.error_messages:
                        console.print(f"    [red]• {msg}[/red]")
            sys.exit(1)
        except JiraAuthError as e:
            if output_json:
                json_output(success=False, error={"code": "AUTH_ERROR", "message": str(e)})
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except JiraApiError as e:
            if output_json:
                json_output(success=False, error={
                    "code": "API_ERROR",
                    "message": str(e),
                    "status_code": e.status_code
                })
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except JiraConnectionError as e:
            if output_json:
                json_output(success=False, error={"code": "CONNECTION_ERROR", "message": str(e)})
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)

        # Optionally create session
        if create_session:
            console.print(f"\n[dim]Creating session for {issue_key}...[/dim]")
            from devflow.cli.commands.new_command import create_new_session
            create_new_session(
                name=issue_key,
                goal=f"{issue_key}: {summary}",
                working_directory=None,
                path=None,
                branch=None,
                issue_key=issue_key,
                template=None,
            )

    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        sys.exit(1)


def create_task(
    summary: Optional[str],
    priority: str,
    parent: Optional[str],
    description: Optional[str],
    description_file: Optional[str],
    interactive: bool,
    create_session: bool,
    custom_fields: Optional[dict] = None,
) -> None:
    """Create a JIRA task issue.

    Args:
        summary: Task summary (or None to prompt)
        priority: Task priority
        parent: Parent issue key to link to (epic for tasks)
        description: Description from --description flag (or None)
        description_file: Path to description file (or None)
        interactive: Use interactive template mode
        create_session: Create daf session after creation
        custom_fields: Custom field values from --field options (e.g., {"workstream": "Platform"})
    """
    try:
        # Load config
        config_loader = ConfigLoader()
        config = config_loader.load_config()

        if not config or not config.jira:
            console.print("[red]✗[/red] JIRA not configured. Run [cyan]daf init[/cyan] first.")
            sys.exit(1)

        # Get project first (needed for field discovery)
        resolved_project = _get_project(config, config_loader, None)  # No --project flag yet
        if not resolved_project:
            console.print("[red]✗[/red] Project is required for task creation")
            sys.exit(1)

        # Ensure field mappings
        field_mapper = _ensure_field_mappings(config, config_loader)

        # Get all required custom fields for Task issue type
        required_custom_fields = _get_required_custom_fields(
            config, config_loader, field_mapper, "Task", custom_fields or {}
        )
        if required_custom_fields is None:
            # User cancelled or required field missing
            sys.exit(1)

        # Prompt for summary if not provided
        if not summary:
            if not is_json_mode():
                summary = Prompt.ask("\n[bold]Task summary[/bold]")
                if not summary or not summary.strip():
                    console.print("[red]✗[/red] Summary is required")
                    sys.exit(1)
                summary = summary.strip()
            else:
                # JSON mode - return error for missing required field
                json_output(
                    success=False,
                    error={
                        "code": "MISSING_REQUIRED_FIELD",
                        "message": "Summary is required. Use --summary flag."
                    }
                )
                sys.exit(1)

        # Get description
        task_description = _get_description(description, description_file, TASK_TEMPLATE, interactive)

        # Create task
        jira_client = JiraClient()
        try:
            issue_key = jira_client.create_task(
                summary=summary,
                description=task_description,
                priority=priority,
                project_key=resolved_project,
                field_mapper=field_mapper,
                parent=parent,
                required_custom_fields=required_custom_fields,  # Pass all required custom fields
            )

            console.print(f"\n[green]✓[/green] Created task: [bold]{issue_key}[/bold]")
            console.print(f"   {config.jira.url}/browse/{issue_key}")
        except JiraValidationError as e:
            if output_json:
                json_output(success=False, error={
                    "code": "VALIDATION_ERROR",
                    "message": str(e),
                    "field_errors": e.field_errors,
                    "error_messages": e.error_messages
                })
            else:
                console.print(f"[red]✗[/red] {e}")
                if e.field_errors:
                    console.print("  [red]Field errors:[/red]")
                    for field, msg in e.field_errors.items():
                        console.print(f"    [red]• {field}: {msg}[/red]")
                if e.error_messages:
                    for msg in e.error_messages:
                        console.print(f"    [red]• {msg}[/red]")
            sys.exit(1)
        except JiraAuthError as e:
            if output_json:
                json_output(success=False, error={"code": "AUTH_ERROR", "message": str(e)})
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except JiraApiError as e:
            if output_json:
                json_output(success=False, error={
                    "code": "API_ERROR",
                    "message": str(e),
                    "status_code": e.status_code
                })
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except JiraConnectionError as e:
            if output_json:
                json_output(success=False, error={"code": "CONNECTION_ERROR", "message": str(e)})
            else:
                console.print(f"[red]✗[/red] {e}")
            sys.exit(1)

        # Optionally create session
        if create_session:
            console.print(f"\n[dim]Creating session for {issue_key}...[/dim]")
            from devflow.cli.commands.new_command import create_new_session
            create_new_session(
                name=issue_key,
                goal=f"{issue_key}: {summary}",
                working_directory=None,
                path=None,
                branch=None,
                issue_key=issue_key,
                template=None,
            )

    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        sys.exit(1)
