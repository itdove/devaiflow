"""Text User Interface for DevAIFlow configuration.

This module provides an interactive TUI for managing all daf configuration settings
using the Textual framework.

Features:
- Tabbed interface for different configuration sections
- Input validation for URLs, paths, and required fields
- Save/cancel with backup functionality
- Keyboard navigation and vim-style bindings (optional)
- Help screen with keyboard shortcuts
- Preview mode before saving
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import shutil
import os
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer, VerticalScroll
from textual.css.query import NoMatches
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
from textual.validation import ValidationResult, Validator, Integer, Number
from textual.message import Message
from rich.console import Console
from rich.text import Text

from devflow.config.loader import ConfigLoader
from devflow.config.models import Config, JiraTransitionConfig, ContextFile, WorkspaceDefinition
from devflow.jira.client import JiraClient
from devflow.jira.utils import get_field_with_alias


console = Console()


def _is_vertex_ai_available() -> bool:
    """Check if GCP Vertex AI is being used for Claude.

    Returns:
        True if CLAUDE_CODE_USE_VERTEX environment variable is set, False otherwise
    """
    return os.environ.get("CLAUDE_CODE_USE_VERTEX", "").lower() in ("1", "true", "yes")


def _get_vertex_ai_regions() -> List[tuple[str, str]]:
    """Get available GCP Vertex AI regions for Claude models.

    Returns a static list of regions where Claude models are supported on Vertex AI.

    HOW TO UPDATE THIS LIST:
    1. Check the official Claude on Vertex AI documentation:
       https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/use-claude

    2. Look for the "Before you begin" section and regional endpoint examples
       - Endpoint URLs will show region IDs (e.g., us-east5-aiplatform.googleapis.com)

    3. Verify in the Vertex AI Model Garden console:
       https://console.cloud.google.com/vertex-ai/model-garden
       - Search for "Claude"
       - Check which regions show model availability

    4. Cross-reference with Claude Code documentation:
       https://code.claude.com/docs/en/google-vertex-ai
       - Look for recommended regional configurations

    5. Update the list below with any new regions
       - Format: (Display Name, region_id)
       - Keep alphabetical order within geographic areas
       - Include location names in parentheses for clarity

    Last updated: 2025-01-XX (update this date when you refresh the list)
    Source: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/use-claude

    Returns:
        List of (display_name, region_id) tuples
    """
    # Static list of GCP Vertex AI regions that support Claude models
    # As of 2025-01, Claude is available in only 4 specific regions + global endpoint
    return [
        ("Global (dynamic routing)", "global"),
        ("US East 5 (Columbus, Ohio)", "us-east5"),
        ("Europe West 1 (Belgium)", "europe-west1"),
        ("Asia East 1 (Taiwan)", "asia-east1"),
        ("Asia Southeast 1 (Singapore)", "asia-southeast1"),
    ]


def _bool_to_choice(value: Optional[bool]) -> str:
    """Convert Optional[bool] to tri-state choice string.

    Args:
        value: Optional boolean value

    Returns:
        "true" for True, "false" for False, "prompt" for None
    """
    if value is True:
        return "true"
    elif value is False:
        return "false"
    else:  # None
        return "prompt"


def _choice_to_bool(choice: str) -> Optional[bool]:
    """Convert tri-state choice string to Optional[bool].

    Args:
        choice: One of "true", "false", or "prompt"

    Returns:
        True for "true", False for "false", None for "prompt"
    """
    if choice == "true":
        return True
    elif choice == "false":
        return False
    else:  # "prompt"
        return None


# ============================================================================
# Validators
# ============================================================================


class URLValidator(Validator):
    """Validator for URL fields."""

    def validate(self, value: str) -> ValidationResult:
        """Validate that value is a valid URL."""
        if not value or not value.strip():
            return self.success()  # Allow empty for optional fields
        if not (value.startswith("http://") or value.startswith("https://")):
            return self.failure("URL must start with http:// or https://")
        return self.success()


class PathValidator(Validator):
    """Validator for file path fields."""

    def validate(self, value: str) -> ValidationResult:
        """Validate that value is a valid path."""
        if not value or not value.strip():
            return self.success()  # Allow empty for optional fields
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


# ============================================================================
# Custom Widgets
# ============================================================================


class ConfigInput(Container):
    """A labeled input field for configuration."""

    DEFAULT_CSS = """
    ConfigInput {
        height: auto;
        margin: 0 0 1 0;
    }

    ConfigInput > Label {
        width: 100%;
        padding: 0 0;
    }

    ConfigInput > Input {
        width: 100%;
        margin: 0 0 0 0;
        min-height: 3;
    }

    ConfigInput > .help-text {
        color: $text-muted;
        width: 100%;
        padding: 0 0;
    }
    """

    def __init__(
        self,
        label: str,
        config_key: str,
        value: str = "",
        help_text: str = "",
        required: bool = False,
        validator: Optional[Validator] = None,
        **kwargs,
    ):
        """Initialize config input.

        Args:
            label: Field label
            config_key: Config key for this field
            value: Initial value
            help_text: Help text
            required: Whether field is required
            validator: Input validator
        """
        super().__init__(**kwargs)
        self.config_key = config_key
        self._label = label
        self._value = value
        self._help_text = help_text
        self._required = required
        self._validator = validator

    def compose(self) -> ComposeResult:
        """Compose the input widgets."""
        label_text = self._label
        if self._required:
            label_text += " *"
        yield Label(label_text)

        validators = [self._validator] if self._validator else []
        if self._required and not self._validator:
            validators = [NonEmptyValidator()]

        yield Input(
            value=self._value,
            placeholder=self._help_text if not self._value else "",
            validators=validators,
            id=f"input_{self.config_key.replace('.', '_')}",
        )

        if self._help_text:
            yield Label(self._help_text, classes="help-text")

    def get_value(self) -> str:
        """Get current input value."""
        input_widget = self.query_one(f"#input_{self.config_key.replace('.', '_')}", Input)
        return input_widget.value.strip()


class ConfigCheckbox(Container):
    """A labeled checkbox for configuration."""

    DEFAULT_CSS = """
    ConfigCheckbox {
        height: auto;
        margin: 0 0 1 0;
    }

    ConfigCheckbox > Label {
        width: 100%;
        padding: 0 0;
    }

    ConfigCheckbox > Horizontal {
        width: 100%;
        height: auto;
    }

    ConfigCheckbox Checkbox {
        width: auto;
    }

    ConfigCheckbox > .help-text {
        color: $text-muted;
        width: 100%;
        padding: 0 0;
    }
    """

    def __init__(
        self,
        label: str,
        config_key: str,
        value: Optional[bool] = None,
        help_text: str = "",
        **kwargs,
    ):
        """Initialize config checkbox.

        Args:
            label: Field label
            config_key: Config key for this field
            value: Initial value (None = unset, True/False = set)
            help_text: Help text
        """
        super().__init__(**kwargs)
        self.config_key = config_key
        self._label = label
        self._value = value
        self._help_text = help_text

    def compose(self) -> ComposeResult:
        """Compose the checkbox widgets."""
        yield Label(self._label)
        with Horizontal():
            checkbox_value = self._value if self._value is not None else False
            yield Checkbox(value=checkbox_value, id=f"checkbox_{self.config_key.replace('.', '_')}")
            if self._value is None:
                yield Label("[dim](not set - will prompt)[/dim]")

        if self._help_text:
            yield Label(self._help_text, classes="help-text")

    def get_value(self) -> bool:
        """Get current checkbox value."""
        checkbox = self.query_one(f"#checkbox_{self.config_key.replace('.', '_')}", Checkbox)
        return checkbox.value


class ConfigSelect(Container):
    """A labeled select dropdown for configuration."""

    DEFAULT_CSS = """
    ConfigSelect {
        height: auto;
        margin: 0 0 1 0;
    }

    ConfigSelect > Label {
        width: 100%;
        padding: 0 0;
    }

    ConfigSelect > Select {
        width: 100%;
        margin: 0 0 0 0;
    }

    ConfigSelect > .help-text {
        color: $text-muted;
        width: 100%;
        padding: 0 0;
    }
    """

    def __init__(
        self,
        label: str,
        config_key: str,
        choices: List[tuple],
        value: Optional[str] = None,
        help_text: str = "",
        allow_blank: bool = True,
        **kwargs,
    ):
        """Initialize config select.

        Args:
            label: Field label
            config_key: Config key for this field
            choices: List of (value, label) tuples
            value: Initial value
            help_text: Help text
            allow_blank: Whether to allow blank/None selection
        """
        super().__init__(**kwargs)
        self.config_key = config_key
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
            id=f"select_{self.config_key.replace('.', '_')}",
        )

        if self._help_text:
            yield Label(self._help_text, classes="help-text")

    def get_value(self) -> Optional[str]:
        """Get current select value."""
        select = self.query_one(f"#select_{self.config_key.replace('.', '_')}", Select)
        return select.value if select.value != Select.BLANK else None


class ContextFileEntry(Container):
    """Widget for displaying a single context file entry with edit/remove buttons."""

    DEFAULT_CSS = """
    ContextFileEntry {
        height: auto;
        margin: 0 0 1 0;
        border: solid $primary;
        padding: 1;
    }

    ContextFileEntry .ctx-path {
        width: 100%;
        color: $accent;
    }

    ContextFileEntry .ctx-description {
        width: 100%;
        color: $text-muted;
        margin: 0 0 1 0;
    }

    ContextFileEntry .button-row {
        width: 100%;
        height: auto;
        align: right middle;
    }

    ContextFileEntry Button {
        margin: 0 0 0 1;
    }
    """

    class EditPressed(Message):
        """Message sent when edit button is pressed."""

        def __init__(self, index: int, context_file: ContextFile):
            super().__init__()
            self.index = index
            self.context_file = context_file

    class RemovePressed(Message):
        """Message sent when remove button is pressed."""

        def __init__(self, index: int):
            super().__init__()
            self.index = index

    def __init__(self, index: int, context_file: ContextFile, **kwargs):
        """Initialize context file entry.

        Args:
            index: Index of this context file in the list
            context_file: The context file to display
        """
        super().__init__(**kwargs)
        self.index = index
        self.context_file = context_file

    def compose(self) -> ComposeResult:
        """Compose the context file entry widgets."""
        yield Static(f"[bold]{self.context_file.path}[/bold]", classes="ctx-path")
        yield Static(self.context_file.description, classes="ctx-description")
        with Horizontal(classes="button-row"):
            yield Button("Edit", variant="primary", id=f"edit_{self.index}", classes="compact")
            yield Button("Remove", variant="error", id=f"remove_{self.index}", classes="compact")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        event.stop()  # Prevent event bubbling
        if event.button.id.startswith("edit_"):
            self.post_message(self.EditPressed(self.index, self.context_file))
        elif event.button.id.startswith("remove_"):
            self.post_message(self.RemovePressed(self.index))


class WorkspaceEntry(Container):
    """Widget for displaying a single workspace entry with edit/remove/set-as-last-used buttons."""

    DEFAULT_CSS = """
    WorkspaceEntry {
        height: auto;
        margin: 0 0 1 0;
        border: solid $primary;
        padding: 1;
    }

    WorkspaceEntry .ws-header {
        width: 100%;
        margin: 0 0 1 0;
    }

    WorkspaceEntry .ws-name {
        color: $accent;
    }

    WorkspaceEntry .ws-badge {
        color: $warning;
        margin: 0 0 0 1;
    }

    WorkspaceEntry .ws-path {
        width: 100%;
        color: $text-muted;
        margin: 0 0 1 0;
    }

    WorkspaceEntry .button-row {
        width: 100%;
        height: auto;
        align: right middle;
    }

    WorkspaceEntry Button {
        margin: 0 0 0 1;
    }
    """

    class EditPressed(Message):
        """Message sent when edit button is pressed."""

        def __init__(self, index: int, workspace: WorkspaceDefinition):
            super().__init__()
            self.index = index
            self.workspace = workspace

    class RemovePressed(Message):
        """Message sent when remove button is pressed."""

        def __init__(self, index: int):
            super().__init__()
            self.index = index

    class SetAsLastUsedPressed(Message):
        """Message sent when set as last used button is pressed."""

        def __init__(self, workspace_name: str):
            super().__init__()
            self.workspace_name = workspace_name

    def __init__(self, index: int, workspace: WorkspaceDefinition, is_last_used: bool = False, **kwargs):
        """Initialize workspace entry.

        Args:
            index: Index of this workspace in the list
            workspace: The workspace to display
            is_last_used: Whether this is the last used workspace
        """
        super().__init__(**kwargs)
        self.index = index
        self.workspace = workspace
        self.is_last_used = is_last_used

    def compose(self) -> ComposeResult:
        """Compose the workspace entry widgets."""
        # Header with name and badge
        name_text = f"[bold]{self.workspace.name}[/bold]"
        if self.is_last_used:
            name_text += " [yellow]⭐ Last Used[/yellow]"
        yield Static(name_text, classes="ws-header")

        # Path
        yield Static(f"Path: {self.workspace.path}", classes="ws-path")

        # Buttons - use workspace name in ID to ensure uniqueness
        btn_id_base = f"ws_{self.workspace.name.replace(' ', '_')}_{self.index}"
        with Horizontal(classes="button-row"):
            if not self.is_last_used:
                yield Button("Use This", variant="success", id=f"use_{btn_id_base}", classes="compact")
            yield Button("Edit", variant="primary", id=f"edit_{btn_id_base}", classes="compact")
            yield Button("Remove", variant="error", id=f"remove_{btn_id_base}", classes="compact")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        event.stop()  # Prevent event bubbling
        if event.button.id.startswith("edit_"):
            self.post_message(self.EditPressed(self.index, self.workspace))
        elif event.button.id.startswith("remove_"):
            self.post_message(self.RemovePressed(self.index))
        elif event.button.id.startswith("use_"):
            self.post_message(self.SetAsLastUsedPressed(self.workspace.name))


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
            yield Static("[bold cyan]DevAIFlow - Configuration TUI Help[/bold cyan]\n")
            yield Static(
                "[bold]Keyboard Shortcuts:[/bold]\n\n"
                "  Tab / Shift+Tab     - Navigate between fields\n"
                "  Arrow Keys          - Navigate tabs and fields\n"
                "  Enter               - Activate button/checkbox\n"
                "  Escape              - Cancel/close\n"
                "  Ctrl+S              - Save configuration\n"
                "  Ctrl+T              - Toggle Simple/Advanced Mode\n"
                "  ?                   - Show this help\n"
                "  Q / Ctrl+C          - Quit\n\n"
                "[bold]Modes:[/bold]\n\n"
                "  Simple Mode         - Topic-based tabs (JIRA, Repository, etc.)\n"
                "  Advanced Mode       - File-based tabs (Enterprise, Organization, Team, User)\n\n"
                "[bold]Field Types:[/bold]\n\n"
                "  * (asterisk)        - Required field\n"
                "  Checkbox            - Toggle with Enter/Space\n"
                "  Select              - Arrow keys to choose\n"
                "  Input               - Type value directly\n\n"
                "[bold]Saving Changes:[/bold]\n\n"
                "  - Changes are validated before saving\n"
                "  - A backup is created automatically\n"
                "  - You can preview changes before saving\n"
            )
            yield Button("Close", variant="primary", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        self.dismiss()


class AddContextFileScreen(ModalScreen):
    """Modal screen for adding a new context file."""

    DEFAULT_CSS = """
    AddContextFileScreen {
        align: center middle;
    }

    AddContextFileScreen > Container {
        width: 80;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    AddContextFileScreen Input {
        width: 100%;
        margin: 0 0 1 0;
    }

    AddContextFileScreen .button-row {
        width: 100%;
        height: auto;
        margin: 1 0 0 0;
        align: center middle;
    }

    AddContextFileScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, existing_file: Optional[ContextFile] = None, index: Optional[int] = None):
        """Initialize add/edit context file screen.

        Args:
            existing_file: If provided, edit mode (otherwise add mode)
            index: Index of file being edited
        """
        super().__init__()
        self.existing_file = existing_file
        self.index = index
        self.is_edit_mode = existing_file is not None

    def compose(self) -> ComposeResult:
        """Compose add context file screen."""
        with Container():
            title = "Edit Context File" if self.is_edit_mode else "Add Context File"
            yield Static(f"[bold cyan]{title}[/bold cyan]\n")

            yield Label("File Path or URL *")
            yield Input(
                value=self.existing_file.path if self.existing_file else "",
                placeholder="e.g., ARCHITECTURE.md or https://github.com/org/repo/blob/main/DESIGN.md",
                id="ctx_path",
            )

            yield Label("Description *")
            yield Input(
                value=self.existing_file.description if self.existing_file else "",
                placeholder="Brief description of what this file contains",
                id="ctx_description",
            )

            with Horizontal(classes="button-row"):
                save_label = "Update" if self.is_edit_mode else "Add"
                yield Button(save_label, variant="success", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "save":
            path_input = self.query_one("#ctx_path", Input)
            desc_input = self.query_one("#ctx_description", Input)

            path = path_input.value.strip()
            description = desc_input.value.strip()

            # Validation
            if not path:
                self.app.notify("Path is required", severity="error")
                return

            if not description:
                self.app.notify("Description is required", severity="error")
                return

            # For local files, validate they exist
            if not (path.startswith("http://") or path.startswith("https://")):
                try:
                    file_path = Path(path).expanduser()
                    if not file_path.exists():
                        self.app.notify(f"File does not exist: {path}", severity="warning")
                        # Don't block - user might be planning to create it
                except Exception as e:
                    self.app.notify(f"Invalid path: {e}", severity="error")
                    return

            # Return the new/updated context file
            ctx_file = ContextFile(path=path, description=description)
            self.dismiss((ctx_file, self.index))
        else:
            self.dismiss(None)


class AddEditWorkspaceScreen(ModalScreen):
    """Modal screen for adding/editing a workspace."""

    DEFAULT_CSS = """
    AddEditWorkspaceScreen {
        align: center middle;
    }

    AddEditWorkspaceScreen > Container {
        width: 80;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    AddEditWorkspaceScreen Input {
        width: 100%;
        margin: 0 0 1 0;
    }

    AddEditWorkspaceScreen .button-row {
        width: 100%;
        height: auto;
        margin: 1 0 0 0;
        align: center middle;
    }

    AddEditWorkspaceScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, existing_workspace: Optional[WorkspaceDefinition] = None, index: Optional[int] = None):
        """Initialize add/edit workspace screen.

        Args:
            existing_workspace: If provided, edit mode (otherwise add mode)
            index: Index of workspace being edited
        """
        super().__init__()
        self.existing_workspace = existing_workspace
        self.index = index
        self.is_edit_mode = existing_workspace is not None

    def compose(self) -> ComposeResult:
        """Compose add/edit workspace screen."""
        with Container():
            title = "Edit Workspace" if self.is_edit_mode else "Add Workspace"
            yield Static(f"[bold cyan]{title}[/bold cyan]\n")

            yield Label("Workspace Name *")
            yield Input(
                value=self.existing_workspace.name if self.existing_workspace else "",
                placeholder="e.g., primary, product-a, feat-caching",
                id="ws_name",
            )

            yield Label("Workspace Path *")
            yield Input(
                value=self.existing_workspace.path if self.existing_workspace else "",
                placeholder="e.g., ~/development/project or /path/to/workspace",
                id="ws_path",
            )

            with Horizontal(classes="button-row"):
                save_label = "Update" if self.is_edit_mode else "Add"
                yield Button(save_label, variant="success", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "save":
            name_input = self.query_one("#ws_name", Input)
            path_input = self.query_one("#ws_path", Input)

            name = name_input.value.strip()
            path = path_input.value.strip()

            # Validation
            if not name:
                self.app.notify("Workspace name is required", severity="error")
                return

            if not path:
                self.app.notify("Workspace path is required", severity="error")
                return

            # Validate path exists
            try:
                expanded_path = Path(path).expanduser()
                if not expanded_path.exists():
                    self.app.notify(f"Path does not exist: {path}", severity="error")
                    return
                if not expanded_path.is_dir():
                    self.app.notify(f"Path is not a directory: {path}", severity="error")
                    return
            except Exception as e:
                self.app.notify(f"Invalid path: {e}", severity="error")
                return

            # Validate workspace contains git repositories (warning only)
            from devflow.git.utils import GitUtils
            if not GitUtils.is_git_repository(expanded_path):
                # Check if workspace contains any git repositories
                has_git_repos = False
                try:
                    for item in expanded_path.iterdir():
                        if item.is_dir() and (item / ".git").exists():
                            has_git_repos = True
                            break
                except PermissionError:
                    pass  # Can't check, skip validation

                if not has_git_repos:
                    self.app.notify(f"⚠ Warning: Workspace does not appear to contain git repositories", severity="warning", timeout=5)

            # Return the new/updated workspace
            workspace = WorkspaceDefinition(name=name, path=path)
            self.dismiss((workspace, self.index))
        else:
            self.dismiss(None)


class PreviewScreen(ModalScreen):
    """Modal screen showing configuration preview before saving."""

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

    def __init__(self, config: Config):
        """Initialize preview screen.

        Args:
            config: Configuration to preview
        """
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose preview screen."""
        with Container():
            yield Static("[bold cyan]Configuration Preview[/bold cyan]\n")
            yield Static("Review the configuration changes below:\n")

            # Convert config to JSON for preview
            config_json = json.dumps(
                self.config.model_dump(by_alias=True, exclude_none=False),
                indent=2,
                default=str,
            )

            yield TextArea(config_json, read_only=True, language="json")

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


class ConfigTUI(App):
    """Text User Interface for DevAIFlow configuration."""

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

    .mode-indicator {
        height: 1;
        padding: 0 2;
        background: $panel;
        text-align: center;
        border-bottom: solid $primary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+p", "preview", "Preview"),
        Binding("ctrl+t", "toggle_mode", "Toggle Mode"),
    ]

    TITLE = "DevAIFlow - Configuration"

    def __init__(self, advanced_mode: bool = False):
        """Initialize the TUI application.

        Args:
            advanced_mode: If True, start in Advanced Mode (file-based tabs)
        """
        super().__init__()
        self.config_loader = ConfigLoader()
        self.config = self.config_loader.load_config()
        if not self.config:
            console.print("[red]Error: Could not load configuration[/red]")
            raise RuntimeError("Failed to load configuration")
        self.original_config = self.config.model_copy(deep=True)
        self.modified = False
        self.advanced_mode = advanced_mode

    def _get_agent_backend_enforcement_source(self) -> Optional[str]:
        """Check if agent_backend is enforced by enterprise or team config.

        Returns:
            "enterprise" if enforced by enterprise config
            "team" if enforced by team config
            None if user can choose
        """
        # Load enterprise and team configs to check if they enforce agent_backend
        enterprise_config = self.config_loader._load_enterprise_config()
        team_config = self.config_loader._load_team_config()

        if enterprise_config and enterprise_config.agent_backend:
            return "enterprise"
        elif team_config and team_config.agent_backend:
            return "team"
        else:
            return None

    def compose(self) -> ComposeResult:
        """Compose the main TUI layout."""
        yield Header()

        # Mode indicator
        mode_text = "[bold cyan]Advanced Mode[/bold cyan] (Ctrl+T to switch to Simple)" if self.advanced_mode else "[bold green]Simple Mode[/bold green] (Ctrl+T to switch to Advanced)"
        yield Static(mode_text, id="mode_indicator", classes="mode-indicator")

        with TabbedContent(id="main_tabs"):
            if self.advanced_mode:
                # Advanced Mode: File-based tabs
                with TabPane("Enterprise", id="tab_enterprise"):
                    yield from self._compose_enterprise_tab()

                with TabPane("Organization", id="tab_organization"):
                    yield from self._compose_organization_tab()

                with TabPane("Team", id="tab_team"):
                    yield from self._compose_team_tab()

                with TabPane("User", id="tab_user"):
                    yield from self._compose_user_tab()
            else:
                # Simple Mode: Topic-based tabs (current)
                with TabPane("JIRA Integration", id="tab_jira"):
                    yield from self._compose_jira_tab()

                with TabPane("Repository & VCS", id="tab_repo"):
                    yield from self._compose_repo_tab()

                with TabPane("Workspaces", id="tab_workspaces"):
                    yield from self._compose_workspaces_tab()

                with TabPane("AI", id="tab_claude"):
                    yield from self._compose_claude_tab()

                with TabPane("Session Workflow", id="tab_workflow"):
                    yield from self._compose_session_workflow_tab()

                with TabPane("Advanced", id="tab_advanced"):
                    yield from self._compose_advanced_tab()

        yield Footer()

    def on_mount(self) -> None:
        """Set initial visibility of Claude-specific sections after mount."""
        # Set initial visibility based on current agent_backend
        self._on_agent_backend_changed(self.config.agent_backend)

        # Also explicitly update API key visibility after mount
        # This ensures the field is properly rendered before we hide it
        self.set_timer(0.1, self._update_api_key_visibility)

    def _compose_jira_tab(self) -> ComposeResult:
        """Compose JIRA configuration tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]JIRA Configuration[/bold cyan]", classes="section-title")
            yield Static(
                "Configure JIRA integration settings for ticket management",
                classes="section-help",
            )

            yield ConfigInput(
                "JIRA URL",
                "jira.url",
                value=self.config.jira.url,
                help_text="JIRA instance URL (e.g., https://jira.example.com)",
                required=True,
                validator=URLValidator(),
            )

            yield ConfigInput(
                "Project Key",
                "jira.project",
                value=self.config.jira.project or "",
                help_text="JIRA project key (e.g., PROJ, TEAM)",
            )

            # Get components from system_field_defaults if it exists
            components_value = None
            if self.config.jira.system_field_defaults and "components" in self.config.jira.system_field_defaults:
                components_list = self.config.jira.system_field_defaults["components"]
                # For dropdown, just use the first component if multiple are set
                if isinstance(components_list, list) and components_list:
                    components_value = components_list[0]
                elif isinstance(components_list, str):
                    components_value = components_list

            # Get available components from field mappings
            component_choices = []
            if self.config.jira.field_mappings:
                # Check for either component/s (server) or components (cloud)
                component_field = get_field_with_alias(self.config.jira.field_mappings, "components")
                if component_field and "allowed_values" in component_field:
                    # Extract component names from allowed_values
                    # allowed_values can be simple strings, dicts, or JSON-serialized strings
                    import json
                    for comp in component_field["allowed_values"]:
                        try:
                            # If it's a simple string (direct value)
                            if isinstance(comp, str):
                                # Try to parse as JSON first (for dict-like strings)
                                try:
                                    comp_dict = json.loads(comp.replace("'", '"'))
                                    if isinstance(comp_dict, dict) and "name" in comp_dict:
                                        component_choices.append((comp_dict["name"], comp_dict["name"]))
                                    else:
                                        # Not a dict, use string directly
                                        component_choices.append((comp, comp))
                                except (json.JSONDecodeError, ValueError):
                                    # Not JSON, use string directly
                                    component_choices.append((comp, comp))
                            # If it's already a dict
                            elif isinstance(comp, dict) and "name" in comp:
                                component_choices.append((comp["name"], comp["name"]))
                        except (KeyError, TypeError, ValueError):
                            # If parsing fails, skip this component
                            pass

            # If we have component choices, use a dropdown; otherwise use text input
            if component_choices:
                yield ConfigSelect(
                    "Component",
                    "jira.components",
                    choices=component_choices,
                    value=components_value,
                    help_text="Select default JIRA component for new issues",
                    allow_blank=True,
                )
            else:
                # Fallback to text input if no choices available
                components_value_str = ""
                if self.config.jira.system_field_defaults and "components" in self.config.jira.system_field_defaults:
                    components_list = self.config.jira.system_field_defaults["components"]
                    if isinstance(components_list, list):
                        components_value_str = ",".join(components_list)
                    else:
                        components_value_str = str(components_list)

                yield ConfigInput(
                    "Components",
                    "jira.components",
                    value=components_value_str,
                    help_text="Comma-separated list of JIRA components (e.g., ansible-saas,backend)",
                )

            yield Static("[bold]Custom Field Defaults[/bold]", classes="subsection-title")
            yield Static(
                "[dim]Set default values for custom fields that will be automatically applied when creating issues[/dim]",
                classes="section-help",
            )

            # Get available custom fields from field_mappings
            custom_field_choices = []
            if self.config.jira.field_mappings:
                for field_key, field_info in self.config.jira.field_mappings.items():
                    # Skip system fields (those without customfield_ id)
                    if isinstance(field_info, dict) and "id" in field_info:
                        field_id = field_info["id"]
                        if isinstance(field_id, str) and field_id.startswith("customfield_"):
                            # This is a custom field
                            field_name = field_info.get("name", field_key)
                            custom_field_choices.append((field_name, field_key))

            # If we have discovered custom fields, show inputs for them
            if custom_field_choices:
                # Get current custom field defaults
                current_defaults = self.config.jira.custom_field_defaults or {}

                # Show inputs for common custom fields (workstream, etc.)
                for field_name, field_key in sorted(custom_field_choices):
                    current_value = current_defaults.get(field_key, "")

                    # Get allowed values if they exist
                    field_info = self.config.jira.field_mappings.get(field_key)
                    allowed_values = field_info.get("allowed_values", []) if field_info else []

                    # If field has allowed values, use dropdown; otherwise use text input
                    if allowed_values and len(allowed_values) > 0:
                        # Create choices from allowed values
                        choices = []
                        for val in allowed_values:
                            if isinstance(val, dict) and "value" in val:
                                choices.append((val["value"], val["value"]))
                            elif isinstance(val, str):
                                choices.append((val, val))

                        if choices:
                            yield ConfigSelect(
                                field_name,
                                f"jira.custom_field_defaults.{field_key}",
                                choices=choices,
                                value=str(current_value) if current_value else None,
                                help_text=f"Default value for {field_name} field",
                                allow_blank=True,
                            )
                        else:
                            # Fallback to text input if choices parsing failed
                            yield ConfigInput(
                                field_name,
                                f"jira.custom_field_defaults.{field_key}",
                                value=str(current_value) if current_value else "",
                                help_text=f"Default value for {field_name} field",
                            )
                    else:
                        # No allowed values, use text input
                        yield ConfigInput(
                            field_name,
                            f"jira.custom_field_defaults.{field_key}",
                            value=str(current_value) if current_value else "",
                            help_text=f"Default value for {field_name} field",
                        )
            else:
                # No custom fields discovered yet
                yield Static(
                    "[dim]No custom fields discovered yet. Run 'daf config show --fields' to discover fields from your JIRA instance.[/dim]",
                    classes="section-help",
                )

            yield Static("[bold]Comment Visibility[/bold]", classes="subsection-title")

            yield ConfigSelect(
                "Comment Visibility Type",
                "jira.comment_visibility_type",
                choices=[("Group", "group"), ("Role", "role")],
                value=self.config.jira.comment_visibility_type if self.config.jira.comment_visibility_type else None,
                help_text="Choose 'group' for group-based or 'role' for role-based visibility",
                allow_blank=True,
            )

            # Show current selection context
            if self.config.jira.comment_visibility_type:
                visibility_hint = (
                    "Group name example: 'jira-users', 'developers', 'project-team'"
                    if self.config.jira.comment_visibility_type == "group"
                    else "Role name example: 'Administrators', 'Developers', 'Users'"
                )
            else:
                visibility_hint = "Group example: 'jira-users' | Role example: 'Administrators'"

            yield ConfigInput(
                "Comment Visibility Value",
                "jira.comment_visibility_value",
                value=self.config.jira.comment_visibility_value or "",
                help_text=visibility_hint,
            )

            yield Static(
                f"\n[dim]Current: {self.config.jira.comment_visibility_type or 'not set'} = "
                f"'{self.config.jira.comment_visibility_value or 'not set'}'[/dim]"
            )

            yield Static("[bold]JIRA Workflow Prompts[/bold]", classes="subsection-title")

            yield ConfigSelect(
                "Auto-add JIRA summary",
                "prompts.auto_add_issue_summary",
                choices=[
                    ("Always add summary", "true"),
                    ("Never add summary", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(self.config.prompts.auto_add_issue_summary),
                help_text="Automatically add session summary to JIRA when completing",
                allow_blank=False,
            )

            yield ConfigSelect(
                "Auto-update JIRA with PR URL",
                "prompts.auto_update_jira_pr_url",
                choices=[
                    ("Always update", "true"),
                    ("Never update", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(self.config.prompts.auto_update_jira_pr_url),
                help_text="Automatically update issue tracker ticket with PR URL when PR is created",
                allow_blank=False,
            )

    def _compose_repo_tab(self) -> ComposeResult:
        """Compose repository configuration tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]Repository Configuration[/bold cyan]", classes="section-title")
            yield Static(
                "Configure repository workspace and detection settings",
                classes="section-help",
            )

            # Note: Workspace configuration now uses the workspaces list editor below
            # The old single workspace field has been removed

            yield Static("[bold]Detection Settings[/bold]", classes="subsection-title")

            yield ConfigSelect(
                "Detection Method",
                "repos.detection.method",
                choices=[
                    ("Keyword Match", "keyword_match"),
                    ("Prompt", "prompt"),
                    ("Fuzzy Search", "fuzzy"),
                ],
                value=self.config.repos.detection.method,
                help_text="Method for detecting which repository to use",
                allow_blank=False,
            )

            yield ConfigSelect(
                "Detection Fallback",
                "repos.detection.fallback",
                choices=[
                    ("Prompt User", "prompt"),
                    ("Abort", "abort"),
                ],
                value=self.config.repos.detection.fallback,
                help_text="Fallback behavior when detection fails",
                allow_blank=False,
            )

            yield Static("\n[dim]Note: Keyword mappings must be configured manually in config.json[/dim]")

            yield Static("[bold]Git Workflow Settings[/bold]", classes="subsection-title")

            yield ConfigSelect(
                "Auto-checkout branch",
                "prompts.auto_checkout_branch",
                choices=[
                    ("Always checkout", "true"),
                    ("Never checkout", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(self.config.prompts.auto_checkout_branch),
                help_text="Automatically checkout session's branch when opening",
                allow_blank=False,
            )

            yield ConfigSelect(
                "Auto-sync with base branch",
                "prompts.auto_sync_with_base",
                choices=[
                    ("Always sync", "always"),
                    ("Never sync", "never"),
                    ("Prompt each time", "prompt"),
                ],
                value=self.config.prompts.auto_sync_with_base,
                help_text="Sync behavior when opening sessions",
                allow_blank=True,
            )

            yield ConfigSelect(
                "Default branch strategy",
                "prompts.default_branch_strategy",
                choices=[
                    ("Create from default branch (main/master)", "from_default"),
                    ("Create from current branch", "from_current"),
                ],
                value=self.config.prompts.default_branch_strategy,
                help_text="Default strategy for creating new branches",
                allow_blank=True,
            )

            yield Static("[bold]Commit Behavior[/bold]", classes="subsection-title")

            yield ConfigSelect(
                "Auto-commit on complete",
                "prompts.auto_commit_on_complete",
                choices=[
                    ("Always commit", "true"),
                    ("Never commit", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(self.config.prompts.auto_commit_on_complete),
                help_text="Automatically commit uncommitted changes when completing",
                allow_blank=False,
            )

            yield ConfigSelect(
                "Auto-accept AI commit message",
                "prompts.auto_accept_ai_commit_message",
                choices=[
                    ("Always accept", "true"),
                    ("Never accept (write my own)", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(self.config.prompts.auto_accept_ai_commit_message),
                help_text="Accept AI-generated commit messages without prompting",
                allow_blank=False,
            )

            yield Static("[bold]PR/MR Settings[/bold]", classes="subsection-title")

            yield ConfigInput(
                "PR/MR Template URL",
                "pr_template_url",
                value=self.config.pr_template_url or "",
                help_text="Optional: URL to PR/MR template. Three options: (1) Provide URL - AI fills template, (2) Leave empty - AI generates automatically, (3) Add template guidance to AGENTS.md/ORGANIZATION.md/TEAM.md",
                validator=URLValidator(),
            )

            yield ConfigSelect(
                "Auto-create PR/MR on complete",
                "prompts.auto_create_pr_on_complete",
                choices=[
                    ("Always create PR/MR", "true"),
                    ("Never create PR/MR", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(self.config.prompts.auto_create_pr_on_complete),
                help_text="Automatically create PR/MR when completing",
                allow_blank=False,
            )

            yield ConfigSelect(
                "PR/MR creation status",
                "prompts.auto_create_pr_status",
                choices=[
                    ("Always draft", "draft"),
                    ("Always ready for review", "ready"),
                    ("Prompt each time", "prompt"),
                ],
                value=self.config.prompts.auto_create_pr_status,
                help_text="Default status when creating PR/MR (draft or ready for review)",
                allow_blank=False,
            )

            yield ConfigSelect(
                "Auto-push to remote",
                "prompts.auto_push_to_remote",
                choices=[
                    ("Always push to remote", "true"),
                    ("Never push to remote", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(self.config.prompts.auto_push_to_remote),
                help_text="Automatically push branch to remote when completing session",
                allow_blank=False,
            )

            yield ConfigSelect(
                "Auto-select target branch",
                "prompts.auto_select_target_branch",
                choices=[
                    ("Always use default branch", "true"),
                    ("Never select target branch", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(self.config.prompts.auto_select_target_branch),
                help_text="Select target branch (e.g., release/2.5) when creating PR/MR",
                allow_blank=False,
            )

    def _compose_claude_tab(self) -> ComposeResult:
        """Compose AI configuration tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]AI Agent Configuration[/bold cyan]", classes="section-title")
            yield Static(
                "Configure your AI coding assistant and related features",
                classes="section-help",
            )

            # Agent Backend Selection
            yield Static("[bold]AI Agent Backend[/bold]", classes="subsection-title")

            # Check if agent_backend is enforced by enterprise or team
            agent_enforced_by = self._get_agent_backend_enforcement_source()

            if agent_enforced_by:
                # Agent backend is enforced - show as read-only
                agent_display_name = {
                    "claude": "Claude Code (fully tested)",
                    "github-copilot": "GitHub Copilot (experimental)",
                    "cursor": "Cursor (experimental)",
                    "windsurf": "Windsurf (experimental)",
                }.get(self.config.agent_backend, self.config.agent_backend)

                yield Static(
                    f"[bold]AI Agent:[/bold] {agent_display_name}\n"
                    f"[dim]Enforced by {agent_enforced_by} configuration (read-only)[/dim]",
                    classes="section-help",
                )
            else:
                # User can choose agent backend
                yield ConfigSelect(
                    "AI Agent",
                    "agent_backend",
                    choices=[
                        ("Claude Code (fully tested)", "claude"),
                        ("GitHub Copilot (experimental)", "github-copilot"),
                        ("Cursor (experimental)", "cursor"),
                        ("Windsurf (experimental)", "windsurf"),
                    ],
                    value=self.config.agent_backend,
                    help_text="Select which AI coding assistant to use with DevAIFlow",
                    allow_blank=False,
                )
                yield Static(
                    "[dim]Note: Only Claude Code is fully tested. Other agents are experimental.[/dim]",
                    classes="section-help",
                )

            # Claude-specific settings (only shown when Claude is selected)
            is_claude = self.config.agent_backend == "claude"

            # GCP Vertex AI Section (Claude only)
            with Vertical(id="claude_vertex_ai_section"):
                yield Static("[bold]GCP Vertex AI (Claude only)[/bold]", classes="subsection-title")

                # Check if Vertex AI is available
                vertex_available = _is_vertex_ai_available()

                if vertex_available:
                    # Vertex AI is available - show region selector
                    vertex_regions = _get_vertex_ai_regions()
                    yield ConfigSelect(
                        "GCP Vertex AI Region",
                        "gcp_vertex_region",
                        choices=vertex_regions,
                        value=self.config.gcp_vertex_region if self.config.gcp_vertex_region else None,
                        help_text="Select the GCP region for Claude on Vertex AI (leave empty to use default)",
                        allow_blank=True,
                    )
                else:
                    # Vertex AI not available - show disabled field with explanation
                    yield Static(
                        "[dim]GCP Vertex AI Region: [italic]Not available[/italic][/dim]\n"
                        "[dim]This setting is only available when using Claude Code with GCP Vertex AI.[/dim]\n"
                        "[dim]Set CLAUDE_CODE_USE_VERTEX environment variable to enable this feature.[/dim]"
                    )

            yield Static("[bold]Session Summary[/bold]", classes="subsection-title")
            yield Static(
                "[dim]Note: AI-powered summaries only work with Claude Code. "
                "Other agents automatically use local mode (git-based).[/dim]",
                classes="section-help",
            )

            yield ConfigSelect(
                "Summary Mode",
                "session_summary.mode",
                choices=[
                    ("Local only", "local"),
                    ("AI-powered (Claude only)", "ai"),
                    ("Both local and AI (Claude only)", "both"),
                ],
                value=self.config.session_summary.mode,
                help_text="How to generate session summaries on completion",
                allow_blank=False,
            )

            # API Key field - always compose it, visibility controlled later
            # Must be composed first before we can hide it
            yield ConfigInput(
                "API Key Environment Variable",
                "session_summary.api_key_env",
                value=self.config.session_summary.api_key_env,
                help_text="Name of environment variable with Anthropic API key",
                id="session_summary_api_key_field",
            )

            # Claude-only sections
            with Vertical(id="claude_slash_commands_section"):
                yield Static("[bold]Claude Code Slash Commands (Claude only)[/bold]", classes="subsection-title")
                yield Static(
                    "Bundled slash commands provide helpful prompts for multi-conversation sessions. "
                    "Commands are installed to <workspace>/.claude/commands/",
                    classes="section-help",
                )

                with Horizontal(classes="button-bar"):
                    yield Button("Upgrade Commands", variant="primary", id="upgrade_commands")

            with Vertical(id="claude_multi_conversation_section"):
                yield Static("[bold]Multi-Conversation Sessions (Claude only)[/bold]", classes="subsection-title")

                yield ConfigSelect(
                    "Auto-load related conversations prompt",
                    "prompts.auto_load_related_conversations",
                    choices=[
                        ("Enable auto-load prompt", "true"),
                        ("Disable auto-load prompt", "false"),
                    ],
                    value="true" if self.config.prompts.auto_load_related_conversations else "false",
                    help_text="Prompt Claude to read conversations from other repositories in multi-project sessions",
                    allow_blank=False,
                )

            yield Static("[bold]AI Agent Behavior[/bold]", classes="subsection-title")

            # Use auto_launch_agent if set, otherwise fall back to auto_launch_claude for backward compatibility
            auto_launch_value = (
                self.config.prompts.auto_launch_agent
                if self.config.prompts.auto_launch_agent is not None
                else self.config.prompts.auto_launch_claude
            )

            yield ConfigSelect(
                "Auto-launch AI Agent",
                "prompts.auto_launch_agent",
                choices=[
                    ("Always launch", "true"),
                    ("Never launch", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(auto_launch_value),
                help_text="Automatically launch your selected AI agent when creating or opening sessions",
                allow_blank=False,
            )

            yield Static("[bold]Testing Preferences[/bold]", classes="subsection-title")

            yield ConfigSelect(
                "Show unit testing instructions",
                "prompts.show_prompt_unit_tests",
                choices=[
                    ("Show testing instructions", "true"),
                    ("Hide testing instructions", "false"),
                ],
                value="true" if self.config.prompts.show_prompt_unit_tests else "false",
                help_text="Show unit testing instructions in initial prompt for development sessions",
                allow_blank=False,
            )

            # Context Files section (placed last due to dynamic size)
            yield Static("[bold]Context Files[/bold]", classes="subsection-title")
            yield Static(
                "Configure additional context files to include in initial prompts. "
                "AGENTS.md and CLAUDE.md are always included if they exist.",
                classes="section-help",
            )

            # Container for context file entries (will be updated dynamically)
            # Only show non-hidden files (skills are auto-managed and marked as hidden)
            with Vertical(id="context_files_list"):
                visible_files = [f for f in self.config.context_files.files if not f.hidden]
                if visible_files:
                    for idx, ctx_file in enumerate(self.config.context_files.files):
                        if not ctx_file.hidden:
                            yield ContextFileEntry(idx, ctx_file)
                else:
                    yield Static("[dim]No additional context files configured[/dim]", id="empty_message")

            # Add button
            with Horizontal(classes="button-bar"):
                yield Button("Add Context File", variant="success", id="add_context_file")

    def _compose_workspaces_tab(self) -> ComposeResult:
        """Compose workspaces configuration tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]Workspace Management[/bold cyan]", classes="section-title")
            yield Static(
                "Manage multiple workspace directories for concurrent multi-branch development. "
                "The last-used workspace (marked with ⭐) is automatically selected for new sessions.",
                classes="section-help",
            )

            # Container for workspace entries (will be updated dynamically)
            with Vertical(id="workspaces_list"):
                if self.config.repos.workspaces:
                    last_used = self.config.repos.last_used_workspace
                    for idx, workspace in enumerate(self.config.repos.workspaces):
                        is_last_used = (workspace.name == last_used)
                        yield WorkspaceEntry(idx, workspace, is_last_used=is_last_used)
                else:
                    yield Static(
                        "[dim]No workspaces configured. Add your first workspace to get started.[/dim]",
                        id="empty_workspaces_message"
                    )

            # Add button
            with Horizontal(classes="button-bar"):
                yield Button("Add Workspace", variant="success", id="add_workspace")

            # Help text
            yield Static(
                "\n[dim]Tips:[/dim]\n"
                "[dim]• Click 'Use This' to set a workspace as your default (last-used)[/dim]\n"
                "[dim]• The last-used workspace is automatically selected when creating new sessions[/dim]\n"
                "[dim]• Use the -w flag to override the last-used workspace per session[/dim]",
                classes="section-help"
            )

    def _compose_session_workflow_tab(self) -> ComposeResult:
        """Compose session workflow configuration tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]Session Workflow Configuration[/bold cyan]", classes="section-title")
            yield Static(
                "Configure automation and behavior for session lifecycle",
                classes="section-help",
            )

            yield Static("[bold]Session Lifecycle[/bold]", classes="subsection-title")

            yield ConfigSelect(
                "Auto-complete on exit",
                "prompts.auto_complete_on_exit",
                choices=[
                    ("Always run daf complete", "true"),
                    ("Never run daf complete", "false"),
                    ("Prompt each time", "prompt"),
                ],
                value=_bool_to_choice(self.config.prompts.auto_complete_on_exit),
                help_text="Automatically run 'daf complete' when Claude Code session exits",
                allow_blank=False,
            )

            yield Static("[bold]Time Tracking[/bold]", classes="subsection-title")

            yield ConfigCheckbox(
                "Enable Time Tracking",
                "jira.time_tracking",
                value=self.config.jira.time_tracking,
                help_text="Track time spent on work sessions",
            )

    def _compose_advanced_tab(self) -> ComposeResult:
        """Compose advanced configuration tab content."""
        with VerticalScroll():
            yield Static("[bold cyan]Advanced Configuration[/bold cyan]", classes="section-title")
            yield Static(
                "Configure advanced settings",
                classes="section-help",
            )

            yield Static("[bold]Update Checker[/bold]", classes="subsection-title")
            yield Static(
                "Configure automatic version update checking from GitLab releases",
                classes="section-help",
            )

            yield ConfigInput(
                "Update Checker Timeout (seconds)",
                "update_checker_timeout",
                value=str(self.config.update_checker_timeout),
                help_text="Timeout in seconds for checking GitLab for new versions (default: 10)",
                validator=Integer(minimum=1, maximum=60),
            )

            # Note: Patches section removed - patch system deprecated
            # Configuration now uses 4-file format (backends/jira.json, organization.json, team.json, config.json)

    # Note: _compose_patches_tab() removed - patch system deprecated
    # Configuration now uses 4-file format (backends/jira.json, organization.json, team.json, config.json)

    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())

    def action_preview(self) -> None:
        """Show configuration preview."""
        # Collect current values from all inputs
        self._collect_values()
        self.push_screen(PreviewScreen(self.config))

    def action_save(self) -> None:
        """Save configuration changes."""
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
            self.config_loader.save_config(self.config)
            self.notify("Configuration saved successfully!", severity="information")
            self.modified = False
            self.original_config = self.config.model_copy(deep=True)
        except Exception as e:
            self.notify(f"Failed to save configuration: {e}", severity="error")

    def action_toggle_mode(self) -> None:
        """Toggle between Simple and Advanced mode."""
        try:
            # Collect current values before exit
            self._collect_values()

            # Save current config if modified
            if self.modified:
                try:
                    self.config_loader.save_config(self.config)
                    self.notify("Configuration saved", severity="information")
                except Exception as e:
                    self.notify(f"Failed to save before mode switch: {e}", severity="error")
                    return

            # Exit with return value to indicate mode to restart in
            new_mode = not self.advanced_mode
            mode_name = "Advanced" if new_mode else "Simple"
            self.notify(f"Switching to {mode_name} Mode...", severity="information")
            self.exit({"restart_mode": "advanced" if new_mode else "simple"})
        except Exception as e:
            self.notify(f"Toggle mode failed: {e}", severity="error")

    def action_quit(self) -> None:
        """Quit the application."""
        if self.modified:
            # TODO: Add confirmation dialog
            self.notify("Unsaved changes will be lost!", severity="warning")
        self.exit()

    def on_context_file_entry_edit_pressed(self, message: ContextFileEntry.EditPressed) -> None:
        """Handle edit button press on context file entry.

        Args:
            message: The edit pressed message containing index and context file
        """
        def handle_edit_result(result):
            """Handle the result from the edit screen."""
            if result:
                ctx_file, index = result
                # Update the context file in config
                if 0 <= index < len(self.config.context_files.files):
                    self.config.context_files.files[index] = ctx_file
                    self._refresh_context_files_list()
                    self.notify(f"Updated context file: {ctx_file.path}", severity="information")
                    self.modified = True

        self.push_screen(
            AddContextFileScreen(existing_file=message.context_file, index=message.index),
            handle_edit_result
        )

    def on_context_file_entry_remove_pressed(self, message: ContextFileEntry.RemovePressed) -> None:
        """Handle remove button press on context file entry.

        Args:
            message: The remove pressed message containing index
        """
        # Remove the context file from config
        if 0 <= message.index < len(self.config.context_files.files):
            removed_file = self.config.context_files.files.pop(message.index)
            self._refresh_context_files_list()
            self.notify(f"Removed context file: {removed_file.path}", severity="information")
            self.modified = True

    def on_workspace_entry_edit_pressed(self, message: WorkspaceEntry.EditPressed) -> None:
        """Handle edit button press on workspace entry.

        Args:
            message: The edit pressed message containing index and workspace
        """
        def handle_edit_result(result):
            """Handle the result from the edit screen."""
            if result:
                workspace, index = result
                # Update the workspace in config
                if 0 <= index < len(self.config.repos.workspaces):
                    # Check if name changed and it's the last_used workspace
                    old_workspace = self.config.repos.workspaces[index]
                    if (old_workspace.name == self.config.repos.last_used_workspace and
                        old_workspace.name != workspace.name):
                        # Update last_used_workspace to new name
                        self.config.repos.last_used_workspace = workspace.name

                    self.config.repos.workspaces[index] = workspace
                    self._refresh_workspaces_list()
                    self.notify(f"Updated workspace: {workspace.name}", severity="information")
                    self.modified = True

        self.push_screen(
            AddEditWorkspaceScreen(existing_workspace=message.workspace, index=message.index),
            handle_edit_result
        )

    def on_workspace_entry_remove_pressed(self, message: WorkspaceEntry.RemovePressed) -> None:
        """Handle remove button press on workspace entry.

        Args:
            message: The remove pressed message containing index
        """
        # Remove the workspace from config
        if 0 <= message.index < len(self.config.repos.workspaces):
            removed_workspace = self.config.repos.workspaces.pop(message.index)

            # If this was the last_used workspace, update to first remaining workspace
            if removed_workspace.name == self.config.repos.last_used_workspace:
                if self.config.repos.workspaces:
                    self.config.repos.last_used_workspace = self.config.repos.workspaces[0].name
                else:
                    self.config.repos.last_used_workspace = None

            self._refresh_workspaces_list()
            self.notify(f"Removed workspace: {removed_workspace.name}", severity="information")
            self.modified = True

    def on_workspace_entry_set_as_last_used_pressed(self, message: WorkspaceEntry.SetAsLastUsedPressed) -> None:
        """Handle set as last used button press on workspace entry.

        Args:
            message: The set as last used message containing workspace name
        """
        self.config.repos.last_used_workspace = message.workspace_name
        self._refresh_workspaces_list()
        self.notify(f"Set '{message.workspace_name}' as last-used workspace", severity="information")
        self.modified = True

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change events.

        Args:
            event: The input changed event
        """
        # Check if it's the workspace input
        if event.input.id == "input_repos_workspace":
            self._on_workspace_changed(event.value)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select dropdown changes.

        Args:
            event: The select changed event
        """
        # Check if it's the agent_backend select
        if event.select.id == "select_agent_backend":
            self._on_agent_backend_changed(event.value)
        # Check if it's the summary mode select
        elif event.select.id == "select_session_summary_mode":
            self._on_summary_mode_changed(event.value)

    def _on_agent_backend_changed(self, agent_backend: str) -> None:
        """Handle agent backend selection changes.

        Shows/hides Claude-specific sections based on selected agent.

        Args:
            agent_backend: The selected agent backend value
        """
        is_claude = agent_backend == "claude"

        # Toggle visibility of Claude-specific sections
        try:
            # GCP Vertex AI section
            vertex_section = self.query_one("#claude_vertex_ai_section", Vertical)
            vertex_section.display = is_claude

            # Slash Commands section
            slash_commands_section = self.query_one("#claude_slash_commands_section", Vertical)
            slash_commands_section.display = is_claude

            # Multi-Conversation Sessions section
            multi_conv_section = self.query_one("#claude_multi_conversation_section", Vertical)
            multi_conv_section.display = is_claude

            # Update API key visibility (depends on both agent and summary mode)
            self._update_api_key_visibility()

        except NoMatches:
            # Sections might not exist yet during initial composition
            pass

    def _on_summary_mode_changed(self, summary_mode: str) -> None:
        """Handle summary mode selection changes.

        Shows/hides API key field based on summary mode (only for AI modes).

        Args:
            summary_mode: The selected summary mode value
        """
        # Update API key visibility (depends on both agent and summary mode)
        self._update_api_key_visibility()

    def _update_api_key_visibility(self) -> None:
        """Update API key field visibility based on agent backend and summary mode.

        API key should only be visible when:
        - Agent is Claude Code AND
        - Summary mode is "ai" or "both"
        """
        try:
            # Get current values
            agent_backend = self.config.agent_backend

            # Try to get summary mode from select widget
            try:
                summary_mode_select = self.query_one("#select_session_summary_mode", Select)
                summary_mode = summary_mode_select.value if summary_mode_select.value != Select.BLANK else "local"
            except NoMatches:
                # Fallback to config value if widget not found
                summary_mode = self.config.session_summary.mode

            # Show API key only if Claude + AI mode
            is_claude = agent_backend == "claude"
            needs_api_key = summary_mode in ("ai", "both")
            should_show = is_claude and needs_api_key

            api_key_field = self.query_one("#session_summary_api_key_field", ConfigInput)
            api_key_field.display = should_show

        except NoMatches:
            # Field might not exist yet during initial composition
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: The button pressed event
        """
        if event.button.id == "add_context_file":
            def handle_add_result(result):
                """Handle the result from the add screen."""
                if result:
                    ctx_file, _ = result
                    # Add the new context file to config
                    self.config.context_files.files.append(ctx_file)
                    self._refresh_context_files_list()
                    self.notify(f"Added context file: {ctx_file.path}", severity="information")
                    self.modified = True

            self.push_screen(AddContextFileScreen(), handle_add_result)

        elif event.button.id == "add_workspace":
            def handle_add_workspace_result(result):
                """Handle the result from the add workspace screen."""
                if result:
                    workspace, _ = result
                    # Check if workspace name already exists
                    if any(w.name == workspace.name for w in self.config.repos.workspaces):
                        self.notify(f"Workspace '{workspace.name}' already exists", severity="error")
                        return

                    # Add the new workspace to config
                    self.config.repos.workspaces.append(workspace)

                    # If this is the first workspace, set it as last_used
                    if len(self.config.repos.workspaces) == 1:
                        self.config.repos.last_used_workspace = workspace.name

                    self._refresh_workspaces_list()
                    self.notify(f"Added workspace: {workspace.name}", severity="information")
                    self.modified = True

            self.push_screen(AddEditWorkspaceScreen(), handle_add_workspace_result)

        elif event.button.id == "upgrade_commands":
            self._handle_upgrade_commands()

    def _handle_upgrade_commands(self) -> None:
        """Handle the upgrade commands button press."""
        from devflow.utils.claude_commands import install_or_upgrade_commands

        workspace_path = self.config.repos.get_default_workspace_path()
        if not workspace_path:
            self.notify("No default workspace configured. Please configure a workspace first.", severity="error")
            return

        workspace = workspace_path
        self.notify("Upgrading slash commands...", severity="information")

        try:
            changed, up_to_date, failed = install_or_upgrade_commands(workspace, quiet=True)

            if changed:
                self.notify(f"✓ Upgraded {len(changed)} command(s)", severity="information")
            elif up_to_date:
                self.notify("✓ All commands are up-to-date", severity="information")

            if failed:
                self.notify(f"✗ Failed to upgrade {len(failed)} command(s)", severity="error")

        except FileNotFoundError as e:
            self.notify(str(e), severity="error")
        except Exception as e:
            self.notify(f"Error upgrading commands: {e}", severity="error")

    def _refresh_context_files_list(self) -> None:
        """Refresh the context files list display after add/edit/remove.

        Only shows non-hidden files. Hidden files are auto-managed (like skills)
        and should not be shown in the TUI.
        """
        # Get the context files list container
        try:
            list_container = self.query_one("#context_files_list", Vertical)

            # Remove all existing children
            list_container.remove_children()

            # Re-add only non-hidden context file entries
            visible_files = [f for f in self.config.context_files.files if not f.hidden]
            if visible_files:
                for idx, ctx_file in enumerate(self.config.context_files.files):
                    if not ctx_file.hidden:
                        list_container.mount(ContextFileEntry(idx, ctx_file))
            else:
                list_container.mount(Static("[dim]No additional context files configured[/dim]", id="empty_message"))

        except Exception as e:
            self.notify(f"Error refreshing context files list: {e}", severity="error")

    def _refresh_workspaces_list(self) -> None:
        """Refresh the workspaces list display after add/edit/remove/set-as-last-used."""
        # Get the workspaces list container
        try:
            list_container = self.query_one("#workspaces_list", Vertical)

            # Remove all existing children
            list_container.remove_children()

            # Re-add workspace entries
            if self.config.repos.workspaces:
                last_used = self.config.repos.last_used_workspace
                for idx, workspace in enumerate(self.config.repos.workspaces):
                    is_last_used = (workspace.name == last_used)
                    list_container.mount(WorkspaceEntry(idx, workspace, is_last_used=is_last_used))
            else:
                list_container.mount(
                    Static(
                        "[dim]No workspaces configured. Add your first workspace to get started.[/dim]",
                        id="empty_workspaces_message"
                    )
                )

        except Exception as e:
            self.notify(f"Error refreshing workspaces list: {e}", severity="error")

    def _collect_values(self) -> None:
        """Collect all values from input widgets and update config."""
        # Helper to convert config key to valid ID
        def key_to_id(prefix: str, key: str) -> str:
            return f"#{prefix}_{key.replace('.', '_')}"

        # JIRA settings (only in Simple mode)
        if not self.advanced_mode:
            try:
                self.config.jira.url = self.query_one(key_to_id("input", "jira.url"), Input).value.strip()

                project_val = self.query_one(key_to_id("input", "jira.project"), Input).value.strip()
                self.config.jira.project = project_val if project_val else None

                # Components - try dropdown first, fallback to text input
                try:
                    # Try to get from dropdown (ConfigSelect)
                    components_val = self.query_one(key_to_id("select", "jira.components"), Select).value
                    if components_val and components_val != Select.BLANK:
                        # Single component from dropdown - store as list
                        if not self.config.jira.system_field_defaults:
                            self.config.jira.system_field_defaults = {}
                        self.config.jira.system_field_defaults["components"] = [components_val]
                    elif self.config.jira.system_field_defaults and "components" in self.config.jira.system_field_defaults:
                        # Clear components if blank selected
                        del self.config.jira.system_field_defaults["components"]
                except NoMatches:
                    # Fallback to text input (ConfigInput) if dropdown not found
                    try:
                        components_val = self.query_one(key_to_id("input", "jira.components"), Input).value.strip()
                        if components_val:
                            components_list = [c.strip() for c in components_val.split(",") if c.strip()]
                            if not self.config.jira.system_field_defaults:
                                self.config.jira.system_field_defaults = {}
                            self.config.jira.system_field_defaults["components"] = components_list
                        elif self.config.jira.system_field_defaults and "components" in self.config.jira.system_field_defaults:
                            # Clear components if empty
                            del self.config.jira.system_field_defaults["components"]
                    except NoMatches:
                        # Neither widget found - skip
                        pass

                # Collect custom field defaults
                if self.config.jira.field_mappings:
                    # Initialize custom_field_defaults dict if needed
                    if not self.config.jira.custom_field_defaults:
                        self.config.jira.custom_field_defaults = {}

                    # Collect each custom field
                    for field_key, field_info in self.config.jira.field_mappings.items():
                        if isinstance(field_info, dict) and "id" in field_info:
                            field_id = field_info["id"]
                            if isinstance(field_id, str) and field_id.startswith("customfield_"):
                                # This is a custom field - try to collect its value
                                config_key = f"jira.custom_field_defaults.{field_key}"

                                try:
                                    # Try dropdown first
                                    value = self.query_one(key_to_id("select", config_key), Select).value
                                    if value and value != Select.BLANK:
                                        self.config.jira.custom_field_defaults[field_key] = value
                                    elif field_key in self.config.jira.custom_field_defaults:
                                        # Clear if blank selected
                                        del self.config.jira.custom_field_defaults[field_key]
                                except NoMatches:
                                    # Try text input
                                    try:
                                        value = self.query_one(key_to_id("input", config_key), Input).value.strip()
                                        if value:
                                            self.config.jira.custom_field_defaults[field_key] = value
                                        elif field_key in self.config.jira.custom_field_defaults:
                                            # Clear if empty
                                            del self.config.jira.custom_field_defaults[field_key]
                                    except NoMatches:
                                        # Widget not found - skip this field
                                        pass

                self.config.jira.time_tracking = self.query_one(key_to_id("checkbox", "jira.time_tracking"), Checkbox).value

                comment_type = self.query_one(key_to_id("select", "jira.comment_visibility_type"), Select).value
                self.config.jira.comment_visibility_type = comment_type if comment_type != Select.BLANK else None

                comment_val = self.query_one(key_to_id("input", "jira.comment_visibility_value"), Input).value.strip()
                self.config.jira.comment_visibility_value = comment_val if comment_val else None

            except Exception as e:
                self.notify(f"Error collecting JIRA values: {e}", severity="error")

        # Repository settings (only in Simple mode)
        if not self.advanced_mode:
            try:
                # Note: repos.workspace field removed - now using workspaces list

                detection_method = self.query_one(key_to_id("select", "repos.detection.method"), Select).value
                if detection_method and detection_method != Select.BLANK:
                    self.config.repos.detection.method = detection_method

                detection_fallback = self.query_one(key_to_id("select", "repos.detection.fallback"), Select).value
                if detection_fallback and detection_fallback != Select.BLANK:
                    self.config.repos.detection.fallback = detection_fallback

                # PR Template URL
                pr_template_val = self.query_one(key_to_id("input", "pr_template_url"), Input).value.strip()
                self.config.pr_template_url = pr_template_val if pr_template_val else None

            except Exception as e:
                self.notify(f"Error collecting repository values: {e}", severity="error")

        # Prompts settings (only in Simple mode)
        if not self.advanced_mode:
            try:
                # Use _choice_to_bool to convert "true"/"false"/"prompt" to Optional[bool]
                self.config.prompts.auto_commit_on_complete = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_commit_on_complete"), Select).value
                )

                self.config.prompts.auto_accept_ai_commit_message = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_accept_ai_commit_message"), Select).value
                )

                self.config.prompts.auto_create_pr_on_complete = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_create_pr_on_complete"), Select).value
                )

                pr_status_val = self.query_one(key_to_id("select", "prompts.auto_create_pr_status"), Select).value
                self.config.prompts.auto_create_pr_status = pr_status_val if pr_status_val and pr_status_val != Select.BLANK else "prompt"

                self.config.prompts.auto_add_issue_summary = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_add_issue_summary"), Select).value
                )

                self.config.prompts.auto_update_jira_pr_url = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_update_jira_pr_url"), Select).value
                )

                self.config.prompts.auto_push_to_remote = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_push_to_remote"), Select).value
                )

                self.config.prompts.auto_select_target_branch = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_select_target_branch"), Select).value
                )

                # Use auto_launch_agent (new field) instead of auto_launch_claude (deprecated)
                self.config.prompts.auto_launch_agent = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_launch_agent"), Select).value
                )
                # Also update auto_launch_claude for backward compatibility
                self.config.prompts.auto_launch_claude = self.config.prompts.auto_launch_agent

                self.config.prompts.auto_checkout_branch = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_checkout_branch"), Select).value
                )

                sync_val = self.query_one(key_to_id("select", "prompts.auto_sync_with_base"), Select).value
                self.config.prompts.auto_sync_with_base = sync_val if sync_val != Select.BLANK else None

                self.config.prompts.auto_complete_on_exit = _choice_to_bool(
                    self.query_one(key_to_id("select", "prompts.auto_complete_on_exit"), Select).value
                )

                branch_strat = self.query_one(key_to_id("select", "prompts.default_branch_strategy"), Select).value
                self.config.prompts.default_branch_strategy = branch_strat if branch_strat != Select.BLANK else None

                # show_prompt_unit_tests is a boolean field (not tri-state)
                show_unit_tests = self.query_one(key_to_id("select", "prompts.show_prompt_unit_tests"), Select).value
                self.config.prompts.show_prompt_unit_tests = (show_unit_tests == "true")

                # auto_load_related_conversations is a boolean field (not tri-state)
                auto_load_conv = self.query_one(key_to_id("select", "prompts.auto_load_related_conversations"), Select).value
                self.config.prompts.auto_load_related_conversations = (auto_load_conv == "true")

            except Exception as e:
                self.notify(f"Error collecting prompts values: {e}", severity="error")

        # AI Agent configuration settings (only in Simple mode)
        if not self.advanced_mode:
            try:
                # Agent backend selection (only if not enforced by org/team)
                if not self._get_agent_backend_enforcement_source():
                    # User can choose - collect the value
                    agent_backend_val = self.query_one(key_to_id("select", "agent_backend"), Select).value
                    if agent_backend_val and agent_backend_val != Select.BLANK:
                        self.config.agent_backend = agent_backend_val
                # If enforced, keep the value from org/team (already in self.config)

                # Only collect region value if Vertex AI is available (field exists) and using Claude
                # Always preserve the value even when not using Claude
                if _is_vertex_ai_available() and self.config.agent_backend == "claude":
                    region_val = self.query_one(key_to_id("select", "gcp_vertex_region"), Select).value
                    self.config.gcp_vertex_region = region_val if region_val != Select.BLANK else None
                # If Vertex AI not available or not using Claude, keep existing value

                # Session summary settings (works for all agents)
                summary_mode = self.query_one(key_to_id("select", "session_summary.mode"), Select).value
                if summary_mode and summary_mode != Select.BLANK:
                    self.config.session_summary.mode = summary_mode

                # API key env - query from ConfigInput widget (always exists, just might be hidden)
                try:
                    api_key_field = self.query_one("#session_summary_api_key_field", ConfigInput)
                    api_key_env_val = api_key_field.get_value()
                    if api_key_env_val:
                        self.config.session_summary.api_key_env = api_key_env_val
                except NoMatches:
                    # Keep existing value if field not found
                    pass

                # Auto-load related conversations (only for Claude, but preserve value)
                # Only query the field if Claude is selected (field only exists when is_claude=True)
                if self.config.agent_backend == "claude":
                    auto_load_conv = self.query_one(key_to_id("select", "prompts.auto_load_related_conversations"), Select).value
                    self.config.prompts.auto_load_related_conversations = (auto_load_conv == "true")
                # Otherwise keep existing value

            except Exception as e:
                self.notify(f"Error collecting AI agent configuration values: {e}", severity="error")

        # Update checker settings (only in Simple mode)
        if not self.advanced_mode:
            try:
                timeout_val = self.query_one("#input_update_checker_timeout", Input).value.strip()
                if timeout_val:
                    self.config.update_checker_timeout = int(timeout_val)
            except Exception as e:
                self.notify(f"Error collecting update checker values: {e}", severity="error")

        # Note: Patches settings removed - patch system deprecated
        # Configuration now uses 4-file format (backends/jira.json, organization.json, team.json, config.json)

        # Organization-level fields (Advanced Mode only)
        # These are saved directly to organization.json, not the merged Config
        if self.advanced_mode:
            try:
                import json
                from pathlib import Path

                # Read current organization.json
                org_file = self.config_loader.config_dir / "organization.json"
                if org_file.exists():
                    with open(org_file, 'r') as f:
                        org_data = json.load(f)
                else:
                    org_data = {}

                # Collect organization.jira_project
                try:
                    jira_project_val = self.query_one(key_to_id("input", "organization.jira_project"), Input).value.strip()
                    if jira_project_val:
                        org_data['jira_project'] = jira_project_val
                        # Also update the merged config for consistency
                        self.config.jira.project = jira_project_val
                except NoMatches:
                    pass  # Field not found, skip

                # Collect organization.hierarchical_config_source
                try:
                    hierarchical_config_val = self.query_one(key_to_id("input", "organization.hierarchical_config_source"), Input).value.strip()
                    org_data['hierarchical_config_source'] = hierarchical_config_val if hierarchical_config_val else None
                except NoMatches:
                    pass  # Field not found, skip

                # Save updated organization.json
                org_file.parent.mkdir(parents=True, exist_ok=True)
                with open(org_file, 'w') as f:
                    json.dump(org_data, f, indent=2)

            except Exception as e:
                self.notify(f"Error collecting organization values: {e}", severity="error")

        # Mark as modified
        if self.config != self.original_config:
            self.modified = True


    def _validate_all(self) -> List[str]:
        """Validate all input fields.

        Returns:
            List of validation error messages
        """
        errors = []

        # Required fields
        if not self.config.jira.url:
            errors.append("JIRA URL is required")
        if not self.config.repos.workspaces or len(self.config.repos.workspaces) == 0:
            errors.append("At least one workspace is required")

        # Workspace path validation
        if self.config.repos.workspaces:
            for workspace in self.config.repos.workspaces:
                try:
                    workspace_path = Path(workspace.path).expanduser()
                    if not workspace_path.exists():
                        errors.append(f"Workspace '{workspace.name}' directory does not exist: {workspace.path}")
                    elif not workspace_path.is_dir():
                        errors.append(f"Workspace '{workspace.name}' path is not a directory: {workspace.path}")
                except Exception as e:
                    errors.append(f"Invalid workspace '{workspace.name}' path: {e}")

        # URL validation
        if not (self.config.jira.url.startswith("http://") or self.config.jira.url.startswith("https://")):
            errors.append("JIRA URL must start with http:// or https://")

        return errors

    def _on_workspace_changed(self, workspace_path: str) -> None:
        """Called when workspace value changes.

        Args:
            workspace_path: The new workspace path
        """
        if not workspace_path or not workspace_path.strip():
            return

        try:
            expanded_path = Path(workspace_path).expanduser()
            if expanded_path.exists() and expanded_path.is_dir():
                repos = [
                    d for d in expanded_path.iterdir()
                    if d.is_dir() and not d.name.startswith('.')
                ]
                self.notify(
                    f"Found {len(repos)} directories in workspace",
                    severity="information",
                    timeout=3
                )
        except (OSError, RuntimeError):
            # OSError: permission denied, file not found, etc.
            # RuntimeError: directory deleted during iteration
            # Ignore errors during live typing
            pass

    def _compose_enterprise_tab(self) -> ComposeResult:
        """Compose Enterprise configuration tab (Advanced Mode)."""
        with VerticalScroll():
            yield Static("[bold cyan]Enterprise Configuration[/bold cyan]", classes="section-title")
            yield Static(
                "Enterprise-wide settings enforced across all users (read-only)",
                classes="section-help",
            )

            # Load enterprise config to display
            enterprise_config = self.config_loader._load_enterprise_config()

            if not enterprise_config:
                yield Static(
                    "[dim]No enterprise.json file found at $DEVAIFLOW_HOME/enterprise.json[/dim]",
                    classes="section-help"
                )
                yield Static(
                    "[yellow]Enterprise configuration is optional and managed by administrators.[/yellow]",
                    classes="section-help"
                )
            else:
                # Show read-only enterprise settings
                if enterprise_config.agent_backend:
                    yield Static(f"[bold]AI Agent Backend:[/bold] {enterprise_config.agent_backend}")
                    yield Static(
                        "[dim]This setting is enforced by your organization[/dim]",
                        classes="section-help"
                    )

                if enterprise_config.backend_overrides:
                    yield Static("\n[bold]Backend Overrides:[/bold]")
                    yield Static(
                        "[dim]Enterprise has configured field metadata corrections[/dim]",
                        classes="section-help"
                    )

                yield Static("\n[yellow]ℹ Enterprise settings are read-only and managed by administrators[/yellow]")

    def _compose_organization_tab(self) -> ComposeResult:
        """Compose Organization configuration tab (Advanced Mode)."""
        with VerticalScroll():
            yield Static("[bold cyan]Organization Configuration[/bold cyan]", classes="section-title")
            yield Static(
                "Project-specific settings (saved to organization.json)",
                classes="section-help",
            )

            # Load organization config
            org_config = self.config_loader._load_organization_config()

            yield ConfigInput(
                "JIRA Project Key",
                "organization.jira_project",
                value=org_config.jira_project if org_config and org_config.jira_project else "",
                help_text="Default JIRA project for this organization (e.g., AAP, PROJ)",
            )

            yield ConfigInput(
                "Hierarchical Config Source",
                "organization.hierarchical_config_source",
                value=org_config.hierarchical_config_source if org_config and org_config.hierarchical_config_source else "",
                help_text="URL or path to hierarchical config files (e.g., file:///company/shared/devaiflow/configs or https://github.com/company/devaiflow-config/configs)",
            )

            yield Static("\n[dim]Advanced: Sync Filters[/dim]", classes="subsection-title")
            yield Static(
                "[dim]Configure which JIRA tickets to sync with 'daf sync'[/dim]",
                classes="section-help"
            )

            # Show current sync filter configuration
            if org_config and org_config.sync_filters and "sync" in org_config.sync_filters:
                sync_filter = org_config.sync_filters["sync"]
                if sync_filter.status:
                    yield Static(f"[dim]Sync Status:[/dim] {', '.join(sync_filter.status)}")
                if sync_filter.required_fields:
                    yield Static(f"[dim]Required Fields:[/dim] {', '.join(sync_filter.required_fields)}")
                if sync_filter.assignee:
                    yield Static(f"[dim]Assignee Filter:[/dim] {sync_filter.assignee}")

            yield Static("\n[yellow]💡 See ORGANIZATION.md for detailed policies and templates[/yellow]")

    def _compose_team_tab(self) -> ComposeResult:
        """Compose Team configuration tab (Advanced Mode)."""
        with VerticalScroll():
            yield Static("[bold cyan]Team Configuration[/bold cyan]", classes="section-title")
            yield Static(
                "Team-wide defaults (saved to team.json)",
                classes="section-help",
            )

            # Load team config
            team_config = self.config_loader._load_team_config()

            # Check if team enforces agent_backend
            if team_config and team_config.agent_backend:
                yield Static(f"[bold]AI Agent Backend:[/bold] {team_config.agent_backend}")
                yield Static(
                    "[dim]This setting is enforced by your team[/dim]",
                    classes="section-help"
                )
            else:
                yield Static("[dim]No team-specific agent backend enforcement[/dim]")

            yield Static("\n[dim]Team defaults for custom fields:[/dim]", classes="subsection-title")
            yield Static(
                "[dim]Configure team-wide defaults for JIRA fields[/dim]",
                classes="section-help"
            )

            if team_config and team_config.jira_custom_field_defaults:
                for field, value in team_config.jira_custom_field_defaults.items():
                    yield Static(f"[dim]{field}:[/dim] {value}")

            yield Static("\n[yellow]💡 See TEAM.md for team conventions and workflows[/yellow]")

    def _compose_user_tab(self) -> ComposeResult:
        """Compose User configuration tab (Advanced Mode)."""
        with VerticalScroll():
            yield Static("[bold cyan]User Configuration[/bold cyan]", classes="section-title")
            yield Static(
                "Your personal preferences (saved to config.json)",
                classes="section-help",
            )

            yield Static("[bold]Repository Settings[/bold]", classes="subsection-title")

            yield ConfigInput(
                "Last Used Workspace",
                "repos.last_used_workspace",
                value=self.config.repos.last_used_workspace or "",
                help_text="Last workspace used (automatically updated)",
            )

            yield Static("\n[bold]AI Settings[/bold]", classes="subsection-title")

            # Only show if not enforced by enterprise/team
            enforcement_source = self._get_agent_backend_enforcement_source()
            if enforcement_source:
                yield Static(
                    f"[yellow]AI Agent Backend is enforced by {enforcement_source} configuration[/yellow]",
                    classes="section-help"
                )
            else:
                agent_backend_select = Select(
                    [
                        ("Claude (Anthropic)", "claude"),
                        ("GitHub Copilot", "github-copilot"),
                    ],
                    value=self.config.agent_backend or "claude",
                    id="agent_backend",
                )
                yield ConfigSelect("AI Agent Backend", "agent_backend", agent_backend_select)

            yield Static("\n[bold]Personal Field Defaults[/bold]", classes="subsection-title")
            yield Static(
                "[dim]Configure your personal defaults for JIRA fields[/dim]",
                classes="section-help"
            )

            if self.config.jira.custom_field_defaults:
                for field, value in self.config.jira.custom_field_defaults.items():
                    yield ConfigInput(
                        f"{field}",
                        f"jira.custom_field_defaults.{field}",
                        value=str(value),
                        help_text=f"Personal default for {field}",
                    )

            yield Static("\n[yellow]💡 See USER.md for personal customization options[/yellow]")

    def _create_backup(self) -> Path:
        """Create backup of current config file.

        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = self.config_loader.session_home / "backups"
        backup_dir.mkdir(exist_ok=True)

        backup_path = backup_dir / f"config-{timestamp}.json"
        shutil.copy2(self.config_loader.config_file, backup_path)

        return backup_path


def run_config_tui(advanced_mode: bool = False) -> None:
    """Run the configuration TUI application.

    Args:
        advanced_mode: If True, start in Advanced Mode (file-based tabs)
    """
    while True:
        app = ConfigTUI(advanced_mode=advanced_mode)
        result = app.run()

        # Check if we need to restart in different mode
        if result and isinstance(result, dict) and "restart_mode" in result:
            advanced_mode = result["restart_mode"] == "advanced"
            # Loop will restart with new mode
        else:
            # Normal exit
            break


if __name__ == "__main__":
    import sys
    # Check for --advanced flag
    advanced = "--advanced" in sys.argv
    run_config_tui(advanced_mode=advanced)
