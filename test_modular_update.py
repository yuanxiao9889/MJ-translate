#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试模块化更新功能
验证新的独立更新对话框模块是否正常工作
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
import customtkinter as ctk
from views.update_dialog import open_update_dialog

def main():
    """主函数"""
    # 设置customtkinter主题
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    
    # 创建主窗口
    root = ctk.CTk()
    root.title("模块化更新功能测试")
    root.geometry("400x200")
    
    # 居中显示
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")
    
    # 创建主框架
    main_frame = ctk.CTkFrame(root)
    main_frame.pack(fill="both", expand=True, padx=20, pady=20)
    
    # 标题
    title_label = ctk.CTkLabel(main_frame, text="模块化更新功能测试", 
                              font=("微软雅黑", 16, "bold"))
    title_label.pack(pady=(20, 30))
    
    # 说明文字
    info_label = ctk.CTkLabel(main_frame, 
                             text="点击下面的按钮测试新的模块化更新功能", 
                             font=("微软雅黑", 12))
    info_label.pack(pady=(0, 20))
    
    # 测试按钮
    test_button = ctk.CTkButton(main_frame, 
                               text="🔄 打开更新对话框", 
                               font=("微软雅黑", 14),
                               fg_color="#28a745",
                               command=lambda: open_update_dialog(root))
    test_button.pack(pady=10)
    
    # 退出按钮
    exit_button = ctk.CTkButton(main_frame, 
                               text="退出", 
                               font=("微软雅黑", 12),
                               fg_color="#6c757d",
                               command=root.quit)
    exit_button.pack(pady=(20, 0))
    
    print("✅ 模块化更新功能测试工具已启动")
    print("📦 测试新的独立更新对话框模块")
    
    # 运行主循环
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        input("按任意键退出...")