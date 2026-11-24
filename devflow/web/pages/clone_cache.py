"""Retained clone-cache review page."""

from pathlib import Path

from nicegui import ui

from devflow.config.loader import ConfigLoader
from devflow.utils.clone_cache import CloneCache
from devflow.web.components.nav import create_header


def create_clone_cache_page() -> None:
    """Render retained clone entries with per-entry and select-all controls."""
    create_header("Retained Clones")
    cache = CloneCache(ConfigLoader().load_config())
    entries = cache.inspect()
    selections: dict[Path, bool] = {}

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        ui.label("Retained session clones").classes("text-2xl font-bold")
        ui.label(
            "Only entries confirmed safe by the same lifecycle and reproducibility checks used by retention can be removed."
        ).classes("text-gray-400")
        select_all = ui.checkbox("Select all eligible")
        rows = ui.column().classes("w-full gap-2")

        def render() -> None:
            rows.clear()
            selections.clear()
            for entry in entries:
                selections[entry.root] = False
                with rows, ui.row().classes("w-full items-center gap-3"):
                    checkbox = ui.checkbox(value=False)
                    checkbox.on_value_change(
                        lambda event, root=entry.root: selections.__setitem__(
                            root, bool(event.value)
                        )
                    )
                    checkbox.enabled = entry.eligible
                    ui.label(f"{entry.root} ({entry.status})").classes("font-mono")
                    ui.label(entry.reason).classes("text-gray-400")

        render()

        def clear_selected() -> None:
            selected = [
                entry
                for entry in entries
                if selections.get(entry.root) and entry.eligible
            ]
            if not selected:
                ui.notify("Select at least one eligible entry", type="warning")
                return
            with ui.dialog() as dialog, ui.card():
                ui.label("Remove selected retained clones?")

                def confirm() -> None:
                    removed = 0
                    for entry in selected:
                        ok, _ = cache.remove(entry.root)
                        removed += int(ok)
                    dialog.close()
                    ui.notify(f"Removed {removed} clone(s)", type="positive")
                    ui.navigate.reload()

                with ui.row():
                    ui.button("Cancel", on_click=dialog.close)
                    ui.button("Remove", on_click=confirm).props("color=negative")
            dialog.open()

        def toggle_all(event: object) -> None:
            value = bool(getattr(event, "value", False))
            for entry in entries:
                if entry.eligible:
                    selections[entry.root] = value

        select_all.on_value_change(toggle_all)
        ui.button("Remove selected", on_click=clear_selected).props("color=negative")
