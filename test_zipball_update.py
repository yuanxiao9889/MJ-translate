#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试使用GitHub zipball_url的更新功能

验证修复后的更新功能是否能正确使用GitHub自动生成的源代码ZIP文件
"""

import tkinter as tk
import customtkinter as ctk
from components.update_progress_dialog import UpdateProgressDialog
from services.update_manager import UpdateManager
import threading
import time
import requests


def test_zipball_update():
    """测试使用zipball的更新功能"""
    
    # 设置CustomTkinter主题
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    
    # 创建主窗口
    root = ctk.CTk()
    root.title("GitHub Zipball更新功能测试")
    root.geometry("700x600")
    
    # 居中显示
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (700 // 2)
    y = (root.winfo_screenheight() // 2) - (600 // 2)
    root.geometry(f"700x600+{x}+{y}")
    
    # 创建UI
    title_label = ctk.CTkLabel(
        root, 
        text="GitHub Zipball更新功能测试", 
        font=("微软雅黑", 20, "bold")
    )
    title_label.pack(pady=20)
    
    info_label = ctk.CTkLabel(
        root,
        text="此测试验证修复后的更新功能是否能正确使用GitHub自动生成的源代码ZIP文件。\n\n" +
             "修复说明：\n" +
             "• GitHub Release页面显示的ZIP文件实际上是GitHub自动生成的源代码压缩包\n" +
             "• 这些文件通过zipball_url提供，而不是assets API\n" +
             "• 修复后的UpdateManager现在能正确处理这种情况\n\n" +
             "测试流程：\n" +
             "1. 检查GitHub Release的zipball_url\n" +
             "2. 验证更新功能能否正确下载和处理源代码ZIP\n" +
             "3. 确认更新过程的用户体验",
        font=("微软雅黑", 12),
        justify="left"
    )
    info_label.pack(pady=20)
    
    # 状态显示区域
    status_frame = ctk.CTkFrame(root)
    status_frame.pack(pady=20, padx=20, fill="both", expand=True)
    
    status_text = ctk.CTkTextbox(
        status_frame,
        font=("微软雅黑", 11),
        wrap="word"
    )
    status_text.pack(pady=10, padx=10, fill="both", expand=True)
    
    def log_status(message):
        """添加状态日志"""
        current_time = time.strftime("%H:%M:%S")
        status_text.insert("end", f"[{current_time}] {message}\n")
        status_text.see("end")
        root.update_idletasks()
    
    def check_zipball_url():
        """检查GitHub Release的zipball_url"""
        log_status("开始检查GitHub Release的zipball_url...")
        
        def check_in_thread():
            try:
                api_url = "https://api.github.com/repos/yuanxiao9889/MJ-translate/releases/latest"
                headers = {
                    'User-Agent': 'MJ-translate-updater/1.0',
                    'Accept': 'application/vnd.github.v3+json'
                }
                
                response = requests.get(api_url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    tag_name = data.get('tag_name', 'N/A')
                    release_name = data.get('name', 'N/A')
                    zipball_url = data.get('zipball_url', 'N/A')
                    assets_count = len(data.get('assets', []))
                    
                    root.after(0, lambda: log_status(f"✅ 成功获取Release信息"))
                    root.after(0, lambda: log_status(f"   Tag: {tag_name}"))
                    root.after(0, lambda: log_status(f"   Name: {release_name}"))
                    root.after(0, lambda: log_status(f"   Assets数量: {assets_count}"))
                    root.after(0, lambda: log_status(f"   Zipball URL: {zipball_url}"))
                    
                    if zipball_url and zipball_url != 'N/A':
                        root.after(0, lambda: log_status("✅ 找到zipball_url，更新功能应该能正常工作"))
                        
                        # 测试zipball_url是否可访问
                        root.after(0, lambda: log_status("正在测试zipball_url的可访问性..."))
                        test_response = requests.head(zipball_url, headers=headers, timeout=15)
                        if test_response.status_code == 200:
                            content_length = test_response.headers.get('content-length', '未知')
                            root.after(0, lambda: log_status(f"✅ zipball_url可访问，文件大小: {content_length} bytes"))
                        else:
                            root.after(0, lambda: log_status(f"⚠️ zipball_url访问异常: {test_response.status_code}"))
                    else:
                        root.after(0, lambda: log_status("❌ 没有找到zipball_url"))
                        
                else:
                    root.after(0, lambda: log_status(f"❌ GitHub API请求失败: {response.status_code}"))
                    
            except Exception as e:
                root.after(0, lambda: log_status(f"❌ 检查失败: {str(e)}"))
        
        # 在新线程中执行检查
        check_thread = threading.Thread(target=check_in_thread, daemon=True)
        check_thread.start()
    
    def start_zipball_update_test():
        """开始zipball更新测试"""
        log_status("开始zipball更新测试...")
        
        try:
            # 使用真实的更新管理器
            real_updater = UpdateManager()
            
            def on_complete(should_restart):
                """更新完成回调"""
                if should_restart:
                    log_status("✅ 更新成功完成！用户选择重启程序")
                else:
                    log_status("✅ 更新成功完成！用户选择稍后重启")
                    
            def on_cancel():
                """更新取消回调"""
                log_status("⚠️ 用户取消了更新")
                
            # 显示进度对话框
            progress_dialog = UpdateProgressDialog(root, real_updater)
            
            # 在新线程中启动更新，避免阻塞UI
            def run_update():
                try:
                    log_status("启动更新进度对话框...")
                    progress_dialog.show_progress_dialog(
                        on_complete=on_complete,
                        on_cancel=on_cancel
                    )
                except Exception as e:
                    root.after(0, lambda: log_status(f"❌ 更新过程异常: {str(e)}"))
            
            # 启动更新线程
            update_thread = threading.Thread(target=run_update, daemon=True)
            update_thread.start()
            
            log_status("🔄 更新测试进行中，请查看弹出的进度对话框...")
            
        except Exception as e:
            log_status(f"❌ 测试启动失败: {str(e)}")
    
    # 按钮框架
    button_frame = ctk.CTkFrame(root, fg_color="transparent")
    button_frame.pack(pady=20)
    
    # 检查zipball按钮
    check_btn = ctk.CTkButton(
        button_frame,
        text="🔍 检查Zipball URL",
        command=check_zipball_url,
        font=("微软雅黑", 14),
        width=180,
        height=40,
        fg_color="#17a2b8",
        hover_color="#138496"
    )
    check_btn.pack(side="left", padx=10)
    
    # 测试按钮
    test_btn = ctk.CTkButton(
        button_frame,
        text="🚀 开始Zipball更新测试",
        command=start_zipball_update_test,
        font=("微软雅黑", 14),
        width=200,
        height=40,
        fg_color="#28a745",
        hover_color="#218838"
    )
    test_btn.pack(side="left", padx=10)
    
    # 清空日志按钮
    clear_btn = ctk.CTkButton(
        button_frame,
        text="🗑️ 清空日志",
        command=lambda: status_text.delete("1.0", "end"),
        font=("微软雅黑", 12),
        width=100,
        height=40,
        fg_color="#ffc107",
        hover_color="#e0a800"
    )
    clear_btn.pack(side="left", padx=10)
    
    # 说明文本
    note_label = ctk.CTkLabel(
        root,
        text="注意：现在更新功能应该能正确使用GitHub自动生成的源代码ZIP文件了。",
        font=("微软雅黑", 10),
        text_color="gray"
    )
    note_label.pack(pady=10)
    
    # 退出按钮
    exit_btn = ctk.CTkButton(
        root,
        text="退出测试",
        command=root.quit,
        font=("微软雅黑", 12),
        width=100,
        height=30,
        fg_color="#6c757d",
        hover_color="#5a6268"
    )
    exit_btn.pack(pady=20)
    
    # 初始日志
    log_status("GitHub Zipball更新功能测试已启动")
    log_status("请先点击'检查Zipball URL'按钮验证GitHub Release状态")
    
    # 运行主循环
    root.mainloop()


if __name__ == "__main__":
    print("启动GitHub Zipball更新功能测试...")
    test_zipball_update()
    print("测试结束")