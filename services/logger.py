"""统一的错误处理和日志记录模块

提供标准化的日志记录、错误处理和用户通知功能，
避免在各个模块中重复实现相同的错误处理逻辑。
"""

import os
import sys
import logging
import traceback
import datetime
from typing import Optional, Callable, Any
from functools import wraps

try:
    from tkinter import messagebox
except ImportError:
    messagebox = None


class MJTranslatorLogger:
    """MJ Translator专用日志记录器"""
    
    def __init__(self, name: str = "mj_translator", log_dir: str = "logs"):
        self.name = name
        self.log_dir = log_dir
        self.logger = None
        self._setup_logger()
    
    def _setup_logger(self):
        """设置日志记录器"""
        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 创建logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重复添加handler
        if self.logger.handlers:
            return
        
        # 创建文件handler
        log_file = os.path.join(self.log_dir, f"{self.name}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 创建控制台handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加handler
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str, **kwargs):
        """记录调试信息"""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """记录一般信息"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """记录警告信息"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, exc_info: bool = True, **kwargs):
        """记录错误信息"""
        self.logger.error(message, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, exc_info: bool = True, **kwargs):
        """记录严重错误信息"""
        self.logger.critical(message, exc_info=exc_info, **kwargs)


# 全局日志记录器实例
logger = MJTranslatorLogger()


def log_exception(func: Callable) -> Callable:
    """装饰器：自动记录函数执行中的异常"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"函数 {func.__name__} 执行失败: {str(e)}")
            raise
    return wrapper


def safe_execute(func: Callable, *args, default_return: Any = None, 
                 log_error: bool = True, show_error: bool = False, 
                 error_title: str = "错误", **kwargs) -> Any:
    """安全执行函数，捕获异常并提供错误处理
    
    Args:
        func: 要执行的函数
        *args: 函数参数
        default_return: 异常时的默认返回值
        log_error: 是否记录错误日志
        show_error: 是否显示错误对话框
        error_title: 错误对话框标题
        **kwargs: 函数关键字参数
    
    Returns:
        函数执行结果或默认返回值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_msg = f"执行 {func.__name__} 时发生错误: {str(e)}"
        
        if log_error:
            logger.error(error_msg)
        
        if show_error and messagebox:
            messagebox.showerror(error_title, error_msg)
        
        return default_return


def handle_api_error(platform: str, error: Exception, api_index: Optional[int] = None) -> str:
    """处理API调用错误，返回用户友好的错误信息
    
    Args:
        platform: API平台名称
        error: 异常对象
        api_index: API索引（用于标记禁用）
    
    Returns:
        str: 用户友好的错误信息
    """
    error_msg = str(error)
    
    # 记录详细错误信息
    logger.error(f"{platform} API调用失败 (索引: {api_index}): {error_msg}")
    
    # 根据错误类型返回友好信息
    if "timeout" in error_msg.lower():
        return f"[{platform}] 请求超时，请检查网络连接"
    elif "connection" in error_msg.lower():
        return f"[{platform}] 网络连接失败"
    elif "401" in error_msg or "unauthorized" in error_msg.lower():
        return f"[{platform}] API密钥无效或已过期"
    elif "403" in error_msg or "forbidden" in error_msg.lower():
        return f"[{platform}] API访问被拒绝，请检查权限"
    elif "429" in error_msg or "rate limit" in error_msg.lower():
        return f"[{platform}] API调用频率超限，请稍后重试"
    elif "500" in error_msg:
        return f"[{platform}] 服务器内部错误"
    else:
        return f"[{platform}] 调用失败: {error_msg}"


def handle_file_error(operation: str, file_path: str, error: Exception) -> str:
    """处理文件操作错误
    
    Args:
        operation: 操作类型（如 '读取', '写入', '删除'）
        file_path: 文件路径
        error: 异常对象
    
    Returns:
        str: 用户友好的错误信息
    """
    error_msg = str(error)
    
    # 记录详细错误信息
    logger.error(f"文件{operation}失败 {file_path}: {error_msg}")
    
    # 根据错误类型返回友好信息
    if "permission" in error_msg.lower() or "access" in error_msg.lower():
        return f"文件{operation}失败: 权限不足，请检查文件权限"
    elif "not found" in error_msg.lower() or "no such file" in error_msg.lower():
        return f"文件{operation}失败: 文件不存在"
    elif "disk" in error_msg.lower() or "space" in error_msg.lower():
        return f"文件{operation}失败: 磁盘空间不足"
    else:
        return f"文件{operation}失败: {error_msg}"


def show_error_dialog(title: str, message: str, details: Optional[str] = None):
    """显示错误对话框
    
    Args:
        title: 对话框标题
        message: 主要错误信息
        details: 详细错误信息（可选）
    """
    if not messagebox:
        print(f"错误: {title} - {message}")
        if details:
            print(f"详细信息: {details}")
        return
    
    full_message = message
    if details:
        full_message += f"\n\n详细信息:\n{details}"
    
    messagebox.showerror(title, full_message)


def show_warning_dialog(title: str, message: str):
    """显示警告对话框"""
    if not messagebox:
        print(f"警告: {title} - {message}")
        return
    
    messagebox.showwarning(title, message)


def show_info_dialog(title: str, message: str):
    """显示信息对话框"""
    if not messagebox:
        print(f"信息: {title} - {message}")
        return
    
    messagebox.showinfo(title, message)


def create_error_report(error: Exception, context: str = "") -> str:
    """创建详细的错误报告
    
    Args:
        error: 异常对象
        context: 错误上下文信息
    
    Returns:
        str: 格式化的错误报告
    """
    report_lines = [
        f"错误时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"错误类型: {type(error).__name__}",
        f"错误信息: {str(error)}",
    ]
    
    if context:
        report_lines.append(f"错误上下文: {context}")
    
    # 添加堆栈跟踪
    report_lines.append("堆栈跟踪:")
    report_lines.append(traceback.format_exc())
    
    return "\n".join(report_lines)


def cleanup_old_logs(log_dir: str = "logs", max_days: int = 30):
    """清理旧的日志文件
    
    Args:
        log_dir: 日志目录
        max_days: 保留天数
    """
    if not os.path.exists(log_dir):
        return
    
    try:
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=max_days)
        
        for filename in os.listdir(log_dir):
            if not filename.endswith('.log'):
                continue
            
            file_path = os.path.join(log_dir, filename)
            file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            
            if file_time < cutoff_time:
                try:
                    os.remove(file_path)
                    logger.info(f"已删除旧日志文件: {filename}")
                except Exception as e:
                    logger.warning(f"删除日志文件失败 {filename}: {e}")
    
    except Exception as e:
        logger.error(f"清理日志文件时发生错误: {e}")