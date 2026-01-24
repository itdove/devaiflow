"""Interactive configuration wizard for daf init."""

from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm

from devflow.config.models import Config

console = Console()


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

    console.print("\n[bold]=== JIRA Configuration ===[/bold]\n")

    # JIRA URL
    default_url = current_config.jira.url if current_config else "https://jira.example.com"
    jira_url = Prompt.ask("JIRA URL", default=default_url)

    # JIRA Project
    default_project = current_config.jira.project if current_config else None
    if default_project:
        jira_project = Prompt.ask("JIRA Project Key", default=default_project)
    else:
        jira_project_input = Prompt.ask("JIRA Project Key (optional, press Enter to skip)", default="")
        jira_project = jira_project_input if jira_project_input else None

    # JIRA User
    default_user = current_config.jira.user if current_config else "your-username"
    jira_user = Prompt.ask("JIRA Username", default=default_user)

    # Workstream
    default_workstream = current_config.jira.workstream if current_config else None
    if default_workstream:
        workstream = Prompt.ask("Which workstream do you work on?", default=default_workstream)
    else:
        workstream_input = Prompt.ask("Which workstream do you work on? (optional, press Enter to skip)", default="")
        workstream = workstream_input if workstream_input else None

    console.print("\n[bold]=== Repository Workspace ===[/bold]\n")

    # Workspace path
    default_workspace = current_config.repos.get_default_workspace_path() if current_config and current_config.repos else str(Path.home() / "development")
    workspace_path = Prompt.ask("Workspace path", default=default_workspace)

    console.print("\n[bold]=== Keyword Mappings ===[/bold]\n")

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
        if Confirm.ask("Configure keyword mappings?", default=False):
            keywords = _prompt_for_keywords({})

    # Build JIRA config with transitions
    jira_config = JiraConfig(
        url=jira_url,
        user=jira_user,
        project=jira_project,
        workstream=workstream,
        transitions={},  # Transitions configured via patches or daf config set-transition-* commands
        filters={
            "sync": JiraFiltersConfig(
                status=["New", "To Do", "In Progress"],
                required_fields=["sprint", "story-points"],
                assignee="currentUser()",
            )
        },
        time_tracking=True,
    )

    # Preserve field mappings from current config if available
    if current_config and current_config.jira.field_mappings:
        jira_config.field_mappings = current_config.jira.field_mappings
        jira_config.field_cache_timestamp = current_config.jira.field_cache_timestamp

    # Build repo config with workspaces list
    from devflow.config.models import WorkspaceDefinition
    repos_config = RepoConfig(
        workspaces=[
            WorkspaceDefinition(name="default", path=workspace_path)
        ],
        last_used_workspace="default",
        keywords=keywords,
    )

    # Build new config
    new_config = Config(
        jira=jira_config,
        repos=repos_config,
        time_tracking=TimeTrackingConfig(),
        session_summary=SessionSummaryConfig(),
        templates=TemplateConfig(),
    )

    # Preserve PR template URL if it exists
    if current_config and current_config.pr_template_url:
        new_config.pr_template_url = current_config.pr_template_url

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
