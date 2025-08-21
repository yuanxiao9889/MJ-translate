#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新对话框模块
独立的更新功能界面，避免ui_main.py过于庞大
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
from services.update_manager import UpdateManager
from components.update_progress_dialog import UpdateProgressDialog

# 字体配置
import sys
if sys.platform == "win32":
    default_font = ("微软雅黑", 13)
    title_font = ("微软雅黑", 14, "bold")
else:
    default_font = ("PingFang SC", 13)
    title_font = ("PingFang SC", 14, "bold")

class UpdateDialog:
    """更新对话框类"""
    
    def __init__(self, parent):
        self.parent = parent
        self.updater = UpdateManager()
        self.popup = None
        self.latest_version_var = None
        self.log_text = None
        self.check_button = None
        self.download_button = None
        
    def show(self):
        """显示更新对话框"""
        self.popup = ctk.CTkToplevel(self.parent)
        self.popup.title("软件更新")
        self.popup.geometry("600x500")
        self.popup.transient(self.parent)
        self.popup.grab_set()
        
        # 居中显示
        self.popup.update_idletasks()
        x = (self.popup.winfo_screenwidth() // 2) - (self.popup.winfo_width() // 2)
        y = (self.popup.winfo_screenheight() // 2) - (self.popup.winfo_height() // 2)
        self.popup.geometry(f"+{x}+{y}")
        
        self._setup_ui()
        
    def _setup_ui(self):
        """设置用户界面"""
        main_frame = ctk.CTkFrame(self.popup)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 标题
        title_label = ctk.CTkLabel(main_frame, text="软件更新检查", font=title_font)
        title_label.pack(pady=(0, 20))
        
        # 版本信息框架
        version_frame = ctk.CTkFrame(main_frame)
        version_frame.pack(fill="x", pady=(0, 20))
        
        version_info_frame = ctk.CTkFrame(version_frame)
        version_info_frame.pack(fill="x", padx=15, pady=15)
        
        current_version_label = ctk.CTkLabel(version_info_frame, 
                                           text=f"当前版本: {self.updater.current_version}", 
                                           font=default_font)
        current_version_label.pack(anchor="w", pady=2)
        
        self.latest_version_var = tk.StringVar(value="未检查")
        latest_version_frame = ctk.CTkFrame(version_info_frame, fg_color="transparent")
        latest_version_frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(latest_version_frame, text="最新版本: ", font=default_font).pack(side="left")
        ctk.CTkLabel(latest_version_frame, textvariable=self.latest_version_var, 
                    font=default_font).pack(side="left")
        
        # 按钮框架
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(0, 20))
        
        self.check_button = ctk.CTkButton(button_frame, text="检查更新", 
                                         fg_color="#007bff", command=self._check_for_updates)
        self.check_button.pack(side="left", padx=(0, 10))
        
        self.download_button = ctk.CTkButton(button_frame, text="下载更新", 
                                           fg_color="#28a745", state="disabled",
                                           command=self._download_update)
        self.download_button.pack(side="left", padx=(0, 10))
        
        test_button = ctk.CTkButton(button_frame, text="测试网络", 
                                   fg_color="#6c757d", command=self._test_network)
        test_button.pack(side="left")
        
        # 日志显示区域
        log_frame = ctk.CTkFrame(main_frame)
        log_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        log_label = ctk.CTkLabel(log_frame, text="日志输出:", font=default_font)
        log_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        self.log_text = ctk.CTkTextbox(log_frame, height=200)
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # 关闭按钮
        close_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        close_frame.pack(fill="x")
        
        ctk.CTkButton(close_frame, text="关闭", command=self.popup.destroy, 
                     fg_color="#6c757d", font=default_font).pack(side="right")
        
        # 初始日志
        self._log_message("✅ 更新检查工具已启动")
        self._log_message(f"📦 当前版本: {self.updater.current_version}")
        
    def _log_message(self, message):
        """添加日志消息"""
        if self.log_text:
            self.log_text.insert("end", f"{message}\n")
            self.log_text.see("end")
            self.popup.update_idletasks()
    
    def _check_for_updates(self):
        """检查更新"""
        self.check_button.configure(state="disabled")
        self._log_message("🔍 开始检查更新...")
        
        def check_thread():
            try:
                latest_version, release_notes = self.updater.check_for_updates()
                
                if latest_version:
                    self.latest_version_var.set(latest_version)
                    self._log_message(f"✅ 成功获取最新版本: {latest_version}")
                    
                    if self.updater.is_new_version_available(latest_version):
                        self._log_message(f"🆕 发现新版本可用!")
                        self.download_button.configure(state="normal")
                    else:
                        self._log_message(f"✅ 当前版本已是最新版本")
                        
                    if release_notes:
                        self._log_message(f"📝 发布说明: {release_notes[:200]}...")
                else:
                    self._log_message("❌ 无法获取版本信息")
                    
            except Exception as e:
                self._log_message(f"❌ 检查更新失败: {e}")
            finally:
                self.check_button.configure(state="normal")
                
        threading.Thread(target=check_thread, daemon=True).start()
    
    def _download_update(self):
        """下载更新"""
        self._log_message("📥 准备下载更新...")
        
        try:
            progress_dialog = UpdateProgressDialog(self.popup, self.updater)
            result = progress_dialog.show()
            
            if result:
                self._log_message("✅ 更新下载完成")
                messagebox.showinfo("更新完成", "更新已成功下载并应用！\n请重启应用程序以使用新版本。")
                self.popup.destroy()
            else:
                self._log_message("❌ 更新下载失败或被取消")
                
        except Exception as e:
            self._log_message(f"❌ 更新过程出错: {e}")
            messagebox.showerror("更新错误", f"更新过程中出现错误:\n{e}")
    
    def _test_network(self):
        """测试网络连接"""
        self._log_message("🌐 测试网络连接...")
        
        def test_thread():
            try:
                import requests
                session = requests.Session()
                session.trust_env = False
                session.proxies = {}
                headers = {
                    'User-Agent': 'MJ-Translator-Update-Checker/1.0',
                    'Accept': 'application/vnd.github.v3+json'
                }
                
                repo_owner = self.updater.config.get('github_owner')
                repo_name = self.updater.config.get('github_repo')
                api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
                
                self._log_message(f"🔗 测试连接: {api_url}")
                response = session.get(api_url, headers=headers, timeout=30, proxies={})
                response.raise_for_status()
                
                self._log_message("✅ 网络连接正常")
                self._log_message(f"📊 响应状态: {response.status_code}")
                self._log_message(f"⏱️ 响应时间: {response.elapsed.total_seconds():.2f}秒")
                
            except Exception as e:
                self._log_message(f"❌ 网络连接失败: {e}")
                
        threading.Thread(target=test_thread, daemon=True).start()

def open_update_dialog(parent):
    """打开更新对话框的便捷函数"""
    dialog = UpdateDialog(parent)
    dialog.show()