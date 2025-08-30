# views/prompt_chat.py — 提示词工程师聊天窗口（MVP）
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from tkinter import simpledialog
import threading
from typing import List, Dict, Callable, Optional
import os
import json

from services.api import zhipu_chat_completion
from services.logger import logger

DEFAULT_PERSONA = (
    "你是一名资深的提示词工程师，专注于生图（AIGC图像生成）。\n"
    "目标：将用户的简要描述（主体/特征）对话式扩写为高质量中文提示词。\n"
    "要求：\n- 只输出中文，不使用任何负面词\n- 仅面向生图提示词场景\n- 先给出可直接复制的‘最终提示词’（尽量一段话、逗号分隔），\n  再给出结构化‘要点卡片’，最后附带‘模型适配建议参数’（即梦/千问/SDXL）。\n"
    "输出格式：\n最终提示词：<一段可直接用于生图的中文提示词>\n要点：主体｜场景｜氛围｜镜头/光照｜姿态/构图｜材质/质感｜风格标签｜尺寸/比例建议\n模型适配建议：<为即梦/千问/SDXL给出尺寸/比例/风格强度等建议，不含负面词>\n"
)

# 人设持久化文件路径（项目根目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONAS_FILE = os.path.join(PROJECT_ROOT, "prompt_personas.json")
DEFAULT_PERSONA_NAME = "默认"


def _load_personas_from_disk() -> Dict[str, str]:
    try:
        if os.path.exists(PERSONAS_FILE):
            with open(PERSONAS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
    except Exception as e:
        logger.error(f"加载人设失败: {e}")
    # 提供一个默认人设
    return {DEFAULT_PERSONA_NAME: DEFAULT_PERSONA}


def _save_personas_to_disk(personas: Dict[str, str]) -> None:
    try:
        with open(PERSONAS_FILE, "w", encoding="utf-8") as f:
            json.dump(personas, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存人设失败: {e}")


class ChatPromptEngineerDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc,
                 on_set_last_output: Optional[Callable[[str], None]] = None,
                 on_insert_to_input: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.title("提示词工程师")
        self.geometry("1070x968")
        self._on_set_last = on_set_last_output
        self._on_insert = on_insert_to_input
        self.messages: List[Dict[str, str]] = [{"role": "system", "content": DEFAULT_PERSONA}]

        # 加载人设
        self.personas: Dict[str, str] = _load_personas_from_disk()
        if DEFAULT_PERSONA_NAME not in self.personas:
            self.personas[DEFAULT_PERSONA_NAME] = DEFAULT_PERSONA
        self.selected_persona_name: str = DEFAULT_PERSONA_NAME

        # 顶部：人设（可编辑）
        persona_frame = ctk.CTkFrame(self)
        persona_frame.pack(fill="x", padx=10, pady=(10,6))
        ctk.CTkLabel(persona_frame, text="系统人设（可编辑）").pack(anchor="w", padx=6, pady=(6,4))

        # 人设选择与管理行
        manage_row = ctk.CTkFrame(persona_frame, fg_color="transparent")
        manage_row.pack(fill="x", padx=6, pady=(0,6))
        # 下拉选择
        self.persona_option = ctk.CTkOptionMenu(
            manage_row,
            values=list(self.personas.keys()),
            command=self._on_select_persona
        )
        self.persona_option.pack(side="left")
        self.persona_option.set(self.selected_persona_name)
        # 名称输入
        self.persona_name_entry = ctk.CTkEntry(manage_row, placeholder_text="人设名称")
        self.persona_name_entry.pack(side="left", padx=(8,0))
        # 保存/更新
        ctk.CTkButton(manage_row, text="保存/更新", width=90, command=self._save_or_update_persona).pack(side="left", padx=6)
        # 删除
        ctk.CTkButton(manage_row, text="删除", width=70, command=self._delete_persona).pack(side="left", padx=(0,6))
        # 重置为默认
        ctk.CTkButton(manage_row, text="重置默认", width=90, command=self._reset_to_default).pack(side="left")

        self.persona_text = ctk.CTkTextbox(persona_frame, height=90)
        self.persona_text.pack(fill="x", padx=6, pady=(0,6))
        self.persona_text.insert("1.0", self.personas.get(self.selected_persona_name, DEFAULT_PERSONA))
        btn_row = ctk.CTkFrame(persona_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=6, pady=(0,6))
        ctk.CTkButton(btn_row, text="应用人设", width=100, command=self.apply_persona).pack(side="left")

        # 中部：聊天区
        self.chat_area = ctk.CTkScrollableFrame(self)
        self.chat_area.pack(fill="both", expand=True, padx=10, pady=6)
        # 初始提示改为输入框占位符，不再在聊天区显示

        # 底部：输入与发送
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=10, pady=(0,10))
        # 快捷命令区域：使用分栏+可滚动布局，支持扩展（支持折叠）
        self.custom_enhance_labels: List[str] = []
        self.custom_lens_labels: List[str] = []
        self._quick_collapsed = False
        quick_container = ctk.CTkFrame(bottom, fg_color="transparent")
        quick_container.pack(fill="x", pady=(0,4))
        header_row = ctk.CTkFrame(quick_container, fg_color="transparent")
        header_row.pack(fill="x")
        self.quick_toggle_btn = ctk.CTkButton(header_row, text="快捷指令 ▾", width=100, command=self._toggle_quick_panel)
        self.quick_toggle_btn.pack(side="left", padx=(0,6), pady=(0,4))
        self.quick_panel = ctk.CTkFrame(quick_container, fg_color="transparent")
        self.quick_panel.pack(fill="x")
        self._build_quick_panels(self.quick_panel)
        # 输入区（增高）
        input_row = ctk.CTkFrame(bottom, fg_color="transparent")
        input_row.pack(fill="x")
        self.input_box = ctk.CTkTextbox(input_row, height=100)
        self.input_box.pack(side="left", fill="x", expand=True)
        self.send_btn = ctk.CTkButton(input_row, text="发送 /expand", width=120, command=self.on_send)
        self.send_btn.pack(side="left", padx=(8,0))

        # 占位提示：灰色字体，输入后消失，清空时恢复
        self.placeholder_text = "请输入主体与特征（如：粉发少女、动物耳、绿色夹克、甜美）。支持快捷命令：更亮/更写实/更马卡龙/更电影感 等"
        self._placeholder_active = False
        self._set_placeholder()
        self.input_box.bind("<FocusIn>", lambda e: self._clear_placeholder())
        self.input_box.bind("<Key>", lambda e: self._clear_placeholder())
        self.input_box.bind("<FocusOut>", lambda e: self._maybe_restore_placeholder())

        self.bind("<Return>", self._submit_on_enter)
        self.input_box.focus_set()

    def _submit_on_enter(self, e):
        # Shift+Enter 换行，单回车发送
        if isinstance(e, tk.Event) and (e.state & 0x1):
            return
        self.on_send()
        return "break"

    def _append_to_input(self, text: str):
        self._clear_placeholder()
        self.input_box.insert("end", ("，" if self._get_input().strip() else "") + text)

    def _on_select_persona(self, name: str):
        # 切换下拉选择时，载入对应人设内容
        try:
            self.selected_persona_name = name
            content = self.personas.get(name, DEFAULT_PERSONA)
            self.persona_text.delete("1.0", "end")
            self.persona_text.insert("1.0", content)
            # 同步到对话的第一条 system
            if self.messages and self.messages[0]["role"] == "system":
                self.messages[0]["content"] = content
            else:
                self.messages.insert(0, {"role": "system", "content": content})
            self._append_info(f"已切换人设：{name}")
        except Exception as e:
            logger.error(f"切换人设失败: {e}")

    def _refresh_persona_menu(self):
        try:
            names = list(self.personas.keys())
            if DEFAULT_PERSONA_NAME not in names:
                names.insert(0, DEFAULT_PERSONA_NAME)
            self.persona_option.configure(values=names)
            if self.selected_persona_name not in names:
                self.selected_persona_name = DEFAULT_PERSONA_NAME
            self.persona_option.set(self.selected_persona_name)
        except Exception:
            pass

    def _save_or_update_persona(self):
        name = (self.persona_name_entry.get() or self.selected_persona_name or "").strip()
        content = self.persona_text.get("1.0", "end").strip()
        if not name:
            messagebox.showinfo("提示", "请输入人设名称")
            return
        if not content:
            messagebox.showinfo("提示", "人设内容不能为空")
            return
        # 写入并保存
        self.personas[name] = content
        try:
            _save_personas_to_disk(self.personas)
        except Exception:
            pass
        self.selected_persona_name = name
        self._refresh_persona_menu()
        self._append_info(f"已保存/更新人设：{name}")

    def _delete_persona(self):
        name = self.selected_persona_name
        if not name or name == DEFAULT_PERSONA_NAME:
            messagebox.showinfo("提示", "默认人设不可删除")
            return
        if name in self.personas:
            try:
                del self.personas[name]
                _save_personas_to_disk(self.personas)
            except Exception:
                pass
            self.selected_persona_name = DEFAULT_PERSONA_NAME
            self._refresh_persona_menu()
            self._on_select_persona(DEFAULT_PERSONA_NAME)
            self._append_info(f"已删除人设：{name}")

    def _reset_to_default(self):
        self.selected_persona_name = DEFAULT_PERSONA_NAME
        self._on_select_persona(DEFAULT_PERSONA_NAME)

    def apply_persona(self):
        content = self.persona_text.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("提示", "人设不能为空")
            return
        # 替换第一条system
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = content
        else:
            self.messages.insert(0, {"role": "system", "content": content})
        self._append_info("已应用新的系统人设。")

    def _set_placeholder(self):
        try:
            self._placeholder_active = True
            self.input_box.configure(text_color="#999999")
            self.input_box.delete("1.0", "end")
            self.input_box.insert("1.0", self.placeholder_text)
        except Exception:
            pass

    def _clear_placeholder(self):
        try:
            if getattr(self, "_placeholder_active", False):
                self._placeholder_active = False
                self.input_box.delete("1.0", "end")
                self.input_box.configure(text_color="black")
        except Exception:
            pass

    def _maybe_restore_placeholder(self):
        try:
            if not self.input_box.get("1.0", "end").strip():
                self._set_placeholder()
        except Exception:
            pass

    def _get_input(self) -> str:
        # 如果占位符处于激活状态，视为无输入
        if getattr(self, "_placeholder_active", False):
            return ""
        return self.input_box.get("1.0", "end").strip()

    def on_send(self):
        user_text = self._get_input()
        if not user_text:
            messagebox.showinfo("提示", "请输入要扩写的主题或指令")
            return
        self.input_box.delete("1.0", "end")
        self._set_placeholder()
        self._append_user(user_text)
        self.send_btn.configure(state="disabled", text="生成中…")
        threading.Thread(target=self._call_api, args=(user_text,), daemon=True).start()

    def _call_api(self, user_text: str):
        try:
            msgs = list(self.messages) + [{"role": "user", "content": user_text}]
            reply = zhipu_chat_completion(msgs, model="glm-4-flash")
        except Exception as e:
            logger.error(f"prompt chat failed: {e}")
            reply = f"[对话失败] {e}"
        self.after(0, lambda: self._finish_reply(user_text, reply))

    def _finish_reply(self, user_text: str, reply: str):
        self.messages.append({"role": "user", "content": user_text})
        self.messages.append({"role": "assistant", "content": reply})
        self._append_assistant(reply)
        main_text = self._extract_main_prompt(reply)
        if main_text and self._on_set_last:
            try:
                self._on_set_last(main_text)
            except Exception:
                pass
        self.send_btn.configure(state="normal", text="发送 /expand")

    def _extract_main_prompt(self, text: str) -> str:
        # 解析“最终提示词：”后的第一段作为插入文本
        markers = ["最终提示词：", "最终提示词:", "最终可复制的提示词："]
        for m in markers:
            if m in text:
                part = text.split(m,1)[1].strip()
                # 截断到下一节标题
                for stop in ["要点：", "要点:", "模型适配建议", "要点卡片"]:
                    idx = part.find(stop)
                    if idx != -1:
                        part = part[:idx].strip()
                        break
                return part.strip()
        return text.strip()

    # --- UI 渲染 ---
    def _append_info(self, text: str):
        self._append_bubble(text, who="info")
    def _append_user(self, text: str):
        self._append_bubble(text, who="user")
    def _append_assistant(self, text: str):
        frame = self._append_bubble(text, who="assistant")
        main = self._extract_main_prompt(text)
        btn = ctk.CTkButton(frame, text="插入翻译输入框", width=140,
                             command=lambda t=main: self._do_insert(t))
        btn.pack(anchor="w", pady=(6,2))

    def _do_insert(self, text: str):
        if not text:
            messagebox.showinfo("提示", "无可插入内容")
            return
        if self._on_insert:
            try:
                self._on_insert(text)
                return
            except Exception as e:
                logger.error(f"insert callback failed: {e}")
        # 兜底：复制到剪贴板
        try:
            import pyperclip
            pyperclip.copy(text)
            messagebox.showinfo("提示", "已复制到剪贴板，可手动粘贴至翻译输入框")
        except Exception:
            pass

    def _append_bubble(self, text: str, who: str = "assistant"):
        holder = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        holder.pack(fill="x", pady=4)
        label = "AI" if who=="assistant" else ("你" if who=="user" else "提示")
        tag_bg = "#e1f3ff" if who=="assistant" else ("#f1f5f9" if who=="user" else "#f5f5f5")
        tag = ctk.CTkLabel(holder, text=label, width=38, fg_color=tag_bg, text_color="#333")
        tag.pack(side="left", padx=(6,6), pady=6)
        # 气泡底色区分
        bubble_bg = "#E9F5FF" if who=="assistant" else ("#F5F7FA" if who=="user" else "#F7F7F7")
        frame = ctk.CTkFrame(holder, fg_color=bubble_bg, corner_radius=8)
        frame.pack(side="left", fill="x", expand=True, padx=(0,10), pady=6)
        txt = ctk.CTkTextbox(frame, height=min(240, max(80, int(len(text)/1.8))), wrap="word", fg_color=bubble_bg, text_color="#222")
        txt.pack(fill="x", expand=True)
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        return frame

    def _toggle_quick_panel(self):
        self._quick_collapsed = not getattr(self, "_quick_collapsed", False)
        if self._quick_collapsed:
            try:
                self.quick_panel.pack_forget()
            except Exception:
                pass
            if hasattr(self, "quick_toggle_btn"):
                self.quick_toggle_btn.configure(text="快捷指令 ▸")
        else:
            try:
                self.quick_panel.pack(fill="x")
            except Exception:
                pass
            if hasattr(self, "quick_toggle_btn"):
                self.quick_toggle_btn.configure(text="快捷指令 ▾")

    def _build_quick_panels(self, parent):
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.pack(fill="x", pady=(6,6))
        self.quick_tabs = ctk.CTkTabview(panel)
        self.quick_tabs.pack(fill="x")
        tab_enhance = self.quick_tabs.add("增强")
        tab_lens = self.quick_tabs.add("镜头")
        # 可滚动区域，容纳大量按钮
        self.enhance_frame = ctk.CTkScrollableFrame(tab_enhance, height=110, fg_color="transparent")
        self.enhance_frame.pack(fill="x", expand=True)
        self.lens_frame = ctk.CTkScrollableFrame(tab_lens, height=110, fg_color="transparent")
        self.lens_frame.pack(fill="x", expand=True)
        self._populate_quick_buttons()

    def _populate_quick_buttons(self):
        # 清空
        for w in list(self.enhance_frame.winfo_children()):
            w.destroy()
        for w in list(self.lens_frame.winfo_children()):
            w.destroy()
        # 默认命令集合
        enhance_defaults = ["更亮", "更写实", "更马卡龙", "更电影感", "更干净背景", "增加体积雾"]
        lens_defaults = [
            "35mm人像", "50mm人像", "85mm人像", "105mm微距人像", "135mm人像压缩",
            "24-70mm人像", "70-200mm人像",
            "f/1.2大光圈", "f/1.4大光圈", "f/1.8浅景深",
            "柔焦镜", "移轴人像", "远摄压缩", "奶油散景", "背景虚化强化"
        ]
        enhance_all = enhance_defaults + list(self.custom_enhance_labels)
        lens_all = lens_defaults + list(self.custom_lens_labels)
        # 栅格化布局
        def build_grid(frame, labels: List[str], cols: int = 6):
            for c in range(cols):
                frame.grid_columnconfigure(c, weight=1)
            for i, label in enumerate(labels):
                r, c = divmod(i, cols)
                btn = ctk.CTkButton(frame, text=label, width=110, command=lambda t=label: self._append_to_input(t))
                btn.grid(row=r, column=c, padx=4, pady=4, sticky="ew")
        build_grid(self.enhance_frame, enhance_all)
        build_grid(self.lens_frame, lens_all)
        # 添加“自定义+”按钮
        def add_custom_button(frame, kind: str, row_offset: int = 0):
            cols = 6
            r, c = divmod((len(frame.winfo_children())), cols)
            add_btn = ctk.CTkButton(frame, text="添加自定义+", width=110, fg_color="#5a9", command=lambda: self._add_custom_quick(kind))
            add_btn.grid(row=r, column=c, padx=4, pady=4, sticky="ew")
        add_custom_button(self.enhance_frame, "enhance")
        add_custom_button(self.lens_frame, "lens")

    def _add_custom_quick(self, kind: str):
        text = simpledialog.askstring("添加自定义命令", "请输入要插入的命令文本：", parent=self)
        if not text:
            return
        if kind == "enhance":
            self.custom_enhance_labels.append(text)
        else:
            self.custom_lens_labels.append(text)
        self._populate_quick_buttons()


def open_prompt_chat_dialog(parent: tk.Misc,
                             on_set_last_output: Optional[Callable[[str], None]] = None,
                             on_insert_to_input: Optional[Callable[[str], None]] = None):
    dlg = ChatPromptEngineerDialog(parent, on_set_last_output, on_insert_to_input)
    dlg.grab_set()
    return dlg