"""Tests for model provider templates."""

import pytest
from devflow.config.templates.model_providers import (
    AnthropicTemplate,
    VertexAITemplate,
    OpenRouterTemplate,
    CustomServerTemplate,
    get_template_registry,
    detect_template_from_profile,
)


class TestAnthropicTemplate:
    """Tests for Anthropic template."""

    def test_template_metadata(self):
        """Test template metadata."""
        template = AnthropicTemplate()
        assert template.get_name() == "Anthropic API (native)"
        assert template.get_template_id() == "anthropic"
        assert "Anthropic" in template.get_description()

    def test_get_fields(self):
        """Test getting template fields."""
        template = AnthropicTemplate()
        fields = template.get_fields()

        assert len(fields) == 3
        field_ids = [f.field_id for f in fields]
        assert "profile_name" in field_ids
        assert "api_key" in field_ids
        assert "model_name" in field_ids

    def test_generate_config_minimal(self):
        """Test generating minimal Anthropic config."""
        template = AnthropicTemplate()
        form_data = {
            "profile_name": "my-anthropic",
        }

        config = template.generate_config(form_data)
        assert config["name"] == "my-anthropic"
        assert "api_key" not in config
        assert "model_name" not in config

    def test_generate_config_with_optional_fields(self):
        """Test generating config with optional fields."""
        template = AnthropicTemplate()
        form_data = {
            "profile_name": "my-anthropic",
            "api_key": "sk-test-123",
            "model_name": "claude-sonnet-4-5",
        }

        config = template.generate_config(form_data)
        assert config["name"] == "my-anthropic"
        assert config["api_key"] == "sk-test-123"
        assert config["model_name"] == "claude-sonnet-4-5"

    def test_validate_missing_required_field(self):
        """Test validation with missing required field."""
        template = AnthropicTemplate()
        form_data = {}

        errors = template.validate(form_data)
        assert len(errors) > 0
        assert any("Profile Name" in err for err in errors)

    def test_validate_success(self):
        """Test validation with all required fields."""
        template = AnthropicTemplate()
        form_data = {
            "profile_name": "my-anthropic",
        }

        errors = template.validate(form_data)
        assert len(errors) == 0


class TestVertexAITemplate:
    """Tests for Vertex AI template."""

    def test_template_metadata(self):
        """Test template metadata."""
        template = VertexAITemplate()
        assert template.get_name() == "Google Vertex AI"
        assert template.get_template_id() == "vertex"
        assert "Vertex AI" in template.get_description()

    def test_get_fields(self):
        """Test getting template fields."""
        template = VertexAITemplate()
        fields = template.get_fields()

        field_ids = [f.field_id for f in fields]
        assert "profile_name" in field_ids
        assert "vertex_project_id" in field_ids
        assert "vertex_region" in field_ids
        assert "model_name" in field_ids

    def test_generate_config(self):
        """Test generating Vertex AI config."""
        template = VertexAITemplate()
        form_data = {
            "profile_name": "vertex-prod",
            "vertex_project_id": "my-gcp-project",
            "vertex_region": "us-east5",
        }

        config = template.generate_config(form_data)
        assert config["name"] == "vertex-prod"
        assert config["use_vertex"] is True
        assert config["vertex_project_id"] == "my-gcp-project"
        assert config["vertex_region"] == "us-east5"

    def test_generate_config_with_model(self):
        """Test generating config with specific model."""
        template = VertexAITemplate()
        form_data = {
            "profile_name": "vertex-prod",
            "vertex_project_id": "my-gcp-project",
            "vertex_region": "us-east5",
            "model_name": "claude-sonnet-4-5@20250929",
        }

        config = template.generate_config(form_data)
        assert config["model_name"] == "claude-sonnet-4-5@20250929"

    def test_validate_missing_required_fields(self):
        """Test validation with missing required fields."""
        template = VertexAITemplate()
        form_data = {
            "profile_name": "vertex-prod",
        }

        errors = template.validate(form_data)
        assert len(errors) > 0
        assert any("GCP Project ID" in err for err in errors)


class TestOpenRouterTemplate:
    """Tests for OpenRouter template."""

    def test_template_metadata(self):
        """Test template metadata."""
        template = OpenRouterTemplate()
        assert template.get_name() == "OpenRouter"
        assert template.get_template_id() == "openrouter"
        assert "OpenRouter" in template.get_description()

    def test_generate_config(self):
        """Test generating OpenRouter config."""
        template = OpenRouterTemplate()
        form_data = {
            "profile_name": "openrouter-deepseek",
            "auth_token": "sk-or-123",
            "model_name": "deepseek/deepseek-v3.2",
        }

        config = template.generate_config(form_data)
        assert config["name"] == "openrouter-deepseek"
        assert config["base_url"] == "https://openrouter.ai/api"
        assert config["auth_token"] == "sk-or-123"
        assert config["api_key"] == ""
        assert config["model_name"] == "deepseek/deepseek-v3.2"

    def test_generate_config_custom_model(self):
        """Test generating config with custom model."""
        template = OpenRouterTemplate()
        form_data = {
            "profile_name": "openrouter-custom",
            "auth_token": "sk-or-123",
            "model_name": "custom",
            "custom_model": "custom/my-model",
        }

        config = template.generate_config(form_data)
        assert config["model_name"] == "custom/my-model"

    def test_validate_custom_model_missing(self):
        """Test validation when custom model is selected but not provided."""
        template = OpenRouterTemplate()
        form_data = {
            "profile_name": "openrouter-custom",
            "auth_token": "sk-or-123",
            "model_name": "custom",
        }

        errors = template.validate(form_data)
        assert len(errors) > 0
        assert any("Custom model" in err for err in errors)


class TestCustomServerTemplate:
    """Tests for custom server template."""

    def test_template_metadata(self):
        """Test template metadata."""
        template = CustomServerTemplate()
        assert template.get_name() == "llama.cpp / Custom Server"
        assert template.get_template_id() == "custom"
        assert "llama.cpp" in template.get_description()

    def test_generate_config_minimal(self):
        """Test generating minimal custom server config."""
        template = CustomServerTemplate()
        form_data = {
            "profile_name": "llama-cpp",
            "base_url": "http://localhost:8000",
            "model_name": "Qwen3-Coder",
        }

        config = template.generate_config(form_data)
        assert config["name"] == "llama-cpp"
        assert config["base_url"] == "http://localhost:8000"
        assert config["model_name"] == "Qwen3-Coder"
        assert "auth_token" not in config
        assert "api_key" not in config

    def test_generate_config_with_auth(self):
        """Test generating config with auth fields."""
        template = CustomServerTemplate()
        form_data = {
            "profile_name": "llama-cpp",
            "base_url": "http://localhost:8000",
            "model_name": "Qwen3-Coder",
            "auth_token": "llama-cpp",
        }

        config = template.generate_config(form_data)
        assert config["auth_token"] == "llama-cpp"
        # api_key should not be present if not provided
        assert "api_key" not in config


class TestTemplateRegistry:
    """Tests for template registry."""

    def test_get_template_registry(self):
        """Test getting template registry."""
        registry = get_template_registry()

        assert "anthropic" in registry
        assert "vertex" in registry
        assert "openrouter" in registry
        assert "custom" in registry

        assert isinstance(registry["anthropic"], AnthropicTemplate)
        assert isinstance(registry["vertex"], VertexAITemplate)
        assert isinstance(registry["openrouter"], OpenRouterTemplate)
        assert isinstance(registry["custom"], CustomServerTemplate)


class TestDetectTemplate:
    """Tests for template detection."""

    def test_detect_anthropic(self):
        """Test detecting Anthropic template."""
        profile = {"name": "anthropic"}
        assert detect_template_from_profile(profile) == "anthropic"

    def test_detect_vertex(self):
        """Test detecting Vertex AI template."""
        profile = {
            "name": "vertex",
            "use_vertex": True,
            "vertex_project_id": "my-project",
        }
        assert detect_template_from_profile(profile) == "vertex"

    def test_detect_openrouter(self):
        """Test detecting OpenRouter template."""
        profile = {
            "name": "openrouter",
            "base_url": "https://openrouter.ai/api",
            "auth_token": "sk-or-123",
        }
        assert detect_template_from_profile(profile) == "openrouter"

    def test_detect_custom(self):
        """Test detecting custom server template."""
        profile = {
            "name": "llama-cpp",
            "base_url": "http://localhost:8000",
            "model_name": "Qwen3-Coder",
        }
        assert detect_template_from_profile(profile) == "custom"
