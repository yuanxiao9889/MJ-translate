"""历史记录和收藏夹服务模块

提供历史记录和收藏夹的保存功能，避免循环导入问题。
"""

import os
import json
import datetime
from tkinter import simpledialog, messagebox


def save_to_history(input_text_str, translated_str):
    """保存翻译记录到历史文件"""
    record = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input": input_text_str,
        "output": translated_str
    }
    history_file = "history.json"
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []
    history.insert(0, record)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def save_to_favorites(input_str, output_str):
    """保存内容到收藏夹"""
    # 标题输入弹窗
    _default_title = (output_str.strip().splitlines()[0] if output_str.strip() else (input_str.strip().splitlines()[0] if input_str.strip() else ""))[:30]
    _title = simpledialog.askstring("设置标题", "请输入收藏标题：", initialvalue=_default_title)
    if _title is None:  # 如果用户点击取消，则返回
        return
    if not _title:
        _title = _default_title or "未命名收藏"
    record = {"title": _title, "input": input_str.strip(), "output": output_str.strip(), "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    fav_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "favorites.txt")
    records = []
    if os.path.exists(fav_file):
        with open(fav_file, "r", encoding="utf-8") as f:
            try:
                records = json.load(f)
            except:
                records = [{"input": "", "output": line.strip()} for line in f if line.strip()]
    records.insert(0, record)
    with open(fav_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    messagebox.showinfo("已收藏", "输入和输出内容已添加到收藏夹")