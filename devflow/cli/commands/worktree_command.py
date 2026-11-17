"""Cleanup-only commands for completed session worktrees."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm

from devflow.cli.utils import (
    is_json_mode,
    is_non_interactive,
    output_json,
    require_outside_claude,
)
from devflow.config.loader import ConfigLoader
from devflow.issue_tracker.factory import create_issue_tracker_client
from devflow.issue_tracker.status import issue_is_closed
from devflow.session.manager import SessionManager
from devflow.utils.backend_detection import get_issue_tracker_backend
from devflow.utils.clone_lifecycle import TemporaryDirectoryInUseError
from devflow.utils.session_worktree import (
    SessionWorktreeCleanupError,
    SessionWorktreeError,
    cleanup_session_worktree,
)

console = Console()


@dataclass(frozen=True)
class RecordedWorktree:
    """A worktree path recorded by a completed session conversation."""

    session_name: str
    working_directory: str
    path: Path
    source_path: Path | None
    branch: str | None
    source_fingerprint: str | None


def _recorded_worktrees(sessions: list[Any], issue_key: str) -> list[RecordedWorktree]:
    """Collect unique worktrees from completed sessions linked to this exact issue."""
    by_path: dict[str, RecordedWorktree] = {}
    duplicate_paths: set[str] = set()

    for session in sessions:
        if session.issue_key != issue_key or session.status != "complete":
            continue
        for working_directory, conversation in session.conversations.items():
            for context in conversation.get_all_sessions():
                if not context.worktree_path:
                    continue
                path = Path(context.worktree_path).expanduser()
                try:
                    path_key = str(path.resolve(strict=False))
                    project_path = (
                        Path(context.project_path).expanduser().resolve(strict=False)
                        if context.project_path
                        else None
                    )
                except (OSError, RuntimeError) as error:
                    raise ValueError(
                        f"Session '{session.name}' has an invalid worktree path; "
                        f"refusing to remove {path}"
                    ) from error
                if project_path is None or str(project_path) != path_key:
                    raise ValueError(
                        f"Session '{session.name}' does not record the worktree as its project path; "
                        f"refusing to remove {path}"
                    )
                candidate = RecordedWorktree(
                    session_name=session.name,
                    working_directory=working_directory,
                    path=path,
                    source_path=(
                        Path(context.original_project_path).expanduser()
                        if context.original_project_path
                        else None
                    ),
                    branch=context.branch,
                    source_fingerprint=context.worktree_source_fingerprint,
                )
                existing = by_path.get(path_key)
                if existing:
                    if existing == candidate:
                        # A session's archived and active conversations can share
                        # the same worktree; identical ownership records are one claim.
                        continue
                    duplicate_paths.add(path_key)
                    continue
                by_path[path_key] = candidate

    if duplicate_paths:
        paths = ", ".join(sorted(duplicate_paths))
        raise ValueError(
            "Multiple session conversations claim the same worktree; refusing to guess "
            f"which session owns it: {paths}"
        )
    return list(by_path.values())


def _fail(message: str, code: str) -> None:
    """Emit a consistent failure result and stop the command."""
    if is_json_mode():
        output_json(success=False, error={"code": code, "message": message})
    else:
        console.print(f"[red]✗[/red] {escape(message)}")
    raise click.exceptions.Exit(1)


def _clean_one_worktree(
    worktree: RecordedWorktree,
    *,
    delete_local_files: bool,
    config: Any,
) -> tuple[bool, str | None]:
    """Remove one verified worktree, optionally after a separate data-loss prompt."""
    if not worktree.source_path:
        return False, f"{worktree.path}: recorded source repository path is missing"
    if not worktree.branch:
        return False, f"{worktree.path}: recorded session branch is missing"

    cleanup_args = {
        "expected_source_fingerprint": worktree.source_fingerprint,
        "expected_branch": worktree.branch,
        "config": config,
    }
    try:
        cleanup_session_worktree(worktree.path, worktree.source_path, **cleanup_args)
        return True, None
    except SessionWorktreeCleanupError as error:
        changes = error.changes
        if not changes or not delete_local_files:
            return False, str(error)

        if not is_json_mode():
            console.print(
                f"[yellow]⚠[/yellow] Worktree [bold]{escape(str(changes.path))}[/bold] "
                f"contains local data ({changes.summary()})."
            )
        if is_json_mode() or is_non_interactive():
            return False, (
                f"{changes.path}: local data was preserved ({changes.summary()}); deleting it "
                "requires an interactive confirmation"
            )

        if not Confirm.ask(
            f"Permanently delete this local data and remove {changes.path}?",
            default=False,
        ):
            return False, (
                f"{changes.path}: local data was preserved by user choice "
                f"({changes.summary()})"
            )

        try:
            cleanup_session_worktree(
                worktree.path,
                worktree.source_path,
                delete_local_files=True,
                expected_changes=changes,
                **cleanup_args,
            )
            return True, None
        except (
            TemporaryDirectoryInUseError,
            SessionWorktreeError,
            OSError,
        ) as retry_error:
            return False, str(retry_error)
    except (TemporaryDirectoryInUseError, SessionWorktreeError, OSError) as error:
        return False, f"{worktree.path}: {error}"


@click.group()
def worktree() -> None:
    """Manage session worktrees."""


@worktree.command(name="clean")
@click.argument("issue_key")
@click.option(
    "--delete-local-files",
    is_flag=True,
    help="Offer a separate confirmation to permanently delete local worktree data",
)
@click.option("--json", "output_json_flag", is_flag=True, help="Output in JSON format")
@require_outside_claude
def clean_worktree(
    issue_key: str, delete_local_files: bool, output_json_flag: bool
) -> None:
    """Retry cleanup for worktrees belonging to completed sessions of ISSUE_KEY.

    The configured issue tracker must confirm the issue is closed. Local,
    untracked, and ignored files are preserved unless --delete-local-files is
    supplied and the user separately confirms their deletion.
    """
    if output_json_flag:
        # The shared helper reads Click's context for JSON output selection.
        ctx = click.get_current_context()
        if not ctx.obj:
            ctx.obj = {}
        ctx.obj["output_json"] = True

    config_loader = ConfigLoader()
    config = config_loader.load_config()
    session_manager = SessionManager(config_loader)
    sessions = list(session_manager.index.sessions.values())
    matching_sessions = [
        session for session in sessions if session.issue_key == issue_key
    ]
    if not matching_sessions:
        _fail(f"No session is recorded for issue {issue_key}.", "SESSION_NOT_FOUND")

    try:
        worktrees = _recorded_worktrees(matching_sessions, issue_key)
    except ValueError as error:
        code = (
            "WORKTREE_ASSOCIATION_AMBIGUOUS"
            if "Multiple session conversations" in str(error)
            else "WORKTREE_ASSOCIATION_INVALID"
        )
        _fail(str(error), code)

    if not worktrees:
        result = {
            "issue_key": issue_key,
            "cleaned": [],
            "preserved": [],
            "message": "No worktrees are recorded for completed sessions.",
        }
        if is_json_mode():
            output_json(success=True, data=result)
        else:
            console.print(
                f"[dim]No worktrees are recorded for completed sessions of {issue_key}.[/dim]"
            )
        return

    backends = {
        get_issue_tracker_backend(session, config)
        for session in matching_sessions
        if session.status == "complete"
    }
    if len(backends) != 1:
        _fail(
            f"Could not determine one issue-tracker backend for {issue_key}; no worktrees were removed.",
            "ISSUE_TRACKER_BACKEND_UNKNOWN",
        )
    backend = next(iter(backends))

    try:
        tracker = create_issue_tracker_client(backend=backend)
        ticket = tracker.get_ticket(issue_key)
    # Any tracker error must fail closed and preserve the worktrees.
    except Exception as error:  # noqa: BLE001
        _fail(
            f"Could not verify issue {issue_key} with {backend}; all worktrees were preserved: {error}",
            "ISSUE_STATUS_UNVERIFIED",
        )

    if not isinstance(ticket, dict) or not issue_is_closed(ticket, backend):
        current_status = ticket.get("status") if isinstance(ticket, dict) else None
        _fail(
            f"Issue {issue_key} is not confirmed closed by {backend} "
            f"(reported status: {current_status or 'unknown'}); all worktrees were preserved.",
            "ISSUE_NOT_CLOSED",
        )

    if not is_json_mode():
        console.print(f"[dim]Issue {issue_key} is confirmed closed by {backend}.[/dim]")

    cleaned: list[str] = []
    preserved: list[dict[str, str]] = []
    for recorded in worktrees:
        removed, error = _clean_one_worktree(
            recorded,
            delete_local_files=delete_local_files,
            config=config,
        )
        if removed:
            cleaned.append(str(recorded.path))
            if not is_json_mode():
                console.print(
                    f"[green]✓[/green] Removed worktree {escape(str(recorded.path))}"
                )
        else:
            reason = error or "worktree was preserved"
            preserved.append({"path": str(recorded.path), "reason": reason})
            if not is_json_mode():
                console.print(
                    f"[yellow]⚠[/yellow] Preserved worktree: {escape(reason)}"
                )

    result = {"issue_key": issue_key, "cleaned": cleaned, "preserved": preserved}
    if is_json_mode():
        output_json(
            success=not preserved,
            data=result if not preserved else None,
            error=(
                {"code": "WORKTREE_CLEANUP_FAILED", "worktrees": preserved}
                if preserved
                else None
            ),
        )
    if preserved:
        raise click.exceptions.Exit(1)
