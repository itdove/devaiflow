"""GitHub issue state transitions for DevAIFlow sessions.

This module handles GitHub issue state transitions when starting or completing work.
Unlike JIRA's complex workflow states, GitHub has binary state (open/closed) with
optional status labels for intermediate states.
"""

from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.prompt import Prompt

from devflow.cli.utils import is_non_interactive
from devflow.config.models import Config, Session
from devflow.github.issues_client import GitHubClient
from devflow.issue_tracker.exceptions import (
    IssueTrackerApiError,
    IssueTrackerAuthError,
    IssueTrackerNotFoundError,
)

console = Console()


def _prompt_status(
    issue_key: str, current_state: str, options: list[tuple[str, str]]
) -> tuple[str, str] | None:
    """Prompt for a status target, returning ``None`` for an explicit skip."""
    console.print(f"\n[bold]Select GitHub status for {issue_key}[/bold]")
    console.print(f"Current issue state: {current_state or 'unknown'}")
    choices = [("Skip (keep current status)", "skip"), *options]
    for index, (label, _value) in enumerate(choices, 1):
        console.print(f"  {index}. {label}")
    choice = Prompt.ask(
        "Select target status",
        choices=[str(index) for index in range(1, len(choices) + 1)],
        default="1",
    )
    selected = choices[int(choice) - 1]
    if selected[1] == "skip":
        console.print("[dim]GitHub status update skipped[/dim]")
        return None
    return selected


def _completion_transition(config: Config) -> Any:
    """Return the shared ``on_complete`` workflow rule when configured."""
    jira = getattr(config, "jira", None)
    transitions = getattr(jira, "transitions", None) if jira else None
    return transitions.get("on_complete") if isinstance(transitions, dict) else None


def transition_on_start(
    session: Session, config: Config, client: GitHubClient | None = None
) -> bool:
    """Transition GitHub issue when starting work on a session.

    GitHub has binary state (open/closed), so we use labels for workflow status.
    This function:
    1. Ensures issue is open
    2. Adds 'status: in-progress' label (optional, based on config)
    3. Removes 'status: blocked' label if present

    Args:
        session: Session being started
        config: Configuration object
        client: Optional pre-initialized GitHubClient

    Returns:
        True if transition succeeded or was skipped, False if failed

    Note:
        GitHub transitions are less strict than JIRA. We don't block session
        start if transition fails - just log a warning.
    """
    # Skip if no issue key
    if not session.issue_key:
        console.print("[dim]No issue key set, skipping GitHub transition[/dim]")
        return True

    # Create client if not provided
    if not client:
        try:
            client = GitHubClient()
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Could not initialize GitHub client: {e}")
            return True  # Don't block session start

    try:
        # Fetch current issue state
        issue = client.get_ticket(session.issue_key)
        current_state = issue.get("status", "").lower()

        # If issue is closed, reopen it (optional - could prompt user)
        if current_state == "closed":
            console.print(
                f"[yellow]ℹ[/yellow] Issue {session.issue_key} is closed, reopening..."
            )
            client.transition_ticket(session.issue_key, "open")
            console.print(f"[green]✓[/green] Reopened issue")

        # Get current labels
        current_labels = issue.get("labels", [])

        # Add 'status: in-progress' label only if configured
        add_status_label = False
        if config.github and hasattr(config.github, "add_status_labels"):
            add_status_label = config.github.add_status_labels

        if add_status_label:
            # Build new label set
            new_labels = [
                label for label in current_labels if not label.startswith("status:")
            ]
            new_labels.append("status: in-progress")

            # Update labels if changed
            if set(new_labels) != set(current_labels):
                try:
                    client.update_issue(session.issue_key, {"labels": new_labels})
                    console.print(f"[green]✓[/green] Updated status labels")
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] Could not update labels: {e}")
        else:
            console.print(
                f"[dim]Status labels disabled (set config.github.add_status_labels=true to enable)[/dim]"
            )

        return True

    except IssueTrackerNotFoundError:
        console.print(f"[yellow]⚠[/yellow] Issue {session.issue_key} not found")
        return True  # Don't block session start for missing issues
    except IssueTrackerAuthError as e:
        console.print(f"[yellow]⚠[/yellow] GitHub authentication failed: {e}")
        console.print(f"[dim]Run 'gh auth login' to authenticate[/dim]")
        return True  # Don't block session start
    except IssueTrackerApiError as e:
        console.print(f"[yellow]⚠[/yellow] GitHub API error: {e}")
        return True  # Don't block session start
    except Exception as e:
        console.print(
            f"[yellow]⚠[/yellow] Unexpected error during GitHub transition: {e}"
        )
        return True  # Don't block session start


def transition_on_complete(
    session: Session,
    config: Config,
    client: GitHubClient | None = None,
    no_issue_update: bool = False,
    on_close_approved: Callable[[], None] | None = None,
) -> bool:
    """Transition GitHub issue when completing work on a session.

    This function:
    1. Prompts to close the issue (or uses config.github.auto_close_on_complete)
    2. Removes 'status: in-progress' label
    3. Adds 'status: completed' or 'status: in-review' label (configurable)

    Args:
        session: Session being completed
        config: Configuration object
        client: Optional pre-initialized GitHubClient
        no_issue_update: If True, skip all issue updates and prompts

    Returns:
        True if transition succeeded or was skipped, False if failed

    Note:
        Unlike JIRA, we don't require strict transitions. Failures are logged
        as warnings but don't block completion.
    """
    # Skip if no issue key
    if not session.issue_key:
        console.print("[dim]No issue key set, skipping GitHub transition[/dim]")
        return True

    # Skip if no_issue_update flag is set
    if no_issue_update:
        console.print(
            "[dim]Skipping GitHub issue update (--no-issue-update flag)[/dim]"
        )
        return True

    # Create client if not provided
    if not client:
        try:
            client = GitHubClient()
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Could not initialize GitHub client: {e}")
            return True  # Don't block completion

    try:
        # Fetch current issue
        issue = client.get_ticket(session.issue_key)
        current_labels = issue.get("labels", [])
        current_state = issue.get("status", "").lower()

        # Check if status labels are enabled
        add_status_label = False
        completion_label = "status: in-review"  # Default to in-review

        if config.github:
            add_status_label = getattr(config.github, "add_status_labels", False)
            completion_label = getattr(
                config.github, "completion_label", "status: in-review"
            )

        transition_config = _completion_transition(config)
        configured_target = str(getattr(transition_config, "to", "") or "").strip()
        configured_prompt = bool(getattr(transition_config, "prompt", False))
        # Automatic closure remains unchanged for the legacy backend setting.
        selected_status: tuple[str, str] | None = None
        should_close = False
        if transition_config and not configured_prompt and not configured_target:
            console.print(
                "[dim]GitHub completion transition skipped (no target configured)[/dim]"
            )
        elif transition_config and not configured_prompt:
            target = configured_target.casefold()
            should_close = target in {
                "closed", "close"
            }
            selected_status = (
                (configured_target, "closed")
                if should_close
                else (configured_target, f"native:{configured_target}")
            )
            console.print(
                f"[dim]Automatically selecting GitHub status '{configured_target}'[/dim]"
            )
        elif (
            config.github
            and getattr(config.github, "auto_close_on_complete", False) is True
        ):
            should_close = True
            console.print(
                "[dim]Automatically closing issue (configured in config.github.auto_close_on_complete)[/dim]"
            )
        elif is_non_interactive():
            selected_status = (
                (completion_label, f"label:{completion_label}")
                if add_status_label
                else ("Open", "open")
            )
        elif configured_prompt or not transition_config:
            if current_state == "open":
                native_options: list[tuple[str, str]] = []
                if config.github:
                    try:
                        native = client.get_issue_statuses(session.issue_key)
                        native_options = [
                            (
                                str(option.get("name", "")),
                                f"native:{option.get('name', '')}",
                            )
                            for option in native.get("statuses", [])
                            if option.get("name")
                        ]
                    except Exception as exc:
                        console.print(
                            f"[yellow]⚠[/yellow] Could not discover GitHub Issue Statuses: {exc}"
                        )
                label_options = (
                    [(completion_label, f"label:{completion_label}")]
                    if add_status_label
                    else []
                )
                selected_status = _prompt_status(
                    session.issue_key,
                    current_state,
                    [
                        *(native_options or [("Open", "open"), ("Closed", "closed")]),
                        *label_options,
                    ],
                )
                should_close = selected_status == ("Closed", "closed")
            else:
                console.print(f"[dim]Issue {session.issue_key} is already closed[/dim]")

        # Close issue if requested
        if should_close and current_state == "open":
            if on_close_approved:
                on_close_approved()
            console.print(f"[cyan]Closing issue {session.issue_key}...[/cyan]")
            try:
                # Remove all status labels when closing
                new_labels = [
                    label for label in current_labels if not label.startswith("status:")
                ]

                # Update labels first (remove status labels)
                if set(new_labels) != set(current_labels):
                    client.update_issue(session.issue_key, {"labels": new_labels})

                # Then close the issue
                client.transition_ticket(session.issue_key, "closed")
                console.print(f"[green]✓[/green] Closed issue")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Could not close issue: {e}")

        # Apply the selected non-closing representation while preserving labels.
        elif current_state == "open" and not should_close and selected_status:
            selected_value = selected_status[1]
            if selected_value.startswith("native:"):
                try:
                    client.update_issue_status(
                        session.issue_key, selected_value.removeprefix("native:")
                    )
                    console.print(
                        f"[green]✓[/green] Updated GitHub status to '{selected_status[0]}'"
                    )
                except Exception as exc:
                    console.print(f"[yellow]⚠[/yellow] Could not update GitHub status: {exc}")
            elif add_status_label:
                new_labels = [
                    label for label in current_labels if not label.startswith("status:")
                ]
                if selected_value.startswith("label:"):
                    new_labels.append(selected_value.removeprefix("label:"))

                if set(new_labels) != set(current_labels):
                    try:
                        client.update_issue(session.issue_key, {"labels": new_labels})
                        console.print(
                            f"[green]✓[/green] Updated status to '{selected_status[0]}'"
                        )
                    except Exception as e:
                        console.print(
                            f"[yellow]⚠[/yellow] Could not update labels: {e}"
                        )
            elif selected_value == "open":
                console.print(
                    f"[dim]Issue {session.issue_key} remains open; no labels were changed "
                    "(status labels are disabled; set "
                    "config.github.add_status_labels=true to enable)[/dim]"
                )

        return True

    except IssueTrackerNotFoundError:
        console.print(f"[yellow]⚠[/yellow] Issue {session.issue_key} not found")
        return True  # Don't block completion
    except IssueTrackerAuthError as e:
        console.print(f"[yellow]⚠[/yellow] GitHub authentication failed: {e}")
        return True  # Don't block completion
    except IssueTrackerApiError as e:
        console.print(f"[yellow]⚠[/yellow] GitHub API error: {e}")
        return True  # Don't block completion
    except Exception as e:
        console.print(
            f"[yellow]⚠[/yellow] Unexpected error during GitHub transition: {e}"
        )
        return True  # Don't block completion
