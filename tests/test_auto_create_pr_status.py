"""Tests for auto_create_pr_status feature."""

import pytest
from devflow.config.models import PromptsConfig


def test_auto_create_pr_status_default_value():
    """Test that auto_create_pr_status has correct default value."""
    prompts = PromptsConfig()
    assert prompts.auto_create_pr_status == "prompt"


def test_auto_create_pr_status_valid_values():
    """Test that valid values are accepted."""
    # Test "draft"
    prompts = PromptsConfig(auto_create_pr_status="draft")
    assert prompts.auto_create_pr_status == "draft"

    # Test "ready"
    prompts = PromptsConfig(auto_create_pr_status="ready")
    assert prompts.auto_create_pr_status == "ready"

    # Test "prompt"
    prompts = PromptsConfig(auto_create_pr_status="prompt")
    assert prompts.auto_create_pr_status == "prompt"


def test_auto_create_pr_status_invalid_value_falls_back_to_prompt():
    """Test that invalid values fall back to 'prompt'."""
    prompts = PromptsConfig(auto_create_pr_status="invalid")
    assert prompts.auto_create_pr_status == "prompt"


def test_auto_create_pr_status_none_value_falls_back_to_prompt():
    """Test that None value falls back to 'prompt'."""
    prompts = PromptsConfig(auto_create_pr_status=None)
    assert prompts.auto_create_pr_status == "prompt"


def test_auto_create_pr_status_empty_string_falls_back_to_prompt():
    """Test that empty string falls back to 'prompt'."""
    prompts = PromptsConfig(auto_create_pr_status="")
    assert prompts.auto_create_pr_status == "prompt"
