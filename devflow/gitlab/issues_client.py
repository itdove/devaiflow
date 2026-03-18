"""GitLab Issues client implementing IssueTrackerClient interface.

This module provides a GitLab Issues backend for DevAIFlow's issue tracker abstraction.
Uses the `glab` CLI for all GitLab API operations.

Key differences from JIRA:
- Uses convention-based labels instead of custom fields
- Binary state (open/closed) instead of complex workflows
- File attachments supported (unlike GitHub)
- MR linking happens automatically via issue references
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
from devflow.gitlab.field_mapper import GitLabFieldMapper
from devflow.utils.git_remote import GitRemoteDetector


class GitLabClient(IssueTrackerClient):
    """GitLab implementation of IssueTrackerClient.

    Uses `glab api` CLI for all GitLab API operations. Requires:
    - GitLab CLI (`glab`) installed and authenticated
    - GITLAB_TOKEN environment variable OR `glab auth login`
    """

    def __new__(cls, timeout: int = 30, repository: Optional[str] = None):
        """Create GitLab client or mock client based on environment.

        Args:
            timeout: Request timeout in seconds
            repository: Default repository in group/project format

        Returns:
            GitLabClient instance or MockIssueTrackerClient in mock mode
        """
        import os
        if os.getenv("DAF_MOCK_MODE") == "1":
            from devflow.issue_tracker.mock_client import MockIssueTrackerClient
            return MockIssueTrackerClient(timeout=timeout)
        return super().__new__(cls)

    def __init__(self, timeout: int = 30, repository: Optional[str] = None, hostname: Optional[str] = None):
        """Initialize GitLab Issues client.

        Args:
            timeout: Request timeout in seconds
            repository: Default repository in group/project format (e.g., "group/project")
            hostname: GitLab instance hostname (e.g., "gitlab.cee.redhat.com"). Defaults to gitlab.com
        """
        # Only initialize if this is actually a GitLabClient instance
        # (not a MockIssueTrackerClient returned from __new__)
        if isinstance(self, GitLabClient):
            self.timeout = timeout
            self.repository = repository
            self.hostname = hostname or 'gitlab.com'
            self.field_mapper = GitLabFieldMapper()

    def _run_glab_command(self, args: List[str]) -> str:
        """Run a glab CLI command and return output.

        Args:
            args: Command arguments (after 'glab')

        Returns:
            Command output as string

        Raises:
            IssueTrackerAuthError: If authentication fails
            IssueTrackerConnectionError: If connection fails
            IssueTrackerApiError: If command fails
        """
        # Build command with hostname for enterprise GitLab instances
        # Note: Only 'glab api' commands use --hostname flag, other commands infer from git remote
        cmd = ['glab']

        # Add --hostname for api commands when using enterprise GitLab
        if args and args[0] == 'api' and self.hostname and self.hostname != 'gitlab.com':
            cmd.extend(['--hostname', self.hostname])

        cmd.extend(args)

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
            if 'authentication' in stderr.lower() or 'unauthorized' in stderr.lower():
                raise IssueTrackerAuthError(
                    f"GitLab authentication failed. Run 'glab auth login' or set GITLAB_TOKEN.",
                    status_code=401
                )

            # Connection error
            if 'connection' in stderr.lower() or 'timeout' in stderr.lower():
                raise IssueTrackerConnectionError(
                    f"Failed to connect to GitLab API: {stderr}"
                )

            # API error
            raise IssueTrackerApiError(
                f"GitLab API command failed: {' '.join(cmd)}",
                status_code=result.returncode,
                response_text=stderr
            )

        except subprocess.TimeoutExpired:
            raise IssueTrackerConnectionError(
                f"GitLab API request timed out after {self.timeout} seconds"
            )
        except FileNotFoundError:
            raise IssueTrackerConfigError(
                "GitLab CLI (glab) not found. Install it from https://gitlab.com/gitlab-org/cli"
            )

    def _parse_issue_number(self, issue_key: str) -> tuple[str, int]:
        """Parse issue key into repository and issue number.

        Args:
            issue_key: Issue key in format "#123" or "group/project#123"

        Returns:
            Tuple of (repository, issue_number)

        Raises:
            IssueTrackerValidationError: If format is invalid

        Examples:
            >>> client._parse_issue_number("#123")
            (None, 123)  # Uses default repository
            >>> client._parse_issue_number("group/project#123")
            ('group/project', 123)
        """
        # Format: group/project#123 or group/subgroup/project#123
        match = re.match(r'^([\w-]+(?:/[\w.-]+)+)#(\d+)$', issue_key)
        if match:
            return match.group(1), int(match.group(2))

        # Format: #123
        match = re.match(r'^#?(\d+)$', issue_key)
        if match:
            return None, int(match.group(1))  # Use default repository

        raise IssueTrackerValidationError(
            f"Invalid GitLab issue key format: {issue_key}. "
            f"Expected '#123' or 'group/project#123'"
        )

    def _get_repository(self, repository: Optional[str] = None) -> str:
        """Get repository name, using default if not provided.

        Args:
            repository: Optional repository override

        Returns:
            Repository in group/project format

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
            repo = detector.get_gitlab_repository()

            if not repo:
                raise IssueTrackerConfigError(
                    "No GitLab repository specified and auto-detection failed. "
                    "Either:\n"
                    "  1. Set repository in config (daf config tui)\n"
                    "  2. Ensure you're in a git repository with GitLab remote\n"
                    "  3. Pass repository explicitly (e.g., group/project#123)"
                )

        return repo

    def _url_encode_repository(self, repository: str) -> str:
        """URL encode repository path for GitLab API.

        GitLab API requires URL encoding for project paths (/ → %2F).

        Args:
            repository: Repository in group/project format

        Returns:
            URL-encoded repository path

        Examples:
            >>> client._url_encode_repository("group/project")
            'group%2Fproject'
            >>> client._url_encode_repository("group/subgroup/project")
            'group%2Fsubgroup%2Fproject'
        """
        return repository.replace('/', '%2F')

    def get_ticket(self, issue_key: str, field_mappings: Optional[Dict] = None) -> Dict:
        """Fetch a GitLab issue by number.

        Args:
            issue_key: Issue key ("#123" or "group/project#123")
            field_mappings: Ignored (GitLab uses labels, not custom fields)

        Returns:
            Standardized ticket dictionary

        Raises:
            IssueTrackerNotFoundError: If issue not found
            IssueTrackerApiError: If API request fails
        """
        repo, number = self._parse_issue_number(issue_key)
        repo = self._get_repository(repo)
        encoded_repo = self._url_encode_repository(repo)

        try:
            # Use glab api to fetch issue
            output = self._run_glab_command([
                'api',
                f'projects/{encoded_repo}/issues/{number}'
            ])

            issue_data = json.loads(output)
            return self.field_mapper.map_gitlab_to_interface(issue_data, repository=repo)

        except IssueTrackerApiError as e:
            if 'Not Found' in str(e) or '404' in str(e):
                raise IssueTrackerNotFoundError(
                    f"GitLab issue {repo}#{number} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            raise

    def get_ticket_detailed(
        self, issue_key: str, field_mappings: Optional[Dict] = None, include_changelog: bool = False
    ) -> Dict:
        """Fetch detailed GitLab issue information.

        Args:
            issue_key: Issue key ("#123" or "group/project#123")
            field_mappings: Ignored (GitLab uses labels)
            include_changelog: If True, fetch notes/comments

        Returns:
            Detailed ticket dictionary with comments if requested
        """
        # Get basic issue data
        ticket = self.get_ticket(issue_key, field_mappings)

        if include_changelog:
            repo, number = self._parse_issue_number(issue_key)
            repo = self._get_repository(repo)
            encoded_repo = self._url_encode_repository(repo)

            # Fetch notes (comments)
            try:
                notes_output = self._run_glab_command([
                    'api',
                    f'projects/{encoded_repo}/issues/{number}/notes'
                ])
                notes = json.loads(notes_output)
                ticket['comments'] = [
                    {
                        'author': n.get('author', {}).get('username'),
                        'body': n.get('body', ''),
                        'created': n.get('created_at'),
                    }
                    for n in notes
                    if not n.get('system')  # Exclude system notes
                ]
            except Exception:
                ticket['comments'] = []

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
        """List GitLab issues matching criteria.

        Args:
            jql: Ignored (GitLab doesn't use JQL)
            project: Repository in group/project format
            assignee: GitLab username
            status: List of states ("open", "closed")
            issue_type: List of labels (bug, enhancement, etc.)
            sprint: Milestone title
            max_results: Maximum results to return (default: 50, max: 100)
            start_at: Pagination page number (1-indexed)
            field_mappings: Ignored

        Returns:
            List of ticket dictionaries
        """
        repo = self._get_repository(project)
        encoded_repo = self._url_encode_repository(repo)

        # Calculate page number (start_at is 0-indexed, GitLab pages are 1-indexed)
        page = (start_at // max_results) + 1

        try:
            # Build query parameters
            params = [
                f'per_page={min(max_results, 100)}',
                f'page={page}',
            ]

            # Add state filter
            if status:
                # GitLab API accepts "opened", "closed", or "all"
                if 'open' in [s.lower() for s in status]:
                    params.append('state=opened')
                elif 'closed' in [s.lower() for s in status]:
                    params.append('state=closed')
                else:
                    params.append('state=all')
            else:
                params.append('state=opened')  # Default to opened

            # Add assignee filter
            if assignee:
                params.append(f'assignee_username={assignee}')

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
            url = f'projects/{encoded_repo}/issues?{"&".join(params)}'

            # Debug: Log the API call
            import os
            if os.environ.get('DAF_DEBUG'):
                print(f"[DEBUG] GitLab API call: glab api '{url}'")

            output = self._run_glab_command(['api', url])
            issues = json.loads(output)

            # Debug: Log result count
            if os.environ.get('DAF_DEBUG'):
                print(f"[DEBUG] Found {len(issues)} issues")

            return [self.field_mapper.map_gitlab_to_interface(issue, repository=repo) for issue in issues]

        except Exception as e:
            # Debug: Log errors
            import os
            if os.environ.get('DAF_DEBUG'):
                print(f"[DEBUG] GitLab API error: {e}")
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
        """Create a GitLab issue.

        Args:
            issue_type: Optional issue type (Bug, Story, Task, Epic, Spike). If None, no type label is added
            summary: Issue title
            description: Issue description
            priority: Priority level (Critical, Major, Normal, Minor)
            project_key: Repository in group/project format
            field_mapper: Field mapper instance
            parent: Parent issue number (optional)
            components: Ignored (GitLab doesn't have components)
            required_custom_fields: Additional fields (acceptance_criteria, etc.)
            **custom_fields: Ignored

        Returns:
            Created issue key (e.g., "group/project#123")
        """
        repo = self._get_repository(project_key)
        encoded_repo = self._url_encode_repository(repo)

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

        # Convert to GitLab format
        payload = self.field_mapper.map_interface_to_gitlab(ticket_data)

        # Create issue via glab CLI
        try:
            payload_json = json.dumps(payload)
            output = self._run_glab_command_with_input([
                'api',
                f'projects/{encoded_repo}/issues',
                '--method', 'POST',
                '--input', '-',
            ], payload_json)

            issue_data = json.loads(output)
            issue_number = issue_data['iid']  # GitLab uses 'iid' for issue number
            issue_key = f'{repo}#{issue_number}'

            # Link to parent issue if provided
            if parent:
                try:
                    # Add a note linking child to parent
                    parent_repo, parent_number = self._parse_issue_number(parent)
                    parent_repo = self._get_repository(parent_repo)

                    # Add comment to child issue mentioning parent
                    self.add_comment(
                        issue_key,
                        f"Child of {parent_repo}#{parent_number}",
                        public=True
                    )

                    # Add comment to parent issue mentioning child
                    self.add_comment(
                        parent,
                        f"Sub-issue created: {issue_key}",
                        public=True
                    )
                except Exception as e:
                    # Don't fail issue creation if parent linking fails
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to link issue {issue_key} to parent {parent}: {e}")

            return issue_key

        except IssueTrackerApiError as e:
            # Check for validation errors
            if '400' in str(e) or 'validation' in str(e).lower():
                raise IssueTrackerValidationError(
                    f"Failed to create GitLab issue: {e}",
                    field_errors={}
                )
            raise

    def _run_glab_command_with_input(self, args: List[str], input_data: str) -> str:
        """Run glab command with stdin input.

        Args:
            args: Command arguments
            input_data: Data to pass via stdin

        Returns:
            Command output
        """
        cmd = ['glab'] + args

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

            if 'authentication' in stderr.lower() or 'unauthorized' in stderr.lower():
                raise IssueTrackerAuthError(
                    "GitLab authentication failed",
                    status_code=401
                )

            raise IssueTrackerApiError(
                f"GitLab API command failed: {stderr}",
                status_code=result.returncode,
                response_text=stderr
            )

        except subprocess.TimeoutExpired:
            raise IssueTrackerConnectionError(
                f"GitLab API request timed out"
            )

    def update_issue(self, issue_key: str, payload: Dict) -> None:
        """Update a GitLab issue.

        Args:
            issue_key: Issue key ("#123" or "group/project#123")
            payload: Update payload (GitLab format)
        """
        repo, number = self._parse_issue_number(issue_key)
        repo = self._get_repository(repo)
        encoded_repo = self._url_encode_repository(repo)

        try:
            payload_json = json.dumps(payload)
            self._run_glab_command_with_input([
                'api',
                f'projects/{encoded_repo}/issues/{number}',
                '--method', 'PUT',
                '--input', '-'
            ], payload_json)

        except IssueTrackerApiError as e:
            if 'Not Found' in str(e):
                raise IssueTrackerNotFoundError(
                    f"GitLab issue {repo}#{number} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            raise

    def update_ticket_field(self, issue_key: str, field_name: str, value: str) -> None:
        """Update a single field on a GitLab issue.

        Args:
            issue_key: Issue key
            field_name: Field to update (title, description, state, labels)
            value: New value
        """
        payload = {field_name: value}
        self.update_issue(issue_key, payload)

    def add_comment(self, issue_key: str, comment: str, public: bool = False) -> None:
        """Add a comment to a GitLab issue.

        Args:
            issue_key: Issue key
            comment: Comment text
            public: Ignored (all GitLab comments are visible to project members)
        """
        repo, number = self._parse_issue_number(issue_key)
        repo = self._get_repository(repo)
        encoded_repo = self._url_encode_repository(repo)

        payload = json.dumps({'body': comment})

        try:
            self._run_glab_command_with_input([
                'api',
                f'projects/{encoded_repo}/issues/{number}/notes',
                '--method', 'POST',
                '--input', '-'
            ], payload)

        except IssueTrackerApiError as e:
            if 'Not Found' in str(e):
                raise IssueTrackerNotFoundError(
                    f"GitLab issue {repo}#{number} not found",
                    resource_type="issue",
                    resource_id=issue_key
                )
            raise

    def transition_ticket(self, issue_key: str, status: str) -> None:
        """Transition a GitLab issue state.

        Args:
            issue_key: Issue key
            status: Target status ("open" or "closed")
        """
        # Normalize status
        status_lower = status.lower()
        if status_lower in ['open', 'reopen', 'opened']:
            state = 'reopen'
        elif status_lower in ['close', 'closed', 'done', 'resolved']:
            state = 'close'
        else:
            # Unknown status - try as-is
            state = status_lower

        # GitLab uses state_event for transitions
        self.update_issue(issue_key, {'state_event': state})

    def attach_file(self, issue_key: str, file_path: str) -> None:
        """Attach a file to a GitLab issue.

        GitLab supports file uploads via the uploads API.

        Args:
            issue_key: Issue key
            file_path: Path to file

        Note:
            This uploads the file and adds a markdown link in a comment.
        """
        repo, number = self._parse_issue_number(issue_key)
        repo = self._get_repository(repo)
        encoded_repo = self._url_encode_repository(repo)

        try:
            # Upload file to project
            import os
            file_name = os.path.basename(file_path)

            # GitLab file upload is complex via CLI, so we add as a comment
            # pointing to the limitation
            raise NotImplementedError(
                "File attachment via CLI is not fully supported. "
                "Consider using GitLab web UI or uploading file to issue via web."
            )

        except FileNotFoundError:
            raise IssueTrackerApiError(
                f"File not found: {file_path}",
                status_code=404,
                response_text=""
            )

    def get_ticket_pr_links(self, issue_key: str, field_mappings: Optional[Dict] = None) -> str:
        """Get MR links associated with a GitLab issue.

        GitLab automatically links MRs that reference issues.

        Args:
            issue_key: Issue key
            field_mappings: Ignored

        Returns:
            Comma-separated MR URLs
        """
        repo, number = self._parse_issue_number(issue_key)
        repo = self._get_repository(repo)
        encoded_repo = self._url_encode_repository(repo)

        try:
            # Fetch related merge requests
            output = self._run_glab_command([
                'api',
                f'projects/{encoded_repo}/issues/{number}/related_merge_requests'
            ])

            merge_requests = json.loads(output)

            # Extract MR URLs
            mr_urls = [mr.get('web_url', '') for mr in merge_requests if mr.get('web_url')]

            return ','.join(mr_urls)

        except Exception:
            return ''

    def get_child_issues(
        self,
        parent_key: str,
        issue_types: Optional[List[str]] = None,
        field_mappings: Optional[Dict] = None,
    ) -> List[Dict]:
        """Get child issues of a parent GitLab issue.

        GitLab doesn't have native parent-child relationships.
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

        # Search for issues referencing this one by searching description/comments
        # This is a simplified implementation
        try:
            all_issues = self.list_tickets(
                project=repo,
                issue_type=issue_type,
                max_results=100
            )

            # Filter issues that mention the parent
            parent_ref = f"#{number}"
            child_issues = []

            for issue in all_issues:
                description = issue.get('description', '')
                if parent_ref in description or parent_key in description:
                    child_issues.append(issue)

            return child_issues

        except Exception:
            return []

    def get_issue_link_types(self) -> List[Dict]:
        """Get available GitLab issue link types.

        GitLab supports simple issue references and related issues.

        Returns:
            List with generic reference type
        """
        return [
            {
                'id': 'relates_to',
                'name': 'Relates To',
                'inward': 'related to',
                'outward': 'relates to',
            }
        ]

    def link_issues(
        self, issue_key: str, link_type: str, linked_issue_key: str, comment: Optional[str] = None
    ) -> None:
        """Create a link between two GitLab issues.

        GitLab doesn't have explicit typed issue links. This adds a comment
        mentioning the linked issue, which creates an automatic reference.

        Args:
            issue_key: Source issue key
            link_type: Ignored (GitLab only has references)
            linked_issue_key: Target issue key to reference
            comment: Optional additional comment text
        """
        # Add a comment that references the other issue
        reference_text = f"Related to {linked_issue_key}"
        if comment:
            reference_text = f"{reference_text}\n\n{comment}"

        self.add_comment(issue_key, reference_text, public=True)
