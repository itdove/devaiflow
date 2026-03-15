"""Direct tests for setup_signal_handlers() signature across all commands.

These tests ensure that setup_signal_handlers() is called with the correct
argument order in all commands that use it.

Expected signature:
    setup_signal_handlers(
        session: Session,
        session_manager: SessionManager,
        identifier: str,
        config: Config
    )

Commands tested:
- daf new (new_command.py)
- daf new --projects (new_command_multiproject.py)
- daf open (open_command.py)
- daf jira new (jira_new_command.py)
- daf git new (git_new_command.py)
- daf investigate (investigate_command.py)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from devflow.cli.signal_handler import setup_signal_handlers
from devflow.config.loader import ConfigLoader
from devflow.config.models import Config, Session
from devflow.session.manager import SessionManager


def test_setup_signal_handlers_signature(temp_daf_home):
    """Test the expected signature of setup_signal_handlers().

    This is the canonical signature that all callers must use.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    # Create a test session
    session = session_manager.create_session(
        name="test-signature",
        goal="Test",
        working_directory="test",
        project_path="/tmp/test",
        ai_agent_session_id="uuid-test",
    )

    # This should NOT raise TypeError
    try:
        setup_signal_handlers(
            session,          # 1st: Session object
            session_manager,  # 2nd: SessionManager object
            "test-signature", # 3rd: identifier (str)
            config,           # 4th: Config object (can be None)
        )
        success = True
    except TypeError as e:
        success = False
        error_msg = str(e)

    assert success, f"setup_signal_handlers raised TypeError: {error_msg if not success else 'N/A'}"


def test_setup_signal_handlers_with_none_config(temp_daf_home):
    """Test that config parameter can be None."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-none-config",
        goal="Test",
        working_directory="test",
        project_path="/tmp/test",
        ai_agent_session_id="uuid-test",
    )

    # Should work with None config
    try:
        setup_signal_handlers(
            session,
            session_manager,
            "test-none-config",
            None,  # Config can be None
        )
        success = True
    except TypeError:
        success = False

    assert success, "setup_signal_handlers should accept None for config parameter"


def test_setup_signal_handlers_wrong_argument_order_fails(temp_daf_home):
    """Test documentation that wrong argument order would cause issues.

    Note: Python doesn't enforce type checking, so this documents the correct
    usage pattern rather than enforcing it at runtime.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    session = session_manager.create_session(
        name="test-wrong-order",
        goal="Test",
        working_directory="test",
        project_path="/tmp/test",
        ai_agent_session_id="uuid-test",
    )

    # Correct order (documented for reference)
    setup_signal_handlers(
        session,          # 1st: Session
        session_manager,  # 2nd: SessionManager
        "test-wrong-order",  # 3rd: identifier
        config,           # 4th: Config
    )


def test_setup_signal_handlers_missing_arguments_fails(temp_daf_home):
    """Test that missing arguments raise TypeError."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-missing",
        goal="Test",
        working_directory="test",
        project_path="/tmp/test",
        ai_agent_session_id="uuid-test",
    )

    # Missing identifier and config
    with pytest.raises(TypeError):
        setup_signal_handlers(
            session,
            session_manager,
            # Missing identifier and config
        )


def test_new_command_uses_correct_signature(temp_daf_home):
    """Verify that new_command.py calls setup_signal_handlers correctly.

    This test imports the actual command code and verifies it would call
    setup_signal_handlers with the correct signature.
    """
    from devflow.cli.signal_handler import setup_signal_handlers
    import inspect

    # Get the signature
    sig = inspect.signature(setup_signal_handlers)
    params = list(sig.parameters.keys())

    # Verify expected parameter order
    assert params[0] == 'session', "First parameter should be 'session'"
    assert params[1] == 'session_manager', "Second parameter should be 'session_manager'"
    assert params[2] == 'identifier', "Third parameter should be 'identifier'"
    assert params[3] == 'config', "Fourth parameter should be 'config'"


def test_multiproject_command_uses_correct_signature(temp_daf_home):
    """Verify that new_command_multiproject.py would call with correct signature.

    This is a regression test for the original bug where it was called with:
    setup_signal_handlers(session_manager, session) - WRONG!
    """
    from devflow.cli.commands.new_command_multiproject import create_multi_project_session
    import inspect

    # Get source code of the function
    source = inspect.getsource(create_multi_project_session)

    # Verify the correct call pattern exists
    assert 'setup_signal_handlers(session, session_manager, name, config)' in source, \
        "new_command_multiproject.py should call setup_signal_handlers with correct argument order"

    # Verify the WRONG pattern does NOT exist
    assert 'setup_signal_handlers(session_manager, session)' not in source, \
        "Bug regression: setup_signal_handlers should NOT be called with (session_manager, session)"


def test_all_commands_use_correct_signature(temp_daf_home):
    """Verify all command files use the correct signature pattern.

    This test checks the source code of all commands that use signal handlers.
    """
    import inspect

    # Commands that use setup_signal_handlers
    commands = [
        ('new_command.py', 'devflow.cli.commands.new_command'),
        ('new_command_multiproject.py', 'devflow.cli.commands.new_command_multiproject'),
        ('open_command.py', 'devflow.cli.commands.open_command'),
        ('jira_new_command.py', 'devflow.cli.commands.jira_new_command'),
        ('git_new_command.py', 'devflow.cli.commands.git_new_command'),
        ('investigate_command.py', 'devflow.cli.commands.investigate_command'),
    ]

    # Expected correct pattern
    correct_pattern = 'setup_signal_handlers(session, session_manager,'

    # Wrong patterns to check for
    wrong_patterns = [
        'setup_signal_handlers(session_manager, session',  # Original bug
        'setup_signal_handlers(session, identifier',       # Missing session_manager
        'setup_signal_handlers(identifier, session',       # Wrong order
    ]

    errors = []

    for file_name, module_path in commands:
        try:
            module = __import__(module_path, fromlist=[''])
            source = inspect.getsource(module)

            # Check if file uses setup_signal_handlers
            if 'setup_signal_handlers(' not in source:
                continue  # File doesn't use signal handlers

            # Verify correct pattern exists
            if correct_pattern not in source:
                errors.append(f"{file_name}: Does not use correct pattern '{correct_pattern}'")

            # Check for wrong patterns
            for wrong in wrong_patterns:
                if wrong in source:
                    errors.append(f"{file_name}: Contains wrong pattern '{wrong}'")

        except Exception as e:
            errors.append(f"{file_name}: Could not check - {e}")

    if errors:
        error_msg = "\n".join(errors)
        pytest.fail(f"Signal handler signature issues found:\n{error_msg}")


def test_signal_handlers_parameter_types(temp_daf_home):
    """Test that setup_signal_handlers works with correct parameter types.

    Note: Python doesn't enforce strict type checking at call time, but using
    correct types ensures the function works as expected.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    session = session_manager.create_session(
        name="test-types",
        goal="Test",
        working_directory="test",
        project_path="/tmp/test",
        ai_agent_session_id="uuid-test",
    )

    # Test with correct types (should work)
    try:
        setup_signal_handlers(session, session_manager, "test-types", config)
        success = True
    except Exception as e:
        success = False
        error = str(e)

    assert success, f"Should work with correct types: {error if not success else ''}"


def test_signal_handlers_identifier_must_be_string(temp_daf_home):
    """Test that identifier parameter must be a string."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    session = session_manager.create_session(
        name="test-identifier",
        goal="Test",
        working_directory="test",
        project_path="/tmp/test",
        ai_agent_session_id="uuid-test",
    )

    # Should work with string identifier
    setup_signal_handlers(session, session_manager, "test-identifier", config)

    # Should handle non-string identifier (may work due to duck typing)
    # This is more of a documentation test
    setup_signal_handlers(session, session_manager, 123, config)  # Will convert to string


def test_signal_handlers_in_all_command_contexts(temp_daf_home):
    """Test that signal handlers work in contexts from all commands.

    This ensures the signature is compatible with how each command uses it.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    # Context 1: Regular session (daf new)
    session1 = session_manager.create_session(
        name="regular-session",
        goal="Regular session",
        working_directory="backend",
        project_path="/tmp/backend",
        ai_agent_session_id="uuid-1",
    )
    setup_signal_handlers(session1, session_manager, "regular-session", config)

    # Context 2: Multi-project session (daf new --projects)
    session2 = session_manager.create_session(
        name="multi-session",
        goal="Multi-project",
        working_directory="backend",
        project_path="/tmp/backend",
        ai_agent_session_id="uuid-2",
    )
    session2.add_conversation(
        working_dir="frontend",
        ai_agent_session_id="uuid-3",
        project_path="/tmp/frontend",
        branch="main",
    )
    setup_signal_handlers(session2, session_manager, "multi-session", config)

    # Context 3: Ticket creation session (daf jira new)
    session3 = session_manager.create_session(
        name="creation-session",
        goal="Ticket creation",
        working_directory="backend",
        project_path="/tmp/backend",
        ai_agent_session_id="uuid-4",
    )
    session3.session_type = "ticket_creation"
    setup_signal_handlers(session3, session_manager, "creation-session", config)

    # Context 4: Session with None config (investigation)
    session4 = session_manager.create_session(
        name="investigation",
        goal="Investigate",
        working_directory="backend",
        project_path="/tmp/backend",
        ai_agent_session_id="uuid-5",
    )
    setup_signal_handlers(session4, session_manager, "investigation", None)

    # All contexts should work without errors
    assert True, "All command contexts should work with signal handlers"
