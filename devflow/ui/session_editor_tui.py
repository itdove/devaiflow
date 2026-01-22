"""Text User Interface for editing Claude Session metadata.

This module provides an interactive TUI for modifying and fixing session metadata
using the Textual framework.

Features:
- Tabbed interface for session metadata, conversations, and JIRA integration
- Input validation for required fields and data types
- Multi-conversation management (add/edit/remove conversations)
- Save/cancel with automatic backup
- Keyboard navigation
- Help screen with keyboard shortcuts
- Read-only fields (created timestamp, session_id) clearly marked
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import shutil
from datetime import datetime
import re

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer, VerticalScroll
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.validation import ValidationResult, Validator
from textual.message import Message
from rich.console import Console

from devflow.session.manager import SessionManager
from devflow.config.models import Session, ConversationContext
from devflow.config.loader import ConfigLoader


console = Console()


# ============================================================================
# Validators
# ============================================================================


class PathValidator(Validator):
    """Validator for file path fields."""

    def validate(self, value: str) -> ValidationResult:
        """Validate that value is a valid path."""
        if not value or not value.strip():
            return self.failure("Path is required")
        # Expand user directory
        try:
            path = Path(value).expanduser()
            # Don't fail on non-existent paths during typing
            return self.success()
        except Exception as e:
            return self.failure(f"Invalid path: {e}")


class NonEmptyValidator(Validator):
    """Validator for required non-empty fields."""

    def validate(self, value: str) -> ValidationResult:
        """Validate that value is not empty."""
        if not value or not value.strip():
            return self.failure("This field is required")
        return self.success()


class JiraKeyValidator(Validator):
    """Validator for issue key format (e.g., PROJ-12345)."""

    def validate(self, value: str) -> ValidationResult:
        """Validate issue key format."""
        if not value or not value.strip():
            return self.success()  # Allow empty for optional field

        # issue key format: PROJECT-NUMBER
        if not re.match(r'^[A-Z]+-\d+$', value.strip()):
            return self.failure("issue key must be in format: PROJECT-NUMBER (e.g., PROJ-12345)")

        return self.success()


class UUIDValidator(Validator):
    """Validator for UUID format."""

    def validate(self, value: str) -> ValidationResult:
        """Validate UUID format."""
        if not value or not value.strip():
            return self.failure("UUID is required")

        # UUID format: 8-4-4-4-12 hex digits
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', value.strip().lower()):
            return self.failure("Invalid UUID format")

        return self.success()


# ============================================================================
# Custom Widgets
# ============================================================================


class SessionInput(Container):
    """A labeled input field for session metadata."""

    DEFAULT_CSS = """
    SessionInput {
        height: auto;
        margin: 0 0 1 0;
    }

    SessionInput > Label {
        width: 100%;
        padding: 0 0;
    }

    SessionInput > Input {
        width: 100%;
        margin: 0 0 0 0;
    }

    SessionInput > .help-text {
        color: $text-muted;
        width: 100%;
        padding: 0 0;
    }

    SessionInput > .read-only-text {
        color: $text-muted;
        width: 100%;
        padding: 1 0;
        background: $panel;
    }
    """

    def __init__(
        self,
        label: str,
        field_key: str,
        value: str = "",
        help_text: str = "",
        required: bool = False,
        read_only: bool = False,
        validator: Optional[Validator] = None,
        **kwargs,
    ):
        """Initialize session input.

        Args:
            label: Field label
            field_key: Field key for this input
            value: Initial value
            help_text: Help text
            required: Whether field is required
            read_only: Whether field is read-only
            validator: Input validator
        """
        super().__init__(**kwargs)
        self.field_key = field_key
        self._label = label
        self._value = value
        self._help_text = help_text
        self._required = required
        self._read_only = read_only
        self._validator = validator

    def compose(self) -> ComposeResult:
        """Compose the input widgets."""
        label_text = self._label
        if self._required:
            label_text += " *"
        if self._read_only:
            label_text += " [dim](read-only)[/dim]"
        yield Label(label_text)

        if self._read_only:
            # Read-only field - show as static text
            yield Static(self._value or "[dim]Not set[/dim]", classes="read-only-text")
        else:
            # Editable field - show as input
            validators = [self._validator] if self._validator else []
            if self._required and not self._validator:
                validators = [NonEmptyValidator()]

            yield Input(
                value=self._value,
                placeholder=self._help_text if not self._value else "",
                validators=validators,
                id=f"input_{self.field_key}",
            )

        if self._help_text and not self._read_only:
            yield Label(self._help_text, classes="help-text")

    def get_value(self) -> str:
        """Get current input value."""
        if self._read_only:
            return self._value
        input_widget = self.query_one(f"#input_{self.field_key}", Input)
        return input_widget.value.strip()


class SessionSelect(Container):
    """A labeled select dropdown for session metadata."""

    DEFAULT_CSS = """
    SessionSelect {
        height: auto;
        margin: 0 0 1 0;
    }

    SessionSelect > Label {
        width: 100%;
        padding: 0 0;
    }

    SessionSelect > Select {
        width: 100%;
        margin: 0 0 0 0;
    }

    SessionSelect > .help-text {
        color: $text-muted;
        width: 100%;
        padding: 0 0;
    }
    """

    def __init__(
        self,
        label: str,
        field_key: str,
        choices: List[tuple],
        value: Optional[str] = None,
        help_text: str = "",
        allow_blank: bool = False,
        **kwargs,
    ):
        """Initialize session select.

        Args:
            label: Field label
            field_key: Field key for this select
            choices: List of (value, label) tuples
            value: Initial value
            help_text: Help text
            allow_blank: Whether to allow blank/None selection
        """
        super().__init__(**kwargs)
        self.field_key = field_key
        self._label = label
        self._choices = choices
        self._value = value
        self._help_text = help_text
        self._allow_blank = allow_blank

    def compose(self) -> ComposeResult:
        """Compose the select widgets."""
        yield Label(self._label)

        yield Select(
            options=self._choices,
            value=self._value if self._value else Select.BLANK,
            allow_blank=self._allow_blank,
            id=f"select_{self.field_key}",
        )

        if self._help_text:
            yield Label(self._help_text, classes="help-text")

    def get_value(self) -> Optional[str]:
        """Get current select value."""
        select = self.query_one(f"#select_{self.field_key}", Select)
        return select.value if select.value != Select.BLANK else None


class ConversationEntry(Container):
    """Widget for displaying a single conversation with edit/remove buttons."""

    DEFAULT_CSS = """
    ConversationEntry {
        height: auto;
        margin: 0 0 1 0;
        border: solid $primary;
        padding: 1;
    }

    ConversationEntry .conv-key {
        width: 100%;
        color: $accent;
    }

    ConversationEntry .conv-details {
        width: 100%;
        color: $text-muted;
        margin: 0 0 1 0;
    }

    ConversationEntry .button-row {
        width: 100%;
        height: auto;
        align: right middle;
    }

    ConversationEntry Button {
        margin: 0 0 0 1;
    }
    """

    class EditPressed(Message):
        """Message sent when edit button is pressed."""

        def __init__(self, conv_key: str, conversation: ConversationContext):
            super().__init__()
            self.conv_key = conv_key
            self.conversation = conversation

    class RemovePressed(Message):
        """Message sent when remove button is pressed."""

        def __init__(self, conv_key: str):
            super().__init__()
            self.conv_key = conv_key

    def __init__(self, conv_key: str, conversation: ConversationContext, **kwargs):
        """Initialize conversation entry.

        Args:
            conv_key: Key for this conversation (e.g., "repo#session-id")
            conversation: The conversation context to display
        """
        super().__init__(**kwargs)
        self.conv_key = conv_key
        self.conversation = conversation

    def compose(self) -> ComposeResult:
        """Compose the conversation entry widgets."""
        yield Static(f"[bold]{self.conv_key}[/bold]", classes="conv-key")

        # Build details string
        details = []
        details.append(f"Branch: {self.conversation.branch}")
        if self.conversation.project_path:
            details.append(f"Path: {self.conversation.project_path}")
        details.append(f"Messages: {self.conversation.message_count}")

        yield Static(" | ".join(details), classes="conv-details")

        with Horizontal(classes="button-row"):
            yield Button("Edit", variant="primary", id=f"edit_{self.conv_key}", classes="compact")
            yield Button("Remove", variant="error", id=f"remove_{self.conv_key}", classes="compact")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        event.stop()  # Prevent event bubbling
        if event.button.id.startswith("edit_"):
            self.post_message(self.EditPressed(self.conv_key, self.conversation))
        elif event.button.id.startswith("remove_"):
            self.post_message(self.RemovePressed(self.conv_key))


# ============================================================================
# Modal Screens
# ============================================================================


class HelpScreen(ModalScreen):
    """Modal screen showing keyboard shortcuts and help."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Container {
        width: 80;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    HelpScreen Static {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Compose help screen."""
        with Container():
            yield Static("[bold cyan]DevAIFlow - Session Editor Help[/bold cyan]\n")
            yield Static(
                "[bold]Keyboard Shortcuts:[/bold]\n\n"
                "  Tab / Shift+Tab     - Navigate between fields\n"
                "  Arrow Keys          - Navigate tabs and fields\n"
                "  Enter               - Activate button/select\n"
                "  Escape              - Cancel/close\n"
                "  Ctrl+S              - Save changes\n"
                "  ?                   - Show this help\n"
                "  Q / Ctrl+C          - Quit\n\n"
                "[bold]Field Types:[/bold]\n\n"
                "  * (asterisk)        - Required field\n"
                "  (read-only)         - Cannot be edited\n"
                "  Select              - Arrow keys to choose\n"
                "  Input               - Type value directly\n\n"
                "[bold]Saving Changes:[/bold]\n\n"
                "  - Changes are validated before saving\n"
                "  - A backup is created automatically\n"
                "  - You can cancel to discard changes\n"
            )
            yield Button("Close", variant="primary", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        self.dismiss()


class AddConversationScreen(ModalScreen):
    """Modal screen for adding/editing a conversation."""

    DEFAULT_CSS = """
    AddConversationScreen {
        align: center middle;
    }

    AddConversationScreen > Container {
        width: 80;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    AddConversationScreen Input {
        width: 100%;
        margin: 0 0 1 0;
    }

    AddConversationScreen .button-row {
        width: 100%;
        height: auto;
        margin: 1 0 0 0;
        align: center middle;
    }

    AddConversationScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(
        self,
        existing_conv: Optional[ConversationContext] = None,
        conv_key: Optional[str] = None,
    ):
        """Initialize add/edit conversation screen.

        Args:
            existing_conv: If provided, edit mode (otherwise add mode)
            conv_key: Key of conversation being edited
        """
        super().__init__()
        self.existing_conv = existing_conv
        self.conv_key = conv_key
        self.is_edit_mode = existing_conv is not None

    def compose(self) -> ComposeResult:
        """Compose add conversation screen."""
        with Container():
            title = "Edit Conversation" if self.is_edit_mode else "Add Conversation"
            yield Static(f"[bold cyan]{title}[/bold cyan]\n")

            yield Label("Claude Session ID (UUID) *")
            yield Input(
                value=self.existing_conv.ai_agent_session_id if self.existing_conv else "",
                placeholder="e.g., 12345678-1234-1234-1234-123456789abc",
                id="ai_agent_session_id",
                validators=[UUIDValidator()],
            )

            yield Label("Project Path *")
            yield Input(
                value=self.existing_conv.project_path or "" if self.existing_conv else "",
                placeholder="/path/to/project",
                id="project_path",
                validators=[PathValidator()],
            )

            yield Label("Branch Name *")
            yield Input(
                value=self.existing_conv.branch if self.existing_conv else "",
                placeholder="feature-branch-name",
                id="branch",
                validators=[NonEmptyValidator()],
            )

            yield Label("Base Branch")
            yield Input(
                value=self.existing_conv.base_branch if self.existing_conv else "main",
                placeholder="main",
                id="base_branch",
            )

            with Horizontal(classes="button-row"):
                save_label = "Update" if self.is_edit_mode else "Add"
                yield Button(save_label, variant="success", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "save":
            session_id_input = self.query_one("#ai_agent_session_id", Input)
            path_input = self.query_one("#project_path", Input)
            branch_input = self.query_one("#branch", Input)
            base_branch_input = self.query_one("#base_branch", Input)

            ai_agent_session_id = session_id_input.value.strip()
            project_path = path_input.value.strip()
            branch = branch_input.value.strip()
            base_branch = base_branch_input.value.strip() or "main"

            # Validation
            if not ai_agent_session_id:
                self.app.notify("Claude Session ID is required", severity="error")
                return

            if not project_path:
                self.app.notify("Project path is required", severity="error")
                return

            if not branch:
                self.app.notify("Branch name is required", severity="error")
                return

            # Validate path exists
            try:
                path_obj = Path(project_path).expanduser()
                if not path_obj.exists():
                    self.app.notify(f"Path does not exist: {project_path}", severity="warning")
                    # Don't block - user might be planning to create it
            except Exception as e:
                self.app.notify(f"Invalid path: {e}", severity="error")
                return

            # Create or update conversation context
            if self.is_edit_mode:
                # Update existing conversation
                self.existing_conv.ai_agent_session_id = ai_agent_session_id
                self.existing_conv.project_path = project_path
                self.existing_conv.branch = branch
                self.existing_conv.base_branch = base_branch
                conv = self.existing_conv
            else:
                # Create new conversation
                conv = ConversationContext(
                    ai_agent_session_id=ai_agent_session_id,
                    project_path=project_path,
                    branch=branch,
                    base_branch=base_branch,
                )

            self.dismiss((conv, self.conv_key))
        else:
            self.dismiss(None)


class PreviewScreen(ModalScreen):
    """Modal screen showing session preview before saving."""

    DEFAULT_CSS = """
    PreviewScreen {
        align: center middle;
    }

    PreviewScreen > Container {
        width: 90;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    PreviewScreen TextArea {
        height: 1fr;
        margin: 1 0;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, session: Session):
        """Initialize preview screen.

        Args:
            session: Session to preview
        """
        super().__init__()
        self.session = session

    def compose(self) -> ComposeResult:
        """Compose preview screen."""
        with Container():
            yield Static("[bold cyan]Session Preview[/bold cyan]\n")
            yield Static("Review the session changes below:\n")

            # Convert session to JSON for preview
            session_json = json.dumps(
                self.session.model_dump(mode='json'),
                indent=2,
                default=str,
            )

            yield TextArea(session_json, read_only=True, language="json")

            with Horizontal():
                yield Button("Confirm & Save", variant="success", id="confirm")
                yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)


# ============================================================================
# Main TUI Application
# ============================================================================


class SessionEditorTUI(App):
    """Text User Interface for editing Claude Session metadata."""

    CSS_PATH = None  # Use inline CSS for now

    DEFAULT_CSS = """
    Screen {
        background: $surface;
    }

    Header {
        background: $primary;
        color: $text;
    }

    Footer {
        background: $panel;
    }

    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 1 2;
    }

    .section-title {
        margin: 0 0 1 0;
        text-align: center;
    }

    .section-help {
        color: $text-muted;
        margin: 0 0 1 0;
    }

    .subsection-title {
        margin: 1 0 0 0;
    }

    .button-bar {
        height: auto;
        width: 100%;
        margin: 2 0 0 0;
        align: center middle;
    }

    .button-bar Button {
        margin: 0 1;
    }

    VerticalScroll {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, session_identifier: str):
        """Initialize the TUI application.

        Args:
            session_identifier: Session name or issue key to edit
        """
        super().__init__()
        self.session_identifier = session_identifier
        self.session_manager = SessionManager()
        self.config_loader = ConfigLoader()

        # Load session
        try:
            self.session = self.session_manager.get_session(session_identifier)
            if not self.session:
                console.print(f"[red]Error: Session not found: {session_identifier}[/red]")
                raise RuntimeError(f"Session not found: {session_identifier}")
        except Exception as e:
            console.print(f"[red]Error loading session: {e}[/red]")
            raise

        self.original_session = self.session.model_copy(deep=True)
        self.modified = False

        self.TITLE = f"DevAIFlow - Edit Session: {self.session.name}"

    def compose(self) -> ComposeResult:
        """Compose the main TUI layout."""
        yield Header()

        with TabbedContent():
            with TabPane("Core Metadata", id="tab_core"):
                yield from self._compose_core_tab()

            with TabPane("Conversations", id="tab_conversations"):
                yield from self._compose_conversations_tab()

            with TabPane("JIRA Integration", id="tab_jira"):
                yield from self._compose_jira_tab()

            with TabPane("Time Tracking", id="tab_time"):
                yield from self._compose_time_tab()

        yield Footer()

    def _compose_core_tab(self) -> ComposeResult:
        """Compose core metadata tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]Core Session Metadata[/bold cyan]", classes="section-title")
            yield Static(
                "Edit basic session information and configuration",
                classes="section-help",
            )

            # Read-only fields
            yield SessionInput(
                "Session Name",
                "name",
                value=self.session.name,
                help_text="Primary identifier for this session",
                read_only=True,
            )

            yield SessionInput(
                "Created",
                "created",
                value=self.session.created.isoformat(),
                help_text="When this session was created",
                read_only=True,
            )

            # Editable fields
            yield SessionInput(
                "Goal",
                "goal",
                value=self.session.goal or "",
                help_text="Session goal or description",
            )

            yield SessionSelect(
                "Session Type",
                "session_type",
                choices=[
                    ("Development", "development"),
                    ("Ticket Creation", "ticket_creation"),
                ],
                value=self.session.session_type,
                help_text="Type of session (affects workflow)",
            )

            yield SessionSelect(
                "Status",
                "status",
                choices=[
                    ("Created", "created"),
                    ("In Progress", "in_progress"),
                    ("Complete", "complete"),
                ],
                value=self.session.status,
                help_text="Current session status",
            )

            # Working directory (deprecated but still editable)
            yield SessionInput(
                "Working Directory",
                "working_directory",
                value=self.session.working_directory or "",
                help_text="Active conversation working directory (deprecated: use conversations)",
            )

            with Horizontal(classes="button-bar"):
                yield Button("Save Changes", variant="success", id="save_btn")
                yield Button("Cancel", variant="default", id="cancel_btn")

    def _compose_conversations_tab(self) -> ComposeResult:
        """Compose conversations management tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]Conversation Management[/bold cyan]", classes="section-title")
            yield Static(
                "Manage Claude Code conversations for this session. "
                "Each conversation represents work in one repository.",
                classes="section-help",
            )

            # Container for conversation entries (will be updated dynamically)
            with Vertical(id="conversations_list"):
                if self.session.conversations:
                    for conv_key, conv in self.session.conversations.items():
                        yield ConversationEntry(conv_key, conv)
                else:
                    yield Static("[dim]No conversations configured[/dim]", id="empty_message")

            # Add button
            with Horizontal(classes="button-bar"):
                yield Button("Add Conversation", variant="success", id="add_conversation")

    def _compose_jira_tab(self) -> ComposeResult:
        """Compose JIRA integration tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]JIRA Integration[/bold cyan]", classes="section-title")
            yield Static(
                "Configure issue tracker ticket association and sync settings",
                classes="section-help",
            )

            yield SessionInput(
                "JIRA Key",
                "issue_key",
                value=self.session.issue_key or "",
                help_text="issue tracker key (e.g., PROJ-12345)",
                validator=JiraKeyValidator(),
            )

            yield Static("[dim]Additional JIRA fields (like summary, status in issue_metadata) are read-only and managed by sync operations[/dim]")

    def _compose_time_tab(self) -> ComposeResult:
        """Compose time tracking tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]Time Tracking[/bold cyan]", classes="section-title")
            yield Static(
                "View time tracking information for this session",
                classes="section-help",
            )

            yield SessionSelect(
                "Time Tracking State",
                "time_tracking_state",
                choices=[
                    ("Paused", "paused"),
                    ("Active", "active"),
                    ("Tracking", "tracking"),
                ],
                value=self.session.time_tracking_state,
                help_text="Current time tracking state",
            )

            # Show work sessions summary
            total_sessions = len(self.session.work_sessions)
            yield Static(f"\n[bold]Work Sessions:[/bold] {total_sessions} total")

            if self.session.work_sessions:
                for idx, ws in enumerate(self.session.work_sessions, 1):
                    start_time = ws.start.strftime("%Y-%m-%d %H:%M:%S")
                    end_time = ws.end.strftime("%Y-%m-%d %H:%M:%S") if ws.end else "In Progress"
                    duration = ws.duration or "N/A"
                    user = ws.user or "Unknown"
                    yield Static(f"  {idx}. {start_time} → {end_time} ({duration}) [{user}]")

    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())

    def action_save(self) -> None:
        """Save session changes."""
        # Collect all values from inputs
        self._collect_values()

        # Validate
        validation_errors = self._validate_all()
        if validation_errors:
            error_msg = "Validation errors:\n" + "\n".join(f"- {err}" for err in validation_errors)
            self.notify(error_msg, severity="error", timeout=10)
            return

        # Create backup
        try:
            backup_path = self._create_backup()
            self.notify(f"Backup created: {backup_path.name}", severity="information")
        except Exception as e:
            self.notify(f"Failed to create backup: {e}", severity="warning")

        # Save
        try:
            self.session_manager.save_session(self.session)
            self.notify("Session saved successfully!", severity="information")
            self.modified = False
            self.original_session = self.session.model_copy(deep=True)
        except Exception as e:
            self.notify(f"Failed to save session: {e}", severity="error")

    def action_quit(self) -> None:
        """Quit the application."""
        if self.modified:
            self.notify("Unsaved changes will be lost!", severity="warning")
        self.exit()

    def on_conversation_entry_edit_pressed(self, message: ConversationEntry.EditPressed) -> None:
        """Handle edit button press on conversation entry."""
        def handle_edit_result(result):
            """Handle the result from the edit screen."""
            if result:
                conv, conv_key = result
                # Update the conversation in session
                self.session.conversations[conv_key] = conv
                self._refresh_conversations_list()
                self.notify(f"Updated conversation: {conv_key}", severity="information")
                self.modified = True

        self.push_screen(
            AddConversationScreen(existing_conv=message.conversation, conv_key=message.conv_key),
            handle_edit_result
        )

    def on_conversation_entry_remove_pressed(self, message: ConversationEntry.RemovePressed) -> None:
        """Handle remove button press on conversation entry."""
        # Remove the conversation from session
        if message.conv_key in self.session.conversations:
            del self.session.conversations[message.conv_key]
            self._refresh_conversations_list()
            self.notify(f"Removed conversation: {message.conv_key}", severity="information")
            self.modified = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "add_conversation":
            def handle_add_result(result):
                """Handle the result from the add screen."""
                if result:
                    conv, _ = result
                    # Generate conversation key
                    # For new conversations, use a simple incrementing key
                    existing_keys = [k for k in self.session.conversations.keys() if k.startswith("conv_")]
                    conv_num = len(existing_keys) + 1
                    conv_key = f"conv_{conv_num}"

                    # Add the new conversation to session
                    self.session.conversations[conv_key] = conv
                    self._refresh_conversations_list()
                    self.notify(f"Added conversation: {conv_key}", severity="information")
                    self.modified = True

            self.push_screen(AddConversationScreen(), handle_add_result)

        elif event.button.id == "save_btn":
            self.action_save()

        elif event.button.id == "cancel_btn":
            if self.modified:
                self.notify("Discarding changes...", severity="warning")
            self.exit()

    def _refresh_conversations_list(self) -> None:
        """Refresh the conversations list display after add/edit/remove."""
        try:
            list_container = self.query_one("#conversations_list", Vertical)

            # Remove all existing children
            list_container.remove_children()

            # Re-add the conversation entries
            if self.session.conversations:
                for conv_key, conv in self.session.conversations.items():
                    list_container.mount(ConversationEntry(conv_key, conv))
            else:
                list_container.mount(Static("[dim]No conversations configured[/dim]", id="empty_message"))

        except Exception as e:
            self.notify(f"Error refreshing conversations list: {e}", severity="error")

    def _collect_values(self) -> None:
        """Collect all values from input widgets and update session."""
        # Helper to safely get input value
        def get_input_value(field_key: str) -> str:
            try:
                input_widget = self.query_one(f"#input_{field_key}", Input)
                return input_widget.value.strip()
            except:
                return ""

        # Helper to safely get select value
        def get_select_value(field_key: str) -> Optional[str]:
            try:
                select = self.query_one(f"#select_{field_key}", Select)
                return select.value if select.value != Select.BLANK else None
            except:
                return None

        # Core metadata
        try:
            goal_val = get_input_value("goal")
            self.session.goal = goal_val if goal_val else None

            session_type = get_select_value("session_type")
            if session_type:
                self.session.session_type = session_type

            status = get_select_value("status")
            if status:
                self.session.status = status

            working_dir = get_input_value("working_directory")
            self.session.working_directory = working_dir if working_dir else None

        except Exception as e:
            self.notify(f"Error collecting core metadata: {e}", severity="error")

        # JIRA integration
        try:
            issue_key= get_input_value("issue_key")
            self.session.issue_key = issue_key if issue_key else None

        except Exception as e:
            self.notify(f"Error collecting JIRA metadata: {e}", severity="error")

        # Time tracking
        try:
            time_state = get_select_value("time_tracking_state")
            if time_state:
                self.session.time_tracking_state = time_state

        except Exception as e:
            self.notify(f"Error collecting time tracking metadata: {e}", severity="error")

        # Mark as modified
        if self.session != self.original_session:
            self.modified = True

    def _validate_all(self) -> List[str]:
        """Validate all input fields.

        Returns:
            List of validation error messages
        """
        errors = []

        # Session name is required (but read-only, so no need to validate)
        # issue key format validation (if provided)
        if self.session.issue_key:
            if not re.match(r'^[A-Z]+-\d+$', self.session.issue_key):
                errors.append("issue key must be in format: PROJECT-NUMBER (e.g., PROJ-12345)")

        # Validate conversations
        for conv_key, conv in self.session.conversations.items():
            # Validate UUID format
            if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', conv.ai_agent_session_id.lower()):
                errors.append(f"Conversation {conv_key}: Invalid UUID format")

            # Validate project path exists
            if conv.project_path:
                try:
                    path = Path(conv.project_path).expanduser()
                    if not path.exists():
                        errors.append(f"Conversation {conv_key}: Project path does not exist: {conv.project_path}")
                except Exception as e:
                    errors.append(f"Conversation {conv_key}: Invalid project path: {e}")

        return errors

    def _create_backup(self) -> Path:
        """Create backup of session metadata.

        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = self.config_loader.session_home / "backups"
        backup_dir.mkdir(exist_ok=True)

        # Backup the session's metadata file
        session_dir = self.config_loader.session_home / "sessions" / self.session.name
        metadata_file = session_dir / "metadata.json"

        backup_path = backup_dir / f"session-{self.session.name}-{timestamp}.json"

        if metadata_file.exists():
            shutil.copy2(metadata_file, backup_path)
        else:
            # If metadata file doesn't exist yet, save current session state
            with open(backup_path, 'w') as f:
                json.dump(self.session.model_dump(mode='json'), f, indent=2, default=str)

        return backup_path


def run_session_editor_tui(session_identifier: str) -> None:
    """Run the session editor TUI application.

    Args:
        session_identifier: Session name or issue key to edit
    """
    app = SessionEditorTUI(session_identifier)
    app.run()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        console.print("[red]Usage: python session_editor_tui.py <session-name-or-jira-key>[/red]")
        sys.exit(1)

    run_session_editor_tui(sys.argv[1])
