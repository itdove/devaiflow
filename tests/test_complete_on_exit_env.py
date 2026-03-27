"""Test that daf complete works after agent exits by properly managing environment variables."""
import os
import pytest
from unittest.mock import Mock, patch


def test_prompt_for_complete_unsets_session_env_vars(temp_daf_home, monkeypatch):
    """Test that _prompt_for_complete_on_exit unsets DEVAIFLOW_IN_SESSION before calling complete_session.

    This test verifies the fix for the bug where 'daf complete' would fail after the agent
    exits because DEVAIFLOW_IN_SESSION was still set in the parent process.
    """
    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit

    # Set up environment as if we're inside an AI session
    monkeypatch.setenv("DEVAIFLOW_IN_SESSION", "1")
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-session-id")

    # Mock session
    session = Mock()
    session.name = "test-session"

    # Mock config to auto-complete
    config = Mock()
    config.prompts = Mock()
    config.prompts.auto_complete_on_exit = True

    # Track environment variables during complete_session call
    env_during_complete = {}

    def mock_complete_session(**kwargs):
        # Capture environment variables when complete_session is called
        env_during_complete['DEVAIFLOW_IN_SESSION'] = os.environ.get('DEVAIFLOW_IN_SESSION')
        env_during_complete['AI_AGENT_SESSION_ID'] = os.environ.get('AI_AGENT_SESSION_ID')

    # Patch complete_session where it's imported
    with patch('devflow.cli.commands.complete_command.complete_session', side_effect=mock_complete_session):
        _prompt_for_complete_on_exit(session, config)

    # Verify environment variables were unset during complete_session call
    assert env_during_complete['DEVAIFLOW_IN_SESSION'] is None, \
        "DEVAIFLOW_IN_SESSION should be unset when calling complete_session"
    assert env_during_complete['AI_AGENT_SESSION_ID'] is None, \
        "AI_AGENT_SESSION_ID should be unset when calling complete_session"

    # Verify environment variables were restored after
    assert os.environ.get('DEVAIFLOW_IN_SESSION') == "1", \
        "DEVAIFLOW_IN_SESSION should be restored after complete_session"
    assert os.environ.get('AI_AGENT_SESSION_ID') == "test-session-id", \
        "AI_AGENT_SESSION_ID should be restored after complete_session"


def test_prompt_for_complete_handles_missing_env_vars(temp_daf_home, monkeypatch):
    """Test that function works correctly when env vars are not set."""
    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit

    # Ensure env vars are not set
    monkeypatch.delenv("DEVAIFLOW_IN_SESSION", raising=False)
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    # Mock session
    session = Mock()
    session.name = "test-session"

    # Mock config to auto-complete
    config = Mock()
    config.prompts = Mock()
    config.prompts.auto_complete_on_exit = True

    # Mock complete_session
    with patch('devflow.cli.commands.complete_command.complete_session'):
        _prompt_for_complete_on_exit(session, config)

    # Verify env vars are still not set after
    assert os.environ.get('DEVAIFLOW_IN_SESSION') is None
    assert os.environ.get('AI_AGENT_SESSION_ID') is None


def test_prompt_for_complete_restores_env_on_exception(temp_daf_home, monkeypatch):
    """Test that environment variables are restored even if complete_session raises an exception."""
    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit

    # Set up environment as if we're inside an AI session
    monkeypatch.setenv("DEVAIFLOW_IN_SESSION", "1")
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "test-session-id")

    # Mock session
    session = Mock()
    session.name = "test-session"

    # Mock config to auto-complete
    config = Mock()
    config.prompts = Mock()
    config.prompts.auto_complete_on_exit = True

    # Mock complete_session to raise exception
    with patch('devflow.cli.commands.complete_command.complete_session', side_effect=Exception("Test error")):
        with patch('rich.console.Console.print'):  # Suppress error output
            _prompt_for_complete_on_exit(session, config)

    # Verify environment variables were restored even after exception
    assert os.environ.get('DEVAIFLOW_IN_SESSION') == "1", \
        "DEVAIFLOW_IN_SESSION should be restored after exception"
    assert os.environ.get('AI_AGENT_SESSION_ID') == "test-session-id", \
        "AI_AGENT_SESSION_ID should be restored after exception"
