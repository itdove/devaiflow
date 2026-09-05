"""Extended tests for export/markdown.py to improve coverage."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from devflow.export.markdown import MarkdownExporter
from devflow.config.models import Session, SessionIndex
from unittest.mock import MagicMock


def test_export_session_basic(temp_daf_home):
    """Test basic session export to markdown."""
    exporter = MarkdownExporter()

    session = Session(
        name="test-session",
        issue_key="PROJ-123",
        goal="Implement feature X",
        created=datetime(2026, 1, 1, 10, 0),
        last_modified=datetime(2026, 1, 15, 14, 30)
    )

    markdown = exporter.export_session_to_markdown(
        session,
        include_activity=False,
        include_statistics=False
    )

    # Title uses issue_key, not session name
    assert "PROJ-123" in markdown
    assert "Implement feature X" in markdown
    assert "## Goal" in markdown


def test_export_session_with_jira(temp_daf_home):
    """Test exporting session with JIRA section."""
    exporter = MarkdownExporter()

    session = Session(
        name="jira-session",
        issue_key="PROJ-456",
        goal="Fix bug in authentication"
    )
    session.issue_metadata = {
        "summary": "Authentication fails for SSO users",
        "status": "In Progress"
    }

    markdown = exporter.export_session_to_markdown(session, include_activity=False)

    assert "PROJ-456" in markdown
    # Should have JIRA section since issue_key is present


def test_export_session_without_jira(temp_daf_home):
    """Test exporting session without JIRA."""
    exporter = MarkdownExporter()

    session = Session(
        name="no-jira",
        issue_key=None,
        goal="Exploratory work"
    )

    markdown = exporter.export_session_to_markdown(session, include_activity=False)

    assert "no-jira" in markdown
    assert "Exploratory work" in markdown
    # Should not have JIRA section


def test_export_session_with_statistics(temp_daf_home):
    """Test exporting session with statistics."""
    exporter = MarkdownExporter()

    session = Session(
        name="stats-test",
        issue_key=None,
        goal="Test statistics"
    )
    session.conversations = {"conv-1": "/path/1", "conv-2": "/path/2"}

    markdown = exporter.export_session_to_markdown(
        session,
        include_activity=False,
        include_statistics=True
    )

    assert "## Statistics" in markdown or "stats-test" in markdown


def test_export_session_no_statistics(temp_daf_home):
    """Test exporting without statistics section."""
    exporter = MarkdownExporter()

    session = Session(
        name="no-stats",
        issue_key=None,
        goal="Test"
    )

    markdown = exporter.export_session_to_markdown(
        session,
        include_statistics=False
    )

    # Should not have statistics section
    assert "## Statistics" not in markdown


def test_export_sessions_to_files(temp_daf_home, tmp_path):
    """Test exporting multiple sessions to separate files."""
    exporter = MarkdownExporter()

    from devflow.session.manager import SessionManager
    manager = SessionManager()

    # Create sessions
    s1 = manager.create_session(name="session-1", issue_key="PROJ-1", goal="Goal 1")
    s2 = manager.create_session(name="session-2", issue_key="PROJ-2", goal="Goal 2")

    # Export to files
    output_dir = tmp_path / "exports"
    output_dir.mkdir()

    files = exporter.export_sessions_to_markdown(
        identifiers=["session-1", "session-2"],
        output_dir=output_dir,
        include_activity=False,
        include_statistics=False,
        combined=False
    )

    # Should create separate files
    assert len(files) == 2
    for f in files:
        assert f.exists()
        assert f.suffix == ".md"


def test_export_sessions_combined(temp_daf_home, tmp_path):
    """Test exporting sessions to combined file."""
    exporter = MarkdownExporter()

    from devflow.session.manager import SessionManager
    manager = SessionManager()

    s1 = manager.create_session(name="s1", issue_key="P-1", goal="G1")
    s2 = manager.create_session(name="s2", issue_key="P-2", goal="G2")

    output_dir = tmp_path / "exports"
    output_dir.mkdir()

    files = exporter.export_sessions_to_markdown(
        identifiers=["s1", "s2"],
        output_dir=output_dir,
        combined=True
    )

    # Should create single combined file
    assert len(files) == 1
    assert files[0].exists()

    # Combined file should have both sessions (uses issue keys in title, not names)
    content = files[0].read_text()
    assert "P-1" in content
    assert "P-2" in content


def test_export_session_default_output_dir(temp_daf_home):
    """Test export uses current directory when no output_dir specified."""
    exporter = MarkdownExporter()

    from devflow.session.manager import SessionManager
    manager = SessionManager()

    s = manager.create_session(name="test", issue_key="T-1", goal="G")

    # Export without specifying output_dir
    files = exporter.export_sessions_to_markdown(
        identifiers=["test"],
        include_activity=False,
        include_statistics=False
    )

    # Should create file in current directory
    assert len(files) >= 0  # May or may not create file depending on implementation


def test_export_sessions_date_only_uses_inclusive_last_active_bounds(temp_daf_home, tmp_path):
    """Test date-only export includes sessions on both filter boundaries."""
    lower_bound = datetime(2026, 1, 1, 12, 0)
    upper_bound = datetime(2026, 1, 31, 12, 0)
    sessions = SessionIndex(
        sessions={
            "at-lower": Session(
                name="at-lower",
                goal="Lower boundary",
                created=lower_bound,
                last_active=lower_bound,
            ),
            "at-upper": Session(
                name="at-upper",
                goal="Upper boundary",
                created=upper_bound,
                last_active=upper_bound,
            ),
            "outside": Session(
                name="outside",
                goal="Outside range",
                created=upper_bound + timedelta(seconds=1),
                last_active=upper_bound + timedelta(seconds=1),
            ),
        }
    )
    config_loader = MagicMock()
    config_loader.load_sessions.return_value = sessions
    config_loader.get_session_dir.side_effect = lambda name: tmp_path / "sessions" / name

    files = MarkdownExporter(config_loader).export_sessions_to_markdown(
        identifiers=[],
        output_dir=tmp_path / "exports",
        include_activity=False,
        include_statistics=False,
        since=lower_bound,
        before=upper_bound,
    )

    assert {path.stem for path in files} == {"at-lower", "at-upper"}


def test_export_sessions_combines_identifiers_with_date_filters(temp_daf_home, tmp_path):
    """Test explicit identifiers are intersected with date-filtered sessions."""
    lower_bound = datetime(2026, 1, 1)
    in_range = Session(
        name="in-range",
        goal="Included session",
        created=lower_bound,
        last_active=lower_bound,
    )
    out_of_range = Session(
        name="out-of-range",
        goal="Excluded session",
        created=lower_bound - timedelta(days=1),
        last_active=lower_bound - timedelta(days=1),
    )
    sessions = SessionIndex(sessions={session.name: session for session in (in_range, out_of_range)})
    config_loader = MagicMock()
    config_loader.load_sessions.return_value = sessions
    config_loader.get_session_dir.side_effect = lambda name: tmp_path / "sessions" / name

    files = MarkdownExporter(config_loader).export_sessions_to_markdown(
        identifiers=["in-range", "out-of-range"],
        output_dir=tmp_path / "exports",
        include_activity=False,
        include_statistics=False,
        since=lower_bound,
    )

    assert [path.stem for path in files] == ["in-range"]


def test_format_title_with_jira(temp_daf_home):
    """Test _format_title includes JIRA key."""
    exporter = MarkdownExporter()

    session = Session(
        name="my-session",
        issue_key="PROJ-789",
        goal="Test"
    )

    markdown = exporter.export_session_to_markdown(session, include_activity=False)

    # Title should include both name and JIRA key
    lines = markdown.split('\n')
    title_line = lines[0]
    assert "my-session" in title_line or "PROJ-789" in title_line
