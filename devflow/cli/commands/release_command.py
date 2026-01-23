"""Implementation of 'daf release' command."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from devflow.cli.utils import require_outside_claude
from devflow.release.permissions import check_release_permission
from devflow.release.manager import ReleaseManager
from devflow.release.version import Version

console = Console()


def create_release(
    version: str,
    from_tag: Optional[str] = None,
    dry_run: bool = False,
    auto_push: bool = False,
    force: bool = False,
    skip_pr_fetch: bool = False,
) -> None:
    """Create a new release (minor, major, or patch).

    Args:
        version: Target version (e.g., "1.0.0")
        from_tag: Base tag for patches (default: latest tag for minor version)
        dry_run: Preview changes without executing
        auto_push: Push to remote without confirmation
        force: Force release even if tests fail (emergency use only)
        skip_pr_fetch: Skip PR/MR metadata fetching for changelog (offline mode)
    """
    # Allow dry-run to run inside Claude Code (it's read-only)
    # But block actual releases
    if not dry_run:
        from devflow.cli.utils import check_outside_ai_session
        check_outside_ai_session()

    repo_path = Path.cwd()

    # Display header
    console.print()
    console.print("[bold cyan]═══ DevAIFlow Release ═══[/bold cyan]")
    console.print()

    # Step 1: Check permissions
    console.print("[bold]Step 1:[/bold] Checking release permissions...")
    try:
        has_permission, perm_msg = check_release_permission(repo_path)
        if not has_permission:
            console.print(f"[red]✗[/red] {perm_msg}")
            console.print()
            console.print("[yellow]Release requires Maintainer or Owner access.[/yellow]")
            return
        console.print(f"[green]✓[/green] {perm_msg}")
    except ValueError as e:
        console.print(f"[red]✗[/red] Permission check failed: {e}")
        return
    console.print()

    # Step 2: Initialize release manager
    console.print("[bold]Step 2:[/bold] Preparing release...")
    manager = ReleaseManager(repo_path)

    try:
        context = manager.prepare_release(version, dry_run=dry_run)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to prepare release: {e}")
        return

    # Display release plan
    console.print(f"[green]✓[/green] Release validated")
    console.print()

    _display_release_plan(context)

    # Confirm if not dry-run and not auto-push
    if not dry_run and not auto_push:
        console.print()
        if not click.confirm("Continue with release?", default=False):
            console.print("[yellow]Release cancelled[/yellow]")
            return

    console.print()

    # Step 3: Run unit tests
    console.print("[bold]Step 3:[/bold] Running unit test suite...")
    success, output = manager.run_tests(dry_run=dry_run)
    if not success:
        console.print(f"[red]✗[/red] Unit tests failed")
        console.print()
        console.print("[yellow]Test output:[/yellow]")
        console.print(output[-1000:])  # Show last 1000 chars
        console.print()
        console.print("[red]Fix unit tests before creating release[/red]")
        return
    console.print(f"[green]✓[/green] All unit tests passed")
    console.print()

    # Step 4: Run integration tests
    console.print("[bold]Step 4:[/bold] Running integration tests...")
    console.print("[dim]This may take several minutes...[/dim]")
    success, summary, failed_tests = manager.run_integration_tests(dry_run=dry_run)

    if not success:
        console.print(f"[red]✗[/red] {summary}")
        console.print()
        console.print("[yellow]Failed tests:[/yellow]")
        for test in failed_tests:
            console.print(f"  • {test}")
        console.print()

        # Prompt user if --force is not set
        if not force and not dry_run:
            console.print("[yellow]⚠  Integration tests failed, but you can continue anyway.[/yellow]")
            if not click.confirm("Continue with release despite test failures?", default=False):
                console.print("[red]Release cancelled due to integration test failures[/red]")
                return
            console.print("[yellow]⚠  Proceeding with release despite failures[/yellow]")
        elif force:
            console.print("[yellow]⚠  Continuing with release (--force enabled)[/yellow]")
        console.print()
    else:
        console.print(f"[green]✓[/green] {summary}")
        console.print()

    # Step 5: Create branch (if needed)
    if context.release_type in ["minor", "major"]:
        console.print(f"[bold]Step 5:[/bold] Creating release branch '{context.release_branch}'...")
        success, msg = manager.create_branch(context.release_branch, from_branch=context.current_branch, dry_run=dry_run)
        if not success:
            console.print(f"[red]✗[/red] {msg}")
            return
        console.print(f"[green]✓[/green] {msg}")
    elif context.release_type == "patch":
        # For patches, user should already be on hotfix branch or we create it
        if from_tag:
            console.print(f"[bold]Step 5:[/bold] Creating hotfix branch from '{from_tag}'...")
            success, msg = manager.create_branch(context.hotfix_branch, from_branch=from_tag, dry_run=dry_run)
            if not success:
                console.print(f"[red]✗[/red] {msg}")
                return
            console.print(f"[green]✓[/green] {msg}")
        else:
            console.print(f"[bold]Step 5:[/bold] Using current branch '{context.current_branch}'...")
            console.print(f"[green]✓[/green] Ready for hotfix")

    console.print()

    # Step 6: Update version files
    console.print(f"[bold]Step 6:[/bold] Updating version to {context.target_version}...")
    try:
        manager.update_version_files(context.target_version, dry_run=dry_run)
        console.print(f"[green]✓[/green] Updated devflow/__init__.py and setup.py")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to update version files: {e}")
        return

    console.print()

    # Step 7: Update CHANGELOG
    console.print("[bold]Step 7:[/bold] Updating CHANGELOG.md...")
    if not skip_pr_fetch:
        console.print("[dim]Fetching PR/MR metadata from git history...[/dim]")

    try:
        manager.update_changelog(
            context.target_version,
            auto_generate=not skip_pr_fetch,
            dry_run=dry_run
        )
        if skip_pr_fetch:
            console.print(f"[green]✓[/green] Added version {context.target_version} to CHANGELOG.md (without auto-generated content)")
        else:
            console.print(f"[green]✓[/green] Generated changelog for {context.target_version} from PR/MR metadata")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to update CHANGELOG: {e}")
        return

    console.print()

    # Step 8: Commit changes
    console.print("[bold]Step 8:[/bold] Committing version bump...")
    commit_msg = f"""chore: bump version to {context.target_version} for release

Prepare for v{context.target_version} release:
- Update version in devflow/__init__.py
- Update version in setup.py
- Update CHANGELOG.md with release date

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

    success, msg = manager.commit_changes(commit_msg, dry_run=dry_run)
    if not success:
        console.print(f"[red]✗[/red] {msg}")
        return
    console.print(f"[green]✓[/green] {msg}")

    console.print()

    # Step 9: Create git tag
    console.print(f"[bold]Step 9:[/bold] Creating git tag '{context.tag_name}'...")
    tag_msg = f"Release version {context.target_version}\n\nSee CHANGELOG.md for details."
    success, msg = manager.create_tag(context.tag_name, tag_msg, dry_run=dry_run)
    if not success:
        console.print(f"[red]✗[/red] {msg}")
        return
    console.print(f"[green]✓[/green] {msg}")

    console.print()

    # Step 10: Bump to next dev version
    if context.release_type in ["minor", "major"]:
        # Bump release branch to next patch dev version
        console.print(f"[bold]Step 10:[/bold] Bumping release branch to {context.next_dev_version}...")
        try:
            manager.update_version_files(context.next_dev_version, dry_run=dry_run)
            commit_msg = f"""chore: bump version to {context.next_dev_version}

Begin development cycle for next patch release.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
            manager.commit_changes(commit_msg, dry_run=dry_run)
            console.print(f"[green]✓[/green] Release branch ready for development")
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Could not bump dev version: {e}")

        console.print()

        # Merge back to main and bump main to next minor dev
        console.print(f"[bold]Step 11:[/bold] Preparing main branch for next development cycle...")
        console.print(f"[dim]You'll need to manually:[/dim]")
        console.print(f"[dim]  1. git checkout main[/dim]")
        console.print(f"[dim]  2. git merge {context.release_branch} --no-ff[/dim]")
        console.print(f"[dim]  3. Update version to next minor dev version[/dim]")
        console.print(f"[dim]  4. git push origin main {context.release_branch} {context.tag_name}[/dim]")

    console.print()

    # Display summary
    _display_summary(context, dry_run, auto_push)


def _display_release_plan(context) -> None:
    """Display release plan table."""
    table = Table(title="Release Plan", show_header=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Release Type", f"[bold]{context.release_type.upper()}[/bold]")
    table.add_row("Current Version", str(context.current_version))
    table.add_row("Target Version", f"[green]{context.target_version}[/green]")
    table.add_row("Current Branch", context.current_branch)

    if context.release_branch:
        table.add_row("Release Branch", context.release_branch)
    if context.hotfix_branch:
        table.add_row("Hotfix Branch", context.hotfix_branch)

    table.add_row("Tag Name", context.tag_name)
    table.add_row("Next Dev Version", str(context.next_dev_version))

    if context.dry_run:
        table.add_row("Mode", "[yellow]DRY RUN (no changes will be made)[/yellow]")

    console.print(table)


def _display_summary(context, dry_run: bool, auto_push: bool) -> None:
    """Display release summary."""
    if dry_run:
        summary = Panel(
            "[yellow]DRY RUN COMPLETE[/yellow]\n\n"
            "No changes were made. Review the plan above and run without --dry-run to execute.",
            title="Summary",
            border_style="yellow"
        )
    else:
        push_cmds = []
        if context.release_branch:
            push_cmds.append(f"git push origin {context.release_branch}")
        push_cmds.append(f"git push origin {context.tag_name}")

        summary = Panel(
            f"[green]✓ Release {context.target_version} prepared successfully![/green]\n\n"
            f"Tag created: {context.tag_name}\n\n"
            f"[bold]Next steps:[/bold]\n"
            f"1. Review the changes\n"
            f"2. Push to remote:\n   {chr(10).join(f'   {cmd}' for cmd in push_cmds)}\n"
            f"3. Create GitLab/GitHub release from tag\n"
            f"4. Merge release branch back to main (for minor/major releases)",
            title="✓ Release Complete",
            border_style="green"
        )

    console.print(summary)
    console.print()


def approve_release(
    version: str,
    dry_run: bool = False,
) -> None:
    """Approve and complete a prepared release.

    This command completes the post-steps after `daf release` has prepared a release:
    1. Validates that release was prepared (tag exists, versions correct)
    2. Pushes release branch and tag to remote
    3. Creates GitLab/GitHub release with CHANGELOG content
    4. For minor/major: merges to main and bumps to next minor dev version

    Args:
        version: Target version (e.g., "0.2.0")
        dry_run: Preview actions without executing
    """
    # Block actual approval from running inside Claude Code (dry-run is allowed)
    if not dry_run:
        from devflow.cli.utils import check_outside_ai_session
        check_outside_ai_session()

    repo_path = Path.cwd()

    # Display header
    console.print()
    console.print("[bold cyan]═══ DevAIFlow Release Approval ═══[/bold cyan]")
    console.print()

    # Step 1: Validate release preparation
    console.print("[bold]Step 1:[/bold] Validating release preparation...")
    manager = ReleaseManager(repo_path)

    try:
        parsed_version = Version.parse(version)
    except ValueError as e:
        console.print(f"[red]✗[/red] Invalid version format: {e}")
        return

    success, msg, release_branch = manager.validate_release_prepared(parsed_version)
    if not success:
        console.print(f"[red]✗[/red] {msg}")
        return

    console.print(f"[green]✓[/green] {msg}")
    console.print()

    # Determine release type
    if release_branch:
        release_type = "minor" if parsed_version.minor > 0 else "major"
    else:
        release_type = "patch"

    # Display approval plan
    _display_approval_plan(parsed_version, release_type, release_branch, dry_run)

    # Confirm if not dry-run
    if not dry_run:
        console.print()
        if not click.confirm("Continue with release approval?", default=False):
            console.print("[yellow]Release approval cancelled[/yellow]")
            return

    console.print()

    # Step 2: Push to remote
    tag_name = f"v{version}"

    console.print("[bold]Step 2:[/bold] Pushing to remote...")
    if release_branch:
        success, msg = manager.push_to_remote(release_branch, dry_run=dry_run)
        if not success:
            console.print(f"[red]✗[/red] {msg}")
            return
        console.print(f"[green]✓[/green] {msg}")

    success, msg = manager.push_to_remote(tag_name, dry_run=dry_run)
    if not success:
        console.print(f"[red]✗[/red] {msg}")
        return
    console.print(f"[green]✓[/green] {msg}")
    console.print()

    # Step 3: Create platform release
    console.print("[bold]Step 3:[/bold] Creating platform release...")

    # Detect platform
    from devflow.release.permissions import get_git_remote_url, parse_git_remote, Platform

    remote_url = get_git_remote_url(repo_path)
    if not remote_url:
        console.print("[yellow]⚠[/yellow] Could not determine git remote. Skipping release creation.")
        release_url = None
    else:
        platform, owner, repo = parse_git_remote(remote_url)

        if platform == Platform.GITHUB:
            success, msg, release_url = manager.create_github_release(parsed_version, dry_run=dry_run)
            if not success:
                console.print(f"[yellow]⚠[/yellow] {msg}")
                console.print("[dim]Continuing with remaining steps...[/dim]")
                release_url = None
            else:
                console.print(f"[green]✓[/green] {msg}")
        elif platform == Platform.GITLAB:
            success, msg, release_url = manager.create_gitlab_release(parsed_version, dry_run=dry_run)
            if not success:
                console.print(f"[yellow]⚠[/yellow] {msg}")
                console.print("[dim]Continuing with remaining steps...[/dim]")
                release_url = None
            else:
                console.print(f"[green]✓[/green] {msg}")
        else:
            console.print(f"[yellow]⚠[/yellow] Unknown platform: {platform}. Skipping release creation.")
            release_url = None

    console.print()

    # Step 4: Merge to main and bump (for minor/major only)
    if release_branch and release_type in ["minor", "major"]:
        console.print(f"[bold]Step 4:[/bold] Merging to main and bumping version...")
        success, msg = manager.merge_to_main_and_bump(release_branch, parsed_version, dry_run=dry_run)
        if not success:
            console.print(f"[red]✗[/red] {msg}")
            console.print()
            console.print("[yellow]⚠ Release was created but main merge failed.[/yellow]")
            console.print("[yellow]You may need to merge manually:[/yellow]")
            console.print(f"[dim]  git checkout main[/dim]")
            console.print(f"[dim]  git merge {release_branch} --no-ff[/dim]")
            console.print(f"[dim]  # Update version to next minor dev[/dim]")
            console.print(f"[dim]  git push origin main[/dim]")
            return
        console.print(f"[green]✓[/green] {msg}")
        console.print()

    # Display summary
    _display_approval_summary(parsed_version, release_type, release_url, dry_run)


def _display_approval_plan(version: Version, release_type: str, release_branch: Optional[str], dry_run: bool) -> None:
    """Display approval plan table."""
    table = Table(title="Approval Plan", show_header=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Release Type", f"[bold]{release_type.upper()}[/bold]")
    table.add_row("Version", f"[green]{version}[/green]")
    table.add_row("Tag Name", f"v{version}")

    if release_branch:
        table.add_row("Release Branch", release_branch)
        table.add_row("Main Merge", "[green]Yes[/green] (will merge to main and bump)")
    else:
        table.add_row("Main Merge", "[yellow]No[/yellow] (patch release)")

    if dry_run:
        table.add_row("Mode", "[yellow]DRY RUN (no changes will be made)[/yellow]")

    console.print(table)


def _display_approval_summary(version: Version, release_type: str, release_url: Optional[str], dry_run: bool) -> None:
    """Display approval completion summary."""
    if dry_run:
        summary = Panel(
            "[yellow]DRY RUN COMPLETE[/yellow]\n\n"
            "No changes were made. Review the plan above and run without --dry-run to execute.",
            title="Summary",
            border_style="yellow"
        )
    else:
        summary_text = f"[green]✓ Release {version} approved and completed![/green]\n\n"

        if release_url:
            summary_text += f"Release URL: {release_url}\n\n"

        if release_type in ["minor", "major"]:
            next_minor_dev = version.bump_minor().with_dev()
            summary_text += (
                f"[bold]What happened:[/bold]\n"
                f"• Pushed release/tag to remote\n"
                f"• Created platform release\n"
                f"• Merged to main\n"
                f"• Bumped main to {next_minor_dev}\n\n"
                f"[bold]Next steps:[/bold]\n"
                f"• Close JIRA epic\n"
                f"• Announce release to team"
            )
        else:
            summary_text += (
                f"[bold]What happened:[/bold]\n"
                f"• Pushed tag to remote\n"
                f"• Created platform release\n\n"
                f"[bold]Note:[/bold] Patch release - main branch not modified"
            )

        summary = Panel(
            summary_text,
            title="✓ Release Approved",
            border_style="green"
        )

    console.print(summary)
    console.print()


def suggest_release() -> None:
    """Analyze commits and suggest appropriate release type.

    This is a read-only operation and safe to run from anywhere.
    """
    repo_path = Path.cwd()

    console.print()
    console.print("[bold cyan]═══ Release Type Suggestion ═══[/bold cyan]")
    console.print()

    # Initialize manager
    manager = ReleaseManager(repo_path)

    # Get suggestion
    console.print("[bold]Analyzing commits since last release...[/bold]")
    suggestion, explanation, analysis = manager.suggest_release_type()

    console.print()

    # Display analysis
    if suggestion:
        console.print(f"[bold green]Recommendation:[/bold green] [green]{suggestion.upper()} release[/green]")
    else:
        console.print(f"[bold yellow]Recommendation:[/bold yellow] [yellow]Unable to determine automatically[/yellow]")

    console.print()
    console.print(f"[dim]{explanation}[/dim]")
    console.print()

    # Show commit breakdown
    table = Table(title="Commit Analysis", show_header=True)
    table.add_column("Type", style="cyan", width=20)
    table.add_column("Count", justify="right", style="white", width=10)
    table.add_column("Impact", style="yellow")

    if analysis['breaking']:
        table.add_row(
            "Breaking Changes",
            str(len(analysis['breaking'])),
            "→ Requires MAJOR release"
        )

    if analysis['features']:
        table.add_row(
            "New Features",
            str(len(analysis['features'])),
            "→ Requires MINOR release"
        )

    if analysis['fixes']:
        table.add_row(
            "Bug Fixes",
            str(len(analysis['fixes'])),
            "→ Allows PATCH release"
        )

    if analysis['other']:
        table.add_row(
            "Other Commits",
            str(len(analysis['other'])),
            "→ No conventional prefix"
        )

    console.print(table)
    console.print()

    # Show example commits for each category
    if analysis['breaking']:
        console.print("[bold red]Breaking Changes:[/bold red]")
        for commit in analysis['breaking'][:3]:  # Show first 3
            console.print(f"  [red]•[/red] [dim]{commit}[/dim]")
        if len(analysis['breaking']) > 3:
            console.print(f"  [dim]... and {len(analysis['breaking']) - 3} more[/dim]")
        console.print()

    if analysis['features']:
        console.print("[bold green]New Features:[/bold green]")
        for commit in analysis['features'][:3]:
            console.print(f"  [green]•[/green] [dim]{commit}[/dim]")
        if len(analysis['features']) > 3:
            console.print(f"  [dim]... and {len(analysis['features']) - 3} more[/dim]")
        console.print()

    if analysis['fixes']:
        console.print("[bold blue]Bug Fixes:[/bold blue]")
        for commit in analysis['fixes'][:3]:
            console.print(f"  [blue]•[/blue] [dim]{commit}[/dim]")
        if len(analysis['fixes']) > 3:
            console.print(f"  [dim]... and {len(analysis['fixes']) - 3} more[/dim]")
        console.print()

    # Show suggested command
    if suggestion:
        # Get current version to suggest next version
        try:
            init_version, _ = manager.read_current_version()
            current = Version.parse(init_version)

            # If current version has -dev suffix, we're working toward that version
            # So the suggested release should complete the current dev cycle first
            if current.dev:
                # For -dev versions, remove suffix to get the target release version
                next_version = current.without_dev()
            else:
                # For released versions, bump according to suggestion
                if suggestion == "major":
                    next_version = current.bump_major()
                elif suggestion == "minor":
                    next_version = current.bump_minor()
                else:  # patch
                    next_version = current.bump_patch()

            console.print("[bold]Suggested Command:[/bold]")
            console.print(f"  [cyan]daf release {next_version}[/cyan]")
            console.print()
            console.print("[dim]Or preview with:[/dim]")
            console.print(f"  [dim]daf release {next_version} --dry-run[/dim]")
        except Exception:
            console.print("[bold]Suggested Command:[/bold]")
            console.print(f"  [cyan]daf release <version>[/cyan]  [dim](choose version based on {suggestion} release)[/dim]")

    console.print()
    console.print("[dim]Note: This suggestion is based on conventional commit prefixes[/dim]")
    console.print("[dim](feat:, fix:, BREAKING CHANGE:). Review commits manually if unsure.[/dim]")
    console.print()
