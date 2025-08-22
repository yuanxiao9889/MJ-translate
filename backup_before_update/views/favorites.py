"""Favorites view for the MJ Translator.

This module provides access to the favorites window functionality. The
actual implementation remains in ``main.py`` for now; this module
re-exports the ``view_favorites`` function. If the favorites logic
is later refactored into a more modular form, the code can be moved
here without affecting callers.
"""

from __future__ import annotations

try:
    from views.ui_main import view_favorites  # type: ignore
except Exception:
    # Define a stub if the main module has not defined ``view_favorites``.
    def view_favorites(*args, **kwargs):  # type: ignore
        raise NotImplementedError("view_favorites is not available.")

__all__ = ["view_favorites"]