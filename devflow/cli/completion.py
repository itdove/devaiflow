"""Shell completion support for DevAIFlow."""

import click
from pathlib import Path
from typing import List, Optional

from devflow.config.loader import ConfigLoader


def complete_session_identifiers(ctx, param, incomplete):
    """Auto-complete session group names and JIRA keys.

    Args:
        ctx: Click context
        param: Parameter being completed
        incomplete: Partial input from user

    Returns:
        List of completion suggestions
    """
    try:
        config_loader = ConfigLoader()
        sessions_index = config_loader.load_sessions()

        completions = []

        # Add session group names
        for group_name in sessions_index.sessions.keys():
            if group_name.startswith(incomplete):
                # Get first session in group for metadata
                session_list = sessions_index.sessions[group_name]
                if session_list:
                    session = session_list[0]
                    issue_info = f" (JIRA: {session.issue_key})" if session.issue_key else ""
                    completions.append((group_name, f"{session.goal[:50]}{issue_info}"))

        # Add JIRA keys (if different from group names)
        for group_name, session_list in sessions_index.sessions.items():
            for session in session_list:
                if session.issue_key and session.issue_key.startswith(incomplete):
                    if session.issue_key != group_name:  # Avoid duplicates
                        completions.append((session.issue_key, f"{session.goal[:50]} (Group: {group_name})"))

        return completions
    except Exception:
        # If config doesn't exist or error occurs, return empty list
        return []


def complete_working_directories(ctx, param, incomplete):
    """Auto-complete working directory names.

    Args:
        ctx: Click context
        param: Parameter being completed
        incomplete: Partial input from user

    Returns:
        List of completion suggestions
    """
    try:
        config_loader = ConfigLoader()
        sessions_index = config_loader.load_sessions()

        working_dirs = set()
        for session_list in sessions_index.sessions.values():
            for session in session_list:
                if session.working_directory:
                    working_dirs.add(session.working_directory)

        return [d for d in working_dirs if d.startswith(incomplete)]
    except Exception:
        return []


def complete_sprints(ctx, param, incomplete):
    """Auto-complete sprint names.

    Args:
        ctx: Click context
        param: Parameter being completed
        incomplete: Partial input from user

    Returns:
        List of completion suggestions
    """
    try:
        config_loader = ConfigLoader()
        sessions_index = config_loader.load_sessions()

        sprints = set()
        for session_list in sessions_index.sessions.values():
            for session in session_list:
                if session.issue_metadata and session.issue_metadata.get("sprint"):
                    sprints.add(session.issue_metadata.get("sprint"))

        # Add "current" as a special value
        sprints.add("current")

        return [s for s in sprints if s.startswith(incomplete)]
    except Exception:
        return []


def complete_tags(ctx, param, incomplete):
    """Auto-complete tag names.

    Args:
        ctx: Click context
        param: Parameter being completed
        incomplete: Partial input from user

    Returns:
        List of completion suggestions
    """
    try:
        config_loader = ConfigLoader()
        sessions_index = config_loader.load_sessions()

        tags = set()
        for session_list in sessions_index.sessions.values():
            for session in session_list:
                if hasattr(session, 'tags') and session.tags:
                    tags.update(session.tags)

        return [t for t in tags if t.startswith(incomplete)]
    except Exception:
        return []


def complete_file_paths(ctx, param, incomplete):
    """Auto-complete file paths (for backup/restore/import/export).

    Args:
        ctx: Click context
        param: Parameter being completed
        incomplete: Partial input from user

    Returns:
        List of file path completions
    """
    # Let shell handle file completion by returning empty
    # Click will fall back to shell's native file completion
    return []
