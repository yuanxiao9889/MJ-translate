"""Application entry point for the modular MJ Translator.

This module centralizes the startup sequence for the application. It
initializes the local HTTP bridge, creates the Tkinter root window,
configures the system tray icon, builds the UI by calling into
``main.start_ui`` and schedules polling of the browser bridge. Running
this module will start the event loop to keep the application alive.

Separating these responsibilities from ``main.py`` keeps the main module
focused on business logic while ``app.py`` handles environment setup.
"""

from __future__ import annotations

import customtkinter as ctk

from tray_manager import TrayManager
from services.bridge import start_bridge, poll_from_browser
from views.ui_main import build_ui
from services.api import load_api_config
from services.data_processor import process_pending_data


def run() -> None:
    """Start the MJ Translator application.

    This function performs the following steps:

    * Starts the background HTTP bridge used by the browser extension.
    * Creates the main Tkinter root window.
    * Initializes the system tray icon so closing the window minimizes
      to the tray rather than exiting.
    * Delegates UI construction to ``main.start_ui`` passing the root.
    * Schedules periodic polling of the browser bridge.
    * Enters the Tkinter main event loop.
    """
    # 1) Start the local bridge. This call is idempotent; if the bridge
    #    is already running it does nothing.
    start_bridge()

    # 2) Create the root window using customtkinter. Set title, geometry
    #    and minimum size here for centralized window configuration.
    root = ctk.CTk()
    root.title("MJ提示词工具")
    # 设置窗口图标
    try:
        root.iconbitmap("mj_icon.ico")
    except Exception as e:
        print(f"设置图标失败: {e}")
    
    # 设置窗口尺寸和最小尺寸
    root.geometry("1200x830")
    root.minsize(950, 650)

    # 3) Setup the system tray. ``TrayManager`` will intercept the
    #    window close event and minimize to the tray. When the user
    #    selects "退出程序" from the tray menu the application exits.
    tray = TrayManager(root, app_name="MJ提示词工具", icon_path=None, close_to_tray=True)
    tray.start_tray()

    # 统一配置加载和数据处理
    load_api_config()
    process_pending_data()

    # 4) Build the UI via views.ui_main.build_ui
    build_ui(root)

    # 5) Begin polling the browser bridge for incoming data. This will
    #    schedule itself repeatedly using ``root.after``.
    poll_from_browser(root)

    # 暴露global_root给其他模块使用
    import sys
    sys.modules[__name__].global_root = root
    
    # 暴露refresh_tags_ui函数给其他模块使用
    if hasattr(root, 'refresh_tags_ui'):
        sys.modules[__name__].refresh_tags_ui = root.refresh_tags_ui

    # 6) Start the Tk event loop. This call will block until the user
    #    exits the application via the tray menu or the window is closed
    #    without tray minimization.
    root.mainloop()


if __name__ == "__main__":
    run()