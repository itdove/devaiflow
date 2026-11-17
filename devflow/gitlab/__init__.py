"""GitLab integration for DevAIFlow.

This module provides GitLab Issues backend support, including:
- Issue tracker client (GitLabClient)
- Field mapping between GitLab labels and DevAIFlow fields
- Merge request creation (via daf complete command)
"""

from devflow.gitlab.issues_client import GitLabClient
from devflow.gitlab.field_mapper import GitLabFieldMapper
from devflow.gitlab.transitions import transition_on_complete

__all__ = ['GitLabClient', 'GitLabFieldMapper', 'transition_on_complete']
