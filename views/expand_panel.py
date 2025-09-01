import threading
import tkinter as tk
import customtkinter as ctk
import tkinter.messagebox as messagebox
import re
import json
import os
from typing import Callable, List, Dict, Optional

try:
    # 复用现有的预设加载逻辑
    from main import load_expand_presets
except Exception:
    def load_expand_presets():
        return []

# 简单本地兜底：基于规则的扩写（离线可用）
_ADJ_BANK_ZH = {
    "轻": ["清晰", "自然", "精炼"],
    "中": ["细致", "生动", "层次分明", "富有画面感"],
    "重": ["极为细腻", "质感丰富", "强烈氛围", "结构清晰", "高度凝练"],
}
_ADJ_BANK_EN = {
    "轻": ["clear", "natural", "concise"],
    "中": ["detailed", "vivid", "layered", "evocative"],
    "重": ["highly detailed", "rich texture", "strong atmosphere", "well-structured", "highly concise"],
}
_NEGATIVE_COMMON = {
    "zh": "避免低质量、模糊、畸形、重复元素、构图混乱、过度修饰。",
    "en": "avoid low quality, blurry, deformed, duplicate elements, poor composition, over-embellishment",
}

# 常见占位符建议选项（快速填充）


# 新增：导入扩写开关构建器
try:
    from services.expand_switches import build_hints as _build_switch_hints, OPTIONS as _SWITCH_OPTIONS
except Exception:
    _SWITCH_OPTIONS = {}
    def _build_switch_hints(selected, lang):
        return ""

def _build_system_preset(base_content: str, strength: str, length: str, tone: str, lang: str,
                          use_tags: bool, tags: Dict[str, List[str]], use_negative: bool,
                          variant_hint: Optional[str] = None, extra_hints: str = "") -> str:
    # 长度提示
    length_map_zh = {"短": "请控制在60字以内", "中": "请控制在120字以内", "长": "请控制在200字以内"}
    length_map_en = {"短": "limit to within 60 characters", "中": "limit to within 120 characters", "长": "limit to within 200 characters"}

    # 语气提示
    tone_map_zh = {
        "正式": "语气需正式、准确", "活泼": "语气更生动活泼", "简洁": "语言简洁干练",
        "技术": "技术风格，强调参数与要点", "营销": "更具吸引力与行动号召"
    }
    tone_map_en = {
        "正式": "use formal and precise tone", "活泼": "use lively and vivid tone",
        "简洁": "be concise and to the point", "技术": "technical tone, emphasize parameters",
        "营销": "marketing tone with CTA"
    }

    is_en = (lang == "English")
    length_hint = length_map_en[length] if is_en else length_map_zh[length]
    tone_hint = tone_map_en[tone] if is_en else tone_map_zh[tone]

    # 强度 -> 形容词
    adjs = _ADJ_BANK_EN[strength] if is_en else _ADJ_BANK_ZH[strength]
    adj_hint = (", ".join(adjs)) if is_en else "、".join(adjs)

    # 标签拼接
    tag_text = ""
    if use_tags and tags:
        head = tags.get("head", []) or []
        tail = tags.get("tail", []) or []
        if is_en:
            tag_text = f"Use styles/elements: head({', '.join(head)}), tail({', '.join(tail)})."
        else:
            tag_text = f"可参考以下风格/要素：头部({', '.join(head)}), 尾部({', '.join(tail)})。"

    negative_text = _NEGATIVE_COMMON['en'] if (use_negative and is_en) else (_NEGATIVE_COMMON['zh'] if use_negative else "")

    extra = []
    if variant_hint:
        extra.append(variant_hint)
    if extra_hints:
        extra.append(extra_hints)

    parts = [
        base_content.strip(),
        ("Please write in English." if is_en else "请使用中文输出。"),
        (f"Style hints: {adj_hint}" if is_en else f"风格倾向：{adj_hint}"),
        length_hint,
        tone_hint,
        tag_text,
        (f"Negative: {negative_text}" if (use_negative and is_en) else negative_text),
    ] + extra

    return "\n".join([p for p in parts if p])


def _local_rules_expand(text: str, lang: str, strength: str, tone: str,
                        tags: Dict[str, List[str]], use_negative: bool, n: int) -> List[str]:
    is_en = (lang == "English")
    adjs = _ADJ_BANK_EN[strength] if is_en else _ADJ_BANK_ZH[strength]
    negative = _NEGATIVE_COMMON['en'] if (use_negative and is_en) else (_NEGATIVE_COMMON['zh'] if use_negative else "")
    tag_join = ", ".join((tags.get("head", []) or []) + (tags.get("tail", []) or []))
    outputs = []
    for i in range(n):
        # 简单规则：用不同形容词采样 + 标签拼接
        adj_sample = ", ".join(adjs[:(i % max(1, len(adjs)))+1]) if is_en else "、".join(adjs[:(i % max(1, len(adjs)))+1])
        if is_en:
            s = f"{text.strip()} — refined with {adj_sample}."
            if tag_join:
                s += f" Styles: {tag_join}."
            if negative:
                s += f" Avoid: {negative}."
        else:
            s = f"{text.strip()}——以{adj_sample}方式细化。"
            if tag_join:
                s += f" 风格要素：{tag_join}。"
            if negative:
                s += f" 负向：{negative}。"
        outputs.append(s)
    return outputs


class ExpandPanel(ctk.CTkToplevel):
    def __init__(self, parent, initial_text: str,
                 get_selected_tags_cb: Optional[Callable[[], Dict[str, List[str]]]] = None,
                 on_apply: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.title("AI 智能扩写")
        self.geometry("820x600")
        self.resizable(True, True)
        # 设置为相对父窗口的模态，并提高层级，避免被其它窗口遮挡
        try:
            self.transient(parent)
            self.attributes('-topmost', True)
            self.grab_set()
            self.focus_force()
        except Exception:
            pass
        self.parent = parent
        self.get_selected_tags_cb = get_selected_tags_cb
        self.on_apply = on_apply

        # 状态变量
        self.var_strength = tk.StringVar(value="中")
        self.var_length = tk.StringVar(value="中")
        self.var_tone = tk.StringVar(value="简洁")
        self.var_lang = tk.StringVar(value="中文")
        self.var_count = tk.IntVar(value=3)
        self.var_use_tags = tk.BooleanVar(value=True)
        self.var_use_negative = tk.BooleanVar(value=True)

        self.presets = load_expand_presets() or []
        self.var_preset_idx = tk.IntVar(value=0)

        # 功能开关变量映射（人物/技术/构图/视角）
        self.switch_vars: Dict[str, tk.Variable] = {}

        # 布局
        self._build_ui(initial_text)

    def _build_ui(self, initial_text: str):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # 顶部参数区
        params = ctk.CTkFrame(main)
        params.pack(fill="x", padx=6, pady=(0, 8))

        # 预设下拉
        ctk.CTkLabel(params, text="预设：").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        titles = [p.get("title", f"预设{i+1}") for i, p in enumerate(self.presets)] or ["默认预设"]
        self.cb_preset = ctk.CTkComboBox(params, values=titles, state="readonly",
                                         command=lambda _: self._update_preset_preview())
        self.cb_preset.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        self.cb_preset.set(titles[0])
        
        # 预设管理按钮
        preset_manage_btn = ctk.CTkButton(params, text="管理预设", width=80, height=28,
                                          command=self._open_preset_manager)
        preset_manage_btn.grid(row=0, column=2, padx=(6, 0), pady=6, sticky="w")

        # 强度
        ctk.CTkLabel(params, text="强度").grid(row=0, column=3, padx=6, pady=6)
        ctk.CTkComboBox(params, values=["轻", "中", "重"], variable=self.var_strength, state="readonly").grid(row=0, column=4, padx=6, pady=6)
        # 长度
        ctk.CTkLabel(params, text="长度").grid(row=0, column=5, padx=6, pady=6)
        ctk.CTkComboBox(params, values=["短", "中", "长"], variable=self.var_length, state="readonly").grid(row=0, column=6, padx=6, pady=6)
        # 语气
        ctk.CTkLabel(params, text="语气").grid(row=1, column=0, padx=6, pady=6)
        ctk.CTkComboBox(params, values=["正式", "活泼", "简洁", "技术", "营销"], variable=self.var_tone, state="readonly").grid(row=1, column=1, padx=6, pady=6)
        # 语言
        ctk.CTkLabel(params, text="语言").grid(row=1, column=3, padx=6, pady=6)
        ctk.CTkComboBox(params, values=["中文", "English"], variable=self.var_lang, state="readonly").grid(row=1, column=4, padx=6, pady=6)
        # 数量
        ctk.CTkLabel(params, text="数量").grid(row=1, column=5, padx=6, pady=6)
        ctk.CTkComboBox(params, values=["1", "2", "3"], command=lambda v: self.var_count.set(int(v))).grid(row=1, column=6, padx=6, pady=6)

        # 复选
        opts = ctk.CTkFrame(main)
        opts.pack(fill="x", padx=6, pady=(0, 8))
        ctk.CTkCheckBox(opts, text="使用当前已选标签参与扩写", variable=self.var_use_tags).pack(side="left", padx=6)
        ctk.CTkCheckBox(opts, text="加入常见负向提示（可选）", variable=self.var_use_negative).pack(side="left", padx=6)

        # 新增：功能开关分组
        switches = ctk.CTkFrame(main)
        switches.pack(fill="x", padx=6, pady=(0, 8))
        ctk.CTkLabel(switches, text="功能开关（可选）：人物 / 技术信息 / 视觉构图 / 视角控制").pack(anchor="w", padx=6, pady=(6, 2))

        grp = ctk.CTkFrame(switches)
        grp.pack(fill="x", padx=6, pady=(0, 6))

        def _mk_row(row: int, label: str, key: str, opt_key: str):
            ctk.CTkLabel(grp, text=label).grid(row=row, column=0, padx=6, pady=4, sticky="w")
            var_on = tk.BooleanVar(value=False)
            self.switch_vars[f"{key}_on"] = var_on
            cb_on = ctk.CTkCheckBox(grp, text="启用", variable=var_on)
            cb_on.grid(row=row, column=1, padx=6, pady=4, sticky="w")
            val = tk.StringVar(value=( _SWITCH_OPTIONS.get(opt_key, [""])[0] if _SWITCH_OPTIONS.get(opt_key) else "" ))
            self.switch_vars[f"{key}_val"] = val
            combo = ctk.CTkComboBox(grp, values=_SWITCH_OPTIONS.get(opt_key, [""]), variable=val, state=("readonly" if _SWITCH_OPTIONS.get(opt_key) else "normal"))
            combo.grid(row=row, column=2, padx=6, pady=4, sticky="we")
            grp.grid_columnconfigure(2, weight=1)

        # 人物类
        _mk_row(0, "人物姿态", "person_posture", "posture")
        _mk_row(1, "年龄", "person_age", "age")

        # 技术信息类
        _mk_row(2, "光照", "tech_lighting", "lighting")
        _mk_row(3, "光源类型", "tech_light_type", "light_type")
        _mk_row(4, "相机角度", "tech_camera_angle", "camera_angle")
        # 详细参数允许自由输入
        ctk.CTkLabel(grp, text="详细参数").grid(row=5, column=0, padx=6, pady=4, sticky="w")
        var_params_on = tk.BooleanVar(value=False)
        self.switch_vars["tech_params_on"] = var_params_on
        ctk.CTkCheckBox(grp, text="启用", variable=var_params_on).grid(row=5, column=1, padx=6, pady=4, sticky="w")
        var_params_val = tk.StringVar(value="")
        self.switch_vars["tech_params_val"] = var_params_val
        ctk.CTkEntry(grp, textvariable=var_params_val).grid(row=5, column=2, padx=6, pady=4, sticky="we")

        # 视觉构图类
        _mk_row(6, "美学质量", "comp_aesthetic_quality", "aesthetic_quality")
        _mk_row(7, "构图风格", "comp_composition_style", "composition_style")
        _mk_row(8, "景深", "comp_dof", "dof")

        # 视角控制类
        _mk_row(9, "镜头类型", "pov_lens_type", "lens_type")
        _mk_row(10, "视角高度", "pov_eye_level", "eye_level")

        # 预设预览
        preview = ctk.CTkFrame(main)
        preview.pack(fill="x", padx=6, pady=(0, 8))
        ctk.CTkLabel(preview, text="预设内容预览：").pack(anchor="w", padx=6, pady=(6, 0))
        self.txt_preset = ctk.CTkTextbox(preview, height=80)
        self.txt_preset.pack(fill="x", padx=6, pady=6)
        self._update_preset_preview()

        # 占位符功能已下线：不再展示变量占位符区块

        # 输入与结果
        io = ctk.CTkFrame(main)
        io.pack(fill="both", expand=True, padx=6, pady=6)

        left = ctk.CTkFrame(io)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(left, text="待扩写内容：").pack(anchor="w", padx=6, pady=(6, 0))
        self.txt_input = ctk.CTkTextbox(left)
        self.txt_input.pack(fill="both", expand=True, padx=6, pady=6)
        if initial_text:
            self.txt_input.insert("end", initial_text)

        right = ctk.CTkFrame(io)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        top_actions = ctk.CTkFrame(right)
        top_actions.pack(fill="x", padx=6, pady=(6, 0))
        self.btn_generate = ctk.CTkButton(top_actions, text="生成候选", command=self._on_generate)
        self.btn_generate.pack(side="left")
        self.lbl_status = ctk.CTkLabel(top_actions, text="")
        self.lbl_status.pack(side="left", padx=8)

        self.result_container = ctk.CTkScrollableFrame(right)
        self.result_container.pack(fill="both", expand=True, padx=6, pady=6)

    # 占位符功能已下线：移除占位符提取与输入重建方法

    def _update_preset_preview(self):
        # 安全获取当前选中的预设索引
        idx = 0
        try:
            # 优先通过显示文本匹配
            title = self.cb_preset.get()
            for i, p in enumerate(self.presets):
                if p.get("title") == title:
                    idx = i
                    break
        except Exception:
            idx = 0
        
        content = ""
        if 0 <= idx < len(self.presets):
            content = self.presets[idx].get("content", "")
        
        self.txt_preset.delete("1.0", "end")
        self.txt_preset.insert("end", content)
        # 占位符功能下线：不再重建占位输入

    def _collect_tags(self) -> Dict[str, List[str]]:
        if self.var_use_tags.get() and self.get_selected_tags_cb:
            try:
                tags = self.get_selected_tags_cb() or {}
                return {"head": tags.get("head", []), "tail": tags.get("tail", [])}
            except Exception:
                return {"head": [], "tail": []}
        return {"head": [], "tail": []}

    def _open_preset_manager(self):
        """打开预设管理器"""
        PresetManagerDialog(self, self.presets, self._on_presets_changed)
    
    def _on_presets_changed(self, new_presets):
        """预设变更回调"""
        self.presets = new_presets
        # 保存到文件
        try:
            import json
            with open("expand_presets.json", "w", encoding="utf-8") as f:
                json.dump(new_presets, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存预设失败: {e}")
        
        # 更新下拉框
        titles = [p.get("title", f"预设{i+1}") for i, p in enumerate(self.presets)] or ["默认预设"]
        self.cb_preset.configure(values=titles)
        if titles:
            self.cb_preset.set(titles[0])
        self._update_preset_preview()

    def _on_generate(self):
        text = self.txt_input.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("提示", "请输入要扩写的内容")
            return
        n = max(1, min(3, self.var_count.get() or 3))
        strength = self.var_strength.get()
        length = self.var_length.get()
        tone = self.var_tone.get()
        lang = self.var_lang.get()
        use_negative = self.var_use_negative.get()
        tags = self._collect_tags()
        base_preset = self.txt_preset.get("1.0", "end").strip() or "请优化并扩写下列内容"

        # 收集功能开关
        selected_switches: Dict[str, Dict[str, Optional[str]]] = {
            "person": {
                "posture": (self.switch_vars.get("person_posture_val").get().strip() if self.switch_vars.get("person_posture_on").get() else None),
                "age": (self.switch_vars.get("person_age_val").get().strip() if self.switch_vars.get("person_age_on").get() else None),
            },
            "tech": {
                "lighting": (self.switch_vars.get("tech_lighting_val").get().strip() if self.switch_vars.get("tech_lighting_on").get() else None),
                "light_type": (self.switch_vars.get("tech_light_type_val").get().strip() if self.switch_vars.get("tech_light_type_on").get() else None),
                "camera_angle": (self.switch_vars.get("tech_camera_angle_val").get().strip() if self.switch_vars.get("tech_camera_angle_on").get() else None),
                "params": (self.switch_vars.get("tech_params_val").get().strip() if self.switch_vars.get("tech_params_on").get() else None),
            },
            "composition": {
                "aesthetic_quality": (self.switch_vars.get("comp_aesthetic_quality_val").get().strip() if self.switch_vars.get("comp_aesthetic_quality_on").get() else None),
                "composition_style": (self.switch_vars.get("comp_composition_style_val").get().strip() if self.switch_vars.get("comp_composition_style_on").get() else None),
                "dof": (self.switch_vars.get("comp_dof_val").get().strip() if self.switch_vars.get("comp_dof_on").get() else None),
            },
            "pov": {
                "lens_type": (self.switch_vars.get("pov_lens_type_val").get().strip() if self.switch_vars.get("pov_lens_type_on").get() else None),
                "eye_level": (self.switch_vars.get("pov_eye_level_val").get().strip() if self.switch_vars.get("pov_eye_level_on").get() else None),
            },
        }

        extra_hints = _build_switch_hints(selected_switches, "English" if lang == "English" else "中文")

        # 占位符功能已下线：仅做温和清理，移除形如 {变量} 的残留以保持兼容
        resolved_preset = re.sub(r"\{[^{}]+\}", "", base_preset) if base_preset else ""

        # 清空结果
        for w in list(self.result_container.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        self.lbl_status.configure(text="生成中…")
        self.btn_generate.configure(state="disabled")

        def worker():
            results: List[str] = []
            # 在线优先
            try:
                from services.api import zhipu_text_expand  # 延迟导入，避免循环依赖
                for i in range(n):
                    sys_preset = _build_system_preset(
                        resolved_preset, strength, length, tone, lang,
                        use_tags=self.var_use_tags.get(), tags=tags, use_negative=use_negative,
                        variant_hint=(f"Provide a different wording for variation #{i+1}." if lang == "English" else f"请给出与其他版本措辞不同的第{i+1}个版本。"),
                        extra_hints=extra_hints,
                    )
                    ans = zhipu_text_expand(text, sys_preset)
                    if not ans or ans.startswith("["):
                        raise RuntimeError(str(ans))
                    results.append(ans)
            except Exception:
                # 兜底：本地规则扩写
                results = _local_rules_expand(text, lang, strength, tone, tags, use_negative, n)

            def on_ui():
                self.lbl_status.configure(text=f"生成完成，共 {len(results)} 个候选")
                self.btn_generate.configure(state="normal")
                for idx, r in enumerate(results, start=1):
                    card = ctk.CTkFrame(self.result_container)
                    card.pack(fill="x", padx=4, pady=6)
                    ctk.CTkLabel(card, text=f"候选 #{idx}").pack(anchor="w", padx=6, pady=(6, 0))
                    txt = ctk.CTkTextbox(card, height=110, wrap="word")
                    txt.pack(fill="x", padx=6, pady=6)
                    txt.insert("end", r)
                    bar = ctk.CTkFrame(card)
                    bar.pack(fill="x", padx=6, pady=(0, 6))

                    def apply_insert(s=r):
                        if self.on_apply:
                            self.on_apply(s)
                            self.destroy()

                    def copy_text(s=r):
                        self.clipboard_clear()
                        self.clipboard_append(s)
                        messagebox.showinfo("已复制", "候选内容已复制到剪贴板")

                    ctk.CTkButton(bar, text="插入到输入框", command=apply_insert).pack(side="left", padx=(0, 6))
                    ctk.CTkButton(bar, text="复制", command=copy_text).pack(side="left")

            self.after(0, on_ui)

        threading.Thread(target=worker, daemon=True).start()


class PresetManagerDialog(ctk.CTkToplevel):
    def __init__(self, parent, presets: List[Dict], callback: Callable[[List[Dict]], None]):
        super().__init__(parent)
        self.title("预设管理器")
        self.geometry("600x500")
        self.resizable(True, True)
        try:
            self.transient(parent)
            self.grab_set()
        except Exception:
            pass
        
        self.presets = presets.copy()
        self.callback = callback
        self._build_ui()
    
    def _build_ui(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=12, pady=12)
        
        # 顶部按钮
        top_bar = ctk.CTkFrame(main)
        top_bar.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(top_bar, text="新增预设", command=self._add_preset).pack(side="left", padx=(0, 6))
        ctk.CTkButton(top_bar, text="编辑预设", command=self._edit_preset).pack(side="left", padx=(0, 6))
        ctk.CTkButton(top_bar, text="删除预设", command=self._delete_preset).pack(side="left", padx=(0, 6))
        
        # 预设列表
        self.listbox = tk.Listbox(main, height=15)
        self.listbox.pack(fill="both", expand=True, pady=(0, 8))
        self._refresh_list()
        
        # 底部按钮
        bottom_bar = ctk.CTkFrame(main)
        bottom_bar.pack(fill="x")
        ctk.CTkButton(bottom_bar, text="保存", command=self._save).pack(side="right", padx=(6, 0))
        ctk.CTkButton(bottom_bar, text="取消", command=self.destroy).pack(side="right")
    
    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for i, preset in enumerate(self.presets):
            title = preset.get("title", f"预设{i+1}")
            self.listbox.insert(tk.END, title)
    
    def _add_preset(self):
        dialog = PresetEditDialog(self, {"title": "新预设", "content": ""}, self._on_preset_edited)
    
    def _edit_preset(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个预设")
            return
        idx = selection[0]
        preset = self.presets[idx]
        dialog = PresetEditDialog(self, preset, lambda p: self._on_preset_edited(p, idx))
    
    def _delete_preset(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个预设")
            return
        idx = selection[0]
        if messagebox.askyesno("确认", "确定要删除这个预设吗？"):
            del self.presets[idx]
            self._refresh_list()
    
    def _on_preset_edited(self, preset: Dict, idx: Optional[int] = None):
        if idx is None:
            self.presets.append(preset)
        else:
            self.presets[idx] = preset
        self._refresh_list()
    
    def _save(self):
        self.callback(self.presets)
        self.destroy()


class PresetEditDialog(ctk.CTkToplevel):
    def __init__(self, parent, preset: Dict, callback: Callable[[Dict], None]):
        super().__init__(parent)
        self.title("编辑预设")
        self.geometry("500x400")
        try:
            self.transient(parent)
            self.grab_set()
        except Exception:
            pass
        
        self.preset = preset.copy()
        self.callback = callback
        self._build_ui()
    
    def _build_ui(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=12, pady=12)
        
        # 标题输入
        ctk.CTkLabel(main, text="预设标题：").pack(anchor="w", pady=(0, 4))
        self.title_entry = ctk.CTkEntry(main)
        self.title_entry.pack(fill="x", pady=(0, 8))
        self.title_entry.insert(0, self.preset.get("title", ""))
        
        # 内容输入
        ctk.CTkLabel(main, text="预设内容：").pack(anchor="w", pady=(0, 4))
        self.content_text = ctk.CTkTextbox(main)
        self.content_text.pack(fill="both", expand=True, pady=(0, 8))
        self.content_text.insert("end", self.preset.get("content", ""))
        
        # 提示信息
        tip = ctk.CTkLabel(main, text="提示：可直接编写预设内容；如预设中存在 {…} 将在生成时自动清理。", 
                          text_color="gray")
        tip.pack(anchor="w", pady=(0, 8))
        
        # 按钮
        btn_frame = ctk.CTkFrame(main)
        btn_frame.pack(fill="x")
        ctk.CTkButton(btn_frame, text="保存", command=self._save).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_frame, text="取消", command=self.destroy).pack(side="right")
    
    def _save(self):
        title = self.title_entry.get().strip()
        content = self.content_text.get("1.0", "end").strip()
        
        if not title:
            messagebox.showwarning("警告", "请输入预设标题")
            return
        if not content:
            messagebox.showwarning("警告", "请输入预设内容")
            return
        
        self.callback({"title": title, "content": content})
        self.destroy()


def open_expand_panel(parent, initial_text: str,
                      get_selected_tags_cb: Optional[Callable[[], Dict[str, List[str]]]] = None,
                      on_apply: Optional[Callable[[str], None]] = None):
    panel = ExpandPanel(parent, initial_text, get_selected_tags_cb, on_apply)
    panel.focus_force()
    return panel