"""更新进度对话框组件

提供可视化的更新进度显示，包括：
- 实时进度条
- 详细状态信息
- 取消更新功能
- 错误处理和回滚提示
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import time
from typing import Callable, Optional


class UpdateProgressDialog:
    """更新进度对话框
    
    显示更新过程的详细进度，包括下载、解压、安装等各个阶段。
    """
    
    def __init__(self, parent: tk.Tk, updater):
        self.parent = parent
        self.updater = updater
        self.dialog = None
        self.progress_var = None
        self.status_var = None
        self.progress_bar = None
        self.cancel_requested = False
        self.update_thread = None
        self.is_completed = False
        
    def show_progress_dialog(self, on_complete: Optional[Callable] = None, on_cancel: Optional[Callable] = None):
        """显示进度对话框并开始更新
        
        Args:
            on_complete: 更新完成回调函数
            on_cancel: 取消更新回调函数
        """
        self.on_complete = on_complete
        self.on_cancel = on_cancel
        
        # 创建模态对话框
        self.dialog = ctk.CTkToplevel(self.parent)
        self.dialog.title("正在更新")
        self.dialog.geometry("500x300")
        self.dialog.resizable(False, False)
        
        # 设置为模态对话框
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (300 // 2)
        self.dialog.geometry(f"500x300+{x}+{y}")
        
        # 防止用户关闭对话框
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_dialog_close)
        
        self._create_ui()
        self._start_update_process()
        
    def _create_ui(self):
        """创建UI组件"""
        # 主容器
        main_frame = ctk.CTkFrame(self.dialog)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 标题
        title_label = ctk.CTkLabel(
            main_frame, 
            text="🔄 正在更新程序", 
            font=("微软雅黑", 18, "bold")
        )
        title_label.pack(pady=(20, 10))
        
        # 状态信息
        self.status_var = tk.StringVar(value="准备开始更新...")
        status_label = ctk.CTkLabel(
            main_frame, 
            textvariable=self.status_var,
            font=("微软雅黑", 12)
        )
        status_label.pack(pady=(0, 20))
        
        # 进度条
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(
            main_frame, 
            variable=self.progress_var,
            width=400,
            height=20
        )
        self.progress_bar.pack(pady=(0, 10))
        
        # 进度百分比
        self.progress_text = ctk.CTkLabel(
            main_frame,
            text="0%",
            font=("微软雅黑", 10)
        )
        self.progress_text.pack(pady=(0, 20))
        
        # 详细信息文本框
        self.detail_text = ctk.CTkTextbox(
            main_frame,
            width=450,
            height=80,
            font=("Consolas", 9)
        )
        self.detail_text.pack(pady=(0, 20))
        
        # 按钮框架
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(0, 10))
        
        # 取消按钮
        self.cancel_btn = ctk.CTkButton(
            button_frame,
            text="取消更新",
            fg_color="#dc3545",
            hover_color="#c82333",
            command=self._cancel_update
        )
        self.cancel_btn.pack(side="right")
        
        # 最小化按钮
        minimize_btn = ctk.CTkButton(
            button_frame,
            text="最小化",
            fg_color="#6c757d",
            hover_color="#5a6268",
            command=self._minimize_dialog
        )
        minimize_btn.pack(side="right", padx=(0, 10))
        
    def _start_update_process(self):
        """开始更新过程"""
        self.update_thread = threading.Thread(target=self._update_worker, daemon=True)
        self.update_thread.start()
        
    def _update_worker(self):
        """更新工作线程"""
        try:
            # 首先检查是否有新版本
            latest_version, release_notes = self.updater.check_for_updates()
            if not latest_version:
                self._update_progress(100, "❌ 检查更新失败", "无法获取最新版本信息")
                self._show_error("检查更新失败", "无法获取最新版本信息，请检查网络连接。")
                return
            
            if not self.updater.is_new_version_available(latest_version):
                self._update_progress(100, "✅ 已是最新版本", f"当前版本 {self.updater.current_version} 已是最新")
                self._show_error("无需更新", "当前已是最新版本。")
                return
                
            # 定义进度回调函数
            def progress_callback(progress, status, detail):
                if self.cancel_requested:
                    # 如果用户取消了更新，抛出异常来中断更新过程
                    raise InterruptedError("用户取消了更新")
                    
                # 根据状态添加合适的图标
                status_icons = {
                    "检查更新": "🔍",
                    "准备更新": "📋", 
                    "创建备份": "💾",
                    "下载更新": "⬇️",
                    "下载中": "📥",
                    "下载完成": "✅",
                    "解压文件": "📦",
                    "分析文件": "🔍",
                    "应用更新": "🔧",
                    "复制文件": "📁",
                    "清理文件": "🧹",
                    "更新完成": "🎉",
                    "更新失败": "❌",
                    "回滚中": "↩️",
                    "回滚完成": "✅"
                }
                
                icon = status_icons.get(status, "⚙️")
                formatted_status = f"{icon} {status}"
                
                self._update_progress(progress, formatted_status, detail)
            
            # 执行更新，传入进度回调
            update_success = self.updater.download_and_apply_update(progress_callback)
            
            if update_success:
                self.is_completed = True
                self._disable_cancel_button()
                
                # 延迟显示完成对话框
                self.dialog.after(1000, lambda: self._show_completion_dialog(latest_version))
            else:
                self._show_error("更新失败", "更新过程中发生错误，程序已自动回滚到之前版本。")
                
        except InterruptedError:
            # 用户取消更新，不显示错误
            self._update_progress(100, "❌ 更新已取消", "用户取消了更新操作")
            if self.on_cancel:
                self.on_cancel()
            self.dialog.after(1000, self.dialog.destroy)
            
        except Exception as e:
            error_msg = str(e)
            if "GitHub Release中没有找到可下载的文件" in error_msg:
                self._update_progress(100, "❌ 更新失败", "GitHub Release中没有可下载的文件")
                self._show_error(
                    "更新失败", 
                    "GitHub Release中没有找到可下载的更新文件。\n\n" +
                    "这通常是因为：\n" +
                    "• 开发者还没有上传更新文件到Release\n" +
                    "• Release只包含源代码，没有编译好的程序\n\n" +
                    "请联系开发者或稍后再试。"
                )
            else:
                self._update_progress(100, "❌ 更新异常", f"发生异常: {error_msg}")
                self._show_error("更新异常", f"更新过程中发生异常：{error_msg}")
            
    def _update_progress(self, progress: int, status: str, detail: str):
        """更新进度显示
        
        Args:
            progress: 进度百分比 (0-100)
            status: 状态文本
            detail: 详细信息
        """
        def update_ui():
            self.progress_var.set(progress / 100.0)
            self.status_var.set(status)
            self.progress_text.configure(text=f"{progress}%")
            
            # 添加详细信息到文本框
            current_time = time.strftime("%H:%M:%S")
            self.detail_text.insert("end", f"[{current_time}] {detail}\n")
            self.detail_text.see("end")
            
        # 在主线程中更新UI
        self.dialog.after(0, update_ui)
        
    def _cancel_update(self):
        """取消更新"""
        if self.is_completed:
            self.dialog.destroy()
            return
            
        if messagebox.askyesno("确认取消", "确定要取消更新吗？\n\n取消后将保持当前版本。", parent=self.dialog):
            self.cancel_requested = True
            self._update_progress(100, "❌ 用户取消更新", "更新已被用户取消")
            
            if self.on_cancel:
                self.on_cancel()
                
            self.dialog.after(1000, self.dialog.destroy)
            
    def _minimize_dialog(self):
        """最小化对话框"""
        self.dialog.iconify()
        
    def _disable_cancel_button(self):
        """禁用取消按钮"""
        self.cancel_btn.configure(text="更新完成", state="disabled")
        
    def _show_completion_dialog(self, version: str):
        """显示完成对话框"""
        result = messagebox.askyesno(
            "更新完成", 
            f"🎉 成功更新到版本 {version}！\n\n程序将在您下次启动时使用新版本。\n\n是否现在重启程序以使用新功能？",
            parent=self.dialog
        )
        
        if self.on_complete:
            self.on_complete(result)  # 传递是否重启的选择
            
        self.dialog.destroy()
        
    def _show_error(self, title: str, message: str):
        """显示错误对话框"""
        def show_error_dialog():
            messagebox.showerror(title, message, parent=self.dialog)
            self.dialog.destroy()
            
        self.dialog.after(1000, show_error_dialog)
        
    def _on_dialog_close(self):
        """处理对话框关闭事件"""
        if not self.is_completed:
            self._cancel_update()
        else:
            self.dialog.destroy()