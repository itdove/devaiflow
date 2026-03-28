"""Tests for feature orchestration functionality."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from devflow.config.models import FeatureOrchestration, VerificationResult
from devflow.orchestration.storage import FeatureStorage, FeatureIndex
from devflow.orchestration.parent_discovery import ParentTicketDiscovery


class TestFeatureIndex:
    """Test FeatureIndex operations."""

    def test_add_and_get_feature(self):
        """Test adding and retrieving a feature."""
        index = FeatureIndex()
        feature = FeatureOrchestration(
            name="test-feature",
            branch="feature/test",
            sessions=["session1", "session2"],
        )

        index.add_feature(feature)
        retrieved = index.get_feature("test-feature")

        assert retrieved is not None
        assert retrieved.name == "test-feature"
        assert len(retrieved.sessions) == 2

    def test_get_nonexistent_feature(self):
        """Test getting a feature that doesn't exist."""
        index = FeatureIndex()
        result = index.get_feature("nonexistent")
        assert result is None

    def test_list_features(self):
        """Test listing all features."""
        index = FeatureIndex()

        feature1 = FeatureOrchestration(name="feature1", branch="f1", sessions=["s1"])
        feature2 = FeatureOrchestration(name="feature2", branch="f2", sessions=["s2"])

        index.add_feature(feature1)
        index.add_feature(feature2)

        features = index.list_features()
        assert len(features) == 2
        assert any(f.name == "feature1" for f in features)
        assert any(f.name == "feature2" for f in features)

    def test_remove_feature(self):
        """Test removing a feature."""
        index = FeatureIndex()
        feature = FeatureOrchestration(name="test", branch="b", sessions=["s"])

        index.add_feature(feature)
        assert index.get_feature("test") is not None

        index.remove_feature("test")
        assert index.get_feature("test") is None

    def test_duplicate_feature_raises_error(self):
        """Test that adding duplicate feature raises ValueError."""
        index = FeatureIndex()

        feature = FeatureOrchestration(
            name="my-feature",
            branch="feature/test",
            sessions=["PROJ-101", "PROJ-102"],
        )
        index.add_feature(feature)

        # Try to add same feature again
        duplicate = FeatureOrchestration(
            name="my-feature",
            branch="feature/other",
            sessions=["PROJ-103"],
        )

        with pytest.raises(ValueError, match="already exists"):
            index.add_feature(duplicate)


class TestParentTicketDiscovery:
    """Test parent ticket discovery functionality."""

    def test_detect_backend_type_jira(self):
        """Test detecting JIRA backend from issue key."""
        mock_client = Mock()
        discovery = ParentTicketDiscovery(mock_client)

        assert discovery._detect_backend_type("PROJ-123") == "jira"
        assert discovery._detect_backend_type("ABC-999") == "jira"

    def test_detect_backend_type_github(self):
        """Test detecting GitHub/GitLab backend from issue key."""
        mock_client = Mock()
        discovery = ParentTicketDiscovery(mock_client)

        assert discovery._detect_backend_type("#123") == "github"
        assert discovery._detect_backend_type("owner/repo#456") == "github"

    def test_detect_backend_type_unknown(self):
        """Test unknown backend type."""
        mock_client = Mock()
        discovery = ParentTicketDiscovery(mock_client)

        assert discovery._detect_backend_type("invalid") == "unknown"

    def test_parse_issue_references_github(self):
        """Test parsing GitHub issue references from text."""
        mock_client = Mock()
        discovery = ParentTicketDiscovery(mock_client)

        text = "Related to #123 and owner/repo#456, also GH-789"
        refs = discovery._parse_issue_references(text, "owner/repo#100")

        # Should find all references except parent itself
        assert len(refs) >= 2
        assert "#123" in refs or "owner/repo#123" in refs

    def test_order_by_dependencies_simple(self):
        """Test simple dependency ordering."""
        mock_client = Mock()
        discovery = ParentTicketDiscovery(mock_client)

        # Task 2 is blocked by Task 1
        children = [
            {
                "key": "TASK-2",
                "blocks": [],
                "blocked_by": ["TASK-1"],
            },
            {
                "key": "TASK-1",
                "blocks": ["TASK-2"],
                "blocked_by": [],
            },
        ]

        ordered, warnings = discovery.order_by_dependencies(children)

        # TASK-1 should come before TASK-2
        assert ordered[0]["key"] == "TASK-1"
        assert ordered[1]["key"] == "TASK-2"
        assert len(warnings) == 0

    def test_order_by_dependencies_cycle(self):
        """Test dependency ordering with cycle detection."""
        mock_client = Mock()
        discovery = ParentTicketDiscovery(mock_client)

        # Circular dependency: 1 blocks 2, 2 blocks 1
        children = [
            {
                "key": "TASK-1",
                "blocks": ["TASK-2"],
                "blocked_by": ["TASK-2"],
            },
            {
                "key": "TASK-2",
                "blocks": ["TASK-1"],
                "blocked_by": ["TASK-1"],
            },
        ]

        ordered, warnings = discovery.order_by_dependencies(children)

        # Should still order them and warn about cycle
        assert len(ordered) == 2
        assert len(warnings) > 0
        assert "cycle" in warnings[0].lower()

    def test_filter_children_by_status(self):
        """Test filtering children by status."""
        mock_client = Mock()
        discovery = ParentTicketDiscovery(mock_client)

        children = [
            {"key": "TASK-1", "status": "To Do", "type": "Story"},
            {"key": "TASK-2", "status": "In Progress", "type": "Story"},
            {"key": "TASK-3", "status": "New", "type": "Story"},
        ]

        sync_filters = {
            "status": ["To Do", "New"],
        }

        filtered = discovery._filter_children(children, sync_filters)

        assert len(filtered) == 2
        assert any(c["key"] == "TASK-1" for c in filtered)
        assert any(c["key"] == "TASK-3" for c in filtered)
        assert not any(c["key"] == "TASK-2" for c in filtered)


class TestJiraIssueLinkParsing:
    """Test JIRA issue link parsing for blocking relationships."""

    def test_parse_issue_links_blocks(self):
        """Test parsing outward 'blocks' relationship."""
        from devflow.jira.client import JiraClient

        # Mock issuelinks data
        issuelinks = [
            {
                "type": {"name": "Blocks"},
                "outwardIssue": {"key": "PROJ-102"},
            }
        ]

        client = JiraClient.__new__(JiraClient)  # Create instance without __init__
        blocks, blocked_by = client._parse_issue_links(issuelinks)

        assert "PROJ-102" in blocks
        assert len(blocked_by) == 0

    def test_parse_issue_links_blocked_by(self):
        """Test parsing inward 'blocked by' relationship."""
        from devflow.jira.client import JiraClient

        issuelinks = [
            {
                "type": {"name": "Blocks"},
                "inwardIssue": {"key": "PROJ-100"},
            }
        ]

        client = JiraClient.__new__(JiraClient)
        blocks, blocked_by = client._parse_issue_links(issuelinks)

        assert len(blocks) == 0
        assert "PROJ-100" in blocked_by

    def test_parse_issue_links_non_blocking(self):
        """Test that non-blocking links are ignored."""
        from devflow.jira.client import JiraClient

        issuelinks = [
            {
                "type": {"name": "Relates"},
                "outwardIssue": {"key": "PROJ-103"},
            }
        ]

        client = JiraClient.__new__(JiraClient)
        blocks, blocked_by = client._parse_issue_links(issuelinks)

        assert len(blocks) == 0
        assert len(blocked_by) == 0


class TestFeatureOrchestrationModel:
    """Test FeatureOrchestration Pydantic model."""

    def test_create_feature_minimal(self):
        """Test creating feature with minimal required fields."""
        feature = FeatureOrchestration(
            name="test",
            branch="feature/test",
            sessions=["s1", "s2"],
        )

        assert feature.name == "test"
        assert feature.status == "created"
        assert feature.current_session_index == 0
        assert feature.verification_mode == "auto"

    def test_feature_get_current_session(self):
        """Test getting current session."""
        feature = FeatureOrchestration(
            name="test",
            branch="feature/test",
            sessions=["s1", "s2", "s3"],
            current_session_index=1,
        )

        assert feature.get_current_session() == "s2"

    def test_feature_get_completed_sessions(self):
        """Test getting completed sessions."""
        feature = FeatureOrchestration(
            name="test",
            branch="feature/test",
            sessions=["s1", "s2", "s3"],
            session_statuses={"s1": "completed", "s2": "running", "s3": "pending"},
        )

        completed = feature.get_completed_sessions()
        assert "s1" in completed
        assert "s2" not in completed
        assert "s3" not in completed


class TestVerificationResult:
    """Test VerificationResult model."""

    def test_verification_result_passed(self):
        """Test verification result with passed status."""
        result = VerificationResult(
            session_name="test-session",
            status="passed",
            total_criteria=5,
            verified_criteria=5,
            tests_passed=True,
        )

        assert result.status == "passed"
        assert result.total_criteria == result.verified_criteria

    def test_verification_result_gaps(self):
        """Test verification result with gaps found."""
        result = VerificationResult(
            session_name="test-session",
            status="gaps_found",
            total_criteria=5,
            verified_criteria=3,
            unverified_criteria=["Criterion 1", "Criterion 2"],
        )

        assert result.status == "gaps_found"
        assert len(result.unverified_criteria) == 2
        assert result.verified_criteria < result.total_criteria


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
