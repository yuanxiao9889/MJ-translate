# ========= 标准化导入 =========
import os
import json
import threading
import shutil
import datetime

# GUI 库
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

# 项目模块
from services.api import load_api_config, api_config, current_platform, translate_text
from services.tags import load_tags, save_tags
from services.data_processor import process_pending_data
from services.logger import logger, show_error_dialog, show_info_dialog, safe_execute

# 需要的其他导入
import csv
from tkinter import simpledialog
from utils import smart_sync_tags
# ========= 全局变量 =========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# UI相关全局变量
last_typing_time = [0]
last_translation = ""
expand_preset_window = None
tag_edit_window = None
favorite_window = None
history_window_instance = None
PRESET_FILE = "expand_presets.json"
API_TIMEOUT = 40

# ========= UI配置 =========
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")
default_font = ("微软雅黑", 13)
tab_font = ("微软雅黑", 13, "bold")
tag_font = ("微软雅黑", 13, "bold")
tag_block_font = ("微软雅黑", 13, "bold")

# save_tags函数已迁移到services/tags.py，移除重复定义

# save_to_favorites and save_to_history functions moved to views.ui_main module

# flow_layout_canvas function moved to views.ui_main module

# make_scrollable_flow_area function moved to views.ui_main module

# create_tag_btn function moved to views.ui_main module
# The following large function definition has been removed to eliminate code duplication




def export_tags_to_csv():
    tags_data = load_tags()
    csv_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV文件", "*.csv")])
    if not csv_path:
        return
    try:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["类型", "Tab", "中文标签名", "英文提示词", "图片路径"])
            for tag_type in tags_data:
                tab_data = tags_data[tag_type]
                if not isinstance(tab_data, dict):
                    continue
                for tab in tab_data:
                    for zh, tag_info in tab_data[tab].items():
                        # 兼容新旧数据格式
                        if isinstance(tag_info, str):
                            en_text = tag_info
                            img_path = ""
                        else:
                            en_text = tag_info.get("en", "")
                            img_path = tag_info.get("image", "")
                        # 写入数据行
                        writer.writerow([tag_type, tab, zh, en_text, img_path])
        messagebox.showinfo("导出成功", f"已导出至 {csv_path}")
    except PermissionError:
        messagebox.showerror("权限错误", "无法写入文件，请关闭可能占用该文件的程序或选择其他保存位置")
    except Exception as e:
        messagebox.showerror("导出失败", f"发生错误：{str(e)}")

def load_expand_presets():
    """加载扩写预设数据"""
    try:
        if os.path.exists(PRESET_FILE):
            with open(PRESET_FILE, 'r', encoding='utf-8') as f:
                presets = json.load(f)
                # 确保数据格式正确
                if isinstance(presets, list) and all(isinstance(p, dict) and 'title' in p and 'content' in p for p in presets):
                    return presets
        # 如果文件不存在或格式错误，返回默认预设
        return [
            {
                "title": "MJ极简扩写",
                "content": "请将以下内容扩写为适合Midjourney画面描述的精简中文提示词，字数不超过80字，突出主体与氛围，不添加无关修饰。"
            },
            {
                "title": "MJ画面感扩写",
                "content": "请用画面感极强的语言，将下列内容扩写为适合Midjourney的场景描述，突出光影、色彩、构图和艺术风格，字数100字以内。"
            }
        ]
    except Exception as e:
        logger.error(f"加载扩写预设失败: {e}")
        # 返回默认预设
        return [
            {
                "title": "MJ极简扩写",
                "content": "请将以下内容扩写为适合Midjourney画面描述的精简中文提示词，字数不超过80字，突出主体与氛围，不添加无关修饰。"
            }
        ]

def save_expand_presets(presets):
    """保存扩写预设数据"""
    try:
        # 确保数据格式正确
        if isinstance(presets, list) and all(isinstance(p, dict) and 'title' in p and 'content' in p for p in presets):
            with open(PRESET_FILE, 'w', encoding='utf-8') as f:
                json.dump(presets, f, ensure_ascii=False, indent=2)
            logger.info("扩写预设保存成功")
        else:
            logger.error("扩写预设数据格式错误")
    except Exception as e:
        logger.error(f"保存扩写预设失败: {e}")
        show_error_dialog("保存失败", f"无法保存扩写预设：{str(e)}")

def show_expand_preset_dialog(callback=None):
    presets = load_expand_presets()
    win = ctk.CTkToplevel()
    win.attributes('-topmost', True)
    win.title("选择扩写预设")
    win.geometry("540x360")
    win.resizable(True, True)
    win.grid_rowconfigure(0, weight=1)
    win.grid_columnconfigure(0, weight=1)
    sel_idx = [0]

    # 统一字体
    font_bold = ("微软雅黑", 14, "bold")
    font_normal = ("微软雅黑", 12)
    font_btn = ("微软雅黑", 12)

    # ====== 左侧带滑动条的Frame ======
    left_outer = ctk.CTkFrame(win, width=120)
    left_outer.grid(row=0, column=0, sticky="ns", padx=5, pady=5)
    left_outer.grid_rowconfigure(0, weight=1)
    left_canvas = ctk.CTkCanvas(left_outer, width=110, borderwidth=0, highlightthickness=0)
    left_canvas.grid(row=0, column=0, sticky="nswe")
    left_scrollbar = ctk.CTkScrollbar(left_outer, orientation="vertical", command=left_canvas.yview)
    left_scrollbar.grid(row=0, column=1, sticky="ns")
    left_canvas.configure(yscrollcommand=left_scrollbar.set)
    left_frame = ctk.CTkFrame(left_canvas, fg_color="#f3f7fa")
    left_canvas.create_window((0, 0), window=left_frame, anchor="nw")

    # ====== 右侧内容Frame + 滚动条 ======
    right_outer = ctk.CTkFrame(win)
    right_outer.grid(row=0, column=1, sticky="nsew", padx=3, pady=5)
    right_outer.grid_rowconfigure(0, weight=1)
    right_outer.grid_columnconfigure(0, weight=1)
    right_canvas = ctk.CTkCanvas(right_outer, borderwidth=0, highlightthickness=0)
    right_canvas.pack(side="left", fill="both", expand=True)
    right_scrollbar = ctk.CTkScrollbar(right_outer, orientation="vertical", command=right_canvas.yview)
    right_scrollbar.pack(side="right", fill="y")
    right_canvas.configure(yscrollcommand=right_scrollbar.set)
    right_frame = ctk.CTkFrame(right_canvas, fg_color="#f7f7fa")
    right_canvas.create_window((0, 0), window=right_frame, anchor="nw")

    def update_scrollregion(event=None):
        left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        right_canvas.configure(scrollregion=right_canvas.bbox("all"))
    left_frame.bind("<Configure>", update_scrollregion)
    right_frame.bind("<Configure>", update_scrollregion)

    def refresh_left():
        for w in left_frame.winfo_children():
            w.destroy()
        for idx, p in enumerate(presets):
            btn = ctk.CTkButton(left_frame, text=p["title"], width=120,
                font=font_btn,
                fg_color="#3078ef" if idx == sel_idx[0] else "#e3e4e8",
                text_color="white" if idx == sel_idx[0] else "#222",
                command=lambda i=idx: select_idx(i))
            btn.pack(fill="x", pady=1, padx=3)
        ctk.CTkButton(left_frame, text="➕ 新增", font=font_btn, fg_color="#19a8b9", width=120,
                      command=add_preset).pack(fill="x", pady=(10, 1), padx=3)
        if len(presets) > 1:
            ctk.CTkButton(left_frame, text="🗑️ 删除", font=font_btn, fg_color="#fd6767", width=120,
                          command=del_preset).pack(fill="x", pady=1, padx=3)

    def select_idx(i):
        sel_idx[0] = i
        refresh_left()
        refresh_right()

    def refresh_right():
        for w in right_frame.winfo_children():
            w.destroy()
        p = presets[sel_idx[0]]
        ctk.CTkLabel(right_frame, text=p["title"], font=font_bold).pack(anchor="w", pady=(5, 2), padx=6)
        content_box = ctk.CTkTextbox(right_frame, height=90, font=font_normal,
                                     fg_color="#f7f7fa", wrap="word", state="normal")
        content_box.pack(fill="x", pady=6, padx=6)
        content_box.insert("end", p["content"])
        content_box.configure(state="disabled")
        ctk.CTkButton(right_frame, text="使用此预设扩写", font=font_btn,
                      fg_color="#19a8b9", width=170,
                      command=lambda: use_preset(p["content"])).pack(pady=(12, 0), anchor="e", padx=6)

    def use_preset(preset_content):
        win.destroy()
        if callback:
            callback(preset_content)

    def add_preset():
        def do_add():
            title = entry_title.get().strip()
            content = entry_content.get("0.0", "end").strip()
            if not title or not content:
                messagebox.showinfo("提示", "标题和内容都不能为空")
                return
            presets.append({"title": title, "content": content})
            save_expand_presets(presets)
            sel_idx[0] = len(presets) - 1
            top.destroy()
            refresh_left()
            refresh_right()

        top = ctk.CTkToplevel(win)
        top.title("新增扩写预设")
        top.geometry("400x260")
        ctk.CTkLabel(top, text="标题：", font=font_normal).pack(anchor="w", padx=16, pady=(16, 0))
        entry_title = ctk.CTkEntry(top, width=350, font=font_normal)
        entry_title.pack(padx=16, pady=4)
        ctk.CTkLabel(top, text="内容（扩写风格/提示）：", font=font_normal).pack(anchor="w", padx=16, pady=(12, 0))
        entry_content = ctk.CTkTextbox(top, width=350, height=90, font=font_normal)
        entry_content.pack(padx=16, pady=4)
        ctk.CTkButton(top, text="保存", font=font_btn, fg_color="#19a8b9", command=do_add).pack(pady=14)

    def del_preset():
        if len(presets) <= 1:
            return
        idx = sel_idx[0]
        presets.pop(idx)
        save_expand_presets(presets)
        sel_idx[0] = max(0, idx - 1)
        refresh_left()
        refresh_right()

    refresh_left()
    refresh_right()
    win.grab_set()
# --------------------------  已弃用的 start_ui（主要逻辑已迁移至 views/ui_main.py）  ----------------------------
def start_ui(root_param=None):
    """Legacy UI initialization function.

    This function is deprecated. The main UI construction logic has been
    moved to ``views.ui_main.build_ui`` for better modularization. This
    function now only provides backward compatibility and minimal business
    logic setup that hasn't been migrated yet.

    :param root_param: Optional pre-existing root window to attach the UI to.
    :returns: The root window used for the UI.
    """
    global input_text, output_text, root, status_var
    from oss_sync import upload_all, load_tags_with_sync
    from services.data_processor import process_web_inbox_data
    from views.ui_main import build_ui
    
    # 设置 root 为传入的窗口或创建新窗口
    if root_param is None:
        root = ctk.CTk()
    else:
        root = root_param
        
    # 处理暂存数据
    process_pending_data()
    
    # 调用模块化的 UI 构建函数
    build_ui(root)
    
    # 浏览器相关功能（显示截图、浏览器数据创建标签）已迁移至 views/ui_main.py，重复实现已删除。
    
    def refresh_from_cloud():
        smart_sync_tags()
        # 这些函数需要在UI构建后通过root对象调用
        # 在实际使用时会通过views/ui_main.py中的setup_topbar函数重新定义

    def import_tags_from_csv():
        import chardet   # ✅ 新增：导入 chardet 自动识别编码
        global tags_data
        csv_path = filedialog.askopenfilename(filetypes=[("CSV文件", "*.csv")])
        if not csv_path:
            return

        # 🔍 先检测 CSV 文件的编码
        with open(csv_path, "rb") as f:
            raw_data = f.read(4096)  # 只读取前 4KB 就能判断
            result = chardet.detect(raw_data)
            file_encoding = result["encoding"] or "utf-8"  # 识别不到就默认 utf-8
            print(f"检测到文件编码: {file_encoding}")

        new_tags = {"head": {}, "tail": {}}
        try:
            # ✅ 用检测到的编码打开文件（而不是固定 utf-8）
            with open(csv_path, "r", encoding=file_encoding, errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tag_type = row.get("类型", "")
                    tab = row.get("Tab", "")
                    zh = row.get("中文标签名", "")
                    en = row.get("英文提示词", "")
                    img_path = row.get("图片路径", "")
                    
                    if tag_type not in ("head", "tail") or not tab or not zh or not en:
                        continue
                    
                    if tab not in new_tags[tag_type]:
                        new_tags[tag_type][tab] = {}
                    
                    # ✅ 修复：保持正确的数据结构格式
                    entry = {"en": en, "usage_count": 0}
                    if img_path and os.path.exists(img_path):
                        entry["image"] = img_path
                    
                    new_tags[tag_type][tab][zh] = entry

            # ✅ 导入完成后让用户选择覆盖或合并
            if messagebox.askyesno("导入方式", "导入完成，是否全量覆盖现有标签？（否则为合并导入）"):
                tags_data = new_tags
            else:
                for tag_type in new_tags:
                    for tab in new_tags[tag_type]:
                        if tab not in tags_data[tag_type]:
                            tags_data[tag_type][tab] = {}
                        
                        # 只添加新标签，不覆盖已有标签
                        for zh, new_entry in new_tags[tag_type][tab].items():
                            if zh not in tags_data[tag_type][tab]:
                                tags_data[tag_type][tab][zh] = new_entry
                            else:
                                # 如果是旧格式，升级到新的字典格式
                                existing = tags_data[tag_type][tab][zh]
                                if isinstance(existing, str):
                                    tags_data[tag_type][tab][zh] = {
                                        "en": existing,
                                        "usage_count": 0
                                    }

            save_tags(tags_data)
            # refresh_tab_list() # 需要在UI构建后通过root对象调用
            messagebox.showinfo("导入完成", "标签已导入！")

        except Exception as e:
            messagebox.showerror("导入错误", f"导入出错: {e}")

    def open_add_api_popup():
        popup = tk.Toplevel()
        popup.title("新增API账号")
        popup.geometry("350x250")
        popup.resizable(False, False)
        
        tk.Label(popup, text="选择平台：").pack(anchor="w", padx=16, pady=(18, 4))
        plat_var = tk.StringVar(value=list(api_config.keys())[0])
        platform_menu = ttk.Combobox(popup, textvariable=plat_var, values=list(api_config.keys()), state="readonly")
        platform_menu.pack(fill="x", padx=16, pady=2)

        # 动态输入项
        entry_labels = {"baidu": ["App ID", "App Key"], "zhipu": ["API Key"], "zhipu-glm45": ["API Key"]}
        entry_vars = [tk.StringVar(), tk.StringVar()]
        entry_widgets = []

        frame = tk.Frame(popup)
        frame.pack(fill="x", padx=16, pady=12)

        def render_fields(*_):
            # 清空原有输入框
            for w in entry_widgets: w.destroy()
            entry_widgets.clear()
            for i, label in enumerate(entry_labels[plat_var.get()]):
                tk.Label(frame, text=label+":").grid(row=i, column=0, sticky="w", pady=2)
                e = tk.Entry(frame, textvariable=entry_vars[i])
                e.grid(row=i, column=1, sticky="ew", pady=2)
                entry_widgets.append(e)
            for j in range(len(entry_labels[plat_var.get()]), 2):  # 清理多余
                entry_vars[j].set("")
        render_fields()
        platform_menu.bind("<<ComboboxSelected>>", render_fields)

        def on_ok():
            plat = plat_var.get()
            if plat == "baidu":
                v1, v2 = entry_vars[0].get().strip(), entry_vars[1].get().strip()
                if not v1 or not v2:
                    messagebox.showwarning("提示", "请填写完整百度API信息！")
                    return
                api_config["baidu"].append({"app_id": v1, "app_key": v2, "disabled": False})
            elif plat == "zhipu":
                v1 = entry_vars[0].get().strip()
                if not v1:
                    messagebox.showwarning("提示", "请填写智谱API Key！")
                    return
                api_config["zhipu"].append({"api_key": v1, "disabled": False})
            elif plat == "zhipu-glm45":  # 新增GLM-4.5处理
                v1 = entry_vars[0].get().strip()
                if not v1:
                    messagebox.showwarning("提示", "请填写GLM-4.5 API Key！")
                    return
                api_config["zhipu-glm45"].append({"api_key": v1, "disabled": False})
            save_api_config()
            popup.destroy()
            messagebox.showinfo("成功", "API账号已添加！请在平台下拉框切换试用。")
            # 可选：自动刷新平台账号显示
        tk.Button(popup, text="确定添加", command=on_ok, width=16).pack(pady=10)
        tk.Button(popup, text="取消", command=popup.destroy, width=16).pack()

    # 恢复备份按钮
    def open_restore_backup_popup():
        import tkinter.filedialog as filedialog
        import json
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        backup_files = [f for f in os.listdir(script_dir) if f.startswith("tags_backup_") and f.endswith(".json")]
        
        if not backup_files:
            messagebox.showinfo("提示", "没有找到备份文件")
            return
        
        # 创建备份选择对话框
        popup = ctk.CTkToplevel(root)
        popup.title("选择备份文件恢复")
        popup.geometry("500x400")  # 增加窗口高度和宽度
        popup.transient(root)
        popup.grab_set()
        popup.resizable(False, False)  # 禁止调整大小
        
        # 设置窗口居中
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() - popup.winfo_width()) // 2
        y = (popup.winfo_screenheight() - popup.winfo_height()) // 2
        popup.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(popup, text="请选择要恢复的备份文件:", font=default_font).pack(pady=10)
        
        # 创建框架来包含列表框和滚动条
        list_frame = ctk.CTkFrame(popup)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        listbox = tk.Listbox(list_frame, font=default_font, selectmode=tk.SINGLE)
        scrollbar = tk.Scrollbar(list_frame)
        
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)
        
        for file in sorted(backup_files, reverse=True):
            listbox.insert(tk.END, file)
        
        def do_restore():
            if not listbox.curselection():
                messagebox.showinfo("提示", "请先选择备份文件")
                return
            
            selected_file = listbox.get(listbox.curselection())
            file_path = os.path.join(script_dir, selected_file)
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
                
                # 恢复到当前标签文件
                save_tags(backup_data)
                
                # 重新加载标签
                global tags_data
                tags_data = load_tags()
                # refresh_tab_list() # 需要在UI构建后通过root对象调用
                # refresh_head_tags() # 需要在UI构建后通过root对象调用
                # refresh_tail_tags() # 需要在UI构建后通过root对象调用
                
                messagebox.showinfo("成功", f"已从备份 {selected_file} 恢复数据")
                popup.destroy()
            except Exception as e:
                messagebox.showerror("恢复失败", f"无法恢复备份: {str(e)}")
        
        # 按钮框架
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 20))
        
        # 使用grid布局确保按钮居中且不被遮挡
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)
        
        ctk.CTkButton(btn_frame, font=("微软雅黑", 12), text="恢复选中备份", command=do_restore).grid(row=0, column=1, padx=10)
        ctk.CTkButton(btn_frame, font=("微软雅黑", 12), text="取消", command=popup.destroy).grid(row=0, column=2, padx=10)

    tags_data = load_tags()
    inserted_tags = {"head": [], "tail": []}  # 添加mj列表
    last_translation = ""

    # Determine which root to use: either the provided one or create a new CTk
    if root_param is not None:
        root = root_param
    else:
        root = ctk.CTk()

    # Configure root window basics only if we created it here
    if root_param is None:
        root.title("MJ提示词工具")
        # 设置窗口图标
        try:
            root.iconbitmap("mj_icon.ico")
        except Exception as e:
            print(f"设置图标失败: {e}")
    root.geometry("1370x1000")
    root.minsize(950, 650)

    # 初始化状态栏变量和控件
    status_var = tk.StringVar(value="就绪")
    status_bar = ctk.CTkLabel(
        root,
        textvariable=status_var,
        fg_color="#f0f0f0",
        height=25,
        anchor="w",
        font=("微软雅黑", 12)
    )
    status_bar.pack(side="bottom", fill="x", padx=5, pady=2)
    load_api_config()  # 启动时加载API配置
    global platform_var, current_platform
        # ==== 合并顶部栏按钮区 ====
    topbar = ctk.CTkFrame(root, fg_color="#eef5fb")
    topbar.pack(fill="x", padx=0, pady=(0, 4))
    platform_var = tk.StringVar(value=current_platform)
    platforms = list(api_config.keys())

    # 翻译平台选择
    platform_menu = ctk.CTkOptionMenu(topbar, variable=platform_var, values=platforms,
                                      command=lambda val: globals().__setitem__('current_platform', val))
    platform_menu.pack(side="left", padx=8, pady=3)
    ctk.CTkLabel(topbar, text="翻译平台选择", font=default_font).pack(side="left", padx=(2, 14))

    # 新增API账号
    ctk.CTkButton(topbar, text="新增API账号", font=default_font, command=open_add_api_popup).pack(side="left", padx=8)
    # 恢复备份
    ctk.CTkButton(topbar, text="恢复备份", font=default_font, command=open_restore_backup_popup).pack(side="left", padx=8)
    # 刷新云端
    def do_smart_sync_tags():
        status_var.set("同步中...")
        smart_sync_tags()  # 你的原有同步逻辑
        status_var.set("同步完成")
        root.after(2000, lambda: status_var.set("就绪"))  # 2秒后回到“就绪”
    ctk.CTkButton(topbar, text="☁️ 云端同步", font=default_font, fg_color="#4682B4",
              command=lambda: threading.Thread(target=do_smart_sync_tags, daemon=True).start()
              ).pack(side="left", padx=4)
    # 从云端下载（新增）
    def download_from_cloud():
        """从云端下载数据，自动创建本地备份"""
        answer = messagebox.askyesno(
            "从云端下载", 
            "此操作将：\n"
            "1. 自动备份当前本地数据\n"
            "2. 从云端下载最新数据\n"
            "3. 覆盖本地所有标签和图片\n\n"
            "确定要继续吗？"
        )
        if answer:
            try:
                # 先创建本地备份
                status_var.set("正在创建本地备份...")
                backup_filename = f"tags_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                if os.path.exists("tags.json"):
                    shutil.copy2("tags.json", backup_filename)
                if os.path.exists("images"):
                    shutil.copytree("images", f"images_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}", dirs_exist_ok=True)
                
                # 下载云端数据
                status_var.set("正在从云端下载...")
                from oss_sync import download_all
                download_all(status_var, root)
                
                # 重新加载数据
                global tags_data
                tags_data = load_tags()
                # 通过root对象调用刷新函数
                if hasattr(root, 'refresh_tab_list'):
                    root.refresh_tab_list()
                if hasattr(root, 'refresh_head_tags'):
                    root.refresh_head_tags()
                if hasattr(root, 'refresh_tail_tags'):
                    root.refresh_tail_tags()
                
                messagebox.showinfo("完成", f"云端数据下载完成！\n本地备份已创建：{backup_filename}")
                status_var.set("云端数据下载完成")
                root.after(2000, lambda: status_var.set("就绪"))
                
            except Exception as e:
                messagebox.showerror("下载失败", f"从云端下载失败：{str(e)}")
                status_var.set("下载失败")
                root.after(2000, lambda: status_var.set("就绪"))

    ctk.CTkButton(topbar, text="⬇️ 从云端下载", font=default_font, fg_color="#FF6B35",
                  command=lambda: threading.Thread(target=download_from_cloud, daemon=True).start()
                  ).pack(side="left", padx=8)
    # 占位拉伸
    ctk.CTkLabel(topbar, text="", font=default_font).pack(side="left", expand=True, fill="x")

    # 收藏夹/历史记录 靠右显示
    from views.ui_main import view_favorites, view_history
    ctk.CTkButton(topbar, text="📂 收藏夹", font=("微软雅黑", 13), fg_color="#4a90e2", command=view_favorites).pack(side="right", padx=8)
    ctk.CTkButton(topbar, text="🕘 历史记录", font=("微软雅黑", 13), fg_color="#4a90e2", command=view_history).pack(side="right", padx=8)
    
    main_pane = ctk.CTkFrame(root, fg_color="transparent")
    main_pane.pack(fill="both", expand=True, padx=8, pady=4)

    # 左侧输入输出 - 固定宽度
    io_pane = ctk.CTkFrame(main_pane, fg_color="transparent", width=850)
    io_pane.pack(side="left", fill="y", padx=(0, 0))
    io_pane.pack_propagate(False)

    # 输入框标题 + 按钮行（上方）
    input_title_frame = ctk.CTkFrame(io_pane, fg_color="transparent")
    input_title_frame.pack(fill="x", anchor="w", pady=(2, 4))  # 减少顶部空白

    # 标题标签
    ctk.CTkLabel(input_title_frame, text="输入提示词（自动识别/翻译）", font=default_font).pack(side="left")

    # 按钮框架（右侧对齐）
    input_buttons_frame = ctk.CTkFrame(input_title_frame, fg_color="transparent")
    input_buttons_frame.pack(side="right")

    # 清空按钮 - 无底色简洁样式
    clear_btn = ctk.CTkButton(
        input_buttons_frame, 
        text="🗑️", 
        width=30, 
        height=30,
        corner_radius=15,
        fg_color="transparent",
        hover_color="#f0f0f0",
        text_color="#666666",
        font=("微软雅黑", 14),
        command=lambda: input_text.delete("0.0", ctk.END)
    )
    clear_btn.pack(side="right", padx=3)

    # 复制按钮功能 - 无底色简洁样式
    def copy_input_to_clipboard():
        try:
            text = input_text.get("0.0", ctk.END).strip()
            if not text:
                status_var.set("输入框为空，无内容可复制")
                root.after(3000, lambda: status_var.set("就绪"))
                return
            pyperclip.copy(text)
            status_var.set("输入框内容已复制到剪贴板 ✓")
            root.after(3000, lambda: status_var.set("就绪"))
        except Exception as e:
            status_var.set(f"复制失败: {str(e)}")
            root.after(3000, lambda: status_var.set("就绪"))

    input_copy_icon = ctk.CTkButton(
        input_buttons_frame, 
        text="📋", 
        width=30, 
        height=30,
        corner_radius=15,
        fg_color="transparent",
        hover_color="#f0f0f0",
        text_color="#666666",
        font=("微软雅黑", 14),
        command=copy_input_to_clipboard
    )
    input_copy_icon.pack(side="right", padx=3)

    # 括号格式控制行
    bracket_frame = ctk.CTkFrame(io_pane, fg_color="transparent")
    bracket_frame.pack(fill="x", anchor="w", pady=(0, 4))

    # 左侧括号工具
    left_frame = ctk.CTkFrame(bracket_frame, fg_color="transparent")
    left_frame.pack(side="left", fill="x", expand=True)

    def add_brackets():
        try:
            selected = input_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if not selected:
                messagebox.showinfo("提示", "请先选择要加括号的内容")
                return
            format_type = format_var.get()
            prefix = f"({selected})"
            if format_type:
                weight = weight_entry.get().strip()
                if not weight:
                    messagebox.showinfo("提示", f"请输入{format_type}的权重数值")
                    return
                prefix += f"{format_type}{weight}"
            input_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
            input_text.insert(tk.INSERT, prefix)
        except tk.TclError:
            messagebox.showinfo("提示", "请先选择要加括号的内容")

    ctk.CTkButton(left_frame, text="加括号", command=add_brackets,
                  font=("微软雅黑", 12), width=80, height=28).pack(side="left", padx=(0, 8))

    # 加权选项
    format_var = tk.StringVar(value="")
    radio_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
    radio_frame.pack(side="left", padx=(0, 8))

    ctk.CTkRadioButton(radio_frame, text="**", variable=format_var,
                       value="**", font=("微软雅黑", 12)).pack(side="left", padx=(0, 4))
    ctk.CTkRadioButton(radio_frame, text="::", variable=format_var,
                       value="::", font=("微软雅黑", 12)).pack(side="left", padx=(0, 4))

    def clear_selection():
        format_var.set("")
    ctk.CTkButton(radio_frame, text="不选", command=clear_selection,
                  font=("微软雅黑", 12), width=50, height=24).pack(side="left", padx=(4, 0))

    weight_entry = ctk.CTkEntry(left_frame, placeholder_text="权重值",
                                width=80, height=28, font=("微软雅黑", 12))
    weight_entry.pack(side="left", padx=(0, 4))
    
    # 添加按钮
    def add_weight():
        try:
            selected = input_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if not selected:
                messagebox.showinfo("提示", "请先选择要加权重的内容")
                return
            format_type = format_var.get()
            weight = weight_entry.get().strip()
            if not format_type:
                messagebox.showinfo("提示", "请先选择权重格式（** 或 ::）")
                return
            if not weight:
                messagebox.showinfo("提示", f"请输入{format_type}的权重数值")
                return
            prefix = f"({selected}){format_type}{weight}"
            input_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
            input_text.insert(tk.INSERT, prefix)
        except tk.TclError:
            messagebox.showinfo("提示", "请先选择要加权重的内容")
    
    ctk.CTkButton(left_frame, text="添加", command=add_weight,
                  font=("微软雅黑", 12), width=50, height=28).pack(side="left", padx=(0, 8))

    # 右侧连字符替换
    def replace_spaces_with_hyphen():
        try:
            selected = input_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if not selected:
                messagebox.showinfo("提示", "请先选择英文短语")
                return
            hyphenated = selected.replace(" ", "-")
            input_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
            input_text.insert(tk.INSERT, hyphenated)
        except tk.TclError:
            messagebox.showinfo("提示", "请先选择英文短语")

    separator = ctk.CTkFrame(bracket_frame, width=2, height=28, fg_color="#cccccc")
    separator.pack(side="left", padx=(0, 8))

    ctk.CTkButton(bracket_frame, text="连字符", command=replace_spaces_with_hyphen,
                  font=("微软雅黑", 12), width=80, height=28).pack(side="left")

    # 输入框
    input_frame = ctk.CTkFrame(io_pane, fg_color="#f9fcff")
    input_frame.pack(fill="both", expand=True, padx=3)

    input_text = ctk.CTkTextbox(input_frame, height=100, font=default_font, fg_color="white")
    input_text.pack(fill="both", expand=True, side="left", padx=(0, 4))
    input_scrollbar = ctk.CTkScrollbar(input_frame, command=input_text.yview)
    input_scrollbar.pack(side="right", fill="y")
    input_text.configure(yscrollcommand=input_scrollbar.set)
    
    # 启用划词翻译功能
    try:
        from services.text_selection_translator import enable_text_selection_translation
        text_translator = enable_text_selection_translation(input_text)
    except Exception as e:
        print(f"[划词翻译] 启用失败: {e}")

    # 添加输入框提示文本
    placeholder_text = "请输入要翻译的英文或中文内容...\n支持快捷键：\nCtrl+Enter 翻译\nCtrl+D 清空\nCtrl+T 创建标签"
    input_text.insert("0.0", placeholder_text)
    input_text.configure(text_color="#999999")  # 灰色提示文字

    def clear_placeholder(event=None):
        """清除提示文本"""
        current_text = input_text.get("0.0", ctk.END).strip()
        if current_text == placeholder_text.strip() or current_text == "":
            input_text.delete("0.0", ctk.END)
            input_text.configure(text_color="black")  # 恢复黑色文字

    def restore_placeholder(event=None):
        """如果输入框为空，恢复提示文本"""
        current_text = input_text.get("0.0", ctk.END).strip()
        if not current_text:
            input_text.insert("0.0", placeholder_text)
            input_text.configure(text_color="#999999")

    # 绑定事件处理
    input_text.bind('<FocusIn>', clear_placeholder)
    input_text.bind('<Button-1>', clear_placeholder)
    input_text.bind('<KeyPress>', lambda e: input_text.configure(text_color="black"))

    input_text.bind('<Control-Return>', lambda event: do_translate())
    input_text.bind('<Control-D>', lambda event: (input_text.delete("0.0", ctk.END), clear_placeholder()))
    input_text.bind('<Control-Shift-C>', lambda event: pyperclip.copy(get_output_for_copy()))

    def do_expand_text():
        txt = input_text.get("0.0", ctk.END).strip()
        if not txt:
            messagebox.showinfo("提示", "请输入要扩写的内容")
            return
        # 选择扩写预设后自动发起扩写
        def on_choose_preset(preset):
            def async_expand():
                expanded = zhipu_text_expand(txt, preset)
                input_text.delete("0.0", ctk.END)
                input_text.insert("end", expanded)
            threading.Thread(target=async_expand, daemon=True).start()
        show_expand_preset_dialog(callback=on_choose_preset)

    # 创建水平按钮框架
    btn_frame = ctk.CTkFrame(io_pane, fg_color="transparent")
    btn_frame.pack(anchor="w", pady=(8,0))
    
    # 智能扩写按钮
    expand_btn = ctk.CTkButton(btn_frame, text="AI智能扩写", font=default_font, fg_color="#5F378F", command=do_expand_text)
    expand_btn.pack(side="left", padx=(0, 8))
    
    # 图片反推按钮（放在后面）
    def do_image_caption():
        filetypes = [("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.webp")]
        img_path = filedialog.askopenfilename(title="选择图片", filetypes=filetypes)
        if not img_path:
            return
        # 这里不用管当前平台，只管api_config["zhipu"]轮询
        def async_caption():
            output_text.config(state="normal")
            output_text.delete("1.0", tk.END)
            output_text.insert("end", "正在识别图片，请稍候...")
            result = zhipu_image_caption(img_path)
            output_text.config(state="normal")
            output_text.delete("1.0", tk.END)
            output_text.insert("end", result)
        threading.Thread(target=async_caption, daemon=True).start()
    
    image_btn = ctk.CTkButton(btn_frame, text="图片反推", font=default_font, fg_color="#19a8b9", command=do_image_caption)
    image_btn.pack(side="left")


    def on_create_tag_shortcut(event=None):
        try:
            selection = input_text.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
        except tk.TclError:
            selection = ""
        if not selection or contains_chinese(selection):
            messagebox.showinfo("提示", "请先在输入区选择英文内容再按快捷键")
            return
        show_create_tag_dialog(selection)
    input_text.bind('<Control-t>', on_create_tag_shortcut)

    # 创建输出框标题和按钮框架
    output_title_frame = ctk.CTkFrame(io_pane, fg_color="transparent")
    output_title_frame.pack(fill="x", anchor="w", pady=(10,2))
    
    # 标题标签
    ctk.CTkLabel(output_title_frame, text="翻译结果（含标签自动拼接）", font=default_font).pack(side="left")
    
    # 按钮框架（右侧对齐）
    output_buttons_frame = ctk.CTkFrame(output_title_frame, fg_color="transparent")
    output_buttons_frame.pack(side="right")
    
    def clear_output():
        try:
            # 清除输出文本 - 使用多种方式确保清空成功
            output_text.delete("1.0", "end")
            output_text.delete("1.0", tk.END)
            # 确保文本框完全清空
            output_text.config(state="normal")
            output_text.delete("1.0", "end")
            
            # 清除所有标签选中状态
            inserted_tags["head"].clear()
            inserted_tags["tail"].clear()
            
            # 刷新标签显示
            if hasattr(root, 'refresh_head_tags'):
                root.refresh_head_tags()
            if hasattr(root, 'refresh_tail_tags'):
                root.refresh_tail_tags()
            
            # 刷新输出文本
            refresh_output_text()
            
            # 显示状态提示
            status_var.set("输出框已清空")
            root.after(1000, lambda: status_var.set("就绪"))
            
        except Exception as e:
            status_var.set(f"清空失败: {str(e)}")
            root.after(2000, lambda: status_var.set("就绪"))
    
    # 清空按钮 - 无底色简洁样式
    output_clear_btn = ctk.CTkButton(
        output_buttons_frame, 
        text="🗑️", 
        width=30, 
        height=30,
        corner_radius=15,
        fg_color="transparent",
        hover_color="#f0f0f0",
        text_color="#666666",
        font=("微软雅黑", 14),
        command=clear_output
    )
    output_clear_btn.pack(side="right", padx=3)
    
    def copy_to_clipboard():
        try:
            # 构建包含标签的完整文本内容
            head_tags = ', '.join(inserted_tags["head"])
            tail_tags = ', '.join(inserted_tags["tail"])
            
            # 组合所有内容，处理可能的空值情况
            parts = []
            if head_tags:
                parts.append(head_tags)
            parts.append(last_translation)
            if tail_tags:
                parts.append(tail_tags)
            
            text = ', '.join(parts)
            if not text:
                status_var.set("输出框为空，无内容可复制")
                root.after(3000, lambda: status_var.set("就绪"))
                return
            pyperclip.copy(text)
            status_var.set("内容已复制到剪贴板 ✓")
            root.after(3000, lambda: status_var.set("就绪"))  # 3秒后恢复默认状态
        except Exception as e:
            status_var.set(f"复制失败: {str(e)}")
            root.after(3000, lambda: status_var.set("就绪"))
    output_copy_icon = ctk.CTkButton(
        output_buttons_frame, 
        text="📋", 
        width=30, 
        height=30,
        corner_radius=15,
        fg_color="transparent",
        hover_color="#f0f0f0",
        text_color="#666666",
        font=("微软雅黑", 14),
        command=copy_to_clipboard
    )
    output_copy_icon.pack(side="right", padx=3)
    
    # 输出框框架
    output_frame = ctk.CTkFrame(io_pane, fg_color="#f9fcff")
    output_frame.pack(fill="both", expand=True, padx=3)
    output_text = tk.Text(
        output_frame,
        height=7,
        font=default_font,
        wrap="word",
        bg="white",
        relief="flat",
        bd=0,
        state="normal"
    )
    output_text.pack(fill="both", expand=True, side="left", padx=(0, 4))
    output_scrollbar = ctk.CTkScrollbar(output_frame, command=output_text.yview)
    output_scrollbar.pack(side="right", fill="y")
    output_text.config(yscrollcommand=output_scrollbar.set)

    def get_output_for_copy():
        s = ""
        if inserted_tags["head"]:
            s += ", ".join(inserted_tags["head"]) + ", "
        s += last_translation
        # 添加返回语句
        return s

    # 创建按钮水平容器
    btn_frame = ctk.CTkFrame(io_pane)
    btn_frame.pack(anchor="w", pady=(12, 2), fill="x")
    
    # 收藏结果按钮
    ctk.CTkButton(btn_frame, text="收藏结果", font=default_font, fg_color="green",
                  command=lambda: save_to_favorites(input_text.get("0.0", ctk.END), get_output_for_copy())
    ).pack(side="left", padx=(0, 8))

    def do_translate():
        global status_var, root
        txt = input_text.get("0.0", ctk.END).strip()
        if not txt:
            messagebox.showinfo("提示", "请输入内容")
            return
        def do_async():
            global last_translation
            status_var.set("正在翻译...")
            translated = translate_text(txt)
            last_translation = translated
            refresh_output_text()
            save_to_history(txt, translated)
            status_var.set("翻译完成")
            root.after(2000, lambda: status_var.set("就绪"))
            # recommend_tags()
        threading.Thread(target=do_async, daemon=True).start()
    # 翻译按钮
    translate_btn = ctk.CTkButton(btn_frame, text="翻译", font=default_font, fg_color="#4a90e2", command=do_translate)
    translate_btn.pack(side="left", padx=(0, 8))

    
    # UI构建逻辑已迁移至views.ui_main.build_ui函数，避免代码重复
    # 所有标签区域、头部标签、尾部标签的UI构建都在build_ui中完成
    # 重复的UI构建代码已移除，统一使用views.ui_main.build_ui函数
    # 所有头部标签UI构建代码已移除，统一在build_ui中处理

    # 所有标签管理和UI交互函数已移除，统一在build_ui中处理
    # 包括：add_edit_tab、add_edit_tag、refresh_tab_list、refresh_output_text、
    # insert_tag_block、show_create_tag_dialog、update_on_resize等函数

    # UI初始化和刷新逻辑已迁移到views/ui_main.py中的build_ui函数
    
    # refresh_tags_ui 方法已迁移到 views/ui_main.py 中实现
    
    # ``root.mainloop()`` is intentionally not called here. The caller (see
    # ``app.run``) is responsible for entering the main loop so that the
    # application can integrate additional services (tray, bridge, etc.) before
    # starting the event loop.
    return root

# --------- 收藏夹和历史记录窗口（含分页+日期筛选） ------------

# view_history, view_favorites 和 open_tag_table_manager 函数已迁移到 views.ui_main 模块，移除重复实现 
if __name__ == "__main__":
    # 统一入口
    from app import run
    run()