"""Tests for GitHub field mapper."""

import pytest

from devflow.github.field_mapper import GitHubFieldMapper


class TestParseLabelsToFields:
    """Tests for parse_labels_to_fields method."""

    def test_parse_bug_label(self):
        """Test parsing bug issue type label."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields(['bug'])
        assert fields['issue_type'] == 'bug'

    def test_parse_enhancement_label(self):
        """Test parsing enhancement (story) label."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields(['enhancement'])
        assert fields['issue_type'] == 'story'

    def test_parse_task_label(self):
        """Test parsing task label."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields(['task'])
        assert fields['issue_type'] == 'task'

    def test_parse_priority_high(self):
        """Test parsing priority: high label."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields(['priority: high'])
        assert fields['priority'] == 'high'

    def test_parse_priority_critical(self):
        """Test parsing priority: critical label."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields(['priority: critical'])
        assert fields['priority'] == 'critical'

    def test_parse_points_3(self):
        """Test parsing points: 3 label."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields(['points: 3'])
        assert fields['points'] == 3

    def test_parse_points_8(self):
        """Test parsing points: 8 label."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields(['points: 8'])
        assert fields['points'] == 8

    def test_parse_status_in_progress(self):
        """Test parsing status: in-progress label."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields(['status: in-progress'])
        assert fields['status'] == 'in-progress'

    def test_parse_combined_labels(self):
        """Test parsing multiple labels together."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields([
            'bug',
            'priority: high',
            'points: 5',
            'status: in-progress',
            'backend',  # Additional label (ignored)
        ])
        assert fields['issue_type'] == 'bug'
        assert fields['priority'] == 'high'
        assert fields['points'] == 5
        assert fields['status'] == 'in-progress'

    def test_parse_empty_labels(self):
        """Test parsing empty label list."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields([])
        assert fields == {}

    def test_parse_case_insensitive(self):
        """Test label parsing is case insensitive."""
        mapper = GitHubFieldMapper()
        fields = mapper.parse_labels_to_fields(['Bug', 'PRIORITY: HIGH', 'Points: 3'])
        assert fields['issue_type'] == 'bug'
        assert fields['priority'] == 'high'
        assert fields['points'] == 3


class TestExtractAcceptanceCriteria:
    """Tests for extract_acceptance_criteria method."""

    def test_extract_basic_criteria(self):
        """Test extracting basic acceptance criteria."""
        mapper = GitHubFieldMapper()
        body = '''
Description text

<!-- ACCEPTANCE_CRITERIA_START -->
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
<!-- ACCEPTANCE_CRITERIA_END -->

More text
'''
        criteria = mapper.extract_acceptance_criteria(body)
        assert criteria == ['Criterion 1', 'Criterion 2', 'Criterion 3']

    def test_extract_checked_criteria(self):
        """Test extracting criteria with checked boxes."""
        mapper = GitHubFieldMapper()
        body = '''
<!-- ACCEPTANCE_CRITERIA_START -->
- [x] Completed criterion
- [ ] Pending criterion
<!-- ACCEPTANCE_CRITERIA_END -->
'''
        criteria = mapper.extract_acceptance_criteria(body)
        assert criteria == ['Completed criterion', 'Pending criterion']

    def test_extract_no_criteria(self):
        """Test body without acceptance criteria."""
        mapper = GitHubFieldMapper()
        body = 'Just a description'
        criteria = mapper.extract_acceptance_criteria(body)
        assert criteria == []

    def test_extract_empty_body(self):
        """Test empty body."""
        mapper = GitHubFieldMapper()
        criteria = mapper.extract_acceptance_criteria('')
        assert criteria == []

    def test_extract_with_asterisk(self):
        """Test extraction with asterisk bullet points."""
        mapper = GitHubFieldMapper()
        body = '''
<!-- ACCEPTANCE_CRITERIA_START -->
* [ ] Criterion 1
* [x] Criterion 2
<!-- ACCEPTANCE_CRITERIA_END -->
'''
        criteria = mapper.extract_acceptance_criteria(body)
        assert criteria == ['Criterion 1', 'Criterion 2']

    def test_extract_uppercase_X(self):
        """Test extraction with uppercase X in checkbox."""
        mapper = GitHubFieldMapper()
        body = '''
<!-- ACCEPTANCE_CRITERIA_START -->
- [X] Criterion with uppercase X
<!-- ACCEPTANCE_CRITERIA_END -->
'''
        criteria = mapper.extract_acceptance_criteria(body)
        assert criteria == ['Criterion with uppercase X']


class TestFormatAcceptanceCriteria:
    """Tests for format_acceptance_criteria method."""

    def test_format_basic_criteria(self):
        """Test formatting basic criteria."""
        mapper = GitHubFieldMapper()
        criteria = ['Criterion 1', 'Criterion 2']
        formatted = mapper.format_acceptance_criteria(criteria)

        expected = '''<!-- ACCEPTANCE_CRITERIA_START -->
- [ ] Criterion 1
- [ ] Criterion 2
<!-- ACCEPTANCE_CRITERIA_END -->'''
        assert formatted == expected

    def test_format_empty_criteria(self):
        """Test formatting empty criteria list."""
        mapper = GitHubFieldMapper()
        formatted = mapper.format_acceptance_criteria([])
        assert formatted == ''

    def test_format_single_criterion(self):
        """Test formatting single criterion."""
        mapper = GitHubFieldMapper()
        formatted = mapper.format_acceptance_criteria(['Single criterion'])
        assert '- [ ] Single criterion' in formatted
        assert mapper.AC_START in formatted
        assert mapper.AC_END in formatted


class TestInjectAcceptanceCriteria:
    """Tests for inject_acceptance_criteria method."""

    def test_inject_into_empty_body(self):
        """Test injecting criteria into empty body."""
        mapper = GitHubFieldMapper()
        criteria = ['Test 1', 'Test 2']
        result = mapper.inject_acceptance_criteria('', criteria)

        assert mapper.AC_START in result
        assert '- [ ] Test 1' in result
        assert '- [ ] Test 2' in result

    def test_inject_into_existing_body(self):
        """Test injecting criteria into body with content."""
        mapper = GitHubFieldMapper()
        criteria = ['Test 1']
        result = mapper.inject_acceptance_criteria('Description text', criteria)

        assert result.startswith('Description text')
        assert mapper.AC_START in result
        assert '- [ ] Test 1' in result

    def test_replace_existing_criteria(self):
        """Test replacing existing criteria."""
        mapper = GitHubFieldMapper()
        old_body = '''Description

<!-- ACCEPTANCE_CRITERIA_START -->
- [ ] Old criterion
<!-- ACCEPTANCE_CRITERIA_END -->

Footer'''
        new_criteria = ['New criterion 1', 'New criterion 2']
        result = mapper.inject_acceptance_criteria(old_body, new_criteria)

        assert 'Description' in result
        assert 'Footer' in result
        assert '- [ ] New criterion 1' in result
        assert '- [ ] New criterion 2' in result
        assert 'Old criterion' not in result

    def test_inject_empty_criteria(self):
        """Test injecting empty criteria list returns unchanged body."""
        mapper = GitHubFieldMapper()
        body = 'Test body'
        result = mapper.inject_acceptance_criteria(body, [])
        assert result == body


class TestMapGitHubToInterface:
    """Tests for map_github_to_interface method."""

    def test_map_basic_issue(self):
        """Test mapping basic GitHub issue."""
        mapper = GitHubFieldMapper()
        issue = {
            'number': 123,
            'title': 'Test issue',
            'body': 'Description',
            'state': 'open',
            'labels': [{'name': 'bug'}, {'name': 'priority: high'}],
        }
        result = mapper.map_github_to_interface(issue)

        assert result['key'] == '#123'
        assert result['summary'] == 'Test issue'
        assert result['description'] == 'Description'
        assert result['status'] == 'open'
        assert result['type'] == 'bug'
        assert result['priority'] == 'high'

    def test_map_with_assignees(self):
        """Test mapping issue with assignees."""
        mapper = GitHubFieldMapper()
        issue = {
            'number': 123,
            'title': 'Test',
            'body': '',
            'state': 'open',
            'labels': [],
            'assignees': [{'login': 'user1'}, {'login': 'user2'}],
        }
        result = mapper.map_github_to_interface(issue)

        assert result['assignee'] == 'user1'  # First assignee

    def test_map_with_milestone(self):
        """Test mapping issue with milestone."""
        mapper = GitHubFieldMapper()
        issue = {
            'number': 123,
            'title': 'Test',
            'body': '',
            'state': 'open',
            'labels': [],
            'milestone': {'title': 'v1.0'},
        }
        result = mapper.map_github_to_interface(issue)

        assert result['sprint'] == 'v1.0'
        assert result['milestone'] == 'v1.0'

    def test_map_with_acceptance_criteria(self):
        """Test mapping issue with acceptance criteria."""
        mapper = GitHubFieldMapper()
        body = '''Description

<!-- ACCEPTANCE_CRITERIA_START -->
- [ ] Criterion 1
- [ ] Criterion 2
<!-- ACCEPTANCE_CRITERIA_END -->'''

        issue = {
            'number': 123,
            'title': 'Test',
            'body': body,
            'state': 'open',
            'labels': [],
        }
        result = mapper.map_github_to_interface(issue)

        assert result['acceptance_criteria'] == ['Criterion 1', 'Criterion 2']

    def test_map_with_all_fields(self):
        """Test mapping issue with all fields populated."""
        mapper = GitHubFieldMapper()
        issue = {
            'number': 456,
            'title': 'Complete feature',
            'body': 'Full description',
            'state': 'closed',
            'labels': [
                {'name': 'enhancement'},
                {'name': 'priority: critical'},
                {'name': 'points: 8'},
                {'name': 'backend'},
            ],
            'assignees': [{'login': 'developer'}],
            'milestone': {'title': 'Sprint 10'},
        }
        result = mapper.map_github_to_interface(issue)

        assert result['key'] == '#456'
        assert result['summary'] == 'Complete feature'
        assert result['type'] == 'story'  # enhancement → story
        assert result['priority'] == 'critical'
        assert result['points'] == 8
        assert result['assignee'] == 'developer'
        assert result['sprint'] == 'Sprint 10'
        assert 'backend' in result['labels']


class TestMapInterfaceToGitHub:
    """Tests for map_interface_to_github method."""

    def test_map_basic_ticket(self):
        """Test mapping basic ticket to GitHub."""
        mapper = GitHubFieldMapper()
        ticket = {
            'summary': 'Add feature',
            'description': 'Description text',
            'type': 'bug',
        }
        result = mapper.map_interface_to_github(ticket)

        assert result['title'] == 'Add feature'
        assert result['body'] == 'Description text'
        assert 'bug' in result['labels']

    def test_map_with_priority(self):
        """Test mapping ticket with priority."""
        mapper = GitHubFieldMapper()
        ticket = {
            'summary': 'Test',
            'description': '',
            'type': 'task',
            'priority': 'high',
        }
        result = mapper.map_interface_to_github(ticket)

        assert 'task' in result['labels']
        assert 'priority: high' in result['labels']

    def test_map_with_points(self):
        """Test mapping ticket with story points."""
        mapper = GitHubFieldMapper()
        ticket = {
            'summary': 'Test',
            'description': '',
            'type': 'story',
            'points': 5,
        }
        result = mapper.map_interface_to_github(ticket)

        assert 'enhancement' in result['labels']  # story → enhancement
        assert 'points: 5' in result['labels']

    def test_map_with_acceptance_criteria(self):
        """Test mapping ticket with acceptance criteria."""
        mapper = GitHubFieldMapper()
        ticket = {
            'summary': 'Test',
            'description': 'Description',
            'acceptance_criteria': ['Test 1', 'Test 2'],
        }
        result = mapper.map_interface_to_github(ticket)

        assert mapper.AC_START in result['body']
        assert '- [ ] Test 1' in result['body']
        assert '- [ ] Test 2' in result['body']
        assert 'Description' in result['body']

    def test_map_with_assignee(self):
        """Test mapping ticket with assignee."""
        mapper = GitHubFieldMapper()
        ticket = {
            'summary': 'Test',
            'description': '',
            'assignee': 'username',
        }
        result = mapper.map_interface_to_github(ticket)

        assert result['assignees'] == ['username']

    def test_map_with_milestone(self):
        """Test mapping ticket with milestone."""
        mapper = GitHubFieldMapper()
        ticket = {
            'summary': 'Test',
            'description': '',
            'milestone': 'v2.0',
        }
        result = mapper.map_interface_to_github(ticket)

        assert result['milestone'] == 'v2.0'

    def test_map_with_additional_labels(self):
        """Test mapping ticket with additional custom labels."""
        mapper = GitHubFieldMapper()
        ticket = {
            'summary': 'Test',
            'description': '',
            'type': 'bug',
            'labels': ['backend', 'urgent'],
        }
        result = mapper.map_interface_to_github(ticket)

        assert 'bug' in result['labels']
        assert 'backend' in result['labels']
        assert 'urgent' in result['labels']

    def test_map_complete_ticket(self):
        """Test mapping complete ticket with all fields."""
        mapper = GitHubFieldMapper()
        ticket = {
            'summary': 'Implement caching',
            'description': 'Add Redis caching layer',
            'type': 'story',
            'priority': 'high',
            'points': 8,
            'acceptance_criteria': ['Redis integrated', 'Tests added'],
            'assignee': 'dev1',
            'milestone': 'v3.0',
            'labels': ['backend', 'performance'],
        }
        result = mapper.map_interface_to_github(ticket)

        assert result['title'] == 'Implement caching'
        assert 'Add Redis caching layer' in result['body']
        assert mapper.AC_START in result['body']
        assert '- [ ] Redis integrated' in result['body']
        assert 'enhancement' in result['labels']  # story → enhancement
        assert 'priority: high' in result['labels']
        assert 'points: 8' in result['labels']
        assert 'backend' in result['labels']
        assert result['assignees'] == ['dev1']
        assert result['milestone'] == 'v3.0'
