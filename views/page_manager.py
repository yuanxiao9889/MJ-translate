# views/page_manager.py —— 分页管理模块
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import customtkinter as ctk
import pyperclip
from datetime import datetime

from services.api import translate_text, zhipu_text_expand, zhipu_image_caption
from services.tags import load_tags, save_tags
from services.logger import logger, show_error_dialog, show_info_dialog
from main import show_expand_preset_dialog
from services.history_favorites import save_to_history, save_to_favorites
from services.page_tag_manager import PageTagManager
from services.tag_template_manager import TagTemplateManager


class TranslationPage:
    """单个翻译分页类，封装所有翻译功能"""
    
    def __init__(self, page_id, name="新分页", root=None):
        self.page_id = page_id
        self.name = name
        self.created_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 分页数据
        self.input_text = ""
        self.output_text = ""
        self.last_translation = ""
        self.inserted_tags = {"head": [], "tail": []}  # 兼容旧格式
        self.tags = {"head": {}, "tail": {}}  # 新的独立标签数据结构
        
        # 标签管理器
        self.tag_manager = None
        
        # UI组件引用（在创建UI时设置）
        self.input_widget = None
        self.output_widget = None
        self.status_var = None
        self.root = root  # 添加root引用用于动画效果
        
        # UI缓存相关
        self.ui_frame = None  # 缓存的UI框架
        self.ui_created = False  # 标记UI是否已创建
        self.is_visible = False  # 标记UI是否可见
    
    def initialize_tag_manager(self):
        """初始化标签管理器"""
        if not self.tag_manager:
            # 传递 self 实例而不是字典
            self.tag_manager = PageTagManager(self)
            
            # 当页面还没有任何标签时，自动从全局 tags.json 载入作为默认模板
            try:
                if not self.tags.get('head') and not self.tags.get('tail'):
                    default_tags = load_tags()
                    if default_tags:
                        # 使用 False 表示覆盖模式，确保初始状态干净
                        self.tag_manager.import_data(default_tags, merge=False)
                        print(f"为页面 {self.name} 加载了默认标签模板，所有标签初始状态为未选中")
                else:
                    # 即使页面已有标签数据，也要确保初始状态为未选中
                    self.tag_manager.clear_all_selections()
                    print(f"页面 {self.name} 的标签已重置为未选中状态")
            except Exception as e:
                print(f"[initialize_tag_manager] 导入默认标签失败: {e}")
    
    def get_tag_manager(self):
        """获取标签管理器"""
        if not self.tag_manager:
            self.initialize_tag_manager()
        return self.tag_manager
        
    def to_dict(self):
        """转换为字典用于序列化"""
        return {
            "page_id": self.page_id,
            "name": self.name,
            "created_time": self.created_time,
            "input_text": self.input_text,
            "output_text": self.output_text,
            "last_translation": self.last_translation,
            "inserted_tags": self.inserted_tags,  # 兼容旧格式
            "tags": self.tags  # 新的独立标签数据
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建分页对象"""
        page = cls(data["page_id"], data["name"])
        page.created_time = data.get("created_time", page.created_time)
        page.input_text = data.get("input_text", "")
        page.output_text = data.get("output_text", "")
        page.last_translation = data.get("last_translation", "")
        page.inserted_tags = data.get("inserted_tags", {"head": [], "tail": []})  # 兼容旧格式
        page.tags = data.get("tags", {"head": {}, "tail": {}})  # 新的独立标签数据
        return page
    
    def save_current_state(self):
        """保存当前UI状态到分页数据"""
        if self.input_widget:
            self.input_text = self.input_widget.get("0.0", ctk.END).strip()
        if self.output_widget:
            self.output_text = self.output_widget.get("1.0", tk.END).strip()
    
    def restore_ui_state(self):
        """恢复UI状态"""
        if self.input_widget:
            self.input_widget.delete("0.0", ctk.END)
            if self.input_text:
                self.input_widget.insert("0.0", self.input_text)
        
        if self.output_widget:
            # 使用refresh_output_text来正确显示标签块，而不是简单的文本插入
            self.refresh_output_text()
    
    def do_translate(self):
        """执行翻译"""
        if not self.input_widget:
            return
            
        txt = self.input_widget.get("0.0", ctk.END).strip()
        if not txt:
            messagebox.showinfo("提示", "请输入内容")
            return
            
        def do_async():
            if self.status_var:
                self.status_var.set("正在翻译...")
            
            translated = translate_text(txt)
            self.last_translation = translated
            self.refresh_output_text()
            save_to_history(txt, translated)
            
            if self.status_var:
                self.status_var.set("翻译完成")
                if self.root:
                    self.root.after(2000, lambda: self.status_var.set("就绪"))
        
        threading.Thread(target=do_async, daemon=True).start()
    
    def refresh_output_text(self):
        """刷新输出文本"""
        if not self.output_widget:
            return
            
        # 使用新的标签管理器获取选中的标签
        try:
            from views.ui_main import insert_tag_block
            from services.ui_state_manager import ui_state_manager
            
            output_text = self.output_widget
            output_text.config(state="normal")
            output_text.delete("1.0", tk.END)
            
            # 清空当前分页的输出文本UI状态，准备重新记录
            page_id = str(self.page_id)
            ui_state_manager.save_output_text_state(
                page_id=page_id,
                tag_blocks=[],
                text_content="",
                cursor_position="1.0"
            )
            
            # 获取标签管理器 - 强制刷新状态
            tag_manager = self.get_tag_manager()
            if tag_manager:
                # 使用新的标签管理器获取选中的标签
                head_tags = tag_manager.get_selected_tags("head")
                tail_tags = tag_manager.get_selected_tags("tail")
                print(f"[refresh_output_text] 页面{self.page_id} - 头部标签: {head_tags}, 尾部标签: {tail_tags}")
            else:
                # 兼容旧的逻辑
                head_tags = self.inserted_tags.get("head", [])
                tail_tags = self.inserted_tags.get("tail", [])
                print(f"[refresh_output_text] 页面{self.page_id} - 使用旧逻辑 - 头部标签: {head_tags}, 尾部标签: {tail_tags}")
            
            # 头部标签 - 每个标签后添加逗号
            for tag in head_tags:
                insert_tag_block(tag, "head", output_text)
                output_text.insert(tk.END, ", ")
            
            # 插入主翻译内容
            if self.last_translation:
                output_text.insert(tk.END, self.last_translation)
            
            # 尾部标签添加逗号前缀
            for tag in tail_tags:
                output_text.insert(tk.END, ", ")  # 添加逗号和空格
                insert_tag_block(tag, "tail", output_text)
            
            # 禁用文本框编辑以确保标签块正确显示
            output_text.config(state="disabled")
            
            # 最终保存完整的输出文本状态
            try:
                final_text_content = output_text.get("1.0", tk.END)
                output_state = ui_state_manager.get_output_text_state(page_id)
                ui_state_manager.save_output_text_state(
                    page_id=page_id,
                    tag_blocks=output_state.get("tag_blocks", []),
                    text_content=final_text_content,
                    cursor_position="1.0"
                )
            except Exception as e:
                print(f"[refresh_output_text] 保存最终UI状态失败: {e}")
            
        except Exception as e:
            # 如果调用失败，使用简单的文本拼接作为备用方案
            print(f"[refresh_output_text] 调用标签块失败，使用备用方案: {e}")
            self.output_widget.config(state="normal")
            self.output_widget.delete("1.0", tk.END)
            
            # 获取标签管理器
            tag_manager = self.get_tag_manager()
            if tag_manager:
                head_tags = tag_manager.get_selected_tags("head")
                tail_tags = tag_manager.get_selected_tags("tail")
            else:
                insert_tag_block(tag, "head", output_text)
                output_text.insert(tk.END, ", ")
            
            # 插入主翻译内容
            if self.last_translation:
                output_text.insert(tk.END, self.last_translation)
            
            # 尾部标签添加逗号前缀
            for tag in tail_tags:
                output_text.insert(tk.END, ", ")  # 添加逗号和空格
                insert_tag_block(tag, "tail", output_text)
            
            # 禁用文本框编辑以确保标签块正确显示
            output_text.config(state="disabled")
            
            # 最终保存完整的输出文本状态
            try:
                final_text_content = output_text.get("1.0", tk.END)
                output_state = ui_state_manager.get_output_text_state(page_id)
                ui_state_manager.save_output_text_state(
                    page_id=page_id,
                    tag_blocks=output_state.get("tag_blocks", []),
                    text_content=final_text_content,
                    cursor_position="1.0"
                )
            except Exception as e:
                print(f"[refresh_output_text] 保存最终UI状态失败: {e}")
            
        except Exception as e:
            # 如果调用失败，使用简单的文本拼接作为备用方案
            print(f"[refresh_output_text] 调用标签块失败，使用备用方案: {e}")
            self.output_widget.config(state="normal")
            self.output_widget.delete("1.0", tk.END)
            
            # 获取标签管理器
            tag_manager = self.get_tag_manager()
            if tag_manager:
                head_tags = tag_manager.get_selected_tags("head")
                tail_tags = tag_manager.get_selected_tags("tail")
            else:
                head_tags = self.inserted_tags.get("head", [])
                tail_tags = self.inserted_tags.get("tail", [])
            
            # 组合头部标签、翻译结果、尾部标签
            parts = []
            if head_tags:
                parts.append(", ".join(head_tags))
            if self.last_translation:
                parts.append(self.last_translation)
            if tail_tags:
                parts.append(", ".join(tail_tags))
            
            result = ", ".join(parts)
            if result:
                self.output_widget.insert("1.0", result)
            # 禁用文本框编辑以确保正确显示
            self.output_widget.config(state="disabled")
    
    def show_ui(self, with_animation=True):
        """显示UI组件（支持动画效果）"""
        if self.ui_frame:
            if with_animation:
                self._animate_show()
            else:
                self.ui_frame.pack(fill="both", expand=True)
                self.is_visible = True
            print(f"[show_ui] 分页 {self.name} UI已显示")
    
    def hide_ui(self, with_animation=True):
        """隐藏UI组件（支持动画效果）"""
        if self.ui_frame:
            if with_animation:
                self._animate_hide()
            else:
                self.ui_frame.pack_forget()
                self.is_visible = False
            print(f"[hide_ui] 分页 {self.name} UI已隐藏")
    
    def _animate_show(self):
        """显示动画效果"""
        if self.ui_frame:
            # 直接显示UI框架
            self.ui_frame.pack(fill="both", expand=True)
            
            # 渐进显示效果（简化版本）
            self._fade_in(0)
            self.is_visible = True
    
    def _animate_hide(self):
        """隐藏动画效果"""
        if self.ui_frame:
            # 渐进隐藏
            self._fade_out(10)
    
    def _fade_in(self, step):
        """淡入效果"""
        if step <= 10 and self.ui_frame:
            alpha = step / 10.0
            # 由于CustomTkinter的限制，我们使用简化的动画效果
            if self.root:
                self.root.after(20, lambda: self._fade_in(step + 1))
    
    def _fade_out(self, step):
        """淡出效果"""
        if step >= 0 and self.ui_frame:
            if step == 0:
                self.ui_frame.pack_forget()
                self.is_visible = False
            else:
                if self.root:
                    self.root.after(20, lambda: self._fade_out(step - 1))
    
    def create_ui_if_needed(self, parent):
        """如果需要则创建UI（渐进式创建）"""
        if not self.ui_created:
            from views.ui_main import create_translation_ui_components
            import customtkinter as ctk
            
            # 创建专用的UI框架
            self.ui_frame = ctk.CTkFrame(parent, fg_color="transparent")
            
            # 渐进式创建UI组件
            self._create_ui_progressively()
            
            self.ui_created = True
            print(f"[create_ui_if_needed] 分页 {self.name} UI已创建（渐进式）")
        
        return self.ui_frame
    
    def _create_ui_progressively(self):
        """渐进式创建UI组件"""
        from views.ui_main import create_translation_ui_components
        
        # 立即创建基础UI结构
        create_translation_ui_components(self.ui_frame, self)
        
        # 如果有root引用，可以分批次创建复杂组件
        if self.root:
            # 延迟50ms后进行UI优化
            self.root.after(50, self._optimize_ui_components)
    
    def _optimize_ui_components(self):
        """优化UI组件性能"""
        try:
            # 这里可以添加UI组件的性能优化逻辑
            # 例如：预加载、缓存计算结果等
            print(f"[_optimize_ui_components] 分页 {self.name} UI组件已优化")
        except Exception as e:
            print(f"[_optimize_ui_components] UI优化失败: {e}")
    
    def clear_input(self):
        """清空输入框"""
        if self.input_widget:
            self.input_widget.delete("0.0", ctk.END)
            self.input_text = ""
    
    def clear_output(self):
        """清空输出框和标签"""
        if self.output_widget:
            self.output_widget.config(state="normal")
            self.output_widget.delete("1.0", tk.END)
        
        self.output_text = ""
        self.last_translation = ""
        self.inserted_tags = {"head": [], "tail": []}
        
        # 清空标签选中状态
        tag_manager = self.get_tag_manager()
        if tag_manager:
            tag_manager.clear_all_selections()
        
        if self.status_var:
            self.status_var.set("输出框已清空")
            if self.root:
                self.root.after(1000, lambda: self.status_var.set("就绪"))
    
    def copy_output_to_clipboard(self):
        """复制输出内容到剪贴板"""
        # 获取当前选中的标签
        tag_manager = self.get_tag_manager()
        head_tags = []
        tail_tags = []
        
        if tag_manager:
            head_tags = tag_manager.get_selected_tags("head")
            tail_tags = tag_manager.get_selected_tags("tail")
        
        # 如果没有选中标签，则使用已插入的标签
        if not head_tags:
            head_tags = self.inserted_tags["head"]
        if not tail_tags:
            tail_tags = self.inserted_tags["tail"]
        
        parts = []
        if head_tags:
            parts.append(', '.join(head_tags))
        if self.last_translation:
            parts.append(self.last_translation)
        if tail_tags:
            parts.append(', '.join(tail_tags))
        
        text = ', '.join(parts)
        if not text:
            if self.status_var:
                self.status_var.set("输出框为空，无内容可复制")
                if self.root:
                    self.root.after(3000, lambda: self.status_var.set("就绪"))
            return
        
        pyperclip.copy(text)
        if self.status_var:
            self.status_var.set("内容已复制到剪贴板 ✓")
            if self.root:
                self.root.after(3000, lambda: self.status_var.set("就绪"))
    
    def save_to_favorites(self):
        """保存到收藏夹"""
        input_content = self.input_widget.get("0.0", ctk.END) if self.input_widget else self.input_text
        output_content = self.get_output_for_copy()
        save_to_favorites(input_content, output_content)
    
    def get_output_for_copy(self):
        """获取用于复制的输出内容"""
        parts = []
        if self.inserted_tags["head"]:
            parts.append(", ".join(self.inserted_tags["head"]))
        if self.last_translation:
            parts.append(self.last_translation)
        if self.inserted_tags["tail"]:
            parts.append(", ".join(self.inserted_tags["tail"]))
        return ", ".join(parts)


class PageManager:
    """分页管理器"""
    
    def __init__(self):
        self.pages = {}  # {page_id: TranslationPage}
        self.current_page_id = None
        self.next_page_id = 1
        self.data_file = "pages_data.json"
        
        # UI组件引用
        self.page_list_frame = None
        self.current_page_frame = None
        self.status_var = None
        self.root = None
        
        # 加载保存的分页数据
        self.load_pages_data()
        
        # 如果没有分页，创建默认分页
        if not self.pages:
            self.create_new_page("默认分页")
    
    def load_pages_data(self):
        """加载分页数据"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for page_data in data.get("pages", []):
                    page = TranslationPage.from_dict(page_data)
                    self.pages[page.page_id] = page
                
                self.current_page_id = data.get("current_page_id")
                self.next_page_id = data.get("next_page_id", 1)
                
                # 确保当前分页ID有效
                if self.current_page_id not in self.pages and self.pages:
                    self.current_page_id = list(self.pages.keys())[0]
                    
            except Exception as e:
                logger.error(f"加载分页数据失败: {e}")
    
    def save_pages_data(self):
        """保存分页数据"""
        try:
            # 保存当前分页状态
            if self.current_page_id and self.current_page_id in self.pages:
                self.pages[self.current_page_id].save_current_state()
            
            data = {
                "pages": [page.to_dict() for page in self.pages.values()],
                "current_page_id": self.current_page_id,
                "next_page_id": self.next_page_id
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存分页数据失败: {e}")
    
    def create_new_page(self, name=None):
        """创建新分页"""
        if name is None:
            name = f"分页 {self.next_page_id}"
        
        page = TranslationPage(self.next_page_id, name, self.root)
        page.initialize_tag_manager()  # 初始化标签管理器
        self.pages[self.next_page_id] = page
        self.current_page_id = self.next_page_id
        self.next_page_id += 1
        
        self.save_pages_data()
        self.refresh_page_list()
        self.switch_to_page(page.page_id)
        
        return page
    
    def delete_page(self, page_id):
        """删除分页"""
        if len(self.pages) <= 1:
            messagebox.showwarning("警告", "至少需要保留一个分页")
            return False
        
        if page_id not in self.pages:
            return False
        
        page_name = self.pages[page_id].name
        if not messagebox.askyesno("确认删除", f"确定要删除分页 '{page_name}' 吗？\n此操作不可撤销。"):
            return False
        
        # 删除分页数据
        del self.pages[page_id]
        
        # 如果删除的是当前分页，切换到其他分页
        if self.current_page_id == page_id:
            self.current_page_id = list(self.pages.keys())[0]
            self.switch_to_page(self.current_page_id)
        
        # 保存数据并刷新UI
        self.save_pages_data()
        self.refresh_page_list()
        
        # 刷新翻译界面以确保UI与数据同步
        if hasattr(self, 'translation_area') and self.translation_area:
            from views.ui_main import refresh_translation_ui
            refresh_translation_ui()
        
        return True
    
    def clear_all_pages(self):
        """清空所有分页任务列表"""
        self.pages.clear()
        self.current_page_id = None
        self.next_page_id = 1
        self.save_pages_data()
        self.refresh_page_list()
        # 刷新翻译界面以确保UI与数据同步
        if hasattr(self, 'translation_area') and self.translation_area:
            from views.ui_main import refresh_translation_ui
            refresh_translation_ui()
    
    def rename_page(self, page_id, new_name):
        """重命名分页"""
        if page_id in self.pages:
            self.pages[page_id].name = new_name
            self.save_pages_data()
            self.refresh_page_list()
    
    def switch_to_page(self, page_id):
        """切换到指定分页（优化版本，使用UI缓存）"""
        if page_id not in self.pages:
            return
        
        # 保存当前分页状态
        if self.current_page_id and self.current_page_id in self.pages:
            current_page = self.pages[self.current_page_id]
            current_page.save_current_state()
            # 隐藏当前分页的UI
            current_page.hide_ui()
        
        # 切换分页
        self.current_page_id = page_id
        target_page = self.pages[page_id]
        
        # 确保目标分页的UI已创建并显示
        if hasattr(self, 'translation_area') and self.translation_area:
            # 先隐藏所有其他分页的UI
            for other_page_id, other_page in self.pages.items():
                if other_page_id != page_id and hasattr(other_page, 'ui_frame') and other_page.ui_frame:
                    other_page.hide_ui(with_animation=False)
            
            # 创建或显示目标分页的UI
            target_page.create_ui_if_needed(self.translation_area)
            target_page.show_ui(with_animation=False)
        
        # 恢复UI状态（写入输入文本等）
        target_page.restore_ui_state()
        
        # 刷新页面列表显示
        self.refresh_page_list()
        
        # 刷新标签UI和输出 - 优化执行顺序
        try:
            # 首先恢复标签UI状态，确保标签选择状态正确
            tag_manager = target_page.get_tag_manager()
            if tag_manager:
                tag_manager.restore_ui_state()
            
            # 恢复全局标签UI状态
            self.restore_tag_ui_state()
            
            # 延迟执行输出文本刷新，确保标签UI状态已完全恢复
            if self.root:
                self.root.after(50, lambda: self._delayed_refresh_output(target_page))
            else:
                target_page.refresh_output_text()
            
            print(f"[switch_to_page] 已切换到分页 {target_page.name}，使用缓存UI")
        except Exception as e:
            print(f"[switch_to_page] 刷新标签UI失败: {e}")
        
        # 更新状态
        if self.status_var:
            self.status_var.set(f"已切换到: {current_page.name}")
            if self.root:
                self.root.after(2000, lambda: self.status_var.set("就绪"))
    
    def _delayed_refresh_output(self, page):
        """延迟刷新输出文本，确保标签UI状态已完全恢复"""
        try:
            page.refresh_output_text()
            print("[_delayed_refresh_output] 输出文本刷新完成")
        except Exception as e:
            print(f"[_delayed_refresh_output] 输出文本刷新失败: {e}")
    
    def get_current_page(self):
        """获取当前分页"""
        if self.current_page_id and self.current_page_id in self.pages:
            return self.pages[self.current_page_id]
        return None
    
    def get_current_page_tag_manager(self):
        """获取当前分页的标签管理器"""
        current_page = self.get_current_page()
        if current_page:
            return current_page.get_tag_manager()
        return None
    
    def save_data(self):
        """保存数据（save_pages_data的别名）"""
        self.save_pages_data()
    
    def restore_tag_ui_state(self):
        """恢复标签UI状态"""
        current_page = self.get_current_page()
        if not current_page:
            return
        
        try:
            # 获取UI状态管理器
            from services.ui_state_manager import ui_state_manager
            
            # 恢复头部和尾部标签的UI状态
            head_ui_state = ui_state_manager.get_tag_ui_state(current_page.page_id, "head")
            tail_ui_state = ui_state_manager.get_tag_ui_state(current_page.page_id, "tail")
            
            # 这里可以根据需要添加具体的UI状态恢复逻辑
            # 例如：恢复标签的可见性、位置、选中状态等
            print(f"[restore_tag_ui_state] 恢复分页 {current_page.page_id} 的标签UI状态")
            print(f"头部标签UI状态: {len(head_ui_state)} 个标签")
            print(f"尾部标签UI状态: {len(tail_ui_state)} 个标签")
            
        except Exception as e:
            print(f"[restore_tag_ui_state] 恢复标签UI状态失败: {e}")
    
    def refresh_page_list(self):
        """刷新分页列表UI（由UI模块实现）"""
        pass