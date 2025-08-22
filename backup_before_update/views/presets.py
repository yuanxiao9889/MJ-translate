"""Preset selection dialog for the MJ Translator.

This module provides access to the preset-related dialog originally
implemented in the monolithic main module. It simply re-exports
functions from ``main.py`` to maintain compatibility with existing
code. If further customization or refactoring of preset handling is
desired, extend this module accordingly.
"""

from __future__ import annotations

# Import the preset functions from the main module. These functions
# manage the preset list and display the selection dialog. Importing
# at module level avoids circular import issues when ``main`` imports
# from ``views.presets``. Note that the functions are defined in
# ``main.py`` so that they can still access any required global state.
try:
    from main import show_expand_preset_dialog, load_expand_presets, save_expand_presets  # type: ignore
except Exception:
    # Fallback stubs in case ``main`` has not defined these symbols yet.
    def show_expand_preset_dialog(*args, **kwargs):  # type: ignore
        raise NotImplementedError("show_expand_preset_dialog is not available.")

    def load_expand_presets() -> list:  # type: ignore
        return []

    def save_expand_presets(presets: list) -> None:  # type: ignore
        pass

__all__ = ["show_expand_preset_dialog", "load_expand_presets", "save_expand_presets"]