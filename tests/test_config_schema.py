"""Tests for config schema generation and validation."""

import json
import pytest
from pathlib import Path

from devflow.config.schema import (
    generate_json_schema,
    save_schema,
    validate_config_dict,
    validate_config_file,
)
from devflow.config.loader import ConfigLoader
from devflow.config.models import Config


def test_generate_json_schema():
    """Test JSON Schema generation from Pydantic models."""
    schema = generate_json_schema()

    # Verify schema metadata
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert "title" in schema
    assert "properties" in schema

    # Verify required top-level properties
    assert "jira" in schema["properties"]
    assert "repos" in schema["properties"]
    assert "prompts" in schema["properties"]

    # Verify required fields
    assert "jira" in schema["required"]
    assert "repos" in schema["required"]


def test_save_schema(tmp_path):
    """Test saving JSON Schema to file."""
    output_path = tmp_path / "test_schema.json"
    result_path = save_schema(output_path)

    assert result_path == output_path
    assert output_path.exists()

    # Verify schema content
    with open(output_path, "r") as f:
        schema = json.load(f)

    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert "properties" in schema


def test_validate_valid_config():
    """Test validation of a valid configuration."""
    config_dict = {
        "jira": {
            "url": "https://jira.example.com",
            "user": "test-user",
            "transitions": {
                "on_start": {
                    "from": ["New", "To Do"],
                    "to": "In Progress",
                    "prompt": False,
                    "on_fail": "warn"
                },
                "on_complete": {
                    "prompt": True,
                    "on_fail": "warn"
                }
            }
        },
        "repos": {
            "workspace": "/tmp/test-workspace"
        }
    }

    config_loader = ConfigLoader()
    is_valid, error_message = config_loader.validate_config_dict(config_dict)
    assert is_valid is True
    assert error_message is None


def test_validate_invalid_config_missing_required():
    """Test validation fails for missing required fields."""
    config_dict = {
        "jira": {
            "url": "https://jira.example.com"
            # Missing 'user' and 'transitions' (required)
        },
        "repos": {
            "workspace": "/tmp/test-workspace"
        }
    }

    config_loader = ConfigLoader()
    is_valid, error_message = config_loader.validate_config_dict(config_dict)
    assert is_valid is False
    assert error_message is not None
    assert "user" in error_message or "transitions" in error_message


def test_validate_invalid_config_wrong_type():
    """Test validation fails for wrong data types."""
    config_dict = {
        "jira": {
            "url": "https://jira.example.com",
            "user": "test-user",
            "transitions": {
                "on_start": {
                    "from": ["New", "To Do"],
                    "to": "In Progress",
                    "prompt": "invalid",  # Should be boolean
                    "on_fail": "warn"
                }
            }
        },
        "repos": {
            "workspace": "/tmp/test-workspace"
        }
    }

    config_loader = ConfigLoader()
    is_valid, error_message = config_loader.validate_config_dict(config_dict)
    assert is_valid is False
    assert error_message is not None


def test_validate_config_file_valid(tmp_path):
    """Test validation of a valid config file."""
    config_file = tmp_path / "config.json"
    config_dict = {
        "jira": {
            "url": "https://jira.example.com",
            "user": "test-user",
            "transitions": {
                "on_start": {
                    "from": ["New", "To Do"],
                    "to": "In Progress",
                    "prompt": False,
                    "on_fail": "warn"
                },
                "on_complete": {
                    "prompt": True,
                    "on_fail": "warn"
                }
            }
        },
        "repos": {
            "workspace": "/tmp/test-workspace"
        }
    }

    with open(config_file, "w") as f:
        json.dump(config_dict, f)

    config_loader = ConfigLoader(config_dir=tmp_path)
    is_valid, error_message = config_loader.validate_config_file()
    assert is_valid is True
    assert error_message is None


def test_validate_config_file_not_found(tmp_path):
    """Test validation fails when config file doesn't exist."""
    config_loader = ConfigLoader(config_dir=tmp_path)

    is_valid, error_message = config_loader.validate_config_file()
    assert is_valid is False
    assert "not found" in error_message.lower()


def test_validate_config_file_invalid_json(tmp_path):
    """Test validation fails for invalid JSON."""
    config_file = tmp_path / "config.json"

    with open(config_file, "w") as f:
        f.write("{ invalid json }")

    config_loader = ConfigLoader(config_dir=tmp_path)
    is_valid, error_message = config_loader.validate_config_file()
    assert is_valid is False
    assert "json" in error_message.lower()


def test_schema_has_all_model_fields():
    """Test that schema includes all fields from Config model."""
    schema = generate_json_schema()

    # Check top-level properties match Config model
    expected_top_level = [
        "jira",
        "repos",
        "time_tracking",
        "session_summary",
        "templates",
        "context_files",
        "prompts",
        "pr_template_url",
        "mock_services",
        "gcp_vertex_region",
        "update_checker_timeout"
    ]

    for field in expected_top_level:
        assert field in schema["properties"], f"Missing field: {field}"


def test_schema_jira_fields():
    """Test that JIRA configuration fields are properly defined in schema."""
    schema = generate_json_schema()

    # Navigate to JiraConfig definition
    jira_def = None
    if "$defs" in schema and "JiraConfig" in schema["$defs"]:
        jira_def = schema["$defs"]["JiraConfig"]

    assert jira_def is not None, "JiraConfig definition not found in schema"

    # Check required JIRA fields
    assert "url" in jira_def["properties"]
    assert "transitions" in jira_def["properties"]

    # Check optional JIRA fields
    assert "project" in jira_def["properties"]
    assert "custom_field_defaults" in jira_def["properties"]
    assert "field_mappings" in jira_def["properties"]


def test_validate_config_with_optional_fields():
    """Test validation succeeds with optional fields included."""
    config_dict = {
        "jira": {
            "url": "https://jira.example.com",
            "user": "test-user",
            "project": "PROJ",
            "workstream": "Platform",
            "transitions": {
                "on_start": {
                    "from": ["New", "To Do"],
                    "to": "In Progress"
                }
            },
            "field_cache_max_age_hours": 48
        },
        "repos": {
            "workspace": "/tmp/test-workspace",
            "detection": {
                "method": "keyword_match",
                "fallback": "prompt"
            },
            "keywords": {
                "repo1": ["keyword1", "keyword2"]
            }
        },
        "prompts": {
            "auto_commit_on_complete": True,
            "auto_launch_claude": False,
            "show_prompt_unit_tests": True
        }
    }

    config_loader = ConfigLoader()
    is_valid, error_message = config_loader.validate_config_dict(config_dict)
    assert is_valid is True
    assert error_message is None


def test_validate_config_with_null_optional_fields():
    """Test validation succeeds with null values for optional fields."""
    config_dict = {
        "jira": {
            "url": "https://jira.example.com",
            "user": "test-user",
            "project": None,
            "workstream": None,
            "affected_version": None,
            "transitions": {
                "on_start": {
                    "from": ["New", "To Do"],
                    "to": "In Progress"
                }
            }
        },
        "repos": {
            "workspace": "/tmp/test-workspace"
        }
    }

    config_loader = ConfigLoader()
    is_valid, error_message = config_loader.validate_config_dict(config_dict)
    assert is_valid is True
    assert error_message is None
