"""Interactive configuration wizard for daf init."""

from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm

from devflow.config.models import Config, GitHubFiltersConfig, GitLabConfig

console = Console()


def _detect_issue_tracker_from_git() -> Optional[str]:
    """Auto-detect issue tracker type from git remote URLs.

    Returns:
        "github", "gitlab", or None if not detected
    """
    try:
        from devflow.git.utils import GitUtils
        current_dir = Path.cwd()

        # Check if current directory is a git repository
        if GitUtils.is_git_repository(current_dir):
            return GitUtils.detect_repo_type(current_dir)

        return None
    except Exception:
        return None


def _suggest_workspace_path() -> str:
    """Suggest workspace path based on current directory.

    Returns:
        Suggested workspace path
    """
    from devflow.git.utils import GitUtils
    current_dir = Path.cwd()

    # If current directory is a git repo, suggest parent directory
    if GitUtils.is_git_repository(current_dir):
        return str(current_dir.parent)

    # Otherwise suggest current directory
    return str(current_dir)


def _check_tool_availability() -> dict:
    """Check availability of external tools.

    Returns:
        Dict with keys: gh_available, glab_available, jira_token_set
    """
    import os
    import shutil

    return {
        "gh_available": shutil.which("gh") is not None,
        "glab_available": shutil.which("glab") is not None,
        "jira_token_set": bool(os.getenv("JIRA_API_TOKEN")),
    }


def _show_next_steps(preset_type: str, config: "Config") -> None:
    """Display next steps after init completes.

    Args:
        preset_type: Type of preset used ("github", "gitlab", "jira", "local", "full")
        config: The created configuration
    """
    console.print("\n[green]✓[/green] [bold]Configuration saved![/bold]\n")

    console.print("[bold]Next Steps:[/bold]\n")

    # Step 1: Install Claude Code skills (common to all)
    console.print("  1. Install Claude Code skills:")
    console.print("     [cyan]daf skills[/cyan]\n")

    # Preset-specific next steps
    if preset_type == "github":
        console.print("  2. Ensure GitHub CLI is authenticated:")
        console.print("     [cyan]gh auth login[/cyan]\n")
        console.print("  3. Create your first issue:")
        console.print("     [cyan]daf git new enhancement --goal \"Your feature description\"[/cyan]\n")
        console.print("  4. Or sync assigned issues:")
        console.print("     [cyan]daf sync[/cyan]\n")
        console.print("\n  [dim]Tip: Sync filters can be customized in ~/.devaiflow/config.json under github.filters.sync[/dim]")
        console.print("[dim]Quick start: https://github.com/itdove/devaiflow#github-issues[/dim]")

    elif preset_type == "gitlab":
        console.print("  2. Ensure GitLab CLI is authenticated:")
        console.print("     [cyan]glab auth login[/cyan]\n")
        console.print("  3. Create your first issue:")
        console.print("     [cyan]daf git new enhancement --goal \"Your feature description\"[/cyan]\n")
        console.print("  4. Or sync assigned issues:")
        console.print("     [cyan]daf sync[/cyan]\n")
        console.print("\n  [dim]Tip: Sync filters can be customized in ~/.devaiflow/config.json under gitlab.filters.sync[/dim]")
        console.print("[dim]Quick start: https://github.com/itdove/devaiflow#gitlab-issues[/dim]")

    elif preset_type == "jira":
        console.print("  2. Set JIRA_API_TOKEN environment variable:")
        console.print("     [cyan]export JIRA_API_TOKEN=\"your-token\"[/cyan]\n")
        console.print("  3. Refresh JIRA fields:")
        console.print("     [cyan]daf config refresh-jira-fields[/cyan]\n")
        console.print("  4. Configure sync filters (optional but recommended):")
        console.print("     Edit [cyan]~/.devaiflow/organization.json[/cyan] to add required fields:")
        console.print("""     [dim]{
       "jira": {
         "filters": {
           "sync": {
             "required_fields": {
               "Story": ["sprint", "points"],
               "Bug": ["severity"],
               "Task": ["sprint"]
             }
           }
         }
       }
     }[/dim]
""")
        console.print("  5. Create your first ticket:")
        console.print("     [cyan]daf jira new story --parent PROJ-123 --goal \"Your feature\"[/cyan]\n")
        console.print("  6. Or sync current sprint:")
        console.print("     [cyan]daf sync --sprint current[/cyan]\n")
        console.print("[dim]JIRA setup guide: https://github.com/itdove/devaiflow/docs/jira-integration.md[/dim]")

    elif preset_type == "local":
        console.print("  2. Create your first session:")
        console.print("     [cyan]daf new --name \"my-feature\" --goal \"Your feature\"[/cyan]\n")
        console.print("  3. List sessions:")
        console.print("     [cyan]daf list[/cyan]\n")
        console.print("  4. Complete session:")
        console.print("     [cyan]daf complete <session-name>[/cyan]\n")
        console.print("[dim]Documentation: https://github.com/itdove/devaiflow#local-sessions[/dim]")

    console.print("\nFor help: [cyan]daf --help[/cyan]")


def _run_github_preset(current_config: Optional["Config"] = None) -> "Config":
    """Run GitHub-only preset.

    Args:
        current_config: Optional existing config to use as defaults

    Returns:
        New Config object
    """
    from devflow.config.models import (
        JiraConfig,
        JiraFiltersConfig,
        GitHubConfig,
        RepoConfig,
        WorkspaceDefinition,
        TimeTrackingConfig,
        SessionSummaryConfig,
        TemplateConfig,
    )
    from devflow.git.utils import GitUtils

    console.print("\n[bold]GitHub Issues Setup[/bold]\n")

    # Auto-detection feedback
    current_dir = Path.cwd()
    if GitUtils.is_git_repository(current_dir):
        remote_url = GitUtils.get_remote_url(current_dir)
        if remote_url and "github.com" in remote_url:
            console.print(f"[green]✓[/green] Detected GitHub remote: {remote_url}")
        else:
            console.print("[yellow]⚠[/yellow] Current directory is not a GitHub repository")
            console.print("[dim]  DevAIFlow can still work with GitHub Issues in other repositories[/dim]")

    # Check GitHub CLI
    tools = _check_tool_availability()
    if tools["gh_available"]:
        console.print("[green]✓[/green] GitHub CLI (gh) is installed")
    else:
        console.print("[yellow]⚠[/yellow] GitHub CLI (gh) is not installed")
        console.print("[dim]  Install it from: https://cli.github.com/[/dim]")

    console.print()
    console.print("[bold]=== Required Configuration ===[/bold]\n")

    # Workspace path (required)
    suggested_workspace = _suggest_workspace_path()
    default_workspace = current_config.repos.get_default_workspace_path() if current_config and current_config.repos else suggested_workspace
    workspace_path = Prompt.ask("Workspace path", default=default_workspace)

    console.print("\n[bold]=== Optional Configuration ===[/bold]")
    console.print("[dim]Press Enter to skip these settings[/dim]\n")

    # Default labels (optional)
    default_labels_str = ""
    if current_config and current_config.github and current_config.github.default_labels:
        default_labels_str = ",".join(current_config.github.default_labels)

    console.print("[dim]Default labels to add to all created issues (optional)[/dim]")
    console.print("[dim]Example: backend,devaiflow[/dim]")
    labels_input = Prompt.ask("Default labels (comma-separated, or Enter to skip)", default=default_labels_str or "")
    github_default_labels = [label.strip() for label in labels_input.split(",") if label.strip()] if labels_input else []

    # Auto-close on complete (optional)
    default_auto_close = current_config.github.auto_close_on_complete if current_config and current_config.github else False
    console.print("\n[dim]Auto-close issues when session completes?[/dim]")
    console.print("[dim]If disabled, DevAIFlow uses status labels (status: completed) instead[/dim]")
    github_auto_close = Confirm.ask("Auto-close issues on complete", default=default_auto_close)

    # Sync filters configuration
    console.print("\n[bold]Sync Filters Configuration[/bold]")
    console.print("[dim]Configure filters for daf sync and feature orchestration[/dim]\n")

    # Assignee filter
    console.print("[dim]Filter by assignee (@me for current user, or specific username)[/dim]")
    default_assignee = "@me"
    if current_config and current_config.github and current_config.github.filters:
        sync_filters = current_config.github.filters.get("sync")
        if sync_filters:
            default_assignee = sync_filters.assignee
    assignee = Prompt.ask("Assignee filter", default=default_assignee)

    # Required fields
    console.print("\n[dim]Required fields that issues must have (comma-separated)[/dim]")
    console.print("[dim]Example: assignee,milestone[/dim]")
    default_req_fields = "assignee"
    if current_config and current_config.github and current_config.github.filters:
        sync_filters = current_config.github.filters.get("sync")
        if sync_filters and sync_filters.required_fields:
            default_req_fields = ",".join(sync_filters.required_fields)
    req_fields_input = Prompt.ask("Required fields", default=default_req_fields)
    required_fields = [field.strip() for field in req_fields_input.split(",") if field.strip()]

    # Build config
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            project=None,
            transitions={},
            filters={"sync": JiraFiltersConfig(status=[], required_fields=[], assignee="currentUser()")},
            time_tracking=True,
        ),
        github=GitHubConfig(
            api_url="https://api.github.com",
            repository=None,  # Auto-detected from git remote
            default_labels=github_default_labels,
            auto_close_on_complete=github_auto_close,
            filters={
                "sync": GitHubFiltersConfig(
                    status=["open"],
                    assignee=assignee,
                    required_fields=required_fields,
                )
            },
        ),
        repos=RepoConfig(
            workspaces=[WorkspaceDefinition(name="default", path=workspace_path)],
            last_used_workspace="default",
            keywords={},
        ),
        time_tracking=TimeTrackingConfig(),
        session_summary=SessionSummaryConfig(),
        templates=TemplateConfig(),
    )

    _show_next_steps("github", config)
    return config


def _run_gitlab_preset(current_config: Optional["Config"] = None) -> "Config":
    """Run GitLab-only preset.

    Args:
        current_config: Optional existing config to use as defaults

    Returns:
        New Config object
    """
    from devflow.config.models import (
        JiraConfig,
        JiraFiltersConfig,
        GitHubConfig,
        RepoConfig,
        WorkspaceDefinition,
        TimeTrackingConfig,
        SessionSummaryConfig,
        TemplateConfig,
    )
    from devflow.git.utils import GitUtils

    console.print("\n[bold]GitLab Issues Setup[/bold]\n")

    # Auto-detection feedback
    current_dir = Path.cwd()
    if GitUtils.is_git_repository(current_dir):
        remote_url = GitUtils.get_remote_url(current_dir)
        if remote_url and "gitlab" in remote_url.lower():
            console.print(f"[green]✓[/green] Detected GitLab remote: {remote_url}")
        else:
            console.print("[yellow]⚠[/yellow] Current directory is not a GitLab repository")
            console.print("[dim]  DevAIFlow can still work with GitLab Issues in other repositories[/dim]")

    # Check GitLab CLI
    tools = _check_tool_availability()
    if tools["glab_available"]:
        console.print("[green]✓[/green] GitLab CLI (glab) is installed")
    else:
        console.print("[yellow]⚠[/yellow] GitLab CLI (glab) is not installed")
        console.print("[dim]  Install it from: https://gitlab.com/gitlab-org/cli[/dim]")

    console.print()
    console.print("[bold]=== Required Configuration ===[/bold]\n")

    # Workspace path (required)
    suggested_workspace = _suggest_workspace_path()
    default_workspace = current_config.repos.get_default_workspace_path() if current_config and current_config.repos else suggested_workspace
    workspace_path = Prompt.ask("Workspace path", default=default_workspace)

    console.print("\n[bold]=== Optional Configuration ===[/bold]")
    console.print("[dim]Press Enter to skip these settings[/dim]\n")

    # Default labels (optional)
    default_labels_str = ""
    if current_config and current_config.github and current_config.github.default_labels:
        default_labels_str = ",".join(current_config.github.default_labels)

    console.print("[dim]Default labels to add to all created issues (optional)[/dim]")
    console.print("[dim]Example: backend,devaiflow[/dim]")
    labels_input = Prompt.ask("Default labels (comma-separated, or Enter to skip)", default=default_labels_str or "")
    gitlab_default_labels = [label.strip() for label in labels_input.split(",") if label.strip()] if labels_input else []

    # Auto-close on complete (optional)
    default_auto_close = current_config.gitlab.auto_close_on_complete if current_config and current_config.gitlab else False
    console.print("\n[dim]Auto-close issues when session completes?[/dim]")
    console.print("[dim]If disabled, DevAIFlow uses status labels (status: completed) instead[/dim]")
    gitlab_auto_close = Confirm.ask("Auto-close issues on complete", default=default_auto_close)

    # Sync filters configuration
    console.print("\n[bold]Sync Filters Configuration[/bold]")
    console.print("[dim]Configure filters for daf sync and feature orchestration[/dim]\n")

    # Assignee filter
    console.print("[dim]Filter by assignee (@me for current user, or specific username)[/dim]")
    default_assignee = "@me"
    if current_config and current_config.gitlab and current_config.gitlab.filters:
        sync_filters = current_config.gitlab.filters.get("sync")
        if sync_filters:
            default_assignee = sync_filters.assignee
    assignee = Prompt.ask("Assignee filter", default=default_assignee)

    # Required fields
    console.print("\n[dim]Required fields that issues must have (comma-separated)[/dim]")
    console.print("[dim]Example: assignee,milestone[/dim]")
    default_req_fields = "assignee"
    if current_config and current_config.gitlab and current_config.gitlab.filters:
        sync_filters = current_config.gitlab.filters.get("sync")
        if sync_filters and sync_filters.required_fields:
            default_req_fields = ",".join(sync_filters.required_fields)
    req_fields_input = Prompt.ask("Required fields", default=default_req_fields)
    required_fields = [field.strip() for field in req_fields_input.split(",") if field.strip()]

    # Build config
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            project=None,
            transitions={},
            filters={"sync": JiraFiltersConfig(status=[], required_fields=[], assignee="currentUser()")},
            time_tracking=True,
        ),
        github=None,
        gitlab=GitLabConfig(
            api_url="https://gitlab.com/api/v4",
            repository=None,  # Auto-detected from git remote
            default_labels=gitlab_default_labels,
            auto_close_on_complete=gitlab_auto_close,
            filters={
                "sync": GitHubFiltersConfig(
                    status=["open"],
                    assignee=assignee,
                    required_fields=required_fields,
                )
            },
        ),
        repos=RepoConfig(
            workspaces=[WorkspaceDefinition(name="default", path=workspace_path)],
            last_used_workspace="default",
            keywords={},
        ),
        time_tracking=TimeTrackingConfig(),
        session_summary=SessionSummaryConfig(),
        templates=TemplateConfig(),
    )

    _show_next_steps("gitlab", config)
    return config


def _run_jira_preset(current_config: Optional["Config"] = None) -> "Config":
    """Run JIRA-only preset.

    Args:
        current_config: Optional existing config to use as defaults

    Returns:
        New Config object
    """
    from devflow.config.models import (
        JiraConfig,
        JiraFiltersConfig,
        RepoConfig,
        WorkspaceDefinition,
        TimeTrackingConfig,
        SessionSummaryConfig,
        TemplateConfig,
    )

    console.print("\n[bold]JIRA Setup[/bold]\n")

    # Check JIRA token
    tools = _check_tool_availability()
    if tools["jira_token_set"]:
        console.print("[green]✓[/green] JIRA_API_TOKEN environment variable is set")
    else:
        console.print("[yellow]⚠[/yellow] JIRA_API_TOKEN environment variable is not set")
        console.print("[dim]  You'll need to set it after init completes[/dim]")

    console.print()
    console.print("[bold]=== Required Configuration ===[/bold]\n")

    # JIRA URL (required)
    default_url = current_config.jira.url if current_config else "https://jira.example.com"
    jira_url = Prompt.ask("JIRA URL", default=default_url)

    # JIRA Project (required for creating issues)
    console.print("\n[dim]The project key is the short identifier for your JIRA project (e.g., 'PROJ', 'ENG')[/dim]")
    console.print("[dim]You can find it in your JIRA URL: https://jira.company.com/browse/PROJ-123 → 'PROJ'[/dim]")

    default_project = None
    if current_config:
        from devflow.config.loader import ConfigLoader
        config_loader = ConfigLoader()
        org_config = config_loader._load_organization_config()
        if org_config and org_config.jira_project:
            default_project = org_config.jira_project
        elif current_config.jira.project:
            default_project = current_config.jira.project

    if default_project:
        jira_project = Prompt.ask("JIRA Project Key", default=default_project)
    else:
        jira_project = Prompt.ask("JIRA Project Key")

    # Workspace path (required)
    suggested_workspace = _suggest_workspace_path()
    default_workspace = current_config.repos.get_default_workspace_path() if current_config and current_config.repos else suggested_workspace
    workspace_path = Prompt.ask("\nWorkspace path", default=default_workspace)

    console.print("\n[bold]=== Optional Configuration ===[/bold]")
    console.print("[dim]Press Enter to use defaults[/dim]\n")

    # Comment visibility (optional)
    console.print("[dim]Control who can see comments that DevAIFlow adds to JIRA tickets[/dim]")
    default_visibility_type = current_config.jira.comment_visibility_type if current_config and current_config.jira.comment_visibility_type else "group"
    console.print("\nVisibility type:")
    console.print("  1. group - Restrict by JIRA group membership (most common)")
    console.print("  2. role - Restrict by JIRA role")
    visibility_type = Prompt.ask("Choice", choices=["group", "role"], default=default_visibility_type)

    default_visibility_value = current_config.jira.comment_visibility_value if current_config and current_config.jira.comment_visibility_value else None
    if visibility_type == "group":
        console.print("\n[dim]Enter the JIRA group name (e.g., 'Engineering Team', 'Developers')[/dim]")
        default_value = default_visibility_value or "Engineering Team"
    else:
        console.print("\n[dim]Enter the JIRA role name (e.g., 'Administrators', 'Developers')[/dim]")
        default_value = default_visibility_value or "Developers"

    visibility_value = Prompt.ask(f"{visibility_type.capitalize()} name", default=default_value)

    # Build config
    config = Config(
        jira=JiraConfig(
            url=jira_url,
            project=jira_project,
            transitions={},
            filters={
                "sync": JiraFiltersConfig(
                    status=["New", "To Do", "In Progress"],
                    required_fields=[],
                    assignee="currentUser()",
                )
            },
            time_tracking=True,
            comment_visibility_type=visibility_type,
            comment_visibility_value=visibility_value,
        ),
        github=None,
        repos=RepoConfig(
            workspaces=[WorkspaceDefinition(name="default", path=workspace_path)],
            last_used_workspace="default",
            keywords={},
        ),
        time_tracking=TimeTrackingConfig(),
        session_summary=SessionSummaryConfig(),
        templates=TemplateConfig(),
    )

    # Save JIRA project to organization.json
    _save_organization_config(jira_project, None)

    _show_next_steps("jira", config)
    return config


def _run_local_preset(current_config: Optional["Config"] = None) -> "Config":
    """Run Local-only preset (no issue tracker).

    Args:
        current_config: Optional existing config to use as defaults

    Returns:
        New Config object
    """
    from devflow.config.models import (
        JiraConfig,
        JiraFiltersConfig,
        RepoConfig,
        WorkspaceDefinition,
        TimeTrackingConfig,
        SessionSummaryConfig,
        TemplateConfig,
    )

    console.print("\n[bold]Local Sessions Only Setup[/bold]\n")
    console.print("[dim]No issue tracker needed! DevAIFlow will manage local sessions only.[/dim]\n")

    console.print("[bold]=== Required Configuration ===[/bold]\n")

    # Workspace path (required)
    suggested_workspace = _suggest_workspace_path()
    default_workspace = current_config.repos.get_default_workspace_path() if current_config and current_config.repos else suggested_workspace
    workspace_path = Prompt.ask("Workspace path", default=default_workspace)

    # Build minimal config
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            project=None,
            transitions={},
            filters={"sync": JiraFiltersConfig(status=[], required_fields=[], assignee="currentUser()")},
            time_tracking=True,
        ),
        github=None,
        repos=RepoConfig(
            workspaces=[WorkspaceDefinition(name="default", path=workspace_path)],
            last_used_workspace="default",
            keywords={},
        ),
        time_tracking=TimeTrackingConfig(),
        session_summary=SessionSummaryConfig(),
        templates=TemplateConfig(),
    )

    _show_next_steps("local", config)
    return config


def run_init_wizard(current_config: Optional[Config] = None) -> Config:
    """Run interactive configuration wizard.

    Args:
        current_config: Optional existing config to use as defaults

    Returns:
        New Config object with user-provided values
    """
    from devflow.config.models import (
        JiraConfig,
        JiraFiltersConfig,
        JiraTransitionConfig,
        RepoConfig,
        TimeTrackingConfig,
        SessionSummaryConfig,
        TemplateConfig,
    )

    console.print("\n[bold]DevAIFlow Configuration Wizard[/bold]\n")
    console.print("[dim]All settings can be changed later using 'daf config edit'[/dim]\n")

    # If current_config exists, skip preset selection and use full wizard
    # This happens when user runs `daf init --reset`
    if current_config is None:
        # Step 1: Preset selection (only for new configs)
        console.print("[bold]What would you like to use DevAIFlow for?[/bold]\n")

        # Auto-detect current setup
        detected_tracker = _detect_issue_tracker_from_git()
        tools = _check_tool_availability()

        # Build preset options with auto-detection hints
        preset_options = []
        if detected_tracker == "github" and tools["gh_available"]:
            preset_options.append("1. [green]GitHub Issues[/green] (detected from git remote)")
        else:
            preset_options.append("1. GitHub Issues")

        if detected_tracker == "gitlab" and tools["glab_available"]:
            preset_options.append("2. [green]GitLab Issues[/green] (detected from git remote)")
        else:
            preset_options.append("2. GitLab Issues")

        if tools["jira_token_set"]:
            preset_options.append("3. [green]JIRA[/green] (JIRA_API_TOKEN detected)")
        else:
            preset_options.append("3. JIRA")

        preset_options.append("4. Local sessions only (no issue tracker)")
        preset_options.append("5. Custom configuration (full wizard)")

        for option in preset_options:
            console.print(f"  {option}")

        console.print()

        # Determine default choice based on auto-detection
        default_choice = "1"
        if detected_tracker == "github" and tools["gh_available"]:
            default_choice = "1"
        elif detected_tracker == "gitlab" and tools["glab_available"]:
            default_choice = "2"
        elif tools["jira_token_set"]:
            default_choice = "3"

        preset = Prompt.ask(
            "Choice",
            choices=["1", "2", "3", "4", "5"],
            default=default_choice
        )

        # Route to appropriate preset handler
        if preset == "1":
            return _run_github_preset(current_config)
        elif preset == "2":
            return _run_gitlab_preset(current_config)
        elif preset == "3":
            return _run_jira_preset(current_config)
        elif preset == "4":
            return _run_local_preset(current_config)
        else:  # preset == "5"
            # Fall through to original full wizard
            pass

    console.print("\n[bold]=== JIRA Configuration ===[/bold]\n")

    # JIRA URL
    default_url = current_config.jira.url if current_config else "https://jira.example.com"
    jira_url = Prompt.ask("JIRA URL", default=default_url)

    # JIRA Project (stored in organization.json)
    console.print("[dim]The project key is the short identifier for your JIRA project (e.g., 'PROJ', 'ENG', 'DEVOPS')[/dim]")
    console.print("[dim]You can find it in your JIRA URL: https://jira.company.com/browse/PROJ-123 → 'PROJ'[/dim]")
    console.print("[dim]Can be set later, but required for: creating issues, field discovery[/dim]")

    # Try to get default from organization.json first (more accurate), then fall back to merged config
    default_project = None
    if current_config:
        from devflow.config.loader import ConfigLoader
        config_loader = ConfigLoader()
        org_config = config_loader._load_organization_config()
        if org_config and org_config.jira_project:
            default_project = org_config.jira_project
        elif current_config.jira.project:
            default_project = current_config.jira.project

    if default_project:
        jira_project = Prompt.ask("JIRA Project Key", default=default_project)
    else:
        jira_project_input = Prompt.ask("JIRA Project Key (optional, press Enter to skip)", default="")
        jira_project = jira_project_input if jira_project_input else None

    console.print("\n[bold]=== JIRA Comment Visibility ===[/bold]\n")
    console.print("[dim]Control who can see comments that DevAIFlow adds to JIRA tickets.[/dim]")
    console.print("[dim]Can be set later via 'daf config edit'.[/dim]\n")

    # Comment visibility type
    default_visibility_type = current_config.jira.comment_visibility_type if current_config and current_config.jira.comment_visibility_type else "group"
    console.print("Choose visibility type:")
    console.print("  [white]1.[/white] group - Restrict by JIRA group membership (most common)")
    console.print("  [white]2.[/white] role - Restrict by JIRA role")
    console.print()
    visibility_type_choice = Prompt.ask("Visibility type", choices=["group", "role"], default=default_visibility_type)

    # Comment visibility value
    default_visibility_value = current_config.jira.comment_visibility_value if current_config and current_config.jira.comment_visibility_value else None
    console.print()
    if visibility_type_choice == "group":
        console.print("[dim]Enter the JIRA group name (e.g., 'Engineering Team', 'Developers')[/dim]")
        default_value = default_visibility_value or "Engineering Team"
    else:
        console.print("[dim]Enter the JIRA role name (e.g., 'Administrators', 'Developers')[/dim]")
        default_value = default_visibility_value or "Developers"

    visibility_value = Prompt.ask(f"{visibility_type_choice.capitalize()} name", default=default_value)

    console.print("\n[bold]=== GitHub/GitLab Integration ===[/bold]\n")
    console.print("[dim]Optional: Configure GitHub Issues or GitLab Issues integration.[/dim]")
    console.print("[dim]Most settings are auto-detected from git remotes. Only configure if:[/dim]")
    console.print("[dim]  - Using GitHub Enterprise (custom API URL)[/dim]")
    console.print("[dim]  - Want default labels on all created issues[/dim]")
    console.print("[dim]  - Want to auto-close issues when sessions complete[/dim]")
    console.print("[dim]Can be set later via 'daf config edit'.[/dim]\n")

    # GitHub configuration (optional)
    github_api_url = None
    github_default_labels = []
    github_auto_close = False

    configure_github = Confirm.ask("Configure GitHub/GitLab integration now?", default=False)

    if configure_github:
        # GitHub API URL (only for Enterprise)
        default_api_url = current_config.github.api_url if current_config and current_config.github else "https://api.github.com"
        console.print("\n[dim]GitHub API URL (default: https://api.github.com for public GitHub)[/dim]")
        console.print("[dim]Only change this for GitHub Enterprise: https://github.company.com/api/v3[/dim]")
        api_url_input = Prompt.ask("GitHub API URL", default=default_api_url)
        github_api_url = api_url_input if api_url_input != "https://api.github.com" else "https://api.github.com"

        # Default labels (optional)
        default_labels_str = ""
        if current_config and current_config.github and current_config.github.default_labels:
            default_labels_str = ",".join(current_config.github.default_labels)

        console.print("\n[dim]Default labels to add to all created issues (optional)[/dim]")
        console.print("[dim]Example: backend,devaiflow,automation[/dim]")
        labels_input = Prompt.ask("Default labels (comma-separated, or Enter to skip)", default=default_labels_str or "")
        if labels_input:
            github_default_labels = [label.strip() for label in labels_input.split(",") if label.strip()]

        # Auto-close on complete
        default_auto_close = current_config.github.auto_close_on_complete if current_config and current_config.github else False
        console.print("\n[dim]Auto-close issues when session completes?[/dim]")
        console.print("[dim]If disabled, DevAIFlow uses status labels (status: completed) instead[/dim]")
        github_auto_close = Confirm.ask("Auto-close issues on complete", default=default_auto_close)

    console.print("\n[bold]=== Repository Workspace ===[/bold]\n")

    # Workspace path
    default_workspace = current_config.repos.get_default_workspace_path() if current_config and current_config.repos else str(Path.home() / "development")
    workspace_path = Prompt.ask("Workspace path", default=default_workspace)

    # Validate workspace path contains git repositories
    workspace_path_obj = Path(workspace_path).expanduser()
    if workspace_path_obj.exists():
        from devflow.git.utils import GitUtils
        # Check if workspace itself is a git repo
        if GitUtils.is_git_repository(workspace_path_obj):
            console.print(f"[green]✓[/green] Workspace is a git repository")
        else:
            # Check if workspace contains any git repositories
            has_git_repos = False
            try:
                # Look for .git directories in immediate subdirectories (don't recurse too deep)
                for item in workspace_path_obj.iterdir():
                    if item.is_dir() and (item / ".git").exists():
                        has_git_repos = True
                        break
            except PermissionError:
                pass  # Can't check, skip validation

            if has_git_repos:
                console.print(f"[green]✓[/green] Workspace contains git repositories")
            else:
                console.print(f"[yellow]⚠[/yellow] Warning: Workspace does not appear to contain git repositories")
                console.print(f"[dim]  DevAIFlow works with git repositories in subdirectories of the workspace.[/dim]")
                console.print(f"[dim]  Example: {workspace_path}/my-project/.git[/dim]")
    else:
        console.print(f"[yellow]⚠[/yellow] Warning: Workspace path does not exist yet: {workspace_path}")
        console.print(f"[dim]  It will be created when you clone repositories into it.[/dim]")

    console.print("\n[bold]=== Keyword Mappings ===[/bold]\n")
    console.print("[dim]Optional: Keywords help suggest repositories when working across multiple repos.[/dim]")
    console.print("[dim]DevAIFlow learns from your usage patterns, so keywords are only needed if you want[/dim]")
    console.print("[dim]explicit routing rules. You can skip this and configure later via 'daf config edit'.[/dim]\n")

    # Keywords
    keywords = {}
    if current_config and current_config.repos.keywords:
        console.print("Current keywords:")
        for keyword, repos in current_config.repos.keywords.items():
            console.print(f"  - {keyword}: {', '.join(repos)}")
        console.print()

        update_keywords = Confirm.ask("Update keywords?", default=False)

        if update_keywords:
            # Interactive keyword editing
            keywords = _prompt_for_keywords(current_config.repos.keywords)
        else:
            # Keep existing keywords
            keywords = current_config.repos.keywords
    else:
        # No existing keywords
        if Confirm.ask("Configure keyword mappings now?", default=False):
            keywords = _prompt_for_keywords({})

    # Hierarchical Config Source (organization-level)
    console.print("\n[bold]=== Hierarchical Configuration ===[/bold]\n")
    console.print("[dim]Optional: URL to organization-wide config files (ENTERPRISE.md, ORGANIZATION.md, etc.)[/dim]")
    console.print("[dim]This enables automatic distribution of organization policies and AI agent skills.[/dim]")
    console.print("[dim]After setting this, run 'daf upgrade' to download config files and skills.[/dim]")
    console.print("[dim]Can be set later via 'daf config edit --advanced' in the Organization tab.[/dim]\n")
    console.print("Examples:")
    console.print("  - file:///company/shared/devaiflow/configs")
    console.print("  - https://github.com/company/devaiflow-config/configs")
    console.print()

    hierarchical_config_source = None
    if current_config:
        # Check if there's an organization config with hierarchical_config_source
        from devflow.config.loader import ConfigLoader
        config_loader = ConfigLoader()
        org_config = config_loader._load_organization_config()
        if org_config and org_config.hierarchical_config_source:
            console.print(f"[dim]Current source: {org_config.hierarchical_config_source}[/dim]")
            if Confirm.ask("Update hierarchical config source?", default=False):
                # Show current value as default when updating
                source_input = Prompt.ask(
                    "Hierarchical config source URL (or press Enter to keep current)",
                    default=org_config.hierarchical_config_source
                )
                hierarchical_config_source = source_input if source_input else None
            else:
                hierarchical_config_source = org_config.hierarchical_config_source
        else:
            if Confirm.ask("Configure hierarchical config source now?", default=False):
                source_input = Prompt.ask("Hierarchical config source URL", default="")
                hierarchical_config_source = source_input if source_input else None
    else:
        if Confirm.ask("Configure hierarchical config source now?", default=False):
            source_input = Prompt.ask("Hierarchical config source URL", default="")
            hierarchical_config_source = source_input if source_input else None

    # Build JIRA config with transitions
    jira_config = JiraConfig(
        url=jira_url,
        project=jira_project,
        transitions={},  # Transitions configured via patches or daf config set-transition-* commands
        filters={
            "sync": JiraFiltersConfig(
                status=["New", "To Do", "In Progress"],
                required_fields=[],  # Configure in organization.json or team.json
                assignee="currentUser()",
            )
        },
        time_tracking=True,
        comment_visibility_type=visibility_type_choice,
        comment_visibility_value=visibility_value,
    )

    # Preserve field mappings and custom field defaults from current config if available
    if current_config and current_config.jira.field_mappings:
        jira_config.field_mappings = current_config.jira.field_mappings
        jira_config.field_cache_timestamp = current_config.jira.field_cache_timestamp

    if current_config and current_config.jira.custom_field_defaults:
        jira_config.custom_field_defaults = current_config.jira.custom_field_defaults

    # Build repo config with workspaces list
    from devflow.config.models import WorkspaceDefinition
    repos_config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="default", path=workspace_path)
        ],
        last_used_workspace="default",
        keywords=keywords,
    )

    # Build GitHub config (optional)
    github_config = None
    if configure_github or (current_config and current_config.github):
        from devflow.config.models import GitHubConfig
        github_config = GitHubConfig(
            api_url=github_api_url if github_api_url else "https://api.github.com",
            repository=None,  # Auto-detected from git remote
            default_labels=github_default_labels,
            auto_close_on_complete=github_auto_close,
        )
        # Preserve existing repository setting if present
        if current_config and current_config.github and current_config.github.repository:
            github_config.repository = current_config.github.repository

    # Build new config
    new_config = Config(
        jira=jira_config,
        github=github_config,
        repos=repos_config,
        time_tracking=TimeTrackingConfig(),
        session_summary=SessionSummaryConfig(),
        templates=TemplateConfig(),
    )

    # PR/MR Template Configuration (optional)
    console.print("\n[bold]=== PR/MR Template Configuration ===[/bold]\n")
    console.print("[dim]Optional: Configure how AI generates PR/MR descriptions.[/dim]")
    console.print("[dim]Templates are auto-discovered from organization and repository locations.[/dim]")
    console.print("[dim]Manual configuration can be added later via 'daf config edit' or by editing config.json.[/dim]\n")
    console.print("You have three options for generating PR/MR descriptions:")
    console.print("  [white]1.[/white] Provide a template URL - AI will fill your organization's template")
    console.print("  [white]2.[/white] Leave empty - AI will generate descriptions automatically")
    console.print("  [white]3.[/white] Add template guidance to AGENTS.md/ORGANIZATION.md/TEAM.md files")
    console.print()

    pr_template_url = None
    if current_config and current_config.pr_template_url:
        # Show current value
        console.print(f"[dim]Current template URL: {current_config.pr_template_url}[/dim]")
        if Confirm.ask("Update PR/MR template URL?", default=False):
            console.print()
            console.print("[dim]For GitHub templates, use the raw URL format:[/dim]")
            console.print("[dim]  https://raw.githubusercontent.com/YOUR-ORG/.github/main/.github/PULL_REQUEST_TEMPLATE.md[/dim]")
            console.print("[dim]  (Not the regular GitHub URL - must be raw.githubusercontent.com)[/dim]")
            console.print()
            # Show current URL as default when updating
            template_url_input = Prompt.ask(
                "Enter PR/MR template URL (or press Enter to keep current)",
                default=current_config.pr_template_url
            )
            pr_template_url = template_url_input.strip() if template_url_input.strip() else None
        else:
            # Keep existing URL
            pr_template_url = current_config.pr_template_url
    else:
        # No existing template URL
        if Confirm.ask("Configure PR/MR template URL?", default=False):
            console.print()
            console.print("[dim]For GitHub templates, use the raw URL format:[/dim]")
            console.print("[dim]  https://raw.githubusercontent.com/YOUR-ORG/.github/main/.github/PULL_REQUEST_TEMPLATE.md[/dim]")
            console.print("[dim]  (Not the regular GitHub URL - must be raw.githubusercontent.com)[/dim]")
            console.print()
            template_url_input = Prompt.ask("Enter PR/MR template URL (leave empty to skip)", default="")
            pr_template_url = template_url_input.strip() if template_url_input.strip() else None

    new_config.pr_template_url = pr_template_url

    # Save hierarchical_config_source to organization.json
    if hierarchical_config_source is not None:  # Only save if user provided a value
        _save_organization_config(jira_project, hierarchical_config_source)

    return new_config


def _prompt_for_keywords(existing_keywords: dict) -> dict:
    """Prompt user to add/update keyword mappings.

    Args:
        existing_keywords: Current keyword mappings

    Returns:
        Updated keyword mappings dictionary
    """
    keywords = dict(existing_keywords)

    console.print("\n[dim]Enter keyword mappings (keyword -> repository names)[/dim]")
    console.print("[dim]Leave keyword empty to finish[/dim]\n")

    while True:
        keyword = Prompt.ask("Keyword (or Enter to finish)", default="")
        if not keyword:
            break

        # Show existing mapping if available
        if keyword in keywords:
            existing_repos = ", ".join(keywords[keyword])
            console.print(f"[dim]Current: {existing_repos}[/dim]")

        repos_input = Prompt.ask(f"Repository names for '{keyword}' (comma-separated)")
        if repos_input:
            repos = [r.strip() for r in repos_input.split(",") if r.strip()]
            if repos:
                keywords[keyword] = repos

    return keywords


def _save_organization_config(jira_project: Optional[str], hierarchical_config_source: str) -> None:
    """Save organization-level configuration to organization.json.

    Args:
        jira_project: JIRA project key
        hierarchical_config_source: URL to hierarchical config files
    """
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import OrganizationConfig
    import json

    config_loader = ConfigLoader()
    org_config_path = config_loader.session_home / "organization.json"

    # Load existing organization config if it exists
    if org_config_path.exists():
        try:
            with open(org_config_path, 'r') as f:
                org_data = json.load(f)
        except Exception:
            org_data = {}
    else:
        org_data = {}

    # Update with new values
    if jira_project:
        org_data['jira_project'] = jira_project
    if hierarchical_config_source:
        org_data['hierarchical_config_source'] = hierarchical_config_source

    # Save organization config
    with open(org_config_path, 'w') as f:
        json.dump(org_data, f, indent=2)

    console.print(f"[green]✓[/green] Organization config saved to: {org_config_path}")
