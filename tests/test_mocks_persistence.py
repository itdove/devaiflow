"""Tests for mocks/persistence.py to improve coverage."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from devflow.mocks.persistence import MockDataStore


def test_load_service_corrupted_json(tmp_path, monkeypatch):
    """Test loading service with corrupted JSON file."""
    # Mock get_daf_sessions_home to return tmp_path
    monkeypatch.setattr("devflow.utils.paths.get_cs_home", lambda: tmp_path)
    
    # Create data directory
    data_dir = tmp_path / "mock-data"
    data_dir.mkdir()

    # Write corrupted JSON
    jira_file = data_dir / "jira.json"
    jira_file.write_text("{invalid json content")

    # Should handle gracefully
    store = MockDataStore()
    store._load_service("jira")

    # Should have empty dict (fresh start)
    assert store._data["jira"] == {}


def test_save_service_io_error(tmp_path, monkeypatch, capsys):
    """Test save_service handles IOError gracefully."""
    monkeypatch.setattr("devflow.utils.paths.get_cs_home", lambda: tmp_path)
    
    store = MockDataStore()
    store._data["jira"] = {"test": "data"}

    # Mock open to raise IOError
    with patch("builtins.open", side_effect=IOError("Disk full")):
        store._save_service("jira")

        # Should print warning
        captured = capsys.readouterr()
        assert "Failed to save mock data" in captured.err


def test_persistence_across_instances(tmp_path, monkeypatch):
    """Test that data persists across MockDataStore instances."""
    monkeypatch.setattr("devflow.utils.paths.get_cs_home", lambda: tmp_path)

    # Create first instance and add data
    store1 = MockDataStore()
    store1.set_jira_ticket("PROJ-100", {"key": "PROJ-100", "summary": "Persistent"})

    # Create second instance - should load persisted data
    store2 = MockDataStore()
    ticket = store2.get_jira_ticket("PROJ-100")

    assert ticket is not None
    assert ticket["summary"] == "Persistent"
