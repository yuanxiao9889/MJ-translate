"""Simple system tray integration for the MJ Translator.

This module provides the ``TrayManager`` class which encapsulates
interaction with the operating system tray using the ``pystray`` library.
It allows the main application window to minimize to the tray instead of
exiting when the user clicks the window close button. A context menu
provides options to restore the window or quit the application.

To use the tray manager, create an instance after constructing your root
window and call ``start_tray()``. You should also override the root's
``WM_DELETE_WINDOW`` protocol handler to call ``tray.on_close``.
"""

from __future__ import annotations

import threading
from typing import Optional, Callable

import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import messagebox


class TrayManager:
    """Manage a system tray icon for a Tkinter application."""

    def __init__(
        self,
        root: tk.Tk,
        app_name: str = "MJ Translator",
        icon_path: Optional[str] = None,
        close_to_tray: bool = True,
        on_quit: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize the tray manager.

        :param root: The Tkinter root window to manage.
        :param app_name: Name displayed in the tray tooltip.
        :param icon_path: Optional path to an image file used for the tray icon.
        :param close_to_tray: When True, closing the window hides it to the tray
            instead of exiting the application.
        :param on_quit: Optional callback invoked just before the application
            exits via the tray menu.
        """
        self.root = root
        self.app_name = app_name
        self.icon_path = icon_path
        self.close_to_tray = close_to_tray
        self.on_quit_callback = on_quit

        self.icon: Optional[pystray.Icon] = None
        self._tray_thread: Optional[threading.Thread] = None
        self._is_tray_running: bool = False

        # Use a simple generated icon if no path is provided
        self.image = self._load_or_generate_icon()

        # Intercept the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _load_or_generate_icon(self) -> Image.Image:
        """Load a custom icon or generate a simple one."""
        if self.icon_path:
            try:
                return Image.open(self.icon_path)
            except Exception:
                pass
        # Generate a default blue circle icon
        size = 32
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((4, 4, size - 4, size - 4), fill=(37, 99, 235, 255))
        return image

    def _create_menu(self) -> pystray.Menu:
        """Create the context menu for the tray icon."""
        return pystray.Menu(
            pystray.MenuItem(
                "显示主窗口", lambda: self.root.after(0, self.show_main_window)
            ),
            pystray.MenuItem(
                "退出程序", lambda: self.root.after(0, self._on_quit)
            ),
        )

    def start_tray(self) -> None:
        """Start the system tray icon on a background thread."""
        if self._is_tray_running:
            return
        self._is_tray_running = True

        def _run():
            self.icon = pystray.Icon(
                self.app_name,
                self.image,
                self.app_name,
                self._create_menu(),
            )
            self.icon.run()

        self._tray_thread = threading.Thread(target=_run, daemon=True)
        self._tray_thread.start()

    def on_close(self) -> None:
        """Handle the window close event.

        If ``close_to_tray`` is True, the window is hidden and the tray icon
        is started. Otherwise, the application will exit immediately.
        """
        if self.close_to_tray:
            self.hide_main_window()
            self.start_tray()
        else:
            self._on_quit()

    def _on_quit(self) -> None:
        """Quit the application and stop the tray icon."""
        try:
            if callable(self.on_quit_callback):
                self.on_quit_callback()
        except Exception:
            pass
        # Stop the tray icon
        try:
            if self.icon:
                self.icon.stop()
        except Exception:
            pass
        # Destroy the root window
        self.root.destroy()

    def hide_main_window(self) -> None:
        """Hide the main window from the taskbar."""
        try:
            # On Windows ``iconify`` minimizes to the taskbar, so use withdraw
            self.root.withdraw()
        except Exception:
            pass

    def show_main_window(self) -> None:
        """Restore and focus the main window."""
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass