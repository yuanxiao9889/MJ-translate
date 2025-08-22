# -*- coding: utf-8 -*-
"""
分页标签管理器
实现每个分页独立的标签内容管理
"""

import json
import os
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from copy import deepcopy

# 避免循环导入，使用TYPE_CHECKING
if TYPE_CHECKING:
    from views.page_manager import TranslationPage


class PageTagManager:
    """分页标签管理器 - 管理单个分页的标签数据"""
    
    def __init__(self, page: 'TranslationPage'):
        """
        初始化分页标签管理器
        
        Args:
            page: TranslationPage 对象
        """
        self.page = page
        self.page_id = page.page_id
        
        # 直接引用page的tags，确保引用一致性
        self.tags = self.page.tags
        
        # 确保标签数据结构存在，但不破坏引用
        if not isinstance(self.tags, dict):
            self.page.tags = {'head': {}, 'tail': {}}
            self.tags = self.page.tags
        
        # 确保head和tail键存在，但不破坏引用
        if 'head' not in self.tags:
            self.tags['head'] = {}
        if 'tail' not in self.tags:
            self.tags['tail'] = {}
    
    def get_all_tags(self, tag_type: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        获取指定类型的所有标签
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            
        Returns:
            标签数据字典 {tab_name: {tag_name: tag_data}}
        """
        return self.tags.get(tag_type, {})
    
    def get_selected_tags(self, tag_type: str) -> List[str]:
        """
        获取已选中的标签英文名列表
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            
        Returns:
            已选中标签的英文名列表
        """
        selected = []
        for tab_name, tab_tags in self.tags.get(tag_type, {}).items():
            for tag_name, tag_data in tab_tags.items():
                if tag_data.get('selected', False):
                    selected.append(tag_data.get('en', tag_name))
        return selected
    
    def get_selected_tags_with_info(self, tag_type: str) -> List[Dict[str, Any]]:
        """
        获取已选中的标签详细信息
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            
        Returns:
            已选中标签的详细信息列表
        """
        selected = []
        for tab_name, tab_tags in self.tags.get(tag_type, {}).items():
            for tag_name, tag_data in tab_tags.items():
                if tag_data.get('selected', False):
                    selected.append({
                        'zh_name': tag_name,
                        'en_name': tag_data.get('en', tag_name),
                        'tab_name': tab_name,
                        'tag_data': tag_data
                    })
        return selected
    
    def is_tag_selected(self, tag_type: str, tab_name: Optional[str], tag_name: str) -> bool:
        """
        检查标签是否已选中
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            tab_name: 标签分类名；若为None则自动在所有分类中查找
            tag_name: 标签中文名
            
        Returns:
            是否已选中
        """
        # 如果未指定分类，自动查找包含该标签的分类
        if tab_name is None:
            for t_name, tab_tags in self.tags.get(tag_type, {}).items():
                if tag_name in tab_tags:
                    tab_name = t_name
                    break
        
        if (tag_type in self.tags and 
            tab_name in self.tags[tag_type] and 
            tag_name in self.tags[tag_type][tab_name]):
            return self.tags[tag_type][tab_name][tag_name].get('selected', False)
        return False
    
    def toggle_tag(self, tag_type: str, tab_name: Optional[str], tag_name: str) -> bool:
        """
        切换标签选中状态
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            tab_name: 标签分类名；若为None则自动在所有分类中查找
            tag_name: 标签中文名
            
        Returns:
            操作是否成功 (True表示成功切换，False表示标签不存在)
        """
        # 如果未指定分类，自动查找包含该标签的分类
        if tab_name is None:
            for t_name, tab_tags in self.tags.get(tag_type, {}).items():
                if tag_name in tab_tags:
                    tab_name = t_name
                    break
        
        if (tag_type in self.tags and 
            tab_name and tab_name in self.tags[tag_type] and 
            tag_name in self.tags[tag_type][tab_name]):
            current_state = self.tags[tag_type][tab_name][tag_name].get('selected', False)
            new_state = not current_state
            self.tags[tag_type][tab_name][tag_name]['selected'] = new_state
            
            print(f"[PageTagManager] 页面{self.page_id} - 标签状态切换: {tag_type}/{tab_name}/{tag_name} {current_state} -> {new_state}")
            
            # 更新使用次数
            if new_state:  # 如果是选中操作
                current_count = self.tags[tag_type][tab_name][tag_name].get('usage_count', 0)
                self.tags[tag_type][tab_name][tag_name]['usage_count'] = current_count + 1
            
            # 返回True表示操作成功，而不是返回新状态
            return True
        
        print(f"[PageTagManager] 页面{self.page_id} - 标签切换失败: {tag_type}/{tab_name}/{tag_name} 未找到")
        return False
    
    def add_tag(self, tag_type: str, tab_name: str, tag_name: str, tag_data: Dict[str, Any]) -> bool:
        """
        添加新标签到分页
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            tab_name: 标签分类名
            tag_name: 标签中文名
            tag_data: 标签数据
            
        Returns:
            是否添加成功
        """
        try:
            # 确保数据结构存在
            if tag_type not in self.tags:
                self.tags[tag_type] = {}
            if tab_name not in self.tags[tag_type]:
                self.tags[tag_type][tab_name] = {}
            
            # 设置默认值
            default_data = {
                'en': tag_data.get('en', tag_name),
                'selected': tag_data.get('selected', False),
                'usage_count': tag_data.get('usage_count', 0),
                'image': tag_data.get('image', ''),
                'url': tag_data.get('url', ''),
                'title': tag_data.get('title', ''),
                'timestamp': tag_data.get('timestamp', 0)
            }
            
            self.tags[tag_type][tab_name][tag_name] = default_data
            return True
        except Exception as e:
            print(f"添加标签失败: {e}")
            return False
    
    def remove_tag(self, tag_type: str, tab_name: str, tag_name: str) -> bool:
        """
        从分页中移除标签
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            tab_name: 标签分类名
            tag_name: 标签中文名
            
        Returns:
            是否移除成功
        """
        try:
            if (tag_type in self.tags and 
                tab_name in self.tags[tag_type] and 
                tag_name in self.tags[tag_type][tab_name]):
                
                del self.tags[tag_type][tab_name][tag_name]
                
                # 如果分类为空，删除分类
                if not self.tags[tag_type][tab_name]:
                    del self.tags[tag_type][tab_name]
                
                return True
        except Exception as e:
            print(f"移除标签失败: {e}")
        return False
    
    def update_tag_data(self, tag_type: str, tab_name: str, tag_name: str, 
                       updates: Dict[str, Any]) -> bool:
        """
        更新标签数据
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            tab_name: 标签分类名
            tag_name: 标签中文名
            updates: 要更新的数据字典
            
        Returns:
            是否更新成功
        """
        try:
            if (tag_type in self.tags and 
                tab_name in self.tags[tag_type] and 
                tag_name in self.tags[tag_type][tab_name]):
                
                self.tags[tag_type][tab_name][tag_name].update(updates)
                return True
        except Exception as e:
            print(f"更新标签数据失败: {e}")
        return False
    
    def get_tag_data(self, tag_type: str, tab_name: str, tag_name: str) -> Optional[Dict[str, Any]]:
        """
        获取标签数据
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            tab_name: 标签分类名
            tag_name: 标签中文名
            
        Returns:
            标签数据字典，如果不存在返回None
        """
        if (tag_type in self.tags and 
            tab_name in self.tags[tag_type] and 
            tag_name in self.tags[tag_type][tab_name]):
            return self.tags[tag_type][tab_name][tag_name].copy()
        return None
    
    def clear_all_selections(self, tag_type: Optional[str] = None):
        """
        清除所有标签的选中状态
        
        Args:
            tag_type: 标签类型，如果为None则清除所有类型
        """
        tag_types = [tag_type] if tag_type else ['head', 'tail']
        
        for t_type in tag_types:
            for tab_name, tab_tags in self.tags.get(t_type, {}).items():
                for tag_name, tag_data in tab_tags.items():
                    tag_data['selected'] = False
    
    def get_tab_names(self, tag_type: str) -> List[str]:
        """
        获取指定类型的所有分类名
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            
        Returns:
            分类名列表
        """
        return list(self.tags.get(tag_type, {}).keys())
    
    def get_tag_names_in_tab(self, tag_type: str, tab_name: str) -> List[str]:
        """
        获取指定分类中的所有标签名
        
        Args:
            tag_type: 标签类型 ('head' 或 'tail')
            tab_name: 标签分类名
            
        Returns:
            标签名列表
        """
        if tag_type in self.tags and tab_name in self.tags[tag_type]:
            return list(self.tags[tag_type][tab_name].keys())
        return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取标签统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            'total_tags': 0,
            'selected_tags': 0,
            'head_tags': 0,
            'tail_tags': 0,
            'head_selected': 0,
            'tail_selected': 0,
            'tabs': {'head': 0, 'tail': 0}
        }
        
        for tag_type in ['head', 'tail']:
            stats['tabs'][tag_type] = len(self.tags.get(tag_type, {}))
            
            for tab_name, tab_tags in self.tags.get(tag_type, {}).items():
                for tag_name, tag_data in tab_tags.items():
                    stats['total_tags'] += 1
                    stats[f'{tag_type}_tags'] += 1
                    
                    if tag_data.get('selected', False):
                        stats['selected_tags'] += 1
                        stats[f'{tag_type}_selected'] += 1
        
        return stats
    
    def export_data(self) -> Dict[str, Any]:
        """
        导出标签数据
        
        Returns:
            标签数据的深拷贝
        """
        return deepcopy(self.tags)
    
    def import_data(self, tag_data: Dict[str, Any], merge: bool = True) -> bool:
        """
        导入标签数据
        
        Args:
            tag_data: 要导入的标签数据
            merge: 是否合并模式（True）还是覆盖模式（False）
            
        Returns:
            是否导入成功
        """
        try:
            if not merge:
                # 覆盖模式：清空现有数据
                self.tags.clear()
                self.tags.update({'head': {}, 'tail': {}})
            
            # 导入数据
            for tag_type in ['head', 'tail']:
                if tag_type in tag_data:
                    if tag_type not in self.tags:
                        self.tags[tag_type] = {}
                    
                    for tab_name, tab_tags in tag_data[tag_type].items():
                        if merge and tab_name in self.tags[tag_type]:
                            # 合并模式：更新现有标签，但确保初始状态未选中
                            for tag_name, tag_info in tab_tags.items():
                                clean_tag_info = deepcopy(tag_info) if isinstance(tag_info, dict) else {'en': tag_info}
                                # 确保初始状态未选中
                                clean_tag_info['selected'] = False
                                clean_tag_info['usage_count'] = clean_tag_info.get('usage_count', 0)
                                self.tags[tag_type][tab_name][tag_name] = clean_tag_info
                        else:
                            # 覆盖模式或新标签：直接设置，但确保初始状态未选中
                            clean_tab_tags = {}
                            for tag_name, tag_info in tab_tags.items():
                                clean_tag_info = deepcopy(tag_info) if isinstance(tag_info, dict) else {'en': tag_info}
                                # 确保初始状态未选中
                                clean_tag_info['selected'] = False
                                clean_tag_info['usage_count'] = clean_tag_info.get('usage_count', 0)
                                clean_tab_tags[tag_name] = clean_tag_info
                            self.tags[tag_type][tab_name] = clean_tab_tags
            
            return True
        except Exception as e:
            print(f"导入标签数据失败: {e}")
            return False
    
    def restore_ui_state(self):
        """
        恢复标签UI状态
        
        这个方法在分页切换时被调用，用于确保标签UI能够正确显示选中状态。
        由于标签的选中状态已经存储在数据库中，UI刷新时会自动读取这些状态，
        所以这个方法主要用于触发UI刷新和状态同步。
        """
        try:
            print(f"[PageTagManager] 恢复分页 {self.page_id} 的标签UI状态")
            
            # 获取当前选中的标签统计
            head_selected = self.get_selected_tags("head")
            tail_selected = self.get_selected_tags("tail")
            
            print(f"头部选中标签: {len(head_selected)} 个 - {head_selected}")
            print(f"尾部选中标签: {len(tail_selected)} 个 - {tail_selected}")
            
            # 标签UI会在refresh_head_tags和refresh_tail_tags中自动根据
            # is_tag_selected方法的返回值来设置正确的选中状态
            
        except Exception as e:
            print(f"[PageTagManager] 恢复标签UI状态失败: {e}")