"""Resolution helpers for per-backend model settings."""

from typing import Any, Dict, Optional


def get_agent_model_config(
    config: Any, backend: str, utility: bool = False
) -> Dict[str, Optional[str]]:
    """Return effective model and reasoning settings for a backend."""
    settings_map = getattr(config, "agent_models", {}) if config else {}
    settings = settings_map.get(backend.lower()) if isinstance(settings_map, dict) else None
    if settings is None:
        return {"model": None, "reasoning_effort": None}

    model = getattr(settings, "utility_model" if utility else "session_model", None)
    reasoning = getattr(
        settings,
        "utility_reasoning_effort" if utility else "reasoning_effort",
        None,
    )
    if utility:
        model = model or getattr(settings, "session_model", None)
        reasoning = reasoning or getattr(settings, "reasoning_effort", None)
    return {"model": model, "reasoning_effort": reasoning}
