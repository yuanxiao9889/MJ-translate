"""优化的历史记录管理器

提供高性能的历史记录加载、缓存和筛选功能，解决大数据量时的性能问题。
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from threading import Lock


class HistoryManager:
    """历史记录管理器 - 提供高性能的数据加载和缓存机制"""
    
    def __init__(self, history_file: str = "history.json"):
        self.history_file = history_file
        self._cache = None
        self._cache_timestamp = 0
        self._date_index = {}
        self._lock = Lock()
        self.cache_ttl = 300  # 缓存5分钟
        
    def _should_reload_cache(self) -> bool:
        """检查是否需要重新加载缓存"""
        if self._cache is None:
            return True
            
        # 检查缓存是否过期
        if time.time() - self._cache_timestamp > self.cache_ttl:
            return True
            
        # 检查文件是否被修改
        if os.path.exists(self.history_file):
            file_mtime = os.path.getmtime(self.history_file)
            if file_mtime > self._cache_timestamp:
                return True
                
        return False
    
    def _load_history_data(self) -> List[Dict]:
        """从文件加载历史记录数据"""
        if not os.path.exists(self.history_file):
            return []
            
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError) as e:
            print(f"加载历史记录失败: {e}")
            return []
    
    def _build_date_index(self, data: List[Dict]) -> Dict[str, List[int]]:
        """构建日期索引以加速筛选"""
        date_index = {}
        for idx, item in enumerate(data):
            timestamp = item.get("timestamp") or item.get("date", "")
            if timestamp:
                date_key = timestamp[:10]  # YYYY-MM-DD
                if date_key not in date_index:
                    date_index[date_key] = []
                date_index[date_key].append(idx)
        return date_index
    
    def get_history_data(self, force_reload: bool = False) -> List[Dict]:
        """获取历史记录数据（带缓存）"""
        with self._lock:
            if force_reload or self._should_reload_cache():
                start_time = time.time()
                self._cache = self._load_history_data()
                self._date_index = self._build_date_index(self._cache)
                self._cache_timestamp = time.time()
                load_time = time.time() - start_time
                print(f"历史记录加载完成: {len(self._cache)} 条记录，耗时 {load_time:.3f}s")
            
            return self._cache.copy() if self._cache else []
    
    def get_filtered_data(self, date_filter: Optional[str] = None) -> List[Dict]:
        """获取筛选后的数据（使用索引加速）"""
        data = self.get_history_data()
        
        if not date_filter:
            return data
            
        # 使用日期索引快速筛选
        if date_filter in self._date_index:
            indices = self._date_index[date_filter]
            return [data[i] for i in indices if i < len(data)]
        else:
            return []
    
    def get_page_data(self, page: int, page_size: int, date_filter: Optional[str] = None) -> Tuple[List[Dict], int, int]:
        """获取分页数据
        
        Returns:
            Tuple[List[Dict], int, int]: (页面数据, 总页数, 总记录数)
        """
        filtered_data = self.get_filtered_data(date_filter)
        total_records = len(filtered_data)
        total_pages = max(1, (total_records + page_size - 1) // page_size)
        
        # 确保页码在有效范围内
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, total_records)
        
        page_data = filtered_data[start_idx:end_idx]
        
        return page_data, total_pages, total_records
    
    def clear_cache(self):
        """清空缓存"""
        with self._lock:
            self._cache = None
            self._cache_timestamp = 0
            self._date_index = {}
    
    def get_cache_info(self) -> Dict:
        """获取缓存信息（用于调试）"""
        return {
            "cached": self._cache is not None,
            "cache_size": len(self._cache) if self._cache else 0,
            "cache_age": time.time() - self._cache_timestamp if self._cache_timestamp else 0,
            "date_index_size": len(self._date_index)
        }
    
    def cleanup_old_records(self, days: int) -> int:
        """清理指定天数前的记录
        
        Returns:
            int: 清理的记录数量
        """
        data = self.get_history_data()
        cutoff = datetime.now() - timedelta(days=days)
        
        new_data = []
        removed_count = 0
        
        for item in data:
            timestamp = item.get("timestamp") or item.get("date", "")
            if timestamp:
                try:
                    item_date = datetime.strptime(timestamp[:10], "%Y-%m-%d")
                    if item_date > cutoff:
                        new_data.append(item)
                    else:
                        removed_count += 1
                except ValueError:
                    # 如果日期格式不正确，保留记录
                    new_data.append(item)
            else:
                new_data.append(item)
        
        # 保存清理后的数据
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)
            
            # 清空缓存以强制重新加载
            self.clear_cache()
            
        except IOError as e:
            print(f"保存历史记录失败: {e}")
            return 0
        
        return removed_count
    
    def clear_all_records(self) -> bool:
        """清空所有历史记录
        
        Returns:
            bool: 是否成功清空
        """
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            
            # 清空缓存
            self.clear_cache()
            return True
            
        except IOError as e:
            print(f"清空历史记录失败: {e}")
            return False


# 全局历史记录管理器实例
_history_manager = None


def get_history_manager() -> HistoryManager:
    """获取全局历史记录管理器实例"""
    global _history_manager
    if _history_manager is None:
        _history_manager = HistoryManager()
    return _history_manager