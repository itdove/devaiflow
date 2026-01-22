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

from devflow.cli.utils import check_concurrent_session, console_print, get_status_display, is_json_mode, output_json as json_output, require_outside_claude, serialize_session, should_launch_claude_code
from devflow.config.loader import ConfigLoader
from devflow.git.utils import GitUtils
from devflow.jira import JiraClient
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError
from devflow.session.manager import SessionManager
from devflow.suggestions import RepositorySuggester

console = Console()

# Global variables for signal handler cleanup
_cleanup_session = None
_cleanup_session_manager = None
_cleanup_name = None
_cleanup_config = None
_cleanup_done = False


def _cleanup_on_signal(signum, frame):
    """Handle signals by performing cleanup before exit."""
    global _cleanup_done

    console.print(f"\n[yellow]Received signal {signum}, cleaning up...[/yellow]")

    if _cleanup_session and _cleanup_session_manager and _cleanup_name:
        try:
            console.print(f"[green]✓[/green] Claude session completed")

            # Update session status to paused
            # CRITICAL: Explicitly set status before calling update_session
            _cleanup_session.status = "paused"

            # Log the update for debugging
            from devflow.cli.commands.open_command import _log_error
            _log_error(f"Signal handler (new): Updating session {_cleanup_session.name} to paused status")

            # Update session (this now includes explicit fsync to prevent data loss)
            _cleanup_session_manager.update_session(_cleanup_session)

            # Verify the update was persisted (for debugging intermittent issues)
            _log_error(f"Signal handler (new): Session update completed for {_cleanup_session.name}")

            _cleanup_session_manager.end_work_session(_cleanup_name)
            console.print(f"[dim]Resume anytime with: daf open {_cleanup_name}[/dim]")

            # Call the complete prompt
            from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
            _prompt_for_complete_on_exit(_cleanup_session, _cleanup_config)

            # Mark cleanup as done so finally block doesn't repeat it
            _cleanup_done = True
        except Exception as e:
            console.print(f"[red]Error during cleanup: {e}[/red]")
            import traceback
            error_details = traceback.format_exc()
            console.print(f"[dim]{error_details}[/dim]")
            from devflow.cli.commands.open_command import _log_error
            _log_error(f"Signal handler (new) error: {e}\n{error_details}")

    # Exit gracefully
    sys.exit(0)


def _discover_all_skills(project_path: Optional[str] = None, workspace: Optional[str] = None) -> list[tuple[str, str]]:
    """Discover all skills from user-level, workspace-level, and project-level locations.

    Args:
        project_path: Project directory path (for project-level skills)
        workspace: Workspace directory path (for workspace-level skills)

    Returns:
        List of tuples (skill_path, description) for all discovered skills
    """
    discovered_skills = []

    # 1. User-level skills: ~/.claude/skills/
    user_skills_dir = Path.home() / ".claude" / "skills"
    if user_skills_dir.exists():
        for skill_dir in user_skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    description = f"{skill_dir.name} skill"
                    # Try to extract description from YAML frontmatter
                    try:
                        with open(skill_file, 'r') as f:
                            lines = f.readlines()
                            if lines and lines[0].strip() == '---':
                                for line in lines[1:]:
                                    if line.strip() == '---':
                                        break
                                    if line.startswith('description:'):
                                        description = line.split('description:', 1)[1].strip()
                                        break
                    except Exception:
                        pass
                    discovered_skills.append((str(skill_file.resolve()), description))

    # 2. Workspace-level skills: <workspace>/.claude/skills/
    if workspace:
        from devflow.utils.claude_commands import get_workspace_skills_dir
        workspace_skills_dir = get_workspace_skills_dir(workspace)
        if workspace_skills_dir.exists():
            for skill_dir in workspace_skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        description = f"{skill_dir.name} skill"
                        try:
                            with open(skill_file, 'r') as f:
                                lines = f.readlines()
                                if lines and lines[0].strip() == '---':
                                    for line in lines[1:]:
                                        if line.strip() == '---':
                                            break
                                        if line.startswith('description:'):
                                            description = line.split('description:', 1)[1].strip()
                                            break
                        except Exception:
                            pass
                        discovered_skills.append((str(skill_file.resolve()), description))

    # 3. Project-level skills: <project>/.claude/skills/
    if project_path:
        project_skills_dir = Path(project_path) / ".claude" / "skills"
        if project_skills_dir.exists():
            for skill_dir in project_skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        description = f"{skill_dir.name} skill"
                        try:
                            with open(skill_file, 'r') as f:
                                lines = f.readlines()
                                if lines and lines[0].strip() == '---':
                                    for line in lines[1:]:
                                        if line.strip() == '---':
                                            break
                                        if line.startswith('description:'):
                                            description = line.split('description:', 1)[1].strip()
                                            break
                        except Exception:
                            pass
                        discovered_skills.append((str(skill_file.resolve()), description))

    return discovered_skills


def _load_hierarchical_context_files(config: Optional['Config']) -> list:
    """Load context files from hierarchical configuration.

    Returns list of (path, description) tuples for context files that EXIST.

    Checks for context files from:
    - Backend: backends/JIRA.md
    - Organization: ORGANIZATION.md
    - Team: TEAM.md
    - User: CONFIG.md

    Only returns files that physically exist on disk.
    Paths are resolved relative to DEVAIFLOW_HOME.

    Args:
        config: Configuration object (may be None, not used currently but kept for future use)

    Returns:
        List of (absolute_path, description) tuples for existing files only
    """
    from devflow.utils.paths import get_cs_home

    context_files = []
    cs_home = get_cs_home()

    # Backend context (JIRA backend specific)
    backend_path = cs_home / "backends" / "JIRA.md"
    if backend_path.exists() and backend_path.is_file():
        # Use absolute path so Claude can read it with Read tool
        context_files.append((str(backend_path), "JIRA backend integration rules"))

    # Organization context
    org_path = cs_home / "ORGANIZATION.md"
    if org_path.exists() and org_path.is_file():
        context_files.append((str(org_path), "organization coding standards"))

    # Team context
    team_path = cs_home / "TEAM.md"
    if team_path.exists() and team_path.is_file():
        context_files.append((str(team_path), "team conventions and workflows"))

    # User context
    user_path = cs_home / "CONFIG.md"
    if user_path.exists() and user_path.is_file():
        context_files.append((str(user_path), "personal notes and preferences"))

    return context_files


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
) -> str:
    """Generate the initial prompt for Claude Code with context loading hints.

    The prompt includes:
    - A clear goal statement (if goal/JIRA provided)
    - Instructions to read AGENTS.md, CLAUDE.md, and DAF_AGENTS.md (always included)
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

    Returns:
        Formatted initial prompt for Claude Code

    Examples:
        Without goal or JIRA (exploratory session):
            "Please start by reading the following context files if they exist:
            - AGENTS.md (agent-specific instructions)
            - CLAUDE.md (project guidelines and standards)
            - DAF_AGENTS.md (daf tool usage guide)"

        With goal only:
            "Work on: backup-feature

            Please start by reading the following context files if they exist:
            - AGENTS.md (agent-specific instructions)
            - CLAUDE.md (project guidelines and standards)
            - DAF_AGENTS.md (daf tool usage guide)"

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
    default_files = [
        ("AGENTS.md", "agent-specific instructions"),
        ("CLAUDE.md", "project guidelines and standards"),
        ("DAF_AGENTS.md", "daf tool usage guide"),
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
    hierarchical_files = _load_hierarchical_context_files(config)

    # Discover skills from filesystem (instead of loading from config)
    # This ensures we only reference skills that actually exist on disk
    skill_files = _discover_all_skills(project_path=project_path, workspace=workspace)

    # Combine regular context files: defaults + hierarchical + configured (no skills from config)
    regular_files = default_files + hierarchical_files + configured_files

    # Add context loading instructions
    prompt += "Please start by reading the following context files if they exist:\n"
    for path, description in regular_files:
        prompt += f"- {path} ({description})\n"

    # Add explicit skill loading section if skills are present
    if skill_files:
        prompt += "\n⚠️  CRITICAL: Read ALL of the following skill files before proceeding:\n"
        for path, description in skill_files:
            prompt += f"- {path}\n"
        prompt += "\nThese skills contain essential tool usage information and must be read completely.\n"

    # Add JIRA reading instruction using daf jira view command
    if issue_key:
        prompt += f"\nAlso read the issue tracker ticket:\n"
        prompt += f"daf jira view {issue_key}\n"

    # Add multi-project scope constraints if this session has multiple conversations
    if other_projects and current_project:
        prompt += f"\n⚠️  MULTI-PROJECT SESSION SCOPE:\n"
        prompt += f"   • This session works across {len(other_projects) + 1} different projects\n"
        prompt += f"   • YOU ARE CURRENTLY IN: {current_project}\n"
        prompt += f"   • Other projects in this session: {', '.join(other_projects)}\n"
        prompt += f"\n   🚨 CRITICAL: Only make changes in the '{current_project}' project!\n"
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
    force_new_session: bool = False,
    output_json: bool = False,
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
        force_new_session: If True, always create new session instead of adding conversation
        output_json: If True, output JSON instead of human-readable text
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

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

    # Determine project path
    if path is None:
        # Check if current directory is a git repository (indicates it's a project)
        current_dir = Path.cwd()
        is_current_dir_a_project = GitUtils.is_git_repository(current_dir)

        # Always offer intelligent repository suggestions (with or without JIRA)
        suggested_path = _suggest_and_select_repository(
            config_loader,
            issue_metadata_dict=issue_metadata_dict,
            issue_key=issue_key,
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

    # Auto-create template if enabled and no template was used
    config = config_loader.load_config()

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
    if not check_concurrent_session(session_manager, project_path, name, action="create"):
        return

    # Handle git branch creation if this is a git repository
    if branch is None:
        # Use issue_key if available, otherwise use name for branch creation
        branch_identifier = issue_key if issue_key else name
        branch = _handle_branch_creation(project_path, branch_identifier, goal)

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
                return

            # Add conversation to existing session
            console.print(f"\n[cyan]Adding conversation to existing session: {name}[/cyan]")
            config = config_loader.load_config()
            workspace = config.repos.workspace if config else None

            session.add_conversation(
                working_dir=working_directory,
                ai_agent_session_id=session_id,
                project_path=project_path,
                branch=branch or "",  # branch is required, use empty string if None
                workspace=workspace,
            )
            session.working_directory = working_directory
            session_manager.update_session(session)
        else:
            # Multiple sessions exist - prompt user to select one or create new
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

            new_option = len(existing_sessions) + 1
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
                    return

                console.print(f"\n[cyan]Adding conversation to session [/cyan]")
                config = config_loader.load_config()
                workspace = config.repos.workspace if config else None

                session.add_conversation(
                    working_dir=working_directory,
                    ai_agent_session_id=session_id,
                    project_path=project_path,
                    branch=branch or "",  # branch is required, use empty string if None
                    workspace=workspace,
                )
                session.working_directory = working_directory
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
        )

    # Populate JIRA metadata if available
    if issue_metadata_dict:
        if not session.issue_metadata:
            session.issue_metadata = {}
        session.issue_metadata["summary"] = issue_metadata_dict.get("summary")
        session.issue_metadata["type"] = issue_metadata_dict.get("type")
        session.issue_metadata["status"] = issue_metadata_dict.get("status")
        session.issue_metadata["sprint"] = issue_metadata_dict.get("sprint")
        session.issue_metadata["points"] = issue_metadata_dict.get("points")
        session.issue_metadata["assignee"] = issue_metadata_dict.get("assignee")
        session.issue_metadata["epic"] = issue_metadata_dict.get("epic")
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
        workspace = config.repos.workspace if config and config.repos else None
        initial_prompt = _generate_initial_prompt(
            name, session.goal, issue_key, issue_title,
            project_path=project_path, workspace=workspace
        )

        # Build the claude command with session ID and enhanced prompt
        # Prompt must come BEFORE --add-dir flags (positional argument)
        cmd = ["claude", "--session-id", session_id, initial_prompt]

        # Add all skills directories to allowed paths (auto-approve skill file reads)
        # Skills can be in 3 locations: user-level, workspace-level, project-level
        skills_dirs = []

        # 1. User-level skills: ~/.claude/skills/
        user_skills = Path.home() / ".claude" / "skills"
        if user_skills.exists():
            skills_dirs.append(str(user_skills))

        # 2. Workspace-level skills: <workspace>/.claude/skills/
        if config and config.repos and config.repos.workspace:
            from devflow.utils.claude_commands import get_workspace_skills_dir
            workspace_skills = get_workspace_skills_dir(config.repos.workspace)
            if workspace_skills.exists():
                skills_dirs.append(str(workspace_skills))

        # 3. Project-level skills: <project>/.claude/skills/
        project_skills = Path(project_path) / ".claude" / "skills"
        if project_skills.exists():
            skills_dirs.append(str(project_skills))

        # Add all discovered skills directories AFTER the prompt
        for skills_dir in skills_dirs:
            cmd.extend(["--add-dir", skills_dir])

        # Set environment variables for the AI agent process
        # DEVAIFLOW_IN_SESSION: Flag to indicate we're inside an AI session (used by safety guards)
        # AI_AGENT_SESSION_ID: Generic session ID (works with any AI agent)
        env = os.environ.copy()
        env["DEVAIFLOW_IN_SESSION"] = "1"
        env["AI_AGENT_SESSION_ID"] = session_id

        # Set GCP Vertex AI region if configured
        if config and config.gcp_vertex_region:
            env["CLOUD_ML_REGION"] = config.gcp_vertex_region

        # Set up signal handlers for cleanup
        global _cleanup_session, _cleanup_session_manager, _cleanup_name, _cleanup_config, _cleanup_done
        _cleanup_session = session
        _cleanup_session_manager = session_manager
        _cleanup_name = name
        _cleanup_config = config

        # Register signal handlers for graceful shutdown
        # SIGTERM is not available on Windows, use SIGBREAK instead
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, _cleanup_on_signal)
        else:
            signal.signal(signal.SIGBREAK, _cleanup_on_signal)
        signal.signal(signal.SIGINT, _cleanup_on_signal)

        # Execute claude in the project directory with the environment
        try:
            subprocess.run(cmd, cwd=project_path, env=env)
        finally:
            if not _cleanup_done:
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
        workspace = config.repos.workspace if config and config.repos else None
        initial_prompt = _generate_initial_prompt(name, session.goal, issue_key, issue_title,
                                                   project_path=project_path, workspace=workspace)
        console.print(f"  claude --session-id {session_id} \"{initial_prompt}\"")


def _suggest_and_select_repository(
    config_loader: ConfigLoader,
    issue_metadata_dict: Optional[dict] = None,
    issue_key: Optional[str] = None,
) -> Optional[str]:
    """Suggest repositories based on issue tracker ticket and let user select.

    Args:
        config_loader: ConfigLoader instance
        issue_metadata_dict: issue tracker ticket metadata (if available)
        issue_key: issue tracker key (if available)

    Returns:
        Selected repository path or None if user cancelled
    """
    config = config_loader.load_config()

    # Get available repositories from workspace
    available_repos = []
    workspace_path = None
    if config and config.repos:
        workspace_path = Path(config.repos.workspace).expanduser()
        if workspace_path.exists() and workspace_path.is_dir():
            try:
                directories = [d for d in workspace_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
                available_repos = sorted([d.name for d in directories])
            except Exception as e:
                console.print(f"[yellow]Warning: Could not scan workspace: {e}[/yellow]")

    if not available_repos:
        # No workspace configured or no repos found
        return None

    # Check if we have a remembered repository for this JIRA project
    if config and config.prompts and issue_key:
        project_key = issue_key.split('-')[0] if '-' in issue_key else None
        if project_key and config.prompts.remember_last_repo_per_project:
            remembered_repo = config.prompts.remember_last_repo_per_project.get(project_key)
            if remembered_repo and remembered_repo in available_repos:
                console.print(f"\n[cyan]Using remembered repository for {project_key}: {remembered_repo}[/cyan]")
                console.print("[dim]Run [cyan]daf config unset-prompts --all[/cyan] to clear remembered repos[/dim]")
                if workspace_path:
                    selected_path = str(workspace_path / remembered_repo)
                    # Still record selection for learning
                    if issue_metadata_dict:
                        suggester = RepositorySuggester()
                        suggester.record_selection(
                            repository=remembered_repo,
                            issue_key=issue_key,
                            ticket_type=issue_metadata_dict.get("type"),
                            summary=issue_metadata_dict.get("summary", ""),
                            description=issue_metadata_dict.get("description"),
                            labels=issue_metadata_dict.get("labels", []),
                        )
                    return selected_path

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
    console.print(f"  • Enter 'cancel' to use current directory")

    selection = Prompt.ask("Selection")

    # Validate input is not empty
    if not selection or selection.strip() == "":
        console.print(f"[red]✗[/red] Empty selection not allowed. Please enter a number (1-{len(available_repos)}), repository name, path, or 'cancel'")
        return None

    # Handle cancel
    if selection.lower() == "cancel":
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

                # Remember this repository for the JIRA project
                if issue_key and config:
                    project_key = issue_key.split('-')[0] if '-' in issue_key else None
                    if project_key:
                        config.prompts.remember_last_repo_per_project[project_key] = repo_name
                        config_loader.save_config(config)
                        console.print(f"[dim]Remembered {repo_name} for {project_key} tickets[/dim]")

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

            return str(project_path)
        else:
            console.print(f"[red]✗[/red] No workspace configured in config")
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
    config: Optional[any] = None
) -> Optional[str]:
    """Handle git branch creation if in a git repository.

    Args:
        project_path: Project directory path
        issue_key: issue tracker key
        goal: Session goal (optional)
        auto_from_default: If True, automatically create branch from default branch
            with latest changes (used by daf open). If False, prompt user for strategy
            (used by daf new).
        config: Configuration object (optional, will load if not provided)

    Returns:
        Branch name if created/exists, None otherwise
    """
    path = Path(project_path)

    # Check if this is a git repository
    if not GitUtils.is_git_repository(path):
        return None

    console_print("\n[cyan]✓[/cyan] Detected git repository")

    # Load config if not provided
    if config is None:
        config_loader = ConfigLoader()
        config = config_loader.load_config()

    # Ask if user wants to create a branch (unless auto mode or JSON mode)
    if not auto_from_default:
        # In JSON mode, use default value (True) without prompting
        if is_json_mode():
            # Default to creating branch in JSON mode
            should_create = True
        else:
            should_create = Confirm.ask("Create git branch for this session?", default=True)

        if not should_create:
            return None

    # Generate default branch name
    suggested_branch = GitUtils.generate_branch_name(issue_key, goal)
    console_print(f"\n[dim]Suggested branch name: {suggested_branch}[/dim]")

    # Check if suggested branch already exists
    if GitUtils.branch_exists(path, suggested_branch):
        console_print(f"\n[yellow]⚠ Branch '{suggested_branch}' already exists[/yellow]")

        # Handle branch conflict
        branch_name = _handle_branch_conflict(path, suggested_branch)
        if not branch_name:
            # User chose to skip or cancel
            return None
    else:
        branch_name = suggested_branch

    # Determine strategy
    if auto_from_default:
        # Auto mode: always create from default branch with latest changes
        strategy = "2"
        console.print("[cyan]Creating branch from default branch (with latest changes)...[/cyan]")
    else:
        # Check if default_branch_strategy is configured in prompts
        if config and config.prompts and config.prompts.default_branch_strategy:
            # Use configured strategy
            if config.prompts.default_branch_strategy == "from_default":
                strategy = "2"
                console.print("[cyan]Using configured strategy: from default branch[/cyan]")
            else:  # "from_current"
                strategy = "1"
                console.print("[cyan]Using configured strategy: from current branch[/cyan]")
        else:
            # Interactive mode: ask for branch creation strategy
            # In JSON mode, use default strategy (option 2) without prompting
            if is_json_mode():
                strategy = "2"  # Default to from default branch
            else:
                console.print("\n[bold]Branch creation strategy:[/bold]")
                console.print("1. From current state (stay on current branch)")
                console.print("2. From default branch (checkout main/master first)")
                strategy = Prompt.ask("Select", choices=["1", "2"], default="2")

    try:
        # If user chose to use existing branch, just checkout to it
        if branch_name == suggested_branch and GitUtils.branch_exists(path, branch_name):
            # Branch exists and user wants to use it
            console.print(f"\n[cyan]Switching to existing branch: {branch_name}...[/cyan]")
            if GitUtils.checkout_branch(path, branch_name):
                console.print(f"[green]✓[/green] Switched to branch: [bold]{branch_name}[/bold]")
                return branch_name
            else:
                console.print(f"[red]✗[/red] Failed to checkout branch")
                return None

        # Otherwise, create new branch
        if strategy == "2":
            # Strategy: From default branch (fresh start)
            console.print("\n[cyan]Fetching latest from origin...[/cyan]")
            GitUtils.fetch_origin(path)

            default_branch = GitUtils.get_default_branch(path)
            if default_branch:
                console.print(f"[cyan]Checking out {default_branch}...[/cyan]")
                if GitUtils.checkout_branch(path, default_branch):
                    console.print(f"[cyan]Pulling latest {default_branch}...[/cyan]")
                    GitUtils.pull_current_branch(path)
            else:
                console.print("[yellow]Warning: Could not determine default branch[/yellow]")

        # Create and checkout the new branch
        console.print(f"\n[cyan]Creating branch: {branch_name}...[/cyan]")
        if GitUtils.create_branch(path, branch_name):
            console.print(f"[green]✓[/green] Created and switched to branch: [bold]{branch_name}[/bold]")
            return branch_name
        else:
            console.print(f"[red]✗[/red] Failed to create branch")
            return None

    except Exception as e:
        console.print(f"[red]✗[/red] Git operation failed: {e}")
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
