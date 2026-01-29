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

    console.print("\n[bold]DevAIFlow Configuration Wizard[/bold]\n")
    console.print("[dim]All settings can be changed later using 'daf config tui'[/dim]\n")

    console.print("[bold]=== JIRA Configuration ===[/bold]\n")

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
    console.print("[dim]Can be set later via 'daf config tui'.[/dim]\n")

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
    console.print("[dim]explicit routing rules. You can skip this and configure later via 'daf config tui'.[/dim]\n")

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
    console.print("[dim]Can be set later via 'daf config tui --advanced' in the Organization tab.[/dim]\n")
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

    # Build new config
    new_config = Config(
        jira=jira_config,
        repos=repos_config,
        time_tracking=TimeTrackingConfig(),
        session_summary=SessionSummaryConfig(),
        templates=TemplateConfig(),
    )

    # PR/MR Template Configuration (optional)
    console.print("\n[bold]=== PR/MR Template Configuration ===[/bold]\n")
    console.print("[dim]Optional: Configure how AI generates PR/MR descriptions.[/dim]")
    console.print("[dim]Can be set later via 'daf config tui' or 'daf config set-pr-template-url'.[/dim]\n")
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
