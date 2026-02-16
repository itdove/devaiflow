"""Extended tests for config/models.py to improve coverage."""

import pytest
from devflow.config.models import (
    JiraFiltersConfig,
    JiraTransitionConfig,
    Session,
    SessionIndex,
)


def test_jira_filters_get_required_fields_list_format():
    """Test get_required_fields_for_type with old list format."""
    config = JiraFiltersConfig(
        status=["New"],
        required_fields=["summary", "description", "priority"]
    )

    # Should return same list for any type
    assert config.get_required_fields_for_type("Bug") == ["summary", "description", "priority"]
    assert config.get_required_fields_for_type("Story") == ["summary", "description", "priority"]


def test_jira_filters_get_required_fields_dict_format():
    """Test get_required_fields_for_type with new dict format."""
    config = JiraFiltersConfig(
        status=["New"],
        required_fields={
            "Bug": ["summary", "description", "severity"],
            "Story": ["summary", "description", "acceptance_criteria"],
        }
    )

    assert config.get_required_fields_for_type("Bug") == ["summary", "description", "severity"]
    assert config.get_required_fields_for_type("Story") == ["summary", "description", "acceptance_criteria"]


def test_jira_filters_get_required_fields_missing_type():
    """Test get_required_fields_for_type for type not in dict."""
    config = JiraFiltersConfig(
        status=["New"],
        required_fields={
            "Bug": ["summary"],
        }
    )

    # Type not in dict should return empty list
    assert config.get_required_fields_for_type("Epic") == []


def test_jira_transition_config_defaults():
    """Test JiraTransitionConfig default values."""
    config = JiraTransitionConfig()

    assert config.from_status == ["New", "To Do"]
    assert config.to == ""
    assert config.prompt is False
    assert config.on_fail == "warn"
    assert config.options is None


def test_session_index_get_sessions_returns_list():
    """Test get_sessions returns list of sessions."""
    index = SessionIndex()

    session = Session(name="test", issue_key="PROJ-123", goal="Test")
    index.sessions["test"] = session

    results = index.get_sessions("test")
    assert len(results) == 1
    assert results[0].name == "test"


def test_session_index_get_sessions_not_found():
    """Test get_sessions returns empty list for non-existent session."""
    index = SessionIndex()

    results = index.get_sessions("nonexistent")
    assert results == []
