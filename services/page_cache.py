"""页面缓存管理 - 优化页面切换性能

这个模块实现了页面状态缓存和智能预加载，解决页面切换时的卡顿问题：
1. 缓存页面UI组件状态，避免重复创建
2. 智能预加载即将访问的页面
3. 内存管理，防止缓存过多导致内存泄漏
4. 页面切换动画优化

遵循Linus的"Never break userspace"原则：确保缓存不影响用户数据。
"""

import tkinter as tk
from typing import Dict, Any, Optional, Callable, List, Tuple
import weakref
import gc
import threading
import time
from services.batch_ui_updater import get_batch_updater, batch_ui_update
from services.ui_debouncer import get_debounce_manager


class PageState:
    """页面状态封装
    
    保存页面的UI状态和数据状态。
    """
    
    def __init__(self, page_id: str, widget: tk.Widget = None, 
                 data: Dict[str, Any] = None, scroll_position: float = 0.0):
        self.page_id = page_id
        self.widget = widget  # 页面的根控件
        self.data = data or {}  # 页面数据
        self.scroll_position = scroll_position  # 滚动位置
        self.last_access_time = time.time()  # 最后访问时间
        self.is_dirty = False  # 数据是否已修改
        self.creation_time = time.time()  # 创建时间
        
        # UI组件状态
        self.ui_state = {
            'focus_widget': None,  # 当前焦点控件
            'selection_state': {},  # 选择状态
            'form_data': {},  # 表单数据
            'expanded_items': set(),  # 展开的项目
        }
    
    def update_access_time(self) -> None:
        """更新访问时间"""
        self.last_access_time = time.time()
    
    def mark_dirty(self) -> None:
        """标记为已修改"""
        self.is_dirty = True
    
    def mark_clean(self) -> None:
        """标记为未修改"""
        self.is_dirty = False
    
    def get_age(self) -> float:
        """获取页面年龄（秒）"""
        return time.time() - self.last_access_time
    
    def save_ui_state(self, widget: tk.Widget) -> None:
        """保存UI状态"""
        try:
            # 保存焦点
            self.ui_state['focus_widget'] = widget.focus_get()
            
            # 保存滚动位置（如果是Canvas或Text）
            if hasattr(widget, 'canvasy'):
                try:
                    self.scroll_position = widget.canvasy(0)
                except:
                    pass
            elif hasattr(widget, 'yview'):
                try:
                    self.scroll_position = widget.yview()[0]
                except:
                    pass
        except Exception as e:
            print(f"保存UI状态失败: {e}")
    
    def restore_ui_state(self, widget: tk.Widget) -> None:
        """恢复UI状态"""
        try:
            # 恢复滚动位置
            if hasattr(widget, 'yview_moveto') and self.scroll_position > 0:
                widget.after_idle(lambda: widget.yview_moveto(self.scroll_position))
            
            # 恢复焦点（延迟执行，确保控件已完全创建）
            focus_widget = self.ui_state.get('focus_widget')
            if focus_widget and hasattr(focus_widget, 'focus_set'):
                widget.after_idle(lambda: focus_widget.focus_set())
        except Exception as e:
            print(f"恢复UI状态失败: {e}")


class PageCache:
    """页面缓存管理器
    
    管理页面的缓存、预加载和内存清理。
    """
    
    def __init__(self, max_cache_size: int = 10, max_age_seconds: int = 300):
        self.max_cache_size = max_cache_size  # 最大缓存页面数
        self.max_age_seconds = max_age_seconds  # 最大缓存时间（秒）
        
        # 缓存存储
        self.cache: Dict[str, PageState] = {}
        self.access_order: List[str] = []  # LRU访问顺序
        
        # 预加载管理
        self.preload_queue: List[str] = []  # 预加载队列
        self.preload_callbacks: Dict[str, Callable] = {}  # 预加载回调
        self.is_preloading = False
        
        # 内存管理
        self._cleanup_thread = None
        self._stop_cleanup = False
        self._start_cleanup_thread()
        
        # 性能统计
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'preload_hits': 0,
            'pages_evicted': 0,
            'memory_cleanups': 0
        }
    
    def _start_cleanup_thread(self) -> None:
        """启动清理线程"""
        def cleanup_worker():
            while not self._stop_cleanup:
                try:
                    self._cleanup_expired_pages()
                    time.sleep(30)  # 每30秒清理一次
                except Exception as e:
                    print(f"缓存清理线程错误: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def get_page(self, page_id: str) -> Optional[PageState]:
        """获取缓存的页面
        
        Args:
            page_id: 页面ID
            
        Returns:
            PageState或None
        """
        if page_id in self.cache:
            page_state = self.cache[page_id]
            page_state.update_access_time()
            
            # 更新LRU顺序
            if page_id in self.access_order:
                self.access_order.remove(page_id)
            self.access_order.append(page_id)
            
            self.stats['cache_hits'] += 1
            return page_state
        
        self.stats['cache_misses'] += 1
        return None
    
    def cache_page(self, page_id: str, widget: tk.Widget, 
                   data: Dict[str, Any] = None) -> PageState:
        """缓存页面
        
        Args:
            page_id: 页面ID
            widget: 页面根控件
            data: 页面数据
            
        Returns:
            PageState: 创建的页面状态
        """
        # 如果已存在，更新现有缓存
        if page_id in self.cache:
            page_state = self.cache[page_id]
            page_state.widget = widget
            if data:
                page_state.data.update(data)
            page_state.update_access_time()
            return page_state
        
        # 创建新的页面状态
        page_state = PageState(page_id, widget, data)
        
        # 检查缓存大小限制
        if len(self.cache) >= self.max_cache_size:
            self._evict_oldest_page()
        
        # 添加到缓存
        self.cache[page_id] = page_state
        self.access_order.append(page_id)
        
        return page_state
    
    def remove_page(self, page_id: str) -> bool:
        """移除页面缓存
        
        Args:
            page_id: 页面ID
            
        Returns:
            bool: 是否成功移除
        """
        if page_id in self.cache:
            page_state = self.cache.pop(page_id)
            
            # 清理UI控件
            if page_state.widget:
                try:
                    page_state.widget.destroy()
                except:
                    pass
            
            # 从访问顺序中移除
            if page_id in self.access_order:
                self.access_order.remove(page_id)
            
            return True
        return False
    
    def _evict_oldest_page(self) -> None:
        """驱逐最旧的页面"""
        if not self.access_order:
            return
        
        # 找到最旧的页面（LRU）
        oldest_page_id = self.access_order[0]
        
        # 检查是否有脏数据需要保存
        if oldest_page_id in self.cache:
            page_state = self.cache[oldest_page_id]
            if page_state.is_dirty:
                # 这里可以添加保存逻辑
                print(f"警告：驱逐包含未保存数据的页面: {oldest_page_id}")
        
        self.remove_page(oldest_page_id)
        self.stats['pages_evicted'] += 1
    
    def _cleanup_expired_pages(self) -> None:
        """清理过期页面"""
        current_time = time.time()
        expired_pages = []
        
        for page_id, page_state in self.cache.items():
            if page_state.get_age() > self.max_age_seconds:
                expired_pages.append(page_id)
        
        for page_id in expired_pages:
            self.remove_page(page_id)
        
        if expired_pages:
            self.stats['memory_cleanups'] += 1
            # 强制垃圾回收
            gc.collect()
    
    def preload_page(self, page_id: str, 
                     preload_callback: Callable[[], Tuple[tk.Widget, Dict]]) -> None:
        """预加载页面
        
        Args:
            page_id: 页面ID
            preload_callback: 预加载回调函数，返回(widget, data)
        """
        if page_id not in self.cache and page_id not in self.preload_queue:
            self.preload_queue.append(page_id)
            self.preload_callbacks[page_id] = preload_callback
            
            # 异步执行预加载
            self._execute_preload()
    
    def _execute_preload(self) -> None:
        """执行预加载"""
        if self.is_preloading or not self.preload_queue:
            return
        
        def preload_worker():
            self.is_preloading = True
            try:
                while self.preload_queue:
                    page_id = self.preload_queue.pop(0)
                    callback = self.preload_callbacks.pop(page_id, None)
                    
                    if callback and page_id not in self.cache:
                        try:
                            widget, data = callback()
                            if widget:
                                self.cache_page(page_id, widget, data)
                                self.stats['preload_hits'] += 1
                        except Exception as e:
                            print(f"预加载页面 {page_id} 失败: {e}")
                    
                    # 避免阻塞主线程
                    time.sleep(0.1)
            finally:
                self.is_preloading = False
        
        # 在后台线程执行预加载
        threading.Thread(target=preload_worker, daemon=True).start()
    
    def clear_cache(self) -> None:
        """清空所有缓存"""
        for page_id in list(self.cache.keys()):
            self.remove_page(page_id)
        
        self.preload_queue.clear()
        self.preload_callbacks.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'cached_pages': len(self.cache),
            'hit_rate_percent': round(hit_rate, 2),
            'preload_queue_size': len(self.preload_queue)
        }
    
    def __del__(self):
        """析构函数"""
        self._stop_cleanup = True
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=1)
        self.clear_cache()


class PageTransitionManager:
    """页面切换管理器
    
    管理页面切换动画和性能优化。
    """
    
    def __init__(self, container: tk.Widget, page_cache: PageCache):
        self.container = container
        self.page_cache = page_cache
        self.current_page_id: Optional[str] = None
        self.current_widget: Optional[tk.Widget] = None
        
        # 切换动画参数
        self.transition_duration = 200  # 毫秒
        self.is_transitioning = False
    
    @batch_ui_update
    def switch_to_page(self, page_id: str, 
                       page_factory: Optional[Callable[[], Tuple[tk.Widget, Dict]]] = None,
                       animate: bool = True) -> bool:
        """切换到指定页面
        
        Args:
            page_id: 目标页面ID
            page_factory: 页面工厂函数（如果缓存中没有）
            animate: 是否使用动画
            
        Returns:
            bool: 是否成功切换
        """
        if self.is_transitioning:
            return False
        
        # 保存当前页面状态
        if self.current_page_id and self.current_widget:
            current_page = self.page_cache.get_page(self.current_page_id)
            if current_page:
                current_page.save_ui_state(self.current_widget)
        
        # 获取目标页面
        target_page = self.page_cache.get_page(page_id)
        
        if not target_page:
            # 页面不在缓存中，需要创建
            if not page_factory:
                print(f"页面 {page_id} 不在缓存中且没有提供工厂函数")
                return False
            
            try:
                widget, data = page_factory()
                target_page = self.page_cache.cache_page(page_id, widget, data)
            except Exception as e:
                print(f"创建页面 {page_id} 失败: {e}")
                return False
        
        # 执行页面切换
        if animate and self.current_widget:
            self._animate_transition(target_page)
        else:
            self._direct_switch(target_page)
        
        self.current_page_id = page_id
        return True
    
    def _direct_switch(self, target_page: PageState) -> None:
        """直接切换页面（无动画）"""
        # 隐藏当前页面
        if self.current_widget:
            self.current_widget.pack_forget()
        
        # 显示目标页面
        if target_page.widget:
            target_page.widget.pack(fill="both", expand=True)
            target_page.restore_ui_state(target_page.widget)
            self.current_widget = target_page.widget
    
    def _animate_transition(self, target_page: PageState) -> None:
        """动画切换页面"""
        self.is_transitioning = True
        
        # 简单的淡入淡出效果
        def fade_out():
            if self.current_widget:
                # 淡出当前页面
                self.current_widget.configure(state='disabled')
                self.container.after(self.transition_duration // 2, fade_in)
            else:
                fade_in()
        
        def fade_in():
            # 切换页面
            if self.current_widget:
                self.current_widget.pack_forget()
            
            if target_page.widget:
                target_page.widget.pack(fill="both", expand=True)
                target_page.restore_ui_state(target_page.widget)
                self.current_widget = target_page.widget
            
            # 恢复交互
            self.container.after(self.transition_duration // 2, finish_transition)
        
        def finish_transition():
            if self.current_widget:
                try:
                    self.current_widget.configure(state='normal')
                except:
                    pass
            self.is_transitioning = False
        
        fade_out()
    
    def preload_adjacent_pages(self, current_page_id: str, 
                              page_sequence: List[str],
                              page_factories: Dict[str, Callable]) -> None:
        """预加载相邻页面
        
        Args:
            current_page_id: 当前页面ID
            page_sequence: 页面序列
            page_factories: 页面工厂函数字典
        """
        try:
            current_index = page_sequence.index(current_page_id)
            
            # 预加载前一页和后一页
            for offset in [-1, 1]:
                target_index = current_index + offset
                if 0 <= target_index < len(page_sequence):
                    target_page_id = page_sequence[target_index]
                    factory = page_factories.get(target_page_id)
                    
                    if factory:
                        self.page_cache.preload_page(target_page_id, factory)
        except ValueError:
            # 当前页面不在序列中
            pass


# 全局页面缓存实例
_global_page_cache: Optional[PageCache] = None
_global_transition_manager: Optional[PageTransitionManager] = None


def get_page_cache() -> PageCache:
    """获取全局页面缓存实例"""
    global _global_page_cache
    if _global_page_cache is None:
        _global_page_cache = PageCache()
    return _global_page_cache


def get_transition_manager(container: tk.Widget) -> PageTransitionManager:
    """获取全局页面切换管理器"""
    global _global_transition_manager
    if _global_transition_manager is None:
        _global_transition_manager = PageTransitionManager(container, get_page_cache())
    return _global_transition_manager


def cache_page_decorator(page_id: str):
    """页面缓存装饰器
    
    用于自动缓存页面创建函数的结果。
    """
    def decorator(func: Callable[[], Tuple[tk.Widget, Dict]]):
        def wrapper(*args, **kwargs):
            cache = get_page_cache()
            cached_page = cache.get_page(page_id)
            
            if cached_page:
                return cached_page.widget, cached_page.data
            
            # 创建新页面
            widget, data = func(*args, **kwargs)
            cache.cache_page(page_id, widget, data)
            
            return widget, data
        
        return wrapper
    return decorator