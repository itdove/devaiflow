"""Test workspace_name field in daf list --json output (itdove/devaiflow#65)."""

import json
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_list_json_includes_workspace_name(temp_daf_home):
    """Test that daf list --json includes workspace_name field when set (itdove/devaiflow#65)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with workspace_name set
    session = session_manager.create_session(
        name="test-workspace-session",
        goal="Test workspace display",
        working_directory="test-repo",
        project_path="/path/to/repo",
        ai_agent_session_id="uuid-workspace-test",
    )
    session.workspace_name = "ansible-saas"
    session.issue_key = "PROJ-999"
    session_manager.update_session(session)

    # Test JSON output
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

    assert result.exit_code == 0

    # Parse JSON output
    output_lines = result.output.strip().split('\n')
    json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
    output = json.loads(json_part)

    # Verify success
    assert output["success"] is True
    assert len(output["data"]["sessions"]) == 1

    # Verify workspace_name field is included
    session_data = output["data"]["sessions"][0]
    assert "workspace_name" in session_data, "workspace_name field should be present in JSON output"
    assert session_data["workspace_name"] == "ansible-saas", "workspace_name value should match session data"
    assert session_data["name"] == "test-workspace-session"


def test_list_json_includes_null_workspace_name(temp_daf_home):
    """Test that daf list --json includes workspace_name field as null when not set (itdove/devaiflow#65)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session WITHOUT workspace_name set
    session = session_manager.create_session(
        name="test-no-workspace",
        goal="Test no workspace",
        working_directory="test-repo",
        project_path="/path/to/repo",
        ai_agent_session_id="uuid-no-workspace-test",
    )
    # Explicitly set to None
    session.workspace_name = None
    session_manager.update_session(session)

    # Test JSON output
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

    assert result.exit_code == 0

    # Parse JSON output
    output_lines = result.output.strip().split('\n')
    json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
    output = json.loads(json_part)

    # Verify workspace_name field exists but is null
    session_data = output["data"]["sessions"][0]
    assert "workspace_name" in session_data, "workspace_name field should be present even when null"
    assert session_data["workspace_name"] is None, "workspace_name should be null when not set"


def test_list_json_workspace_name_matches_table_display(temp_daf_home):
    """Test that workspace_name in JSON matches what's shown in table display (itdove/devaiflow#65)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions with different workspace_name values
    session1 = session_manager.create_session(
        name="workspace-ai",
        goal="AI workspace",
        working_directory="repo1",
        project_path="/path/to/repo1",
        ai_agent_session_id="uuid-ai",
    )
    session1.workspace_name = "ai"
    session_manager.update_session(session1)

    session2 = session_manager.create_session(
        name="workspace-ansible-saas",
        goal="Ansible SaaS workspace",
        working_directory="repo2",
        project_path="/path/to/repo2",
        ai_agent_session_id="uuid-ansible",
    )
    session2.workspace_name = "ansible-saas"
    session_manager.update_session(session2)

    session3 = session_manager.create_session(
        name="no-workspace",
        goal="No workspace",
        working_directory="repo3",
        project_path="/path/to/repo3",
        ai_agent_session_id="uuid-none",
    )
    session3.workspace_name = None
    session_manager.update_session(session3)

    # Get JSON output
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--json"], catch_exceptions=False)

    assert result.exit_code == 0
    output_lines = result.output.strip().split('\n')
    json_part = '\n'.join([line for line in output_lines if not line.startswith('Warning:')])
    output = json.loads(json_part)

    # Verify all sessions have correct workspace_name values
    sessions_by_name = {s["name"]: s for s in output["data"]["sessions"]}

    assert sessions_by_name["workspace-ai"]["workspace_name"] == "ai"
    assert sessions_by_name["workspace-ansible-saas"]["workspace_name"] == "ansible-saas"
    assert sessions_by_name["no-workspace"]["workspace_name"] is None
