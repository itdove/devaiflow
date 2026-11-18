"""Issue closure and safe session worktree cleanup commands."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm, Prompt

from devflow.cli.utils import (
    is_json_mode,
    is_non_interactive,
    output_json,
    require_outside_claude,
)
from devflow.config.loader import ConfigLoader
from devflow.issue_tracker.factory import create_issue_tracker_client
from devflow.issue_tracker.status import (
    issue_is_closed,
    ticket_matches_closed_transition,
)
from devflow.session.manager import SessionManager
from devflow.utils.backend_detection import (
    detect_backend_from_key,
    get_backend_display_name,
    get_issue_tracker_backend,
)
from devflow.utils.clone_lifecycle import TemporaryDirectoryInUseError
from devflow.utils.paths import is_mock_mode
from devflow.utils.session_worktree import (
    SessionWorktreeBranchUnmergedError,
    SessionWorktreeCleanupError,
    SessionWorktreeError,
    cleanup_session_worktree,
    delete_local_session_branch,
    inspect_local_session_branch,
    worktree_source_fingerprint,
)

console = Console()


@dataclass(frozen=True)
class RecordedWorktree:
    """A worktree path recorded by a session conversation."""

    session_name: str
    session_status: str
    working_directory: str
    path: Path
    source_path: Path | None
    branch: str | None
    source_fingerprint: str | None


@dataclass(frozen=True)
class RecordedBranch:
    """A local branch recorded by a completed session conversation."""

    source_path: Path | None
    branch: str
    worktree_path: Path | None
    source_fingerprint: str | None
    ambiguous: bool = False


def _recorded_worktrees(
    sessions: list[Any], issue_key: str, *, completed_only: bool = True
) -> list[RecordedWorktree]:
    """Collect unique worktrees linked to this exact issue."""
    by_path: dict[str, RecordedWorktree] = {}
    duplicate_paths: set[str] = set()

    for session in sessions:
        if session.issue_key != issue_key or (
            completed_only and session.status != "complete"
        ):
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
                    session_status=session.status,
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


def _recorded_branches(sessions: list[Any], issue_key: str) -> list[RecordedBranch]:
    """Collect unique local branches recorded by completed sessions for an issue."""
    by_ref: dict[tuple[str | None, str], RecordedBranch] = {}
    for session in sessions:
        if session.issue_key != issue_key or session.status != "complete":
            continue
        for conversation in session.conversations.values():
            for context in conversation.get_all_sessions():
                if not context.branch:
                    continue
                worktree_path = (
                    Path(context.worktree_path).expanduser()
                    if context.worktree_path
                    else None
                )
                source_value = (
                    context.original_project_path
                    if context.worktree_path
                    else context.project_path
                )
                try:
                    source_path = (
                        Path(source_value).expanduser().resolve(strict=False)
                        if source_value
                        else None
                    )
                    if worktree_path:
                        worktree_path = worktree_path.resolve(strict=False)
                except (OSError, RuntimeError) as error:
                    raise ValueError(
                        f"Session '{session.name}' has an invalid branch repository path; "
                        "refusing to delete its branch"
                    ) from error
                ref_key = (str(source_path) if source_path else None, context.branch)
                candidate = RecordedBranch(
                    source_path=source_path,
                    branch=context.branch,
                    worktree_path=worktree_path,
                    source_fingerprint=context.worktree_source_fingerprint,
                )
                existing = by_ref.get(ref_key)
                if existing is None:
                    by_ref[ref_key] = candidate
                elif existing.ambiguous:
                    continue
                elif (
                    existing.source_fingerprint != candidate.source_fingerprint
                    or existing.worktree_path != candidate.worktree_path
                ):
                    # Keep conflicting claims visible; the caller will preserve
                    # that branch instead of guessing which workspace owns it.
                    by_ref[ref_key] = RecordedBranch(
                        source_path=source_path,
                        branch=context.branch,
                        worktree_path=None,
                        source_fingerprint=None,
                        ambiguous=True,
                    )
    return list(by_ref.values())


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


def _backend_for_close(issue_key: str, sessions: list[Any], config: Any) -> str:
    """Resolve the tracker from exact session metadata, then the key/config."""
    backends = {
        get_issue_tracker_backend(session, config)
        for session in sessions
        if session.issue_key == issue_key
    }
    if len(backends) > 1:
        raise ValueError(
            f"Sessions for {issue_key} disagree about the issue-tracker backend"
        )
    if backends:
        return next(iter(backends))

    detected = detect_backend_from_key(issue_key, config)
    if detected == "jira":
        return detected
    configured = getattr(config, "issue_tracker_backend", None)
    # Hash-qualified IDs cannot distinguish GitHub from GitLab; retain an
    # explicitly configured GitLab backend, otherwise prefer the key's GitHub form.
    if "#" in issue_key:
        return configured if configured in {"github", "gitlab", "mock"} else detected
    return configured or detected


def _jira_closed_transition_target(tracker: Any, issue_key: str, config: Any) -> str:
    """Choose only a currently available JIRA transition into a closed status."""
    response = tracker._api_request("GET", f"/rest/api/2/issue/{issue_key}/transitions")
    if response.status_code != 200:
        raise RuntimeError(
            f"Could not inspect available JIRA transitions (HTTP {response.status_code})"
        )
    payload = response.json()
    transitions = payload.get("transitions") if isinstance(payload, dict) else None
    if not isinstance(transitions, list):
        raise TypeError("JIRA returned an invalid transitions response")

    targets: list[str] = []
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        target = transition.get("to")
        if not isinstance(target, dict):
            continue
        name = target.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        category = target.get("statusCategory")
        status: dict[str, Any] = {"status": name}
        if isinstance(category, dict):
            status["status_category"] = category
        if issue_is_closed(status, "jira") and name not in targets:
            targets.append(name)

    jira_config = getattr(config, "jira", None)
    configured_transitions = getattr(jira_config, "transitions", None)
    on_complete = (
        configured_transitions.get("on_complete")
        if isinstance(configured_transitions, dict)
        else None
    )
    configured_target = getattr(on_complete, "to", "")
    if isinstance(configured_target, str) and configured_target.strip():
        selected = next(
            (
                target
                for target in targets
                if target.casefold() == configured_target.strip().casefold()
            ),
            None,
        )
        if selected is None:
            raise RuntimeError(
                f"Configured JIRA on_complete target '{configured_target}' is not an "
                "available transition to a closed status"
            )
        return selected

    if not targets:
        raise RuntimeError(
            "JIRA has no available transition to a closed status; configure "
            "jira.transitions.on_complete.to or update the issue workflow"
        )
    if len(targets) == 1:
        return targets[0]
    if is_json_mode() or is_non_interactive():
        raise RuntimeError(
            "JIRA offers multiple closed-status transitions; configure "
            "jira.transitions.on_complete.to to select one"
        )

    console.print(f"Available closed-status transitions for {issue_key}:")
    for index, target in enumerate(targets, start=1):
        console.print(f"  {index}. {escape(target)}")
    choice = Prompt.ask(
        "Select the closed status",
        choices=[str(index) for index in range(1, len(targets) + 1)],
        default="1",
    )
    return targets[int(choice) - 1]


def _close_and_verify_issue(
    tracker: Any, backend: str, issue_key: str, config: Any
) -> tuple[str, bool]:
    """Close an issue and verify the resulting tracker state before cleanup."""
    current = tracker.get_ticket(issue_key)
    if not isinstance(current, dict):
        raise TypeError("The issue tracker returned an invalid issue response")
    if issue_is_closed(current, backend):
        return str(current.get("status") or "closed"), False

    target = (
        _jira_closed_transition_target(tracker, issue_key, config)
        if backend == "jira"
        else "closed"
    )
    tracker.transition_ticket(issue_key, target)
    verified = tracker.get_ticket(issue_key)
    if not isinstance(verified, dict) or not ticket_matches_closed_transition(
        verified, backend, target if backend == "jira" else None
    ):
        reported = verified.get("status") if isinstance(verified, dict) else None
        raise RuntimeError(
            "the tracker did not confirm a closed status after the transition "
            f"(reported status: {reported or 'unknown'})"
        )
    return str(verified.get("status") or target), True


def _worktree_claimed_by_other_issue(
    sessions: list[Any], issue_key: str, worktree_path: Path
) -> str | None:
    """Find a different issue session that records the same worktree path."""
    target = worktree_path.resolve(strict=False)
    for session in sessions:
        if session.issue_key == issue_key:
            continue
        for conversation in session.conversations.values():
            for context in conversation.get_all_sessions():
                if not context.worktree_path:
                    continue
                try:
                    claimed = (
                        Path(context.worktree_path).expanduser().resolve(strict=False)
                    )
                except (OSError, RuntimeError):
                    continue
                if claimed == target:
                    return session.name
    return None


def _branch_claimed_by_other_issue(
    sessions: list[Any], issue_key: str, branch: RecordedBranch
) -> str | None:
    """Find a different issue session that records the same local branch."""
    if not branch.source_path:
        return None
    target_source = branch.source_path.resolve(strict=False)
    for session in sessions:
        if session.issue_key == issue_key:
            continue
        for conversation in session.conversations.values():
            for context in conversation.get_all_sessions():
                if context.branch != branch.branch:
                    continue
                source_value = (
                    context.original_project_path
                    if context.worktree_path
                    else context.project_path
                )
                if not source_value:
                    continue
                try:
                    claimed_source = (
                        Path(source_value).expanduser().resolve(strict=False)
                    )
                except (OSError, RuntimeError):
                    continue
                if claimed_source == target_source:
                    return session.name
    return None


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


@click.command(name="close")
@click.argument("issue_key")
@click.option(
    "--delete-local-files",
    is_flag=True,
    help="Offer a separate confirmation to permanently delete local worktree data",
)
@click.option("--json", "output_json_flag", is_flag=True, help="Output in JSON format")
@require_outside_claude
def close_issue(
    issue_key: str, delete_local_files: bool, output_json_flag: bool
) -> None:
    """Close ISSUE_KEY and safely clean its recorded worktrees and local branches.

    Issue closure is verified with the configured tracker before workspace cleanup.
    Worktree data is preserved by default, and unmerged branches require a separate
    interactive confirmation before force deletion.
    """
    if output_json_flag:
        ctx = click.get_current_context()
        if not ctx.obj:
            ctx.obj = {}
        ctx.obj["output_json"] = True

    config_loader = ConfigLoader()
    config = config_loader.load_config()
    if config is None:
        config = config_loader.create_default_config()
    sessions = list(SessionManager(config_loader).index.sessions.values())
    matching_sessions = [
        session for session in sessions if session.issue_key == issue_key
    ]

    try:
        backend = _backend_for_close(issue_key, matching_sessions, config)
    except ValueError as error:
        _fail(str(error), "ISSUE_TRACKER_BACKEND_AMBIGUOUS")
    if is_mock_mode():
        backend = "mock"

    preflight_errors: list[str] = []
    try:
        worktrees = _recorded_worktrees(
            matching_sessions, issue_key, completed_only=False
        )
    except ValueError as error:
        worktrees = []
        preflight_errors.append(str(error))
    try:
        branches = _recorded_branches(matching_sessions, issue_key)
    except ValueError as error:
        branches = []
        preflight_errors.append(str(error))

    try:
        tracker = create_issue_tracker_client(backend=backend)
        issue_status, transitioned = _close_and_verify_issue(
            tracker, backend, issue_key, config
        )
    except Exception as error:  # noqa: BLE001
        _fail(
            f"Could not close and verify issue {issue_key} with {backend}; "
            f"all worktrees and branches were preserved: {error}",
            "ISSUE_CLOSE_FAILED",
        )

    worktrees_removed: list[str] = []
    worktrees_preserved: list[dict[str, str]] = []
    removed_paths: set[str] = set()

    if not is_json_mode():
        action = "Closed" if transitioned else "Issue was already closed"
        console.print(
            f"[green]✓[/green] {action}: {escape(issue_key)} "
            f"({escape(get_backend_display_name(backend))}, "
            f"status: {escape(issue_status)})"
        )

    if preflight_errors:
        reason = "; ".join(preflight_errors)
        worktrees_preserved.append({"path": issue_key, "reason": reason})
        if not is_json_mode():
            console.print(
                f"[yellow]⚠[/yellow] Preserved workspace associations: "
                f"{escape(reason)}"
            )
    else:
        for recorded in worktrees:
            if recorded.session_status != "complete":
                reason = (
                    f"{recorded.path}: session '{recorded.session_name}' is "
                    f"{recorded.session_status}, not complete; it was preserved"
                )
                worktrees_preserved.append(
                    {"path": str(recorded.path), "reason": reason}
                )
                if not is_json_mode():
                    console.print(
                        f"[yellow]⚠[/yellow] Preserved worktree: {escape(reason)}"
                    )
                continue
            other_owner = _worktree_claimed_by_other_issue(
                sessions, issue_key, recorded.path
            )
            if other_owner:
                reason = (
                    f"{recorded.path}: also recorded by session '{other_owner}' "
                    "for a different issue; it was preserved"
                )
                worktrees_preserved.append(
                    {"path": str(recorded.path), "reason": reason}
                )
                if not is_json_mode():
                    console.print(
                        f"[yellow]⚠[/yellow] Preserved worktree: {escape(reason)}"
                    )
                continue

            removed, error = _clean_one_worktree(
                recorded,
                delete_local_files=delete_local_files,
                config=config,
            )
            if removed:
                path_key = str(recorded.path.resolve(strict=False))
                removed_paths.add(path_key)
                worktrees_removed.append(str(recorded.path))
                if not is_json_mode():
                    console.print(
                        f"[green]✓[/green] Removed worktree "
                        f"{escape(str(recorded.path))}"
                    )
            else:
                reason = error or "worktree was preserved"
                worktrees_preserved.append(
                    {"path": str(recorded.path), "reason": reason}
                )
                if not is_json_mode():
                    console.print(
                        f"[yellow]⚠[/yellow] Preserved worktree: {escape(reason)}"
                    )

    branches_deleted: list[dict[str, str]] = []
    branches_already_absent: list[dict[str, str]] = []
    branches_preserved: list[dict[str, str]] = []
    for recorded in branches:
        ref_label = (
            f"{recorded.source_path or '<unknown repository>'}:{recorded.branch}"
        )
        source_path = recorded.source_path
        branch_reason: str | None = None
        if preflight_errors:
            branch_reason = "session workspace associations could not be validated; branch was preserved"
        elif recorded.ambiguous:
            branch_reason = (
                "conflicting session records claim this branch; it was preserved"
            )
        elif source_path is None:
            branch_reason = (
                "recorded source repository path is missing; branch was preserved"
            )
        elif recorded.worktree_path is None:
            branch_reason = (
                "no associated DAF-managed worktree was recorded; branch was preserved"
            )
        elif (
            recorded.worktree_path
            and str(recorded.worktree_path.resolve(strict=False)) not in removed_paths
        ):
            branch_reason = (
                "the associated worktree was not removed; branch was preserved"
            )
        elif _branch_claimed_by_other_issue(sessions, issue_key, recorded):
            branch_reason = (
                "another issue session records this branch; it was preserved"
            )

        if branch_reason:
            branches_preserved.append({"branch": ref_label, "reason": branch_reason})
            if not is_json_mode():
                console.print(
                    f"[yellow]⚠[/yellow] Preserved branch {escape(ref_label)}: "
                    f"{escape(branch_reason)}"
                )
            continue

        assert source_path is not None
        try:
            if recorded.source_fingerprint and (
                worktree_source_fingerprint(source_path) != recorded.source_fingerprint
            ):
                raise SessionWorktreeError(
                    "The source repository no longer matches the session record"
                )
            branch_status = inspect_local_session_branch(source_path, recorded.branch)
            if branch_status is None:
                branches_already_absent.append(
                    {"branch": ref_label, "status": "already absent"}
                )
                continue

            force_unmerged = False
            if not branch_status.merged:
                prompt = (
                    f"Branch {recorded.branch} is not merged into the current "
                    f"source checkout. Force-delete it from {source_path}?"
                )
                if is_json_mode() or is_non_interactive():
                    raise SessionWorktreeBranchUnmergedError(
                        "the branch is unmerged and requires an interactive "
                        "confirmation; it was preserved"
                    )
                if not Confirm.ask(prompt, default=False):
                    raise SessionWorktreeBranchUnmergedError(
                        "force deletion was not approved; the branch was preserved"
                    )
                force_unmerged = True

            deleted = delete_local_session_branch(
                source_path,
                recorded.branch,
                expected_revision=branch_status.revision,
                force_unmerged=force_unmerged,
            )
            if deleted:
                branches_deleted.append({"branch": ref_label})
                if not is_json_mode():
                    console.print(
                        f"[green]✓[/green] Deleted local branch {escape(ref_label)}"
                    )
            else:
                branches_already_absent.append(
                    {"branch": ref_label, "status": "already absent"}
                )
        except (SessionWorktreeError, OSError) as error:
            branches_preserved.append({"branch": ref_label, "reason": str(error)})
            if not is_json_mode():
                console.print(
                    f"[yellow]⚠[/yellow] Preserved branch {escape(ref_label)}: "
                    f"{escape(str(error))}"
                )

    result = {
        "issue_key": issue_key,
        "backend": backend,
        "issue_status": issue_status,
        "transitioned": transitioned,
        "worktrees_removed": worktrees_removed,
        "worktrees_preserved": worktrees_preserved,
        "branches_deleted": branches_deleted,
        "branches_already_absent": branches_already_absent,
        "branches_preserved": branches_preserved,
    }
    has_preserved = bool(worktrees_preserved or branches_preserved)
    if is_json_mode():
        output_json(
            success=not has_preserved,
            data=result,
            error=(
                {
                    "code": "ISSUE_CLOSED_CLEANUP_PARTIAL",
                    "worktrees": worktrees_preserved,
                    "branches": branches_preserved,
                }
                if has_preserved
                else None
            ),
        )
    if has_preserved:
        raise click.exceptions.Exit(1)
