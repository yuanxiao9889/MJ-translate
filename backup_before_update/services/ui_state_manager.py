#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI状态管理器 - 管理分页的UI显示状态
负责记录和恢复每个分页的标签UI显示状态，确保分页切换时UI显示正确
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class UIStateManager:
    """UI状态管理器 - 管理分页的UI显示状态"""
    
    def __init__(self, data_file: str = "ui_states.json"):
        """
        初始化UI状态管理器
        
        Args:
            data_file: UI状态数据文件路径
        """
        self.data_file = data_file
        self.ui_states = {}  # {page_id: ui_state_data}
        self.load_ui_states()
    
    def load_ui_states(self):
        """加载UI状态数据"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.ui_states = json.load(f)
            except Exception as e:
                print(f"[UIStateManager] 加载UI状态数据失败: {e}")
                self.ui_states = {}
        else:
            self.ui_states = {}
    
    def save_ui_states(self):
        """保存UI状态数据"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.ui_states, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UIStateManager] 保存UI状态数据失败: {e}")
    
    def get_page_ui_state(self, page_id: str) -> Dict[str, Any]:
        """
        获取指定分页的UI状态
        
        Args:
            page_id: 分页ID
            
        Returns:
            分页的UI状态数据
        """
        if page_id not in self.ui_states:
            # 创建默认UI状态
            self.ui_states[page_id] = self._create_default_ui_state()
        
        return self.ui_states[page_id]
    
    def _create_default_ui_state(self) -> Dict[str, Any]:
        """创建默认UI状态"""
        return {
            "output_text_state": {
                "tag_blocks": [],  # 标签块信息列表
                "text_content": "",  # 文本内容
                "cursor_position": "1.0",  # 光标位置
                "scroll_position": 0.0  # 滚动位置
            },
            "tag_ui_state": {
                "head_tags": {
                    "visible_tags": [],  # 可见的头部标签
                    "selected_tags": [],  # 选中的头部标签
                    "scroll_position": 0.0  # 滚动位置
                },
                "tail_tags": {
                    "visible_tags": [],  # 可见的尾部标签
                    "selected_tags": [],  # 选中的尾部标签
                    "scroll_position": 0.0  # 滚动位置
                }
            },
            "layout_state": {
                "layout_mode": "waterfall",  # 布局模式：list, waterfall
                "canvas_width": 0,  # 画布宽度
                "canvas_height": 0  # 画布高度
            },
            "last_updated": datetime.now().isoformat()
        }
    
    def save_output_text_state(self, page_id: str, tag_blocks: List[Dict], text_content: str, 
                              cursor_position: str = "1.0", scroll_position: float = 0.0):
        """
        保存输出文本框的状态
        
        Args:
            page_id: 分页ID
            tag_blocks: 标签块信息列表
            text_content: 文本内容
            cursor_position: 光标位置
            scroll_position: 滚动位置
        """
        ui_state = self.get_page_ui_state(page_id)
        ui_state["output_text_state"] = {
            "tag_blocks": tag_blocks,
            "text_content": text_content,
            "cursor_position": cursor_position,
            "scroll_position": scroll_position
        }
        ui_state["last_updated"] = datetime.now().isoformat()
        self.save_ui_states()
    
    def get_output_text_state(self, page_id: str) -> Dict[str, Any]:
        """
        获取输出文本框的状态
        
        Args:
            page_id: 分页ID
            
        Returns:
            输出文本框状态数据
        """
        ui_state = self.get_page_ui_state(page_id)
        return ui_state.get("output_text_state", {
            "tag_blocks": [],
            "text_content": "",
            "cursor_position": "1.0",
            "scroll_position": 0.0
        })
    
    def save_tag_ui_state(self, page_id: str, tag_type: str, visible_tags: List[str], 
                         selected_tags: List[str], scroll_position: float = 0.0):
        """
        保存标签UI状态
        
        Args:
            page_id: 分页ID
            tag_type: 标签类型 ('head' 或 'tail')
            visible_tags: 可见的标签列表
            selected_tags: 选中的标签列表
            scroll_position: 滚动位置
        """
        ui_state = self.get_page_ui_state(page_id)
        if "tag_ui_state" not in ui_state:
            ui_state["tag_ui_state"] = {"head_tags": {}, "tail_tags": {}}
        
        tag_key = f"{tag_type}_tags"
        ui_state["tag_ui_state"][tag_key] = {
            "visible_tags": visible_tags,
            "selected_tags": selected_tags,
            "scroll_position": scroll_position
        }
        ui_state["last_updated"] = datetime.now().isoformat()
        self.save_ui_states()
    
    def get_tag_ui_state(self, page_id: str, tag_type: str) -> Dict[str, Any]:
        """
        获取标签UI状态
        
        Args:
            page_id: 分页ID
            tag_type: 标签类型 ('head' 或 'tail')
            
        Returns:
            标签UI状态数据
        """
        ui_state = self.get_page_ui_state(page_id)
        tag_key = f"{tag_type}_tags"
        return ui_state.get("tag_ui_state", {}).get(tag_key, {
            "visible_tags": [],
            "selected_tags": [],
            "scroll_position": 0.0
        })
    
    def save_layout_state(self, page_id: str, layout_mode: str, canvas_width: int = 0, canvas_height: int = 0):
        """
        保存布局状态
        
        Args:
            page_id: 分页ID
            layout_mode: 布局模式
            canvas_width: 画布宽度
            canvas_height: 画布高度
        """
        ui_state = self.get_page_ui_state(page_id)
        ui_state["layout_state"] = {
            "layout_mode": layout_mode,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height
        }
        ui_state["last_updated"] = datetime.now().isoformat()
        self.save_ui_states()
    
    def get_layout_state(self, page_id: str) -> Dict[str, Any]:
        """
        获取布局状态
        
        Args:
            page_id: 分页ID
            
        Returns:
            布局状态数据
        """
        ui_state = self.get_page_ui_state(page_id)
        return ui_state.get("layout_state", {
            "layout_mode": "waterfall",
            "canvas_width": 0,
            "canvas_height": 0
        })
    
    def create_tag_block_info(self, text: str, tag_type: str, position: str, 
                             style: Optional[Dict] = None) -> Dict[str, Any]:
        """
        创建标签块信息
        
        Args:
            text: 标签文本
            tag_type: 标签类型
            position: 在文本中的位置
            style: 样式信息
            
        Returns:
            标签块信息字典
        """
        return {
            "text": text,
            "tag_type": tag_type,
            "position": position,
            "style": style or {
                "color": "#3776ff" if tag_type == "head" else "#74e4b6",
                "hover_color": "#1857b6" if tag_type == "head" else "#2fa98c",
                "font": ("微软雅黑", 13, "bold"),
                "padding": {"x": 8, "y": 2}
            },
            "created_at": datetime.now().isoformat()
        }
    
    def clear_page_ui_state(self, page_id: str):
        """
        清空指定分页的UI状态
        
        Args:
            page_id: 分页ID
        """
        if page_id in self.ui_states:
            del self.ui_states[page_id]
            self.save_ui_states()
    
    def get_all_page_ids(self) -> List[str]:
        """
        获取所有有UI状态记录的分页ID
        
        Returns:
            分页ID列表
        """
        return list(self.ui_states.keys())
    
    def cleanup_orphaned_states(self, valid_page_ids: List[str]):
        """
        清理孤立的UI状态（对应的分页已不存在）
        
        Args:
            valid_page_ids: 有效的分页ID列表
        """
        orphaned_ids = [pid for pid in self.ui_states.keys() if pid not in valid_page_ids]
        for pid in orphaned_ids:
            del self.ui_states[pid]
        
        if orphaned_ids:
            self.save_ui_states()
            print(f"[UIStateManager] 清理了 {len(orphaned_ids)} 个孤立的UI状态")
    
    def clear_tag_ui_state(self, page_id: str, tag_type: str):
        """
        清空指定分页和标签类型的UI状态
        
        Args:
            page_id: 分页ID
            tag_type: 标签类型 ('head' 或 'tail')
        """
        if page_id not in self.ui_states:
            self.ui_states[page_id] = self._create_default_ui_state()
        
        if 'tag_ui_states' not in self.ui_states[page_id]:
            self.ui_states[page_id]['tag_ui_states'] = {}
        
        # 清空指定类型的标签UI状态
        self.ui_states[page_id]['tag_ui_states'][tag_type] = {
            'visible_tags': [],
            'selected_tags': [],
            'scroll_position': 0.0,
            'tag_details': {}  # 存储每个标签的详细信息
        }
    
    def set_tag_ui_state(self, page_id: str, tag_type: str, tag_label: str, tag_info: Dict[str, Any]):
        """
        设置指定标签的UI状态信息
        
        Args:
            page_id: 分页ID
            tag_type: 标签类型 ('head' 或 'tail')
            tag_label: 标签名称
            tag_info: 标签信息字典
        """
        if page_id not in self.ui_states:
            self.ui_states[page_id] = self._create_default_ui_state()
        
        if 'tag_ui_states' not in self.ui_states[page_id]:
            self.ui_states[page_id]['tag_ui_states'] = {}
        
        if tag_type not in self.ui_states[page_id]['tag_ui_states']:
            self.ui_states[page_id]['tag_ui_states'][tag_type] = {
                'visible_tags': [],
                'selected_tags': [],
                'scroll_position': 0.0,
                'tag_details': {}
            }
        
        # 设置标签详细信息
        self.ui_states[page_id]['tag_ui_states'][tag_type]['tag_details'][tag_label] = tag_info
        
        # 更新可见标签列表
        if tag_info.get('is_visible', False) and tag_label not in self.ui_states[page_id]['tag_ui_states'][tag_type]['visible_tags']:
            self.ui_states[page_id]['tag_ui_states'][tag_type]['visible_tags'].append(tag_label)
        
        # 更新选中标签列表
        if tag_info.get('is_selected', False) and tag_label not in self.ui_states[page_id]['tag_ui_states'][tag_type]['selected_tags']:
            self.ui_states[page_id]['tag_ui_states'][tag_type]['selected_tags'].append(tag_label)

# 全局UI状态管理器实例
ui_state_manager = UIStateManager()