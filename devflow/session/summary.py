"""Session summary extraction from Claude Code conversation files."""

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

from devflow.config.models import Session


class CommandExecution(BaseModel):
    """Represents a command execution from the session."""

    command: str
    exit_code: Optional[int] = None
    timestamp: datetime
    output_summary: Optional[str] = None


class TodoItem(BaseModel):
    """Represents a todo item from TodoWrite tool."""

    content: str
    status: str  # "pending", "in_progress", "completed"
    active_form: str


class TodoHistory(BaseModel):
    """Represents the history of todos throughout a session."""

    all_todos: List[TodoItem] = []
    completed_todos: List[TodoItem] = []
    pending_todos: List[TodoItem] = []


class SessionSummary(BaseModel):
    """Summary of session activity extracted from conversation."""

    files_created: List[str] = []
    files_modified: List[str] = []
    files_read: List[str] = []
    commands_run: List[CommandExecution] = []
    last_assistant_message: Optional[str] = None
    tool_call_stats: Dict[str, int] = {}
    todo_history: Optional[TodoHistory] = None


def parse_conversation_jsonl(jsonl_path: Path) -> List[Dict]:
    """Parse .jsonl conversation file.

    Each line is a JSON object with:
    - type: "user" | "assistant" | "tool_call" | "tool_result"
    - content: message or tool parameters
    - timestamp: ISO datetime

    Args:
        jsonl_path: Path to the .jsonl conversation file

    Returns:
        List of parsed message dictionaries
    """
    messages = []
    if not jsonl_path.exists():
        return messages

    try:
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
    except (json.JSONDecodeError, IOError) as e:
        # If we can't parse the file, return empty list
        # The summary will just be empty
        pass

    return messages


def extract_tool_calls(messages: List[Dict]) -> Dict[str, List[Dict]]:
    """Group tool calls by type (Read, Write, Edit, Bash).

    Args:
        messages: List of parsed messages

    Returns:
        Dictionary mapping tool name to list of tool call messages
    """
    tool_calls = defaultdict(list)
    for msg in messages:
        # Look for tool use in various message formats
        if isinstance(msg, dict):
            # Direct tool call format
            if msg.get("type") == "tool_use":
                tool_name = msg.get("name")
                if tool_name:
                    tool_calls[tool_name].append(msg)
            # Claude Code format: nested message.content structure
            elif "message" in msg:
                inner_msg = msg.get("message", {})
                content = inner_msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_name = block.get("name")
                            if tool_name:
                                tool_calls[tool_name].append(block)
            # Content block format with tool uses
            elif "content" in msg:
                content = msg["content"]
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_name = block.get("name")
                            if tool_name:
                                tool_calls[tool_name].append(block)

    return tool_calls


def summarize_file_operations(tool_calls: Dict) -> Tuple[List[str], List[str], List[str]]:
    """Extract files created, modified, and read.

    Args:
        tool_calls: Dictionary of tool calls by type

    Returns:
        Tuple of (files_created, files_modified, files_read)
    """
    created = []
    modified = []
    read = []

    # Write tool = new file
    for call in tool_calls.get("Write", []):
        if "input" in call and "file_path" in call["input"]:
            file_path = call["input"]["file_path"]
            if file_path not in created:
                created.append(file_path)

    # Edit tool = modified file
    for call in tool_calls.get("Edit", []):
        if "input" in call and "file_path" in call["input"]:
            file_path = call["input"]["file_path"]
            if file_path not in modified:
                modified.append(file_path)

    # Read tool = read file
    for call in tool_calls.get("Read", []):
        if "input" in call and "file_path" in call["input"]:
            file_path = call["input"]["file_path"]
            if file_path not in read:
                read.append(file_path)

    return created, modified, read


def extract_bash_commands(tool_calls: Dict) -> List[CommandExecution]:
    """Extract bash commands executed during the session.

    Args:
        tool_calls: Dictionary of tool calls by type

    Returns:
        List of CommandExecution objects
    """
    commands = []

    for call in tool_calls.get("Bash", []):
        if "input" in call and "command" in call["input"]:
            command = call["input"]["command"]

            # Try to get timestamp
            timestamp = None
            if "timestamp" in call:
                try:
                    timestamp = datetime.fromisoformat(call["timestamp"])
                except (ValueError, TypeError):
                    pass

            # Default to now if no timestamp
            if timestamp is None:
                timestamp = datetime.now()

            commands.append(
                CommandExecution(
                    command=command,
                    timestamp=timestamp,
                )
            )

    return commands


def extract_todo_history(messages: List[Dict]) -> TodoHistory:
    """Extract complete todo history from TodoWrite tool results.

    This function parses all TodoWrite tool calls throughout the session
    to build a comprehensive view of all todos created and their final states.

    Args:
        messages: List of parsed messages from conversation

    Returns:
        TodoHistory object with all todos, completed todos, and pending todos
    """
    todo_history = TodoHistory()

    # Track todos by content to identify duplicates and state changes
    todo_states = {}  # content -> latest status
    todo_items_by_content = {}  # content -> TodoItem

    for msg in messages:
        if not isinstance(msg, dict):
            continue

        # Look for toolUseResult in user messages
        if msg.get("type") == "user" and "toolUseResult" in msg:
            tool_result = msg["toolUseResult"]

            # Check if this is a TodoWrite result (has newTodos field)
            if "newTodos" in tool_result:
                new_todos = tool_result.get("newTodos", [])

                for todo_dict in new_todos:
                    if not isinstance(todo_dict, dict):
                        continue

                    content = todo_dict.get("content")
                    status = todo_dict.get("status")
                    active_form = todo_dict.get("activeForm", content)

                    if content and status:
                        # Create TodoItem
                        todo_item = TodoItem(
                            content=content,
                            status=status,
                            active_form=active_form
                        )

                        # Track the latest state of this todo
                        todo_states[content] = status
                        todo_items_by_content[content] = todo_item

    # Build final lists based on latest states
    for content, todo_item in todo_items_by_content.items():
        # Use the latest status from todo_states
        final_status = todo_states[content]
        # Update the todo item with final status
        todo_item.status = final_status

        todo_history.all_todos.append(todo_item)

        if final_status == "completed":
            todo_history.completed_todos.append(todo_item)
        else:
            # pending or in_progress
            todo_history.pending_todos.append(todo_item)

    return todo_history


def extract_last_assistant_message(messages: List[Dict]) -> Optional[str]:
    """Extract the most informative assistant message from the conversation.

    Prioritizes messages with structured documentation (markdown headers),
    otherwise returns the last assistant message.

    Args:
        messages: List of parsed messages

    Returns:
        Most informative assistant message text, or None if not found
    """
    def extract_text_from_message(msg: Dict) -> Optional[str]:
        """Helper to extract text from a message in various formats."""
        # Claude Code format: nested message.content structure
        if "message" in msg and msg.get("type") == "assistant":
            inner_msg = msg.get("message", {})
            content = inner_msg.get("content")
            if content:
                # Handle string content
                if isinstance(content, str):
                    return content.strip()
                # Handle list of content blocks
                elif isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                text_parts.append(text)
                    if text_parts:
                        return " ".join(text_parts).strip()
        # Direct format with role field
        elif msg.get("role") == "assistant":
            content = msg.get("content")
            if content:
                # Handle string content
                if isinstance(content, str):
                    return content.strip()
                # Handle list of content blocks
                elif isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                text_parts.append(text)
                    if text_parts:
                        return " ".join(text_parts).strip()
        return None

    # First pass: look for messages with "### Issue Identified" header
    # Search from oldest to newest to find the FIRST occurrence (not a reference to it)
    # This is more likely to be the original detailed explanation
    for msg in messages:  # Forward search (oldest first)
        if isinstance(msg, dict):
            text = extract_text_from_message(msg)
            if text and "### Issue Identified" in text and "### Fixes Applied" in text:
                # Only return if it has BOTH markers (full structured summary)
                return text

    # Second pass: look for messages with "## Summary of Changes" header
    # These are comprehensive summaries
    for msg in messages:  # Forward search
        if isinstance(msg, dict):
            text = extract_text_from_message(msg)
            if text and "## Summary of Changes" in text and "###" in text:
                # Must have both ## Summary and ### sections
                return text

    # Third pass: return the last assistant message as fallback
    for msg in reversed(messages):
        if isinstance(msg, dict):
            text = extract_text_from_message(msg)
            if text:
                return text

    return None


def calculate_tool_call_stats(tool_calls: Dict) -> Dict[str, int]:
    """Calculate statistics on tool usage.

    Args:
        tool_calls: Dictionary of tool calls by type

    Returns:
        Dictionary mapping tool name to count
    """
    stats = {}
    for tool_name, calls in tool_calls.items():
        stats[tool_name] = len(calls)
    return stats


def find_conversation_file(session: Session) -> Optional[Path]:
    """Find the conversation .jsonl file for a session.

    Args:
        session: Session object

    Returns:
        Path to conversation file, or None if not found
    """
    active_conv = session.active_conversation
    if not active_conv or not active_conv.project_path or not active_conv.ai_agent_session_id:
        return None

    # Claude Code stores conversations in ~/.claude/projects/{encoded-path}/{uuid}.jsonl
    # Encode the project path (replace / with - AND replace _ with -)
    project_path = Path(active_conv.project_path)
    encoded_path = str(project_path).replace("/", "-").replace("_", "-")

    # Note: Claude Code KEEPS the leading dash in directory names
    # Do NOT remove it

    claude_dir = Path.home() / ".claude" / "projects" / encoded_path
    conversation_file = claude_dir / f"{active_conv.ai_agent_session_id}.jsonl"

    if conversation_file.exists():
        return conversation_file

    return None


def generate_prose_summary(
    summary: SessionSummary,
    mode: str = "local",
    api_key: Optional[str] = None,
    agent_backend: Optional[str] = None
) -> str:
    """Generate a prose summary describing what was done in the session.

    Args:
        summary: SessionSummary object with extracted information
        mode: Summary mode - "local", "ai", or "both"
        api_key: API key for AI mode (if None, reads from env var)
        agent_backend: AI agent backend used ("claude", "github-copilot", etc.)
                      If not Claude, auto-downgrades to "local" mode

    Returns:
        Prose summary text (may include markdown sections if present in last message)

    Note:
        AI summaries only work with Claude Code because they require parsing
        conversation files. Other agents (GitHub Copilot, Cursor, Windsurf) will
        automatically fall back to "local" mode which uses git changes and manual notes.
    """
    # Auto-downgrade to local mode for non-Claude agents
    # Only Claude Code has accessible conversation files for AI summary generation
    effective_mode = mode
    if agent_backend and agent_backend != "claude" and mode in ("ai", "both"):
        effective_mode = "local"
        # Note: We don't warn here because the caller can inform the user

    # PRIORITY 1: Check if we have todo history - this is the most comprehensive summary
    if summary.todo_history and summary.todo_history.all_todos:
        # Generate summary from todo history
        todo_summary = _generate_todo_summary(summary.todo_history)

        # If we have a structured last message, combine them
        if summary.last_assistant_message:
            msg = summary.last_assistant_message
            if "###" in msg or "## " in msg:
                return f"{todo_summary}\n\n{msg}"

        return todo_summary

    # PRIORITY 2: Check if the last assistant message contains structured documentation
    # (e.g., "### Issue Identified", "### Fixes Applied", etc.)
    if summary.last_assistant_message:
        msg = summary.last_assistant_message

        # If the message contains markdown headers (###), it's likely a detailed explanation
        # Return it as-is (it's already a good summary)
        if "###" in msg or "## " in msg:
            return msg

        # Otherwise, check if it's a long explanatory message
        if len(msg) > 300:
            # Likely a detailed explanation, return it
            return msg

    # PRIORITY 3: Try AI summary if effective mode is "ai" or "both"
    if effective_mode in ("ai", "both"):
        ai_summary = generate_ai_summary(summary, api_key)
        if ai_summary:
            if mode == "both":
                # Return both AI and local summary
                local = _generate_local_summary(summary)
                return f"{ai_summary}\n\n{local}"
            return ai_summary

    # PRIORITY 4: Fall back to local summary generation
    return _generate_local_summary(summary)


def _generate_todo_summary(todo_history: TodoHistory) -> str:
    """Generate a summary from todo history.

    Args:
        todo_history: TodoHistory object with all todos

    Returns:
        Formatted summary of work completed based on todos
    """
    parts = []

    # Summary header
    total_todos = len(todo_history.all_todos)
    completed_count = len(todo_history.completed_todos)
    pending_count = len(todo_history.pending_todos)

    parts.append(f"## Session Work Summary")
    parts.append(f"\nCompleted {completed_count} of {total_todos} tasks.\n")

    # Completed work
    if todo_history.completed_todos:
        parts.append("### Completed Tasks:")
        for todo in todo_history.completed_todos:
            parts.append(f"- ✓ {todo.content}")

    # Pending work
    if todo_history.pending_todos:
        parts.append("\n### Remaining Tasks:")
        for todo in todo_history.pending_todos:
            status_marker = "⧖" if todo.status == "in_progress" else "○"
            parts.append(f"- {status_marker} {todo.content}")

    return "\n".join(parts)


def _generate_local_summary(summary: SessionSummary) -> str:
    """Generate a basic statistical summary from tool call data.

    Args:
        summary: SessionSummary object with extracted information

    Returns:
        Statistical summary text
    """
    parts = []

    # Describe file operations
    if summary.files_created or summary.files_modified:
        file_parts = []
        if summary.files_created:
            file_parts.append(f"created {len(summary.files_created)} new files")
        if summary.files_modified:
            file_parts.append(f"modified {len(summary.files_modified)} existing files")
        parts.append("The session " + " and ".join(file_parts) + ".")

    # Describe major activities based on tool usage
    if summary.tool_call_stats:
        edit_count = summary.tool_call_stats.get("Edit", 0)
        write_count = summary.tool_call_stats.get("Write", 0)
        bash_count = summary.tool_call_stats.get("Bash", 0)

        activities = []
        if edit_count > 0:
            activities.append(f"made {edit_count} edits")
        if write_count > 0:
            activities.append(f"wrote {write_count} files")
        if bash_count > 0:
            activities.append(f"ran {bash_count} commands")

        if activities:
            parts.append("Work included: " + ", ".join(activities) + ".")

    # Add a brief excerpt from the last message if available
    if summary.last_assistant_message and not parts:
        # Extract first sentence if available
        msg = summary.last_assistant_message
        sentences = msg.split(". ")
        if sentences:
            first_sentence = sentences[0].strip()
            if first_sentence and len(first_sentence) < 150:
                parts.append(f"Latest activity: {first_sentence}.")

    return " ".join(parts) if parts else "No significant activity detected in this session."


def generate_ai_summary(summary: SessionSummary, api_key: Optional[str] = None) -> Optional[str]:
    """Generate an AI-powered summary using Claude API.

    Args:
        summary: SessionSummary object with extracted information
        api_key: Anthropic API key (if None, reads from ANTHROPIC_API_KEY env var)

    Returns:
        AI-generated summary text, or None if API call fails
    """
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        # anthropic package not installed
        return None

    try:
        # Build context from session data
        context_parts = []

        if summary.files_created:
            context_parts.append(f"Files created ({len(summary.files_created)}): {', '.join(summary.files_created[:10])}")
            if len(summary.files_created) > 10:
                context_parts.append(f"... and {len(summary.files_created) - 10} more")

        if summary.files_modified:
            context_parts.append(f"Files modified ({len(summary.files_modified)}): {', '.join(summary.files_modified[:10])}")
            if len(summary.files_modified) > 10:
                context_parts.append(f"... and {len(summary.files_modified) - 10} more")

        if summary.commands_run:
            commands = [cmd.command for cmd in summary.commands_run[:10]]
            context_parts.append(f"Commands run ({len(summary.commands_run)}): {', '.join(commands)}")
            if len(summary.commands_run) > 10:
                context_parts.append(f"... and {len(summary.commands_run) - 10} more")

        if summary.tool_call_stats:
            stats_str = ", ".join([f"{tool}: {count}" for tool, count in summary.tool_call_stats.items()])
            context_parts.append(f"Tool usage: {stats_str}")

        if summary.last_assistant_message:
            context_parts.append(f"Last message: {summary.last_assistant_message[:500]}")

        context = "\n".join(context_parts)

        # Call Claude API
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": f"""Based on this coding session data, write a concise summary (2-4 sentences) of what was accomplished:

{context}

Focus on what was built, fixed, or changed - not just statistics. Be specific and technical."""
                }
            ]
        )

        # Extract text from response
        if message.content and len(message.content) > 0:
            return message.content[0].text

        return None

    except Exception:
        # API call failed (network, auth, etc.)
        return None


def generate_session_summary(session: Session) -> SessionSummary:
    """Parse .jsonl conversation file and extract summary information.

    Args:
        session: Session object

    Returns:
        SessionSummary with extracted information
    """
    summary = SessionSummary()

    # Find the conversation file
    conversation_file = find_conversation_file(session)
    if not conversation_file:
        return summary

    # Parse the conversation
    messages = parse_conversation_jsonl(conversation_file)
    if not messages:
        return summary

    # Extract tool calls
    tool_calls = extract_tool_calls(messages)

    # Extract file operations
    created, modified, read = summarize_file_operations(tool_calls)
    summary.files_created = created
    summary.files_modified = modified
    summary.files_read = read

    # Extract bash commands
    summary.commands_run = extract_bash_commands(tool_calls)

    # Extract last assistant message
    summary.last_assistant_message = extract_last_assistant_message(messages)

    # Extract todo history
    summary.todo_history = extract_todo_history(messages)

    # Calculate tool stats
    summary.tool_call_stats = calculate_tool_call_stats(tool_calls)

    return summary
