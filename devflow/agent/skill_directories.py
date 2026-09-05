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

7. OpenCode (Experimental)
   - Global: ~/.config/opencode/skills/ (or $XDG_CONFIG_HOME/opencode/skills/)
   - Project: <project>/.opencode/skills/
   - Env var: XDG_CONFIG_HOME (standard XDG override)
   - Docs: https://opencode.ai/docs

8. Codex (Experimental)
   - Global: ~/.codex/skills/ (or $CODEX_HOME/skills/ or
     $XDG_CONFIG_HOME/codex/skills/)
   - Project: <project>/.codex/skills/
   - Env vars: CODEX_HOME, XDG_CONFIG_HOME
   - Docs: https://github.com/openai/codex

9. Crush (Experimental)
   - Global: ~/.local/share/crush/skills/ (or
     $XDG_DATA_HOME/crush/skills/)
   - Project: <project>/.crush/skills/
   - Env var: XDG_DATA_HOME
   - Docs: https://crush.ai/

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
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple


def get_agent_global_skills_dir(agent: str) -> Path:
    """Get the global skills directory for a specific agent.

    Respects agent-specific environment variables where supported:
    - Claude Code: CLAUDE_CONFIG_DIR (defaults to ~/.claude/)
    - GitHub Copilot: COPILOT_HOME (defaults to ~/.copilot/)
    - Codex: CODEX_HOME, then XDG_CONFIG_HOME (defaults to ~/.codex/)
    - OpenCode: XDG_CONFIG_HOME (defaults to ~/.config/)
    - Crush: XDG_DATA_HOME (defaults to ~/.local/share/)
    - Other agents: Use their documented default directories

    Args:
        agent: Agent name (for example, 'claude', 'codex', or 'cursor')

    Returns:
        Path to agent's global skills directory

    Raises:
        ValueError: If agent name is not recognized
    """
    agent = agent.lower()
    if agent in ('github-copilot', 'github_copilot'):
        agent = 'copilot'
    elif agent in ('opencode-ai', 'opencode_ai'):
        agent = 'opencode'

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

    elif agent == 'opencode':
        # OpenCode: follows XDG spec
        # Docs: https://opencode.ai/docs
        # Default: ~/.config/opencode/skills/ or $XDG_CONFIG_HOME/opencode/skills/
        xdg_config = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config:
            base_dir = Path(xdg_config).expanduser() / 'opencode'
        else:
            base_dir = Path.home() / '.config' / 'opencode'
        return base_dir / 'skills'

    elif agent == 'codex':
        # Codex follows CODEX_HOME, then the XDG config directory, then ~/.codex.
        # This mirrors CodexAgent's storage resolution.
        codex_home = os.environ.get('CODEX_HOME')
        if codex_home:
            base_dir = Path(codex_home).expanduser()
        elif os.environ.get('XDG_CONFIG_HOME'):
            base_dir = Path(os.environ['XDG_CONFIG_HOME']).expanduser() / 'codex'
        else:
            base_dir = Path.home() / '.codex'
        return base_dir / 'skills'

    elif agent == 'crush':
        # Crush follows the XDG data directory for its global data.
        xdg_data = os.environ.get('XDG_DATA_HOME')
        if xdg_data:
            base_dir = Path(xdg_data).expanduser() / 'crush'
        else:
            base_dir = Path.home() / '.local' / 'share' / 'crush'
        return base_dir / 'skills'

    else:
        raise ValueError(
            f"Unknown agent: {agent}. "
            f"Supported: {', '.join(SUPPORTED_AGENTS)}"
        )


def get_agent_project_skills_dir(agent: str, project_path: Path) -> Path:
    """Get the project-level skills directory for a specific agent.

    Args:
        agent: Agent name (for example, 'claude', 'codex', or 'cursor')
        project_path: Path to project directory

    Returns:
        Path to agent's project-level skills directory

    Raises:
        ValueError: If agent name is not recognized
    """
    agent = agent.lower()
    if agent in ('github-copilot', 'github_copilot'):
        agent = 'copilot'
    elif agent in ('opencode-ai', 'opencode_ai'):
        agent = 'opencode'
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

    elif agent == 'opencode':
        return project_path / '.opencode' / 'skills'

    elif agent == 'codex':
        return project_path / '.codex' / 'skills'

    elif agent == 'crush':
        return project_path / '.crush' / 'skills'

    else:
        raise ValueError(
            f"Unknown agent: {agent}. "
            f"Supported: {', '.join(SUPPORTED_AGENTS)}"
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


# Supported agent names. ``github-copilot`` is retained as a user-facing alias
# for compatibility; the normalized skill directory name is ``copilot``.
SUPPORTED_AGENTS = [
    'claude',
    'copilot',
    'github-copilot',
    'cursor',
    'windsurf',
    'aider',
    'continue',
    'opencode',
    'codex',
    'crush',
]

_CANONICAL_SKILL_AGENTS = [
    'claude', 'copilot', 'cursor', 'windsurf', 'aider', 'continue',
    'opencode', 'codex', 'crush',
]

# Only agents with a unique command are detected from PATH. Copilot and Continue
# both use the ``code`` command, so detecting it would incorrectly enable both.
_AGENT_CLI_COMMANDS = {
    'claude': 'claude',
    'cursor': 'cursor',
    'windsurf': 'windsurf',
    'aider': 'aider',
    'opencode': 'opencode',
    'codex': 'codex',
    'crush': 'crush',
}

_AGENT_HOME_ENV_VARS = {
    'claude': 'CLAUDE_CONFIG_DIR',
    'copilot': 'COPILOT_HOME',
    'codex': 'CODEX_HOME',
}


def _normalize_detection_agent(agent: Any) -> Optional[str]:
    """Return the canonical skill agent name for a configured backend."""
    if not agent:
        return None

    normalized = str(agent).strip().lower()
    normalized = {
        'github-copilot': 'copilot',
        'github_copilot': 'copilot',
        'opencode-ai': 'opencode',
        'opencode_ai': 'opencode',
        'anthropic': 'claude',
        # Ollama's supported adapter uses Claude Code, so its skills live there.
        'ollama': 'claude',
        'ollama-claude': 'claude',
    }.get(normalized, normalized)

    return normalized if normalized in _CANONICAL_SKILL_AGENTS else None


def get_agent_config_dir(agent: str) -> Path:
    """Return the global configuration/data directory for a skill agent."""
    normalized = _normalize_detection_agent(agent)
    if normalized is None:
        raise ValueError(f"Unknown agent: {agent}")

    skills_dir = get_agent_global_skills_dir(normalized)
    return skills_dir.parent


def _agent_detection_paths(agent: str) -> Iterable[Path]:
    """Yield known global paths that indicate an agent is configured."""
    normalized = _normalize_detection_agent(agent)
    if normalized is None:
        return

    yield get_agent_config_dir(normalized)

    # Windsurf stores agent data under ~/.windsurf while its skills path is
    # under ~/.codeium/windsurf. Accept both locations as configuration signals.
    if normalized == 'windsurf':
        yield Path.home() / '.windsurf'

    # Crush keeps runtime data under XDG_DATA_HOME, but its user config is
    # conventionally stored under XDG_CONFIG_HOME. Either location indicates
    # that Crush has been configured.
    if normalized == 'crush':
        xdg_config = os.environ.get('XDG_CONFIG_HOME')
        config_home = (
            Path(xdg_config).expanduser()
            if xdg_config
            else Path.home() / '.config'
        )
        yield config_home / 'crush'


def is_agent_configured(agent: str, check_cli: bool = True) -> bool:
    """Check whether an agent has a known configuration, home, or CLI signal.

    Args:
        agent: Agent name or supported alias.
        check_cli: Also consider a uniquely identifying executable on ``PATH``.

    Returns:
        ``True`` when the agent appears configured or installed.
    """
    normalized = _normalize_detection_agent(agent)
    if normalized is None:
        return False

    env_var = _AGENT_HOME_ENV_VARS.get(normalized)
    if env_var and os.environ.get(env_var):
        return True

    if any(path.exists() for path in _agent_detection_paths(normalized)):
        return True

    cli_command = _AGENT_CLI_COMMANDS.get(normalized)
    return bool(check_cli and cli_command and shutil.which(cli_command))


def _config_value(value: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a Pydantic/object config or a mapping."""
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _config_field_is_explicit(value: Any, key: str) -> bool:
    """Tell whether a config field was supplied instead of defaulted."""
    if isinstance(value, dict):
        return key in value

    fields_set = getattr(value, 'model_fields_set', None)
    if fields_set is None:
        fields_set = getattr(value, '__fields_set__', None)
    # SimpleNamespace and other lightweight test/config objects do not track
    # field provenance; treat their attributes as explicit for compatibility.
    return fields_set is None or key in fields_set


def _configured_agents_from_config(config: Any) -> List[str]:
    """Extract agent signals from a loaded DevAIFlow configuration."""
    if config is None:
        return []

    configured: List[str] = []
    agent_config = _config_value(config, 'agent')
    enabled_agents = _config_value(agent_config, 'enabled_agents', [])
    if _config_field_is_explicit(agent_config, 'enabled_agents'):
        if isinstance(enabled_agents, str):
            enabled_agents = [enabled_agents]
        elif not isinstance(enabled_agents, (list, tuple, set)):
            enabled_agents = []
        configured.extend(enabled_agents or [])

    configured.extend([
        _config_value(config, 'agent_backend'),
    ])

    model_provider = _config_value(config, 'model_provider')
    profiles = _config_value(model_provider, 'profiles') if model_provider else None
    if isinstance(profiles, dict):
        # Use the same provider-to-adapter inference as session launch, while
        # keeping this module independent from the Pydantic config models.
        from devflow.utils.model_provider import get_agent_backend_from_profile

        for profile in profiles.values():
            configured.append(get_agent_backend_from_profile(profile))

    agents: List[str] = []
    for agent in configured:
        normalized = _normalize_detection_agent(agent)
        if normalized and normalized not in agents:
            agents.append(normalized)
    return agents


def detect_configured_agents(config: Any = None, check_cli: bool = True) -> List[str]:
    """Detect the supported agents that should receive bundled skills.

    Detection combines explicit DevAIFlow configuration with known agent home
    directories/environment variables and unique agent CLIs. Claude is always
    returned as the compatibility fallback when no other signal is found.

    Args:
        config: Optional loaded DevAIFlow ``Config`` object.
        check_cli: Whether unique agent executables on ``PATH`` count as signals.

    Returns:
        Canonical agent names without aliases or duplicates.
    """
    configured = set(_configured_agents_from_config(config))
    configured.update(
        agent for agent in _CANONICAL_SKILL_AGENTS
        if is_agent_configured(agent, check_cli=check_cli)
    )

    if not configured:
        return ['claude']

    # Keep output stable for predictable installation and user-facing messages.
    return [agent for agent in _CANONICAL_SKILL_AGENTS if agent in configured]


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

        # Normalize aliases
        if agent_lower in ('github-copilot', 'github_copilot'):
            agent_lower = 'copilot'
        elif agent_lower in ('opencode-ai', 'opencode_ai'):
            agent_lower = 'opencode'

        if agent_lower not in SUPPORTED_AGENTS and agent_lower != 'copilot':
            raise ValueError(
                f"Unsupported agent: {agent}. "
                f"Supported: {', '.join(SUPPORTED_AGENTS)}"
            )

        normalized.append(agent_lower)

    return normalized
