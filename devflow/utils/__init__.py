"""Utility functions for DevAIFlow."""

from devflow.utils.paths import get_cs_home, get_cs_config_home, get_cs_state_home, is_mock_mode
from devflow.utils.user import get_current_user

__all__ = ["get_current_user", "get_cs_home", "get_cs_config_home", "get_cs_state_home", "is_mock_mode", "strip_code_fences"]


def strip_code_fences(text: str) -> str:
    """Remove wrapping markdown code fences from AI-generated text."""
    text = text.strip('`').strip()
    if not text.startswith('```'):
        return text
    lines = text.split('\n')
    if lines[0].strip().startswith('```'):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith('```'):
        lines = lines[:-1]
    return '\n'.join(lines).strip()
