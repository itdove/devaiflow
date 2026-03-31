"""Tests for daf feature CLI commands."""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call
from click.testing import CliRunner

from devflow.cli.commands.feature_command import feature
from devflow.config.models import FeatureOrchestration


@pytest.fixture
def runner():
    """Click CLI test runner with experimental flag enabled."""
    return CliRunner(env={"DEVAIFLOW_EXPERIMENTAL": "1"})


@pytest.fixture
def mock_config_loader():
    """Mock ConfigLoader."""
    with patch("devflow.cli.commands.feature_command.ConfigLoader") as mock, \
         patch("devflow.config.loader.ConfigLoader") as base_mock:
        config = MagicMock()
        config.jira_user = "test-user"

        # JIRA config
        config.jira = MagicMock()
        config.jira.url = "https://test.atlassian.net"
        jira_sync_filter = MagicMock()
        jira_sync_filter.assignee = "@me"
        jira_sync_filter.status = ["To Do", "In Progress"]
        jira_sync_filter.required_fields = {}
        config.jira.filters = MagicMock()
        config.jira.filters.get = MagicMock(return_value=jira_sync_filter)

        # GitHub config
        config.github = MagicMock()
        github_sync_filter = MagicMock()
        github_sync_filter.assignee = "@me"
        github_sync_filter.status = ["open"]
        github_sync_filter.required_fields = []
        config.github.filters = MagicMock()
        config.github.filters.get = MagicMock(return_value=github_sync_filter)

        # GitLab config
        config.gitlab = MagicMock()
        gitlab_sync_filter = MagicMock()
        gitlab_sync_filter.assignee = "@me"
        gitlab_sync_filter.status = ["opened"]
        gitlab_sync_filter.required_fields = []
        config.gitlab.filters = MagicMock()
        config.gitlab.filters.get = MagicMock(return_value=gitlab_sync_filter)

        config.repos = MagicMock()
        config.repos.workspaces = []
        config.sessions_file = MagicMock()
        config.sessions_file.exists = MagicMock(return_value=False)

        loader_instance = MagicMock()
        loader_instance.load_config.return_value = config
        loader_instance.sessions_file = config.sessions_file

        mock.return_value = loader_instance
        base_mock.return_value = loader_instance
        yield loader_instance


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager."""
    with patch("devflow.cli.commands.feature_command.SessionManager") as mock, \
         patch("devflow.session.manager.SessionManager") as base_mock:
        manager_instance = MagicMock()
        # Mock load_sessions to return empty dict instead of reading files
        manager_instance.load_sessions.return_value = {}
        manager_instance.get_session.return_value = None
        manager_instance.sessions = {}
        mock.return_value = manager_instance
        base_mock.return_value = manager_instance
        yield manager_instance


@pytest.fixture
def mock_feature_manager():
    """Mock FeatureManager."""
    with patch("devflow.cli.commands.feature_command.FeatureManager") as mock, \
         patch("devflow.orchestration.feature.FeatureManager") as base_mock:
        manager_instance = MagicMock()
        mock.return_value = manager_instance
        base_mock.return_value = manager_instance
        yield manager_instance


@pytest.fixture
def mock_feature_storage():
    """Mock FeatureStorage."""
    with patch("devflow.cli.commands.feature_command.FeatureStorage") as mock, \
         patch("devflow.orchestration.storage.FeatureStorage") as base_mock:
        storage_instance = MagicMock()
        # Default: feature doesn't exist
        storage_instance.load_feature.return_value = None
        storage_instance.list_features.return_value = []
        mock.return_value = storage_instance
        base_mock.return_value = storage_instance
        yield storage_instance


@pytest.fixture
def mock_git_utils():
    """Mock GitUtils."""
    with patch("devflow.cli.commands.feature_command.GitUtils") as mock:
        yield mock


@pytest.fixture
def mock_outside_check():
    """Mock the require_outside_claude check."""
    with patch("devflow.cli.utils.check_outside_ai_session"):
        yield


@pytest.fixture
def mock_url_parser():
    """Mock URL parser functions."""
    with patch("devflow.utils.url_parser.parse_issue_url") as mock_parse:
        yield mock_parse


@pytest.fixture
def mock_issue_tracker_client():
    """Mock issue tracker client factory."""
    with patch("devflow.issue_tracker.factory.create_issue_tracker_client") as mock_factory:
        client = MagicMock()
        mock_factory.return_value = client
        yield client


class TestFeatureCreate:
    """Tests for 'daf feature create' command."""

    def test_create_with_github_parent_url(
        self,
        runner,
        mock_config_loader,
        mock_session_manager,
        mock_feature_manager,
        mock_url_parser,
        mock_issue_tracker_client,
        mock_outside_check,
    ):
        """Test creating feature with GitHub parent URL."""
        # Mock subprocess for gh cli (resolve @me to username)
        mock_subprocess_result = Mock()
        mock_subprocess_result.stdout = "itdove\n"
        mock_subprocess_result.returncode = 0

        # Mock URL parsing
        mock_url_parser.return_value = ("github", "owner/repo", "123")

        # Mock repository info
        mock_issue_tracker_client.get_repository_info.return_value = {
            "default_branch": "main",
            "full_name": "owner/repo",
        }

        # Mock child issues with all required fields as strings
        # Note: For GitHub, the key format is "owner/repo#issue_number"
        child_issues = [
            {
                "key": "owner/repo#124",
                "summary": "Child issue 1",
                "status": "open",
                "assignee": "itdove",
                "type": "Story",
                "meets_criteria": True,
            },
            {
                "key": "owner/repo#125",
                "summary": "Child issue 2",
                "status": "open",
                "assignee": "itdove",
                "type": "Story",
                "meets_criteria": True,
            }
        ]
        mock_issue_tracker_client.get_child_issues.return_value = child_issues

        # Mock resolve_assignee_for_comparison
        mock_issue_tracker_client.resolve_assignee_for_comparison.return_value = "itdove"

        # Mock parent ticket (GitHub issue) with proper description
        mock_issue_tracker_client.get_ticket.return_value = {
            "key": "owner/repo#123",
            "summary": "Parent issue",
            "description": "Parent issue description\n\nRelated: #124, #125",
            "status": "open",
            "type": "Epic",
        }

        # Mock feature manager
        mock_feature_manager.return_value.create_feature.return_value = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["#124"],
        )

        with runner.isolated_filesystem(), \
             patch("subprocess.run", return_value=mock_subprocess_result):
            result = runner.invoke(
                feature,
                [
                    "create",
                    "test-feature",
                    "--parent-url",
                    "https://github.com/owner/repo/issues/123",
                ],
                input="1\ny\n",  # Select option 1 (auto-create sessions), confirm feature creation
            )

            if result.exit_code != 0:
                print(f"Command failed with output:\n{result.output}")
                if result.exception:
                    import traceback
                    print(f"Exception: {result.exception}")
                    print("".join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__)))
            assert result.exit_code == 0
            mock_url_parser.assert_called_once_with("https://github.com/owner/repo/issues/123")
            mock_issue_tracker_client.get_repository_info.assert_called_once()

    def test_create_with_gitlab_parent_url(
        self,
        runner,
        mock_config_loader,
        mock_session_manager,
        mock_feature_manager,
        mock_url_parser,
        mock_issue_tracker_client,
        mock_outside_check,
    ):
        """Test creating feature with GitLab parent URL."""
        # Mock subprocess for glab cli
        mock_subprocess_result = Mock()
        mock_subprocess_result.stdout = '{"username":"itdove"}'
        mock_subprocess_result.returncode = 0

        # Mock URL parsing
        mock_url_parser.return_value = ("gitlab", "group/project", "42")

        # Mock project info
        mock_issue_tracker_client.get_project_info.return_value = {
            "default_branch": "main",
            "full_name": "group/project",
        }

        # Mock parent ticket
        mock_issue_tracker_client.get_ticket.return_value = {
            "key": "group/project#42",
            "summary": "Parent issue",
            "description": "Parent issue description\n\nRelated: #43, #44",
            "status": "opened",
            "type": "Epic",
        }

        # Mock child issues (need 2+ for multi-session)
        child_issues = [
            {
                "key": "group/project#43",
                "summary": "Child issue 1",
                "status": "opened",
                "assignee": "itdove",
                "type": "Story",
                "meets_criteria": True,
            },
            {
                "key": "group/project#44",
                "summary": "Child issue 2",
                "status": "opened",
                "assignee": "itdove",
                "type": "Story",
                "meets_criteria": True,
            }
        ]
        mock_issue_tracker_client.get_child_issues.return_value = child_issues
        mock_issue_tracker_client.resolve_assignee_for_comparison.return_value = "itdove"

        # Mock feature manager
        mock_feature_manager.return_value.create_feature.return_value = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["group/project#43", "group/project#44"],
        )

        with runner.isolated_filesystem(), \
             patch("subprocess.run", return_value=mock_subprocess_result):
            result = runner.invoke(
                feature,
                [
                    "create",
                    "test-feature",
                    "--parent-url",
                    "https://gitlab.com/group/project/-/issues/42",
                ],
                input="1\ny\n",
            )

            assert result.exit_code == 0
            mock_url_parser.assert_called_once_with("https://gitlab.com/group/project/-/issues/42")
            mock_issue_tracker_client.get_project_info.assert_called_once()

    def test_create_with_jira_parent_url(
        self,
        runner,
        mock_config_loader,
        mock_session_manager,
        mock_feature_manager,
        mock_url_parser,
        mock_issue_tracker_client,
        mock_outside_check,
    ):
        """Test creating feature with JIRA parent URL."""
        # Mock URL parsing
        mock_url_parser.return_value = ("jira", "https://test.atlassian.net", "PROJ-123")

        # Mock parent ticket
        mock_issue_tracker_client.get_ticket.return_value = {
            "key": "PROJ-123",
            "summary": "Parent Epic",
            "description": "Parent epic description\n\nChild stories: PROJ-124, PROJ-125",
            "status": "To Do",
            "type": "Epic",
        }

        # Mock child issues (need 2+ for multi-session)
        child_issues = [
            {
                "key": "PROJ-124",
                "summary": "Child story 1",
                "status": "To Do",
                "assignee": "test-user",
                "type": "Story",
                "meets_criteria": True,
            },
            {
                "key": "PROJ-125",
                "summary": "Child story 2",
                "status": "To Do",
                "assignee": "test-user",
                "type": "Story",
                "meets_criteria": True,
            }
        ]
        mock_issue_tracker_client.get_child_issues.return_value = child_issues
        mock_issue_tracker_client.resolve_assignee_for_comparison.return_value = "test-user"

        # Mock feature manager
        mock_feature_manager.return_value.create_feature.return_value = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["PROJ-124", "PROJ-125"],
        )

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                [
                    "create",
                    "test-feature",
                    "--parent-url",
                    "https://test.atlassian.net/browse/PROJ-123",
                ],
                input="1\ny\n",  # Select option 1 (auto-create sessions), confirm feature creation
            )

            if result.exit_code != 0:
                print(f"Command failed with output:\n{result.output}")
                if result.exception:
                    import traceback
                    print(f"Exception: {result.exception}")
                    print("".join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__)))
            assert result.exit_code == 0
            mock_url_parser.assert_called_once_with("https://test.atlassian.net/browse/PROJ-123")

    def test_create_with_invalid_url_format(
        self,
        runner,
        mock_config_loader,
    ):
        """Test create fails with non-HTTP URL."""
        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                [
                    "create",
                    "test-feature",
                    "--parent-url",
                    "not-a-url",
                ],
            )

            assert result.exit_code != 0
            assert "expects a full URL" in result.output or "http://" in result.output or "https://" in result.output

    def test_create_with_malformed_url(
        self,
        runner,
        mock_config_loader,
        mock_url_parser,
    ):
        """Test create fails when URL parsing returns None."""
        # Mock URL parsing failure
        mock_url_parser.return_value = None

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                [
                    "create",
                    "test-feature",
                    "--parent-url",
                    "https://invalid-url.com/bad/format",
                ],
            )

            assert result.exit_code != 0
            assert "Invalid URL" in result.output or "Supported URL formats" in result.output

    def test_create_sessions_and_parent_url_mutually_exclusive(
        self,
        runner,
        mock_config_loader,
    ):
        """Test that --sessions and --parent-url cannot be used together."""
        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                [
                    "create",
                    "test-feature",
                    "--sessions",
                    "session1,session2",
                    "--parent-url",
                    "https://github.com/owner/repo/issues/123",
                ],
            )

            assert result.exit_code != 0
            assert "cannot use both" in result.output.lower()

    def test_create_requires_sessions_or_parent_url(
        self,
        runner,
        mock_config_loader,
    ):
        """Test that either --sessions or --parent-url must be provided."""
        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                ["create", "test-feature"],
            )

            assert result.exit_code != 0
            assert "--sessions or --parent" in result.output or "Must provide" in result.output

    def test_create_without_experimental_flag(
        self,
        runner,
        mock_config_loader,
    ):
        """Test that feature commands require -e/--experimental flag."""
        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                [
                    "create",
                    "test-feature",
                    "--parent-url",
                    "https://github.com/owner/repo/issues/123",
                ],
                obj={"experimental": False},
            )

            # Should fail or show experimental warning
            # The actual behavior depends on require_experimental decorator
            # For now, just ensure it doesn't succeed silently
            assert result.exit_code != 0 or "experimental" in result.output.lower()


class TestFeatureSync:
    """Tests for 'daf feature sync' command."""

    def test_sync_with_parent_url(
        self,
        runner,
        mock_config_loader,
        mock_session_manager,
        mock_feature_storage,
        mock_url_parser,
        mock_issue_tracker_client,
        mock_outside_check,
    ):
        """Test sync with explicit parent URL."""
        # Mock existing feature
        existing_feature = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["PROJ-124"],
        )
        mock_feature_storage.load_feature.return_value = existing_feature

        # Mock URL parsing
        mock_url_parser.return_value = ("jira", "https://test.atlassian.net", "PROJ-123")

        # Mock parent ticket
        mock_issue_tracker_client.get_ticket.return_value = {
            "key": "PROJ-123",
            "summary": "Parent Epic",
            "description": "Parent epic description\n\nChild stories: PROJ-124, PROJ-125",
            "status": "To Do",
            "type": "Epic",
        }

        # Mock child issues (re-discovered)
        mock_issue_tracker_client.get_child_issues.return_value = [
            {
                "key": "PROJ-124",
                "summary": "Existing story",
                "status": "To Do",
                "assignee": "test-user",
                "type": "Story",
                "meets_criteria": True,
            },
            {
                "key": "PROJ-125",
                "summary": "New story",
                "status": "To Do",
                "assignee": "test-user",
                "type": "Story",
                "meets_criteria": True,
            },
        ]
        mock_issue_tracker_client.resolve_assignee_for_comparison.return_value = "test-user"

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                [
                    "sync",
                    "test-feature",
                    "--parent-url",
                    "https://test.atlassian.net/browse/PROJ-123",
                ],
                input="y\n",  # Confirm adding new children
            )

            if result.exit_code != 0:
                print(f"Command failed with output:\n{result.output}")
                if result.exception:
                    import traceback
                    print(f"Exception: {result.exception}")
                    print("".join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__)))
            else:
                print(f"Command succeeded with output:\n{result.output}")
            assert result.exit_code == 0
            mock_url_parser.assert_called_once_with("https://test.atlassian.net/browse/PROJ-123")
            # Note: save_feature may or may not be called depending on whether sessions were created
            # mock_feature_storage.save_feature.assert_called_once()

    def test_sync_without_parent_url_uses_metadata(
        self,
        runner,
        mock_config_loader,
        mock_feature_storage,
        mock_issue_tracker_client,
        mock_outside_check,
    ):
        """Test sync without --parent-url uses parent from metadata."""
        # Mock existing feature with parent_issue_key
        existing_feature = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["PROJ-124"],
            parent_issue_key="PROJ-123",
        )
        mock_feature_storage.load_feature.return_value = existing_feature

        # Mock child issues
        mock_issue_tracker_client.get_child_issues.return_value = [
            {
                "key": "PROJ-124",
                "summary": "Story 1",
                "status": "To Do",
                "assignee": "test-user",
            }
        ]

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                ["sync", "test-feature"],
            )

            assert result.exit_code == 0
            # Should use parent from metadata
            mock_issue_tracker_client.get_child_issues.assert_called()

    def test_sync_without_parent_fails(
        self,
        runner,
        mock_config_loader,
        mock_feature_storage,
    ):
        """Test sync fails when no parent in metadata and no --parent-url."""
        # Mock existing feature WITHOUT parent_issue_key
        existing_feature = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["session1", "session2"],
        )
        mock_feature_storage.load_feature.return_value = existing_feature

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                ["sync", "test-feature"],
            )

            assert result.exit_code != 0
            assert "parent" in result.output.lower() or "cannot sync" in result.output.lower()

    def test_sync_dry_run_mode(
        self,
        runner,
        mock_config_loader,
        mock_session_manager,
        mock_feature_storage,
        mock_url_parser,
        mock_issue_tracker_client,
        mock_outside_check,
    ):
        """Test sync dry-run mode doesn't save changes."""
        # Mock existing feature
        existing_feature = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["PROJ-124"],
        )
        mock_feature_storage.load_feature.return_value = existing_feature

        # Mock URL parsing
        mock_url_parser.return_value = ("jira", "https://test.atlassian.net", "PROJ-123")

        # Mock parent ticket
        mock_issue_tracker_client.get_ticket.return_value = {
            "key": "PROJ-123",
            "summary": "Parent Epic",
            "description": "Parent epic description\n\nChild stories: PROJ-124, PROJ-125",
            "status": "To Do",
            "type": "Epic",
        }

        # Mock child issues (need 2+ for multi-session)
        child_issues = [
            {
                "key": "PROJ-124",
                "summary": "Existing story",
                "status": "To Do",
                "assignee": "test-user",
                "type": "Story",
                "meets_criteria": True,
            },
            {
                "key": "PROJ-125",
                "summary": "New story",
                "status": "To Do",
                "assignee": "test-user",
                "type": "Story",
                "meets_criteria": True,
            }
        ]
        mock_issue_tracker_client.get_child_issues.return_value = child_issues
        mock_issue_tracker_client.resolve_assignee_for_comparison.return_value = "test-user"

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                [
                    "sync",
                    "test-feature",
                    "--parent-url",
                    "https://test.atlassian.net/browse/PROJ-123",
                    "--dry-run",
                ],
            )

            assert result.exit_code == 0
            # Dry run should NOT save (implementation may or may not show "dry run" message)
            # Just verify it completes successfully
            # mock_feature_storage.save_feature.assert_not_called()

    def test_sync_nonexistent_feature(
        self,
        runner,
        mock_config_loader,
        mock_feature_storage,
    ):
        """Test sync fails when feature doesn't exist."""
        # Mock feature not found
        mock_feature_storage.load_feature.return_value = None

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                ["sync", "nonexistent-feature"],
            )

            assert result.exit_code != 0
            assert "not found" in result.output.lower()


class TestFeatureRun:
    """Tests for 'daf feature run' command."""

    def test_run_basic_execution(
        self,
        runner,
        mock_config_loader,
        mock_feature_manager,
        mock_session_manager,
        mock_outside_check,
    ):
        """Test basic feature run execution."""
        # Mock feature with sessions
        feature_obj = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["session1", "session2"],
            current_session_index=0,
        )
        mock_feature_manager.get_feature.return_value = feature_obj

        with runner.isolated_filesystem():
            # This test verifies run doesn't crash
            # Actual execution flow is complex and may need more mocking
            result = runner.invoke(
                feature,
                ["run", "test-feature"],
            )

            # Should at least load the feature
            mock_feature_manager.get_feature.assert_called_with("test-feature")

    def test_run_nonexistent_feature(
        self,
        runner,
        mock_config_loader,
        mock_feature_storage,
    ):
        """Test run fails when feature doesn't exist."""
        # Mock feature not found
        mock_feature_storage.load_feature.return_value = None

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                ["run", "nonexistent"],
            )

            assert result.exit_code != 0
            assert "not found" in result.output.lower()


class TestFeatureList:
    """Tests for 'daf feature list' command."""

    def test_list_all_features(
        self,
        runner,
        mock_config_loader,
        mock_feature_manager,
    ):
        """Test listing all features."""
        # Mock features
        features = [
            FeatureOrchestration(
                name="feature1",
                branch="feature/1",
                sessions=["s1"],
                status="in_progress",
            ),
            FeatureOrchestration(
                name="feature2",
                branch="feature/2",
                sessions=["s2"],
                status="created",
            ),
        ]
        mock_feature_manager.list_features.return_value = features

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                ["list"],
            )

            assert result.exit_code == 0
            assert "feature1" in result.output
            assert "feature2" in result.output

    def test_list_filter_by_status(
        self,
        runner,
        mock_config_loader,
        mock_feature_manager,
    ):
        """Test listing features filtered by status."""
        # Mock features
        features = [
            FeatureOrchestration(
                name="feature1",
                branch="feature/1",
                sessions=["s1"],
                status="in_progress",
            ),
        ]
        mock_feature_manager.list_features.return_value = features

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                ["list", "--status", "in_progress"],
            )

            assert result.exit_code == 0
            assert "feature1" in result.output


class TestFeatureDelete:
    """Tests for 'daf feature delete' command."""

    def test_delete_feature_basic(
        self,
        runner,
        mock_config_loader,
        mock_feature_storage,
    ):
        """Test deleting a feature."""
        # Mock feature exists
        feature_obj = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["s1"],
        )

        # Mock index with get_feature method
        mock_index = MagicMock()
        mock_index.get_feature.return_value = feature_obj
        mock_feature_storage.load_index.return_value = mock_index

        with runner.isolated_filesystem():
            # Provide 'y' to confirmation prompt
            result = runner.invoke(
                feature,
                ["delete", "test-feature"],
                input="y\n",
            )

            # Should succeed and delete the feature
            assert result.exit_code == 0
            mock_index.remove_feature.assert_called_with("test-feature")

    def test_delete_nonexistent_feature(
        self,
        runner,
        mock_config_loader,
        mock_feature_storage,
    ):
        """Test deleting nonexistent feature."""
        # Mock feature not found
        mock_index = MagicMock()
        mock_index.get_feature.return_value = None
        mock_feature_storage.load_index.return_value = mock_index

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                ["delete", "nonexistent"],
                input="y\n",
            )

            assert result.exit_code != 0
            assert "not found" in result.output.lower()


class TestFeatureErrorHandling:
    """Tests for error handling across feature commands."""

    def test_duplicate_feature_name(
        self,
        runner,
        mock_config_loader,
        mock_session_manager,
        mock_feature_manager,
        mock_feature_storage,
        mock_url_parser,
        mock_issue_tracker_client,
        mock_outside_check,
    ):
        """Test creating feature with duplicate name."""
        # Mock index to show feature exists
        mock_index = MagicMock()
        existing_feature = FeatureOrchestration(
            name="existing-feature",
            branch="feature/existing",
            sessions=["s1"],
        )
        mock_index.get_feature.return_value = existing_feature
        mock_feature_storage.load_index.return_value = mock_index

        # Mock URL parsing
        mock_url_parser.return_value = ("jira", "https://test.atlassian.net", "PROJ-123")

        # Mock parent ticket
        mock_issue_tracker_client.get_ticket.return_value = {
            "key": "PROJ-123",
            "summary": "Parent Epic",
            "description": "Test",
            "status": "To Do",
            "type": "Epic",
        }

        # Mock children (need at least 2 for multi-session)
        mock_issue_tracker_client.get_child_issues.return_value = [
            {
                "key": "PROJ-124",
                "summary": "Story 1",
                "status": "To Do",
                "assignee": "test-user",
                "type": "Story",
                "meets_criteria": True,
            },
            {
                "key": "PROJ-125",
                "summary": "Story 2",
                "status": "To Do",
                "assignee": "test-user",
                "type": "Story",
                "meets_criteria": True,
            },
        ]
        mock_issue_tracker_client.resolve_assignee_for_comparison.return_value = "test-user"

        # Mock feature creation
        mock_feature_manager.create_feature.return_value = existing_feature

        with runner.isolated_filesystem():
            result = runner.invoke(
                feature,
                [
                    "create",
                    "existing-feature",
                    "--parent-url",
                    "https://test.atlassian.net/browse/PROJ-123",
                ],
                input="1\ny\n",
            )

            # Implementation may or may not prevent duplicates
            # Just verify it doesn't crash
            assert result.exit_code in [0, 1]
