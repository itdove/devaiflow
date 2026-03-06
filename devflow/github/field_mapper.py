"""GitHub field mapper for converting between GitHub Issues and DevAIFlow interface.

GitHub uses convention-based labels instead of custom fields:
- Issue types: bug, enhancement, task, spike, epic
- Priority: priority: critical, priority: high, priority: medium, priority: low
- Story points: points: 1, points: 2, points: 3, points: 5, points: 8
- Status: status: in-progress, status: in-review, status: blocked

Acceptance criteria are stored in the issue body with HTML comment delimiters.
"""

import re
from typing import Dict, List, Optional, Any


class GitHubFieldMapper:
    """Maps GitHub issue fields to standardized DevAIFlow interface fields."""

    # Label convention patterns
    PRIORITY_PATTERN = re.compile(r'^priority:\s*(.+)$', re.IGNORECASE)
    POINTS_PATTERN = re.compile(r'^points:\s*(\d+)$', re.IGNORECASE)
    STATUS_PATTERN = re.compile(r'^status:\s*(.+)$', re.IGNORECASE)

    # Issue type labels (simple labels, not prefixed)
    ISSUE_TYPES = {
        'bug': 'bug',
        'enhancement': 'story',
        'task': 'task',
        'spike': 'spike',
        'epic': 'epic',
    }

    # Acceptance criteria delimiters
    AC_START = '<!-- ACCEPTANCE_CRITERIA_START -->'
    AC_END = '<!-- ACCEPTANCE_CRITERIA_END -->'

    def __init__(self, label_conventions: Optional[Dict[str, str]] = None):
        """Initialize field mapper.

        Args:
            label_conventions: Custom label conventions override
                              (e.g., {"bug": "type:bug", "priority_high": "pri:high"})
        """
        self.label_conventions = label_conventions or {}

    def parse_labels_to_fields(self, labels: List[str]) -> Dict[str, Any]:
        """Extract type, priority, points, and status from GitHub labels.

        Args:
            labels: List of label names

        Returns:
            Dictionary with extracted fields:
            {
                "issue_type": "bug" | "story" | "task" | "spike" | "epic",
                "priority": "critical" | "high" | "medium" | "low",
                "points": int,
                "status": "in-progress" | "in-review" | "blocked"
            }

        Examples:
            >>> mapper = GitHubFieldMapper()
            >>> mapper.parse_labels_to_fields(['bug', 'priority: high', 'points: 3'])
            {'issue_type': 'bug', 'priority': 'high', 'points': 3}
        """
        fields = {}

        for label in labels:
            label_lower = label.lower()

            # Check for issue type
            if label_lower in self.ISSUE_TYPES:
                fields['issue_type'] = self.ISSUE_TYPES[label_lower]

            # Check for priority
            priority_match = self.PRIORITY_PATTERN.match(label)
            if priority_match:
                fields['priority'] = priority_match.group(1).strip().lower()

            # Check for story points
            points_match = self.POINTS_PATTERN.match(label)
            if points_match:
                fields['points'] = int(points_match.group(1))

            # Check for status
            status_match = self.STATUS_PATTERN.match(label)
            if status_match:
                fields['status'] = status_match.group(1).strip().lower()

        return fields

    def extract_acceptance_criteria(self, body: str) -> List[str]:
        """Extract acceptance criteria from GitHub issue body.

        Args:
            body: Issue body text

        Returns:
            List of acceptance criteria items (without checkbox syntax)

        Examples:
            >>> mapper = GitHubFieldMapper()
            >>> body = '''
            ... <!-- ACCEPTANCE_CRITERIA_START -->
            ... - [ ] Criterion 1
            ... - [x] Criterion 2
            ... <!-- ACCEPTANCE_CRITERIA_END -->
            ... '''
            >>> mapper.extract_acceptance_criteria(body)
            ['Criterion 1', 'Criterion 2']
        """
        if not body:
            return []

        # Find acceptance criteria section
        start_idx = body.find(self.AC_START)
        end_idx = body.find(self.AC_END)

        if start_idx == -1 or end_idx == -1:
            return []

        # Extract section content
        ac_section = body[start_idx + len(self.AC_START):end_idx].strip()

        # Parse markdown checkbox items
        criteria = []
        for line in ac_section.split('\n'):
            line = line.strip()
            # Match both checked and unchecked boxes
            match = re.match(r'^[-*]\s*\[[ xX]\]\s*(.+)$', line)
            if match:
                criteria.append(match.group(1).strip())

        return criteria

    def format_acceptance_criteria(self, criteria: List[str]) -> str:
        """Format acceptance criteria for GitHub issue body.

        Args:
            criteria: List of acceptance criteria items (plain text or with checkbox syntax)

        Returns:
            Formatted acceptance criteria section with delimiters

        Examples:
            >>> mapper = GitHubFieldMapper()
            >>> mapper.format_acceptance_criteria(['Criterion 1', 'Criterion 2'])
            '<!-- ACCEPTANCE_CRITERIA_START -->\\n- [ ] Criterion 1\\n- [ ] Criterion 2\\n<!-- ACCEPTANCE_CRITERIA_END -->'
        """
        if not criteria:
            return ''

        items = []
        for item in criteria:
            # Handle multi-line strings (split and process each line)
            lines = item.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Remove existing checkbox syntax if present
                line = re.sub(r'^[-*]\s*\[[ xX]\]\s*', '', line)

                # Add checkbox syntax
                if line:  # Only add non-empty lines
                    items.append(f'- [ ] {line}')

        content = '\n'.join(items)
        return f'{self.AC_START}\n{content}\n{self.AC_END}'

    def inject_acceptance_criteria(self, body: str, criteria: List[str]) -> str:
        """Inject or update acceptance criteria in issue body.

        Args:
            body: Existing issue body
            criteria: List of acceptance criteria items

        Returns:
            Updated issue body with acceptance criteria

        Examples:
            >>> mapper = GitHubFieldMapper()
            >>> mapper.inject_acceptance_criteria('Description', ['Test 1'])
            'Description\\n\\n<!-- ACCEPTANCE_CRITERIA_START -->\\n- [ ] Test 1\\n<!-- ACCEPTANCE_CRITERIA_END -->'
        """
        if not criteria:
            return body

        body = body or ''
        ac_section = self.format_acceptance_criteria(criteria)

        # Check if AC section already exists
        start_idx = body.find(self.AC_START)
        end_idx = body.find(self.AC_END)

        if start_idx != -1 and end_idx != -1:
            # Replace existing section
            return body[:start_idx] + ac_section + body[end_idx + len(self.AC_END):]
        else:
            # Append to body
            separator = '\n\n' if body.strip() else ''
            return body + separator + ac_section

    def map_github_to_interface(self, issue_data: Dict, repository: Optional[str] = None) -> Dict:
        """Convert GitHub issue data to standardized interface format.

        Args:
            issue_data: GitHub issue dict from API
            repository: Optional repository in owner/repo format (e.g., "itdove/devaiflow")

        Returns:
            Standardized ticket dictionary

        Examples:
            >>> mapper = GitHubFieldMapper()
            >>> issue = {
            ...     'number': 123,
            ...     'title': 'Add feature',
            ...     'body': 'Description',
            ...     'state': 'open',
            ...     'labels': [{'name': 'bug'}, {'name': 'priority: high'}],
            ...     'assignees': [{'login': 'user1'}],
            ...     'milestone': {'title': 'v1.0'},
            ... }
            >>> result = mapper.map_github_to_interface(issue, repository='owner/repo')
            >>> result['key']
            'owner/repo#123'
            >>> result['summary']
            'Add feature'
            >>> result['type']
            'bug'
        """
        # Extract label names
        label_names = [label['name'] if isinstance(label, dict) else label
                      for label in issue_data.get('labels', [])]

        # Parse labels to fields
        parsed_fields = self.parse_labels_to_fields(label_names)

        # Extract assignees
        assignees = issue_data.get('assignees', [])
        assignee = assignees[0]['login'] if assignees else None

        # Extract milestone
        milestone = issue_data.get('milestone')
        milestone_name = milestone['title'] if milestone else None

        # Extract acceptance criteria
        body = issue_data.get('body', '')
        acceptance_criteria = self.extract_acceptance_criteria(body)

        # Build issue key with repository if provided
        issue_number = issue_data['number']
        if repository:
            issue_key = f"{repository}#{issue_number}"
        else:
            issue_key = f"#{issue_number}"

        # Map to interface format
        return {
            'key': issue_key,
            'summary': issue_data.get('title', ''),
            'description': body,
            'status': issue_data.get('state', 'open'),  # 'open' or 'closed'
            'type': parsed_fields.get('issue_type', 'task'),
            'priority': parsed_fields.get('priority'),
            'assignee': assignee,
            'sprint': milestone_name,  # Map milestone to sprint
            'points': parsed_fields.get('points'),
            'labels': label_names,
            'acceptance_criteria': acceptance_criteria,
            # GitHub-specific fields
            'milestone': milestone_name,
            'github_state': issue_data.get('state'),
            'github_number': issue_data.get('number'),
        }

    def map_interface_to_github(self, ticket_data: Dict) -> Dict:
        """Convert standardized interface format to GitHub issue data.

        Args:
            ticket_data: Standardized ticket dictionary

        Returns:
            GitHub issue creation/update payload

        Examples:
            >>> mapper = GitHubFieldMapper()
            >>> ticket = {
            ...     'summary': 'Add feature',
            ...     'description': 'Description',
            ...     'type': 'bug',
            ...     'priority': 'high',
            ...     'points': 3,
            ...     'acceptance_criteria': ['Test 1', 'Test 2'],
            ...     'assignee': 'user1',
            ...     'milestone': 'v1.0',
            ... }
            >>> result = mapper.map_interface_to_github(ticket)
            >>> result['title']
            'Add feature'
            >>> 'bug' in result['labels']
            True
            >>> 'priority: high' in result['labels']
            True
        """
        # Build labels from ticket fields
        labels = []

        # Add issue type label
        issue_type = ticket_data.get('type')
        if issue_type:
            # Reverse lookup in ISSUE_TYPES
            for label, mapped_type in self.ISSUE_TYPES.items():
                if mapped_type == issue_type:
                    labels.append(label)
                    break

        # Add priority label
        priority = ticket_data.get('priority')
        if priority:
            labels.append(f'priority: {priority}')

        # Add points label
        points = ticket_data.get('points')
        if points:
            labels.append(f'points: {points}')

        # Add status label (if not in standard state)
        status = ticket_data.get('status')
        if status and status not in ['open', 'closed']:
            labels.append(f'status: {status}')

        # Add any additional labels
        additional_labels = ticket_data.get('labels', [])
        if isinstance(additional_labels, list):
            labels.extend(additional_labels)

        # Remove duplicates while preserving order
        seen = set()
        labels = [x for x in labels if not (x in seen or seen.add(x))]

        # Inject acceptance criteria into body
        body = ticket_data.get('description', '')
        acceptance_criteria = ticket_data.get('acceptance_criteria', [])
        if acceptance_criteria:
            body = self.inject_acceptance_criteria(body, acceptance_criteria)

        # Build GitHub issue payload
        payload = {
            'title': ticket_data.get('summary', ''),
            'body': body,
            'labels': labels,
        }

        # Add optional fields if provided
        if ticket_data.get('assignee'):
            payload['assignees'] = [ticket_data['assignee']]

        if ticket_data.get('milestone'):
            payload['milestone'] = ticket_data['milestone']

        return payload
