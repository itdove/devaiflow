"""Tests for daf jira view command."""

import json
import pytest
from devflow.jira.client import JiraClient
from devflow.jira.exceptions import JiraNotFoundError
from devflow.cli.commands.jira_view_command import (
    format_ticket_for_claude,
    format_changelog_for_claude,
    format_child_issues_for_claude,
    format_comments_for_claude,
    view_jira_ticket,
)


def test_format_ticket_basic_fields():
    """Test formatting a ticket with basic fields."""
    ticket_data = {
        "key": "PROJ-12345",
        "summary": "Test ticket summary",
        "type": "Story",
        "status": "In Progress",
        "priority": "Major",
        "assignee": "John Doe",
    }

    result = format_ticket_for_claude(ticket_data)

    assert "Key: PROJ-12345" in result
    assert "Summary: Test ticket summary" in result
    assert "Type: Story" in result
    assert "Status: In Progress" in result
    assert "Priority: Major" in result
    assert "Assignee: John Doe" in result


def test_format_ticket_with_description():
    """Test formatting a ticket with description."""
    ticket_data = {
        "key": "PROJ-12345",
        "summary": "Test ticket",
        "type": "Bug",
        "status": "New",
        "description": "This is a test bug description\nwith multiple lines",
    }

    result = format_ticket_for_claude(ticket_data)

    assert "Description:" in result
    assert "This is a test bug description" in result
    assert "with multiple lines" in result


def test_format_ticket_with_acceptance_criteria():
    """Test formatting a ticket with acceptance criteria."""
    ticket_data = {
        "key": "PROJ-12345",
        "summary": "Feature implementation",
        "type": "Story",
        "status": "New",
        "acceptance_criteria": "- Criterion 1\n- Criterion 2\n- Criterion 3",
    }

    result = format_ticket_for_claude(ticket_data)

    assert "Acceptance Criteria:" in result
    assert "- Criterion 1" in result
    assert "- Criterion 2" in result
    assert "- Criterion 3" in result


def test_format_ticket_with_sprint_and_points():
    """Test formatting a ticket with sprint and story points."""
    ticket_data = {
        "key": "PROJ-12345",
        "summary": "Sprint task",
        "type": "Story",
        "status": "In Progress",
        "sprint": "Sprint 42",
        "points": 5,
        "epic": "PROJ-10000",
    }

    result = format_ticket_for_claude(ticket_data)

    assert "Sprint: Sprint 42" in result
    assert "Points: 5" in result
    assert "Epic: PROJ-10000" in result


def test_format_ticket_complete_example():
    """Test formatting a ticket with all fields."""
    ticket_data = {
        "key": "PROJ-59207",
        "summary": "Add daf jira view command for reliable issue tracker ticket reading",
        "type": "Story",
        "status": "In Progress",
        "priority": "Major",
        "assignee": "Dominique Vernier",
        "reporter": "Dominique Vernier",
        "epic": "PROJ-59038",
        "sprint": "Platform Sprint 2025-47",
        "points": 2,
        "description": "As a developer using Claude Code within a daf session, I want a reliable way to read issue tracker ticket information using a simple daf command, so that Claude can consistently access ticket details without authentication or curl formatting issues.",
        "acceptance_criteria": "- daf jira view command implemented using JiraClient\n- Command outputs issue tracker ticket in Claude-friendly format\n- Initial prompt updated to use daf jira view instead of curl\n- More reliable than curl with proper error handling\n- Consistent authentication handling via JiraClient",
    }

    result = format_ticket_for_claude(ticket_data)

    # Verify all fields are present
    assert "Key: PROJ-59207" in result
    assert "Summary: Add daf jira view command for reliable issue tracker ticket reading" in result
    assert "Type: Story" in result
    assert "Status: In Progress" in result
    assert "Priority: Major" in result
    assert "Assignee: Dominique Vernier" in result
    assert "Reporter: Dominique Vernier" in result
    assert "Epic: PROJ-59038" in result
    assert "Sprint: Platform Sprint 2025-47" in result
    assert "Points: 2" in result
    assert "Description:" in result
    assert "As a developer using Claude Code" in result
    assert "Acceptance Criteria:" in result
    assert "daf jira view command implemented using JiraClient" in result


def test_format_ticket_minimal_fields():
    """Test formatting a ticket with only required fields."""
    ticket_data = {
        "key": "PROJ-12345",
        "summary": "Minimal ticket",
        "type": "Task",
        "status": "New",
    }

    result = format_ticket_for_claude(ticket_data)

    # Required fields should be present
    assert "Key: PROJ-12345" in result
    assert "Summary: Minimal ticket" in result
    assert "Type: Task" in result
    assert "Status: New" in result

    # Optional fields should not be present
    assert "Priority:" not in result
    assert "Assignee:" not in result
    assert "Epic:" not in result
    assert "Sprint:" not in result
    assert "Story Points:" not in result


def test_get_ticket_detailed_with_description(mock_jira_cli):
    """Test fetching a detailed ticket with description."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket with description",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "description": "This is the ticket description",
            "priority": {"name": "Major"},
            "customfield_12315940": "- Acceptance criterion 1\n- Acceptance criterion 2",
        }
    })

    # Provide field_mappings so that acceptance_criteria can be resolved
    field_mappings = {
        "acceptance_criteria": {
            "id": "customfield_12315940"
        }
    }

    client = JiraClient()
    ticket = client.get_ticket_detailed("PROJ-12345", field_mappings=field_mappings)

    assert ticket is not None
    assert ticket["key"] == "PROJ-12345"
    assert ticket["summary"] == "Test ticket with description"
    assert ticket["description"] == "This is the ticket description"
    assert ticket["priority"] == "Major"
    assert ticket["acceptance_criteria"] == "- Acceptance criterion 1\n- Acceptance criterion 2"


def test_get_ticket_detailed_not_found(mock_jira_cli):
    """Test fetching a non-existent ticket raises JiraNotFoundError."""
    client = JiraClient()

    with pytest.raises(JiraNotFoundError) as exc_info:
        client.get_ticket_detailed("PROJ-99999")

    assert exc_info.value.resource_id == "PROJ-99999"


def test_get_ticket_detailed_with_all_fields(mock_jira_cli):
    """Test fetching a ticket with all supported fields."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Complete ticket",
            "status": {"name": "Code Review"},
            "issuetype": {"name": "Story"},
            "description": "Full description",
            "priority": {"name": "Critical"},
            "assignee": {"displayName": "Jane Smith"},
            "reporter": {"displayName": "John Doe"},
            "customfield_12310243": 8,  # Story points
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@123[id=123,name=Sprint 45,state=ACTIVE]"],
            "customfield_12311140": "PROJ-10000",  # Epic
            "customfield_12315940": "- Criterion A\n- Criterion B",  # Acceptance criteria
        }
    })

    # Provide field_mappings for all custom fields
    field_mappings = {
        "acceptance_criteria": {
            "id": "customfield_12315940",
            "type": "string",
            "schema": "string"
        },
        "story_points": {
            "id": "customfield_12310243",
            "type": "number",
            "schema": "number"
        },
        "sprint": {
            "id": "customfield_12310940",
            "type": "array",
            "schema": "com.pyxis.greenhopper.jira:gh-sprint"
        },
        "epic_link": {
            "id": "customfield_12311140",
            "type": "string",
            "schema": "string"
        }
    }

    client = JiraClient()
    ticket = client.get_ticket_detailed("PROJ-12345", field_mappings=field_mappings)

    assert ticket is not None
    assert ticket["key"] == "PROJ-12345"
    assert ticket["summary"] == "Complete ticket"
    assert ticket["status"] == "Code Review"
    assert ticket["type"] == "Story"
    assert ticket["description"] == "Full description"
    assert ticket["priority"] == "Critical"
    assert ticket["assignee"] == "Jane Smith"
    assert ticket["reporter"] == "John Doe"
    assert ticket["points"] == 8
    assert ticket["sprint"] == "Sprint 45"
    assert ticket["epic"] == "PROJ-10000"
    assert ticket["acceptance_criteria"] == "- Criterion A\n- Criterion B"


def test_view_jira_ticket_success(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test viewing a issue tracker ticket using the command."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    # Provide data in raw JIRA API format - JiraClient.get_ticket_detailed() will process it
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "issuetype": {"name": "Story"},
            "status": {"name": "New"},
            "description": "Test description",
            "priority": {"name": "Major"},
        }
    })

    view_jira_ticket("PROJ-12345")

    captured = capsys.readouterr()
    assert "Key: PROJ-12345" in captured.out
    assert "Summary: Test ticket" in captured.out
    assert "Status: New" in captured.out
    assert "Type: Story" in captured.out
    assert "Priority: Major" in captured.out
    assert "Description:" in captured.out
    assert "Test description" in captured.out


def test_view_jira_ticket_not_found(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test viewing a non-existent issue tracker ticket."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    with pytest.raises(SystemExit) as exc_info:
        view_jira_ticket("PROJ-99999")

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "issue tracker ticket PROJ-99999 not found" in captured.out


def test_format_changelog_basic():
    """Test formatting changelog with basic entries."""
    changelog = {
        "total": 3,
        "histories": [
            {
                "id": "12345",
                "created": "2025-12-05T20:13:45.380+0000",
                "author": {
                    "displayName": "John Doe"
                },
                "items": [
                    {
                        "field": "status",
                        "fromString": "New",
                        "toString": "In Progress"
                    }
                ]
            },
            {
                "id": "12346",
                "created": "2025-12-05T20:14:00.401+0000",
                "author": {
                    "displayName": "Jane Smith"
                },
                "items": [
                    {
                        "field": "assignee",
                        "fromString": None,
                        "toString": "Jane Smith"
                    }
                ]
            }
        ]
    }

    result = format_changelog_for_claude(changelog)

    assert "Changelog/History:" in result
    assert "2025-12-05 20:13:45" in result
    assert "John Doe" in result
    assert "status: New → In Progress" in result
    assert "2025-12-05 20:14:00" in result
    assert "Jane Smith" in result
    assert "assignee: (empty) → Jane Smith" in result


def test_format_changelog_empty():
    """Test formatting empty changelog."""
    changelog = {
        "total": 0,
        "histories": []
    }

    result = format_changelog_for_claude(changelog)

    assert result == ""


def test_format_changelog_limits_to_15():
    """Test that changelog is limited to last 15 entries."""
    # Create 20 history entries
    histories = []
    for i in range(20):
        histories.append({
            "id": str(i),
            "created": f"2025-12-{i+1:02d}T10:00:00.000+0000",
            "author": {
                "displayName": f"User {i}"
            },
            "items": [
                {
                    "field": "status",
                    "fromString": "New",
                    "toString": "In Progress"
                }
            ]
        })

    changelog = {
        "total": 20,
        "histories": histories
    }

    result = format_changelog_for_claude(changelog)

    # Should only show last 15 entries (entries 5-19, which are days 6-20)
    assert "2025-12-06" in result  # Entry 5
    assert "2025-12-20" in result  # Entry 19
    assert "2025-12-01" not in result  # Entry 0 should not be shown
    assert "2025-12-05" not in result  # Entry 4 should not be shown


def test_format_changelog_multiple_items():
    """Test formatting changelog with multiple items in one history entry."""
    changelog = {
        "total": 1,
        "histories": [
            {
                "id": "12345",
                "created": "2025-12-05T20:13:45.380+0000",
                "author": {
                    "displayName": "John Doe"
                },
                "items": [
                    {
                        "field": "status",
                        "fromString": "New",
                        "toString": "In Progress"
                    },
                    {
                        "field": "priority",
                        "fromString": "Normal",
                        "toString": "Major"
                    },
                    {
                        "field": "Story Points",
                        "fromString": None,
                        "toString": "5"
                    }
                ]
            }
        ]
    }

    result = format_changelog_for_claude(changelog)

    assert "status: New → In Progress" in result
    assert "priority: Normal → Major" in result
    assert "Story Points: (empty) → 5" in result
    # All items should have the same timestamp and author
    assert result.count("2025-12-05 20:13:45") == 3
    assert result.count("John Doe") == 3


def test_get_ticket_detailed_with_changelog(mock_jira_cli):
    """Test fetching a ticket with changelog included."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "description": "Test description",
        },
        "changelog": {
            "total": 2,
            "histories": [
                {
                    "id": "1",
                    "created": "2025-12-05T20:13:45.380+0000",
                    "author": {
                        "displayName": "John Doe"
                    },
                    "items": [
                        {
                            "field": "status",
                            "fromString": "New",
                            "toString": "In Progress"
                        }
                    ]
                }
            ]
        }
    }, expand_changelog=True)

    client = JiraClient()
    ticket = client.get_ticket_detailed("PROJ-12345", include_changelog=True)

    assert ticket is not None
    assert "changelog" in ticket
    assert ticket["changelog"]["total"] == 2
    assert len(ticket["changelog"]["histories"]) == 1


def test_view_jira_ticket_with_history(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test viewing a issue tracker ticket with changelog history."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
            "description": "Test description",
            "priority": {"name": "Major"},
        },
        "changelog": {
            "total": 2,
            "histories": [
                {
                    "id": "1",
                    "created": "2025-12-05T20:13:45.380+0000",
                    "author": {
                        "displayName": "John Doe"
                    },
                    "items": [
                        {
                            "field": "status",
                            "fromString": "New",
                            "toString": "In Progress"
                        }
                    ]
                },
                {
                    "id": "2",
                    "created": "2025-12-05T20:14:00.000+0000",
                    "author": {
                        "displayName": "Jane Smith"
                    },
                    "items": [
                        {
                            "field": "priority",
                            "fromString": "Normal",
                            "toString": "Major"
                        }
                    ]
                }
            ]
        }
    }, expand_changelog=True)

    view_jira_ticket("PROJ-12345", show_history=True)

    captured = capsys.readouterr()
    # Check ticket info is present
    assert "Key: PROJ-12345" in captured.out
    assert "Summary: Test ticket" in captured.out

    # Check changelog is present
    assert "Changelog/History:" in captured.out
    assert "2025-12-05 20:13:45" in captured.out
    assert "John Doe" in captured.out
    assert "status: New → In Progress" in captured.out
    assert "2025-12-05 20:14:00" in captured.out
    assert "Jane Smith" in captured.out
    assert "priority: Normal → Major" in captured.out


def test_view_jira_ticket_without_history(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test that changelog is not shown when show_history=False."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "description": "Test description",
        }
    })

    view_jira_ticket("PROJ-12345", show_history=False)

    captured = capsys.readouterr()
    # Check ticket info is present
    assert "Key: PROJ-12345" in captured.out
    assert "Summary: Test ticket" in captured.out

    # Check changelog is NOT present
    assert "Changelog/History:" not in captured.out


def test_get_child_issues_with_subtasks_and_epic_children(mock_jira_cli, temp_daf_home, monkeypatch):
    """Test fetching child issues including subtasks and epic children."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    # Create minimal config.json (required for parent_field_mapping defaults)
    import json
    config_data = {
        "backend_config_source": "local",
        "repos": {},
        "time_tracking": {},
        "session_summary": {},
        "templates": {},
        "context_files": {},
        "prompts": {},
        "pr_template_url": None,
        "mock_services": None,
        "gcp_vertex_region": None,
        "update_checker_timeout": 5
    }
    with open(temp_daf_home / "config.json", "w") as f:
        json.dump(config_data, f)

    # Create jira.json with parent_field_mapping
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(parents=True, exist_ok=True)
    jira_config = {
        "url": "https://test.jira.com",
        "user": "test_user",
        "transitions": {},
        "parent_field_mapping": {
            "bug": "epic_link",
            "story": "epic_link",
            "task": "epic_link",
            "spike": "epic_link",
            "epic": "epic_link",
            "sub-task": "parent"
        }
    }
    with open(backends_dir / "jira.json", "w") as f:
        json.dump(jira_config, f)

    # Create organization.json
    with open(temp_daf_home / "organization.json", "w") as f:
        json.dump({"jira_project": "TEST", "sync_filters": {}}, f)

    # Set up JQL search response
    mock_jira_cli.set_search_results({
        "jql": 'parent = PROJ-12345 OR "Epic Link" = PROJ-12345 ORDER BY key ASC',
        "issues": [
            {
                "key": "PROJ-12346",
                "fields": {
                    "summary": "Subtask 1",
                    "status": {"name": "In Progress"},
                    "issuetype": {"name": "Sub-task"},
                    "assignee": {"displayName": "John Doe"},
                }
            },
            {
                "key": "PROJ-12347",
                "fields": {
                    "summary": "Story 1",
                    "status": {"name": "New"},
                    "issuetype": {"name": "Story"},
                    "assignee": {"displayName": "Jane Smith"},
                }
            },
            {
                "key": "PROJ-12348",
                "fields": {
                    "summary": "Task 1",
                    "status": {"name": "Done"},
                    "issuetype": {"name": "Task"},
                    "assignee": None,
                }
            }
        ]
    })

    # Provide field_mappings for epic_link with display name
    field_mappings = {
        "epic_link": {
            "id": "customfield_12311140",
            "name": "Epic Link"
        }
    }

    client = JiraClient()
    children = client.get_child_issues("PROJ-12345", field_mappings=field_mappings)

    assert len(children) == 3
    assert children[0]["key"] == "PROJ-12346"
    assert children[0]["type"] == "Sub-task"
    assert children[0]["status"] == "In Progress"
    assert children[0]["summary"] == "Subtask 1"
    assert children[0]["assignee"] == "John Doe"

    assert children[1]["key"] == "PROJ-12347"
    assert children[1]["type"] == "Story"
    assert children[1]["status"] == "New"

    assert children[2]["key"] == "PROJ-12348"
    assert children[2]["assignee"] is None


def test_get_child_issues_no_children(mock_jira_cli, temp_daf_home, monkeypatch):
    """Test fetching child issues when there are none."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    # Set up empty JQL search response
    mock_jira_cli.set_search_results({
        "jql": 'parent = PROJ-12345 OR "Epic Link" = PROJ-12345 ORDER BY key ASC',
        "issues": []
    })

    # Provide field_mappings for epic_link with display name
    field_mappings = {
        "epic_link": {
            "id": "customfield_12311140",
            "name": "Epic Link"
        }
    }

    client = JiraClient()
    children = client.get_child_issues("PROJ-12345", field_mappings=field_mappings)

    assert len(children) == 0


def test_get_child_issues_without_epic_link_mapping(mock_jira_cli, temp_daf_home, monkeypatch):
    """Test fetching child issues when epic_link field mapping is not configured."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    # Set up JQL search response
    mock_jira_cli.set_search_results({
        "jql": "parent = PROJ-12345 ORDER BY key ASC",
        "issues": [
            {
                "key": "PROJ-12346",
                "fields": {
                    "summary": "Subtask 1",
                    "status": {"name": "In Progress"},
                    "issuetype": {"name": "Sub-task"},
                    "assignee": None,
                }
            }
        ]
    })

    client = JiraClient()
    children = client.get_child_issues("PROJ-12345", field_mappings=None)

    assert len(children) == 1
    assert children[0]["key"] == "PROJ-12346"


def test_format_child_issues_basic():
    """Test formatting child issues with basic data."""
    children = [
        {
            "key": "PROJ-12346",
            "type": "Sub-task",
            "status": "In Progress",
            "summary": "Implement API endpoint",
            "assignee": "John Doe",
        },
        {
            "key": "PROJ-12347",
            "type": "Story",
            "status": "New",
            "summary": "Add frontend component",
            "assignee": "Jane Smith",
        },
        {
            "key": "PROJ-12348",
            "type": "Task",
            "status": "Done",
            "summary": "Update documentation",
            "assignee": None,
        }
    ]

    result = format_child_issues_for_claude(children)

    assert "Child Issues:" in result
    assert "PROJ-12346 | Sub-task | In Progress | Implement API endpoint | Assignee: John Doe" in result
    assert "PROJ-12347 | Story | New | Add frontend component | Assignee: Jane Smith" in result
    assert "PROJ-12348 | Task | Done | Update documentation" in result
    # PROJ-12348 should not have "Assignee:" since it's None
    assert result.count("Assignee:") == 2


def test_format_child_issues_empty():
    """Test formatting empty child issues list."""
    children = []

    result = format_child_issues_for_claude(children)

    assert result == "\nNo child issues found"


def test_view_jira_ticket_with_children(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test viewing a issue tracker ticket with child issues."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    # Create minimal config.json (required for new format detection)
    config_data = {
        "backend_config_source": "local",
        "repos": {},
        "time_tracking": {},
        "session_summary": {},
        "templates": {},
        "context_files": {},
        "prompts": {},
        "pr_template_url": None,
        "mock_services": None,
        "gcp_vertex_region": None,
        "update_checker_timeout": 5
    }
    with open(temp_daf_home / "config.json", "w") as f:
        json.dump(config_data, f)

    # Set up jira.json config with field_mappings including epic_link
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(parents=True, exist_ok=True)

    jira_config = {
        "url": "https://test.jira.com",
        "user": "test_user",
        "transitions": {},
        "field_mappings": {
            "epic_link": {
                "id": "customfield_12311140",
                "name": "Epic Link"
            }
        },
        "parent_field_mapping": {
            "bug": "epic_link",
            "story": "epic_link",
            "task": "epic_link",
            "spike": "epic_link",
            "epic": "epic_link",
            "sub-task": "parent"
        }
    }

    with open(backends_dir / "jira.json", "w") as f:
        json.dump(jira_config, f)

    # Create minimal organization.json and team.json
    with open(temp_daf_home / "organization.json", "w") as f:
        json.dump({"jira_project": "TEST", "sync_filters": {}}, f)

    with open(temp_daf_home / "team.json", "w") as f:
        json.dump({"jira_custom_field_defaults": None}, f)

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Epic ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Epic"},
            "description": "Epic description",
            "priority": {"name": "Major"},
        }
    })

    # Set up child issues
    # With epic_link field mapping, the JQL includes "Epic Link"
    mock_jira_cli.set_search_results({
        "jql": 'parent = PROJ-12345 OR "Epic Link" = PROJ-12345 ORDER BY key ASC',
        "issues": [
            {
                "key": "PROJ-12346",
                "fields": {
                    "summary": "Child story 1",
                    "status": {"name": "New"},
                    "issuetype": {"name": "Story"},
                    "assignee": {"displayName": "John Doe"},
                }
            },
            {
                "key": "PROJ-12347",
                "fields": {
                    "summary": "Child story 2",
                    "status": {"name": "Done"},
                    "issuetype": {"name": "Story"},
                    "assignee": None,
                }
            }
        ]
    })

    view_jira_ticket("PROJ-12345", show_children=True)

    captured = capsys.readouterr()
    # Check ticket info is present
    assert "Key: PROJ-12345" in captured.out
    assert "Summary: Epic ticket" in captured.out

    # Check child issues are present
    assert "Child Issues:" in captured.out
    assert "PROJ-12346 | Story | New | Child story 1 | Assignee: John Doe" in captured.out
    assert "PROJ-12347 | Story | Done | Child story 2" in captured.out


def test_view_jira_ticket_with_children_no_children(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test viewing a issue tracker ticket with no child issues."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    # Create minimal config.json (required for new format detection)
    config_data = {
        "backend_config_source": "local",
        "repos": {},
        "time_tracking": {},
        "session_summary": {},
        "templates": {},
        "context_files": {},
        "prompts": {},
        "pr_template_url": None,
        "mock_services": None,
        "gcp_vertex_region": None,
        "update_checker_timeout": 5
    }
    with open(temp_daf_home / "config.json", "w") as f:
        json.dump(config_data, f)

    # Set up jira.json config with field_mappings including epic_link
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(parents=True, exist_ok=True)

    jira_config = {
        "url": "https://test.jira.com",
        "user": "test_user",
        "transitions": {},
        "field_mappings": {
            "epic_link": {
                "id": "customfield_12311140",
                "name": "Epic Link"
            }
        },
        "parent_field_mapping": {
            "bug": "epic_link",
            "story": "epic_link",
            "task": "epic_link",
            "spike": "epic_link",
            "epic": "epic_link",
            "sub-task": "parent"
        }
    }

    with open(backends_dir / "jira.json", "w") as f:
        json.dump(jira_config, f)

    # Create minimal organization.json and team.json
    with open(temp_daf_home / "organization.json", "w") as f:
        json.dump({"jira_project": "TEST", "sync_filters": {}}, f)

    with open(temp_daf_home / "team.json", "w") as f:
        json.dump({"jira_custom_field_defaults": None}, f)

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Epic ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Epic"},
            "description": "Epic description",
        }
    })

    # Set up empty child issues
    # With epic_link field mapping, the JQL includes "Epic Link"
    mock_jira_cli.set_search_results({
        "jql": 'parent = PROJ-12345 OR "Epic Link" = PROJ-12345 ORDER BY key ASC',
        "issues": []
    })

    view_jira_ticket("PROJ-12345", show_children=True)

    captured = capsys.readouterr()
    # Check ticket info is present
    assert "Key: PROJ-12345" in captured.out

    # Check no child issues message
    assert "No child issues found" in captured.out


def test_view_jira_ticket_without_children(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test that child issues are not shown when show_children=False."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "description": "Test description",
        }
    })

    view_jira_ticket("PROJ-12345", show_children=False)

    captured = capsys.readouterr()
    # Check ticket info is present
    assert "Key: PROJ-12345" in captured.out
    assert "Summary: Test ticket" in captured.out

    # Check child issues are NOT present
    assert "Child Issues:" not in captured.out
    assert "No child issues found" not in captured.out


def test_format_comments_basic():
    """Test formatting comments with basic data."""
    comments = [
        {
            "id": "10001",
            "author": "John Doe",
            "created": "2025-12-05T20:13:45.380+0000",
            "body": "This is a comment",
        },
        {
            "id": "10002",
            "author": "Jane Smith",
            "created": "2025-12-05T20:14:00.401+0000",
            "body": "This is another comment\nwith multiple lines",
        }
    ]

    result = format_comments_for_claude(comments)

    assert "Comments:" in result
    assert "2025-12-05 20:13:45 | John Doe" in result
    assert "  This is a comment" in result
    assert "2025-12-05 20:14:00 | Jane Smith" in result
    assert "  This is another comment" in result
    assert "  with multiple lines" in result


def test_format_comments_with_visibility():
    """Test formatting comments with visibility restrictions."""
    comments = [
        {
            "id": "10001",
            "author": "John Doe",
            "created": "2025-12-05T20:13:45.380+0000",
            "body": "Restricted comment",
            "visibility": {
                "type": "group",
                "value": "developers"
            }
        }
    ]

    result = format_comments_for_claude(comments)

    assert "Comments:" in result
    assert "[Visibility: group=developers]" in result
    assert "  Restricted comment" in result


def test_format_comments_empty():
    """Test formatting empty comments list."""
    comments = []

    result = format_comments_for_claude(comments)

    assert result == ""


def test_get_comments(mock_jira_cli):
    """Test fetching comments from a JIRA ticket."""
    # First create the ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    mock_jira_cli.set_comments("PROJ-12345", {
        "comments": [
            {
                "id": "10001",
                "author": {"displayName": "John Doe"},
                "created": "2025-12-05T20:13:45.380+0000",
                "body": "First comment",
            },
            {
                "id": "10002",
                "author": {"displayName": "Jane Smith"},
                "created": "2025-12-05T20:14:00.401+0000",
                "body": "Second comment",
                "visibility": {
                    "type": "group",
                    "value": "developers"
                }
            }
        ]
    })

    client = JiraClient()
    comments = client.get_comments("PROJ-12345")

    assert len(comments) == 2
    assert comments[0]["id"] == "10001"
    assert comments[0]["author"] == "John Doe"
    assert comments[0]["body"] == "First comment"
    assert "visibility" not in comments[0]

    assert comments[1]["id"] == "10002"
    assert comments[1]["author"] == "Jane Smith"
    assert comments[1]["body"] == "Second comment"
    assert comments[1]["visibility"]["type"] == "group"
    assert comments[1]["visibility"]["value"] == "developers"


def test_get_comments_no_comments(mock_jira_cli):
    """Test fetching comments when there are none."""
    # First create the ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    mock_jira_cli.set_comments("PROJ-12345", {
        "comments": []
    })

    client = JiraClient()
    comments = client.get_comments("PROJ-12345")

    assert len(comments) == 0


def test_get_ticket_detailed_with_comments(mock_jira_cli):
    """Test fetching a ticket with comments included."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "description": "Test description",
        }
    })

    mock_jira_cli.set_comments("PROJ-12345", {
        "comments": [
            {
                "id": "10001",
                "author": {"displayName": "John Doe"},
                "created": "2025-12-05T20:13:45.380+0000",
                "body": "Test comment",
            }
        ]
    })

    client = JiraClient()
    ticket = client.get_ticket_detailed("PROJ-12345", include_comments=True)

    assert ticket is not None
    assert "comments" in ticket
    assert len(ticket["comments"]) == 1
    assert ticket["comments"][0]["author"] == "John Doe"


def test_view_jira_ticket_with_comments(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test viewing a JIRA ticket with comments."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
            "description": "Test description",
            "priority": {"name": "Major"},
        }
    })

    mock_jira_cli.set_comments("PROJ-12345", {
        "comments": [
            {
                "id": "10001",
                "author": {"displayName": "John Doe"},
                "created": "2025-12-05T20:13:45.380+0000",
                "body": "First comment",
            },
            {
                "id": "10002",
                "author": {"displayName": "Jane Smith"},
                "created": "2025-12-05T20:14:00.000+0000",
                "body": "Second comment",
            }
        ]
    })

    view_jira_ticket("PROJ-12345", show_comments=True)

    captured = capsys.readouterr()
    # Check ticket info is present
    assert "Key: PROJ-12345" in captured.out
    assert "Summary: Test ticket" in captured.out

    # Check comments are present
    assert "Comments:" in captured.out
    assert "2025-12-05 20:13:45 | John Doe" in captured.out
    assert "  First comment" in captured.out
    assert "2025-12-05 20:14:00 | Jane Smith" in captured.out
    assert "  Second comment" in captured.out


def test_view_jira_ticket_without_comments(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test that comments are not shown when show_comments=False."""
    # Use DEVAIFLOW_HOME to point to temp directory
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "description": "Test description",
        }
    })

    view_jira_ticket("PROJ-12345", show_comments=False)

    captured = capsys.readouterr()
    # Check ticket info is present
    assert "Key: PROJ-12345" in captured.out
    assert "Summary: Test ticket" in captured.out

    # Check comments are NOT present
    assert "Comments:" not in captured.out


def test_format_ticket_with_url_fields():
    """Test formatting ticket with URL fields (git_pull_request, *_url)."""
    ticket_data = {
        "key": "PROJ-123",
        "summary": "Test",
        "type": "Story",
        "status": "New",
        "git_pull_request": "https://github.com/org/repo/pull/123, https://github.com/org/repo/pull/124",
        "documentation_url": "https://docs.example.com"
    }

    result = format_ticket_for_claude(ticket_data)

    assert "Git Pull Requests:" in result
    assert "  - https://github.com/org/repo/pull/123" in result
    assert "  - https://github.com/org/repo/pull/124" in result
    assert "Documentation Url: https://docs.example.com" in result


def test_format_ticket_with_url_fields_list_format():
    """Test formatting ticket with URL fields as list."""
    ticket_data = {
        "key": "PROJ-123",
        "summary": "Test",
        "type": "Story",
        "status": "New",
        "git_pull_request": ["https://github.com/org/repo/pull/123", "https://github.com/org/repo/pull/124"],
    }

    result = format_ticket_for_claude(ticket_data)

    assert "Git Pull Requests:" in result
    assert "  - https://github.com/org/repo/pull/123" in result
    assert "  - https://github.com/org/repo/pull/124" in result


def test_format_ticket_with_long_text_fields():
    """Test formatting ticket with long text custom fields."""
    long_text = "A" * 150
    ticket_data = {
        "key": "PROJ-123",
        "summary": "Test",
        "type": "Story",
        "status": "New",
        "technical_details": long_text
    }

    result = format_ticket_for_claude(ticket_data)

    assert "Technical Details:" in result
    assert long_text in result


def test_format_ticket_skips_empty_values():
    """Test that empty and None values are skipped."""
    ticket_data = {
        "key": "PROJ-123",
        "summary": "Test",
        "type": "Story",
        "status": "New",
        "empty_field": "",
        "none_field": None,
        "valid_field": "Value"
    }

    result = format_ticket_for_claude(ticket_data)

    assert "Empty Field:" not in result
    assert "None Field:" not in result
    assert "Valid Field: Value" in result


def test_format_changelog_missing_timestamp():
    """Test changelog formatting when timestamp is missing."""
    changelog = {
        "histories": [
            {
                "created": "",
                "author": {"displayName": "John Doe"},
                "items": [
                    {
                        "field": "status",
                        "fromString": "New",
                        "toString": "Done"
                    }
                ]
            }
        ]
    }

    result = format_changelog_for_claude(changelog)

    assert "Unknown time" in result
    assert "John Doe" in result


def test_format_changelog_invalid_timestamp():
    """Test changelog formatting with invalid timestamp format."""
    changelog = {
        "histories": [
            {
                "created": "invalid-timestamp",
                "author": {"displayName": "John Doe"},
                "items": [
                    {
                        "field": "status",
                        "fromString": "New",
                        "toString": "Done"
                    }
                ]
            }
        ]
    }

    result = format_changelog_for_claude(changelog)

    # Should fallback to first 19 characters
    assert "invalid-timestamp" in result


def test_format_comments_missing_timestamp():
    """Test comments formatting when timestamp is missing."""
    comments = [
        {
            "created": "",
            "author": "John Doe",
            "body": "Comment with no timestamp"
        }
    ]

    result = format_comments_for_claude(comments)

    assert "Unknown time" in result
    assert "John Doe" in result
    assert "  Comment with no timestamp" in result


def test_format_comments_invalid_timestamp():
    """Test comments formatting with invalid timestamp format."""
    comments = [
        {
            "created": "invalid-timestamp",
            "author": "John Doe",
            "body": "Comment with invalid timestamp"
        }
    ]

    result = format_comments_for_claude(comments)

    # Should fallback to first 19 characters
    assert "invalid-timestamp" in result


def test_view_jira_ticket_json_output_success(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for successful ticket view."""
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "description": "Test description",
        }
    })

    view_jira_ticket("PROJ-12345", output_json=True)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["success"] is True
    assert output["data"]["ticket"]["key"] == "PROJ-12345"
    assert output["data"]["ticket"]["summary"] == "Test ticket"


def test_view_jira_ticket_json_output_with_changelog(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output with changelog data."""
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        },
        "changelog": {
            "histories": [
                {
                    "created": "2025-12-05T20:13:45.380+0000",
                    "author": {"displayName": "John Doe"},
                    "items": [
                        {
                            "field": "status",
                            "fromString": "New",
                            "toString": "Done"
                        }
                    ]
                }
            ]
        }
    }, expand_changelog=True)

    view_jira_ticket("PROJ-12345", show_history=True, output_json=True)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["success"] is True
    assert "changelog" in output["data"]
    assert len(output["data"]["changelog"]) == 1
    assert output["data"]["changelog"][0]["field"] == "status"


def test_view_jira_ticket_json_output_not_found(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for not found error."""
    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    with pytest.raises(SystemExit) as exc_info:
        view_jira_ticket("PROJ-99999", output_json=True)

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["success"] is False
    assert output["error"]["code"] == "NOT_FOUND"


def test_view_jira_ticket_auth_error_json(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for auth error."""
    from devflow.jira.exceptions import JiraAuthError
    from unittest.mock import patch

    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    with patch('devflow.jira.client.JiraClient.get_ticket_detailed', side_effect=JiraAuthError("Auth failed", status_code=401)):
        with pytest.raises(SystemExit) as exc_info:
            view_jira_ticket("PROJ-12345", output_json=True)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["error"]["code"] == "AUTH_ERROR"


def test_view_jira_ticket_api_error_json(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for API error."""
    from devflow.jira.exceptions import JiraApiError
    from unittest.mock import patch

    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    with patch('devflow.jira.client.JiraClient.get_ticket_detailed', side_effect=JiraApiError("API error", status_code=500, response_text="Error")):
        with pytest.raises(SystemExit) as exc_info:
            view_jira_ticket("PROJ-12345", output_json=True)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["error"]["code"] == "API_ERROR"
        assert output["error"]["status_code"] == 500


def test_view_jira_ticket_connection_error_json(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for connection error."""
    from devflow.jira.exceptions import JiraConnectionError
    from unittest.mock import patch

    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    with patch('devflow.jira.client.JiraClient.get_ticket_detailed', side_effect=JiraConnectionError("Connection failed")):
        with pytest.raises(SystemExit) as exc_info:
            view_jira_ticket("PROJ-12345", output_json=True)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["error"]["code"] == "CONNECTION_ERROR"


def test_view_jira_ticket_runtime_error(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test handling of RuntimeError."""
    from unittest.mock import patch

    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    with patch('devflow.config.loader.ConfigLoader.load_config', side_effect=RuntimeError("Config error")):
        with pytest.raises(SystemExit) as exc_info:
            view_jira_ticket("PROJ-12345", output_json=False)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Config error" in captured.out


def test_view_jira_ticket_runtime_error_json(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for RuntimeError."""
    from unittest.mock import patch

    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    with patch('devflow.config.loader.ConfigLoader.load_config', side_effect=RuntimeError("Config error")):
        with pytest.raises(SystemExit) as exc_info:
            view_jira_ticket("PROJ-12345", output_json=True)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["error"]["code"] == "RUNTIME_ERROR"


def test_view_jira_ticket_unexpected_error_json(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for unexpected error."""
    from unittest.mock import patch

    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    with patch('devflow.config.loader.ConfigLoader.load_config', side_effect=ValueError("Unexpected")):
        with pytest.raises(SystemExit) as exc_info:
            view_jira_ticket("PROJ-12345", output_json=True)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["error"]["code"] == "UNEXPECTED_ERROR"


def test_view_jira_ticket_children_auth_error_json(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for auth error when fetching children."""
    from devflow.jira.exceptions import JiraAuthError
    from unittest.mock import patch, MagicMock

    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    with patch('devflow.jira.client.JiraClient.get_child_issues', side_effect=JiraAuthError("Auth failed", status_code=401)):
        with pytest.raises(SystemExit) as exc_info:
            view_jira_ticket("PROJ-12345", show_children=True, output_json=True)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["error"]["code"] == "AUTH_ERROR"


def test_view_jira_ticket_children_api_error_json(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for API error when fetching children."""
    from devflow.jira.exceptions import JiraApiError
    from unittest.mock import patch

    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    with patch('devflow.jira.client.JiraClient.get_child_issues', side_effect=JiraApiError("API error", status_code=500, response_text="Error")):
        with pytest.raises(SystemExit) as exc_info:
            view_jira_ticket("PROJ-12345", show_children=True, output_json=True)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["error"]["code"] == "API_ERROR"
        assert output["error"]["status_code"] == 500


def test_view_jira_ticket_children_connection_error_json(mock_jira_cli, temp_daf_home, monkeypatch, capsys):
    """Test JSON output for connection error when fetching children."""
    from devflow.jira.exceptions import JiraConnectionError
    from unittest.mock import patch

    monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    with patch('devflow.jira.client.JiraClient.get_child_issues', side_effect=JiraConnectionError("Connection failed")):
        with pytest.raises(SystemExit) as exc_info:
            view_jira_ticket("PROJ-12345", show_children=True, output_json=True)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["error"]["code"] == "CONNECTION_ERROR"
