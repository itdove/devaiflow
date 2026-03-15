"""Tests for multi-project session creation workflow.

This test module verifies the multi-project session creation functionality:
1. Signal handler setup with correct argument order
2. Branch name prompting (avoiding duplicates across projects)
3. Project context in prompts (showing which project each prompt relates to)
4. Backward compatibility with single-project workflows
5. End-to-end multi-project session creation
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from devflow.cli.commands.new_command_multiproject import create_multi_project_session
from devflow.cli.commands.new_command import _handle_branch_creation
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_setup_signal_handlers_correct_arguments(temp_daf_home, tmp_path):
    """Test that setup_signal_handlers is called with correct arguments.

    Issue: Line 298 in new_command_multiproject.py was calling:
        setup_signal_handlers(session_manager, session)

    Expected signature:
        setup_signal_handlers(session, session_manager, identifier, config)

    This caused: TypeError: setup_signal_handlers() missing 2 required positional arguments
    """
    from devflow.cli.signal_handler import setup_signal_handlers
    from devflow.config.models import Session

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    # Create a simple session
    session = session_manager.create_session(
        name="test-signal",
        goal="Test signal handling",
        working_directory="test-repo",
        project_path="/tmp/test-repo",
        ai_agent_session_id="test-uuid",
    )

    # Test that setup_signal_handlers can be called with correct arguments
    # This should NOT raise TypeError
    try:
        setup_signal_handlers(session, session_manager, "test-signal", config)
        success = True
    except TypeError as e:
        success = False
        error_msg = str(e)

    assert success, f"setup_signal_handlers raised TypeError: {error_msg if not success else 'N/A'}"


def test_branch_name_not_asked_twice(temp_daf_home, tmp_path):
    """Test that branch name is only prompted once for multi-project sessions.

    Issue: Branch name was asked twice:
    - Line 109: "Branch name for all projects"
    - Line 1481: _handle_branch_creation asks again

    Fix: Pass branch_name parameter to _handle_branch_creation to skip duplicate prompt.
    """
    # Create test git repo
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    # Mock GitUtils to avoid actual git operations
    with patch('devflow.cli.commands.new_command.GitUtils') as mock_git:
        mock_git.is_git_repository.return_value = True
        mock_git.has_uncommitted_changes.return_value = False
        mock_git.branch_exists.return_value = False
        mock_git.get_current_branch.return_value = 'main'
        mock_git.create_branch.return_value = True
        mock_git.fetch_origin.return_value = True
        mock_git.checkout_branch.return_value = True

        # Mock Prompt to track if it's called
        with patch('devflow.cli.commands.new_command.Prompt') as mock_prompt:
            mock_prompt.ask.return_value = 'test-branch'

            # Call _handle_branch_creation with branch_name pre-provided
            result = _handle_branch_creation(
                project_path=str(repo_path),
                issue_key="TEST-123",
                goal="Test goal",
                auto_from_default=False,
                config=None,
                source_branch='origin/main',
                branch_name='test-branch',  # Pre-provided - should NOT prompt
                project_name='test-project',
            )

            # Verify Prompt.ask was NOT called (branch name already provided)
            assert mock_prompt.ask.call_count == 0, \
                "Should not prompt for branch name when branch_name is provided"

            # Verify branch was created successfully
            assert result == ('test-branch', 'origin/main')


def test_project_context_in_prompts(temp_daf_home, tmp_path):
    """Test that project name is shown in prompts for multi-project sessions.

    Issue: Prompts didn't mention which project they were for, causing confusion.

    Fix: Add project_name parameter and prefix prompts with [project_name].
    """
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    # Mock GitUtils
    with patch('devflow.cli.commands.new_command.GitUtils') as mock_git:
        mock_git.is_git_repository.return_value = True
        mock_git.has_uncommitted_changes.return_value = False
        mock_git.branch_exists.return_value = False
        mock_git.get_current_branch.return_value = 'main'
        mock_git.create_branch.return_value = True
        mock_git.fetch_origin.return_value = True
        mock_git.checkout_branch.return_value = True

        # Mock console_print to capture output
        printed_messages = []

        def capture_print(msg):
            printed_messages.append(msg)

        with patch('devflow.cli.commands.new_command.console_print', side_effect=capture_print):
            # Call _handle_branch_creation with project_name
            result = _handle_branch_creation(
                project_path=str(repo_path),
                issue_key="TEST-123",
                goal="Test goal",
                auto_from_default=True,  # Auto mode to avoid prompts
                config=None,
                source_branch='origin/main',
                branch_name='test-branch',
                project_name='backend-api',  # Project name for context
            )

            # Verify project name appears in messages
            project_prefixed = [msg for msg in printed_messages if '[backend-api]' in msg]

            assert len(project_prefixed) > 0, \
                "At least one message should include [backend-api] prefix"

            # Verify specific messages include project context
            assert any('[backend-api] Detected git repository' in msg for msg in printed_messages), \
                "Git detection message should include project name"

            assert any('[backend-api] Creating branch' in msg for msg in printed_messages), \
                "Branch creation message should include project name"


def test_handle_branch_creation_preserves_backward_compatibility(temp_daf_home, tmp_path):
    """Test that _handle_branch_creation still works without new optional parameters.

    This ensures we don't break existing single-project workflows.
    """
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    # Mock GitUtils
    with patch('devflow.cli.commands.new_command.GitUtils') as mock_git:
        mock_git.is_git_repository.return_value = True
        mock_git.has_uncommitted_changes.return_value = False
        mock_git.branch_exists.return_value = False
        mock_git.generate_branch_name.return_value = 'test-branch'
        mock_git.get_current_branch.return_value = 'main'
        mock_git.create_branch.return_value = True
        mock_git.fetch_origin.return_value = True
        mock_git.checkout_branch.return_value = True

        # Call without new parameters (backward compatibility)
        result = _handle_branch_creation(
            project_path=str(repo_path),
            issue_key="TEST-123",
            goal="Test goal",
            auto_from_default=True,
            config=None,
            source_branch='origin/main',
            # NOT passing branch_name or project_name - should still work
        )

        # Should succeed
        assert result is not None


def test_multi_project_session_creation_end_to_end(temp_daf_home, tmp_path):
    """End-to-end test of multi-project session creation with all fixes applied."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    # Create workspace with two projects
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    for proj_name in ["backend", "frontend"]:
        proj_path = workspace_path / proj_name
        proj_path.mkdir()
        (proj_path / ".git").mkdir()

    # Mock Git operations
    with patch('devflow.cli.commands.new_command.GitUtils') as mock_git:
        mock_git.is_git_repository.return_value = True
        mock_git.has_uncommitted_changes.return_value = False
        mock_git.branch_exists.return_value = False
        mock_git.generate_branch_name.return_value = 'feature-123'
        mock_git.get_current_branch.return_value = 'main'
        mock_git.create_branch.return_value = True
        mock_git.fetch_origin.return_value = True
        mock_git.checkout_branch.return_value = True

        with patch('devflow.cli.commands.new_command._get_default_source_branch') as mock_default:
            mock_default.return_value = 'origin/main'

            # Create multi-project session in JSON mode
            create_multi_project_session(
                session_manager=session_manager,
                config_loader=config_loader,
                config=config,
                name="test-feature",
                goal="Test feature",
                issue_key=None,
                issue_metadata_dict=None,
                issue_title=None,
                project_names=["backend", "frontend"],
                workspace_path=str(workspace_path),
                selected_workspace_name="test-workspace",
                force_new_session=False,
                model_profile=None,
                output_json=True,
            )

            # Verify session was created successfully
            session = session_manager.get_session("test-feature")
            assert session is not None

            # NEW ARCHITECTURE: One conversation with multiple projects
            assert len(session.conversations) == 1

            # Get the multi-project conversation
            active_conv = session.active_conversation
            assert active_conv is not None
            assert active_conv.is_multi_project is True
            assert active_conv.projects is not None
            assert len(active_conv.projects) == 2
            assert "backend" in active_conv.projects
            assert "frontend" in active_conv.projects

            # Verify both projects have correct branches
            # Branch name comes from session name (test-feature), not from GitUtils.generate_branch_name
            assert active_conv.projects["backend"].branch == "test-feature"
            assert active_conv.projects["frontend"].branch == "test-feature"


def test_branch_name_updates_across_projects_when_changed(temp_daf_home, tmp_path):
    """Test that shared_branch_name is updated when branch creation returns different name.

    Bug scenario:
    1. User creates multi-project session with branch name "multi-project-test"
    2. Branch already exists in first project, user provides new name "multi-project-test-2"
    3. BUG: Second project still uses "multi-project-test" (original shared_branch_name)
    4. FIX: Update shared_branch_name when actual branch differs from expected
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    # Create workspace with two projects
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    for proj_name in ["project1", "project2"]:
        proj_path = workspace_path / proj_name
        proj_path.mkdir()
        (proj_path / ".git").mkdir()

    # Track branch names passed to _handle_branch_creation
    branch_creation_params = []

    original_handle_branch = _handle_branch_creation

    def mock_handle_branch_creation(**kwargs):
        """Track parameters and simulate user choosing different branch name."""
        branch_creation_params.append(kwargs.copy())

        # First call: Simulate user choosing different name "multi-project-test-2"
        if len(branch_creation_params) == 1:
            # Return tuple (created_branch, source_branch) as if user created new branch
            return ('multi-project-test-2', 'origin/main')
        # Second call: Should receive the UPDATED branch name "multi-project-test-2"
        else:
            # This would be the bug - if it receives "multi-project-test" instead
            assert kwargs.get('branch_name') == 'multi-project-test-2', \
                f"Bug: Second project received original name '{kwargs.get('branch_name')}' instead of updated 'multi-project-test-2'"
            return ('multi-project-test-2', 'origin/main')

    with patch('devflow.cli.commands.new_command._handle_branch_creation', side_effect=mock_handle_branch_creation):
        # Create multi-project session in JSON mode (simpler mocking)
        create_multi_project_session(
            session_manager=session_manager,
            config_loader=config_loader,
            config=config,
            name="test-multi",
            goal="Test branch update",
            issue_key=None,
            issue_metadata_dict=None,
            issue_title=None,
            project_names=["project1", "project2"],
            workspace_path=str(workspace_path),
            selected_workspace_name="test-workspace",
            force_new_session=False,
            model_profile=None,
            output_json=True,  # JSON mode to avoid interactive prompts
        )

        # Verify session was created
        session = session_manager.get_session("test-multi")
        assert session is not None

        # NEW ARCHITECTURE: One conversation with multiple projects
        assert len(session.conversations) == 1

        # Verify _handle_branch_creation was called twice
        assert len(branch_creation_params) == 2, \
            f"Should have called _handle_branch_creation twice, got {len(branch_creation_params)} calls"

        # Verify first call used original shared_branch_name
        assert branch_creation_params[0]['branch_name'] == 'test-multi', \
            f"First call should use session name 'test-multi', got '{branch_creation_params[0]['branch_name']}'"

        # CRITICAL: Verify second call used UPDATED branch name
        assert branch_creation_params[1]['branch_name'] == 'multi-project-test-2', \
            f"Second call should use updated name 'multi-project-test-2', got '{branch_creation_params[1]['branch_name']}'"

        # Verify both projects have the updated branch name
        active_conv = session.active_conversation
        assert active_conv is not None
        assert active_conv.is_multi_project is True
        project1_branch = active_conv.projects["project1"].branch
        project2_branch = active_conv.projects["project2"].branch

        assert project1_branch == "multi-project-test-2"
        assert project2_branch == "multi-project-test-2"


def test_multi_project_complete_workflow_integration(temp_daf_home, tmp_path):
    """Full integration test: create multi-project session -> make changes -> complete -> create PRs.

    This test verifies the complete multi-project workflow:
    1. Create a multi-project session with 2 projects
    2. Simulate changes in both projects
    3. Run daf complete
    4. Verify PRs are created for each project with correct base branches
    """
    from unittest.mock import MagicMock, call
    from devflow.cli.commands.complete_command import complete_session

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    # Create workspace with two git repositories
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    for proj_name in ["backend", "frontend"]:
        proj_path = workspace_path / proj_name
        proj_path.mkdir()
        (proj_path / ".git").mkdir()

        # Create a test file to simulate changes
        test_file = proj_path / "README.md"
        test_file.write_text(f"# {proj_name.capitalize()} Project\n")

    # Mock Git operations
    with patch('devflow.cli.commands.new_command.GitUtils') as mock_git_new:
        mock_git_new.is_git_repository.return_value = True
        mock_git_new.has_uncommitted_changes.return_value = False
        mock_git_new.branch_exists.return_value = False
        mock_git_new.generate_branch_name.return_value = 'feature-123'
        mock_git_new.get_current_branch.return_value = 'main'
        mock_git_new.create_branch.return_value = True
        mock_git_new.fetch_origin.return_value = True
        mock_git_new.checkout_branch.return_value = True

        with patch('devflow.cli.commands.new_command._get_default_source_branch') as mock_default:
            mock_default.return_value = 'origin/main'

            # Create multi-project session
            create_multi_project_session(
                session_manager=session_manager,
                config_loader=config_loader,
                config=config,
                name="integration-test",
                goal="Integration test for multi-project completion",
                issue_key="TEST-123",
                issue_metadata_dict={"summary": "Test issue"},
                issue_title=None,
                project_names=["backend", "frontend"],
                workspace_path=str(workspace_path),
                selected_workspace_name="test-workspace",
                force_new_session=False,
                model_profile=None,
                output_json=True,
            )

    # Verify session was created correctly
    session = session_manager.get_session("integration-test")
    assert session is not None
    assert len(session.conversations) == 1

    active_conv = session.active_conversation
    assert active_conv is not None
    assert active_conv.is_multi_project is True
    assert len(active_conv.projects) == 2
    assert "backend" in active_conv.projects
    assert "frontend" in active_conv.projects

    # Simulate file changes in both projects
    backend_file = workspace_path / "backend" / "api.py"
    backend_file.write_text("# New backend code\n")

    frontend_file = workspace_path / "frontend" / "app.js"
    frontend_file.write_text("// New frontend code\n")

    # Mock Git operations for completion
    with patch('devflow.cli.commands.complete_command.GitUtils') as mock_git_complete:
        mock_git_complete.is_git_repository.return_value = True
        mock_git_complete.has_uncommitted_changes.return_value = True
        mock_git_complete.get_status_summary.return_value = "M api.py\nM app.js"
        mock_git_complete.commit_all.return_value = True
        mock_git_complete.push_branch.return_value = True
        mock_git_complete.is_branch_pushed.return_value = True
        mock_git_complete.has_unpushed_commits.return_value = True
        mock_git_complete.get_current_branch.return_value = "test-123"  # Match the branch name
        mock_git_complete.get_default_branch.return_value = "main"

        # Mock PR creation functions
        with patch('devflow.cli.commands.complete_command._create_github_pr') as mock_gh_pr:
            with patch('devflow.cli.commands.complete_command._create_gitlab_mr') as mock_gl_mr:
                # Mock GitHub PR creation to return URLs
                mock_gh_pr.return_value = "https://github.com/test/backend/pull/1"

                # Mock Confirm.ask to automatically answer "yes" to prompts
                with patch('devflow.cli.commands.complete_command.Confirm') as mock_confirm:
                    mock_confirm.ask.return_value = True

                    # Mock the @require_outside_claude decorator to bypass the check
                    with patch('devflow.cli.commands.complete_command.require_outside_claude', lambda f: f):
                        # Run daf complete
                        try:
                            with patch('devflow.cli.commands.complete_command.console') as mock_console:
                                complete_session(
                                    identifier="integration-test",
                                    status=None,
                                    attach_to_issue=False,
                                    latest=False,
                                    no_commit=False,
                                    no_pr=False,
                                    no_issue_update=True,  # Skip JIRA updates in test
                                )
                        except SystemExit:
                            # complete_session may exit, that's ok
                            pass

                # Verify Git operations were called for EACH project
                # Should have committed changes in both projects
                assert mock_git_complete.commit_all.call_count >= 2, \
                    f"Should commit in both projects, got {mock_git_complete.commit_all.call_count} calls"

                # Should have pushed branches for both projects
                assert mock_git_complete.push_branch.call_count >= 2, \
                    f"Should push both branches, got {mock_git_complete.push_branch.call_count} calls"

    # Reload session to verify it was marked as completed
    session = session_manager.get_session("integration-test")

    # Session should still exist and have the multi-project conversation
    assert session is not None
    assert session.active_conversation is not None
    assert session.active_conversation.is_multi_project is True
    assert len(session.active_conversation.projects) == 2
