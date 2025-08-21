#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复后的更新机制

验证以下功能：
1. GitHub Release assets检查
2. zipball_url备用下载
3. 进度回调功能
4. 更新进度对话框
"""

import tkinter as tk
import customtkinter as ctk
from services.update_manager import UpdateManager
from components.update_progress_dialog import UpdateProgressDialog
import threading
import time

class UpdateMechanismTester:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("更新机制测试工具")
        self.root.geometry("600x500")
        
        self.update_manager = UpdateManager()
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        # 主标题
        title_label = ctk.CTkLabel(
            self.root, 
            text="🔧 更新机制测试工具", 
            font=("微软雅黑", 20, "bold")
        )
        title_label.pack(pady=20)
        
        # 信息显示区域
        self.info_text = ctk.CTkTextbox(
            self.root,
            width=550,
            height=200,
            font=("Consolas", 10)
        )
        self.info_text.pack(pady=10)
        
        # 按钮区域
        button_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        button_frame.pack(pady=20)
        
        # 检查GitHub Release按钮
        check_btn = ctk.CTkButton(
            button_frame,
            text="🔍 检查GitHub Release",
            command=self.check_github_release,
            width=200,
            height=40
        )
        check_btn.pack(pady=5)
        
        # 测试进度回调按钮
        progress_btn = ctk.CTkButton(
            button_frame,
            text="📊 测试进度回调",
            command=self.test_progress_callback,
            width=200,
            height=40
        )
        progress_btn.pack(pady=5)
        
        # 启动完整更新测试按钮
        update_btn = ctk.CTkButton(
            button_frame,
            text="🚀 启动完整更新测试",
            command=self.start_full_update_test,
            width=200,
            height=40,
            fg_color="#28a745",
            hover_color="#218838"
        )
        update_btn.pack(pady=5)
        
        # 清空日志按钮
        clear_btn = ctk.CTkButton(
            button_frame,
            text="🗑️ 清空日志",
            command=self.clear_log,
            width=200,
            height=40,
            fg_color="#6c757d",
            hover_color="#5a6268"
        )
        clear_btn.pack(pady=5)
        
    def log(self, message):
        """添加日志信息"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.info_text.insert("end", log_message)
        self.info_text.see("end")
        self.root.update()
        
    def clear_log(self):
        """清空日志"""
        self.info_text.delete("1.0", "end")
        
    def check_github_release(self):
        """检查GitHub Release信息"""
        self.log("开始检查GitHub Release...")
        
        def check_worker():
            try:
                import requests
                repo_owner = self.update_manager.config.get('github_owner')
                repo_name = self.update_manager.config.get('github_repo')
                
                if not repo_owner or not repo_name:
                    self.log("❌ GitHub仓库配置不完整")
                    return
                    
                api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
                self.log(f"请求URL: {api_url}")
                
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                release_data = response.json()
                
                self.log(f"✅ 成功获取Release信息:")
                self.log(f"   Tag: {release_data.get('tag_name', 'N/A')}")
                self.log(f"   Name: {release_data.get('name', 'N/A')}")
                self.log(f"   Assets数量: {len(release_data.get('assets', []))}")
                
                assets = release_data.get('assets', [])
                if assets:
                    self.log("   Assets列表:")
                    for i, asset in enumerate(assets):
                        self.log(f"     {i+1}. {asset['name']} ({asset.get('size', 0)} bytes)")
                else:
                    self.log("   ⚠️ 没有找到用户上传的assets")
                    
                zipball_url = release_data.get('zipball_url')
                if zipball_url:
                    self.log(f"   ✅ Zipball URL: {zipball_url}")
                    
                    # 测试zipball_url的可访问性
                    self.log("   测试zipball_url可访问性...")
                    zipball_response = requests.head(zipball_url, timeout=10)
                    self.log(f"   Zipball响应状态: {zipball_response.status_code}")
                    if zipball_response.status_code in [200, 302]:
                        self.log("   ✅ Zipball URL可访问")
                    else:
                        self.log("   ❌ Zipball URL不可访问")
                else:
                    self.log("   ❌ 没有找到zipball_url")
                    
            except Exception as e:
                self.log(f"❌ 检查失败: {str(e)}")
                
        threading.Thread(target=check_worker, daemon=True).start()
        
    def test_progress_callback(self):
        """测试进度回调功能"""
        self.log("开始测试进度回调功能...")
        
        def progress_callback(progress, status, detail):
            self.log(f"进度回调: {progress}% - {status} - {detail}")
            
        def test_worker():
            try:
                # 模拟各个更新阶段的进度回调
                stages = [
                    (10, "准备更新", "初始化更新环境"),
                    (20, "创建备份", "正在备份当前版本"),
                    (30, "下载更新", "正在下载更新文件"),
                    (50, "下载中", "下载进度50%"),
                    (70, "下载完成", "文件下载完成"),
                    (80, "应用更新", "正在解压和应用更新"),
                    (95, "清理文件", "正在清理临时文件"),
                    (100, "更新完成", "更新已成功应用")
                ]
                
                for progress, status, detail in stages:
                    progress_callback(progress, status, detail)
                    time.sleep(0.5)  # 模拟处理时间
                    
                self.log("✅ 进度回调测试完成")
                
            except Exception as e:
                self.log(f"❌ 进度回调测试失败: {str(e)}")
                
        threading.Thread(target=test_worker, daemon=True).start()
        
    def start_full_update_test(self):
        """启动完整的更新测试"""
        self.log("启动完整更新测试...")
        
        try:
            # 创建更新进度对话框
            progress_dialog = UpdateProgressDialog(self.root, self.update_manager)
            
            def on_complete():
                self.log("✅ 更新测试完成")
                
            def on_cancel():
                self.log("❌ 更新测试被取消")
                
            # 显示进度对话框并开始更新
            progress_dialog.show_progress_dialog(
                on_complete=on_complete,
                on_cancel=on_cancel
            )
            
        except Exception as e:
            self.log(f"❌ 启动更新测试失败: {str(e)}")
            
    def run(self):
        """运行测试工具"""
        self.log("🔧 更新机制测试工具已启动")
        self.log("请选择要执行的测试项目")
        self.log("="*50)
        
        self.root.mainloop()

if __name__ == "__main__":
    print("启动更新机制测试工具...")
    tester = UpdateMechanismTester()
    tester.run()