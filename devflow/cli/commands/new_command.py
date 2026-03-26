"""Implementation of 'daf new' command."""

import click
import os
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt

from devflow.cli.utils import check_concurrent_session, console_print, get_status_display, is_json_mode, output_json as json_output, require_outside_claude, resolve_workspace_path, scan_workspace_repositories, serialize_session, should_launch_claude_code
from devflow.config.loader import ConfigLoader
from devflow.git.utils import GitUtils
from devflow.jira import JiraClient
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError
from devflow.session.manager import SessionManager
from devflow.suggestions import RepositorySuggester

# Import unified utilities
from devflow.cli.signal_handler import setup_signal_handlers, is_cleanup_done
from devflow.cli.skills_discovery import discover_skills
from devflow.utils.context_files import load_hierarchical_context_files
from devflow.utils.backend_detection import detect_backend_from_key
from devflow.utils.daf_agents_validation import validate_daf_agents_md

console = Console()


def _is_non_interactive(output_json: bool = False) -> bool:
    """Check if running in non-interactive mode.

    Non-interactive mode is enabled when:
    - --json flag is set
    - --non-interactive global flag is set (sets DAF_NON_INTERACTIVE=1)
    - Running in CI environment (CI, GITHUB_ACTIONS, GITLAB_CI, etc.)
    - DAF_NON_INTERACTIVE=1 environment variable is explicitly set

    Args:
        output_json: Whether JSON output mode is enabled

    Returns:
        True if in non-interactive mode (no user prompts allowed)
    """
    # Check if in JSON mode
    if output_json:
        return True

    # Check for CI environment variables
    ci_vars = ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_HOME', 'TRAVIS', 'CIRCLECI']
    if any(os.getenv(var) for var in ci_vars):
        return True

    # Check for explicit non-interactive flag (set by --non-interactive or manually)
    if os.getenv('DAF_NON_INTERACTIVE') == '1':
        return True

    return False




def _generate_initial_prompt(
    name: str,
    goal: Optional[str],
    issue_key: Optional[str] = None,
    issue_title: Optional[str] = None,
    session_type: str = "development",
    current_project: Optional[str] = None,
    other_projects: Optional[list] = None,
    project_path: Optional[str] = None,
    workspace: Optional[str] = None,
    is_multi_project: bool = False,
    project_paths: Optional[dict] = None,
) -> str:
    """Generate the initial prompt for Claude Code with context loading hints.

    The prompt includes:
    - A clear goal statement (if goal/JIRA provided)
    - Instructions to read AGENTS.md and CLAUDE.md (always included)
    - Note: daf-workflow skill is auto-loaded by Claude Code
    - Instructions to read configured context files (from config, including hidden skills)
    - issue tracker ticket reading instruction using daf jira view (if issue_key is provided)
    - Analysis-only constraints (if session_type is "ticket_creation")
    - Multi-project scope constraints (if other_projects is provided)

    Args:
        name: Session group name
        goal: Optional user-provided goal
        issue_key: Optional issue tracker key
        issue_title: Optional issue tracker ticket title (fetched from JIRA)
        session_type: Type of session ("development" or "ticket_creation")
        current_project: Optional name of current project directory
        other_projects: Optional list of other project names in this session
        project_path: Optional path to the project (for single project sessions)
        workspace: Optional workspace path (for multi-project sessions)
        is_multi_project: Flag indicating if this is a multi-project session
        project_paths: Optional dict mapping repo_name -> project_path for multi-project sessions

    Returns:
        Formatted initial prompt for Claude Code

    Examples:
        Without goal or JIRA (exploratory session):
            "Please start by reading the following context files if they exist:
            - AGENTS.md (agent-specific instructions)
            - CLAUDE.md (project guidelines and standards)
            - (daf-workflow skill auto-loaded)"

        With goal only:
            "Work on: backup-feature

            Please start by reading the following context files if they exist:
            - AGENTS.md (agent-specific instructions)
            - CLAUDE.md (project guidelines and standards)
            - (daf-workflow skill auto-loaded)"

        With JIRA and title:
            "Work on: Implement customer backup and restore

            Please start by reading the following context files if they exist:
            - AGENTS.md (agent-specific instructions)
            - CLAUDE.md (project guidelines and standards)
            - DAF_AGENTS.md (daf tool usage guide)

            Also read the issue tracker ticket:
            daf jira view PROJ-52470"
    """
    prompt = ""

    # Build the goal line if we have any goal information
    goal_line = None
    if issue_key and issue_title:
        goal_line = f"{issue_key}: {issue_title}"
    elif issue_key and goal:
        goal_line = f"{issue_key}: {goal}"
    elif issue_key:
        goal_line = issue_key
    elif goal:
        goal_line = goal

    # Add "Work on:" line only if we have a goal
    if goal_line:
        prompt = f"Work on: {goal_line}\n\n"

    # Build list of all context files (defaults + configured)
    # Default context files (always included)
    # Note: DAF_AGENTS.md replaced by daf-workflow skill (auto-loaded)
    default_files = [
        ("AGENTS.md", "agent-specific instructions"),
        ("CLAUDE.md", "project guidelines and standards"),
    ]

    # Load configured context files from config (non-skill files only)
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    configured_files = []
    if config and config.context_files:
        # Only include non-skill context files from config (hidden=false)
        # Skills will be discovered from filesystem instead
        configured_files = [(f.path, f.description) for f in config.context_files.files if not f.hidden]

    # Load hierarchical context files (only those that exist)
    hierarchical_files = load_hierarchical_context_files(config)

    # Discover skills from filesystem (instead of loading from config)
    # This ensures we only reference skills that actually exist on disk
    skill_files = discover_skills(project_path=project_path, workspace=workspace)

    # Combine regular context files: defaults + hierarchical + configured (no skills from config)
    regular_files = default_files + hierarchical_files + configured_files

    # Add context loading instructions
    prompt += "Please start by reading the following context files if they exist:\n"
    for path, description in regular_files:
        prompt += f"- {path} ({description})\n"

    # For multi-project sessions, also read project-level default files
    if is_multi_project and project_paths:
        from pathlib import Path
        prompt += "\nAlso read project-level context files for each project:\n"
        for repo_name in sorted(project_paths.keys()):
            proj_path = project_paths[repo_name]
            # Get project directory name relative to workspace
            proj_dir = Path(proj_path).name if workspace else repo_name
            prompt += f"\n{repo_name}:\n"
            for filename, description in default_files:
                prompt += f"- {proj_dir}/{filename} ({description})\n"

    # Add explicit skill loading section if skills are present
    if skill_files:
        prompt += "\n⚠️  CRITICAL: Read ALL of the following skill files before proceeding:\n"
        for path, description in skill_files:
            prompt += f"- {path}\n"
        prompt += "\nThese skills contain essential tool usage information and must be read completely.\n"

    # Add issue tracker reading instruction with backend detection
    if issue_key:
        # Detect backend from issue key format
        backend = detect_backend_from_key(issue_key, config)

        prompt += f"\nAlso read the issue tracker ticket with comments:\n"
        if backend == "github":
            prompt += f"daf git view {issue_key} --comments\n"
        else:
            # JIRA or other backends
            prompt += f"daf jira view {issue_key} --comments\n"

    # Add multi-project scope constraints
    if is_multi_project and other_projects:
        # New mode: Shared context across all projects
        prompt += f"\n⚠️  MULTI-PROJECT SESSION:\n"
        prompt += f"   • This session spans {len(other_projects)} projects with SHARED CONTEXT\n"
        prompt += f"   • Projects: {', '.join(other_projects)}\n"
        prompt += f"   • You can make changes in ANY of these projects\n"

        # Add explicit file permission guidance based on session_type
        if session_type == "development":
            prompt += f"   • File Permissions: You can EDIT files in any of these project directories\n"
        else:  # ticket_creation or investigation
            prompt += f"   • File Permissions: You can only READ files in these directories - DO NOT edit any files\n"

        prompt += f"\n   ✅ ADVANTAGES:\n"
        prompt += f"   • All changes are coordinated in a single conversation\n"
        prompt += f"   • You can update frontend to match backend API changes\n"
        prompt += f"   • Shared understanding across all related code\n"
        prompt += f"\n   🔍 IMPORTANT:\n"
        prompt += f"   • Each project has its OWN git repository\n"
        prompt += f"   • Use `daf active` to see all projects in this session\n"
        prompt += f"   • File paths are relative to workspace root\n"
        prompt += f"   • Example: `backend-api/src/api.py`, `frontend-app/src/client.ts`\n"
    elif other_projects and current_project:
        # Old mode: Isolated conversations (backward compatibility)
        prompt += f"\n⚠️  MULTI-PROJECT SESSION SCOPE:\n"
        prompt += f"   • This session works across {len(other_projects) + 1} different projects\n"
        prompt += f"   • YOU ARE CURRENTLY IN: {current_project}\n"
        prompt += f"   • Other projects in this session: {', '.join(other_projects)}\n"
        prompt += f"\n   🚨 CRITICAL: Only make changes in the '{current_project}' project!\n"

        # Add explicit file permission guidance based on session_type
        if session_type == "development":
            prompt += f"   • File Permissions: You can EDIT files in '{current_project}' directory only\n"
        else:  # ticket_creation or investigation
            prompt += f"   • File Permissions: You can only READ files in '{current_project}' directory - DO NOT edit any files\n"

        prompt += f"\n   WHY THIS MATTERS:\n"
        prompt += f"   • Each project has its OWN git repository and branch\n"
        prompt += f"   • The other projects ({', '.join(other_projects)}) may be on DIFFERENT branches\n"
        prompt += f"   • Making changes in the wrong project will cause:\n"
        prompt += f"     - Lost work (commits to wrong repository)\n"
        prompt += f"     - Merge conflicts (wrong branch state)\n"
        prompt += f"     - Build failures (missing dependencies from other projects)\n"
        prompt += f"\n   If the work requires changes in {', '.join(other_projects)}:\n"
        prompt += f"   1. Tell the user which project needs changes\n"
        prompt += f"   2. Ask them to exit and run: daf open {name}\n"
        prompt += f"   3. They will select the correct project conversation\n"
        prompt += f"\n   NEVER attempt to navigate to or modify files in other project directories.\n"

    # Add auto-load related conversations prompt (if enabled and multi-conversation session)
    if (
        session_type != "ticket_creation"
        and config
        and config.prompts.auto_load_related_conversations
        and other_projects
        and len(other_projects) > 0
    ):
        prompt += "\n⚠️  CROSS-REPOSITORY CONTEXT:\n"
        prompt += "   • This session has work in multiple repositories\n"
        prompt += f"   • Other repositories: {', '.join(other_projects)}\n"
        prompt += "\n   RECOMMENDED: Use the /daf list-conversations slash command to see all conversations\n"
        prompt += "   Use the /daf read-conversation slash command to read work done in other repositories\n"
        prompt += "\n   This helps maintain consistency across the multi-repository feature implementation.\n"

    # Add analysis-only constraints for ticket_creation sessions
    if session_type == "ticket_creation":
        prompt += "\n⚠️  IMPORTANT CONSTRAINTS:\n"
        prompt += "   • This is an ANALYSIS-ONLY session for issue tracker ticket creation\n"
        prompt += "   • DO NOT modify any code or create/checkout git branches\n"
        prompt += "   • DO NOT make any file changes - only READ and ANALYZE\n"
        prompt += "   • Focus on understanding the codebase to write a good issue tracker ticket\n"
        prompt += "\nRemember: This is READ-ONLY analysis. Do not modify any files.\n"

    # Add testing instructions for development sessions (if enabled in config)
    if session_type == "development" and config and config.prompts.show_prompt_unit_tests:
        prompt += "\n⚠️  IMPORTANT: Testing Requirements:\n"
        prompt += "   • Identify the project's testing framework from the codebase\n"
        prompt += "   • Run the project's test suite after making code changes\n"
        prompt += "   • Create tests for new methods before or during implementation\n"
        prompt += "   • Parse test output and identify failures\n"
        prompt += "   • Fix all failing tests before marking tasks complete\n"
        prompt += "   • Report test results clearly to the user\n"
        prompt += "\nCommon test commands by language:\n"
        prompt += "   • Python: pytest (or python -m pytest)\n"
        prompt += "   • JavaScript/TypeScript: npm test (or jest, vitest)\n"
        prompt += "   • Go: go test ./...\n"
        prompt += "   • Rust: cargo test\n"
        prompt += "   • Java: mvn test (or gradle test)\n"
        prompt += "\nTarget: maintain or improve test coverage.\n"

    return prompt


def _fetch_issue_metadata_dict(issue_key: str) -> Optional[dict]:
    """Fetch issue tracker ticket metadata using JIRA REST API.

    Args:
        issue_key: issue tracker key (e.g., PROJ-52470)

    Returns:
        issue tracker ticket metadata dictionary if successful, None if fetch failed.
        The dictionary includes 'acceptance_criteria' field if present in the ticket.

    Raises:
        RuntimeError: If JIRA API request fails or ticket is not found
        FileNotFoundError: If JIRA_API_TOKEN is not set
    """
    try:
        # Load config to get field mappings
        config_loader = ConfigLoader()
        config = config_loader.load_config()
        field_mappings = config.jira.field_mappings if config else None

        jira_client = JiraClient(timeout=10)
        # Use get_ticket_detailed to include acceptance_criteria field
        ticket = jira_client.get_ticket_detailed(issue_key, field_mappings=field_mappings)
        return ticket

    except JiraNotFoundError as e:
        raise RuntimeError(f"issue tracker ticket {issue_key} not found")
    except JiraAuthError as e:
        raise RuntimeError(f"Authentication failed: {e}")
    except JiraApiError as e:
        raise RuntimeError(f"JIRA API error: {e}")
    except JiraConnectionError as e:
        raise RuntimeError(f"Connection error: {e}")
    except FileNotFoundError:
        raise
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timeout fetching issue tracker ticket {issue_key}")


@require_outside_claude
def create_new_session(
    name: str,
    goal: Optional[str] = None,
    working_directory: Optional[str] = None,
    path: Optional[str] = None,
    branch: Optional[str] = None,
    issue_key: Optional[str] = None,
    template_name: Optional[str] = None,
    workspace_name: Optional[str] = None,
    projects: Optional[str] = None,
    force_new_session: bool = False,
    model_profile: Optional[str] = None,
    output_json: bool = False,
    create_branch: Optional[bool] = None,
    source_branch: Optional[str] = None,
    on_branch_exists: Optional[str] = None,
    allow_uncommitted: bool = False,
    sync_upstream: Optional[bool] = None,
    auto_workspace: bool = False,
    session_index: Optional[int] = None,
) -> None:
    """Create a new session or add conversation to existing session.

    Args:
        name: Session group name (primary identifier)
        goal: Session goal/description (optional, uses JIRA title if provided)
        working_directory: Working directory name (defaults to directory name)
        path: Project path
        branch: Git branch name
        issue_key: Optional issue tracker key
        template_name: Optional template to use for session configuration
        workspace_name: Optional workspace name (AAP-63377)
        projects: Comma-separated list of repository names for multi-project sessions
        force_new_session: If True, always create new session instead of adding conversation
        model_profile: Optional model provider profile to use (e.g., "vertex", "llama-cpp")
        output_json: If True, output JSON instead of human-readable text
        create_branch: Control branch creation (None=prompt, True=create, False=skip)
        source_branch: Source branch to create new branch from
        on_branch_exists: Action when branch exists (error|use-existing|add-suffix|skip)
        allow_uncommitted: Allow uncommitted changes when switching branches
        sync_upstream: Sync with upstream before creating branch (None=prompt, True=sync, False=skip)
        auto_workspace: Auto-select workspace without prompting
        session_index: Select existing session by index (for multi-session selection)
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    # Determine if in non-interactive mode
    non_interactive = _is_non_interactive(output_json)

    # Load or auto-detect template
    from devflow.templates.manager import TemplateManager
    template_manager = TemplateManager()
    template = None
    auto_detected_template = False

    if template_name:
        # Explicit template specified
        template = template_manager.get_template(template_name)

        if not template:
            console.print(f"[red]✗[/red] Template '{template_name}' not found")
            console.print("\n[dim]List templates with: daf template list[/dim]")
            sys.exit(1)

        if not output_json:
            console.print(f"\n[cyan]Using template:[/cyan] [bold]{template.name}[/bold]")
            if template.description:
                console.print(f"[dim]{template.description}[/dim]")
    else:
        # Auto-detect template based on current directory (if auto_use is enabled)
        config = config_loader.load_config()

        if config and config.templates.auto_use:
            current_dir = Path.cwd()
            template = template_manager.find_matching_template(current_dir)
            if template:
                auto_detected_template = True
                if not output_json:
                    console.print(f"\n[cyan]✓ Auto-detected template:[/cyan] [bold]{template.name}[/bold]")
                    if template.description:
                        console.print(f"[dim]{template.description}[/dim]")

    # Use template values as defaults (can be overridden by explicit arguments)
    # Note: Do NOT use template.issue_key as issue_key - it's a project prefix (e.g., "PROJ")
    # not a full ticket key (e.g., "PROJ-12345"). User must explicitly provide --jira flag.
    if template:
        if working_directory is None and template.working_directory:
            working_directory = template.working_directory
        if branch is None and template.branch:
            branch = template.branch

    # Fetch JIRA metadata if issue key is provided (and validate ticket exists)
    issue_metadata_dict = None
    issue_title = None
    if issue_key:
        try:
            console.print(f"\n[cyan]Fetching issue tracker ticket {issue_key}...[/cyan]")
            issue_metadata_dict = _fetch_issue_metadata_dict(issue_key)
            if issue_metadata_dict:
                issue_title = issue_metadata_dict.get("summary")
                console.print(f"[green]✓[/green] Title: {issue_title}")
                console.print(f"[dim]Status: {issue_metadata_dict.get('status')}, Type: {issue_metadata_dict.get('type')}[/dim]")
            else:
                console.print("[yellow]⚠[/yellow] Could not parse JIRA metadata, but ticket exists")
        except RuntimeError as e:
            console.print(f"[red]✗[/red] {e}")
            sys.exit(1)

    # Note: Session existence check moved to after working_directory is determined
    # This allows proper multi-conversation support (add conversation vs create new session)

    # AAP-63377: Workspace selection BEFORE repository discovery
    # Check if session already exists to get stored workspace preference
    existing_session = session_manager.get_session(name)

    # Select workspace using priority resolution
    from devflow.cli.utils import select_workspace
    selected_workspace_name = select_workspace(
        config,
        workspace_flag=workspace_name,
        session=existing_session,
        skip_prompt=(output_json or auto_workspace or non_interactive)
    )

    # Get workspace path for multi-project detection
    workspace_path = None
    if selected_workspace_name:
        from devflow.cli.utils import get_workspace_path
        workspace_path = get_workspace_path(config, selected_workspace_name)

        # Auto-upgrade skills and commands for this workspace if needed
        if workspace_path:
            from devflow.utils.workspace_utils import ensure_workspace_skills_and_commands
            success, error = ensure_workspace_skills_and_commands(workspace_path, quiet=True)
            if not success:
                console.print(f"[yellow]⚠[/yellow] Warning: {error}")

    # Multi-project workflow (Issue #149)
    # If --projects flag is provided OR user wants to select multiple projects interactively
    multi_project_names = None

    if projects:
        # --projects flag provided - use those projects
        multi_project_names = [p.strip() for p in projects.split(',')]
    elif workspace_path and not non_interactive and path is None:
        # No --projects flag, but we have a workspace - offer interactive multi-project selection
        workspace_path_obj = Path(workspace_path)
        available_repos = scan_workspace_repositories(workspace_path_obj)

        if len(available_repos) > 1:
            # Multiple repos available - ask if user wants multi-project session
            console.print(f"\n[cyan]Detected {len(available_repos)} git repositories in workspace '{selected_workspace_name}':[/cyan]")
            for repo in available_repos[:10]:  # Show first 10
                console.print(f"  • {repo}")
            if len(available_repos) > 10:
                console.print(f"  ... and {len(available_repos) - 10} more")

            if Confirm.ask("\nCreate multi-project session (work across multiple repos)?", default=False):
                # User wants multi-project - let them select projects
                from rich.prompt import Prompt

                console.print("\n[bold]Select projects (comma-separated numbers or names):[/bold]")
                for i, repo in enumerate(available_repos, 1):
                    console.print(f"{i}. {repo}")

                selection = Prompt.ask("\nEnter project numbers or names (e.g., 1,3,5 or backend-api,frontend-app)")

                # Parse selection (could be numbers or names)
                selected_projects = []
                for item in selection.split(','):
                    item = item.strip()
                    if item.isdigit():
                        # Numeric selection
                        idx = int(item) - 1
                        if 0 <= idx < len(available_repos):
                            selected_projects.append(available_repos[idx])
                    else:
                        # Name selection
                        if item in available_repos:
                            selected_projects.append(item)
                        else:
                            console.print(f"[yellow]⚠[/yellow] Project '{item}' not found - skipping")

                if len(selected_projects) > 1:
                    multi_project_names = selected_projects
                    console.print(f"\n[green]✓[/green] Selected {len(multi_project_names)} projects:")
                    for proj in multi_project_names:
                        console.print(f"  • {proj}")
                elif len(selected_projects) == 1:
                    # Only one project selected - continue with single-project flow
                    path = str(workspace_path_obj / selected_projects[0])
                    console.print(f"\n[dim]Only one project selected - continuing with single-project session[/dim]")
                else:
                    console.print("\n[yellow]⚠[/yellow] No valid projects selected - continuing with single-project session")

    # If multi-project mode, create multi-project session
    if multi_project_names:
        # Validate all projects exist in workspace
        if not workspace_path:
            console.print("[red]✗[/red] Internal error: workspace_path not set (should have been validated)")
            raise click.Abort()

        workspace_path_obj = Path(workspace_path)
        missing_projects = []
        for proj_name in multi_project_names:
            proj_path = workspace_path_obj / proj_name
            if not proj_path.exists() or not (proj_path / '.git').exists():
                missing_projects.append(proj_name)

        if missing_projects:
            console.print(f"[red]✗[/red] The following projects were not found in workspace '{selected_workspace_name}':")
            for proj in missing_projects:
                console.print(f"  • {proj}")
            console.print(f"\n[dim]Workspace path: {workspace_path}[/dim]")
            raise click.Abort()

        # Multi-project session creation - delegate to helper function
        from devflow.cli.commands.new_command_multiproject import create_multi_project_session
        create_multi_project_session(
            session_manager=session_manager,
            config_loader=config_loader,
            config=config,
            name=name,
            goal=goal,
            issue_key=issue_key,
            issue_metadata_dict=issue_metadata_dict,
            issue_title=issue_title,
            project_names=multi_project_names,
            workspace_path=workspace_path,
            selected_workspace_name=selected_workspace_name,
            force_new_session=force_new_session,
            model_profile=model_profile,
            output_json=output_json,
            create_branch=create_branch,
            source_branch=source_branch,
            on_branch_exists=on_branch_exists,
            allow_uncommitted=allow_uncommitted,
            sync_upstream=sync_upstream,
            non_interactive=non_interactive,
        )
        return

    # Determine project path (single-project mode)
    if path is None:
        # Check if current directory is a git repository (indicates it's a project)
        current_dir = Path.cwd()
        is_current_dir_a_project = GitUtils.is_git_repository(current_dir)

        if non_interactive:
            # Non-interactive mode: use current directory or error
            if is_current_dir_a_project:
                path = str(current_dir)
                console_print(f"[dim]Non-interactive mode: using current directory: {path}[/dim]")
            else:
                console.print("[red]✗[/red] No --path specified and current directory is not a git repository")
                console.print("[dim]In non-interactive mode, you must either:")
                console.print("  1. Run from a git repository directory, or")
                console.print("  2. Specify --path explicitly[/dim]")
                if output_json:
                    json_output(success=False, error={"code": "NO_PATH", "message": "Path required in non-interactive mode"})
                raise click.Abort()
        else:
            # Interactive mode: offer suggestions and prompts
            # Always offer intelligent repository suggestions (with or without JIRA)
            # Pass selected workspace to ensure correct repository discovery
            suggested_path = _suggest_and_select_repository(
                config_loader,
                issue_metadata_dict=issue_metadata_dict,
                issue_key=issue_key,
                workspace_name=selected_workspace_name,
            )
            if suggested_path:
                path = suggested_path
            elif is_current_dir_a_project:
                # Current directory is a project - offer to use it
                if Confirm.ask(f"Use current directory?\n  {current_dir}", default=True):
                    path = str(current_dir)
                else:
                    path = Prompt.ask("Enter project path")
                    if not path or not path.strip():
                        console.print("[red]✗[/red] Project path cannot be empty")
                        raise click.Abort()
                    path = path.strip()
            else:
                # Not in a project directory and no suggestions - must specify path
                console.print(f"\n[yellow]Current directory is not a git repository[/yellow]")
                console.print(f"[dim]You must select a project directory for the session[/dim]")
                path = Prompt.ask("Enter project path")
                if not path or not path.strip():
                    console.print("[red]✗[/red] Project path cannot be empty")
                    raise click.Abort()
                path = path.strip()

    project_path = str(Path(path).absolute())

    # Determine working directory name
    if working_directory is None:
        working_directory = Path(project_path).name

    # Note: workspace_path already resolved earlier in the function

    # Auto-create template if enabled and no template was used

    if config and config.templates.auto_create and not template:
        # Check if template already exists for this directory
        project_path_obj = Path(project_path)
        existing_template = template_manager.find_matching_template(project_path_obj)

        if not existing_template:
            # Auto-create template
            template = template_manager.auto_create_template(
                project_path=project_path_obj,
                description=f"Auto-created template for {project_path_obj.name}",
                default_jira_project=issue_key.split('-')[0] if issue_key and '-' in issue_key else None,
            )
            if not output_json:
                console.print(f"\n[cyan]✓ Auto-created template:[/cyan] [bold]{template.name}[/bold]")
                console.print(f"[dim]Template will be automatically used for future sessions in this directory[/dim]")

    # Update template usage if a template was used
    if template:
        template_manager.update_usage(template.name)

    # Check for concurrent active sessions in the same project BEFORE any git operations
    # AAP-63377: Pass workspace_name to enable workspace-aware concurrent session checking
    if not check_concurrent_session(session_manager, project_path, name, selected_workspace_name, action="create"):
        return

    # Initialize source_branch_for_base (used later for setting base_branch)
    source_branch_for_base = None

    # Handle git branch creation if this is a git repository
    if branch is None:
        # Use issue_key if available, otherwise use name for branch creation
        branch_identifier = issue_key if issue_key else name
        branch_result = _handle_branch_creation(
            project_path,
            branch_identifier,
            goal,
            config=config,
            source_branch=source_branch,
            create_branch=create_branch,
            on_branch_exists=on_branch_exists,
            allow_uncommitted=allow_uncommitted,
            sync_upstream=sync_upstream,
            non_interactive=non_interactive,
        )

        # Check if user explicitly cancelled due to uncommitted changes
        if branch_result is False:
            console.print("\n[yellow]Session creation cancelled[/yellow]")
            return

        # Handle return value: could be tuple (branch, source_branch) or just branch name
        if isinstance(branch_result, tuple):
            branch, source_branch_for_base = branch_result
        else:
            branch = branch_result

    # Generate session ID upfront
    session_id = str(uuid.uuid4())

    # Build concatenated goal for storage
    # If issue tracker ticket, concatenate: "{ISSUE_KEY}: {JIRA_TITLE}" or "{ISSUE_KEY}: {goal}"
    # Otherwise use the provided goal
    storage_goal = goal
    if issue_key and issue_title:
        storage_goal = f"{issue_key}: {issue_title}"
    elif issue_key and goal:
        storage_goal = f"{issue_key}: {goal}"
    elif issue_key:
        storage_goal = issue_key

    # Check if a session already exists for this name/issue key (multi-conversation support)
    # If so, add a conversation to the existing session instead of creating a new session
    # Skip this check if --new-session flag is set (force creation of new session)
    existing_sessions = session_manager.index.get_sessions(name)
    session = None

    if force_new_session and existing_sessions:
        console.print(f"\n[cyan]Creating new session (--new-session flag set)[/cyan]")
        console.print(f"[dim]Existing sessions: {len(existing_sessions)}. New session will be #{len(existing_sessions) + 1}[/dim]\n")

    if existing_sessions and not force_new_session:
        # Sessions exist - check if we should add a conversation or create a new session
        if len(existing_sessions) == 1:
            session = existing_sessions[0]

            # Check if a conversation already exists for this working directory
            if session.get_conversation(working_directory):
                console.print(f"\n[yellow]⚠ A conversation already exists for {working_directory} in session {name}[/yellow]")
                console.print(f"[dim]Use 'daf open {name}' to resume the existing conversation[/dim]")
                sys.exit(1)

            # Add conversation to existing session
            console.print(f"\n[cyan]Adding conversation to existing session: {name}[/cyan]")

            # AAP-64886: Use selected workspace_path instead of default
            # Set base_branch to source_branch if available (fixes #139 - no sync prompt after creating branch)
            session.add_conversation(
                working_dir=working_directory,
                ai_agent_session_id=session_id,
                project_path=project_path,
                branch=branch or "",  # branch is required, use empty string if None
                base_branch=source_branch_for_base or "main",
                workspace=workspace_path,
            )
            session.working_directory = working_directory

            # AAP-64886: Update session's workspace if not already set
            if not session.workspace_name and selected_workspace_name:
                session.workspace_name = selected_workspace_name

            session_manager.update_session(session)
        else:
            # Multiple sessions exist - use session_index or prompt user to select one or create new
            new_option = len(existing_sessions) + 1

            if session_index is not None:
                # Use provided session index
                if session_index < 1 or session_index > new_option:
                    console.print(f"[red]✗[/red] Invalid session index: {session_index}")
                    console.print(f"[dim]Valid range: 1-{new_option} (1-{len(existing_sessions)} for existing sessions, {new_option} for new)[/dim]")
                    if output_json:
                        json_output(success=False, error={"code": "INVALID_SESSION_INDEX", "message": f"Session index must be between 1 and {new_option}"})
                    raise click.Abort()

                if session_index == new_option:
                    session = None  # Create new session
                    console_print(f"[dim]Using session index {session_index}: creating new conversation[/dim]")
                else:
                    session = existing_sessions[session_index - 1]
                    console_print(f"[dim]Using session index {session_index}: adding to session #{session.session_id}[/dim]")
            elif non_interactive:
                # Non-interactive mode without session_index - error
                console.print(f"[red]✗[/red] Multiple sessions found for '{name}' - must specify --session-index")
                console.print(f"[dim]Found {len(existing_sessions)} sessions. Use --session-index 1-{len(existing_sessions)} to select, or {new_option} to create new[/dim]")
                if output_json:
                    json_output(success=False, error={"code": "AMBIGUOUS_SESSION", "message": "Multiple sessions found, --session-index required"})
                raise click.Abort()
            else:
                # Interactive mode - prompt user
                from rich.prompt import IntPrompt

                console.print(f"\n[yellow]Found {len(existing_sessions)} existing sessions for '{name}':[/yellow]\n")
                for i, sess in enumerate(existing_sessions, 1):
                    console.print(f"  {i}. Session #{sess.session_id}")
                    console.print(f"     Goal: {sess.goal}")
                    console.print(f"     Conversations: {len(sess.conversations)}")
                    if sess.conversations:
                        for wd in sess.conversations.keys():
                            console.print(f"       - {wd}")
                    console.print()

                console.print(f"  {new_option}. → Create new conversation (separate work stream)")
                console.print()

                choice = IntPrompt.ask(
                    "Add to which session? (or create new conversation)",
                    choices=[str(i) for i in range(1, new_option + 1)],
                    default="1"
                )

                if choice == new_option:
                    # User wants to create new session - set session to None to fall through
                    session = None
                else:
                    # Add to selected session
                    session = existing_sessions[choice - 1]

                # Check if conversation already exists
                if session.get_conversation(working_directory):
                    console.print(f"\n[yellow]⚠ A conversation already exists for {working_directory} in session [/yellow]")
                    console.print(f"[dim]Use 'daf open {name}' to resume the existing conversation[/dim]")
                    sys.exit(1)

                console.print(f"\n[cyan]Adding conversation to session [/cyan]")

                # AAP-63377: Use selected workspace path
                # Set base_branch to source_branch if available (fixes #139 - no sync prompt after creating branch)
                session.add_conversation(
                    working_dir=working_directory,
                    ai_agent_session_id=session_id,
                    project_path=project_path,
                    branch=branch or "",  # branch is required, use empty string if None
                    base_branch=source_branch_for_base or "main",
                    workspace=workspace_path,
                )
                session.working_directory = working_directory

                # AAP-63377: Update session's workspace if not already set
                if not session.workspace_name and selected_workspace_name:
                    session.workspace_name = selected_workspace_name

                session_manager.update_session(session)

    # Create session if we didn't add to an existing one
    if session is None:
        session = session_manager.create_session(
            name=name,
            issue_key=issue_key,
            goal=storage_goal,
            working_directory=working_directory,
            project_path=project_path,
            branch=branch,
            ai_agent_session_id=session_id,
            model_profile=model_profile,
        )

        # Set base_branch to source_branch if available (fixes #139 - no sync prompt after creating branch)
        if source_branch_for_base and session.active_conversation:
            session.active_conversation.base_branch = source_branch_for_base
            session_manager.update_session(session)

        # AAP-63377: Store selected workspace in session
        if selected_workspace_name:
            session.workspace_name = selected_workspace_name
            session_manager.update_session(session)

    # Populate JIRA metadata if available
    if issue_metadata_dict:
        # Copy ALL fields from issue_metadata_dict to issue_metadata (generic approach)
        # Exclude the 'key' and 'updated' fields (already stored separately)
        session.issue_metadata = {k: v for k, v in issue_metadata_dict.items() if k not in ('key', 'updated') and v is not None}
        session_manager.update_session(session)

    # JSON output mode
    if output_json:
        session_data = serialize_session(session)
        json_output(
            success=True,
            data={
                "session": session_data,
                "ai_agent_session_id": session_id,
            }
        )
        return

    # Display message (only in non-JSON mode)
    if not output_json:
        display_name = f"{name} ({issue_key})" if issue_key else name
        console.print(f"\n[green]✓[/green] Created session for [bold]{display_name}[/bold] (session )")

        # Display session context - use session.goal which now contains the concatenated value
        jira_url = config.jira.url if config and config.jira else None
        _display_session_banner(name, session.goal, working_directory, branch, project_path, session_id, issue_key, jira_url)

    # Check if we should launch Claude Code
    if not should_launch_claude_code(config=config, mock_mode=True):
        if not output_json:
            console.print(f"\n[dim]Start later with: daf open {name}[/dim]")
        return

    # Change to project directory and launch Claude Code
    try:
        console.print(f"\n[cyan]Launching Claude Code in {project_path}...[/cyan]")

        # Update session status and start work session
        session.status = "in_progress"
        session_manager.start_work_session(name)

        # Generate the initial prompt with context loading hints
        # Use session.goal which now contains the concatenated value
        # AAP-XXXXX: Use selected workspace instead of default workspace for skill discovery
        workspace = None
        if selected_workspace_name and config and config.repos:
            from devflow.cli.utils import get_workspace_path
            workspace = get_workspace_path(config, selected_workspace_name)
        elif config and config.repos:
            workspace = config.repos.get_default_workspace_path()

        initial_prompt = _generate_initial_prompt(
            name, session.goal, issue_key, issue_title,
            project_path=project_path, workspace=workspace
        )

        # Get agent backend from config
        from devflow.agent import create_agent_client

        agent_backend = config.agent_backend if config else "claude"
        agent = create_agent_client(agent_backend)

        # Get model provider profile if configured
        from devflow.utils.model_provider import get_active_profile as get_model_profile
        model_profile = None
        if config and config.model_provider:
            model_profile = get_model_profile(config, override_profile_name=session.model_profile)

        # Set environment variables for the AI agent process
        # DEVAIFLOW_IN_SESSION: Flag to indicate we're inside an AI session (used by safety guards)
        # AI_AGENT_SESSION_ID: Generic session ID (works with any AI agent)
        env = os.environ.copy()
        env["DEVAIFLOW_IN_SESSION"] = "1"
        env["AI_AGENT_SESSION_ID"] = session_id

        # Set GCP Vertex AI region if configured (deprecated - for backward compatibility)
        if config and config.gcp_vertex_region:
            env["CLOUD_ML_REGION"] = config.gcp_vertex_region

        # Apply environment variables to current process (so agent sees them)
        for key, value in env.items():
            if key not in os.environ:
                os.environ[key] = value

        # Validate that DAF_AGENTS.md exists before launching agent
        if not validate_daf_agents_md(session, config_loader):
            return

        # Set up signal handlers for cleanup (using unified utility)
        setup_signal_handlers(session, session_manager, name, config)

        # Launch agent with initial prompt
        try:
            process = agent.launch_with_prompt(
                project_path=project_path,
                initial_prompt=initial_prompt,
                session_id=session_id,
                model_provider_profile=model_profile,
                skills_dirs=None,  # Will be auto-discovered
                workspace_path=workspace_path,
                config=config
            )
            # Wait for the agent process to complete
            process.wait()
        finally:
            if not is_cleanup_done():
                console.print(f"\n[green]✓[/green] Claude session completed")

                # Update session status to paused
                session.status = "paused"
                session_manager.update_session(session)

                # Auto-pause: End work session when Claude Code closes
                session_manager.end_work_session(name)

                console.print(f"[dim]Resume anytime with: daf open {name}[/dim]")

                # Check if we should run 'daf complete' on exit
                # Import here to avoid circular dependency
                from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
                _prompt_for_complete_on_exit(session, config)

    except Exception as e:
        console.print(f"\n[red]Error launching Claude Code:[/red] {e}")

        # Update session status to paused on error
        session.status = "paused"
        session_manager.update_session(session)

        # Auto-pause: End work session even if Claude launch failed
        try:
            session_manager.end_work_session(name)
        except Exception:
            # Silently ignore if work session wasn't started
            pass

        console.print(f"\n[yellow]You can manually start with:[/yellow]")
        console.print(f"  cd {project_path}")
        # AAP-XXXXX: Use selected workspace instead of default workspace
        workspace = None
        if selected_workspace_name and config and config.repos:
            from devflow.cli.utils import get_workspace_path
            workspace = get_workspace_path(config, selected_workspace_name)
        elif config and config.repos:
            workspace = config.repos.get_default_workspace_path()
        initial_prompt = _generate_initial_prompt(name, session.goal, issue_key, issue_title,
                                                   project_path=project_path, workspace=workspace)
        console.print(f"  claude --session-id {session_id} \"{initial_prompt}\"")


def _suggest_and_select_repository(
    config_loader: ConfigLoader,
    issue_metadata_dict: Optional[dict] = None,
    issue_key: Optional[str] = None,
    workspace_name: Optional[str] = None,
) -> Optional[str]:
    """Suggest repositories based on issue tracker ticket and let user select.

    Args:
        config_loader: ConfigLoader instance
        issue_metadata_dict: issue tracker ticket metadata (if available)
        issue_key: issue tracker key (if available)
        workspace_name: Optional workspace name to use (AAP-64886)

    Returns:
        Selected repository path or None if user cancelled
    """
    config = config_loader.load_config()

    # Get available repositories from workspace
    available_repos = []
    workspace_path = None
    # AAP-64886: Use selected workspace instead of default
    workspace_path_str = resolve_workspace_path(config, workspace_name)
    if workspace_path_str:
        workspace_path = Path(workspace_path_str).expanduser()
        try:
            available_repos = scan_workspace_repositories(workspace_path_str)
        except (ValueError, RuntimeError) as e:
            console.print(f"[yellow]Warning: {e}[/yellow]")

    if not available_repos:
        # No workspace configured or no repos found
        return None

    # Calculate default repository using 3-tier priority system
    default_repo = None

    if config and config.prompts and issue_key:
        # Tier 1: Project-specific memory (JIRA project key or Git owner/repo)
        # Check for JIRA project key (format: "PROJ-123")
        project_key = issue_key.split('-')[0] if '-' in issue_key and not issue_key.startswith('#') else None
        if project_key and config.prompts.remember_last_repo_per_project:
            remembered_repo = config.prompts.remember_last_repo_per_project.get(project_key)
            if remembered_repo and remembered_repo in available_repos:
                default_repo = remembered_repo
                console.print(f"\n[cyan]Remembered repository for {project_key}: {remembered_repo}[/cyan]")
                console.print("[dim]Press Enter to use it, or type a different selection[/dim]")

        # Check for Git issue key (format: "owner/repo#123" or "#123")
        if not default_repo and '#' in issue_key:
            # Extract owner/repo part if present
            if '/' in issue_key and '#' in issue_key:
                git_repo_key = issue_key.split('#')[0]  # Extract "owner/repo"
                if config.prompts.remember_last_repo_per_git_repo:
                    remembered_repo = config.prompts.remember_last_repo_per_git_repo.get(git_repo_key)
                    if remembered_repo and remembered_repo in available_repos:
                        default_repo = remembered_repo
                        console.print(f"\n[cyan]Remembered repository for {git_repo_key}: {remembered_repo}[/cyan]")
                        console.print("[dim]Press Enter to use it, or type a different selection[/dim]")

    # Tier 2: Workspace-level last-used repo (fallback)
    if not default_repo and config and config.prompts and workspace_name:
        if config.prompts.last_used_repo_per_workspace:
            remembered_repo = config.prompts.last_used_repo_per_workspace.get(workspace_name)
            if remembered_repo and remembered_repo in available_repos:
                default_repo = remembered_repo
                console.print(f"\n[cyan]Last used repository in workspace '{workspace_name}': {remembered_repo}[/cyan]")
                console.print("[dim]Press Enter to use it, or type a different selection[/dim]")

    # Generate repository suggestions using the learning model
    suggester = RepositorySuggester()

    suggestions = []
    if issue_metadata_dict:
        # Extract ticket information for suggestions
        summary = issue_metadata_dict.get("summary", "")
        description = issue_metadata_dict.get("description")
        ticket_type = issue_metadata_dict.get("type")
        labels = issue_metadata_dict.get("labels", [])

        # Get config keywords for fallback
        config_keywords = config.repos.keywords if config and config.repos else {}

        suggestions = suggester.suggest_repositories(
            issue_key=issue_key,
            ticket_type=ticket_type,
            summary=summary,
            description=description,
            labels=labels,
            available_repos=available_repos,
            config_keywords=config_keywords,
        )

    # Display suggestions
    if suggestions:
        console.print("\n[bold cyan]Suggested repositories (based on ticket content):[/bold cyan]")
        for i, suggestion in enumerate(suggestions, 1):
            confidence_pct = int(suggestion.confidence * 100)
            console.print(f"  {i}. [bold]{suggestion.repository}[/bold] ({confidence_pct}% confidence)")
            if suggestion.reasons:
                console.print(f"     [dim]• {suggestion.reasons[0]}[/dim]")
        console.print()

    # Display all available repositories
    console.print(f"\n[bold]Available repositories ({len(available_repos)}):[/bold]")
    for i, repo in enumerate(available_repos, 1):
        # Highlight if it's in suggestions
        if suggestions and any(s.repository == repo for s in suggestions[:3]):
            console.print(f"  {i}. {repo} [dim](suggested)[/dim]")
        else:
            console.print(f"  {i}. {repo}")

    # Prompt for selection
    console.print(f"\n[bold]Select repository:[/bold]")
    console.print(f"  • Enter a number (1-{len(available_repos)}) to select from the list above")
    console.print(f"  • Enter a repository name")
    console.print(f"  • Enter an absolute path (starting with / or ~)")
    console.print(f"  • Enter 'cancel' or 'q' to use current directory")

    # Tier 3: Calculate default selection based on suggestions or default_repo
    default_selection = "1"  # Final fallback: first repository
    if default_repo and default_repo in available_repos:
        # Use the remembered repo index as default
        default_index = available_repos.index(default_repo) + 1
        default_selection = str(default_index)
    elif suggestions:
        # Use first suggestion as default
        suggested_repo = suggestions[0].repository
        if suggested_repo in available_repos:
            default_index = available_repos.index(suggested_repo) + 1
            default_selection = str(default_index)

    selection = Prompt.ask("Selection", default=default_selection)

    # Validate input is not empty
    if not selection or selection.strip() == "":
        console.print(f"[red]✗[/red] Empty selection not allowed. Please enter a number (1-{len(available_repos)}), repository name, path, or 'cancel'/'q'")
        return None

    # Handle cancel
    if selection.lower() in ["cancel", "q"]:
        return None

    # Check if it's a number (selecting from list)
    if selection.isdigit():
        repo_index = int(selection) - 1
        if 0 <= repo_index < len(available_repos):
            repo_name = available_repos[repo_index]
            console.print(f"[dim]Selected: {repo_name}[/dim]")

            if workspace_path:
                selected_path = str(workspace_path / repo_name)

                # Record selection for learning
                if issue_metadata_dict:
                    suggester.record_selection(
                        repository=repo_name,
                        issue_key=issue_key,
                        ticket_type=issue_metadata_dict.get("type"),
                        summary=issue_metadata_dict.get("summary"),
                        description=issue_metadata_dict.get("description"),
                        labels=issue_metadata_dict.get("labels", []),
                    )

                # Remember this repository (project-specific, git-specific, and workspace-level)
                if config:
                    config_updated = False

                    # Save for JIRA project (format: "PROJ-123")
                    if issue_key and '-' in issue_key and not issue_key.startswith('#'):
                        project_key = issue_key.split('-')[0]
                        config.prompts.remember_last_repo_per_project[project_key] = repo_name
                        console.print(f"[dim]Remembered {repo_name} for {project_key} tickets[/dim]")
                        config_updated = True

                    # Save for Git repository (format: "owner/repo#123")
                    if issue_key and '#' in issue_key and '/' in issue_key:
                        git_repo_key = issue_key.split('#')[0]  # Extract "owner/repo"
                        config.prompts.remember_last_repo_per_git_repo[git_repo_key] = repo_name
                        console.print(f"[dim]Remembered {repo_name} for {git_repo_key} issues[/dim]")
                        config_updated = True

                    # Always save as last-used repo for this workspace (fallback)
                    if workspace_name:
                        config.prompts.last_used_repo_per_workspace[workspace_name] = repo_name
                        config_updated = True

                    if config_updated:
                        config_loader.save_config(config)

                return selected_path
        else:
            console.print(f"[red]✗[/red] Invalid selection. Please choose 1-{len(available_repos)}")
            return None

    # Check if it's an absolute path
    elif selection.startswith("/") or selection.startswith("~"):
        project_path = Path(selection).expanduser().absolute()

        if not project_path.exists():
            console.print(f"[yellow]⚠[/yellow] Path does not exist: {project_path}")
            if not Confirm.ask("Use this path anyway?", default=False):
                return None

        # Record selection for learning (use directory name as repo)
        if issue_metadata_dict:
            suggester.record_selection(
                repository=project_path.name,
                issue_key=issue_key,
                ticket_type=issue_metadata_dict.get("type"),
                summary=issue_metadata_dict.get("summary"),
                description=issue_metadata_dict.get("description"),
                labels=issue_metadata_dict.get("labels", []),
            )

        return str(project_path)

    # Otherwise treat as repository name
    else:
        repo_name = selection

        if workspace_path:
            project_path = workspace_path / repo_name

            if not project_path.exists():
                console.print(f"[yellow]⚠[/yellow] Repository not found: {project_path}")
                if not Confirm.ask("Use this path anyway?", default=False):
                    return None

            # Record selection for learning
            if issue_metadata_dict:
                suggester.record_selection(
                    repository=repo_name,
                    issue_key=issue_key,
                    ticket_type=issue_metadata_dict.get("type"),
                    summary=issue_metadata_dict.get("summary"),
                    description=issue_metadata_dict.get("description"),
                    labels=issue_metadata_dict.get("labels", []),
                )

            # Remember this repository (project-specific, git-specific, and workspace-level)
            if config:
                config_updated = False

                # Save for JIRA project (format: "PROJ-123")
                if issue_key and '-' in issue_key and not issue_key.startswith('#'):
                    project_key = issue_key.split('-')[0]
                    config.prompts.remember_last_repo_per_project[project_key] = repo_name
                    console.print(f"[dim]Remembered {repo_name} for {project_key} tickets[/dim]")
                    config_updated = True

                # Save for Git repository (format: "owner/repo#123")
                if issue_key and '#' in issue_key and '/' in issue_key:
                    git_repo_key = issue_key.split('#')[0]  # Extract "owner/repo"
                    config.prompts.remember_last_repo_per_git_repo[git_repo_key] = repo_name
                    console.print(f"[dim]Remembered {repo_name} for {git_repo_key} issues[/dim]")
                    config_updated = True

                # Always save as last-used repo for this workspace (fallback)
                if workspace_name:
                    config.prompts.last_used_repo_per_workspace[workspace_name] = repo_name
                    config_updated = True

                if config_updated:
                    config_loader.save_config(config)

            return str(project_path)
        else:
            console.print(f"[red]✗[/red] No workspace configured in config")
            return None


def _get_default_source_branch(path: Path) -> str:
    """Determine the smart default source branch.

    Priority:
    1. upstream/main (if upstream remote exists)
    2. origin/main (if origin remote exists)
    3. main (local)

    Args:
        path: Repository path

    Returns:
        Default source branch name
    """
    # Check if upstream remote exists
    remotes = GitUtils.get_remote_names(path)

    if 'upstream' in remotes:
        # Check if upstream/main exists
        if GitUtils.branch_exists(path, 'upstream/main'):
            return 'upstream/main'
        # Try upstream/master
        if GitUtils.branch_exists(path, 'upstream/master'):
            return 'upstream/master'

    if 'origin' in remotes:
        # Check if origin/main exists
        if GitUtils.branch_exists(path, 'origin/main'):
            return 'origin/main'
        # Try origin/master
        if GitUtils.branch_exists(path, 'origin/master'):
            return 'origin/master'

    # Fallback to local main
    if GitUtils.branch_exists(path, 'main'):
        return 'main'
    if GitUtils.branch_exists(path, 'master'):
        return 'master'

    # Last resort: return current branch
    current = GitUtils.get_current_branch(path)
    return current if current else 'main'


def _show_branch_suggestions(path: Path, attempted_branch: str) -> None:
    """Show helpful branch suggestions when user enters invalid branch.

    Args:
        path: Repository path
        attempted_branch: The branch name that failed validation
    """
    # Extract remote name if present
    if '/' in attempted_branch:
        remote, branch_part = attempted_branch.split('/', 1)

        # Check if remote exists
        remotes = GitUtils.get_remote_names(path)
        if remote not in remotes:
            console.print(f"[dim]Available remotes: {', '.join(remotes)}[/dim]")
            return

        # Show branches on that remote
        import subprocess
        result = subprocess.run(
            ['git', 'branch', '-r'],
            cwd=path,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            remote_branches = [
                line.strip().replace('origin/', '').replace('upstream/', '')
                for line in result.stdout.split('\n')
                if remote in line and '->' not in line
            ]

            # Find similar branches (fuzzy match)
            similar = [b for b in remote_branches if branch_part.lower() in b.lower()]

            if similar:
                console.print(f"\n[dim]Available branches on '{remote}':[/dim]")
                for branch in similar[:5]:  # Show max 5
                    console.print(f"  • {remote}/{branch}")


def _prompt_for_source_branch(path: Path, default_base: str) -> Optional[str]:
    """Prompt user for source branch with validation.

    Args:
        path: Repository path
        default_base: Default source branch suggestion

    Returns:
        Source branch name if valid, None if user cancelled
    """
    from rich.prompt import IntPrompt

    console.print("\nCreate branch from which base?")
    console.print(f"[dim]Default: {default_base}[/dim]")
    console.print(f"[dim]Or enter any branch name (e.g., upstream/develop, origin/feature/api)[/dim]")

    while True:
        source_branch = Prompt.ask("Enter source branch", default=default_base)

        # Allow cancel
        if source_branch.lower() in ['cancel', 'q']:
            return None

        # Validate branch exists
        if GitUtils.branch_exists(path, source_branch):
            console.print(f"[green]✓[/green] Branch '{source_branch}' exists")
            return source_branch
        else:
            console.print(f"[red]✗[/red] Branch '{source_branch}' does not exist")

            # Show helpful suggestions
            _show_branch_suggestions(path, source_branch)

            # Ask again
            console.print("[dim]Please try again or type 'cancel' to quit[/dim]")


def _handle_existing_branch(
    path: Path,
    branch_name: str,
    default_source: str,
    config: Optional[any] = None
) -> Optional[str]:
    """Handle case where branch already exists.

    Args:
        path: Repository path
        branch_name: Branch name that already exists
        default_source: Default source branch for merging
        config: Configuration object

    Returns:
        Branch name if successful, None if user cancelled
    """
    from rich.prompt import IntPrompt

    console.print(f"\n[yellow]⚠[/yellow] Branch '{branch_name}' already exists locally")
    console.print("\nWhat would you like to do?")
    console.print("  1. Switch to it and merge with another branch (sync it)")
    console.print("  2. Switch to it without merging (use as-is)")
    console.print("  3. Choose a different branch name")
    console.print("  4. Cancel")

    choice = IntPrompt.ask("Selection", choices=["1", "2", "3", "4"], default=1)

    if choice == 1:
        # Switch and merge
        if not GitUtils.checkout_branch(path, branch_name):
            console.print(f"[red]✗[/red] Failed to switch to branch '{branch_name}'")
            return None

        console.print(f"[green]✓[/green] Switched to '{branch_name}'")

        # Prompt for merge source
        source = _prompt_for_source_branch(path, default_source)
        if not source:
            # User cancelled - stay on branch but don't merge
            console.print("[yellow]Cancelled merge - staying on current branch[/yellow]")
            return branch_name

        # Attempt merge
        console.print(f"\nMerging '{source}' into '{branch_name}'...")
        if GitUtils.merge_branch(path, source):
            console.print(f"[green]✓[/green] Successfully merged")
            return branch_name
        else:
            console.print(f"[red]✗[/red] Merge conflicts detected")
            console.print("\n[yellow]Conflicting files:[/yellow]")

            # Show conflicting files
            import subprocess
            result = subprocess.run(
                ['git', 'diff', '--name-only', '--diff-filter=U'],
                cwd=path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout:
                for file in result.stdout.split('\n'):
                    if file:
                        console.print(f"  • {file}")

            console.print("\n[dim]Please resolve conflicts manually:[/dim]")
            console.print("[dim]  1. Fix conflicts in the files above[/dim]")
            console.print("[dim]  2. Run: git add <files>[/dim]")
            console.print("[dim]  3. Run: git commit[/dim]")
            console.print("[dim]  4. Run: daf open <session> (to continue)[/dim]")

            return None

    elif choice == 2:
        # Just switch, no merge
        if GitUtils.checkout_branch(path, branch_name):
            console.print(f"[green]✓[/green] Switched to '{branch_name}' (no merge)")
            return branch_name
        else:
            console.print(f"[red]✗[/red] Failed to switch to branch")
            return None

    elif choice == 3:
        # Choose different name - return special value to trigger retry
        return False  # Signal to caller to prompt for new name

    else:  # choice == 4
        console.print("[yellow]Cancelled[/yellow]")
        return None


def _handle_branch_conflict(path: Path, suggested_branch: str) -> Optional[str]:
    """Handle branch name conflict when suggested branch already exists.

    Provides interactive menu for resolving the conflict:
    1. Add suffix to branch name
    2. Use existing branch
    3. Provide custom branch name
    4. Skip branch creation

    Args:
        path: Repository path
        suggested_branch: Suggested branch name that already exists

    Returns:
        Branch name to use, or None to skip branch creation
    """
    # In JSON mode, default to using existing branch (option 2) without prompting
    if is_json_mode():
        return suggested_branch

    console.print("\n[bold]Options:[/bold]")
    console.print("1. Add suffix to branch name (e.g., aap-12345-fix-bug-v2)")
    console.print("2. Use existing branch (switch to it)")
    console.print("3. Provide custom branch name")
    console.print("4. Skip branch creation")

    choice = Prompt.ask("Select", choices=["1", "2", "3", "4"], default="1")

    if choice == "1":
        # Add suffix to branch name
        suffix = Prompt.ask("Enter suffix", default="v2")
        new_branch = f"{suggested_branch}-{suffix}"

        # Validate that new branch doesn't exist
        if GitUtils.branch_exists(path, new_branch):
            console.print(f"[yellow]⚠ Branch '{new_branch}' also exists[/yellow]")
            console.print("[yellow]Falling back to custom name option...[/yellow]")
            return _prompt_custom_branch_name(path, suggested_branch)

        return new_branch

    elif choice == "2":
        # Use existing branch
        return suggested_branch

    elif choice == "3":
        # Provide custom branch name
        return _prompt_custom_branch_name(path, suggested_branch)

    elif choice == "4":
        # Skip branch creation
        return None

    return None


def _prompt_custom_branch_name(path: Path, suggested_branch: str) -> Optional[str]:
    """Prompt user for a custom branch name.

    Args:
        path: Repository path
        suggested_branch: Original suggested branch name (for reference)

    Returns:
        Valid branch name, or None if user cancels
    """
    while True:
        custom_name = Prompt.ask("Enter custom branch name")

        if not custom_name:
            console.print("[yellow]Branch name cannot be empty[/yellow]")
            continue

        # Check if branch already exists
        if GitUtils.branch_exists(path, custom_name):
            console.print(f"[yellow]⚠ Branch '{custom_name}' already exists[/yellow]")
            if not Confirm.ask("Try another name?", default=True):
                # User wants to skip
                return None
            continue

        # Valid new branch name
        return custom_name


def _handle_branch_creation(
    project_path: str,
    issue_key: str,
    goal: Optional[str],
    auto_from_default: bool = False,
    config: Optional[any] = None,
    source_branch: Optional[str] = None,
    branch_name: Optional[str] = None,
    project_name: Optional[str] = None,
    create_branch: Optional[bool] = None,
    on_branch_exists: Optional[str] = None,
    allow_uncommitted: bool = False,
    sync_upstream: Optional[bool] = None,
    non_interactive: bool = False,
) -> Optional[str] | bool | tuple[str, str]:
    """Handle git branch creation with enhanced UX.

    Enhanced workflow:
    1. Check git repository
    2. Check uncommitted changes
    3. Prompt to create branch (show suggested name) OR use create_branch parameter
    4. Allow user to customize branch name OR use branch_name parameter
    5. Check if branch exists
       - If exists: use on_branch_exists strategy or offer merge/switch/rename options
       - If new: use source_branch parameter or prompt for source branch with validation
    6. If user declines: offer to sync with upstream/main OR use sync_upstream parameter

    Args:
        project_path: Project directory path
        issue_key: issue tracker key
        goal: Session goal (optional)
        auto_from_default: If True, use automatic mode with defaults
        config: Configuration object (optional, will load if not provided)
        source_branch: Optional source branch to use (skips prompt if provided)
        branch_name: Optional branch name to use (skips prompt if provided)
        project_name: Optional project name for display in prompts (multi-project mode)
        create_branch: Control branch creation (None=prompt, True=create, False=skip)
        on_branch_exists: Action when branch exists (error|use-existing|add-suffix|skip)
        allow_uncommitted: Allow uncommitted changes when switching branches
        sync_upstream: Sync with upstream before creating branch (None=prompt, True=sync, False=skip)
        non_interactive: If True, use defaults instead of prompting

    Returns:
        Tuple of (branch_name, source_branch) if newly created
        Branch name (str) if switched to existing branch
        None if no git repo or user chose not to create a branch (continue anyway)
        False if user explicitly cancelled due to uncommitted changes (don't continue)
    """
    from rich.prompt import IntPrompt

    path = Path(project_path)

    # Check if this is a git repository
    if not GitUtils.is_git_repository(path):
        return None

    msg = "Detected git repository"
    if project_name:
        msg = f"[{project_name}] {msg}"
    console_print(f"\n[cyan]✓[/cyan] {msg}")

    # Check for uncommitted changes before creating new branch
    if GitUtils.has_uncommitted_changes(path):
        msg = "Warning: You have uncommitted changes in the current branch"
        if project_name:
            msg = f"[{project_name}] {msg}"
        console_print(f"\n[yellow]⚠ {msg}[/yellow]")

        # Show status summary
        status_summary = GitUtils.get_status_summary(path)
        if status_summary:
            console_print("\n[dim]Uncommitted changes:[/dim]")
            for line in status_summary.split('\n'):
                console_print(f"  {line}")

        # Check if we should allow uncommitted changes
        if allow_uncommitted:
            msg = "Proceeding with uncommitted changes (--allow-uncommitted flag set)"
            if project_name:
                msg = f"[{project_name}] {msg}"
            console_print(f"\n[yellow]{msg}[/yellow]")
        elif is_json_mode() or auto_from_default or non_interactive:
            # In JSON mode, auto mode, or non-interactive mode
            mode_str = "JSON mode" if is_json_mode() else ("auto mode" if auto_from_default else "non-interactive mode")
            msg = f"Proceeding with branch creation despite uncommitted changes ({mode_str})"
            if project_name:
                msg = f"[{project_name}] {msg}"
            console_print(f"\n[yellow]{msg}[/yellow]")
        else:
            # Ask user if they want to continue
            console_print(
                "\n[dim]Creating a new branch with uncommitted changes may cause issues.\n"
                "Consider committing, stashing, or discarding your changes first.[/dim]"
            )

            prompt = "\nContinue anyway?"
            if project_name:
                prompt = f"\n[{project_name}] Continue anyway?"
            should_continue = Confirm.ask(prompt, default=False)
            if not should_continue:
                msg = "Branch creation cancelled"
                if project_name:
                    msg = f"[{project_name}] {msg}"
                console_print(f"\n[yellow]{msg}[/yellow]")
                console_print("[dim]Tip: Commit your changes with 'git commit' or stash them with 'git stash' before creating a new branch[/dim]")
                return False  # Explicit cancellation - don't continue

    # Load config if not provided
    if config is None:
        config_loader = ConfigLoader()
        config = config_loader.load_config()

    # Generate suggested branch name
    backend = detect_backend_from_key(issue_key, config)
    # Get use_issue_key_only setting with safe fallback
    use_issue_key_only = True  # Default value
    if config and hasattr(config, 'prompts') and config.prompts:
        use_issue_key_only = config.prompts.use_issue_key_as_branch
    suggested_branch = GitUtils.generate_branch_name(
        issue_key,
        goal,
        use_issue_key_only=use_issue_key_only,
        backend=backend
    )

    # Get smart default source branch
    default_source = _get_default_source_branch(path)

    # === STEP 1: Ask if user wants to create a branch ===
    if not auto_from_default and branch_name is None:
        # Determine if should create branch
        if create_branch is not None:
            # Explicit parameter provided
            should_create = create_branch
            if should_create:
                mode_msg = "Creating branch (--create-branch flag set)"
                if project_name:
                    mode_msg = f"[{project_name}] {mode_msg}"
                console_print(f"\n[dim]{mode_msg}[/dim]")
            else:
                mode_msg = "Skipping branch creation (--no-create-branch flag set)"
                if project_name:
                    mode_msg = f"[{project_name}] {mode_msg}"
                console_print(f"\n[dim]{mode_msg}[/dim]")
        elif is_json_mode() or non_interactive:
            # Non-interactive mode - default to creating branch
            should_create = True
            mode_str = "JSON mode" if is_json_mode() else "non-interactive mode"
            mode_msg = f"Creating branch by default ({mode_str})"
            if project_name:
                mode_msg = f"[{project_name}] {mode_msg}"
            console_print(f"\n[dim]{mode_msg}[/dim]")
        else:
            # Interactive mode - prompt user
            prompt_prefix = f"\n[{project_name}] " if project_name else "\n"
            should_create = Confirm.ask(f"{prompt_prefix}Would you like to create a new branch?", default=True)

        if not should_create:
            # User declined - offer to sync with upstream/main
            console_print("\n[dim]No new branch will be created.[/dim]")

            # Determine if should sync
            if sync_upstream is not None:
                should_sync = sync_upstream
                if should_sync:
                    sync_msg = "Syncing with upstream (--sync-upstream flag set)"
                    if project_name:
                        sync_msg = f"[{project_name}] {sync_msg}"
                    console_print(f"[dim]{sync_msg}[/dim]")
                else:
                    console_print("[dim]Skipping upstream sync (--no-sync-upstream flag set)[/dim]")
            elif non_interactive:
                # Non-interactive mode - default to syncing
                should_sync = True
                console_print("[dim]Syncing with upstream by default (non-interactive mode)[/dim]")
            else:
                # Interactive mode - prompt
                sync_prompt = f"Would you like to sync current branch with {default_source}?"
                if project_name:
                    sync_prompt = f"[{project_name}] {sync_prompt}"
                should_sync = Confirm.ask(sync_prompt, default=True)

            if should_sync:
                console_print(f"\nPulling latest changes from {default_source}...")

                # Fetch first
                console_print("[cyan]Fetching latest from remote...[/cyan]")
                GitUtils.fetch_origin(path)

                # Try to merge
                if GitUtils.merge_branch(path, default_source):
                    console_print(f"[green]✓[/green] Successfully synced with {default_source}")
                else:
                    console_print(f"[yellow]⚠[/yellow] Could not merge {default_source} automatically")

            return None  # No branch created, but that's OK

    # === STEP 2: Prompt for branch name (with suggestion) ===
    # Skip prompting if branch_name already provided (multi-project mode)
    if branch_name is None:
        console_print(f"\n[bold]Suggested branch name:[/bold] {suggested_branch}")

        if is_json_mode() or auto_from_default or non_interactive:
            branch_name = suggested_branch
            mode_str = "JSON mode" if is_json_mode() else ("auto mode" if auto_from_default else "non-interactive mode")
            console_print(f"[dim]Using suggested branch name ({mode_str})[/dim]")
        else:
            branch_name = Prompt.ask("Enter branch name", default=suggested_branch)

    # === STEP 3: Check if branch exists ===
    while True:
        if GitUtils.branch_exists(path, branch_name):
            # Branch exists - handle based on on_branch_exists parameter
            if on_branch_exists:
                # Parameter provided - use it
                if on_branch_exists == 'error':
                    msg = f"Branch '{branch_name}' already exists"
                    if project_name:
                        msg = f"[{project_name}] {msg}"
                    console.print(f"[red]✗[/red] {msg}")
                    console.print(f"[dim]Use --on-branch-exists={'{use-existing|add-suffix|skip}'} to handle automatically[/dim]")
                    if is_json_mode():
                        from devflow.cli.utils import output_json
                        output_json(success=False, error={"code": "BRANCH_EXISTS", "message": f"Branch {branch_name} already exists"})
                    return None
                elif on_branch_exists == 'use-existing':
                    msg = f"Using existing branch '{branch_name}' (--on-branch-exists=use-existing)"
                    if project_name:
                        msg = f"[{project_name}] {msg}"
                    console_print(f"[dim]{msg}[/dim]")
                    # Checkout the existing branch
                    if GitUtils.checkout_branch(path, branch_name):
                        return branch_name
                    else:
                        console.print(f"[red]✗[/red] Failed to checkout branch '{branch_name}'")
                        return None
                elif on_branch_exists == 'add-suffix':
                    # Add numeric suffix
                    original_name = branch_name
                    suffix = 2
                    while GitUtils.branch_exists(path, f"{original_name}-v{suffix}"):
                        suffix += 1
                    branch_name = f"{original_name}-v{suffix}"
                    msg = f"Branch '{original_name}' exists - using '{branch_name}' (--on-branch-exists=add-suffix)"
                    if project_name:
                        msg = f"[{project_name}] {msg}"
                    console_print(f"[dim]{msg}[/dim]")
                    # Continue to create the new branch
                    break
                elif on_branch_exists == 'skip':
                    msg = f"Branch '{branch_name}' exists - skipping branch creation (--on-branch-exists=skip)"
                    if project_name:
                        msg = f"[{project_name}] {msg}"
                    console_print(f"[dim]{msg}[/dim]")
                    return None
            elif non_interactive:
                # Non-interactive mode without explicit strategy - error
                msg = f"Branch '{branch_name}' already exists"
                if project_name:
                    msg = f"[{project_name}] {msg}"
                console.print(f"[red]✗[/red] {msg}")
                console.print(f"[dim]In non-interactive mode, use --on-branch-exists to specify behavior[/dim]")
                if is_json_mode():
                    from devflow.cli.utils import output_json
                    output_json(success=False, error={"code": "BRANCH_EXISTS", "message": "Branch exists, --on-branch-exists required in non-interactive mode"})
                return None
            else:
                # Interactive mode - use existing UX
                result = _handle_existing_branch(path, branch_name, default_source, config)

                if result is False:
                    # User chose "Choose different name" - prompt again
                    branch_prompt = "Enter branch name"
                    if project_name:
                        branch_prompt = f"[{project_name}] {branch_prompt}"
                    branch_name = Prompt.ask(branch_prompt)
                    continue  # Loop to check new name
                elif result is None:
                    # User cancelled
                    return None
                else:
                    # User switched to branch (with or without merge)
                    return result

        # Branch doesn't exist - break loop and create it
        break

    # === STEP 4: Prompt for source branch ===
    # Use provided source_branch if available (for multi-project sessions or --source-branch flag)
    if source_branch is None:
        if is_json_mode() or auto_from_default or non_interactive:
            source_branch = default_source
            mode_str = "JSON mode" if is_json_mode() else ("auto mode" if auto_from_default else "non-interactive mode")
            msg = f"Creating branch from: {source_branch} ({mode_str})"
            if project_name:
                msg = f"[{project_name}] {msg}"
            console_print(f"[dim]{msg}[/dim]")
        else:
            source_branch = _prompt_for_source_branch(path, default_source)

            if not source_branch:
                # User cancelled
                msg = "Branch creation cancelled"
                if project_name:
                    msg = f"[{project_name}] {msg}"
                console_print(f"[yellow]{msg}[/yellow]")
                return None
    else:
        # Source branch provided (multi-project mode or --source-branch flag) - use it
        msg = f"Creating branch from: {source_branch}"
        if project_name:
            msg = f"[{project_name}] {msg}"
        console_print(f"[dim]{msg}[/dim]")

    # === STEP 5: Create the branch from source ===
    try:
        msg = f"Creating branch '{branch_name}' from '{source_branch}'..."
        if project_name:
            msg = f"[{project_name}] {msg}"
        console_print(f"\n[cyan]{msg}[/cyan]")

        # Fetch latest to ensure we have up-to-date remote branches
        msg = "Fetching latest from remote..."
        if project_name:
            msg = f"[{project_name}] {msg}"
        console_print(f"[cyan]{msg}[/cyan]")
        GitUtils.fetch_origin(path)

        # Checkout source branch first
        current_branch = GitUtils.get_current_branch(path)
        if current_branch != source_branch:
            msg = f"Checking out {source_branch}..."
            if project_name:
                msg = f"[{project_name}] {msg}"
            console_print(f"[cyan]{msg}[/cyan]")
            if not GitUtils.checkout_branch(path, source_branch):
                msg = f"Failed to checkout {source_branch}"
                if project_name:
                    msg = f"[{project_name}] {msg}"
                console_print(f"[red]✗[/red] {msg}")
                return None

            # Pull latest if it's a tracking branch
            if '/' not in source_branch:  # Local branch
                msg = f"Pulling latest {source_branch}..."
                if project_name:
                    msg = f"[{project_name}] {msg}"
                console_print(f"[cyan]{msg}[/cyan]")
                GitUtils.pull_current_branch(path)

        # Create new branch
        if GitUtils.create_branch(path, branch_name):
            msg = f"Created and switched to branch: [bold]{branch_name}[/bold]"
            if project_name:
                msg = f"[{project_name}] {msg}"
            console_print(f"[green]✓[/green] {msg}")
            # Return both branch name and source branch for proper base_branch tracking
            return (branch_name, source_branch)
        else:
            msg = "Failed to create branch"
            if project_name:
                msg = f"[{project_name}] {msg}"
            console_print(f"[red]✗[/red] {msg}")
            return None

    except Exception as e:
        msg = f"Git operation failed: {e}"
        if project_name:
            msg = f"[{project_name}] {msg}"
        console.print(f"[red]✗[/red] {msg}")
        return None


def _display_session_banner(
    name: str,
    goal: Optional[str],
    working_directory: str,
    branch: str,
    project_path: str,
    ai_agent_session_id: str,
    issue_key: Optional[str] = None,
    jira_url: Optional[str] = None,
) -> None:
    """Display session context banner.

    Args:
        name: Session name
        goal: Session goal (optional)
        working_directory: Working directory name
        branch: Git branch name
        project_path: Project path
        ai_agent_session_id: Claude session UUID
        issue_key: Optional issue tracker key
        jira_url: Optional JIRA base URL from config
    """
    console.print("\n" + "━" * 60)
    display_title = f"{name} ({issue_key})" if issue_key else name
    console.print(f"📋 Session: {display_title}")
    if goal:
        console.print(f"🎯 Goal: {goal}")
    console.print(f"📁 Working Directory: {working_directory}")
    console.print(f"📂 Path: {project_path}")
    if branch:
        console.print(f"🌿 Branch: {branch}")
    console.print(f"🆔 Claude Session ID: {ai_agent_session_id}")
    if issue_key and jira_url:
        console.print(f"🔗 JIRA: {jira_url}/browse/{issue_key}")
    console.print("━" * 60 + "\n")
