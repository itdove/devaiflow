"""Conversation file repair utilities for Claude Code sessions."""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console

console = Console()


class ConversationRepairError(Exception):
    """Error during conversation file repair."""
    pass


def get_conversation_file_path(ai_agent_session_id: str) -> Optional[Path]:
    """Get the path to a Claude Code conversation file by UUID.

    Args:
        ai_agent_session_id: Claude Code session UUID

    Returns:
        Path to conversation file if found, None otherwise
    """
    claude_home = Path.home() / ".claude"
    projects_dir = claude_home / "projects"

    if not projects_dir.exists():
        return None

    # Search for the conversation file in all project directories
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        conv_file = project_dir / f"{ai_agent_session_id}.jsonl"
        if conv_file.exists():
            return conv_file

    return None


def is_valid_uuid(uuid_str: str) -> bool:
    """Check if string is a valid UUID format.

    Args:
        uuid_str: String to validate

    Returns:
        True if valid UUID format, False otherwise
    """
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(uuid_str))


def detect_corruption(conversation_file: Path) -> Dict[str, any]:
    """Detect corruption issues in a conversation file.

    Args:
        conversation_file: Path to the .jsonl conversation file

    Returns:
        Dictionary with corruption details:
        - is_corrupt: bool
        - issues: List of issue descriptions
        - invalid_lines: List of (line_number, error) tuples
        - truncation_needed: List of (line_number, current_size, content_type) tuples
    """
    issues = []
    invalid_lines = []
    truncation_needed = []

    try:
        with open(conversation_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)

                    # Check for large tool results
                    if data.get('type') == 'tool_result':
                        result_content = data.get('content', '')
                        if isinstance(result_content, str) and len(result_content) > 10000:
                            truncation_needed.append((line_num, len(result_content), 'tool_result'))

                    # Check for large tool use content
                    if data.get('type') == 'tool_use':
                        for key in ['content', 'input', 'parameters']:
                            value = data.get(key)
                            if isinstance(value, str) and len(value) > 10000:
                                truncation_needed.append((line_num, len(value), f'tool_use.{key}'))
                            elif isinstance(value, dict):
                                # Check dict values
                                for sub_key, sub_value in value.items():
                                    if isinstance(sub_value, str) and len(sub_value) > 10000:
                                        truncation_needed.append((line_num, len(sub_value), f'tool_use.{key}.{sub_key}'))

                except json.JSONDecodeError as e:
                    invalid_lines.append((line_num, str(e)))
                except UnicodeDecodeError as e:
                    invalid_lines.append((line_num, f"Unicode error: {e}"))

    except UnicodeDecodeError as e:
        issues.append(f"File has Unicode encoding issues: {e}")
        return {
            'is_corrupt': True,
            'issues': issues,
            'invalid_lines': invalid_lines,
            'truncation_needed': truncation_needed,
        }
    except Exception as e:
        issues.append(f"Error reading file: {e}")
        return {
            'is_corrupt': True,
            'issues': issues,
            'invalid_lines': invalid_lines,
            'truncation_needed': truncation_needed,
        }

    # Determine if file is corrupt
    is_corrupt = len(invalid_lines) > 0 or len(truncation_needed) > 0

    if invalid_lines:
        issues.append(f"Found {len(invalid_lines)} invalid JSON lines")
    if truncation_needed:
        issues.append(f"Found {len(truncation_needed)} lines with content exceeding 10KB")

    return {
        'is_corrupt': is_corrupt,
        'issues': issues,
        'invalid_lines': invalid_lines,
        'truncation_needed': truncation_needed,
    }


def remove_invalid_surrogates(text: str) -> str:
    """Remove invalid Unicode surrogate pairs from text.

    Args:
        text: Input text potentially containing invalid surrogates

    Returns:
        Cleaned text with surrogates removed
    """
    # Replace invalid surrogate characters
    return text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')


def truncate_content(content: any, max_size: int = 10000) -> Tuple[any, bool]:
    """Truncate large content to max_size.

    Args:
        content: Content to truncate (string, dict, or other)
        max_size: Maximum size in characters

    Returns:
        Tuple of (truncated_content, was_truncated)
    """
    if isinstance(content, str):
        if len(content) > max_size:
            return content[:max_size] + f"\n\n[TRUNCATED: {len(content) - max_size} chars removed by daf repair-conversation]", True
        return content, False

    elif isinstance(content, dict):
        truncated_dict = {}
        was_truncated = False
        for key, value in content.items():
            new_value, truncated = truncate_content(value, max_size)
            truncated_dict[key] = new_value
            was_truncated = was_truncated or truncated
        return truncated_dict, was_truncated

    elif isinstance(content, list):
        truncated_list = []
        was_truncated = False
        for item in content:
            new_item, truncated = truncate_content(item, max_size)
            truncated_list.append(new_item)
            was_truncated = was_truncated or truncated
        return truncated_list, was_truncated

    return content, False


def repair_conversation_file(
    conversation_file: Path,
    max_size: int = 10000,
    dry_run: bool = False
) -> Dict[str, any]:
    """Repair a corrupted conversation file.

    Args:
        conversation_file: Path to the .jsonl conversation file
        max_size: Maximum size for truncation (default: 10000 chars)
        dry_run: If True, report issues without making changes

    Returns:
        Dictionary with repair results:
        - success: bool
        - backup_path: Optional path to backup file
        - lines_repaired: int
        - truncations: List of (line_num, old_size, new_size) tuples
        - errors_fixed: List of (line_num, error_type) tuples
        - total_lines: int
    """
    if not conversation_file.exists():
        raise ConversationRepairError(f"Conversation file not found: {conversation_file}")

    # Detect corruption first
    corruption_info = detect_corruption(conversation_file)

    if not corruption_info['is_corrupt']:
        return {
            'success': True,
            'backup_path': None,
            'lines_repaired': 0,
            'truncations': [],
            'errors_fixed': [],
            'total_lines': 0,
            'message': 'No corruption detected',
        }

    if dry_run:
        return {
            'success': False,
            'backup_path': None,
            'lines_repaired': len(corruption_info['invalid_lines']) + len(corruption_info['truncation_needed']),
            'truncations': corruption_info['truncation_needed'],
            'errors_fixed': corruption_info['invalid_lines'],
            'total_lines': 0,
            'message': 'Dry run - no changes made',
            'issues': corruption_info['issues'],
        }

    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_file = conversation_file.with_suffix(f'.jsonl.backup-{timestamp}')
    shutil.copy2(conversation_file, backup_file)

    # Repair file
    repaired_lines = []
    truncations = []
    errors_fixed = []
    total_lines = 0

    try:
        with open(conversation_file, 'r', encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                total_lines += 1
                line = line.strip()
                if not line:
                    repaired_lines.append('')
                    continue

                try:
                    data = json.loads(line)

                    # Truncate large content
                    was_truncated = False

                    if data.get('type') == 'tool_result':
                        content = data.get('content', '')
                        new_content, truncated = truncate_content(content, max_size)
                        if truncated:
                            old_size = len(str(content))
                            data['content'] = new_content
                            new_size = len(str(new_content))
                            truncations.append((line_num, old_size, new_size))
                            was_truncated = True

                    elif data.get('type') == 'tool_use':
                        for key in ['content', 'input', 'parameters']:
                            if key in data:
                                value = data[key]
                                new_value, truncated = truncate_content(value, max_size)
                                if truncated:
                                    old_size = len(str(value))
                                    data[key] = new_value
                                    new_size = len(str(new_value))
                                    truncations.append((line_num, old_size, new_size))
                                    was_truncated = True

                    # Clean surrogates from all string values
                    cleaned_data = json.loads(
                        remove_invalid_surrogates(json.dumps(data))
                    )

                    repaired_lines.append(json.dumps(cleaned_data))

                except json.JSONDecodeError as e:
                    # Try to fix by removing surrogates
                    try:
                        cleaned_line = remove_invalid_surrogates(line)
                        data = json.loads(cleaned_line)
                        repaired_lines.append(json.dumps(data))
                        errors_fixed.append((line_num, 'JSONDecodeError'))
                    except:
                        # Skip this line entirely if unfixable
                        console.print(f"[yellow]⚠[/yellow] Skipping unfixable line {line_num}")
                        errors_fixed.append((line_num, 'Skipped'))
                        continue

        # Write repaired file
        with open(conversation_file, 'w', encoding='utf-8') as f:
            for line in repaired_lines:
                if line:  # Skip empty lines
                    f.write(line + '\n')

        return {
            'success': True,
            'backup_path': backup_file,
            'lines_repaired': len(errors_fixed) + len(truncations),
            'truncations': truncations,
            'errors_fixed': errors_fixed,
            'total_lines': total_lines,
            'message': 'Repair completed successfully',
        }

    except Exception as e:
        # Restore from backup on error
        if backup_file.exists():
            shutil.copy2(backup_file, conversation_file)
        raise ConversationRepairError(f"Repair failed: {e}")


def scan_all_conversations() -> List[Tuple[str, Path, Dict[str, any]]]:
    """Scan all Claude Code conversation files for corruption.

    Returns:
        List of tuples: (ai_agent_session_id, file_path, corruption_info)
    """
    claude_home = Path.home() / ".claude"
    projects_dir = claude_home / "projects"

    if not projects_dir.exists():
        return []

    corrupted_files = []

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        for conv_file in project_dir.glob("*.jsonl"):
            # Extract UUID from filename
            ai_agent_session_id = conv_file.stem

            # Skip non-UUID filenames (like agent-*.jsonl)
            if not is_valid_uuid(ai_agent_session_id):
                continue

            corruption_info = detect_corruption(conv_file)

            if corruption_info['is_corrupt']:
                corrupted_files.append((ai_agent_session_id, conv_file, corruption_info))

    return corrupted_files
