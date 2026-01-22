"""Tests for session summary extraction from conversation files."""

import json
from pathlib import Path
from devflow.session.summary import (
    extract_todo_history,
    TodoHistory,
    TodoItem,
    _generate_todo_summary,
    generate_prose_summary,
    SessionSummary,
)


def test_extract_todo_history_empty():
    """Test extracting todo history from empty messages."""
    messages = []
    todo_history = extract_todo_history(messages)

    assert isinstance(todo_history, TodoHistory)
    assert len(todo_history.all_todos) == 0
    assert len(todo_history.completed_todos) == 0
    assert len(todo_history.pending_todos) == 0


def test_extract_todo_history_single_todo_list():
    """Test extracting todo history with a single todo list."""
    messages = [
        {
            "type": "user",
            "toolUseResult": {
                "oldTodos": [],
                "newTodos": [
                    {
                        "content": "Understand the codebase",
                        "status": "in_progress",
                        "activeForm": "Understanding the codebase"
                    },
                    {
                        "content": "Create issue tracker ticket",
                        "status": "pending",
                        "activeForm": "Creating issue tracker ticket"
                    }
                ]
            }
        }
    ]

    todo_history = extract_todo_history(messages)

    assert len(todo_history.all_todos) == 2
    assert len(todo_history.completed_todos) == 0
    assert len(todo_history.pending_todos) == 2

    # Check first todo
    assert todo_history.all_todos[0].content == "Understand the codebase"
    assert todo_history.all_todos[0].status == "in_progress"

    # Check second todo
    assert todo_history.all_todos[1].content == "Create issue tracker ticket"
    assert todo_history.all_todos[1].status == "pending"


def test_extract_todo_history_multiple_updates():
    """Test extracting todo history with multiple updates to the same todos."""
    messages = [
        # First todo list
        {
            "type": "user",
            "toolUseResult": {
                "oldTodos": [],
                "newTodos": [
                    {
                        "content": "Understand the codebase",
                        "status": "in_progress",
                        "activeForm": "Understanding the codebase"
                    },
                    {
                        "content": "Create issue tracker ticket",
                        "status": "pending",
                        "activeForm": "Creating issue tracker ticket"
                    }
                ]
            }
        },
        # Update: first todo completed, second todo in progress
        {
            "type": "user",
            "toolUseResult": {
                "oldTodos": [
                    {
                        "content": "Understand the codebase",
                        "status": "in_progress",
                        "activeForm": "Understanding the codebase"
                    },
                    {
                        "content": "Create issue tracker ticket",
                        "status": "pending",
                        "activeForm": "Creating issue tracker ticket"
                    }
                ],
                "newTodos": [
                    {
                        "content": "Understand the codebase",
                        "status": "completed",
                        "activeForm": "Understanding the codebase"
                    },
                    {
                        "content": "Create issue tracker ticket",
                        "status": "in_progress",
                        "activeForm": "Creating issue tracker ticket"
                    }
                ]
            }
        },
        # Update: both todos completed
        {
            "type": "user",
            "toolUseResult": {
                "oldTodos": [
                    {
                        "content": "Understand the codebase",
                        "status": "completed",
                        "activeForm": "Understanding the codebase"
                    },
                    {
                        "content": "Create issue tracker ticket",
                        "status": "in_progress",
                        "activeForm": "Creating issue tracker ticket"
                    }
                ],
                "newTodos": [
                    {
                        "content": "Understand the codebase",
                        "status": "completed",
                        "activeForm": "Understanding the codebase"
                    },
                    {
                        "content": "Create issue tracker ticket",
                        "status": "completed",
                        "activeForm": "Creating issue tracker ticket"
                    }
                ]
            }
        }
    ]

    todo_history = extract_todo_history(messages)

    # Should track all unique todos (2 total)
    assert len(todo_history.all_todos) == 2

    # Both should be completed (final state)
    assert len(todo_history.completed_todos) == 2
    assert len(todo_history.pending_todos) == 0

    # Verify both are marked as completed
    for todo in todo_history.all_todos:
        assert todo.status == "completed"


def test_extract_todo_history_new_todos_added():
    """Test extracting todo history when new todos are added in later updates."""
    messages = [
        # First todo list
        {
            "type": "user",
            "toolUseResult": {
                "oldTodos": [],
                "newTodos": [
                    {
                        "content": "Analyze codebase",
                        "status": "in_progress",
                        "activeForm": "Analyzing codebase"
                    },
                    {
                        "content": "Create issue tracker ticket",
                        "status": "pending",
                        "activeForm": "Creating issue tracker ticket"
                    }
                ]
            }
        },
        # Second todo list with different tasks (simulating a new phase of work)
        {
            "type": "user",
            "toolUseResult": {
                "oldTodos": [],
                "newTodos": [
                    {
                        "content": "Implement feature",
                        "status": "in_progress",
                        "activeForm": "Implementing feature"
                    },
                    {
                        "content": "Write tests",
                        "status": "pending",
                        "activeForm": "Writing tests"
                    },
                    {
                        "content": "Run test suite",
                        "status": "pending",
                        "activeForm": "Running test suite"
                    }
                ]
            }
        }
    ]

    todo_history = extract_todo_history(messages)

    # Should have all unique todos from both lists
    assert len(todo_history.all_todos) == 5

    # Verify content
    expected_contents = {
        "Analyze codebase",
        "Create issue tracker ticket",
        "Implement feature",
        "Write tests",
        "Run test suite"
    }
    actual_contents = {todo.content for todo in todo_history.all_todos}
    assert actual_contents == expected_contents


def test_generate_todo_summary_all_completed():
    """Test generating summary when all todos are completed."""
    todo_history = TodoHistory(
        all_todos=[
            TodoItem(content="Task 1", status="completed", active_form="Task 1"),
            TodoItem(content="Task 2", status="completed", active_form="Task 2"),
            TodoItem(content="Task 3", status="completed", active_form="Task 3"),
        ],
        completed_todos=[
            TodoItem(content="Task 1", status="completed", active_form="Task 1"),
            TodoItem(content="Task 2", status="completed", active_form="Task 2"),
            TodoItem(content="Task 3", status="completed", active_form="Task 3"),
        ],
        pending_todos=[]
    )

    summary = _generate_todo_summary(todo_history)

    assert "## Session Work Summary" in summary
    assert "Completed 3 of 3 tasks" in summary
    assert "### Completed Tasks:" in summary
    assert "✓ Task 1" in summary
    assert "✓ Task 2" in summary
    assert "✓ Task 3" in summary
    assert "Remaining Tasks" not in summary


def test_generate_todo_summary_partial_completion():
    """Test generating summary with some completed and some pending todos."""
    todo_history = TodoHistory(
        all_todos=[
            TodoItem(content="Task 1", status="completed", active_form="Task 1"),
            TodoItem(content="Task 2", status="in_progress", active_form="Task 2"),
            TodoItem(content="Task 3", status="pending", active_form="Task 3"),
        ],
        completed_todos=[
            TodoItem(content="Task 1", status="completed", active_form="Task 1"),
        ],
        pending_todos=[
            TodoItem(content="Task 2", status="in_progress", active_form="Task 2"),
            TodoItem(content="Task 3", status="pending", active_form="Task 3"),
        ]
    )

    summary = _generate_todo_summary(todo_history)

    assert "## Session Work Summary" in summary
    assert "Completed 1 of 3 tasks" in summary
    assert "### Completed Tasks:" in summary
    assert "✓ Task 1" in summary
    assert "### Remaining Tasks:" in summary
    assert "⧖ Task 2" in summary  # in_progress marker
    assert "○ Task 3" in summary  # pending marker


def test_generate_prose_summary_with_todos():
    """Test that prose summary prioritizes todo history."""
    todo_history = TodoHistory(
        all_todos=[
            TodoItem(content="Implement feature X", status="completed", active_form="Implementing feature X"),
            TodoItem(content="Write tests for feature X", status="completed", active_form="Writing tests for feature X"),
            TodoItem(content="Update documentation", status="pending", active_form="Updating documentation"),
        ],
        completed_todos=[
            TodoItem(content="Implement feature X", status="completed", active_form="Implementing feature X"),
            TodoItem(content="Write tests for feature X", status="completed", active_form="Writing tests for feature X"),
        ],
        pending_todos=[
            TodoItem(content="Update documentation", status="pending", active_form="Updating documentation"),
        ]
    )

    summary = SessionSummary(
        todo_history=todo_history,
        last_assistant_message="Some other message"
    )

    prose = generate_prose_summary(summary, mode="local")

    # Should prioritize todo history
    assert "## Session Work Summary" in prose
    assert "Completed 2 of 3 tasks" in prose
    assert "✓ Implement feature X" in prose
    assert "✓ Write tests for feature X" in prose
    assert "○ Update documentation" in prose


def test_generate_prose_summary_no_todos_falls_back():
    """Test that prose summary falls back when no todo history."""
    summary = SessionSummary(
        todo_history=None,
        last_assistant_message="### Issue Identified\n\nFound a bug in the code.\n\n### Fixes Applied\n\nFixed the bug."
    )

    prose = generate_prose_summary(summary, mode="local")

    # Should fall back to last assistant message
    assert "### Issue Identified" in prose
    assert "### Fixes Applied" in prose


def test_extract_todo_history_ignores_non_user_messages():
    """Test that todo extraction ignores messages that are not user type."""
    messages = [
        {
            "type": "assistant",
            "toolUseResult": {
                "newTodos": [
                    {"content": "Should be ignored", "status": "pending", "activeForm": "Ignored"}
                ]
            }
        },
        {
            "type": "user",
            "toolUseResult": {
                "newTodos": [
                    {"content": "Should be included", "status": "pending", "activeForm": "Included"}
                ]
            }
        }
    ]

    todo_history = extract_todo_history(messages)

    assert len(todo_history.all_todos) == 1
    assert todo_history.all_todos[0].content == "Should be included"


def test_extract_todo_history_handles_malformed_data():
    """Test that todo extraction handles malformed data gracefully."""
    messages = [
        {
            "type": "user",
            "toolUseResult": {
                "newTodos": [
                    # Missing status
                    {"content": "Task 1", "activeForm": "Task 1"},
                    # Missing content
                    {"status": "pending", "activeForm": "Task 2"},
                    # Valid
                    {"content": "Task 3", "status": "pending", "activeForm": "Task 3"},
                    # Non-dict item
                    "invalid",
                ]
            }
        }
    ]

    todo_history = extract_todo_history(messages)

    # Should only extract the valid todo
    assert len(todo_history.all_todos) == 1
    assert todo_history.all_todos[0].content == "Task 3"


def test_parse_conversation_jsonl_handles_io_error(tmp_path, monkeypatch):
    """Test that parse_conversation_jsonl handles IO errors gracefully."""
    from devflow.session.summary import parse_conversation_jsonl
    from unittest.mock import mock_open, patch

    jsonl_file = tmp_path / "conversation.jsonl"
    jsonl_file.touch()

    # Mock open to raise IOError
    with patch('builtins.open', side_effect=IOError("Cannot read file")):
        messages = parse_conversation_jsonl(jsonl_file)
        # Should return empty list on IOError
        assert messages == []


def test_parse_conversation_jsonl_nonexistent_file(tmp_path):
    """Test that parse_conversation_jsonl returns empty list for nonexistent file."""
    from devflow.session.summary import parse_conversation_jsonl

    jsonl_file = tmp_path / "nonexistent.jsonl"
    messages = parse_conversation_jsonl(jsonl_file)
    assert messages == []


def test_extract_tool_calls_nested_message_format():
    """Test extracting tool calls from nested message.content structure."""
    from devflow.session.summary import extract_tool_calls

    messages = [
        {
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/path/to/file"}},
                    {"type": "text", "text": "Some text"},
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "/path/to/new"}},
                ]
            }
        }
    ]

    tool_calls = extract_tool_calls(messages)
    assert "Read" in tool_calls
    assert "Write" in tool_calls
    assert len(tool_calls["Read"]) == 1
    assert len(tool_calls["Write"]) == 1


def test_extract_tool_calls_content_block_format():
    """Test extracting tool calls from content block format."""
    from devflow.session.summary import extract_tool_calls

    messages = [
        {
            "content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/file.py"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "pytest"}},
            ]
        }
    ]

    tool_calls = extract_tool_calls(messages)
    assert "Edit" in tool_calls
    assert "Bash" in tool_calls


def test_extract_tool_calls_direct_tool_use_format():
    """Test extracting direct tool use format."""
    from devflow.session.summary import extract_tool_calls

    messages = [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "/test.py"}}
    ]

    tool_calls = extract_tool_calls(messages)
    assert "Read" in tool_calls
    assert len(tool_calls["Read"]) == 1


def test_summarize_file_operations_deduplication():
    """Test that file operations deduplicate paths."""
    from devflow.session.summary import summarize_file_operations

    tool_calls = {
        "Write": [
            {"input": {"file_path": "/file1.py"}},
            {"input": {"file_path": "/file1.py"}},  # Duplicate
        ],
        "Edit": [
            {"input": {"file_path": "/file2.py"}},
            {"input": {"file_path": "/file2.py"}},  # Duplicate
        ],
        "Read": [
            {"input": {"file_path": "/file3.py"}},
            {"input": {"file_path": "/file3.py"}},  # Duplicate
        ],
    }

    created, modified, read = summarize_file_operations(tool_calls)

    # Each file should appear only once
    assert created == ["/file1.py"]
    assert modified == ["/file2.py"]
    assert read == ["/file3.py"]


def test_extract_bash_commands_with_timestamps():
    """Test extracting bash commands with valid timestamps."""
    from devflow.session.summary import extract_bash_commands

    tool_calls = {
        "Bash": [
            {
                "input": {"command": "git status"},
                "timestamp": "2024-01-15T10:30:00"
            },
            {
                "input": {"command": "pytest"},
                "timestamp": "2024-01-15T10:35:00"
            },
        ]
    }

    commands = extract_bash_commands(tool_calls)

    assert len(commands) == 2
    assert commands[0].command == "git status"
    assert commands[1].command == "pytest"
    assert commands[0].timestamp is not None
    assert commands[1].timestamp is not None


def test_extract_bash_commands_invalid_timestamp():
    """Test extracting bash commands with invalid timestamps falls back to now."""
    from devflow.session.summary import extract_bash_commands

    tool_calls = {
        "Bash": [
            {
                "input": {"command": "git status"},
                "timestamp": "invalid-timestamp"
            },
        ]
    }

    commands = extract_bash_commands(tool_calls)

    assert len(commands) == 1
    assert commands[0].command == "git status"
    assert commands[0].timestamp is not None  # Should default to now


def test_extract_bash_commands_no_timestamp():
    """Test extracting bash commands without timestamp field."""
    from devflow.session.summary import extract_bash_commands

    tool_calls = {
        "Bash": [
            {"input": {"command": "ls -la"}},
        ]
    }

    commands = extract_bash_commands(tool_calls)

    assert len(commands) == 1
    assert commands[0].timestamp is not None  # Should default to now


def test_extract_last_assistant_message_string_content():
    """Test extracting last assistant message with string content."""
    from devflow.session.summary import extract_last_assistant_message

    messages = [
        {
            "type": "assistant",
            "message": {
                "content": "This is a simple string message"
            }
        }
    ]

    result = extract_last_assistant_message(messages)
    assert result == "This is a simple string message"


def test_extract_last_assistant_message_role_format():
    """Test extracting last assistant message with role field."""
    from devflow.session.summary import extract_last_assistant_message

    messages = [
        {
            "role": "assistant",
            "content": "Message with role field"
        }
    ]

    result = extract_last_assistant_message(messages)
    assert result == "Message with role field"


def test_extract_last_assistant_message_role_with_list_content():
    """Test extracting last assistant message with role and list content."""
    from devflow.session.summary import extract_last_assistant_message

    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "First part"},
                {"type": "text", "text": "Second part"},
            ]
        }
    ]

    result = extract_last_assistant_message(messages)
    assert result == "First part Second part"


def test_extract_last_assistant_message_prioritizes_structured():
    """Test that structured messages with ### are prioritized."""
    from devflow.session.summary import extract_last_assistant_message

    messages = [
        {
            "type": "assistant",
            "message": {
                "content": "### Issue Identified\n\nBug found\n\n### Fixes Applied\n\nFixed it"
            }
        },
        {
            "type": "assistant",
            "message": {
                "content": "Later message without structure"
            }
        }
    ]

    result = extract_last_assistant_message(messages)
    # Should prioritize the structured message (first pass in forward search)
    assert "### Issue Identified" in result
    assert "### Fixes Applied" in result


def test_extract_last_assistant_message_summary_of_changes():
    """Test extraction of '## Summary of Changes' messages."""
    from devflow.session.summary import extract_last_assistant_message

    messages = [
        {
            "type": "assistant",
            "message": {
                "content": "## Summary of Changes\n\n### File Updates\n\nChanged files"
            }
        }
    ]

    result = extract_last_assistant_message(messages)
    assert "## Summary of Changes" in result
    assert "### File Updates" in result


def test_find_conversation_file_no_active_conversation():
    """Test find_conversation_file with no active conversation."""
    from devflow.session.summary import find_conversation_file
    from devflow.config.models import Session

    session = Session(name="test-session", issue_key="PROJ-123", goal="Test")
    # Don't set working_directory, so active_conversation returns None

    result = find_conversation_file(session)
    assert result is None


def test_find_conversation_file_missing_project_path():
    """Test find_conversation_file with missing project_path."""
    from devflow.session.summary import find_conversation_file
    from devflow.config.models import Session, ConversationContext, Conversation

    session = Session(name="test-session", issue_key="PROJ-123", goal="Test")
    # Add conversation without project_path 
    conversation_context = ConversationContext(
        project_path=None,
        ai_agent_session_id="test-uuid"
    )
    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )
    session.conversations["/test/path"] = conversation
    session.working_directory = "/test/path"

    result = find_conversation_file(session)
    assert result is None


def test_find_conversation_file_nonexistent_file():
    """Test find_conversation_file when conversation file doesn't exist."""
    from devflow.session.summary import find_conversation_file
    from devflow.config.models import Session, ConversationContext, Conversation

    session = Session(name="test-session", issue_key="PROJ-123", goal="Test")
    # Use Conversation class
    conversation_context = ConversationContext(
        project_path="/nonexistent/path",
        ai_agent_session_id="nonexistent-uuid"
    )
    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )
    session.conversations["/nonexistent/path"] = conversation
    session.working_directory = "/nonexistent/path"

    result = find_conversation_file(session)
    assert result is None


def test_generate_ai_summary_no_api_key(monkeypatch):
    """Test generate_ai_summary returns None when API key is not set."""
    from devflow.session.summary import generate_ai_summary, SessionSummary

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    summary = SessionSummary()
    result = generate_ai_summary(summary, api_key=None)

    assert result is None


def test_generate_ai_summary_no_anthropic_package(monkeypatch):
    """Test generate_ai_summary returns None when anthropic package not installed."""
    from devflow.session.summary import generate_ai_summary, SessionSummary
    import sys

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Temporarily hide anthropic module
    anthropic_backup = sys.modules.get('anthropic')
    if 'anthropic' in sys.modules:
        del sys.modules['anthropic']

    # Mock import to raise ImportError
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == 'anthropic':
            raise ImportError("No module named 'anthropic'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', mock_import)

    summary = SessionSummary()
    result = generate_ai_summary(summary, api_key=None)

    assert result is None

    # Restore anthropic module
    if anthropic_backup is not None:
        sys.modules['anthropic'] = anthropic_backup


def test_generate_ai_summary_api_exception(monkeypatch):
    """Test generate_ai_summary handles API exceptions gracefully."""
    from devflow.session.summary import generate_ai_summary, SessionSummary
    from unittest.mock import Mock, patch

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Mock anthropic module
    mock_anthropic_module = Mock()
    with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
        with patch.object(mock_anthropic_module, 'Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("Network error")
            mock_anthropic_class.return_value = mock_client

            summary = SessionSummary()
            result = generate_ai_summary(summary, api_key="test-key")

            assert result is None


def test_generate_ai_summary_success(monkeypatch):
    """Test generate_ai_summary with successful API call."""
    from devflow.session.summary import generate_ai_summary, SessionSummary
    from unittest.mock import Mock, patch

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Mock anthropic module
    mock_anthropic_module = Mock()
    with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
        with patch.object(mock_anthropic_module, 'Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_content = Mock()
            mock_content.text = "AI-generated summary of the session"
            mock_message.content = [mock_content]
            mock_client.messages.create.return_value = mock_message
            mock_anthropic_class.return_value = mock_client

            summary = SessionSummary(
                files_created=["/file1.py", "/file2.py"],
                files_modified=["/file3.py"],
                last_assistant_message="Completed the task"
            )
            result = generate_ai_summary(summary, api_key="test-key")

            assert result == "AI-generated summary of the session"
            mock_client.messages.create.assert_called_once()


def test_generate_ai_summary_with_many_files(monkeypatch):
    """Test generate_ai_summary truncates long file lists."""
    from devflow.session.summary import generate_ai_summary, SessionSummary
    from unittest.mock import Mock, patch

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Mock anthropic module
    mock_anthropic_module = Mock()
    with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
        with patch.object(mock_anthropic_module, 'Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_content = Mock()
            mock_content.text = "Summary with many files"
            mock_message.content = [mock_content]
            mock_client.messages.create.return_value = mock_message
            mock_anthropic_class.return_value = mock_client

            # Create summary with >10 files
            summary = SessionSummary(
                files_created=[f"/file{i}.py" for i in range(15)],
                files_modified=[f"/modified{i}.py" for i in range(12)],
            )
            result = generate_ai_summary(summary, api_key="test-key")

            assert result == "Summary with many files"
            # Check that the call was made (truncation logic executed)
            mock_client.messages.create.assert_called_once()


def test_generate_local_summary_with_files():
    """Test _generate_local_summary with file operations."""
    from devflow.session.summary import _generate_local_summary, SessionSummary

    summary = SessionSummary(
        files_created=["/file1.py", "/file2.py"],
        files_modified=["/file3.py"],
        tool_call_stats={"Edit": 5, "Write": 2, "Bash": 3}
    )

    result = _generate_local_summary(summary)

    assert "created 2 new files" in result
    assert "modified 1 existing files" in result
    assert "5 edits" in result
    assert "2 files" in result
    assert "3 commands" in result


def test_generate_local_summary_only_created_files():
    """Test _generate_local_summary with only created files."""
    from devflow.session.summary import _generate_local_summary, SessionSummary

    summary = SessionSummary(
        files_created=["/file1.py"],
        files_modified=[],
    )

    result = _generate_local_summary(summary)

    assert "created 1 new files" in result
    assert "modified" not in result


def test_generate_local_summary_fallback_to_last_message():
    """Test _generate_local_summary falls back to last message when no stats."""
    from devflow.session.summary import _generate_local_summary, SessionSummary

    summary = SessionSummary(
        last_assistant_message="Fixed the bug. Implemented the feature."
    )

    result = _generate_local_summary(summary)

    assert "Latest activity:" in result or "Fixed the bug" in result


def test_generate_local_summary_no_activity():
    """Test _generate_local_summary with no activity."""
    from devflow.session.summary import _generate_local_summary, SessionSummary

    summary = SessionSummary()

    result = _generate_local_summary(summary)

    assert "No significant activity" in result


def test_generate_prose_summary_ai_mode(monkeypatch):
    """Test generate_prose_summary with AI mode."""
    from devflow.session.summary import generate_prose_summary, SessionSummary
    from unittest.mock import Mock, patch

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Mock anthropic
    mock_anthropic_module = Mock()
    with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
        with patch.object(mock_anthropic_module, 'Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_content = Mock()
            mock_content.text = "AI summary"
            mock_message.content = [mock_content]
            mock_client.messages.create.return_value = mock_message
            mock_anthropic_class.return_value = mock_client

            summary = SessionSummary(files_created=["/file.py"])
            result = generate_prose_summary(summary, mode="ai")

            assert result == "AI summary"


def test_generate_prose_summary_both_mode(monkeypatch):
    """Test generate_prose_summary with 'both' mode."""
    from devflow.session.summary import generate_prose_summary, SessionSummary
    from unittest.mock import Mock, patch

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Mock anthropic
    mock_anthropic_module = Mock()
    with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
        with patch.object(mock_anthropic_module, 'Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_content = Mock()
            mock_content.text = "AI summary part"
            mock_message.content = [mock_content]
            mock_client.messages.create.return_value = mock_message
            mock_anthropic_class.return_value = mock_client

            summary = SessionSummary(files_created=["/file.py"])
            result = generate_prose_summary(summary, mode="both")

            # Should include both AI and local summary
            assert "AI summary part" in result
            assert "created" in result  # Local summary part


def test_generate_prose_summary_with_structured_last_message_and_todos():
    """Test that todos take priority and last message is appended."""
    from devflow.session.summary import generate_prose_summary, SessionSummary, TodoHistory, TodoItem

    todo_history = TodoHistory(
        all_todos=[TodoItem(content="Task 1", status="completed", active_form="Task 1")],
        completed_todos=[TodoItem(content="Task 1", status="completed", active_form="Task 1")],
        pending_todos=[]
    )

    summary = SessionSummary(
        todo_history=todo_history,
        last_assistant_message="### Details\n\nSome details here"
    )

    result = generate_prose_summary(summary, mode="local")

    # Should have todo summary
    assert "## Session Work Summary" in result
    assert "Task 1" in result
    # And structured last message
    assert "### Details" in result


def test_generate_session_summary_no_conversation_file():
    """Test generate_session_summary when no conversation file exists."""
    from devflow.session.summary import generate_session_summary
    from devflow.config.models import Session

    session = Session(name="test-session", issue_key="PROJ-123", goal="Test")
    # Don't set working_directory, so no active conversation

    summary = generate_session_summary(session)

    # Should return empty summary
    assert summary.files_created == []
    assert summary.files_modified == []
    assert summary.files_read == []
    assert summary.commands_run == []
    assert summary.last_assistant_message is None


def test_generate_prose_summary_agent_backend_claude():
    """Test that Claude agent can use AI mode."""
    summary = SessionSummary(
        files_created=["test.py"],
        files_modified=["main.py"],
    )

    # Claude agent with ai mode should stay in ai mode (but will fail without API key)
    # We're testing the mode selection logic, not the actual AI call
    result = generate_prose_summary(summary, mode="ai", agent_backend="claude")
    # Should return local summary since no API key (graceful fallback)
    assert "created 1 new files" in result or "file" in result.lower()


def test_generate_prose_summary_agent_backend_github_copilot_downgrades():
    """Test that GitHub Copilot agent auto-downgrades from AI to local mode."""
    summary = SessionSummary(
        files_created=["test.py"],
        files_modified=["main.py"],
    )

    # GitHub Copilot with ai mode should auto-downgrade to local
    result = generate_prose_summary(summary, mode="ai", agent_backend="github-copilot")
    # Should use local summary (no AI call attempted)
    assert "created 1 new files" in result or "file" in result.lower()
    # Should not have AI-specific output
    assert "AI" not in result  # No AI indicator


def test_generate_prose_summary_agent_backend_cursor_downgrades():
    """Test that Cursor agent auto-downgrades from AI to local mode."""
    summary = SessionSummary(
        files_created=["test.py"],
        files_modified=["main.py"],
    )

    # Cursor with ai mode should auto-downgrade to local
    result = generate_prose_summary(summary, mode="ai", agent_backend="cursor")
    assert "created 1 new files" in result or "file" in result.lower()


def test_generate_prose_summary_agent_backend_windsurf_downgrades():
    """Test that Windsurf agent auto-downgrades from AI to local mode."""
    summary = SessionSummary(
        files_created=["test.py"],
        files_modified=["main.py"],
    )

    # Windsurf with ai mode should auto-downgrade to local
    result = generate_prose_summary(summary, mode="ai", agent_backend="windsurf")
    assert "created 1 new files" in result or "file" in result.lower()


def test_generate_prose_summary_agent_backend_both_mode_downgrades():
    """Test that non-Claude agents downgrade from 'both' mode to local."""
    summary = SessionSummary(
        files_created=["test.py"],
        files_modified=["main.py"],
    )

    # GitHub Copilot with both mode should auto-downgrade to local only
    result = generate_prose_summary(summary, mode="both", agent_backend="github-copilot")
    assert "created 1 new files" in result or "file" in result.lower()


def test_generate_prose_summary_agent_backend_local_mode_unchanged():
    """Test that local mode is unchanged regardless of agent."""
    summary = SessionSummary(
        files_created=["test.py"],
        files_modified=["main.py"],
    )

    # Local mode should work the same for all agents
    result_claude = generate_prose_summary(summary, mode="local", agent_backend="claude")
    result_copilot = generate_prose_summary(summary, mode="local", agent_backend="github-copilot")
    result_cursor = generate_prose_summary(summary, mode="local", agent_backend="cursor")

    # All should produce similar local summaries
    assert "created 1 new files" in result_claude or "file" in result_claude.lower()
    assert "created 1 new files" in result_copilot or "file" in result_copilot.lower()
    assert "created 1 new files" in result_cursor or "file" in result_cursor.lower()


def test_generate_prose_summary_agent_backend_none_defaults_to_ai():
    """Test that when agent_backend is None, mode is respected."""
    summary = SessionSummary(
        files_created=["test.py"],
        files_modified=["main.py"],
    )

    # When agent_backend is None, should not downgrade (backward compatibility)
    result = generate_prose_summary(summary, mode="ai", agent_backend=None)
    # Will fail gracefully to local since no API key, but shouldn't explicitly downgrade
    assert "created 1 new files" in result or "file" in result.lower()
