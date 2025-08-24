"""Text selection translation service.

This module provides text selection detection and automatic translation
functionality with floating tooltip display. It integrates with the existing
translation API services and provides a seamless user experience.
"""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
import threading
import time
from typing import Optional, Callable, Tuple

from .api import translate_text
from .logger import logger, safe_execute
# Pillow for shadow rendering
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter
except Exception:
    Image = ImageTk = ImageDraw = ImageFilter = None


class FloatingTooltip:
    """Floating tooltip widget for displaying translation results."""
    
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        self.tooltip_window: Optional[tk.Toplevel] = None
        self.fade_after_id: Optional[str] = None
        
    def show(self, text: str, x: int, y: int) -> None:
        """Show tooltip at specified coordinates."""
        self.hide()  # Hide any existing tooltip
        
        # Create tooltip window
        self.tooltip_window = tk.Toplevel(self.parent)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_attributes("-topmost", True)
        # 移除 alpha，保持不透明，避免驱动/主题问题
        # self.tooltip_window.wm_attributes("-alpha", 0.95)
        
        # Style the tooltip
        frame = ctk.CTkFrame(
            self.tooltip_window,
            fg_color=("#ffffff", "#2b2b2b"),
            border_width=1,
            border_color=("#cccccc", "#555555"),
            corner_radius=8
        )
        frame.pack(fill="both", expand=True)
        
        # Add text label
        label = ctk.CTkLabel(
            frame,
            text=text,
            font=("微软雅黑", 12),
            text_color=("#333333", "#ffffff"),
            wraplength=300,
            justify="left"
        )
        label.pack(padx=10, pady=8)
        
        # Position tooltip
        self.tooltip_window.update_idletasks()
        width = self.tooltip_window.winfo_reqwidth()
        height = self.tooltip_window.winfo_reqheight()
        
        # Adjust position to keep tooltip on screen
        screen_width = self.tooltip_window.winfo_screenwidth()
        screen_height = self.tooltip_window.winfo_screenheight()
        
        if x + width > screen_width:
            x = screen_width - width - 10
        if y + height > screen_height:
            y = y - height - 10
            
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # Auto-hide after 5 seconds
        self.fade_after_id = self.tooltip_window.after(5000, self.hide)
        
    def hide(self) -> None:
        """Hide the tooltip."""
        if self.fade_after_id:
            try:
                self.tooltip_window.after_cancel(self.fade_after_id)
            except (tk.TclError, AttributeError):
                pass
            self.fade_after_id = None
            
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except tk.TclError:
                pass
            self.tooltip_window = None


class TextSelectionTranslator:
    """Text selection translator with automatic detection and translation."""
    
    def __init__(self, text_widget: tk.Text):
        self.text_widget = text_widget
        self.tooltip = FloatingTooltip(text_widget)
        self.selection_timer: Optional[threading.Timer] = None
        self.last_selection = ""
        self.translation_thread: Optional[threading.Thread] = None
        
        # Bind selection events
        self._bind_events()
        
    def _bind_events(self) -> None:
        """Bind text selection events."""
        # Bind selection events
        self.text_widget.bind("<<Selection>>", self._on_selection_change)
        self.text_widget.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.text_widget.bind("<KeyRelease>", self._on_key_release)
        
    def _on_selection_change(self, event=None) -> None:
        """Handle selection change event."""
        self._schedule_translation_check()
        
    def _on_mouse_release(self, event=None) -> None:
        """Handle mouse release event."""
        self._schedule_translation_check()
        
    def _on_key_release(self, event=None) -> None:
        """Handle key release event."""
        # Only check for selection-related keys
        if event and event.keysym in ('Left', 'Right', 'Up', 'Down', 'Home', 'End', 'Prior', 'Next'):
            self._schedule_translation_check()
            
    def _schedule_translation_check(self) -> None:
        """Schedule translation check after 2 seconds delay."""
        # Cancel existing timer
        if self.selection_timer:
            self.selection_timer.cancel()
            
        # Schedule new timer
        self.selection_timer = threading.Timer(1.5, self._check_and_translate)
        self.selection_timer.daemon = True
        self.selection_timer.start()
        
    def _check_and_translate(self) -> None:
        """Check current selection and translate if valid."""
        try:
            # Get current selection
            try:
                selection = self.text_widget.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
            except tk.TclError:
                # No selection
                return
                
            # Skip if selection is empty or same as last
            if not selection or selection == self.last_selection:
                return
                
            # Skip if selection is too short or too long
            if len(selection) < 2 or len(selection) > 500:
                return
                
            # Skip if selection contains mostly Chinese (assume it's already translated)
            if self._is_mostly_chinese(selection):
                return
                
            self.last_selection = selection
            
            # Start translation in background thread
            if self.translation_thread and self.translation_thread.is_alive():
                return  # Previous translation still running
                
            self.translation_thread = threading.Thread(
                target=self._translate_and_show,
                args=(selection,),
                daemon=True
            )
            self.translation_thread.start()
            
        except Exception as e:
            logger.error(f"Error in translation check: {e}")
            
    def _translate_and_show(self, text: str) -> None:
        """Translate text and show result in tooltip."""
        try:
            # Translate text
            # 使用用户选择的翻译API
            current_api = get_current_translation_api()
            
            # 临时设置翻译平台
            from .api import set_current_platform, get_current_platform
            original_platform = get_current_platform()
            set_current_platform(current_api)
            
            try:
                translated = translate_text(text)
            finally:
                # 恢复原始平台设置
                set_current_platform(original_platform)
            
            # Skip if translation failed or is same as original
            if not translated or translated.startswith('[') or translated == text:
                return
                
            # Get cursor position for tooltip placement
            try:
                # Get selection coordinates
                bbox = self.text_widget.bbox(tk.SEL_FIRST)
                if bbox:
                    x = self.text_widget.winfo_rootx() + bbox[0]
                    y = self.text_widget.winfo_rooty() + bbox[1] + bbox[3] + 5
                else:
                    # Fallback to widget center
                    x = self.text_widget.winfo_rootx() + self.text_widget.winfo_width() // 2
                    y = self.text_widget.winfo_rooty() + self.text_widget.winfo_height() // 2
            except (tk.TclError, AttributeError):
                # Fallback position
                x = self.text_widget.winfo_rootx() + 100
                y = self.text_widget.winfo_rooty() + 100
                
            # Show tooltip with translation
            self.text_widget.after(0, lambda: self.tooltip.show(translated, x, y))
            
        except Exception as e:
            logger.error(f"Error in translation: {e}")
            
    def _is_mostly_chinese(self, text: str) -> bool:
        """Check if text is mostly Chinese characters."""
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        return chinese_chars > len(text) * 0.5
        
    def destroy(self) -> None:
        """Clean up resources."""
        if self.selection_timer:
            self.selection_timer.cancel()
            
        if self.translation_thread and self.translation_thread.is_alive():
            # Note: We can't force-stop a thread, but it will finish naturally
            pass
            
        self.tooltip.hide()


# 全局翻译API配置
_current_translation_api = 'baidu'

def update_translation_api(api_key):
    """更新翻译API配置"""
    global _current_translation_api
    _current_translation_api = api_key
    print(f"划词翻译API已切换为: {api_key}")

def get_current_translation_api():
    """获取当前翻译API配置"""
    return _current_translation_api

def enable_text_selection_translation(text_widget: tk.Text) -> TextSelectionTranslator:
    """Enable text selection translation for a text widget.
    
    Args:
        text_widget: The text widget to enable translation for
        
    Returns:
        TextSelectionTranslator instance for further control
    """
    return TextSelectionTranslator(text_widget)


# ==== 新增：系统级全局热键 + 桌面划词翻译（Ctrl+T 触发） ====

# 仅在 Windows 下可用（使用 ctypes 调用 Win32 API）
try:
    import ctypes
    from ctypes import wintypes
except Exception:
    ctypes = None

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_T = 0x54
VK_CONTROL = 0x11
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002

# ==== 新增：配置与热键解析工具 ====
import os, json

def _config_path() -> str:
    return os.path.join(os.getcwd(), "config.json")

def _load_config_dict() -> dict:
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config_dict(cfg: dict) -> None:
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# 修饰键与按键解析/格式化
_MOD_NAME_MAP = {
    "CTRL": MOD_CONTROL,
    "CONTROL": MOD_CONTROL,
    "ALT": MOD_ALT,
    "SHIFT": MOD_SHIFT,
    "WIN": MOD_WIN,
    "WINDOWS": MOD_WIN,
}

def _vk_for_key(key: str) -> int:
    k = key.upper()
    # A-Z
    if len(k) == 1 and "A" <= k <= "Z":
        return ord(k)
    # 0-9
    if len(k) == 1 and "0" <= k <= "9":
        return ord(k)
    # F1-F24
    if k.startswith("F") and k[1:].isdigit():
        n = int(k[1:])
        if 1 <= n <= 24:
            return 0x70 + (n - 1)
    # 常见键别名
    aliases = {
        "TAB": 0x09,
        "SPACE": 0x20,
        "ESC": 0x1B,
        "ESCAPE": 0x1B,
        "ENTER": 0x0D,
        "RETURN": 0x0D,
        "BACKSPACE": 0x08,
    }
    if k in aliases:
        return aliases[k]
    raise ValueError(f"不支持的按键: {key}")

def parse_hotkey_string(hotkey: str) -> tuple[int, int]:
    if not isinstance(hotkey, str) or not hotkey.strip():
        raise ValueError("热键字符串不能为空")
    parts = [p.strip() for p in hotkey.replace("-", "+").split("+") if p.strip()]
    if not parts:
        raise ValueError("无效的热键")
    mods = 0
    key_part = None
    for p in parts:
        up = p.upper()
        if up in _MOD_NAME_MAP:
            mods |= _MOD_NAME_MAP[up]
        else:
            key_part = p
    if key_part is None:
        raise ValueError("缺少主键，例如: Ctrl+T")
    vk = _vk_for_key(key_part)
    return mods, vk

def _format_hotkey(mods: int, vk: int) -> str:
    names = []
    if mods & MOD_CONTROL: names.append("Ctrl")
    if mods & MOD_ALT: names.append("Alt")
    if mods & MOD_SHIFT: names.append("Shift")
    if mods & MOD_WIN: names.append("Win")
    # 反向格式化 vk
    def key_name_from_vk(v: int) -> str:
        if 0x41 <= v <= 0x5A:
            return chr(v)
        if 0x30 <= v <= 0x39:
            return chr(v)
        if 0x70 <= v <= 0x87:
            return f"F{v - 0x70 + 1}"
        table = {0x09: "Tab", 0x20: "Space", 0x1B: "Esc", 0x0D: "Enter", 0x08: "Backspace"}
        return table.get(v, hex(v))
    names.append(key_name_from_vk(vk))
    return "+".join(names) if names else ""

# 全局持有系统翻译控制器实例，便于运行时更新热键
_system_translator_instance = None  # type: ignore

def get_current_system_hotkey() -> str:
    try:
        inst = _system_translator_instance
        if inst is not None and hasattr(inst, "_modifiers"):
            return _format_hotkey(inst._modifiers, inst._vk)  # type: ignore
    except Exception:
        pass
    cfg = _load_config_dict()
    return cfg.get("system_hotkey", "Ctrl+T")

def update_system_hotkey(hotkey_str: str) -> None:
    """更新系统划词翻译的全局热键（立即生效并持久化）。"""
    mods, vk = parse_hotkey_string(hotkey_str)
    # 更新运行中实例
    inst = _system_translator_instance
    if inst is not None:
        try:
            inst.rebind_hotkey(mods, vk)  # type: ignore
        except Exception as e:
            raise e
    # 落地到配置
    cfg = _load_config_dict()
    cfg["system_hotkey"] = _format_hotkey(mods, vk)
    _save_config_dict(cfg)

class SystemFloatingPopup:
    """系统级悬浮翻译弹窗（美观卡片式UI，标题栏+圆角+分隔线，Canvas 模糊阴影）。"""
    def __init__(self, root: tk.Misc):
        self.root = root
        self.win: Optional[tk.Toplevel] = None
        self.shadow_wins: list[tk.Toplevel] = []  # 兼容保留，不再使用
        self._shadow_canvas: Optional[tk.Canvas] = None
        self._shadow_img_tk: Optional[ImageTk.PhotoImage] = None  # Pillow 影像引用
        self._shadow_margin = 20
        self._corner_radius = 12
        self._shadow_blur = 18
        self._shadow_alpha = 120  # 0-255 (阴影不透明度)
        self.lbl_src: Optional[ctk.CTkLabel] = None
        self.lbl_dst: Optional[ctk.CTkLabel] = None
        self.top_scroll: Optional[ctk.CTkScrollableFrame] = None
        self.content_scroll: Optional[ctk.CTkScrollableFrame] = None
        self._visible = False
        self._mask_color = "#00ff00"  # Windows 透明镂空色
        self._pos_x = 0
        self._pos_y = 0
        # 调整默认尺寸与换行宽度，让信息容纳更好
        self._max_src_height = 170
        self._max_dst_height = 480
        self._wraplength = 520
        # 记录当前滚动区域高度，用于按屏幕空间自适应
        self._top_h: int = 0
        self._dst_h: int = 0
        # 记录是否启用了透明色（避免与全局 alpha 冲突）
        self._use_transparentcolor: bool = False
        # 新增：是否启用阴影（禁用可绕过部分显卡/透明度组合导致的遮罩问题）
        self._enable_shadow: bool = False
        # 新增：极简安全模式（True 时完全不走 CTk/Canvas 路径，仅用纯 Tk 渲染）
        self.simple_mode: bool = True

    def show(self, original: str, x: int, y: int, pending: bool = True):
        self.hide()
    
        # 极简安全模式：完全避开 CTk / Canvas / 透明 & 阴影
        if getattr(self, "simple_mode", False):
            self.win = tk.Toplevel(self.root)
            # 不使用 overrideredirect，交给系统窗口管理器，兼容性最好
            self.win.wm_attributes("-topmost", True)
            try:
                self.win.title("翻译结果")
            except Exception:
                pass
            container = tk.Frame(self.win, bg="#2b2b2b")
            container.pack(fill="both", expand=True)
            src_lbl = tk.Label(container, text=original, justify="left",
                                fg="#eaeaea", bg="#2b2b2b", wraplength=320, anchor="w", font=("微软雅黑", 14))
            src_lbl.pack(fill="x", padx=12, pady=(10, 6))
            sep = tk.Frame(container, height=1, bg="#444444")
            sep.pack(fill="x", padx=10, pady=(0, 6))
            self.lbl_dst = tk.Label(container, text=("翻译中…" if pending else ""), justify="left",
                                     fg="#ffffff", bg="#2b2b2b", wraplength=320, anchor="w", font=("微软雅黑", 14))
            self.lbl_dst.pack(fill="x", padx=12, pady=(0, 12))
            # 统一引用，update_translation 复用
            self.lbl_src = src_lbl  # type: ignore
    
            # 计算并放置位置，确保最小尺寸为 350x150
            self.win.update_idletasks()
            w = max(350, container.winfo_reqwidth())
            h = max(150, container.winfo_reqheight())
            scr_w = self.win.winfo_screenwidth()
            scr_h = self.win.winfo_screenheight()
            if x + w > scr_w:
                x = max(5, scr_w - w - 10)
            if y + h > scr_h:
                y = max(5, scr_h - h - 10)
            self._pos_x, self._pos_y = x, y
            self.win.geometry(f"{w}x{h}+{x}+{y}")
            self._visible = True
            return
    
        # 主弹窗：改回标准 Tk Toplevel，提升兼容性（高级样式路径）
        self.win = tk.Toplevel(self.root)
        self.win.wm_overrideredirect(True)
        self.win.wm_attributes("-topmost", True)
        # 彻底禁用色键与整窗透明，排除透明合成导致的遮罩/空白问题
        self._use_transparentcolor = False
        try:
            # 保持完全不透明，避免显卡/主题组合问题
            self.win.configure(bg="#111111")
        except Exception:
            pass

        # 先创建外层卡片容器（稍后赋予边距以给阴影留空间）
        outer = ctk.CTkFrame(
            self.win,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=self._corner_radius,
            border_width=1,
            border_color=("#d9d9d9", "#444444"),
        )

        # 顶部标题栏
        header = ctk.CTkFrame(
            outer,
            fg_color=("#f7f7f7", "#1f1f1f"),
            corner_radius=self._corner_radius,
            border_width=0,
        )
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)
        title_lbl = ctk.CTkLabel(
            header,
            text="翻译结果",
            font=("微软雅黑", 12, "bold"),
            text_color=("#4b4b4b", "#dddddd"),
        )
        title_lbl.grid(row=0, column=0, sticky="w", padx=6, pady=4)

        # 关闭按钮
        close_lbl = ctk.CTkLabel(
            header,
            text="×",
            width=24,
            height=24,
            font=("微软雅黑", 18, "bold"),
            text_color=("#666666", "#d0d0d0"),
        )
        close_lbl.grid(row=0, column=1, sticky="e", padx=6, pady=4)
        close_lbl.configure(cursor="hand2")
        close_lbl.bind("<Button-1>", lambda e: self.hide())
        close_lbl.bind("<Enter>", lambda e: close_lbl.configure(text_color=("#111111", "#ffffff")))
        close_lbl.bind("<Leave>", lambda e: close_lbl.configure(text_color=("#666666", "#d0d0d0")))

        # 原文（可滚动）
        self.top_scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self.top_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(2, 6))
        self.lbl_src = ctk.CTkLabel(
            self.top_scroll,
            text=original,
            justify="left",
            font=("微软雅黑", 14),
            text_color=("#333333", "#eaeaea"),
            wraplength=self._wraplength,
        )
        self.lbl_src.grid(row=0, column=0, sticky="w")

        # 分割线
        is_dark = (ctk.get_appearance_mode() == "Dark")
        divider_color = "#3f3f3f" if is_dark else "#e8e8e8"
        divider = tk.Frame(outer, bg=divider_color, height=1, highlightthickness=0, bd=0)
        divider.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        # 译文（可滚动）
        self.content_scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self.content_scroll.grid(row=3, column=0, sticky="nsew", padx=12, pady=(2, 12))
        self.lbl_dst = ctk.CTkLabel(
            self.content_scroll,
            text=("翻译中…" if pending else ""),
            justify="left",
            font=("微软雅黑", 14),
            text_color=("#111111", "#ffffff"),
            wraplength=self._wraplength,
        )
        self.lbl_dst.grid(row=0, column=0, sticky="w")

        outer.grid_rowconfigure(0, weight=0)  # header
        outer.grid_rowconfigure(1, weight=0)  # source
        outer.grid_rowconfigure(2, weight=0)  # divider
        outer.grid_rowconfigure(3, weight=1)  # translation
        outer.grid_columnconfigure(0, weight=1)

        # 先测量内容尺寸
        self.win.update_idletasks()
        self._apply_scroll_limits()
        self.win.update_idletasks()

        # 创建/绘制 Canvas 阴影，并统一布局（Canvas 背景 + 外层卡片 with 边距）
        self._install_or_update_shadow(outer)

        # 放置窗口
        self._fit_and_place(x, y)
        self._visible = True

    # Canvas 阴影：创建或更新
    def _install_or_update_shadow(self, outer: ctk.CTkFrame):
        if not self.win:
            return
        # 如果禁用阴影：直接布局外层卡片并退出（默认禁用）
        if getattr(self, "_enable_shadow", False) is False:
            if self._shadow_canvas is not None:
                try:
                    self._shadow_canvas.destroy()
                except Exception:
                    pass
                self._shadow_canvas = None
            # 简单边距布局
            outer.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
            self.win.grid_rowconfigure(0, weight=1)
            self.win.grid_columnconfigure(0, weight=1)
            self.win.update_idletasks()
            return
        # 计算内容尺寸
        self.win.update_idletasks()
        ow = max(outer.winfo_reqwidth(), outer.winfo_width())
        oh = max(outer.winfo_reqheight(), outer.winfo_height())
        cw = ow + self._shadow_margin * 2
        ch = oh + self._shadow_margin * 2

        # 生成或更新阴影图
        if Image and ImageTk:
            img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            rr = Image.new("L", (cw, ch), 0)
            draw = ImageDraw.Draw(rr)
            x0 = self._shadow_margin
            y0 = self._shadow_margin
            x1 = x0 + ow
            y1 = y0 + oh
            # 圆角矩形蒙版（先画实心白，再高斯模糊作为阴影）
            draw.rounded_rectangle([x0, y0, x1, y1], radius=self._corner_radius + 2, fill=255)
            blurred = rr.filter(ImageFilter.GaussianBlur(self._shadow_blur))
            # 合成到 RGBA：黑色阴影 + 期望不透明度
            shadow_rgba = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            shadow_rgba.paste((0, 0, 0, self._shadow_alpha), (0, 0), blurred)
            self._shadow_img_tk = ImageTk.PhotoImage(shadow_rgba)
        else:
            self._shadow_img_tk = None

        # 创建或更新 Canvas
        if self._shadow_canvas is None:
            self._shadow_canvas = tk.Canvas(
                self.win,
                width=cw,
                height=ch,
                bd=0,
                highlightthickness=0,
                bg=(self._mask_color if self._use_transparentcolor else "#111111"),
                relief="flat",
            )
            # Canvas 铺满父容器
            self._shadow_canvas.grid(row=0, column=0, sticky="nsew")
            self.win.grid_rowconfigure(0, weight=1)
            self.win.grid_columnconfigure(0, weight=1)
        else:
            self._shadow_canvas.configure(width=cw, height=ch, bg=(self._mask_color if self._use_transparentcolor else "#111111"))
            self._shadow_canvas.delete("all")

        # 绘制阴影图
        if self._shadow_img_tk is not None:
            self._shadow_canvas.create_image(0, 0, image=self._shadow_img_tk, anchor="nw")
        else:
            # Pillow 不可用时的退化：用一层半透明矩形模拟（效果较弱）
            m = self._shadow_margin
            self._shadow_canvas.create_rectangle(
                m-4, m-4, cw-(m-4), ch-(m-4), fill="#000000", outline="", stipple="gray50"
            )

        # 将外层卡片放在同一个格子，设置边距以露出阴影
        outer.grid(row=0, column=0, sticky="nsew", padx=self._shadow_margin, pady=self._shadow_margin)
        # 控制堆叠顺序：先画 Canvas，再抬起卡片
        try:
            self._shadow_canvas.lower()
            outer.lift()
        except Exception:
            pass

        # 重新测量窗口尺寸
        self.win.update_idletasks()

    # 限制各区高度并记录值
    def _apply_scroll_limits(self):
        if not self.win:
            return
        # 限制原文高度
        if self.top_scroll and self.lbl_src:
            self.top_scroll.update_idletasks()
            src_req = self.lbl_src.winfo_reqheight() + 6
            h = min(max(40, src_req), self._max_src_height)
            self.top_scroll.configure(height=h)
            self._top_h = int(h)
        # 限制译文高度
        if self.content_scroll and self.lbl_dst:
            self.content_scroll.update_idletasks()
            dst_req = self.lbl_dst.winfo_reqheight() + 8
            h2 = min(max(40, dst_req), self._max_dst_height)
            self.content_scroll.configure(height=h2)
            self._dst_h = int(h2)

    # 使窗口在屏幕内显示，并根据可用空间进一步压缩滚动区高度
    def _fit_and_place(self, x: int, y: int):
        if not self.win:
            return
        self.win.update_idletasks()
        width = self.win.winfo_reqwidth()
        height = self.win.winfo_reqheight()
        # 强制最小尺寸
        width = max(350, int(width))
        height = max(150, int(height))
        scr_w = self.win.winfo_screenwidth()
        scr_h = self.win.winfo_screenheight()
        max_h = int(scr_h * 0.8)
        if height > max_h:
            overflow = height - max_h
            if self.content_scroll and self._dst_h:
                new_dst = max(80, self._dst_h - overflow)
                overflow -= max(0, self._dst_h - new_dst)
                self.content_scroll.configure(height=new_dst)
                self._dst_h = int(new_dst)
            if overflow > 0 and self.top_scroll and self._top_h:
                new_top = max(60, self._top_h - overflow)
                self.top_scroll.configure(height=new_top)
                self._top_h = int(new_top)
            # 高度改变后需要更新阴影画布
            self._install_or_update_shadow(self.top_scroll.master)  # outer
            self.win.update_idletasks()
            width = self.win.winfo_reqwidth()
            height = self.win.winfo_reqheight()
            width = max(350, int(width))
            height = max(150, int(height))
        if x + width > scr_w:
            x = max(5, scr_w - width - 10)
        if y + height > scr_h:
            y = max(5, scr_h - height - 10)
        self._pos_x, self._pos_y = x, y
        self.win.geometry(f"{width}x{height}+{x}+{y}")

    def _create_shadows(self, width: int, height: int, x: int, y: int):
        """兼容保留：不再创建多窗口阴影。"""
        for sw in self.shadow_wins:
            try:
                sw.destroy()
            except tk.TclError:
                pass
        self.shadow_wins.clear()
        return

    def update_translation(self, translated: str):
        if self.lbl_dst and self.win:
            self.lbl_dst.configure(text=translated)
            # 更新排版与高度限制 + 重新绘制阴影
            self._apply_scroll_limits()
            self.win.update_idletasks()
            # outer = self.top_scroll.master  # type: ignore
            try:
                outer = self.top_scroll.master  # type: ignore
                self._install_or_update_shadow(outer)
            except Exception:
                pass
            self._fit_and_place(self._pos_x, self._pos_y)

    def hide(self):
        self._visible = False
        if self.win:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
        for sw in self.shadow_wins:
            try:
                sw.destroy()
            except tk.TclError:
                pass
        self.shadow_wins.clear()


class GlobalHotkeyListener:
    """使用 Win32 RegisterHotKey 监听全局热键（后台线程）。"""
    def __init__(self, modifiers: int, vk: int, callback: Callable[[], None]):
        self.modifiers = modifiers
        self.vk = vk
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None

    def start(self):
        if ctypes is None:
            logger.error("ctypes 不可用，无法注册全局热键")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, self.modifiers, self.vk):
            logger.error("注册全局热键失败（可能被其它程序占用）")
            return
        msg = wintypes.MSG()
        try:
            while self._running:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0:  # WM_QUIT
                    break
                if msg.message == WM_HOTKEY:
                    try:
                        self.callback()
                    except Exception as e:
                        logger.error(f"热键回调错误: {e}")
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            user32.UnregisterHotKey(None, 1)

    def stop(self):
        if not self._running:
            return
        self._running = False
        try:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
        except Exception:
            pass


def _simulate_ctrl_c():
    """模拟 Ctrl+C，将选中文本复制到剪贴板。"""
    if ctypes is None:
        return
    user32 = ctypes.windll.user32
    try:
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_C, 0, 0, 0)
        time.sleep(0.06)
        user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    except Exception as e:
        logger.error(f"模拟 Ctrl+C 失败: {e}")


def enable_system_selection_translation_global(root: tk.Misc) -> "SystemSelectionTranslator":
    """启用系统级划词翻译（读取配置中的自定义热键，默认 Ctrl+T）。"""
    # 从配置读取热键
    cfg = _load_config_dict()
    hotkey_str = cfg.get("system_hotkey", "Ctrl+T")
    try:
        mods, vk = parse_hotkey_string(hotkey_str)
    except Exception:
        mods, vk = MOD_CONTROL, VK_T
    inst = SystemSelectionTranslator(root, mods, vk)
    global _system_translator_instance
    _system_translator_instance = inst
    return inst


class SystemSelectionTranslator:
    def __init__(self, root: tk.Misc, modifiers: int = MOD_CONTROL, vk: int = VK_T):
        self.root = root
        self.popup = SystemFloatingPopup(root)
        self._modifiers = modifiers
        self._vk = vk
        self.hotkey = GlobalHotkeyListener(modifiers, vk, self._on_hotkey)
        self._last_text = ""
        self._translating = False
        self.hotkey.start()
        try:
            logger.info(f"系统划词翻译已启用（{_format_hotkey(self._modifiers, self._vk)}）")
        except Exception:
            logger.info("系统划词翻译已启用")

    def rebind_hotkey(self, modifiers: int, vk: int) -> None:
        """重新绑定全局热键（运行时生效）。"""
        try:
            self.hotkey.stop()
        except Exception:
            pass
        self._modifiers = modifiers
        self._vk = vk
        self.hotkey = GlobalHotkeyListener(modifiers, vk, self._on_hotkey)
        self.hotkey.start()
        try:
            logger.info(f"系统划词翻译热键已更新为：{_format_hotkey(modifiers, vk)}")
        except Exception:
            pass

    def _on_hotkey(self):
        # 将操作转到 Tk 主线程，避免线程间 UI 操作
        self.root.after(0, self._handle_hotkey_mainthread)

    def _handle_hotkey_mainthread(self):
        # 1) 尝试复制选择
        _simulate_ctrl_c()
        # 稍等剪贴板刷新（长文本更保险）
        self.root.after(200, self._read_clipboard_and_translate)

    def _read_clipboard_and_translate(self):
        try:
            text = self.root.clipboard_get()  # 读取剪贴板文本
        except tk.TclError:
            text = ""
        if not text:
            return
        text = text.strip()
        # 放宽长度限制，支持更长文本
        if not text or len(text) < 2 or len(text) > 2000:
            return
        # 简单过滤：若大部分为中文则忽略（与你已有逻辑一致）
        if self._is_mostly_chinese(text):
            return
        # 避免重复
        if text == self._last_text and self._translating:
            return
        self._last_text = text

        # 2) 弹出“翻译中”窗体
        x = self.root.winfo_pointerx() + 12
        y = self.root.winfo_pointery() + 12
        self.popup.show(original=text, x=x, y=y, pending=True)

        # 3) 后台翻译
        if self._translating:
            return
        self._translating = True
        threading.Thread(target=self._translate_bg, args=(text,), daemon=True).start()

    def _translate_bg(self, text: str):
        try:
            # 使用当前平台配置
            from .api import set_current_platform, get_current_platform
            current_api = get_current_translation_api()
            original_platform = get_current_platform()
            set_current_platform(current_api)
            try:
                translated = translate_text(text)
            finally:
                set_current_platform(original_platform)
            if not translated or translated == text:
                translated = "(未获得有效翻译结果)"
            # 回到主线程更新 UI
            self.root.after(0, lambda: self.popup.update_translation(translated))
        except Exception as e:
            logger.error(f"系统划词翻译失败: {e}")
            self.root.after(0, lambda: self.popup.update_translation(f"翻译失败：{e}"))
        finally:
            self._translating = False

    @staticmethod
    def _is_mostly_chinese(text: str) -> bool:
        chinese_chars = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
        return chinese_chars > len(text) * 0.5

    def destroy(self):
        try:
            self.hotkey.stop()
        except Exception:
            pass
        self.popup.hide()


def can_register_hotkey(hotkey_str: str):
    """预检热键是否可注册，返回 (ok, normalized_or_error)。不修改当前绑定、不持久化。
    - ok 为 True 时，normalized_or_error 为规范化后的热键文本（例如 Ctrl+Shift+F）
    - ok 为 False 时，normalized_or_error 为错误原因描述
    """
    try:
        mods, vk = parse_hotkey_string(hotkey_str)
        normalized = _format_hotkey(mods, vk)
    except Exception as e:
        return False, str(e)

    # 尝试通过 Win32 API 临时注册并立即释放，检测是否被占用
    try:
        import ctypes  # 延迟导入，避免非 Windows 环境报错
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    except Exception:
        # 无法进行系统级校验时，放行并交给运行时绑定处理
        return True, normalized

    HOTKEY_ID = 0x6FFF  # 使用一个较大的、与监听线程不同的测试ID
    try:
        if not user32.RegisterHotKey(None, HOTKEY_ID, mods, vk):
            return False, "该组合已被系统或其他程序占用，请更换"
        return True, normalized
    finally:
        try:
            user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass