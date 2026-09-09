"""Tests for provider/profile and command model resolution."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from devflow.agent.factory import resolve_agent_backend
from devflow.config.models import ModelProviderConfig, ModelProviderProfile
from devflow.utils.model_provider import (
    build_env_from_profile,
    get_active_profile,
    get_default_profile_name,
    get_profile_agent_backend,
    get_model_for_command,
    get_model_name_from_profile,
    get_profile_compatibility_error,
    get_reasoning_for_command,
    ModelProviderValidationResult,
    ModelProviderProfileNotFoundError,
    validate_model_provider_profile,
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


def test_only_profile_is_used_when_configured_default_is_missing():
    """A lone profile is the effective default even if the legacy default is stale."""
    profile = ModelProviderProfile(
        name="codex_gpt-5.6_luna",
        provider="codex",
        agent_backend="codex",
        model_name="gpt-5.6-luna",
    )
    config = _config({"codex_gpt-5.6_luna": profile}, "anthropic")

    assert get_default_profile_name(config) == "codex_gpt-5.6_luna"
    assert get_active_profile(config)["name"] == "codex_gpt-5.6_luna"
    assert get_profile_agent_backend(config) == "codex"
    assert resolve_agent_backend(config=config) == "codex"


def test_non_string_session_profile_metadata_is_not_treated_as_profile_name():
    profile = ModelProviderProfile(
        name="codex-profile",
        provider="codex",
        agent_backend="codex",
        model_name="codex-model",
    )
    config = _config({"codex-profile": profile}, "codex-profile")
    session = SimpleNamespace(model_profile=object(), agent_backend=None)

    assert resolve_agent_backend(config=config, session=session) == "codex"


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


def test_agent_backend_does_not_select_a_different_profile():
    profile = ModelProviderProfile(
        name="local-ollama",
        provider="ollama",
        base_url="http://localhost:11434",
        model_name="local-model",
    )
    cloud = ModelProviderProfile(name="cloud", provider="anthropic", model_name="cloud-model")
    config = _config({"local-ollama": profile, "cloud": cloud}, "cloud")

    with pytest.raises(ValueError, match="matching agent adapter"):
        get_active_profile(config, agent_backend="ollama")


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


def test_validate_model_provider_profile_success_is_secret_free():
    """Valid profiles report checks without copying credential values to output."""
    profile = ModelProviderProfile(
        name="codex-profile",
        provider="codex",
        agent_backend="codex",
        api_key="test-secret-token",
        model_name="model-a",
        reasoning_efforts={"open": "high"},
    )
    before = profile.model_dump()

    result = validate_model_provider_profile(profile, environ={})

    assert isinstance(result, ModelProviderValidationResult)
    assert result.valid is True
    assert result.issues == []
    assert "test-secret-token" not in str(result.as_dict())
    assert profile.model_dump() == before


def test_validate_model_provider_profile_reports_codex_configuration_errors():
    """Codex model and reasoning typos are reported with actionable messages."""
    profile = {
        "name": "codex-profile",
        "provider": "codex",
        "agent_backend": "codex",
        "model_name": "model with spaces",
        "reasoning_efforts": {"open": "unsupported"},
    }

    result = validate_model_provider_profile(profile, environ={})

    assert result.valid is False
    assert any("default model" in issue and "whitespace" in issue for issue in result.issues)
    assert any("Reasoning strength" in issue and "Supported values" in issue for issue in result.issues)


def test_validate_model_provider_profile_reports_provider_agent_mismatch():
    """Provider and agent selections must be compatible before remote checks run."""
    result = validate_model_provider_profile(
        ModelProviderProfile(
            name="codex-profile",
            provider="codex",
            agent_backend="claude",
            model_name="model-a",
        ),
        environ={},
    )

    assert result.valid is False
    assert any("not compatible" in issue for issue in result.issues)


def test_validate_model_provider_profile_redacts_url_credentials():
    """Malformed URLs never echo embedded credentials or query tokens."""
    result = validate_model_provider_profile(
        {
            "name": "custom-profile",
            "provider": "custom",
            "agent_backend": "claude",
            "base_url": "https://user:password@example.invalid/api?token=secret",
            "model_name": "model-a",
        },
        environ={},
    )

    output = str(result.as_dict())
    assert result.valid is False
    assert "password" not in output
    assert "secret" not in output
    assert "embedded credentials" in output


@patch("devflow.utils.model_provider.requests.get")
def test_validate_model_provider_profile_verifies_models_on_explicit_request(mock_get):
    """Remote model verification occurs only when explicitly requested."""
    response = Mock(status_code=200)
    response.json.return_value = {"data": [{"id": "model-a"}]}
    mock_get.return_value = response
    profile = ModelProviderProfile(
        name="codex-profile",
        provider="codex",
        agent_backend="codex",
        api_key="test-secret-token",
        model_name="model-a",
    )

    static_result = validate_model_provider_profile(profile, environ={})
    assert mock_get.called is False
    assert static_result.remote_verified is False

    result = validate_model_provider_profile(profile, verify_remote=True, environ={})

    mock_get.assert_called_once_with(
        "https://api.openai.com/v1/models",
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer test-secret-token",
        },
        timeout=5.0,
    )
    assert result.remote_verified is True
    assert result.valid is True
    assert "test-secret-token" not in str(result.as_dict())


@patch("devflow.utils.model_provider.requests.get")
def test_validate_model_provider_profile_reports_unavailable_model_without_secret(mock_get):
    """A successful model-list response flags a model the account cannot use."""
    response = Mock(status_code=200)
    response.json.return_value = {"data": [{"id": "model-a"}]}
    mock_get.return_value = response

    result = validate_model_provider_profile(
        ModelProviderProfile(
            name="codex-profile",
            provider="codex",
            agent_backend="codex",
            api_key="test-secret-token",
            model_name="model-b",
        ),
        verify_remote=True,
        environ={},
    )

    assert result.valid is False
    assert any("model-b" in issue for issue in result.issues)
    assert "test-secret-token" not in str(result.as_dict())


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


def test_explicit_model_profile_overrides_existing_session_backend():
    profile = ModelProviderProfile(name="openai", provider="codex")
    config = _config({"openai": profile}, "unused")
    session = SimpleNamespace(model_profile=None, agent_backend="claude")

    assert resolve_agent_backend(
        session=session,
        config=config,
        model_profile="openai",
    ) == "codex"


def test_explicit_unknown_model_profile_does_not_fall_back_to_claude():
    config = _config({}, "anthropic")

    with pytest.raises(ModelProviderProfileNotFoundError, match="not configured"):
        get_active_profile(config, override_profile_name="codex-luna")


def test_selected_session_profile_supersedes_stored_agent_backend():
    profile = ModelProviderProfile(name="openai", provider="codex")
    config = _config({"openai": profile}, "openai")
    session = SimpleNamespace(model_profile="openai", agent_backend="claude")

    assert resolve_agent_backend(session=session, config=config) == "codex"
