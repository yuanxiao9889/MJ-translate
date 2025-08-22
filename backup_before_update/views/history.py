"""History view for the MJ Translator.

This module exposes the history window functionality. It simply
re-exports the ``view_history`` function from ``main.py``. Should the
history implementation need to be maintained separately in future,
it can be relocated here, leaving the interface unchanged.
"""

from __future__ import annotations

try:
    from views.ui_main import view_history  # type: ignore
except Exception:
    # Provide a meaningful stub if the main module has not yet defined
    # ``view_history``. This allows the program to import the module
    # without crashing during startup.
    def view_history(*args, **kwargs):  # type: ignore
        raise NotImplementedError("view_history is not available.")

__all__ = ["view_history"]