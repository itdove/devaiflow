"""Tests for complete command."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devflow.cli.commands.complete_command import complete_session
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.jira.exceptions import JiraApiError, JiraNotFoundError, JiraValidationError
from devflow.git.utils import GitUtils


def test_complete_session_basic(temp_daf_home, monkeypatch, capsys):
    """Test completing a session without JIRA."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="complete-test",
        goal="Test completion",
        working_directory="test-dir",
        project_path="/test",
        ai_agent_session_id="uuid-1",
    )

    # Start and end a work session to track time
    session_manager.start_work_session("complete-test")
    session_manager.end_work_session("complete-test")

    # Mock Confirm.ask to avoid interactive prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Complete the session
    complete_session("complete-test")

    # Reload and verify
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("complete-test")
    assert len(sessions) == 1
    assert sessions[0].status == "complete"

    # Check output
    captured = capsys.readouterr()
    assert "marked as complete" in captured.out
    assert "Total time tracked" in captured.out


def test_complete_session_with_jira(temp_daf_home, monkeypatch, capsys):
    """Test completing a session with issue key."""
    # Create a session with issue key
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="jira-complete",
        goal="Complete with JIRA",
        working_directory="jira-dir",
        project_path="/jira",
        ai_agent_session_id="uuid-jira",
        issue_key="PROJ-12345",
    )

    # Start and end work session
    session_manager.start_work_session("jira-complete")
    session_manager.end_work_session("jira-complete")

    # Mock JIRA transition and confirm
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Complete the session
    complete_session("jira-complete")

    # Verify
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("jira-complete")
    assert sessions[0].status == "complete"

    captured = capsys.readouterr()
    assert "PROJ-12345" in captured.out


def test_complete_session_with_summary_to_jira(temp_daf_home, monkeypatch, capsys):
    """Test completing session and adding summary to JIRA."""
    # Create session with JIRA
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="summary-test",
        goal="Test summary",
        working_directory="summary-dir",
        project_path="/summary",
        ai_agent_session_id="uuid-summary",
        issue_key="PROJ-99999",
    )

    # Add work session with some time (at least 5 minutes)
    session_manager.start_work_session("summary-test")
    # Manually add a work session with time to ensure it meets the 5-minute threshold
    session.work_sessions.append({
        "start": datetime.now() - timedelta(minutes=15),
        "end": datetime.now() - timedelta(minutes=5),
        "user": "testuser"
    })
    session_manager.update_session(session)

    # Mock functions
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: True)  # Accept summary
    monkeypatch.setattr("devflow.cli.commands.complete_command.add_jira_comment", lambda *args, **kwargs: True)

    # Complete session
    complete_session("summary-test")

    captured = capsys.readouterr()
    assert "Session summary added to JIRA" in captured.out


def test_complete_session_with_notes(temp_daf_home, monkeypatch, capsys):
    """Test completing session with notes file."""
    # Create session with JIRA
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="notes-test",
        goal="Test with notes",
        working_directory="notes-dir",
        project_path="/notes",
        ai_agent_session_id="uuid-notes",
        issue_key="PROJ-88888",
    )

    # Create notes file
    session_dir = config_loader.get_session_dir("notes-test")
    session_dir.mkdir(parents=True, exist_ok=True)
    notes_file = session_dir / "notes.md"
    notes_file.write_text("Test notes content")

    # Add work session with time (at least 5 minutes)
    session_manager.start_work_session("notes-test")
    # Manually add a work session with time to ensure it meets the 5-minute threshold
    session.work_sessions.append({
        "start": datetime.now() - timedelta(minutes=20),
        "end": datetime.now() - timedelta(minutes=10),
        "user": "testuser"
    })
    session_manager.update_session(session)

    # Mock functions - capture the comment
    captured_comment = []

    def mock_add_comment(issue_key, comment, **kwargs):
        captured_comment.append(comment)
        return True

    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: True)
    monkeypatch.setattr("devflow.cli.commands.complete_command.add_jira_comment", mock_add_comment)

    # Complete session
    complete_session("notes-test")

    # Verify notes were included
    assert len(captured_comment) > 0
    assert "Test notes content" in captured_comment[0]


def test_complete_session_skips_minimal_activity_jira_comment(temp_daf_home, monkeypatch, capsys):
    """Test that JIRA comment is skipped for sessions with minimal/no activity."""
    # Create session with JIRA but minimal activity (like --latest might find)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="minimal-test",
        goal="Recent session",  # Generic goal
        working_directory="recent-dir",  # Generic directory
        project_path="/recent",
        ai_agent_session_id=None,  # No Claude session started
        issue_key="PROJ-11111",
    )

    # No work session added - 0h 0m

    # Mock functions
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)

    # Track if add_jira_comment was called
    comment_added = []
    def mock_add_comment(*args, **kwargs):
        comment_added.append(True)
        return True

    monkeypatch.setattr("devflow.cli.commands.complete_command.add_jira_comment", mock_add_comment)

    # Complete session
    complete_session("minimal-test")

    captured = capsys.readouterr()

    # Should skip JIRA comment
    assert "Skipping JIRA summary - session has minimal activity" in captured.out
    assert len(comment_added) == 0  # Comment should not have been added


def test_complete_session_multiple_users(temp_daf_home, monkeypatch, capsys):
    """Test completing session with multiple users (time breakdown)."""
    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="multi-user",
        goal="Multiple users",
        working_directory="multi-dir",
        project_path="/multi",
        ai_agent_session_id="uuid-multi",
        issue_key="PROJ-77777",
    )

    # Simulate work sessions by different users
    from devflow.config.models import WorkSession

    session.work_sessions = [
        WorkSession(
            user="user1",
            start=datetime.now() - timedelta(hours=2),
            end=datetime.now() - timedelta(hours=1),
        ),
        WorkSession(
            user="user2",
            start=datetime.now() - timedelta(minutes=30),
            end=datetime.now(),
        ),
    ]
    session_manager.update_session(session)

    # Mock functions - capture comment
    captured_comment = []

    def mock_add_comment(issue_key, comment, **kwargs):
        captured_comment.append(comment)
        return True

    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: True)
    monkeypatch.setattr("devflow.cli.commands.complete_command.add_jira_comment", mock_add_comment)

    # Complete session
    complete_session("multi-user")

    # Verify multi-user time breakdown in comment
    assert len(captured_comment) > 0
    assert "user1" in captured_comment[0]
    assert "user2" in captured_comment[0]


def test_complete_session_without_issue_key(temp_daf_home, monkeypatch, capsys):
    """Test completing session without issue key."""
    # Create session without JIRA
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-jira",
        goal="No issue key",
        working_directory="no-jira-dir",
        project_path="/no-jira",
        ai_agent_session_id="uuid-no-jira",
    )

    # Add work session
    session_manager.start_work_session("no-jira")
    session_manager.end_work_session("no-jira")

    # Complete session
    complete_session("no-jira")

    captured = capsys.readouterr()
    assert "skipping JIRA summary" in captured.out


def test_complete_session_attach_to_issue(temp_daf_home, monkeypatch, capsys):
    """Test completing session with export and attach to JIRA."""
    # Create session with JIRA
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="attach-test",
        goal="Test attach",
        working_directory="attach-dir",
        project_path="/attach",
        ai_agent_session_id="uuid-attach",
        issue_key="PROJ-66666",
    )

    # Add work session
    session_manager.start_work_session("attach-test")
    session_manager.end_work_session("attach-test")

    # Mock functions
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Mock JiraClient.attach_file() to succeed (returns None)
    def mock_attach_file(self, issue_key, file_path):
        pass  # Returns None on success

    monkeypatch.setattr("devflow.jira.client.JiraClient.attach_file", mock_attach_file)
    monkeypatch.setattr("devflow.cli.commands.complete_command.add_jira_comment", lambda *args, **kwargs: True)

    # Complete with attach flag
    complete_session("attach-test", attach_to_issue=True)

    captured = capsys.readouterr()
    assert "Exporting session group" in captured.out
    assert "Attached to JIRA" in captured.out


def test_complete_session_attach_without_issue_key(temp_daf_home, monkeypatch, capsys):
    """Test attach to JIRA fails when session has no issue key."""
    # Create session without JIRA
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="attach-no-jira",
        goal="Attach without JIRA",
        working_directory="attach-no-dir",
        project_path="/attach-no",
        ai_agent_session_id="uuid-attach-no",
    )

    # Add work session
    session_manager.start_work_session("attach-no-jira")
    session_manager.end_work_session("attach-no-jira")

    # Complete with attach flag
    complete_session("attach-no-jira", attach_to_issue=True)

    captured = capsys.readouterr()
    assert "Cannot attach to JIRA - session has no issue key" in captured.out


def test_complete_session_jira_attach_failure(temp_daf_home, monkeypatch, capsys):
    """Test handling JIRA attach failure."""
    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="attach-fail",
        goal="Attach failure",
        working_directory="fail-dir",
        project_path="/fail",
        ai_agent_session_id="uuid-fail",
        issue_key="PROJ-55555",
    )

    # Add work session
    session_manager.start_work_session("attach-fail")
    session_manager.end_work_session("attach-fail")

    # Mock functions
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Mock JiraClient.attach_file() to fail (raises exception)
    def mock_attach_file(self, issue_key, file_path):
        raise JiraApiError("Failed to attach file")

    monkeypatch.setattr("devflow.jira.client.JiraClient.attach_file", mock_attach_file)

    # Complete with attach flag
    complete_session("attach-fail", attach_to_issue=True)

    captured = capsys.readouterr()
    assert "JIRA API error" in captured.out


def test_complete_session_jira_cli_not_found(temp_daf_home, monkeypatch, capsys):
    """Test handling when JIRA CLI is not installed."""
    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-cli",
        goal="No CLI",
        working_directory="no-cli-dir",
        project_path="/no-cli",
        ai_agent_session_id="uuid-no-cli",
        issue_key="PROJ-44444",
    )

    # Add work session
    session_manager.start_work_session("no-cli")
    session_manager.end_work_session("no-cli")

    # Mock functions
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Mock JiraClient.attach_file() to raise JiraApiError (JIRA not configured)
    def mock_attach_file(self, issue_key, file_path):
        raise JiraApiError("JIRA API token not configured")

    monkeypatch.setattr("devflow.jira.client.JiraClient.attach_file", mock_attach_file)

    # Complete with attach flag
    complete_session("no-cli", attach_to_issue=True)

    captured = capsys.readouterr()
    assert "JIRA API error" in captured.out


def test_complete_session_jira_timeout(temp_daf_home, monkeypatch, capsys):
    """Test handling JIRA API timeout."""
    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="timeout-test",
        goal="Timeout",
        working_directory="timeout-dir",
        project_path="/timeout",
        ai_agent_session_id="uuid-timeout",
        issue_key="PROJ-33333",
    )

    # Add work session
    session_manager.start_work_session("timeout-test")
    session_manager.end_work_session("timeout-test")

    # Mock functions
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Mock JiraClient.attach_file() to raise a timeout-like error
    def mock_attach_file(self, issue_key, file_path):
        raise JiraApiError("Request timeout")

    monkeypatch.setattr("devflow.jira.client.JiraClient.attach_file", mock_attach_file)

    # Complete with attach flag
    complete_session("timeout-test", attach_to_issue=True)

    captured = capsys.readouterr()
    assert "JIRA API error" in captured.out


def test_complete_nonexistent_session(temp_daf_home, monkeypatch, capsys):
    """Test completing nonexistent session."""
    # Mock get_session_with_prompt to return None (session not found)
    monkeypatch.setattr("devflow.cli.commands.complete_command.get_session_with_prompt", lambda *args: None)

    # Complete nonexistent session
    complete_session("nonexistent")

    # Should return early without error
    captured = capsys.readouterr()
    # No error output expected, just returns


def test_complete_session_summary_error_handling(temp_daf_home, monkeypatch, capsys):
    """Test error handling when summary generation fails."""
    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="summary-error",
        goal="Summary error",
        working_directory="error-dir",
        project_path="/error",
        ai_agent_session_id="uuid-error",
        issue_key="PROJ-22222",
    )

    # Add work session with time (at least 5 minutes)
    session_manager.start_work_session("summary-error")
    # Manually add a work session with time to ensure it meets the 5-minute threshold
    session.work_sessions.append({
        "start": datetime.now() - timedelta(minutes=30),
        "end": datetime.now() - timedelta(minutes=20),
        "user": "testuser"
    })
    session_manager.update_session(session)

    # Mock functions
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: True)

    # Mock add_jira_comment to raise exception
    def mock_add_comment(*args, **kwargs):
        raise Exception("JIRA API error")

    monkeypatch.setattr("devflow.cli.commands.complete_command.add_jira_comment", mock_add_comment)

    # Complete session - should handle error gracefully
    complete_session("summary-error")

    captured = capsys.readouterr()
    assert "Failed to generate session summary" in captured.out


def test_complete_session_skips_pr_creation_with_no_commits(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that PR creation is skipped when there are no commits and no file changes."""
    import subprocess

    # Create a git repository
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch with no new commits
    subprocess.run(["git", "checkout", "-b", "feature-branch"], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-commits-test",
        goal="Test no commits",
        working_directory="test-repo",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-no-commits",
        branch="feature-branch",
    )

    # Add work session
    session_manager.start_work_session("no-commits-test")
    session_manager.end_work_session("no-commits-test")

    # Mock Confirm.ask to avoid interactive prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Complete the session
    complete_session("no-commits-test")

    captured = capsys.readouterr()
    # Should skip PR creation because there are no file changes
    assert "No new commits - skipping PR creation" in captured.out
    # Should NOT prompt for PR creation
    assert "Create a PR/MR now?" not in captured.out


def test_complete_session_prompts_pr_with_uncommitted_changes(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that PR creation IS prompted when there are uncommitted changes (even with no commits)."""
    import subprocess

    # Create a git repository
    repo_dir = tmp_path / "test-repo-uncommitted"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch with no new commits
    subprocess.run(["git", "checkout", "-b", "feature-uncommitted"], cwd=repo_dir, capture_output=True)

    # Add uncommitted changes (modify file but don't commit)
    (repo_dir / "test.txt").write_text("modified")

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="uncommitted-test",
        goal="Test uncommitted",
        working_directory="test-repo-uncommitted",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-uncommitted",
        branch="feature-uncommitted",
    )

    # Add work session
    session_manager.start_work_session("uncommitted-test")
    session_manager.end_work_session("uncommitted-test")

    # Mock Confirm.ask to return False for all prompts (commit prompt, PR prompt, etc.)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Complete the session
    complete_session("uncommitted-test")

    captured = capsys.readouterr()
    # Should show uncommitted changes warning (from commit prompt section)
    assert "uncommitted changes" in captured.out
    # Should NOT skip PR creation (because there ARE uncommitted changes)
    assert "No new commits - skipping PR creation" not in captured.out


def test_complete_session_prompts_pr_with_committed_changes(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that PR creation IS prompted when there are committed changes during this cycle."""
    import subprocess

    # Create a git repository
    repo_dir = tmp_path / "test-repo-committed"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-committed"], cwd=repo_dir, capture_output=True)

    # Add uncommitted changes (will be committed during complete_session)
    (repo_dir / "new-file.txt").write_text("new content")

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="committed-test",
        goal="Test committed",
        working_directory="test-repo-committed",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-committed",
        branch="feature-committed",
    )

    # Add work session
    session_manager.start_work_session("committed-test")
    session_manager.end_work_session("committed-test")

    # Mock Confirm.ask to accept commit but decline PR
    def mock_confirm(prompt, **kwargs):
        if "Commit these changes" in prompt:
            return True
        if "Use this commit message" in prompt:
            return True
        if "Push" in prompt:
            return False
        if "PR" in prompt or "MR" in prompt:
            return False
        return False

    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm)
    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message", lambda s: "Test commit")
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: None)

    # Complete the session
    complete_session("committed-test")

    captured = capsys.readouterr()
    # Should prompt for PR creation (because commit was made THIS cycle)
    assert "No PR/MR found for this branch" in captured.out
    # Should NOT skip PR creation
    assert "No new commits - skipping PR creation" not in captured.out


def test_complete_session_skips_pr_with_commits_but_no_file_changes(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that PR creation is skipped when there are commits but no net file changes."""
    import subprocess

    # Create a git repository
    repo_dir = tmp_path / "test-repo-no-net-changes"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-no-net"], cwd=repo_dir, capture_output=True)

    # Make a change and commit it
    (repo_dir / "test.txt").write_text("modified")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Modify file"], cwd=repo_dir, capture_output=True)

    # Revert the change (results in no net file changes vs main)
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Revert to original"], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-net-changes-test",
        goal="Test no net changes",
        working_directory="test-repo-no-net-changes",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-no-net",
        branch="feature-no-net",
    )

    # Add work session
    session_manager.start_work_session("no-net-changes-test")
    session_manager.end_work_session("no-net-changes-test")

    # Mock Confirm.ask to avoid interactive prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Complete the session
    complete_session("no-net-changes-test")

    captured = capsys.readouterr()
    # Should skip PR creation because there are no net file changes
    assert "No new commits - skipping PR creation" in captured.out
    # Should NOT prompt for PR creation
    assert "Create a PR/MR now?" not in captured.out


def test_complete_session_skips_pr_after_merge_to_base(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that PR creation is skipped when branch was already merged to base (PROJ-60805).

    This is the primary scenario from the issue tracker ticket:
    - User creates feature branch
    - User makes commits and creates PR
    - PR gets merged to main
    - User runs daf complete while still on feature branch
    - Should NOT prompt to create PR (already merged)
    """
    import subprocess

    # Create a git repository
    repo_dir = tmp_path / "test-repo-merged"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch with new commits
    subprocess.run(["git", "checkout", "-b", "feature-merged"], cwd=repo_dir, capture_output=True)
    (repo_dir / "new-file.txt").write_text("feature content")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add feature"], cwd=repo_dir, capture_output=True)

    # Simulate PR merge: merge feature branch into main
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "merge", "feature-merged", "--no-ff", "-m", "Merge PR"], cwd=repo_dir, capture_output=True)

    # Go back to feature branch (as if user is still on it after merge)
    subprocess.run(["git", "checkout", "feature-merged"], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="merged-test",
        goal="Test after merge",
        working_directory="test-repo-merged",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-merged",
        branch="feature-merged",
    )

    # Add work session
    session_manager.start_work_session("merged-test")
    session_manager.end_work_session("merged-test")

    # Mock Confirm.ask to avoid interactive prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)

    # Complete the session
    complete_session("merged-test")

    captured = capsys.readouterr()
    # Should skip PR creation because branch was already merged
    # After merge, there are no new commits on feature branch vs main
    # The key requirement is that it should NOT prompt to create a PR
    assert "Create a PR/MR now?" not in captured.out
    # And it should indicate no changes or no PR found
    assert ("No new commits - skipping PR creation" in captured.out or
            "No PR/MR found for this branch" in captured.out)


def test_complete_session_skips_pr_when_on_different_branch(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that daf complete auto-checkouts session branch when on different branch (no uncommitted changes)."""
    import subprocess

    # Create a git repository
    repo_dir = tmp_path / "test-repo-different-branch"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Ensure the default branch is named 'main' (not 'master')
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo_dir, capture_output=True)

    # Create another branch with changes
    subprocess.run(["git", "checkout", "-b", "other-feature"], cwd=repo_dir, capture_output=True)
    (repo_dir / "other.txt").write_text("other changes")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add other feature"], cwd=repo_dir, capture_output=True)

    # Create session that was created on main branch
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="branch-mismatch-test",
        goal="Test branch mismatch",
        working_directory="test-repo-different-branch",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-branch-mismatch",
        branch="main",  # Session was created on main
    )

    # Add work session
    session_manager.start_work_session("branch-mismatch-test")
    session_manager.end_work_session("branch-mismatch-test")

    # Mock Confirm.ask to avoid interactive prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)

    # Complete the session (while on other-feature branch, no uncommitted changes)
    complete_session("branch-mismatch-test")

    captured = capsys.readouterr()
    # New behavior: should auto-checkout the session branch
    assert "Branch mismatch detected" in captured.out
    assert "Session branch: main" in captured.out
    assert "Current branch: other-feature" in captured.out
    assert "Switching to session branch 'main'" in captured.out
    assert "Checked out branch 'main'" in captured.out
    # Should complete the session
    assert "marked as complete" in captured.out


def test_fill_pr_template(monkeypatch, sample_pr_template, sample_filled_pr_template):
    """Test that PR template is filled using mocked AI (fixture-based)."""
    from devflow.cli.commands.complete_command import _fill_pr_template
    from devflow.config.models import Session
    from datetime import datetime
    from pathlib import Path

    # Create a mock session
    session = Session(
        name="test-pr",
        goal="Test PR template",
        issue_key="PROJ-12345",
        created=datetime.now(),
        last_active=datetime.now()
    )

    # Mock git context
    git_context = {
        'commit_log': '- Add new feature X\n- Fix bug in component Y',
        'changed_files': ['file1.py', 'file2.py'],
        'base_branch': 'main',
        'current_branch': 'feature-branch'
    }

    working_dir = Path("/tmp/test-pr")

    # Mock the AI template filling to return fixture data (no actual API call)
    def mock_fill_pr_template_with_ai(template, session, working_dir, git_context):
        return sample_filled_pr_template

    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.fill_pr_template_with_ai",
        mock_fill_pr_template_with_ai
    )

    # Fill the template (using mocked AI)
    filled = _fill_pr_template(sample_pr_template, session, working_dir, git_context)

    # Verify issue key is present
    assert "PROJ-12345" in filled
    # Verify description is filled
    assert "This PR adds new feature X" in filled
    # Verify structure preserved
    assert "## Description" in filled
    assert "## Testing" in filled


def test_fill_pr_template_without_jira(monkeypatch, sample_pr_template):
    """Test PR template filling when session has no issue key (fixture-based)."""
    from devflow.cli.commands.complete_command import _fill_pr_template
    from devflow.config.models import Session
    from datetime import datetime
    from pathlib import Path

    session = Session(
        name="test-no-jira",
        goal="Test without JIRA",
        created=datetime.now(),
        last_active=datetime.now()
    )

    git_context = {
        'commit_log': 'Simple bug fix',
        'changed_files': ['bugfix.py'],
        'base_branch': 'main',
        'current_branch': 'bugfix-branch'
    }

    working_dir = Path("/tmp/test-no-jira")

    # Mock AI to return a filled template without JIRA
    def mock_fill_pr_template_with_ai(template, session, working_dir, git_context):
        return """## Description
Simple bug fix in bugfix.py

## Testing
### Steps to test
1. Pull down the PR
2. Verify the bug is fixed

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""

    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.fill_pr_template_with_ai",
        mock_fill_pr_template_with_ai
    )

    filled = _fill_pr_template(sample_pr_template, session, working_dir, git_context)

    # Should produce filled content
    assert len(filled) > 0
    # Should mention the changes
    assert "bug" in filled.lower()
    # Should NOT have JIRA link
    assert "PROJ-" not in filled


def test_generate_pr_title_strips_backticks(temp_daf_home, tmp_path, monkeypatch):
    """Test that _generate_pr_title strips backticks from commit messages."""
    import subprocess
    from devflow.cli.commands.complete_command import _generate_pr_title
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-repo-backticks"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-backticks"], cwd=repo_dir, capture_output=True)

    # Create a commit with backticks in the message (simulating AI-generated commit)
    (repo_dir / "new-file.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)

    # Commit message with backticks (like from AI)
    commit_msg = "``` Improve PR/MR creation checks to use file changes instead of commits"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="backtick-test",
        goal="Test backtick stripping",
        working_directory="test-repo-backticks",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-backticks",
        branch="feature-backticks",
        issue_key="PROJ-60103",
    )

    # Generate PR title
    title = _generate_pr_title(session, repo_dir)

    # Title should NOT contain backticks
    assert "```" not in title
    # Title should have issue key
    assert "PROJ-60103" in title
    # Title should have the clean commit message
    assert "Improve PR/MR creation checks" in title


def test_generate_pr_title_strips_trailing_backticks(temp_daf_home, tmp_path, monkeypatch):
    """Test that _generate_pr_title strips trailing backticks too."""
    import subprocess
    from devflow.cli.commands.complete_command import _generate_pr_title
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-repo-trailing"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-trailing"], cwd=repo_dir, capture_output=True)

    # Create a commit with backticks at both ends
    (repo_dir / "new-file.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)

    commit_msg = "```Fix validation logic```"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="trailing-test",
        goal="Test trailing backticks",
        working_directory="test-repo-trailing",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-trailing",
        branch="feature-trailing",
        issue_key="PROJ-60103",
    )

    # Generate PR title
    title = _generate_pr_title(session, repo_dir)

    # Title should NOT contain backticks
    assert "```" not in title
    assert "`" not in title
    # Title should have clean message
    assert "Fix validation logic" in title


def test_generate_pr_title_strips_backticks_with_jira_prefix(temp_daf_home, tmp_path, monkeypatch):
    """Test backtick stripping when commit already has JIRA prefix."""
    import subprocess
    from devflow.cli.commands.complete_command import _generate_pr_title
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-repo-jira-prefix"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-jira"], cwd=repo_dir, capture_output=True)

    # Commit with JIRA prefix AND backticks
    (repo_dir / "new-file.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)

    commit_msg = "PROJ-60103: ``` Add new validation feature"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="jira-prefix-test",
        goal="Test JIRA prefix with backticks",
        working_directory="test-repo-jira-prefix",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-jira-prefix",
        branch="feature-jira",
        issue_key="PROJ-60103",
    )

    # Generate PR title
    title = _generate_pr_title(session, repo_dir)

    # Title should NOT contain backticks
    assert "```" not in title
    assert "`" not in title
    # Title should have issue key only once (not duplicated)
    assert title.count("PROJ-60103") == 1
    # Title should have clean message
    assert "Add new validation feature" in title
    # Expected format: "PROJ-60103: Add new validation feature"
    assert title == "PROJ-60103: Add new validation feature"


def test_generate_pr_title_without_backticks_still_works(temp_daf_home, tmp_path, monkeypatch):
    """Test that normal commits without backticks still work correctly."""
    import subprocess
    from devflow.cli.commands.complete_command import _generate_pr_title
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-repo-normal"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-normal"], cwd=repo_dir, capture_output=True)

    # Normal commit without backticks
    (repo_dir / "new-file.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)

    commit_msg = "Add comprehensive test coverage for validation"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="normal-test",
        goal="Test normal commit",
        working_directory="test-repo-normal",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-normal",
        branch="feature-normal",
        issue_key="PROJ-12345",
    )

    # Generate PR title
    title = _generate_pr_title(session, repo_dir)

    # Title should have issue key
    assert "PROJ-12345" in title
    # Title should have the commit message
    assert "Add comprehensive test coverage for validation" in title
    # Expected format
    assert title == "PROJ-12345: Add comprehensive test coverage for validation"


def test_complete_session_with_latest_flag(temp_daf_home, monkeypatch, capsys):
    """Test completing the most recently active session using --latest flag."""
    # Create multiple sessions
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session (older)
    session1 = session_manager.create_session(
        name="old-session",
        goal="Old session",
        working_directory="old-dir",
        project_path="/old",
        ai_agent_session_id="uuid-old",
        issue_key="PROJ-11111",
    )
    session1.last_active = datetime.now() - timedelta(hours=5)
    session_manager.update_session(session1)

    # Create second session (more recent)
    session2 = session_manager.create_session(
        name="recent-session",
        goal="Recent session",
        working_directory="recent-dir",
        project_path="/recent",
        ai_agent_session_id="uuid-recent",
        issue_key="PROJ-22222",
    )
    session2.last_active = datetime.now() - timedelta(hours=1)
    session_manager.update_session(session2)

    # Start and end work session on the recent one
    session_manager.start_work_session("recent-session")
    session_manager.end_work_session("recent-session")

    # Mock Confirm.ask to confirm completion
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: True)
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)

    # Complete using --latest flag
    complete_session(latest=True)

    # Verify the most recently active session was completed
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("recent-session")
    assert sessions[0].status == "complete"

    # Verify the old session was NOT completed
    old_sessions = session_manager.index.get_sessions("old-session")
    assert old_sessions[0].status != "complete"

    captured = capsys.readouterr()
    assert "Completing most recently active session" in captured.out
    assert "recent-session" in captured.out
    assert "PROJ-22222" in captured.out


def test_complete_session_latest_with_no_sessions(temp_daf_home, monkeypatch, capsys):
    """Test --latest flag when no sessions exist."""
    # Complete using --latest flag (no sessions exist)
    complete_session(latest=True)

    captured = capsys.readouterr()
    assert "No sessions found" in captured.out


def test_complete_session_latest_user_cancels(temp_daf_home, monkeypatch, capsys):
    """Test --latest flag when user cancels confirmation."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="cancel-test",
        goal="Test cancellation",
        working_directory="cancel-dir",
        project_path="/cancel",
        ai_agent_session_id="uuid-cancel",
    )

    # Mock Confirm.ask to return False (user cancels)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Complete using --latest flag
    complete_session(latest=True)

    # Verify session was NOT completed
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("cancel-test")
    assert sessions[0].status != "complete"

    captured = capsys.readouterr()
    assert "Cancelled" in captured.out


def test_complete_session_without_identifier_and_without_latest_flag(temp_daf_home, capsys):
    """Test that calling complete without identifier and without --latest shows error."""
    # Call complete with no identifier and no latest flag
    complete_session(identifier=None, latest=False)

    captured = capsys.readouterr()
    assert "Error: IDENTIFIER is required" in captured.out
    assert "daf complete <identifier> or daf complete --latest" in captured.out


def test_complete_session_latest_shows_session_details(temp_daf_home, monkeypatch, capsys):
    """Test that --latest shows proper session details in confirmation."""
    # Create a session with goal
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="detail-test",
        goal="PROJ-99999: Implement advanced features for testing",
        working_directory="detail-dir",
        project_path="/detail",
        ai_agent_session_id="uuid-detail",
        issue_key="PROJ-99999",
    )

    # Mock Confirm.ask to cancel (so we can just check the output)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Complete using --latest flag
    complete_session(latest=True)

    captured = capsys.readouterr()
    # Should show session details
    assert "detail-test" in captured.out
    assert "PROJ-99999" in captured.out
    assert "detail-dir" in captured.out  # Working directory
    assert "Status:" in captured.out
    # Status should be displayed as-is (default is "created")
    assert "created" in captured.out or "in_progress" in captured.out or "complete" in captured.out
    assert "Implement advanced features for testing" in captured.out
    assert "Last active:" in captured.out


def test_transition_on_complete_fetches_transitions_dynamically(temp_daf_home, monkeypatch, capsys):
    """Test that transition_on_complete fetches available transitions from JIRA API."""
    from devflow.jira.transitions import transition_on_complete
    from devflow.config.models import Session, Config, JiraConfig, JiraTransitionConfig, RepoConfig
    from unittest.mock import Mock

    # Create a session with issue key
    session = Session(
        name="transition-test",
        goal="Test transitions",
        issue_key="PROJ-12345",
        issue_metadata={"status": "In Progress"},
        created=datetime.now(),
        last_active=datetime.now()
    )

    # Create config with on_complete transition
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="testuser",
            project="PROJ",
            transitions={
                "on_complete": JiraTransitionConfig(
                    from_status=["In Progress"],
                    to="Review",
                    prompt=True,
                    on_fail="warn",
                )
            }
        ),
        repos=RepoConfig(workspace="/tmp/test")
    )

    # Mock JiraClient
    mock_jira_client = Mock()

    # Mock the API response with dynamic transitions
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "transitions": [
            {"id": "1", "to": {"name": "New"}},
            {"id": "2", "to": {"name": "Refinement"}},
            {"id": "3", "to": {"name": "Backlog"}},
            {"id": "4", "to": {"name": "In Progress"}},
            {"id": "5", "to": {"name": "Review"}},
            {"id": "6", "to": {"name": "Release Pending"}},
            {"id": "7", "to": {"name": "Closed"}},
        ]
    }
    mock_jira_client._api_request.return_value = mock_response

    # Mock transition_ticket to succeed (returns None)
    mock_jira_client.transition_ticket.return_value = None

    # Mock Prompt.ask to select "Review" (option 6, index 5 in 1-based list with skip)
    monkeypatch.setattr("devflow.jira.transitions.Prompt.ask", lambda *args, **kwargs: "6")

    # Call transition_on_complete
    result = transition_on_complete(session, config, jira_client=mock_jira_client)

    # Verify API was called to fetch transitions
    mock_jira_client._api_request.assert_called_once_with(
        "GET",
        "/rest/api/2/issue/PROJ-12345/transitions"
    )

    # Verify success
    assert result is True

    # Check output contains the dynamic transitions
    captured = capsys.readouterr()
    assert "Transition issue tracker ticket PROJ-12345?" in captured.out
    assert "Current status: In Progress" in captured.out
    # Should show dynamically fetched transitions
    assert "Review" in captured.out
    assert "Closed" in captured.out
    assert "Release Pending" in captured.out


def test_transition_on_complete_handles_api_failure(temp_daf_home, monkeypatch, capsys):
    """Test that transition_on_complete handles JIRA API failures gracefully."""
    from devflow.jira.transitions import transition_on_complete
    from devflow.config.models import Session, Config, JiraConfig, JiraTransitionConfig, RepoConfig
    from unittest.mock import Mock

    # Create a session with issue key
    session = Session(
        name="api-fail-test",
        goal="Test API failure",
        issue_key="PROJ-99999",
        issue_status="In Progress",
        created=datetime.now(),
        last_active=datetime.now()
    )

    # Create config
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="testuser",
            project="PROJ",
            transitions={
                "on_complete": JiraTransitionConfig(
                    from_status=["In Progress"],
                    to="Review",
                    prompt=True,
                    on_fail="warn",
                )
            }
        ),
        repos=RepoConfig(workspace="/tmp/test")
    )

    # Mock JiraClient with API failure
    mock_jira_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 500  # Server error
    mock_jira_client._api_request.return_value = mock_response

    # Call transition_on_complete
    result = transition_on_complete(session, config, jira_client=mock_jira_client)

    # Should return True (don't block completion on API failure)
    assert result is True

    # Check output shows warning
    captured = capsys.readouterr()
    assert "Could not fetch transitions from JIRA" in captured.out
    assert "JIRA transition skipped" in captured.out


def test_transition_on_complete_handles_empty_transitions(temp_daf_home, monkeypatch, capsys):
    """Test that transition_on_complete handles empty transitions list gracefully."""
    from devflow.jira.transitions import transition_on_complete
    from devflow.config.models import Session, Config, JiraConfig, JiraTransitionConfig, RepoConfig
    from unittest.mock import Mock

    # Create a session with issue key
    session = Session(
        name="empty-transitions-test",
        goal="Test empty transitions",
        issue_key="PROJ-88888",
        issue_status="Closed",
        created=datetime.now(),
        last_active=datetime.now()
    )

    # Create config
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="testuser",
            project="PROJ",
            transitions={
                "on_complete": JiraTransitionConfig(
                    from_status=["In Progress"],
                    to="Review",
                    prompt=True,
                    on_fail="warn",
                )
            }
        ),
        repos=RepoConfig(workspace="/tmp/test")
    )

    # Mock JiraClient with empty transitions
    mock_jira_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"transitions": []}
    mock_jira_client._api_request.return_value = mock_response

    # Call transition_on_complete
    result = transition_on_complete(session, config, jira_client=mock_jira_client)

    # Should return True (don't block completion)
    assert result is True

    # Check output shows warning
    captured = capsys.readouterr()
    assert "No transitions available for this ticket" in captured.out
    assert "JIRA transition skipped" in captured.out


def test_transition_on_complete_automatic_transition(temp_daf_home, monkeypatch, capsys):
    """Test that automatic transition works when prompt=False."""
    from devflow.jira.transitions import transition_on_complete
    from devflow.config.models import Session, Config, JiraConfig, JiraTransitionConfig, RepoConfig
    from unittest.mock import Mock

    # Create a session with issue key
    session = Session(
        name="auto-transition-test",
        goal="Test automatic transition",
        issue_key="PROJ-77777",
        issue_status="In Progress",
        created=datetime.now(),
        last_active=datetime.now()
    )

    # Create config with automatic transition (prompt=False)
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="testuser",
            project="PROJ",
            transitions={
                "on_complete": JiraTransitionConfig(
                    from_status=["In Progress"],
                    to="Done",
                    prompt=False,  # Automatic transition
                    on_fail="warn",
                )
            }
        ),
        repos=RepoConfig(workspace="/tmp/test")
    )

    # Mock JiraClient
    mock_jira_client = Mock()
    mock_jira_client.transition_ticket.return_value = None  # Returns None on success

    # Call transition_on_complete
    result = transition_on_complete(session, config, jira_client=mock_jira_client)

    # Verify transition was called with the configured target status
    mock_jira_client.transition_ticket.assert_called_once_with("PROJ-77777", "Done")

    # Verify success
    assert result is True

    # Check output
    captured = capsys.readouterr()
    assert "PROJ-77777 → Done" in captured.out

    # Verify session status was updated
    assert session.issue_metadata.get("status") == "Done"


def test_transition_on_complete_automatic_transition_no_target(temp_daf_home, monkeypatch, capsys):
    """Test that automatic transition is skipped when no target status is configured."""
    from devflow.jira.transitions import transition_on_complete
    from devflow.config.models import Session, Config, JiraConfig, JiraTransitionConfig, RepoConfig
    from unittest.mock import Mock

    # Create a session with issue key
    session = Session(
        name="no-target-test",
        goal="Test no target",
        issue_key="PROJ-66666",
        issue_status="In Progress",
        created=datetime.now(),
        last_active=datetime.now()
    )

    # Create config with prompt=False but empty target
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="testuser",
            project="PROJ",
            transitions={
                "on_complete": JiraTransitionConfig(
                    from_status=["In Progress"],
                    to="",  # No target status
                    prompt=False,
                    on_fail="warn",
                )
            }
        ),
        repos=RepoConfig(workspace="/tmp/test")
    )

    # Mock JiraClient
    mock_jira_client = Mock()

    # Call transition_on_complete
    result = transition_on_complete(session, config, jira_client=mock_jira_client)

    # Should return True (skip transition gracefully)
    assert result is True

    # Verify no transition was attempted
    mock_jira_client.transition_ticket.assert_not_called()


def test_get_pr_for_branch_glab_correct_syntax(temp_daf_home, tmp_path, monkeypatch):
    """Test that _get_pr_for_branch uses correct glab syntax (-F json, no --hostname)."""
    import subprocess
    import json
    from devflow.cli.commands.complete_command import _get_pr_for_branch

    # Create a git repository with GitLab remote
    repo_dir = tmp_path / "test-gitlab-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "git@gitlab.example.com:group/project.git"], cwd=repo_dir, capture_output=True)

    # Mock subprocess.run to capture glab command
    original_run = subprocess.run
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)

        # Simulate glab mr list response
        if cmd[0] == "glab" and "mr" in cmd:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps([{
                "state": "opened",
                "web_url": "https://gitlab.example.com/group/project/-/merge_requests/123"
            }])
            mock_result.stderr = ""
            return mock_result

        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", mock_run)

    # Call _get_pr_for_branch
    result = _get_pr_for_branch(repo_dir, "feature-branch")

    # Verify correct glab command was used
    glab_cmd = [c for c in captured_commands if c[0] == "glab"][0]

    # Should use -F json (not --json)
    assert "-F" in glab_cmd
    assert "json" in glab_cmd
    assert "--json" not in glab_cmd

    # Should NOT use --hostname flag
    assert "--hostname" not in glab_cmd

    # Verify result
    assert result is not None
    assert result['state'] == 'open'
    assert result['url'] == "https://gitlab.example.com/group/project/-/merge_requests/123"


def test_get_pr_for_branch_glab_error_handling(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that _get_pr_for_branch handles glab command failures with clear error messages."""
    import subprocess
    from devflow.cli.commands.complete_command import _get_pr_for_branch

    # Create a git repository with GitLab remote
    repo_dir = tmp_path / "test-gitlab-error"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "git@gitlab.example.com:group/project.git"], cwd=repo_dir, capture_output=True)

    # Save original subprocess.run
    original_run = subprocess.run

    # Mock subprocess.run to simulate glab failure
    def mock_run(cmd, *args, **kwargs):
        if len(cmd) > 0 and cmd[0] == "glab":
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "glab: authentication required"
            return mock_result

        # For other commands, use original
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", mock_run)

    # Call _get_pr_for_branch
    result = _get_pr_for_branch(repo_dir, "feature-branch")

    # Should return None but print error message
    assert result is None

    # Verify error message was printed
    captured = capsys.readouterr()
    assert "Failed to detect MR" in captured.out
    assert "glab: authentication required" in captured.out


def test_get_pr_for_branch_glab_not_found(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that _get_pr_for_branch handles missing glab CLI with clear message."""
    import subprocess
    from devflow.cli.commands.complete_command import _get_pr_for_branch

    # Create a git repository with GitLab remote
    repo_dir = tmp_path / "test-glab-missing"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "git@gitlab.example.com:group/project.git"], cwd=repo_dir, capture_output=True)

    # Save original subprocess.run
    original_run = subprocess.run

    # Mock subprocess.run to simulate glab not found
    def mock_run(cmd, *args, **kwargs):
        if len(cmd) > 0 and cmd[0] == "glab":
            raise FileNotFoundError("[Errno 2] No such file or directory: 'glab'")

        # For other commands, use original
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", mock_run)

    # Call _get_pr_for_branch
    result = _get_pr_for_branch(repo_dir, "feature-branch")

    # Should return None but print helpful message
    assert result is None

    # Verify helpful error message was printed
    captured = capsys.readouterr()
    assert "GitLab CLI ('glab') not found" in captured.out
    assert "https://gitlab.com/gitlab-org/cli" in captured.out


def test_get_pr_for_branch_glab_json_decode_error(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that _get_pr_for_branch handles invalid JSON response gracefully."""
    import subprocess
    from devflow.cli.commands.complete_command import _get_pr_for_branch

    # Create a git repository with GitLab remote
    repo_dir = tmp_path / "test-glab-json-error"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "git@gitlab.example.com:group/project.git"], cwd=repo_dir, capture_output=True)

    # Save original subprocess.run
    original_run = subprocess.run

    # Mock subprocess.run to return invalid JSON
    def mock_run(cmd, *args, **kwargs):
        if len(cmd) > 0 and cmd[0] == "glab":
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "not valid json {"
            mock_result.stderr = ""
            return mock_result

        # For other commands, use original
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", mock_run)

    # Call _get_pr_for_branch
    result = _get_pr_for_branch(repo_dir, "feature-branch")

    # Should return None but print error
    assert result is None

    # Verify JSON parse error was handled
    captured = capsys.readouterr()
    assert "Failed to parse PR/MR response" in captured.out


def test_complete_session_updates_jira_with_existing_mr_url(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that completing session updates JIRA when existing MR is detected."""
    import subprocess
    import json
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository with GitLab remote
    repo_dir = tmp_path / "test-jira-update-mr"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "git@gitlab.example.com:group/project.git"], cwd=repo_dir, capture_output=True)

    # Create initial commit
    (repo_dir / "test.txt").write_text("content")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create feature branch with a commit
    subprocess.run(["git", "checkout", "-b", "feature-mr"], cwd=repo_dir, capture_output=True)
    (repo_dir / "feature.txt").write_text("feature")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add feature"], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="mr-jira-update",
        goal="Test MR JIRA update",
        working_directory="test-jira-update-mr",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-mr-jira",
        issue_key="PROJ-60247",
        branch="feature-mr",
    )

    # Add work session
    session_manager.start_work_session("mr-jira-update")
    session_manager.end_work_session("mr-jira-update")

    # Mock glab to return existing MR
    original_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        if cmd[0] == "glab" and "mr" in cmd:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps([{
                "state": "opened",
                "web_url": "https://gitlab.example.com/group/project/-/merge_requests/999"
            }])
            mock_result.stderr = ""
            return mock_result

        return original_run(cmd, *args, **kwargs)

    # Track if _update_jira_pr_field was called
    jira_update_called = []
    original_update = None

    def mock_update_jira(issue_key, pr_url, no_issue_update=False):
        jira_update_called.append((issue_key, pr_url))

    # Import the function to mock it
    import devflow.cli.commands.complete_command as cc
    original_update = cc._update_jira_pr_field

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("devflow.cli.commands.complete_command._update_jira_pr_field", mock_update_jira)
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)

    # Complete the session
    complete_session("mr-jira-update")

    # Verify JIRA update was called with correct MR URL
    assert len(jira_update_called) > 0
    assert jira_update_called[0] == ("PROJ-60247", "https://gitlab.example.com/group/project/-/merge_requests/999")

    captured = capsys.readouterr()
    assert "Existing open PR/MR found" in captured.out
    assert "https://gitlab.example.com/group/project/-/merge_requests/999" in captured.out


def test_complete_session_aborts_on_wrong_branch_with_uncommitted_changes(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that daf complete aborts when on wrong branch with uncommitted changes."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-wrong-branch-uncommitted"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create session branch
    subprocess.run(["git", "checkout", "-b", "session-branch"], cwd=repo_dir, capture_output=True)

    # Switch to different branch
    subprocess.run(["git", "checkout", "-b", "other-branch"], cwd=repo_dir, capture_output=True)

    # Add uncommitted changes
    (repo_dir / "test.txt").write_text("modified")

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="wrong-branch-uncommitted",
        goal="Test wrong branch with uncommitted changes",
        working_directory="test-wrong-branch-uncommitted",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-wrong-uncommitted",
        branch="session-branch",
    )

    # Add work session
    session_manager.start_work_session("wrong-branch-uncommitted")
    session_manager.end_work_session("wrong-branch-uncommitted")

    # Mock Confirm.ask to avoid interactive prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Complete the session - should abort
    complete_session("wrong-branch-uncommitted")

    captured = capsys.readouterr()
    # Should detect branch mismatch
    assert "Branch mismatch detected" in captured.out
    assert "Session branch: session-branch" in captured.out
    assert "Current branch: other-branch" in captured.out
    # Should abort with error
    assert "Cannot complete session on wrong branch with uncommitted changes" in captured.out
    # Should provide resolution steps
    assert "Commit or stash your changes" in captured.out
    assert "git checkout session-branch" in captured.out
    # Should NOT commit to wrong branch
    assert "Changes committed" not in captured.out


def test_complete_session_auto_checkout_on_wrong_branch_without_uncommitted_changes(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that daf complete auto-checkouts session branch when on wrong branch without uncommitted changes."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-auto-checkout"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Ensure the default branch is named 'main' (not 'master')
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo_dir, capture_output=True)

    # Create session branch
    subprocess.run(["git", "checkout", "-b", "session-branch"], cwd=repo_dir, capture_output=True)

    # Switch to main (no uncommitted changes)
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="auto-checkout-test",
        goal="Test auto checkout",
        working_directory="test-auto-checkout",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-auto-checkout",
        branch="session-branch",
    )

    # Add work session
    session_manager.start_work_session("auto-checkout-test")
    session_manager.end_work_session("auto-checkout-test")

    # Mock Confirm.ask to avoid interactive prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)

    # Complete the session - should auto-checkout
    complete_session("auto-checkout-test")

    captured = capsys.readouterr()
    # Should detect branch mismatch
    assert "Branch mismatch detected" in captured.out
    assert "Session branch: session-branch" in captured.out
    assert "Current branch: main" in captured.out
    # Should auto-checkout
    assert "Switching to session branch 'session-branch'" in captured.out
    assert "Checked out branch 'session-branch'" in captured.out
    # Should continue with completion
    assert "marked as complete" in captured.out

    # Verify we're now on session-branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    assert result.stdout.strip() == "session-branch"


def test_complete_session_checkout_failure_aborts(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that daf complete aborts if auto-checkout fails."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-checkout-failure"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create session (but session branch doesn't exist in repo)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="checkout-failure-test",
        goal="Test checkout failure",
        working_directory="test-checkout-failure",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-checkout-failure",
        branch="nonexistent-branch",  # Branch doesn't exist
    )

    # Add work session
    session_manager.start_work_session("checkout-failure-test")
    session_manager.end_work_session("checkout-failure-test")

    # Mock Confirm.ask to avoid interactive prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)

    # Complete the session - should abort
    complete_session("checkout-failure-test")

    captured = capsys.readouterr()
    # Should detect branch mismatch
    assert "Branch mismatch detected" in captured.out
    # Should attempt checkout
    assert "Switching to session branch 'nonexistent-branch'" in captured.out
    # Should fail and abort
    assert "Failed to checkout branch 'nonexistent-branch'" in captured.out
    # Should provide resolution steps
    assert "Manually checkout the session branch" in captured.out
    # Should NOT complete the session
    assert "marked as complete" not in captured.out


def test_complete_session_correct_branch_no_check_needed(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that daf complete works normally when already on correct branch."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-correct-branch"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create and stay on session branch
    subprocess.run(["git", "checkout", "-b", "session-branch"], cwd=repo_dir, capture_output=True)

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="correct-branch-test",
        goal="Test correct branch",
        working_directory="test-correct-branch",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-correct-branch",
        branch="session-branch",
    )

    # Add work session
    session_manager.start_work_session("correct-branch-test")
    session_manager.end_work_session("correct-branch-test")

    # Mock Confirm.ask to avoid interactive prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", lambda s, c: None)

    # Complete the session - should work normally
    complete_session("correct-branch-test")

    captured = capsys.readouterr()
    # Should NOT show branch mismatch
    assert "Branch mismatch detected" not in captured.out
    # Should complete normally
    assert "marked as complete" in captured.out
    # Verify we're still on session-branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    assert result.stdout.strip() == "session-branch"


def test_fetch_github_with_gh_cli_success(monkeypatch):
    """Test fetching via gh CLI (authenticated)."""
    from devflow.cli.commands.complete_command import _fetch_github_with_gh_cli
    import base64
    from unittest.mock import Mock

    # Mock subprocess to return base64 content
    template_content = "# PR Template\nTest content"
    encoded_content = base64.b64encode(template_content.encode('utf-8')).decode('utf-8')

    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = encoded_content

    def mock_subprocess_run(*args, **kwargs):
        return mock_result

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    result = _fetch_github_with_gh_cli("owner", "repo", "template.md")

    assert result == template_content


def test_fetch_github_with_gh_cli_not_found(monkeypatch):
    """Test gh CLI not installed."""
    from devflow.cli.commands.complete_command import _fetch_github_with_gh_cli

    def mock_subprocess_run(*args, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    result = _fetch_github_with_gh_cli("owner", "repo", "template.md")

    assert result is None


def test_fetch_github_with_api_success(monkeypatch):
    """Test fetching via GitHub API (unauthenticated)."""
    from devflow.cli.commands.complete_command import _fetch_github_with_api
    import base64
    from unittest.mock import Mock

    template_content = "# PR Template\nTest content"
    encoded_content = base64.b64encode(template_content.encode('utf-8')).decode('utf-8')

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'content': encoded_content}

    def mock_requests_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr("requests.get", mock_requests_get)

    result = _fetch_github_with_api("owner", "repo", "template.md", "main")

    assert result == template_content


def test_fetch_github_with_api_rate_limit(monkeypatch):
    """Test GitHub API rate limit (403)."""
    from devflow.cli.commands.complete_command import _fetch_github_with_api
    from unittest.mock import Mock

    mock_response = Mock()
    mock_response.status_code = 403

    def mock_requests_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr("requests.get", mock_requests_get)

    result = _fetch_github_with_api("owner", "repo", "template.md", "main")

    assert result is None


def test_fetch_github_raw_success(monkeypatch):
    """Test fetching via raw URL."""
    from devflow.cli.commands.complete_command import _fetch_github_raw
    from unittest.mock import Mock

    template_content = "# PR Template\nTest content"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = template_content

    def mock_requests_get(*args, **kwargs):
        return mock_response

    monkeypatch.setattr("requests.get", mock_requests_get)

    result = _fetch_github_raw("owner", "repo", "template.md", "main")

    assert result == template_content


def test_fetch_github_template_fallback_chain(monkeypatch, sample_pr_template):
    """Test complete fallback: gh CLI → API → raw URL."""
    from devflow.cli.commands.complete_command import _fetch_github_template
    from unittest.mock import Mock

    # Mock gh CLI to fail (FileNotFoundError)
    def mock_subprocess_run(*args, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # Mock GitHub API to fail (403 rate limit)
    mock_api_response = Mock()
    mock_api_response.status_code = 403

    # Mock raw URL to succeed
    mock_raw_response = Mock()
    mock_raw_response.status_code = 200
    mock_raw_response.text = sample_pr_template

    call_count = [0]
    def mock_requests_get(url, *args, **kwargs):
        call_count[0] += 1
        if 'api.github.com' in url:
            return mock_api_response
        else:  # raw.githubusercontent.com
            return mock_raw_response

    monkeypatch.setattr("requests.get", mock_requests_get)

    # Fetch template
    result = _fetch_github_template("https://github.com/owner/repo/blob/main/template.md")

    # Should succeed via raw URL
    assert result == sample_pr_template
    # Should have tried API first (failed), then raw URL (succeeded)
    assert call_count[0] == 2


def test_fetch_github_template_all_methods_fail(monkeypatch, capsys):
    """Test when all three methods fail."""
    from devflow.cli.commands.complete_command import _fetch_github_template
    from unittest.mock import Mock

    # Mock gh CLI to fail
    def mock_subprocess_run(*args, **kwargs):
        raise FileNotFoundError("gh not found")
    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # Mock all requests to fail
    mock_response = Mock()
    mock_response.status_code = 404
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: mock_response)

    result = _fetch_github_template("https://github.com/owner/repo/blob/main/template.md")

    # Should return None
    assert result is None

    # Should show appropriate error message
    captured = capsys.readouterr()
    assert "Could not fetch template from GitHub" in captured.out
    assert "private repository" in captured.out


def test_complete_ticket_creation_session_skips_git_operations(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that ticket_creation sessions skip git operations (commit/PR) entirely."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository with uncommitted changes
    repo_dir = tmp_path / "test-ticket-creation"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-branch"], cwd=repo_dir, capture_output=True)

    # Add uncommitted changes (to verify they're ignored for ticket_creation)
    (repo_dir / "test.txt").write_text("modified")

    # Create session with session_type="ticket_creation"
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="ticket-creation-test",
        goal="PROJ-99999: Create detailed issue tracker ticket for new feature",
        working_directory="test-ticket-creation",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-ticket-creation",
        issue_key="PROJ-99999",
        branch="feature-branch",
    )

    # Set session_type to ticket_creation
    session.session_type = "ticket_creation"
    session_manager.update_session(session)

    # Add work session with meaningful time (at least 5 minutes)
    session_manager.start_work_session("ticket-creation-test")
    from devflow.config.models import WorkSession
    session.work_sessions.append(WorkSession(
        user="testuser",
        start=datetime.now() - timedelta(minutes=15),
        end=datetime.now() - timedelta(minutes=5),
    ))
    session_manager.update_session(session)

    # Mock Confirm.ask to track if commit/PR prompts are shown
    confirm_prompts = []
    def mock_confirm_ask(prompt, **kwargs):
        confirm_prompts.append(prompt)
        return True  # Accept all prompts

    # Track if transition_on_complete is called (it should NOT be for ticket_creation)
    transition_called = []
    def mock_transition_on_complete(s, c):
        transition_called.append(True)

    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm_ask)
    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", mock_transition_on_complete)
    monkeypatch.setattr("devflow.cli.commands.complete_command.add_jira_comment", lambda *args, **kwargs: True)

    # Complete the session
    complete_session("ticket-creation-test")

    captured = capsys.readouterr()

    # Should mark session as complete
    assert "marked as complete" in captured.out

    # Should NOT prompt for commit (commit block skipped for ticket_creation)
    assert "Commit these changes now?" not in "\n".join(confirm_prompts)
    assert "uncommitted changes" not in captured.out

    # Should NOT prompt for PR creation (PR block skipped for ticket_creation)
    assert "Create a PR/MR now?" not in "\n".join(confirm_prompts)
    assert "No PR/MR found for this branch" not in captured.out

    # Should NOT attempt any git operations
    assert "Changes committed" not in captured.out
    assert "Pushing" not in captured.out
    assert "Created PR" not in captured.out
    assert "Created MR" not in captured.out

    # Should still add JIRA summary (this is allowed for ticket_creation)
    assert "Add session summary to JIRA?" in "\n".join(confirm_prompts)

    # Should NOT call transition_on_complete for ticket_creation sessions (PROJ-62680)
    # Transitioning the parent ticket's status doesn't make sense - only analysis was performed
    assert len(transition_called) == 0, "transition_on_complete should not be called for ticket_creation sessions"

    # Verify session was marked as complete
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("ticket-creation-test")
    assert sessions[0].status == "complete"
    assert sessions[0].session_type == "ticket_creation"


def test_complete_development_session_calls_jira_transition(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that development sessions DO call transition_on_complete (regression test for PROJ-62680)."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager
    from devflow.config.models import Config, JiraConfig, RepoConfig, JiraTransitionConfig
    from unittest.mock import Mock

    # Create a git repository
    repo_dir = tmp_path / "test-development"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-branch"], cwd=repo_dir, capture_output=True)

    # Create session with session_type="development" (default)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="development-test",
        goal="PROJ-99998: Implement new feature",
        working_directory="test-development",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-development",
        issue_key="PROJ-99998",
        branch="feature-branch",
    )

    # Explicitly set session_type to development (default, but be explicit)
    session.session_type = "development"
    session_manager.update_session(session)

    # Add work session with meaningful time
    session_manager.start_work_session("development-test")
    from devflow.config.models import WorkSession
    session.work_sessions.append(WorkSession(
        user="testuser",
        start=datetime.now() - timedelta(minutes=15),
        end=datetime.now() - timedelta(minutes=5),
    ))
    session_manager.update_session(session)

    # Create a config with JIRA transitions enabled
    mock_config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="testuser",
            project="PROJ",
            transitions={
                "on_complete": JiraTransitionConfig(
                    from_status=["In Progress"],
                    to="Review",
                    prompt=True,
                    on_fail="warn",
                )
            }
        ),
        repos=RepoConfig(workspace="/tmp/test")
    )

    # Mock ConfigLoader.load_config to return our config
    def mock_load_config(self):
        return mock_config

    monkeypatch.setattr("devflow.config.loader.ConfigLoader.load_config", mock_load_config)

    # Mock Confirm.ask to accept all prompts
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda prompt, **kwargs: False)

    # Track if transition_on_complete is called (it SHOULD be for development sessions)
    transition_called = []
    def mock_transition_on_complete(s, c):
        transition_called.append(True)

    monkeypatch.setattr("devflow.cli.commands.complete_command.transition_on_complete", mock_transition_on_complete)
    monkeypatch.setattr("devflow.cli.commands.complete_command.add_jira_comment", lambda *args, **kwargs: True)

    # Complete the session
    complete_session("development-test")

    # Should call transition_on_complete for development sessions
    assert len(transition_called) == 1, "transition_on_complete should be called for development sessions"

    # Verify session was marked as complete
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("development-test")
    assert sessions[0].status == "complete"
    assert sessions[0].session_type == "development"


def test_generate_commit_message_with_git_diff(temp_daf_home, monkeypatch, tmp_path):
    """Test commit message generation from git diff (PROJ-60656)."""
    from devflow.cli.commands.complete_command import _generate_commit_message
    import subprocess

    # Create session with git repository
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Initialize a git repository
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)

    # Create initial commit
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial content\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)

    # Make uncommitted changes
    test_file.write_text("modified content\n")

    session = session_manager.create_session(
        name="diff-test",
        goal="Test git diff",
        working_directory="diff-dir",
        project_path=str(tmp_path),
        ai_agent_session_id="uuid-diff",
    )

    # Mock the AI commit message generation
    def mock_generate_from_diff(diff_content, status_summary):
        return "Update test.txt with modified content"

    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message_from_diff", mock_generate_from_diff)

    # Generate commit message
    commit_msg = _generate_commit_message(session)

    # Verify commit message was generated from git diff
    assert commit_msg == "Update test.txt with modified content"


def test_generate_commit_message_no_git_repo(temp_daf_home, capsys):
    """Test feedback when not in a git repository (PROJ-60656)."""
    from devflow.cli.commands.complete_command import _generate_commit_message

    # Create session without git repository
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-git-test",
        goal="Test missing git repo",
        working_directory="no-git-dir",
        project_path="/nonexistent",
        ai_agent_session_id="uuid-missing",
    )

    # Generate commit message (should fall back to simple message)
    commit_msg = _generate_commit_message(session)

    # Verify fallback message
    assert commit_msg == "Test missing git repo"

    # Verify user feedback
    captured = capsys.readouterr()
    assert "Not a git repository" in captured.out
    assert "using simple commit message" in captured.out


def test_generate_commit_message_no_uncommitted_changes(temp_daf_home, tmp_path, capsys):
    """Test feedback when there are no uncommitted changes (PROJ-60656)."""
    from devflow.cli.commands.complete_command import _generate_commit_message
    import subprocess

    # Create session with git repository but no uncommitted changes
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Initialize a git repository
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)

    # Create initial commit (no uncommitted changes)
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial content\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)

    session = session_manager.create_session(
        name="no-changes-test",
        goal="Test no uncommitted changes",
        working_directory="no-changes-dir",
        project_path=str(tmp_path),
        ai_agent_session_id="uuid-no-changes",
    )

    # Generate commit message (should fall back to simple message)
    commit_msg = _generate_commit_message(session)

    # Verify fallback message
    assert commit_msg == "Test no uncommitted changes"

    # Verify user feedback
    captured = capsys.readouterr()
    assert "No uncommitted changes" in captured.out
    assert "using simple commit message" in captured.out


def test_generate_commit_message_logging(temp_daf_home, tmp_path, monkeypatch):
    """Test that diagnostic logging is created (PROJ-60656)."""
    from devflow.cli.commands.complete_command import _generate_commit_message
    import subprocess

    # Create session with git repository
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Initialize a git repository
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)

    # Create initial commit
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial content\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)

    # Make uncommitted changes
    test_file.write_text("modified content\n")

    session = session_manager.create_session(
        name="log-test",
        goal="Test logging",
        working_directory="log-dir",
        project_path=str(tmp_path),
        ai_agent_session_id="uuid-log",
    )

    # Mock AI functions to simulate success
    def mock_generate_from_diff(diff_content, status_summary):
        return "Test commit message from diff"

    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message_from_diff", mock_generate_from_diff)

    # Generate commit message
    _generate_commit_message(session)

    # Verify log file was created
    from devflow.utils.paths import get_cs_home
    log_file = get_cs_home() / "logs" / "complete.log"
    assert log_file.exists()

    # Read log and verify content
    log_content = log_file.read_text()
    assert "Starting commit message generation" in log_content
    assert "Found git diff" in log_content
    assert "Successfully generated AI commit message from git diff" in log_content


def test_generate_commit_message_multi_commit_scenario(temp_daf_home, tmp_path, monkeypatch):
    """Test that multiple commits in same session each get accurate messages (PROJ-60656).

    This tests the key scenario from the issue tracker ticket:
    1. User makes changes A and commits
    2. User makes changes B and commits again
    3. Second commit message should only describe changes B, not A+B
    """
    from devflow.cli.commands.complete_command import _generate_commit_message
    import subprocess

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Initialize a git repository
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)

    # Create initial commit
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial content\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)

    session = session_manager.create_session(
        name="multi-commit-test",
        goal="Test multi-commit scenario",
        working_directory="multi-commit-dir",
        project_path=str(tmp_path),
        ai_agent_session_id="uuid-multi",
    )

    # FIRST COMMIT: Make changes A
    test_file.write_text("changes A\n")

    # Track calls to the diff generator
    diff_calls = []

    def mock_generate_from_diff_first(diff_content, status_summary):
        diff_calls.append(diff_content)
        # Verify first diff only contains changes A
        assert "changes A" in diff_content
        assert "changes B" not in diff_content
        return "Add changes A to test.txt"

    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message_from_diff", mock_generate_from_diff_first)

    # Generate first commit message
    commit_msg_1 = _generate_commit_message(session)
    assert commit_msg_1 == "Add changes A to test.txt"

    # Actually commit changes A
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", commit_msg_1], cwd=tmp_path, check=True, capture_output=True)

    # SECOND COMMIT: Make changes B (different from changes A)
    test_file.write_text("changes B\n")

    def mock_generate_from_diff_second(diff_content, status_summary):
        diff_calls.append(diff_content)
        # Verify second diff only contains changes B in test.txt
        # (log files may contain references to "changes A" but that's OK)
        assert "changes B" in diff_content
        # The key test: verify test.txt diff shows -changes A +changes B
        # This proves we're seeing the diff between current and previous state
        assert "+changes B" in diff_content
        assert "-changes A" in diff_content  # This shows we're comparing against the committed version
        return "Add changes B to test.txt"

    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message_from_diff", mock_generate_from_diff_second)

    # Generate second commit message
    commit_msg_2 = _generate_commit_message(session)
    assert commit_msg_2 == "Add changes B to test.txt"

    # Verify we got different commit messages for different changes
    assert commit_msg_1 != commit_msg_2
    assert "changes A" in commit_msg_1
    assert "changes B" in commit_msg_2

    # Verify the diff generator was called twice with different content
    assert len(diff_calls) == 2


def test_update_jira_pr_field_success(temp_daf_home, monkeypatch, capsys):
    """Test that successful JIRA PR field update displays correct success message."""
    from devflow.cli.commands.complete_command import _update_jira_pr_field
    from devflow.jira.client import JiraClient
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Config, JiraConfig, PromptsConfig

    # Mock config with field mappings
    mock_config = Mock(spec=Config)
    mock_config.jira = Mock(spec=JiraConfig)
    mock_config.jira.field_mappings = {
        "git_pull_request": {
            "id": "customfield_12345",
            "name": "Git Pull Request"
        }
    }
    mock_config.prompts = Mock(spec=PromptsConfig)
    mock_config.prompts.auto_update_jira_pr_url = True

    # Mock ConfigLoader
    mock_config_loader = Mock(spec=ConfigLoader)
    mock_config_loader.load_config.return_value = mock_config

    # Mock JiraClient
    mock_client = Mock(spec=JiraClient)
    # update_ticket_field returns None on success
    mock_client.update_ticket_field.return_value = None
    mock_client.get_ticket_pr_links.return_value = None

    # Patch dependencies
    monkeypatch.setattr("devflow.cli.commands.complete_command.ConfigLoader", lambda: mock_config_loader)
    monkeypatch.setattr("devflow.cli.commands.complete_command.JiraClient", lambda: mock_client)

    # Call the function
    _update_jira_pr_field(
        issue_key="PROJ-12345",
        pr_url="https://github.com/org/repo/pull/123",
        no_issue_update=False
    )

    # Verify update was called
    mock_client.update_ticket_field.assert_called_once()

    # Verify success message is displayed (not failure message)
    captured = capsys.readouterr()
    assert "✓ Updated JIRA Git Pull Request field" in captured.out
    assert "Failed to update issue tracker ticket" not in captured.out


def test_update_jira_pr_field_failure(temp_daf_home, monkeypatch, capsys):
    """Test that failed JIRA PR field update displays correct error message."""
    from devflow.cli.commands.complete_command import _update_jira_pr_field
    from devflow.jira.client import JiraClient
    from devflow.jira.exceptions import JiraApiError
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Config, JiraConfig, PromptsConfig

    # Mock config with field mappings
    mock_config = Mock(spec=Config)
    mock_config.jira = Mock(spec=JiraConfig)
    mock_config.jira.field_mappings = {
        "git_pull_request": {
            "id": "customfield_12345",
            "name": "Git Pull Request"
        }
    }
    mock_config.prompts = Mock(spec=PromptsConfig)
    mock_config.prompts.auto_update_jira_pr_url = True

    # Mock ConfigLoader
    mock_config_loader = Mock(spec=ConfigLoader)
    mock_config_loader.load_config.return_value = mock_config

    # Mock JiraClient to raise exception
    mock_client = Mock(spec=JiraClient)
    mock_client.get_ticket_pr_links.return_value = None
    mock_client.update_ticket_field.side_effect = JiraApiError(
        "Field update failed",
        status_code=400,
        response_text="Invalid field value"
    )

    # Patch dependencies
    monkeypatch.setattr("devflow.cli.commands.complete_command.ConfigLoader", lambda: mock_config_loader)
    monkeypatch.setattr("devflow.cli.commands.complete_command.JiraClient", lambda: mock_client)

    # Call the function
    _update_jira_pr_field(
        issue_key="PROJ-12345",
        pr_url="https://github.com/org/repo/pull/123",
        no_issue_update=False
    )

    # Verify error message is displayed
    captured = capsys.readouterr()
    assert "Failed to update JIRA Git Pull Request field" in captured.out
    assert "✓ Updated JIRA Git Pull Request field" not in captured.out


def test_update_jira_pr_field_validation_error_with_field_errors(temp_daf_home, monkeypatch, capsys):
    """Test JiraValidationError handling with field-level errors."""
    from devflow.cli.commands.complete_command import _update_jira_pr_field
    from devflow.jira.client import JiraClient
    from devflow.jira.exceptions import JiraValidationError
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Config, JiraConfig, PromptsConfig

    # Mock config
    mock_config = Mock(spec=Config)
    mock_config.jira = Mock(spec=JiraConfig)
    mock_config.jira.field_mappings = {
        "git_pull_request": {
            "id": "customfield_12345",
            "name": "Git Pull Request"
        }
    }
    mock_config.prompts = Mock(spec=PromptsConfig)
    mock_config.prompts.auto_update_jira_pr_url = True

    mock_config_loader = Mock(spec=ConfigLoader)
    mock_config_loader.load_config.return_value = mock_config

    # Mock JiraClient to raise JiraValidationError with field errors
    mock_client = Mock(spec=JiraClient)
    mock_client.get_ticket_pr_links.return_value = None
    mock_client.update_ticket_field.side_effect = JiraValidationError(
        "Validation failed",
        field_errors={
            "customfield_12345": "Invalid URL format",
            "summary": "Required field missing"
        },
        error_messages=["URL must be accessible"]
    )

    monkeypatch.setattr("devflow.cli.commands.complete_command.ConfigLoader", lambda: mock_config_loader)
    monkeypatch.setattr("devflow.cli.commands.complete_command.JiraClient", lambda: mock_client)

    # Call the function
    _update_jira_pr_field(
        issue_key="PROJ-12345",
        pr_url="https://github.com/org/repo/pull/123",
        no_issue_update=False
    )

    # Verify detailed error messages
    captured = capsys.readouterr()
    assert "Failed to update JIRA Git Pull Request field" in captured.out
    assert "Field errors:" in captured.out
    assert "customfield_12345: Invalid URL format" in captured.out
    assert "summary: Required field missing" in captured.out
    assert "Error messages:" in captured.out
    assert "URL must be accessible" in captured.out
    assert "Suggestion: Verify that the PR/MR URL is accessible and properly formatted" in captured.out


def test_update_jira_pr_field_validation_error_with_error_messages_only(temp_daf_home, monkeypatch, capsys):
    """Test JiraValidationError handling with only error messages (no field errors)."""
    from devflow.cli.commands.complete_command import _update_jira_pr_field
    from devflow.jira.client import JiraClient
    from devflow.jira.exceptions import JiraValidationError
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Config, JiraConfig, PromptsConfig

    mock_config = Mock(spec=Config)
    mock_config.jira = Mock(spec=JiraConfig)
    mock_config.jira.field_mappings = {
        "git_pull_request": {
            "id": "customfield_12345",
            "name": "Git Pull Request"
        }
    }
    mock_config.prompts = Mock(spec=PromptsConfig)
    mock_config.prompts.auto_update_jira_pr_url = True

    mock_config_loader = Mock(spec=ConfigLoader)
    mock_config_loader.load_config.return_value = mock_config

    mock_client = Mock(spec=JiraClient)
    mock_client.get_ticket_pr_links.return_value = None
    mock_client.update_ticket_field.side_effect = JiraValidationError(
        "Validation failed",
        error_messages=["The issue is closed and cannot be edited", "Workflow transition not allowed"]
    )

    monkeypatch.setattr("devflow.cli.commands.complete_command.ConfigLoader", lambda: mock_config_loader)
    monkeypatch.setattr("devflow.cli.commands.complete_command.JiraClient", lambda: mock_client)

    _update_jira_pr_field(
        issue_key="PROJ-12345",
        pr_url="https://github.com/org/repo/pull/123",
        no_issue_update=False
    )

    captured = capsys.readouterr()
    assert "Failed to update JIRA Git Pull Request field" in captured.out
    assert "Error messages:" in captured.out
    assert "The issue is closed and cannot be edited" in captured.out
    assert "Workflow transition not allowed" in captured.out


def test_update_jira_pr_field_not_found_error(temp_daf_home, monkeypatch, capsys):
    """Test JiraNotFoundError handling with resource details."""
    from devflow.cli.commands.complete_command import _update_jira_pr_field
    from devflow.jira.client import JiraClient
    from devflow.jira.exceptions import JiraNotFoundError
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Config, JiraConfig, PromptsConfig

    mock_config = Mock(spec=Config)
    mock_config.jira = Mock(spec=JiraConfig)
    mock_config.jira.field_mappings = {
        "git_pull_request": {
            "id": "customfield_12345",
            "name": "Git Pull Request"
        }
    }
    mock_config.prompts = Mock(spec=PromptsConfig)
    mock_config.prompts.auto_update_jira_pr_url = True

    mock_config_loader = Mock(spec=ConfigLoader)
    mock_config_loader.load_config.return_value = mock_config

    mock_client = Mock(spec=JiraClient)
    mock_client.get_ticket_pr_links.return_value = None
    mock_client.update_ticket_field.side_effect = JiraNotFoundError(
        "Issue not found",
        resource_type="issue",
        resource_id="PROJ-12345"
    )

    monkeypatch.setattr("devflow.cli.commands.complete_command.ConfigLoader", lambda: mock_config_loader)
    monkeypatch.setattr("devflow.cli.commands.complete_command.JiraClient", lambda: mock_client)

    _update_jira_pr_field(
        issue_key="PROJ-12345",
        pr_url="https://github.com/org/repo/pull/123",
        no_issue_update=False
    )

    captured = capsys.readouterr()
    assert "Failed to update JIRA Git Pull Request field" in captured.out
    assert "Resource not found: issue PROJ-12345" in captured.out
    assert "Suggestion: Verify that the JIRA ticket PROJ-12345 exists and is accessible" in captured.out


def test_update_jira_pr_field_auth_error(temp_daf_home, monkeypatch, capsys):
    """Test JiraAuthError handling."""
    from devflow.cli.commands.complete_command import _update_jira_pr_field
    from devflow.jira.client import JiraClient
    from devflow.jira.exceptions import JiraAuthError
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Config, JiraConfig, PromptsConfig

    mock_config = Mock(spec=Config)
    mock_config.jira = Mock(spec=JiraConfig)
    mock_config.jira.field_mappings = {
        "git_pull_request": {
            "id": "customfield_12345",
            "name": "Git Pull Request"
        }
    }
    mock_config.prompts = Mock(spec=PromptsConfig)
    mock_config.prompts.auto_update_jira_pr_url = True

    mock_config_loader = Mock(spec=ConfigLoader)
    mock_config_loader.load_config.return_value = mock_config

    mock_client = Mock(spec=JiraClient)
    mock_client.get_ticket_pr_links.return_value = None
    mock_client.update_ticket_field.side_effect = JiraAuthError(
        "Invalid API token or insufficient permissions"
    )

    monkeypatch.setattr("devflow.cli.commands.complete_command.ConfigLoader", lambda: mock_config_loader)
    monkeypatch.setattr("devflow.cli.commands.complete_command.JiraClient", lambda: mock_client)

    _update_jira_pr_field(
        issue_key="PROJ-12345",
        pr_url="https://github.com/org/repo/pull/123",
        no_issue_update=False
    )

    captured = capsys.readouterr()
    assert "Failed to update JIRA Git Pull Request field" in captured.out
    assert "Authentication error: Invalid API token or insufficient permissions" in captured.out
    assert "Suggestion: Check your JIRA API token and permissions" in captured.out


def test_update_jira_pr_field_api_error_with_status_code(temp_daf_home, monkeypatch, capsys):
    """Test JiraApiError handling with HTTP status code and detailed errors."""
    from devflow.cli.commands.complete_command import _update_jira_pr_field
    from devflow.jira.client import JiraClient
    from devflow.jira.exceptions import JiraApiError
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Config, JiraConfig, PromptsConfig

    mock_config = Mock(spec=Config)
    mock_config.jira = Mock(spec=JiraConfig)
    mock_config.jira.field_mappings = {
        "git_pull_request": {
            "id": "customfield_12345",
            "name": "Git Pull Request"
        }
    }
    mock_config.prompts = Mock(spec=PromptsConfig)
    mock_config.prompts.auto_update_jira_pr_url = True

    mock_config_loader = Mock(spec=ConfigLoader)
    mock_config_loader.load_config.return_value = mock_config

    mock_client = Mock(spec=JiraClient)
    mock_client.get_ticket_pr_links.return_value = None
    mock_client.update_ticket_field.side_effect = JiraApiError(
        "Field update failed",
        status_code=400,
        response_text='{"errorMessages": ["Operation failed"], "errors": {"customfield_12345": "Invalid value"}}',
        error_messages=["Operation failed"],
        field_errors={"customfield_12345": "Invalid value"}
    )

    monkeypatch.setattr("devflow.cli.commands.complete_command.ConfigLoader", lambda: mock_config_loader)
    monkeypatch.setattr("devflow.cli.commands.complete_command.JiraClient", lambda: mock_client)

    _update_jira_pr_field(
        issue_key="PROJ-12345",
        pr_url="https://github.com/org/repo/pull/123",
        no_issue_update=False
    )

    captured = capsys.readouterr()
    assert "Failed to update JIRA Git Pull Request field" in captured.out
    assert "HTTP status code: 400" in captured.out
    assert "Error messages:" in captured.out
    assert "Operation failed" in captured.out
    assert "Field errors:" in captured.out
    assert "customfield_12345: Invalid value" in captured.out
    assert "Suggestion: Review the error details above and check JIRA field configuration" in captured.out


def test_update_jira_pr_field_connection_error(temp_daf_home, monkeypatch, capsys):
    """Test JiraConnectionError handling."""
    from devflow.cli.commands.complete_command import _update_jira_pr_field
    from devflow.jira.client import JiraClient
    from devflow.jira.exceptions import JiraConnectionError
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Config, JiraConfig, PromptsConfig

    mock_config = Mock(spec=Config)
    mock_config.jira = Mock(spec=JiraConfig)
    mock_config.jira.field_mappings = {
        "git_pull_request": {
            "id": "customfield_12345",
            "name": "Git Pull Request"
        }
    }
    mock_config.prompts = Mock(spec=PromptsConfig)
    mock_config.prompts.auto_update_jira_pr_url = True

    mock_config_loader = Mock(spec=ConfigLoader)
    mock_config_loader.load_config.return_value = mock_config

    mock_client = Mock(spec=JiraClient)
    mock_client.get_ticket_pr_links.return_value = None
    mock_client.update_ticket_field.side_effect = JiraConnectionError(
        "Failed to connect to https://jira.example.com: Connection timeout"
    )

    monkeypatch.setattr("devflow.cli.commands.complete_command.ConfigLoader", lambda: mock_config_loader)
    monkeypatch.setattr("devflow.cli.commands.complete_command.JiraClient", lambda: mock_client)

    _update_jira_pr_field(
        issue_key="PROJ-12345",
        pr_url="https://github.com/org/repo/pull/123",
        no_issue_update=False
    )

    captured = capsys.readouterr()
    assert "Failed to update JIRA Git Pull Request field" in captured.out
    assert "Connection error: Failed to connect to https://jira.example.com" in captured.out
    assert "timeout" in captured.out
    assert "Suggestion: Check your network connection and JIRA URL configuration" in captured.out


def test_complete_pushes_commits_after_committing_with_auto_config(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test Commits are pushed to remote immediately after committing with auto config."""
    import subprocess

    # Create a git repository with a remote
    repo_dir = tmp_path / "test-repo-push"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create a bare remote repository
    remote_dir = tmp_path / "remote.git"
    remote_dir.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_dir, capture_output=True)

    # Add remote
    subprocess.run(["git", "remote", "add", "origin", str(remote_dir)], cwd=repo_dir, capture_output=True)

    # Create initial commit on main and push to remote
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-push"], cwd=repo_dir, capture_output=True)

    # Create uncommitted changes
    (repo_dir / "new-file.txt").write_text("new content")

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="push-test",
        goal="Test push",
        working_directory="test-repo-push",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-push",
        branch="feature-push",
    )

    # Add work session
    session_manager.start_work_session("push-test")
    session_manager.end_work_session("push-test")

    # Configure auto_push_to_remote
    from devflow.config.models import Config, JiraConfig, PromptsConfig, RepoConfig
    config = config_loader.load_config()
    if not config:
        # Create a default config if none exists
        config = Config(
            jira=JiraConfig(
                url="https://jira.example.com",
                user="testuser",
                transitions={}
            ),
            repos=RepoConfig(
                workspace=str(tmp_path)
            )
        )
    config.prompts = PromptsConfig(
        auto_commit_on_complete=True,
        auto_push_to_remote=True,  # Auto push enabled
        auto_create_pr_on_complete=False
    )
    config_loader.save_config(config)

    # Mock commit message generation
    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message", lambda s: "Test commit")

    # Mock all Confirm.ask calls (we're testing with auto_commit_on_complete=True, but there's still a confirm prompt)
    # The auto_commit_on_complete config bypasses the "Commit these changes?" prompt
    # but NOT the "Use this commit message?" prompt
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: True)

    # Complete the session
    complete_session("push-test")

    # Verify commits were pushed to remote
    result = subprocess.run(
        ["git", "log", "origin/feature-push..feature-push", "--oneline"],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    # Should have NO unpushed commits (empty output means branch is up to date with remote)
    assert result.stdout.strip() == "", "Expected no unpushed commits after complete"

    # Verify output mentions push
    captured = capsys.readouterr()
    assert "Commits pushed to remote" in captured.out or "No unpushed commits" in captured.out


def test_complete_pushes_commits_after_committing_with_prompt(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test Commits are pushed to remote when user confirms prompt."""
    import subprocess

    # Create a git repository with a remote
    repo_dir = tmp_path / "test-repo-push-prompt"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create a bare remote repository
    remote_dir = tmp_path / "remote-prompt.git"
    remote_dir.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_dir, capture_output=True)

    # Add remote
    subprocess.run(["git", "remote", "add", "origin", str(remote_dir)], cwd=repo_dir, capture_output=True)

    # Create initial commit on main and push to remote
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-prompt"], cwd=repo_dir, capture_output=True)

    # Create uncommitted changes
    (repo_dir / "new-file.txt").write_text("new content")

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="push-prompt-test",
        goal="Test push prompt",
        working_directory="test-repo-push-prompt",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-push-prompt",
        branch="feature-prompt",
    )

    # Add work session
    session_manager.start_work_session("push-prompt-test")
    session_manager.end_work_session("push-prompt-test")

    # Mock commit message generation
    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message", lambda s: "Test commit")

    # Mock Confirm.ask to return True for commit and push, False for everything else
    confirm_calls = []
    def mock_confirm(prompt, **kwargs):
        confirm_calls.append(prompt)
        # Accept commit and push prompts, decline everything else
        if "Commit these changes" in prompt:
            return True
        if "Use this commit message" in prompt:
            return True
        if "Push commits to remote" in prompt:
            return True
        return False

    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm)

    # Complete the session
    complete_session("push-prompt-test")

    # Verify commits were pushed to remote
    result = subprocess.run(
        ["git", "log", "origin/feature-prompt..feature-prompt", "--oneline"],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    assert result.stdout.strip() == "", "Expected no unpushed commits after complete"

    # Verify push prompt was shown
    captured = capsys.readouterr()
    assert "Commits pushed to remote" in captured.out


def test_complete_skips_push_when_user_declines(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test Push is skipped when user declines the prompt."""
    import subprocess

    # Create a git repository with a remote
    repo_dir = tmp_path / "test-repo-skip-push"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create a bare remote repository
    remote_dir = tmp_path / "remote-skip.git"
    remote_dir.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_dir, capture_output=True)

    # Add remote
    subprocess.run(["git", "remote", "add", "origin", str(remote_dir)], cwd=repo_dir, capture_output=True)

    # Create initial commit on main and push to remote
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-skip"], cwd=repo_dir, capture_output=True)

    # Create uncommitted changes
    (repo_dir / "new-file.txt").write_text("new content")

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="skip-push-test",
        goal="Test skip push",
        working_directory="test-repo-skip-push",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-skip-push",
        branch="feature-skip",
    )

    # Add work session
    session_manager.start_work_session("skip-push-test")
    session_manager.end_work_session("skip-push-test")

    # Mock commit message generation
    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message", lambda s: "Test commit")

    # Mock Confirm.ask to accept commit but decline push
    def mock_confirm(prompt, **kwargs):
        if "Commit these changes" in prompt:
            return True
        if "Use this commit message" in prompt:
            return True
        if "Push commits to remote" in prompt:
            return False  # Decline push
        return False

    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm)

    # Complete the session
    complete_session("skip-push-test")

    # Verify commits were NOT pushed to remote
    # Check if branch exists on remote
    result = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", "feature-skip"],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    # Branch should NOT exist on remote when user declines push
    assert result.stdout.strip() == "", "Expected branch to not exist on remote when user declines push"

    # Verify the commit was made locally
    result = subprocess.run(
        ["git", "log", "--oneline", "-1"],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    assert "Test commit" in result.stdout, "Expected commit to exist locally"

    # Verify skip message was shown
    captured = capsys.readouterr()
    assert "Skipping push - commits remain local" in captured.out


def test_complete_no_duplicate_push_when_creating_pr(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test Ensure no duplicate push when creating PR after committing."""
    import subprocess

    # Create a git repository with a remote
    repo_dir = tmp_path / "test-repo-no-dup"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create a bare remote repository
    remote_dir = tmp_path / "remote-no-dup.git"
    remote_dir.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_dir, capture_output=True)

    # Add remote
    subprocess.run(["git", "remote", "add", "origin", str(remote_dir)], cwd=repo_dir, capture_output=True)

    # Create initial commit on main and push to remote
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-no-dup"], cwd=repo_dir, capture_output=True)

    # Create uncommitted changes
    (repo_dir / "new-file.txt").write_text("new content")

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-dup-test",
        goal="Test no duplicate",
        working_directory="test-repo-no-dup",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-no-dup",
        branch="feature-no-dup",
    )

    # Add work session
    session_manager.start_work_session("no-dup-test")
    session_manager.end_work_session("no-dup-test")

    # Mock commit message generation
    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message", lambda s: "Test commit")

    # Track push operations
    push_count = 0
    original_push = GitUtils.push_branch
    def track_push(*args, **kwargs):
        nonlocal push_count
        push_count += 1
        return original_push(*args, **kwargs)

    monkeypatch.setattr("devflow.git.utils.GitUtils.push_branch", track_push)
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.push_branch", track_push)

    # Mock Confirm.ask to accept commit, push, and PR creation
    def mock_confirm(prompt, **kwargs):
        if "Commit these changes" in prompt:
            return True
        if "Use this commit message" in prompt:
            return True
        if "Push" in prompt:
            return True
        if "Create a PR/MR" in prompt:
            return True
        return False

    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm)

    # Mock PR creation to avoid needing gh/glab CLI
    monkeypatch.setattr("devflow.cli.commands.complete_command._create_pr_mr", lambda s, w, sm: "https://example.com/pr/1")
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: None)

    # Complete the session
    complete_session("no-dup-test")

    # Verify push was called only ONCE (not duplicated)
    # After my fix, push happens once after commit, and PR creation skips push if no unpushed commits
    assert push_count == 1, f"Expected push to be called once, but was called {push_count} times"

    # Verify commits were pushed to remote
    result = subprocess.run(
        ["git", "log", "origin/feature-no-dup..feature-no-dup", "--oneline"],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    assert result.stdout.strip() == "", "Expected no unpushed commits after complete"


# Tests for daf complete prompts for PR/MR creation even when no commits exist


def test_complete_no_pr_prompt_when_no_commits(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that daf complete does NOT prompt for PR when no commits were made this cycle."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-no-commits"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch with a commit
    subprocess.run(["git", "checkout", "-b", "feature-old-commits"], cwd=repo_dir, capture_output=True)
    (repo_dir / "feature.txt").write_text("feature work")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add feature"], cwd=repo_dir, capture_output=True)

    # Simulate that this branch was already merged to main
    # (In reality, user created PR, merged it, but session wasn't marked complete)
    # For this test, we just have old commits on the branch

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-commits-test",
        goal="Test no commits scenario",
        working_directory="test-no-commits",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-no-commits",
        branch="feature-old-commits",
    )

    # Add work session with meaningful time
    session_manager.start_work_session("no-commits-test")
    from devflow.config.models import WorkSession
    session.work_sessions.append(WorkSession(
        user="testuser",
        start=datetime.now() - timedelta(minutes=10),
        end=datetime.now() - timedelta(minutes=5),
    ))
    session_manager.update_session(session)

    # Track confirm prompts
    confirm_prompts = []
    def mock_confirm_ask(prompt, **kwargs):
        confirm_prompts.append(prompt)
        return False  # Decline all prompts

    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm_ask)

    # Complete the session (no changes, no commits)
    complete_session("no-commits-test")

    # Verify NO PR prompt was shown
    pr_prompts = [p for p in confirm_prompts if "PR" in p or "MR" in p]
    assert len(pr_prompts) == 0, f"Expected no PR prompts, but got: {pr_prompts}"

    # Check output shows skip message
    captured = capsys.readouterr()
    assert "No new commits - skipping PR creation" in captured.out


def test_complete_prompts_pr_when_commit_made(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that daf complete DOES prompt for PR when a commit was made this cycle."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-with-commit"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-new-work"], cwd=repo_dir, capture_output=True)

    # Add uncommitted changes (will be committed during complete)
    (repo_dir / "feature.txt").write_text("new feature work")

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="with-commit-test",
        goal="Test commit scenario",
        working_directory="test-with-commit",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-with-commit",
        branch="feature-new-work",
    )

    # Add work session
    session_manager.start_work_session("with-commit-test")
    from devflow.config.models import WorkSession
    session.work_sessions.append(WorkSession(
        user="testuser",
        start=datetime.now() - timedelta(minutes=10),
        end=datetime.now() - timedelta(minutes=5),
    ))
    session_manager.update_session(session)

    # Track confirm prompts
    confirm_prompts = []
    def mock_confirm_ask(prompt, **kwargs):
        confirm_prompts.append(prompt)
        if "Commit these changes" in prompt:
            return True  # Accept commit
        if "Use this commit message" in prompt:
            return True
        if "Push" in prompt:
            return False  # Decline push (to simplify test)
        if "PR" in prompt or "MR" in prompt:
            return False  # Decline PR
        return False

    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm_ask)
    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_commit_message", lambda s: "Test commit")
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: None)

    # Complete the session
    complete_session("with-commit-test")

    # Verify PR prompt WAS shown (because we made a commit)
    pr_prompts = [p for p in confirm_prompts if "PR" in p or "MR" in p]
    assert len(pr_prompts) > 0, f"Expected PR prompt after making a commit, but got no prompts"


def test_complete_prompts_pr_when_uncommitted_changes_exist(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that daf complete prompts for PR when uncommitted changes exist (even if user declines commit)."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-uncommitted"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature-uncommitted"], cwd=repo_dir, capture_output=True)

    # Add uncommitted changes
    (repo_dir / "feature.txt").write_text("uncommitted work")

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="uncommitted-test",
        goal="Test uncommitted changes",
        working_directory="test-uncommitted",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-uncommitted",
        branch="feature-uncommitted",
    )

    # Add work session
    session_manager.start_work_session("uncommitted-test")
    from devflow.config.models import WorkSession
    session.work_sessions.append(WorkSession(
        user="testuser",
        start=datetime.now() - timedelta(minutes=10),
        end=datetime.now() - timedelta(minutes=5),
    ))
    session_manager.update_session(session)

    # Track confirm prompts
    confirm_prompts = []
    def mock_confirm_ask(prompt, **kwargs):
        confirm_prompts.append(prompt)
        if "Commit these changes" in prompt:
            return False  # Decline commit (user chooses not to commit)
        if "PR" in prompt or "MR" in prompt:
            return False  # Decline PR
        return False

    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm_ask)
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: None)

    # Complete the session
    complete_session("uncommitted-test")

    # Verify PR prompt WAS shown (because there are uncommitted changes, even though user declined commit)
    pr_prompts = [p for p in confirm_prompts if "PR" in p or "MR" in p]
    assert len(pr_prompts) > 0, f"Expected PR prompt when uncommitted changes exist, but got no prompts"


def test_complete_no_pr_prompt_after_merged_branch(temp_daf_home, tmp_path, monkeypatch, capsys):
    """Test that daf complete does NOT prompt for PR when branch was already merged."""
    import subprocess
    from devflow.config.loader import ConfigLoader
    from devflow.session.manager import SessionManager

    # Create a git repository
    repo_dir = tmp_path / "test-merged"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)

    # Create initial commit on main
    (repo_dir / "test.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_dir, capture_output=True)

    # Create a feature branch with work
    subprocess.run(["git", "checkout", "-b", "feature-merged"], cwd=repo_dir, capture_output=True)
    (repo_dir / "feature.txt").write_text("feature work")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add feature"], cwd=repo_dir, capture_output=True)

    # Simulate merge: go back to main and merge the feature branch
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "merge", "feature-merged", "--no-ff", "-m", "Merge feature"], cwd=repo_dir, capture_output=True)

    # Go back to feature branch (user reopens session after merge)
    subprocess.run(["git", "checkout", "feature-merged"], cwd=repo_dir, capture_output=True)

    # Create session (simulating user reopening after merge)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="merged-test",
        goal="Test merged branch scenario",
        working_directory="test-merged",
        project_path=str(repo_dir),
        ai_agent_session_id="uuid-merged",
        branch="feature-merged",
    )

    # Add work session
    session_manager.start_work_session("merged-test")
    from devflow.config.models import WorkSession
    session.work_sessions.append(WorkSession(
        user="testuser",
        start=datetime.now() - timedelta(minutes=10),
        end=datetime.now() - timedelta(minutes=5),
    ))
    session_manager.update_session(session)

    # Track confirm prompts
    confirm_prompts = []
    def mock_confirm_ask(prompt, **kwargs):
        confirm_prompts.append(prompt)
        return False

    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm_ask)

    # Complete the session (no new changes, branch already merged)
    complete_session("merged-test")

    # Verify NO PR prompt was shown
    pr_prompts = [p for p in confirm_prompts if "PR" in p or "MR" in p]
    assert len(pr_prompts) == 0, f"Expected no PR prompts for merged branch, but got: {pr_prompts}"

    # Check output shows skip message
    captured = capsys.readouterr()
    assert "No new commits - skipping PR creation" in captured.out
