"""Model provider templates for TUI configuration.

This module provides template-based configuration for different AI model providers,
making it easier for users to configure providers with provider-specific forms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FormField:
    """Represents a form field in a provider template."""

    field_id: str
    label: str
    field_type: str  # "input", "select", "checkbox"
    placeholder: str = ""
    required: bool = False
    default_value: Any = None
    options: Optional[List[Tuple[str, str]]] = None  # For select fields
    help_text: str = ""


class ProviderTemplate(ABC):
    """Base class for model provider templates."""

    @abstractmethod
    def get_name(self) -> str:
        """Get template display name."""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get description for template selection screen."""
        pass

    @abstractmethod
    def get_template_id(self) -> str:
        """Get unique template identifier."""
        pass

    @abstractmethod
    def get_fields(self) -> List[FormField]:
        """Get form fields for this provider."""
        pass

    @abstractmethod
    def generate_config(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate profile configuration from form data.

        Args:
            form_data: Dictionary of field_id -> value from the form

        Returns:
            Profile configuration dictionary
        """
        pass

    def validate(self, form_data: Dict[str, Any]) -> List[str]:
        """Validate form data.

        Args:
            form_data: Dictionary of field_id -> value from the form

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        for field in self.get_fields():
            if field.required:
                value = form_data.get(field.field_id, "")
                if not value or (isinstance(value, str) and not value.strip()):
                    errors.append(f"{field.label} is required")
        return errors


class AnthropicTemplate(ProviderTemplate):
    """Template for Anthropic API configuration."""

    def get_name(self) -> str:
        return "Anthropic API (native)"

    def get_description(self) -> str:
        return "Use official Anthropic Claude API (requires API key)"

    def get_template_id(self) -> str:
        return "anthropic"

    def get_fields(self) -> List[FormField]:
        """Anthropic needs minimal configuration - most use env vars."""
        return [
            FormField(
                field_id="profile_name",
                label="Profile Name",
                field_type="input",
                placeholder="e.g., anthropic, claude-api",
                required=True,
                help_text="Unique name for this profile",
            ),
            FormField(
                field_id="api_key",
                label="API Key (optional)",
                field_type="input",
                placeholder="Leave empty to use ANTHROPIC_API_KEY env var",
                required=False,
                help_text="Anthropic API key - defaults to environment variable",
            ),
            FormField(
                field_id="model_name",
                label="Model Name (optional)",
                field_type="input",
                placeholder="e.g., claude-sonnet-4-5",
                required=False,
                help_text="Specific model to use - leave empty for default",
            ),
        ]

    def generate_config(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Anthropic profile configuration."""
        config = {
            "name": form_data["profile_name"],
        }

        # Only add optional fields if provided
        if form_data.get("api_key"):
            config["api_key"] = form_data["api_key"]
        if form_data.get("model_name"):
            config["model_name"] = form_data["model_name"]

        return config


class VertexAITemplate(ProviderTemplate):
    """Template for Google Vertex AI configuration."""

    def get_name(self) -> str:
        return "Google Vertex AI"

    def get_description(self) -> str:
        return "Use Claude via Google Cloud Vertex AI (requires GCP project)"

    def get_template_id(self) -> str:
        return "vertex"

    def get_fields(self) -> List[FormField]:
        """Vertex AI needs GCP project and region."""
        return [
            FormField(
                field_id="profile_name",
                label="Profile Name",
                field_type="input",
                placeholder="e.g., vertex-prod, gcp-claude",
                required=True,
                help_text="Unique name for this profile",
            ),
            FormField(
                field_id="vertex_project_id",
                label="GCP Project ID",
                field_type="input",
                placeholder="your-gcp-project-id",
                required=True,
                help_text="Google Cloud Platform project ID",
            ),
            FormField(
                field_id="vertex_region",
                label="GCP Region",
                field_type="select",
                required=True,
                default_value="us-east5",
                options=self._get_vertex_regions(),
                help_text="Region where Vertex AI Claude is available",
            ),
            FormField(
                field_id="model_name",
                label="Model Name (optional)",
                field_type="input",
                placeholder="e.g., claude-sonnet-4-5@20250929",
                required=False,
                help_text="Specific Claude model version",
            ),
        ]

    def _get_vertex_regions(self) -> List[Tuple[str, str]]:
        """Get list of Vertex AI regions supporting Claude."""
        return [
            ("US East (Virginia)", "us-east5"),
            ("Europe West (Belgium)", "europe-west1"),
            ("Europe West (London)", "europe-west2"),
            ("Asia Southeast (Singapore)", "asia-southeast1"),
        ]

    def generate_config(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Vertex AI profile configuration."""
        config = {
            "name": form_data["profile_name"],
            "use_vertex": True,
            "vertex_project_id": form_data["vertex_project_id"],
            "vertex_region": form_data["vertex_region"],
        }

        if form_data.get("model_name"):
            config["model_name"] = form_data["model_name"]

        return config


class OpenRouterTemplate(ProviderTemplate):
    """Template for OpenRouter configuration."""

    def get_name(self) -> str:
        return "OpenRouter"

    def get_description(self) -> str:
        return "Access multiple models via OpenRouter (pay-per-use, very affordable)"

    def get_template_id(self) -> str:
        return "openrouter"

    def get_fields(self) -> List[FormField]:
        """OpenRouter needs API key and model selection."""
        return [
            FormField(
                field_id="profile_name",
                label="Profile Name",
                field_type="input",
                placeholder="e.g., openrouter-deepseek, openrouter-free",
                required=True,
                help_text="Unique name for this profile",
            ),
            FormField(
                field_id="auth_token",
                label="API Key",
                field_type="input",
                placeholder="Your OpenRouter API key",
                required=True,
                help_text="Get from openrouter.ai/keys",
            ),
            FormField(
                field_id="model_name",
                label="Model",
                field_type="select",
                required=True,
                default_value="deepseek/deepseek-v3.2",
                options=self._get_popular_models(),
                help_text="Select model or choose Custom to enter manually",
            ),
            FormField(
                field_id="custom_model",
                label="Custom Model Name",
                field_type="input",
                placeholder="model/name",
                required=False,
                help_text="Only if you selected 'Custom' above",
            ),
            FormField(
                field_id="base_url",
                label="Base URL (optional)",
                field_type="input",
                placeholder="https://openrouter.ai/api",
                required=False,
                default_value="https://openrouter.ai/api",
                help_text="Default is correct for most users",
            ),
        ]

    def _get_popular_models(self) -> List[Tuple[str, str]]:
        """Get list of popular OpenRouter models."""
        return [
            ("DeepSeek V3.2 ($0.28/M - cheapest)", "deepseek/deepseek-v3.2"),
            ("Claude 3.5 Sonnet (high quality)", "anthropic/claude-3.5-sonnet"),
            ("GPT-OSS 120B (free tier)", "openai/gpt-oss-120b:free"),
            ("Custom (enter manually below)", "custom"),
        ]

    def generate_config(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate OpenRouter profile configuration."""
        # Use custom model if "custom" was selected
        model_name = form_data["model_name"]
        if model_name == "custom":
            model_name = form_data.get("custom_model", "")
            if not model_name:
                raise ValueError("Custom model name is required when 'Custom' is selected")

        config = {
            "name": form_data["profile_name"],
            "base_url": form_data.get("base_url") or "https://openrouter.ai/api",
            "auth_token": form_data["auth_token"],
            "api_key": "",  # Empty string to disable ANTHROPIC_API_KEY
            "model_name": model_name,
        }

        return config

    def validate(self, form_data: Dict[str, Any]) -> List[str]:
        """Validate OpenRouter configuration."""
        errors = super().validate(form_data)

        # Check if custom model is provided when needed
        if form_data.get("model_name") == "custom":
            if not form_data.get("custom_model", "").strip():
                errors.append("Custom model name is required when 'Custom' is selected")

        return errors


class CustomServerTemplate(ProviderTemplate):
    """Template for custom server configuration (llama.cpp, LM Studio, etc.)."""

    def get_name(self) -> str:
        return "llama.cpp / Custom Server"

    def get_description(self) -> str:
        return "Connect to local llama.cpp server or other custom API endpoint"

    def get_template_id(self) -> str:
        return "custom"

    def get_fields(self) -> List[FormField]:
        """Custom server needs URL and auth details."""
        return [
            FormField(
                field_id="profile_name",
                label="Profile Name",
                field_type="input",
                placeholder="e.g., llama-cpp, lmstudio, local-model",
                required=True,
                help_text="Unique name for this profile",
            ),
            FormField(
                field_id="base_url",
                label="Base URL",
                field_type="input",
                placeholder="http://localhost:8000",
                required=True,
                help_text="URL where your server is running",
            ),
            FormField(
                field_id="auth_token",
                label="Auth Token (optional)",
                field_type="input",
                placeholder="llama-cpp",
                required=False,
                help_text="Authentication token - use 'llama-cpp' for llama.cpp server",
            ),
            FormField(
                field_id="api_key",
                label="API Key (optional)",
                field_type="input",
                placeholder="Leave empty for local servers",
                required=False,
                help_text="Leave empty to disable ANTHROPIC_API_KEY env var",
            ),
            FormField(
                field_id="model_name",
                label="Model Name",
                field_type="input",
                placeholder="e.g., Qwen3-Coder",
                required=True,
                help_text="Model alias as configured in your server (--alias flag for llama.cpp)",
            ),
        ]

    def generate_config(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate custom server profile configuration."""
        config = {
            "name": form_data["profile_name"],
            "base_url": form_data["base_url"],
            "model_name": form_data["model_name"],
        }

        # Add optional fields
        if form_data.get("auth_token"):
            config["auth_token"] = form_data["auth_token"]
        if form_data.get("api_key"):
            config["api_key"] = form_data["api_key"]

        return config


# Template Registry
_TEMPLATE_REGISTRY: Dict[str, ProviderTemplate] = {
    "anthropic": AnthropicTemplate(),
    "vertex": VertexAITemplate(),
    "openrouter": OpenRouterTemplate(),
    "custom": CustomServerTemplate(),
}


def get_template_registry() -> Dict[str, ProviderTemplate]:
    """Get the template registry.

    Returns:
        Dictionary mapping template_id -> ProviderTemplate instance
    """
    return _TEMPLATE_REGISTRY


def detect_template_from_profile(profile_data: Dict[str, Any]) -> str:
    """Detect which template a profile was created with.

    Args:
        profile_data: Profile configuration dictionary

    Returns:
        Template ID (one of: anthropic, vertex, openrouter, custom)
    """
    # Check for Vertex AI
    if profile_data.get("use_vertex"):
        return "vertex"

    # Check for OpenRouter (has base_url pointing to openrouter.ai)
    base_url = profile_data.get("base_url", "")
    if "openrouter.ai" in base_url:
        return "openrouter"

    # Check for custom server (has base_url but not OpenRouter)
    if base_url:
        return "custom"

    # Default to Anthropic
    return "anthropic"
