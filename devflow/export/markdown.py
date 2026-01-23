"""Markdown export functionality for DevAIFlow."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from devflow.config.loader import ConfigLoader
from devflow.config.models import Session
from devflow.session.summary import find_conversation_file, generate_session_summary, generate_prose_summary


class MarkdownExporter:
    """Export sessions to Markdown documentation format."""

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """Initialize the Markdown exporter.

        Args:
            config_loader: ConfigLoader instance. Defaults to new instance.
        """
        self.config_loader = config_loader or ConfigLoader()

    def export_session_to_markdown(
        self,
        session: Session,
        include_activity: bool = True,
        include_statistics: bool = True,
        ai_summary: bool = False,
    ) -> str:
        """Export a single session to Markdown format.

        Args:
            session: Session to export
            include_activity: Include session activity summary
            include_statistics: Include detailed statistics
            ai_summary: Use AI-powered summary (requires ANTHROPIC_API_KEY)

        Returns:
            Markdown-formatted string
        """
        lines = []

        # Header
        title = self._format_title(session)
        lines.append(f"# {title}\n")

        # Metadata section
        lines.extend(self._format_metadata(session))
        lines.append("")

        # Goal section
        lines.append("## Goal\n")
        lines.append(f"{session.goal}\n")

        # JIRA section (if applicable)
        if session.issue_key:
            lines.extend(self._format_jira_section(session))
            lines.append("")

        # Progress notes section
        notes = self._load_progress_notes(session)
        if notes:
            lines.append("## Progress Notes\n")
            lines.append(notes)
            lines.append("")

        # Session activity section
        if include_activity:
            activity = self._format_session_activity(session, ai_summary)
            if activity:
                lines.append("## Session Activity\n")
                lines.append(activity)
                lines.append("")

        # Statistics section
        if include_statistics:
            stats = self._format_statistics(session)
            if stats:
                lines.append("## Statistics\n")
                lines.append(stats)
                lines.append("")

        return "\n".join(lines)

    def export_sessions_to_markdown(
        self,
        identifiers: List[str],
        output_dir: Optional[Path] = None,
        include_activity: bool = True,
        include_statistics: bool = True,
        ai_summary: bool = False,
        combined: bool = False,
    ) -> List[Path]:
        """Export multiple sessions to Markdown files.

        Args:
            identifiers: List of session identifiers (names or JIRA keys)
            output_dir: Directory to write Markdown files. Defaults to current directory.
            include_activity: Include session activity summary
            include_statistics: Include detailed statistics
            ai_summary: Use AI-powered summary (requires ANTHROPIC_API_KEY)
            combined: Export all sessions to a single combined file

        Returns:
            List of paths to created Markdown files
        """
        if output_dir is None:
            output_dir = Path.cwd()

        output_dir.mkdir(parents=True, exist_ok=True)
        created_files = []

        # Load sessions
        sessions_index = self.config_loader.load_sessions()
        all_sessions = []

        for identifier in identifiers:
            session_list = sessions_index.get_sessions(identifier)
            if session_list:
                all_sessions.extend(session_list)

        if not all_sessions:
            raise ValueError("No sessions found to export")

        if combined:
            # Export to single combined file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"sessions-export-{timestamp}.md"

            combined_content = []
            combined_content.append(f"# Session Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            combined_content.append(f"Exported {len(all_sessions)} session(s)\n")
            combined_content.append("---\n")

            for session in all_sessions:
                content = self.export_session_to_markdown(
                    session,
                    include_activity=include_activity,
                    include_statistics=include_statistics,
                    ai_summary=ai_summary,
                )
                combined_content.append(content)
                combined_content.append("\n---\n")

            output_path.write_text("\n".join(combined_content))
            created_files.append(output_path)
        else:
            # Export each session to separate file
            for session in all_sessions:
                content = self.export_session_to_markdown(
                    session,
                    include_activity=include_activity,
                    include_statistics=include_statistics,
                    ai_summary=ai_summary,
                )

                # Generate filename
                filename = self._generate_filename(session)
                output_path = output_dir / filename

                output_path.write_text(content)
                created_files.append(output_path)

        return created_files

    def _format_title(self, session: Session) -> str:
        """Format the session title.

        Args:
            session: Session object

        Returns:
            Formatted title string
        """
        # Check for summary in issue_metadata
        summary = session.issue_metadata.get("summary") if session.issue_metadata else None
        if session.issue_key and summary:
            return f"Session: {session.issue_key} - {summary}"
        elif session.issue_key:
            return f"Session: {session.issue_key} - {session.goal}"
        else:
            return f"Session: {session.name} - {session.goal}"

    def _format_metadata(self, session: Session) -> List[str]:
        """Format the metadata section.

        Args:
            session: Session object

        Returns:
            List of formatted metadata lines
        """
        lines = []

        # Status
        lines.append(f"**Status:** {session.status.title()}")

        # Time spent
        total_seconds = session.total_time_seconds()
        time_str = self._format_duration(total_seconds)
        lines.append(f"**Time Spent:** {time_str}")

        # Created date
        created_str = session.created.strftime("%Y-%m-%d %H:%M")
        lines.append(f"**Created:** {created_str}")

        # Last active
        last_active_str = session.last_active.strftime("%Y-%m-%d %H:%M")
        lines.append(f"**Last Active:** {last_active_str}")

        # Completed date (if applicable)
        if session.status == "completed" and session.work_sessions:
            # Find the last work session end time
            last_session = session.work_sessions[-1]
            if last_session.end:
                completed_str = last_session.end.strftime("%Y-%m-%d %H:%M")
                lines.append(f"**Completed:** {completed_str}")

        # Working directory
        if session.working_directory:
            lines.append(f"**Working Directory:** {session.working_directory}")

        # Branch (use conversation-based API)
        active_conv = session.active_conversation
        if active_conv and active_conv.branch:
            lines.append(f"**Git Branch:** {active_conv.branch}")

        return lines

    def _format_jira_section(self, session: Session) -> List[str]:
        """Format the JIRA section.

        Args:
            session: Session object

        Returns:
            List of formatted JIRA lines
        """
        lines = []
        lines.append("## Issue Tracker Ticket\n")

        # Load config to get JIRA URL
        config = self.config_loader.load_config()
        jira_url = config.jira.url if config and config.jira else None

        # issue key with link (if URL configured)
        if jira_url:
            ticket_url = f"{jira_url}/browse/{session.issue_key}"
            lines.append(f"- **Key:** [{session.issue_key}]({ticket_url})")
        else:
            # No JIRA URL configured - just show the key
            lines.append(f"- **Key:** {session.issue_key}")

        # Get values from issue_metadata
        summary = session.issue_metadata.get("summary") if session.issue_metadata else None
        issue_type = session.issue_metadata.get("type") if session.issue_metadata else None
        status = session.issue_metadata.get("status") if session.issue_metadata else None
        sprint = session.issue_metadata.get("sprint") if session.issue_metadata else None
        points = session.issue_metadata.get("points") if session.issue_metadata else None
        epic = session.issue_metadata.get("epic") if session.issue_metadata else None

        # Summary
        if summary:
            lines.append(f"- **Summary:** {summary}")

        # Type
        if issue_type:
            lines.append(f"- **Type:** {issue_type}")

        # Status
        if status:
            lines.append(f"- **Status:** {status}")

        # Sprint
        if sprint:
            lines.append(f"- **Sprint:** {sprint}")

        # Points
        if points is not None:
            lines.append(f"- **Story Points:** {points}")

        # Epic
        if epic:
            epic_url = f"{jira_url}/browse/{epic}"
            lines.append(f"- **Epic:** [{epic}]({epic_url})")

        return lines

    def _load_progress_notes(self, session: Session) -> Optional[str]:
        """Load progress notes from notes.md file.

        Args:
            session: Session object

        Returns:
            Notes content or None if no notes exist
        """
        session_dir = self.config_loader.get_session_dir(session.name)
        notes_file = session_dir / "notes.md"

        if notes_file.exists():
            return notes_file.read_text().strip()

        return None

    def _format_session_activity(self, session: Session, ai_summary: bool = False) -> Optional[str]:
        """Format the session activity summary.

        Args:
            session: Session object
            ai_summary: Use AI-powered summary

        Returns:
            Formatted activity summary or None if no activity
        """
        # Generate session summary from conversation file
        summary = generate_session_summary(session)

        if not summary.tool_call_stats and not summary.last_assistant_message:
            return None

        # Generate prose summary
        mode = "ai" if ai_summary else "local"
        # Pass agent_backend for graceful degradation (non-Claude agents use local mode)
        config = self.config_loader.load_config()
        prose = generate_prose_summary(
            summary,
            mode=mode,
            agent_backend=config.agent_backend if config else None
        )

        lines = [prose]

        # Add file operations if available
        if summary.files_created or summary.files_modified:
            lines.append("\n### File Changes\n")

            if summary.files_created:
                lines.append(f"**Created ({len(summary.files_created)}):**")
                for file_path in summary.files_created[:10]:  # Limit to 10
                    lines.append(f"- `{file_path}`")
                if len(summary.files_created) > 10:
                    lines.append(f"- ... and {len(summary.files_created) - 10} more\n")

            if summary.files_modified:
                lines.append(f"\n**Modified ({len(summary.files_modified)}):**")
                for file_path in summary.files_modified[:10]:  # Limit to 10
                    lines.append(f"- `{file_path}`")
                if len(summary.files_modified) > 10:
                    lines.append(f"- ... and {len(summary.files_modified) - 10} more")

        # Add commands if available
        if summary.commands_run:
            lines.append("\n### Commands Run\n")
            for cmd in summary.commands_run[:10]:  # Limit to 10
                lines.append(f"- `{cmd.command}`")
            if len(summary.commands_run) > 10:
                lines.append(f"- ... and {len(summary.commands_run) - 10} more")

        return "\n".join(lines)

    def _format_statistics(self, session: Session) -> str:
        """Format the statistics section.

        Args:
            session: Session object

        Returns:
            Formatted statistics string
        """
        lines = []

        # Message count (use conversation-based API)
        message_count = session.active_conversation.message_count if session.active_conversation else 0
        lines.append(f"- **Messages:** {message_count}")

        # Work sessions
        work_session_count = len(session.work_sessions)
        lines.append(f"- **Work Sessions:** {work_session_count}")

        # Total time
        total_seconds = session.total_time_seconds()
        time_str = self._format_duration(total_seconds)
        lines.append(f"- **Total Time:** {time_str}")

        # Time by user (if multiple users)
        time_by_user = session.time_by_user()
        if len(time_by_user) > 1:
            lines.append(f"- **Contributors:** {len(time_by_user)}")
            for user, seconds in time_by_user.items():
                user_time = self._format_duration(seconds)
                lines.append(f"  - {user}: {user_time}")

        # Pull requests (use conversation-based API)
        active_conv = session.active_conversation
        prs = active_conv.prs if active_conv else []
        if prs:
            lines.append(f"- **Pull Requests:** {len(prs)}")
            for pr in prs:
                lines.append(f"  - {pr}")

        # Tags
        if session.tags:
            tags_str = ", ".join(session.tags)
            lines.append(f"- **Tags:** {tags_str}")

        # Generate session summary to get file/command stats
        summary = generate_session_summary(session)
        if summary.files_created:
            lines.append(f"- **Files Created:** {len(summary.files_created)}")
        if summary.files_modified:
            lines.append(f"- **Files Modified:** {len(summary.files_modified)}")
        if summary.commands_run:
            lines.append(f"- **Commands Run:** {len(summary.commands_run)}")

        return "\n".join(lines)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string (e.g., "2h 30m", "45m", "1h 15m 30s")
        """
        if seconds < 60:
            return f"{int(seconds)}s"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remaining_seconds = int(seconds % 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if remaining_seconds > 0 and hours == 0:  # Only show seconds if less than 1 hour
            parts.append(f"{remaining_seconds}s")

        return " ".join(parts) if parts else "0s"

    def _generate_filename(self, session: Session) -> str:
        """Generate a filename for the session export.

        Args:
            session: Session object

        Returns:
            Filename for the Markdown file
        """
        if session.issue_key:
            base = session.issue_key
        else:
            # Sanitize session name for filename
            base = session.name.replace("/", "-").replace(" ", "-")

        return f"{base}.md"
