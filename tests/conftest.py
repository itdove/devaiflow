"""Pytest configuration and fixtures."""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def unset_ai_session_env_vars(monkeypatch):
    """Automatically unset AI session environment variables for all tests.

    This allows tests to run inside Claude Code without triggering the
    safety guards that prevent commands like 'daf open', 'daf new', etc.
    from running inside an AI agent session.

    This is an autouse fixture, so it applies to all tests automatically.
    """
    monkeypatch.delenv("DEVAIFLOW_IN_SESSION", raising=False)
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)


@pytest.fixture
def mock_jira_cli(monkeypatch):
    """Mock the JIRA REST API and CLI calls.

    Returns a MockJiraCLI instance that can be configured to return
    specific responses for JIRA REST API and CLI commands.

    Example usage:
        def test_something(mock_jira_cli):
            # Configure mock responses
            mock_jira_cli.set_ticket("PROJ-12345", {
                "key": "PROJ-12345",
                "fields": {
                    "summary": "Test ticket",
                    "status": {"name": "In Progress"},
                    "issuetype": {"name": "Story"},
                }
            })

            # Run command that calls JIRA
            # JIRA REST API and CLI calls will be intercepted and return mock data
    """
    # Set JIRA environment variables for REST API client
    monkeypatch.setenv("JIRA_API_TOKEN", "mock-token-for-testing")
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")

    mock = MockJiraCLI()

    # Set environment variables for JIRA client
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    monkeypatch.setenv("JIRA_URL", "https://test.jira.com")

    # Monkey-patch subprocess.run to intercept JIRA CLI calls
    original_run = subprocess.run

    def mock_subprocess_run(cmd, *args, **kwargs):
        """Intercept subprocess.run calls and handle JIRA commands."""
        # Check if this is a jira CLI command
        if isinstance(cmd, list) and cmd[0] == "jira":
            return mock.handle_command(cmd)
        # Pass through non-jira commands
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # Monkey-patch requests.request to intercept JIRA REST API calls
    def mock_request(method, url, **kwargs):
        """Intercept requests.request calls and handle JIRA REST API."""
        return mock.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    # Monkey-patch requests.post for file attachments
    def mock_post(url, **kwargs):
        """Intercept requests.post calls for file attachments."""
        return mock.handle_rest_post(url, **kwargs)

    monkeypatch.setattr("requests.post", mock_post)

    return mock


@pytest.fixture
def temp_daf_home(tmp_path, monkeypatch):
    """Create a temporary .daf-sessions directory for testing.

    This fixture ensures tests don't modify the user's actual sessions.
    Also removes AI_AGENT_SESSION_ID from environment to allow tests to run
    inside Claude Code without triggering nested session detection.

    Additionally, this fixture copies the default patches from the project
    to the temp directory so that tests can verify patch application behavior.
    """
    import json
    import shutil

    daf_home = tmp_path / ".daf-sessions"
    daf_home.mkdir()

    # Create backends directory with minimal valid jira.json
    backends_dir = daf_home / "backends"
    backends_dir.mkdir()
    jira_config = backends_dir / "jira.json"
    jira_config.write_text(json.dumps({
        "url": "https://jira.test.com",
        "user": "test-user",
        "transitions": {}
    }, indent=2))

    # Create minimal valid organization.json
    org_config = daf_home / "organization.json"
    org_config.write_text(json.dumps({
        "jira_project": "TEST",
        "sync_filters": {
            "sync": {
                "status": [],
                "required_fields": [],
                "assignee": "currentUser()"
            }
        }
    }, indent=2))

    # Monkey-patch Path.home() to return temp directory
    def mock_home():
        return tmp_path

    monkeypatch.setattr(Path, "home", mock_home)

    # Remove AI_AGENT_SESSION_ID from environment if present
    # This allows tests to run inside Claude Code without triggering
    # the "Cannot run 'daf open' while inside Claude Code" protection
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    return daf_home


@pytest.fixture
def temp_daf_home_no_patches(tmp_path, monkeypatch):
    """Create a temporary .daf-sessions directory for testing WITHOUT patches.

    This fixture is used for tests that need to test custom config values
    without patches overriding them.
    """
    import json

    daf_home = tmp_path / ".daf-sessions"
    daf_home.mkdir()

    # Create backends directory with minimal valid jira.json
    backends_dir = daf_home / "backends"
    backends_dir.mkdir()
    jira_config = backends_dir / "jira.json"
    jira_config.write_text(json.dumps({
        "url": "https://jira.test.com",
        "user": "test-user",
        "transitions": {}
    }, indent=2))

    # Create minimal valid organization.json
    org_config = daf_home / "organization.json"
    org_config.write_text(json.dumps({
        "jira_project": "TEST",
        "sync_filters": {
            "sync": {
                "status": [],
                "required_fields": [],
                "assignee": "currentUser()"
            }
        }
    }, indent=2))

    # Monkey-patch Path.home() to return temp directory
    def mock_home():
        return tmp_path

    monkeypatch.setattr(Path, "home", mock_home)

    # Remove AI_AGENT_SESSION_ID from environment if present
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    return daf_home


class MockJiraCLI:
    """Mock JIRA CLI and REST API for testing."""

    def __init__(self):
        """Initialize mock JIRA CLI and REST API."""
        self.tickets: Dict[str, Dict[str, Any]] = {}
        self.comments: Dict[str, List[str]] = {}
        self.attachments: Dict[str, List[str]] = {}
        self.transitions: Dict[str, str] = {}
        self.fail_commands: List[str] = []
        self.available_transitions: Dict[str, List[Dict[str, Any]]] = {}
        self.transition_errors: Dict[str, Dict[str, Any]] = {}  # Store transition error responses
        self.search_results: Dict[str, Dict[str, Any]] = {}  # Store JQL query -> search results mapping

    def set_ticket(self, key: str, data: Dict[str, Any], expand_changelog: bool = False) -> None:
        """Configure a mock issue tracker ticket.

        Args:
            key: issue tracker key (e.g., "PROJ-12345")
            data: Ticket data dictionary
            expand_changelog: If True, include changelog data in the response
        """
        self.tickets[key] = data
        # Store whether this ticket includes changelog for later use in GET requests
        if expand_changelog and "changelog" in data:
            if not hasattr(self, 'tickets_with_changelog'):
                self.tickets_with_changelog = {}
            self.tickets_with_changelog[key] = data["changelog"]

    def add_comment(self, key: str, comment: str) -> None:
        """Add a comment to a ticket (for verification).

        Args:
            key: issue tracker key
            comment: Comment text
        """
        if key not in self.comments:
            self.comments[key] = []
        self.comments[key].append(comment)

    def add_attachment(self, key: str, filename: str) -> None:
        """Add an attachment to a ticket (for verification).

        Args:
            key: issue tracker key
            filename: Attachment filename
        """
        if key not in self.attachments:
            self.attachments[key] = []
        self.attachments[key].append(filename)

    def set_transition(self, key: str, new_status: str) -> None:
        """Record a status transition.

        Args:
            key: issue tracker key
            new_status: New status name
        """
        self.transitions[key] = new_status
        # Update ticket status if it exists
        if key in self.tickets:
            self.tickets[key]["fields"]["status"]["name"] = new_status

    def fail_next_command(self, command_pattern: str) -> None:
        """Make the next matching command fail.

        Args:
            command_pattern: Pattern to match (e.g., "issue view")
        """
        self.fail_commands.append(command_pattern)

    def set_transition_error(self, key: str, error_response: Dict[str, Any]) -> None:
        """Configure a transition to fail with specific error response.

        Args:
            key: issue tracker key
            error_response: Error response dict with errorMessages and/or errors fields
        """
        self.transition_errors[key] = error_response

    def set_search_results(self, search_config: Dict[str, Any]) -> None:
        """Configure mock search results for a specific JQL query.

        Args:
            search_config: Dictionary with 'jql' key for the query and 'issues' key for results
                          Example: {"jql": "parent = PROJ-123", "issues": [...]}
        """
        jql = search_config.get("jql")
        issues = search_config.get("issues", [])
        if jql:
            self.search_results[jql] = {"issues": issues}

    def handle_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Handle a JIRA CLI command and return mock response.

        Args:
            cmd: Command list (e.g., ["jira", "issue", "view", "PROJ-12345"])

        Returns:
            Mock CompletedProcess with appropriate returncode and stdout
        """
        # Join command parts for pattern matching
        cmd_str = " ".join(cmd)

        # Check if this command should fail
        for pattern in self.fail_commands[:]:
            if pattern in cmd_str:
                self.fail_commands.remove(pattern)
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="",
                    stderr=f"Error: Mock JIRA command failed: {cmd_str}",
                )

        # Parse command type
        if len(cmd) >= 3:
            if cmd[1] == "issue" and cmd[2] == "view":
                return self._handle_issue_view(cmd)
            elif cmd[1] == "issue" and cmd[2] == "comment":
                return self._handle_issue_comment(cmd)
            elif cmd[1] == "issue" and cmd[2] == "attach":
                return self._handle_issue_attach(cmd)
            elif cmd[1] == "issue" and cmd[2] == "move":
                return self._handle_issue_move(cmd)
            elif cmd[1] == "issue" and cmd[2] == "list":
                return self._handle_issue_list(cmd)

        # Unknown command - return error
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr=f"Unknown JIRA command: {cmd_str}",
        )

    def _handle_issue_view(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Handle 'jira issue view <KEY>' command."""
        if len(cmd) < 4:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="Missing ticket key"
            )

        key = cmd[3]

        if key not in self.tickets:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr=f"Error: Issue {key} not found",
            )

        ticket_data = self.tickets[key]

        # Check if --plain flag is present
        if "--plain" in cmd:
            # Return plain text format
            fields = ticket_data.get("fields", {})
            output_lines = [
                f"KEY: {key}",
            ]

            if "issuetype" in fields:
                output_lines.append(f"TYPE: {fields['issuetype'].get('name', '')}")
            if "status" in fields:
                output_lines.append(f"STATUS: {fields['status'].get('name', '')}")
            if "summary" in fields:
                output_lines.append(f"SUMMARY: {fields['summary']}")
            if "customfield_sprint" in fields:
                output_lines.append(f"SPRINT: {fields['customfield_sprint']}")
            if "customfield_12310243" in fields:
                output_lines.append(f"STORY POINTS: {fields['customfield_12310243']}")
            if "assignee" in fields and fields['assignee']:
                output_lines.append(f"ASSIGNEE: {fields['assignee'].get('displayName', '')}")
            if "customfield_epic" in fields:
                output_lines.append(f"EPIC: {fields['customfield_epic']}")

            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="\n".join(output_lines),
                stderr="",
            )
        else:
            # Return ticket data as JSON
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=json.dumps(ticket_data),
                stderr="",
            )

    def _handle_issue_comment(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Handle 'jira issue comment <KEY> --comment <TEXT>' command."""
        if len(cmd) < 5:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="Missing arguments"
            )

        key = cmd[3]

        # Extract comment text after --comment flag
        comment_text = ""
        if "--comment" in cmd:
            comment_idx = cmd.index("--comment")
            if comment_idx + 1 < len(cmd):
                comment_text = cmd[comment_idx + 1]
        else:
            comment_text = " ".join(cmd[4:])

        if key not in self.tickets:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr=f"Error: Issue {key} not found",
            )

        self.add_comment(key, comment_text)

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=f"Comment added to {key}",
            stderr="",
        )

    def _handle_issue_attach(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Handle 'jira issue attach <KEY> <FILE>' command."""
        if len(cmd) < 5:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="Missing arguments"
            )

        key = cmd[3]
        filename = cmd[4]

        if key not in self.tickets:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr=f"Error: Issue {key} not found",
            )

        self.add_attachment(key, filename)

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=f"Attached {filename} to {key}",
            stderr="",
        )

    def _handle_issue_move(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Handle 'jira issue move <KEY> <STATUS>' command."""
        if len(cmd) < 5:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="Missing arguments"
            )

        key = cmd[3]
        new_status = " ".join(cmd[4:]).strip('"')

        if key not in self.tickets:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr=f"Error: Issue {key} not found",
            )

        self.set_transition(key, new_status)

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=f"Moved {key} to {new_status}",
            stderr="",
        )

    def _handle_issue_list(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Handle 'jira issue list' command."""
        # Check if --plain flag is present
        if "--plain" in cmd:
            # Return plain text format with one ticket key per line
            ticket_keys = list(self.tickets.keys())
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="\n".join(ticket_keys),
                stderr="",
            )
        else:
            # Return list of all tickets as JSON
            tickets = list(self.tickets.values())
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=json.dumps(tickets),
                stderr="",
            )

    def handle_rest_request(self, method: str, url: str, **kwargs) -> MagicMock:
        """Handle JIRA REST API requests.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            url: Full URL of the request
            **kwargs: Additional request arguments

        Returns:
            Mock response object
        """
        response = MagicMock()

        # Extract ticket key from URL if present
        if "/rest/api/2/issue/" in url:
            parts = url.split("/rest/api/2/issue/")
            if len(parts) > 1:
                endpoint = parts[1]
                # Extract key (before ? or /)
                key_part = endpoint.split("?")[0].split("/")[0]
                key = key_part

                # Handle GET /rest/api/2/issue/{key} (may include ?expand=changelog)
                # Only handle if there's no sub-path after the key (except query params)
                rest_of_endpoint = endpoint[len(key):]
                is_simple_get = method == "GET" and (rest_of_endpoint == "" or rest_of_endpoint.startswith("?"))

                if is_simple_get:
                    if key in self.tickets:
                        response.status_code = 200
                        ticket_data = self.tickets[key].copy()

                        # Check if changelog should be included
                        if "expand=changelog" in url and hasattr(self, 'tickets_with_changelog') and key in self.tickets_with_changelog:
                            ticket_data["changelog"] = self.tickets_with_changelog[key]

                        response.json.return_value = ticket_data
                        return response
                    else:
                        response.status_code = 404
                        response.text = f"Issue {key} not found"
                        return response

                # Handle POST /rest/api/2/issue/{key}/comment
                elif method == "POST" and "/comment" in endpoint:
                    if key in self.tickets:
                        # Extract comment from request body
                        json_data = kwargs.get("json", {})
                        comment_body = json_data.get("body", "")
                        self.add_comment(key, comment_body)
                        response.status_code = 201
                        response.json.return_value = {"id": "12345"}
                    else:
                        response.status_code = 404
                        response.text = f"Issue {key} not found"
                    return response

                # Handle GET /rest/api/2/issue/{key}/transitions
                elif method == "GET" and "/transitions" in endpoint:
                    if key in self.tickets:
                        # Return available transitions
                        transitions = self.available_transitions.get(key, [
                            {"id": "1", "name": "In Progress", "to": {"name": "In Progress"}},
                            {"id": "2", "name": "Done", "to": {"name": "Done"}},
                            {"id": "3", "name": "Review", "to": {"name": "Review"}},
                        ])
                        response.status_code = 200
                        response.json.return_value = {"transitions": transitions}
                    else:
                        response.status_code = 404
                    return response

                # Handle POST /rest/api/2/issue/{key}/transitions
                elif method == "POST" and "/transitions" in endpoint:
                    if key in self.tickets:
                        # Check if this transition should fail with an error
                        if key in self.transition_errors:
                            response.status_code = 400
                            error_data = self.transition_errors[key]
                            response.json.return_value = error_data
                            response.text = json.dumps(error_data)
                            # Remove the error so subsequent calls can succeed if needed
                            del self.transition_errors[key]
                            return response

                        # Extract transition from request body
                        json_data = kwargs.get("json", {})
                        transition_id = json_data.get("transition", {}).get("id")

                        # Find the transition name
                        transitions = self.available_transitions.get(key, [
                            {"id": "1", "name": "In Progress", "to": {"name": "In Progress"}},
                            {"id": "2", "name": "Done", "to": {"name": "Done"}},
                            {"id": "3", "name": "Review", "to": {"name": "Review"}},
                        ])
                        for trans in transitions:
                            if trans["id"] == transition_id:
                                new_status = trans["to"]["name"]
                                self.set_transition(key, new_status)
                                response.status_code = 204
                                return response

                        response.status_code = 400
                        response.text = "Invalid transition"
                    else:
                        response.status_code = 404
                    return response

        # Handle GET /rest/api/2/search (list tickets)
        elif "/rest/api/2/search" in url:
            if method == "GET":
                # Extract JQL from params
                params = kwargs.get("params", {})
                jql = params.get("jql", "")

                # Check if we have configured search results for this JQL
                if jql in self.search_results:
                    response.status_code = 200
                    response.json.return_value = self.search_results[jql]
                    return response

                # Fallback: Return all tickets as search results
                issues = list(self.tickets.values())
                response.status_code = 200
                response.json.return_value = {"issues": issues}
                return response

        # Handle GET /rest/api/2/field (field metadata)
        elif "/rest/api/2/field" in url:
            if method == "GET":
                response.status_code = 200
                response.json.return_value = [
                    {"id": "customfield_12310243", "name": "Story Points"},
                    {"id": "customfield_12310940", "name": "Sprint"},
                    {"id": "customfield_12311140", "name": "Epic Link"},
                ]
                return response

        # Unknown endpoint
        response.status_code = 404
        response.text = f"Unknown endpoint: {url}"
        return response

    def handle_rest_post(self, url: str, **kwargs) -> MagicMock:
        """Handle JIRA REST API POST requests (for attachments).

        Args:
            url: Full URL of the request
            **kwargs: Additional request arguments

        Returns:
            Mock response object
        """
        response = MagicMock()

        # Handle POST /rest/api/2/issue/{key}/attachments
        if "/rest/api/2/issue/" in url and "/attachments" in url:
            parts = url.split("/rest/api/2/issue/")
            if len(parts) > 1:
                key = parts[1].split("/")[0]

                if key in self.tickets:
                    # Extract filename from files parameter
                    files = kwargs.get("files", {})
                    if files:
                        # files is a dict like {'file': file_object}
                        # For testing, we'll just record that an attachment was made
                        self.add_attachment(key, "attachment")
                    response.status_code = 200
                else:
                    response.status_code = 404
                    response.text = f"Issue {key} not found"
                return response

        # Unknown endpoint
        response.status_code = 404
        response.text = f"Unknown endpoint: {url}"
        return response


@pytest.fixture
def sample_pr_template():
    """Fixture providing sample PR template content."""
    return """<!--- Put Jira story/task/bug number in the link below -->
Jira Issue: <https://jira.example.com/browse/PROJ-NNNN>
<!-- This PR does not need a corresponding Jira item. -->

## Description
<!-- Describe the changes introduced in the PR below -->

## Testing
<!-- Describe the testing process -->
### Steps to test
1. Pull down the PR
2. Run tests

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""


@pytest.fixture
def sample_filled_pr_template():
    """Fixture providing a pre-filled PR template (simulating AI output)."""
    return """Jira Issue: <https://jira.example.com/browse/PROJ-12345>

## Description
This PR adds new feature X and fixes bug in component Y.

Changes include:
- Implementation of feature X
- Bug fix in component Y
- Updated tests

## Testing
### Steps to test
1. Pull down the PR
2. Run pytest to verify all tests pass
3. Test feature X manually

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""
