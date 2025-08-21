"""Browser bridge and inbound queue handling.

This module encapsulates all logic related to the local HTTP bridge used by
the MJ Translator application. When the browser extension sends tags,
annotations or screenshots to the desktop app, the bridge handles saving the
data and queueing it for consumption by the UI. Separating this code into
its own module isolates the side effects (file I/O, HTTP polling) from the
rest of the application and makes it easier to test and maintain.

Key functions:

``start_bridge()``
    Starts the underlying HTTP server in a background thread using
    ``tag_sync_server.start_in_background``. Should be invoked before the
    UI is built.

``poll_from_browser(root)``
    Schedules periodic polling of the bridge's ``/api/pull`` endpoint on
    the given Tkinter root. New items are written to ``INBOX_PATH`` and
    any images are extracted to ``IMAGES_DIR``.

The constants ``BRIDGE_PORT``, ``INBOX_PATH`` and ``IMAGES_DIR`` define
where the bridge listens and where it stores incoming data. They are
calculated relative to the project root so that paths remain stable no
matter where this module is imported from.
"""

from __future__ import annotations

import os
import re
import json
import time
import base64
from typing import Optional, Dict, Any

import requests

# Import the correct function to start the tag sync server in the background.
# Depending on the version of ``tag_sync_server``, the function may be named
# ``start_in_background`` (older versions) or ``start_server_in_background`` (newer versions).
import sys
import os
# Add parent directory to path to import tag_sync_server from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Newer versions export ``start_server_in_background``. Alias it to
    # ``start_in_background`` for backward compatibility. The ``type: ignore`` comment
    # silences type checkers about conditional imports.
    from tag_sync_server import start_server_in_background as start_in_background  # type: ignore
except ImportError:
    # Fall back to importing the legacy name. This will still raise an
    # ImportError if neither function is available, which surfaces the error
    # during startup instead of silently passing.
    from tag_sync_server import start_in_background  # type: ignore

# Default port for the local HTTP bridge. You can override this when calling
# ``start_bridge`` if you need to run on a different port.
BRIDGE_PORT: int = 8766

# Compute project root relative to this file. This assumes that ``services``
# lives in the project root (e.g. project_root/services/bridge.py).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where incoming JSON payloads are appended. Each line is a JSON object.
INBOX_PATH: str = os.path.join(PROJECT_ROOT, "web_inbox.jsonl")

# Directory where base64 encoded images from the browser will be stored.
IMAGES_DIR: str = os.path.join(PROJECT_ROOT, "webcaps")
os.makedirs(IMAGES_DIR, exist_ok=True)

def start_bridge(port: int = BRIDGE_PORT) -> None:
    """Start the local HTTP bridge in a background thread.

    The bridge listens for POST requests from the browser extension on
    ``/api/push`` and stores incoming payloads for later processing. This
    function should be called once during application startup. If the
    bridge is already running, subsequent calls have no effect.

    :param port: TCP port on which to listen. Defaults to 8766.
    """
    start_in_background(port)

def _save_data_url_to_file(data_url: str, label_name: str = "浏览器截图") -> Optional[str]:
    """Persist a data URL as an image file and return its path.

    Data URLs encoded as ``data:image/<ext>;base64,...`` are extracted
    and written to the ``IMAGES_DIR`` directory. If the data URL is
    invalid or an error occurs during writing, ``None`` is returned.

    :param data_url: A base64 encoded image data URL.
    :param label_name: The label name to use for filename, defaults to "浏览器截图"
    :returns: Path to the saved image or ``None`` on failure.
    """
    try:
        match = re.match(r"^data:(image/\w+);base64,(.+)$", data_url)
        if not match:
            return None
        ext = match.group(1).split("/")[-1]
        raw = base64.b64decode(match.group(2))
        # 使用与本地标签相同的命名规则：中文标签名+时间戳
        import time
        filename = f"{label_name}_{int(time.time())}.{ext}"
        path = os.path.join(IMAGES_DIR, filename)
        with open(path, "wb") as f:
            f.write(raw)
        return path
    except Exception:
        return None

def process_payload(payload: Dict[str, Any]) -> None:
    """Handle an individual payload from the browser extension.

    If the payload contains an ``imageDataUrl`` key, the image will be
    written to disk and the ``imageDataUrl`` key will be replaced with
    ``imageFile`` containing the filesystem path. Then the payload is
    appended to ``INBOX_PATH`` as a JSON line.

    :param payload: The JSON object to process.
    """
    img_file: Optional[str] = None
    # Extract image data URL if present and convert it to a file
    if payload.get("imageDataUrl"):
        # 尝试从payload中获取标签名称，如果没有则使用默认值
        label_name = payload.get("label", payload.get("tag", "浏览器截图"))
        img_file = _save_data_url_to_file(payload["imageDataUrl"], label_name)
        if img_file:
            payload = dict(payload)  # make a shallow copy before mutating
            payload["imageFile"] = img_file
            payload.pop("imageDataUrl", None)

    # Append payload to inbox
    try:
        with open(INBOX_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Silently ignore write errors; callers can decide how to handle this
        pass

def poll_from_browser(root: Any, port: int = BRIDGE_PORT) -> None:
    """Schedule periodic polling of the bridge endpoint.

    This function uses Tkinter's ``after`` mechanism to schedule itself
    repeatedly. On each iteration it performs a GET request to the
    ``/api/pull`` endpoint on the bridge, processes each returned item via
    ``process_payload`` and then reschedules itself. Network errors are
    ignored silently.
    Additionally, this function monitors the tags.json file for changes
    and triggers UI refresh when modifications are detected.

    :param root: A Tkinter root or Toplevel used to schedule future
        invocations. Must implement ``after``.
    :param port: The TCP port where the bridge is listening.
    """
    # Check for tags.json file changes and refresh UI if needed
    _check_tags_file_and_refresh(root)
    
    url = f"http://127.0.0.1:{port}/api/pull"
    try:
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        items = response.json().get("items", [])
        for item in items:
            payload = item.get("data") or {}
            if isinstance(payload, dict):
                process_payload(payload)
    except Exception:
        # Ignore any network or JSON errors
        pass
    finally:
        # Reschedule polling after 1500ms
        try:
            root.after(1500, lambda: poll_from_browser(root, port))
        except Exception:
            pass

# Global variables to track tags.json file state
_tags_file_mtime = 0
_tags_file_exists = False

def _check_tags_file_and_refresh(root: Any) -> None:
    """Check if tags.json file has been modified and trigger UI refresh.
    
    This function monitors the modification time of tags.json file and
    triggers a UI refresh when changes are detected. It uses a simple
    file modification time tracking mechanism to avoid unnecessary refreshes.
    
    :param root: A Tkinter root or Toplevel used to access UI refresh functions.
    """
    global _tags_file_mtime, _tags_file_exists
    
    tags_file = os.path.join(PROJECT_ROOT, "tags.json")
    
    try:
        current_exists = os.path.exists(tags_file)
        current_mtime = 0
        
        if current_exists:
            current_mtime = os.path.getmtime(tags_file)
            
        # Check if file state has changed
        if (current_exists != _tags_file_exists) or \
           (current_exists and current_mtime != _tags_file_mtime):
            
            # Update tracking variables
            _tags_file_exists = current_exists
            _tags_file_mtime = current_mtime
            
            # Trigger UI refresh if the file exists
            if current_exists:
                try:
                    # Use a callback approach to avoid circular imports
                    if hasattr(root, 'refresh_tags_ui'):
                        root.refresh_tags_ui(tags_file)
                except Exception as e:
                    # Silently ignore refresh errors to avoid breaking the polling loop
                    pass
                    
    except Exception as e:
        # Silently ignore file checking errors to avoid breaking the polling loop
        pass