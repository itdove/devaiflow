"""issue tracker ticket transition management."""

from typing import List, Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt

from devflow.config.models import Config, JiraTransitionConfig, Session
from devflow.jira import JiraClient
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError

console = Console()


def should_transition_on_start(session: Session, config: Config) -> bool:
    """Check if ticket should transition when starting work.

    Args:
        session: Session being opened
        config: Configuration with transition rules

    Returns:
        True if transition should occur, False otherwise
    """
    # Only transition if issue key is set
    if not session.issue_key:
        return False

    # Check if we have transition config for on_start
    if "on_start" not in config.jira.transitions:
        return False

    transition_config = config.jira.transitions["on_start"]

    # Check if current JIRA status is in the "from" list
    current_status = session.issue_metadata.get("status") if session.issue_metadata else None
    if current_status and current_status not in transition_config.from_status:
        return False

    return True


def transition_on_start(
    session: Session, config: Config, jira_client: Optional[JiraClient] = None
) -> bool:
    """Transition issue tracker ticket when starting work on a session.

    According to config, this typically transitions: New/To Do → In Progress

    Args:
        session: Session being opened
        config: Configuration with transition rules
        jira_client: Optional JiraClient instance (creates new if not provided)

    Returns:
        True if transition succeeded (or was skipped), False if failed
    """
    if not should_transition_on_start(session, config):
        return True  # Nothing to do, consider success

    transition_config = config.jira.transitions["on_start"]

    # Prompt user if configured (skip in mock mode - PROJ-62779)
    from devflow.utils import is_mock_mode
    mock_mode = is_mock_mode()

    if transition_config.prompt and not mock_mode:
        if not Confirm.ask(
            f"Transition issue tracker ticket {session.issue_key} to '{transition_config.to}'?",
            default=True,
        ):
            console.print("[dim]JIRA transition skipped[/dim]")
            return True
    elif transition_config.prompt and mock_mode:
        console.print(f"[dim]Mock mode: Auto-transitioning {session.issue_key} to '{transition_config.to}'[/dim]")

    # Perform transition
    try:
        if jira_client is None:
            jira_client = JiraClient()

        jira_client.transition_ticket(session.issue_key, transition_config.to)
        console.print(
            f"[green]✓[/green] issue tracker ticket {session.issue_key} → {transition_config.to}"
        )
        # Update session's cached JIRA status
        if not session.issue_metadata:
            session.issue_metadata = {}
        session.issue_metadata["status"] = transition_config.to
        return True

    except JiraValidationError as e:
        # Transition failed - always stop execution
        console.print(
            f"[red]✗[/red] Failed to transition {session.issue_key} to {transition_config.to}"
        )
        console.print(
            f"[yellow]Fix required fields in JIRA before continuing[/yellow]"
        )
        if e.field_errors:
            console.print("  [red]Field errors:[/red]")
            for field, msg in e.field_errors.items():
                console.print(f"    [red]• {field}: {msg}[/red]")
        if e.error_messages:
            for msg in e.error_messages:
                console.print(f"    [red]• {msg}[/red]")
        return False
    except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError) as e:
        console.print(f"[red]✗[/red] Failed to transition issue tracker ticket: {e}")
        return False


def transition_on_complete(
    session: Session, config: Config, jira_client: Optional[JiraClient] = None
) -> bool:
    """Transition issue tracker ticket when completing a session.

    Dynamically fetches available transitions from JIRA API and prompts user to select.

    Args:
        session: Session being completed
        config: Configuration with transition rules
        jira_client: Optional JiraClient instance (creates new if not provided)

    Returns:
        True if transition succeeded (or was skipped), False if failed
    """
    # Only transition if issue key is set
    if not session.issue_key:
        return True

    # Check if we have transition config for on_complete
    if "on_complete" not in config.jira.transitions:
        return True

    transition_config = config.jira.transitions["on_complete"]

    # Create JIRA client if needed
    if jira_client is None:
        jira_client = JiraClient()

    # If prompt is False, do automatic transition to configured target status
    if not transition_config.prompt:
        if not transition_config.to:
            # No target status configured, skip transition
            return True

        try:
            jira_client.transition_ticket(session.issue_key, transition_config.to)
            console.print(
                f"[green]✓[/green] issue tracker ticket {session.issue_key} → {transition_config.to}"
            )
            # Update session's cached JIRA status
            if not session.issue_metadata:
                session.issue_metadata = {}
            session.issue_metadata["status"] = transition_config.to
            return True

        except (JiraValidationError, JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError) as e:
            console.print(f"[yellow]⚠[/yellow] Failed to transition issue tracker ticket: {e}")
            return True  # Don't block completion on JIRA failure

    # Fetch available transitions from JIRA API (for prompt=True)
    try:
        response = jira_client._api_request(
            "GET",
            f"/rest/api/2/issue/{session.issue_key}/transitions"
        )

        if response.status_code != 200:
            console.print(
                f"[yellow]⚠[/yellow] Could not fetch transitions from JIRA (HTTP {response.status_code})"
            )
            console.print("[dim]JIRA transition skipped[/dim]")
            return True  # Don't block completion on API error

        transitions = response.json().get("transitions", [])

        if not transitions:
            console.print("[yellow]⚠[/yellow] No transitions available for this ticket")
            console.print("[dim]JIRA transition skipped[/dim]")
            return True

        # Extract transition names
        options = [t.get("to", {}).get("name", "") for t in transitions if t.get("to", {}).get("name")]

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Failed to fetch transitions from JIRA: {e}")
        console.print("[dim]JIRA transition skipped[/dim]")
        return True  # Don't block completion on API error

    # Show options
    console.print(f"\n[bold]Transition issue tracker ticket {session.issue_key}?[/bold]")
    current_status = session.issue_metadata.get("status") if session.issue_metadata else None
    console.print(f"Current status: {current_status or 'Unknown'}")
    console.print()

    # Add "Keep current status" option
    options_with_skip = ["Skip (keep current status)"] + options

    for i, option in enumerate(options_with_skip):
        console.print(f"  {i + 1}. {option}")

    console.print()
    choice = Prompt.ask(
        "Select target status",
        choices=[str(i + 1) for i in range(len(options_with_skip))],
        default="1",
    )

    choice_idx = int(choice) - 1

    # If user chose "Skip", return success
    if choice_idx == 0:
        console.print("[dim]JIRA transition skipped[/dim]")
        return True

    target_status = options[choice_idx - 1]  # -1 because we added "Skip" at index 0

    # Perform transition
    try:
        jira_client.transition_ticket(session.issue_key, target_status)
        console.print(f"[green]✓[/green] issue tracker ticket {session.issue_key} → {target_status}")
        # Update session's cached JIRA status
        if not session.issue_metadata:
            session.issue_metadata = {}
        session.issue_metadata["status"] = target_status
        return True

    except (JiraValidationError, JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError) as e:
        console.print(f"[yellow]⚠[/yellow] Failed to transition issue tracker ticket: {e}")
        return True  # Don't block completion on JIRA failure


def _handle_transition_failure(issue_key: str, target_status: str, on_fail: str) -> None:
    """Handle JIRA transition failure according to config.

    Args:
        issue_key: issue tracker key
        target_status: Target status that failed
        on_fail: Failure handling mode ("warn" or "error")
    """
    if on_fail == "warn":
        console.print(
            f"[yellow]⚠[/yellow] Could not transition {issue_key} to {target_status}"
        )
        console.print("[dim]Continuing without JIRA update[/dim]")
    else:  # error
        console.print(f"[red]✗[/red] Failed to transition {issue_key} to {target_status}")
        console.print("[red]JIRA transition required by configuration[/red]")
