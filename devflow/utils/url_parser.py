"""URL parser for issue tracker URLs.

Parses issue URLs and keys from GitHub, GitLab, and JIRA to extract:
- Backend type (github/gitlab/jira)
- Repository/project identifier
- Issue number/key
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse


def parse_issue_identifier(identifier: str) -> Optional[Tuple[str, str, str]]:
    """Parse issue identifier (URL or short format) to extract backend, repository, and issue key.

    Handles both full URLs and short formats:
    - Full URLs: https://github.com/owner/repo/issues/123
    - Short formats: owner/repo#123, group/project#42
    - JIRA keys: AAP-123 (no repository needed)

    Args:
        identifier: Issue URL or short format identifier

    Returns:
        Tuple of (backend, repository, issue_key) or None if invalid

        For GitHub: ('github', 'owner/repo', '123')
        For GitLab: ('gitlab', 'group/project', '123')
        For JIRA: ('jira', '', 'PROJECT-123')  # Empty repository for JIRA

    Examples:
        >>> parse_issue_identifier('https://github.com/itdove/devaiflow/issues/305')
        ('github', 'itdove/devaiflow', '305')

        >>> parse_issue_identifier('itdove/devaiflow#305')
        ('github', 'itdove/devaiflow', '305')

        >>> parse_issue_identifier('group/project#42')
        ('github', 'group/project', '42')

        >>> parse_issue_identifier('AAP-70183')
        ('jira', '', 'AAP-70183')
    """
    if not identifier:
        return None

    # Try parsing as full URL first
    result = parse_issue_url(identifier)
    if result:
        return result

    # Try parsing as short format: owner/repo#123 or group/project#42
    short_pattern = r'^([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)#(\d+)$'
    match = re.match(short_pattern, identifier)
    if match:
        repository, number = match.groups()
        # Default to GitHub for short format (most common)
        # Could be GitLab too, but without hostname we can't tell
        return ('github', repository, number)

    # Try parsing as JIRA key: PROJECT-123
    jira_pattern = r'^([A-Z][A-Z0-9]*)-(\d+)$'
    match = re.match(jira_pattern, identifier)
    if match:
        issue_key = identifier
        return ('jira', '', issue_key)  # Empty repository for JIRA

    return None


def parse_issue_url(url: str) -> Optional[Tuple[str, str, str]]:
    """Parse issue URL and extract backend, repository, and issue identifier.

    Args:
        url: Full issue URL (GitHub, GitLab, or JIRA)

    Returns:
        Tuple of (backend, repository, issue_key) or None if invalid URL

        For GitHub: ('github', 'owner/repo', '123')
        For GitLab: ('gitlab', 'group/project', '123')
        For JIRA: ('jira', 'https://domain.atlassian.net', 'PROJECT-123')

    Examples:
        >>> parse_issue_url('https://github.com/itdove/devaiflow/issues/305')
        ('github', 'itdove/devaiflow', '305')

        >>> parse_issue_url('https://gitlab.com/group/project/-/issues/42')
        ('gitlab', 'group/project', '42')

        >>> parse_issue_url('https://redhat.atlassian.net/browse/AAP-70183')
        ('jira', 'https://redhat.atlassian.net', 'AAP-70183')
    """
    if not url:
        return None

    parsed = urlparse(url)

    # GitHub: https://github.com/owner/repo/issues/123
    github_pattern = r'^/([^/]+)/([^/]+)/issues/(\d+)'
    if parsed.hostname and 'github.com' in parsed.hostname:
        match = re.match(github_pattern, parsed.path)
        if match:
            owner, repo, number = match.groups()
            return ('github', f'{owner}/{repo}', number)

    # GitLab: https://gitlab.com/group/project/-/issues/123
    # Also supports: https://gitlab.cee.redhat.com/group/subgroup/project/-/issues/123
    gitlab_pattern = r'^/(.+?)/-/issues/(\d+)'
    if parsed.hostname and ('gitlab' in parsed.hostname or parsed.hostname in ['gitlab.cee.redhat.com']):
        match = re.match(gitlab_pattern, parsed.path)
        if match:
            project_path, number = match.groups()
            return ('gitlab', project_path, number)

    # JIRA: https://domain.atlassian.net/browse/PROJECT-123
    # Also supports: https://jira.company.com/browse/PROJECT-123
    jira_pattern = r'^/browse/([A-Z]+-\d+)'
    if parsed.hostname:
        match = re.match(jira_pattern, parsed.path)
        if match:
            issue_key = match.group(1)
            # Return base URL without path for JIRA
            jira_url = f'{parsed.scheme}://{parsed.hostname}'
            return ('jira', jira_url, issue_key)

    return None


def get_hostname_from_url(url: str) -> Optional[str]:
    """Extract hostname from URL.

    Args:
        url: Full URL

    Returns:
        Hostname or None if invalid

    Examples:
        >>> get_hostname_from_url('https://gitlab.cee.redhat.com/group/project')
        'gitlab.cee.redhat.com'
    """
    if not url:
        return None

    parsed = urlparse(url)
    return parsed.hostname
