"""虚拟滚动组件 - 支持大量标签的高效显示

这个模块实现了虚拟滚动技术，只渲染可见区域的标签，解决大量标签时的性能问题：
1. 只创建可见区域的DOM元素
2. 动态回收和复用不可见的元素
3. 智能预加载缓冲区
4. 支持不同高度的项目

遵循Linus的"好品味"原则：用简单的数据结构解决复杂问题。
"""

import tkinter as tk
from typing import List, Dict, Callable, Optional, Any, Tuple
import math
import os
from services.batch_ui_updater import get_batch_updater, batch_ui_update
from services.ui_debouncer import ScrollDebouncer

# 全局防抖器实例
scroll_debouncer = ScrollDebouncer()


class VirtualScrollItem:
    """虚拟滚动项目
    
    表示一个可以被虚拟滚动的项目。
    """
    
    def __init__(self, data: Any, height: int = None, key: str = None):
        self.data = data
        self.height = height or 100  # 默认高度
        self.key = key or str(id(data))
        self.y_position = 0  # 在虚拟空间中的Y位置
        self.widget: Optional[tk.Widget] = None  # 对应的UI控件
        self.is_visible = False  # 是否当前可见


class VirtualScrollContainer:
    """虚拟滚动容器
    
    管理大量项目的虚拟滚动显示。
    """
    
    def __init__(self, canvas: tk.Canvas, frame: tk.Frame, 
                 item_renderer: Callable[[tk.Widget, Any], tk.Widget]):
        self.canvas = canvas
        self.frame = frame
        self.item_renderer = item_renderer  # 项目渲染函数
        
        # 虚拟滚动参数
        self.items: List[VirtualScrollItem] = []
        self.visible_items: Dict[str, VirtualScrollItem] = {}  # 当前可见的项目
        self.item_pool: List[tk.Widget] = []  # 控件对象池，用于复用
        
        # 滚动参数
        self.viewport_height = 0
        self.total_height = 0
        self.scroll_top = 0
        self.buffer_size = 5  # 缓冲区大小（上下各多渲染几个项目）
        
        # 性能优化参数
        self.estimated_item_height = 100  # 估算的项目高度
        self.measured_heights: Dict[str, int] = {}  # 实际测量的高度
        
        # 绑定事件
        self._setup_events()
    
    def _setup_events(self) -> None:
        """设置滚动事件"""
        # 绑定滚动事件
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        
        # 绑定键盘滚动
        self.canvas.bind('<Up>', lambda e: self._scroll_by(-50))
        self.canvas.bind('<Down>', lambda e: self._scroll_by(50))
        self.canvas.bind('<Prior>', lambda e: self._scroll_by(-self.viewport_height))
        self.canvas.bind('<Next>', lambda e: self._scroll_by(self.viewport_height))
        
        # 确保canvas可以获得焦点
        self.canvas.focus_set()
    
    def set_items(self, items_data: List[Any], 
                  height_calculator: Optional[Callable[[Any], int]] = None) -> None:
        """设置要显示的项目数据
        
        Args:
            items_data: 项目数据列表
            height_calculator: 高度计算函数，如果不提供则使用默认高度
        """
        # 清理现有项目
        self._clear_all_items()
        
        # 创建新的虚拟项目
        self.items = []
        y_position = 0
        
        for i, data in enumerate(items_data):
            height = (height_calculator(data) if height_calculator 
                     else self.estimated_item_height)
            
            item = VirtualScrollItem(
                data=data,
                height=height,
                key=f"item_{i}"
            )
            item.y_position = y_position
            
            self.items.append(item)
            y_position += height
        
        self.total_height = y_position
        self._update_scrollregion()
        self._update_visible_items()
    
    def _clear_all_items(self) -> None:
        """清理所有项目"""
        # 销毁所有可见的控件
        for item in self.visible_items.values():
            if item.widget:
                item.widget.destroy()
        
        # 清理对象池
        for widget in self.item_pool:
            widget.destroy()
        
        self.visible_items.clear()
        self.item_pool.clear()
        self.items.clear()
    
    def _get_widget_from_pool(self) -> Optional[tk.Widget]:
        """从对象池获取控件"""
        if self.item_pool:
            return self.item_pool.pop()
        return None
    
    def _return_widget_to_pool(self, widget: tk.Widget) -> None:
        """将控件返回对象池"""
        if widget and len(self.item_pool) < 50:  # 限制对象池大小
            # 隐藏控件但不销毁
            widget.place_forget()
            self.item_pool.append(widget)
        elif widget:
            widget.destroy()
    
    def _update_visible_items(self) -> None:
        """更新可见项目（带防抖）"""
        # 使用防抖机制避免频繁更新
        scroll_debouncer.debounce_scroll(
            f"virtual_scroll_{id(self)}", 
            self._do_update_visible_items
        )
    
    def _do_update_visible_items(self) -> None:
        """实际执行可见项目更新"""
        if not self.items:
            return
        
        # 计算可见范围
        visible_start, visible_end = self._calculate_visible_range()
        
        # 获取需要显示的项目
        items_to_show = set()
        for i in range(visible_start, visible_end):
            if 0 <= i < len(self.items):
                items_to_show.add(self.items[i].key)
        
        # 移除不再可见的项目
        items_to_remove = []
        for key in self.visible_items:
            if key not in items_to_show:
                items_to_remove.append(key)
        
        for key in items_to_remove:
            item = self.visible_items.pop(key)
            if item.widget:
                self._return_widget_to_pool(item.widget)
                item.widget = None
            item.is_visible = False
        
        # 添加新的可见项目
        for i in range(visible_start, visible_end):
            if 0 <= i < len(self.items):
                item = self.items[i]
                if item.key not in self.visible_items:
                    self._create_visible_item(item)
    
    def _calculate_visible_range(self) -> Tuple[int, int]:
        """计算可见项目的范围"""
        if not self.items or self.viewport_height <= 0:
            return 0, 0
        
        # 计算可见区域的Y范围
        viewport_top = self.scroll_top
        viewport_bottom = viewport_top + self.viewport_height
        
        # 添加缓冲区
        buffer_height = self.buffer_size * self.estimated_item_height
        viewport_top = max(0, viewport_top - buffer_height)
        viewport_bottom = min(self.total_height, viewport_bottom + buffer_height)
        
        # 二分查找可见项目的起始和结束索引
        start_index = self._find_item_at_position(viewport_top)
        end_index = self._find_item_at_position(viewport_bottom) + 1
        
        return start_index, min(end_index, len(self.items))
    
    def _find_item_at_position(self, y_position: float) -> int:
        """二分查找指定Y位置对应的项目索引"""
        if not self.items:
            return 0
        
        left, right = 0, len(self.items) - 1
        
        while left <= right:
            mid = (left + right) // 2
            item = self.items[mid]
            
            if item.y_position <= y_position < item.y_position + item.height:
                return mid
            elif item.y_position > y_position:
                right = mid - 1
            else:
                left = mid + 1
        
        return min(left, len(self.items) - 1)
    
    def _create_visible_item(self, item: VirtualScrollItem) -> None:
        """创建可见项目的UI控件"""
        # 总是创建新控件，因为历史记录项目结构复杂
        widget = self.item_renderer(self.frame, item.data)
        
        if widget:
            # 计算相对于滚动位置的Y坐标
            relative_y = item.y_position - self.scroll_top
            
            # 放置控件 - customtkinter不支持place的width参数
            widget.place(x=0, y=relative_y)
            
            # 更新项目信息
            item.widget = widget
            item.is_visible = True
            self.visible_items[item.key] = item
            
            # 测量实际高度（如果需要）
            self._measure_item_height(item)
    
    def _measure_item_height(self, item: VirtualScrollItem) -> None:
        """测量项目的实际高度"""
        if item.widget and item.key not in self.measured_heights:
            # 延迟测量，等待控件完全渲染
            def measure_height():
                try:
                    actual_height = item.widget.winfo_reqheight()
                    if actual_height > 0 and actual_height != item.height:
                        self.measured_heights[item.key] = actual_height
                        # 可以在这里触发重新布局，但为了性能考虑暂时跳过
                except:
                    pass
            
            self.canvas.after_idle(measure_height)
    
    def _on_canvas_configure(self, event) -> None:
        """画布配置改变事件"""
        if event.widget == self.canvas:
            new_height = event.height
            if new_height != self.viewport_height:
                self.viewport_height = new_height
                self._update_visible_items()
    
    def _on_mousewheel(self, event) -> None:
        """鼠标滚轮事件"""
        # 计算滚动距离
        delta = -event.delta if hasattr(event, 'delta') else -event.num * 40
        self._scroll_by(delta)
    
    def _scroll_by(self, delta: int) -> None:
        """滚动指定距离"""
        new_scroll_top = max(0, min(self.scroll_top + delta, 
                                   self.total_height - self.viewport_height))
        
        if new_scroll_top != self.scroll_top:
            self.scroll_top = new_scroll_top
            self._update_scroll_position()
            self._update_visible_items()
    
    def _update_scroll_position(self) -> None:
        """更新滚动条位置"""
        if self.total_height > 0:
            # 更新画布滚动区域
            self.canvas.configure(scrollregion=(0, 0, 0, self.total_height))
            
            # 计算滚动比例
            scroll_fraction = self.scroll_top / max(1, self.total_height - self.viewport_height)
            
            # 更新所有可见控件的位置
            for item in self.visible_items.values():
                if item.widget:
                    relative_y = item.y_position - self.scroll_top
                    item.widget.place(y=relative_y)
    
    def _update_scrollregion(self) -> None:
        """更新滚动区域"""
        self.canvas.configure(scrollregion=(0, 0, 0, self.total_height))
    
    def scroll_to_item(self, item_index: int) -> None:
        """滚动到指定项目"""
        if 0 <= item_index < len(self.items):
            target_y = self.items[item_index].y_position
            # 滚动到项目顶部
            self.scroll_top = max(0, min(target_y, self.total_height - self.viewport_height))
            self._update_scroll_position()
            self._update_visible_items()
    
    def get_visible_item_count(self) -> int:
        """获取当前可见项目数量"""
        return len(self.visible_items)
    
    def get_total_item_count(self) -> int:
        """获取总项目数量"""
        return len(self.items)
    
    def refresh(self) -> None:
        """刷新显示"""
        self._update_visible_items()


class VirtualTagScrollContainer(VirtualScrollContainer):
    """专门用于标签的虚拟滚动容器
    
    针对MJ Translator的标签显示进行了优化。
    """
    
    def __init__(self, canvas: tk.Canvas, frame: tk.Frame, 
                 tag_renderer: Callable[[tk.Widget, Dict], tk.Widget],
                 insert_tag_callback: Callable[[str, str], None]):
        self.tag_renderer = tag_renderer
        self.insert_tag_callback = insert_tag_callback
        
        # 标签特定的渲染函数
        def item_renderer(parent, tag_data):
            return self._render_tag_item(parent, tag_data)
        
        super().__init__(canvas, frame, item_renderer)
        
        # 标签特定参数
        self.estimated_item_height = 80  # 标签的估算高度
    
    def _render_tag_item(self, parent: tk.Widget, tag_data: Dict) -> tk.Widget:
        """渲染标签项目"""
        label = tag_data.get('label', '')
        tag_entry = tag_data.get('entry', {})
        is_selected = tag_data.get('is_selected', False)
        tag_type = tag_data.get('tag_type', '')
        
        # 使用原有的标签渲染逻辑
        return self.tag_renderer(parent, label, tag_entry, is_selected,
                               lambda: self.insert_tag_callback(tag_type, label))
    
    def set_tags(self, tags: Dict, inserted_tags: Dict, tag_type: str) -> None:
        """设置要显示的标签
        
        Args:
            tags: 标签字典
            inserted_tags: 已插入的标签
            tag_type: 标签类型
        """
        # 转换标签数据为虚拟滚动项目格式
        items_data = []
        for label, tag_entry in tags.items():
            is_selected = label in inserted_tags.get(tag_type, [])
            
            item_data = {
                'label': label,
                'entry': tag_entry,
                'is_selected': is_selected,
                'tag_type': tag_type
            }
            items_data.append(item_data)
        
        # 设置项目
        self.set_items(items_data, self._calculate_tag_height)
    
    def _calculate_tag_height(self, tag_data: Dict) -> int:
        """计算标签高度"""
        label = tag_data.get('label', '')
        tag_entry = tag_data.get('entry', {})
        
        # 检查是否有图片
        has_image = (isinstance(tag_entry, dict) and 
                    tag_entry.get("image", "") and 
                    os.path.exists(tag_entry.get("image", "")))
        
        if has_image:
            return 120  # 有图片的标签高度
        else:
            # 根据文本长度估算
            text_lines = max(2, len(label) // 20)
            return 60 + (text_lines - 2) * 20


class HistoryVirtualScrollFrame(tk.Frame):
    """历史记录虚拟滚动框架
    
    专门用于历史记录显示的虚拟滚动组件，集成了画布、滚动条和虚拟滚动容器。
    """
    
    def __init__(self, parent: tk.Widget, add_to_favorites_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.add_to_favorites_callback = add_to_favorites_callback
        
        # 创建画布和滚动条
        self.canvas = tk.Canvas(self, highlightthickness=0, bg='white')
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # 创建内容框架
        self.content_frame = tk.Frame(self.canvas, bg='white')
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        
        # 布局
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # 创建虚拟滚动容器
        self.virtual_container = VirtualScrollContainer(
            self.canvas, 
            self.content_frame, 
            self._render_history_item
        )
        
        # 历史记录数据
        self.history_data = []
        
        # 绑定画布配置事件
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.content_frame.bind('<Configure>', self._on_frame_configure)
        
        # 初始化视口高度
        self.after(100, self._initialize_viewport)
    
    def _render_history_item(self, parent: tk.Widget, item_data: Dict) -> tk.Widget:
        """渲染历史记录项目"""
        import customtkinter as ctk
        from tkinter import messagebox
        
        # 创建历史记录项目框架 - 设置明确的尺寸
        item_frame = ctk.CTkFrame(parent, width=780, height=120)
        # 不使用pack，因为虚拟滚动使用place布局
        
        # 时间戳
        timestamp = item_data.get('timestamp', '')
        time_label = ctk.CTkLabel(
            item_frame, 
            text=timestamp, 
            font=("微软雅黑", 10),
            text_color="gray"
        )
        time_label.place(x=10, y=5)
        
        # 输入文本
        input_text = item_data.get('input', '')
        input_label = ctk.CTkLabel(
            item_frame,
            text=f"输入: {input_text}",
            font=("微软雅黑", 11),
            wraplength=700,
            justify="left"
        )
        input_label.place(x=10, y=25)
        
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
        output_label.place(x=10, y=55)
        
        # 操作按钮 - 使用place布局
        def copy_to_clipboard(text):
            try:
                parent.clipboard_clear()
                parent.clipboard_append(text)
                messagebox.showinfo("提示", "已复制到剪贴板")
            except Exception as e:
                messagebox.showerror("错误", f"复制失败: {e}")
        
        # 复制输入按钮
        copy_input_btn = ctk.CTkButton(
            item_frame,
            text="复制输入",
            width=80,
            height=25,
            font=("微软雅黑", 10),
            command=lambda: copy_to_clipboard(input_text)
        )
        copy_input_btn.place(x=10, y=85)
        
        # 复制输出按钮
        copy_output_btn = ctk.CTkButton(
            item_frame,
            text="复制输出",
            width=80,
            height=25,
            font=("微软雅黑", 10),
            command=lambda: copy_to_clipboard(output_text)
        )
        copy_output_btn.place(x=95, y=85)
        
        # 添加到收藏夹按钮
        if self.add_to_favorites_callback:
            add_fav_btn = ctk.CTkButton(
                item_frame,
                text="收藏",
                width=60,
                height=25,
                font=("微软雅黑", 10),
                command=lambda: self.add_to_favorites_callback(item_data)
            )
            add_fav_btn.place(x=180, y=85)
        
        return item_frame
    
    def set_history_data(self, history_data: List[Dict], add_to_favorites_callback: Optional[Callable] = None):
        """设置历史记录数据"""
        self.history_data = history_data
        if add_to_favorites_callback:
            self.add_to_favorites_callback = add_to_favorites_callback
        
        # 设置虚拟滚动数据
        self.virtual_container.set_items(history_data, self._calculate_item_height)
    
    def _calculate_item_height(self, item_data: Dict) -> int:
        """计算历史记录项目高度"""
        input_text = item_data.get('input', '')
        output_text = item_data.get('output', '')
        
        # 基础高度
        base_height = 100
        
        # 根据文本长度估算额外高度
        input_lines = max(1, len(input_text) // 50)
        output_lines = max(1, len(output_text) // 50)
        
        extra_height = (input_lines + output_lines - 2) * 20
        
        return base_height + extra_height
    
    def _on_canvas_configure(self, event):
        """画布配置改变事件"""
        # 更新内容框架的宽度
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        
        # 更新虚拟滚动容器的视口信息
        self.virtual_container.viewport_height = event.height
        # 画布配置改变时直接更新，避免防抖延迟
        self.virtual_container._do_update_visible_items()
    
    def _on_frame_configure(self, event):
        """内容框架配置改变事件"""
        # 更新滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _initialize_viewport(self):
        """初始化视口高度"""
        # 强制更新画布尺寸
        self.update_idletasks()
        
        # 设置虚拟容器的视口高度
        canvas_height = self.canvas.winfo_height()
        canvas_width = self.canvas.winfo_width()
        
        print(f"[DEBUG] _initialize_viewport: canvas_height={canvas_height}, canvas_width={canvas_width}")
        
        if canvas_height > 1 and canvas_width > 1:  # 确保画布已经正确渲染
            self.virtual_container.viewport_height = canvas_height
            print(f"[DEBUG] 设置视口高度: {canvas_height}")
            # 初始化时直接调用_do_update_visible_items，避免防抖延迟
            self.virtual_container._do_update_visible_items()
            print(f"[DEBUG] 初始化后可见项目数: {len(self.virtual_container.visible_items)}")
        else:
            # 如果还没有正确的高度，最多重试10次
            if not hasattr(self, '_init_retry_count'):
                self._init_retry_count = 0
            
            self._init_retry_count += 1
            if self._init_retry_count < 10:
                print(f"[DEBUG] 画布尺寸未就绪，重试第{self._init_retry_count}次")
                self.after(100, self._initialize_viewport)
            else:
                # 强制设置一个默认高度
                print(f"[DEBUG] 重试次数已达上限，使用默认高度600")
                self.virtual_container.viewport_height = 600
                self.virtual_container._do_update_visible_items()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'total_items': len(self.history_data),
            'rendered_items': self.virtual_container.get_visible_item_count()
        }


def create_virtual_scroll_canvas(parent: tk.Widget, height: int = 400) -> Tuple[tk.Canvas, VirtualScrollContainer]:
    """创建虚拟滚动画布
    
    Args:
        parent: 父控件
        height: 画布高度
    
    Returns:
        (canvas, virtual_container): 画布和虚拟滚动容器
    """
    # 创建画布和滚动条
    canvas = tk.Canvas(parent, height=height, highlightthickness=0)
    scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # 创建内部frame
    frame = tk.Frame(canvas)
    canvas.create_window((0, 0), window=frame, anchor="nw")
    
    # 布局
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # 创建虚拟滚动容器
    def default_renderer(parent, data):
        return tk.Label(parent, text=str(data))
    
    virtual_container = VirtualScrollContainer(canvas, frame, default_renderer)
    
    return canvas, virtual_container