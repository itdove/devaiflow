"""Utilities for managing model provider configuration and profiles.

This module provides functions to get active model provider profiles from configuration
and build environment variables for launching Claude Code with alternative AI providers.
"""

import os
import re
from typing import Dict, Optional, Any


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

    profile = model_provider_config.profiles.get(profile_name)
    if profile:
        return profile.model_dump() if hasattr(profile, 'model_dump') else profile

    return None


def get_active_profile(config, override_profile_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the active model provider profile from configuration.

    Profile resolution order:
    1. override_profile_name parameter (highest priority - from --model-profile flag)
    2. Environment variable MODEL_PROVIDER_PROFILE
    3. Config default_profile setting
    4. None (use default Anthropic API)

    Args:
        config: Merged configuration object with model_provider field
        override_profile_name: Optional profile name to use (e.g., from CLI flag or session setting)

    Returns:
        Profile dictionary or None if using default Anthropic API
    """
    if not config or not hasattr(config, 'model_provider'):
        return None

    model_provider_config = config.model_provider
    if not model_provider_config or not model_provider_config.profiles:
        return None

    # Check override parameter first (from --model-profile flag or session.model_profile)
    if override_profile_name:
        profile = model_provider_config.profiles.get(override_profile_name)
        if profile:
            return profile.model_dump() if hasattr(profile, 'model_dump') else profile
        else:
            # Override specified but profile not found - warn but continue with next priority
            print(f"Warning: Model profile '{override_profile_name}' not found in configuration")

    # Check environment variable second (temporary override)
    env_profile_name = os.environ.get("MODEL_PROVIDER_PROFILE")
    if env_profile_name:
        profile = model_provider_config.profiles.get(env_profile_name)
        if profile:
            return profile.model_dump() if hasattr(profile, 'model_dump') else profile
        else:
            # Env var specified but profile not found - warn but continue with default
            print(f"Warning: MODEL_PROVIDER_PROFILE={env_profile_name} not found in configuration")

    # Use configured default profile
    if model_provider_config.default_profile:
        profile = model_provider_config.profiles.get(model_provider_config.default_profile)
        if profile:
            return profile.model_dump() if hasattr(profile, 'model_dump') else profile

    # No profile configured - use default Anthropic API
    return None


def build_env_from_profile(profile: Optional[Dict[str, Any]], base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build environment variables from a model provider profile.

    Args:
        profile: Model provider profile dictionary (optional)
        base_env: Base environment dict to copy from (defaults to os.environ)

    Returns:
        Environment dict with profile settings applied
    """
    # Start with copy of base environment
    if base_env is None:
        env = os.environ.copy()
    else:
        env = base_env.copy()

    # If no profile, return base environment
    if not profile:
        return env

    # Apply profile settings
    if profile.get("base_url"):
        env["ANTHROPIC_BASE_URL"] = profile["base_url"]

    if profile.get("auth_token"):
        env["ANTHROPIC_AUTH_TOKEN"] = profile["auth_token"]

    if "api_key" in profile and profile["api_key"] is not None:
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


def get_model_name_from_profile(profile: Optional[Dict[str, Any]]) -> Optional[str]:
    """Get the model name from a profile.

    Args:
        profile: Model provider profile dictionary (optional)

    Returns:
        Model name string or None
    """
    if not profile:
        return None

    return profile.get("model_name")


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

    # Add additional context based on configuration
    if profile.get("use_vertex"):
        project_id = profile.get("vertex_project_id", "unknown")
        return f"Vertex AI ({project_id})"

    if profile.get("base_url"):
        base_url = profile["base_url"]
        if "localhost" in base_url or "127.0.0.1" in base_url:
            model = profile.get("model_name", "local model")
            return f"{name} ({model})"
        elif "openrouter" in base_url:
            model = profile.get("model_name", "cloud model")
            return f"OpenRouter ({model})"
        else:
            return f"{name} ({base_url})"

    return name


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


def get_co_authored_by_line(config=None, model_profile_override: Optional[str] = None) -> str:
    """Build the Co-Authored-By attribution line for commit messages.

    Args:
        config: Merged configuration object (optional)
        model_profile_override: Optional profile name from session.model_profile

    Returns:
        Full attribution string, e.g., "Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    """
    name = get_model_attribution_name(config, model_profile_override) if config else "Claude"
    return f"Co-Authored-By: {name} <noreply@anthropic.com>"
