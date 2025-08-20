# views/ui_main.py —— UI主模块
import os, csv, json, threading, datetime, time, shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import customtkinter as ctk
from PIL import Image, ImageTk
import pyperclip
try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None

from services.api import *
from services.tags import *
from services.data_processor import process_pending_data
from services.logger import logger, show_error_dialog, show_info_dialog, safe_execute
from utils import smart_sync_tags
from image_tools import select_and_crop_image
from oss_sync import upload_all, download_all, save_tags_with_sync, load_tags_with_sync
from main import show_expand_preset_dialog
from views.page_manager import PageManager, TranslationPage
from services.history_favorites import save_to_history, save_to_favorites
from services.page_tag_manager import PageTagManager
from services.tag_template_manager import TagTemplateManager
from services.ui_state_manager import ui_state_manager
# 收藏夹和历史记录函数现在在本文件中定义

# 全局分页管理器
page_manager = None

def show_create_tag_dialog(en_content):
    """创建新标签的对话框"""
    dlg = ctk.CTkToplevel(global_root)
    dlg.title("创建新标签")
    dlg.geometry("430x480")  # 增加高度以容纳图片上传组件
    tk_type = tk.StringVar(value="head")
    ctk.CTkLabel(dlg, text="标签类型：").pack(pady=5)
    type_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    type_frame.pack()
    ctk.CTkRadioButton(type_frame, text="头部标签", variable=tk_type, value="head").pack(side="left", padx=12)
    ctk.CTkRadioButton(type_frame, text="尾部标签", variable=tk_type, value="tail").pack(side="left", padx=12)

    tab_var = tk.StringVar()
    tabs_head = list(tags_data["head"].keys())
    tabs_tail = list(tags_data["tail"].keys())
    tab_combo = ttk.Combobox(dlg, textvariable=tab_var, values=tabs_head, state="readonly")
    tab_combo.pack(pady=6)
    tab_var.set(tabs_head[0] if tabs_head else "")

    ctk.CTkLabel(dlg, text="中文名称（自动翻译可修改）").pack()
    zh_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    zh_frame.pack()
    zh_var = tk.StringVar(value="翻译中…")
    zh_entry = ctk.CTkEntry(zh_frame, textvariable=zh_var, width=220)
    zh_entry.pack(side="left", padx=(0, 8))
    def click_translate():
        zh_var.set("翻译中…")
        def update():
            result = translate_text(en_content)
            zh_var.set(result)
        threading.Thread(target=update, daemon=True).start()
    ctk.CTkButton(zh_frame, text="翻译", width=55, command=click_translate).pack(side="left")

    ctk.CTkLabel(dlg, text="英文提示词").pack()
    en_var = tk.StringVar(value=en_content)
    en_entry = ctk.CTkEntry(dlg, textvariable=en_var)
    en_entry.pack(pady=4)
    
    # 添加图片上传功能
    ctk.CTkLabel(dlg, text="标签图片（可选）").pack(pady=(10, 5))
    image_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    image_frame.pack(pady=5)
    
    # 图片预览标签
    image_preview_label = ctk.CTkLabel(image_frame, text="未选择图片", width=200, height=80, 
                                      fg_color=("gray75", "gray25"), corner_radius=8)
    image_preview_label.pack(side="left", padx=(0, 8))
    
    # 存储选中的图片路径
    selected_image_path = [None]
    
    def upload_image():
        """上传并裁剪图片 - 复用编辑标签的成熟逻辑"""
        try:
            from image_tools import select_and_crop_image
            label_for_img = zh_var.get().strip() or "标签"
            save_path = select_and_crop_image(label_for_img, box_size=(200, 200))
            if not save_path:
                return
            selected_image_path[0] = save_path
            # 显示缩略图 - 使用与编辑标签相同的逻辑
            try:
                from PIL import Image
                im2 = Image.open(save_path).resize((80, 80))
                # 使用CTkImage替代ImageTk.PhotoImage
                ctk_image = ctk.CTkImage(
                    light_image=im2,
                    dark_image=im2,
                    size=(80, 80)
                )
                image_preview_label.configure(image=ctk_image, text="")
            except Exception as e:
                image_preview_label.configure(text="图片预览失败", image="")
                print(f"图片预览错误: {e}")
        except Exception as e:
            messagebox.showerror("错误", f"图片上传失败: {str(e)}")
    
    upload_btn = ctk.CTkButton(image_frame, text="选择图片", width=80, command=upload_image)
    upload_btn.pack(side="left")

    def update_tab_options(*_):
        if tk_type.get() == "head":
            tab_combo["values"] = tabs_head
            if tabs_head:
                tab_var.set(tabs_head[0])
        else:
            tab_combo["values"] = tabs_tail
            if tabs_tail:
                tab_var.set(tabs_tail[0])
    tk_type.trace_add("write", update_tab_options)

    click_translate()
   
    # 添加缺失的save_函数定义
    def save_():
        tag_type = tk_type.get()
        tab_name = tab_var.get().strip()
        zh_name = zh_var.get().strip()
        en_name = en_var.get().strip()
        
        if not (tab_name and zh_name and en_name):
            messagebox.showerror("错误", "请完整填写所有字段")
            return
        
        # 确保标签类型字典存在
        if tab_name not in tags_data[tag_type]:
            tags_data[tag_type][tab_name] = {}
        
        # 添加新标签到全局标签库，包含图片路径
        new_tag_data = {"en": en_name, "usage_count": 0}
        
        # 如果有选择图片，添加图片路径（统一保存为相对路径）
        if selected_image_path[0]:
            rel_img_path = os.path.relpath(selected_image_path[0], os.path.join(PROJECT_ROOT, "images"))
            new_tag_data["image"] = os.path.join("images", rel_img_path)
        
        tags_data[tag_type][tab_name][zh_name] = new_tag_data
        save_tags(tags_data)
        
        # 同步添加到所有分页的标签数据
        if page_manager:
            for page in page_manager.pages.values():
                tag_manager = page.get_tag_manager()
                if tag_manager:
                    tag_manager.add_tag(tag_type, tab_name, zh_name, new_tag_data)
            
            # 保存分页数据
            page_manager.save_pages_data()
        
        # 刷新标签列表
        if hasattr(global_root, 'refresh_tab_list'):
            global_root.refresh_tab_list()
        
        # 显示成功消息
        success_msg = f"标签 '{zh_name}' 创建成功！"
        if selected_image_path[0]:
            success_msg += f"\n图片已保存至: {selected_image_path[0]}"
        messagebox.showinfo("成功", success_msg)
        
        dlg.destroy()
    
    ctk.CTkButton(dlg, text="保存", command=save_).pack(pady=12)
    update_tab_options()

def get_page_tag_manager():
    """获取当前页面的标签管理器"""
    if page_manager:
        return page_manager.get_current_page_tag_manager()
    return None

def insert_tag_block(text, tag_type, output_text_widget):
    """在输出文本框中插入标签块"""
    from services.ui_state_manager import ui_state_manager
    
    color = "#3776ff" if tag_type=="head" else "#74e4b6"
    hover_color = "#1857b6" if tag_type=="head" else "#2fa98c"
    # 直接定义字体，避免作用域问题
    font = ("微软雅黑", 13, "bold") if sys.platform == "win32" else ("PingFang SC", 13, "bold")
    label = tk.Label(output_text_widget, text=text, bg=color, fg="white", font=font,
                     padx=8, pady=2, borderwidth=0, relief="ridge")
    label.bind("<Enter>", lambda e, l=label: l.config(bg=hover_color))
    label.bind("<Leave>", lambda e, l=label: l.config(bg=color))
    
    # 记录标签块信息到UI状态管理器
    if page_manager:
        current_page = page_manager.get_current_page()
        if current_page:
            position = output_text_widget.index(tk.END)
            tag_block_info = ui_state_manager.create_tag_block_info(
                text=text,
                tag_type=tag_type,
                position=position,
                style={
                    "color": color,
                    "hover_color": hover_color,
                    "font": font,
                    "padding": {"x": 8, "y": 2}
                }
            )
    def remove_this_tag(event, t=text, tt=tag_type):
        # 真正删除标签，而不是取消选中
        try:
            # 查找标签所在的标签页（先在全局标签库中查找）
            found_tab = None
            tag_entry = None
            
            # 首先在全局标签库中查找
            for tab_name, tab_tags in tags_data[tt].items():
                if t in tab_tags:
                    found_tab = tab_name
                    tag_entry = tab_tags[t]
                    break
            
            # 如果在全局库中没找到，尝试在当前分页数据中查找
            if not found_tab and page_manager:
                current_page = page_manager.get_current_page()
                if current_page and tt in current_page.tags:
                    for tab_name, tab_tags in current_page.tags[tt].items():
                        if t in tab_tags:
                            found_tab = tab_name
                            tag_entry = tab_tags[t]
                            break
            
            # 处理图片删除（如果有的话）
            if tag_entry and isinstance(tag_entry, dict) and 'image' in tag_entry:
                image_path = tag_entry['image']
                # 统一解析为绝对路径再删除
                abs_img_path = os.path.join(PROJECT_ROOT, image_path) if not os.path.isabs(image_path) else image_path
                if os.path.exists(abs_img_path):
                    try:
                        os.remove(abs_img_path)
                        if 'status_var' in globals():
                            status_var.set(f"已删除图片文件: {abs_img_path}")
                            if 'global_root' in globals():
                                global_root.after(2000, lambda: status_var.set("就绪"))
                    except Exception as e:
                        print(f"删除图片失败: {e}")
            
            # 从全局标签库删除标签数据（如果存在）
            if found_tab and found_tab in tags_data[tt] and t in tags_data[tt][found_tab]:
                tags_data[tt][found_tab].pop(t, None)
                save_tags(tags_data)
                
                # 如果该 Tab 下已经没有标签，移除空 Tab
                if not tags_data[tt].get(found_tab):
                    tags_data[tt].pop(found_tab, None)
                    save_tags(tags_data)
                    if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                        global_root.refresh_tab_list()
            
            # 无论是否在全局库中找到，都要从所有分页数据中删除
            if page_manager:
                for page in page_manager.pages.values():
                    # 从分页的tags中删除
                    if tt in page.tags:
                        for tab_name, tab_tags in page.tags[tt].items():
                            if t in tab_tags:
                                page.tags[tt][tab_name].pop(t, None)
                                # 如果tab为空，删除tab
                                if not page.tags[tt][tab_name]:
                                    page.tags[tt].pop(tab_name, None)
                    
                    # 从inserted_tags中移除
                    if t in page.inserted_tags[tt]:
                        page.inserted_tags[tt].remove(t)
                
                # 保存分页数据
                page_manager.save_pages_data()
            
            # 刷新UI显示
            refresh_tags_ui()
            # 刷新当前页面的输出文本
            if page_manager:
                current_page = page_manager.get_current_page()
                if current_page:
                    current_page.refresh_output_text()
                    
            print(f"已删除标签: {t} (类型: {tt})")
                
        except Exception as e:
            print(f"删除标签失败: {e}")
            # 备用逻辑：仅从当前页面的inserted_tags中移除
            if page_manager:
                current_page = page_manager.get_current_page()
                if current_page and t in current_page.inserted_tags[tt]:
                    current_page.inserted_tags[tt].remove(t)
                    current_page.refresh_output_text()
                    try:
                        current_page.refresh_output_text()
                    except Exception as e:
                        print(f"刷新输出文本失败: {e}")
    label.bind("<Button-1>", remove_this_tag)
    output_text_widget.window_create(tk.END, window=label)
    
    # 保存标签块创建后的UI状态
    if page_manager:
        current_page = page_manager.get_current_page()
        if current_page:
            try:
                # 获取当前输出文本框的所有内容和标签块信息
                text_content = output_text_widget.get("1.0", tk.END)
                cursor_pos = output_text_widget.index(tk.INSERT)
                
                # 获取现有的标签块信息
                output_state = ui_state_manager.get_output_text_state(str(current_page.page_id))
                tag_blocks = output_state.get("tag_blocks", [])
                tag_blocks.append(tag_block_info)
                
                # 保存更新后的输出文本状态
                ui_state_manager.save_output_text_state(
                    page_id=str(current_page.page_id),
                    tag_blocks=tag_blocks,
                    text_content=text_content,
                    cursor_position=cursor_pos
                )
            except Exception as e:
                print(f"[insert_tag_block] 保存UI状态失败: {e}")

def create_page_navigation_ui(parent):
    """创建分页导航UI"""
    global page_manager
    
    # 标题
    title_frame = ctk.CTkFrame(parent, fg_color="transparent")
    title_frame.pack(fill="x", padx=8, pady=(8, 4))
    
    ctk.CTkLabel(title_frame, text="翻译分页", font=("微软雅黑", 16, "bold")).pack(side="left")
    
    # 分页管理按钮
    btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
    btn_frame.pack(fill="x", padx=8, pady=(0, 8))
    
    def create_new_page():
        name = simpledialog.askstring("新建分页", "请输入分页名称:", initialvalue=f"分页 {page_manager.next_page_id}")
        if name:
            page_manager.create_new_page(name.strip())
    
    ctk.CTkButton(btn_frame, text="➕ 新建", font=default_font, width=80, height=28,
                  fg_color="#28a745", command=create_new_page).pack(side="left", padx=(0, 4))
    
    def clear_current_page():
        """清空当前分页的内容"""
        current_page = page_manager.get_current_page()
        if current_page:
            if messagebox.askyesno("确认清空", f"确定要清空分页 '{current_page.name}' 的所有内容吗？\n此操作不可撤销。"):
                # 清空输入和输出内容
                current_page.input_text = ""
                current_page.output_text = ""
                current_page.last_translation = ""
                
                # 清空标签选中状态
                tag_manager = current_page.get_tag_manager()
                if tag_manager:
                    tag_manager.clear_all_selections()
                
                # 刷新UI
                refresh_translation_ui()
                page_manager.save_data()
                
                # 显示状态通知
                if hasattr(page_manager, 'status_var') and page_manager.status_var:
                    page_manager.status_var.set(f"已清空分页: {current_page.name}")
                    if hasattr(page_manager, 'root') and page_manager.root:
                        page_manager.root.after(2000, lambda: page_manager.status_var.set("就绪"))
    

    
    def clear_all_pages():
        """清空所有分页任务列表"""
        if messagebox.askyesno("确认清空全部", "确定要清空所有分页任务列表吗？\n此操作不可撤销。"):
            page_manager.clear_all_pages()
            # 清空后自动新建一个初始分页任务
            page_manager.create_new_page("初始分页")
            refresh_translation_ui()
            if hasattr(page_manager, 'status_var') and page_manager.status_var:
                page_manager.status_var.set("已清空所有分页任务列表，并新建了初始分页")
                if hasattr(page_manager, 'root') and page_manager.root:
                    page_manager.root.after(2000, lambda: page_manager.status_var.set("就绪"))
    ctk.CTkButton(btn_frame, text="🗑️ 清空", font=default_font, width=80, height=28,
                  fg_color="#dc3545", command=clear_all_pages).pack(side="left", padx=(0, 4))
    
    # 分页列表
    list_frame = ctk.CTkFrame(parent, fg_color="#ffffff")
    list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    
    # 创建滚动区域
    canvas = ctk.CTkCanvas(list_frame, highlightthickness=0, bg="#ffffff")
    scrollbar = ctk.CTkScrollbar(list_frame, command=canvas.yview)
    scrollable_frame = ctk.CTkFrame(canvas, fg_color="#ffffff")
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    def _sync_inner_width(event=None):
        try:
            canvas.itemconfigure(window_id, width=canvas.winfo_width())
        except Exception:
            pass
    canvas.bind("<Configure>", _sync_inner_width)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # 保存引用以便刷新
    page_manager.page_list_frame = scrollable_frame
    page_manager.refresh_page_list = lambda: refresh_page_list_ui(scrollable_frame)
    
    # 初始化分页列表
    refresh_page_list_ui(scrollable_frame)

def refresh_page_list_ui(list_frame):
    """刷新分页列表UI"""
    global page_manager
    
    # 清空现有内容
    for widget in list_frame.winfo_children():
        widget.destroy()
    
    # 添加分页项
    for page_id, page in page_manager.pages.items():
        is_current = page_id == page_manager.current_page_id
        
        # 分页项容器，添加悬停效果
        page_item = ctk.CTkFrame(
            list_frame, 
            fg_color="#007bff" if is_current else "#f8f9fa",
            cursor="hand2" if not is_current else "arrow"
        )
        page_item.pack(fill="x", padx=4, pady=2)
        
        # 为非当前分页添加点击切换功能
        if not is_current:
            def switch_page(pid=page_id):
                page_manager.switch_to_page(pid)
                refresh_translation_ui()
            
            # 为分页项及其子组件绑定点击事件
            page_item.bind("<Button-1>", lambda e, pid=page_id: switch_page(pid))
        
        # 分页信息容器
        info_frame = ctk.CTkFrame(page_item, fg_color="transparent")
        info_frame.pack(fill="x", padx=8, pady=4)
        
        # 为信息框架也绑定点击事件（如果不是当前分页）
        if not is_current:
            info_frame.bind("<Button-1>", lambda e, pid=page_id: switch_page(pid))
        
        # 分页名称
        name_color = "white" if is_current else "black"
        name_label = ctk.CTkLabel(
            info_frame, 
            text=page.name, 
            font=("微软雅黑", 13, "bold"),
            text_color=name_color
        )
        name_label.pack(anchor="w")
        
        # 为名称标签也绑定点击事件（如果不是当前分页）
        if not is_current:
            name_label.bind("<Button-1>", lambda e, pid=page_id: switch_page(pid))
        
        # 创建时间
        time_color = "#e6f3ff" if is_current else "#666666"
        time_label = ctk.CTkLabel(
            info_frame, 
            text=page.created_time, 
            font=("微软雅黑", 10),
            text_color=time_color
        )
        time_label.pack(anchor="w")
        
        # 为时间标签也绑定点击事件（如果不是当前分页）
        if not is_current:
            time_label.bind("<Button-1>", lambda e, pid=page_id: switch_page(pid))
        
        # 按钮区域（只显示重命名按钮和当前状态）
        btn_frame = ctk.CTkFrame(page_item, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(0, 4))
        
        # 当前分页标识
        if is_current:
            ctk.CTkLabel(
                btn_frame, 
                text="● 当前", 
                font=("微软雅黑", 11, "bold"),
                text_color="white"
            ).pack(side="left", padx=(0, 4))
        
        # 删除按钮
        def delete_page(pid=page_id):
            page_manager.delete_page(pid)
        
        delete_btn = ctk.CTkButton(
            btn_frame, 
            text="🗑️", 
            font=("微软雅黑", 11), 
            width=30, 
            height=24,
            fg_color="#e9ecef",  # 初始不显眼的灰色
            text_color="#6c757d",  # 初始灰色文字
            hover_color="#dc3545",  # 悬停时的红色
            command=delete_page
        )
        delete_btn.pack(side="right", padx=(0, 4))
        
        # 重命名按钮
        def rename_page(pid=page_id):
            current_name = page_manager.pages[pid].name
            new_name = simpledialog.askstring("重命名分页", "请输入新名称:", initialvalue=current_name)
            if new_name and new_name.strip() != current_name:
                page_manager.rename_page(pid, new_name.strip())
        
        rename_btn = ctk.CTkButton(
            btn_frame, 
            text="✏️", 
            font=("微软雅黑", 11), 
            width=30, 
            height=24,
            fg_color="#e9ecef",  # 初始不显眼的灰色
            text_color="#6c757d",  # 初始灰色文字
            hover_color="#ffc107",  # 悬停时的黄色
            command=rename_page
        )
        rename_btn.pack(side="right")

def create_translation_ui_for_current_page(parent):
    """为当前分页创建翻译界面（兼容缓存机制）"""
    global page_manager
    
    current_page = page_manager.get_current_page()
    if not current_page:
        return
    
    # 首先清空parent中的所有非缓存UI组件
    # 这是为了避免新旧UI组件同时存在
    for widget in parent.winfo_children():
        # 检查是否是缓存的UI框架
        is_cached_ui = False
        for page_id, page in page_manager.pages.items():
            if hasattr(page, 'ui_frame') and page.ui_frame == widget:
                is_cached_ui = True
                break
        
        # 如果不是缓存的UI框架，则销毁
        if not is_cached_ui:
            widget.destroy()
    
    # 如果使用缓存机制，则直接显示缓存的UI
    if current_page.ui_created:
        # 隐藏所有其他分页的UI
        for page_id, page in page_manager.pages.items():
            if page_id != page_manager.current_page_id:
                page.hide_ui()
        
        # 显示当前分页的UI
        current_page.show_ui()
        return
    
    # 如果没有缓存，则创建新UI
    create_translation_ui_components(parent, current_page)

def refresh_translation_ui():
    """刷新翻译界面"""
    global page_manager
    
    if hasattr(page_manager, 'translation_area') and page_manager.translation_area:
        create_translation_ui_for_current_page(page_manager.translation_area)

def create_translation_ui_components(parent, page):
    """创建翻译UI组件"""
    global page_manager, tags_data, inserted_tags, last_translation, status_var, platform_var, current_platform, global_root
    
    # 使用分页的数据
    page.ui_components = {}
    # 绑定分页的状态与根窗口引用，便于page_manager内部方法使用
    page.status_var = status_var
    page.root = global_root
    
    # 输入框标题 + 按钮行（上方）
    input_title_frame = ctk.CTkFrame(parent, fg_color="transparent")
    input_title_frame.pack(fill="x", anchor="w", pady=(8,2))
    
    # 标题标签
    ctk.CTkLabel(input_title_frame, text="输入内容", font=default_font).pack(side="left")
    
    # 按钮框架（右侧对齐）
    input_buttons_frame = ctk.CTkFrame(input_title_frame, fg_color="transparent")
    input_buttons_frame.pack(side="right")
    
    def clear_input():
        page.input_text = ""
        if 'input_widget' in page.ui_components:
            page.ui_components['input_widget'].delete("0.0", ctk.END)
            page.ui_components['input_widget'].insert("0.0", "请输入要翻译的英文或中文内容...\n支持快捷键：\nCtrl+Enter 翻译\nCtrl+D 清空\nCtrl+T 创建标签")
            page.ui_components['input_widget'].configure(text_color="#999999")
        page_manager.save_data()
        status_var.set("输入框已清空")
        global_root.after(1000, lambda: status_var.set("就绪"))
    
    # 清空按钮
    input_clear_btn = ctk.CTkButton(
        input_buttons_frame, 
        text="🗑️", 
        width=30, 
        height=30,
        corner_radius=15,
        fg_color="transparent",
        hover_color="#f0f0f0",
        text_color="#666666",
        font=("微软雅黑", 14),
        command=clear_input
    )
    input_clear_btn.pack(side="right", padx=3)
    
    def copy_input():
        if 'input_widget' in page.ui_components:
            text = page.ui_components['input_widget'].get("0.0", ctk.END).strip()
            if text and text != "请输入要翻译的英文或中文内容...\n支持快捷键：\nCtrl+Enter 翻译\nCtrl+D 清空\nCtrl+T 创建标签":
                pyperclip.copy(text)
                status_var.set("输入内容已复制到剪贴板 ✓")
                global_root.after(3000, lambda: status_var.set("就绪"))
            else:
                status_var.set("输入框为空，无内容可复制")
                global_root.after(3000, lambda: status_var.set("就绪"))
    
    # 复制按钮
    input_copy_btn = ctk.CTkButton(
        input_buttons_frame, 
        text="📋", 
        width=30, 
        height=30,
        corner_radius=15,
        fg_color="transparent",
        hover_color="#f0f0f0",
        text_color="#666666",
        font=("微软雅黑", 14),
        command=copy_input
    )
    input_copy_btn.pack(side="right", padx=3)
    
    # 括号格式控制行
    bracket_frame = ctk.CTkFrame(parent, fg_color="transparent")
    bracket_frame.pack(fill="x", anchor="w", pady=(8,4))
    
    # 左侧加括号和权重控制
    left_frame = ctk.CTkFrame(bracket_frame, fg_color="transparent")
    left_frame.pack(side="left")
    
    def add_brackets():
        if 'input_widget' not in page.ui_components:
            return
        try:
            selected = page.ui_components['input_widget'].get(tk.SEL_FIRST, tk.SEL_LAST)
            if not selected:
                messagebox.showinfo("提示", "请先选择要加括号的内容")
                return
            bracketed = f"({selected})"
            page.ui_components['input_widget'].delete(tk.SEL_FIRST, tk.SEL_LAST)
            page.ui_components['input_widget'].insert(tk.INSERT, bracketed)
        except tk.TclError:
            messagebox.showinfo("提示", "请先选择要加括号的内容")
    
    ctk.CTkButton(left_frame, text="加括号", command=add_brackets,
                  font=("微软雅黑", 12), width=80, height=28).pack(side="left", padx=(0, 8))
    
    # 加权选项
    weight_format = tk.StringVar()
    ctk.CTkRadioButton(left_frame, text="**", variable=weight_format, value="**",
                       font=("微软雅黑", 11)).pack(side="left", padx=(0, 4))
    ctk.CTkRadioButton(left_frame, text="::", variable=weight_format, value="::",
                       font=("微软雅黑", 11)).pack(side="left", padx=(0, 4))
    
    def clear_weight_selection():
        weight_format.set("")
    
    ctk.CTkButton(left_frame, text="不选", command=clear_weight_selection,
                  font=("微软雅黑", 11), width=40, height=28).pack(side="left", padx=(0, 8))
    
    # 权重值输入
    weight_entry = ctk.CTkEntry(left_frame, width=60, height=28, font=("微软雅黑", 11))
    weight_entry.pack(side="left", padx=(0, 8))
    
    def add_weight():
        if 'input_widget' not in page.ui_components:
            return
        try:
            selected = page.ui_components['input_widget'].get(tk.SEL_FIRST, tk.SEL_LAST)
            if not selected:
                messagebox.showinfo("提示", "请先选择要加权重的内容")
                return
            format_type = weight_format.get()
            weight = weight_entry.get().strip()
            if not format_type:
                messagebox.showinfo("提示", "请先选择权重格式（** 或 ::）")
                return
            if not weight:
                messagebox.showinfo("提示", f"请输入{format_type}的权重数值")
                return
            prefix = f"({selected}){format_type}{weight}"
            page.ui_components['input_widget'].delete(tk.SEL_FIRST, tk.SEL_LAST)
            page.ui_components['input_widget'].insert(tk.INSERT, prefix)
        except tk.TclError:
            messagebox.showinfo("提示", "请先选择要加权重的内容")
    
    ctk.CTkButton(left_frame, text="添加", command=add_weight,
                  font=("微软雅黑", 12), width=50, height=28).pack(side="left", padx=(0, 8))
    
    # 右侧连字符替换
    def replace_spaces_with_hyphen():
        if 'input_widget' not in page.ui_components:
            return
        try:
            selected = page.ui_components['input_widget'].get(tk.SEL_FIRST, tk.SEL_LAST)
            if not selected:
                messagebox.showinfo("提示", "请先选择英文短语")
                return
            hyphenated = selected.replace(" ", "-")
            page.ui_components['input_widget'].delete(tk.SEL_FIRST, tk.SEL_LAST)
            page.ui_components['input_widget'].insert(tk.INSERT, hyphenated)
        except tk.TclError:
            messagebox.showinfo("提示", "请先选择英文短语")
    
    separator = ctk.CTkFrame(bracket_frame, width=2, height=28, fg_color="#cccccc")
    separator.pack(side="left", padx=(0, 8))
    
    ctk.CTkButton(bracket_frame, text="连字符", command=replace_spaces_with_hyphen,
                  font=("微软雅黑", 12), width=80, height=28).pack(side="left")
    
    # 输入框
    input_frame = ctk.CTkFrame(parent, fg_color="#f9fcff")
    input_frame.pack(fill="both", expand=True, padx=3)
    
    input_text = ctk.CTkTextbox(input_frame, height=100, font=default_font, fg_color="white")
    input_text.pack(fill="both", expand=True, side="left", padx=(0, 4))
    input_scrollbar = ctk.CTkScrollbar(input_frame, command=input_text.yview)
    input_scrollbar.pack(side="right", fill="y")
    input_text.configure(yscrollcommand=input_scrollbar.set)
    
    # 保存输入框引用
    page.ui_components['input_widget'] = input_text
    # 同步到分页对象
    page.input_widget = input_text
    
    # 启用划词翻译功能
    try:
        from services.text_selection_translator import enable_text_selection_translation
        page.text_translator = enable_text_selection_translation(input_text)
    except Exception as e:
        print(f"[划词翻译] 启用失败: {e}")
    
    # 添加输入框提示文本
    placeholder_text = "请输入要翻译的英文或中文内容...\n支持快捷键：\nCtrl+Enter 翻译\nCtrl+D 清空\nCtrl+T 创建标签"
    
    # 恢复分页的输入内容
    if page.input_text:
        input_text.insert("0.0", page.input_text)
        input_text.configure(text_color="black")
    else:
        input_text.insert("0.0", placeholder_text)
        input_text.configure(text_color="#999999")
    
    def clear_placeholder(event=None):
        """清除提示文本"""
        current_text = input_text.get("0.0", ctk.END).strip()
        if current_text == placeholder_text.strip() or current_text == "":
            input_text.delete("0.0", ctk.END)
            input_text.configure(text_color="black")
    
    def restore_placeholder(event=None):
        """如果输入框为空，恢复提示文本"""
        current_text = input_text.get("0.0", ctk.END).strip()
        if not current_text:
            input_text.insert("0.0", placeholder_text)
            input_text.configure(text_color="#999999")
    
    def save_input_text(event=None):
        """保存输入文本到分页"""
        current_text = input_text.get("0.0", ctk.END).strip()
        if current_text != placeholder_text.strip():
            page.input_text = current_text
        else:
            page.input_text = ""
        page_manager.save_data()
    
    # 绑定事件处理
    input_text.bind('<FocusIn>', clear_placeholder)
    input_text.bind('<Button-1>', clear_placeholder)
    input_text.bind('<KeyPress>', lambda e: input_text.configure(text_color="black"))
    input_text.bind('<KeyRelease>', save_input_text)
    
    def do_translate():
        txt = input_text.get("0.0", ctk.END).strip()
        if not txt or txt == placeholder_text.strip():
            messagebox.showinfo("提示", "请输入内容")
            return
        
        def do_async():
            status_var.set("正在翻译...")
            translated = translate_text(txt)
            page.output_text = translated
            page.last_translation = translated
            if 'output_widget' in page.ui_components:
                page.ui_components['output_widget'].config(state="normal")
                page.ui_components['output_widget'].delete("1.0", tk.END)
                page.ui_components['output_widget'].insert("end", translated)
            save_to_history(txt, translated)
            page_manager.save_data()
            status_var.set("翻译完成")
            global_root.after(2000, lambda: status_var.set("就绪"))
        
        threading.Thread(target=do_async, daemon=True).start()
    
    input_text.bind('<Control-Return>', lambda event: do_translate())
    input_text.bind('<Control-D>', lambda event: clear_input())
    
    def do_expand_text():
        txt = input_text.get("0.0", ctk.END).strip()
        if not txt or txt == placeholder_text.strip():
            messagebox.showinfo("提示", "请输入要扩写的内容")
            return
        
        def on_choose_preset(preset):
            def async_expand():
                expanded = zhipu_text_expand(txt, preset)
                input_text.delete("0.0", ctk.END)
                input_text.insert("end", expanded)
                save_input_text()
            threading.Thread(target=async_expand, daemon=True).start()
        
        show_expand_preset_dialog(callback=on_choose_preset)
    
    # 创建水平按钮框架
    btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
    btn_frame.pack(anchor="w", pady=(8,0))
    
    # 智能扩写按钮
    expand_btn = ctk.CTkButton(btn_frame, text="AI智能扩写", font=default_font, fg_color="#5F378F", command=do_expand_text)
    expand_btn.pack(side="left", padx=(0, 8))
    
    # 图片反推按钮
    def do_image_caption():
        filetypes = [("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.webp")]
        img_path = filedialog.askopenfilename(title="选择图片", filetypes=filetypes)
        if not img_path:
            return
        
        def async_caption():
            if 'output_widget' in page.ui_components:
                page.ui_components['output_widget'].config(state="normal")
                page.ui_components['output_widget'].delete("1.0", tk.END)
                page.ui_components['output_widget'].insert("end", "正在识别图片，请稍候...")
            result = zhipu_image_caption(img_path)
            if 'output_widget' in page.ui_components:
                page.ui_components['output_widget'].config(state="normal")
                page.ui_components['output_widget'].delete("1.0", tk.END)
                page.ui_components['output_widget'].insert("end", result)
            page.output_text = result
            page_manager.save_data()
        
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
    output_title_frame = ctk.CTkFrame(parent, fg_color="transparent")
    output_title_frame.pack(fill="x", anchor="w", pady=(10,2))
    
    # 标题标签
    ctk.CTkLabel(output_title_frame, text="翻译结果（含标签自动拼接）", font=default_font).pack(side="left")
    
    # 按钮框架（右侧对齐）
    output_buttons_frame = ctk.CTkFrame(output_title_frame, fg_color="transparent")
    output_buttons_frame.pack(side="right")
    
    def clear_output():
        try:
            if 'output_widget' in page.ui_components:
                page.ui_components['output_widget'].delete("1.0", "end")
                page.ui_components['output_widget'].delete("1.0", tk.END)
                page.ui_components['output_widget'].config(state="normal")
                page.ui_components['output_widget'].delete("1.0", "end")
            
            page.output_text = ""
            page.last_translation = ""
            page.inserted_tags = {"head": [], "tail": []}
            
            # 清空标签选中状态
            tag_manager = get_page_tag_manager()
            if tag_manager:
                tag_manager.clear_all_selections()
            
            page_manager.save_data()
            
            # 刷新标签UI显示
            refresh_tags_ui()
            
            status_var.set("输出框已清空")
            global_root.after(1000, lambda: status_var.set("就绪"))
            
        except Exception as e:
            status_var.set(f"清空失败: {str(e)}")
            global_root.after(2000, lambda: status_var.set("就绪"))
    
    # 清空按钮
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
    
    # 复制按钮
    def copy_to_clipboard():
        try:
            # 获取当前选中的标签
            tag_manager = get_page_tag_manager()
            head_tags = []
            tail_tags = []
            
            if tag_manager:
                head_tags = tag_manager.get_selected_tags("head")
                tail_tags = tag_manager.get_selected_tags("tail")
            
            # 如果没有选中标签，则使用已插入的标签
            if not head_tags:
                head_tags = page.inserted_tags.get("head", [])
            if not tail_tags:
                tail_tags = page.inserted_tags.get("tail", [])
            
            parts = []
            if head_tags:
                parts.append(', '.join(head_tags))
            if page.last_translation:
                parts.append(page.last_translation)
            if tail_tags:
                parts.append(', '.join(tail_tags))
            
            text = ', '.join(parts)
            if not text:
                status_var.set("输出框为空，无内容可复制")
                global_root.after(3000, lambda: status_var.set("就绪"))
                return
            pyperclip.copy(text)
            status_var.set("内容已复制到剪贴板 ✓")
            global_root.after(3000, lambda: status_var.set("就绪"))
        except Exception as e:
            status_var.set(f"复制失败: {str(e)}")
            global_root.after(3000, lambda: status_var.set("就绪"))
    
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
    output_frame = ctk.CTkFrame(parent, fg_color="#f9fcff")
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
    
    # 保存输出框引用
    page.ui_components['output_widget'] = output_text
    # 同步到分页对象
    page.output_widget = output_text
    
    # 恢复分页的输出内容
    if page.output_text:
        output_text.insert("end", page.output_text)
    
    def get_output_for_copy():
        s = ""
        if page.inserted_tags.get("head"):
            s += ", ".join(page.inserted_tags["head"]) + ", "
        if page.last_translation:
            s += page.last_translation
        return s
    
    # 创建按钮水平容器
    btn_frame = ctk.CTkFrame(parent)
    btn_frame.pack(anchor="w", pady=(12, 2), fill="x")
    
    # 收藏结果按钮
    def save_to_favorites_page():
        input_str = input_text.get("0.0", ctk.END).strip()
        if input_str == placeholder_text.strip():
            input_str = ""
        output_str = get_output_for_copy()
        save_to_favorites(input_str, output_str)
    
    ctk.CTkButton(btn_frame, text="收藏结果", font=default_font, fg_color="green",
                  command=save_to_favorites_page).pack(side="left", padx=(0, 8))
    
    # 翻译按钮
    translate_btn = ctk.CTkButton(btn_frame, text="翻译", font=default_font, fg_color="#4a90e2", command=do_translate)
    translate_btn.pack(side="left", padx=(0, 8))

# 配置文件处理函数
def load_config():
    """加载配置文件"""
    config_file = "config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
    return {}

def save_config(config):
    """保存配置文件"""
    config_file = "config.json"
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        return False

# 默认字体
import sys
if sys.platform == "win32":
    default_font = ("微软雅黑", 13)
    small_font = ("微软雅黑", 11)
    title_font = ("微软雅黑", 14, "bold")
    tag_block_font = ("微软雅黑", 13, "bold")
else:
    default_font = ("PingFang SC", 13)
    small_font = ("PingFang SC", 11)
    title_font = ("PingFang SC", 14, "bold")
    tag_block_font = ("PingFang SC", 13, "bold")


def make_scrollable_flow_area(parent, height=200):
    """创建可滚动的流式布局区域"""
    # 创建主框架
    main_frame = ctk.CTkFrame(parent, fg_color="#f0f0f0")
    main_frame.pack(fill="both", expand=True)
    
    # 创建canvas和滚动条
    canvas = ctk.CTkCanvas(main_frame, highlightthickness=0, bg="#f0f0f0")
    scrollbar = ctk.CTkScrollbar(main_frame, command=canvas.yview)
    
    # 创建内容框架
    scrollable_frame = ctk.CTkFrame(canvas, fg_color="#f0f0f0")
    
    # 配置滚动
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    # 保存内部窗口ID，便于绑定宽度
    window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # 使内部窗口宽度始终匹配canvas，避免水平裁剪
    def _sync_inner_width(event=None):
        try:
            canvas.itemconfigure(window_id, width=canvas.winfo_width())
        except Exception:
            pass
    canvas.bind("<Configure>", _sync_inner_width)
    
    # 设置高度
    canvas.configure(height=height)
    
    # 布局
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    return canvas, scrollable_frame


def create_tag_btn(parent, label, tag_entry, is_selected, on_click, width=None, edit_callback=None, del_callback=None, is_edit_mode=False, tag_type=None):
    """创建标签按钮（美观优化版本 - 现代卡片设计）"""
    # 获取英文提示词和图片路径
    if isinstance(tag_entry, dict):
        en_text = tag_entry.get("en", "")
        image_path = tag_entry.get("image", "")
        url = tag_entry.get("url", "")
    else:
        en_text = tag_entry if isinstance(tag_entry, str) else ""
        image_path = ""
        url = ""
    
    # 优化图片检查：支持相对路径和绝对路径
    has_image = False
    if image_path:
        # 如果是相对路径，转换为绝对路径
        if not os.path.isabs(image_path):
            abs_image_path = os.path.abspath(image_path)
        else:
            abs_image_path = image_path
        has_image = os.path.exists(abs_image_path)
        # 更新image_path为绝对路径，供后续使用
        if has_image:
            image_path = abs_image_path
    
    # 创建主容器 - 使用更现代的设计
    frame_kwargs = {
        "fg_color": ("#ffffff", "#2b2b2b"),  # 明暗主题适配
        "corner_radius": 0,  # 移除圆角
        "border_width": 1,
        "border_color": ("#e1e5e9", "#404040")  # 微妙的边框
    }
    if width:
        frame_kwargs["width"] = width
        frame_kwargs["height"] = width  # 保持正方形
    btn_frame = ctk.CTkFrame(parent, **frame_kwargs)
    
    if has_image:
        try:
            from PIL import Image, ImageTk
            # 加载图片
            img = Image.open(image_path)
            
            # 获取容器尺寸
            container_width = width if width else 140
            container_height = container_width  # 与宽度一致，保持正方形
            
            # 裁剪图片以完全填充容器（居中裁剪）
            img_width, img_height = img.size
            aspect_ratio = img_width / img_height
            container_ratio = container_width / container_height
            
            if aspect_ratio > container_ratio:
                # 图片更宽，按高度缩放后裁剪宽度
                new_height = container_height
                new_width = int(new_height * aspect_ratio)
                img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # 居中裁剪
                left = (new_width - container_width) // 2
                img_cropped = img_resized.crop((left, 0, left + container_width, container_height))
            else:
                # 图片更高，按宽度缩放后裁剪高度
                new_width = container_width
                new_height = int(new_width / aspect_ratio)
                img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # 居中裁剪
                top = (new_height - container_height) // 2
                img_cropped = img_resized.crop((0, top, container_width, top + container_height))
            
            # 使用CTkImage替代ImageTk.PhotoImage以支持高DPI显示
            ctk_image = ctk.CTkImage(
                light_image=img_cropped,
                dark_image=img_cropped,
                size=(container_width-6, container_height-6)  # 留出边框空间
            )
            
            # 创建图片标签，留出边框空间以显示选中效果
            border_offset = 3 if is_selected else 1  # 根据选中状态调整边框偏移
            img_label = ctk.CTkLabel(
                btn_frame,
                image=ctk_image,
                text="",  # 不显示文本
                width=container_width-2*border_offset,
                height=container_height-2*border_offset,
                cursor="hand2"
            )
            img_label.place(x=border_offset, y=border_offset)  # 只设置位置，尺寸在构造函数中设置
            
            # 创建透明浮动文本容器（使用Canvas实现真正透明效果）
            overlay_height = 38  # 固定高度38像素
            text_overlay = tk.Canvas(
                btn_frame,
                width=container_width-2*border_offset,
                height=overlay_height,
                highlightthickness=0,
                bg='black'
            )
            # 底部对齐覆盖，适应边框偏移
            text_overlay.place(x=border_offset, y=container_height-overlay_height-border_offset)
            
            # 创建半透明矩形背景
            overlay_width = container_width-2*border_offset
            text_overlay.create_rectangle(
                0, 0, overlay_width, overlay_height,
                fill='black', stipple='gray50', outline=''
            )
            
            # 在Canvas上创建文本（水平居中显示）
            text_overlay.create_text(
                overlay_width // 2, overlay_height // 2,
                text=label,
                font=("微软雅黑", max(9, int(container_width * 0.06))),
                fill="white",
                anchor="center",
                width=max(100, int(overlay_width * 0.8))
            )
            
            # 点击事件绑定
            def on_frame_click(event):
                on_click()
            
            img_label.bind("<Button-1>", on_frame_click)
            text_overlay.bind("<Button-1>", on_frame_click)
            
            # 如果有网址，添加网址图标和跳转功能
            if url and url.strip():
                # 创建URL图标按钮
                url_icon = ctk.CTkButton(
                    btn_frame,
                    text="🔗",  # 链接图标
                    width=24,
                    height=24,
                    fg_color=("#ffffff", "#2b2b2b"),
                    hover_color=("#f0f0f0", "#404040"),
                    text_color=("#666666", "#cccccc"),
                    corner_radius=12,
                    border_width=1,
                    border_color=("#e0e0e0", "#555555"),
                    command=lambda: open_url_in_browser(url)
                )
                # 将URL图标放置在右上角
                url_icon.place(x=container_width-30, y=6)
                
                def open_url_in_browser(url_to_open):
                    import webbrowser
                    try:
                        webbrowser.open(url_to_open)
                    except Exception as e:
                        print(f"打开网址失败: {e}")
                
                # 将函数绑定到按钮
                url_icon.configure(command=lambda: open_url_in_browser(url))
                
                # 双击图片也可以打开网址（保持原有功能）
                def open_url(event):
                    open_url_in_browser(url)
                img_label.bind("<Double-Button-1>", open_url)
                try:
                    img_label.configure(cursor="hand2")
                except:
                    # 如果hand2也不支持，则跳过cursor设置
                    pass
                
        except Exception as e:
            import traceback
            print(f"图片加载错误: {e}")
            print(f"详细错误信息: {traceback.format_exc()}")
            has_image = False
    
    # 如果没有图片，使用优化的文本布局
    if not has_image:
        # 创建渐变背景文本区域
        text_container = ctk.CTkFrame(
            btn_frame, 
            fg_color=("#f8fafc", "#374151"),  # 微妙的背景色
            corner_radius=0
        )
        # 如果传入了固定宽度，则保证整体为正方形高度
        if width:
            btn_frame.configure(width=width, height=width)
            text_container.configure(height=width - 12)  # 考虑内边距
        text_container.pack(fill="both", expand=True, padx=6, pady=6)
        
        # 中文标签名（主标题）- 现代化设计
        label_text = ctk.CTkLabel(
            text_container,
            text=label,
            font=("微软雅黑", 13, "bold"),  # 稍大的字体
            text_color=("#1f2937", "#f9fafb"),  # 明暗主题适配
            wraplength=120
        )
        label_text.pack(anchor="w", padx=12, pady=(12, 12))
        
        # 初始化本地选中状态以实现乐观更新
        try:
            btn_frame.selected_state = bool(is_selected)
        except Exception:
            btn_frame.selected_state = False
        
        # 点击事件绑定 - 简化版本，直接同步执行业务逻辑
        def on_frame_click(event):
            try:
                # 直接执行业务逻辑，让数据驱动UI更新
                on_click()
                # 业务逻辑执行完毕后，强制更新UI状态以确保同步
                btn_frame.after_idle(update_selection_style)
            except Exception as e:
                print(f"[on_frame_click] 点击处理失败: {e}")
        
        btn_frame.bind("<Button-1>", on_frame_click)
        text_container.bind("<Button-1>", on_frame_click)
        label_text.bind("<Button-1>", on_frame_click)
        
        # 如果有网址，为文本标签添加URL图标
        if url and url.strip():
            def open_url_in_browser(url_to_open):
                import webbrowser
                try:
                    webbrowser.open(url_to_open)
                except Exception as e:
                    print(f"打开网址失败: {e}")
            
            # 创建URL图标按钮
            url_icon = ctk.CTkButton(
                btn_frame,
                text="🔗",  # 链接图标
                width=24,
                height=24,
                fg_color=("#ffffff", "#2b2b2b"),
                hover_color=("#f0f0f0", "#404040"),
                text_color=("#666666", "#cccccc"),
                corner_radius=12,
                border_width=1,
                border_color=("#e0e0e0", "#555555"),
                command=lambda: open_url_in_browser(url)
            )
            # 将URL图标放置在右上角
            container_width = width if width else 140
            url_icon.place(x=container_width-30, y=6)
    
    # 选中状态的现代视觉效果 - 动态设置
    # 现代悬停效果 - 考虑选中状态
    def get_current_selection_state():
        """获取当前标签的选中状态（优先本地状态，回退全局管理器）"""
        # 优先读取本地缓存的选中状态，保证视觉反馈即时
        try:
            if hasattr(btn_frame, "selected_state"):
                return bool(btn_frame.selected_state)
        except Exception:
            pass
        
        # 回退到全局管理器的实时状态
        tag_manager = get_page_tag_manager()
        if tag_manager and tag_type:
            try:
                return tag_manager.is_tag_selected(tag_type, None, label)
            except Exception as e:
                print(f"获取标签选中状态失败: {e}")
        return False  # 默认返回未选中状态
    
    def update_selection_style():
        """动态更新标签选中状态的视觉样式"""
        try:
            # 检查组件是否仍然存在
            if not btn_frame.winfo_exists():
                return
            
            # 获取当前实际的选中状态
            current_selected = get_current_selection_state()
            
            if current_selected:
                btn_frame.configure(
                    border_width=3, 
                    border_color=("#3b82f6", "#60a5fa"),  # 现代蓝色
                    fg_color=("#eff6ff", "#1e3a8a")  # 选中时的背景色
                )
            else:
                btn_frame.configure(
                    border_width=1,
                    border_color=("#e1e5e9", "#404040"),
                    fg_color=("#ffffff", "#2b2b2b")  # 未选中时的背景色
                )
        except tk.TclError as e:
            # 组件已被销毁，忽略错误
            print(f"[update_selection_style] 组件已销毁，跳过样式更新: {e}")
        except Exception as e:
            print(f"[update_selection_style] 样式更新失败: {e}")
    
    # 将update_selection_style函数暴露给外部，以便其他地方调用
    btn_frame.update_selection_style = update_selection_style
    
    # 初始化时设置正确的选中状态
    update_selection_style()
    
    def on_enter(event):
        try:
            if not btn_frame.winfo_exists():
                return
            current_selected = get_current_selection_state()
            if current_selected:
                # 选中状态下的悬停效果
                btn_frame.configure(
                    border_width=3, 
                    border_color=("#2563eb", "#3b82f6"),  # 更深的蓝色
                    fg_color=("#dbeafe", "#1e40af")  # 稍微调整背景色
                )
            else:
                # 未选中状态下的悬停效果
                btn_frame.configure(
                    border_width=2, 
                    border_color=("#d1d5db", "#6b7280"),
                    fg_color=("#f9fafb", "#374151")
                )
        except tk.TclError:
            # 组件已被销毁，忽略错误
            pass
        except Exception as e:
            print(f"[on_enter] 悬停效果更新失败: {e}")
    
    def on_leave(event):
        try:
            if not btn_frame.winfo_exists():
                return
            current_selected = get_current_selection_state()
            if current_selected:
                # 恢复选中状态样式
                btn_frame.configure(
                    border_width=3, 
                    border_color=("#3b82f6", "#60a5fa"),
                    fg_color=("#eff6ff", "#1e3a8a")
                )
            else:
                # 恢复未选中状态样式
                btn_frame.configure(
                    border_width=1,
                    border_color=("#e1e5e9", "#404040"),
                    fg_color=("#ffffff", "#2b2b2b")
                )
        except tk.TclError:
            # 组件已被销毁，忽略错误
            pass
        except Exception as e:
            print(f"[on_leave] 悬停效果恢复失败: {e}")
    
    btn_frame.bind("<Enter>", on_enter)
    btn_frame.bind("<Leave>", on_leave)
    
    # 编辑模式下显示现代化编辑和删除按钮
    if is_edit_mode:
        edit_btn = ctk.CTkButton(
            btn_frame,
            text="✏️",
            width=28,
            height=28,
            fg_color=("#ffffff", "#374151"),  # 明暗主题适配
            hover_color=("#f3f4f6", "#4b5563"),
            text_color=("#374151", "#f9fafb"),
            command=edit_callback,
            corner_radius=0,
            border_width=1,
            border_color=("#d1d5db", "#6b7280")
        )
        edit_btn.place(x=8, y=8)
        
        del_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️",  # 更现代的删除图标
            width=28,
            height=28,
            fg_color=("#fef2f2", "#7f1d1d"),  # 红色主题
            hover_color=("#fee2e2", "#991b1b"),
            text_color=("#dc2626", "#fca5a5"),
            command=del_callback,
            corner_radius=0,
            border_width=1,
            border_color=("#fecaca", "#b91c1c")
        )
        del_btn.place(x=42, y=8)
    
    return btn_frame


def list_layout_canvas(frame, canvas, tags, inserted_tags, tag_type, insert_tag, make_btn):
    """列表布局标签到canvas中 - 固定200x200像素容器"""
    # 清空框架
    for widget in frame.winfo_children():
        widget.destroy()
    
    # 获取容器宽度 - 改进获取逻辑
    max_width = canvas.winfo_width()
    if max_width <= 1:  # 如果canvas还未渲染，尝试获取父容器宽度
        try:
            parent_width = canvas.master.winfo_width()
            if parent_width > 1:
                max_width = parent_width - 20  # 减去滚动条等边距
            else:
                max_width = 800  # 使用更大的默认值
        except:
            max_width = 800  # 使用更大的默认值
    
    # 确保内部frame宽度与可用宽度一致，避免水平裁剪
    try:
        frame.configure(width=max_width)
    except Exception:
        pass
    
    # 列表布局参数 - 固定容器尺寸
    container_size = 200  # 固定容器尺寸200x200
    gap = 12  # 间距
    column_count = max(1, (max_width - gap) // (container_size + gap))  # 自适应列数
    
    # 创建所有标签按钮
    tag_widgets = []
    for label, tag_entry in tags.items():
        # 使用PageTagManager来判断标签是否被选中
        tag_manager = get_page_tag_manager()
        is_selected = False
        if tag_manager:
            is_selected = tag_manager.is_tag_selected(tag_type, None, label)
        else:
            # 回退到原有逻辑 - 使用英文名称判断（因为inserted_tags存储的是英文名）
            tag_en_name = tag_entry.get('en', label) if isinstance(tag_entry, dict) else label
            is_selected = tag_en_name in inserted_tags[tag_type]
        
        # 创建按钮 - 固定尺寸
        btn_frame = make_btn(frame, label, tag_entry, is_selected, 
                           lambda l=label: insert_tag(tag_type, l), width=container_size)
        
        # 确保固定尺寸200x200
        btn_frame.configure(width=container_size, height=container_size)
        
        tag_widgets.append((btn_frame, label))
    
    # 列表布局 - 按行列排列
    row = 0
    col = 0
    for btn_frame, label in tag_widgets:
        # 计算位置
        x = col * (container_size + gap) + gap
        y = row * (container_size + gap) + gap
        
        # 放置按钮 - 位置固定
        btn_frame.place(x=x, y=y)
        
        # 更新行列位置
        col += 1
        if col >= column_count:
            col = 0
            row += 1
    
    # 更新canvas滚动区域
    frame.update_idletasks()
    total_height = (row + 1) * (container_size + gap) + gap
    try:
        frame.configure(height=total_height)
    except Exception:
        pass
    # 使用bbox('all')以匹配内部窗口尺寸
    try:
        canvas.configure(scrollregion=canvas.bbox("all"))
    except Exception:
        canvas.configure(scrollregion=(0, 0, max_width, total_height))


def waterfall_layout_canvas(frame, canvas, tags, inserted_tags, tag_type, insert_tag, make_btn):
    """瀑布流布局标签到canvas中 - 优化版本，减少UI阻塞"""
    # 清空框架
    for widget in frame.winfo_children():
        widget.destroy()
    
    # 获取容器宽度 - 改进获取逻辑
    max_width = canvas.winfo_width()
    if max_width <= 1:  # 如果canvas还未渲染，尝试获取父容器宽度
        try:
            parent_width = canvas.master.winfo_width()
            if parent_width > 1:
                max_width = parent_width - 20  # 减去滚动条等边距
            else:
                max_width = 1200  # 使用更大的默认值
        except:
            max_width = 1200  # 使用更大的默认值
    
    # 瀑布流参数 - 自适应列数，确保等宽标签
    min_column_width = 180  # 增加最小列宽以适应内容
    gap = 15  # 稍微增加间距
    column_count = max(2, min(6, (max_width - gap) // (min_column_width + gap)))  # 自适应列数
    column_width = (max_width - gap * (column_count + 1)) // column_count  # 每列宽度
    column_heights = [0] * column_count  # 记录每列当前高度
    
    # 确保frame宽度与canvas一致
    try:
        frame.configure(width=max_width)
    except Exception:
        pass
    
    # 创建所有标签按钮并估算高度（避免频繁的update_idletasks调用）
    tag_widgets = []
    for label, tag_entry in tags.items():
        # 使用PageTagManager来判断标签是否被选中
        tag_manager = get_page_tag_manager()
        is_selected = False
        if tag_manager:
            is_selected = tag_manager.is_tag_selected(tag_type, None, label)
        else:
            # 回退到原有逻辑 - 直接使用标签名称判断
            is_selected = label in inserted_tags[tag_type]
        
        # 创建按钮 - 传递固定宽度参数确保等宽
        btn_frame = make_btn(frame, label, tag_entry, is_selected, 
                           lambda l=label: insert_tag(tag_type, l), width=column_width)
        
        # 强制设置固定宽度
        btn_frame.configure(width=column_width)
        
        # 优化：直接估算高度，避免频繁的update_idletasks调用
        has_image = isinstance(tag_entry, dict) and tag_entry.get("image", "") and os.path.exists(tag_entry.get("image", ""))
        if has_image:
            # 有图片的标签：图片区域 + 文本覆盖层
            btn_height = column_width + 40  # 正方形图片 + 底部文本区域
        else:
            # 纯文本标签：根据文本长度计算
            text_lines = max(2, (len(label) * 2) // (column_width // 8))  # 更准确的行数估算
            btn_height = 60 + (text_lines - 2) * 25  # 基础高度 + 额外行高
        
        tag_widgets.append((btn_frame, btn_height, label))
    
    # 瀑布流布局 - 按列排列，自动填充最短列
    for btn_frame, btn_height, label in tag_widgets:
        # 找到最短的列
        min_col = min(range(column_count), key=lambda i: column_heights[i])
        
        # 计算位置
        x = min_col * (column_width + gap) + gap
        y = column_heights[min_col] + gap
        
        # 放置按钮 - 使用place确保精确定位
        btn_frame.place(x=x, y=y)
        
        # 更新列高度
        column_heights[min_col] = y + btn_height
    
    # 只在最后进行一次UI更新，减少阻塞
    total_height = max(column_heights) + gap if column_heights else gap
    try:
        frame.configure(height=total_height)
        # 延迟更新滚动区域，避免阻塞
        def update_scroll_region():
            try:
                canvas.configure(scrollregion=(0, 0, max_width, total_height))
            except Exception:
                pass
        frame.after_idle(update_scroll_region)
    except Exception:
        # 回退方案
        canvas.configure(scrollregion=(0, 0, max_width, total_height))


def flow_layout_canvas(frame, canvas, tags, inserted_tags, tag_type, insert_tag, make_btn):
    """流式布局标签到canvas中（支持多种布局模式）"""
    # 获取当前布局模式
    try:
        layout_mode = layout_var.get()
    except:
        layout_mode = "瀑布流"  # 默认瀑布流
    
    if layout_mode == "列表":
        return list_layout_canvas(frame, canvas, tags, inserted_tags, tag_type, insert_tag, make_btn)
    else:
        return waterfall_layout_canvas(frame, canvas, tags, inserted_tags, tag_type, insert_tag, make_btn)


def setup_status_bar(root):
    """设置状态栏"""
    global status_var
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
    return status_var

def setup_topbar(root):
    """设置顶部工具栏"""
    global platform_var, current_platform
    
    def refresh_from_cloud():
        smart_sync_tags()
        if 'global_root' in globals() and hasattr(global_root, 'refresh_tags_ui'):
            global_root.refresh_tags_ui()
        else:
            try:
                if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                    global_root.refresh_tab_list()
                if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                    global_root.refresh_head_tags()
                if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                    global_root.refresh_tail_tags()
            except (NameError, AttributeError):
                pass

def import_tags_from_csv():
    """导入CSV标签文件"""
    import chardet
    global tags_data
    csv_path = filedialog.askopenfilename(filetypes=[("CSV文件", "*.csv")])
    if not csv_path:
        return

    # 检测CSV文件编码
    with open(csv_path, "rb") as f:
        raw_data = f.read(4096)
        result = chardet.detect(raw_data)
        file_encoding = result["encoding"] or "utf-8"
        print(f"检测到文件编码: {file_encoding}")

    new_tags = {"head": {}, "tail": {}}
    try:
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
                
                entry = {"en": en, "usage_count": 0}
                if img_path:
                    if not os.path.isabs(img_path):
                        img_path = os.path.abspath(img_path)
                if img_path and os.path.exists(img_path):
                    entry["image"] = img_path
                
                new_tags[tag_type][tab][zh] = entry

        # 导入完成后让用户选择覆盖或合并
        if messagebox.askyesno("导入方式", "导入完成，是否全量覆盖现有标签？（否则为合并导入）"):
            tags_data = new_tags
        else:
            for tag_type in new_tags:
                for tab in new_tags[tag_type]:
                    if tab not in tags_data[tag_type]:
                        tags_data[tag_type][tab] = {}
                    
                    for zh, new_entry in new_tags[tag_type][tab].items():
                        if zh not in tags_data[tag_type][tab]:
                            tags_data[tag_type][tab][zh] = new_entry
                        else:
                            existing = tags_data[tag_type][tab][zh]
                            if isinstance(existing, str):
                                tags_data[tag_type][tab][zh] = {
                                    "en": existing,
                                    "usage_count": 0
                                }

        save_tags(tags_data)
        # 使用全局可访问的刷新函数
        if hasattr(global_root, 'refresh_tags_ui'):
            global_root.refresh_tags_ui()
        messagebox.showinfo("导入完成", "标签已导入！")

    except Exception as e:
        messagebox.showerror("导入错误", f"导入出错: {e}")


def open_add_api_popup():
    """打开新增API账号弹窗"""
    popup = tk.Toplevel()
    popup.title("新增API账号")
    popup.geometry("350x250")
    popup.resizable(False, False)
    
    tk.Label(popup, text="选择平台：").pack(anchor="w", padx=16, pady=(18, 4))
    
    # 支持的平台键和其显示名称的映射
    platform_keys = ["baidu", "zhipu", "zhipu-glm45"]
    platform_display = {"baidu": "百度翻译", "zhipu": "智谱AI", "zhipu-glm45": "GLM-4.5"}
    
    # 处理api_config为空的情况
    default_platform = list(api_config.keys())[0] if api_config else "baidu"
    plat_var = tk.StringVar(value=default_platform)
    
    # 使用标准化的英文平台键作为选项，避免KeyError
    platform_menu = ttk.Combobox(popup, textvariable=plat_var, values=platform_keys, state="readonly")
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
        
        selected_platform = plat_var.get()
        # 确保选中的平台键在entry_labels中存在
        if selected_platform not in entry_labels:
            selected_platform = "baidu"  # fallback到默认平台
            plat_var.set(selected_platform)
        
        for i, label in enumerate(entry_labels[selected_platform]):
            tk.Label(frame, text=label+":").grid(row=i, column=0, sticky="w", pady=2)
            e = tk.Entry(frame, textvariable=entry_vars[i])
            e.grid(row=i, column=1, sticky="ew", pady=2)
            entry_widgets.append(e)
        for j in range(len(entry_labels[selected_platform]), 2):  # 清理多余
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

def open_settings_popup(root):
    """打开设置弹窗，使用标签页布局整合多个功能"""
    popup = ctk.CTkToplevel(root)
    popup.title("设置")
    popup.geometry("700x600")
    popup.transient(root)
    popup.grab_set()
    popup.resizable(False, False)
    
    # 设置窗口居中
    popup.update_idletasks()
    x = (popup.winfo_screenwidth() - popup.winfo_width()) // 2
    y = (popup.winfo_screenheight() - popup.winfo_height()) // 2
    popup.geometry(f"+{x}+{y}")
    
    # 标题
    ctk.CTkLabel(popup, text="应用设置", font=("微软雅黑", 18, "bold")).pack(pady=(20, 20))
    
    # 创建标签页视图
    tabview = ctk.CTkTabview(popup, width=600, height=420)
    tabview.pack(padx=25, pady=(0, 20), fill="both", expand=True)
    
    # 添加标签页
    tab1 = tabview.add("基础设置")
    tab2 = tabview.add("数据管理")
    tab3 = tabview.add("API与存储")
    tab4 = tabview.add("云端同步")
    tab5 = tabview.add("关于与更新")
    
    # === 标签页5: 关于与更新 ===
    update_frame = ctk.CTkFrame(tab5)
    update_frame.pack(fill="x", padx=20, pady=20)
    
    ctk.CTkLabel(update_frame, text="版本信息", font=("微软雅黑", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
    
    try:
        from services import __version__ as current_version
    except ImportError:
        current_version = "1.0.0"

    ctk.CTkLabel(update_frame, text=f"当前版本: {current_version}", font=default_font).pack(anchor="w", padx=20, pady=5)
    
    latest_version_var = tk.StringVar(value="最新版本: -")
    ctk.CTkLabel(update_frame, textvariable=latest_version_var, font=default_font).pack(anchor="w", padx=20, pady=5)

    def check_update_thread():
        try:
            from services.update_manager import UpdateManager
            updater = UpdateManager()
            latest_version, release_notes = updater.check_for_updates()
            if latest_version:
                latest_version_var.set(f"最新版本: {latest_version}")
                if updater.is_new_version_available(latest_version):
                    if messagebox.askyesno("发现新版本", f"发现新版本 {latest_version}！\n\n{release_notes}\n\n是否立即下载并安装更新？\n\n注意：更新过程中会自动备份当前版本，如果更新失败会自动回滚。"):
                        # 显示更新进度
                        progress_msg = messagebox.showinfo("正在更新", "正在下载并安装更新，请稍候...\n\n更新过程中请勿关闭程序。")
                        
                        # 执行更新
                        update_success = updater.download_and_apply_update()
                        
                        if update_success:
                            messagebox.showinfo("更新成功", f"更新到版本 {latest_version} 成功！\n\n程序将在您下次启动时使用新版本。\n\n建议现在重启程序以使用新功能。")
                        else:
                            messagebox.showerror("更新失败", "更新过程中发生错误，已自动回滚到之前版本。\n\n请检查网络连接或稍后重试。")
                else:
                    messagebox.showinfo("已是最新版", "您当前使用的已是最新版本。")
            else:
                messagebox.showinfo("检查更新", "未检测到新版本或网络连接失败。")
        except Exception as e:
            messagebox.showerror("更新错误", f"检查更新失败: {e}\n\n请检查网络连接和GitHub仓库配置。")

    def start_update_check():
        import threading
        threading.Thread(target=check_update_thread, daemon=True).start()

    ctk.CTkButton(update_frame, text="检查更新", command=start_update_check, font=default_font, height=35).pack(anchor="w", padx=20, pady=20)
    
    # === 标签页1: 基础设置 ===
    # 布局模式设置
    layout_frame = ctk.CTkFrame(tab1)
    layout_frame.pack(fill="x", padx=20, pady=20)
    
    ctk.CTkLabel(layout_frame, text="布局模式", font=("微软雅黑", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
    
    layout_options = ["瀑布流", "列表"]
    def on_layout_change(val):
        global layout_var
        layout_var.set(val)
        # 通过root对象调用刷新函数
        try:
            if hasattr(root, 'refresh_tags_ui'):
                global_root.refresh_tags_ui()
            else:
                # 如果refresh_tags_ui不存在，尝试直接刷新
                status_var.set(f"布局已切换为: {val}")
                global_root.after(2000, lambda: status_var.set("就绪"))
        except Exception as e:
            print(f"布局切换失败: {e}")
    
    layout_menu = ctk.CTkOptionMenu(layout_frame, variable=layout_var, values=layout_options,
                                   command=on_layout_change, font=default_font, height=35)
    layout_menu.pack(anchor="w", padx=20, pady=(0, 20))
    
    # 划词翻译设置
    translation_frame = ctk.CTkFrame(tab1)
    translation_frame.pack(fill="x", padx=20, pady=(20, 0))
    
    ctk.CTkLabel(translation_frame, text="划词翻译设置", font=("微软雅黑", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
    
    # 加载当前配置
    config = load_config()
    translation_api = config.get('translation_api', 'baidu')
    
    # 翻译API选择
    api_label_frame = ctk.CTkFrame(translation_frame, fg_color="transparent")
    api_label_frame.pack(fill="x", padx=20, pady=(0, 10))
    
    ctk.CTkLabel(api_label_frame, text="翻译API：", font=default_font).pack(side="left")
    
    # 翻译API选项
    translation_api_options = ["百度翻译", "智谱AI", "GLM-4.5"]
    translation_api_mapping = {"百度翻译": "baidu", "智谱AI": "zhipu", "GLM-4.5": "zhipu-glm45"}
    reverse_mapping = {v: k for k, v in translation_api_mapping.items()}
    
    translation_api_var = tk.StringVar(value=reverse_mapping.get(translation_api, "百度翻译"))
    
    def on_translation_api_change(selected_display_name):
        """处理翻译API选择变化"""
        api_key = translation_api_mapping[selected_display_name]
        config = load_config()
        config['translation_api'] = api_key
        save_config(config)
        
        # 更新翻译服务的API配置
        try:
            from services.text_selection_translator import update_translation_api
            update_translation_api(api_key)
        except ImportError:
            pass  # 如果模块不存在则忽略
    
    translation_api_menu = ctk.CTkOptionMenu(api_label_frame, variable=translation_api_var, 
                                           values=translation_api_options,
                                           command=on_translation_api_change, 
                                           font=default_font, height=35, width=120)
    translation_api_menu.pack(side="left", padx=(10, 0))
    
    # 添加翻译设置说明
    translation_desc_frame = ctk.CTkFrame(translation_frame, fg_color="transparent")
    translation_desc_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    ctk.CTkLabel(translation_desc_frame, text="💡 划词翻译说明", font=("微软雅黑", 14, "bold"), 
                 text_color=("#666666", "#AAAAAA")).pack(anchor="w", pady=(0, 5))
    ctk.CTkLabel(translation_desc_frame, text="• 在输入框中选择英文文本，停顿1.5秒后自动翻译", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    ctk.CTkLabel(translation_desc_frame, text="• 翻译结果以浮动提示显示，不干扰正常操作", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    
    # === 标签页2: 数据管理 ===
    # 数据导入导出
    data_frame = ctk.CTkFrame(tab2)
    data_frame.pack(fill="x", padx=20, pady=(20, 15))
    
    ctk.CTkLabel(data_frame, text="数据导入导出", font=("微软雅黑", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
    
    # 导入导出按钮容器
    import_export_btn_frame = ctk.CTkFrame(data_frame, fg_color="transparent")
    import_export_btn_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    def import_csv_from_settings():
        popup.destroy()
        import_tags_from_csv()
    
    def export_csv_from_settings():
        popup.destroy()
        from main import export_tags_to_csv
        export_tags_to_csv()
    
    ctk.CTkButton(import_export_btn_frame, text="📥 导入CSV", font=default_font, height=40,
                  fg_color="#17a2b8", hover_color="#138496",
                  command=import_csv_from_settings).pack(side="left", padx=(0, 10))
    
    ctk.CTkButton(import_export_btn_frame, text="📤 导出CSV", font=default_font, height=40,
                  fg_color="#28a745", hover_color="#218838",
                  command=export_csv_from_settings).pack(side="left")
    

    
    # 备份管理
    backup_frame = ctk.CTkFrame(tab2)
    backup_frame.pack(fill="x", padx=20, pady=(0, 15))
    
    ctk.CTkLabel(backup_frame, text="备份管理", font=("微软雅黑", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
    
    def open_restore_backup_from_settings():
        popup.destroy()
        open_restore_backup_popup()
    
    ctk.CTkButton(backup_frame, text="📁 恢复备份", font=default_font, height=40,
                  fg_color="#FF8C00", hover_color="#FFA500",
                  command=open_restore_backup_from_settings).pack(anchor="w", padx=20, pady=(0, 20))
    
    # === 标签页3: API与存储管理 ===
    from services.credentials_manager import get_credentials_manager
    
    def open_credentials_manager():
        """打开API与存储管理窗口"""
        popup.destroy()
        open_credentials_management_window(root)
    
    # API与存储管理说明
    cred_desc_frame = ctk.CTkFrame(tab3, fg_color="transparent")
    cred_desc_frame.pack(fill="x", padx=20, pady=(20, 15))
    
    ctk.CTkLabel(cred_desc_frame, text="🔐 API与存储管理", font=("微软雅黑", 16, "bold")).pack(anchor="w", pady=(0, 10))
    ctk.CTkLabel(cred_desc_frame, text="统一管理翻译API密钥和阿里云存储凭据，支持分类查看和安全存储", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    
    # API与存储管理按钮容器
    cred_btn_frame = ctk.CTkFrame(tab3)
    cred_btn_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    ctk.CTkLabel(cred_btn_frame, text="管理操作", font=("微软雅黑", 14, "bold")).pack(anchor="w", padx=20, pady=(20, 15))
    
    # 打开API与存储管理器按钮
    ctk.CTkButton(cred_btn_frame, text="🔑 打开API与存储管理器", font=default_font, height=45,
                  fg_color="#2E8B57", hover_color="#3CB371",
                  command=lambda: open_credentials_management_window(popup)).pack(anchor="w", padx=20, pady=(0, 20))
    
    # API与存储管理说明
    cred_info_frame = ctk.CTkFrame(tab3, fg_color="transparent")
    cred_info_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    ctk.CTkLabel(cred_info_frame, text="📋 功能说明", font=("微软雅黑", 14, "bold"), 
                 text_color=("#666666", "#AAAAAA")).pack(anchor="w", pady=(0, 5))
    ctk.CTkLabel(cred_info_frame, text="• 分类管理：翻译API和云端存储凭据分类显示", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    ctk.CTkLabel(cred_info_frame, text="• 安全存储：所有敏感数据均采用加密存储", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    ctk.CTkLabel(cred_info_frame, text="• 统一管理：支持百度翻译、智谱AI、阿里云OSS等凭据", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    ctk.CTkLabel(cred_info_frame, text="• 便捷操作：支持添加、编辑、删除和查看操作", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    
    # === 标签页4: 云端同步 ===
    # 云端同步说明
    sync_desc_frame = ctk.CTkFrame(tab4, fg_color="transparent")
    sync_desc_frame.pack(fill="x", padx=20, pady=(20, 15))
    
    ctk.CTkLabel(sync_desc_frame, text="☁️ 云端同步功能", font=("微软雅黑", 16, "bold")).pack(anchor="w", pady=(0, 10))
    ctk.CTkLabel(sync_desc_frame, text="将本地标签和图片数据同步到云端，或从云端下载最新数据", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    
    # 云端同步按钮容器
    sync_btn_frame = ctk.CTkFrame(tab4)
    sync_btn_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    def do_smart_sync_tags():
        popup.destroy()
        try:
            status_var.set("同步中...")
            smart_sync_tags()
            status_var.set("同步完成")
            global_root.after(2000, lambda: status_var.set("就绪"))
        except Exception as e:
            status_var.set(f"同步失败: {str(e)}")
            global_root.after(3000, lambda: status_var.set("就绪"))
    
    def download_from_cloud():
        popup.destroy()
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
                global status_var, tags_data
                status_var.set("正在创建本地备份...")
                backup_filename = f"tags_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                if os.path.exists("tags.json"):
                    shutil.copy2("tags.json", backup_filename)
                if os.path.exists("images"):
                    shutil.copytree("images", f"images_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}", dirs_exist_ok=True)
                
                # 下载云端数据
                status_var.set("正在从云端下载...")
                from oss_sync import download_all
                download_all(status_var, global_root)
                
                # 重新加载数据
                tags_data = load_tags()
                # 通过global_root调用刷新函数以避免NameError
                if 'global_root' in globals() and hasattr(global_root, 'refresh_tags_ui'):
                    global_root.refresh_tags_ui()
                else:
                    # 兼容旧逻辑：尽量通过global_root调用，否则跳过
                    try:
                        if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                            global_root.refresh_tab_list()
                        if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                            global_root.refresh_head_tags()
                        if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                            global_root.refresh_tail_tags()
                    except (NameError, AttributeError):
                        # 当函数尚未定义时避免中断
                        pass
                
                messagebox.showinfo("完成", f"云端数据下载完成！\n本地备份已创建：{backup_filename}")
                status_var.set("云端数据下载完成")
                global_root.after(2000, lambda: status_var.set("就绪"))
                
            except Exception as e:
                messagebox.showerror("下载失败", f"从云端下载失败：{str(e)}")
                status_var.set("下载失败")
                global_root.after(2000, lambda: status_var.set("就绪"))
    
    # 云端同步按钮 - 使用网格布局，两个按钮并排
    ctk.CTkLabel(sync_btn_frame, text="同步操作", font=("微软雅黑", 14, "bold")).pack(anchor="w", padx=20, pady=(20, 15))
    
    # 按钮容器
    btn_container = ctk.CTkFrame(sync_btn_frame, fg_color="transparent")
    btn_container.pack(fill="x", padx=20, pady=(0, 20))
    
    # 上传到云端按钮
    sync_upload_btn = ctk.CTkButton(btn_container, text="⬆️ 上传到云端", font=default_font, 
                                   fg_color="#4682B4", hover_color="#5A9BD4", height=45, width=250,
                                   corner_radius=8, border_width=0,
                                   command=lambda: threading.Thread(target=do_smart_sync_tags, daemon=True).start())
    sync_upload_btn.pack(side="left", padx=(0, 10))
    
    # 从云端下载按钮
    sync_download_btn = ctk.CTkButton(btn_container, text="⬇️ 从云端下载", font=default_font, 
                                     fg_color="#FF6B35", hover_color="#FF8C69", height=45, width=250,
                                     corner_radius=8, border_width=0,
                                     command=lambda: threading.Thread(target=download_from_cloud, daemon=True).start())
    sync_download_btn.pack(side="left")
    
    # 同步状态说明
    status_desc_frame = ctk.CTkFrame(tab4, fg_color="transparent")
    status_desc_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    ctk.CTkLabel(status_desc_frame, text="📋 操作说明", font=("微软雅黑", 14, "bold"), 
                 text_color=("#666666", "#AAAAAA")).pack(anchor="w", pady=(0, 5))
    ctk.CTkLabel(status_desc_frame, text="• 上传到云端：将本地数据同步到云端存储", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    ctk.CTkLabel(status_desc_frame, text="• 从云端下载：下载云端最新数据并自动备份本地数据", 
                 font=default_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w")
    
    # 关闭按钮
    ctk.CTkButton(popup, text="关闭", font=default_font, command=popup.destroy, height=35).pack(pady=(10, 20))


def open_credentials_management_window(root):
    """打开API与存储管理窗口"""
    from services.credentials_manager import get_credentials_manager
    
    # 创建API与存储管理窗口
    cred_window = ctk.CTkToplevel(root)
    cred_window.title("API与存储管理")
    cred_window.geometry("900x700")
    cred_window.transient(root)
    cred_window.grab_set()
    cred_window.resizable(True, True)
    
    # 设置窗口居中
    cred_window.update_idletasks()
    x = (cred_window.winfo_screenwidth() - cred_window.winfo_width()) // 2
    y = (cred_window.winfo_screenheight() - cred_window.winfo_height()) // 2
    cred_window.geometry(f"+{x}+{y}")
    
    # 获取凭据管理器
    cred_manager = get_credentials_manager()
    
    # 标题
    title_frame = ctk.CTkFrame(cred_window, fg_color="transparent")
    title_frame.pack(fill="x", padx=20, pady=(20, 10))
    
    ctk.CTkLabel(title_frame, text="🔐 API与存储管理", font=("微软雅黑", 20, "bold")).pack(side="left")
    
    # 添加凭据按钮
    ctk.CTkButton(title_frame, text="➕ 添加凭据", font=default_font, height=35,
                  fg_color="#28a745", hover_color="#218838",
                  command=lambda: open_add_credential_dialog(cred_window, cred_manager, refresh_credentials_list)).pack(side="right")
    
    # 创建主框架
    main_frame = ctk.CTkFrame(cred_window)
    main_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    # 创建标签页容器
    tabview = ctk.CTkTabview(main_frame)
    tabview.pack(fill="both", expand=True, padx=10, pady=10)
    
    # 创建标签页
    api_tab = tabview.add("🌐 翻译API")
    storage_tab = tabview.add("☁️ 云端存储")
    other_tab = tabview.add("🔧 其他凭据")
    
    # 为每个标签页创建滚动框架
    api_frame = ctk.CTkScrollableFrame(api_tab)
    api_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    storage_frame = ctk.CTkScrollableFrame(storage_tab)
    storage_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    other_frame = ctk.CTkScrollableFrame(other_tab)
    other_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    def refresh_credentials_list():
        """刷新凭据列表"""
        # 清空现有内容
        for widget in api_frame.winfo_children():
            widget.destroy()
        for widget in storage_frame.winfo_children():
            widget.destroy()
        for widget in other_frame.winfo_children():
            widget.destroy()
        
        # 获取所有凭据
        all_credentials = cred_manager.get_credentials()
        credential_types = cred_manager.get_credential_types()
        
        # 定义凭据分类
        api_types = ["baidu_translate", "zhipu_ai", "zhipu_glm45"]
        storage_types = ["aliyun_oss"]
        
        # 显示翻译API
        api_credentials = {k: v for k, v in all_credentials.items() if k in api_types and v}
        if api_credentials:
            for cred_type, credentials in api_credentials.items():
                type_info = credential_types.get(cred_type, {"name": cred_type})
                
                # 类型标题
                type_frame = ctk.CTkFrame(api_frame, fg_color=("#e8f4fd", "#1a4a5c"))
                type_frame.pack(fill="x", pady=(5, 10), padx=5)
                
                ctk.CTkLabel(type_frame, text=f"🔑 {type_info['name']}", 
                            font=("微软雅黑", 16, "bold"), text_color=("#0066cc", "#66b3ff")).pack(anchor="w", padx=15, pady=10)
                
                # 凭据项
                for cred in credentials:
                    create_credential_item(api_frame, cred_type, cred, cred_manager, refresh_credentials_list)
        else:
            # 没有API凭据时显示提示
            empty_frame = ctk.CTkFrame(api_frame, fg_color="transparent")
            empty_frame.pack(fill="x", pady=50)
            
            ctk.CTkLabel(empty_frame, text="🔑 暂无翻译API凭据", font=("微软雅黑", 16, "bold"),
                        text_color=("#999999", "#666666")).pack()
            ctk.CTkLabel(empty_frame, text="点击右上角\"添加凭据\"按钮添加百度翻译、智谱AI等翻译服务凭据",
                        font=default_font, text_color=("#999999", "#666666")).pack(pady=(5, 0))
        
        # 显示云端存储
        storage_credentials = {k: v for k, v in all_credentials.items() if k in storage_types and v}
        if storage_credentials:
            for cred_type, credentials in storage_credentials.items():
                type_info = credential_types.get(cred_type, {"name": cred_type})
                
                # 类型标题
                type_frame = ctk.CTkFrame(storage_frame, fg_color=("#e8f5e8", "#1a4a1a"))
                type_frame.pack(fill="x", pady=(5, 10), padx=5)
                
                ctk.CTkLabel(type_frame, text=f"📂 {type_info['name']}", 
                            font=("微软雅黑", 16, "bold"), text_color=("#28a745", "#5cb85c")).pack(anchor="w", padx=15, pady=10)
                
                # 凭据项
                for cred in credentials:
                    create_credential_item(storage_frame, cred_type, cred, cred_manager, refresh_credentials_list)
        else:
            # 没有存储凭据时显示提示
            empty_frame = ctk.CTkFrame(storage_frame, fg_color="transparent")
            empty_frame.pack(fill="x", pady=50)
            
            ctk.CTkLabel(empty_frame, text="☁️ 暂无云端存储凭据", font=("微软雅黑", 16, "bold"),
                        text_color=("#999999", "#666666")).pack()
            ctk.CTkLabel(empty_frame, text="点击右上角\"添加凭据\"按钮添加阿里云OSS等云存储服务凭据",
                        font=default_font, text_color=("#999999", "#666666")).pack(pady=(5, 0))
        
        # 显示其他凭据
        other_credentials = {k: v for k, v in all_credentials.items() if k not in api_types + storage_types and v}
        if other_credentials:
            for cred_type, credentials in other_credentials.items():
                type_info = credential_types.get(cred_type, {"name": cred_type})
                
                # 类型标题
                type_frame = ctk.CTkFrame(other_frame, fg_color=("#f8f9fa", "#343a40"))
                type_frame.pack(fill="x", pady=(5, 10), padx=5)
                
                ctk.CTkLabel(type_frame, text=f"🔧 {type_info['name']}", 
                            font=("微软雅黑", 16, "bold"), text_color=("#6c757d", "#adb5bd")).pack(anchor="w", padx=15, pady=10)
                
                # 凭据项
                for cred in credentials:
                    create_credential_item(other_frame, cred_type, cred, cred_manager, refresh_credentials_list)
        else:
            # 没有其他凭据时显示提示
            empty_frame = ctk.CTkFrame(other_frame, fg_color="transparent")
            empty_frame.pack(fill="x", pady=50)
            
            ctk.CTkLabel(empty_frame, text="🔧 暂无其他凭据", font=("微软雅黑", 16, "bold"),
                        text_color=("#999999", "#666666")).pack()
            ctk.CTkLabel(empty_frame, text="如有其他类型的凭据需要管理，可通过\"添加凭据\"功能添加",
                        font=default_font, text_color=("#999999", "#666666")).pack(pady=(5, 0))
    
    def create_credential_item(parent, cred_type, credential, cred_manager, refresh_callback):
        """创建凭据项UI"""
        item_frame = ctk.CTkFrame(parent)
        item_frame.pack(fill="x", pady=2, padx=10)
        
        # 左侧信息区域
        info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)
        
        # 设置最大宽度，为右侧按钮预留空间
        info_frame.configure(width=400)
        
        # 凭据名称和状态
        name_status_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        name_status_frame.pack(fill="x", anchor="w")
        
        # 名称
        name_text = credential.get("name", "未命名凭据")
        ctk.CTkLabel(name_status_frame, text=name_text, font=("微软雅黑", 14, "bold")).pack(side="left")
        
        # 状态标签
        status_text = "🔴 已禁用" if credential.get("disabled", False) else "🟢 已启用"
        status_color = ("#dc3545", "#dc3545") if credential.get("disabled", False) else ("#28a745", "#28a745")
        ctk.CTkLabel(name_status_frame, text=status_text, font=small_font,
                    text_color=status_color).pack(side="left", padx=(10, 0))
        
        # 凭据详情（脱敏显示）
        masked_cred = cred_manager.get_masked_credential(cred_type, credential.get("id"))
        if masked_cred:
            credential_types = cred_manager.get_credential_types()
            type_config = credential_types.get(cred_type, {})
            fields = type_config.get("fields", [])
            
            details_text = []
            for field in fields:
                field_key = field["key"]
                if field_key in masked_cred:
                    field_label = field["label"]
                    field_value = masked_cred[field_key]
                    # 限制字段值长度，避免过长文本
                    if len(str(field_value)) > 20:
                        field_value = str(field_value)[:20] + "..."
                    details_text.append(f"{field_label}: {field_value}")
            
            if details_text:
                # 限制整体文本长度
                full_text = " | ".join(details_text)
                if len(full_text) > 80:
                    full_text = full_text[:80] + "..."
                
                ctk.CTkLabel(info_frame, text=full_text, 
                            font=small_font, text_color=("#666666", "#AAAAAA")).pack(anchor="w", pady=(5, 0))
        
        # 时间信息
        time_info = []
        if credential.get("created_at"):
            time_info.append(f"创建: {credential['created_at']}")
        if credential.get("updated_at"):
            time_info.append(f"更新: {credential['updated_at']}")
        
        if time_info:
            ctk.CTkLabel(info_frame, text=" | ".join(time_info), 
                        font=small_font, text_color=("#999999", "#666666")).pack(anchor="w", pady=(2, 0))
        
        # 右侧操作按钮区域
        btn_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        btn_frame.pack(side="right", padx=15, pady=10)
        
        # 确保按钮区域有固定宽度
        btn_frame.configure(width=220)
        
        # 编辑按钮
        ctk.CTkButton(btn_frame, text="✏️ 编辑", font=small_font, width=60, height=30,
                     fg_color="#17a2b8", hover_color="#138496",
                     command=lambda: open_edit_credential_dialog(parent, cred_manager, cred_type, credential, refresh_callback)).pack(side="left", padx=(0, 5))
        
        # 启用/禁用按钮
        toggle_text = "启用" if credential.get("disabled", False) else "禁用"
        toggle_color = "#28a745" if credential.get("disabled", False) else "#ffc107"
        toggle_hover = "#218838" if credential.get("disabled", False) else "#e0a800"
        
        ctk.CTkButton(btn_frame, text=toggle_text, font=small_font, width=60, height=30,
                     fg_color=toggle_color, hover_color=toggle_hover,
                     command=lambda: toggle_credential_status(cred_manager, cred_type, credential, refresh_callback)).pack(side="left", padx=(0, 5))
        
        # 删除按钮
        ctk.CTkButton(btn_frame, text="🗑️ 删除", font=small_font, width=60, height=30,
                     fg_color="#dc3545", hover_color="#c82333",
                     command=lambda: delete_credential(cred_manager, cred_type, credential, refresh_callback)).pack(side="left")
    
    def toggle_credential_status(cred_manager, cred_type, credential, refresh_callback):
        """切换凭据状态"""
        success, message = cred_manager.toggle_credential_status(cred_type, credential.get("id"))
        if success:
            refresh_callback()
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("错误", message)
    
    def delete_credential(cred_manager, cred_type, credential, refresh_callback):
        """删除凭据"""
        if messagebox.askyesno("确认删除", f"确定要删除凭据 '{credential.get('name', '未命名凭据')}' 吗？\n\n此操作不可撤销。"):
            success, message = cred_manager.delete_credential(cred_type, credential.get("id"))
            if success:
                refresh_callback()
                messagebox.showinfo("成功", message)
            else:
                messagebox.showerror("错误", message)
    
    # 初始加载凭据列表
    refresh_credentials_list()
    
    # 底部按钮
    bottom_frame = ctk.CTkFrame(cred_window, fg_color="transparent")
    bottom_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    ctk.CTkButton(bottom_frame, text="关闭", font=default_font, height=35,
                  command=cred_window.destroy).pack(side="right")


def open_add_credential_dialog(parent, cred_manager, refresh_callback):
    """打开添加凭据对话框"""
    dialog = ctk.CTkToplevel(parent)
    dialog.title("添加凭据")
    dialog.geometry("500x750")
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)
    
    # 设置窗口居中
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
    y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
    dialog.geometry(f"+{x}+{y}")
    
    # 标题
    ctk.CTkLabel(dialog, text="添加新凭据", font=("微软雅黑", 18, "bold")).pack(pady=(20, 20))
    
    # 主框架
    main_frame = ctk.CTkFrame(dialog)
    main_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    # 凭据类型选择
    type_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    type_frame.pack(fill="x", padx=20, pady=(20, 10))
    
    ctk.CTkLabel(type_frame, text="凭据类型:", font=default_font).pack(anchor="w")
    
    credential_types = cred_manager.get_credential_types()
    type_names = [info["name"] for info in credential_types.values()]
    type_keys = list(credential_types.keys())
    
    selected_type = tk.StringVar(value=type_names[0] if type_names else "")
    type_menu = ctk.CTkOptionMenu(type_frame, variable=selected_type, values=type_names)
    type_menu.pack(fill="x", pady=(5, 0))
    
    # 动态字段容器
    fields_frame = ctk.CTkFrame(main_frame)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))
    
    # 存储字段变量
    field_vars = {}
    field_widgets = {}
    
    def update_fields():
        """根据选择的凭据类型更新字段"""
        # 清空现有字段
        for widget in fields_frame.winfo_children():
            widget.destroy()
        field_vars.clear()
        field_widgets.clear()
        
        # 获取选中的类型
        selected_name = selected_type.get()
        selected_key = None
        for key, info in credential_types.items():
            if info["name"] == selected_name:
                selected_key = key
                break
        
        if not selected_key:
            return
        
        type_config = credential_types[selected_key]
        fields = type_config.get("fields", [])
        
        # 凭据名称字段
        name_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
        name_frame.pack(fill="x", pady=(10, 5))
        
        ctk.CTkLabel(name_frame, text="凭据名称:", font=default_font).pack(anchor="w")
        name_var = tk.StringVar()
        field_vars["name"] = name_var
        name_entry = ctk.CTkEntry(name_frame, textvariable=name_var, placeholder_text="为此凭据起一个名称")
        name_entry.pack(fill="x", pady=(5, 0))
        field_widgets["name"] = name_entry
        
        # 动态字段
        for field in fields:
            field_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
            field_frame.pack(fill="x", pady=5)
            
            label_text = field["label"]
            if field.get("required", False):
                label_text += " *"
            
            ctk.CTkLabel(field_frame, text=f"{label_text}:", font=default_font).pack(anchor="w")
            
            field_var = tk.StringVar()
            field_vars[field["key"]] = field_var
            
            if field["type"] == "password":
                entry = ctk.CTkEntry(field_frame, textvariable=field_var, show="*", 
                                   placeholder_text=f"请输入{field['label']}")
                entry.pack(fill="x", pady=(5, 0))
                field_widgets[field["key"]] = entry
            elif field["type"] == "select":
                # 下拉选择框
                options = field.get("options", [])
                option_values = [opt["value"] for opt in options]
                option_labels = [opt["label"] for opt in options]
                
                if option_values:
                    field_var.set(option_values[0])  # 设置默认值
                
                select_menu = ctk.CTkOptionMenu(field_frame, variable=field_var, values=option_labels)
                
                # 创建值映射函数
                def create_value_mapper(labels, values):
                    label_to_value = dict(zip(labels, values))
                    value_to_label = dict(zip(values, labels))
                    
                    def on_select(selected_label):
                        field_var.set(label_to_value.get(selected_label, selected_label))
                    
                    return on_select, value_to_label
                
                on_select, value_to_label = create_value_mapper(option_labels, option_values)
                select_menu.configure(command=on_select)
                
                select_menu.pack(fill="x", pady=(5, 0))
                field_widgets[field["key"]] = select_menu
            else:
                entry = ctk.CTkEntry(field_frame, textvariable=field_var,
                                   placeholder_text=f"请输入{field['label']}")
                entry.pack(fill="x", pady=(5, 0))
                field_widgets[field["key"]] = entry
    
    # 绑定类型选择变化事件
    def on_type_change(value):
        update_fields()
    
    type_menu.configure(command=on_type_change)
    
    # 初始化字段
    update_fields()
    
    # 底部按钮
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    def save_credential():
        """保存凭据"""
        # 获取选中的类型
        selected_name = selected_type.get()
        selected_key = None
        for key, info in credential_types.items():
            if info["name"] == selected_name:
                selected_key = key
                break
        
        if not selected_key:
            messagebox.showerror("错误", "请选择凭据类型")
            return
        
        # 收集字段数据
        credential_data = {}
        for field_key, field_var in field_vars.items():
            credential_data[field_key] = field_var.get().strip()
        
        # 验证必填字段
        type_config = credential_types[selected_key]
        for field in type_config.get("fields", []):
            if field.get("required", False) and not credential_data.get(field["key"]):
                messagebox.showerror("错误", f"请填写{field['label']}")
                return
        
        if not credential_data.get("name"):
            # 自动生成名称
            credential_data["name"] = f"{type_config['name']}_{int(time.time())}"
        
        # 保存凭据
        success, message = cred_manager.add_credential(selected_key, credential_data)
        if success:
            dialog.destroy()
            refresh_callback()
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("错误", message)
    
    ctk.CTkButton(btn_frame, text="保存", font=default_font, height=35,
                  fg_color="#28a745", hover_color="#218838",
                  command=save_credential).pack(side="right", padx=(10, 0))
    
    ctk.CTkButton(btn_frame, text="取消", font=default_font, height=35,
                  command=dialog.destroy).pack(side="right")


def open_edit_credential_dialog(parent, cred_manager, cred_type, credential, refresh_callback):
    """打开编辑凭据对话框"""
    dialog = ctk.CTkToplevel(parent)
    dialog.title("编辑凭据")
    dialog.geometry("500x750")
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)
    
    # 设置窗口居中
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
    y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
    dialog.geometry(f"+{x}+{y}")
    
    # 标题
    ctk.CTkLabel(dialog, text="编辑凭据", font=("微软雅黑", 18, "bold")).pack(pady=(20, 20))
    
    # 主框架
    main_frame = ctk.CTkFrame(dialog)
    main_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    # 凭据类型显示（不可编辑）
    type_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    type_frame.pack(fill="x", padx=20, pady=(20, 10))
    
    credential_types = cred_manager.get_credential_types()
    type_info = credential_types.get(cred_type, {"name": cred_type})
    
    ctk.CTkLabel(type_frame, text="凭据类型:", font=default_font).pack(anchor="w")
    ctk.CTkLabel(type_frame, text=type_info["name"], font=("微软雅黑", 14, "bold"),
                text_color=("#666666", "#AAAAAA")).pack(anchor="w", pady=(5, 0))
    
    # 字段容器
    fields_frame = ctk.CTkFrame(main_frame)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))
    
    # 存储字段变量
    field_vars = {}
    
    # 凭据名称字段
    name_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
    name_frame.pack(fill="x", pady=(10, 5))
    
    ctk.CTkLabel(name_frame, text="凭据名称:", font=default_font).pack(anchor="w")
    name_var = tk.StringVar(value=credential.get("name", ""))
    field_vars["name"] = name_var
    name_entry = ctk.CTkEntry(name_frame, textvariable=name_var)
    name_entry.pack(fill="x", pady=(5, 0))
    
    # 动态字段
    type_config = credential_types.get(cred_type, {})
    fields = type_config.get("fields", [])
    
    for field in fields:
        field_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
        field_frame.pack(fill="x", pady=5)
        
        label_text = field["label"]
        if field.get("required", False):
            label_text += " *"
        
        ctk.CTkLabel(field_frame, text=f"{label_text}:", font=default_font).pack(anchor="w")
        
        # 获取原始值（未脱敏）
        original_value = credential.get(field["key"], "")
        field_var = tk.StringVar(value=original_value)
        field_vars[field["key"]] = field_var
        
        if field["type"] == "password":
            entry = ctk.CTkEntry(field_frame, textvariable=field_var, show="*")
            entry.pack(fill="x", pady=(5, 0))
        elif field["type"] == "select":
            # 下拉选择框
            options = field.get("options", [])
            option_values = [opt["value"] for opt in options]
            option_labels = [opt["label"] for opt in options]
            
            # 找到当前值对应的标签
            current_label = original_value
            for opt in options:
                if opt["value"] == original_value:
                    current_label = opt["label"]
                    break
            
            select_menu = ctk.CTkOptionMenu(field_frame, variable=field_var, values=option_labels)
            
            # 设置当前值
            if current_label in option_labels:
                select_menu.set(current_label)
            
            # 创建值映射函数
            def create_value_mapper_edit(labels, values):
                label_to_value = dict(zip(labels, values))
                
                def on_select(selected_label):
                    field_var.set(label_to_value.get(selected_label, selected_label))
                
                return on_select
            
            on_select = create_value_mapper_edit(option_labels, option_values)
            select_menu.configure(command=on_select)
            
            select_menu.pack(fill="x", pady=(5, 0))
        else:
            entry = ctk.CTkEntry(field_frame, textvariable=field_var)
            entry.pack(fill="x", pady=(5, 0))
    
    # 底部按钮
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    def save_changes():
        """保存更改"""
        # 收集字段数据
        credential_data = {}
        for field_key, field_var in field_vars.items():
            credential_data[field_key] = field_var.get().strip()
        
        # 验证必填字段
        for field in fields:
            if field.get("required", False) and not credential_data.get(field["key"]):
                messagebox.showerror("错误", f"请填写{field['label']}")
                return
        
        if not credential_data.get("name"):
            messagebox.showerror("错误", "请填写凭据名称")
            return
        
        # 更新凭据
        success, message = cred_manager.update_credential(cred_type, credential.get("id"), credential_data)
        if success:
            dialog.destroy()
            refresh_callback()
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("错误", message)
    
    ctk.CTkButton(btn_frame, text="保存", font=default_font, height=35,
                  fg_color="#28a745", hover_color="#218838",
                  command=save_changes).pack(side="right", padx=(10, 0))
    
    ctk.CTkButton(btn_frame, text="取消", font=default_font, height=35,
                  command=dialog.destroy).pack(side="right")


def open_restore_backup_popup():
    """打开恢复备份弹窗"""
    import tkinter.filedialog as filedialog
    import json
    
    # 修复：备份文件在项目根目录，不是在views目录
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_files = [f for f in os.listdir(script_dir) if f.startswith("tags_backup_") and f.endswith(".json")]
        
    if not backup_files:
        messagebox.showinfo("提示", "没有找到备份文件")
        return
    
    # 创建备份选择对话框
    popup = ctk.CTkToplevel(global_root)
    popup.title("选择备份文件恢复")
    popup.geometry("500x400")  # 增加窗口高度和宽度
    popup.transient(global_root)
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
            if 'global_root' in globals() and hasattr(global_root, 'refresh_tags_ui'):
                global_root.refresh_tags_ui()
            else:
                try:
                    if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                        global_root.refresh_tab_list()
                    if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                        global_root.refresh_head_tags()
                    if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                        global_root.refresh_tail_tags()
                except (NameError, AttributeError):
                    pass
            
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

def build_ui(root):
    """构建主UI界面"""
    global tags_data, inserted_tags, last_translation, status_var, platform_var, current_platform, global_root, page_manager, head_tab, tail_tab
    global_root = root
    
    # 初始化分页管理器
    page_manager = PageManager()
    page_manager.root = root
    
    # get_page_tag_manager 函数已移到模块级别
    
    # 确保current_platform与services.api模块同步
    import services.api as api_module
    
    tags_data = load_tags()
    inserted_tags = {"head": [], "tail": []}  # 添加mj列表
    last_translation = ""

    # 托盘管理和浏览器轮询已由 app.py 统一处理

    # 窗口标题、图标、geometry 和 minsize 已由 app.py 统一处理
     # 添加状态栏
    status_var = tk.StringVar(value="就绪")
    status_bar = ctk.CTkLabel(
        root,
        textvariable=status_var,
        fg_color="#f0f0f0",
        height=25,
        anchor="w",
        font=("微软雅黑", 12)  # 设置字体为微软雅黑，大小为12
    )
    status_bar.pack(side="bottom", fill="x", padx=5, pady=2)
    # 绑定到分页管理器，便于统一状态显示
    page_manager.status_var = status_var
    # 确保API配置已加载
    try:
        import services.api as api_module
        api_module.load_api_config()
    except Exception as e:
        logger.error(f"Failed to load API config: {e}")
        # 使用统一的错误处理
        show_error_dialog("API配置加载失败", f"无法加载API配置: {e}")
    global platform_var, current_platform
    # 从配置文件加载用户之前保存的平台选择
    config = load_config()
    saved_platform = config.get('current_platform', 'baidu')
    current_platform = saved_platform  # 使用保存的平台设置
    
    # ==== 合并顶部栏按钮区 ====
    topbar = ctk.CTkFrame(root, fg_color="#eef5fb")
    topbar.pack(fill="x", padx=0, pady=(0, 4))
    # 从services.api读取当前平台和平台列表
    try:
        import services.api as api_module
        # 同步更新services.api模块中的current_platform为用户保存的设置
        api_module.current_platform = current_platform
        platform_var = tk.StringVar(value=current_platform)
        platforms = list(api_module.api_config.keys()) or ["baidu", "zhipu", "zhipu-glm45"]
    except Exception:
        platform_var = tk.StringVar(value=current_platform)
        platforms = list(api_config.keys()) or ["baidu", "zhipu", "zhipu-glm45"]

    # 翻译平台选择
    def on_platform_change(val):
        global current_platform
        import services.api as api_module
        current_platform = val
        # 同步更新services.api模块中的current_platform
        api_module.current_platform = val
        platform_var.set(val)
        # 保存平台选择到配置
        try:
            config = load_config()
            config['current_platform'] = val
            save_config(config)
            status_var.set(f"翻译平台已切换为: {val}")
            global_root.after(2000, lambda: status_var.set("就绪"))
        except Exception as e:
            print(f"保存平台配置失败: {e}")
    
    platform_menu = ctk.CTkOptionMenu(topbar, variable=platform_var, values=platforms,
                                      command=on_platform_change)
    platform_menu.pack(side="left", padx=8, pady=3)
    ctk.CTkLabel(topbar, text="翻译平台选择", font=default_font).pack(side="left", padx=(2, 14))
    
    # 布局选择变量（保留用于设置弹窗）
    global layout_var
    layout_var = tk.StringVar(value="瀑布流")

    # 设置按钮（整合多个功能）
    ctk.CTkButton(topbar, text="⚙️ 设置", font=default_font, fg_color="#6c757d", command=lambda: open_settings_popup(root)).pack(side="left", padx=8)

    # 原有独立按钮已整合到设置弹窗中
    # 刷新云端
    def do_smart_sync_tags():
        status_var.set("同步中...")
        smart_sync_tags()  # 你的原有同步逻辑
        status_var.set("同步完成")
        global_root.after(2000, lambda: status_var.set("就绪"))  # 2秒后回到"就绪"2秒后回到“就绪”
    # 云端同步按钮已整合到设置弹窗中
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
                download_all(status_var, global_root)
                
                # 重新加载数据
                global tags_data
                tags_data = load_tags()
                # 通过root对象调用刷新函数
                if 'global_root' in globals() and hasattr(global_root, 'refresh_tags_ui'):
                    global_root.refresh_tags_ui()
                else:
                    # 兼容旧逻辑：尽量通过global_root调用，否则跳过
                    try:
                        if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                            global_root.refresh_tab_list()
                        if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                            global_root.refresh_head_tags()
                        if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                            global_root.refresh_tail_tags()
                    except (NameError, AttributeError):
                        pass
                
                messagebox.showinfo("完成", f"云端数据下载完成！\n本地备份已创建：{backup_filename}")
                status_var.set("云端数据下载完成")
                global_root.after(2000, lambda: status_var.set("就绪"))
                
            except Exception as e:
                messagebox.showerror("下载失败", f"从云端下载失败：{str(e)}")
                status_var.set("下载失败")
                global_root.after(2000, lambda: status_var.set("就绪"))

    # 从云端下载按钮已整合到设置弹窗中
    # 占位拉伸
    ctk.CTkLabel(topbar, text="", font=default_font).pack(side="left", expand=True, fill="x")

    # 收藏夹/历史记录 靠右显示
    ctk.CTkButton(topbar, text="📂 收藏夹", font=("微软雅黑", 13), fg_color="#4a90e2", command=view_favorites).pack(side="right", padx=8)
    ctk.CTkButton(topbar, text="🕘 历史记录", font=("微软雅黑", 13), fg_color="#4a90e2", command=view_history).pack(side="right", padx=8)
    
    main_pane = ctk.CTkFrame(root, fg_color="transparent")
    main_pane.pack(fill="both", expand=True, padx=8, pady=4)

    # 左侧分页导航区域
    page_nav_pane = ctk.CTkFrame(main_pane, fg_color="#f8f9fa", width=200)
    page_nav_pane.pack(side="left", fill="y", padx=(0, 8))
    page_nav_pane.pack_propagate(False)
    
    # 创建分页导航UI
    create_page_navigation_ui(page_nav_pane)

    # 中间翻译区域 - 固定宽度
    io_pane = ctk.CTkFrame(main_pane, fg_color="transparent", width=650)
    io_pane.pack(side="left", fill="y", padx=(0, 8))
    io_pane.pack_propagate(False)
    
    # 保存翻译区域引用到分页管理器
    page_manager.translation_area = io_pane
    
    # 创建当前分页的翻译界面
    create_translation_ui_for_current_page(io_pane)



    
    if not api_config.get("zhipu", []) or all(a.get("disabled") for a in api_config.get("zhipu", [])):
        status_var.set("⚠️ 请先添加API账号（顶部“新增API账号”按钮）")
        global_root.after(5000, lambda: status_var.set("就绪"))



    tag_area = ctk.CTkFrame(main_pane, fg_color="#eaf8fd")
    tag_area.pack(side="right", fill="both", expand=True, padx=(0, 0))

    # 创建顶部按钮行框架
    btn_top_row = ctk.CTkFrame(tag_area, fg_color="transparent")
    btn_top_row.pack(anchor="nw", padx=12, pady=(8, 2))

    is_edit_mode = tk.BooleanVar(value=False)
    def toggle_edit_mode():
        is_edit_mode.set(not is_edit_mode.get())
        if 'global_root' in globals() and hasattr(global_root, 'refresh_tags_ui'):
            global_root.refresh_tags_ui()
        else:
            try:
                if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                    global_root.refresh_tab_list()
                if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                    global_root.refresh_head_tags()
                if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                    global_root.refresh_tail_tags()
            except (NameError, AttributeError):
                pass
    # 编辑按钮放在新框架中，靠左排列
    ctk.CTkButton(btn_top_row, text="编辑", font=default_font, width=60, fg_color="#f4c273", text_color="black", command=toggle_edit_mode).pack(side="left", padx=(0, 10))
    
    # 标签表格管理按钮放在同一框架，水平排列
    ctk.CTkButton(
        btn_top_row,
        text="标签表格", font=default_font, width=80 ,
        command=lambda: open_tag_table_manager(refresh_tab_list)
    ).pack(side="left", padx=(0, 10))

    # 添加标签搜索框
    search_frame = ctk.CTkFrame(tag_area, fg_color="transparent")
    search_frame.pack(anchor="nw", padx=12, pady=(2, 8), fill="x")
    
    search_var = tk.StringVar()
    search_entry = ctk.CTkEntry(
        search_frame,
        placeholder_text="搜索标签...",
        textvariable=search_var,
        width=200,
        font=default_font
    )
    search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
    
    # 绑定搜索事件
    def on_search_change(*args):
        if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
            global_root.refresh_head_tags()
        if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
            global_root.refresh_tail_tags() # 同时刷新尾部标签
    search_var.trace_add("write", on_search_change)

    tag_area.update_idletasks()
    # 动态计算高度分配，基于实际可用空间
    actual_height = tag_area.winfo_height()
    if actual_height and actual_height > 100:
        # 如果能获取到实际高度，使用30%作为头部区域
        half_height = max(int(0.3 * actual_height), 150)
    else:
        # 如果无法获取实际高度，使用更合理的默认值
        half_height = 250

        # --- 头部标签折叠区 ---
    head_block = ctk.CTkFrame(tag_area, fg_color="#eaf8fd")
    head_block.pack(fill="both", expand=True)

    head_toggle_var = tk.BooleanVar(value=True)

    # 折叠/展开按钮
    head_toggle_btn = ctk.CTkButton(
        head_block,
        text="▼ 头部标签",
        font=("微软雅黑", 16, "bold"),
        width=130,
        height=28,
        fg_color="#eaf8fd",
        text_color="#333",
        hover_color="#d9e8ff",
        command=lambda: toggle_head()
    )
    head_toggle_btn.grid(row=0, column=0, sticky="w", padx=(8, 2), pady=(6, 1))  # 减少右侧内边距

    # 始终创建按钮，通过grid_remove控制可见性
    head_add_tab_btn = ctk.CTkButton(
        head_block,
        text="➕Tab",
        width=35,
        font=default_font,
        fg_color="#dadada",
        text_color="black",
        command=lambda: add_edit_tab("head")
    )
    head_add_tag_btn = ctk.CTkButton(
        head_block,
        text="➕标签",
        width=24,
        font=default_font,
        fg_color="#dadada",
        text_color="black",
        command=lambda: add_edit_tag("head")
    )

    # 动态更新按钮可见性
    def update_head_buttons(*args):
        if is_edit_mode.get():
            # 调整pady参数，与尾部保持一致
            head_add_tab_btn.grid(row=0, column=1, padx=(0, 1), pady=(6, 2), sticky="w")
            head_add_tag_btn.grid(row=0, column=2, padx=(0, 8), pady=(6, 2), sticky="w")
        else:
            head_add_tab_btn.grid_remove()
            head_add_tag_btn.grid_remove()

    # 初始状态设置
    update_head_buttons()
    # 绑定编辑模式变化事件
    is_edit_mode.trace_add("write", update_head_buttons)

    # 内容容器（固定 grid 位置）
    head_content = ctk.CTkFrame(head_block, fg_color="#eaf8fd")
    head_content.grid(row=1, column=0, sticky="nsew", padx=8, columnspan=3)  # 注意增加columnspan

    # 让内容区可伸缩
    head_block.grid_rowconfigure(1, weight=1)
    # 修改列配置，与尾部标签区域保持一致
    head_block.grid_columnconfigure(0, weight=0)
    head_block.grid_columnconfigure(1, weight=0)
    head_block.grid_columnconfigure(2, weight=1)

    def toggle_head():
        if head_toggle_var.get():
            head_content.grid_remove()
            head_toggle_btn.configure(text="▶ 头部标签")
            head_toggle_var.set(False)
        else:
            head_content.grid()
            head_toggle_btn.configure(text="▼ 头部标签")
            head_toggle_var.set(True)
        head_block.update_idletasks()

    head_tab_frame = ctk.CTkFrame(head_content, fg_color="transparent")
    head_tab_frame.pack(fill="x", padx=8, pady=(0, 2))
    
    # 获取当前页面的头部标签Tab列表
    global head_tab_names, tail_tab_names
    tag_manager = get_page_tag_manager()
    if tag_manager:
        head_tab_names = tag_manager.get_tab_names("head")
    else:
        # 向后兼容：如果没有标签管理器，使用全局数据
        tags_data = load_tags()
        head_tab_names = list(tags_data["head"].keys())

    
    head_tab = tk.StringVar(value=head_tab_names[0] if head_tab_names else "")


    def select_head_tab(tab):
        head_tab.set(tab)
        refresh_head_tabbar()
        if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
            global_root.refresh_head_tags()

    def refresh_head_tabbar():
        for w in head_tab_frame.winfo_children():
            w.destroy()
        
        # 创建自动换行的容器
        current_row_frame = None
        current_row_width = 0
        # 强制更新容器尺寸
        head_tab_frame.update_idletasks()
        actual_width = head_tab_frame.winfo_width()
        # 真正的自适应：使用实际容器宽度，减去边距
        max_width = max(200, actual_width - 20) if actual_width > 50 else 400  # 最小200像素，减去20像素边距
        # print(f"[DEBUG] refresh_head_tabbar - 实际容器宽度: {actual_width}, 使用宽度: {max_width}, 标签数量: {len(head_tab_names)}")
        # print(f"[DEBUG] head_tab_names: {head_tab_names}")
        
        for i, name in enumerate(head_tab_names):
            # 动态计算按钮实际宽度（基于文本长度）
            text_width = len(name) * 12 + 20  # 估算文本宽度，每个字符约12像素，加上内边距
            btn_width = max(60, text_width) + 2  # 主按钮宽度 + 间距，最小60像素
            if is_edit_mode.get():
                btn_width += 20 + 2 + 20 + 7  # 编辑按钮 + 删除按钮 + 间距
            
            # print(f"[DEBUG] 标签 '{name}' - 文本长度: {len(name)}, 计算宽度: {btn_width}, 当前行宽度: {current_row_width}")
            
            # 如果当前行为空或宽度不够，创建新行
            if current_row_frame is None or current_row_width + btn_width > max_width:
                # print(f"[DEBUG] 创建新行 - 需要宽度: {current_row_width + btn_width}, 最大宽度: {max_width}")
                current_row_frame = ctk.CTkFrame(head_tab_frame, fg_color="transparent")
                current_row_frame.pack(fill="x", pady=(0, 2))
                current_row_width = 0
            
            # 创建主按钮，使用动态宽度
            actual_btn_width = max(60, text_width)
            btn = ctk.CTkButton(current_row_frame, text=name, font=('微软雅黑', 14, 'bold'),
                                fg_color="#3776ff" if name==head_tab.get() else "#dde6fc",
                                text_color="white" if name==head_tab.get() else "#3261a3",
                                width=actual_btn_width, height=24, corner_radius=4,
                                command=lambda n=name: select_head_tab(n))
            btn.pack(side="left", padx=(0, 1), pady=(0,0))
            current_row_width += actual_btn_width + 1
            
            # 编辑模式下添加编辑和删除按钮
            if is_edit_mode.get():
                edit_btn = ctk.CTkButton(current_row_frame, text="✏️", width=20, fg_color="#dadada", text_color="black",
                                       command=lambda n=name: add_edit_tab("head", True, n))
                edit_btn.pack(side="left", padx=(0, 2))
                current_row_width += 20 + 2
                
                del_btn = ctk.CTkButton(current_row_frame, text="❌", width=20, fg_color="red", text_color="white",
                                      command=lambda n=name: delete_tab("head", n))
                del_btn.pack(side="left", padx=(0, 7))
                current_row_width += 20 + 7


    head_canvas, head_frame = make_scrollable_flow_area(head_content, height=half_height-50)
    def _bind_head_mousewheel(event):
        head_canvas.bind_all("<MouseWheel>", _on_head_mousewheel)
    def _unbind_head_mousewheel(event):
        head_canvas.unbind_all("<MouseWheel>")
    def _on_head_mousewheel(event):
        head_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # 在head_frame上绑定
    head_frame.bind("<Enter>", _bind_head_mousewheel)
    head_frame.bind("<Leave>", _unbind_head_mousewheel)

    separator = ctk.CTkFrame(tag_area, height=2, fg_color="#dde3ea")
    separator.pack(fill="x", padx=8, pady=2)

    # --- 尾部标签折叠区 ---
    tail_block = ctk.CTkFrame(tag_area, fg_color="#eaf8fd")
    tail_block.pack(fill="both", expand=True)

    tail_toggle_var = tk.BooleanVar(value=True)

    # 折叠/展开按钮
    tail_toggle_btn = ctk.CTkButton(
        tail_block,
        text="▼ 尾部标签",
        font=("微软雅黑", 16, "bold"),
        width=130,
        height=28,
        fg_color="#eaf8fd",
        text_color="#333",
        hover_color="#d9e8ff",
        command=lambda: toggle_tail()
    )
    tail_toggle_btn.grid(row=0, column=0, sticky="w", padx=(8, 2), pady=(6, 2))

    # 始终创建按钮，通过grid_remove控制可见性
    tail_add_tab_btn = ctk.CTkButton(
        tail_block,
        text="➕Tab",
        width=24,
        font=default_font,
        fg_color="#dadada",
        text_color="black",
        command=lambda: add_edit_tab("tail")
    )
    tail_add_tag_btn = ctk.CTkButton(
        tail_block,
        text="➕标签",
        width=30,
        font=default_font,
        fg_color="#dadada",
        text_color="black",
        command=lambda: add_edit_tag("tail")
    )

    # 动态更新按钮可见性
    def update_tail_buttons(*args):
        if is_edit_mode.get():
            # 减小按钮间间距，设置为紧凑靠左
            tail_add_tab_btn.grid(row=0, column=1, padx=(0, 1), pady=(6, 2), sticky="w")
            tail_add_tag_btn.grid(row=0, column=2, padx=(0, 8), pady=(6, 2), sticky="w")
        else:
            tail_add_tab_btn.grid_remove()
            tail_add_tag_btn.grid_remove()

    # 初始状态设置
    update_tail_buttons()
    # 绑定编辑模式变化事件
    is_edit_mode.trace_add("write", update_tail_buttons)

    # 内容容器（固定 grid 位置）
    tail_content = ctk.CTkFrame(tail_block, fg_color="#eaf8fd")
    tail_content.grid(row=1, column=0, sticky="nsew", padx=8, columnspan=3)
    # 移除固定高度限制，允许自适应布局

    # 让内容区可伸缩
    tail_block.grid_rowconfigure(1, weight=1)
    # 添加：配置列权重确保按钮靠左
    tail_block.grid_columnconfigure(0, weight=0)
    tail_block.grid_columnconfigure(1, weight=0)
    tail_block.grid_columnconfigure(2, weight=1)

    # 添加：强制刷新布局
    tail_block.update_idletasks()

    def toggle_tail():
        if tail_toggle_var.get():
            # 折叠：隐藏内容但保留占位空间
            tail_content.grid_remove()
            tail_toggle_btn.configure(text="▶ 尾部标签")
            tail_toggle_var.set(False)
        else:
            # 展开：恢复内容显示
            tail_content.grid()
            tail_toggle_btn.configure(text="▼ 尾部标签")
            tail_toggle_var.set(True)
        
        # ✅ 强制刷新布局，避免抖动
        tail_block.update_idletasks()
        global_root.update_idletasks()

    tail_tab_frame = ctk.CTkFrame(tail_content, fg_color="transparent")
    tail_tab_frame.pack(fill="x", padx=8, pady=(0, 2))
    
    # 获取当前页面的尾部标签Tab列表
    global tail_tab_names
    tag_manager = get_page_tag_manager()
    if tag_manager:
        tail_tab_names = tag_manager.get_tab_names("tail")
    else:
        # 向后兼容：如果没有标签管理器，使用全局数据
        tags_data = load_tags()
        tail_tab_names = list(tags_data["tail"].keys())

    
    tail_tab = tk.StringVar(value=tail_tab_names[0] if tail_tab_names else "")

    def select_tail_tab(tab):
        tail_tab.set(tab)
        refresh_tail_tabbar()
        if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
            global_root.refresh_tail_tags()

    def refresh_tail_tabbar():
        for w in tail_tab_frame.winfo_children():
            w.destroy()
        
        # 创建自动换行的容器
        current_row_frame = None
        current_row_width = 0
        # 强制更新容器尺寸
        tail_tab_frame.update_idletasks()
        actual_width = tail_tab_frame.winfo_width()
        # 真正的自适应：使用实际容器宽度，减去边距
        max_width = max(200, actual_width - 20) if actual_width > 50 else 400  # 最小200像素，减去20像素边距
        # print(f"[DEBUG] refresh_tail_tabbar - 实际容器宽度: {actual_width}, 使用宽度: {max_width}, 标签数量: {len(tail_tab_names)}")
        
        for i, name in enumerate(tail_tab_names):
            # 动态计算按钮实际宽度（基于文本长度）
            text_width = len(name) * 12 + 20  # 估算文本宽度，每个字符约12像素，加上内边距
            btn_width = max(60, text_width) + 2  # 主按钮宽度 + 间距，最小60像素
            if is_edit_mode.get():
                btn_width += 20 + 2 + 20 + 7  # 编辑按钮 + 删除按钮 + 间距
            
            # 如果当前行为空或宽度不够，创建新行
            if current_row_frame is None or current_row_width + btn_width > max_width:
                current_row_frame = ctk.CTkFrame(tail_tab_frame, fg_color="transparent")
                current_row_frame.pack(fill="x", pady=(0, 2))
                current_row_width = 0
            
            # 创建主按钮，使用动态宽度
            actual_btn_width = max(60, text_width)
            btn = ctk.CTkButton(current_row_frame, text=name, font=('微软雅黑', 14, 'bold'),
                                fg_color='#74e4b6' if name==tail_tab.get() else '#ebf7f0',
                                text_color='white' if name==tail_tab.get() else '#1a7b51',
                                width=actual_btn_width, height=24, corner_radius=4,
                                command=lambda n=name: select_tail_tab(n))
            btn.pack(side="left", padx=(0, 2), pady=(0,1))
            current_row_width += actual_btn_width + 2
            
            # 编辑模式下添加编辑和删除按钮
            if is_edit_mode.get():
                edit_btn = ctk.CTkButton(current_row_frame, text="✏️", width=20, fg_color="#dadada", text_color="black",
                                       command=lambda n=name: add_edit_tab("tail", True, n))
                edit_btn.pack(side="left", padx=(0, 2))
                current_row_width += 20 + 2
                
                del_btn = ctk.CTkButton(current_row_frame, text="❌", width=20, fg_color="red", text_color="white",
                                      command=lambda n=name: delete_tab("tail", n))
                del_btn.pack(side="left", padx=(0, 7))
                current_row_width += 20 + 7


    tail_canvas, tail_frame = make_scrollable_flow_area(tail_content, height=half_height-50)
    def _bind_tail_mousewheel(event):
        global_root.bind_all("<MouseWheel>", _on_tail_mousewheel)
    def _unbind_tail_mousewheel(event):
        global_root.unbind_all("<MouseWheel>")
    def _on_tail_mousewheel(event):
        tail_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    tail_frame.bind("<Enter>", _bind_tail_mousewheel)
    tail_frame.bind("<Leave>", _unbind_tail_mousewheel)

    # 初始化标签管理器
    page_tag_manager = None
    template_manager = TagTemplateManager()
    
    def insert_tag(tag_type, tag_text):
        global status_var
        tag_manager = get_page_tag_manager()
        if not tag_manager:
            print(f"[insert_tag] 错误: 无法获取标签管理器")
            return
        
        print(f"[insert_tag] 开始处理标签点击: {tag_type}/{tag_text}")
        
        # 切换标签选中状态
        success = tag_manager.toggle_tag(tag_type, None, tag_text)  # tab_name为None，自动查找
        
        if success:
            print(f"[insert_tag] 标签状态切换成功，开始保存和刷新")
            # 保存页面数据
            page_manager.save_data()
            
            # 优化：使用批量刷新，减少UI阻塞
            def batch_refresh():
                try:
                    print(f"[insert_tag] 开始批量刷新 - 标签类型: {tag_type}, 标签: {tag_text}")
                    
                    # 先刷新标签UI，确保标签状态正确显示
                    if tag_type == "head":
                        if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                            global_root.refresh_head_tags()
                    elif tag_type == "tail":
                        if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                            global_root.refresh_tail_tags()
                    
                    # 强制UI更新，确保标签状态变化立即生效
                    global_root.update_idletasks()
                    
                    # 然后刷新输出文本，基于最新的标签状态
                    current_page = page_manager.get_current_page()
                    if current_page:
                        print(f"[insert_tag] 刷新页面{current_page.page_id}的输出文本")
                        current_page.refresh_output_text()
                        # 再次强制更新，确保输出文本立即显示
                        global_root.update_idletasks()
                        print(f"[insert_tag] 页面{current_page.page_id}输出文本刷新完成")
                except Exception as e:
                    print(f"[insert_tag] 批量刷新失败: {e}")
            
            # 立即执行刷新，确保用户能及时看到标签变化
            batch_refresh()
            
            # 显示状态通知
            is_selected = tag_manager.is_tag_selected(tag_type, None, tag_text)
            action = "添加" if is_selected else "移除"
            status_var.set(f"{tag_type}标签 {action}: {tag_text}")
            global_root.after(2000, lambda: status_var.set("就绪"))
        else:
            print(f"[insert_tag] 标签状态切换失败: {tag_type}/{tag_text}")

    def refresh_all_layouts():
        """刷新所有布局"""
        if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
            global_root.refresh_head_tags()
        if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
            global_root.refresh_tail_tags()
    
    def refresh_tag_ui_optimized(tag_type, focus_tag=None):
        """优化的标签UI刷新，只刷新指定类型的标签"""
        if tag_type == "head":
            if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                global_root.refresh_head_tags(focus_tag)
        elif tag_type == "tail":
            if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                global_root.refresh_tail_tags(focus_tag)
        else:
            # 如果类型未指定，刷新所有
            if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                global_root.refresh_head_tags(focus_tag)
            if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                global_root.refresh_tail_tags(focus_tag)
    
    def refresh_head_tags(focus_tag=None):
        # 优化：只获取一次标签管理器，避免重复调用
        tag_manager = get_page_tag_manager()
        current_tab = head_tab.get()
        print(f"[DEBUG] refresh_head_tags - 当前选中的头部标签页: '{current_tab}'")
        
        if not tag_manager:
            tags = tags_data["head"].get(current_tab, {})
            print(f"[DEBUG] 使用全局数据，'{current_tab}'分类下有{len(tags)}个标签: {list(tags.keys())}")
        else:
            all_tags = tag_manager.get_all_tags("head")
            tags = all_tags.get(current_tab, {}) if current_tab else {}
            print(f"[DEBUG] 使用标签管理器，'{current_tab}'分类下有{len(tags)}个标签: {list(tags.keys())}")
        
        # 优化：提前过滤和排序，减少后续处理
        search_text = search_var.get().lower()
        if search_text:
            tags = {k: v for k, v in tags.items() if search_text in k.lower()}
        tags = dict(sorted(tags.items(), key=lambda item: (
            item[1].get('usage_count', 0) // 10
        ), reverse=True))
        
        # 优化：批量销毁子组件
        children = head_frame.winfo_children()
        if children:
            for w in children:
                w.destroy()
        
        # 清空当前分页的头部标签UI状态
        if page_manager:
            current_page = page_manager.get_current_page()
            if current_page:
                ui_state_manager.clear_tag_ui_state(current_page.page_id, "head")
        
        def make_btn(parent, label, tag_entry, is_selected, on_click, width=None):
            btn_frame = create_tag_btn(
                parent, label, tag_entry, is_selected, on_click, width=width,
                edit_callback=lambda l=label: add_edit_tag("head", True, l, tag_entry, head_tab.get(), root),
                del_callback=lambda l=label: delete_tag("head", l),
                is_edit_mode=is_edit_mode.get(),
                tag_type="head"
            )
            if focus_tag and label == focus_tag:
                btn_frame.configure(fg_color="#FFD700")  # 高亮色
            btn_frame.bind("<Enter>", _bind_head_mousewheel)
            btn_frame.bind("<Leave>", _unbind_head_mousewheel)
            for child in btn_frame.winfo_children():
                child.bind("<Enter>", _bind_head_mousewheel)
                child.bind("<Leave>", _unbind_head_mousewheel)
            
            # 记录标签UI状态
            if page_manager:
                current_page = page_manager.get_current_page()
                if current_page:
                    tag_ui_info = {
                        'label': label,
                        'tab': head_tab.get(),
                        'is_selected': is_selected,
                        'is_visible': True,
                        'position': len(parent.winfo_children())
                    }
                    ui_state_manager.set_tag_ui_state(current_page.page_id, "head", label, tag_ui_info)
            
            return btn_frame
        
        # 优化：复用已获取的标签管理器，避免重复调用
        current_inserted_tags = {"head": [], "tail": []}
        if tag_manager:
            current_inserted_tags = {
                "head": tag_manager.get_selected_tags("head"),
                "tail": tag_manager.get_selected_tags("tail")
            }
        elif page_manager:
            current_page = page_manager.get_current_page()
            if current_page:
                current_inserted_tags = current_page.inserted_tags
        
        flow_layout_canvas(head_frame, head_canvas, tags, current_inserted_tags, "head", insert_tag, make_btn)
    
    def refresh_tail_tags(focus_tag=None):
        # 优化：只获取一次标签管理器，避免重复调用
        tag_manager = get_page_tag_manager()
        if not tag_manager:
            tags = tags_data["tail"].get(tail_tab.get(), {})
        else:
            current_tab = tail_tab.get()
            all_tags = tag_manager.get_all_tags("tail")
            tags = all_tags.get(current_tab, {}) if current_tab else {}
        
        # 优化：提前过滤和排序，减少后续处理
        search_text = search_var.get().lower()
        if search_text:
            tags = {k: v for k, v in tags.items() if search_text in k.lower()}
        tags = dict(sorted(tags.items(), key=lambda item: (
            item[1].get('usage_count', 0) // 10
        ), reverse=True))
        
        # 优化：批量销毁子组件
        children = tail_frame.winfo_children()
        if children:
            for w in children:
                w.destroy()
        
        # 清空当前分页的尾部标签UI状态
        if page_manager:
            current_page = page_manager.get_current_page()
            if current_page:
                ui_state_manager.clear_tag_ui_state(current_page.page_id, "tail")
        
        def make_btn(parent, label, tag_entry, is_selected, on_click, width=None):
            btn_frame = create_tag_btn(
                parent, label, tag_entry, is_selected, on_click, width=width,
                edit_callback=lambda l=label: add_edit_tag("tail", True, l, tag_entry, tail_tab.get(), root),
                del_callback=lambda l=label: delete_tag("tail", l),
                is_edit_mode=is_edit_mode.get(),
                tag_type="tail"
            )
            if focus_tag and label == focus_tag:
                btn_frame.configure(fg_color="#FFD700")  # 高亮色
            btn_frame.bind("<Enter>", _bind_tail_mousewheel)
            btn_frame.bind("<Leave>", _unbind_tail_mousewheel)
            for child in btn_frame.winfo_children():
                child.bind("<Enter>", _bind_tail_mousewheel)
                child.bind("<Leave>", _unbind_tail_mousewheel)
            
            # 记录标签UI状态
            if page_manager:
                current_page = page_manager.get_current_page()
                if current_page:
                    tag_ui_info = {
                        'label': label,
                        'tab': tail_tab.get(),
                        'is_selected': is_selected,
                        'is_visible': True,
                        'position': len(parent.winfo_children())
                    }
                    ui_state_manager.set_tag_ui_state(current_page.page_id, "tail", label, tag_ui_info)
            
            return btn_frame
        
        # 优化：复用已获取的标签管理器，避免重复调用
        current_inserted_tags = {"head": [], "tail": []}
        if tag_manager:
            current_inserted_tags = {
                "head": tag_manager.get_selected_tags("head"),
                "tail": tag_manager.get_selected_tags("tail")
            }
        elif page_manager:
            current_page = page_manager.get_current_page()
            if current_page:
                current_inserted_tags = current_page.inserted_tags
        
        flow_layout_canvas(tail_frame, tail_canvas, tags, current_inserted_tags, "tail", insert_tag, make_btn)


    def delete_tab(tag_type, tabname):
        if messagebox.askyesno("确认", f"确定要删除{('头部' if tag_type=='head' else '尾部')}Tab【{tabname}】及其标签吗？"):
            # 从全局标签库删除标签页数据
            tags_data[tag_type].pop(tabname, None)
            save_tags(tags_data)
            
            # 同步删除到所有分页的标签数据
            if page_manager:
                for page in page_manager.pages.values():
                    tag_manager = page.get_tag_manager()
                    if tag_manager and tag_type in tag_manager.tags:
                        if tabname in tag_manager.tags[tag_type]:
                            tag_manager.tags[tag_type].pop(tabname, None)
                # 保存分页数据
                page_manager.save_pages_data()
            
            # 更新全局变量
            global head_tab_names, tail_tab_names
            head_tab_names = list(tags_data["head"].keys())
            tail_tab_names = list(tags_data["tail"].keys())
            
            # 如果删除的是当前选中的标签页，切换到第一个可用的标签页
            current_tab = head_tab.get() if tag_type == "head" else tail_tab.get()
            if current_tab == tabname:
                available_tabs = head_tab_names if tag_type == "head" else tail_tab_names
                if available_tabs:
                    new_tab = available_tabs[0]
                    if tag_type == "head":
                        head_tab.set(new_tab)
                    else:
                        tail_tab.set(new_tab)
            
            # 刷新UI
            if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                global_root.refresh_tab_list()
            
            # 刷新标签页内容显示
            if tag_type == "head":
                if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                    global_root.refresh_head_tags()
            else:
                if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                    global_root.refresh_tail_tags()
            
            print(f"已删除{('头部' if tag_type=='head' else '尾部')}标签页: {tabname}")

    def delete_tag(tag_type, label):
        """
        删除指定标签并立即刷新显示
        """
        # 找出当前所在的 Tab
        tab = head_tab.get() if tag_type == "head" else tail_tab.get()
        if tab and label in tags_data[tag_type].get(tab, {}):
            # 获取标签条目
            tag_entry = tags_data[tag_type][tab][label]
            # 检查是否有图片路径并删除文件
            if isinstance(tag_entry, dict) and 'image' in tag_entry:
                image_path = tag_entry['image']
                # 统一解析为绝对路径再删除
                abs_img_path = os.path.join(PROJECT_ROOT, image_path) if not os.path.isabs(image_path) else image_path
                if os.path.exists(abs_img_path):
                    try:
                        os.remove(abs_img_path)
                        status_var.set(f"已删除图片文件: {abs_img_path}")
                        global_root.after(2000, lambda: status_var.set("就绪"))
                    except Exception as e:
                        status_var.set(f"删除图片失败: {str(e)}")
                        root.after(2000, lambda: status_var.set("就绪"))
            
            # 从全局标签库删除标签数据
            tags_data[tag_type][tab].pop(label, None)
            save_tags(tags_data)
            
            # 同步删除到所有分页的标签数据
            if page_manager:
                for page in page_manager.pages.values():
                    tag_manager = page.get_tag_manager()
                    if tag_manager:
                        tag_manager.remove_tag(tag_type, tab, label)
                # 保存分页数据
                page_manager.save_pages_data()
            
            # 如果该 Tab 下已经没有标签，顺便移除空 Tab（可选）
            if not tags_data[tag_type].get(tab):
                tags_data[tag_type].pop(tab, None)
                save_tags(tags_data)
                if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                    global_root.refresh_tab_list()
            else:
                # 仅刷新当前标签列表
                if tag_type == "head":
                    if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                        global_root.refresh_head_tags()
                else:
                    if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                        global_root.refresh_tail_tags()

    def delete_tag_in_table(tag_type, tab, label):
        # 获取标签条目
        tag_entry = tags_data[tag_type][tab].get(label)
        if tag_entry:
            # 检查是否有图片路径并删除文件
            if isinstance(tag_entry, dict) and 'image' in tag_entry:
                image_path = tag_entry['image']
                # 统一解析为绝对路径再删除
                abs_img_path = os.path.join(PROJECT_ROOT, image_path) if not os.path.isabs(image_path) else image_path
                if os.path.exists(abs_img_path):
                    try:
                        os.remove(abs_img_path)
                        status_var.set(f"已删除图片文件: {abs_img_path}")
                        root.after(2000, lambda: status_var.set("就绪"))
                    except Exception as e:
                        status_var.set(f"删除图片失败: {str(e)}")
                        root.after(2000, lambda: status_var.set("就绪"))
        
        # 从全局标签库删除标签数据
        tags_data[tag_type][tab].pop(label, None)
        if not tags_data[tag_type][tab]:
            tags_data[tag_type].pop(tab)
        save_tags(tags_data)
        
        # 同步删除到所有分页的标签数据
        if page_manager:
            for page in page_manager.pages.values():
                tag_manager = page.get_tag_manager()
                if tag_manager:
                    tag_manager.remove_tag(tag_type, tab, label)
            # 保存分页数据
            page_manager.save_pages_data()
        
        refresh_table_view()    # 弹窗自己刷新
        if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
            global_root.refresh_tab_list()      # 主界面也刷新
 

                
    def open_tag_table_manager(refresh_callback=None):
        """打开标签表格管理窗口"""
        table_window = ctk.CTkToplevel(root)
        table_window.title("标签表格管理")
        table_window.geometry("900x600")
        table_window.transient(root)
        table_window.grab_set()
        table_window.resizable(True, True)
        
        # 设置窗口居中
        table_window.update_idletasks()
        x = (table_window.winfo_screenwidth() - table_window.winfo_width()) // 2
        y = (table_window.winfo_screenheight() - table_window.winfo_height()) // 2
        table_window.geometry(f"+{x}+{y}")
        
        # 创建主框架
        main_frame = ctk.CTkFrame(table_window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 标题
        title_label = ctk.CTkLabel(main_frame, text="标签表格管理", font=("微软雅黑", 18, "bold"))
        title_label.pack(pady=(10, 20))
        
        # 创建表格框架
        table_frame = ctk.CTkFrame(main_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 创建Treeview表格
        columns = ("类型", "分类", "中文标签", "英文提示词", "使用次数", "图片")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)
        
        # 设置列标题和宽度
        tree.heading("类型", text="类型")
        tree.heading("分类", text="分类")
        tree.heading("中文标签", text="中文标签")
        tree.heading("英文提示词", text="英文提示词")
        tree.heading("使用次数", text="使用次数")
        tree.heading("图片", text="图片")
        
        tree.column("类型", width=60, minwidth=50)
        tree.column("分类", width=100, minwidth=80)
        tree.column("中文标签", width=150, minwidth=120)
        tree.column("英文提示词", width=300, minwidth=200)
        tree.column("使用次数", width=80, minwidth=60)
        tree.column("图片", width=80, minwidth=60)
        
        # 添加滚动条
        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        scrollbar_x = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # 布局表格和滚动条
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        def refresh_table_view():
            """刷新表格视图"""
            # 清空现有数据
            for item in tree.get_children():
                tree.delete(item)
            
            # 重新加载标签数据
            current_tags_data = load_tags()
            
            # 填充表格数据
            for tag_type in ["head", "tail"]:
                type_name = "头部" if tag_type == "head" else "尾部"
                if tag_type in current_tags_data:
                    for tab_name, tab_data in current_tags_data[tag_type].items():
                        if isinstance(tab_data, dict):
                            for zh_label, tag_info in tab_data.items():
                                if isinstance(tag_info, dict):
                                    en_text = tag_info.get("en", "")
                                    usage_count = tag_info.get("usage_count", 0)
                                    has_image = "是" if tag_info.get("image") else "否"
                                else:
                                    en_text = tag_info if isinstance(tag_info, str) else ""
                                    usage_count = 0
                                    has_image = "否"
                                
                                # 插入数据行
                                item_id = tree.insert("", "end", values=(
                                    type_name, tab_name, zh_label, en_text, usage_count, has_image
                                ), tags=(tag_type, tab_name, zh_label))
        
        # 按钮框架
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 0))
        
        def delete_selected_tag():
            """删除选中的标签"""
            selected_item = tree.selection()
            if not selected_item:
                messagebox.showwarning("警告", "请先选择要删除的标签")
                return
            
            item = selected_item[0]
            tags = tree.item(item, "tags")
            if len(tags) >= 3:
                tag_type, tab_name, zh_label = tags[0], tags[1], tags[2]
                
                if messagebox.askyesno("确认删除", f"确定要删除标签 '{zh_label}' 吗？"):
                    delete_tag_in_table(tag_type, tab_name, zh_label)
        
        def edit_selected_tag():
            """编辑选中的标签"""
            selected_item = tree.selection()
            if not selected_item:
                messagebox.showwarning("警告", "请先选择要编辑的标签")
                return
            
            item = selected_item[0]
            tags = tree.item(item, "tags")
            if len(tags) >= 3:
                tag_type, tab_name, zh_label = tags[0], tags[1], tags[2]
                current_tags_data = load_tags()
                tag_entry = current_tags_data[tag_type][tab_name].get(zh_label)
                add_edit_tag(tag_type, edit=True, label=zh_label, tag_entry=tag_entry, current_tab=tab_name, parent_window=table_window)
        
        # 添加按钮
        ctk.CTkButton(button_frame, text="删除选中", fg_color="#dc3545", hover_color="#c82333", 
                     command=delete_selected_tag).pack(side="left", padx=(0, 10))
        ctk.CTkButton(button_frame, text="编辑选中", fg_color="#ffc107", text_color="black", 
                     hover_color="#e0a800", command=edit_selected_tag).pack(side="left", padx=(0, 10))
        ctk.CTkButton(button_frame, text="刷新", fg_color="#28a745", hover_color="#218838", 
                     command=refresh_table_view).pack(side="left", padx=(0, 10))
        ctk.CTkButton(button_frame, text="关闭", fg_color="#6c757d", hover_color="#5a6268", 
                     command=table_window.destroy).pack(side="right")
        
        # 初始化表格数据
        refresh_table_view()
        
        # 双击编辑功能
        def on_double_click(event):
            edit_selected_tag()
        
        tree.bind("<Double-1>", on_double_click)
    
    def add_edit_tab(tag_type, edit=False, tabname=None):
        win = ctk.CTkToplevel(root)
        win.title("添加/编辑Tab")
        win.geometry("340x150")
        win.attributes('-topmost', True)  # 设置窗口置顶
        ctk.CTkLabel(win, text="Tab名称").pack()
        tab_var = tk.StringVar(value=tabname if edit else "")
        ctk.CTkEntry(win, textvariable=tab_var).pack()
        def save_():
            t = tab_var.get().strip()
            if not t:
                messagebox.showerror("错误", "请输入Tab名称")
                return
            if edit:
                # 重命名Tab时保留原有标签
                if t != tabname:  # 只有在名称真正改变时才进行重命名
                    old_data = tags_data[tag_type].pop(tabname, {})
                    tags_data[tag_type][t] = old_data
                    
                    # 同步更新所有分页中的标签页名称
                    if page_manager:
                        for page in page_manager.pages.values():
                            if tag_type in page.tags and tabname in page.tags[tag_type]:
                                # 重命名分页中的标签页
                                page_tab_data = page.tags[tag_type].pop(tabname, {})
                                page.tags[tag_type][t] = page_tab_data
                                print(f"[add_edit_tab] 已更新分页{page.page_id}中的标签页: {tabname} -> {t}")
                        # 保存分页数据
                        page_manager.save_pages_data()
                # 如果名称没有改变，不需要做任何操作
            else:
                # 新建Tab
                tags_data[tag_type][t] = {}
            save_tags(tags_data)
            
            # 更新全局变量
            global head_tab_names, tail_tab_names
            head_tab_names = list(tags_data["head"].keys())
            tail_tab_names = list(tags_data["tail"].keys())
            
            # 刷新UI
            if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                global_root.refresh_tab_list()
            
            # 刷新标签页内容显示
            if tag_type == "head":
                if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
                    global_root.refresh_head_tags()
            else:
                if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
                    global_root.refresh_tail_tags()
            
            win.destroy()
        ctk.CTkButton(win, text="确定", fg_color="#19a8b9", command=save_).pack(pady=12)

    def add_edit_tag(tag_type, edit=False, label=None, tag_entry=None, current_tab=None, parent_window=None):
        global status_var, global_root, head_tab, tail_tab, tags_data
        parent = parent_window if parent_window is not None else root
        win = ctk.CTkToplevel(parent)
        win.title("添加/编辑标签")
        win.geometry("370x370")
        win.attributes('-topmost', True)  # 窗口置顶
        # 将弹窗设为父窗口的从属并接管输入事件
        try:
            win.transient(parent)
            win.grab_set()
        except Exception:
            pass
        win.lift()
        win.focus_set()
        ctk.CTkLabel(win, text="Tab选择").pack()

        # 在编辑模式下使用传入的current_tab，否则使用当前选中的tab
        if edit and current_tab:
            cur_tab = current_tab
        else:
            cur_tab = head_tab.get() if tag_type == "head" else tail_tab.get()
        tab_var = tk.StringVar(value=cur_tab)
        tab_combo = ttk.Combobox(win, textvariable=tab_var, values=list(tags_data[tag_type].keys()), state="readonly")
        tab_combo.pack()

        # 中文标签名
        ctk.CTkLabel(win, text="中文标签名").pack()
        label_var = tk.StringVar(value=label if edit else "")
        ctk.CTkEntry(win, textvariable=label_var).pack()

        # 英文提示词
        ctk.CTkLabel(win, text="英文提示词").pack()
        if tag_entry and isinstance(tag_entry, dict):
            en_val = tag_entry.get("en", "")
            img_val = tag_entry.get("image", "")
        else:
            en_val = tag_entry if tag_entry and isinstance(tag_entry, str) else ""
            img_val = ""
        en_var = tk.StringVar(value=en_val)
        ctk.CTkEntry(win, textvariable=en_var).pack(pady=4)

        # 图片上传
        img_path_var = tk.StringVar(value=img_val)

        def upload_img():
            from image_tools import select_and_crop_image
            import uuid
            label_for_img = label_var.get().strip() or "tag"
            save_path = select_and_crop_image(label_for_img, box_size=(200, 200))
            if not save_path:
                return
            img_path_var.set(save_path)
            # 显示缩略图
            try:
                from PIL import Image, ImageTk
                im2 = Image.open(save_path).resize((48, 48))
                # 使用CTkImage替代ImageTk.PhotoImage
                ctk_image = ctk.CTkImage(
                    light_image=im2,
                    dark_image=im2,
                    size=(48, 48)
                )
                if hasattr(upload_img, "preview_label"):
                    upload_img.preview_label.configure(image=ctk_image)
                else:
                    upload_img.preview_label = ctk.CTkLabel(win, image=ctk_image, text="")
                    upload_img.preview_label.pack()
            except Exception as e:
                print(f"预览图显示错误: {e}")

        ctk.CTkButton(win, text="上传图片（正方裁剪）", command=upload_img).pack(pady=5)



        if img_val:
            try:
                im = Image.open(img_val).resize((48, 48))
                # 使用CTkImage替代ImageTk.PhotoImage
                ctk_image = ctk.CTkImage(
                    light_image=im,
                    dark_image=im,
                    size=(48, 48)
                )
                upload_img.preview_label = ctk.CTkLabel(win, image=ctk_image, text="")
                upload_img.preview_label.pack()
            except Exception:
                pass

        # ================== 保存函数 ==================
        def save_():
            nonlocal tag_type
            tab_name = tab_var.get().strip()
            zh_name = label_var.get().strip()
            en_name = en_var.get().strip()
            img_path = img_path_var.get()

            if not (tab_name and zh_name and en_name):
                messagebox.showerror("错误", "请完整填写所有字段")
                return

            # ✅ 如果是编辑模式，先删除旧标签（但不删除旧 tab）
            if edit and label:
                # 找到标签原来的 tab 并获取旧图片路径
                for tab_key, tab_data in tags_data[tag_type].items():
                    if label in tab_data:
                        old_tag_entry = tab_data[label]
                        # 删除旧图片文件
                        if isinstance(old_tag_entry, dict) and 'image' in old_tag_entry:
                            old_image_path = old_tag_entry['image']
                            if old_image_path:
                                # 统一解析为绝对路径再删除
                                abs_old_img_path = os.path.join(PROJECT_ROOT, old_image_path) if not os.path.isabs(old_image_path) else old_image_path
                                if os.path.exists(abs_old_img_path) and abs_old_img_path != img_path:
                                    try:
                                        os.remove(abs_old_img_path)
                                        status_var.set(f"已删除旧图片文件: {abs_old_img_path}")
                                        global_root.after(2000, lambda: status_var.set("就绪"))
                                    except Exception as e:
                                        status_var.set(f"删除旧图片失败: {str(e)}")
                                        global_root.after(2000, lambda: status_var.set("就绪"))
                        # 只删除标签，不删除 tab
                        tags_data[tag_type][tab_key].pop(label, None)
                        break

            # ✅ 如果 tab 不存在就新建
            if tab_name not in tags_data[tag_type]:
                tags_data[tag_type][tab_name] = {}

            # 构建标签数据
            entry = {"en": en_name}
            # 处理图片路径：统一保存为相对于images目录的相对路径
            if img_path:
                # 验证文件存在性时使用绝对路径
                abs_img_path = img_path if os.path.isabs(img_path) else os.path.abspath(img_path)
                if os.path.exists(abs_img_path):
                    # 统一保存为相对于images目录的相对路径
                    try:
                        images_dir = os.path.join(PROJECT_ROOT, "images")
                        rel_img_path = os.path.relpath(abs_img_path, images_dir)
                        entry["image"] = os.path.join("images", rel_img_path).replace('\\', '/')
                    except ValueError:
                        # 如果无法转换为相对路径，保持绝对路径
                        entry["image"] = img_path.replace('\\', '/')

            # ✅ 编辑时继承 usage_count
            if edit and label:
                original_usage_count = 0
                for tab_data in tags_data[tag_type].values():
                    if label in tab_data and isinstance(tab_data[label], dict):
                        original_usage_count = tab_data[label].get("usage_count", 0)
                        break
                entry["usage_count"] = original_usage_count
            else:
                entry["usage_count"] = 0

            # ✅ 添加/更新标签
            tags_data[tag_type][tab_name][zh_name] = entry

            # 保存
            save_tags(tags_data)
            if 'global_root' in globals() and hasattr(global_root, 'refresh_tab_list'):
                global_root.refresh_tab_list()
            win.destroy()

        # 确定按钮
        ctk.CTkButton(win, text="确定", fg_color="#19a8b9", command=save_).pack(pady=12)

    def refresh_tab_list():
        global head_tab_names, tail_tab_names
        # 优先从当前页面的标签管理器获取 Tab 列表；无管理器时回退到全局数据
        tag_manager = get_page_tag_manager()
        if tag_manager:
            head_tab_names = tag_manager.get_tab_names("head")
            tail_tab_names = tag_manager.get_tab_names("tail")
        else:
            head_tab_names = list(tags_data["head"].keys())
            tail_tab_names = list(tags_data["tail"].keys())
        if not head_tab_names:
            head_tab.set("")
        elif head_tab.get() not in head_tab_names:
            head_tab.set(head_tab_names[0])
        if not tail_tab_names:
            tail_tab.set("")
        elif tail_tab.get() not in tail_tab_names:
            tail_tab.set(tail_tab_names[0])
        refresh_head_tabbar()
        if 'global_root' in globals() and hasattr(global_root, 'refresh_head_tags'):
            global_root.refresh_head_tags()
        refresh_tail_tabbar()
        if 'global_root' in globals() and hasattr(global_root, 'refresh_tail_tags'):
            global_root.refresh_tail_tags()

    def refresh_output_text(translated=None):
        if page_manager:
            current_page = page_manager.get_current_page()
            if current_page and current_page.output_widget:
                output_text = current_page.output_widget
                last_translation = current_page.last_translation
                
                # 获取标签管理器
                tag_manager = get_page_tag_manager()
                if tag_manager:
                    # 使用新的标签管理器获取选中的标签
                    head_tags = tag_manager.get_selected_tags("head")
                    tail_tags = tag_manager.get_selected_tags("tail")
                else:
                    # 兼容旧的逻辑
                    head_tags = current_page.inserted_tags.get("head", [])
                    tail_tags = current_page.inserted_tags.get("tail", [])
                
                output_text.config(state="normal")
                output_text.delete("1.0", tk.END)
                # 头部标签 - 每个标签后添加逗号
                for tag in head_tags:
                    insert_tag_block(tag, "head", output_text)
                    output_text.insert(tk.END, ", ")
                # 插入主翻译内容
                if last_translation:
                    output_text.insert(tk.END, last_translation)
                # 尾部标签添加逗号前缀
                for tag in tail_tags:
                    output_text.insert(tk.END, ", ")  # 添加逗号和空格
                    insert_tag_block(tag, "tail", output_text)
                # 禁用文本框编辑以确保标签块正确显示
                output_text.config(state="disabled")



    # show_create_tag_dialog 函数已移至全局作用域

    global resize_timer  # 添加这行声明
    resize_timer = None  # 初始化定时器变量

    def update_on_resize(event):
        global resize_timer
        # 取消之前的定时器
        if resize_timer:
            global_root.after_cancel(resize_timer)
        # 200毫秒后执行刷新，避免频繁触发
        resize_timer = global_root.after(200, lambda: (
            refresh_head_tabbar(),  # 刷新头部标签页换行布局
            refresh_tail_tabbar(),  # 刷新尾部标签页换行布局
            global_root.refresh_head_tags() if hasattr(global_root, 'refresh_head_tags') else None, 
            global_root.refresh_tail_tags() if hasattr(global_root, 'refresh_tail_tags') else None
        ))

    head_canvas.bind("<Configure>", update_on_resize)
    tail_canvas.bind("<Configure>", update_on_resize)

    # refresh_tab_list()
    # refresh_output_text()
    # 延迟100毫秒执行刷新，确保UI组件已初始化
    global_root.after(100, lambda: (
        (global_root.refresh_tab_list() if hasattr(global_root, 'refresh_tab_list') else None),
        refresh_output_text()
    ))
    
    def refresh_tags_ui(tags_file=None):
        """当tags.json文件变化时刷新UI显示"""
        global tags_data
        try:
            print(f"[refresh_tags_ui] 开始刷新标签UI - 文件: {tags_file}")
            
            # 重新加载标签数据
            tags_data = load_tags()
            print(f"[refresh_tags_ui] 已重新加载标签数据，头部分类数: {len(tags_data.get('head', {}))}")
            
            # 关键修复：将全局标签数据同步到当前分页的标签管理器
            if page_manager:
                current_page = page_manager.get_current_page()
                if current_page:
                    tag_manager = current_page.get_tag_manager()
                    if tag_manager:
                        print(f"[refresh_tags_ui] 同步全局标签数据到分页{current_page.page_id}")
                        # 使用import_data方法将全局数据合并到分页数据中
                        tag_manager.import_data(tags_data, merge=True)
                        print(f"[refresh_tags_ui] 分页{current_page.page_id}标签数据同步完成")
            
            # 强制UI立即更新
            global_root.update_idletasks()
            
            # 刷新标签列表和显示
            if hasattr(global_root, 'refresh_tab_list'):
                print(f"[refresh_tags_ui] 刷新标签页列表")
                global_root.refresh_tab_list()
                global_root.update_idletasks()  # 强制更新
                
            if hasattr(global_root, 'refresh_head_tags'):
                print(f"[refresh_tags_ui] 刷新头部标签")
                global_root.refresh_head_tags()
                global_root.update_idletasks()  # 强制更新
                
            if hasattr(global_root, 'refresh_tail_tags'):
                print(f"[refresh_tags_ui] 刷新尾部标签")
                global_root.refresh_tail_tags()
                global_root.update_idletasks()  # 强制更新
            
            # 最终强制刷新整个UI
            global_root.update()
            
            # 更新状态栏
            status_var.set("标签数据已更新")
            global_root.after(2000, lambda: status_var.set("就绪"))
            
            print(f"[refresh_tags_ui] 标签数据已刷新完成")
            
        except Exception as e:
            print(f"[refresh_tags_ui] 刷新标签数据时出错: {e}")
            import traceback
            traceback.print_exc()
    
    # 将刷新函数暴露到全局作用域
    global_root.refresh_tab_list = refresh_tab_list
    global_root.refresh_head_tags = refresh_head_tags
    global_root.refresh_tail_tags = refresh_tail_tags
    
    # 将refresh_tags_ui方法添加到root对象
    global_root.refresh_tags_ui = refresh_tags_ui


# --------- 收藏夹和历史记录窗口（含分页+日期筛选） ------------

# 全局变量用于跟踪窗口实例
favorite_window = None
history_window_instance = None
favorites = []  # 收藏夹数据
history = []    # 历史记录数据



def view_favorites():
    global favorite_window

    # 如果窗口还在，直接置顶并return，不再新建窗口
    if favorite_window is not None:
        try:
            if favorite_window.winfo_exists():
                favorite_window.lift()
                return
        except:
            favorite_window = None  # 如果窗口已关闭或不存在，重置

    import datetime
    import os
    from tkinter import messagebox

    global favorites  # 声明全局变量
    favorites_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "favorites.txt")
    if not os.path.exists(favorites_file):
            messagebox.showinfo("提示", "暂无收藏内容")
            favorites = []
            return
    with open(favorites_file, "r", encoding="utf-8") as f:
        try:
            favorites = json.load(f)
        except:
            favorites = []

    PAGE_SIZE = 50
    page = [0]
    filter_date = [None]

    win = ctk.CTkToplevel()
    win.attributes('-topmost', True)  # 添加置顶属性
    favorite_window = win  # 保存当前窗口引用
    win.title("收藏夹")
    win.geometry("1050x720")

    def on_close():
        global favorite_window
        favorite_window = None
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)

    main_frame = ctk.CTkFrame(win)
    main_frame.pack(fill="both", expand=True)

    # 顶部标题和筛选区域
    header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    header_frame.pack(fill="x", padx=18, pady=(10,0))
    
    ctk.CTkLabel(header_frame, text="收藏夹", font=("微软雅黑", 15, "bold")).pack(anchor="w", pady=(0,8))
    
    # 日期筛选区域
    filter_frame = ctk.CTkFrame(header_frame, fg_color="#f6f7fa")
    filter_frame.pack(fill="x", pady=(0,10))
    
    ctk.CTkLabel(filter_frame, text="按日期筛选：", font=("微软雅黑", 12)).pack(side="left", padx=(16,2), pady=8)
    if DateEntry:
        date_picker = DateEntry(filter_frame, date_pattern="yyyy-mm-dd", width=12, font=("微软雅黑", 12))
        date_picker.pack(side="left", padx=(0,8), pady=8)
    else:
        date_picker = ctk.CTkEntry(filter_frame, placeholder_text="YYYY-MM-DD", width=120)
        date_picker.pack(side="left", padx=(0,8), pady=8)
    
    def on_date_selected(*_):
        if DateEntry:
            filter_date[0] = date_picker.get()
        else:
            filter_date[0] = date_picker.get()
        page[0] = 0
        render_favorites_page()
    
    if DateEntry:
        date_picker.bind("<<DateEntrySelected>>", on_date_selected)
    
    def clear_date_filter():
        filter_date[0] = None
        page[0] = 0
        render_favorites_page()
    ctk.CTkButton(filter_frame, text="全部", fg_color="#e3e4e8", width=42, text_color="gray", font=("微软雅黑",11),
                 command=clear_date_filter).pack(side="left", padx=(0, 10), pady=8)

    content_area = ctk.CTkFrame(main_frame)
    content_area.pack(fill="both", expand=True, padx=18, pady=(0,0))

    canvas = ctk.CTkCanvas(content_area, bg="#f9f9fb")
    scrollbar = ctk.CTkScrollbar(content_area, orientation="vertical", command=canvas.yview)
    content_frame = ctk.CTkFrame(canvas, fg_color="#f9f9fb")
    canvas.create_window((0, 0), window=content_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # ---- 底部工具栏 ----
    bottom_frame = ctk.CTkFrame(main_frame, fg_color="#f6f7fa")
    bottom_frame.pack(fill="x", side="bottom", pady=(4,12), padx=(0, 0))

    # 分页控件
    page_label = ctk.CTkLabel(bottom_frame, text="", font=("微软雅黑", 12))
    page_label.pack(side="left", padx=(16,8))

    btn_prev = ctk.CTkButton(bottom_frame, text="上一页", width=80, font=("微软雅黑", 12),
                             fg_color="#dddddd", text_color="gray")
    btn_next = ctk.CTkButton(bottom_frame, text="下一页", width=80, font=("微软雅黑", 12),
                             fg_color="#dddddd", text_color="gray")
    btn_prev.pack(side="left", padx=6)
    btn_next.pack(side="left", padx=(4,20))

    # 操作按钮
    ctk.CTkButton(bottom_frame, text="删除选中", fg_color="#ff4444", text_color="white", command=lambda: delete_selected_favorites()).pack(side="left", padx=8)
    ctk.CTkButton(bottom_frame, text="清空全部", command=lambda: clear_all_favorites()).pack(side="left", padx=8)
    ctk.CTkButton(bottom_frame, text="清除一周前", command=lambda: clear_favorites_older_than(7)).pack(side="left", padx=8)
    ctk.CTkButton(bottom_frame, text="清除一月前", command=lambda: clear_favorites_older_than(30)).pack(side="left", padx=8)

    selected_items = {}


    def delete_selected_favorites():
        global favorites
        if not selected_items:
            messagebox.showinfo("提示", "未选择任何项目", parent=win)
            return
        
        # 获取所有选中项的唯一标识（时间戳）
        selected_timestamps = {timestamp for timestamp, (item, var) in selected_items.items() if var.get()}
        
        if not selected_timestamps:
            messagebox.showinfo("提示", "未选择任何项目", parent=win)
            return
        
        if not messagebox.askyesno("确认", f"确定要删除选中的 {len(selected_timestamps)} 个项目吗？", parent=win):
            return
        
        # 过滤掉选中的项目
        new_favorites = [item for item in favorites if item.get("timestamp") not in selected_timestamps]

        # 更新文件和内存中的收藏夹
        with open(favorites_file, "w", encoding="utf-8") as f:
            json.dump(new_favorites, f, ensure_ascii=False, indent=2)
        
        favorites[:] = new_favorites
        selected_items.clear()
        render_favorites_page()



    def clear_favorites_older_than(days=7):
        global favorites
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        try:
            new_favorites = []
            for item in favorites:
                d = item.get("timestamp", "") or item.get("date", "")
                if d:
                    try:
                        item_date = datetime.datetime.strptime(d[:10], "%Y-%m-%d")
                        if item_date > cutoff:
                            new_favorites.append(item)
                    except:
                        pass
            with open(favorites_file, "w", encoding="utf-8") as f:
                json.dump(new_favorites, f, ensure_ascii=False, indent=2)
            favorites[:] = new_favorites
            render_favorites_page()
        except Exception as e:
            print("清理收藏错误：", e)

    def clear_all_favorites():
        global favorites
        with open(favorites_file, "w", encoding="utf-8") as f:
            json.dump([], f)
        favorites.clear()
        render_favorites_page()

    def render_favorites_page():
        if filter_date[0]:
            items = [r for r in favorites if (r.get("timestamp") or r.get("date") or "").startswith(filter_date[0])]
        else:
            items = favorites
        n_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
        if page[0] >= n_pages:
            page[0] = n_pages-1
        for widget in content_frame.winfo_children():
            widget.destroy()
        start = page[0]*PAGE_SIZE
        end = min(len(items), start+PAGE_SIZE)
        curr_page = page[0]+1
        page_label.configure(text=f"第 {curr_page} / {n_pages} 页  （共 {len(items)} 条）")
        for idx, item in enumerate(items[start:end]):
            frame = ctk.CTkFrame(content_frame, fg_color="white", corner_radius=12)

            # 多选框
            var = ctk.BooleanVar()
            chk = ctk.CTkCheckBox(frame, text="", variable=var, width=20)
            chk.pack(side="left", padx=10)
            # 将控件和变量关联到item上，方便后续引用
            selected_items[item["timestamp"]] = (item, var)

            # 显示标题（如果有）
            title = item.get("title", "")
            if title:
                ctk.CTkLabel(frame, text=f"标题：{title}", anchor="w", wraplength=900,
                             font=("微软雅黑", 12, "bold")).pack(anchor="w", pady=(8,0), padx=16)
            ctk.CTkLabel(frame, text=f"时间：{item.get('timestamp', item.get('date', ''))}", anchor="w", wraplength=900,
                         font=("微软雅黑", 11, "bold")).pack(anchor="w", pady=(8,0), padx=16)
            ctk.CTkLabel(frame, text=f"输入：{item.get('input', '')}", anchor="w", wraplength=900, font=("微软雅黑", 12)).pack(anchor="w", padx=16)
            ctk.CTkLabel(frame, text=f"输出：{item.get('output', '')}", anchor="w", wraplength=900, font=("微软雅黑", 12)).pack(anchor="w", padx=16, pady=(0,8))
            btn_row = ctk.CTkFrame(frame, fg_color="white")
            btn_row.pack(anchor="e", padx=12, pady=(0,10))
            ctk.CTkButton(btn_row, text="复制输入", fg_color="#36b48b", text_color="white", font=("微软雅黑", 12), width=130, height=32, corner_radius=16,
                          command=lambda t=item.get('input', ''): pyperclip.copy(t)).pack(side="right", padx=7)
            ctk.CTkButton(btn_row, text="复制输出", fg_color="#3078ef", text_color="white", font=("微软雅黑", 12), width=130, height=32, corner_radius=16,
                          command=lambda t=item.get('output', ''): pyperclip.copy(t)).pack(side="right", padx=7)
            frame.pack(fill="x", pady=7, padx=8)
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        btn_prev.configure(state=("disabled" if page[0]<=0 else "normal"))
        btn_next.configure(state=("disabled" if page[0]>=n_pages-1 else "normal"))

    def prev_page():
        if page[0] > 0:
            page[0] -= 1
            render_favorites_page()
    def next_page():
        if filter_date[0]:
            items = [r for r in favorites if (r.get("timestamp") or r.get("date") or "").startswith(filter_date[0])]
        else:
            items = favorites
        n_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
        if page[0] < n_pages-1:
            page[0] += 1
            render_favorites_page()
    btn_prev.configure(command=prev_page)
    btn_next.configure(command=next_page)

    render_favorites_page()

def view_history():
    global history_window_instance

    # 如果窗口还在，直接置顶并return，不再新建窗口
    if history_window_instance is not None:
        try:
            if history_window_instance.winfo_exists():
                history_window_instance.lift()
                return
        except:
            history_window_instance = None  # 如果窗口已关闭或不存在，重置

    import datetime
    import os
    from tkinter import messagebox
    from services.history_manager import get_history_manager

    # 使用优化的历史记录管理器
    history_manager = get_history_manager()
    
    # 检查是否有历史记录
    if not os.path.exists("history.json"):
        messagebox.showinfo("提示", "暂无历史记录")
        return

    PAGE_SIZE = 50
    page = [0]
    filter_date = [None]
    current_page_data = []  # 当前页面数据缓存
    rendered_items = {}  # 已渲染的UI组件缓存

    win = ctk.CTkToplevel()
    win.attributes('-topmost', True)  # 添加置顶属性
    history_window_instance = win  # 保存当前窗口引用
    win.title("翻译历史记录")
    win.geometry("1050x720")

    def on_close():
        global history_window_instance
        history_window_instance = None
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)

    main_frame = ctk.CTkFrame(win)
    main_frame.pack(fill="both", expand=True)

    # 标题区域
    title_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    title_frame.pack(fill="x", padx=18, pady=(10,0))
    ctk.CTkLabel(title_frame, text="翻译历史记录", font=("微软雅黑", 15, "bold")).pack(anchor="w")

    # ---- 底部工具栏 ----（先创建底部工具栏，确保它始终可见）
    bottom_frame = ctk.CTkFrame(main_frame, fg_color="#f6f7fa", height=60)
    bottom_frame.pack(fill="x", side="bottom", pady=(4,12), padx=18)
    bottom_frame.pack_propagate(False)  # 防止子组件改变frame高度

    # 内容区域（填充剩余空间）
    content_area = ctk.CTkFrame(main_frame)
    content_area.pack(fill="both", expand=True, padx=18, pady=(6,4))

    # 使用简单滚动组件
    from services.simple_scroll import HistorySimpleScrollFrame
    simple_scroll = HistorySimpleScrollFrame(content_area, add_to_favorites_callback=None)
    simple_scroll.pack(fill="both", expand=True)
    
    # 保持兼容性的变量
    canvas = simple_scroll.canvas
    content_frame = simple_scroll.content_frame

    ctk.CTkLabel(bottom_frame, text="按日期筛选：", font=("微软雅黑", 12)).pack(side="left", padx=(16,2))
    if DateEntry:
        date_picker = DateEntry(bottom_frame, date_pattern="yyyy-mm-dd", width=12, font=("微软雅黑", 12))
        date_picker.pack(side="left", padx=(0,8), pady=5)
    else:
        date_picker = ctk.CTkEntry(bottom_frame, placeholder_text="YYYY-MM-DD", width=120)
        date_picker.pack(side="left", padx=(0,8), pady=5)

    def on_date_selected(*_):
        if DateEntry:
            filter_date[0] = date_picker.get()
        else:
            filter_date[0] = date_picker.get()
        page[0] = 0
        render_page()
    date_picker.bind("<<DateEntrySelected>>", on_date_selected)

    def clear_date_filter():
        filter_date[0] = None
        page[0] = 0
        render_page()
    ctk.CTkButton(bottom_frame, text="全部", fg_color="#e3e4e8", width=42, text_color="gray", font=("微软雅黑",11),
                 command=clear_date_filter).pack(side="left", padx=(0, 10))

    page_label = ctk.CTkLabel(bottom_frame, text="", font=("微软雅黑", 12))
    page_label.pack(side="left", padx=2)

    btn_prev = ctk.CTkButton(bottom_frame, text="上一页", width=80, font=("微软雅黑", 12),
                             fg_color="#dddddd", text_color="gray")
    btn_next = ctk.CTkButton(bottom_frame, text="下一页", width=80, font=("微软雅黑", 12),
                             fg_color="#dddddd", text_color="gray")
    btn_prev.pack(side="left", padx=6)
    btn_next.pack(side="left", padx=(4,20))

    # 清理按钮
    ctk.CTkButton(bottom_frame, text="清空全部", command=lambda: clear_all_history()).pack(side="left", padx=8)
    ctk.CTkButton(bottom_frame, text="清除一周前", command=lambda: clear_history_older_than(7)).pack(side="left", padx=8)
    ctk.CTkButton(bottom_frame, text="清除一月前", command=lambda: clear_history_older_than(30)).pack(side="left", padx=8)



    def clear_history_older_than(days=7):
        try:
            removed_count = history_manager.cleanup_old_records(days)
            if removed_count > 0:
                messagebox.showinfo("清理完成", f"已清理 {removed_count} 条 {days} 天前的记录")
                page[0] = 0  # 重置到第一页
                render_page()
            else:
                messagebox.showinfo("提示", f"没有找到 {days} 天前的记录")
        except Exception as e:
            messagebox.showerror("错误", f"清理历史记录失败: {e}")
            print("清理历史错误：", e)

    def clear_all_history():
        if messagebox.askyesno("确认", "确定要清空所有历史记录吗？此操作不可撤销。"):
            try:
                if history_manager.clear_all_records():
                    messagebox.showinfo("完成", "所有历史记录已清空")
                    page[0] = 0
                    render_page()
                else:
                    messagebox.showerror("错误", "清空历史记录失败")
            except Exception as e:
                messagebox.showerror("错误", f"清空历史记录失败: {e}")
                print("清空历史错误：", e)

    def add_to_favorites(item):
        """将历史记录项添加到收藏夹"""
        fav_file = "favorites.txt"
        favorites = []
        
        # 读取现有收藏
        if os.path.exists(fav_file):
            with open(fav_file, "r", encoding="utf-8") as f:
                try:
                    favorites = json.load(f)
                except Exception:
                    favorites = []
        
        # 检查重复(通过输入内容判断)
        from tkinter import simpledialog
        # 标题输入弹窗
        _default_title = (item.get("output", "").strip().splitlines()[0] if item.get("output", "").strip() else (item.get("input", "").strip().splitlines()[0] if item.get("input", "").strip() else ""))[:30]
        title = simpledialog.askstring("设置标题", "请输入收藏标题：", initialvalue=_default_title)
        if not title:
            title = _default_title or "未命名收藏"
        input_text = item.get("input", "")
        if any(fav.get("input") == input_text for fav in favorites):
            messagebox.showinfo("提示", "该内容已在收藏夹中")
            return
        
        # 添加新收藏(只保留必要字段)
        new_fav = {
            "input": input_text,
            "output": item.get("output", ""),
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        # 追加标题字段
        try:
            new_fav["title"] = title
        except Exception:
            pass
        favorites.append(new_fav)
        
        # 保存收藏
        with open(fav_file, "w", encoding="utf-8") as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
        
        messagebox.showinfo("成功", "已添加到收藏夹")

    def render_page():
        import time
        start_time = time.time()
        
        # 使用历史记录管理器获取分页数据
        page_data, total_pages, total_records = history_manager.get_page_data(
            page[0], PAGE_SIZE, filter_date[0]
        )
        
        # 更新页面信息
        curr_page = page[0] + 1
        page_label.configure(text=f"第 {curr_page} / {total_pages} 页  （共 {total_records} 条）")
        
        # 设置简单滚动数据
        simple_scroll.set_history_data(page_data, add_to_favorites)
        
        # 更新当前页面数据缓存
        current_page_data[:] = page_data
        rendered_items.clear()
        for idx, item in enumerate(page_data):
            item_id = f"{item.get('timestamp', '')}-{idx}"
            rendered_items[item_id] = item
        
        # 更新按钮状态
        btn_prev.configure(state=("disabled" if page[0] <= 0 else "normal"))
        btn_next.configure(state=("disabled" if page[0] >= total_pages - 1 else "normal"))
        
        # 获取统计信息
        render_time = time.time() - start_time
        stats = simple_scroll.get_stats()
        print(f"[简单滚动] 渲染耗时: {render_time:.3f}s, 总记录: {stats['total_items']}, 渲染项目: {stats['rendered_items']}")
    
    # create_history_item_ui函数已移至虚拟滚动组件中

    def prev_page():
        if page[0] > 0:
            page[0] -= 1
            render_page()
    
    def next_page():
        _, total_pages, _ = history_manager.get_page_data(page[0], PAGE_SIZE, filter_date[0])
        if page[0] < total_pages - 1:
            page[0] += 1
            render_page()
    btn_prev.configure(command=prev_page)
    btn_next.configure(command=next_page)

    render_page()
    date_picker.bind("<<DateEntrySelected>>", on_date_selected)


