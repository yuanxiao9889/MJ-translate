#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复后的更新功能测试脚本

测试修复后的更新功能是否能正确处理GitHub Release中的ZIP文件
"""

import tkinter as tk
import customtkinter as ctk
from components.update_progress_dialog import UpdateProgressDialog
from services.update_manager import UpdateManager
import threading
import time


def test_fixed_update():
    """测试修复后的更新功能"""
    
    # 设置CustomTkinter主题
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    
    # 创建主窗口
    root = ctk.CTk()
    root.title("修复后更新功能测试")
    root.geometry("600x500")
    
    # 居中显示
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (600 // 2)
    y = (root.winfo_screenheight() // 2) - (500 // 2)
    root.geometry(f"600x500+{x}+{y}")
    
    # 创建UI
    title_label = ctk.CTkLabel(
        root, 
        text="修复后更新功能测试", 
        font=("微软雅黑", 20, "bold")
    )
    title_label.pack(pady=20)
    
    info_label = ctk.CTkLabel(
        root,
        text="此测试将验证修复后的更新功能是否能正确处理GitHub Release中的ZIP文件。\n\n" +
             "修复内容：\n" +
             "• 优先选择ZIP文件进行下载\n" +
             "• 改进了assets检测逻辑\n" +
             "• 增加了更详细的进度信息\n" +
             "• 更好的错误处理和用户提示\n\n" +
             "如果GitHub Release中有ZIP文件，更新应该能正常进行。",
        font=("微软雅黑", 12),
        justify="left"
    )
    info_label.pack(pady=20)
    
    # 状态显示区域
    status_frame = ctk.CTkFrame(root)
    status_frame.pack(pady=20, padx=20, fill="x")
    
    status_label = ctk.CTkLabel(
        status_frame,
        text="点击下面的按钮开始测试",
        font=("微软雅黑", 12)
    )
    status_label.pack(pady=10)
    
    def check_github_status():
        """检查GitHub Release状态"""
        status_label.configure(text="正在检查GitHub Release状态...")
        
        def check_in_thread():
            try:
                import requests
                api_url = "https://api.github.com/repos/yuanxiao9889/MJ-translate/releases/latest"
                response = requests.get(api_url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    assets = data.get('assets', [])
                    assets_count = len(assets)
                    tag_name = data.get('tag_name', 'N/A')
                    release_name = data.get('name', 'N/A')
                    
                    # 检查ZIP文件
                    zip_assets = [asset for asset in assets if asset['name'].lower().endswith('.zip')]
                    zip_count = len(zip_assets)
                    
                    status_text = f"GitHub Release状态：\n" + \
                                 f"• Tag: {tag_name}\n" + \
                                 f"• Name: {release_name}\n" + \
                                 f"• 总Assets数量: {assets_count}\n" + \
                                 f"• ZIP文件数量: {zip_count}\n"
                    
                    if zip_count > 0:
                        status_text += "\n✅ 找到ZIP文件，更新功能应该能正常工作\n"
                        status_text += "ZIP文件列表:\n"
                        for asset in zip_assets:
                            size_mb = asset.get('size', 0) / (1024 * 1024)
                            status_text += f"  • {asset['name']} ({size_mb:.1f} MB)\n"
                    elif assets_count > 0:
                        status_text += "\n⚠️ 有assets但没有ZIP文件\n"
                        status_text += "Assets列表:\n"
                        for asset in assets[:3]:  # 只显示前3个
                            status_text += f"  • {asset['name']}\n"
                    else:
                        status_text += "\n❌ 没有找到任何assets"
                        
                    root.after(0, lambda: status_label.configure(text=status_text))
                else:
                    root.after(0, lambda: status_label.configure(
                        text=f"❌ GitHub API请求失败: {response.status_code}"
                    ))
                    
            except Exception as e:
                root.after(0, lambda: status_label.configure(
                    text=f"❌ 检查GitHub状态失败: {str(e)}"
                ))
        
        # 在新线程中执行检查
        check_thread = threading.Thread(target=check_in_thread, daemon=True)
        check_thread.start()
    
    def start_real_update_test():
        """开始真实更新测试"""
        status_label.configure(text="正在启动真实更新测试...")
        
        try:
            # 使用真实的更新管理器
            real_updater = UpdateManager()
            
            def on_complete(should_restart):
                """更新完成回调"""
                if should_restart:
                    status_label.configure(text="✅ 更新成功完成！用户选择重启程序")
                    print("更新成功完成，用户选择重启程序")
                else:
                    status_label.configure(text="✅ 更新成功完成！用户选择稍后重启")
                    print("更新成功完成，用户选择稍后重启")
                    
            def on_cancel():
                """更新取消回调"""
                status_label.configure(text="⚠️ 用户取消了更新")
                print("用户取消了更新")
                
            # 显示进度对话框
            progress_dialog = UpdateProgressDialog(root, real_updater)
            
            # 在新线程中启动更新，避免阻塞UI
            def run_update():
                try:
                    progress_dialog.show_progress_dialog(
                        on_complete=on_complete,
                        on_cancel=on_cancel
                    )
                except Exception as e:
                    root.after(0, lambda: status_label.configure(
                        text=f"❌ 更新过程异常: {str(e)}"
                    ))
            
            # 启动更新线程
            update_thread = threading.Thread(target=run_update, daemon=True)
            update_thread.start()
            
            status_label.configure(text="🔄 更新测试进行中...")
            
        except Exception as e:
            status_label.configure(text=f"❌ 测试启动失败: {str(e)}")
            print(f"真实更新测试失败: {e}")
    
    # 按钮框架
    button_frame = ctk.CTkFrame(root, fg_color="transparent")
    button_frame.pack(pady=30)
    
    # 检查状态按钮
    check_btn = ctk.CTkButton(
        button_frame,
        text="🔍 检查GitHub Release状态",
        command=check_github_status,
        font=("微软雅黑", 14),
        width=200,
        height=40,
        fg_color="#17a2b8",
        hover_color="#138496"
    )
    check_btn.pack(side="top", pady=10)
    
    # 测试按钮
    test_btn = ctk.CTkButton(
        button_frame,
        text="🚀 开始真实更新测试",
        command=start_real_update_test,
        font=("微软雅黑", 14),
        width=200,
        height=40,
        fg_color="#28a745",
        hover_color="#218838"
    )
    test_btn.pack(side="top", pady=10)
    
    # 说明文本
    note_label = ctk.CTkLabel(
        root,
        text="注意：如果GitHub Release中确实有ZIP文件，\n更新功能现在应该能正常工作了。",
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
    
    # 运行主循环
    root.mainloop()


if __name__ == "__main__":
    print("启动修复后更新功能测试...")
    test_fixed_update()
    print("测试结束")