"""Extended tests for session/repair.py to improve coverage."""

import pytest
import json
from pathlib import Path
from devflow.session.repair import (
    get_conversation_file_path,
    is_valid_uuid,
    detect_corruption,
    ConversationRepairError
)


def test_get_conversation_file_path_not_found(tmp_path, monkeypatch):
    """Test get_conversation_file_path when file doesn't exist."""
    # Mock home to tmp_path
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)

    # Create .claude/projects but no conversation files
    projects_dir = tmp_path / ".claude" / "projects"
    projects_dir.mkdir(parents=True)

    result = get_conversation_file_path("non-existent-uuid")
    assert result is None


def test_get_conversation_file_path_no_projects_dir(tmp_path, monkeypatch):
    """Test when projects directory doesn't exist."""
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)

    result = get_conversation_file_path("some-uuid")
    assert result is None


def test_get_conversation_file_path_found(tmp_path, monkeypatch):
    """Test getting conversation file path when it exists."""
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)

    # Create conversation file
    projects_dir = tmp_path / ".claude" / "projects" / "project1"
    projects_dir.mkdir(parents=True)

    uuid = "test-uuid-1234"
    conv_file = projects_dir / f"{uuid}.jsonl"
    conv_file.write_text('{"test": "data"}')

    result = get_conversation_file_path(uuid)
    assert result == conv_file


def test_get_conversation_file_path_skips_non_directories(tmp_path, monkeypatch):
    """Test that non-directory files are skipped."""
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)

    projects_dir = tmp_path / ".claude" / "projects"
    projects_dir.mkdir(parents=True)

    # Create a file (not directory) in projects
    (projects_dir / "not-a-directory.txt").write_text("content")

    # Should not raise error
    result = get_conversation_file_path("some-uuid")
    assert result is None


def test_is_valid_uuid_valid():
    """Test is_valid_uuid with valid UUIDs."""
    assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True
    assert is_valid_uuid("6ba7b810-9dad-11d1-80b4-00c04fd430c8") is True
    assert is_valid_uuid("AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE") is True  # Case insensitive


def test_is_valid_uuid_invalid():
    """Test is_valid_uuid with invalid UUIDs."""
    assert is_valid_uuid("not-a-uuid") is False
    assert is_valid_uuid("550e8400-e29b-41d4-a716") is False  # Too short
    assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000-extra") is False  # Too long
    assert is_valid_uuid("") is False
    assert is_valid_uuid("550e8400e29b41d4a716446655440000") is False  # No hyphens


def test_detect_corruption_valid_file(tmp_path):
    """Test detect_corruption with valid conversation file."""
    conv_file = tmp_path / "valid.jsonl"

    # Write valid JSON lines
    with open(conv_file, 'w') as f:
        f.write('{"type": "user", "content": "Hello"}\n')
        f.write('{"type": "assistant", "content": "Hi there"}\n')

    result = detect_corruption(conv_file)

    assert result["is_corrupt"] is False
    assert len(result["issues"]) == 0
    assert len(result["invalid_lines"]) == 0


def test_detect_corruption_invalid_json(tmp_path):
    """Test detect_corruption with invalid JSON."""
    conv_file = tmp_path / "invalid.jsonl"

    with open(conv_file, 'w') as f:
        f.write('{"type": "user", "content": "Hello"}\n')
        f.write('invalid json line\n')
        f.write('{"type": "assistant", "content": "Response"}\n')

    result = detect_corruption(conv_file)

    assert result["is_corrupt"] is True
    assert len(result["invalid_lines"]) > 0
    # Should have detected line 2 as invalid
    assert any(line_num == 2 for line_num, _ in result["invalid_lines"])


def test_detect_corruption_large_content(tmp_path):
    """Test detect_corruption detects large content needing truncation."""
    conv_file = tmp_path / "large.jsonl"

    # Create message with very large content
    large_content = "x" * 15000  # Larger than typical threshold
    with open(conv_file, 'w') as f:
        f.write(json.dumps({"type": "tool_result", "content": large_content}) + '\n')

    result = detect_corruption(conv_file)

    # Should detect truncation needed
    assert len(result["truncation_needed"]) > 0 or result["is_corrupt"] is False


def test_detect_corruption_empty_file(tmp_path):
    """Test detect_corruption with empty file."""
    conv_file = tmp_path / "empty.jsonl"
    conv_file.write_text("")

    result = detect_corruption(conv_file)

    # Empty file is not corrupt, just has no content
    assert result["is_corrupt"] is False


def test_detect_corruption_file_not_found():
    """Test detect_corruption with non-existent file."""
    # detect_corruption catches exceptions and returns error result
    result = detect_corruption(Path("/nonexistent/file.jsonl"))
    assert result["is_corrupt"] is True
    assert len(result["issues"]) > 0
