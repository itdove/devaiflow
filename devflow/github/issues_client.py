"""GitHub Issues client implementing IssueTrackerClient interface.

This module provides a GitHub Issues backend for DevAIFlow's issue tracker abstraction.
Uses the `gh` CLI for all GitHub API operations.

Key differences from JIRA:
- Uses convention-based labels instead of custom fields
- Binary state (open/closed) instead of complex workflows
- No file attachments (GitHub doesn't support file uploads to issues)
- PR linking happens automatically via issue references
"""

import json
import re
import subprocess
from typing import Dict, List, Optional

from devflow.issue_tracker.interface import IssueTrackerClient
from devflow.issue_tracker.exceptions import (
    IssueTrackerApiError,
    IssueTrackerAuthError,
    IssueTrackerConnectionError,
    IssueTrackerNotFoundError,
    IssueTrackerValidationError,
    IssueTrackerConfigError,
)
from devflow.github.field_mapper import GitHubFieldMapper
from devflow.utils.git_remote import GitRemoteDetector


class GitHubClient(IssueTrackerClient):
    """GitHub implementation of IssueTrackerClient.

    Uses `gh api` CLI for all GitHub API operations. Requires:
    - GitHub CLI (`gh`) installed and authenticated
    - GITHUB_TOKEN environment variable OR `gh auth login`
    """

    def __new__(cls, timeout: int = 30, repository: Optional[str] = None):
        """Create GitHub client or mock client based on environment.

        Args:
            timeout: Request timeout in seconds
            repository: Default repository in owner/repo format

        Returns:
            GitHubClient instance or MockIssueTrackerClient in mock mode
        """
        import os
        if os.getenv("DAF_MOCK_MODE") == "1":
            from devflow.issue_tracker.mock_client import MockIssueTrackerClient
            return MockIssueTrackerClient(timeout=timeout)
        return super().__new__(cls)

    def __init__(self, timeout: int = 30, repository: Optional[str] = None):
        """Initialize GitHub Issues client.

        Args:
            timeout: Request timeout in seconds
            repository: Default repository in owner/repo format (e.g., "ansible-saas/devaiflow")
        """
        # Only initialize if this is actually a GitHubClient instance
        # (not a MockIssueTrackerClient returned from __new__)
        if isinstance(self, GitHubClient):
            self.timeout = timeout
            self.repository = repository
            self.field_mapper = GitHubFieldMapper()

    def _run_gh_command(self, args: List[str]) -> str:
        """Run a gh CLI command and return output.

        Args:
            args: Command arguments (after 'gh')

        Returns:
            Command output as string

        Raises:
            IssueTrackerAuthError: If authentication fails (exit code 4)
            IssueTrackerConnectionError: If connection fails
            IssueTrackerApiError: If command fails
        """
        cmd = ['gh'] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False
            )

            if result.returncode == 0:
                return result.stdout

            # Parse error codes
            stderr = result.stderr

            # Authentication error
            if result.returncode == 4 or 'authentication' in stderr.lower():
                raise IssueTrackerAuthError(
                    f"GitHub authentication failed. Run 'gh auth login' or set GITHUB_TOKEN.",
                    status_code=401
                )

            # Connection error
            if 'connection' in stderr.lower() or 'timeout' in stderr.lower():
                raise IssueTrackerConnectionError(
                    f"Failed to connect to GitHub API: {stderr}"
                )

            # API error
            raise IssueTrackerApiError(
                f"GitHub API command failed: {' '.join(cmd)}",
                status_code=result.returncode,
                response_text=stderr
            )

        except subprocess.TimeoutExpired:
            raise IssueTrackerConnectionError(
                f"GitHub API request timed out after {self.timeout} seconds"
            )
        except FileNotFoundError:
            raise IssueTrackerConfigError(
                "GitHub CLI (gh) not found. Install it from https://cli.github.com/"
            )

    def _parse_issue_number(self, issue_key: str) -> tuple[str, int]:
        """Parse issue key into repository and issue number.

        Args:
            issue_key: Issue key in format "#123" or "owner/repo#123"

        Returns:
            Tuple of (repository, issue_number)

        Raises:
            IssueTrackerValidationError: If format is invalid

        Examples:
            >>> client._parse_issue_number("#123")
            (None, 123)  # Uses default repository
            >>> client._parse_issue_number("owner/repo#123")
            ('owner/repo', 123)
        """
        # Format: owner/repo#123
        match = re.match(r'^([\w-]+/[\w.-]+)#(\d+)$', issue_key)
        if match:
            return match.group(1), int(match.group(2))

        # Format: #123
        match = re.match(r'^#?(\d+)$', issue_key)
        if match:
            return None, int(match.group(1))  # Use default repository

        raise IssueTrackerValidationError(
            f"Invalid GitHub issue key format: {issue_key}. "
            f"Expected '#123' or 'owner/repo#123'"
        )

    def _get_repository(self, repository: Optional[str] = None) -> str:
        """Get repository name, using default if not provided.

        Args:
            repository: Optional repository override

        Returns:
            Repository in owner/repo format

        Raises:
            IssueTrackerConfigError: If no repository specified or auto-detection fails

        Note:
            Auto-detects repository from git remotes if not configured.
            Priority: upstream (for forks) → origin (for direct repos)
        """
        repo = repository or self.repository

        # Auto-detect from git remote if not configured
        if not repo:
            detector = GitRemoteDetector()
            repo = detector.get_github_repository()

            if not repo:
                raise IssueTrackerConfigError(
                    "No GitHub repository specified and auto-detection failed. "
                    "Either:\n"
                    "  1. Set repository in config (daf config tui)\n"
                    "  2. Ensure you're in a git repository with GitHub remote\n"
                    "  3. Pass repository explicitly (e.g., owner/repo#123)"
                )

        return repo

    def get_ticket(self, issue_key: str, field_mappings: Optional[Dict] = None) -> Dict:
        """Fetch a GitHub issue by number.

        Args:
            issue_key: Issue key ("#123" or "owner/repo#123")
            field_mappings: Ignored (GitHub uses labels, not custom fields)

        Returns:
            Standardized ticket dictionary

        Raises:
            IssueTrackerNotFoundError: If issue not found
            IssueTrackerApiError: If API request fails
        """
        repo, number = self._parse_issue_number(issue_key)
        repo = self._get_repository(repo)

        try:
            # Use gh api to fetch issue
            output = self._run_gh_command([
                'api',
                f'/repos/{repo}/issues/{number}',
                '--jq', '.'
            ])

            issue_data = json.loads(output)
            return self.field_mapper.map_github_to_interface(issue_data, repository=repo)

        except IssueTrackerApiError as e:
            if 'Not Found' in str(e) or '404' in str(e):
                raise IssueTrackerNotFoundError(
                    f"GitHub issue {repo}#{number} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            raise

    def get_ticket_detailed(
        self, issue_key: str, field_mappings: Optional[Dict] = None, include_changelog: bool = False
    ) -> Dict:
        """Fetch detailed GitHub issue information.

        Args:
            issue_key: Issue key ("#123" or "owner/repo#123")
            field_mappings: Ignored (GitHub uses labels)
            include_changelog: If True, fetch events/comments

        Returns:
            Detailed ticket dictionary with comments/events if requested
        """
        # Get basic issue data
        ticket = self.get_ticket(issue_key, field_mappings)

        if include_changelog:
            repo, number = self._parse_issue_number(issue_key)
            repo = self._get_repository(repo)

            # Fetch comments
            try:
                comments_output = self._run_gh_command([
                    'api',
                    f'/repos/{repo}/issues/{number}/comments',
                    '--jq', '.'
                ])
                comments = json.loads(comments_output)
                ticket['comments'] = [
                    {
                        'author': c.get('user', {}).get('login'),
                        'body': c.get('body', ''),
                        'created': c.get('created_at'),
                    }
                    for c in comments
                ]
            except Exception:
                ticket['comments'] = []

            # Fetch events (timeline)
            try:
                events_output = self._run_gh_command([
                    'api',
                    f'/repos/{repo}/issues/{number}/events',
                    '--jq', '.'
                ])
                events = json.loads(events_output)
                ticket['events'] = events
            except Exception:
                ticket['events'] = []

        return ticket

    def list_tickets(
        self,
        jql: Optional[str] = None,
        project: Optional[str] = None,
        assignee: Optional[str] = None,
        status: Optional[List[str]] = None,
        issue_type: Optional[List[str]] = None,
        sprint: Optional[str] = None,
        max_results: int = 50,
        start_at: int = 0,
        field_mappings: Optional[Dict] = None,
    ) -> List[Dict]:
        """List GitHub issues matching criteria.

        Args:
            jql: Ignored (GitHub doesn't use JQL)
            project: Repository in owner/repo format
            assignee: GitHub username
            status: List of states ("open", "closed")
            issue_type: List of labels (bug, enhancement, etc.)
            sprint: Milestone name
            max_results: Maximum results to return (default: 50, max: 100)
            start_at: Pagination page number (1-indexed)
            field_mappings: Ignored

        Returns:
            List of ticket dictionaries
        """
        repo = self._get_repository(project)

        # Calculate page number (start_at is 0-indexed, GitHub pages are 1-indexed)
        page = (start_at // max_results) + 1

        try:
            # Use Issues API instead of Search API for better reliability
            # The Issues API works for both public and private repos
            # Build query parameters
            params = [
                f'per_page={min(max_results, 100)}',
                f'page={page}',
            ]

            # Add state filter
            if status:
                # GitHub API accepts "open", "closed", or "all"
                if 'open' in [s.lower() for s in status]:
                    params.append('state=open')
                elif 'closed' in [s.lower() for s in status]:
                    params.append('state=closed')
                else:
                    params.append('state=all')
            else:
                params.append('state=open')  # Default to open

            # Add assignee filter
            if assignee:
                params.append(f'assignee={assignee}')

            # Add labels filter
            if issue_type:
                labels = []
                for itype in issue_type:
                    label = itype.lower()
                    if label == 'story':
                        label = 'enhancement'
                    labels.append(label)
                params.append(f'labels={",".join(labels)}')

            # Add milestone filter
            if sprint:
                params.append(f'milestone={sprint}')

            # Build full URL with query parameters
            url = f'/repos/{repo}/issues?{"&".join(params)}'

            # Debug: Log the API call
            import os
            if os.environ.get('DAF_DEBUG'):
                print(f"[DEBUG] GitHub API call: gh api '{url}'")

            output = self._run_gh_command(['api', url])
            issues = json.loads(output)

            # Debug: Log result count
            if os.environ.get('DAF_DEBUG'):
                print(f"[DEBUG] Found {len(issues)} issues")

            return [self.field_mapper.map_github_to_interface(issue, repository=repo) for issue in issues]

        except Exception as e:
            # Debug: Log errors
            import os
            if os.environ.get('DAF_DEBUG'):
                print(f"[DEBUG] GitHub API error: {e}")
            # Return empty list if API call fails (graceful degradation)
            return []

    def create_issue(
        self,
        issue_type: Optional[str],
        summary: str,
        description: str,
        priority: str,
        project_key: str,
        field_mapper,
        parent: Optional[str] = None,
        components: Optional[list] = None,
        required_custom_fields: Optional[dict] = None,
        **custom_fields
    ) -> str:
        """Create a GitHub issue.

        Args:
            issue_type: Optional issue type (Bug, Story, Task, Epic, Spike). If None, no type label is added
            summary: Issue title
            description: Issue body
            priority: Priority level (Critical, Major, Normal, Minor)
            project_key: Repository in owner/repo format
            field_mapper: Field mapper instance
            parent: Parent issue number (optional)
            components: Ignored (GitHub doesn't have components)
            required_custom_fields: Additional fields (acceptance_criteria, etc.)
            **custom_fields: Ignored

        Returns:
            Created issue key (e.g., "owner/repo#123")
        """
        repo = self._get_repository(project_key)

        # Build ticket data
        ticket_data = {
            'summary': summary,
            'description': description,
            'type': issue_type.lower() if issue_type else None,
            'priority': priority.lower() if priority else None,
        }

        # Add acceptance criteria if provided
        if required_custom_fields and 'acceptance_criteria' in required_custom_fields:
            ticket_data['acceptance_criteria'] = required_custom_fields['acceptance_criteria']

        # Add additional labels if provided
        if required_custom_fields and 'labels' in required_custom_fields:
            ticket_data['labels'] = required_custom_fields['labels']

        # Convert to GitHub format
        payload = self.field_mapper.map_interface_to_github(ticket_data)

        # Create issue via gh CLI
        try:
            payload_json = json.dumps(payload)
            output = self._run_gh_command_with_input([
                'api',
                f'/repos/{repo}/issues',
                '--method', 'POST',
                '--input', '-',
                '--jq', '.number'
            ], payload_json)

            issue_number = output.strip()
            return f'{repo}#{issue_number}'

        except IssueTrackerApiError as e:
            # Check for validation errors
            if '422' in str(e) or 'Validation Failed' in str(e):
                raise IssueTrackerValidationError(
                    f"Failed to create GitHub issue: {e}",
                    field_errors={}
                )
            raise

    def _run_gh_command_with_input(self, args: List[str], input_data: str) -> str:
        """Run gh command with stdin input.

        Args:
            args: Command arguments
            input_data: Data to pass via stdin

        Returns:
            Command output
        """
        cmd = ['gh'] + args

        try:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False
            )

            if result.returncode == 0:
                return result.stdout

            stderr = result.stderr

            if result.returncode == 4 or 'authentication' in stderr.lower():
                raise IssueTrackerAuthError(
                    "GitHub authentication failed",
                    status_code=401
                )

            raise IssueTrackerApiError(
                f"GitHub API command failed: {stderr}",
                status_code=result.returncode,
                response_text=stderr
            )

        except subprocess.TimeoutExpired:
            raise IssueTrackerConnectionError(
                f"GitHub API request timed out"
            )

    def update_issue(self, issue_key: str, payload: Dict) -> None:
        """Update a GitHub issue.

        Args:
            issue_key: Issue key ("#123" or "owner/repo#123")
            payload: Update payload (GitHub format)
        """
        repo, number = self._parse_issue_number(issue_key)
        repo = self._get_repository(repo)

        try:
            payload_json = json.dumps(payload)
            self._run_gh_command_with_input([
                'api',
                f'/repos/{repo}/issues/{number}',
                '--method', 'PATCH',
                '--input', '-'
            ], payload_json)

        except IssueTrackerApiError as e:
            if 'Not Found' in str(e):
                raise IssueTrackerNotFoundError(
                    f"GitHub issue {repo}#{number} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            raise

    def update_ticket_field(self, issue_key: str, field_name: str, value: str) -> None:
        """Update a single field on a GitHub issue.

        Args:
            issue_key: Issue key
            field_name: Field to update (title, body, state, labels)
            value: New value
        """
        payload = {field_name: value}
        self.update_issue(issue_key, payload)

    def add_comment(self, issue_key: str, comment: str, public: bool = False) -> None:
        """Add a comment to a GitHub issue.

        Args:
            issue_key: Issue key
            comment: Comment text
            public: Ignored (all GitHub comments are public to collaborators)
        """
        repo, number = self._parse_issue_number(issue_key)
        repo = self._get_repository(repo)

        payload = json.dumps({'body': comment})

        try:
            self._run_gh_command_with_input([
                'api',
                f'/repos/{repo}/issues/{number}/comments',
                '--method', 'POST',
                '--input', '-'
            ], payload)

        except IssueTrackerApiError as e:
            if 'Not Found' in str(e):
                raise IssueTrackerNotFoundError(
                    f"GitHub issue {repo}#{number} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            raise

    def transition_ticket(self, issue_key: str, status: str) -> None:
        """Transition a GitHub issue state.

        Args:
            issue_key: Issue key
            status: Target status ("open" or "closed")
        """
        # Normalize status
        status_lower = status.lower()
        if status_lower in ['open', 'reopen']:
            state = 'open'
        elif status_lower in ['close', 'closed', 'done', 'resolved']:
            state = 'closed'
        else:
            # Unknown status - try as-is
            state = status_lower

        self.update_issue(issue_key, {'state': state})

    def attach_file(self, issue_key: str, file_path: str) -> None:
        """Attach a file to a GitHub issue.

        GitHub Issues don't support direct file attachments.
        This method raises NotImplementedError.

        Args:
            issue_key: Issue key
            file_path: Path to file

        Raises:
            NotImplementedError: GitHub doesn't support file attachments
        """
        raise NotImplementedError(
            "GitHub Issues do not support file attachments. "
            "Consider adding the file content as a comment or uploading to a gist."
        )

    def get_ticket_pr_links(self, issue_key: str, field_mappings: Optional[Dict] = None) -> str:
        """Get PR links associated with a GitHub issue.

        GitHub automatically links PRs that reference issues.
        This method extracts PR URLs from the issue's timeline.

        Args:
            issue_key: Issue key
            field_mappings: Ignored

        Returns:
            Comma-separated PR URLs
        """
        repo, number = self._parse_issue_number(issue_key)
        repo = self._get_repository(repo)

        try:
            # Fetch timeline events
            output = self._run_gh_command([
                'api',
                f'/repos/{repo}/issues/{number}/timeline',
                '--jq', '.'
            ])

            events = json.loads(output)

            # Extract PR references
            pr_urls = []
            for event in events:
                if event.get('event') == 'cross-referenced':
                    source = event.get('source', {})
                    if source.get('type') == 'issue' and 'pull_request' in source.get('issue', {}):
                        pr_urls.append(source['issue']['html_url'])

            return ','.join(pr_urls)

        except Exception:
            return ''

    def get_child_issues(
        self,
        parent_key: str,
        issue_types: Optional[List[str]] = None,
        field_mappings: Optional[Dict] = None,
    ) -> List[Dict]:
        """Get child issues of a parent GitHub issue.

        GitHub doesn't have native parent-child relationships.
        This searches for issues that reference the parent.

        Args:
            parent_key: Parent issue key
            issue_types: Filter by issue types (labels)
            field_mappings: Ignored

        Returns:
            List of child issue dictionaries
        """
        repo, number = self._parse_issue_number(parent_key)
        repo = self._get_repository(repo)

        # Search for issues referencing this one
        query = f'repo:{repo} {parent_key} in:body'

        if issue_types:
            for itype in issue_types:
                label = itype.lower()
                if label == 'story':
                    label = 'enhancement'
                query += f' label:{label}'

        try:
            output = self._run_gh_command([
                'api',
                '/search/issues',
                '-f', f'q={query}',
                '--jq', '.items'
            ])

            issues = json.loads(output)
            return [self.field_mapper.map_github_to_interface(issue, repository=repo) for issue in issues]

        except Exception:
            return []

    def get_issue_link_types(self) -> List[Dict]:
        """Get available GitHub issue link types.

        GitHub supports simple issue references, not typed links like JIRA.

        Returns:
            List with single generic reference type
        """
        return [
            {
                'id': 'reference',
                'name': 'Reference',
                'inward': 'referenced by',
                'outward': 'references',
            }
        ]

    def link_issues(
        self, issue_key: str, link_type: str, linked_issue_key: str, comment: Optional[str] = None
    ) -> None:
        """Create a link between two GitHub issues.

        GitHub doesn't have explicit issue links. This adds a comment
        mentioning the linked issue, which creates an automatic reference.

        Args:
            issue_key: Source issue key
            link_type: Ignored (GitHub only has references)
            linked_issue_key: Target issue key to reference
            comment: Optional additional comment text
        """
        # Add a comment that references the other issue
        reference_text = f"Related to {linked_issue_key}"
        if comment:
            reference_text = f"{reference_text}\n\n{comment}"

        self.add_comment(issue_key, reference_text, public=True)
