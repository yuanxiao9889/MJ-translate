"""Tag management services for the MJ Translator.

This module provides functions for reading, writing and exporting tag data.
These functions were extracted from the original monolithic main module to
encapsulate data access and manipulation concerns. Tags are stored in
``tags.json`` relative to the project root. Optionally the functions can
sync with a remote storage via ``oss_sync`` if configured.
"""

from __future__ import annotations

import os
import json
import time
import csv
from typing import Dict, Any

try:
    from tkinter import messagebox
except Exception:
    messagebox = None  # Fallback when Tkinter is not available

# 导入统一文件I/O工具
from .file_utils import safe_json_load, safe_json_save, ensure_dir

# Attempt to import cloud sync functions. If not available the
# corresponding features will silently degrade to local only.
try:
    from oss_sync import save_tags_with_sync, load_tags_with_sync
except Exception:
    save_tags_with_sync = None  # type: ignore
    load_tags_with_sync = None  # type: ignore

# Path to the tags file relative to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAGS_FILE = os.path.join(PROJECT_ROOT, "tags.json")

# Path to pending data files used by process_pending_data. These allow
# browser‑sent data to be temporarily stored before being merged into
# the main tag file.
PENDING_TAGS_FILE = os.path.join(PROJECT_ROOT, "pending_tags.json")
PENDING_IMAGES_FILE = os.path.join(PROJECT_ROOT, "pending_images.json")

def clean_tag_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively clean tag names by stripping whitespace and newlines."""
    if not isinstance(data, dict):
        return data
    cleaned = {}
    for k, v in data.items():
        key = k.strip().replace("\n", "").replace("\r", "")
        cleaned[key] = clean_tag_keys(v) if isinstance(v, dict) else v
    return cleaned

def load_tags(use_cloud: bool = False) -> Dict[str, Any]:
    """Load tag data from disk or cloud storage.

    :param use_cloud: If True and cloud sync functions are available, load
        from remote storage instead of local file.
    :returns: A nested dictionary with ``head`` and ``tail`` keys.
    """
    if use_cloud and load_tags_with_sync:
        try:
            data = load_tags_with_sync()
            return clean_tag_keys(data)
        except Exception as e:
            if messagebox:
                messagebox.showerror("同步失败", f"从云端同步失败：{e}")
            return {"head": {}, "tail": {}}

    # Local loading using unified file I/O tools
    default_structure = {"head": {}, "tail": {}}
    data = safe_json_load(TAGS_FILE, default_structure)
    return clean_tag_keys(data)

def save_tags(tags_data: Dict[str, Any], use_cloud: bool = False) -> None:
    """Save tag data to disk and optionally sync to cloud.

    A timestamp will be added under the key ``last_modified``. If cloud
    syncing is enabled and the corresponding functions are available,
    they will be invoked. Also creates backup files automatically.
    """
    import datetime
    import shutil
    
    # Ensure project directory exists
    ensure_dir(PROJECT_ROOT)
    
    # Clean tag keys before saving
    tags_data = clean_tag_keys(tags_data)
    
    # Create backup if file exists
    if os.path.exists(TAGS_FILE):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(PROJECT_ROOT, f"tags_backup_{timestamp}.json")
        shutil.copy2(TAGS_FILE, backup_path)
        
        # Keep only latest 5 backups
        backup_files = sorted(
            [f for f in os.listdir(PROJECT_ROOT) if f.startswith("tags_backup_")],
            reverse=True
        )
        for old_backup in backup_files[5:]:
            try:
                os.remove(os.path.join(PROJECT_ROOT, old_backup))
            except Exception:
                pass  # Ignore backup cleanup errors
    
    # Write local file with a timestamp using unified file I/O tools
    tags_data["last_modified"] = time.time()
    safe_json_save(TAGS_FILE, tags_data)
    
    # Sync to cloud if requested
    if use_cloud and save_tags_with_sync:
        try:
            save_tags_with_sync(tags_data)
        except Exception as e:
            if messagebox:
                messagebox.showwarning("云端同步失败", f"{e}")

def export_tags_to_csv(output_path: str | None = None) -> str:
    """Export tag data to a CSV file and return the file path."""
    if output_path is None:
        output_path = os.path.join(PROJECT_ROOT, "tags_export.csv")
    data = load_tags(use_cloud=False)
    rows = []
    for section in ("head", "tail"):
        section_data = data.get(section, {}) or {}
        for category, tag_map in section_data.items():
            if not isinstance(tag_map, dict):
                continue
            for key, val in tag_map.items():
                val_str = (
                    json.dumps(val, ensure_ascii=False)
                    if not isinstance(val, (str, int, float))
                    else val
                )
                rows.append([section, category, key, val_str])
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["section", "category", "key", "value"])
        writer.writerows(rows)
    return output_path

    # process_pending_data 函数已移至 services.data_processor.py 模块
    # 避免重复定义和循环导入问题