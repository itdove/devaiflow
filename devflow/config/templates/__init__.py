"""Model provider templates for DevAIFlow."""

from .model_providers import (
    ProviderTemplate,
    AnthropicTemplate,
    CodexTemplate,
    VertexAITemplate,
    OpenRouterTemplate,
    CustomServerTemplate,
    LlamaCppTemplate,
    OllamaTemplate,
    MLXTemplate,
    get_template_registry,
)

__all__ = [
    "ProviderTemplate",
    "AnthropicTemplate",
    "CodexTemplate",
    "VertexAITemplate",
    "OpenRouterTemplate",
    "CustomServerTemplate",
    "LlamaCppTemplate",
    "OllamaTemplate",
    "MLXTemplate",
    "get_template_registry",
]
