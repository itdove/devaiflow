"""GitLab field mapper for converting between GitLab Issues and DevAIFlow interface.

GitLab uses convention-based labels instead of custom fields (same as GitHub):
- Issue types: bug, enhancement, task, spike, epic
- Priority: priority: critical, priority: high, priority: medium, priority: low
- Story points: points: 1, points: 2, points: 3, points: 5, points: 8
- Status: status: in-progress, status: in-review, status: blocked

Acceptance criteria are stored in the issue description with HTML comment delimiters.
"""

import re
from typing import Dict, List, Optional, Any


class GitLabFieldMapper:
    """Maps GitLab issue fields to standardized DevAIFlow interface fields."""

    # Label convention patterns (same as GitHub)
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

    # Acceptance criteria delimiters (same as GitHub)
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
        """Extract type, priority, points, and status from GitLab labels.

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
            >>> mapper = GitLabFieldMapper()
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

    def extract_acceptance_criteria(self, description: str) -> List[str]:
        """Extract acceptance criteria from GitLab issue description.

        Args:
            description: Issue description text

        Returns:
            List of acceptance criteria items (without checkbox syntax)

        Examples:
            >>> mapper = GitLabFieldMapper()
            >>> desc = '''
            ... <!-- ACCEPTANCE_CRITERIA_START -->
            ... - [ ] Criterion 1
            ... - [x] Criterion 2
            ... <!-- ACCEPTANCE_CRITERIA_END -->
            ... '''
            >>> mapper.extract_acceptance_criteria(desc)
            ['Criterion 1', 'Criterion 2']
        """
        if not description:
            return []

        # Find acceptance criteria section
        start_idx = description.find(self.AC_START)
        end_idx = description.find(self.AC_END)

        if start_idx == -1 or end_idx == -1:
            return []

        # Extract section content
        ac_section = description[start_idx + len(self.AC_START):end_idx].strip()

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
        """Format acceptance criteria for GitLab issue description.

        Args:
            criteria: List of acceptance criteria items (plain text or with checkbox syntax)

        Returns:
            Formatted acceptance criteria section with delimiters

        Examples:
            >>> mapper = GitLabFieldMapper()
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

    def inject_acceptance_criteria(self, description: str, criteria: List[str]) -> str:
        """Inject or update acceptance criteria in issue description.

        Args:
            description: Existing issue description
            criteria: List of acceptance criteria items

        Returns:
            Updated issue description with acceptance criteria

        Examples:
            >>> mapper = GitLabFieldMapper()
            >>> mapper.inject_acceptance_criteria('Description', ['Test 1'])
            'Description\\n\\n<!-- ACCEPTANCE_CRITERIA_START -->\\n- [ ] Test 1\\n<!-- ACCEPTANCE_CRITERIA_END -->'
        """
        if not criteria:
            return description

        description = description or ''
        ac_section = self.format_acceptance_criteria(criteria)

        # Check if AC section already exists
        start_idx = description.find(self.AC_START)
        end_idx = description.find(self.AC_END)

        if start_idx != -1 and end_idx != -1:
            # Replace existing section
            return description[:start_idx] + ac_section + description[end_idx + len(self.AC_END):]
        else:
            # Append to description
            separator = '\n\n' if description.strip() else ''
            return description + separator + ac_section

    def map_gitlab_to_interface(self, issue_data: Dict, repository: Optional[str] = None) -> Dict:
        """Convert GitLab issue data to standardized interface format.

        Args:
            issue_data: GitLab issue dict from API
            repository: Optional repository in group/project format (e.g., "group/project")

        Returns:
            Standardized ticket dictionary

        Examples:
            >>> mapper = GitLabFieldMapper()
            >>> issue = {
            ...     'iid': 123,
            ...     'title': 'Add feature',
            ...     'description': 'Description',
            ...     'state': 'opened',
            ...     'labels': ['bug', 'priority: high'],
            ...     'assignees': [{'username': 'user1'}],
            ...     'milestone': {'title': 'v1.0'},
            ... }
            >>> result = mapper.map_gitlab_to_interface(issue, repository='group/project')
            >>> result['key']
            'group/project#123'
            >>> result['summary']
            'Add feature'
            >>> result['type']
            'bug'
        """
        # Extract label names
        label_names = issue_data.get('labels', [])
        if isinstance(label_names, list) and label_names and isinstance(label_names[0], dict):
            label_names = [label['name'] for label in label_names]

        # Parse labels to fields
        parsed_fields = self.parse_labels_to_fields(label_names)

        # Extract assignees (GitLab uses 'assignees' array)
        assignees = issue_data.get('assignees', [])
        assignee = assignees[0]['username'] if assignees else None

        # Extract milestone
        milestone = issue_data.get('milestone')
        milestone_name = milestone['title'] if milestone else None

        # Extract acceptance criteria
        description = issue_data.get('description', '')
        acceptance_criteria = self.extract_acceptance_criteria(description)

        # Build issue key with repository if provided
        # GitLab uses 'iid' for issue number (project-specific ID)
        issue_number = issue_data['iid']
        if repository:
            issue_key = f"{repository}#{issue_number}"
        else:
            issue_key = f"#{issue_number}"

        # Map GitLab state to standard status
        # GitLab states: 'opened', 'closed'
        gitlab_state = issue_data.get('state', 'opened')
        status = 'open' if gitlab_state == 'opened' else 'closed'

        # Map to interface format
        return {
            'key': issue_key,
            'summary': issue_data.get('title', ''),
            'description': description,
            'status': status,
            'type': parsed_fields.get('issue_type', 'task'),
            'priority': parsed_fields.get('priority'),
            'assignee': assignee,
            'sprint': milestone_name,  # Map milestone to sprint
            'points': parsed_fields.get('points'),
            'labels': label_names,
            'acceptance_criteria': acceptance_criteria,
            # GitLab-specific fields
            'milestone': milestone_name,
            'gitlab_state': gitlab_state,
            'gitlab_iid': issue_data.get('iid'),
            'gitlab_id': issue_data.get('id'),
        }

    def map_interface_to_gitlab(self, ticket_data: Dict) -> Dict:
        """Convert standardized interface format to GitLab issue data.

        Args:
            ticket_data: Standardized ticket dictionary

        Returns:
            GitLab issue creation/update payload

        Examples:
            >>> mapper = GitLabFieldMapper()
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
            >>> result = mapper.map_interface_to_gitlab(ticket)
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
        if status and status not in ['open', 'opened', 'closed']:
            labels.append(f'status: {status}')

        # Add any additional labels
        additional_labels = ticket_data.get('labels', [])
        if isinstance(additional_labels, list):
            labels.extend(additional_labels)

        # Remove duplicates while preserving order
        seen = set()
        labels = [x for x in labels if not (x in seen or seen.add(x))]

        # Inject acceptance criteria into description
        description = ticket_data.get('description', '')
        acceptance_criteria = ticket_data.get('acceptance_criteria', [])
        if acceptance_criteria:
            description = self.inject_acceptance_criteria(description, acceptance_criteria)

        # Build GitLab issue payload
        payload = {
            'title': ticket_data.get('summary', ''),
            'description': description,
            'labels': ','.join(labels),  # GitLab expects comma-separated string
        }

        # Add optional fields if provided
        if ticket_data.get('assignee'):
            # GitLab accepts assignee_ids, but we'll use assignee_id for single assignee
            # This requires looking up user ID, which is complex
            # For now, we'll skip this and let users assign manually
            pass

        if ticket_data.get('milestone'):
            # GitLab accepts milestone_id, which requires lookup
            # For now, we'll skip this and let users assign manually
            pass

        return payload
