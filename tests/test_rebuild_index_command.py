"""Tests for rebuild_index_command (AAP-63388)."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_sessions_dir(tmp_path):
    """Create a mock sessions directory with session data."""
    cs_home = tmp_path / "cs_home"
    sessions_dir = cs_home / "sessions"
    sessions_dir.mkdir(parents=True)

    # Create session 1 with metadata
    session1_dir = sessions_dir / "session-1"
    session1_dir.mkdir()
    metadata1 = {
        "name": "session-1",
        "goal": "Test session 1",
        "status": "in_progress",
        "created": "2024-01-01T10:00:00",
        "last_active": "2024-01-01T12:00:00",
        "issue_key": "PROJ-123"
    }
    (session1_dir / "metadata.json").write_text(json.dumps(metadata1))

    # Create session 2 with metadata and conversations
    session2_dir = sessions_dir / "session-2"
    session2_dir.mkdir()
    metadata2 = {
        "name": "session-2",
        "goal": "Test session 2",
        "status": "completed",
        "created": "2024-01-02T10:00:00",
        "last_active": "2024-01-02T15:00:00",
        "conversations": {
            "repo1": {
                "active_session": {
                    "ai_agent_session_id": "uuid-123"
                }
            }
        }
    }
    (session2_dir / "metadata.json").write_text(json.dumps(metadata2))

    # Create session 3 without metadata
    session3_dir = sessions_dir / "session-3"
    session3_dir.mkdir()

    # Create a file (not directory) to test filtering
    (sessions_dir / "some_file.txt").write_text("not a session")

    return cs_home


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_success(mock_sessions_dir, capsys):
    """Test rebuilding index successfully."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Found 2 sessions with valid metadata" in captured.out
    assert "Skipped 1 directories without metadata.json" in captured.out

    # Verify sessions.json was created
    sessions_file = mock_sessions_dir / "sessions.json"
    assert sessions_file.exists()

    with open(sessions_file) as f:
        index = json.load(f)

    assert len(index['sessions']) == 2
    assert "session-1" in index['sessions']
    assert "session-2" in index['sessions']
    assert index['sessions']['session-1']['goal'] == "Test session 1"


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_no_sessions_directory(tmp_path, capsys):
    """Test rebuild when sessions directory doesn't exist."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    cs_home = tmp_path / "cs_home"
    cs_home.mkdir()

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=cs_home):
        rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "No sessions directory found" in captured.out


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_dry_run(mock_sessions_dir, capsys):
    """Test dry run mode."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        rebuild_index(dry_run=True, force=False)

    captured = capsys.readouterr()
    assert "DRY RUN - No changes will be made" in captured.out
    assert "What would be rebuilt:" in captured.out

    # Verify sessions.json was NOT created
    sessions_file = mock_sessions_dir / "sessions.json"
    assert not sessions_file.exists()


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_force_mode(mock_sessions_dir, capsys):
    """Test force mode skips confirmation."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        # No Confirm.ask mock needed in force mode
        rebuild_index(dry_run=False, force=True)

    captured = capsys.readouterr()
    assert "Rebuilt sessions.json with 2 sessions" in captured.out


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_cancel_confirmation(mock_sessions_dir, capsys):
    """Test canceling rebuild at confirmation prompt."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=False):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Cancelled" in captured.out


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_with_backup(mock_sessions_dir, capsys):
    """Test backup of existing sessions.json."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    # Create existing sessions.json
    sessions_file = mock_sessions_dir / "sessions.json"
    existing_data = {"sessions": {"old-session": {"name": "old-session"}}}
    sessions_file.write_text(json.dumps(existing_data))

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Backup created" in captured.out

    # Verify backup was created
    backup_file = mock_sessions_dir / "sessions.json.backup"
    assert backup_file.exists()


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_preserve_conversations(mock_sessions_dir, capsys):
    """Test preserving conversation data from backup."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    # Create existing sessions.json with conversation data
    sessions_file = mock_sessions_dir / "sessions.json"
    existing_data = {
        "sessions": {
            "session-1": {
                "name": "session-1",
                "conversations": {
                    "repo2": {
                        "active_session": {
                            "ai_agent_session_id": "uuid-456"
                        }
                    }
                }
            }
        }
    }
    sessions_file.write_text(json.dumps(existing_data))

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Merged" in captured.out and "conversations" in captured.out

    # Verify conversation was preserved
    with open(sessions_file) as f:
        index = json.load(f)

    assert "repo2" in index['sessions']['session-1']['conversations']


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_migrate_old_format(mock_sessions_dir, capsys):
    """Test migrating old conversation format."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    # Create existing sessions.json with old conversation format
    sessions_file = mock_sessions_dir / "sessions.json"
    existing_data = {
        "sessions": {
            "session-1": {
                "name": "session-1",
                "conversations": {
                    "repo3": {
                        "claude_session_id": "old-uuid-789"  # Old field name
                    }
                }
            }
        }
    }
    sessions_file.write_text(json.dumps(existing_data))

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Migrated" in captured.out and "conversations from old format" in captured.out

    # Verify conversation was migrated
    with open(sessions_file) as f:
        index = json.load(f)

    conv = index['sessions']['session-1']['conversations']['repo3']
    assert 'active_session' in conv
    assert 'ai_agent_session_id' in conv['active_session']
    assert conv['active_session']['ai_agent_session_id'] == "old-uuid-789"


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_with_errors(mock_sessions_dir, capsys):
    """Test handling metadata read errors."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    # Create session with invalid metadata
    session_error_dir = mock_sessions_dir / "sessions" / "session-error"
    session_error_dir.mkdir()
    (session_error_dir / "metadata.json").write_text("invalid json {")

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Errors reading" in captured.out and "session metadata files" in captured.out


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_default_datetime_fields(mock_sessions_dir, capsys):
    """Test handling sessions without datetime fields."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    # Create session without created/last_active fields
    session_no_dates_dir = mock_sessions_dir / "sessions" / "session-no-dates"
    session_no_dates_dir.mkdir()
    metadata = {
        "name": "session-no-dates",
        "goal": "Test session without dates"
    }
    (session_no_dates_dir / "metadata.json").write_text(json.dumps(metadata))

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Rebuilt sessions.json" in captured.out

    # Verify defaults were applied
    sessions_file = mock_sessions_dir / "sessions.json"
    with open(sessions_file) as f:
        index = json.load(f)

    session = index['sessions']['session-no-dates']
    assert session['created']  # Should have a value
    assert session['last_active']  # Should have a value


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_many_skipped_sessions(mock_sessions_dir, capsys):
    """Test display when many sessions are skipped."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    sessions_dir = mock_sessions_dir / "sessions"

    # Create 15 sessions without metadata
    for i in range(15):
        (sessions_dir / f"skipped-{i}").mkdir()

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Skipped 16 directories" in captured.out  # 15 + 1 from fixture
    assert "first 10" in captured.out


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_many_errors(mock_sessions_dir, capsys):
    """Test display when many errors occur."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    sessions_dir = mock_sessions_dir / "sessions"

    # Create 10 sessions with invalid metadata
    for i in range(10):
        error_dir = sessions_dir / f"error-{i}"
        error_dir.mkdir()
        (error_dir / "metadata.json").write_text("invalid json {")

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Errors reading 10 session metadata files" in captured.out
    assert "first 5" in captured.out


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_conversations_from_metadata(mock_sessions_dir, capsys):
    """Test counting conversations loaded from metadata."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Loaded conversation data for 1 sessions from metadata.json" in captured.out


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_backup_preserve_error(mock_sessions_dir, capsys):
    """Test handling errors when preserving conversations from backup."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    # Create invalid sessions.json
    sessions_file = mock_sessions_dir / "sessions.json"
    sessions_file.write_text("invalid json {")

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    captured = capsys.readouterr()
    assert "Could not preserve conversations" in captured.out


@patch('devflow.cli.commands.rebuild_index_command.require_outside_claude', lambda f: f)
def test_rebuild_index_all_fields_preserved(mock_sessions_dir, capsys):
    """Test that all session fields are preserved in rebuild."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    sessions_dir = mock_sessions_dir / "sessions"
    full_session_dir = sessions_dir / "full-session"
    full_session_dir.mkdir()

    metadata = {
        "name": "full-session",
        "goal": "Test all fields",
        "session_type": "bug_fix",
        "status": "in_progress",
        "created": "2024-01-01T10:00:00",
        "started": "2024-01-01T10:05:00",
        "last_active": "2024-01-01T12:00:00",
        "work_sessions": [{"start": "2024-01-01T10:00:00"}],
        "time_tracking_state": "active",
        "tags": ["urgent", "backend"],
        "related_sessions": ["session-1"],
        "working_directory": "/path/to/repo",
        "workspace_name": "primary",
        "issue_tracker": "jira",
        "issue_key": "PROJ-456",
        "issue_updated": "2024-01-01T11:00:00",
        "issue_metadata": {"priority": "high"}
    }
    (full_session_dir / "metadata.json").write_text(json.dumps(metadata))

    with patch('devflow.cli.commands.rebuild_index_command.get_cs_home', return_value=mock_sessions_dir):
        with patch('devflow.cli.commands.rebuild_index_command.Confirm.ask', return_value=True):
            rebuild_index(dry_run=False, force=False)

    # Verify all fields were preserved
    sessions_file = mock_sessions_dir / "sessions.json"
    with open(sessions_file) as f:
        index = json.load(f)

    session = index['sessions']['full-session']
    assert session['goal'] == "Test all fields"
    assert session['session_type'] == "bug_fix"
    assert session['status'] == "in_progress"
    assert session['time_tracking_state'] == "active"
    assert session['tags'] == ["urgent", "backend"]
    assert session['workspace_name'] == "primary"
    assert session['issue_key'] == "PROJ-456"
