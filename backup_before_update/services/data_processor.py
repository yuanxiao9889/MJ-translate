"""数据处理服务模块

该模块处理标签数据的合并、保存和UI刷新触发等操作。
"""

import os
import json
import threading
from typing import Dict, Any


def process_web_inbox_data(root=None):
    """处理浏览器传过来的截图数据
    
    该函数检查web_inbox.jsonl文件是否存在，如果存在则读取其中的截图数据
    并将图片复制到images目录，创建相应的标签，然后删除已处理的数据。
    """
    # 使用与bridge.py相同的路径计算方式
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inbox_file = os.path.join(project_root, "web_inbox.jsonl")
    
    if not os.path.exists(inbox_file):
        return
    
    try:
        # 读取inbox数据
        processed_items = []
        with open(inbox_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # 如果有截图文件，处理图片和标签
                    if data.get("imageFile") and os.path.exists(data["imageFile"]):
                        print(f"[process_web_inbox_data] 发现截图: {data['imageFile']}")
                        
                        # 处理图片：复制到images目录并创建标签
                        image_path = data["imageFile"]
                        label_name = data.get("label", "浏览器截图")
                        text = data.get("text", "")
                        
                        # 复制图片到images目录
                        import shutil
                        import uuid
                        
                        # 确保images目录存在
                        images_dir = os.path.join(project_root, "images")
                        if not os.path.exists(images_dir):
                            os.makedirs(images_dir)
                        
                        # 生成新的文件名（保持与本地标签相同的命名规则：中文标签名+时间戳）
                        original_filename = os.path.basename(image_path)
                        name_part, ext = os.path.splitext(original_filename)
                        
                        # 始终使用"中文标签名_时间戳"格式，与本地创建的标签保持一致
                        import time
                        new_filename = f"{label_name}_{int(time.time())}{ext}"
                        
                        new_image_path = os.path.join(images_dir, new_filename)
                        
                        # 复制图片文件
                        try:
                            shutil.copy2(image_path, new_image_path)
                            print(f"[process_web_inbox_data] 图片已复制到: {new_image_path}")
                            
                            # 创建标签
                            if root and hasattr(root, 'create_tag_from_browser_data'):
                                try:
                                    root.create_tag_from_browser_data(label_name, new_image_path, text)
                                    print(f"[process_web_inbox_data] 标签已创建: {label_name}")
                                except Exception as e:
                                    print(f"[process_web_inbox_data] 创建标签时出错: {e}")
                            else:
                                # 如果没有create_tag_from_browser_data方法，直接修改tags.json
                                create_tag_in_json(label_name, new_image_path, project_root)
                                
                        except Exception as e:
                            print(f"[process_web_inbox_data] 复制图片时出错: {e}")
                        
                        # 如果有root对象，尝试在UI中显示截图
                        if root and hasattr(root, 'show_browser_screenshot'):
                            try:
                                root.show_browser_screenshot(data["imageFile"], data.get("text", ""))
                            except Exception as e:
                                print(f"[process_web_inbox_data] 显示截图时出错: {e}")
                    
                    processed_items.append(data)
                    
                except json.JSONDecodeError as e:
                    print(f"[process_web_inbox_data] 解析第{line_num}行JSON时出错: {e}")
                    continue
        
        # 如果处理了数据，重写文件（只保留未处理的数据）
        if processed_items:
            # 这里简单起见，直接清空文件
            # 在实际应用中，可能需要更复杂的逻辑来只删除已处理的数据
            with open(inbox_file, 'w', encoding='utf-8') as f:
                f.write("")
            
            print(f"[process_web_inbox_data] 处理了{len(processed_items)}条截图数据")
            
            # 触发UI刷新
            if root and hasattr(root, 'refresh_tags_ui'):
                try:
                    tags_file = os.path.join(project_root, "tags.json")
                    root.refresh_tags_ui(tags_file)
                except Exception as e:
                    print(f"[process_web_inbox_data] 刷新UI时出错: {e}")
        
    except Exception as e:
        print(f"[process_web_inbox_data] 处理inbox数据时出错: {e}")


def create_tag_in_json(label_name, image_path, project_root):
    """直接在tags.json中创建标签
    
    当UI不可用时，直接修改tags.json文件来创建标签。
    """
    try:
        tags_file = os.path.join(project_root, "tags.json")
        
        # 读取现有标签数据
        tags_data = {}
        if os.path.exists(tags_file):
            with open(tags_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)
        
        # 确保基本结构存在
        if "head" not in tags_data:
            tags_data["head"] = {}
        if "tail" not in tags_data:
            tags_data["tail"] = {}
        
        # 确定标签类型和分类（默认添加到head的基础分类中）
        tag_type = "head"
        category = "基础"
        
        if tag_type not in tags_data:
            tags_data[tag_type] = {}
        if category not in tags_data[tag_type]:
            tags_data[tag_type][category] = {}
        
        # 创建新标签
        # 处理图片路径：保存相对路径
        relative_image_path = image_path
        if image_path and os.path.isabs(image_path):
            try:
                relative_image_path = os.path.relpath(image_path, os.getcwd()).replace('\\', '/')
            except ValueError:
                # 如果无法转换为相对路径，保持绝对路径
                relative_image_path = image_path
        elif image_path:
            relative_image_path = image_path.replace('\\', '/')
            
        new_tag = {
            "en": label_name,  # 使用中文标签名作为英文提示词
            "image": relative_image_path,
            "usage_count": 0
        }
        
        # 添加标签（如果不存在）
        if label_name not in tags_data[tag_type][category]:
            tags_data[tag_type][category][label_name] = new_tag
            print(f"[create_tag_in_json] 标签已添加到tags.json: {label_name}")
        else:
            print(f"[create_tag_in_json] 标签已存在，跳过: {label_name}")
        
        # 保存标签数据
        with open(tags_file, 'w', encoding='utf-8') as f:
            json.dump(tags_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"[create_tag_in_json] 创建标签时出错: {e}")


def process_pending_data():
    """处理暂存的标签数据并合并到主标签文件中
    
    该函数检查pending_tags.json文件是否存在，如果存在则将其内容
    与tags.json合并，然后删除暂存文件并触发UI刷新。
    """
    # 使用绝对路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pending_file = os.path.join(project_root, "pending_tags.json")
    main_file = os.path.join(project_root, "tags.json")
    
    if not os.path.exists(pending_file):
        return
    
    try:
        # 读取暂存数据
        with open(pending_file, 'r', encoding='utf-8') as f:
            pending_data = json.load(f)
        
        # 读取主数据
        main_data = {}
        if os.path.exists(main_file):
            with open(main_file, 'r', encoding='utf-8') as f:
                main_data = json.load(f)
        
        # 合并数据
        for tag_type in ["head", "tail"]:
            if tag_type in pending_data:
                if tag_type not in main_data:
                    main_data[tag_type] = {}
                
                for tab_name, tab_data in pending_data[tag_type].items():
                    if tab_name not in main_data[tag_type]:
                        main_data[tag_type][tab_name] = {}
                    
                    for tag_name, tag_info in tab_data.items():
                        # 如果标签已存在，保留使用计数
                        if tag_name in main_data[tag_type][tab_name]:
                            existing = main_data[tag_type][tab_name][tag_name]
                            if isinstance(existing, dict) and "usage_count" in existing:
                                tag_info["usage_count"] = existing["usage_count"]
                        
                        main_data[tag_type][tab_name][tag_name] = tag_info
        
        # 保存合并后的数据
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2)
        
        # 删除暂存文件
        os.remove(pending_file)
        
        print(f"[process_pending_data] 数据合并完成，已删除暂存文件")
        
    except Exception as e:
        print(f"[process_pending_data] 处理暂存数据时出错: {e}")