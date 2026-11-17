"""GitLab issue state transitions for completed DevAIFlow sessions."""

from collections.abc import Callable

from rich.console import Console
from rich.prompt import Confirm

from devflow.config.models import Config, Session
from devflow.gitlab.issues_client import GitLabClient

console = Console()


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

        should_close = bool(
            config.gitlab
            and getattr(config.gitlab, "auto_close_on_complete", False) is True
        )
        if should_close:
            console.print(
                "[dim]Automatically closing issue (configured in "
                "config.gitlab.auto_close_on_complete)[/dim]"
            )
        else:
            should_close = Confirm.ask(
                f"\nClose GitLab issue {session.issue_key}?", default=False
            )

        if not should_close:
            return True

        if on_close_approved:
            on_close_approved()
        try:
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
