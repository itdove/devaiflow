"""Configuration editor page -- mirrors the Textual TUI config editor.

Provides all 8 tabs from the TUI: JIRA Integration, GitHub/GitLab,
Repository & VCS, Workspaces, AI, Model Providers, Session Workflow, Advanced.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from nicegui import ui

from devflow.config.models import (
    ContextFile,
    ModelProviderConfig,
    ModelProviderProfile,
    WorkspaceDefinition,
)
from devflow.config.templates.model_providers import (
    detect_template_from_profile,
    get_template_registry,
)
from devflow.utils.model_provider import (
    ModelProviderValidationResult,
    validate_model_provider_profile,
)
from devflow.web.components.nav import create_header
from devflow.web.utils.data_bridge import DataBridge

# -- Tri-state helpers (matches TUI _bool_to_choice / _choice_to_bool) --------

_TRI_STATE_OPTIONS = {"True": True, "False": False, "Prompt": None}
_BOOL_OPTIONS = {"True": True, "False": False}


def _bool_to_choice(val: Optional[bool]) -> str:
    if val is True:
        return "True"
    if val is False:
        return "False"
    return "Prompt"


def _choice_to_bool(val: str) -> Optional[bool]:
    return _TRI_STATE_OPTIONS.get(val)


def _strict_bool(val: str) -> bool:
    return val == "True"


_PROFILE_MODEL_FIELDS = (
    ("new", "Model for daf new"),
    ("open", "Model for daf open"),
    ("git_new", "Model for daf git new"),
    ("jira_new", "Model for daf jira new"),
    ("investigation", "Model for daf investigation"),
    ("commit_message", "Model for commit messages"),
    ("pr_template", "Model for PR/MR templates"),
)


def _profile_to_dict(profile: Any) -> Dict[str, Any]:
    """Return a provider profile as a plain dictionary."""
    if hasattr(profile, "model_dump"):
        return profile.model_dump()
    return dict(profile or {})


def _profile_summary(profile: Any) -> str:
    """Build the non-secret summary shown for a model provider profile."""
    data = _profile_to_dict(profile)
    provider = data.get("provider") or (
        "vertex" if data.get("use_vertex") else "anthropic"
    )
    agent_backend = data.get("agent_backend") or "claude"
    details = f"{provider} · {agent_backend}"
    if data.get("use_vertex"):
        details += f" · {data.get('vertex_region') or 'default region'}"
    elif data.get("base_url"):
        details += f" · {data['base_url']}"
    if data.get("model_name"):
        details += f" · default={data['model_name']}"
    return details


def _model_provider_enforcement_source(bridge: DataBridge) -> Optional[str]:
    """Return the hierarchy layer that owns the model-provider configuration."""
    for source, getter in (
        ("enterprise", bridge.get_enterprise_config),
        ("organization", bridge.get_organization_config),
        ("team", bridge.get_team_config),
    ):
        try:
            source_config = getter()
        except Exception:  # noqa: BLE001 - hierarchy readers may be unavailable
            source_config = None
        if source_config and (
            source_config.get("model_provider")
            if isinstance(source_config, dict)
            else getattr(source_config, "model_provider", None)
        ):
            return source
    return None


def _validate_profile_safely(
    profile_name: str, profile: Any
) -> ModelProviderValidationResult:
    """Validate a profile without exposing unexpected provider or credential errors."""
    try:
        return validate_model_provider_profile(profile, verify_remote=True)
    except Exception:
        return ModelProviderValidationResult(
            profile_name=profile_name,
            issues=["Profile validation could not be completed safely."],
        )


def _path_validation_error(path: str, *, directory: bool) -> Optional[str]:
    """Return a TUI-compatible local path validation error, if any."""
    try:
        expanded_path = Path(path).expanduser()
        if not expanded_path.exists():
            return f"Path does not exist: {path}"
        if directory and not expanded_path.is_dir():
            return f"Path is not a directory: {path}"
        if not directory and not expanded_path.is_file():
            return f"Path is not a file: {path}"
    except Exception as exc:
        return f"Invalid path: {exc}"
    return None


# -- Reusable form widgets ---------------------------------------------------


def _field_row(label: str, help_text: str = "") -> ui.column:
    """Start a labelled field row and return the container for the widget."""
    col = ui.column().classes("w-full gap-0")
    with col:
        ui.label(label).classes("text-sm font-semibold text-gray-300")
        if help_text:
            ui.label(help_text).classes("text-xs text-gray-500")
    return col


def _tri_select(label: str, value: Optional[bool], help_text: str = "") -> ui.select:
    with _field_row(label, help_text):
        return ui.select(
            options=list(_TRI_STATE_OPTIONS.keys()),
            value=_bool_to_choice(value),
        ).classes("w-full")


def _bool_select(label: str, value: bool, help_text: str = "") -> ui.select:
    with _field_row(label, help_text):
        return ui.select(
            options=list(_BOOL_OPTIONS.keys()),
            value="True" if value else "False",
        ).classes("w-full")


def _text_input(
    label: str, value: str = "", help_text: str = "", placeholder: str = ""
) -> ui.input:
    with _field_row(label, help_text):
        return ui.input(value=value, placeholder=placeholder).classes("w-full")


def _select(
    label: str,
    options: Union[List[str], Dict[str, str]],
    value: str = "",
    help_text: str = "",
) -> ui.select:
    with _field_row(label, help_text):
        return ui.select(options=options, value=value).classes("w-full")


# -- Tab builders  -----------------------------------------------------------


def _extract_component_choices(jira: Any) -> List[str]:
    """Extract component allowed values from field_mappings.

    Checks for both 'components' and 'component/s' keys (server vs cloud).

    Args:
        jira: JiraConfig object.

    Returns:
        List of component name strings, empty if none discovered.
    """
    import json as _json

    if not jira or not jira.field_mappings:
        return []

    # Try both field name variants (server: component/s, cloud: components)
    component_field = None
    for key in ("components", "component/s"):
        if key in jira.field_mappings:
            component_field = jira.field_mappings[key]
            break
    if not component_field or "allowed_values" not in component_field:
        return []

    choices: List[str] = []
    for comp in component_field["allowed_values"]:
        try:
            if isinstance(comp, str):
                try:
                    parsed = _json.loads(comp.replace("'", '"'))
                    if isinstance(parsed, dict) and "name" in parsed:
                        choices.append(parsed["name"])
                    else:
                        choices.append(comp)
                except (_json.JSONDecodeError, ValueError):
                    choices.append(comp)
            elif isinstance(comp, dict) and "name" in comp:
                choices.append(comp["name"])
        except (KeyError, TypeError, ValueError):
            pass
    return choices


def _extract_custom_fields(jira: Any) -> List[Dict[str, Any]]:
    """Extract custom fields from field_mappings for the config editor.

    Only returns fields whose ID starts with 'customfield_'.

    Args:
        jira: JiraConfig object.

    Returns:
        List of dicts with keys: field_key, field_name, allowed_values.
    """
    if not jira or not jira.field_mappings:
        return []

    fields: List[Dict[str, Any]] = []
    for field_key, field_info in jira.field_mappings.items():
        if not isinstance(field_info, dict) or "id" not in field_info:
            continue
        field_id = field_info["id"]
        if not isinstance(field_id, str) or not field_id.startswith("customfield_"):
            continue

        field_name = field_info.get("name", field_key)
        raw_values = field_info.get("allowed_values", [])

        # Normalise allowed_values to simple strings
        allowed: List[str] = []
        for val in raw_values:
            if isinstance(val, dict) and "value" in val:
                allowed.append(val["value"])
            elif isinstance(val, str):
                allowed.append(val)

        fields.append(
            {
                "key": field_key,
                "name": field_name,
                "allowed_values": allowed,
            }
        )

    return sorted(fields, key=lambda f: f["name"])


def _build_jira_tab(config: Any) -> Dict[str, Any]:
    """Build JIRA Integration tab fields. Returns dict of widget refs."""
    widgets: Dict[str, Any] = {}
    jira = config.jira if config.jira else None

    widgets["jira_url"] = _text_input(
        "JIRA URL", jira.url if jira else "", "Base URL of your JIRA instance"
    )
    widgets["jira_project"] = _text_input(
        "Project Key",
        jira.project or "" if jira else "",
        "JIRA project key (e.g. PROJ)",
    )

    # --- Components: dropdown if allowed_values exist, else text input -------
    component_choices = _extract_component_choices(jira)

    # Current value
    components_current = ""
    if (
        jira
        and jira.system_field_defaults
        and "components" in jira.system_field_defaults
    ):
        cval = jira.system_field_defaults["components"]
        if isinstance(cval, list) and cval:
            components_current = cval[0]  # dropdown: first item
        elif isinstance(cval, str):
            components_current = cval

    if component_choices:
        widgets["jira_components"] = _select(
            "Component",
            [""] + component_choices,
            components_current,
            "Select default JIRA component for new issues",
        )
        widgets["_components_is_select"] = True
    else:
        # Fallback to comma-separated text input
        if (
            jira
            and jira.system_field_defaults
            and "components" in jira.system_field_defaults
        ):
            cval = jira.system_field_defaults["components"]
            components_current = ",".join(cval) if isinstance(cval, list) else str(cval)
        widgets["jira_components"] = _text_input(
            "Components", components_current, "Comma-separated default components"
        )
        widgets["_components_is_select"] = False

    # --- Custom Field Defaults (dynamic from field_mappings) -----------------
    ui.separator().classes("my-3")
    ui.label("Custom Field Defaults").classes("text-sm font-bold text-blue-300")
    ui.label("Default values automatically applied when creating issues").classes(
        "text-xs text-gray-500 mb-2"
    )

    custom_fields = _extract_custom_fields(jira)
    current_defaults = (jira.custom_field_defaults or {}) if jira else {}

    if custom_fields:
        for cf in custom_fields:
            current_value = (
                str(current_defaults.get(cf["key"], ""))
                if current_defaults.get(cf["key"])
                else ""
            )
            if cf["allowed_values"]:
                widgets[f"custom_{cf['key']}"] = _select(
                    cf["name"],
                    [""] + cf["allowed_values"],
                    current_value,
                    f"Default value for {cf['name']}",
                )
            else:
                widgets[f"custom_{cf['key']}"] = _text_input(
                    cf["name"], current_value, f"Default value for {cf['name']}"
                )
    else:
        # No custom fields discovered -- show any manually-set defaults
        if current_defaults:
            for key, val in current_defaults.items():
                widgets[f"custom_{key}"] = _text_input(key, str(val) if val else "")
        else:
            ui.label(
                "No custom fields discovered yet. Run 'daf config refresh-jira-fields' to discover fields."
            ).classes("text-gray-500 text-sm italic")

    # --- Comment Visibility --------------------------------------------------
    ui.separator().classes("my-3")
    ui.label("Comment Visibility").classes("text-sm font-bold text-blue-300")
    vis_type = jira.comment_visibility_type if jira else None
    widgets["comment_visibility_type"] = _select(
        "Comment Visibility Type",
        ["", "group", "role"],
        vis_type or "",
        "Choose 'group' for group-based or 'role' for role-based visibility",
    )
    widgets["comment_visibility_value"] = _text_input(
        "Comment Visibility Value",
        jira.comment_visibility_value or "" if jira else "",
        "Group example: 'jira-users' | Role example: 'Administrators'",
    )
    # Show current state
    if vis_type and jira is not None:
        ui.label(
            f"Current: {vis_type} = '{jira.comment_visibility_value or 'not set'}'"
        ).classes("text-xs text-gray-500")

    # --- Issue Tracker Workflow Prompts --------------------------------------
    ui.separator().classes("my-3")
    ui.label("Issue Tracker Workflow Prompts").classes(
        "text-sm font-bold text-blue-300"
    )
    prompts = config.prompts
    widgets["auto_add_issue_summary"] = _tri_select(
        "Auto-add issue summary on complete",
        prompts.auto_add_issue_summary,
        "Automatically add session summary to issue tracker when completing (JIRA, GitHub, GitLab)",
    )
    widgets["auto_update_jira_pr_url"] = _tri_select(
        "Auto-update issue with PR/MR URL",
        prompts.auto_update_jira_pr_url,
        "Automatically update issue tracker with PR/MR URL when created",
    )

    return widgets


def _build_github_tab(config: Any) -> Dict[str, Any]:
    """Build GitHub/GitLab tab fields."""
    widgets: Dict[str, Any] = {}
    gh = config.github

    widgets["github_api_url"] = _text_input(
        "GitHub API URL",
        gh.api_url if gh else "https://api.github.com",
        "API base URL",
    )
    widgets["github_repository"] = _text_input(
        "Default Repository",
        gh.repository or "" if gh else "",
        "owner/repo format",
    )
    labels_val = ",".join(gh.default_labels) if gh and gh.default_labels else ""
    widgets["github_default_labels"] = _text_input(
        "Default Labels", labels_val, "Comma-separated labels"
    )
    widgets["github_auto_close"] = _bool_select(
        "Auto-close issues on complete",
        gh.auto_close_on_complete if gh else False,
    )
    widgets["github_add_status_labels"] = _bool_select(
        "Add status labels",
        gh.add_status_labels if gh else False,
    )
    widgets["github_completion_label"] = _text_input(
        "Completion Label",
        gh.completion_label if gh else "status: in-review",
    )

    # GitLab section
    ui.separator().classes("my-3")
    ui.label("GitLab").classes("text-sm font-bold text-blue-300")
    gl = config.gitlab
    widgets["gitlab_api_url"] = _text_input(
        "GitLab API URL",
        gl.api_url if gl else "https://gitlab.com/api/v4",
    )
    widgets["gitlab_repository"] = _text_input(
        "GitLab Repository",
        gl.repository or "" if gl else "",
        "owner/repo format",
    )
    return widgets


def _build_repo_tab(config: Any) -> Dict[str, Any]:
    """Build Repository & VCS tab fields."""
    widgets: Dict[str, Any] = {}
    detection = config.repos.detection if config.repos else None
    prompts = config.prompts

    widgets["detection_method"] = _select(
        "Detection Method",
        ["keyword_match", "prompt", "fuzzy"],
        detection.method if detection else "keyword_match",
        "How repos are matched to tickets",
    )
    widgets["detection_fallback"] = _select(
        "Detection Fallback",
        ["prompt", "abort"],
        detection.fallback if detection else "prompt",
    )

    ui.separator().classes("my-3")
    ui.label("Branch & Commit Behaviour").classes("text-sm font-bold text-blue-300")

    widgets["auto_checkout_branch"] = _tri_select(
        "Auto-checkout branch", prompts.auto_checkout_branch
    )
    widgets["auto_sync_with_base"] = _select(
        "Auto-sync with base branch",
        ["always", "never", "prompt"],
        prompts.auto_sync_with_base or "prompt",
    )
    widgets["default_branch_strategy"] = _select(
        "Default branch strategy",
        ["", "from_default", "from_current"],
        prompts.default_branch_strategy or "",
    )
    widgets["use_issue_key_as_branch"] = _bool_select(
        "Use issue key as branch name", prompts.use_issue_key_as_branch
    )
    widgets["auto_commit_on_complete"] = _tri_select(
        "Auto-commit on complete", prompts.auto_commit_on_complete
    )
    widgets["auto_accept_ai_commit_message"] = _tri_select(
        "Auto-accept AI commit message", prompts.auto_accept_ai_commit_message
    )

    ui.separator().classes("my-3")
    ui.label("Pull Request / Merge Request").classes("text-sm font-bold text-blue-300")

    widgets["pr_template_url"] = _text_input(
        "PR/MR Template URL", config.pr_template_url or ""
    )
    widgets["auto_create_pr_on_complete"] = _tri_select(
        "Auto-create PR/MR on complete", prompts.auto_create_pr_on_complete
    )
    widgets["auto_create_pr_status"] = _select(
        "PR/MR creation status",
        ["draft", "ready", "prompt"],
        prompts.auto_create_pr_status or "prompt",
    )
    widgets["auto_push_to_remote"] = _tri_select(
        "Auto-push to remote", prompts.auto_push_to_remote
    )
    widgets["auto_select_target_branch"] = _tri_select(
        "Auto-select target branch", prompts.auto_select_target_branch
    )
    return widgets


def _build_workspaces_tab(
    config: Any,
    bridge: DataBridge,
    mark_dirty_fn: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    """Build Workspaces tab with add/edit/remove."""
    widgets: Dict[str, Any] = {}
    workspaces = config.repos.workspaces if config.repos else []
    last_used = config.repos.last_used_workspace if config.repos else None

    ws_container = ui.column().classes("w-full gap-2")
    widgets["_ws_container"] = ws_container
    widgets["_workspaces_list"] = workspaces  # mutable reference

    def _mark_dirty() -> None:
        if mark_dirty_fn:
            mark_dirty_fn()

    def _render_workspaces() -> None:
        ws_container.clear()
        with ws_container:
            if not workspaces:
                ui.label("No workspaces configured.").classes("text-gray-400")
            for i, ws in enumerate(workspaces):
                is_default = ws.name == last_used
                with ui.card().classes("w-full bg-gray-800"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-0"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(ws.name).classes("font-bold")
                                if is_default:
                                    ui.badge("Default").classes(
                                        "bg-yellow-600 text-white"
                                    )
                            ui.label(ws.path).classes("text-sm text-gray-400")
                        with ui.row().classes("gap-1"):
                            if not is_default:
                                idx = i

                                def _set_default(name: str = ws.name) -> None:
                                    config.repos.last_used_workspace = name
                                    nonlocal last_used
                                    last_used = name
                                    _render_workspaces()
                                    _mark_dirty()

                                ui.button("Set Default", on_click=_set_default).props(
                                    "flat dense"
                                )
                            idx = i

                            def _edit(index: int = idx) -> None:
                                _open_workspace_dialog(index)

                            ui.button("Edit", on_click=_edit).props("flat dense")

                            def _remove(index: int = idx) -> None:
                                nonlocal last_used
                                removed = workspaces.pop(index)
                                if removed.name == last_used:
                                    last_used = (
                                        workspaces[0].name if workspaces else None
                                    )
                                    config.repos.last_used_workspace = last_used
                                _render_workspaces()
                                _mark_dirty()

                            ui.button("Remove", on_click=_remove).props(
                                "flat dense color=red"
                            )

    def _open_workspace_dialog(index: Optional[int] = None) -> None:
        existing = workspaces[index] if index is not None else None
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label("Edit Workspace" if existing else "Add Workspace").classes(
                "text-lg font-bold"
            )
            name_input = _text_input(
                "Workspace Name",
                existing.name if existing else "",
                placeholder="e.g., primary, product-a, feat-caching",
            )
            path_input = _text_input(
                "Workspace Path",
                existing.path if existing else "",
                placeholder="e.g., ~/development/project or /path/to/workspace",
            )

            def _save_workspace() -> None:
                nonlocal last_used
                name = (name_input.value or "").strip()
                path = (path_input.value or "").strip()
                if not name or not path:
                    ui.notify("Workspace name and path are required.", type="warning")
                    return
                path_error = _path_validation_error(path, directory=True)
                if path_error:
                    ui.notify(path_error, type="negative")
                    return

                workspace = WorkspaceDefinition(name=name, path=path)
                if index is None:
                    workspaces.append(workspace)
                    if len(workspaces) == 1:
                        last_used = name
                        config.repos.last_used_workspace = name
                    message = f"Workspace '{name}' added."
                else:
                    old_workspace = workspaces[index]
                    if old_workspace.name == last_used and old_workspace.name != name:
                        last_used = name
                        config.repos.last_used_workspace = name
                    workspaces[index] = workspace
                    message = f"Workspace '{name}' updated."
                _render_workspaces()
                _mark_dirty()
                dialog.close()
                ui.notify(message, type="positive")

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Update" if existing else "Add", on_click=_save_workspace
                ).classes("bg-blue-600")
        dialog.open()

    _render_workspaces()

    ui.separator().classes("my-3")
    ui.button("Add Workspace", on_click=lambda: _open_workspace_dialog()).classes(
        "bg-blue-600"
    )

    return widgets


def _build_ai_tab(
    config: Any,
    mark_dirty_fn: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    """Build AI tab fields."""
    widgets: Dict[str, Any] = {}
    from devflow.agent.factory import AGENT_DISPLAY_NAMES, AGENT_REGISTRY

    widgets["agent_backend"] = _select(
        "AI Agent Backend",
        {name: AGENT_DISPLAY_NAMES.get(name, name) for name in AGENT_REGISTRY},
        config.agent_backend or "claude",
        "Which AI agent to use",
    )

    ui.separator().classes("my-3")
    ui.label("Session Summary").classes("text-sm font-bold text-blue-300")
    ss = config.session_summary
    widgets["summary_mode"] = _select(
        "Summary Mode", ["local", "ai", "both"], ss.mode if ss else "local"
    )
    widgets["summary_api_key_env"] = _text_input(
        "API Key Environment Variable",
        ss.api_key_env if ss else "ANTHROPIC_API_KEY",
    )

    ui.separator().classes("my-3")
    ui.label("Session Behaviour").classes("text-sm font-bold text-blue-300")
    prompts = config.prompts
    widgets["auto_launch_agent"] = _tri_select(
        "Auto-launch AI Agent", prompts.auto_launch_agent
    )
    widgets["show_prompt_unit_tests"] = _bool_select(
        "Show unit testing instructions", prompts.show_prompt_unit_tests
    )
    widgets["auto_load_related_conversations"] = _bool_select(
        "Auto-load related conversations", prompts.auto_load_related_conversations
    )

    # Context files
    ui.separator().classes("my-3")
    ui.label("Context Files").classes("text-sm font-bold text-blue-300")
    ctx_files = config.context_files.files if config.context_files else []
    ctx_container = ui.column().classes("w-full gap-1")
    widgets["_ctx_container"] = ctx_container
    widgets["_ctx_files"] = ctx_files

    def _mark_dirty() -> None:
        if mark_dirty_fn:
            mark_dirty_fn()

    def _render_ctx_files() -> None:
        ctx_container.clear()
        current_visible = [f for f in ctx_files if not getattr(f, "hidden", False)]
        with ctx_container:
            if not current_visible:
                ui.label("No context files configured.").classes("text-gray-400")
            for i, cf in enumerate(ctx_files):
                if getattr(cf, "hidden", False):
                    continue
                with ui.row().classes(
                    "w-full items-center gap-2 bg-gray-800 p-2 rounded"
                ):
                    ui.label(cf.path).classes("font-semibold flex-grow")
                    ui.label(cf.description).classes("text-sm text-gray-400")
                    idx = i

                    def _remove_ctx(index: int = idx) -> None:
                        ctx_files.pop(index)
                        _render_ctx_files()
                        _mark_dirty()

                    def _edit_ctx(index: int = idx) -> None:
                        _open_context_file_dialog(index)

                    ui.button("Edit", on_click=_edit_ctx).props("flat dense")
                    ui.button("Remove", on_click=_remove_ctx).props(
                        "flat dense color=red"
                    )

    def _open_context_file_dialog(index: Optional[int] = None) -> None:
        existing = ctx_files[index] if index is not None else None
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label("Edit Context File" if existing else "Add Context File").classes(
                "text-lg font-bold"
            )
            path_input = _text_input(
                "File Path or URL",
                existing.path if existing else "",
                placeholder="e.g., ARCHITECTURE.md or https://example.test/DESIGN.md",
            )
            description_input = _text_input(
                "Description",
                existing.description if existing else "",
                placeholder="Brief description of what this file contains",
            )

            def _save_context_file() -> None:
                path = (path_input.value or "").strip()
                description = (description_input.value or "").strip()
                if not path or not description:
                    ui.notify("Path and description are required.", type="warning")
                    return
                if not path.startswith(("http://", "https://")):
                    path_error = _path_validation_error(path, directory=False)
                    if path_error and "does not exist" not in path_error:
                        ui.notify(path_error, type="negative")
                        return
                    if path_error:
                        ui.notify(path_error, type="warning")

                context_file = ContextFile(path=path, description=description)
                if index is None:
                    ctx_files.append(context_file)
                    message = "Context file added."
                else:
                    ctx_files[index] = context_file
                    message = "Context file updated."
                _render_ctx_files()
                _mark_dirty()
                dialog.close()
                ui.notify(message, type="positive")

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Update" if existing else "Add", on_click=_save_context_file
                ).classes("bg-blue-600")
        dialog.open()

    _render_ctx_files()

    ui.button("Add Context File", on_click=lambda: _open_context_file_dialog()).classes(
        "bg-blue-600"
    )

    return widgets


def _build_model_providers_tab(
    config: Any,
    bridge: Optional[DataBridge] = None,
    mark_dirty_fn: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    """Build Model Providers tab with the TUI's profile actions."""
    widgets: Dict[str, Any] = {}
    mp = config.model_provider
    profiles = mp.profiles if mp else {}
    default_profile = mp.default_profile if mp else "anthropic"
    enforcement_source = _model_provider_enforcement_source(bridge) if bridge else None

    widgets["_profiles"] = profiles
    widgets["_default_profile"] = default_profile

    profiles_container = ui.column().classes("w-full gap-2")
    widgets["_profiles_container"] = profiles_container

    def _mark_dirty() -> None:
        if mark_dirty_fn:
            mark_dirty_fn()

    def _ensure_model_provider() -> ModelProviderConfig:
        nonlocal mp, profiles
        if mp is None:
            mp = ModelProviderConfig(profiles=profiles)
            config.model_provider = mp
            profiles = mp.profiles
        return mp

    def _show_validation_result(
        profile_name: str, result: ModelProviderValidationResult
    ) -> None:
        with (
            ui.dialog() as dialog,
            ui.card().classes("w-full max-w-2xl max-h-[85vh] overflow-auto"),
        ):
            ui.label(f"Validate Profile: {profile_name}").classes("text-lg font-bold")
            if result.issues:
                ui.label("Validation failed").classes("text-red-400 font-bold")
            elif result.warnings:
                ui.label("Validation completed with warnings").classes(
                    "text-yellow-400 font-bold"
                )
            else:
                ui.label("Profile configuration is valid").classes(
                    "text-green-400 font-bold"
                )

            if result.checks:
                ui.label("Checks").classes("font-bold mt-3")
                for check in result.checks:
                    ui.label(f"✓ {check}").classes("text-green-300")
            if result.issues:
                ui.label("Errors").classes("font-bold text-red-400 mt-3")
                for issue in result.issues:
                    ui.label(f"• {issue}").classes("text-red-300")
            if result.warnings:
                ui.label("Warnings").classes("font-bold text-yellow-400 mt-3")
                for warning in result.warnings:
                    ui.label(f"• {warning}").classes("text-yellow-300")
            ui.label(
                "No profile values were changed. Credential values are never displayed."
            ).classes("text-xs text-gray-500 mt-4")
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    def _validate_profile(profile_name: str, profile: Any) -> None:
        ui.notify(f"Validating profile '{profile_name}'...", type="info")
        result = _validate_profile_safely(profile_name, profile)
        _show_validation_result(profile_name, result)

    def _show_profile_dialog(
        template_id: Optional[str] = None,
        existing_name: Optional[str] = None,
        existing_profile: Any = None,
    ) -> None:
        profile_data = _profile_to_dict(existing_profile)
        selected_template_id = (
            detect_template_from_profile(profile_data)
            if existing_name
            else (template_id or "anthropic")
        )
        template = get_template_registry().get(selected_template_id)
        if template is None:
            ui.notify(
                f"Unknown model provider template: {selected_template_id}",
                type="negative",
            )
            return

        is_edit_mode = existing_name is not None
        with (
            ui.dialog() as dialog,
            ui.card().classes("w-full max-w-5xl max-h-[90vh] overflow-auto"),
        ):
            title = (
                f"Edit Profile: {existing_name}"
                if is_edit_mode
                else f"Add {template.get_name()} Profile"
            )
            ui.label(title).classes("text-lg font-bold")
            ui.label(f"Provider: {template.get_name()}").classes(
                "text-sm text-gray-400"
            )
            ui.label(template.get_description()).classes("text-xs text-gray-500 mb-2")

            template_widgets: Dict[str, Any] = {}
            for field in template.get_fields():
                current_value = (
                    existing_name
                    if field.field_id == "profile_name" and is_edit_mode
                    else profile_data.get(field.field_id, field.default_value)
                )
                label = f"{field.label}{' *' if field.required else ''}"
                if field.field_type == "input":
                    template_widgets[field.field_id] = _text_input(
                        label,
                        str(current_value) if current_value is not None else "",
                        field.help_text,
                        field.placeholder,
                    )
                    if is_edit_mode and field.field_id == "profile_name":
                        template_widgets[field.field_id].props("disable")
                elif field.field_type == "select":
                    with _field_row(label, field.help_text):
                        template_widgets[field.field_id] = ui.select(
                            options=field.options or [],
                            value=(
                                current_value
                                if current_value is not None
                                else field.default_value
                            ),
                        ).classes("w-full")
                elif field.field_type == "checkbox":
                    with _field_row(label, field.help_text):
                        template_widgets[field.field_id] = ui.checkbox(
                            value=bool(current_value)
                        )

            from devflow.agent.factory import AGENT_DISPLAY_NAMES, AGENT_REGISTRY

            default_agent_backend = profile_data.get("agent_backend")
            if not default_agent_backend:
                default_agent_backend = getattr(template, "default_agent_backend", None)
            if not default_agent_backend:
                default_agent_backend = {"codex": "codex", "ollama": "ollama"}.get(
                    selected_template_id, "claude"
                )
            agent_options = {
                name: AGENT_DISPLAY_NAMES.get(name, name) for name in AGENT_REGISTRY
            }
            if default_agent_backend not in agent_options:
                agent_options[default_agent_backend] = (
                    f"{default_agent_backend} (custom/legacy)"
                )
            with _field_row(
                "Agent / IDE adapter *", "The adapter used to launch this profile"
            ):
                agent_widget = ui.select(
                    options=agent_options,
                    value=default_agent_backend,
                ).classes("w-full")

            arguments_widget = ui.textarea(
                label="Adapter arguments (one argv token per line)",
                value="\n".join(
                    str(argument) for argument in (profile_data.get("arguments") or [])
                ),
            ).classes("w-full")

            ui.label("Command models").classes("font-bold mt-3")
            ui.label(
                "Utility models are used for commit messages and PR/MR templates and ignore --model."
            ).classes("text-xs text-gray-500")
            model_widgets: Dict[str, Any] = {}
            reasoning_widgets: Dict[str, Any] = {}
            existing_models = profile_data.get("models") or {}
            existing_reasoning = profile_data.get("reasoning_efforts") or {}
            for command, label in _PROFILE_MODEL_FIELDS:
                current_model = existing_models.get(command, "")
                if command == "commit_message":
                    current_model = current_model or profile_data.get(
                        "commit_message_model", ""
                    )
                elif command == "pr_template":
                    current_model = current_model or profile_data.get(
                        "pr_template_model", ""
                    )
                model_widgets[command] = _text_input(
                    label,
                    str(current_model) if current_model else "",
                    placeholder="Leave empty to use the profile default model",
                )
                reasoning_widgets[command] = _text_input(
                    f"{label} reasoning strength",
                    (
                        str(existing_reasoning.get(command, ""))
                        if existing_reasoning.get(command)
                        else ""
                    ),
                    placeholder="Optional: low, medium, high, max",
                )

            def _save_profile() -> None:
                form_data: Dict[str, Any] = {}
                for field in template.get_fields():
                    value = template_widgets[field.field_id].value
                    form_data[field.field_id] = (
                        value.strip() if isinstance(value, str) else value
                    )
                validation_errors = template.validate(form_data)
                if validation_errors:
                    ui.notify(
                        "Validation errors: " + "; ".join(validation_errors),
                        type="negative",
                    )
                    return

                agent_backend = agent_widget.value
                if not isinstance(agent_backend, str) or not agent_backend:
                    ui.notify("Agent / IDE adapter is required.", type="negative")
                    return

                command_models = {
                    command: (widget.value or "").strip()
                    for command, widget in model_widgets.items()
                    if isinstance(widget.value, str) and widget.value.strip()
                }
                reasoning_efforts = {
                    command: (widget.value or "").strip()
                    for command, widget in reasoning_widgets.items()
                    if isinstance(widget.value, str) and widget.value.strip()
                }
                try:
                    generated = template.generate_config(form_data)
                    generated["agent_backend"] = agent_backend
                    generated["arguments"] = (arguments_widget.value or "").splitlines()
                    generated["models"] = command_models
                    generated["reasoning_efforts"] = reasoning_efforts
                    generated.setdefault("provider", selected_template_id)
                    profile_name = str(form_data.get("profile_name") or "").strip()
                    profile = ModelProviderProfile(**generated)
                except Exception:
                    ui.notify(
                        "Error generating profile configuration.", type="negative"
                    )
                    return

                target = _ensure_model_provider()
                target.profiles[profile_name] = profile
                if not target.default_profile or len(target.profiles) == 1:
                    target.default_profile = profile_name
                nonlocal default_profile
                default_profile = target.default_profile
                _render_profiles()
                _mark_dirty()
                dialog.close()
                ui.notify(
                    f"Profile '{profile_name}' {'updated' if is_edit_mode else 'added'}.",
                    type="positive",
                )

            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Update" if is_edit_mode else "Add", on_click=_save_profile
                ).classes("bg-blue-600")
        dialog.open()

    def _show_template_selection() -> None:
        with (
            ui.dialog() as dialog,
            ui.card().classes("w-full max-w-3xl max-h-[85vh] overflow-auto"),
        ):
            ui.label("Select Provider Type").classes("text-lg font-bold")
            ui.label("Choose the provider template for the new profile.").classes(
                "text-sm text-gray-400 mb-2"
            )
            for template_id, template in get_template_registry().items():
                with ui.card().classes("w-full bg-gray-800"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-0"):
                            ui.label(template.get_name()).classes("font-semibold")
                            ui.label(template.get_description()).classes(
                                "text-xs text-gray-400"
                            )

                        def _select_template(selected_id: str = template_id) -> None:
                            dialog.close()
                            _show_profile_dialog(template_id=selected_id)

                        ui.button("Select", on_click=_select_template).props(
                            "flat dense"
                        )
            ui.button("Cancel", on_click=dialog.close).props("flat")
        dialog.open()

    def _render_profiles() -> None:
        profiles_container.clear()
        with profiles_container:
            if enforcement_source:
                ui.label(
                    f"Model provider configuration is enforced by {enforcement_source}."
                ).classes("text-yellow-400")
            if not profiles:
                ui.label("No model provider profiles configured.").classes(
                    "text-gray-400"
                )
            for name, profile in profiles.items():
                is_default = name == default_profile
                with ui.card().classes("w-full bg-gray-800"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-0"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(name).classes("font-bold")
                                if is_default:
                                    ui.badge("Default").classes(
                                        "bg-yellow-600 text-white"
                                    )
                            ui.label(_profile_summary(profile)).classes(
                                "text-sm text-gray-400"
                            )
                        with ui.row().classes("gap-1"):
                            if not is_default:

                                def _set_mp_default(profile_name: str = name) -> None:
                                    target = _ensure_model_provider()
                                    if enforcement_source:
                                        ui.notify(
                                            f"Cannot change default profile: model provider is enforced by {enforcement_source}.",
                                            type="negative",
                                        )
                                        return
                                    target.default_profile = profile_name
                                    nonlocal default_profile
                                    default_profile = profile_name
                                    _render_profiles()
                                    _mark_dirty()

                                default_button = ui.button(
                                    "Set Default", on_click=_set_mp_default
                                ).props("flat dense")
                                if enforcement_source:
                                    default_button.disable()

                            ui.button(
                                "Validate",
                                on_click=lambda n=name, p=profile: _validate_profile(
                                    n, p
                                ),
                            ).props("flat dense")

                            def _edit_profile(
                                profile_name: str = name, profile_data: Any = profile
                            ) -> None:
                                if enforcement_source:
                                    ui.notify(
                                        f"Cannot edit profile: model provider is enforced by {enforcement_source}.",
                                        type="negative",
                                    )
                                    return
                                _show_profile_dialog(
                                    existing_name=profile_name,
                                    existing_profile=profile_data,
                                )

                            edit_button = ui.button(
                                "Edit", on_click=_edit_profile
                            ).props("flat dense")
                            if enforcement_source:
                                edit_button.disable()

                            if not is_default and name != "anthropic":

                                def _remove_profile(profile_name: str = name) -> None:
                                    if enforcement_source:
                                        ui.notify(
                                            f"Cannot remove profile: model provider is enforced by {enforcement_source}.",
                                            type="negative",
                                        )
                                        return
                                    profiles.pop(profile_name, None)
                                    _render_profiles()
                                    _mark_dirty()

                                remove_button = ui.button(
                                    "Delete", on_click=_remove_profile
                                ).props("flat dense color=red")
                                if enforcement_source:
                                    remove_button.disable()

    _render_profiles()
    ui.separator().classes("my-3")
    add_button = ui.button("Add Profile", on_click=_show_template_selection).classes(
        "bg-blue-600"
    )
    if enforcement_source:
        add_button.disable()
    return widgets


def _build_workflow_tab(config: Any) -> Dict[str, Any]:
    """Build Session Workflow tab fields."""
    widgets: Dict[str, Any] = {}
    prompts = config.prompts

    widgets["auto_complete_on_exit"] = _tri_select(
        "Auto-complete session on exit", prompts.auto_complete_on_exit
    )
    widgets["time_tracking"] = _bool_select(
        "Enable Time Tracking",
        config.jira.time_tracking if config.jira else True,
    )
    return widgets


def _build_advanced_tab(config: Any) -> Dict[str, Any]:
    """Build Advanced tab fields."""
    widgets: Dict[str, Any] = {}

    widgets["update_checker_timeout"] = _text_input(
        "Update Checker Timeout (seconds)",
        str(config.update_checker_timeout),
        "How long to wait for update check (1-60 seconds)",
    )

    widgets["issue_tracker_backend"] = _select(
        "Issue Tracker Backend",
        ["jira", "github", "gitlab"],
        config.issue_tracker_backend or "jira",
    )

    widgets["hierarchical_config_source"] = _text_input(
        "Hierarchical Config Source",
        config.repos.hierarchical_config_source or "" if config.repos else "",
        "URL or path to shared config repo",
    )

    return widgets


# -- Collect values back into Config ------------------------------------------


def _collect_values(config: Any, all_widgets: Dict[str, Dict[str, Any]]) -> None:
    """Update config object from widget values.

    Args:
        config: Config object to update in-place.
        all_widgets: Dict mapping tab names to widget dicts.
    """
    # JIRA tab
    jira_w = all_widgets.get("jira", {})
    if config.jira:
        if "jira_url" in jira_w:
            config.jira.url = jira_w["jira_url"].value.strip()
        if "jira_project" in jira_w:
            config.jira.project = jira_w["jira_project"].value.strip() or None
        if "jira_components" in jira_w:
            is_select = jira_w.get("_components_is_select", False)
            val = jira_w["jira_components"].value
            if is_select:
                # Select returns a single value; store as list
                if val:
                    if config.jira.system_field_defaults is None:
                        config.jira.system_field_defaults = {}
                    config.jira.system_field_defaults["components"] = [val]
                else:
                    # Cleared selection
                    if (
                        config.jira.system_field_defaults
                        and "components" in config.jira.system_field_defaults
                    ):
                        del config.jira.system_field_defaults["components"]
            else:
                # Text input: comma-separated
                val = val.strip() if isinstance(val, str) else ""
                if val:
                    if config.jira.system_field_defaults is None:
                        config.jira.system_field_defaults = {}
                    config.jira.system_field_defaults["components"] = [
                        c.strip() for c in val.split(",") if c.strip()
                    ]
        if "comment_visibility_type" in jira_w:
            config.jira.comment_visibility_type = (
                jira_w["comment_visibility_type"].value or None
            )
        if "comment_visibility_value" in jira_w:
            config.jira.comment_visibility_value = (
                jira_w["comment_visibility_value"].value.strip() or None
            )
        # Custom field defaults -- collect from all custom_ widgets
        if config.jira.custom_field_defaults is None:
            config.jira.custom_field_defaults = {}
        for wkey, widget in jira_w.items():
            if wkey.startswith("custom_") and hasattr(widget, "value"):
                field_key = wkey[len("custom_") :]
                raw = widget.value
                val_str = raw.strip() if isinstance(raw, str) else (raw or "")
                if val_str:
                    config.jira.custom_field_defaults[field_key] = val_str
                else:
                    # Remove empty defaults
                    config.jira.custom_field_defaults.pop(field_key, None)

    # Prompts from JIRA tab
    prompts = config.prompts
    if "auto_add_issue_summary" in jira_w:
        prompts.auto_add_issue_summary = _choice_to_bool(
            jira_w["auto_add_issue_summary"].value
        )
    if "auto_update_jira_pr_url" in jira_w:
        prompts.auto_update_jira_pr_url = _choice_to_bool(
            jira_w["auto_update_jira_pr_url"].value
        )

    # GitHub tab
    gh_w = all_widgets.get("github", {})
    if config.github is None:
        from devflow.config.models import GitHubConfig

        config.github = GitHubConfig()
    gh = config.github
    if "github_api_url" in gh_w:
        gh.api_url = gh_w["github_api_url"].value.strip()
    if "github_repository" in gh_w:
        gh.repository = gh_w["github_repository"].value.strip() or None
    if "github_default_labels" in gh_w:
        val = gh_w["github_default_labels"].value.strip()
        gh.default_labels = (
            [l.strip() for l in val.split(",") if l.strip()] if val else []
        )
    if "github_auto_close" in gh_w:
        gh.auto_close_on_complete = _strict_bool(gh_w["github_auto_close"].value)
    if "github_add_status_labels" in gh_w:
        gh.add_status_labels = _strict_bool(gh_w["github_add_status_labels"].value)
    if "github_completion_label" in gh_w:
        gh.completion_label = gh_w["github_completion_label"].value.strip()

    # Repo tab
    repo_w = all_widgets.get("repo", {})
    if config.repos and config.repos.detection:
        if "detection_method" in repo_w:
            config.repos.detection.method = repo_w["detection_method"].value
        if "detection_fallback" in repo_w:
            config.repos.detection.fallback = repo_w["detection_fallback"].value
    if "auto_checkout_branch" in repo_w:
        prompts.auto_checkout_branch = _choice_to_bool(
            repo_w["auto_checkout_branch"].value
        )
    if "auto_sync_with_base" in repo_w:
        val = repo_w["auto_sync_with_base"].value
        prompts.auto_sync_with_base = val if val != "prompt" else None
    if "default_branch_strategy" in repo_w:
        prompts.default_branch_strategy = (
            repo_w["default_branch_strategy"].value or None
        )
    if "use_issue_key_as_branch" in repo_w:
        prompts.use_issue_key_as_branch = _strict_bool(
            repo_w["use_issue_key_as_branch"].value
        )
    if "auto_commit_on_complete" in repo_w:
        prompts.auto_commit_on_complete = _choice_to_bool(
            repo_w["auto_commit_on_complete"].value
        )
    if "auto_accept_ai_commit_message" in repo_w:
        prompts.auto_accept_ai_commit_message = _choice_to_bool(
            repo_w["auto_accept_ai_commit_message"].value
        )
    if "pr_template_url" in repo_w:
        config.pr_template_url = repo_w["pr_template_url"].value.strip() or None
    if "auto_create_pr_on_complete" in repo_w:
        prompts.auto_create_pr_on_complete = _choice_to_bool(
            repo_w["auto_create_pr_on_complete"].value
        )
    if "auto_create_pr_status" in repo_w:
        prompts.auto_create_pr_status = repo_w["auto_create_pr_status"].value
    if "auto_push_to_remote" in repo_w:
        prompts.auto_push_to_remote = _choice_to_bool(
            repo_w["auto_push_to_remote"].value
        )
    if "auto_select_target_branch" in repo_w:
        prompts.auto_select_target_branch = _choice_to_bool(
            repo_w["auto_select_target_branch"].value
        )

    # AI tab
    ai_w = all_widgets.get("ai", {})
    if "agent_backend" in ai_w:
        config.agent_backend = ai_w["agent_backend"].value
    if "summary_mode" in ai_w and config.session_summary:
        config.session_summary.mode = ai_w["summary_mode"].value
    if "summary_api_key_env" in ai_w and config.session_summary:
        config.session_summary.api_key_env = ai_w["summary_api_key_env"].value.strip()
    if "auto_launch_agent" in ai_w:
        prompts.auto_launch_agent = _choice_to_bool(ai_w["auto_launch_agent"].value)
    if "show_prompt_unit_tests" in ai_w:
        prompts.show_prompt_unit_tests = _strict_bool(
            ai_w["show_prompt_unit_tests"].value
        )
    if "auto_load_related_conversations" in ai_w:
        prompts.auto_load_related_conversations = _strict_bool(
            ai_w["auto_load_related_conversations"].value
        )

    # Workflow tab
    wf_w = all_widgets.get("workflow", {})
    if "auto_complete_on_exit" in wf_w:
        prompts.auto_complete_on_exit = _choice_to_bool(
            wf_w["auto_complete_on_exit"].value
        )
    if "time_tracking" in wf_w and config.jira:
        config.jira.time_tracking = _strict_bool(wf_w["time_tracking"].value)

    # Advanced tab
    adv_w = all_widgets.get("advanced", {})
    if "update_checker_timeout" in adv_w:
        try:
            config.update_checker_timeout = int(adv_w["update_checker_timeout"].value)
        except (ValueError, TypeError):
            pass
    if "issue_tracker_backend" in adv_w:
        config.issue_tracker_backend = adv_w["issue_tracker_backend"].value
    if "hierarchical_config_source" in adv_w and config.repos:
        config.repos.hierarchical_config_source = (
            adv_w["hierarchical_config_source"].value.strip() or None
        )


# -- Advanced Mode tab builders -----------------------------------------------


def _build_enterprise_tab(bridge: DataBridge) -> Dict[str, Any]:
    """Build Enterprise tab (read-only)."""
    ec = bridge.get_enterprise_config()

    if not ec:
        ui.label("No enterprise.json file found.").classes("text-gray-400")
        ui.label(
            "Enterprise configuration is optional and managed by administrators."
        ).classes("text-xs text-gray-500")
        return {}

    if ec.get("agent_backend"):
        with _field_row(
            "AI Agent Backend (enforced)",
            "This setting is enforced by your organization",
        ):
            ui.label(ec["agent_backend"]).classes("text-white font-semibold")

    if ec.get("backend_overrides"):
        ui.label("Backend Overrides: configured").classes("text-sm text-gray-400 mt-2")

    if ec.get("github_issue_types"):
        types_list = ec["github_issue_types"]
        if isinstance(types_list, list):
            ui.label(f"GitHub Issue Types: {', '.join(types_list)}").classes(
                "text-sm text-gray-400 mt-2"
            )

    if ec.get("model_provider"):
        ui.label("Model Provider: enforced by enterprise").classes(
            "text-sm text-gray-400 mt-2"
        )

    ui.label(
        "Enterprise settings are read-only and managed by administrators."
    ).classes("text-sm text-yellow-500 mt-4")
    return {}


def _build_organization_tab(bridge: DataBridge) -> Dict[str, Any]:
    """Build Organization tab (partially editable)."""
    widgets: Dict[str, Any] = {}
    oc = bridge.get_organization_config()

    widgets["org_jira_project"] = _text_input(
        "JIRA Project Key",
        oc.get("jira_project", "") if oc else "",
        "Default JIRA project for this organization",
    )

    github_types = ""
    if oc and oc.get("github_issue_types"):
        types_list = oc["github_issue_types"]
        github_types = (
            ",".join(types_list) if isinstance(types_list, list) else str(types_list)
        )
    widgets["org_github_issue_types"] = _text_input(
        "GitHub Issue Types",
        github_types,
        "Comma-separated valid issue types (e.g. bug,enhancement,task,spike,epic)",
    )

    # Read-only sections
    ui.separator().classes("my-3")
    ui.label("Sync Filters").classes("text-sm font-bold text-blue-300")
    if oc and oc.get("sync_filters") and "sync" in oc["sync_filters"]:
        sf = oc["sync_filters"]["sync"]
        if isinstance(sf, dict):
            if sf.get("status"):
                ui.label(f"Status: {', '.join(sf['status'])}").classes(
                    "text-sm text-gray-400"
                )
            if sf.get("required_fields"):
                ui.label(
                    f"Required fields: {', '.join(sf['required_fields'])}"
                ).classes("text-sm text-gray-400")
            if sf.get("assignee"):
                ui.label(f"Assignee: {sf['assignee']}").classes("text-sm text-gray-400")
    else:
        ui.label("No sync filters configured.").classes("text-sm text-gray-500")

    ui.separator().classes("my-3")
    ui.label("Workflow Configuration").classes("text-sm font-bold text-blue-300")
    if oc and oc.get("transitions"):
        t = oc["transitions"]
        names = list(t.keys()) if isinstance(t, dict) else []
        ui.label(
            f"Configured transitions: {', '.join(names) if names else 'none'}"
        ).classes("text-sm text-gray-400")
    else:
        ui.label("No custom transitions configured (using defaults).").classes(
            "text-sm text-gray-500"
        )

    ui.label(
        "To edit transitions or sync filters, edit organization.json directly."
    ).classes("text-xs text-gray-500 mt-2")

    return widgets


def _build_team_tab_advanced(bridge: DataBridge) -> Dict[str, Any]:
    """Build Team tab (read-only)."""
    tc = bridge.get_team_config()

    if tc and tc.get("agent_backend"):
        with _field_row(
            "AI Agent Backend (enforced)", "This setting is enforced by your team"
        ):
            ui.label(tc["agent_backend"]).classes("text-white font-semibold")
    else:
        ui.label("No team-specific agent backend enforcement.").classes(
            "text-sm text-gray-500"
        )

    ui.separator().classes("my-3")
    ui.label("Team Custom Field Defaults").classes("text-sm font-bold text-blue-300")
    defaults = tc.get("jira_custom_field_defaults") if tc else None
    if defaults and isinstance(defaults, dict):
        for field, value in defaults.items():
            ui.label(f"{field}: {value}").classes("text-sm text-gray-400")
    else:
        ui.label("No team custom field defaults configured.").classes(
            "text-sm text-gray-500"
        )

    sys_defaults = tc.get("jira_system_field_defaults") if tc else None
    if sys_defaults and isinstance(sys_defaults, dict):
        ui.separator().classes("my-2")
        ui.label("Team System Field Defaults").classes(
            "text-sm font-bold text-blue-300"
        )
        for field, value in sys_defaults.items():
            display = ", ".join(value) if isinstance(value, list) else str(value)
            ui.label(f"{field}: {display}").classes("text-sm text-gray-400")

    ui.label("Team settings are read-only. Edit team.json directly.").classes(
        "text-xs text-gray-500 mt-4"
    )
    return {}


def _build_user_tab(config: Any) -> Dict[str, Any]:
    """Build User tab (editable personal settings)."""
    widgets: Dict[str, Any] = {}

    ui.label("Repository Settings").classes("text-sm font-bold text-blue-300")
    widgets["user_last_used_workspace"] = _text_input(
        "Last Used Workspace",
        config.repos.last_used_workspace or "" if config.repos else "",
        "Last workspace used (automatically updated)",
    )
    widgets["user_hierarchical_config_source"] = _text_input(
        "Hierarchical Config Source",
        config.repos.hierarchical_config_source or "" if config.repos else "",
        "URL or path to shared config repo",
    )

    ui.separator().classes("my-3")
    ui.label("Personal Field Defaults").classes("text-sm font-bold text-blue-300")
    if config.jira and config.jira.custom_field_defaults:
        for field, value in config.jira.custom_field_defaults.items():
            widgets[f"user_custom_{field}"] = _text_input(
                field,
                str(value) if value else "",
                f"Personal default for {field}",
            )
    else:
        ui.label("No personal field defaults configured.").classes(
            "text-sm text-gray-500"
        )

    return widgets


# -- Main page ----------------------------------------------------------------


def _attach_dirty_tracking(
    all_widgets: Dict[str, Dict[str, Any]],
    state: Dict[str, Any],
    mark_dirty_fn,
    undo_buttons: List[Any],
) -> None:
    """Attach change listeners to all form widgets for dirty-state and undo tracking.

    Each widget's value is snapshotted on attach. On change, the old value is
    pushed onto ``state["undo_stack"]`` so it can be restored.

    Args:
        all_widgets: Dict mapping tab names to widget dicts.
        state: Mutable dict with keys ``undo_stack`` (list) and ``suppressing`` (bool).
        mark_dirty_fn: Callback invoked when any widget value changes.
        undo_buttons: List of undo button refs to enable when history is non-empty.
    """
    for tab_widgets in all_widgets.values():
        for key, widget in tab_widgets.items():
            if key.startswith("_"):
                continue
            if not (hasattr(widget, "on") and hasattr(widget, "value")):
                continue

            val_holder = [widget.value]

            def _make_handler(w, vh):
                def _handler(*_args):
                    if state.get("suppressing"):
                        vh[0] = w.value
                        return
                    old_val = vh[0]
                    new_val = w.value
                    if old_val != new_val:
                        state["undo_stack"].append((w, old_val, vh))
                        vh[0] = new_val
                        mark_dirty_fn()
                        for btn in undo_buttons:
                            btn.enable()

                return _handler

            try:
                widget.on("update:model-value", _make_handler(widget, val_holder))
            except Exception:
                pass


def create_config_editor_page(bridge: DataBridge, advanced: bool = False) -> None:
    """Create the configuration editor page with Simple or Advanced mode.

    Simple Mode: 8 topic-based tabs (JIRA, GitHub, Repo, Workspaces, AI, Providers, Workflow, Advanced).
    Advanced Mode: 4 file-based tabs (Enterprise, Organization, Team, User).

    Args:
        bridge: DataBridge instance for data access.
        advanced: If True, start in Advanced Mode.
    """
    create_header()

    config = bridge.load_config()
    if config is None:
        with ui.column().classes("w-full max-w-5xl mx-auto p-4"):
            ui.label("No configuration found.").classes("text-red-400 text-xl")
            ui.label("Run 'daf init' to create a configuration.").classes(
                "text-gray-400"
            )
        return

    all_widgets: Dict[str, Dict[str, Any]] = {}

    # -- Dirty state and undo tracking -----------------------------------------
    _state: Dict[str, Any] = {"dirty": False, "undo_stack": [], "suppressing": False}
    _save_buttons: List[Any] = []
    _undo_buttons: List[Any] = []

    def _mark_dirty(*_args) -> None:
        if not _state["dirty"]:
            _state["dirty"] = True
            for btn in _save_buttons:
                btn.classes(remove="bg-gray-600", add="bg-orange-600")

    def _mark_clean() -> None:
        _state["dirty"] = False
        for btn in _save_buttons:
            btn.classes(remove="bg-orange-600", add="bg-gray-600")

    def _do_undo() -> None:
        if not _state["undo_stack"]:
            return
        widget, old_val, vh = _state["undo_stack"].pop()
        _state["suppressing"] = True
        widget.value = old_val
        vh[0] = old_val
        _state["suppressing"] = False
        if not _state["undo_stack"]:
            for btn in _undo_buttons:
                btn.disable()
            _mark_clean()

    # -- Shared save/preview callbacks -----------------------------------------

    async def _do_preview() -> None:
        _collect_values(config, all_widgets)
        json_str = bridge.get_config_as_json(config)
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-3xl"):
            ui.label("Configuration Preview").classes("text-lg font-bold")
            ui.code(json_str, language="json").classes("w-full max-h-96 overflow-auto")
            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Close", on_click=dialog.close).props("flat")

                def _confirm_save() -> None:
                    ok = bridge.save_config(config)
                    dialog.close()
                    if ok:
                        _state["undo_stack"].clear()
                        for btn in _undo_buttons:
                            btn.disable()
                        _mark_clean()
                        ui.notify("Configuration saved.", type="positive")
                    else:
                        ui.notify("Failed to save configuration.", type="negative")

                ui.button("Confirm & Save", on_click=_confirm_save).classes(
                    "bg-green-600"
                )
        dialog.open()

    async def _do_save() -> None:
        _collect_values(config, all_widgets)
        ok = bridge.save_config(config)
        if ok:
            _state["undo_stack"].clear()
            for btn in _undo_buttons:
                btn.disable()
            _mark_clean()
            ui.notify("Configuration saved.", type="positive")
        else:
            ui.notify("Failed to save configuration.", type="negative")

    def _do_cancel() -> None:
        target = "/config/advanced" if advanced else "/config"
        ui.navigate.to(target)

    def _create_action_buttons() -> None:
        """Create Cancel + Undo + Preview + Save buttons."""
        ui.button("Cancel", on_click=_do_cancel).props("flat color=red")
        undo_btn = ui.button("Undo", on_click=_do_undo).props("flat")
        undo_btn.disable()
        _undo_buttons.append(undo_btn)
        ui.button("Preview JSON", on_click=_do_preview).props("flat")
        btn = ui.button("Save", on_click=_do_save).classes("bg-gray-600")
        _save_buttons.append(btn)

    with ui.column().classes("w-full max-w-5xl mx-auto p-4 gap-4"):
        ui.link("<< Back to Dashboard", "/").classes(
            "text-blue-400 hover:text-blue-300"
        )

        # Header row with title and mode toggle
        with ui.row().classes("w-full items-center justify-between"):
            mode_label = "Advanced" if advanced else "Simple"
            ui.label(f"Configuration Editor ({mode_label} Mode)").classes(
                "text-2xl font-bold"
            )

            toggle_target = "/config" if advanced else "/config/advanced"
            toggle_text = (
                "Switch to Simple Mode" if advanced else "Switch to Advanced Mode"
            )
            ui.link(toggle_text, toggle_target).classes(
                "text-blue-400 hover:text-blue-300 text-sm"
            )

        # -- Top action bar (visible without scrolling) ------------------------
        with ui.row().classes("w-full justify-end gap-2"):
            _create_action_buttons()

        if not advanced:
            # ---- Simple Mode: 8 topic-based tabs ----------------------------
            with ui.tabs().classes("w-full") as tabs:
                tab_jira = ui.tab("JIRA")
                tab_github = ui.tab("GitHub/GitLab")
                tab_repo = ui.tab("Repository & VCS")
                tab_workspaces = ui.tab("Workspaces")
                tab_ai = ui.tab("AI")
                tab_providers = ui.tab("Model Providers")
                tab_workflow = ui.tab("Workflow")
                tab_advanced = ui.tab("Advanced")

            with ui.tab_panels(tabs, value=tab_jira).classes("w-full"):
                with ui.tab_panel(tab_jira):
                    all_widgets["jira"] = _build_jira_tab(config)
                with ui.tab_panel(tab_github):
                    all_widgets["github"] = _build_github_tab(config)
                with ui.tab_panel(tab_repo):
                    all_widgets["repo"] = _build_repo_tab(config)
                with ui.tab_panel(tab_workspaces):
                    all_widgets["workspaces"] = _build_workspaces_tab(
                        config, bridge, _mark_dirty
                    )
                with ui.tab_panel(tab_ai):
                    all_widgets["ai"] = _build_ai_tab(config, _mark_dirty)
                with ui.tab_panel(tab_providers):
                    all_widgets["providers"] = _build_model_providers_tab(
                        config, bridge, _mark_dirty
                    )
                with ui.tab_panel(tab_workflow):
                    all_widgets["workflow"] = _build_workflow_tab(config)
                with ui.tab_panel(tab_advanced):
                    all_widgets["advanced"] = _build_advanced_tab(config)

        else:
            # ---- Advanced Mode: 4 file-based tabs ---------------------------
            with ui.tabs().classes("w-full") as tabs:
                tab_enterprise = ui.tab("Enterprise")
                tab_organization = ui.tab("Organization")
                tab_team = ui.tab("Team")
                tab_user = ui.tab("User")

            with ui.tab_panels(tabs, value=tab_enterprise).classes("w-full"):
                with ui.tab_panel(tab_enterprise):
                    all_widgets["enterprise"] = _build_enterprise_tab(bridge)
                with ui.tab_panel(tab_organization):
                    all_widgets["organization"] = _build_organization_tab(bridge)
                with ui.tab_panel(tab_team):
                    all_widgets["team_adv"] = _build_team_tab_advanced(bridge)
                with ui.tab_panel(tab_user):
                    all_widgets["user"] = _build_user_tab(config)

        # -- Bottom action bar -------------------------------------------------
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            _create_action_buttons()

    # -- Attach dirty-state and undo change listeners to all form widgets ------
    _attach_dirty_tracking(all_widgets, _state, _mark_dirty, _undo_buttons)
