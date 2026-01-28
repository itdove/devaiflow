"""Base validator for backend configuration files."""

from devflow.config.validators.base import BaseConfigValidator


class BaseBackendValidator(BaseConfigValidator):
    """Base class for backend-specific validators (JIRA, GitHub, GitLab, etc.).

    Backend validators add specific placeholder patterns and validations
    for issue tracker backends.
    """

    # Backend validators can override this with backend-specific patterns
    PLACEHOLDER_PATTERNS = BaseConfigValidator.PLACEHOLDER_PATTERNS + []
