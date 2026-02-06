"""Command for daf investigate - create investigation-only session without ticket creation."""

import os
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm

from devflow.cli.utils import console_print, get_workspace_path, is_json_mode, output_json, require_outside_claude, should_launch_claude_code
from devflow.git.utils import GitUtils

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

    console_print(f"\n[yellow]Received signal {signum}, cleaning up...[/yellow]")

    if _cleanup_session and _cleanup_session_manager and _cleanup_name:
        console_print(f"[green]✓[/green] Claude session completed")

        # Reload index from disk
        _cleanup_session_manager.index = _cleanup_session_manager.config_loader.load_sessions()

        # Get current session
        current_session = _cleanup_session_manager.get_session(_cleanup_name)
        if not current_session:
            current_session = _cleanup_session

        # End work session
        try:
            _cleanup_session_manager.end_work_session(_cleanup_name)
        except ValueError as e:
            console_print(f"[yellow]⚠[/yellow] Could not end work session: {e}")

        console_print(f"[dim]Resume anytime with: daf open {_cleanup_name}[/dim]")

        # Save conversation file before cleaning up temp directory
        if current_session and current_session.active_conversation and current_session.active_conversation.temp_directory:
            from devflow.cli.commands.open_command import _copy_conversation_from_temp
            _copy_conversation_from_temp(current_session, current_session.active_conversation.temp_directory)

        # Clean up temporary directory if present
        if _cleanup_session.active_conversation and _cleanup_session.active_conversation.temp_directory:
            from devflow.utils.temp_directory import cleanup_temp_directory
            cleanup_temp_directory(_cleanup_session.active_conversation.temp_directory)

        # Prompt for complete on exit
        from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
        if current_session:
            _prompt_for_complete_on_exit(current_session, _cleanup_config)
        else:
            _prompt_for_complete_on_exit(_cleanup_session, _cleanup_config)

        # Mark cleanup as done
        _cleanup_done = True

    # Exit gracefully
    sys.exit(0)


def slugify_goal(goal: str) -> str:
    """Convert a goal string into a valid session name slug.

    Args:
        goal: The goal/description text

    Returns:
        Slugified name suitable for session identifier with random suffix
    """
    import re
    import secrets

    # Convert to lowercase
    slug = goal.lower()

    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)

    # Remove leading/trailing hyphens
    slug = slug.strip('-')

    # Limit length to 43 chars to leave room for random suffix
    if len(slug) > 43:
        slug = slug[:43].rstrip('-')

    # Add 6-character random suffix to prevent collisions
    random_suffix = secrets.token_hex(3)
    slug = f"{slug}-{random_suffix}"

    return slug


@require_outside_claude
def create_investigation_session(
    goal: str,
    parent: Optional[str] = None,
    name: Optional[str] = None,
    path: Optional[str] = None,
    workspace: Optional[str] = None,
) -> None:
    """Create a new investigation session for codebase analysis.

    This creates a session with session_type="investigation" which:
    - Skips branch creation automatically
    - Includes analysis-only instructions in the initial prompt
    - Does NOT expect ticket creation
    - Generates investigation report instead

    Args:
        goal: Goal/description for the investigation
        parent: Optional parent issue key (for tracking investigation under an epic)
        name: Optional session name (auto-generated from goal if not provided)
        path: Optional project path (bypasses interactive selection if provided)
        workspace: Optional workspace name (overrides session default and config default)
    """
    from devflow.session.manager import SessionManager
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console_print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        if is_json_mode():
            output_json(success=False, error={"message": "No configuration found", "code": "NO_CONFIG"})
        sys.exit(1)

    # Validate parent ticket if provided (for tracking purposes)
    from devflow.utils import is_mock_mode
    if parent and not is_mock_mode():
        console_print(f"[dim]Validating parent ticket: {parent}[/dim]")
        from devflow.jira.utils import validate_jira_ticket
        from devflow.jira import JiraClient

        try:
            jira_client = JiraClient()
            parent_ticket = validate_jira_ticket(parent, client=jira_client)

            if not parent_ticket:
                console_print(f"[red]✗[/red] Cannot proceed with invalid parent ticket")
                if is_json_mode():
                    output_json(
                        success=False,
                        error={
                            "code": "INVALID_PARENT",
                            "message": f"Parent ticket {parent} not found or validation failed"
                        }
                    )
                sys.exit(1)
        except Exception as e:
            console_print(f"[red]✗[/red] Failed to validate parent ticket: {e}")
            if is_json_mode():
                output_json(success=False, error={"message": f"Parent validation failed: {e}", "code": "VALIDATION_ERROR"})
            sys.exit(1)

        console_print(f"[green]✓[/green] Parent ticket validated: {parent}")

    # Auto-generate session name from goal if not provided
    if not name:
        name = slugify_goal(goal)
        console_print(f"[dim]Auto-generated session name: {name}[/dim]")

    # Determine project path
    selected_workspace_name = None
    if path is not None:
        # Use provided path
        project_path = str(Path(path).absolute())
        # Validate path exists
        if not Path(project_path).exists():
            console_print(f"[red]✗[/red] Directory does not exist: {project_path}")
            if is_json_mode():
                output_json(success=False, error={"message": f"Directory does not exist: {project_path}", "code": "INVALID_PATH"})
            sys.exit(1)
        console_print(f"[dim]Using specified path: {project_path}[/dim]")
    else:
        # Prompt for repository selection from workspace
        from devflow.cli.commands.jira_new_command import _prompt_for_repository_selection
        project_path, selected_workspace_name = _prompt_for_repository_selection(config, workspace_flag=workspace)
        if not project_path:
            # User cancelled or no workspace configured
            if is_json_mode():
                output_json(success=False, error={"message": "Repository selection cancelled or failed", "code": "NO_REPOSITORY"})
            sys.exit(1)

    working_directory = Path(project_path).name

    # Prompt to clone project in temporary directory for clean analysis
    # Skip in mock mode or JSON mode
    temp_directory = None
    original_project_path = None
    mock_mode = is_mock_mode()
    is_json = is_json_mode()

    # Skip temp directory prompt in non-interactive modes
    should_skip_temp_prompt = mock_mode or is_json

    if should_skip_temp_prompt:
        console_print(f"[dim]Non-interactive mode - skipping temp directory clone prompt[/dim]")
    else:
        from devflow.utils.temp_directory import should_clone_to_temp, prompt_and_clone_to_temp
        if should_clone_to_temp(Path(project_path)):
            temp_dir_result = prompt_and_clone_to_temp(Path(project_path))
            if temp_dir_result:
                temp_directory, original_project_path = temp_dir_result
                # Use temp directory as project_path for this session
                project_path = temp_directory
                # Use the original repository name for working_directory
                working_directory = Path(original_project_path).name
                console_print(f"[green]✓[/green] Using temporary clone: {temp_directory}")
            else:
                console_print(f"[dim]User declined temp clone or cloning failed - using current directory[/dim]")

    # Build the goal string for investigation
    if parent:
        full_goal = f"Investigate (under {parent}): {goal}"
    else:
        full_goal = f"Investigate: {goal}"

    # Create session with session_type="investigation"
    session_manager = SessionManager(config_loader=config_loader)

    session = session_manager.create_session(
        name=name,
        goal=full_goal,
        working_directory=working_directory,
        project_path=project_path,
        branch=None,  # No branch for investigation sessions
    )

    # Set session_type to "investigation"
    session.session_type = "investigation"
    # Set parent for tracking if provided
    if parent:
        session.issue_key = parent

    # AAP-64296: Store selected workspace in session
    if selected_workspace_name:
        session.workspace_name = selected_workspace_name

    session_manager.update_session(session)

    console_print(f"\n[green]✓[/green] Created session [cyan]{name}[/cyan] (session_type: [yellow]investigation[/yellow])")
    console_print(f"[dim]Goal: {full_goal}[/dim]")
    if parent:
        console_print(f"[dim]Tracking under: {parent}[/dim]")
    console_print(f"[dim]Working directory: {working_directory}[/dim]")
    console_print(f"[dim]No branch will be created (analysis-only mode)[/dim]\n")

    # In mock mode, simulate investigation without launching Claude
    if is_mock_mode():
        console_print("[yellow]📝 Mock mode: Simulating investigation session[/yellow]")
        console_print(f"[green]✓[/green] Investigation session created: [bold]{name}[/bold]")
        console_print(f"[dim]Reopen session with: daf open {name}[/dim]")

        if is_json_mode():
            from devflow.cli.utils import serialize_session
            output_json(
                success=True,
                data={
                    "session_name": name,
                    "session": serialize_session(session),
                    "goal": goal,
                    "parent": parent
                }
            )
        return

    # Check if we should launch Claude Code
    if not should_launch_claude_code(config=config, mock_mode=False):
        console_print("[yellow]⚠[/yellow] Session created but Claude Code not launched.")
        console_print(f"  Run [cyan]daf open {name}[/cyan] to start working on it.")
        return

    # Generate a new Claude session ID
    ai_agent_session_id = str(uuid.uuid4())

    # Update session with Claude session ID
    current_branch = GitUtils.get_current_branch(Path(temp_directory)) if temp_directory and GitUtils.is_git_repository(Path(temp_directory)) else None

    session.add_conversation(
        working_dir=working_directory,
        ai_agent_session_id=ai_agent_session_id,
        project_path=project_path,
        branch=current_branch,
        temp_directory=temp_directory,
        original_project_path=original_project_path,
        workspace=get_workspace_path(config, session.workspace_name) if session.workspace_name else config.repos.get_default_workspace_path(),
    )
    session.working_directory = working_directory

    # Start time tracking
    session_manager.start_work_session(name)

    session_manager.update_session(session)

    # Build initial prompt with investigation-only constraints
    # AAP-64886: Get workspace path from session instead of using default
    workspace = None
    if session.workspace_name and config and config.repos:
        workspace = get_workspace_path(config, session.workspace_name)
    elif config and config.repos:
        workspace = config.repos.get_default_workspace_path()
    initial_prompt = _build_investigation_prompt(goal, parent, config, name, project_path=project_path, workspace=workspace)

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

    # Set CS_SESSION_NAME environment variable
    env = os.environ.copy()
    env["CS_SESSION_NAME"] = name

    # Set GCP Vertex AI region if configured
    if config and config.gcp_vertex_region:
        env["CLOUD_ML_REGION"] = config.gcp_vertex_region

    # Launch Claude Code
    try:
        # Build command with all skills and context directories
        from devflow.utils.claude_commands import build_claude_command

        # AAP-64886: Get workspace path from session instead of using default
        workspace_path = None
        if session.workspace_name and config and config.repos:
            from devflow.cli.utils import get_workspace_path
            workspace_path = get_workspace_path(config, session.workspace_name)
        elif config and config.repos:
            workspace_path = config.repos.get_default_workspace_path()

        cmd = build_claude_command(
            session_id=ai_agent_session_id,
            initial_prompt=initial_prompt,
            project_path=project_path,
            workspace_path=workspace_path,
            config=config
        )

        # Debug output
        console_print(f"\n[dim]Debug - Command:[/dim]")
        console_print(f"[dim]  claude executable: {cmd[0]}[/dim]")
        console_print(f"[dim]  --session-id: {cmd[2]}[/dim]")
        console_print(f"[dim]  --add-dir flags: {len([x for x in cmd if x == '--add-dir'])}[/dim]")
        console_print(f"[dim]  Prompt (first 100 chars): {cmd[-1][:100]}...[/dim]")
        console_print(f"[dim]  Working directory: {project_path}[/dim]")
        console_print()

        subprocess.run(
            cmd,
            cwd=project_path,
            env=env,
            check=False
        )
    finally:
        if not _cleanup_done:
            console_print(f"\n[green]✓[/green] Claude session completed")

            # Reload index from disk
            session_manager.index = session_manager.config_loader.load_sessions()

            # Get current session
            current_session = session_manager.get_session(name)
            if not current_session:
                current_session = session

            # End work session
            try:
                session_manager.end_work_session(name)
            except ValueError as e:
                console_print(f"[yellow]⚠[/yellow] Could not end work session: {e}")

            console_print(f"[dim]Resume anytime with: daf open {name}[/dim]")

            # Save conversation file before cleanup
            if current_session and current_session.active_conversation and current_session.active_conversation.temp_directory:
                from devflow.cli.commands.open_command import _copy_conversation_from_temp
                _copy_conversation_from_temp(current_session, current_session.active_conversation.temp_directory)

            # Clean up temporary directory
            if temp_directory:
                from devflow.utils.temp_directory import cleanup_temp_directory
                cleanup_temp_directory(temp_directory)

            # Prompt for complete on exit
            from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
            if current_session:
                _prompt_for_complete_on_exit(current_session, config)
            else:
                _prompt_for_complete_on_exit(session, config)


def _load_hierarchical_context_files(config: Optional['Config']) -> list:
    """Load context files from hierarchical configuration.

    Returns list of (path, description) tuples for context files that EXIST.
    """
    from devflow.utils.paths import get_cs_home

    context_files = []
    cs_home = get_cs_home()

    # Backend context
    backend_path = cs_home / "backends" / "JIRA.md"
    if backend_path.exists() and backend_path.is_file():
        context_files.append((str(backend_path), "JIRA backend integration rules"))

    # Enterprise context
    enterprise_path = cs_home / "ENTERPRISE.md"
    if enterprise_path.exists() and enterprise_path.is_file():
        context_files.append((str(enterprise_path), "enterprise-wide policies and standards"))

    # Organization context
    org_path = cs_home / "ORGANIZATION.md"
    if org_path.exists() and org_path.is_file():
        context_files.append((str(org_path), "organization-wide policies and requirements"))

    # Team context
    team_path = cs_home / "TEAM.md"
    if team_path.exists() and team_path.is_file():
        context_files.append((str(team_path), "team conventions and workflows"))

    # User context
    user_path = cs_home / "USER.md"
    if user_path.exists() and user_path.is_file():
        context_files.append((str(user_path), "personal notes and preferences"))

    return context_files


def _discover_all_skills(project_path: Optional[str] = None, workspace: Optional[str] = None) -> list[tuple[str, str]]:
    """Discover all skills from user-level, workspace-level, hierarchical (DEVAIFLOW_HOME), and project-level locations.

    Discovery order (guarantees load order - generic skills before organization-specific extensions):
    1. User-level generic skills: ~/.claude/skills/ (alphabetical)
    2. Workspace-level skills: <workspace>/.claude/skills/ (alphabetical) - generic tool skills (daf-cli, gh-cli, etc.)
    3. Hierarchical skills: $DEVAIFLOW_HOME/.claude/skills/ (numbered: 01-enterprise, 02-organization, etc.) - extends generic skills
    4. Project-level skills: <project>/.claude/skills/ (alphabetical)

    Rationale: Hierarchical skills extend generic skills (see "Extends: daf-cli" in skill frontmatter),
    so generic skills must be loaded first.

    Args:
        project_path: Project directory path (for project-level skills)
        workspace: Workspace directory path (for workspace-level skills)

    Returns:
        List of tuples (skill_path, description) for all discovered skills in load order
    """
    discovered_skills = []

    def _scan_skill_dir(skill_file: Path, skill_dir_name: str) -> Optional[tuple[str, str]]:
        """Scan a single skill directory and extract description."""
        if not skill_file.exists():
            return None

        description = f"{skill_dir_name} skill"
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

        return (str(skill_file.resolve()), description)

    # 1. User-level skills: ~/.claude/skills/ (generic skills like daf-cli, git-cli)
    user_skills_dir = Path.home() / ".claude" / "skills"
    if user_skills_dir.exists():
        for skill_dir in sorted(user_skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                result = _scan_skill_dir(skill_file, skill_dir.name)
                if result:
                    discovered_skills.append(result)

    # 2. Workspace-level skills: <workspace>/.claude/skills/ (generic tool skills)
    if workspace:
        from devflow.utils.claude_commands import get_workspace_skills_dir
        workspace_skills_dir = get_workspace_skills_dir(workspace)
        if workspace_skills_dir.exists():
            for skill_dir in sorted(workspace_skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    result = _scan_skill_dir(skill_file, skill_dir.name)
                    if result:
                        discovered_skills.append(result)

    # 3. Hierarchical skills: $DEVAIFLOW_HOME/.claude/skills/ (organization-specific skills that extend generic ones)
    # These are numbered (01-enterprise, 02-organization, 03-team, 04-user) to guarantee order
    from devflow.utils.paths import get_cs_home
    cs_home = get_cs_home()
    hierarchical_skills_dir = cs_home / ".claude" / "skills"
    if hierarchical_skills_dir.exists():
        # Sort to ensure numbered order (01-, 02-, 03-, 04-)
        for skill_dir in sorted(hierarchical_skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                result = _scan_skill_dir(skill_file, skill_dir.name)
                if result:
                    discovered_skills.append(result)

    # 4. Project-level skills: <project>/.claude/skills/
    if project_path:
        project_skills_dir = Path(project_path) / ".claude" / "skills"
        if project_skills_dir.exists():
            for skill_dir in sorted(project_skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    result = _scan_skill_dir(skill_file, skill_dir.name)
                    if result:
                        discovered_skills.append(result)

    return discovered_skills


def _build_investigation_prompt(
    goal: str,
    parent: Optional[str],
    config,
    session_name: str,
    project_path: Optional[str] = None,
    workspace: Optional[str] = None,
) -> str:
    """Build the initial prompt for investigation sessions.

    Args:
        goal: Goal/description for the investigation
        parent: Parent issue key (optional, for tracking)
        config: Configuration object
        session_name: Name of the session
        project_path: Project path
        workspace: Workspace path

    Returns:
        Initial prompt string with investigation-focused instructions
    """
    # Build the "Work on" line
    if parent:
        work_on_line = f"Work on: Investigate (tracking under {parent}): {goal}"
    else:
        work_on_line = f"Work on: Investigate: {goal}"

    prompt_parts = [
        work_on_line,
        "",
    ]

    # Add context files section
    default_files = [
        ("AGENTS.md", "agent-specific instructions"),
        ("CLAUDE.md", "project guidelines and standards"),
        ("DAF_AGENTS.md", "daf tool usage guide"),
    ]

    # Load configured context files
    configured_files = []
    if config and config.context_files:
        configured_files = [(f.path, f.description) for f in config.context_files.files if not f.hidden]

    # Load hierarchical context files
    hierarchical_files = _load_hierarchical_context_files(config)

    # Discover skills
    skill_files = _discover_all_skills(project_path=project_path, workspace=workspace)

    # Combine regular context files
    regular_files = default_files + hierarchical_files + configured_files

    prompt_parts.append("Please start by reading the following context files if they exist:")
    for path, description in regular_files:
        prompt_parts.append(f"- {path} ({description})")

    # Add skill loading section
    if skill_files:
        prompt_parts.append("")
        prompt_parts.append("⚠️  CRITICAL: Read ALL of the following skill files before proceeding:")
        for path, description in skill_files:
            prompt_parts.append(f"- {path}")
        prompt_parts.append("")
        prompt_parts.append("These skills contain essential tool usage information and must be read completely.")

    prompt_parts.append("")

    # Add investigation instructions
    prompt_parts.extend([
        "⚠️  IMPORTANT CONSTRAINTS:",
        "   • This is an INVESTIGATION-ONLY session for codebase analysis",
        "   • DO NOT modify any code or create/checkout git branches",
        "   • DO NOT make any file changes - only READ and ANALYZE",
        "   • Focus on understanding the codebase and documenting findings",
        "",
        "Your task:",
        f"1. Investigate the codebase to understand: {goal}",
        "2. Read relevant files, search for patterns, understand the architecture",
        "3. Analyze feasibility and identify implementation approaches",
        "4. Generate a summary of your findings and recommendations",
        "5. Suggest whether this work should proceed and what approach to take",
        "6. If you discover bugs or improvements during investigation, you MAY create issue tracker tickets using 'daf jira create' commands",
        "",
        "When you're done investigating:",
        "- Provide a clear summary of what you discovered",
        "- List the key files and components involved",
        "- Suggest implementation approaches (if applicable)",
        "- Note any concerns or blockers",
        "- Create issue tracker tickets for any bugs or improvements discovered (if applicable)",
        "",
        "The user will save your findings using 'daf note' or export them.",
        "",
        "Remember: This is READ-ONLY investigation for code/git. Do not modify any files or branches.",
    ])

    return "\n".join(prompt_parts)
