"""Implementation of 'daf jira update' command."""

import sys
from typing import Optional, Dict, Any
from rich.console import Console

from devflow.cli.utils import output_json as json_output, require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.jira.client import JiraClient
from devflow.jira.field_mapper import JiraFieldMapper
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError
from devflow.jira.utils import merge_pr_urls

console = Console()


def build_field_value(field_info: Dict[str, Any], value: str, field_mapper: JiraFieldMapper) -> Any:
    """Build the appropriate field value based on field type.

    Args:
        field_info: Field metadata from field mapper
        value: Raw string value from CLI
        field_mapper: JiraFieldMapper instance

    Returns:
        Properly formatted field value for JIRA API
    """
    field_type = field_info.get("type", "string")
    schema = field_info.get("schema", "string")

    # Handle different field types
    # IMPORTANT: Check array fields BEFORE single-select fields
    # to properly handle multi-select fields like workstream (type=array, schema=option)
    if schema == "multiurl" or "url" in schema.lower():
        # For URL fields, return as-is
        return value
    elif schema == "array" or field_type == "array":
        # Multi-select field (like workstream)
        if "option" in schema:
            return [{"value": value}]
        else:
            # Array of strings
            return [value]
    elif schema == "option" or schema == "com.atlassian.jira.plugin.system.customfieldtypes:select":
        # Single-select field
        return {"value": value}
    elif schema == "priority":
        return {"name": value}
    elif schema == "user":
        if value.lower() == "none":
            return None
        return {"name": value}
    else:
        # Default: return as string
        return value


def update_jira_issue(
    issue_key: str,
    description: Optional[str] = None,
    description_file: Optional[str] = None,
    priority: Optional[str] = None,
    assignee: Optional[str] = None,
    summary: Optional[str] = None,
    git_pull_request: Optional[str] = None,
    status: Optional[str] = None,
    linked_issue: Optional[str] = None,
    issue: Optional[str] = None,
    output_json: bool = False,
    **custom_fields
) -> None:
    """Update a JIRA issue with specified fields.

    This function supports both hardcoded common fields and dynamically discovered
    custom fields through **custom_fields kwargs.

    Args:
        issue_key: JIRA issue key (e.g., PROJ-12345)
        description: New description text
        description_file: Path to file containing description
        priority: New priority value
        assignee: New assignee username
        summary: New summary text
        git_pull_request: PR/MR URLs (comma-separated, will be appended to existing)
        status: Target status to transition to (e.g., 'In Progress', 'Review', 'Closed')
        linked_issue: Type of relationship (e.g., 'blocks', 'is blocked by', 'relates to')
        issue: Issue key to link to (e.g., PROJ-12345)
        **custom_fields: Additional custom fields discovered dynamically (e.g., workstream="Platform", acceptance_criteria="...")
    """
    try:
        # Load config
        config_loader = ConfigLoader()
        config = config_loader.load_config()

        if not config or not config.jira:
            console.print("[red]✗[/red] JIRA not configured. Run [cyan]daf init[/cyan] first.")
            sys.exit(1)

        # Initialize JIRA client and field mapper
        from devflow.utils import is_mock_mode
        if is_mock_mode():
            from devflow.mocks.jira_mock import MockJiraClient
            jira_client = MockJiraClient(config=config)
        else:
            jira_client = JiraClient()

        # Ensure field mappings exist
        field_mapper = None
        if config.jira.field_mappings:
            field_mapper = JiraFieldMapper(jira_client, config.jira.field_mappings)
        else:
            console.print("[dim]No cached field mappings found, using field defaults[/dim]")
            field_mapper = JiraFieldMapper(jira_client, {})

        # Build update payload
        payload = {"fields": {}}

        # Handle description (file takes precedence)
        if description_file:
            try:
                with open(description_file, 'r') as f:
                    payload["fields"]["description"] = f.read()
            except Exception as e:
                console.print(f"[red]✗[/red] Could not read file {description_file}: {e}")
                sys.exit(1)
        elif description:
            payload["fields"]["description"] = description

        # Handle summary
        if summary:
            payload["fields"]["summary"] = summary

        # Handle priority
        if priority:
            payload["fields"]["priority"] = {"name": priority}

        # Handle assignee
        if assignee:
            if assignee.lower() == "none":
                # Clear assignee
                payload["fields"]["assignee"] = None
            else:
                payload["fields"]["assignee"] = {"name": assignee}

        # Handle git-pull-request (fetch, append, update)
        if git_pull_request:
            # Get the git-pull-request field ID from mapper
            git_pr_field = field_mapper.get_field_id("git_pull_request")
            if not git_pr_field:
                if output_json:
                    json_output(success=False, error={"code": "FIELD_NOT_FOUND", "message": "git_pull_request field not found in JIRA"})
                else:
                    console.print("[red]✗[/red] git_pull_request field not found in JIRA. Run 'daf jira discover' to refresh field mappings.")
                sys.exit(1)

            # Fetch current PR links
            try:
                current_prs = jira_client.get_ticket_pr_links(issue_key)
            except JiraNotFoundError as e:
                if output_json:
                    json_output(success=False, error={"code": "NOT_FOUND", "message": str(e)})
                else:
                    console.print(f"[red]✗[/red] {e}")
                sys.exit(1)
            except (JiraAuthError, JiraApiError, JiraConnectionError) as e:
                if output_json:
                    json_output(success=False, error={"code": "API_ERROR", "message": str(e)})
                else:
                    console.print(f"[red]✗[/red] Failed to fetch current PR links: {e}")
                sys.exit(1)

            # Merge new PRs with existing ones (handles duplicates, whitespace, and list formats)
            merged_prs = merge_pr_urls(current_prs, git_pull_request)

            payload["fields"][git_pr_field] = merged_prs

        # Handle dynamically discovered custom fields
        if custom_fields:
            # Discover editable fields for this issue (on-demand, no caching)
            console.print(f"[dim]Discovering editable fields for {issue_key}...[/dim]")
            try:
                editable_mappings = field_mapper.discover_editable_fields(issue_key)
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Could not discover editable fields: {e}")
                console.print("  Using creation field mappings as fallback")
                editable_mappings = config.jira.field_mappings or {}

            # Process each custom field
            for field_name, field_value in custom_fields.items():
                if field_value is None:
                    continue

                # Get field info from editable mappings
                field_info = editable_mappings.get(field_name.replace("-", "_"))
                if not field_info:
                    console.print(f"[yellow]⚠[/yellow] Unknown field: {field_name}")
                    console.print(f"  Available fields: {', '.join(list(editable_mappings.keys())[:10])}")
                    continue

                field_id = field_info["id"]

                # Build the appropriate value based on field type
                formatted_value = build_field_value(field_info, field_value, field_mapper)
                payload["fields"][field_id] = formatted_value

        # Handle issue linking separately (can work even with no field updates)
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
            if not output_json:
                console.print(f"[dim]Validating linked issue: {issue}[/dim]")

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

            if not output_json:
                console.print(f"[green]✓[/green] Linked issue validated: {issue}")

            # Create the issue link
            if not output_json:
                console.print(f"[dim]Creating issue link: {issue_key} {linked_issue} {issue}[/dim]")

            try:
                jira_client.link_issues(
                    issue_key=issue_key,
                    link_to_issue_key=issue,
                    link_type_description=linked_issue
                )
                if not output_json:
                    console.print(f"[green]✓[/green] Linked {issue_key} {linked_issue} {issue}")
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

        # Check if any fields were specified (linking and status transition don't require field updates)
        if not payload["fields"] and not (linked_issue and issue) and not status:
            if output_json:
                json_output(
                    success=False,
                    error={"message": "No fields specified for update", "code": "NO_FIELDS"}
                )
            else:
                console.print("[yellow]⚠[/yellow] No fields specified for update")
                console.print("  Use --help to see available options")
            sys.exit(1)

        # Only update fields if there are any to update
        if payload["fields"]:
            # Update the issue
            if not output_json:
                console.print(f"\n[dim]Updating JIRA issue {issue_key}...[/dim]")

            try:
                jira_client.update_issue(issue_key, payload)

                # Build list of updated field names for output
                updated_fields = []
                for field_key in payload["fields"].keys():
                    # Get human-readable field name
                    if field_key in ["description", "summary", "priority", "assignee"]:
                        field_name = field_key.capitalize()
                    elif field_mapper:
                        # Try to reverse lookup the field name
                        field_name = field_key
                        for norm_name, field_info in field_mapper._cache.items():
                            if field_info.get("id") == field_key:
                                field_name = field_info.get("name", field_key)
                                break
                    else:
                        field_name = field_key

                    updated_fields.append(field_name)

                # JSON output mode
                if output_json:
                    json_output(
                        success=True,
                        data={
                            "issue_key": issue_key,
                            "url": f"{config.jira.url}/browse/{issue_key}",
                            "updated_fields": updated_fields,
                        }
                    )
                    return

                console.print(f"[green]✓[/green] Successfully updated {issue_key}")
                console.print(f"   {config.jira.url}/browse/{issue_key}")

                # Show what was updated
                console.print("\n[dim]Updated fields:[/dim]")
                for field_name in updated_fields:
                    console.print(f"  • {field_name}")

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
            except JiraNotFoundError as e:
                if output_json:
                    json_output(success=False, error={"code": "NOT_FOUND", "message": str(e)})
                else:
                    console.print(f"[red]✗[/red] {e}")
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

        # Handle status transition if requested
        if status:
            if not output_json:
                console.print(f"\n[dim]Transitioning {issue_key} to '{status}'...[/dim]")

            try:
                jira_client.transition_ticket(issue_key, status)

                # Success message
                if output_json:
                    json_output(
                        success=True,
                        data={
                            "issue_key": issue_key,
                            "url": f"{config.jira.url}/browse/{issue_key}",
                            "new_status": status,
                        }
                    )
                else:
                    console.print(f"[green]✓[/green] issue tracker ticket {issue_key} → {status}")
                    console.print(f"   {config.jira.url}/browse/{issue_key}")

            except JiraNotFoundError as e:
                # Status not available - show available transitions
                if output_json:
                    json_output(
                        success=False,
                        error={
                            "code": "INVALID_STATUS",
                            "message": str(e)
                        }
                    )
                else:
                    console.print(f"[red]✗[/red] {e}")
                sys.exit(1)
            except JiraValidationError as e:
                # Transition requires additional fields
                if output_json:
                    json_output(
                        success=False,
                        error={
                            "code": "VALIDATION_ERROR",
                            "message": str(e),
                            "field_errors": e.field_errors,
                            "error_messages": e.error_messages
                        }
                    )
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
                    json_output(
                        success=False,
                        error={
                            "code": "API_ERROR",
                            "message": str(e),
                            "status_code": e.status_code
                        }
                    )
                else:
                    console.print(f"[red]✗[/red] {e}")
                sys.exit(1)
            except JiraConnectionError as e:
                if output_json:
                    json_output(success=False, error={"code": "CONNECTION_ERROR", "message": str(e)})
                else:
                    console.print(f"[red]✗[/red] {e}")
                sys.exit(1)

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
