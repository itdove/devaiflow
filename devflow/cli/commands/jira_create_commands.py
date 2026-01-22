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


def _get_workstream(config, config_loader, field_mapper, flag_value: Optional[str]) -> Optional[str]:
    """Get workstream value from flag, config, or prompt.

    Logic:
    1. If --workstream flag provided, use it (prompt to save if different from config)
    2. Else if workstream in config, use it
    3. Else prompt user (using field_mapper for allowed values)

    Args:
        config: Config object
        config_loader: ConfigLoader instance
        field_mapper: JiraFieldMapper instance
        flag_value: Value from --workstream flag (or None)

    Returns:
        Workstream value to use, or None if cancelled
    """
    # Case 1: Flag provided
    if flag_value:
        # Check if different from config
        if config.jira.workstream and config.jira.workstream != flag_value:
            console_print(f"[dim]ℹ Current workstream in config: \"{config.jira.workstream}\"[/dim]")
            console_print(f"[dim]ℹ Command uses workstream: \"{flag_value}\"[/dim]")
            console_print()

            if not is_json_mode() and Confirm.ask(f"Update config.json to use \"{flag_value}\" as default?", default=False):
                config.jira.workstream = flag_value
                config_loader.save_config(config)
                console_print(f"[green]✓[/green] Updated config.json with workstream \"{flag_value}\"\n")

        return flag_value

    # Case 2: Workstream in config
    if config.jira.workstream:
        console_print(f"[dim]Using workstream from config: \"{config.jira.workstream}\"[/dim]")
        return config.jira.workstream

    # Case 3: Prompt user
    workstream = field_mapper.get_workstream_with_prompt(
        config_workstream=None,
        save_to_config=False  # We'll handle saving ourselves
    )

    if workstream:
        # Save to config
        config.jira.workstream = workstream
        config_loader.save_config(config)
        console_print(f"\n[green]ℹ[/green] Workstream set to \"{workstream}\" and saved to config.json")
        console_print(f"[dim]You can change it later with: daf config tui <WORKSTREAM>[/dim]\n")

    return workstream


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
            console_print()

            if not is_json_mode() and Confirm.ask(f"Update config.json to use \"{flag_value}\" as default?", default=False):
                config.jira.project = flag_value
                config_loader.save_config(config)
                console_print(f"[green]✓[/green] Updated config.json with project \"{flag_value}\"\n")

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


def _get_affected_version(config, config_loader, flag_value: Optional[str]) -> str:
    """Get affected version value from flag, config, or prompt.

    Logic:
    1. If --affected-version flag provided, use it (prompt to save if different from config)
    2. Else if affected_version in config, use it
    3. Else prompt user with default value

    Args:
        config: Config object
        config_loader: ConfigLoader instance
        flag_value: Value from --affected-version flag (or None)

    Returns:
        Affected version to use (always returns a value)
    """
    # Case 1: Flag provided
    if flag_value:
        # Check if different from config
        if config.jira.affected_version and config.jira.affected_version != flag_value:
            console_print(f"[dim]ℹ Current affected version in config: \"{config.jira.affected_version}\"[/dim]")
            console_print(f"[dim]ℹ Command uses affected version: \"{flag_value}\"[/dim]")
            console_print()

            if not is_json_mode() and Confirm.ask(f"Update config.json to use \"{flag_value}\" as default?", default=False):
                config.jira.affected_version = flag_value
                config_loader.save_config(config)
                console_print(f"[green]✓[/green] Updated config.json with affected version \"{flag_value}\"\n")

        return flag_value

    # Case 2: Affected version in config
    if config.jira.affected_version:
        console_print(f"[dim]Using affected version from config: \"{config.jira.affected_version}\"[/dim]")
        return config.jira.affected_version

    # Case 3: Prompt user with default
    console_print("\n[yellow]⚠[/yellow] No affected version configured.")
    console_print("[dim]Example: v1.0.0[/dim]")
    if not is_json_mode():
        affected_version = Prompt.ask(
            "[bold]Enter affected version[/bold]",
            default="v1.0.0"
        )
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
    workstream: Optional[str],
    parent: Optional[str],
    affected_version: str,
    description: Optional[str],
    description_file: Optional[str],
    interactive: bool,
    create_session: bool,
    linked_issue: Optional[str] = None,
    issue: Optional[str] = None,
    custom_fields: Optional[dict] = None,
    output_json: bool = False,
) -> None:
    """Create a JIRA issue (unified function for bug/story/task).

    Args:
        issue_type: Type of issue (bug, story, task)
        summary: Issue summary (or None to prompt)
        priority: Issue priority
        project: Project key from --project flag (or None)
        workstream: Workstream from --workstream flag (or None)
        parent: Parent issue key to link to (epic for story/task/bug, parent for sub-task)
        affected_version: Affected version (bugs only)
        description: Description from --description flag (or None)
        description_file: Path to description file (or None)
        interactive: Use interactive template mode
        create_session: Create daf session after creation
        linked_issue: Type of relationship (e.g., 'blocks', 'is blocked by', 'relates to')
        issue: Issue key to link to (e.g., PROJ-12345)
        custom_fields: Additional custom fields from --field options
    """
    # Map issue type to template and client method
    ISSUE_TYPE_CONFIG = {
        "epic": {
            "template": EPIC_TEMPLATE,
            "label": "Epic",
            "client_method": "create_epic",
            "uses_affected_version": False,
        },
        "spike": {
            "template": SPIKE_TEMPLATE,
            "label": "Spike",
            "client_method": "create_spike",
            "uses_affected_version": False,
        },
        "story": {
            "template": STORY_TEMPLATE,
            "label": "Story",
            "client_method": "create_story",
            "uses_affected_version": False,
        },
        "task": {
            "template": TASK_TEMPLATE,
            "label": "Task",
            "client_method": "create_task",
            "uses_affected_version": False,
        },
        "bug": {
            "template": BUG_TEMPLATE,
            "label": "Bug",
            "client_method": "create_bug",
            "uses_affected_version": True,
        },
    }

    type_config = ISSUE_TYPE_CONFIG.get(issue_type)
    if not type_config:
        console.print(f"[red]✗[/red] Invalid issue type: {issue_type}")
        sys.exit(1)

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

        # Get workstream
        resolved_workstream = _get_workstream(config, config_loader, field_mapper, workstream)
        if not resolved_workstream:
            console.print(f"[red]✗[/red] Workstream is required for {issue_type} creation")
            sys.exit(1)

        # Get affected version (for bugs only)
        resolved_affected_version = None
        if type_config["uses_affected_version"]:
            resolved_affected_version = _get_affected_version(config, config_loader, affected_version)

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
            summary = Prompt.ask(f"\n[bold]{type_config['label']} summary[/bold]")
            if not summary or not summary.strip():
                console.print("[red]✗[/red] Summary is required")
                sys.exit(1)
            summary = summary.strip()

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
            "workstream": resolved_workstream,
            "field_mapper": field_mapper,
            "parent": parent,
        }

        # Add affected_version only for bugs
        if type_config["uses_affected_version"]:
            create_kwargs["affected_version"] = resolved_affected_version

        # Handle dynamically discovered custom fields
        if custom_fields:
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

            # Use creation mappings from field_mapper cache
            mappings = field_mapper._cache or {}

            # Process each custom field
            from devflow.cli.commands.jira_update_command import build_field_value
            for field_name, field_value in custom_fields.items():
                if field_value is None:
                    continue

                # Get field info from mappings
                field_info = mappings.get(field_name.replace("-", "_"))
                if not field_info:
                    console.print(f"[yellow]⚠[/yellow] Unknown field: {field_name}")
                    console.print(f"  Run [cyan]daf config refresh-jira-fields[/cyan] to discover available fields")
                    continue

                field_id = field_info["id"]

                # Build the appropriate value based on field type
                formatted_value = build_field_value(field_info, field_value, field_mapper)
                create_kwargs[field_id] = formatted_value

        issue_key = client_method(**create_kwargs)

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
                "workstream": resolved_workstream,
                "priority": priority,
            }

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
        if output_json:
            json_output(
                success=False,
                error={"message": f"Unexpected error: {e}", "code": "UNEXPECTED_ERROR"}
            )
        else:
            console.print(f"[red]✗[/red] Unexpected error: {e}")
        sys.exit(1)


def create_bug(
    summary: Optional[str],
    priority: str,
    workstream: Optional[str],
    parent: Optional[str],
    affected_version: str,
    description: Optional[str],
    description_file: Optional[str],
    interactive: bool,
    create_session: bool,
) -> None:
    """Create a JIRA bug issue.

    Args:
        summary: Bug summary (or None to prompt)
        priority: Bug priority
        workstream: Workstream from --workstream flag (or None)
        parent: Parent issue key to link to (epic for bugs)
        affected_version: Affected version
        description: Description from --description flag (or None)
        description_file: Path to description file (or None)
        interactive: Use interactive template mode
        create_session: Create daf session after creation
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

        # Get workstream
        resolved_workstream = _get_workstream(config, config_loader, field_mapper, workstream)
        if not resolved_workstream:
            console.print("[red]✗[/red] Workstream is required for bug creation")
            sys.exit(1)

        # Prompt for summary if not provided
        if not summary:
            summary = Prompt.ask("\n[bold]Bug summary[/bold]")
            if not summary or not summary.strip():
                console.print("[red]✗[/red] Summary is required")
                sys.exit(1)
            summary = summary.strip()

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
                workstream=resolved_workstream,
                field_mapper=field_mapper,
                parent=parent,
                affected_version=affected_version,
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
    workstream: Optional[str],
    parent: Optional[str],
    description: Optional[str],
    description_file: Optional[str],
    interactive: bool,
    create_session: bool,
) -> None:
    """Create a JIRA story issue.

    Args:
        summary: Story summary (or None to prompt)
        priority: Story priority
        workstream: Workstream from --workstream flag (or None)
        parent: Parent issue key to link to (epic for stories)
        description: Description from --description flag (or None)
        description_file: Path to description file (or None)
        interactive: Use interactive template mode
        create_session: Create daf session after creation
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

        # Get workstream
        resolved_workstream = _get_workstream(config, config_loader, field_mapper, workstream)
        if not resolved_workstream:
            console.print("[red]✗[/red] Workstream is required for story creation")
            sys.exit(1)

        # Prompt for summary if not provided
        if not summary:
            summary = Prompt.ask("\n[bold]Story summary[/bold]")
            if not summary or not summary.strip():
                console.print("[red]✗[/red] Summary is required")
                sys.exit(1)
            summary = summary.strip()

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
                workstream=resolved_workstream,
                field_mapper=field_mapper,
                parent=parent,
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
    workstream: Optional[str],
    parent: Optional[str],
    description: Optional[str],
    description_file: Optional[str],
    interactive: bool,
    create_session: bool,
) -> None:
    """Create a JIRA task issue.

    Args:
        summary: Task summary (or None to prompt)
        priority: Task priority
        workstream: Workstream from --workstream flag (or None)
        parent: Parent issue key to link to (epic for tasks)
        description: Description from --description flag (or None)
        description_file: Path to description file (or None)
        interactive: Use interactive template mode
        create_session: Create daf session after creation
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

        # Get workstream
        resolved_workstream = _get_workstream(config, config_loader, field_mapper, workstream)
        if not resolved_workstream:
            console.print("[red]✗[/red] Workstream is required for task creation")
            sys.exit(1)

        # Prompt for summary if not provided
        if not summary:
            summary = Prompt.ask("\n[bold]Task summary[/bold]")
            if not summary or not summary.strip():
                console.print("[red]✗[/red] Summary is required")
                sys.exit(1)
            summary = summary.strip()

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
                workstream=resolved_workstream,
                field_mapper=field_mapper,
                parent=parent,
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
