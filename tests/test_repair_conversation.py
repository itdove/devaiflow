"""Tests for conversation repair functionality."""

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from devflow.session.repair import (
    ConversationRepairError,
    detect_corruption,
    get_conversation_file_path,
    is_valid_uuid,
    remove_invalid_surrogates,
    repair_conversation_file,
    truncate_content,
)


class TestIsValidUUID:
    """Tests for UUID validation."""

    def test_valid_uuid(self):
        """Test valid UUID format."""
        assert is_valid_uuid("f545206f-480f-4c2d-8823-c6643f0e693d")
        assert is_valid_uuid("F545206F-480F-4C2D-8823-C6643F0E693D")  # Uppercase

    def test_invalid_uuid(self):
        """Test invalid UUID formats."""
        assert not is_valid_uuid("not-a-uuid")
        assert not is_valid_uuid("f545206f-480f-4c2d-8823")  # Too short
        assert not is_valid_uuid("PROJ-60039")
        assert not is_valid_uuid("my-session")
        assert not is_valid_uuid("")


class TestRemoveInvalidSurrogates:
    """Tests for removing invalid Unicode surrogates."""

    def test_clean_text(self):
        """Test text without surrogates."""
        text = "Hello, world! 你好世界"
        assert remove_invalid_surrogates(text) == text

    def test_with_surrogates(self):
        """Test text with invalid surrogates."""
        # Create text with invalid surrogate
        text_with_surrogate = "Hello \ud800 world"
        result = remove_invalid_surrogates(text_with_surrogate)
        # Surrogates should be removed
        assert "\ud800" not in result
        assert "Hello" in result
        assert "world" in result

    def test_empty_string(self):
        """Test empty string."""
        assert remove_invalid_surrogates("") == ""


class TestTruncateContent:
    """Tests for content truncation."""

    def test_string_within_limit(self):
        """Test string under max size."""
        content = "Hello, world!"
        result, truncated = truncate_content(content, max_size=100)
        assert result == content
        assert not truncated

    def test_string_exceeds_limit(self):
        """Test string over max size."""
        content = "x" * 15000
        result, truncated = truncate_content(content, max_size=10000)
        assert truncated
        assert len(result) < 15000
        assert "[TRUNCATED:" in result

    def test_dict_truncation(self):
        """Test dict with oversized values."""
        content = {
            "short": "ok",
            "long": "x" * 15000,
        }
        result, truncated = truncate_content(content, max_size=10000)
        assert truncated
        assert result["short"] == "ok"
        assert len(result["long"]) < 15000
        assert "[TRUNCATED:" in result["long"]

    def test_nested_dict_truncation(self):
        """Test nested dict truncation."""
        content = {
            "outer": {
                "inner": "y" * 15000
            }
        }
        result, truncated = truncate_content(content, max_size=10000)
        assert truncated
        assert len(result["outer"]["inner"]) < 15000

    def test_list_truncation(self):
        """Test list with oversized items."""
        content = ["short", "z" * 15000, "also short"]
        result, truncated = truncate_content(content, max_size=10000)
        assert truncated
        assert result[0] == "short"
        assert result[2] == "also short"
        assert len(result[1]) < 15000


class TestDetectCorruption:
    """Tests for corruption detection."""

    def test_clean_file(self, tmp_path):
        """Test clean conversation file."""
        conv_file = tmp_path / "test.jsonl"
        with open(conv_file, 'w') as f:
            f.write(json.dumps({"type": "message", "content": "Hello"}) + "\n")
            f.write(json.dumps({"type": "message", "content": "World"}) + "\n")

        result = detect_corruption(conv_file)
        assert not result['is_corrupt']
        assert len(result['issues']) == 0
        assert len(result['invalid_lines']) == 0
        assert len(result['truncation_needed']) == 0

    def test_invalid_json(self, tmp_path):
        """Test file with invalid JSON."""
        conv_file = tmp_path / "test.jsonl"
        with open(conv_file, 'w') as f:
            f.write(json.dumps({"type": "message", "content": "Hello"}) + "\n")
            f.write("{invalid json\n")  # Invalid JSON
            f.write(json.dumps({"type": "message", "content": "World"}) + "\n")

        result = detect_corruption(conv_file)
        assert result['is_corrupt']
        assert len(result['invalid_lines']) == 1
        assert result['invalid_lines'][0][0] == 2  # Line 2

    def test_oversized_tool_result(self, tmp_path):
        """Test file with oversized tool result."""
        conv_file = tmp_path / "test.jsonl"
        large_content = "x" * 15000
        with open(conv_file, 'w') as f:
            f.write(json.dumps({"type": "tool_result", "content": large_content}) + "\n")

        result = detect_corruption(conv_file)
        assert result['is_corrupt']
        assert len(result['truncation_needed']) == 1
        assert result['truncation_needed'][0][0] == 1  # Line 1
        assert result['truncation_needed'][0][1] == 15000  # Size

    def test_oversized_tool_use(self, tmp_path):
        """Test file with oversized tool use content."""
        conv_file = tmp_path / "test.jsonl"
        large_input = "y" * 15000
        with open(conv_file, 'w') as f:
            f.write(json.dumps({"type": "tool_use", "input": large_input}) + "\n")

        result = detect_corruption(conv_file)
        assert result['is_corrupt']
        assert len(result['truncation_needed']) == 1


class TestRepairConversationFile:
    """Tests for conversation file repair."""

    def test_repair_invalid_json(self, tmp_path):
        """Test repairing invalid JSON lines."""
        conv_file = tmp_path / "test.jsonl"
        with open(conv_file, 'w') as f:
            f.write(json.dumps({"type": "message", "content": "Hello"}) + "\n")
            # Write invalid JSON (missing closing brace)
            f.write('{"type": "message", "content": "Hello world"\n')
            f.write(json.dumps({"type": "message", "content": "World"}) + "\n")

        # First check that file is detected as corrupt
        corruption_info = detect_corruption(conv_file)
        assert corruption_info['is_corrupt']
        assert len(corruption_info['invalid_lines']) > 0

        result = repair_conversation_file(conv_file, max_size=10000, dry_run=False)

        assert result['success']
        # Backup is only created if there's actual corruption to fix
        if result['lines_repaired'] > 0:
            assert result['backup_path'] is not None
            assert result['backup_path'].exists()

        # Verify repaired file - invalid lines should be skipped
        with open(conv_file, 'r') as f:
            lines = f.readlines()
            valid_count = 0
            for line in lines:
                if line.strip():
                    data = json.loads(line)  # Should not raise error
                    assert isinstance(data, dict)
                    valid_count += 1
            # Should have 2 valid lines (first and third, second was skipped)
            assert valid_count == 2

    def test_repair_oversized_content(self, tmp_path):
        """Test repairing oversized tool results."""
        conv_file = tmp_path / "test.jsonl"
        large_content = "x" * 15000

        with open(conv_file, 'w') as f:
            f.write(json.dumps({"type": "tool_result", "content": large_content}) + "\n")
            f.write(json.dumps({"type": "message", "content": "Small"}) + "\n")

        result = repair_conversation_file(conv_file, max_size=10000, dry_run=False)

        assert result['success']
        assert len(result['truncations']) == 1
        assert result['truncations'][0][0] == 1  # Line 1
        assert result['truncations'][0][1] > 10000  # Old size
        assert result['truncations'][0][2] <= 10100  # New size (with truncation message)

        # Verify truncation
        with open(conv_file, 'r') as f:
            first_line = f.readline()
            data = json.loads(first_line)
            assert len(data['content']) < 15000
            assert "[TRUNCATED:" in data['content']

    def test_dry_run_mode(self, tmp_path):
        """Test dry run mode doesn't modify file."""
        conv_file = tmp_path / "test.jsonl"
        large_content = "x" * 15000

        with open(conv_file, 'w') as f:
            f.write(json.dumps({"type": "tool_result", "content": large_content}) + "\n")

        original_content = conv_file.read_text()

        result = repair_conversation_file(conv_file, max_size=10000, dry_run=True)

        # File should be unchanged
        assert conv_file.read_text() == original_content
        assert result['backup_path'] is None

    def test_clean_file_no_repair_needed(self, tmp_path):
        """Test clean file returns success with no changes."""
        conv_file = tmp_path / "test.jsonl"
        with open(conv_file, 'w') as f:
            f.write(json.dumps({"type": "message", "content": "Hello"}) + "\n")

        result = repair_conversation_file(conv_file, max_size=10000, dry_run=False)

        assert result['success']
        assert result['backup_path'] is None  # No backup needed
        assert result['lines_repaired'] == 0
        assert result['message'] == 'No corruption detected'

    def test_file_not_found(self, tmp_path):
        """Test error when file doesn't exist."""
        conv_file = tmp_path / "nonexistent.jsonl"

        with pytest.raises(ConversationRepairError, match="not found"):
            repair_conversation_file(conv_file, max_size=10000, dry_run=False)

    def test_custom_max_size(self, tmp_path):
        """Test custom truncation size."""
        conv_file = tmp_path / "test.jsonl"
        large_content = "x" * 20000

        with open(conv_file, 'w') as f:
            f.write(json.dumps({"type": "tool_result", "content": large_content}) + "\n")

        result = repair_conversation_file(conv_file, max_size=5000, dry_run=False)

        assert result['success']
        assert len(result['truncations']) == 1

        # Verify truncation to custom size
        with open(conv_file, 'r') as f:
            data = json.loads(f.readline())
            # Content should be around 5000 + truncation message
            assert len(data['content']) < 6000
            assert "[TRUNCATED:" in data['content']


class TestGetConversationFilePath:
    """Tests for finding conversation files by UUID."""

    def test_file_found(self, tmp_path, monkeypatch):
        """Test finding existing conversation file."""
        # Create mock .claude directory structure
        claude_home = tmp_path / ".claude"
        projects_dir = claude_home / "projects"
        project_dir = projects_dir / "-Users-test-project"
        project_dir.mkdir(parents=True)

        uuid = "f545206f-480f-4c2d-8823-c6643f0e693d"
        conv_file = project_dir / f"{uuid}.jsonl"
        conv_file.write_text('{"type":"message"}\n')

        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = get_conversation_file_path(uuid)
        assert result == conv_file
        assert result.exists()

    def test_file_not_found(self, tmp_path, monkeypatch):
        """Test UUID not found."""
        # Create empty .claude directory
        claude_home = tmp_path / ".claude"
        projects_dir = claude_home / "projects"
        projects_dir.mkdir(parents=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        uuid = "f545206f-480f-4c2d-8823-c6643f0e693d"
        result = get_conversation_file_path(uuid)
        assert result is None

    def test_no_claude_directory(self, tmp_path, monkeypatch):
        """Test when .claude directory doesn't exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        uuid = "f545206f-480f-4c2d-8823-c6643f0e693d"
        result = get_conversation_file_path(uuid)
        assert result is None


class TestScanAllConversations:
    """Tests for scanning all conversations for corruption."""

    def test_scan_finds_corrupted_files(self, tmp_path, monkeypatch):
        """Test scanning finds corrupted conversation files."""
        from devflow.session.repair import scan_all_conversations

        # Create mock .claude directory with both clean and corrupted files
        claude_home = tmp_path / ".claude"
        projects_dir = claude_home / "projects"
        project_dir = projects_dir / "-Users-test-project"
        project_dir.mkdir(parents=True)

        # Clean file
        uuid1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        clean_file = project_dir / f"{uuid1}.jsonl"
        clean_file.write_text(json.dumps({"type": "message", "content": "ok"}) + "\n")

        # Corrupted file (oversized)
        uuid2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        corrupt_file = project_dir / f"{uuid2}.jsonl"
        large_content = "x" * 15000
        corrupt_file.write_text(json.dumps({"type": "tool_result", "content": large_content}) + "\n")

        # Non-UUID file (should be skipped)
        non_uuid_file = project_dir / "agent-12345.jsonl"
        non_uuid_file.write_text(json.dumps({"type": "message"}) + "\n")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        results = scan_all_conversations()

        # Should find only the corrupted file
        assert len(results) == 1
        assert results[0][0] == uuid2
        assert results[0][1] == corrupt_file
        assert results[0][2]['is_corrupt']

    def test_scan_no_corrupted_files(self, tmp_path, monkeypatch):
        """Test scanning when all files are clean."""
        from devflow.session.repair import scan_all_conversations

        claude_home = tmp_path / ".claude"
        projects_dir = claude_home / "projects"
        project_dir = projects_dir / "-Users-test-project"
        project_dir.mkdir(parents=True)

        uuid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        clean_file = project_dir / f"{uuid}.jsonl"
        clean_file.write_text(json.dumps({"type": "message", "content": "ok"}) + "\n")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        results = scan_all_conversations()
        assert len(results) == 0
