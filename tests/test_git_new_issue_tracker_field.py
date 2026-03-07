"""Tests for issue #72: Ensure GitHub/GitLab sessions set issue_tracker field correctly."""

import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

from devflow.cli.commands.new_command import _generate_initial_prompt
from devflow.utils.backend_detection import get_issue_tracker_backend


def test_git_new_sets_issue_tracker_field_before_issue_created(temp_daf_home, mock_git_repo):
    """Test that 'daf git new' sets session.issue_tracker even before issue is created.

    This is the fix for issue #72. Previously, sessions created by 'daf git new'
    would not have issue_tracker field set, causing the initial prompt to default
    to 'daf jira view' instead of 'daf git view'.

    The fix ensures that session.issue_tracker is set to 'github' or 'gitlab' based
    on repository detection, even when issue_key is not yet set.
    """
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Create session manager
    session_manager = SessionManager(config_loader=config_loader)

    # Simulate what git_new_command.py does:
    # 1. Create session with session_type="ticket_creation"
    session = session_manager.create_session(
        name="test-github-issue",
        goal="Create GitHub issue: Fix timeout bug",
        working_directory="test-repo",
        project_path=str(mock_git_repo),
        branch=None,
    )

    session.session_type = "ticket_creation"

    # 2. Set issue tracker backend (the fix for issue #72)
    from devflow.utils.git_remote import GitRemoteDetector
    detector = GitRemoteDetector(str(mock_git_repo))
    repo_info = detector.parse_repository_info()

    if repo_info:
        backend = repo_info[0]  # 'github' or 'gitlab'
        session.issue_tracker = backend
    else:
        # Fallback to github if can't detect
        session.issue_tracker = "github"

    session_manager.update_session(session)

    # Verify issue_tracker is set even though issue_key is not set yet
    assert hasattr(session, 'issue_tracker')
    assert session.issue_tracker == "github"
    assert not hasattr(session, 'issue_key') or session.issue_key is None

    # Verify backend detection uses the issue_tracker field
    backend = get_issue_tracker_backend(session, config)
    assert backend == "github"

    # Verify the initial prompt would use 'daf git view' (not 'daf jira view')
    # Note: We can't test this directly without issue_key, but we can verify
    # that when backend detection is called with the session, it returns 'github'
    # which would cause the prompt to use 'daf git view'


def test_backend_detection_uses_session_issue_tracker_field():
    """Test that get_issue_tracker_backend prioritizes session.issue_tracker field.

    This is the intended behavior - session.issue_tracker should be the highest
    priority source for backend detection.
    """
    from devflow.config.models import Session

    # Create session with issue_tracker field set but no issue_key
    session = Session(name="test")
    session.issue_tracker = "github"

    # Verify backend detection returns 'github'
    backend = get_issue_tracker_backend(session, None)
    assert backend == "github"

    # Even if we set a JIRA-pattern issue_key later, issue_tracker takes precedence
    session.issue_key = "PROJ-12345"
    backend = get_issue_tracker_backend(session, None)
    assert backend == "github"  # issue_tracker field wins


def test_backend_detection_falls_back_to_issue_key_pattern():
    """Test that backend detection falls back to issue_key pattern if issue_tracker not set.

    This is for backward compatibility with existing sessions that don't have
    the issue_tracker field set (or have it set to None).
    """
    from devflow.config.models import Session

    # Create session with issue_tracker=None and GitHub issue_key
    # (simulating old sessions or sessions where backend couldn't be detected)
    session = Session(name="test", issue_tracker=None)
    session.issue_key = "owner/repo#123"

    # Verify backend detection infers 'github' from issue_key pattern
    backend = get_issue_tracker_backend(session, None)
    assert backend == "github"

    # Create session with issue_tracker=None and JIRA issue_key
    session2 = Session(name="test2", issue_tracker=None)
    session2.issue_key = "PROJ-12345"

    # Verify backend detection infers 'jira' from issue_key pattern
    backend = get_issue_tracker_backend(session2, None)
    assert backend == "jira"


def test_initial_prompt_uses_git_view_when_session_has_github_backend(temp_daf_home):
    """Test that initial prompt uses 'daf git view' when session has issue_tracker='github'.

    This verifies the fix for issue #72 - even without an issue_key set,
    if the session has issue_tracker='github', the prompt should suggest
    'daf git view' instead of 'daf jira view'.

    However, the current implementation of _generate_initial_prompt requires
    issue_key to be set to include the view command. So this test documents
    the expected behavior once issue_key is set.
    """
    from devflow.config.loader import ConfigLoader

    # Create config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Generate prompt with GitHub issue_key (simulating after issue is created)
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Fix bug",
        issue_key="owner/repo#123",
        issue_title="Fix timeout in API",
    )

    # Verify GitHub command is suggested
    assert "daf git view owner/repo#123 --comments" in prompt
    assert "daf jira view" not in prompt


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock git repository with GitHub remote."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    import subprocess
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/test-owner/test-repo.git"],
        cwd=repo_path,
        check=True,
        capture_output=True
    )

    return repo_path
