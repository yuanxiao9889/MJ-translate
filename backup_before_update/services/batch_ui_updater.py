"""批量UI更新器 - 消除DOM操作卡顿

这个模块实现了批量UI更新机制，避免频繁的DOM操作导致界面卡顿。
遵循Linus的"好品味"原则：消除特殊情况，用统一的方式处理所有UI更新。
"""

import tkinter as tk
from typing import Callable, Any, List, Tuple
from functools import wraps
import time


class BatchUIUpdater:
    """批量UI更新器
    
    将多个UI更新操作合并为一次批量执行，显著提升界面响应性能。
    """
    
    def __init__(self, root: tk.Tk = None):
        self.root = root
        self.pending_updates: List[Tuple[Callable, tuple, dict]] = []
        self.update_scheduled = False
        self.last_update_time = 0
        self.min_update_interval = 0.016  # 约60FPS
        self.total_batched = 0
        self.total_updates = 0
    
    def schedule_update(self, update_func: Callable, *args, **kwargs) -> None:
        """调度一个UI更新操作
        
        Args:
            update_func: 要执行的更新函数
            *args: 函数参数
            **kwargs: 函数关键字参数
        """
        self.pending_updates.append((update_func, args, kwargs))
        
        if not self.update_scheduled:
            self.update_scheduled = True
            if self.root:
                # 使用after_idle确保在空闲时批量更新
                self.root.after_idle(self._execute_batch_updates)
    
    def schedule_delayed_update(self, delay_ms: int, update_func: Callable, *args, **kwargs) -> None:
        """调度一个延迟的UI更新操作
        
        Args:
            delay_ms: 延迟毫秒数
            update_func: 要执行的更新函数
            *args: 函数参数
            **kwargs: 函数关键字参数
        """
        if self.root:
            self.root.after(delay_ms, lambda: self.schedule_update(update_func, *args, **kwargs))
    
    def _execute_batch_updates(self) -> None:
        """执行批量更新"""
        if not self.pending_updates:
            self.update_scheduled = False
            return
        
        current_time = time.time()
        
        # 限制更新频率，避免过度刷新
        if current_time - self.last_update_time < self.min_update_interval:
            if self.root:
                self.root.after(int(self.min_update_interval * 1000), self._execute_batch_updates)
            return
        
        # 执行所有待处理的更新
        updates_to_execute = self.pending_updates.copy()
        self.pending_updates.clear()
        
        # 更新统计
        self.total_batched += 1
        self.total_updates += len(updates_to_execute)
        
        for update_func, args, kwargs in updates_to_execute:
            try:
                update_func(*args, **kwargs)
            except Exception as e:
                # 记录错误但不中断其他更新
                print(f"UI更新错误: {e}")
        
        self.last_update_time = current_time
        self.update_scheduled = False
        
        # 如果还有新的更新请求，继续处理
        if self.pending_updates:
            self.update_scheduled = True
            if self.root:
                self.root.after_idle(self._execute_batch_updates)
    
    def force_update(self) -> None:
        """强制立即执行所有待处理的更新"""
        if self.pending_updates:
            self._execute_batch_updates()
    
    def clear_pending_updates(self) -> None:
        """清除所有待处理的更新"""
        self.pending_updates.clear()
        self.update_scheduled = False
    
    def get_stats(self) -> dict:
        """获取批量更新统计信息"""
        return {
            'total_batched': self.total_batched,
            'total_updates': self.total_updates,
            'pending_count': len(self.pending_updates),
            'update_scheduled': self.update_scheduled,
            'avg_batch_size': self.total_updates / max(1, self.total_batched)
        }


# 全局批量更新器实例
_global_updater = None


def get_batch_updater(root: tk.Tk = None) -> BatchUIUpdater:
    """获取全局批量更新器实例"""
    global _global_updater
    if _global_updater is None:
        _global_updater = BatchUIUpdater(root)
    elif root and _global_updater.root is None:
        _global_updater.root = root
    return _global_updater


def batch_ui_update(func: Callable) -> Callable:
    """装饰器：将函数标记为批量UI更新
    
    使用此装饰器的函数将被自动加入批量更新队列。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        updater = get_batch_updater()
        updater.schedule_update(func, *args, **kwargs)
    return wrapper


def debounce_ui_update(delay_ms: int = 100):
    """装饰器：防抖UI更新
    
    在指定延迟时间内，如果多次调用同一函数，只执行最后一次。
    
    Args:
        delay_ms: 防抖延迟时间（毫秒）
    """
    def decorator(func: Callable) -> Callable:
        last_call_time = [0]
        pending_call = [None]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time() * 1000  # 转换为毫秒
            last_call_time[0] = current_time
            
            def delayed_call():
                if time.time() * 1000 - last_call_time[0] >= delay_ms - 10:  # 10ms容差
                    updater = get_batch_updater()
                    updater.schedule_update(func, *args, **kwargs)
                    pending_call[0] = None
            
            # 取消之前的延迟调用
            if pending_call[0]:
                updater = get_batch_updater()
                if updater.root:
                    updater.root.after_cancel(pending_call[0])
            
            # 调度新的延迟调用
            updater = get_batch_updater()
            if updater.root:
                pending_call[0] = updater.root.after(delay_ms, delayed_call)
        
        return wrapper
    return decorator


class UIPerformanceMonitor:
    """UI性能监控器
    
    监控UI更新的性能指标，帮助识别性能瓶颈。
    """
    
    def __init__(self):
        self.update_times = []
        self.max_samples = 100
    
    def record_update_time(self, duration: float) -> None:
        """记录一次更新的耗时"""
        self.update_times.append(duration)
        if len(self.update_times) > self.max_samples:
            self.update_times.pop(0)
    
    def get_average_update_time(self) -> float:
        """获取平均更新时间"""
        if not self.update_times:
            return 0.0
        return sum(self.update_times) / len(self.update_times)
    
    def get_max_update_time(self) -> float:
        """获取最大更新时间"""
        return max(self.update_times) if self.update_times else 0.0
    
    def is_performance_degraded(self, threshold_ms: float = 16.0) -> bool:
        """检查性能是否下降（超过60FPS阈值）"""
        avg_time = self.get_average_update_time() * 1000  # 转换为毫秒
        return avg_time > threshold_ms


# 全局性能监控器
performance_monitor = UIPerformanceMonitor()


def monitor_ui_performance(func: Callable) -> Callable:
    """装饰器：监控UI函数的性能"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start_time
            performance_monitor.record_update_time(duration)
    return wrapper