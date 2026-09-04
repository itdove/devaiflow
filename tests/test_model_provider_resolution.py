"""Tests for provider/profile and command model resolution."""

from types import SimpleNamespace

import pytest

from devflow.agent.factory import resolve_agent_backend
from devflow.config.models import ModelProviderConfig, ModelProviderProfile
from devflow.utils.model_provider import (
    build_env_from_profile,
    get_active_profile,
    get_profile_agent_backend,
    get_model_for_command,
    get_model_name_from_profile,
    get_profile_compatibility_error,
    get_reasoning_for_command,
)


def _config(profiles, default_profile):
    return SimpleNamespace(
        model_provider=ModelProviderConfig(
            default_profile=default_profile,
            profiles=profiles,
        ),
        agent_backend="claude",
        agent_models={},
    )


def test_default_profile_resolves_command_model():
    profile = ModelProviderProfile(
        name="local",
        provider="ollama",
        base_url="http://localhost:11434",
        model_name="fallback-model",
        models={"new": "new-model", "commit_message": "commit-model"},
    )
    config = _config({"local": profile}, "local")

    resolved = get_active_profile(config, agent_backend="ollama", command="new")

    assert resolved["model_name"] == "new-model"
    assert get_model_for_command(config, "ollama", "commit_message", utility=True) == "commit-model"


def test_cli_model_does_not_override_utility_model():
    profile = ModelProviderProfile(
        name="cloud",
        provider="anthropic",
        model_name="session-model",
        models={"pr_template": "utility-model"},
    )
    config = _config({"cloud": profile}, "cloud")

    assert get_model_for_command(config, "claude", "open", cli_model="cli-model") == "cli-model"
    assert get_model_for_command(
        config, "claude", "pr_template", cli_model="cli-model", utility=True
    ) == "utility-model"


def test_agent_override_selects_matching_provider_profile(monkeypatch):
    profile = ModelProviderProfile(
        name="local-ollama",
        provider="ollama",
        base_url="http://localhost:11434",
        model_name="local-model",
    )
    cloud = ModelProviderProfile(name="cloud", provider="anthropic", model_name="cloud-model")
    config = _config({"local-ollama": profile, "cloud": cloud}, "cloud")

    assert get_active_profile(config, agent_backend="ollama")["name"] == "local-ollama"


def test_local_provider_requires_api_url():
    with pytest.raises(ValueError, match="API URL|api_url"):
        ModelProviderProfile(name="local", provider="mlx", model_name="local-model")


def test_ollama_profile_sets_ollama_host_only():
    profile = {
        "name": "local-ollama",
        "provider": "ollama",
        "base_url": "http://localhost:11434",
    }

    env = build_env_from_profile(profile, {"PATH": "/bin"})

    assert env["OLLAMA_HOST"] == "http://localhost:11434"
    assert "PATH" in env


def test_profile_model_aliases_are_normalized():
    profile = {"model_name": "fallback", "models": {"jira_new": "jira-model"}}

    assert get_model_name_from_profile(profile, command="jira-new") == "jira-model"


def test_profile_reasoning_strength_resolves_per_command():
    profile = ModelProviderProfile(
        name="cloud",
        provider="anthropic",
        model_name="session-model",
        models={"open": "fast-model"},
        reasoning_efforts={"open": "high", "commit_message": "low"},
    )
    config = _config({"cloud": profile}, "cloud")

    assert get_reasoning_for_command(config, "claude", "open") == "high"
    assert get_reasoning_for_command(config, "claude", "commit_message", utility=True) == "low"


def test_incompatible_explicit_profile_is_rejected():
    profile = ModelProviderProfile(name="codex-profile", provider="codex")
    config = _config({"codex-profile": profile}, "codex-profile")

    with pytest.raises(ValueError, match="not compatible"):
        get_active_profile(
            config,
            override_profile_name="codex-profile",
            agent_backend="claude",
        )

    assert get_profile_compatibility_error(profile.model_dump(), "claude")


def test_default_model_profile_supersedes_configured_agent_backend():
    profile = ModelProviderProfile(name="openai", provider="codex")
    config = _config({"openai": profile}, "openai")

    assert get_profile_agent_backend(config) == "codex"
    assert resolve_agent_backend(config=config) == "codex"


def test_explicit_agent_overrides_model_profile_backend():
    profile = ModelProviderProfile(name="openai", provider="codex")
    config = _config({"openai": profile}, "openai")

    assert resolve_agent_backend(cli_override="claude", config=config) == "claude"


def test_explicit_model_profile_selects_its_backend():
    profile = ModelProviderProfile(name="openai", provider="codex")
    config = _config({"openai": profile}, "unused")

    assert resolve_agent_backend(config=config, model_profile="openai") == "codex"


def test_selected_session_profile_supersedes_stored_agent_backend():
    profile = ModelProviderProfile(name="openai", provider="codex")
    config = _config({"openai": profile}, "openai")
    session = SimpleNamespace(model_profile="openai", agent_backend="claude")

    assert resolve_agent_backend(session=session, config=config) == "codex"
