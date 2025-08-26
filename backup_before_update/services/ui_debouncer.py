"""UI操作防抖机制 - 避免频繁重绘

这个模块实现了多种防抖策略，解决用户快速操作导致的界面卡顿问题：
1. 输入防抖 - 避免输入时频繁触发搜索/过滤
2. 滚动防抖 - 优化滚动时的布局更新
3. 窗口调整防抖 - 避免窗口大小改变时的频繁重绘
4. 按钮点击防抖 - 防止重复点击

遵循Linus的实用主义：解决真实存在的性能问题，而不是理论上的完美。
"""

import tkinter as tk
from typing import Callable, Dict, Any, Optional
import time
from functools import wraps
from services.batch_ui_updater import get_batch_updater


class DebounceManager:
    """防抖管理器
    
    统一管理所有的防抖操作，避免重复的定时器创建。
    """
    
    def __init__(self):
        self.pending_calls: Dict[str, Any] = {}  # 待执行的调用
        self.last_call_times: Dict[str, float] = {}  # 最后调用时间
    
    def debounce_call(self, key: str, func: Callable, delay_ms: int, 
                     *args, **kwargs) -> None:
        """防抖调用函数
        
        Args:
            key: 防抖键，相同键的调用会被合并
            func: 要调用的函数
            delay_ms: 延迟时间（毫秒）
            *args, **kwargs: 函数参数
        """
        current_time = time.time() * 1000
        self.last_call_times[key] = current_time
        
        # 取消之前的调用
        if key in self.pending_calls:
            updater = get_batch_updater()
            if updater.root and self.pending_calls[key]:
                try:
                    updater.root.after_cancel(self.pending_calls[key])
                except:
                    pass
        
        # 调度新的调用
        def delayed_execution():
            # 检查是否是最新的调用
            if (key in self.last_call_times and 
                time.time() * 1000 - self.last_call_times[key] >= delay_ms - 10):
                try:
                    func(*args, **kwargs)
                finally:
                    if key in self.pending_calls:
                        del self.pending_calls[key]
        
        updater = get_batch_updater()
        if updater.root:
            timer_id = updater.root.after(delay_ms, delayed_execution)
            self.pending_calls[key] = timer_id
    
    def cancel_debounce(self, key: str) -> None:
        """取消指定的防抖调用"""
        if key in self.pending_calls:
            updater = get_batch_updater()
            if updater.root and self.pending_calls[key]:
                try:
                    updater.root.after_cancel(self.pending_calls[key])
                except:
                    pass
            del self.pending_calls[key]
    
    def cancel_all(self) -> None:
        """取消所有防抖调用"""
        updater = get_batch_updater()
        if updater.root:
            for timer_id in self.pending_calls.values():
                if timer_id:
                    try:
                        updater.root.after_cancel(timer_id)
                    except:
                        pass
        self.pending_calls.clear()
        self.last_call_times.clear()


# 全局防抖管理器
_debounce_manager = DebounceManager()


def get_debounce_manager() -> DebounceManager:
    """获取全局防抖管理器"""
    return _debounce_manager


class InputDebouncer:
    """输入防抖器
    
    专门处理文本输入、搜索框等的防抖需求。
    """
    
    def __init__(self, delay_ms: int = 300):
        self.delay_ms = delay_ms
        self.debounce_manager = get_debounce_manager()
    
    def __call__(self, delay_ms: int = None) -> Callable:
        """作为装饰器使用"""
        if delay_ms is None:
            delay_ms = self.delay_ms
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 使用函数名作为唯一标识
                key = f"input_{func.__name__}_{id(func)}"
                self.debounce_manager.debounce_call(key, func, delay_ms, *args, **kwargs)
            return wrapper
        return decorator
    
    def debounce_input(self, widget_id: str, callback: Callable, 
                      *args, **kwargs) -> None:
        """防抖输入回调
        
        Args:
            widget_id: 输入控件的唯一标识
            callback: 输入完成后的回调函数
            *args, **kwargs: 回调函数参数
        """
        key = f"input_{widget_id}"
        self.debounce_manager.debounce_call(key, callback, self.delay_ms, 
                                          *args, **kwargs)
    
    def bind_to_entry(self, entry_widget: tk.Entry, callback: Callable,
                     widget_id: Optional[str] = None) -> None:
        """绑定到Entry控件
        
        Args:
            entry_widget: Entry控件
            callback: 输入完成后的回调函数
            widget_id: 控件ID，如果不提供则自动生成
        """
        if widget_id is None:
            widget_id = str(id(entry_widget))
        
        def on_key_release(event):
            text = entry_widget.get()
            self.debounce_input(widget_id, callback, text)
        
        entry_widget.bind('<KeyRelease>', on_key_release)
    
    def bind_to_text(self, text_widget: tk.Text, callback: Callable,
                    widget_id: Optional[str] = None) -> None:
        """绑定到Text控件"""
        if widget_id is None:
            widget_id = str(id(text_widget))
        
        def on_key_release(event):
            text = text_widget.get('1.0', tk.END)
            self.debounce_input(widget_id, callback, text)
        
        text_widget.bind('<KeyRelease>', on_key_release)


class ScrollDebouncer:
    """滚动防抖器
    
    优化滚动时的布局更新和重绘操作。
    """
    
    def __init__(self, delay_ms: int = 50):
        self.delay_ms = delay_ms
        self.debounce_manager = get_debounce_manager()
    
    def __call__(self, delay_ms: int = None) -> Callable:
        """作为装饰器使用"""
        if delay_ms is None:
            delay_ms = self.delay_ms
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 使用函数名作为唯一标识
                key = f"scroll_{func.__name__}_{id(func)}"
                self.debounce_manager.debounce_call(key, func, delay_ms, *args, **kwargs)
            return wrapper
        return decorator
    
    def debounce_scroll(self, canvas_id: str, callback: Callable,
                       *args, **kwargs) -> None:
        """防抖滚动回调"""
        key = f"scroll_{canvas_id}"
        self.debounce_manager.debounce_call(key, callback, self.delay_ms,
                                          *args, **kwargs)
    
    def bind_to_canvas(self, canvas: tk.Canvas, callback: Callable,
                      canvas_id: Optional[str] = None) -> None:
        """绑定到Canvas控件的滚动事件"""
        if canvas_id is None:
            canvas_id = str(id(canvas))
        
        def on_scroll(event):
            self.debounce_scroll(canvas_id, callback, event)
        
        # 绑定多种滚动事件
        canvas.bind('<MouseWheel>', on_scroll)
        canvas.bind('<Button-4>', on_scroll)
        canvas.bind('<Button-5>', on_scroll)
    
    def bind_to_scrollbar(self, scrollbar: tk.Scrollbar, callback: Callable,
                         scrollbar_id: Optional[str] = None) -> None:
        """绑定到Scrollbar控件"""
        if scrollbar_id is None:
            scrollbar_id = str(id(scrollbar))
        
        def on_scroll(*args):
            self.debounce_scroll(scrollbar_id, callback, *args)
        
        scrollbar.configure(command=on_scroll)


class ResizeDebouncer:
    """窗口调整防抖器
    
    避免窗口大小改变时的频繁重绘。
    """
    
    def __init__(self, delay_ms: int = 100):
        self.delay_ms = delay_ms
        self.debounce_manager = get_debounce_manager()
    
    def __call__(self, delay_ms: int = None) -> Callable:
        """作为装饰器使用"""
        if delay_ms is None:
            delay_ms = self.delay_ms
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 使用函数名作为唯一标识
                key = f"resize_{func.__name__}_{id(func)}"
                self.debounce_manager.debounce_call(key, func, delay_ms, *args, **kwargs)
            return wrapper
        return decorator
    
    def debounce_resize(self, widget_id: str, callback: Callable,
                       *args, **kwargs) -> None:
        """防抖窗口调整回调"""
        key = f"resize_{widget_id}"
        self.debounce_manager.debounce_call(key, callback, self.delay_ms,
                                          *args, **kwargs)
    
    def bind_to_widget(self, widget: tk.Widget, callback: Callable,
                      widget_id: Optional[str] = None) -> None:
        """绑定到任意控件的Configure事件"""
        if widget_id is None:
            widget_id = str(id(widget))
        
        def on_configure(event):
            if event.widget == widget:  # 确保是目标控件的事件
                self.debounce_resize(widget_id, callback, event)
        
        widget.bind('<Configure>', on_configure)


class ClickDebouncer:
    """点击防抖器
    
    防止按钮重复点击导致的重复操作。
    """
    
    def __init__(self, delay_ms: int = 500):
        self.delay_ms = delay_ms
        self.last_click_times: Dict[str, float] = {}
    
    def __call__(self, delay_ms: int = None) -> Callable:
        """作为装饰器使用"""
        if delay_ms is None:
            delay_ms = self.delay_ms
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 使用函数名作为唯一标识
                key = f"click_{func.__name__}_{id(func)}"
                if self.is_click_allowed(key):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def is_click_allowed(self, button_id: str) -> bool:
        """检查点击是否被允许"""
        current_time = time.time() * 1000
        last_time = self.last_click_times.get(button_id, 0)
        
        if current_time - last_time >= self.delay_ms:
            self.last_click_times[button_id] = current_time
            return True
        return False
    
    def debounced_click(self, button_id: str, callback: Callable,
                       *args, **kwargs) -> None:
        """防抖点击处理"""
        if self.is_click_allowed(button_id):
            callback(*args, **kwargs)
    
    def bind_to_button(self, button: tk.Button, callback: Callable,
                      button_id: Optional[str] = None) -> None:
        """绑定到Button控件"""
        if button_id is None:
            button_id = str(id(button))
        
        def on_click():
            self.debounced_click(button_id, callback)
        
        button.configure(command=on_click)


# 装饰器实现
def debounce_input(delay_ms: int = 300, widget_id_func: Optional[Callable] = None):
    """输入防抖装饰器
    
    Args:
        delay_ms: 延迟时间
        widget_id_func: 获取widget_id的函数，接收被装饰函数的参数
    """
    def decorator(func: Callable) -> Callable:
        debouncer = InputDebouncer(delay_ms)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if widget_id_func:
                widget_id = widget_id_func(*args, **kwargs)
            else:
                widget_id = func.__name__
            
            debouncer.debounce_input(widget_id, func, *args, **kwargs)
        
        return wrapper
    return decorator


def debounce_scroll(delay_ms: int = 50, canvas_id_func: Optional[Callable] = None):
    """滚动防抖装饰器"""
    def decorator(func: Callable) -> Callable:
        debouncer = ScrollDebouncer(delay_ms)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if canvas_id_func:
                canvas_id = canvas_id_func(*args, **kwargs)
            else:
                canvas_id = func.__name__
            
            debouncer.debounce_scroll(canvas_id, func, *args, **kwargs)
        
        return wrapper
    return decorator


def debounce_resize(delay_ms: int = 100, widget_id_func: Optional[Callable] = None):
    """窗口调整防抖装饰器"""
    def decorator(func: Callable) -> Callable:
        debouncer = ResizeDebouncer(delay_ms)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if widget_id_func:
                widget_id = widget_id_func(*args, **kwargs)
            else:
                widget_id = func.__name__
            
            debouncer.debounce_resize(widget_id, func, *args, **kwargs)
        
        return wrapper
    return decorator


def debounce_click(delay_ms: int = 500, button_id_func: Optional[Callable] = None):
    """点击防抖装饰器"""
    def decorator(func: Callable) -> Callable:
        debouncer = ClickDebouncer(delay_ms)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if button_id_func:
                button_id = button_id_func(*args, **kwargs)
            else:
                button_id = func.__name__
            
            debouncer.debounced_click(button_id, func, *args, **kwargs)
        
        return wrapper
    return decorator


# 全局防抖器实例
input_debouncer = InputDebouncer()
scroll_debouncer = ScrollDebouncer()
resize_debouncer = ResizeDebouncer()
click_debouncer = ClickDebouncer()


def setup_ui_debouncing(root: tk.Tk) -> None:
    """为应用程序设置UI防抖
    
    这个函数应该在应用启动时调用，为全局UI操作设置防抖。
    """
    # 设置批量更新器的root
    updater = get_batch_updater(root)
    
    # 可以在这里添加全局的防抖设置
    # 例如：为所有Entry控件自动添加防抖
    
    def auto_debounce_entries(widget):
        """自动为Entry控件添加防抖"""
        if isinstance(widget, tk.Entry):
            input_debouncer.bind_to_entry(widget, lambda text: None)
        
        # 递归处理子控件
        for child in widget.winfo_children():
            auto_debounce_entries(child)
    
    # 延迟执行，确保所有控件都已创建
    root.after(1000, lambda: auto_debounce_entries(root))