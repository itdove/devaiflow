"""Tests for configurable JIRA comment visibility (PROJ-60039)."""

import json
from unittest.mock import patch

import pytest

from devflow.config.loader import ConfigLoader
from devflow.jira.client import JiraClient


def test_default_comment_visibility(temp_daf_home, mock_jira_cli):
    """Test that comments use default visibility settings (no default group)."""
    # Setup: Create config with defaults
    config_loader = ConfigLoader()
    config_loader.create_default_config()

    # Setup mock ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
        }
    })

    # Create client and add comment
    client = JiraClient()
    # add_comment now returns None on success
    client.add_comment("PROJ-12345", "Test comment")

    # Verify comment was added successfully
    assert "PROJ-12345" in mock_jira_cli.comments
    assert len(mock_jira_cli.comments["PROJ-12345"]) == 1

    # Verify default visibility settings (open source - no defaults)
    assert client._comment_visibility_type is None
    assert client._comment_visibility_value is None


def test_custom_comment_visibility_group(temp_daf_home_no_patches, mock_jira_cli):
    """Test comments with custom group visibility."""
    # Setup: Create config and set custom group visibility
    config_loader = ConfigLoader()
    config_loader.create_default_config()
    config = config_loader.load_config()
    config.jira.comment_visibility_type = "group"
    config.jira.comment_visibility_value = "Custom Group"
    config_loader.save_config(config)

    # Setup mock ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
        }
    })

    # Create client and add comment
    client = JiraClient()
    # add_comment now returns None on success
    client.add_comment("PROJ-12345", "Test comment")

    # Verify custom settings were loaded
    assert client._comment_visibility_type == "group"
    assert client._comment_visibility_value == "Custom Group"


def test_custom_comment_visibility_role(temp_daf_home_no_patches, mock_jira_cli):
    """Test comments with custom role visibility."""
    # Setup: Create config and set custom role visibility
    config_loader = ConfigLoader()
    config_loader.create_default_config()
    config = config_loader.load_config()
    config.jira.comment_visibility_type = "role"
    config.jira.comment_visibility_value = "Administrators"
    config_loader.save_config(config)

    # Setup mock ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
        }
    })

    # Create client and add comment
    client = JiraClient()
    # add_comment now returns None on success
    client.add_comment("PROJ-12345", "Test comment with role")

    # Verify custom role settings were loaded
    assert client._comment_visibility_type == "role"
    assert client._comment_visibility_value == "Administrators"


def test_comment_visibility_without_config_file(temp_daf_home, mock_jira_cli, monkeypatch):
    """Test that JiraClient has no defaults when config file doesn't exist (open source)."""
    # Ensure config file doesn't exist
    config_loader = ConfigLoader()
    if config_loader.config_file.exists():
        config_loader.config_file.unlink()

    # Setup mock ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
        }
    })

    # Create client (no defaults without config or patches)
    client = JiraClient()

    assert client._comment_visibility_type is None
    assert client._comment_visibility_value is None

    # Verify comment can still be added with no visibility (public comment)
    client.add_comment("PROJ-12345", "Test comment")


def test_comment_visibility_persists_across_client_instances(temp_daf_home_no_patches, mock_jira_cli):
    """Test that visibility settings persist when creating multiple JiraClient instances."""
    # Setup: Create config with custom visibility
    config_loader = ConfigLoader()
    config_loader.create_default_config()
    config = config_loader.load_config()
    config.jira.comment_visibility_type = "role"
    config.jira.comment_visibility_value = "Engineers"
    config_loader.save_config(config)

    # Create first client instance
    client1 = JiraClient()
    assert client1._comment_visibility_type == "role"
    assert client1._comment_visibility_value == "Engineers"

    # Create second client instance (should load same settings)
    client2 = JiraClient()
    assert client2._comment_visibility_type == "role"
    assert client2._comment_visibility_value == "Engineers"


def test_jira_config_model_default_values():
    """Test that JiraConfig model has correct default values for comment visibility."""
    from devflow.config.models import JiraConfig

    # Create JiraConfig with minimal required fields
    jira_config = JiraConfig(
        url="https://jira.example.com",
        user="test@example.com",
        transitions={}
    )

    # Verify defaults (open source - no hardcoded visibility)
    assert jira_config.comment_visibility_type is None
    assert jira_config.comment_visibility_value is None
