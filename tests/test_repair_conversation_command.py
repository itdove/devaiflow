"""Tests for daf repair-conversation command."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from devflow.cli.commands.repair_conversation_command import (
    repair_conversation,
    _repair_single_conversation,
)
from devflow.session.repair import ConversationRepairError


@pytest.fixture
def mock_session():
    """Create a mock session."""
    session = Mock()
    session.name = "test-session"
    session.issue_key = "PROJ-12345"
    session.working_directory = "/path/to/project"
    session.last_active = datetime(2026, 1, 15, 10, 30)
    session.created = datetime(2026, 1, 1, 10, 0)

    # Mock conversation context
    conversation_ctx = Mock()
    conversation_ctx.ai_agent_session_id = "test-uuid-1234"
    conversation_ctx.project_path = "/path/to/project"

    # Mock Conversation object with active_session and archived_sessions
    conversation = Mock()
    conversation.active_session = conversation_ctx
    conversation.archived_sessions = []
    conversation.get_all_sessions = Mock(return_value=[conversation_ctx])

    session.conversations = {
        "/path/to/project#1": conversation
    }

    return session


@pytest.fixture
def mock_corruption_info():
    """Create mock corruption info."""
    return {
        'is_corrupt': True,
        'issues': ['Invalid JSON on line 10', 'Content too large on line 20'],
        'invalid_lines': [(10, 'JSON decode error'), (15, 'Missing comma')],
        'truncation_needed': [(20, 100000, 'content')],
    }


@pytest.fixture
def mock_repair_result():
    """Create mock repair result."""
    return {
        'success': True,
        'lines_repaired': 5,
        'backup_path': Path('/tmp/backup.jsonl'),
        'truncations': [(20, 100000, 50000)],
        'errors_fixed': ['Line 10', 'Line 15'],
        'total_lines': 100,
    }


class TestRepairConversation:
    """Tests for repair_conversation function."""

    def test_check_all_no_corruption(self, monkeypatch):
        """Test --check-all flag when no corruption found."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader'):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager'):
                with patch('devflow.cli.commands.repair_conversation_command.scan_all_conversations') as mock_scan:
                    mock_scan.return_value = []

                    repair_conversation(
                        identifier=None,
                        conversation_id=None,
                        max_size=100000,
                        check_all=True,
                        repair_all=False,
                        dry_run=False
                    )

                    mock_scan.assert_called_once()

    def test_check_all_with_corruption(self, monkeypatch, mock_corruption_info):
        """Test --check-all flag when corruption is found."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        corrupted_files = [
            ("uuid-1", Path("/path/to/conv1.jsonl"), mock_corruption_info),
            ("uuid-2", Path("/path/to/conv2.jsonl"), mock_corruption_info),
        ]

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader'):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager'):
                with patch('devflow.cli.commands.repair_conversation_command.scan_all_conversations') as mock_scan:
                    mock_scan.return_value = corrupted_files

                    repair_conversation(
                        identifier=None,
                        conversation_id=None,
                        max_size=100000,
                        check_all=True,
                        repair_all=False,
                        dry_run=False
                    )

    def test_repair_all_no_corruption(self, monkeypatch):
        """Test --all flag when no corruption found."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader'):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager'):
                with patch('devflow.cli.commands.repair_conversation_command.scan_all_conversations') as mock_scan:
                    mock_scan.return_value = []

                    repair_conversation(
                        identifier=None,
                        conversation_id=None,
                        max_size=100000,
                        check_all=False,
                        repair_all=True,
                        dry_run=False
                    )

    def test_repair_all_with_confirmation_cancel(self, monkeypatch, mock_corruption_info):
        """Test --all flag when user cancels repair."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        corrupted_files = [("uuid-1", Path("/path/to/conv1.jsonl"), mock_corruption_info)]

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader'):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager'):
                with patch('devflow.cli.commands.repair_conversation_command.scan_all_conversations') as mock_scan:
                    with patch('devflow.cli.commands.repair_conversation_command.Confirm.ask') as mock_confirm:
                        mock_scan.return_value = corrupted_files
                        mock_confirm.return_value = False

                        repair_conversation(
                            identifier=None,
                            conversation_id=None,
                            max_size=100000,
                            check_all=False,
                            repair_all=True,
                            dry_run=False
                        )

    def test_repair_all_with_confirmation_accept(self, monkeypatch, mock_corruption_info, mock_repair_result):
        """Test --all flag when user accepts repair."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        corrupted_files = [("uuid-1", Path("/path/to/conv1.jsonl"), mock_corruption_info)]

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader'):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager'):
                with patch('devflow.cli.commands.repair_conversation_command.scan_all_conversations') as mock_scan:
                    with patch('devflow.cli.commands.repair_conversation_command.Confirm.ask') as mock_confirm:
                        with patch('devflow.cli.commands.repair_conversation_command.repair_conversation_file') as mock_repair:
                            mock_scan.return_value = corrupted_files
                            mock_confirm.return_value = True
                            mock_repair.return_value = mock_repair_result

                            repair_conversation(
                                identifier=None,
                                conversation_id=None,
                                max_size=100000,
                                check_all=False,
                                repair_all=True,
                                dry_run=False
                            )

    def test_repair_all_dry_run(self, monkeypatch, mock_corruption_info):
        """Test --all flag with --dry-run."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        corrupted_files = [("uuid-1", Path("/path/to/conv1.jsonl"), mock_corruption_info)]

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader'):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager'):
                with patch('devflow.cli.commands.repair_conversation_command.scan_all_conversations') as mock_scan:
                    with patch('devflow.cli.commands.repair_conversation_command.repair_conversation_file') as mock_repair:
                        mock_scan.return_value = corrupted_files
                        mock_repair.return_value = {'success': True, 'lines_repaired': 5}

                        repair_conversation(
                            identifier=None,
                            conversation_id=None,
                            max_size=100000,
                            check_all=False,
                            repair_all=True,
                            dry_run=True
                        )

    def test_repair_all_handles_error(self, monkeypatch, mock_corruption_info):
        """Test --all flag handles repair errors gracefully."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        corrupted_files = [("uuid-1", Path("/path/to/conv1.jsonl"), mock_corruption_info)]

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader'):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager'):
                with patch('devflow.cli.commands.repair_conversation_command.scan_all_conversations') as mock_scan:
                    with patch('devflow.cli.commands.repair_conversation_command.repair_conversation_file') as mock_repair:
                        mock_scan.return_value = corrupted_files
                        mock_repair.side_effect = ConversationRepairError("Repair failed")

                        repair_conversation(
                            identifier=None,
                            conversation_id=None,
                            max_size=100000,
                            check_all=False,
                            repair_all=True,
                            dry_run=True
                        )

    def test_latest_flag_no_sessions(self, monkeypatch):
        """Test --latest flag when no sessions exist."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        mock_loader = Mock()
        mock_manager = Mock()
        mock_manager.list_sessions.return_value = []

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager', return_value=mock_manager):
                repair_conversation(
                    identifier=None,
                    conversation_id=None,
                    max_size=100000,
                    check_all=False,
                    repair_all=False,
                    dry_run=False,
                    latest=True
                )

    def test_latest_flag_with_sessions(self, monkeypatch, mock_session):
        """Test --latest flag selects most recent session."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        older_session = Mock()
        older_session.name = "old-session"
        older_session.last_active = datetime(2026, 1, 1, 10, 0)
        older_session.created = datetime(2025, 12, 1, 10, 0)
        older_session.conversations = {}

        mock_loader = Mock()
        mock_manager = Mock()
        mock_manager.list_sessions.return_value = [older_session, mock_session]
        mock_manager.get_session.return_value = mock_session

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager', return_value=mock_manager):
                with patch('devflow.cli.commands.repair_conversation_command._repair_single_conversation'):
                    repair_conversation(
                        identifier=None,
                        conversation_id=None,
                        max_size=100000,
                        check_all=False,
                        repair_all=False,
                        dry_run=False,
                        latest=True
                    )

    def test_no_identifier_shows_help(self, monkeypatch):
        """Test that missing identifier shows help message."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader'):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager'):
                repair_conversation(
                    identifier=None,
                    conversation_id=None,
                    max_size=100000,
                    check_all=False,
                    repair_all=False,
                    dry_run=False
                )

    def test_session_found_by_name(self, monkeypatch, mock_session):
        """Test repair when session is found by name."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        mock_loader = Mock()
        mock_manager = Mock()
        mock_manager.get_session.return_value = mock_session

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager', return_value=mock_manager):
                with patch('devflow.cli.commands.repair_conversation_command._repair_single_conversation') as mock_repair:
                    repair_conversation(
                        identifier="test-session",
                        conversation_id=None,
                        max_size=100000,
                        check_all=False,
                        repair_all=False,
                        dry_run=False
                    )

                    mock_repair.assert_called_once()

    def test_session_no_conversations(self, monkeypatch, mock_session):
        """Test repair when session has no conversations."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        mock_session.conversations = {}

        mock_loader = Mock()
        mock_manager = Mock()
        mock_manager.get_session.return_value = mock_session

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager', return_value=mock_manager):
                repair_conversation(
                    identifier="test-session",
                    conversation_id=None,
                    max_size=100000,
                    check_all=False,
                    repair_all=False,
                    dry_run=False
                )

    def test_specific_conversation_not_found(self, monkeypatch, mock_session):
        """Test repair when specific conversation ID not found."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        mock_loader = Mock()
        mock_manager = Mock()
        mock_manager.get_session.return_value = mock_session

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager', return_value=mock_manager):
                repair_conversation(
                    identifier="test-session",
                    conversation_id=999,  # Non-existent conversation ID
                    max_size=100000,
                    check_all=False,
                    repair_all=False,
                    dry_run=False
                )

    def test_specific_conversation_found(self, monkeypatch, mock_session):
        """Test repair of specific conversation by ID."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        mock_loader = Mock()
        mock_manager = Mock()
        mock_manager.get_session.return_value = mock_session

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager', return_value=mock_manager):
                with patch('devflow.cli.commands.repair_conversation_command._repair_single_conversation') as mock_repair:
                    repair_conversation(
                        identifier="test-session",
                        conversation_id=1,
                        max_size=100000,
                        check_all=False,
                        repair_all=False,
                        dry_run=False
                    )

                    mock_repair.assert_called_once_with("test-uuid-1234", 100000, False)

    def test_repair_all_conversations_in_session(self, monkeypatch, mock_session):
        """Test repairing all conversations in a session."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        # Add another conversation context
        conversation_ctx2 = Mock()
        conversation_ctx2.ai_agent_session_id = "test-uuid-5678"
        conversation_ctx2.project_path = "/path/to/project2"

        # Wrap in Conversation object
        conversation2 = Mock()
        conversation2.active_session = conversation_ctx2
        conversation2.archived_sessions = []
        conversation2.get_all_sessions = Mock(return_value=[conversation_ctx2])

        mock_session.conversations["/path/to/project#2"] = conversation2

        mock_loader = Mock()
        mock_manager = Mock()
        mock_manager.get_session.return_value = mock_session

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager', return_value=mock_manager):
                with patch('devflow.cli.commands.repair_conversation_command._repair_single_conversation') as mock_repair:
                    repair_conversation(
                        identifier="test-session",
                        conversation_id=None,
                        max_size=100000,
                        check_all=False,
                        repair_all=False,
                        dry_run=False
                    )

                    # Should repair both conversations
                    assert mock_repair.call_count == 2

    def test_direct_uuid_not_found_as_session(self, monkeypatch):
        """Test using a direct UUID when not found as session."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        mock_loader = Mock()
        mock_manager = Mock()
        mock_manager.get_session.return_value = None

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager', return_value=mock_manager):
                with patch('devflow.cli.commands.repair_conversation_command.is_valid_uuid') as mock_is_valid:
                    with patch('devflow.cli.commands.repair_conversation_command._repair_single_conversation') as mock_repair:
                        mock_is_valid.return_value = True

                        repair_conversation(
                            identifier="f545206f-480f-4c2d-8823-c6643f0e693d",
                            conversation_id=None,
                            max_size=100000,
                            check_all=False,
                            repair_all=False,
                            dry_run=False
                        )

                        mock_repair.assert_called_once()

    def test_invalid_identifier_not_session_not_uuid(self, monkeypatch):
        """Test error when identifier is neither session nor valid UUID."""
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        mock_loader = Mock()
        mock_manager = Mock()
        mock_manager.get_session.return_value = None

        with patch('devflow.cli.commands.repair_conversation_command.ConfigLoader', return_value=mock_loader):
            with patch('devflow.cli.commands.repair_conversation_command.SessionManager', return_value=mock_manager):
                with patch('devflow.cli.commands.repair_conversation_command.is_valid_uuid') as mock_is_valid:
                    mock_is_valid.return_value = False

                    repair_conversation(
                        identifier="invalid-session",
                        conversation_id=None,
                        max_size=100000,
                        check_all=False,
                        repair_all=False,
                        dry_run=False
                    )


class TestRepairSingleConversation:
    """Tests for _repair_single_conversation function."""

    def test_conversation_file_not_found(self):
        """Test when conversation file doesn't exist."""
        with patch('devflow.cli.commands.repair_conversation_command.get_conversation_file_path') as mock_get_path:
            mock_get_path.return_value = None

            _repair_single_conversation("test-uuid", 100000, False)

    def test_no_corruption_detected(self):
        """Test when no corruption is detected."""
        conv_file = Path("/path/to/conv.jsonl")

        with patch('devflow.cli.commands.repair_conversation_command.get_conversation_file_path') as mock_get_path:
            with patch('devflow.cli.commands.repair_conversation_command.detect_corruption') as mock_detect:
                mock_get_path.return_value = conv_file
                mock_detect.return_value = {'is_corrupt': False}

                _repair_single_conversation("test-uuid", 100000, False)

    def test_corruption_detected_dry_run(self, mock_corruption_info):
        """Test corruption detected in dry-run mode."""
        conv_file = Path("/path/to/conv.jsonl")

        with patch('devflow.cli.commands.repair_conversation_command.get_conversation_file_path') as mock_get_path:
            with patch('devflow.cli.commands.repair_conversation_command.detect_corruption') as mock_detect:
                mock_get_path.return_value = conv_file
                mock_detect.return_value = mock_corruption_info

                _repair_single_conversation("test-uuid", 100000, True)

    def test_successful_repair(self, mock_corruption_info, mock_repair_result):
        """Test successful repair of corrupted conversation."""
        conv_file = Path("/path/to/conv.jsonl")

        with patch('devflow.cli.commands.repair_conversation_command.get_conversation_file_path') as mock_get_path:
            with patch('devflow.cli.commands.repair_conversation_command.detect_corruption') as mock_detect:
                with patch('devflow.cli.commands.repair_conversation_command.repair_conversation_file') as mock_repair:
                    mock_get_path.return_value = conv_file
                    mock_detect.return_value = mock_corruption_info
                    mock_repair.return_value = mock_repair_result

                    _repair_single_conversation("test-uuid", 100000, False)

    def test_repair_no_changes_needed(self, mock_corruption_info):
        """Test repair when no changes are needed."""
        conv_file = Path("/path/to/conv.jsonl")

        with patch('devflow.cli.commands.repair_conversation_command.get_conversation_file_path') as mock_get_path:
            with patch('devflow.cli.commands.repair_conversation_command.detect_corruption') as mock_detect:
                with patch('devflow.cli.commands.repair_conversation_command.repair_conversation_file') as mock_repair:
                    mock_get_path.return_value = conv_file
                    mock_detect.return_value = mock_corruption_info
                    mock_repair.return_value = {'success': False, 'message': 'No changes needed'}

                    _repair_single_conversation("test-uuid", 100000, False)

    def test_repair_raises_error(self, mock_corruption_info):
        """Test repair when an error occurs."""
        conv_file = Path("/path/to/conv.jsonl")

        with patch('devflow.cli.commands.repair_conversation_command.get_conversation_file_path') as mock_get_path:
            with patch('devflow.cli.commands.repair_conversation_command.detect_corruption') as mock_detect:
                with patch('devflow.cli.commands.repair_conversation_command.repair_conversation_file') as mock_repair:
                    mock_get_path.return_value = conv_file
                    mock_detect.return_value = mock_corruption_info
                    mock_repair.side_effect = ConversationRepairError("Repair failed")

                    _repair_single_conversation("test-uuid", 100000, False)

    def test_shows_limited_invalid_lines(self):
        """Test that only first 5 invalid lines are shown."""
        conv_file = Path("/path/to/conv.jsonl")

        corruption_info = {
            'is_corrupt': True,
            'issues': ['Many errors'],
            'invalid_lines': [(i, f'Error {i}') for i in range(10)],  # 10 errors
            'truncation_needed': [],
        }

        with patch('devflow.cli.commands.repair_conversation_command.get_conversation_file_path') as mock_get_path:
            with patch('devflow.cli.commands.repair_conversation_command.detect_corruption') as mock_detect:
                mock_get_path.return_value = conv_file
                mock_detect.return_value = corruption_info

                _repair_single_conversation("test-uuid", 100000, True)

    def test_shows_limited_truncations(self):
        """Test that only first 5 truncations are shown."""
        conv_file = Path("/path/to/conv.jsonl")

        corruption_info = {
            'is_corrupt': True,
            'issues': ['Large content'],
            'invalid_lines': [],
            'truncation_needed': [(i, 100000, 'content') for i in range(10)],  # 10 truncations
        }

        with patch('devflow.cli.commands.repair_conversation_command.get_conversation_file_path') as mock_get_path:
            with patch('devflow.cli.commands.repair_conversation_command.detect_corruption') as mock_detect:
                mock_get_path.return_value = conv_file
                mock_detect.return_value = corruption_info

                _repair_single_conversation("test-uuid", 100000, True)
