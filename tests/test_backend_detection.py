"""Tests for backend detection utilities."""

import pytest

from devflow.config.models import Config, Session, JiraConfig, RepoConfig
from devflow.utils.backend_detection import (
    detect_backend_from_key,
    get_issue_tracker_backend,
    validate_issue_key_format,
)


def create_minimal_config(**kwargs):
    """Create a minimal Config with required fields for testing."""
    defaults = {
        "jira": JiraConfig(
            url="https://jira.example.com",
            transitions={}
        ),
        "repos": RepoConfig(
            primary_directory=".",
            repositories=[]
        )
    }
    defaults.update(kwargs)
    return Config(**defaults)


class TestDetectBackendFromKey:
    """Tests for detect_backend_from_key function."""

    def test_jira_standard_format(self):
        """Test JIRA issue keys with standard PROJECT-NUMBER format."""
        assert detect_backend_from_key("AAP-12345") == "jira"
        assert detect_backend_from_key("PROJ-999") == "jira"
        assert detect_backend_from_key("TEST-1") == "jira"
        assert detect_backend_from_key("A-123") == "jira"

    def test_jira_alphanumeric_project(self):
        """Test JIRA project keys with numbers."""
        assert detect_backend_from_key("PROJ2-123") == "jira"
        assert detect_backend_from_key("TEST123-456") == "jira"

    def test_jira_with_config_validation(self):
        """Test JIRA detection with config project validation."""
        config = create_minimal_config(
            jira=JiraConfig(
                url="https://jira.example.com",
                transitions={},
                project="AAP"
            )
        )

        # Matches configured project
        assert detect_backend_from_key("AAP-12345", config) == "jira"

        # Different project but still JIRA pattern
        assert detect_backend_from_key("PROJ-999", config) == "jira"

    def test_github_hash_format(self):
        """Test GitHub issue keys with hash format."""
        assert detect_backend_from_key("#123") == "github"
        assert detect_backend_from_key("#1") == "github"

    def test_github_repo_format(self):
        """Test GitHub issue keys with repository format."""
        assert detect_backend_from_key("owner/repo#123") == "github"
        assert detect_backend_from_key("myorg/myrepo#456") == "github"
        assert detect_backend_from_key("user-name/repo.name#789") == "github"

    def test_github_plain_number(self):
        """Test GitHub issue keys with plain number."""
        assert detect_backend_from_key("123") == "github"
        assert detect_backend_from_key("1") == "github"

    def test_github_lowercase_with_dash(self):
        """Test that lowercase with dashes is GitHub (not JIRA)."""
        assert detect_backend_from_key("my-feature-123") == "github"
        assert detect_backend_from_key("proj-999") == "github"  # lowercase 'proj'

    def test_empty_issue_key_defaults_to_jira(self):
        """Test that empty issue key defaults to JIRA."""
        assert detect_backend_from_key("") == "jira"
        assert detect_backend_from_key(None) == "jira"

    def test_empty_issue_key_uses_config_backend(self):
        """Test that empty issue key uses config backend if available."""
        config = create_minimal_config(issue_tracker_backend="github")
        assert detect_backend_from_key("", config) == "github"
        assert detect_backend_from_key(None, config) == "github"


class TestGetIssueTrackerBackend:
    """Tests for get_issue_tracker_backend function."""

    def test_tier1_explicit_session_metadata(self):
        """Test Tier 1: Explicit session.issue_tracker takes priority."""
        session = Session(
            name="test",
            issue_tracker="github",
            issue_key="AAP-12345"  # JIRA format, but session says GitHub
        )
        # Session metadata should override pattern detection
        assert get_issue_tracker_backend(session, None) == "github"

    def test_tier2_jira_pattern_detection(self):
        """Test Tier 2: Pattern detection from JIRA issue key."""
        session = Session(
            name="test",
            issue_key="AAP-12345"
        )
        # No explicit backend, should detect from pattern
        assert get_issue_tracker_backend(session, None) == "jira"

    def test_tier2_github_pattern_detection(self):
        """Test Tier 2: Pattern detection from GitHub issue key."""
        session = Session(
            name="test",
            issue_key="#123",
            issue_tracker=None  # Explicitly unset to test pattern detection
        )
        # No explicit backend, should detect from pattern
        assert get_issue_tracker_backend(session, None) == "github"

    def test_tier2_with_config_validation(self):
        """Test Tier 2: Pattern detection with config validation."""
        config = create_minimal_config(
            jira=JiraConfig(
                url="https://jira.example.com",
                transitions={},
                project="AAP"
            )
        )
        session = Session(
            name="test",
            issue_key="AAP-12345",
            issue_tracker=None  # Test pattern detection
        )
        # Should detect JIRA and validate against config
        assert get_issue_tracker_backend(session, config) == "jira"

    def test_tier3_global_config(self):
        """Test Tier 3: Global config when no session metadata or key."""
        config = create_minimal_config(issue_tracker_backend="github")
        session = Session(
            name="test",
            issue_tracker=None  # Explicitly None to test config fallback
        )  # No issue_key

        assert get_issue_tracker_backend(session, config) == "github"

    def test_tier4_default_fallback(self):
        """Test Tier 4: Default to JIRA when nothing else available."""
        session = Session(name="test")  # No metadata
        assert get_issue_tracker_backend(session, None) == "jira"

    def test_priority_order(self):
        """Test that session metadata beats pattern detection beats config."""
        config = create_minimal_config(
            issue_tracker_backend="mock",
            jira=JiraConfig(
                url="https://jira.example.com",
                transitions={},
                project="PROJ"
            )
        )

        # Session metadata (github) beats everything
        session = Session(
            name="test",
            issue_tracker="github",
            issue_key="PROJ-123"  # JIRA pattern
        )
        assert get_issue_tracker_backend(session, config) == "github"

        # Pattern detection (jira) beats config (mock)
        session = Session(
            name="test",
            issue_tracker=None,  # Explicitly None to test pattern detection
            issue_key="PROJ-123"
        )
        assert get_issue_tracker_backend(session, config) == "jira"

        # Config (mock) beats default (jira)
        session = Session(
            name="test",
            issue_tracker=None  # Explicitly None to test config fallback
        )
        assert get_issue_tracker_backend(session, config) == "mock"


class TestValidateIssueKeyFormat:
    """Tests for validate_issue_key_format function."""

    def test_jira_valid_formats(self):
        """Test JIRA valid issue key formats."""
        assert validate_issue_key_format("AAP-12345", "jira") is True
        assert validate_issue_key_format("PROJ-999", "jira") is True
        assert validate_issue_key_format("TEST-1", "jira") is True
        assert validate_issue_key_format("A-123", "jira") is True
        assert validate_issue_key_format("PROJ2-123", "jira") is True

    def test_jira_invalid_formats(self):
        """Test JIRA invalid issue key formats."""
        assert validate_issue_key_format("#123", "jira") is False
        assert validate_issue_key_format("owner/repo#123", "jira") is False
        assert validate_issue_key_format("123", "jira") is False
        assert validate_issue_key_format("proj-123", "jira") is False  # lowercase
        assert validate_issue_key_format("my-feature-123", "jira") is False

    def test_github_valid_formats(self):
        """Test GitHub valid issue key formats."""
        assert validate_issue_key_format("#123", "github") is True
        assert validate_issue_key_format("#1", "github") is True
        assert validate_issue_key_format("owner/repo#123", "github") is True
        assert validate_issue_key_format("myorg/myrepo#456", "github") is True
        assert validate_issue_key_format("123", "github") is True
        assert validate_issue_key_format("1", "github") is True

    def test_github_invalid_formats(self):
        """Test GitHub invalid issue key formats."""
        assert validate_issue_key_format("AAP-12345", "github") is False
        assert validate_issue_key_format("PROJ-999", "github") is False
        # These are edge cases - might want to support them later
        # For now, they don't match the strict patterns
        assert validate_issue_key_format("owner/repo", "github") is False  # no issue number
        assert validate_issue_key_format("#", "github") is False  # no number

    def test_unknown_backend(self):
        """Test validation with unknown backend returns False."""
        assert validate_issue_key_format("AAP-12345", "unknown") is False
        assert validate_issue_key_format("#123", "unknown") is False
