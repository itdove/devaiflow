"""Extended tests for session/summary.py to improve coverage."""

import pytest
from devflow.session.summary import extract_last_assistant_message


def test_extract_last_assistant_message_direct_format():
    """Test extracting from direct format messages."""
    messages = [
        {"role": "user", "content": "Question"},
        {"role": "assistant", "content": "Direct response"},
    ]

    result = extract_last_assistant_message(messages)
    assert result == "Direct response"


def test_extract_last_assistant_message_list_content():
    """Test extracting when content is a list of blocks."""
    messages = [{
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Part 1"},
            {"type": "text", "text": "Part 2"},
        ]
    }]

    result = extract_last_assistant_message(messages)
    assert result == "Part 1 Part 2"


def test_extract_last_assistant_message_empty_list():
    """Test with empty message list."""
    result = extract_last_assistant_message([])
    assert result is None


def test_extract_last_assistant_message_no_assistant():
    """Test when no assistant messages exist."""
    messages = [
        {"role": "user", "content": "Question 1"},
        {"role": "user", "content": "Question 2"},
    ]

    result = extract_last_assistant_message(messages)
    assert result is None


def test_extract_last_assistant_message_returns_last():
    """Test that it returns the last assistant message."""
    messages = [
        {"role": "assistant", "content": "First response"},
        {"role": "user", "content": "Follow-up"},
        {"role": "assistant", "content": "Last response"},
    ]

    result = extract_last_assistant_message(messages)
    assert result == "Last response"
