# -*- coding: utf-8 -*-
"""
标签模板管理器
实现标签模板的创建、加载、应用和管理
"""

import json
import os
import time
from typing import Dict, List, Any, Optional
from copy import deepcopy


class TagTemplateManager:
    """标签模板管理器 - 管理标签模板的创建和应用"""
    
    def __init__(self, templates_file: str = "tag_templates.json"):
        """
        初始化标签模板管理器
        
        Args:
            templates_file: 模板文件路径
        """
        self.templates_file = templates_file
        self.templates = self.load_templates()
    
    def load_templates(self) -> Dict[str, Any]:
        """
        加载标签模板
        
        Returns:
            模板数据字典
        """
        try:
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('templates', {})
            else:
                # 创建默认模板
                return self._create_default_templates()
        except Exception as e:
            print(f"加载模板失败: {e}")
            return self._create_default_templates()
    
    def _create_default_templates(self) -> Dict[str, Any]:
        """
        创建默认模板
        
        Returns:
            默认模板字典
        """
        default_templates = {
            "default": {
                "name": "默认模板",
                "description": "包含常用标签的默认模板",
                "created_time": int(time.time()),
                "tags": {
                    "head": {
                        "基础": {
                            "正面角度": {
                                "en": "front angle",
                                "image": ""
                            },
                            "侧面角度": {
                                "en": "side angle",
                                "image": ""
                            }
                        },
                        "风格": {
                            "写实风格": {
                                "en": "photorealistic",
                                "image": ""
                            }
                        }
                    },
                    "tail": {
                        "质量": {
                            "高分辨率": {
                                "en": "high resolution",
                                "image": ""
                            },
                            "高质量": {
                                "en": "high quality",
                                "image": ""
                            }
                        }
                    }
                }
            },
            "portrait": {
                "name": "人像摄影模板",
                "description": "专门用于人像摄影的标签集合",
                "created_time": int(time.time()),
                "tags": {
                    "head": {
                        "角度": {
                            "正面": {"en": "front view", "image": ""},
                            "侧面": {"en": "side view", "image": ""},
                            "仰视": {"en": "low angle view", "image": ""}
                        },
                        "光照": {
                            "自然光": {"en": "natural lighting", "image": ""},
                            "柔光": {"en": "soft lighting", "image": ""}
                        }
                    },
                    "tail": {
                        "质量": {
                            "高清": {"en": "high quality", "image": ""},
                            "专业摄影": {"en": "professional photography", "image": ""}
                        }
                    }
                }
            },
            "landscape": {
                "name": "风景摄影模板",
                "description": "专门用于风景摄影的标签集合",
                "created_time": int(time.time()),
                "tags": {
                    "head": {
                        "视角": {
                            "广角": {"en": "wide angle", "image": ""},
                            "全景": {"en": "panoramic view", "image": ""}
                        },
                        "时间": {
                            "日出": {"en": "sunrise", "image": ""},
                            "日落": {"en": "sunset", "image": ""},
                            "黄金时刻": {"en": "golden hour", "image": ""}
                        }
                    },
                    "tail": {
                        "质量": {
                            "超高清": {"en": "ultra high resolution", "image": ""},
                            "风景摄影": {"en": "landscape photography", "image": ""}
                        }
                    }
                }
            }
        }
        
        # 保存默认模板
        self.save_templates(default_templates)
        return default_templates
    
    def save_templates(self, templates: Optional[Dict[str, Any]] = None):
        """
        保存模板到文件
        
        Args:
            templates: 要保存的模板数据，如果为None则保存当前模板
        """
        try:
            templates_to_save = templates if templates is not None else self.templates
            data = {
                "templates": templates_to_save,
                "last_updated": int(time.time())
            }
            
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存模板失败: {e}")
    
    def get_template_list(self) -> List[Dict[str, Any]]:
        """
        获取模板列表
        
        Returns:
            模板信息列表
        """
        template_list = []
        for template_id, template_data in self.templates.items():
            template_list.append({
                'id': template_id,
                'name': template_data.get('name', template_id),
                'description': template_data.get('description', ''),
                'created_time': template_data.get('created_time', 0)
            })
        
        # 按创建时间排序
        template_list.sort(key=lambda x: x['created_time'], reverse=True)
        return template_list
    
    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            模板数据，如果不存在返回None
        """
        return self.templates.get(template_id)
    
    def apply_template_to_page(self, page_tag_manager, template_id: str, 
                              merge_mode: bool = True) -> bool:
        """
        将模板应用到分页
        
        Args:
            page_tag_manager: 分页标签管理器实例
            template_id: 模板ID
            merge_mode: 合并模式（True）还是覆盖模式（False）
            
        Returns:
            是否应用成功
        """
        try:
            if template_id not in self.templates:
                print(f"模板不存在: {template_id}")
                return False
            
            template = self.templates[template_id]
            template_tags = template.get('tags', {})
            
            if not merge_mode:
                # 覆盖模式：清除现有标签选中状态
                page_tag_manager.clear_all_selections()
            
            # 应用模板标签
            for tag_type in ['head', 'tail']:
                if tag_type in template_tags:
                    for tab_name, tab_tags in template_tags[tag_type].items():
                        for tag_name, tag_data in tab_tags.items():
                            # 准备标签数据
                            new_tag_data = {
                                'en': tag_data.get('en', tag_name),
                                'selected': False,  # 默认不选中
                                'usage_count': 0,
                                'image': tag_data.get('image', ''),
                                'url': tag_data.get('url', ''),
                                'title': tag_data.get('title', ''),
                                'timestamp': int(time.time())
                            }
                            
                            # 检查是否已存在
                            existing_data = page_tag_manager.get_tag_data(tag_type, tab_name, tag_name)
                            if existing_data is None or not merge_mode:
                                # 不存在或覆盖模式：添加标签
                                page_tag_manager.add_tag(tag_type, tab_name, tag_name, new_tag_data)
                            # 存在且合并模式：保持现有标签不变
            
            return True
        except Exception as e:
            print(f"应用模板失败: {e}")
            return False
    
    def create_template_from_page(self, page_tag_manager, template_id: str, 
                                 name: str, description: str = "") -> bool:
        """
        从分页创建新模板
        
        Args:
            page_tag_manager: 分页标签管理器实例
            template_id: 新模板ID
            name: 模板名称
            description: 模板描述
            
        Returns:
            是否创建成功
        """
        try:
            if template_id in self.templates:
                print(f"模板已存在: {template_id}")
                return False
            
            # 从分页导出标签数据
            page_tags = page_tag_manager.export_data()
            
            # 清理数据：移除选中状态和使用次数
            template_tags = {'head': {}, 'tail': {}}
            for tag_type in ['head', 'tail']:
                if tag_type in page_tags:
                    template_tags[tag_type] = {}
                    for tab_name, tab_tags in page_tags[tag_type].items():
                        template_tags[tag_type][tab_name] = {}
                        for tag_name, tag_data in tab_tags.items():
                            # 只保留基础信息，移除运行时状态
                            clean_data = {
                                'en': tag_data.get('en', tag_name),
                                'image': tag_data.get('image', ''),
                                'url': tag_data.get('url', ''),
                                'title': tag_data.get('title', '')
                            }
                            template_tags[tag_type][tab_name][tag_name] = clean_data
            
            # 创建新模板
            self.templates[template_id] = {
                'name': name,
                'description': description,
                'created_time': int(time.time()),
                'tags': template_tags
            }
            
            # 保存模板
            self.save_templates()
            return True
        except Exception as e:
            print(f"创建模板失败: {e}")
            return False
    
    def update_template(self, template_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新模板信息
        
        Args:
            template_id: 模板ID
            updates: 要更新的数据
            
        Returns:
            是否更新成功
        """
        try:
            if template_id not in self.templates:
                return False
            
            self.templates[template_id].update(updates)
            self.save_templates()
            return True
        except Exception as e:
            print(f"更新模板失败: {e}")
            return False
    
    def delete_template(self, template_id: str) -> bool:
        """
        删除模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            是否删除成功
        """
        try:
            if template_id in self.templates:
                # 不允许删除默认模板
                if template_id == 'default':
                    print("不能删除默认模板")
                    return False
                
                del self.templates[template_id]
                self.save_templates()
                return True
            return False
        except Exception as e:
            print(f"删除模板失败: {e}")
            return False
    
    def duplicate_template(self, source_template_id: str, new_template_id: str, 
                          new_name: str) -> bool:
        """
        复制模板
        
        Args:
            source_template_id: 源模板ID
            new_template_id: 新模板ID
            new_name: 新模板名称
            
        Returns:
            是否复制成功
        """
        try:
            if source_template_id not in self.templates:
                return False
            
            if new_template_id in self.templates:
                print(f"模板已存在: {new_template_id}")
                return False
            
            # 深拷贝源模板
            source_template = deepcopy(self.templates[source_template_id])
            source_template['name'] = new_name
            source_template['created_time'] = int(time.time())
            
            self.templates[new_template_id] = source_template
            self.save_templates()
            return True
        except Exception as e:
            print(f"复制模板失败: {e}")
            return False
    
    def export_template(self, template_id: str, export_file: str) -> bool:
        """
        导出模板到文件
        
        Args:
            template_id: 模板ID
            export_file: 导出文件路径
            
        Returns:
            是否导出成功
        """
        try:
            if template_id not in self.templates:
                return False
            
            export_data = {
                'template': {
                    template_id: self.templates[template_id]
                },
                'export_time': int(time.time()),
                'version': '1.0'
            }
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"导出模板失败: {e}")
            return False
    
    def import_template(self, import_file: str, overwrite: bool = False) -> List[str]:
        """
        从文件导入模板
        
        Args:
            import_file: 导入文件路径
            overwrite: 是否覆盖已存在的模板
            
        Returns:
            成功导入的模板ID列表
        """
        imported_templates = []
        try:
            with open(import_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            templates_to_import = import_data.get('template', {})
            
            for template_id, template_data in templates_to_import.items():
                if template_id in self.templates and not overwrite:
                    print(f"模板已存在，跳过: {template_id}")
                    continue
                
                self.templates[template_id] = template_data
                imported_templates.append(template_id)
            
            if imported_templates:
                self.save_templates()
            
        except Exception as e:
            print(f"导入模板失败: {e}")
        
        return imported_templates
    
    def get_template_statistics(self) -> Dict[str, Any]:
        """
        获取模板统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            'total_templates': len(self.templates),
            'templates': []
        }
        
        for template_id, template_data in self.templates.items():
            template_tags = template_data.get('tags', {})
            head_count = sum(len(tab_tags) for tab_tags in template_tags.get('head', {}).values())
            tail_count = sum(len(tab_tags) for tab_tags in template_tags.get('tail', {}).values())
            
            stats['templates'].append({
                'id': template_id,
                'name': template_data.get('name', template_id),
                'head_tags': head_count,
                'tail_tags': tail_count,
                'total_tags': head_count + tail_count,
                'created_time': template_data.get('created_time', 0)
            })
        
        return stats