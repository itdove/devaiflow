"""Utility functions for DevAIFlow."""

from devflow.utils.paths import get_cs_home, get_cs_config_home, get_cs_state_home, is_mock_mode
from devflow.utils.user import get_current_user

__all__ = ["get_current_user", "get_cs_home", "get_cs_config_home", "get_cs_state_home", "is_mock_mode", "strip_code_fences"]


def strip_code_fences(text: str) -> str:
    """Remove wrapping markdown code fences and preamble from AI-generated text."""
    import re
    text = text.strip()

    # If text contains a code fence block, extract its content
    # Handles preamble text before the fence (e.g., "Here's the result:\n```markdown\n...")
    fence_match = re.search(r'^```\w*\n(.*?)^```\s*$', text, re.MULTILINE | re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Simple case: entire text wrapped in backticks
    text = text.strip('`').strip()
    if text.startswith('```'):
        lines = text.split('\n')
        if lines[0].strip().startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        return '\n'.join(lines).strip()

    return text
