"""Service package for the MJ Translator application.

This package contains helper modules that encapsulate various services used by
the application. Splitting these responsibilities into separate modules helps
reduce the size of the main application file and makes each component easier
to understand and maintain. See ``bridge.py`` for the browser‑bridge service
implementation.
"""

__version__ = "1.0.0"

__all__ = ["bridge"]