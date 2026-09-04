"""Utilities for managing model provider configuration and profiles.

This module provides functions to get active model provider profiles from configuration
and build environment variables for launching Claude Code with alternative AI providers.
"""

import os
import re
from typing import Dict, Optional, Any

import click


UTILITY_COMMANDS = {"commit_message", "pr_template"}
LOCAL_PROVIDERS = {"llama.cpp", "llama-cpp", "llamacpp", "ollama", "mlx", "mlx-lm"}
CLAUDE_PROFILE_PROVIDERS = {
    "anthropic",
    "vertex",
    "openrouter",
    "custom",
    "llama.cpp",
    "llama-cpp",
    "llamacpp",
    "mlx",
    "mlx-lm",
}


class ModelProviderCompatibilityError(ValueError, click.ClickException):
    """Raised when a selected profile cannot be used by an agent adapter."""

    def __init__(self, message: str):
        ValueError.__init__(self, message)
        click.ClickException.__init__(self, message)


def _profile_to_dict(profile: Any) -> Optional[Dict[str, Any]]:
    """Return a provider profile as a mutable dictionary."""
    if profile is None:
        return None
    if hasattr(profile, "model_dump"):
        return profile.model_dump()
    return dict(profile)


def normalize_model_command(command: Optional[str]) -> Optional[str]:
    """Normalize command names used by CLI options and configuration files."""
    if not command:
        return None
    return {
        "git-new": "git_new",
        "jira-new": "jira_new",
        "investigate": "investigation",
        "commit": "commit_message",
        "pr": "pr_template",
        "pr-template": "pr_template",
    }.get(command, command)


def _provider_name(profile: Dict[str, Any]) -> str:
    """Return the canonical provider identifier for a profile."""
    provider = profile.get("provider")
    if provider:
        return str(provider).strip().lower()
    if profile.get("use_vertex"):
        return "vertex"
    return str(profile.get("name", "")).strip().lower()


def _canonical_agent_backend(agent_backend: Optional[str]) -> str:
    """Normalize backend aliases for profile selection and compatibility checks."""
    return {
        "ollama-claude": "ollama",
        "anthropic": "claude",
        "opencode-ai": "opencode",
    }.get((agent_backend or "").strip().lower(), (agent_backend or "").strip().lower())


def get_agent_backend_from_profile(profile: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return the agent adapter declared by a model provider profile."""
    if not profile:
        return None
    if not isinstance(profile, dict):
        profile = _profile_to_dict(profile)
    if not profile:
        return None

    explicit_backend = profile.get("agent_backend")
    if explicit_backend:
        return str(explicit_backend)

    provider = _provider_name(profile)
    if provider in {"codex", "openai"}:
        return "codex"
    if provider == "ollama":
        return "ollama"
    if provider in CLAUDE_PROFILE_PROVIDERS:
        return "claude"
    return None


def get_profile_agent_backend(config, profile_name: Optional[str] = None) -> Optional[str]:
    """Return the backend selected by a named or default model profile."""
    profile = get_active_profile(config, override_profile_name=profile_name)
    return get_agent_backend_from_profile(profile)


def _profile_matches_agent(profile_name: str, profile: Dict[str, Any], agent_backend: str) -> bool:
    """Whether a provider profile is an obvious match for an agent backend."""
    backend = (agent_backend or "").strip().lower()
    inferred_backend = get_agent_backend_from_profile(profile)
    if inferred_backend and _canonical_agent_backend(inferred_backend) == _canonical_agent_backend(backend):
        return True
    provider = _provider_name(profile)
    profile_key = profile_name.strip().lower()
    aliases = {
        "ollama-claude": "ollama",
        "llama_cpp": "llama-cpp",
        "llama.cpp": "llama-cpp",
        "mlx-lm": "mlx",
    }
    return provider in {backend, aliases.get(backend, backend)} or profile_key in {
        backend,
        aliases.get(backend, backend),
    }


def get_profile_compatibility_error(
    profile: Optional[Dict[str, Any]], agent_backend: Optional[str]
) -> Optional[str]:
    """Return a clear error when a profile cannot configure an agent backend."""
    if not profile or not agent_backend:
        return None

    backend = _canonical_agent_backend(agent_backend)
    profile_backend = get_agent_backend_from_profile(profile)
    if profile.get("agent_backend"):
        compatible = backend == _canonical_agent_backend(profile_backend)
        if compatible:
            return None
        return (
            f"Model provider profile '{profile.get('name', '<unnamed>')}' selects agent "
            f"backend '{profile_backend}', which is not compatible with agent backend "
            f"'{agent_backend}'. Select a profile with the matching agent adapter."
        )
    provider = _provider_name(profile)

    if provider in {"codex", "openai"}:
        compatible = backend == "codex"
    elif provider == "ollama":
        compatible = backend == "ollama"
    elif provider in CLAUDE_PROFILE_PROVIDERS:
        compatible = backend == "claude"
    else:
        # Unknown/custom provider profiles are only safe for the Anthropic
        # protocol client until an explicit backend adapter is added.
        compatible = backend == "claude"

    if compatible:
        return None

    return (
        f"Model provider profile '{profile.get('name', '<unnamed>')}' uses provider "
        f"'{provider}', which is not compatible with agent backend '{agent_backend}'. "
        f"Select a profile with the matching agent adapter."
    )


def _select_profile_name(config, override_profile_name: Optional[str], agent_backend: Optional[str]) -> Optional[str]:
    """Resolve a profile name while keeping provider and agent selection separate."""
    model_provider_config = getattr(config, "model_provider", None) if config else None
    profiles = getattr(model_provider_config, "profiles", {}) if model_provider_config else {}
    if not isinstance(profiles, dict) or not profiles:
        return None

    if override_profile_name:
        if override_profile_name in profiles:
            profile = _profile_to_dict(profiles[override_profile_name]) or {}
            compatibility_error = get_profile_compatibility_error(profile, agent_backend)
            if compatibility_error:
                raise ModelProviderCompatibilityError(compatibility_error)
            return override_profile_name
        print(f"Warning: Model profile '{override_profile_name}' not found in configuration")

    env_profile_name = os.environ.get("MODEL_PROVIDER_PROFILE")
    if env_profile_name:
        if env_profile_name in profiles:
            profile = _profile_to_dict(profiles[env_profile_name]) or {}
            compatibility_error = get_profile_compatibility_error(profile, agent_backend)
            if compatibility_error:
                raise ModelProviderCompatibilityError(compatibility_error)
            return env_profile_name
        print(f"Warning: MODEL_PROVIDER_PROFILE={env_profile_name} not found in configuration")

    default_profile = getattr(model_provider_config, "default_profile", None)
    if default_profile in profiles:
        profile = _profile_to_dict(profiles[default_profile]) or {}
        compatibility_error = get_profile_compatibility_error(profile, agent_backend)
        if compatibility_error:
            raise ModelProviderCompatibilityError(compatibility_error)
        return default_profile
    return None


def get_profile_by_name(config, profile_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific model provider profile by name.

    Args:
        config: Merged configuration object with model_provider field
        profile_name: Name of the profile to retrieve

    Returns:
        Profile dictionary or None if not found
    """
    if not config or not hasattr(config, 'model_provider'):
        return None

    model_provider_config = config.model_provider
    if not model_provider_config or not model_provider_config.profiles:
        return None

    return _profile_to_dict(model_provider_config.profiles.get(profile_name))


def get_active_profile(
    config,
    override_profile_name: Optional[str] = None,
    agent_backend: Optional[str] = None,
    command: Optional[str] = None,
    utility: bool = False,
) -> Optional[Dict[str, Any]]:
    """Get the active model provider profile from configuration.

    Profile resolution order:
    1. override_profile_name (from --model-profile or the session)
    2. Environment variable MODEL_PROVIDER_PROFILE
    3. A profile matching the selected agent backend
    4. Config default_profile setting
    5. None (the native agent owns provider configuration)

    Args:
        config: Merged configuration object with model_provider field
        override_profile_name: Optional profile name to use (e.g., from CLI flag or session setting)
        agent_backend: Optional AI agent backend used to find a matching provider profile
        command: Optional DevAIFlow command whose model should be selected
        utility: Whether the command is a commit-message/PR-template utility call

    Returns:
        Profile dictionary or None if using default Anthropic API
    """
    profile_name = _select_profile_name(config, override_profile_name, agent_backend)
    profile = get_profile_by_name(config, profile_name) if profile_name else None
    if profile and command:
        model_name = get_model_name_from_profile(profile, command=command, utility=utility)
        if model_name:
            profile["model_name"] = model_name
        reasoning_effort = get_reasoning_effort_from_profile(
            profile, command=command, utility=utility
        )
        if reasoning_effort:
            profile["utility_reasoning_effort" if utility else "reasoning_effort"] = reasoning_effort
    return profile


def build_env_from_profile(profile: Optional[Dict[str, Any]], base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build environment variables from a model provider profile.

    Args:
        profile: Model provider profile dictionary (optional)
        base_env: Base environment dict to copy from (defaults to os.environ)

    Returns:
        Environment dict with profile settings applied
    """
    if profile and not isinstance(profile, dict):
        profile = _profile_to_dict(profile)

    # Start with copy of base environment
    if base_env is None:
        env = os.environ.copy()
    else:
        env = base_env.copy()

    # If no profile, return base environment
    if not profile:
        return env

    # Apply profile settings. API URLs are required only for local providers;
    # cloud providers use their SDK defaults unless a custom URL is supplied.
    provider = _provider_name(profile)
    api_url = profile.get("api_url") or profile.get("base_url")
    if api_url:
        if provider == "ollama":
            env["OLLAMA_HOST"] = api_url
        else:
            env["ANTHROPIC_BASE_URL"] = api_url

    if profile.get("auth_token"):
        if provider in {"codex", "openai"}:
            env["OPENAI_API_KEY"] = profile["auth_token"]
        else:
            env["ANTHROPIC_AUTH_TOKEN"] = profile["auth_token"]

    if "api_key" in profile and profile["api_key"] is not None:
        if provider in {"codex", "openai"}:
            env["OPENAI_API_KEY"] = profile["api_key"]
        else:
            env["ANTHROPIC_API_KEY"] = profile["api_key"]

    if profile.get("use_vertex"):
        env["CLAUDE_CODE_USE_VERTEX"] = "1"

        # Set Vertex-specific env vars if provided
        if profile.get("vertex_project_id"):
            env["ANTHROPIC_VERTEX_PROJECT_ID"] = profile["vertex_project_id"]

        if profile.get("vertex_region"):
            env["ANTHROPIC_VERTEX_REGION"] = profile["vertex_region"]
    else:
        # Explicitly unset Vertex flag if not using Vertex
        env.pop("CLAUDE_CODE_USE_VERTEX", None)

    # Apply additional environment variables
    if profile.get("env_vars"):
        env.update(profile["env_vars"])

    return env


def apply_model_override(profile: Optional[Dict[str, Any]], model: Optional[str]) -> Optional[Dict[str, Any]]:
    """Apply a --model CLI override to a resolved profile.

    Args:
        profile: Resolved model provider profile (may be None)
        model: Model name from --model flag (may be None)

    Returns:
        Profile with model_name overridden, a synthetic profile, or None
    """
    if not model:
        return profile
    if profile is None:
        return {"model_name": model}
    profile = _profile_to_dict(profile)
    profile["model_name"] = model
    return profile


def get_model_name_from_profile(
    profile: Optional[Dict[str, Any]],
    command: Optional[str] = None,
    utility: bool = False,
) -> Optional[str]:
    """Get the model name from a profile.

    Args:
        profile: Model provider profile dictionary (optional)

    Returns:
        Model name string or None
    """
    if not profile:
        return None

    if not isinstance(profile, dict):
        profile = _profile_to_dict(profile)
    if not profile:
        return None

    command = normalize_model_command(command)
    models = profile.get("models") or profile.get("command_models") or {}
    if command and isinstance(models, dict):
        if models.get(command):
            return models[command]
        if utility and models.get("utility"):
            return models["utility"]

    if utility:
        return profile.get("commit_message_model") if command == "commit_message" else (
            profile.get("pr_template_model") if command == "pr_template" else profile.get("utility_model")
        ) or profile.get("model_name")

    return profile.get("model_name")


def get_reasoning_effort_from_profile(
    profile: Optional[Dict[str, Any]],
    command: Optional[str] = None,
    utility: bool = False,
) -> Optional[str]:
    """Get the optional reasoning strength configured for a profile command."""
    if not profile:
        return None

    if not isinstance(profile, dict):
        profile = _profile_to_dict(profile)
    if not profile:
        return None

    command = normalize_model_command(command)
    reasoning_efforts = profile.get("reasoning_efforts") or profile.get("command_reasoning") or {}
    if command and isinstance(reasoning_efforts, dict):
        if reasoning_efforts.get(command):
            return reasoning_efforts[command]
        if utility and reasoning_efforts.get("utility"):
            return reasoning_efforts["utility"]

    if utility:
        return profile.get("utility_reasoning_effort") or profile.get("reasoning_effort")
    return profile.get("reasoning_effort")


def get_reasoning_for_command(
    config,
    agent_backend: str,
    command: str,
    profile_name: Optional[str] = None,
    cli_override: Optional[str] = None,
    utility: bool = False,
) -> Optional[str]:
    """Resolve reasoning strength using the same precedence as model selection."""
    if cli_override:
        return cli_override

    profile = get_active_profile(
        config,
        override_profile_name=profile_name,
        agent_backend=agent_backend,
        command=command,
        utility=utility,
    )
    reasoning_effort = get_reasoning_effort_from_profile(
        profile, command=command, utility=utility
    )
    if reasoning_effort:
        return reasoning_effort

    from devflow.agent.model_config import get_agent_model_config

    return get_agent_model_config(
        config,
        agent_backend,
        utility=utility,
        command=command,
    )["reasoning_effort"]


def get_model_for_command(
    config,
    agent_backend: str,
    command: str,
    profile_name: Optional[str] = None,
    cli_model: Optional[str] = None,
    utility: bool = False,
) -> Optional[str]:
    """Resolve the model for a command, including its provider profile.

    ``cli_model`` applies to session commands only. Utility commands deliberately
    ignore it and use the profile's commit-message or PR-template model.
    """
    profile = get_active_profile(
        config,
        override_profile_name=profile_name,
        agent_backend=agent_backend,
        command=command,
        utility=utility,
    )
    if cli_model and not utility:
        return cli_model
    model = get_model_name_from_profile(profile, command=command, utility=utility)
    if model:
        return model

    from devflow.agent.model_config import get_agent_model_config

    return get_agent_model_config(
        config,
        agent_backend,
        utility=utility,
        command=command,
        model_override=cli_model if not utility else None,
    )["model"]


def get_profile_display_name(profile: Optional[Dict[str, Any]]) -> str:
    """Get a human-readable display name for a profile.

    Args:
        profile: Model provider profile dictionary (optional)

    Returns:
        Display name (e.g., "Anthropic API", "Vertex AI (project-123)", "llama.cpp (Qwen3-Coder)")
    """
    if not profile:
        return "Anthropic API"

    name = profile.get("name", "Unknown")
    provider = _provider_name(profile)

    # Add additional context based on configuration
    if profile.get("use_vertex"):
        project_id = profile.get("vertex_project_id", "unknown")
        return f"Vertex AI ({project_id})"

    if profile.get("base_url") or profile.get("api_url"):
        base_url = profile.get("api_url") or profile["base_url"]
        if "localhost" in base_url or "127.0.0.1" in base_url:
            model = profile.get("model_name", "local model")
            return f"{name} ({model})"
        elif "openrouter" in base_url:
            model = profile.get("model_name", "cloud model")
            return f"OpenRouter ({model})"
        else:
            return f"{name} ({base_url})"

    return f"{name} ({provider})" if provider and provider != name.lower() else name


def parse_claude_model_display_name(model_id: str) -> str:
    """Parse a Claude model ID into a human-readable display name.

    Args:
        model_id: Model identifier (e.g., "claude-opus-4-6", "claude-3-5-sonnet-20241022")

    Returns:
        Human-readable name (e.g., "Claude Opus 4.6") or the original ID if not a Claude model
    """
    if not model_id or not model_id.startswith("claude-"):
        return model_id or "Claude"

    # Strip context marker like [1m]
    clean_id = re.sub(r'\[.*?\]$', '', model_id)

    # Claude 4.x format: claude-{tier}-{major}-{minor}[-date]
    match = re.match(r'^claude-(opus|sonnet|haiku)-(\d+)-(\d+)(?:-\d+)?$', clean_id)
    if match:
        tier = match.group(1).capitalize()
        major = match.group(2)
        minor = match.group(3)
        return f"Claude {tier} {major}.{minor}"

    # Claude 3.x format: claude-{major}[-{minor}]-{tier}[-date]
    match = re.match(r'^claude-(\d+)(?:-(\d+))?-(opus|sonnet|haiku)(?:-\d+)?$', clean_id)
    if match:
        major = match.group(1)
        minor = match.group(2)
        tier = match.group(3).capitalize()
        if minor:
            return f"Claude {major}.{minor} {tier}"
        return f"Claude {major} {tier}"

    return model_id


def get_model_attribution_name(config, model_profile_override: Optional[str] = None) -> str:
    """Resolve the model display name for commit attribution.

    Args:
        config: Merged configuration object
        model_profile_override: Optional profile name from session.model_profile

    Returns:
        Display name (e.g., "Claude Opus 4.6", "Claude") for use in Co-Authored-By
    """
    profile = get_active_profile(config, override_profile_name=model_profile_override)
    model_name = get_model_name_from_profile(profile)

    if not model_name:
        return "Claude"

    if model_name.startswith("claude-"):
        return parse_claude_model_display_name(model_name)

    return model_name


def get_co_authored_by_line(config=None, model_profile_override: Optional[str] = None, agent_backend: Optional[str] = None, model_id: Optional[str] = None) -> str:
    """Build the Co-Authored-By attribution line for commit messages.

    Args:
        config: Merged configuration object (optional)
        model_profile_override: Optional profile name from session.model_profile
        agent_backend: Agent backend identifier (e.g., "claude", "codex", "opencode")
        model_id: Optional model identifier from session.model_id (fallback for model name)

    Returns:
        Full attribution string, e.g., "Co-Authored-By: Codex (gpt-5.6-sol) <noreply@openai.com>"
    """
    _AGENT_ATTRIBUTION = {
        "codex": ("Codex", "noreply@openai.com"),
        "opencode": ("OpenCode", "noreply@opencode.ai"),
        "aider": ("Aider", "noreply@aider.chat"),
    }

    if agent_backend and agent_backend in _AGENT_ATTRIBUTION:
        default_name, email = _AGENT_ATTRIBUTION[agent_backend]
        profile = get_active_profile(config, override_profile_name=model_profile_override) if config else None
        model_name = get_model_name_from_profile(profile) or model_id
        name = f"{default_name} ({model_name})" if model_name else default_name
        return f"Co-Authored-By: {name} <{email}>"

    name = get_model_attribution_name(config, model_profile_override) if config else "Claude"
    return f"Co-Authored-By: {name} <noreply@anthropic.com>"
