r"""Agent skill directory mapping for multi-agent support.

This module provides directory mappings for installing skills to multiple AI agents.
It supports both global (user-level) and project-level skill installations.

Supported Agents and Directory Mappings:
---------------------------------------------
The directory paths and environment variable support for each agent are documented
in their official documentation. See the links below for the authoritative source:

1. Claude Code (Fully Tested)
   - Global: ~/.claude/skills/ (or $CLAUDE_CONFIG_DIR/skills/)
   - Project: <project>/.claude/skills/
   - Env var: CLAUDE_CONFIG_DIR (overrides ~/.claude/)
   - Docs: https://docs.claude.ai/docs/claude-code

2. GitHub Copilot (Experimental)
   - Global: ~/.copilot/skills/ (or $COPILOT_HOME/skills/)
   - Project: <project>/.github-copilot/skills/
   - Env var: COPILOT_HOME (overrides ~/.copilot/)
   - Docs: https://github.com/features/copilot

3. Cursor (Experimental)
   - Global: ~/.cursor/skills/
   - Project: <project>/.cursor/skills/
   - Env var: None (hardcoded path)
   - Docs: https://cursor.sh/

4. Windsurf (Experimental)
   - Global: ~/.codeium/windsurf/skills/ (Unix) or %APPDATA%\Codeium\Windsurf\skills\ (Windows)
   - Project: <project>/.windsurf/skills/
   - Env var: None (hardcoded path)
   - Docs: https://codeium.com/windsurf

5. Aider (Experimental)
   - Global: ~/.aider/skills/
   - Project: <project>/.aider/skills/
   - Env var: None (hardcoded path, AIDER_* env vars are for options only)
   - Docs: https://aider.chat/docs/

6. Continue (Experimental)
   - Global: ~/.continue/skills/
   - Project: <project>/.continue/skills/
   - Env var: None (hardcoded path)
   - Docs: https://continue.dev/docs

Note: Paths marked as "Experimental" are based on conventional patterns observed
in the wild but may not be officially supported by the agent. Always check the
official documentation before adding a new agent or updating paths.

When adding a new agent:
1. Check the official documentation for config directory location
2. Check if the agent supports an environment variable override
3. Add the agent to SUPPORTED_AGENTS constant
4. Implement the directory logic in get_agent_global_skills_dir()
5. Implement the project-level logic in get_agent_project_skills_dir()
6. Update validate_agent_names() if the agent has aliases
7. Update this docstring with documentation links
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_agent_global_skills_dir(agent: str) -> Path:
    """Get the global skills directory for a specific agent.

    Respects agent-specific environment variables where supported:
    - Claude Code: CLAUDE_CONFIG_DIR (defaults to ~/.claude/)
    - GitHub Copilot: COPILOT_HOME (defaults to ~/.copilot/)
    - Other agents: Use hardcoded defaults (no env var support)

    Args:
        agent: Agent name ('claude', 'cursor', 'windsurf', 'copilot', 'aider', 'continue')

    Returns:
        Path to agent's global skills directory

    Raises:
        ValueError: If agent name is not recognized
    """
    agent = agent.lower()

    if agent == 'claude':
        # Claude Code supports CLAUDE_CONFIG_DIR environment variable
        # Docs: https://docs.claude.ai/docs/claude-code
        # Default: ~/.claude/skills/ or $CLAUDE_CONFIG_DIR/skills/
        claude_config = os.environ.get('CLAUDE_CONFIG_DIR')
        if claude_config:
            base_dir = Path(claude_config).expanduser()
        else:
            base_dir = Path.home() / '.claude'
        return base_dir / 'skills'

    elif agent == 'copilot' or agent == 'github-copilot':
        # GitHub Copilot supports COPILOT_HOME environment variable
        # Docs: https://github.com/features/copilot
        # Default: ~/.copilot/skills/ or $COPILOT_HOME/skills/
        copilot_home = os.environ.get('COPILOT_HOME')
        if copilot_home:
            base_dir = Path(copilot_home).expanduser()
        else:
            base_dir = Path.home() / '.copilot'
        return base_dir / 'skills'

    elif agent == 'cursor':
        # Cursor: hardcoded to ~/.cursor/ (no env var support)
        # Docs: https://cursor.sh/
        # Path: ~/.cursor/skills/
        return Path.home() / '.cursor' / 'skills'

    elif agent == 'windsurf':
        # Windsurf: platform-specific paths (no env var support)
        # Docs: https://codeium.com/windsurf
        # Unix/Mac: ~/.codeium/windsurf/skills/
        # Windows: %APPDATA%\Codeium\Windsurf\skills\
        if sys.platform == 'win32':
            # Windows: %APPDATA%\Codeium\Windsurf\
            appdata = os.environ.get('APPDATA')
            if appdata:
                return Path(appdata) / 'Codeium' / 'Windsurf' / 'skills'
            else:
                # Fallback if APPDATA not set
                return Path.home() / 'AppData' / 'Roaming' / 'Codeium' / 'Windsurf' / 'skills'
        else:
            # Unix/Linux/Mac: ~/.codeium/windsurf/
            return Path.home() / '.codeium' / 'windsurf' / 'skills'

    elif agent == 'aider':
        # Aider: hardcoded to ~/.aider/ (no env var support for home dir)
        # Docs: https://aider.chat/docs/
        # Path: ~/.aider/skills/
        # Note: AIDER_* env vars are for command options, not config directory
        return Path.home() / '.aider' / 'skills'

    elif agent == 'continue':
        # Continue: hardcoded to ~/.continue/ (no env var support)
        # Docs: https://continue.dev/docs
        # Path: ~/.continue/skills/
        return Path.home() / '.continue' / 'skills'

    else:
        raise ValueError(
            f"Unknown agent: {agent}. "
            f"Supported: claude, copilot, cursor, windsurf, aider, continue"
        )


def get_agent_project_skills_dir(agent: str, project_path: Path) -> Path:
    """Get the project-level skills directory for a specific agent.

    Args:
        agent: Agent name ('claude', 'cursor', 'windsurf', 'copilot', 'aider', 'continue')
        project_path: Path to project directory

    Returns:
        Path to agent's project-level skills directory

    Raises:
        ValueError: If agent name is not recognized
    """
    agent = agent.lower()
    project_path = Path(project_path).resolve()

    if agent == 'claude':
        return project_path / '.claude' / 'skills'

    elif agent == 'copilot' or agent == 'github-copilot':
        return project_path / '.github-copilot' / 'skills'

    elif agent == 'cursor':
        return project_path / '.cursor' / 'skills'

    elif agent == 'windsurf':
        return project_path / '.windsurf' / 'skills'

    elif agent == 'aider':
        return project_path / '.aider' / 'skills'

    elif agent == 'continue':
        return project_path / '.continue' / 'skills'

    else:
        raise ValueError(
            f"Unknown agent: {agent}. "
            f"Supported: claude, copilot, cursor, windsurf, aider, continue"
        )


def get_skill_install_paths(
    agents: List[str],
    level: str = 'global',
    project_path: Optional[Path] = None
) -> List[Tuple[str, Path]]:
    """Get skill installation paths for specified agents and level.

    Args:
        agents: List of agent names (e.g., ['claude', 'cursor', 'windsurf'])
        level: Installation level - 'global', 'project', or 'both'
        project_path: Project directory path (required for 'project' and 'both' levels)

    Returns:
        List of (agent_name, install_path) tuples

    Raises:
        ValueError: If level is invalid or project_path is missing for project-level install

    Examples:
        >>> get_skill_install_paths(['claude', 'cursor'], level='global')
        [('claude', Path('~/.claude/skills')), ('cursor', Path('~/.cursor/skills'))]

        >>> get_skill_install_paths(['claude'], level='project', project_path=Path('/my/project'))
        [('claude', Path('/my/project/.claude/skills'))]

        >>> get_skill_install_paths(['claude'], level='both', project_path=Path('/my/project'))
        [('claude', Path('~/.claude/skills')), ('claude', Path('/my/project/.claude/skills'))]
    """
    if level not in ('global', 'project', 'both'):
        raise ValueError(f"Invalid level: {level}. Must be 'global', 'project', or 'both'")

    if level in ('project', 'both') and project_path is None:
        raise ValueError(f"project_path is required for level='{level}'")

    install_paths = []

    for agent in agents:
        if level == 'global':
            path = get_agent_global_skills_dir(agent)
            install_paths.append((agent, path))

        elif level == 'project':
            path = get_agent_project_skills_dir(agent, project_path)
            install_paths.append((agent, path))

        elif level == 'both':
            # Global first, then project
            global_path = get_agent_global_skills_dir(agent)
            install_paths.append((agent, global_path))

            project_skills_path = get_agent_project_skills_dir(agent, project_path)
            install_paths.append((agent, project_skills_path))

    return install_paths


# Supported agent names
SUPPORTED_AGENTS = ['claude', 'copilot', 'github-copilot', 'cursor', 'windsurf', 'aider', 'continue']


def validate_agent_names(agents: List[str]) -> List[str]:
    """Validate and normalize agent names.

    Args:
        agents: List of agent names to validate

    Returns:
        List of normalized agent names

    Raises:
        ValueError: If any agent name is not supported
    """
    normalized = []
    for agent in agents:
        agent_lower = agent.lower()

        # Normalize github-copilot to copilot
        if agent_lower == 'github-copilot':
            agent_lower = 'copilot'

        if agent_lower not in SUPPORTED_AGENTS and agent_lower != 'copilot':
            raise ValueError(
                f"Unsupported agent: {agent}. "
                f"Supported: {', '.join(SUPPORTED_AGENTS)}"
            )

        normalized.append(agent_lower)

    return normalized
