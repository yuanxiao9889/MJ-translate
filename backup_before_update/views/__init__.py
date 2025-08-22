"""View modules for the MJ Translator.

This package bundles together UI components that were originally part
of the monolithic main module. Splitting them into a separate
namespace helps keep the top-level modules focused on specific
responsibilities. Each submodule here either re-exports existing
functions from ``main.py`` or, if desired, can be expanded with
additional helper functions in the future.
"""

__all__ = [
    "presets",
    "history",
    "favorites",
]