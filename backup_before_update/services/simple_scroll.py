#!/usr/bin/env python3
"""
简单滚动组件 - 替代虚拟滚动的可靠方案
使用传统的Frame+Scrollbar组合，确保稳定性和兼容性
"""

import tkinter as tk
import customtkinter as ctk
from typing import List, Dict, Callable, Optional
from tkinter import messagebox


class SimpleScrollFrame(ctk.CTkFrame):
    """简单滚动框架
    
    使用传统的Frame+Scrollbar组合，替代复杂的虚拟滚动系统
    适用于中等数量的数据显示（<1000条记录）
    """
    
    def __init__(self, parent: tk.Widget, **kwargs):
        super().__init__(parent, **kwargs)
        
        # 创建画布和滚动条
        self.canvas = tk.Canvas(self, highlightthickness=0, bg='white')
        self.scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # 创建内容框架
        self.content_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        
        # 布局
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # 绑定事件
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.content_frame.bind('<Configure>', self._on_frame_configure)
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        
        # 数据存储
        self.items_data = []
        self.item_widgets = []
        
    def _on_canvas_configure(self, event):
        """画布配置改变事件"""
        # 更新内容框架的宽度以匹配画布
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        
    def _on_frame_configure(self, event):
        """内容框架配置改变事件"""
        # 更新滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def _on_mousewheel(self, event):
        """鼠标滚轮事件"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
    def clear_items(self):
        """清空所有项目"""
        for widget in self.item_widgets:
            widget.destroy()
        self.item_widgets.clear()
        self.items_data.clear()
        
    def add_item(self, item_data: Dict, render_func: Callable[[tk.Widget, Dict], tk.Widget]):
        """添加单个项目"""
        widget = render_func(self.content_frame, item_data)
        if widget:
            widget.pack(fill="x", padx=5, pady=2)
            self.item_widgets.append(widget)
            self.items_data.append(item_data)
            
    def set_items(self, items_data: List[Dict], render_func: Callable[[tk.Widget, Dict], tk.Widget]):
        """设置所有项目"""
        # 清空现有项目
        self.clear_items()
        
        # 添加新项目
        for item_data in items_data:
            self.add_item(item_data, render_func)
            
        # 更新滚动区域
        self.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'total_items': len(self.items_data),
            'rendered_items': len(self.item_widgets),  # 与虚拟滚动保持兼容
            'visible_items': len(self.item_widgets),
            'canvas_height': self.canvas.winfo_height(),
            'content_height': self.content_frame.winfo_reqheight()
        }


class HistorySimpleScrollFrame(SimpleScrollFrame):
    """历史记录简单滚动框架
    
    专门用于历史记录显示的简单滚动组件，支持懒加载优化
    """
    
    def __init__(self, parent: tk.Widget, add_to_favorites_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.add_to_favorites_callback = add_to_favorites_callback
        self.batch_size = 20  # 每批渲染的项目数量
        self.current_batch = 0  # 当前已渲染的批次
        self.all_history_data = []  # 存储所有历史数据
        self.is_loading = False  # 防止重复加载
        
        # 绑定滚动事件以实现懒加载
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        
    def _render_history_item(self, parent: tk.Widget, item_data: Dict) -> tk.Widget:
        """渲染历史记录项目"""
        # 创建历史记录项目框架 - 通栏布局，不扩展避免空白
        item_frame = ctk.CTkFrame(parent)
        item_frame.pack(fill="x", padx=5, pady=2)
        
        # 时间戳
        timestamp = item_data.get('timestamp', '')
        time_label = ctk.CTkLabel(
            item_frame, 
            text=timestamp, 
            font=("微软雅黑", 10),
            text_color="gray"
        )
        time_label.pack(anchor="w", padx=10, pady=(5, 0))
        
        # 输入文本
        input_text = item_data.get('input', '')
        input_label = ctk.CTkLabel(
            item_frame,
            text=f"输入: {input_text}",
            font=("微软雅黑", 11),
            wraplength=700,
            justify="left"
        )
        input_label.pack(anchor="w", padx=10, pady=2)
        
        # 输出文本
        output_text = item_data.get('output', '')
        output_label = ctk.CTkLabel(
            item_frame,
            text=f"输出: {output_text}",
            font=("微软雅黑", 11),
            wraplength=700,
            justify="left",
            text_color="#2E8B57"
        )
        output_label.pack(anchor="w", padx=10, pady=2)
        
        # 操作按钮框架
        button_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        # 复制功能
        def copy_to_clipboard(text):
            try:
                parent.clipboard_clear()
                parent.clipboard_append(text)
                messagebox.showinfo("提示", "已复制到剪贴板")
            except Exception as e:
                messagebox.showerror("错误", f"复制失败: {e}")
        
        # 复制输入按钮 - 改进UI设计
        copy_input_btn = ctk.CTkButton(
            button_frame,
            text="📋 复制输入",
            width=90,
            height=28,
            font=("Microsoft YaHei", 12),
            fg_color=("#3B82F6", "#2563EB"),  # 蓝色主题
            hover_color=("#2563EB", "#1D4ED8"),
            corner_radius=6,
            command=lambda: copy_to_clipboard(input_text)
        )
        copy_input_btn.pack(side="left", padx=(0, 8))
        
        # 复制输出按钮 - 改进UI设计
        copy_output_btn = ctk.CTkButton(
            button_frame,
            text="📄 复制输出",
            width=90,
            height=28,
            font=("Microsoft YaHei", 12),
            fg_color=("#10B981", "#059669"),  # 绿色主题
            hover_color=("#059669", "#047857"),
            corner_radius=6,
            command=lambda: copy_to_clipboard(output_text)
        )
        copy_output_btn.pack(side="left", padx=(0, 8))
        
        # 添加到收藏夹按钮 - 改进UI设计
        if self.add_to_favorites_callback:
            add_fav_btn = ctk.CTkButton(
                button_frame,
                text="⭐ 收藏",
                width=75,
                height=28,
                font=("Microsoft YaHei", 12),
                fg_color=("#F59E0B", "#D97706"),  # 橙色主题
                hover_color=("#D97706", "#B45309"),
                corner_radius=6,
                command=lambda: self.add_to_favorites_callback(item_data)
            )
            add_fav_btn.pack(side="left", padx=(0, 8))
        
        return item_frame
    
    def _on_canvas_configure(self, event):
        """画布配置变化时的处理（先保持父类行为以同步宽度，再做懒加载判断）"""
        try:
            super()._on_canvas_configure(event)  # 同步 content_frame 宽度到画布宽度，避免右侧空白
        except Exception:
            pass
        self._check_need_load_more()
    
    def _on_mousewheel(self, event):
        """鼠标滚轮事件处理（保留父类滚动行为，并在滚动后检查是否需要加载更多）"""
        try:
            super()._on_mousewheel(event)  # 执行实际滚动
        except Exception:
            pass
        # 延迟检查是否需要加载更多
        self.after(100, self._check_need_load_more)
    
    def _check_need_load_more(self):
        """检查是否需要加载更多项目"""
        if self.is_loading or not self.all_history_data:
            return
            
        # 获取当前滚动位置
        try:
            canvas_height = self.canvas.winfo_height()
            content_height = self.content_frame.winfo_reqheight()
            
            if canvas_height <= 0 or content_height <= 0:
                return
                
            # 获取滚动条位置
            scroll_top, scroll_bottom = self.canvas.yview()
            
            # 如果滚动到底部80%，加载更多
            if scroll_bottom > 0.8 and len(self.items_data) < len(self.all_history_data):
                self._load_next_batch()
        except Exception:
            pass  # 忽略配置错误
    
    def _load_next_batch(self):
        """加载下一批数据"""
        if self.is_loading:
            return
            
        self.is_loading = True
        
        try:
            start_idx = len(self.items_data)
            end_idx = min(start_idx + self.batch_size, len(self.all_history_data))
            
            # 批量添加项目
            for i in range(start_idx, end_idx):
                item_data = self.all_history_data[i]
                self.add_item(item_data, self._render_history_item)
            
            # 更新滚动区域
            self.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
        finally:
            self.is_loading = False
        
    def set_history_data(self, history_data: List[Dict], add_to_favorites_callback: Optional[Callable] = None):
        """设置历史记录数据（懒加载版本）"""
        if add_to_favorites_callback:
            self.add_to_favorites_callback = add_to_favorites_callback
            
        # 存储所有数据
        self.all_history_data = history_data
        self.current_batch = 0
        
        # 清空现有项目
        self.clear_items()
        
        # 只加载第一批数据
        if history_data:
            self._load_next_batch()