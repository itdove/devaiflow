"""Tests for Markdown export functionality."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.config.models import Session, WorkSession
from devflow.export.markdown import MarkdownExporter


@pytest.fixture
def sample_session():
    """Create a sample session for testing."""
    now = datetime.now()
    session = Session(
        name="test-session",        issue_key="PROJ-12345",
        issue_tracker="jira",
        issue_metadata={
            "summary": "Implement backup feature",
            "type": "Story",
            "status": "In Progress",
            "sprint": "2025-01",
            "points": 5,
            "epic": "PROJ-10000",
        },
        goal="Implement customer backup and restore",
        working_directory="backend-api",
        status="in_progress",
        created=now - timedelta(days=2),
        last_active=now,
        work_sessions=[
            WorkSession(
                start=now - timedelta(hours=4),
                end=now - timedelta(hours=2),
                user="test-user",
            ),
            WorkSession(
                start=now - timedelta(hours=1),
                end=now,
                user="test-user",
            ),
        ],
        tags=["backend", "api"],
    )

    # Add conversation with per-conversation data
    conv = session.add_conversation(
        working_dir="backend-api",
        ai_agent_session_id="test-uuid-123",
        project_path="/Users/test/backend-api",
        branch="feature/PROJ-12345-backup",
        workspace="workspace",
    )

    # Set message count and PRs
    conv.message_count = 42
    conv.prs = ["https://github.com/org/repo/pull/123"]

    return session


@pytest.fixture
def mock_config_loader(tmp_path):
    """Create a mock ConfigLoader."""
    mock_loader = MagicMock()
    mock_loader.get_session_dir.return_value = tmp_path / "sessions" / "test-session"
    mock_loader.get_session_dir.return_value.mkdir(parents=True, exist_ok=True)

    # Mock config with JIRA URL
    mock_config = MagicMock()
    mock_config.jira.url = "https://jira.example.com"
    mock_loader.load_config.return_value = mock_config

    return mock_loader


def test_format_title_with_jira_summary(sample_session, mock_config_loader):
    """Test title formatting with JIRA summary."""
    exporter = MarkdownExporter(mock_config_loader)
    title = exporter._format_title(sample_session)
    assert title == "Session: PROJ-12345 - Implement backup feature"


def test_format_title_with_jira_no_summary(sample_session, mock_config_loader):
    """Test title formatting with JIRA but no summary."""
    if not sample_session.issue_metadata:
        sample_session.issue_metadata = {}
    sample_session.issue_metadata.pop("summary", None)  # Remove from issue_metadata
    exporter = MarkdownExporter(mock_config_loader)
    title = exporter._format_title(sample_session)
    assert title == "Session: PROJ-12345 - Implement customer backup and restore"


def test_format_title_no_jira(sample_session, mock_config_loader):
    """Test title formatting without JIRA."""
    sample_session.issue_key = None
    if not sample_session.issue_metadata:
        sample_session.issue_metadata = {}
    sample_session.issue_metadata.pop("summary", None)
    exporter = MarkdownExporter(mock_config_loader)
    title = exporter._format_title(sample_session)
    assert title == "Session: test-session - Implement customer backup and restore"


def test_format_metadata(sample_session, mock_config_loader):
    """Test metadata formatting."""
    exporter = MarkdownExporter(mock_config_loader)
    lines = exporter._format_metadata(sample_session)

    assert "**Status:** In_Progress" in lines
    assert any("**Time Spent:**" in line for line in lines)
    assert any("**Created:**" in line for line in lines)
    assert any("**Last Active:**" in line for line in lines)
    assert "**Working Directory:** backend-api" in lines
    assert "**Git Branch:** feature/PROJ-12345-backup" in lines


def test_format_jira_section(sample_session, mock_config_loader):
    """Test JIRA section formatting."""
    exporter = MarkdownExporter(mock_config_loader)
    lines = exporter._format_jira_section(sample_session)

    assert "## Issue Tracker Ticket\n" in lines
    assert "- **Key:** [PROJ-12345](https://jira.example.com/browse/PROJ-12345)" in lines
    assert "- **Summary:** Implement backup feature" in lines
    assert "- **Type:** Story" in lines
    assert "- **Status:** In Progress" in lines
    assert "- **Sprint:** 2025-01" in lines
    assert "- **Story Points:** 5" in lines
    assert "- **Epic:** [PROJ-10000](https://jira.example.com/browse/PROJ-10000)" in lines


def test_load_progress_notes(sample_session, mock_config_loader):
    """Test loading progress notes."""
    # Create notes file
    session_dir = mock_config_loader.get_session_dir(sample_session.name)
    notes_file = session_dir / "notes.md"
    notes_content = "## Progress\n\n- 2025-01-15: Started implementation\n- 2025-01-18: Completed backend API"
    notes_file.write_text(notes_content)

    exporter = MarkdownExporter(mock_config_loader)
    notes = exporter._load_progress_notes(sample_session)

    assert notes == notes_content


def test_load_progress_notes_no_file(sample_session, mock_config_loader):
    """Test loading progress notes when file doesn't exist."""
    exporter = MarkdownExporter(mock_config_loader)
    notes = exporter._load_progress_notes(sample_session)
    assert notes is None


def test_format_duration():
    """Test duration formatting."""
    exporter = MarkdownExporter()

    # Test seconds
    assert exporter._format_duration(30) == "30s"

    # Test minutes
    assert exporter._format_duration(90) == "1m 30s"
    assert exporter._format_duration(300) == "5m"

    # Test hours
    assert exporter._format_duration(3600) == "1h"
    assert exporter._format_duration(3661) == "1h 1m"
    assert exporter._format_duration(7200) == "2h"
    assert exporter._format_duration(7380) == "2h 3m"

    # Test hours and minutes (no seconds when >= 1 hour)
    assert exporter._format_duration(9061) == "2h 31m"


def test_format_statistics(sample_session, mock_config_loader):
    """Test statistics formatting."""
    with patch("devflow.export.markdown.generate_session_summary") as mock_summary:
        # Mock session summary
        mock_summary_obj = MagicMock()
        mock_summary_obj.files_created = ["file1.py", "file2.py"]
        mock_summary_obj.files_modified = ["file3.py"]
        mock_summary_obj.commands_run = [MagicMock(), MagicMock(), MagicMock()]
        mock_summary.return_value = mock_summary_obj

        exporter = MarkdownExporter(mock_config_loader)
        stats = exporter._format_statistics(sample_session)

        assert "- **Messages:** 42" in stats
        assert "- **Work Sessions:** 2" in stats
        assert "- **Total Time:**" in stats
        assert "- **Tags:** backend, api" in stats
        assert "- **Pull Requests:** 1" in stats
        assert "https://github.com/org/repo/pull/123" in stats
        assert "- **Files Created:** 2" in stats
        assert "- **Files Modified:** 1" in stats
        assert "- **Commands Run:** 3" in stats


def test_generate_filename_with_jira(sample_session, mock_config_loader):
    """Test filename generation with issue key."""
    # Mock sessions index
    mock_config_loader.load_sessions.return_value = MagicMock()
    mock_config_loader.load_sessions.return_value.get_sessions.return_value = [sample_session]

    exporter = MarkdownExporter(mock_config_loader)
    filename = exporter._generate_filename(sample_session)
    assert filename == "PROJ-12345.md"


def test_generate_filename_without_jira(sample_session, mock_config_loader):
    """Test filename generation without issue key."""
    sample_session.issue_key = None

    # Mock sessions index
    mock_config_loader.load_sessions.return_value = MagicMock()
    mock_config_loader.load_sessions.return_value.get_sessions.return_value = [sample_session]

    exporter = MarkdownExporter(mock_config_loader)
    filename = exporter._generate_filename(sample_session)
    assert filename == "test-session.md"


def test_generate_filename_multiple_sessions(sample_session, mock_config_loader):
    """Test filename generation - single session (no suffix needed)."""
    # With session groups removed, there's only ever one session per name
    # So filename generation should use just the issue key with no suffix

    # Mock sessions index with single session
    mock_config_loader.load_sessions.return_value = MagicMock()
    mock_config_loader.load_sessions.return_value.get_sessions.return_value = [
        sample_session,
    ]

    exporter = MarkdownExporter(mock_config_loader)
    filename = exporter._generate_filename(sample_session)
    # No suffix needed since there's only one session
    assert filename == "PROJ-12345.md"


def test_export_session_to_markdown_basic(sample_session, mock_config_loader):
    """Test basic Markdown export."""
    with patch("devflow.export.markdown.generate_session_summary") as mock_summary:
        mock_summary.return_value = MagicMock(
            files_created=[],
            files_modified=[],
            commands_run=[],
            last_assistant_message=None,
            tool_call_stats={},
        )

        exporter = MarkdownExporter(mock_config_loader)
        markdown = exporter.export_session_to_markdown(sample_session)

        # Check header
        assert "# Session: PROJ-12345 - Implement backup feature" in markdown

        # Check metadata
        assert "**Status:** In_Progress" in markdown
        assert "**Time Spent:**" in markdown

        # Check goal
        assert "## Goal" in markdown
        assert "Implement customer backup and restore" in markdown

        # Check JIRA section
        assert "## Issue Tracker Ticket" in markdown
        assert "[PROJ-12345](https://jira.example.com/browse/PROJ-12345)" in markdown

        # Check statistics
        assert "## Statistics" in markdown
        assert "- **Messages:** 42" in markdown


def test_export_session_to_markdown_with_notes(sample_session, mock_config_loader):
    """Test Markdown export with progress notes."""
    # Create notes file
    session_dir = mock_config_loader.get_session_dir(sample_session.name)
    notes_file = session_dir / "notes.md"
    notes_content = "- 2025-01-15: Started implementation"
    notes_file.write_text(notes_content)

    with patch("devflow.export.markdown.generate_session_summary") as mock_summary:
        mock_summary.return_value = MagicMock(
            files_created=[],
            files_modified=[],
            commands_run=[],
            last_assistant_message=None,
            tool_call_stats={},
        )

        exporter = MarkdownExporter(mock_config_loader)
        markdown = exporter.export_session_to_markdown(sample_session)

        assert "## Progress Notes" in markdown
        assert notes_content in markdown


def test_export_sessions_to_markdown_separate_files(sample_session, mock_config_loader, tmp_path):
    """Test exporting multiple sessions to separate files."""
    # Mock sessions index
    mock_sessions_index = MagicMock()
    mock_sessions_index.get_sessions.return_value = [sample_session]
    mock_config_loader.load_sessions.return_value = mock_sessions_index

    with patch("devflow.export.markdown.generate_session_summary") as mock_summary:
        mock_summary.return_value = MagicMock(
            files_created=[],
            files_modified=[],
            commands_run=[],
            last_assistant_message=None,
            tool_call_stats={},
        )

        exporter = MarkdownExporter(mock_config_loader)
        output_dir = tmp_path / "output"
        created_files = exporter.export_sessions_to_markdown(
            identifiers=["PROJ-12345"],
            output_dir=output_dir,
        )

        assert len(created_files) == 1
        assert created_files[0].name == "PROJ-12345.md"
        assert created_files[0].exists()

        # Check content
        content = created_files[0].read_text()
        assert "# Session: PROJ-12345 - Implement backup feature" in content


def test_export_sessions_to_markdown_combined(sample_session, mock_config_loader, tmp_path):
    """Test exporting multiple sessions to a single combined file."""
    # Mock sessions index
    mock_sessions_index = MagicMock()
    mock_sessions_index.get_sessions.return_value = [sample_session]
    mock_config_loader.load_sessions.return_value = mock_sessions_index

    with patch("devflow.export.markdown.generate_session_summary") as mock_summary:
        mock_summary.return_value = MagicMock(
            files_created=[],
            files_modified=[],
            commands_run=[],
            last_assistant_message=None,
            tool_call_stats={},
        )

        exporter = MarkdownExporter(mock_config_loader)
        output_dir = tmp_path / "output"
        created_files = exporter.export_sessions_to_markdown(
            identifiers=["PROJ-12345"],
            output_dir=output_dir,
            combined=True,
        )

        assert len(created_files) == 1
        assert "sessions-export-" in created_files[0].name
        assert created_files[0].name.endswith(".md")
        assert created_files[0].exists()

        # Check content
        content = created_files[0].read_text()
        assert "# Session Export" in content
        assert "Exported 1 session(s)" in content
        assert "---" in content  # Separator
        assert "# Session: PROJ-12345 - Implement backup feature" in content


def test_export_sessions_no_sessions_found(mock_config_loader, tmp_path):
    """Test export when no sessions are found."""
    # Mock sessions index with no sessions
    mock_sessions_index = MagicMock()
    mock_sessions_index.get_sessions.return_value = []
    mock_config_loader.load_sessions.return_value = mock_sessions_index

    exporter = MarkdownExporter(mock_config_loader)
    output_dir = tmp_path / "output"

    with pytest.raises(ValueError, match="No sessions found to export"):
        exporter.export_sessions_to_markdown(
            identifiers=["NONEXISTENT"],
            output_dir=output_dir,
        )


def test_export_session_exclude_activity(sample_session, mock_config_loader):
    """Test exporting session without activity section."""
    exporter = MarkdownExporter(mock_config_loader)
    markdown = exporter.export_session_to_markdown(
        sample_session,
        include_activity=False,
    )

    assert "## Session Activity" not in markdown


def test_export_session_exclude_statistics(sample_session, mock_config_loader):
    """Test exporting session without statistics section."""
    exporter = MarkdownExporter(mock_config_loader)
    markdown = exporter.export_session_to_markdown(
        sample_session,
        include_statistics=False,
    )

    assert "## Statistics" not in markdown
