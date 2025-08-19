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
        self.tooltip_window.wm_attributes("-alpha", 0.95)
        
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