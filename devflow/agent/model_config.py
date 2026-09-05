"""Resolution helpers for agent and provider model settings."""

from typing import Any, Dict, Optional


def _value(mapping: Any, key: str) -> Optional[str]:
    """Read a string setting from a dict or a Pydantic model."""
    if isinstance(mapping, dict):
        return mapping.get(key)
    return getattr(mapping, key, None)


def _command_model(mapping: Any, command: Optional[str]) -> Optional[str]:
    """Read a command-specific model from a model configuration object."""
    if not command:
        return None

    for field_name in ("command_models", "models"):
        command_models = _value(mapping, field_name) or {}
        if isinstance(command_models, dict):
            model = command_models.get(command)
            if model:
                return model

            # Accept the spelling variants used by the CLI and config examples.
            aliases = {
                "git-new": "git_new",
                "jira-new": "jira_new",
                "investigate": "investigation",
                "commit": "commit_message",
                "pr": "pr_template",
                "pr-template": "pr_template",
            }
            alias = aliases.get(command)
            if alias and command_models.get(alias):
                return command_models[alias]
    return None


def get_agent_model_config(
    config: Any,
    backend: str,
    utility: bool = False,
    command: Optional[str] = None,
    provider_profile: Optional[Dict[str, Any]] = None,
    model_override: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Return effective model and reasoning settings.

    Provider profiles are the primary source of model selection.  The older
    ``agent_models`` configuration remains a fallback so existing installations
    continue to work.  ``model_override`` is deliberately ignored for utility
    calls; commit messages and PR templates always use their configured utility
    models.
    """
    if provider_profile:
        from devflow.utils.model_provider import (
            get_model_name_from_profile,
            get_reasoning_effort_from_profile,
        )

        profile_model = get_model_name_from_profile(
            provider_profile,
            command=command,
            utility=utility,
        )
        return {
            "model": profile_model if utility or not model_override else model_override,
            "reasoning_effort": get_reasoning_effort_from_profile(
                provider_profile,
                command=command,
                utility=utility,
            ),
        }

    settings_map = getattr(config, "agent_models", {}) if config else {}
    settings = settings_map.get(backend.lower()) if isinstance(settings_map, dict) else None
    if settings is None:
        return {"model": None, "reasoning_effort": None}

    model = _command_model(settings, command)
    if utility:
        model = model or _value(settings, "utility_model")
    else:
        model = model or _value(settings, "session_model")

    reasoning = getattr(
        settings,
        "utility_reasoning_effort" if utility else "reasoning_effort",
        None,
    )
    if utility:
        model = model or _value(settings, "session_model")
        reasoning = reasoning or _value(settings, "reasoning_effort")
    elif model_override:
        model = model_override
    return {"model": model, "reasoning_effort": reasoning}
