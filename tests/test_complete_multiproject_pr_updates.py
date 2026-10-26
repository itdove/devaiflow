"""Tests for multi-project PR URL updates to JIRA (PROJ-60247 / GitHub #183)."""

from datetime import datetime
import json
from pathlib import Path
from unittest.mock import Mock, patch, call
import subprocess

import pytest

from devflow.cli.commands.complete_command import (
    _create_pr_mr_for_conversation,
    _create_pr_mr_for_project,
    complete_session,
)
from devflow.config.loader import ConfigLoader
from devflow.config.models import (
    Config,
    Conversation,
    ConversationContext,
    JiraConfig,
    ProjectInfo,
    RepoConfig,
)
from devflow.git.utils import GitUtils
from devflow.github.issues_client import GitHubClient
from devflow.session.manager import SessionManager


@pytest.fixture
def git_repo(tmp_path):
    """Create a git repository for testing."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True, check=True)

    # Create initial commit on main
    (repo_dir / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True, check=True)

    # Create feature branch with changes
    subprocess.run(["git", "checkout", "-b", "feature-test"], cwd=repo_dir, capture_output=True, check=True)
    (repo_dir / "feature.txt").write_text("new feature")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Add feature"], cwd=repo_dir, capture_output=True, check=True)

    return repo_dir


def test_multiproject_workflow_existing_pr_updates_jira(temp_daf_home, git_repo, monkeypatch, capsys):
    """Test that multi-project workflow updates JIRA with existing PR URL (GitHub #183).

    Tests the fix for lines 303-310 in complete_command.py:
    - Multi-project workflow with projects array
    - Existing open PR
    - Should call _update_issue_pr_field() with existing PR URL
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with JIRA issue key and projects array
    session = session_manager.create_session(
        name="multiproject-existing-pr",
        goal="Test multi-project with existing PR",
        working_directory="backend-api",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-multiproject-1",
        issue_key="PROJ-12345",
        branch="feature-test",
    )

    # Add project to active conversation's projects dict
    active_conv = session.conversations[session.working_directory].active_session
    active_conv.is_multi_project = True
    active_conv.projects = {
        "backend-api": ProjectInfo(
            project_path=str(git_repo),
            branch="feature-test",
            base_branch="main",
            repo_name="backend-api"
        )
    }
    session_manager.update_session(session)

    # Add work session
    session_manager.start_work_session("multiproject-existing-pr")
    session_manager.end_work_session("multiproject-existing-pr")

    # Mock existing PR
    existing_pr_url = "https://github.com/org/backend-api/pull/123"
    mock_pr_status = {'state': 'open', 'url': existing_pr_url}
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: mock_pr_status)

    # Mock _update_issue_pr_field to track calls
    update_pr_field_calls = []
    def mock_update_pr_field(session, config, pr_url, no_issue_update):
        update_pr_field_calls.append({
            'issue_key': session.issue_key,
            'pr_url': pr_url,
            'no_issue_update': no_issue_update
        })
    monkeypatch.setattr("devflow.cli.commands.complete_command._update_issue_pr_field", mock_update_pr_field)

    # Mock other interactions
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.jira_transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.git.utils.GitUtils.has_unpushed_commits", lambda w, b: False)

    # Complete the session
    complete_session("multiproject-existing-pr")

    # Verify _update_issue_pr_field was called with existing PR URL
    assert len(update_pr_field_calls) == 1, f"Expected 1 call to _update_issue_pr_field, got {len(update_pr_field_calls)}"
    assert update_pr_field_calls[0]['issue_key'] == "PROJ-12345"
    assert update_pr_field_calls[0]['pr_url'] == existing_pr_url
    assert update_pr_field_calls[0]['no_issue_update'] == False

    # Verify PR URL was stored in session (reload to get latest state)
    session_manager_check = SessionManager(config_loader)
    reloaded_session = session_manager_check.index.get_sessions("multiproject-existing-pr")[0]
    active_conv = reloaded_session.conversations[reloaded_session.working_directory].active_session
    assert existing_pr_url in active_conv.prs


def test_multiproject_workflow_new_pr_updates_jira(temp_daf_home, git_repo, monkeypatch, capsys):
    """Test that multi-project workflow updates JIRA when creating new PR (GitHub #183).

    Tests the fix for lines 327-338 in complete_command.py:
    - Multi-project workflow with projects array
    - Creating new PR
    - Should call _update_issue_pr_field() with new PR URL
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with JIRA issue key and projects array
    session = session_manager.create_session(
        name="multiproject-new-pr",
        goal="Test multi-project with new PR",
        working_directory="frontend-app",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-multiproject-2",
        issue_key="PROJ-67890",
        branch="feature-test",
    )

    # Add project to active conversation's projects dict
    active_conv = session.conversations[session.working_directory].active_session
    active_conv.is_multi_project = True
    active_conv.projects = {
        "frontend-app": ProjectInfo(
            project_path=str(git_repo),
            branch="feature-test",
            base_branch="main",
            repo_name="frontend-app"
        )
    }
    session_manager.update_session(session)

    # Add work session
    session_manager.start_work_session("multiproject-new-pr")
    session_manager.end_work_session("multiproject-new-pr")

    # Mock no existing PR (will create new one)
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: None)

    # Mock PR creation
    new_pr_url = "https://github.com/org/frontend-app/pull/456"
    monkeypatch.setattr("devflow.cli.commands.complete_command._create_pr_mr_for_project",
                       lambda s, p, w, sm: new_pr_url)

    # Mock _update_issue_pr_field to track calls
    update_pr_field_calls = []
    def mock_update_pr_field(session, config, pr_url, no_issue_update):
        update_pr_field_calls.append({
            'issue_key': session.issue_key,
            'pr_url': pr_url,
            'no_issue_update': no_issue_update
        })
    monkeypatch.setattr("devflow.cli.commands.complete_command._update_issue_pr_field", mock_update_pr_field)

    # Mock other interactions (say yes to creating PR)
    def mock_confirm(prompt, **kwargs):
        if "Create PR/MR" in prompt:
            return True
        return False
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm)
    monkeypatch.setattr("devflow.cli.commands.complete_command.jira_transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.git.utils.GitUtils.get_changed_files", lambda w, b, f: ["feature.txt"])

    # Complete the session
    complete_session("multiproject-new-pr")

    # Verify _update_issue_pr_field was called with new PR URL
    assert len(update_pr_field_calls) == 1, f"Expected 1 call to _update_issue_pr_field, got {len(update_pr_field_calls)}"
    assert update_pr_field_calls[0]['issue_key'] == "PROJ-67890"
    assert update_pr_field_calls[0]['pr_url'] == new_pr_url
    assert update_pr_field_calls[0]['no_issue_update'] == False

    # Verify PR URL was stored in session (reload to get latest state)
    session_manager_check = SessionManager(config_loader)
    reloaded_session = session_manager_check.index.get_sessions("multiproject-new-pr")[0]
    active_conv = reloaded_session.conversations[reloaded_session.working_directory].active_session
    assert new_pr_url in active_conv.prs


def test_multiconversation_existing_pr_updates_jira(temp_daf_home, git_repo, monkeypatch, capsys):
    """Test that multi-conversation architecture updates JIRA with existing PR (GitHub #183).

    Tests the fix for lines 440-447 in complete_command.py:
    - Multi-conversation architecture (separate conversations for different projects)
    - Existing open PR
    - Should call _update_issue_pr_field() with existing PR URL
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with multiple conversations
    session = session_manager.create_session(
        name="multiconv-existing-pr",
        goal="Test multi-conversation with existing PR",
        working_directory="backend-api",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-multiconv-1",
        issue_key="PROJ-11111",
        branch="feature-test",
    )

    # Add second conversation manually
    from devflow.config.models import ConversationContext, Conversation
    second_conv_context = ConversationContext(
        ai_agent_session_id="uuid-multiconv-frontend",
        project_path=str(git_repo / "frontend"),
        branch="feature-test",
        base_branch="main",
        prs=[],
        repo_name="frontend-app",
        created=datetime.now(),
        last_active=datetime.now()
    )
    second_conv = Conversation(
        active_session=second_conv_context,
        archived_sessions=[],
        message_count=0,
        created_at=datetime.now(),
        last_active=datetime.now()
    )
    session.conversations["frontend-app"] = second_conv
    session_manager.update_session(session)

    # Add work session
    session_manager.start_work_session("multiconv-existing-pr")
    session_manager.end_work_session("multiconv-existing-pr")

    # Mock existing PR for both conversations
    existing_pr_urls = {
        "backend-api": "https://github.com/org/backend-api/pull/111",
        "frontend-app": "https://github.com/org/frontend-app/pull/222"
    }

    def mock_get_pr(working_dir, branch):
        # Determine which project based on path
        if "frontend" in str(working_dir):
            return {'state': 'open', 'url': existing_pr_urls["frontend-app"]}
        return {'state': 'open', 'url': existing_pr_urls["backend-api"]}

    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", mock_get_pr)

    # Mock _update_issue_pr_field to track calls
    update_pr_field_calls = []
    def mock_update_pr_field(session, config, pr_url, no_issue_update):
        update_pr_field_calls.append({
            'issue_key': session.issue_key,
            'pr_url': pr_url,
            'no_issue_update': no_issue_update
        })
    monkeypatch.setattr("devflow.cli.commands.complete_command._update_issue_pr_field", mock_update_pr_field)

    # Mock other interactions
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.jira_transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.git.utils.GitUtils.has_unpushed_commits", lambda w, b: False)
    monkeypatch.setattr("devflow.git.utils.GitUtils.is_git_repository", lambda w: True)
    monkeypatch.setattr("devflow.git.utils.GitUtils.get_current_branch", lambda w: "feature-test")

    # Complete the session
    complete_session("multiconv-existing-pr")

    # Verify _update_issue_pr_field was called for both conversations
    assert len(update_pr_field_calls) == 2, f"Expected 2 calls to _update_issue_pr_field (one per conversation), got {len(update_pr_field_calls)}"

    # Verify both PR URLs were sent to JIRA
    pr_urls_sent = {call['pr_url'] for call in update_pr_field_calls}
    assert existing_pr_urls["backend-api"] in pr_urls_sent
    assert existing_pr_urls["frontend-app"] in pr_urls_sent

    # Verify all calls have correct issue key
    for call in update_pr_field_calls:
        assert call['issue_key'] == "PROJ-11111"
        assert call['no_issue_update'] == False


def test_multiconversation_new_pr_updates_jira(temp_daf_home, git_repo, monkeypatch, capsys):
    """Test that multi-conversation architecture updates JIRA when creating new PRs (GitHub #183).

    Tests the fix for lines 465-475 in complete_command.py:
    - Multi-conversation architecture (separate conversations for different projects)
    - Creating new PRs
    - Should call _update_issue_pr_field() with new PR URLs
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with multiple conversations
    session = session_manager.create_session(
        name="multiconv-new-pr",
        goal="Test multi-conversation with new PR",
        working_directory="backend-api",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-multiconv-2",
        issue_key="PROJ-22222",
        branch="feature-test",
    )

    # Add second conversation
    from devflow.config.models import ConversationContext, Conversation
    second_conv_context = ConversationContext(
        ai_agent_session_id="uuid-multiconv-frontend-2",
        project_path=str(git_repo / "frontend"),
        branch="feature-test",
        base_branch="main",
        prs=[],
        repo_name="frontend-app",
        created=datetime.now(),
        last_active=datetime.now()
    )
    second_conv = Conversation(
        active_session=second_conv_context,
        archived_sessions=[],
        message_count=0,
        created_at=datetime.now(),
        last_active=datetime.now()
    )
    session.conversations["frontend-app"] = second_conv
    session_manager.update_session(session)

    # Add work session
    session_manager.start_work_session("multiconv-new-pr")
    session_manager.end_work_session("multiconv-new-pr")

    # Mock no existing PRs (will create new ones)
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: None)

    # Mock PR creation for both conversations
    new_pr_urls = {
        "backend-api": "https://github.com/org/backend-api/pull/333",
        "frontend-app": "https://github.com/org/frontend-app/pull/444"
    }

    pr_creation_count = {'count': 0}
    def mock_create_pr(session, conv, working_dir, session_manager):
        # Alternate between backend and frontend
        pr_creation_count['count'] += 1
        if pr_creation_count['count'] == 1:
            return new_pr_urls["backend-api"]
        return new_pr_urls["frontend-app"]

    monkeypatch.setattr("devflow.cli.commands.complete_command._create_pr_mr_for_conversation", mock_create_pr)

    # Mock _update_issue_pr_field to track calls
    update_pr_field_calls = []
    def mock_update_pr_field(session, config, pr_url, no_issue_update):
        update_pr_field_calls.append({
            'issue_key': session.issue_key,
            'pr_url': pr_url,
            'no_issue_update': no_issue_update
        })
    monkeypatch.setattr("devflow.cli.commands.complete_command._update_issue_pr_field", mock_update_pr_field)

    # Mock other interactions (say yes to creating PRs)
    def mock_confirm(prompt, **kwargs):
        if "Create PR/MR" in prompt:
            return True
        return False
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", mock_confirm)
    monkeypatch.setattr("devflow.cli.commands.complete_command.jira_transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.git.utils.GitUtils.get_changed_files", lambda w, b, f: ["feature.txt"])
    monkeypatch.setattr("devflow.git.utils.GitUtils.is_git_repository", lambda w: True)
    monkeypatch.setattr("devflow.git.utils.GitUtils.get_current_branch", lambda w: "feature-test")

    # Complete the session
    complete_session("multiconv-new-pr")

    # Verify _update_issue_pr_field was called for both conversations
    assert len(update_pr_field_calls) == 2, f"Expected 2 calls to _update_issue_pr_field (one per conversation), got {len(update_pr_field_calls)}"

    # Verify both PR URLs were sent to JIRA
    pr_urls_sent = {call['pr_url'] for call in update_pr_field_calls}
    assert new_pr_urls["backend-api"] in pr_urls_sent
    assert new_pr_urls["frontend-app"] in pr_urls_sent

    # Verify all calls have correct issue key
    for call in update_pr_field_calls:
        assert call['issue_key'] == "PROJ-22222"
        assert call['no_issue_update'] == False


def test_no_issue_update_flag_respected_in_multiproject(temp_daf_home, git_repo, monkeypatch, capsys):
    """Test that --no-issue-update flag is respected in multi-project workflows (GitHub #183)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with projects array
    session = session_manager.create_session(
        name="multiproject-no-update",
        goal="Test --no-issue-update flag",
        working_directory="backend-api",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-no-update",
        issue_key="PROJ-99999",
        branch="feature-test",
    )

    # Add project to projects dict
    active_conv = session.conversations[session.working_directory].active_session
    active_conv.is_multi_project = True
    active_conv.projects = {
        "backend-api": ProjectInfo(
            project_path=str(git_repo),
            branch="feature-test",
            base_branch="main",
            repo_name="backend-api"
        )
    }
    session_manager.update_session(session)

    # Add work session
    session_manager.start_work_session("multiproject-no-update")
    session_manager.end_work_session("multiproject-no-update")

    # Mock existing PR
    existing_pr_url = "https://github.com/org/backend-api/pull/999"
    mock_pr_status = {'state': 'open', 'url': existing_pr_url}
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: mock_pr_status)

    # Mock _update_issue_pr_field to track calls
    update_pr_field_calls = []
    def mock_update_pr_field(session, config, pr_url, no_issue_update):
        update_pr_field_calls.append({
            'issue_key': session.issue_key,
            'pr_url': pr_url,
            'no_issue_update': no_issue_update
        })
    monkeypatch.setattr("devflow.cli.commands.complete_command._update_issue_pr_field", mock_update_pr_field)

    # Mock other interactions
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command.jira_transition_on_complete", lambda s, c: None)
    monkeypatch.setattr("devflow.git.utils.GitUtils.has_unpushed_commits", lambda w, b: False)

    # Complete the session with --no-issue-update flag
    complete_session("multiproject-no-update", no_issue_update=True)

    # Verify _update_issue_pr_field was still called but with no_issue_update=True
    assert len(update_pr_field_calls) == 1
    assert update_pr_field_calls[0]['no_issue_update'] == True

    # The function should have been called (for consistent behavior)
    # but the flag will be checked inside _update_issue_pr_field to skip actual update


@pytest.mark.parametrize("workflow", ["single", "multiproject", "multiconversation"])
@pytest.mark.parametrize("new_pr", [False, True])
@pytest.mark.parametrize("link_state", ["present", "absent", "flag", "disabled"])
def test_github_pr_link_completion_paths(
    temp_daf_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    workflow: str,
    new_pr: bool,
    link_state: str,
) -> None:
    """All completion paths use the remote check and remain idempotent on repeat."""
    from devflow.cli.commands import complete_command as command

    loader = ConfigLoader()
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", transitions={}),
        repos=RepoConfig(),
        issue_tracker_backend="github",
    )
    config.prompts.auto_update_jira_pr_url = False if link_state == "disabled" else None
    config.prompts.auto_add_issue_summary = False
    monkeypatch.setattr(ConfigLoader, "load_config", lambda self: config)
    manager = SessionManager(loader)
    paths = [tmp_path / "project-a"]
    if workflow != "single":
        paths.append(tmp_path / "project-b")
    pr_urls = {
        path: f"https://github.com/owner/{path.name}/pull/{123 + index}"
        for index, path in enumerate(paths)
    }
    session = manager.create_session(
        name="github-pr-links",
        goal="Check GitHub PR links",
        working_directory="project-a",
        project_path=str(paths[0]),
        ai_agent_session_id="uuid-project-a",
        issue_key="owner/project-a#42",
        branch="feature-test",
    )
    active = session.active_conversation
    assert active is not None
    if workflow == "multiproject":
        active.is_multi_project = True
        active.projects = {
            path.name: ProjectInfo(
                project_path=str(path),
                branch="feature-test",
                base_branch="main",
                repo_name=path.name,
            )
            for path in paths
        }
    elif workflow == "multiconversation":
        session.conversations["project-b"] = Conversation(
            active_session=ConversationContext(
                ai_agent_session_id="uuid-project-b",
                project_path=str(paths[1]),
                branch="feature-test",
            )
        )
    manager.update_session(session)

    comments = (
        [{"body": f"Related: {url}"} for url in pr_urls.values()] if link_state == "present" else []
    )
    initial_comment_count = len(comments)
    client = GitHubClient(repository="different/current-repository")

    def read_issue(args: list[str]) -> str:
        """Emulate remote reads while checking fully qualified issue ownership."""
        if args[1] == "/repos/owner/project-a/issues/42":
            return json.dumps({"number": 42, "body": "Issue description"})
        assert args[1] == "/repos/owner/project-a/issues/42/comments?per_page=100"
        assert "--paginate" in args and "--slurp" in args
        return json.dumps([comments])

    def write_comment(args: list[str], payload: str) -> str:
        """Make subsequent remote checks observe the newly added link."""
        assert args[1] == "/repos/owner/project-a/issues/42/comments"
        comments.append(json.loads(payload))
        return "{}"

    read = Mock(side_effect=read_issue)
    write = Mock(side_effect=write_comment)
    monkeypatch.setattr(client, "_run_gh_command", read)
    monkeypatch.setattr(client, "_run_gh_command_with_input", write)
    factory = Mock(return_value=client)
    monkeypatch.setattr(command, "create_issue_tracker_client", factory)
    monkeypatch.setattr(command, "get_issue_tracker_backend", lambda *args: "github")
    monkeypatch.setattr(command, "github_transition_on_complete", Mock())
    monkeypatch.setattr(command, "is_non_interactive", lambda: False)
    monkeypatch.setattr(command, "_start_branch_prefetch", lambda *args: None)
    monkeypatch.setattr(command, "_get_remote_aware_base_ref", lambda *args: "main")
    monkeypatch.setattr(GitUtils, "is_git_repository", lambda *args: True)
    monkeypatch.setattr(GitUtils, "get_current_branch", lambda *args: "feature-test")
    monkeypatch.setattr(GitUtils, "get_default_branch", lambda *args: "main")
    monkeypatch.setattr(GitUtils, "has_uncommitted_changes", lambda *args: False)
    monkeypatch.setattr(GitUtils, "has_unpushed_branch_commits", lambda *args: False)
    monkeypatch.setattr(GitUtils, "get_changed_files", lambda *args: ["feature.txt"])

    def existing_pr(working_dir: Path, branch: str) -> dict[str, str]:
        """Return the appropriate repository's current open PR."""
        return {"state": "open", "url": pr_urls[working_dir]}

    monkeypatch.setattr(
        command, "_get_pr_for_branch", (lambda *args: None) if new_pr else existing_pr
    )
    for helper in ("_create_pr_mr", "_create_pr_mr_for_project", "_create_pr_mr_for_conversation"):
        monkeypatch.setattr(command, helper, Mock(side_effect=list(pr_urls.values())))
    confirm = Mock(
        side_effect=lambda prompt, **kwargs: "Create" in prompt or "with PR URL?" in prompt
    )
    monkeypatch.setattr(command.Confirm, "ask", confirm)

    complete_session(session.name, no_issue_update=link_state == "flag")
    monkeypatch.setattr(command, "_get_pr_for_branch", existing_pr)
    complete_session(session.name, no_issue_update=link_state == "flag")

    link_questions = [entry for entry in confirm.call_args_list if "with PR URL?" in entry.args[0]]
    expected_updates = len(pr_urls) if link_state == "absent" else 0
    assert len(link_questions) == expected_updates
    assert write.call_count == expected_updates
    assert len(comments) == initial_comment_count + expected_updates
    if link_state in {"flag", "disabled"}:
        factory.assert_not_called()
        read.assert_not_called()
    else:
        for pr_url in pr_urls.values():
            assert sum(pr_url in comment["body"] for comment in comments) == 1


def _push_feature_branch_to_remote(repo_dir: Path, remote_dir: Path) -> None:
    """Create an origin remote and publish the repository's current branch."""
    subprocess.run(["git", "init", "--bare", str(remote_dir)], capture_output=True, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote_dir)], cwd=repo_dir, capture_output=True, check=True)
    branch = GitUtils.get_current_branch(repo_dir)
    subprocess.run(["git", "push", "-u", "origin", branch], cwd=repo_dir, capture_output=True, check=True)


def _mock_pr_creation_dependencies(monkeypatch) -> None:
    """Keep helper tests focused on branch push decisions."""
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.detect_repo_type", lambda *args, **kwargs: "github")
    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_pr_description", lambda *args, **kwargs: "Test description")
    monkeypatch.setattr("devflow.cli.commands.complete_command._generate_pr_title", lambda *args, **kwargs: "Test title")
    monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_fork_upstream_info", lambda *args, **kwargs: None)
    monkeypatch.setattr("devflow.cli.commands.complete_command._create_github_pr", lambda *args, **kwargs: "https://example.com/pull/1")


def test_multiproject_pr_helper_does_not_repush_up_to_date_branch(
    temp_daf_home, git_repo, tmp_path, monkeypatch
):
    """An already-pushed project branch should not be pushed again for PR creation."""
    _push_feature_branch_to_remote(git_repo, tmp_path / "project-remote.git")
    _mock_pr_creation_dependencies(monkeypatch)

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.create_session(
        name="multiproject-push-check",
        goal="Test project PR push check",
        working_directory="backend-api",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-project-push-check",
        branch="feature-test",
    )
    project = ProjectInfo(
        project_path=str(git_repo),
        branch="feature-test",
        base_branch="main",
        repo_name="backend-api",
    )

    push_calls = []
    original_push = GitUtils.push_branch

    def track_push(*args, **kwargs):
        push_calls.append(args[1])
        return original_push(*args, **kwargs)

    monkeypatch.setattr(GitUtils, "push_branch", track_push)

    result = _create_pr_mr_for_project(session, project, git_repo, session_manager)

    assert result == "https://example.com/pull/1"
    assert push_calls == []


def test_multiconversation_pr_helper_does_not_repush_up_to_date_branch(
    temp_daf_home, git_repo, tmp_path, monkeypatch
):
    """An already-pushed conversation branch should not be pushed for PR creation."""
    _push_feature_branch_to_remote(git_repo, tmp_path / "conversation-remote.git")
    _mock_pr_creation_dependencies(monkeypatch)

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = session_manager.create_session(
        name="multiconversation-push-check",
        goal="Test conversation PR push check",
        working_directory="backend-api",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-conversation-push-check",
        branch="feature-test",
    )

    push_calls = []
    original_push = GitUtils.push_branch

    def track_push(*args, **kwargs):
        push_calls.append(args[1])
        return original_push(*args, **kwargs)

    monkeypatch.setattr(GitUtils, "push_branch", track_push)

    result = _create_pr_mr_for_conversation(
        session,
        session.active_conversation,
        git_repo,
        session_manager,
    )

    assert result == "https://example.com/pull/1"
    assert push_calls == []
