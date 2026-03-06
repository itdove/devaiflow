"""GitHub Issues integration for DevAIFlow.

This package provides GitHub Issues backend implementation for DevAIFlow's
issue tracker abstraction layer.
"""

from .field_mapper import GitHubFieldMapper
from .issues_client import GitHubClient
from .transitions import transition_on_start, transition_on_complete

__all__ = [
    "GitHubFieldMapper",
    "GitHubClient",
    "transition_on_start",
    "transition_on_complete",
]
