"""Tests for per-backend model configuration resolution."""

from types import SimpleNamespace

from devflow.agent.model_config import get_agent_model_config
from devflow.config.models import AgentModelConfig


def test_get_session_settings_for_backend():
    config = SimpleNamespace(
        agent_models={
            "codex": AgentModelConfig(session_model="model-a", reasoning_effort="high")
        }
    )

    assert get_agent_model_config(config, "Codex") == {
        "model": "model-a",
        "reasoning_effort": "high",
    }


def test_get_utility_settings_fall_back_to_session_values():
    config = SimpleNamespace(
        agent_models={"backend-a": AgentModelConfig(session_model="model-a", reasoning_effort="medium")}
    )

    assert get_agent_model_config(config, "backend-a", utility=True) == {
        "model": "model-a",
        "reasoning_effort": "medium",
    }


def test_get_settings_returns_empty_for_missing_backend():
    assert get_agent_model_config(SimpleNamespace(agent_models={}), "backend-a") == {
        "model": None,
        "reasoning_effort": None,
    }
