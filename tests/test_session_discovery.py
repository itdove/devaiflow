"""Tests for devflow.session.discovery module."""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from devflow.session.discovery import SessionDiscovery, DiscoveredSession


@pytest.fixture
def temp_claude_dir(tmp_path):
    """Create a temporary .claude directory structure."""
    claude_dir = tmp_path / ".claude"
    projects_dir = claude_dir / "projects"
    projects_dir.mkdir(parents=True)
    return claude_dir


@pytest.fixture
def sample_session_messages():
    """Create sample Claude Code session messages."""
    return [
        {
            "type": "user",
            "cwd": "/path/to/project",
            "message": {
                "role": "user",
                "content": "Help me write a test"
            }
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": "I'll help you write a test"
            }
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Add more test cases"
            }
        },
    ]


class TestSessionDiscovery:
    """Tests for SessionDiscovery class."""

    def test_init_default_claude_dir(self):
        """Test initialization with default .claude directory."""
        discovery = SessionDiscovery()
        assert discovery.claude_dir == Path.home() / ".claude"
        assert discovery.projects_dir == Path.home() / ".claude" / "projects"

    def test_init_custom_claude_dir(self, tmp_path):
        """Test initialization with custom .claude directory."""
        custom_dir = tmp_path / "custom_claude"
        discovery = SessionDiscovery(claude_dir=custom_dir)
        assert discovery.claude_dir == custom_dir
        assert discovery.projects_dir == custom_dir / "projects"

    def test_discover_sessions_no_projects_dir(self, tmp_path):
        """Test discover_sessions when projects directory doesn't exist."""
        claude_dir = tmp_path / ".claude"
        discovery = SessionDiscovery(claude_dir=claude_dir)

        sessions = discovery.discover_sessions()
        assert sessions == []

    def test_discover_sessions_empty_projects_dir(self, temp_claude_dir):
        """Test discover_sessions when projects directory is empty."""
        discovery = SessionDiscovery(claude_dir=temp_claude_dir)

        sessions = discovery.discover_sessions()
        assert sessions == []

    def test_discover_single_session(self, temp_claude_dir, sample_session_messages):
        """Test discovering a single session."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)

        session_file = project_dir / "test-uuid-1234.jsonl"
        with open(session_file, "w") as f:
            for msg in sample_session_messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        assert len(sessions) == 1
        assert sessions[0].uuid == "test-uuid-1234"
        assert sessions[0].project_path == "/path/to/project"
        assert sessions[0].message_count == 3
        assert sessions[0].first_message == "Help me write a test"
        assert sessions[0].working_directory == "project"

    def test_discover_multiple_sessions(self, temp_claude_dir, sample_session_messages):
        """Test discovering multiple sessions."""
        # Create two project directories with sessions
        for i in range(2):
            project_dir = temp_claude_dir / "projects" / f"project{i}"
            project_dir.mkdir(parents=True)

            session_file = project_dir / f"uuid-{i}.jsonl"
            with open(session_file, "w") as f:
                for msg in sample_session_messages:
                    f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        assert len(sessions) == 2
        assert any(s.uuid == "uuid-0" for s in sessions)
        assert any(s.uuid == "uuid-1" for s in sessions)

    def test_discover_sessions_sorted_by_last_active(self, temp_claude_dir, sample_session_messages):
        """Test that sessions are sorted by last_active (most recent first)."""
        import time

        # Create first session
        project_dir1 = temp_claude_dir / "projects" / "project1"
        project_dir1.mkdir(parents=True)
        session_file1 = project_dir1 / "uuid-old.jsonl"
        with open(session_file1, "w") as f:
            for msg in sample_session_messages:
                f.write(json.dumps(msg) + "\n")

        # Sleep to ensure different timestamps
        time.sleep(0.1)

        # Create second session (more recent)
        project_dir2 = temp_claude_dir / "projects" / "project2"
        project_dir2.mkdir(parents=True)
        session_file2 = project_dir2 / "uuid-new.jsonl"
        with open(session_file2, "w") as f:
            for msg in sample_session_messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        assert len(sessions) == 2
        # Most recent should be first
        assert sessions[0].uuid == "uuid-new"
        assert sessions[1].uuid == "uuid-old"
        assert sessions[0].last_active > sessions[1].last_active

    def test_parse_session_empty_file(self, temp_claude_dir):
        """Test parsing an empty session file."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)
        session_file = project_dir / "empty.jsonl"
        session_file.write_text("")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        # Empty file should be skipped
        assert len(sessions) == 0

    def test_parse_session_invalid_json(self, temp_claude_dir):
        """Test parsing a session file with invalid JSON."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)
        session_file = project_dir / "invalid.jsonl"
        session_file.write_text("This is not JSON\n{also not json")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        # Invalid JSON should be skipped (no messages parsed)
        assert len(sessions) == 0

    def test_parse_session_partial_invalid_json(self, temp_claude_dir, sample_session_messages):
        """Test parsing a session file with some invalid JSON lines."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)
        session_file = project_dir / "partial-valid.jsonl"

        with open(session_file, "w") as f:
            # Write valid message
            f.write(json.dumps(sample_session_messages[0]) + "\n")
            # Write invalid JSON
            f.write("invalid json line\n")
            # Write another valid message
            f.write(json.dumps(sample_session_messages[1]) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        # Should parse valid messages and skip invalid ones
        assert len(sessions) == 1
        assert sessions[0].message_count == 2  # Only 2 valid messages

    def test_parse_session_content_as_list(self, temp_claude_dir):
        """Test parsing session with content as list of blocks."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)

        messages = [
            {
                "type": "user",
                "cwd": "/path/to/project",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "This is a text block"},
                        {"type": "image", "data": "..."}
                    ]
                }
            }
        ]

        session_file = project_dir / "test-uuid.jsonl"
        with open(session_file, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        assert len(sessions) == 1
        assert sessions[0].first_message == "This is a text block"

    def test_parse_session_no_cwd(self, temp_claude_dir):
        """Test parsing session without cwd field."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)

        messages = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "Test message"
                }
                # No cwd field
            }
        ]

        session_file = project_dir / "test-uuid.jsonl"
        with open(session_file, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        assert len(sessions) == 1
        assert sessions[0].project_path == "unknown"
        assert sessions[0].working_directory == "unknown"

    def test_parse_session_no_user_message(self, temp_claude_dir):
        """Test parsing session with no user messages."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)

        messages = [
            {
                "type": "assistant",
                "cwd": "/path/to/project",
                "message": {
                    "role": "assistant",
                    "content": "Assistant message"
                }
            }
        ]

        session_file = project_dir / "test-uuid.jsonl"
        with open(session_file, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        assert len(sessions) == 1
        assert sessions[0].first_message is None

    def test_parse_session_file_timestamps(self, temp_claude_dir, sample_session_messages):
        """Test that file timestamps are used for created/last_active."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)

        session_file = project_dir / "test-uuid.jsonl"
        with open(session_file, "w") as f:
            for msg in sample_session_messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        assert len(sessions) == 1
        assert isinstance(sessions[0].created, datetime)
        assert isinstance(sessions[0].last_active, datetime)
        # last_active should be >= created
        assert sessions[0].last_active >= sessions[0].created

    def test_parse_session_working_directory_extracted(self, temp_claude_dir):
        """Test that working directory is extracted from project path."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)

        messages = [
            {
                "type": "user",
                "cwd": "/home/user/my-awesome-project",
                "message": {
                    "role": "user",
                    "content": "Test"
                }
            }
        ]

        session_file = project_dir / "test-uuid.jsonl"
        with open(session_file, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        assert len(sessions) == 1
        assert sessions[0].working_directory == "my-awesome-project"

    def test_discover_sessions_skips_non_directories(self, temp_claude_dir):
        """Test that non-directory files in projects are skipped."""
        projects_dir = temp_claude_dir / "projects"

        # Create a file (not directory) in projects
        random_file = projects_dir / "not_a_directory.txt"
        random_file.write_text("random content")

        # Create a valid project directory
        project_dir = projects_dir / "valid_project"
        project_dir.mkdir()

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)

        # Should not raise an error
        sessions = discovery.discover_sessions()
        assert isinstance(sessions, list)

    def test_discover_sessions_skips_non_jsonl_files(self, temp_claude_dir, sample_session_messages):
        """Test that non-.jsonl files are skipped."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)

        # Create a .txt file (should be skipped)
        txt_file = project_dir / "not-a-session.txt"
        txt_file.write_text("text content")

        # Create a valid .jsonl file
        session_file = project_dir / "valid-session.jsonl"
        with open(session_file, "w") as f:
            for msg in sample_session_messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        # Should only find the .jsonl file
        assert len(sessions) == 1
        assert sessions[0].uuid == "valid-session"

    def test_discovered_session_dataclass(self):
        """Test DiscoveredSession dataclass attributes."""
        session = DiscoveredSession(
            uuid="test-uuid",
            project_path="/path/to/project",
            message_count=5,
            created=datetime(2026, 1, 1, 10, 0),
            last_active=datetime(2026, 1, 15, 10, 30),
            first_message="Test message",
            working_directory="project"
        )

        assert session.uuid == "test-uuid"
        assert session.project_path == "/path/to/project"
        assert session.message_count == 5
        assert session.first_message == "Test message"
        assert session.working_directory == "project"
        assert isinstance(session.created, datetime)
        assert isinstance(session.last_active, datetime)

    def test_discovered_session_optional_fields(self):
        """Test DiscoveredSession with optional fields as None."""
        session = DiscoveredSession(
            uuid="test-uuid",
            project_path="/path/to/project",
            message_count=5,
            created=datetime(2026, 1, 1, 10, 0),
            last_active=datetime(2026, 1, 15, 10, 30),
            first_message=None,
            working_directory=None
        )

        assert session.first_message is None
        assert session.working_directory is None

    def test_parse_session_stops_after_finding_data(self, temp_claude_dir):
        """Test that parsing stops after finding first message and cwd."""
        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)

        # Create many messages - parsing should stop after finding what it needs
        messages = [
            {
                "type": "user",
                "cwd": "/path/to/project",
                "message": {
                    "role": "user",
                    "content": "First message"
                }
            }
        ]
        # Add more messages
        for i in range(100):
            messages.append({
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": f"Response {i}"
                }
            })

        session_file = project_dir / "test-uuid.jsonl"
        with open(session_file, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)
        sessions = discovery.discover_sessions()

        assert len(sessions) == 1
        # Should have first message and cwd from first user message
        assert sessions[0].first_message == "First message"
        assert sessions[0].project_path == "/path/to/project"
        assert sessions[0].message_count == 101  # All messages counted

    def test_discover_sessions_parse_exception_handling(self, temp_claude_dir, sample_session_messages):
        """Test that parse exceptions are handled gracefully."""
        from unittest.mock import patch

        project_dir = temp_claude_dir / "projects" / "project1"
        project_dir.mkdir(parents=True)

        # Create a valid session file
        session_file = project_dir / "test-uuid.jsonl"
        with open(session_file, "w") as f:
            for msg in sample_session_messages:
                f.write(json.dumps(msg) + "\n")

        discovery = SessionDiscovery(claude_dir=temp_claude_dir)

        # Mock _parse_session_file to raise an exception
        with patch.object(discovery, '_parse_session_file', side_effect=Exception("Parse error")):
            # Should handle the exception and return empty list
            sessions = discovery.discover_sessions()
            assert sessions == []
