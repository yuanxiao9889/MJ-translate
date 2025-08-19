"""统一的文件I/O工具模块

提供标准化的文件读写、备份、JSON处理等功能，
避免在各个模块中重复实现相同的文件操作逻辑。
"""

import os
import json
import shutil
import datetime
import hashlib
from typing import Dict, Any, Optional, List


def ensure_dir(path: str) -> None:
    """确保目录存在，如果不存在则创建"""
    os.makedirs(path, exist_ok=True)


def get_file_md5(file_path: str) -> str:
    """计算文件的MD5哈希值"""
    if not os.path.exists(file_path):
        return ""
    
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def safe_json_load(file_path: str, default: Any = None) -> Any:
    """安全地加载JSON文件，失败时返回默认值"""
    if not os.path.exists(file_path):
        return default
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"警告: 加载JSON文件失败 {file_path}: {e}")
        return default


def safe_json_save(file_path: str, data: Any, create_backup: bool = True, max_backups: int = 5) -> bool:
    """安全地保存JSON文件，支持自动备份
    
    Args:
        file_path: 文件路径
        data: 要保存的数据
        create_backup: 是否创建备份
        max_backups: 最大备份数量
    
    Returns:
        bool: 保存是否成功
    """
    try:
        # 确保目录存在
        ensure_dir(os.path.dirname(file_path))
        
        # 创建备份
        if create_backup and os.path.exists(file_path):
            create_file_backup(file_path, max_backups)
        
        # 保存文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"错误: 保存JSON文件失败 {file_path}: {e}")
        return False


def create_file_backup(file_path: str, max_backups: int = 5) -> Optional[str]:
    """为文件创建带时间戳的备份
    
    Args:
        file_path: 原文件路径
        max_backups: 最大备份数量
    
    Returns:
        str: 备份文件路径，失败时返回None
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        # 生成备份文件名
        dir_path = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(dir_path, f"{base_name}_backup_{timestamp}{ext}")
        
        # 创建备份
        shutil.copy2(file_path, backup_path)
        
        # 清理旧备份
        cleanup_old_backups(dir_path, f"{base_name}_backup_", ext, max_backups)
        
        return backup_path
    except Exception as e:
        print(f"警告: 创建备份失败 {file_path}: {e}")
        return None


def cleanup_old_backups(dir_path: str, prefix: str, ext: str, max_backups: int) -> None:
    """清理旧的备份文件"""
    try:
        # 获取所有备份文件
        backup_files = [
            f for f in os.listdir(dir_path)
            if f.startswith(prefix) and f.endswith(ext)
        ]
        
        # 按时间排序（最新的在前）
        backup_files.sort(reverse=True)
        
        # 删除超出数量限制的备份
        for old_backup in backup_files[max_backups:]:
            try:
                os.remove(os.path.join(dir_path, old_backup))
            except Exception:
                pass  # 忽略删除失败的情况
    except Exception:
        pass  # 忽略清理失败的情况


def safe_file_read(file_path: str, encoding: str = "utf-8", default: str = "") -> str:
    """安全地读取文本文件"""
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except Exception as e:
        print(f"警告: 读取文件失败 {file_path}: {e}")
        return default


def safe_file_write(file_path: str, content: str, encoding: str = "utf-8", create_backup: bool = False) -> bool:
    """安全地写入文本文件"""
    try:
        # 确保目录存在
        ensure_dir(os.path.dirname(file_path))
        
        # 创建备份
        if create_backup and os.path.exists(file_path):
            create_file_backup(file_path)
        
        # 写入文件
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"错误: 写入文件失败 {file_path}: {e}")
        return False


def get_file_list(dir_path: str, pattern: str = "*", recursive: bool = False) -> List[str]:
    """获取目录下的文件列表
    
    Args:
        dir_path: 目录路径
        pattern: 文件名模式（支持通配符）
        recursive: 是否递归搜索子目录
    
    Returns:
        List[str]: 文件路径列表
    """
    import glob
    
    if not os.path.exists(dir_path):
        return []
    
    if recursive:
        search_pattern = os.path.join(dir_path, "**", pattern)
        return glob.glob(search_pattern, recursive=True)
    else:
        search_pattern = os.path.join(dir_path, pattern)
        return glob.glob(search_pattern)


def copy_file_safe(src: str, dst: str, create_backup: bool = True) -> bool:
    """安全地复制文件"""
    try:
        # 确保目标目录存在
        ensure_dir(os.path.dirname(dst))
        
        # 创建目标文件备份
        if create_backup and os.path.exists(dst):
            create_file_backup(dst)
        
        # 复制文件
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"错误: 复制文件失败 {src} -> {dst}: {e}")
        return False


def move_file_safe(src: str, dst: str, create_backup: bool = True) -> bool:
    """安全地移动文件"""
    try:
        # 确保目标目录存在
        ensure_dir(os.path.dirname(dst))
        
        # 创建目标文件备份
        if create_backup and os.path.exists(dst):
            create_file_backup(dst)
        
        # 移动文件
        shutil.move(src, dst)
        return True
    except Exception as e:
        print(f"错误: 移动文件失败 {src} -> {dst}: {e}")
        return False