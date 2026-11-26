"""GitLab issue state transitions for completed DevAIFlow sessions."""

from collections.abc import Callable

from rich.console import Console
from rich.prompt import Prompt

# Kept as an alias for integrations/tests that patched the former confirmation prompt.
Confirm = Prompt

from devflow.cli.utils import is_non_interactive
from devflow.config.models import Config, Session
from devflow.gitlab.issues_client import GitLabClient

console = Console()


def _completion_transition(config: Config) -> object | None:
    """Return the shared ``on_complete`` workflow rule when configured."""
    jira = getattr(config, "jira", None)
    transitions = getattr(jira, "transitions", None) if jira else None
    return transitions.get("on_complete") if isinstance(transitions, dict) else None


def _prompt_status(
    issue_key: str, current_state: str, options: list[tuple[str, str]]
) -> str | None:
    """Prompt for a GitLab status target, returning ``None`` to preserve it."""
    console.print(f"\n[bold]Select GitLab status for {issue_key}[/bold]")
    console.print(f"Current issue state: {current_state or 'unknown'}")
    choices = [("Skip (keep current status)", "skip"), *options]
    for index, (label, _value) in enumerate(choices, 1):
        console.print(f"  {index}. {label}")
    choice = Prompt.ask(
        "Select target status",
        choices=[str(index) for index in range(1, len(choices) + 1)],
        default="1",
    )
    if isinstance(choice, bool):
        return "closed" if choice else None
    selected = choices[int(choice) - 1][1]
    if selected == "skip":
        console.print("[dim]GitLab status update skipped[/dim]")
        return None
    return selected


def transition_on_complete(
    session: Session,
    config: Config,
    client: GitLabClient | None = None,
    no_issue_update: bool = False,
    on_close_approved: Callable[[], None] | None = None,
) -> bool:
    """Offer to close the GitLab issue and report explicit approval to callers.

    Automatic closure is enabled only by the explicit
    ``gitlab.auto_close_on_complete`` configuration. Regardless of the choice,
    callers must perform a fresh status lookup before destructive cleanup.
    """
    if not session.issue_key or no_issue_update:
        return True

    try:
        client = client or GitLabClient()
        issue = client.get_ticket(session.issue_key)
        current_state = issue.get("status")
        if not isinstance(current_state, str):
            console.print(
                f"[yellow]⚠[/yellow] GitLab issue {session.issue_key} has an unknown state; "
                "it was not closed."
            )
            return True
        current_state = current_state.strip().casefold()
        if current_state == "closed":
            console.print(
                f"[dim]GitLab issue {session.issue_key} is already closed.[/dim]"
            )
            return True
        if current_state != "open":
            console.print(
                f"[yellow]⚠[/yellow] GitLab issue {session.issue_key} has an unknown state "
                f"({current_state}); it was not closed."
            )
            return True

        add_status_label = bool(
            config.gitlab and getattr(config.gitlab, "add_status_labels", False)
        )
        completion_label = (
            getattr(config.gitlab, "completion_label", "status: in-review")
            if config.gitlab
            else "status: in-review"
        )
        current_labels = issue.get("labels", [])
        if not isinstance(current_labels, list):
            current_labels = []
        transition_config = _completion_transition(config)
        configured_target = str(getattr(transition_config, "to", "") or "").strip()
        configured_prompt = bool(getattr(transition_config, "prompt", False))
        should_close = bool(
            config.gitlab
            and getattr(config.gitlab, "auto_close_on_complete", False) is True
        )
        selected_status: str | None = None
        if transition_config and not configured_prompt and not configured_target:
            console.print(
                "[dim]GitLab completion transition skipped (no target configured)[/dim]"
            )
            return True
        if transition_config and not configured_prompt:
            target = configured_target.casefold()
            should_close = target in {
                "closed",
                "close",
                "done",
                "completed",
                "complete",
                "resolved",
            }
            selected_status = "closed" if should_close else "open"
            console.print(
                f"[dim]Automatically selecting GitLab status '{configured_target}'[/dim]"
            )
        elif should_close:
            console.print(
                "[dim]Automatically closing issue (configured in "
                "config.gitlab.auto_close_on_complete)[/dim]"
            )
        elif is_non_interactive():
            selected_status = (
                f"label:{completion_label}" if add_status_label else "open"
            )
        elif configured_prompt or not transition_config:
            selected_status = _prompt_status(
                session.issue_key,
                current_state,
                [
                    ("Open", "open"),
                    ("Closed", "closed"),
                    *(
                        [(completion_label, f"label:{completion_label}")]
                        if add_status_label
                        else []
                    ),
                ],
            )
            should_close = selected_status == "closed"

        if not should_close:
            if (
                current_state == "open"
                and selected_status
                and selected_status.startswith("label:")
            ):
                new_labels = [
                    label for label in current_labels if not label.startswith("status:")
                ]
                new_labels.append(selected_status.removeprefix("label:"))
                if set(new_labels) != set(current_labels):
                    try:
                        client.update_issue(session.issue_key, {"labels": new_labels})
                        console.print(
                            f"[green]✓[/green] Updated status to '{new_labels[-1]}'"
                        )
                    except Exception as error:  # noqa: BLE001
                        console.print(
                            f"[yellow]⚠[/yellow] Could not update GitLab labels: {error}"
                        )
            elif current_state == "open" and selected_status == "open":
                console.print(
                    "[dim]GitLab issue remains open; no labels were changed[/dim]"
                )
            return True

        if on_close_approved:
            on_close_approved()
        try:
            if current_labels and any(
                label.startswith("status:") for label in current_labels
            ):
                new_labels = [
                    label for label in current_labels if not label.startswith("status:")
                ]
                client.update_issue(session.issue_key, {"labels": new_labels})
            client.transition_ticket(session.issue_key, "closed")
            console.print("[green]✓[/green] Closed GitLab issue")
        # A transition failure should warn but must not block completion.
        except Exception as error:  # noqa: BLE001
            console.print(f"[yellow]⚠[/yellow] Could not close GitLab issue: {error}")
        return True
    # Lookup failures are non-fatal to completion and preserve worktrees.
    except Exception as error:  # noqa: BLE001
        console.print(
            f"[yellow]⚠[/yellow] Could not read or update GitLab issue "
            f"{session.issue_key}: {error}"
        )
        return True
