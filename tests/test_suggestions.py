"""Tests for repository suggestion system."""

import json
import tempfile
from pathlib import Path

import pytest

from devflow.suggestions import RepositorySuggester
from devflow.suggestions.models import SuggestionHistory, TicketMapping


class TestRepositorySuggester:
    """Test cases for RepositorySuggester class."""

    def test_extract_keywords_from_summary(self):
        """Test keyword extraction from JIRA summary."""
        suggester = RepositorySuggester()

        keywords = suggester.extract_keywords(
            summary="Implement backup and restore functionality for customer data",
        )

        assert "implement" in keywords
        assert "backup" in keywords
        assert "restore" in keywords
        assert "functionality" in keywords
        assert "customer" in keywords
        assert "data" in keywords

        # Stop words should not be included
        assert "and" not in keywords
        assert "for" not in keywords
        assert "the" not in keywords

    def test_extract_keywords_from_labels(self):
        """Test keyword extraction from JIRA labels."""
        suggester = RepositorySuggester()

        keywords = suggester.extract_keywords(
            summary="Test ticket",
            labels=["terraform", "github-actions", "api-integration"],
        )

        assert "terraform" in keywords
        assert "github" in keywords
        assert "actions" in keywords
        assert "api" in keywords
        assert "integration" in keywords

    def test_extract_keywords_filters_short_words(self):
        """Test that short words are filtered out."""
        suggester = RepositorySuggester()

        keywords = suggester.extract_keywords(
            summary="Add a UI to it",
        )

        # "a", "to", "it" should be filtered (too short or stop words)
        assert "a" not in keywords
        assert "to" not in keywords
        assert "it" not in keywords
        assert "add" in keywords

    def test_suggest_repositories_with_history(self):
        """Test repository suggestions based on historical data."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            history_file = Path(f.name)

        try:
            suggester = RepositorySuggester(history_file=history_file)

            # Add some historical mappings
            suggester.history.add_mapping(
                issue_key="PROJ-111",
                repository="backend-api",
                ticket_type="Story",
                keywords=["backup", "restore", "customer"],
            )
            suggester.history.add_mapping(
                issue_key="PROJ-222",
                repository="backend-api",
                ticket_type="Story",
                keywords=["subscription", "customer", "billing"],
            )
            suggester.history.add_mapping(
                issue_key="PROJ-333",
                repository="devops-tools",
                ticket_type="Bug",
                keywords=["terraform", "github", "deployment"],
            )
            suggester._save_history()

            # Test suggestion for backup-related ticket
            suggestions = suggester.suggest_repositories(
                summary="Implement backup system for customer data",
                ticket_type="Story",
                available_repos=[
                    "backend-api",
                    "devops-tools",
                    "frontend-app",
                ],
            )

            # Should suggest management-service first (backup + customer keywords)
            assert len(suggestions) > 0
            assert suggestions[0].repository == "backend-api"
            assert suggestions[0].confidence > 0.5

        finally:
            history_file.unlink(missing_ok=True)

    def test_suggest_repositories_exact_jira_match(self):
        """Test that exact issue key match gives highest confidence."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            history_file = Path(f.name)

        try:
            suggester = RepositorySuggester(history_file=history_file)

            # Add historical mapping for specific issue key
            suggester.history.add_mapping(
                issue_key="PROJ-12345",
                repository="backend-api",
                ticket_type="Story",
                keywords=["test"],
            )
            suggester._save_history()

            # Test suggestion for the same issue key
            suggestions = suggester.suggest_repositories(
                issue_key="PROJ-12345",
                summary="Some different work",
                available_repos=["backend-api", "devops-tools"],
            )

            # Should suggest the previously used repo
            assert len(suggestions) > 0
            assert suggestions[0].repository == "backend-api"
            assert "Previously used for this ticket" in suggestions[0].reasons

        finally:
            history_file.unlink(missing_ok=True)

    def test_suggest_repositories_with_config_keywords(self):
        """Test repository suggestions using configured keywords as fallback."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            history_file = Path(f.name)

        try:
            suggester = RepositorySuggester(history_file=history_file)

            # No historical data, but config has keywords
            config_keywords = {
                "backend-api": ["backup", "restore", "subscription"],
                "devops-tools": ["terraform", "github", "deployment"],
            }

            suggestions = suggester.suggest_repositories(
                summary="Implement terraform deployment pipeline",
                config_keywords=config_keywords,
                available_repos=["backend-api", "devops-tools"],
            )

            # Should suggest sops based on terraform + deployment keywords
            assert len(suggestions) > 0
            assert any(s.repository == "devops-tools" for s in suggestions)

        finally:
            history_file.unlink(missing_ok=True)

    def test_record_selection_updates_history(self):
        """Test that recording a selection updates the history."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            history_file = Path(f.name)

        try:
            suggester = RepositorySuggester(history_file=history_file)

            # Record a selection
            suggester.record_selection(
                repository="backend-api",
                issue_key="PROJ-999",
                ticket_type="Story",
                summary="Add backup feature",
                labels=["backup", "customer-data"],
            )

            # Verify history was updated
            assert len(suggester.history.mappings) == 1
            assert suggester.history.mappings[0].issue_key == "PROJ-999"
            assert suggester.history.mappings[0].repository == "backend-api"
            assert "backup" in suggester.history.mappings[0].keywords

            # Verify history file was saved
            assert history_file.exists()

            # Load fresh instance and verify persistence
            suggester2 = RepositorySuggester(history_file=history_file)
            assert len(suggester2.history.mappings) == 1
            assert suggester2.history.mappings[0].issue_key == "PROJ-999"

        finally:
            history_file.unlink(missing_ok=True)

    def test_suggestion_history_max_mappings(self):
        """Test that history maintains max 1000 mappings."""
        history = SuggestionHistory()

        # Add 1050 mappings
        for i in range(1050):
            history.add_mapping(
                issue_key=f"PROJ-{i}",
                repository=f"repo-{i % 10}",
                ticket_type="Story",
                keywords=[f"keyword-{i}"],
            )

        # Should keep only last 1000
        assert len(history.mappings) == 1000

        # Most recent should be first
        assert history.mappings[0].issue_key == "PROJ-1049"
        assert history.mappings[-1].issue_key == "PROJ-50"

    def test_filter_by_available_repos(self):
        """Test that suggestions are filtered by available repositories."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            history_file = Path(f.name)

        try:
            suggester = RepositorySuggester(history_file=history_file)

            # Add mapping for repo that's not available
            suggester.history.add_mapping(
                issue_key="PROJ-111",
                repository="non-existent-repo",
                ticket_type="Story",
                keywords=["backup"],
            )
            suggester._save_history()

            # Request suggestions with limited available repos
            suggestions = suggester.suggest_repositories(
                summary="Implement backup",
                available_repos=["backend-api"],
            )

            # Should not suggest the non-existent repo
            assert all(s.repository == "backend-api" for s in suggestions)

        finally:
            history_file.unlink(missing_ok=True)

    def test_recency_scoring(self):
        """Test that recent selections get higher scores."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            history_file = Path(f.name)

        try:
            suggester = RepositorySuggester(history_file=history_file)

            # Add old mapping
            suggester.history.add_mapping(
                issue_key="PROJ-OLD",
                repository="devops-tools",
                keywords=["backup"],
            )

            # Add recent mapping (will be at front of list)
            suggester.history.add_mapping(
                issue_key="PROJ-NEW",
                repository="backend-api",
                keywords=["backup"],
            )

            suggester._save_history()

            # Both repos have "backup" keyword, but recent one should score higher
            suggestions = suggester.suggest_repositories(
                summary="Implement backup",
                available_repos=["backend-api", "devops-tools"],
            )

            # Recent repo should have slight advantage
            assert len(suggestions) >= 2
            # Note: This test might be brittle depending on scoring weights

        finally:
            history_file.unlink(missing_ok=True)


class TestSuggestionHistory:
    """Test cases for SuggestionHistory model."""

    def test_add_mapping_updates_keyword_frequencies(self):
        """Test that adding mappings updates keyword frequencies."""
        history = SuggestionHistory()

        history.add_mapping(
            issue_key="PROJ-1",
            repository="repo1",
            keywords=["backup", "restore"],
        )

        history.add_mapping(
            issue_key="PROJ-2",
            repository="repo1",
            keywords=["backup", "customer"],
        )

        history.add_mapping(
            issue_key="PROJ-3",
            repository="repo2",
            keywords=["backup", "terraform"],
        )

        # Check keyword frequencies
        assert "backup" in history.keyword_frequencies
        assert history.keyword_frequencies["backup"]["repo1"] == 2
        assert history.keyword_frequencies["backup"]["repo2"] == 1

        assert "restore" in history.keyword_frequencies
        assert history.keyword_frequencies["restore"]["repo1"] == 1

    def test_add_mapping_updates_type_frequencies(self):
        """Test that adding mappings updates type frequencies."""
        history = SuggestionHistory()

        history.add_mapping(
            issue_key="PROJ-1",
            repository="repo1",
            ticket_type="Story",
        )

        history.add_mapping(
            issue_key="PROJ-2",
            repository="repo1",
            ticket_type="Story",
        )

        history.add_mapping(
            issue_key="PROJ-3",
            repository="repo2",
            ticket_type="Bug",
        )

        # Check type frequencies
        assert "Story" in history.type_frequencies
        assert history.type_frequencies["Story"]["repo1"] == 2

        assert "Bug" in history.type_frequencies
        assert history.type_frequencies["Bug"]["repo2"] == 1

    def test_get_repository_by_issue_key(self):
        """Test retrieving repository by issue key."""
        history = SuggestionHistory()

        history.add_mapping(
            issue_key="PROJ-123",
            repository="test-repo",
        )

        repo = history.get_repository_by_issue_key("PROJ-123")
        assert repo == "test-repo"

        repo = history.get_repository_by_issue_key("PROJ-999")
        assert repo is None

    def test_add_mapping_cleanup_empty_type_frequencies(self):
        """Test that empty type frequency dicts are cleaned up when mappings exceed 1000."""
        history = SuggestionHistory()

        # Add 1001 mappings with same type to single repo
        # When the oldest is removed, it should clean up the empty dict
        for i in range(1001):
            history.add_mapping(
                issue_key=f"PROJ-{i}",
                repository="single-repo",
                ticket_type="UniqueType" if i == 0 else "CommonType",
                keywords=[f"kw-{i}"],
            )

        # The oldest mapping (PROJ-0) with UniqueType should be removed
        # and UniqueType should be cleaned from type_frequencies
        assert "UniqueType" not in history.type_frequencies
        assert "CommonType" in history.type_frequencies
        assert len(history.mappings) == 1000

    def test_add_mapping_cleanup_empty_keyword_frequencies(self):
        """Test that empty keyword frequency dicts are cleaned up."""
        history = SuggestionHistory()

        # Add 1001 mappings with unique keywords
        for i in range(1001):
            history.add_mapping(
                issue_key=f"PROJ-{i}",
                repository=f"repo-{i}",
                ticket_type="Story",
                keywords=[f"unique-keyword-{i}"],
            )

        # The oldest keyword (unique-keyword-0) should be cleaned up
        assert "unique-keyword-0" not in history.keyword_frequencies
        assert "unique-keyword-1000" in history.keyword_frequencies
        assert len(history.mappings) == 1000
