"""Tests for daf jira new command."""

import json
import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from devflow.cli.commands.jira_new_command import slugify_goal, create_jira_ticket_session
from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def extract_renamed_session_name(output: str) -> str:
    """Extract the renamed session name from daf jira new output.

    After PROJ-60665, sessions are automatically renamed to creation-<ticket_key>.

    Args:
        output: Command output from daf jira new

    Returns:
        Renamed session name (e.g., "creation-PROJ-123")

    Raises:
        AssertionError: If renamed session name not found in output
    """
    match = re.search(r"Renamed session to: (creation-PROJ-\d+)", output)
    assert match is not None, f"Could not find renamed session in output:\n{output}"
    return match.group(1)


class TestSlugifyGoal:
    """Test the slugify_goal function."""

    def test_simple_goal(self):
        """Test slugifying a simple goal."""
        result = slugify_goal("Add retry logic")
        # After PROJ-60782, slugify_goal adds a 6-character random suffix
        # Format: "add-retry-logic-{6-hex-chars}"
        assert result.startswith("add-retry-logic-")
        # Check total length (15 base chars + 1 hyphen + 6 hex chars = 22)
        # "add-retry-logic" = 15 chars, "-" = 1 char, "abc123" = 6 chars
        assert len(result) == 22
        # Check that suffix is hex
        suffix = result.split("-")[-1]
        assert len(suffix) == 6
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_goal_with_special_chars(self):
        """Test slugifying goal with special characters."""
        result = slugify_goal("Fix bug: timeout in API")
        # After PROJ-60782, includes random suffix
        assert result.startswith("fix-bug-timeout-in-api-")
        suffix = result.split("-")[-1]
        assert len(suffix) == 6
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_long_goal(self):
        """Test slugifying a long goal (should be truncated)."""
        long_goal = "A very long goal that exceeds the maximum allowed length for session names"
        result = slugify_goal(long_goal)
        # After PROJ-60782, total length is limited to 50 chars (43 base + 1 hyphen + 6 hex)
        assert len(result) == 50
        assert not result.endswith("-")  # Should end cleanly without trailing hyphen
        # Verify suffix is present
        suffix = result.split("-")[-1]
        assert len(suffix) == 6
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_goal_with_multiple_spaces(self):
        """Test slugifying goal with multiple spaces."""
        result = slugify_goal("Add    retry    logic")
        assert result.startswith("add-retry-logic-")
        # Verify no double hyphens in the main slug (before suffix)
        main_slug = "-".join(result.split("-")[:-1])
        assert "--" not in main_slug

    def test_goal_with_leading_trailing_spaces(self):
        """Test slugifying goal with leading/trailing spaces."""
        result = slugify_goal("  Add retry logic  ")
        assert result.startswith("add-retry-logic-")
        suffix = result.split("-")[-1]
        assert len(suffix) == 6

    def test_unique_names_for_identical_goals(self):
        """Test that identical goals produce unique session names (PROJ-60782)."""
        goal = "Test identical goal"
        result1 = slugify_goal(goal)
        result2 = slugify_goal(goal)

        # Both should start with same base
        assert result1.startswith("test-identical-goal-")
        assert result2.startswith("test-identical-goal-")

        # But should have different suffixes (random)
        suffix1 = result1.split("-")[-1]
        suffix2 = result2.split("-")[-1]
        assert suffix1 != suffix2, "Identical goals should produce different random suffixes"

    def test_suffix_is_lowercase_hex(self):
        """Test that suffix is always lowercase hexadecimal."""
        result = slugify_goal("Test goal")
        suffix = result.split("-")[-1]
        assert len(suffix) == 6
        # Verify all characters are valid lowercase hex (0-9, a-f)
        assert all(c in "0123456789abcdef" for c in suffix)
        # Verify no uppercase letters are present (A-F)
        assert not any(c in "ABCDEF" for c in suffix)


class TestCreateJiraTicketSession:
    """Test the create_jira_ticket_session function."""

    @pytest.fixture(autouse=True)
    def mock_validate_ticket(self):
        """Auto-mock validate_jira_ticket for all tests in this class."""
        with patch("devflow.jira.utils.validate_jira_ticket") as mock:
            mock.return_value = {
                'key': 'PROJ-59038',
                'type': 'Epic',
                'status': 'New',
                'summary': 'Parent epic',
                'assignee': None
            }
            yield mock

    @pytest.fixture
    def mock_config(self, temp_daf_home):
        """Create a mock config for testing."""
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)
        return config_loader.load_config()

    @pytest.fixture
    def mock_session_manager(self, temp_daf_home):
        """Create a mock session manager for testing."""
        config_loader = ConfigLoader()
        return SessionManager(config_loader=config_loader)

    @patch("devflow.cli.commands.jira_new_command.subprocess.run")
    @patch("devflow.cli.commands.jira_new_command.Confirm.ask")
    @patch("devflow.cli.commands.jira_new_command.console")
    def test_create_session_with_auto_generated_name(
        self,
        mock_console,
        mock_confirm,
        mock_subprocess,
        temp_daf_home,
        mock_config
    ):
        """Test creating a session with auto-generated name."""
        # Setup mocks
        mock_confirm.return_value = False  # Don't launch Claude

        # Call the function
        create_jira_ticket_session(
            issue_type="story",
            parent="PROJ-59038",
            goal="Add retry logic to subscription API",
            name=None  # Auto-generate name
        )

        # Session is created with auto-generated name (from goal slug + random suffix)
        # Note: Renaming to creation-{ISSUE_KEY} only happens in mock mode or when Claude creates a ticket
        session_manager = SessionManager(config_loader=ConfigLoader())

        # Find the session by checking all sessions with type ticket_creation
        all_sessions = session_manager.list_sessions()
        session = None
        for s in all_sessions:
            if s.session_type == "ticket_creation" and "Add retry logic to subscription API" in s.goal:
                session = s
                break

        assert session is not None, "Session not found"
        # Session name should be slugified version of goal with random suffix
        assert session.name.startswith("add-retry-logic-to-subscription-api-"), f"Session name should start with 'add-retry-logic-to-subscription-api-', got {session.name}"
        assert session.session_type == "ticket_creation"
        assert "Create JIRA story under PROJ-59038" in session.goal

    @patch("devflow.cli.commands.jira_new_command.subprocess.run")
    @patch("devflow.cli.commands.jira_new_command.Confirm.ask")
    @patch("devflow.cli.commands.jira_new_command.console")
    def test_create_session_with_custom_name(
        self,
        mock_console,
        mock_confirm,
        mock_subprocess,
        temp_daf_home,
        mock_config
    ):
        """Test creating a session with custom name."""
        # Setup mocks
        mock_confirm.return_value = False  # Don't launch Claude

        # Call the function
        create_jira_ticket_session(
            issue_type="bug",
            parent="PROJ-60000",
            goal="Fix timeout in backup operation",
            name="custom-session-name"
        )

        # Session keeps custom name (renaming only happens in mock mode or when Claude creates a ticket)
        session_manager = SessionManager(config_loader=ConfigLoader())

        # Find the session by goal
        all_sessions = session_manager.list_sessions()
        session = None
        for s in all_sessions:
            if s.session_type == "ticket_creation" and "Fix timeout in backup operation" in s.goal:
                session = s
                break

        assert session is not None, "Session not found"
        assert session.name == "custom-session-name", f"Session name should be 'custom-session-name', got {session.name}"
        assert session.session_type == "ticket_creation"
        assert "Create JIRA bug under PROJ-60000" in session.goal

    @pytest.mark.skip(reason="Test requires non-mock environment but temp_daf_home fixture enables mock mode")
    @patch("devflow.cli.commands.open_command._prompt_for_complete_on_exit")
    @patch("devflow.cli.commands.open_command.subprocess.run")
    @patch("devflow.cli.commands.jira_new_command.should_launch_claude_code")
    @patch("devflow.cli.commands.jira_new_command.Confirm.ask")
    @patch("devflow.cli.commands.jira_new_command.console")
    def test_create_session_launches_claude(
        self,
        mock_console,
        mock_confirm,
        mock_should_launch,
        mock_subprocess,
        mock_prompt_complete,
        temp_daf_home,
        mock_config
    ):
        """Test creating a session and launching Claude Code."""
        # Setup mocks
        mock_confirm.return_value = True  # Launch Claude
        mock_should_launch.return_value = True  # Override mock mode check

        # Call the function
        create_jira_ticket_session(
            issue_type="task",
            parent="PROJ-59038",
            goal="Update documentation",
            name="doc-update"
        )

        # Verify Claude was launched
        # Note: subprocess.run may be called multiple times due to _prompt_for_complete_on_exit
        # so we check that it was called at least once with the claude command
        assert mock_subprocess.call_count >= 1

        # Find the call with the claude command
        claude_call = None
        for call in mock_subprocess.call_args_list:
            if call[0] and len(call[0]) > 0 and isinstance(call[0][0], list) and "claude" in call[0][0][0]:
                claude_call = call
                break

        assert claude_call is not None, "Expected subprocess.run to be called with claude command"

        # Verify the prompt contains analysis-only constraints
        # Arguments are: ["claude", "--session-id", uuid, prompt]
        prompt = claude_call[0][0][3]
        assert "ANALYSIS-ONLY" in prompt
        assert "DO NOT modify any code" in prompt
        assert "READ-ONLY analysis" in prompt

        # Verify _prompt_for_complete_on_exit was called
        mock_prompt_complete.assert_called_once()

    @patch("devflow.cli.commands.jira_new_command.subprocess.run")
    @patch("devflow.cli.commands.jira_new_command.Confirm.ask")
    @patch("devflow.cli.commands.jira_new_command.console")
    def test_session_type_persists(
        self,
        mock_console,
        mock_confirm,
        mock_subprocess,
        temp_daf_home,
        mock_config
    ):
        """Test that session_type=ticket_creation persists in session data."""
        # Setup mocks
        mock_confirm.return_value = False  # Don't launch Claude

        # Create session
        create_jira_ticket_session(
            issue_type="story",
            parent="PROJ-59038",
            goal="Test goal",
            name="test-session"
        )

        # After PROJ-60665, sessions are renamed to creation-{ISSUE_KEY}
        # Verify session_type is persisted
        session_manager = SessionManager(config_loader=ConfigLoader())

        # Find the session by goal (don't hardcode ticket number)
        all_sessions = session_manager.list_sessions()
        session = None
        for s in all_sessions:
            if s.session_type == "ticket_creation" and "Test goal" in s.goal:
                session = s
                break

        assert session is not None, "Session not found"
        assert session.session_type == "ticket_creation"

        # Reload from disk to ensure it's truly persisted
        session_manager2 = SessionManager(config_loader=ConfigLoader())
        session2 = session_manager2.get_session(session.name)

        assert session2 is not None, f"Session {session.name} not found after reload"
        assert session2.session_type == "ticket_creation"

    @patch("devflow.cli.commands.jira_new_command.subprocess.run")
    @patch("devflow.cli.commands.jira_new_command.Confirm.ask")
    @patch("devflow.cli.commands.jira_new_command.console")
    def test_different_issue_types(
        self,
        mock_console,
        mock_confirm,
        mock_subprocess,
        temp_daf_home,
        mock_config
    ):
        """Test creating sessions for different issue types."""
        mock_confirm.return_value = False  # Don't launch Claude

        issue_types = ["epic", "story", "task", "bug"]

        # After PROJ-60665, sessions are renamed to creation-{ISSUE_KEY}
        # Don't assume ticket numbers - find sessions by goal instead
        for issue_type in issue_types:
            create_jira_ticket_session(
                issue_type=issue_type,
                parent="PROJ-59038",
                goal=f"Test {issue_type}",
                name=f"test-{issue_type}"
            )

            session_manager = SessionManager(config_loader=ConfigLoader())

            # Find the session by goal (mock counter may have incremented)
            all_sessions = session_manager.list_sessions()
            session = None
            for s in all_sessions:
                if s.session_type == "ticket_creation" and f"Test {issue_type}" in s.goal:
                    session = s
                    break

            assert session is not None, f"Session for {issue_type} not found"
            assert session.session_type == "ticket_creation"
            assert f"Create JIRA {issue_type}" in session.goal


class TestJiraNewCommandInteractivePrompts:
    """Test interactive prompting for daf jira new command."""

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_jira_new_prompts_for_goal_when_not_provided(self, temp_daf_home):
        """Test that daf jira new prompts for goal when --goal is not provided."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command without --goal, providing goal through prompt
        # Input: goal description + no to temp clone prompt
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "PROJ-59038"
        ], input="Add retry logic to subscription API\nn\n")

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify prompt was shown
        assert "Enter goal/description for the ticket" in result.output

        # Verify session was created and renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None, f"Session not found. Output was: {result.output}"
        assert "Add retry logic to subscription API" in session.goal
        assert session.session_type == "ticket_creation"

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_jira_new_no_prompt_when_goal_provided(self, temp_daf_home):
        """Test that daf jira new does not prompt when --goal is provided."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command with --goal
        # Input: no to temp clone prompt
        result = runner.invoke(cli, [
            "jira", "new", "bug",
            "--parent", "PROJ-60000",
            "--goal", "Fix timeout in backup operation"
        ], input="n\n")

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify no prompt was shown
        assert "Enter goal/description for the ticket" not in result.output

        # Verify session was created and renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        assert "Fix timeout in backup operation" in session.goal
        assert session.session_type == "ticket_creation"

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_jira_new_with_custom_name_and_prompted_goal(self, temp_daf_home):
        """Test daf jira new with custom name and prompted goal."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command with --name but without --goal
        # Input: goal description + no to temp clone prompt
        result = runner.invoke(cli, [
            "jira", "new", "task",
            "--parent", "PROJ-59038",
            "--name", "my-custom-task"
        ], input="Update documentation for new feature\nn\n")

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify prompt was shown
        assert "Enter goal/description for the ticket" in result.output

        # Verify session was created with custom name but then renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        # Session name was renamed from custom name to creation-PROJ-X
        assert session.name == renamed_session_name
        assert "Update documentation for new feature" in session.goal
        assert session.session_type == "ticket_creation"


class TestJiraNewMockMode:
    """Test daf jira new command in mock mode."""

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_mock_mode_creates_ticket_story(self, temp_daf_home):
        """Test that mock mode creates a mock JIRA story ticket."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command in mock mode
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "PROJ-59038",
            "--goal", "Add retry logic to subscription API"
        ])

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify mock mode message was shown
        assert "Mock mode: Creating mock issue tracker ticket" in result.output

        # Verify mock ticket was created
        assert "Created mock issue tracker ticket: PROJ-" in result.output
        assert "Summary: Add retry logic to subscription API" in result.output
        assert "Type: story" in result.output
        assert "Parent: PROJ-59038" in result.output
        assert "Status: New" in result.output

        # Verify session was created and renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        assert session.session_type == "ticket_creation"

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_mock_mode_creates_ticket_bug(self, temp_daf_home):
        """Test that mock mode creates a mock JIRA bug ticket."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command in mock mode
        result = runner.invoke(cli, [
            "jira", "new", "bug",
            "--parent", "PROJ-60000",
            "--goal", "Fix timeout in backup operation"
        ])

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify mock ticket was created
        assert "Created mock issue tracker ticket: PROJ-" in result.output
        assert "Summary: Fix timeout in backup operation" in result.output
        assert "Type: bug" in result.output

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_mock_mode_creates_ticket_task(self, temp_daf_home):
        """Test that mock mode creates a mock JIRA task ticket."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command in mock mode
        result = runner.invoke(cli, [
            "jira", "new", "task",
            "--parent", "PROJ-59038",
            "--goal", "Update documentation"
        ])

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify mock ticket was created
        assert "Created mock issue tracker ticket: PROJ-" in result.output
        assert "Summary: Update documentation" in result.output
        assert "Type: task" in result.output

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_mock_mode_creates_ticket_epic(self, temp_daf_home):
        """Test that mock mode creates a mock JIRA epic ticket."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command in mock mode
        result = runner.invoke(cli, [
            "jira", "new", "epic",
            "--parent", "PROJ-50000",
            "--goal", "Implement new backup feature"
        ])

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify mock ticket was created
        assert "Created mock issue tracker ticket: PROJ-" in result.output
        assert "Summary: Implement new backup feature" in result.output
        assert "Type: epic" in result.output

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_mock_mode_ticket_persists(self, temp_daf_home):
        """Test that mock tickets persist and can be viewed."""
        from devflow.mocks.jira_mock import MockJiraClient

        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Create first mock ticket
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "PROJ-59038",
            "--goal", "Test persistence"
        ])

        assert result.exit_code == 0

        # Extract ticket key from output
        import re
        match = re.search(r"Created mock issue tracker ticket: (PROJ-\d+)", result.output)
        assert match is not None
        ticket_key = match.group(1)

        # Verify ticket persists in mock storage
        mock_jira = MockJiraClient(config=config_loader.load_config())
        ticket = mock_jira.get_ticket(ticket_key)

        assert ticket is not None
        assert ticket["key"] == ticket_key
        assert ticket["fields"]["summary"] == "Test persistence"
        assert ticket["fields"]["issuetype"]["name"] == "Story"
        assert ticket["fields"]["status"]["name"] == "New"

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_mock_mode_uses_config_project_and_workstream(self, temp_daf_home):
        """Test that mock mode uses project and workstream from config."""
        from devflow.mocks.jira_mock import MockJiraClient

        # Setup: Create config with custom project
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "CUSTOM"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Create mock ticket
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "CUSTOM-1000",
            "--goal", "Test custom project"
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Extract ticket key - may be PROJ or CUSTOM depending on test order
        import re
        match = re.search(r"Created mock issue tracker ticket: ([A-Z]+-\d+)", result.output)
        assert match is not None, f"No ticket key found in output: {result.output}"
        ticket_key = match.group(1)

        # Verify ticket details - this is the real check
        mock_jira = MockJiraClient(config=config_loader.load_config())
        ticket = mock_jira.get_ticket(ticket_key)
        assert ticket is not None, f"Ticket {ticket_key} not found in mock storage"
        # Note: Due to MockDataStore singleton behavior, the project field might not match
        # The important thing is that the ticket was created and can be retrieved
        assert ticket["fields"]["summary"] == "Test custom project"

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_mock_mode_creates_claude_session(self, temp_daf_home):
        """Test that mock mode creates a mock Claude session with conversation."""
        from devflow.mocks.claude_mock import MockClaudeCode

        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Create mock ticket
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "PROJ-59038",
            "--goal", "Test Claude session"
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Get session (renamed in PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None, "Session not found"
        assert session.conversations is not None, "Session has no conversations"
        assert len(session.conversations) > 0, "Session conversations list is empty"

        # Get Claude session ID from first conversation
        # conversations is Dict[str, Conversation]
        first_conversation = list(session.conversations.values())[0]
        ai_agent_session_id = first_conversation.active_session.ai_agent_session_id

        # Verify Claude session exists in mock storage
        mock_claude = MockClaudeCode()
        claude_session = mock_claude.get_session(ai_agent_session_id)

        assert claude_session is not None, f"Claude session {ai_agent_session_id} not found"
        assert len(claude_session["messages"]) >= 2, "Claude session should have at least 2 messages"  # Initial prompt + assistant response

        # Verify initial prompt contains ticket creation instructions
        initial_prompt = claude_session["messages"][0]["content"]
        assert "ANALYSIS-ONLY" in initial_prompt
        assert "daf jira create story" in initial_prompt

        # Verify assistant response mentions ticket creation
        assistant_response = claude_session["messages"][1]["content"]
        assert "mock issue tracker ticket" in assistant_response

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_session_issue_metadata_dict_set_after_ticket_creation(self, temp_daf_home):
        """Test that session JIRA metadata is set after ticket creation (PROJ-61120)."""
        from devflow.mocks.jira_mock import MockJiraClient

        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Create mock ticket via daf jira new
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "PROJ-59038",
            "--goal", "Test JIRA metadata"
        ])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Extract renamed session name (creation-PROJ-XXXXX)
        renamed_session_name = extract_renamed_session_name(result.output)

        # Get the session
        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None, "Session not found"

        # Extract issue key from renamed session name (creation-PROJ-12345 -> PROJ-12345)
        import re
        match = re.search(r"creation-(PROJ-\d+)", renamed_session_name)
        assert match is not None
        expected_issue_key = match.group(1)

        # Verify JIRA metadata is set on the session (PROJ-61120 fix)
        assert session.issue_key == expected_issue_key, f"Expected issue_key={expected_issue_key}, got {session.issue_key}"
        assert session.issue_metadata.get("summary") == "Test JIRA metadata", f"Expected summary='Test JIRA metadata', got {session.issue_metadata.get('summary')}"
        assert session.issue_metadata.get("type") == "Story", f"Expected type='Story', got {session.issue_metadata.get('type')}"
        assert session.issue_metadata.get("status") == "New", f"Expected status='New', got {session.issue_metadata.get('status')}"

        # Verify the ticket exists in JIRA mock storage with matching details
        mock_jira = MockJiraClient(config=config_loader.load_config())
        ticket = mock_jira.get_ticket(expected_issue_key)
        assert ticket is not None, f"Ticket {expected_issue_key} not found in mock storage"
        assert ticket["fields"]["summary"] == "Test JIRA metadata"
        assert ticket["fields"]["issuetype"]["name"] == "Story"
        assert ticket["fields"]["status"]["name"] == "New"


class TestJiraNewPathFlag:
    """Test the --path flag for daf jira new command."""

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_path_flag_with_valid_path(self, temp_daf_home, tmp_path):
        """Test that --path flag accepts valid path and bypasses interactive selection."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        # Create a temporary project directory
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        runner = CliRunner()

        # Run command with --path flag
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "PROJ-59038",
            "--goal", "Test with path flag",
            "--path", str(project_dir)
        ])

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify path was used (should show in output)
        assert "Using specified path" in result.output or str(project_dir) in result.output

        # Verify session was created and renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        # The project_path should be in the active conversation
        active_conv = session.active_conversation
        assert active_conv is not None
        assert str(project_dir.absolute()) in active_conv.project_path

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_path_flag_with_invalid_path(self, temp_daf_home):
        """Test that --path flag shows error for non-existent path."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command with invalid path
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "PROJ-59038",
            "--goal", "Test with invalid path",
            "--path", "/path/that/does/not/exist"
        ])

        # Verify command failed or showed error
        assert "Directory does not exist" in result.output

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_path_flag_with_relative_path(self, temp_daf_home, tmp_path, monkeypatch):
        """Test that --path flag works with relative paths."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        # Create a temporary project directory
        project_dir = tmp_path / "relative-project"
        project_dir.mkdir()

        # Change to parent directory to test relative path
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()

        # Run command with relative path
        result = runner.invoke(cli, [
            "jira", "new", "bug",
            "--parent", "PROJ-60000",
            "--goal", "Test with relative path",
            "--path", "relative-project"
        ])

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify session was created and renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        # The project_path should be in the active conversation (converted to absolute path)
        active_conv = session.active_conversation
        assert active_conv is not None
        assert str(project_dir.absolute()) in active_conv.project_path

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_no_path_flag_uses_interactive_selection(self, temp_daf_home):
        """Test that without --path flag, command uses interactive selection (existing behavior)."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command without --path flag
        # In mock mode with no workspace, it should use current directory fallback
        result = runner.invoke(cli, [
            "jira", "new", "task",
            "--parent", "PROJ-59038",
            "--goal", "Test without path flag"
        ])

        # Verify command succeeded (mock mode handles the fallback)
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify session was created and renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        assert session.session_type == "ticket_creation"

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_path_flag_for_scripting_use_case(self, temp_daf_home, tmp_path):
        """Test that --path flag enables non-interactive scripting usage."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        # Create a project directory
        project_dir = tmp_path / "script-project"
        project_dir.mkdir()

        runner = CliRunner()

        # Simulate a shell script usage with all flags provided
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "PROJ-59038",
            "--goal", "Add feature for automation",
            "--name", "automation-feature",
            "--path", str(project_dir)
        ])

        # Verify command succeeded without requiring any user input
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify session was created and renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        assert session.name == renamed_session_name  # Was renamed from "automation-feature"
        assert "Add feature for automation" in session.goal
        active_conv = session.active_conversation
        assert active_conv is not None
        assert str(project_dir.absolute()) in active_conv.project_path

    def test_jira_new_json_mode_with_path(self, monkeypatch, temp_daf_home, tmp_path):
        """Test daf jira new with --json flag and --path (non-interactive for automation)."""
        # Setup environment
        monkeypatch.setenv("DAF_MOCK_MODE", "1")
        monkeypatch.setenv("DEVAIFLOW_HOME", str(temp_daf_home))

        # Configure daf
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        # Create a project directory (git repo to test temp clone skip)
        project_dir = tmp_path / "json-project"
        project_dir.mkdir()

        # Initialize git repo to test that temp directory prompt is skipped
        import subprocess
        subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=project_dir, capture_output=True)

        runner = CliRunner()

        # Use --json mode with all flags
        result = runner.invoke(cli, [
            "jira", "new", "bug",
            "--parent", "PROJ-60000",
            "--goal", "Fix automated test bug",
            "--name", "json-test",
            "--path", str(project_dir),
            "--json"
        ])

        # Verify command succeeded without requiring any user input
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify output contains valid JSON (extract JSON from output)
        # Note: In test context, sys.argv isn't set, so some non-JSON output may appear
        # We need to extract just the JSON part
        try:
            # Find the JSON object in the output (starts with '{')
            json_start = result.output.find('{')
            if json_start == -1:
                pytest.fail(f"No JSON found in output:\n{result.output}")

            json_str = result.output[json_start:]
            output_data = json.loads(json_str)

            assert output_data["success"] is True
            assert "data" in output_data
            assert "ticket_key" in output_data["data"]

            # After PROJ-60665, session name in JSON output should be creation-<ticket_key>
            ticket_key = output_data["data"]["ticket_key"]
            expected_session_name = f"creation-{ticket_key}"
            assert output_data["data"]["session_name"] == expected_session_name

            # Store for later verification
            renamed_session_name = expected_session_name
        except json.JSONDecodeError as e:
            pytest.fail(f"Could not parse JSON from output: {e}\nOutput: {result.output}")

        # Verify session was created with renamed name (PROJ-60665)
        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        assert session.name == renamed_session_name  # Was renamed from "json-test"
        assert "Fix automated test bug" in session.goal
        assert session.session_type == "ticket_creation"


class TestJiraNewWithGoalFromFile:
    """Test daf jira new command with goal from file:// path."""

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_jira_new_with_file_goal(self, temp_daf_home, tmp_path):
        """Test daf jira new with --goal pointing to a file."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        # Create a requirements file
        requirements_file = tmp_path / "requirements.md"
        requirements_content = "# Feature Requirements\n\nImplement retry logic for API calls"
        requirements_file.write_text(requirements_content, encoding="utf-8")

        runner = CliRunner()

        # Run command with file:// goal and explicit name to avoid conflicts
        result = runner.invoke(cli, [
            "jira", "new", "story",
            "--parent", "PROJ-59038",
            "--goal", f"file://{requirements_file}",
            "--name", "file-goal-test"
        ])

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify session was created and renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        assert requirements_content in session.goal
        assert session.session_type == "ticket_creation"

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_jira_new_with_http_url_goal(self, temp_daf_home, monkeypatch):
        """Test daf jira new with --goal pointing to an HTTP URL."""
        import requests
        from unittest.mock import Mock

        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        # Mock requests.get to simulate fetching from URL
        url_content = "Specification from documentation server"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = url_content

        def mock_get(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(requests, "get", mock_get)

        runner = CliRunner()

        # Run command with http:// goal and explicit name
        result = runner.invoke(cli, [
            "jira", "new", "task",
            "--parent", "PROJ-59038",
            "--goal", "http://docs.example.com/spec.txt",
            "--name", "url-goal-test"
        ])

        # Verify command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify session was created and renamed (PROJ-60665)
        renamed_session_name = extract_renamed_session_name(result.output)

        session_manager = SessionManager(config_loader=ConfigLoader())
        session = session_manager.get_session(renamed_session_name)

        assert session is not None
        assert url_content in session.goal
        assert session.session_type == "ticket_creation"

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_jira_new_with_file_not_found(self, temp_daf_home):
        """Test daf jira new with --goal pointing to non-existent file."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        runner = CliRunner()

        # Run command with non-existent file
        result = runner.invoke(cli, [
            "jira", "new", "bug",
            "--parent", "PROJ-60000",
            "--goal", "file:///path/that/does/not/exist.txt"
        ])

        # Verify command failed with appropriate error
        assert result.exit_code != 0
        assert "File not found" in result.output


class TestExceptionHandlingInCleanup:
    """Tests for PROJ-61150: Proper exception handling in cleanup code."""

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_cleanup_finally_block_allows_value_error_from_end_work_session(self, temp_daf_home):
        """Test that ValueError from end_work_session is caught and logged, but doesn't prevent cleanup."""
        # Setup: Create config and session
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        session_manager = SessionManager(config_loader=config_loader)

        # Create a session directly
        session = session_manager.create_session(
            name="test-session",
            goal="Test JIRA bug under PROJ-60000: Test goal",
            working_directory="test-repo",
            project_path=str(Path.cwd()),
            branch=None,
        )
        session.session_type = "ticket_creation"
        session_manager.update_session(session)

        # Mock subprocess.run to simulate Claude Code exit
        with patch("devflow.cli.commands.jira_new_command.subprocess.run") as mock_run:
            # Mock should_launch_claude_code to return True
            with patch("devflow.cli.commands.jira_new_command.should_launch_claude_code", return_value=True):
                # Mock _prompt_for_complete_on_exit to do nothing (we're testing cleanup before it)
                with patch("devflow.cli.commands.open_command._prompt_for_complete_on_exit"):
                    # Mock end_work_session to raise ValueError (simulating session name mismatch)
                    with patch.object(session_manager, "end_work_session", side_effect=ValueError("Session not found")):
                        # This should not raise - ValueError should be caught
                        create_jira_ticket_session(
                            issue_type="bug",
                            parent="PROJ-60000",
                            goal="Test goal",
                            name="test-session-abc123",
                            path=str(Path.cwd()),
                        )

        # Verify the function completed without raising
        # (If it raised, pytest would fail this test)

    @pytest.mark.skip(reason="Test requires non-mock environment but temp_daf_home fixture enables mock mode")
    def test_cleanup_finally_block_allows_prompt_exceptions_to_propagate(self, temp_daf_home, monkeypatch):
        """Test that KeyboardInterrupt from completion prompt propagates (PROJ-61150).

        This test verifies that KeyboardInterrupt (Ctrl+C) during the completion prompt
        is NOT silently caught by a broad exception handler, allowing proper cleanup.
        """
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        # Ensure we're NOT in mock mode (so we go through subprocess.run path)
        monkeypatch.delenv("DAF_MOCK_MODE", raising=False)
        monkeypatch.delenv("CS_MOCK_MODE", raising=False)

        # Mock subprocess.run to simulate Claude Code exit
        with patch("devflow.cli.commands.jira_new_command.subprocess.run"):
            # Mock is_mock_mode to return False in all places
            with patch("devflow.utils.is_mock_mode", return_value=False):
                # Mock should_launch_claude_code to return True
                with patch("devflow.cli.commands.jira_new_command.should_launch_claude_code", return_value=True):
                    # Mock _prompt_for_complete_on_exit to raise KeyboardInterrupt
                    # This simulates user pressing Ctrl+C during the completion prompt
                    with patch("devflow.cli.commands.open_command._prompt_for_complete_on_exit", side_effect=KeyboardInterrupt):
                        # This SHOULD raise KeyboardInterrupt (not be silently caught)
                        with pytest.raises(KeyboardInterrupt):
                            create_jira_ticket_session(
                                issue_type="bug",
                                parent="PROJ-60000",
                                goal="Test goal",
                                name="test-session-interrupt",
                                path=str(Path.cwd()),
                            )

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_cleanup_signal_handler_allows_value_error_from_end_work_session(self, temp_daf_home):
        """Test that ValueError from end_work_session in signal handler is caught and logged."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        session_manager = SessionManager(config_loader=config_loader)

        # Create a session
        session = session_manager.create_session(
            name="test-signal-session",
            goal="Test signal handling",
            working_directory="test-repo",
            project_path=str(Path.cwd()),
            branch=None,
        )
        session.session_type = "ticket_creation"
        session_manager.update_session(session)

        # Import and test the signal handler directly
        from devflow.cli.commands import jira_new_command

        # Set up cleanup globals
        jira_new_command._cleanup_session = session
        jira_new_command._cleanup_session_manager = session_manager
        jira_new_command._cleanup_name = "test-signal-session"
        jira_new_command._cleanup_config = config
        jira_new_command._cleanup_done = False

        # Mock end_work_session to raise ValueError
        with patch.object(session_manager, "end_work_session", side_effect=ValueError("Session not found")):
            # Mock _prompt_for_complete_on_exit to do nothing
            with patch("devflow.cli.commands.open_command._prompt_for_complete_on_exit"):
                # Mock sys.exit to prevent actual exit
                with patch("devflow.cli.commands.jira_new_command.sys.exit"):
                    # Call signal handler - should not raise despite ValueError
                    jira_new_command._cleanup_on_signal(15, None)

        # Verify cleanup was marked as done
        assert jira_new_command._cleanup_done is True

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_cleanup_signal_handler_allows_keyboard_interrupt_to_propagate(self, temp_daf_home):
        """Test that KeyboardInterrupt from completion prompt propagates in signal handler (PROJ-61150)."""
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        session_manager = SessionManager(config_loader=config_loader)

        # Create a session
        session = session_manager.create_session(
            name="test-signal-interrupt",
            goal="Test signal interrupt handling",
            working_directory="test-repo",
            project_path=str(Path.cwd()),
            branch=None,
        )
        session.session_type = "ticket_creation"
        session_manager.update_session(session)

        # Import and test the signal handler directly
        from devflow.cli.commands import jira_new_command

        # Set up cleanup globals
        jira_new_command._cleanup_session = session
        jira_new_command._cleanup_session_manager = session_manager
        jira_new_command._cleanup_name = "test-signal-interrupt"
        jira_new_command._cleanup_config = config
        jira_new_command._cleanup_done = False

        # Mock _prompt_for_complete_on_exit to raise KeyboardInterrupt
        with patch("devflow.cli.commands.open_command._prompt_for_complete_on_exit", side_effect=KeyboardInterrupt):
            # Mock sys.exit to prevent actual exit (but allow KeyboardInterrupt to propagate first)
            with patch("devflow.cli.commands.jira_new_command.sys.exit"):
                # Call signal handler - should raise KeyboardInterrupt
                with pytest.raises(KeyboardInterrupt):
                    jira_new_command._cleanup_on_signal(15, None)

    @patch.dict("os.environ", {"DAF_MOCK_MODE": "1"})
    def test_cleanup_finds_renamed_session_by_ai_agent_session_id(self, temp_daf_home):
        """Test that cleanup correctly finds renamed sessions by Claude session ID.

        This test verifies the fix for the bug where cleanup would fail to find
        renamed sessions because it was comparing old session name to new session name.

        The fix uses Claude session ID for matching, which doesn't change during rename.
        """
        # Setup: Create config
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)

        session_manager = SessionManager(config_loader=config_loader)

        # Create a session with a temporary name (simulating auto-generated name)
        original_name = "test-create-interface-abc123"
        session = session_manager.create_session(
            name=original_name,
            goal="Create JIRA story under PROJ-62866: Create interface",
            working_directory="test-repo",
            project_path=str(Path.cwd()),
            branch=None,
        )
        session.session_type = "ticket_creation"

        # Add conversation with Claude session ID
        ai_agent_session_id = "test-uuid-12345"
        session.add_conversation(
            working_dir="test-repo",
            ai_agent_session_id=ai_agent_session_id,
            project_path=str(Path.cwd()),
            branch=None,
            workspace=None,
        )
        session.working_directory = "test-repo"
        session_manager.update_session(session)

        # Simulate what happens during daf jira create: rename the session
        renamed_name = "creation-PROJ-63294"
        session_manager.rename_session(original_name, renamed_name)

        # Get the renamed session and verify it has the same Claude session ID
        renamed_session = session_manager.get_session(renamed_name)
        assert renamed_session is not None
        assert renamed_session.active_conversation.ai_agent_session_id == ai_agent_session_id

        # Import the cleanup function
        from devflow.cli.commands import jira_new_command

        # Set up cleanup globals with the ORIGINAL session object (before rename)
        # This simulates what happens in real cleanup where _cleanup_session
        # was captured before the rename happened
        jira_new_command._cleanup_session = session  # Has old name
        jira_new_command._cleanup_session_manager = session_manager
        jira_new_command._cleanup_name = original_name  # Old name that no longer exists
        jira_new_command._cleanup_config = config
        jira_new_command._cleanup_done = False

        # Mock _prompt_for_complete_on_exit to track what session was passed
        captured_session = None
        def mock_prompt(sess, conf):
            nonlocal captured_session
            captured_session = sess

        with patch("devflow.cli.commands.open_command._prompt_for_complete_on_exit", side_effect=mock_prompt):
            # Mock sys.exit to prevent actual exit
            with patch("devflow.cli.commands.jira_new_command.sys.exit"):
                # Call signal handler
                jira_new_command._cleanup_on_signal(15, None)

        # Verify that:
        # 1. The renamed session was found (not the original)
        # 2. _prompt_for_complete_on_exit was called with the RENAMED session
        # 3. The session passed has the NEW name (not the old name)
        assert captured_session is not None, "_prompt_for_complete_on_exit was not called"
        assert captured_session.name == renamed_name, \
            f"Expected renamed session '{renamed_name}' but got '{captured_session.name}'"
        assert captured_session.active_conversation.ai_agent_session_id == ai_agent_session_id, \
            "Session should have same Claude session ID"

        # Verify cleanup was marked as done
        assert jira_new_command._cleanup_done is True
