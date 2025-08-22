"""UI性能优化集成模块

这个模块整合了所有UI性能优化功能，提供统一的接口：
1. 批量UI更新机制
2. 优化的布局算法
3. UI操作防抖
4. 虚拟滚动
5. 页面缓存和切换优化

遵循Linus的"好品味"原则：一个简单的接口解决所有性能问题。
"""

import tkinter as tk
from typing import Dict, List, Callable, Any, Optional, Tuple
import time
import threading
from services.batch_ui_updater import (
    get_batch_updater, batch_ui_update, debounce_ui_update, 
    UIPerformanceMonitor
)
from services.optimized_layout import (
    OptimizedWaterfallLayout, OptimizedFlowLayout, LayoutCache,
    optimized_waterfall_layout_canvas, optimized_flow_layout_canvas
)
from services.ui_debouncer import (
    get_debounce_manager, input_debouncer, scroll_debouncer,
    resize_debouncer, click_debouncer
)
from services.virtual_scroll import (
    VirtualScrollContainer, VirtualTagScrollContainer,
    create_virtual_scroll_canvas
)
from services.page_cache import (
    get_page_cache, get_transition_manager, cache_page_decorator,
    PageCache, PageTransitionManager
)


class UIPerformanceManager:
    """UI性能管理器
    
    统一管理所有UI性能优化功能。
    """
    
    def __init__(self):
        # 核心组件
        self.batch_updater = get_batch_updater()
        self.debounce_manager = get_debounce_manager()
        self.page_cache = get_page_cache()
        self.performance_monitor = UIPerformanceMonitor()
        
        # 布局缓存
        self.layout_cache = LayoutCache()
        
        # 虚拟滚动容器
        self.virtual_containers: Dict[str, VirtualScrollContainer] = {}
        
        # 页面切换管理器
        self.transition_managers: Dict[str, PageTransitionManager] = {}
        
        # 性能统计
        self.stats = {
            'ui_updates_batched': 0,
            'layout_cache_hits': 0,
            'virtual_scroll_active': 0,
            'page_cache_hits': 0,
            'debounced_operations': 0
        }
        
        # 性能监控线程
        self._monitoring_active = True
        self._start_performance_monitoring()
    
    def _start_performance_monitoring(self) -> None:
        """启动性能监控"""
        def monitor_worker():
            while self._monitoring_active:
                try:
                    # 收集性能数据
                    self._collect_performance_stats()
                    time.sleep(5)  # 每5秒收集一次
                except Exception as e:
                    print(f"性能监控错误: {e}")
        
        threading.Thread(target=monitor_worker, daemon=True).start()
    
    def _collect_performance_stats(self) -> None:
        """收集性能统计数据"""
        # 更新统计信息
        batch_stats = self.batch_updater.get_stats()
        cache_stats = self.page_cache.get_cache_stats()
        
        self.stats.update({
            'ui_updates_batched': batch_stats.get('total_batched', 0),
            'page_cache_hits': cache_stats.get('cache_hits', 0),
            'virtual_scroll_active': len(self.virtual_containers)
        })
    
    def get_batch_stats(self) -> dict:
        """获取批量更新统计信息"""
        return self.batch_updater.get_stats()
    
    # === 批量UI更新相关 ===
    
    def enable_batch_updates(self, widget: tk.Widget) -> None:
        """为控件启用批量更新"""
        @batch_ui_update
        def update_wrapper():
            pass
        
        # 将批量更新绑定到控件
        if hasattr(widget, '_batch_update_enabled'):
            return
        
        widget._batch_update_enabled = True
        self.stats['ui_updates_batched'] += 1
    
    def batch_update_decorator(self, func: Callable) -> Callable:
        """批量更新装饰器"""
        return batch_ui_update(func)
    
    def debounce_decorator(self, delay_ms: int = 100) -> Callable:
        """防抖装饰器"""
        def decorator(func: Callable) -> Callable:
            return debounce_ui_update(delay_ms)(func)
        return decorator
    
    # === 布局优化相关 ===
    
    def create_optimized_waterfall_layout(self, canvas: tk.Canvas, frame: tk.Frame,
                                         tags: Dict, inserted_tags: Dict, 
                                         tag_type: str, insert_callback: Callable) -> Callable:
        """创建优化的瀑布流布局"""
        from services.optimized_layout import get_optimized_waterfall_layout
        
        def layout_func():
            layout = get_optimized_waterfall_layout()
            layout.layout_tags(frame, canvas, tags, inserted_tags, tag_type, insert_callback, None)
            self.stats['layout_cache_hits'] += 1
        
        return layout_func
    
    def create_optimized_flow_layout(self, canvas: tk.Canvas, frame: tk.Frame,
                                   layout_mode: str, tags: Dict, 
                                   inserted_tags: Dict, tag_type: str,
                                   insert_callback: Callable) -> Callable:
        """创建优化的流式布局"""
        from services.optimized_layout import get_optimized_flow_layout
        
        def layout_func():
            layout = get_optimized_flow_layout()
            layout.layout_tags(frame, canvas, tags, inserted_tags, tag_type, insert_callback, None, layout_mode)
            self.stats['layout_cache_hits'] += 1
        
        return layout_func
    
    def clear_layout_cache(self) -> None:
        """清空布局缓存"""
        self.layout_cache.clear()
    
    # === 虚拟滚动相关 ===
    
    def create_virtual_scroll(self, container_id: str, parent: tk.Widget, 
                            height: int = 400) -> Tuple[tk.Canvas, VirtualScrollContainer]:
        """创建虚拟滚动容器"""
        canvas, virtual_container = create_virtual_scroll_canvas(parent, height)
        self.virtual_containers[container_id] = virtual_container
        self.stats['virtual_scroll_active'] += 1
        return canvas, virtual_container
    
    def create_virtual_tag_scroll(self, container_id: str, canvas: tk.Canvas, 
                                frame: tk.Frame, tag_renderer: Callable,
                                insert_callback: Callable) -> VirtualTagScrollContainer:
        """创建虚拟标签滚动容器"""
        container = VirtualTagScrollContainer(canvas, frame, tag_renderer, insert_callback)
        self.virtual_containers[container_id] = container
        return container
    
    def get_virtual_container(self, container_id: str) -> Optional[VirtualScrollContainer]:
        """获取虚拟滚动容器"""
        return self.virtual_containers.get(container_id)
    
    def remove_virtual_container(self, container_id: str) -> bool:
        """移除虚拟滚动容器"""
        if container_id in self.virtual_containers:
            del self.virtual_containers[container_id]
            self.stats['virtual_scroll_active'] -= 1
            return True
        return False
    
    # === 页面缓存相关 ===
    
    def create_page_transition_manager(self, manager_id: str, 
                                     container: tk.Widget) -> PageTransitionManager:
        """创建页面切换管理器"""
        manager = get_transition_manager(container)
        self.transition_managers[manager_id] = manager
        return manager
    
    def switch_page(self, manager_id: str, page_id: str,
                   page_factory: Optional[Callable] = None,
                   animate: bool = True) -> bool:
        """切换页面"""
        manager = self.transition_managers.get(manager_id)
        if manager:
            return manager.switch_to_page(page_id, page_factory, animate)
        return False
    
    def cache_page(self, page_id: str, widget: tk.Widget, 
                  data: Dict[str, Any] = None) -> None:
        """缓存页面"""
        self.page_cache.cache_page(page_id, widget, data)
    
    def preload_page(self, page_id: str, preload_callback: Callable) -> None:
        """预加载页面"""
        self.page_cache.preload_page(page_id, preload_callback)
    
    # === 防抖相关 ===
    
    def debounce_input(self, delay_ms: int = 300) -> Callable:
        """输入防抖装饰器"""
        return input_debouncer(delay_ms)
    
    def debounce_scroll(self, delay_ms: int = 16) -> Callable:
        """滚动防抖装饰器"""
        return scroll_debouncer(delay_ms)
    
    def debounce_resize(self, delay_ms: int = 100) -> Callable:
        """窗口大小调整防抖装饰器"""
        return resize_debouncer(delay_ms)
    
    def debounce_click(self, delay_ms: int = 200) -> Callable:
        """点击防抖装饰器"""
        return click_debouncer(delay_ms)
    
    # === 性能监控相关 ===
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        batch_stats = self.batch_updater.get_stats()
        cache_stats = self.page_cache.get_cache_stats()
        
        return {
            'ui_performance': self.stats,
            'batch_updater': batch_stats,
            'page_cache': cache_stats,
            'virtual_containers': len(self.virtual_containers),
            'transition_managers': len(self.transition_managers)
        }
    
    def start_performance_profiling(self, duration_seconds: int = 60) -> None:
        """开始性能分析"""
        self.performance_monitor.start_profiling(duration_seconds)
    
    def stop_performance_profiling(self) -> Dict[str, Any]:
        """停止性能分析并获取结果"""
        return self.performance_monitor.stop_profiling()
    
    # === 优化建议 ===
    
    def get_optimization_suggestions(self) -> List[str]:
        """获取优化建议"""
        suggestions = []
        stats = self.get_performance_stats()
        
        # 检查批量更新使用情况
        if stats['batch_updater']['pending_count'] > 10:
            suggestions.append("建议：当前有大量待处理的UI更新，考虑减少UI操作频率")
        
        # 检查页面缓存命中率
        cache_hit_rate = stats['page_cache'].get('hit_rate_percent', 0)
        if cache_hit_rate < 50:
            suggestions.append("建议：页面缓存命中率较低，考虑预加载常用页面")
        
        # 检查虚拟滚动使用情况
        if len(self.virtual_containers) == 0:
            suggestions.append("建议：对于大量数据的列表，考虑使用虚拟滚动")
        
        # 检查内存使用
        if stats['page_cache']['cached_pages'] > 8:
            suggestions.append("建议：缓存页面过多，考虑清理不常用的页面")
        
        return suggestions
    
    def optimize_for_low_end_device(self) -> None:
        """为低端设备优化"""
        # 减少缓存大小
        self.page_cache.max_cache_size = 5
        self.page_cache.max_age_seconds = 120
        
        # 增加防抖延迟
        self.debounce_manager.default_delay = 200
        
        # 清理现有缓存
        self.layout_cache.clear()
        
        print("已启用低端设备优化模式")
    
    def optimize_for_high_end_device(self) -> None:
        """为高端设备优化"""
        # 增加缓存大小
        self.page_cache.max_cache_size = 20
        self.page_cache.max_age_seconds = 600
        
        # 减少防抖延迟
        self.debounce_manager.default_delay = 50
        
        print("已启用高端设备优化模式")
    
    def cleanup(self) -> None:
        """清理资源"""
        self._monitoring_active = False
        
        # 清理缓存
        self.page_cache.clear_cache()
        self.layout_cache.clear()
        
        # 清理虚拟滚动容器
        self.virtual_containers.clear()
        self.transition_managers.clear()
        
        print("UI性能管理器已清理")
    
    def __del__(self):
        """析构函数"""
        self.cleanup()


# 全局性能管理器实例
_global_performance_manager: Optional[UIPerformanceManager] = None


def get_ui_performance_manager() -> UIPerformanceManager:
    """获取全局UI性能管理器"""
    global _global_performance_manager
    if _global_performance_manager is None:
        _global_performance_manager = UIPerformanceManager()
    return _global_performance_manager


# 便捷装饰器
def optimize_ui_function(batch_update: bool = True, debounce_ms: int = 0):
    """UI函数优化装饰器
    
    Args:
        batch_update: 是否启用批量更新
        debounce_ms: 防抖延迟（毫秒），0表示不防抖
    """
    def decorator(func: Callable) -> Callable:
        manager = get_ui_performance_manager()
        
        # 应用批量更新
        if batch_update:
            func = manager.batch_update_decorator(func)
        
        # 应用防抖
        if debounce_ms > 0:
            func = manager.debounce_decorator(debounce_ms)(func)
        
        return func
    
    return decorator


# 性能监控装饰器
def monitor_performance(func: Callable) -> Callable:
    """性能监控装饰器"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000  # 转换为毫秒
            
            if execution_time > 100:  # 超过100ms的操作记录警告
                print(f"性能警告：{func.__name__} 执行时间 {execution_time:.2f}ms")
    
    return wrapper


# 快速优化函数
def quick_optimize_canvas(canvas: tk.Canvas, frame: tk.Frame) -> None:
    """快速优化Canvas性能"""
    manager = get_ui_performance_manager()
    
    # 启用批量更新
    manager.enable_batch_updates(canvas)
    manager.enable_batch_updates(frame)
    
    # 绑定优化的滚动事件
    @manager.debounce_scroll(16)  # 60FPS
    def optimized_scroll(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    canvas.bind("<MouseWheel>", optimized_scroll)


def quick_optimize_layout(canvas: tk.Canvas, frame: tk.Frame, 
                         layout_type: str = "waterfall") -> Callable:
    """快速优化布局函数
    
    Args:
        canvas: 画布控件
        frame: 框架控件
        layout_type: 布局类型（"waterfall" 或 "flow"）
        
    Returns:
        优化后的布局函数
    """
    manager = get_ui_performance_manager()
    
    if layout_type == "waterfall":
        return lambda tags, inserted_tags, tag_type, callback: \
            manager.create_optimized_waterfall_layout(
                canvas, frame, tags, inserted_tags, tag_type, callback
            )
    else:
        return lambda mode, tags, inserted_tags, tag_type, callback: \
            manager.create_optimized_flow_layout(
                canvas, frame, mode, tags, inserted_tags, tag_type, callback
            )